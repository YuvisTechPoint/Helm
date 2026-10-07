from acquisition.mailbox_limit import MailboxLimiter
from acquisition.policy import PolicyGuard
from acquisition.providers.calendar import calendar_client
from acquisition.providers.closing import esign_client, payments_client
from acquisition.providers.email import email_sender, email_verifier
from acquisition.providers.messaging import channel_senders
from acquisition.repository import AcquisitionRepository
from core.budget import BudgetGuard
from core.runtime import get_runtime
from youtube.providers_factory import llm


class AcquisitionRuntime:
    def __init__(self, base=None, circuits=None):
        base = base or get_runtime()
        self.settings = base.settings
        self.session = base.session
        self.repo = AcquisitionRepository(base.session)
        self.kill = base.kill
        self.guard = PolicyGuard(kill_switches=base.kill)
        self.sender = email_sender()
        self.verifier = email_verifier()
        self.calendar = calendar_client()
        self.channels = channel_senders(base.settings)
        self.esign = esign_client(base.settings)
        self.payments = payments_client(base.settings)
        self.mailbox_limiter = MailboxLimiter()
        self.llm = llm(base.settings)
        self.budget = BudgetGuard(base.session)
        self.budget.configure(base.settings.acquisition_tenant_id, "outreach", 100_000)
        self.exceptions = base.exceptions
        self.notifier = base.notifier
        if circuits:
            from core.provider_plane import with_circuit

            with_circuit(self.sender, circuits.get("email"), "send")
            if self.llm is not None:
                with_circuit(self.llm, circuits.get("llm"), "complete")
            with_circuit(self.payments, circuits.get("payments"), "payment_link")
            with_circuit(self.esign, circuits.get("esign"), "send")


_CTX: AcquisitionRuntime | None = None


def bind_acquisition_runtime(base=None, circuits=None) -> AcquisitionRuntime:
    global _CTX
    _CTX = AcquisitionRuntime(base or get_runtime(), circuits=circuits)
    return _CTX


def acquisition_runtime() -> AcquisitionRuntime:
    global _CTX
    if _CTX is None:
        _CTX = AcquisitionRuntime()
    return _CTX
