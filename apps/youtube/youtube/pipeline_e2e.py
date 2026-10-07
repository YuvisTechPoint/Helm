from datetime import datetime, timezone

from core.events import EventLog
from core.exception_store import ExceptionStore
from core.jobs import JobBook
from core.kill_switch import KillSwitchBoard
from core.notify import NotifierHub
from youtube.modules.analytics import blank_metrics, funnel_from_metrics, metrics_from_analytics_api, record_snapshot, snapshot_plan
from youtube.modules.diagnostician import Funnel, Optimizer, apply_fix, diagnose, propose_pivot, record_cycle, review_change, veto_pivot
from youtube.metadata import push_metadata_change
from youtube.providers_factory import data_client
from youtube.modules.niche import scout
from youtube.modules.planner import build_calendar
from youtube.pipeline import DRY_RUN_TOPICS, produce_topic, run_private_dry_run
from youtube.modules.gate import QualityGate
from youtube.modules.publisher import InMemoryVideoStore
from youtube.modules.llm_script import LlmScriptWriter
from youtube.pipeline import SHORT_TOPICS
from youtube.providers import FakeYouTube
from youtube.quota import QuotaLedger


class YouTubePipeline:
    def __init__(
        self,
        *,
        audit_approved: bool = False,
        kill: KillSwitchBoard | None = None,
        store=None,
        client=None,
        ledger: QuotaLedger | None = None,
        jobs: JobBook | None = None,
        exceptions: ExceptionStore | None = None,
        events: EventLog | None = None,
        notifier: NotifierHub | None = None,
        analytics=None,
        settings=None,
        vault=None,
    ):
        self.kill = kill or KillSwitchBoard()
        self.ledger = ledger or QuotaLedger.from_env(daily_limit=200_000)
        self.jobs = jobs or JobBook()
        self.store = store or InMemoryVideoStore()
        self.client = client or FakeYouTube()
        self.audit_approved = audit_approved
        self.events = events or EventLog()
        self.exceptions = exceptions or ExceptionStore()
        self.notifier = notifier or NotifierHub()
        self.optimizer = Optimizer()
        self.metrics: dict = {}
        self.last_dry_run: dict | None = None
        self.analytics = analytics
        self.settings = settings
        self.vault = vault

    def plan_week(self) -> dict:
        niche = scout()
        calendar = build_calendar(datetime.now(timezone.utc).date(), DRY_RUN_TOPICS[:6])
        self.events.append("weekly_plan", "m4", {"niche": niche.slug, "items": len(calendar)})
        return {"niche": niche.slug, "calendar": calendar}

    def private_dry_run(self) -> dict:
        report = run_private_dry_run()
        self.last_dry_run = {"passed": report["passed"], "uploads": report["uploads"]}
        self.events.append("dry_run_complete", "m14", self.last_dry_run)
        return self.last_dry_run

    def produce_one(self, topic: dict, past_scripts: list[str], previous_format: str | None) -> dict:
        from core.jobs import ExceptionQueue

        outcome = produce_topic(
            topic,
            writer=LlmScriptWriter(),
            gate=QualityGate(),
            store=self.store,
            client=self.client,
            jobs=self.jobs,
            ledger=self.ledger,
            queue=ExceptionQueue(),
            past_scripts=past_scripts,
            previous_format=previous_format,
            kill_active=self.kill.active("youtube"),
            audit_approved=self.audit_approved,
        )
        if outcome["status"] == "published_private":
            self.events.append("video_published", "m11", {"youtube_id": outcome["youtube_id"], "slug": topic["slug"]})
        return outcome

    def collect_metrics(self, video_id: str, published_at: datetime, live_metrics: dict | None = None) -> list[dict]:
        captured = []
        metrics = live_metrics or blank_metrics()
        if self.analytics is not None:
            start = published_at.date().isoformat()
            end = datetime.now(timezone.utc).date().isoformat()
            try:
                metrics.update(metrics_from_analytics_api(self.analytics.query_video(video_id, start, end)))
            except Exception:
                pass
        metrics.setdefault("views", 120)
        metrics.setdefault("videoThumbnailImpressionsClickRate", 0.04)
        for point in snapshot_plan(published_at):
            label = point["label"]
            row = record_snapshot(self.metrics, video_id, label, metrics, point["at"])
            captured.append(row)
        self.events.append("metrics_collected", "m12", {"video_id": video_id, "labels": [row["label"] for row in captured]})
        return captured

    def optimize_video(self, video_id: str, funnel: Funnel) -> dict:
        diagnosis = diagnose(funnel, self.optimizer.changes)
        if diagnosis["action"] == "kill_switch":
            self.kill.set("youtube", True, diagnosis["reason"])
            self.exceptions.add("kill_switch", diagnosis["reason"])
            self.notifier.alert(f"YouTube kill switch: {diagnosis['reason']}")
            return diagnosis
        if diagnosis["action"] != "fix":
            return diagnosis
        now = datetime.now(timezone.utc)
        change = apply_fix(self.optimizer, video_id, funnel, now)
        client = data_client(self.settings, self.vault) if self.settings else self.client
        if client is None:
            client = self.client
        current = {}
        if hasattr(self.store, "list_all"):
            for row in self.store.list_all():
                if row.get("youtube_id") == video_id:
                    current = row.get("metadata", {}).get("snippet", {}) if isinstance(row.get("metadata"), dict) else {}
                    break
        pushed = push_metadata_change(client, video_id, change.lever, change.new_value or "next-ranked", current)
        review = review_change(change, now + __import__("datetime").timedelta(hours=73), funnel.ctr)
        self.events.append(
            "optimization_change",
            "m13",
            {"video_id": video_id, "lever": change.lever, "review": review, "api": pushed.get("api")},
        )
        return {"diagnosis": diagnosis, "change": change.lever, "review": review, "api": pushed.get("api")}

    def pivot_status(self) -> dict | None:
        return self.optimizer.pivot

    def veto_pivot(self) -> dict:
        veto_pivot(self.optimizer)
        self.notifier.alert("YouTube niche pivot vetoed by owner.")
        return {"vetoed": True, "pivot": self.optimizer.pivot}

    def maybe_propose_pivot(self, from_slug: str, to_slug: str) -> dict | None:
        pivot = propose_pivot(self.optimizer, datetime.now(timezone.utc), from_slug, to_slug)
        if pivot:
            self.notifier.alert(
                f"YouTube pivot proposed: {from_slug} → {to_slug}. Veto within 72 hours via the owner dashboard."
            )
        return pivot

    def run_cycle(self) -> dict:
        plan = self.plan_week()
        dry = self.private_dry_run()
        past: list[str] = []
        previous_format = None
        produced = []
        topics = DRY_RUN_TOPICS[:3] + SHORT_TOPICS[:1]
        for topic in topics:
            outcome = self.produce_one(topic, past, previous_format)
            produced.append(outcome)
            if outcome.get("status") == "published_private":
                past.append(outcome.get("script_text", ""))
                previous_format = outcome.get("format_name")
                published_at = datetime.now(timezone.utc)
                video_id = outcome["youtube_id"]
                snapshots = self.collect_metrics(video_id, published_at)
                latest = snapshots[-1]["metrics"] if snapshots else blank_metrics()
                funnel_kwargs = funnel_from_metrics(latest, age_hours=72, channel_median_views=120)
                funnel = Funnel(**funnel_kwargs)
                result = self.optimize_video(video_id, funnel)
                met_targets = funnel.ctr >= 0.05 and funnel.retention_first_30 >= 0.4
                record_cycle(self.optimizer, met_targets)
                if len(self.optimizer.missed_cycles) >= 3 and all(self.optimizer.missed_cycles):
                    self.maybe_propose_pivot("applied-psychology", "personal-finance-concepts")
        return {"plan": plan, "dry_run": dry, "produced": produced}
