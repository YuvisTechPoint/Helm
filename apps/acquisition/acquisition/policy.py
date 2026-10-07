import re

from core.errors import PolicyDenied, TermsViolation

COLD_CHANNELS = {"email"}
CONSENT_CHANNELS = {"whatsapp", "sms", "voice"}
SPAM_TRIGGERS = ("free money", "act now", "click here", "buy now", "winner guaranteed")
AI_DISCLOSURE = "This is an AI assistant calling for"


class SuppressionList:
    def __init__(self):
        self.rows: list[dict] = []

    def add(self, value: str, kind: str = "email", tenant_id: str | None = None) -> None:
        self.rows.append({"value": value.lower(), "kind": kind, "tenant_id": tenant_id})

    def contains(self, value: str, tenant_id: str | None) -> bool:
        target = value.lower()
        for row in self.rows:
            if row["value"] != target:
                continue
            if row["tenant_id"] is None or row["tenant_id"] == tenant_id:
                return True
        return False


def critique(message: str, corpus: str, *, first_touch: bool) -> dict:
    reasons: list[str] = []
    if first_touch and len(message.split()) > 120:
        reasons.append("first touch is over 120 words")
    if first_touch and re.search(r"https?://", message):
        reasons.append("first touch contains a link")
    lowered = message.lower()
    for trigger in SPAM_TRIGGERS:
        if trigger in lowered:
            reasons.append(f"spam trigger: {trigger}")
    for number in re.findall(r"\d+(?:\.\d+)?%?", message):
        if number not in corpus:
            reasons.append(f"invented number {number}")
    return {"passed": not reasons, "reasons": reasons}


TRANSACTIONAL_KINDS = {"handover", "meeting_confirmation", "meeting_reminder", "payment_receipt"}


def kill_scopes(tenant_id: str | None, channel: str) -> list[str]:
    scopes = ["acquisition", f"acquisition:channel:{channel}"]
    if tenant_id:
        scopes.append(f"acquisition:tenant:{tenant_id}")
    return scopes


class PolicyGuard:
    def __init__(self, kill_switches=None):
        self.suppression = SuppressionList()
        self.frozen: set[str] = set()
        self.replied: set[str] = set()
        self.sender_calls = 0
        self.kill_switches = kill_switches

    def authorize(self, request: dict) -> None:
        channel = request["channel"]
        if channel == "linkedin":
            raise PolicyDenied("LinkedIn automation is out of scope")
        if self.kill_switches is not None:
            for scope in kill_scopes(request.get("tenant_id"), channel):
                if self.kill_switches.active(scope):
                    raise PolicyDenied(f"kill switch active: {scope}")
        lead_id = request["lead_id"]
        if lead_id in self.frozen and request.get("transactional") not in TRANSACTIONAL_KINDS:
            raise PolicyDenied("automation is frozen after handoff")
        if request.get("sequence_touch") and lead_id in self.replied:
            raise PolicyDenied("sequence stops on any reply")
        if not request.get("critic_passed"):
            raise PolicyDenied("critic failed; message was not sent")
        if self.suppression.contains(request.get("email", ""), request.get("tenant_id")):
            raise PolicyDenied("address is suppressed")
        if request.get("phone") and self.suppression.contains(request["phone"], request.get("tenant_id")):
            raise PolicyDenied("number is suppressed")
        if channel == "email":
            if not request.get("lawful_basis"):
                raise PolicyDenied("email needs a recorded lawful basis")
            if request.get("verification") != "valid":
                raise PolicyDenied("email failed verification")
        if channel in CONSENT_CHANNELS:
            consent = request.get("consent") or {}
            if not consent or consent.get("withdrawn"):
                raise PolicyDenied(f"{channel} requires consent")
            if channel == "voice" and request.get("direction", "outbound") == "outbound":
                if consent.get("basis") != "express":
                    raise PolicyDenied("outbound AI voice requires express consent")
                if not request.get("body", "").startswith(AI_DISCLOSURE):
                    raise PolicyDenied("outbound AI voice must identify itself at the start")
            if channel == "whatsapp" and "stop" not in request.get("body", "").lower():
                raise PolicyDenied("WhatsApp templates need an opt-out path")
        if channel not in COLD_CHANNELS | CONSENT_CHANNELS:
            raise PolicyDenied(f"channel {channel} is not enabled")

    def send(self, request: dict, sender, mailbox_limiter=None) -> dict:
        self.authorize(request)
        mailbox = request.get("mailbox")
        daily_cap = request.get("daily_cap")
        if mailbox and daily_cap and mailbox_limiter is not None:
            if not mailbox_limiter.allow(mailbox, daily_cap):
                raise PolicyDenied("mailbox daily cap reached")
        result = sender(request)
        self.sender_calls += 1
        return result


def scrape_linkedin(*_args, **_kwargs):
    raise TermsViolation("LinkedIn's User Agreement forbids scraping and automated DMs")
