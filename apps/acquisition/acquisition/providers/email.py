from core.config import get_settings
from core.errors import MissingCredentials


class DirectMailbox:
    """Records outbound email locally. Swap for Workspace API in production."""

    def __init__(self, from_address: str = "ava@outreach.example"):
        self.from_address = from_address
        self.sent: list[dict] = []

    def send(self, request: dict) -> dict:
        row = {
            "from": self.from_address,
            "to": request["email"],
            "body": request["body"],
            "channel": "email",
            "provider": "direct",
        }
        self.sent.append(row)
        return {"ok": True, "message_id": f"direct-{len(self.sent)}"}


class InstantlyProvider:
    def __init__(self, api_key: str):
        if not api_key:
            raise MissingCredentials("INSTANTLY_API_KEY")
        self.api_key = api_key

    def send(self, request: dict) -> dict:
        import httpx

        response = httpx.post(
            "https://api.instantly.ai/api/v1/unibox/emails/send",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"email": request["email"], "body": request["body"]},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


class ZeroBounceVerifier:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def verify(self, email: str) -> str:
        if not self.api_key:
            return "valid" if "@" in email else "invalid"
        import httpx

        response = httpx.get(
            "https://api.zerobounce.net/v2/validate",
            params={"api_key": self.api_key, "email": email},
            timeout=20,
        )
        response.raise_for_status()
        return "valid" if response.json().get("status") == "valid" else "invalid"


def email_sender():
    settings = get_settings()
    if settings.email_provider == "instantly" and settings.instantly_api_key:
        return InstantlyProvider(settings.instantly_api_key)
    return DirectMailbox()


def email_verifier():
    return ZeroBounceVerifier(get_settings().zerobounce_api_key)
