import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.config import Settings
from core.exception_store import ExceptionStore
from core.jobs import JobBook
from core.kill_switch import KillSwitchBoard
from core.timeutil import utcnow
from core.bootstrap import vault_for
from core.vault import alert_expiring_credentials
from youtube.modules.diagnostician import Funnel, diagnose
from youtube.modules.publisher import InMemoryVideoStore, PublishRequest, publish
from youtube.modules.ypp import ypp_progress
from youtube.oauth_flow import exchange_code, store_tokens
from youtube.pipeline import run_private_dry_run
from youtube.pipeline_e2e import YouTubePipeline
from youtube.providers import authorization_url
from youtube.providers_factory import analytics_client, youtube_client
from youtube.quota import QuotaLedger
from youtube.store import DbVideoStore


class SecretIn(BaseModel):
    name: str
    value: str
    expires_at: str | None = None


class PublishIn(BaseModel):
    idempotency_key: str
    title: str
    description: str = "Sources listed in the dry run."
    privacy_status: str = "private"
    dry_run: bool = True
    made_for_kids: bool | None = False
    contains_synthetic_media: bool | None = True
    uses_ai_voice: bool = True
    uses_realistic_ai_imagery: bool = False
    provisional_research: bool = True


class DiagnoseIn(BaseModel):
    age_hours: float
    views: float = 100
    channel_median_views: float = 100
    impressions_ratio: float = 1
    ctr: float = 0.05
    retention_first_30: float = 0.5
    retention_mid: float = 0.5
    subscribers_per_1000: float = 4
    low_rpm_traffic_share: float = 0.1
    channel_wide_drop: bool = False
    competitors_also_dropped: bool = False
    strike: bool = False
    limited_ads: bool = False


class YoutubeState:
    def __init__(self, settings: Settings | None = None, session=None, circuits=None):
        settings = settings or Settings()
        self.settings = settings
        self.session = session
        self.vault = vault_for(session, settings)
        self.kill = KillSwitchBoard(session)
        self.ledger = QuotaLedger.from_env()
        self.jobs = JobBook(session)
        self.store = DbVideoStore(session) if session is not None else InMemoryVideoStore()
        self.client = youtube_client(settings, self.vault)
        if circuits:
            from core.provider_plane import with_circuit

            with_circuit(self.client, circuits.get("youtube"), "insert")
        self.audit_approved = settings.yt_audit_approved
        self.oauth_client_id = settings.yt_client_id or "replace-me.apps.googleusercontent.com"
        self.redirect_uri = settings.yt_redirect_uri
        self.exceptions = ExceptionStore(session)
        self.pipeline = YouTubePipeline(
            audit_approved=self.audit_approved,
            kill=self.kill,
            store=self.store,
            client=self.client,
            ledger=self.ledger,
            jobs=self.jobs,
            exceptions=self.exceptions,
            analytics=analytics_client(settings, self.vault),
            settings=settings,
            vault=self.vault,
            session=session,
            notifier=__import__("core.notify", fromlist=["NotifierHub"]).NotifierHub(),
        )
        self.last_dry_run: dict | None = None


def router(state: YoutubeState) -> APIRouter:
    api = APIRouter(prefix="/youtube", tags=["youtube"])

    @api.get("/oauth/start")
    def oauth_start():
        state_token = uuid.uuid4().hex
        url = authorization_url(state.oauth_client_id, state.redirect_uri, state_token)
        return {"url": url, "state": state_token}

    @api.get("/oauth/callback")
    def oauth_callback(code: str, state: str = ""):
        if not state.settings.yt_client_secret:
            raise HTTPException(400, "YT_CLIENT_SECRET is not configured")
        tokens = exchange_code(
            state.oauth_client_id,
            state.settings.yt_client_secret,
            state.redirect_uri,
            code,
        )
        store_tokens(state.vault, tokens)
        return {"stored": True, "scopes_ok": True, "state": state}

    @api.post("/vault/secrets")
    def put_secret(body: SecretIn):
        state.vault.put(body.name, body.value, body.expires_at)
        return {"stored": body.name}

    @api.get("/vault/secrets/{name}")
    def get_secret(name: str):
        try:
            state.vault.get(name)
        except Exception as exc:
            raise HTTPException(404, "unknown secret") from exc
        return {"name": name, "stored": True}

    @api.get("/vault/health")
    def vault_health():
        alerts = alert_expiring_credentials(state.vault, state.exceptions, utcnow())
        return {"expiring": alerts}

    @api.post("/kill-switch")
    def set_kill(active: bool, reason: str = ""):
        state.kill.set("youtube", active, reason)
        if active:
            state.exceptions.add("kill_switch", reason or "manual")
        return {"active": state.kill.active("youtube")}

    @api.get("/quota")
    def quota():
        return {"used": state.ledger.used, "reserved": state.ledger.reserved, "remaining": state.ledger.remaining}

    @api.post("/publish")
    def publish_video(body: PublishIn):
        from core.errors import MissingCredentials
        from core.provider_plane import is_production, youtube_client_mode

        if not body.dry_run and is_production(state.settings):
            try:
                if youtube_client_mode(state.settings) != "live":
                    raise HTTPException(503, "YouTube OAuth required for live publish in production")
            except MissingCredentials as exc:
                raise HTTPException(503, str(exc)) from exc
        request = PublishRequest(
            idempotency_key=body.idempotency_key,
            title=body.title,
            description=body.description,
            tags=["psychology"],
            category_id="27",
            language="en",
            made_for_kids=body.made_for_kids,
            contains_synthetic_media=body.contains_synthetic_media,
            uses_ai_voice=body.uses_ai_voice,
            uses_realistic_ai_imagery=body.uses_realistic_ai_imagery,
            privacy_status=body.privacy_status,
            dry_run=body.dry_run,
            provisional_research=body.provisional_research,
            chapters=[],
        )
        try:
            row = publish(
                request,
                store=state.store,
                client=state.client,
                jobs=state.jobs,
                ledger=state.ledger,
                kill_active=state.kill.active("youtube"),
                audit_approved=state.audit_approved,
            )
        except Exception as exc:
            state.exceptions.add("publish_blocked", str(exc))
            raise HTTPException(409, str(exc)) from exc
        return row

    @api.get("/status")
    def status():
        uploads = state.store.list_all() if hasattr(state.store, "list_all") else []
        return {
            "audit_approved": state.audit_approved,
            "kill_switch": state.kill.active("youtube"),
            "quota_remaining": state.ledger.remaining,
            "last_dry_run": state.last_dry_run or getattr(state.pipeline, "last_dry_run", None),
            "uploads": len(uploads),
            "exceptions": state.exceptions.list_open("youtube"),
        }

    @api.get("/ops")
    def ops():
        snapshot = status()
        return {
            **snapshot,
            "open_exceptions": len(snapshot["exceptions"]),
            "quota": {"used": state.ledger.used, "reserved": state.ledger.reserved, "remaining": state.ledger.remaining},
        }

    @api.get("/exceptions")
    def list_exceptions():
        return {"exceptions": state.exceptions.list_open("youtube")}

    @api.post("/exceptions/{item_id}/resolve")
    def resolve_exception(item_id: int):
        if not state.exceptions.resolve(item_id):
            raise HTTPException(404, "exception not found")
        return {"resolved": item_id}

    @api.post("/dry-run")
    def dry_run():
        report = run_private_dry_run()
        state.last_dry_run = {"passed": report["passed"], "uploads": report["uploads"]}
        return state.last_dry_run

    @api.post("/cycle")
    def run_cycle():
        return state.pipeline.run_cycle()

    @api.post("/workflows/dry-run")
    def workflow_dry_run():
        from youtube.orchestrator import start_workflow

        started = start_workflow("ProducePrivateWorkflow", {})
        payload = started.get("result") or {}
        if payload.get("passed") is not None:
            state.last_dry_run = {"passed": payload["passed"], "uploads": payload.get("uploads", 0)}
        return started

    @api.post("/workflows/produce/{slug}")
    def workflow_produce(slug: str):
        from youtube.orchestrator import start_workflow
        from youtube.pipeline import DRY_RUN_TOPICS

        topic = next((row for row in DRY_RUN_TOPICS if row["slug"] == slug), None)
        if topic is None:
            raise HTTPException(404, "unknown topic")
        return start_workflow("ProduceOneWorkflow", topic)

    @api.post("/workflows/weekly-plan")
    def workflow_weekly_plan():
        from youtube.orchestrator import start_workflow

        return start_workflow("WeeklyPlanWorkflow", {})

    @api.get("/videos")
    def videos():
        store = state.pipeline.store if hasattr(state.pipeline, "store") else state.store
        if hasattr(store, "list_all"):
            return {"videos": store.list_all()}
        return {"videos": []}

    @api.get("/plan")
    def plan():
        return state.pipeline.plan_week()

    @api.get("/ypp")
    def ypp(subscribers: int = 0, watch_hours: float = 0):
        return ypp_progress(subscribers, watch_hours)

    @api.post("/diagnose")
    def diagnose_video(body: DiagnoseIn):
        return diagnose(Funnel(**body.model_dump()), [])

    @api.post("/discover")
    def discover_competitors(keywords: list[str] | None = None):
        from youtube.modules.discover import discover_channels, persist_channels

        words = keywords or ["applied psychology", "cognitive bias"]
        channels = discover_channels(state.client, words)
        saved = persist_channels(state.session, channels) if state.session is not None else 0
        return {"channels": len(channels), "saved": saved}

    @api.post("/schedules/bootstrap")
    def bootstrap_schedules():
        from youtube.schedules import bootstrap_schedules

        return {"schedules": bootstrap_schedules()}

    @api.post("/workflows/metrics/{video_id}")
    def workflow_metrics(video_id: str):
        from youtube.orchestrator import start_workflow

        return start_workflow(
            "CollectMetricsWorkflow",
            {"video_id": video_id, "published_at": utcnow().isoformat()},
        )

    @api.post("/workflows/optimize/{video_id}")
    def workflow_optimize(video_id: str, body: DiagnoseIn):
        from youtube.orchestrator import start_workflow

        return start_workflow(
            "OptimizeVideoWorkflow",
            {"video_id": video_id, "funnel": body.model_dump()},
        )

    @api.get("/optimizer/pivot")
    def pivot_status():
        return {"pivot": state.pipeline.pivot_status()}

    @api.post("/optimizer/pivot/veto")
    def veto_pivot():
        return state.pipeline.veto_pivot()

    @api.post("/optimizer/pivot/propose")
    def propose_pivot(from_slug: str = "applied-psychology", to_slug: str = "personal-finance-concepts"):
        pivot = state.pipeline.maybe_propose_pivot(from_slug, to_slug)
        if pivot is None:
            return {"proposed": False, "reason": "targets not missed for three cycles"}
        return {"proposed": True, "pivot": pivot}

    return api
