from core.runtime import get_runtime
from youtube.modules.publisher import InMemoryVideoStore
from youtube.providers import FakeYouTube
from youtube.providers_factory import analytics_client, llm, tts, youtube_client
from youtube.quota import QuotaLedger
from youtube.store import DbMetricStore, DbOptimizerStore, DbVideoStore


class YouTubeRuntime:
    def __init__(self, base=None):
        base = base or get_runtime()
        self.settings = base.settings
        self.session = base.session
        self.vault = base.vault
        self.kill = base.kill
        self.jobs = base.jobs
        self.exceptions = base.exceptions
        self.notifier = base.notifier
        self.ledger = QuotaLedger.from_env()
        self.storage = __import__("core.object_store", fromlist=["object_store"]).object_store(base.settings)
        self.store = DbVideoStore(base.session) if base.session else InMemoryVideoStore()
        self.metrics = DbMetricStore(base.session) if base.session else None
        self.optimizer = DbOptimizerStore(base.session) if base.session else None
        self.budget = __import__("core.budget", fromlist=["BudgetGuard"]).BudgetGuard(base.session)
        if base.session:
            self.budget.configure("youtube", "production", 500_000)
        self.llm = llm(base.settings)
        self.tts = tts(base.settings)
        self.analytics = analytics_client(base.settings, base.vault)
        self.client = youtube_client(base.settings, base.vault)

    @property
    def audit_approved(self) -> bool:
        return self.settings.yt_audit_approved

    def use_live_research(self) -> bool:
        return self.llm is not None

    def publish_mode(self) -> tuple[bool, bool]:
        """Returns (dry_run, provisional_research)."""
        if isinstance(self.client, FakeYouTube):
            return True, True
        return not self.audit_approved, False


_CTX: YouTubeRuntime | None = None


def bind_youtube_runtime(base=None) -> YouTubeRuntime:
    global _CTX
    _CTX = YouTubeRuntime(base or get_runtime())
    return _CTX


def youtube_runtime() -> YouTubeRuntime:
    global _CTX
    if _CTX is None:
        _CTX = YouTubeRuntime()
    return _CTX
