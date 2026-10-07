from core.bootstrap import db_session, vault_for
from core.config import Settings, get_settings
from core.exception_store import ExceptionStore
from core.jobs import JobBook
from core.kill_switch import KillSwitchBoard
from core.notify import NotifierHub


class EngineRuntime:
    """Shared runtime wired from environment. Used by API, workers, and activities."""

    def __init__(self, settings: Settings | None = None, session=None):
        self.settings = settings or get_settings()
        self.session = session
        if session is None:
            try:
                self.session = db_session()
            except Exception:
                self.session = None
        self.vault = vault_for(self.session, self.settings)
        self.kill = KillSwitchBoard(self.session)
        self.jobs = JobBook(self.session)
        self.exceptions = ExceptionStore(self.session)
        self.notifier = NotifierHub()

    @property
    def live_mode(self) -> bool:
        return bool(
            self.settings.anthropic_api_key
            or self.settings.youtube_refresh_token
            or self.settings.instantly_api_key
        )

    @property
    def audit_approved(self) -> bool:
        return self.settings.yt_audit_approved


_RUNTIME: EngineRuntime | None = None


def set_runtime(runtime: EngineRuntime) -> EngineRuntime:
    global _RUNTIME
    _RUNTIME = runtime
    return runtime


def get_runtime() -> EngineRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = EngineRuntime()
    return _RUNTIME
