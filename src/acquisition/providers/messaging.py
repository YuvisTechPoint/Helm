"""Consent-gated channels (FR-7.3, FR-7.4). Every call goes through PolicyGuard first."""

from core.config import Settings, get_settings
from core.errors import MissingCredentials


class MemoryChannel:
    def __init__(self, channel: str):
        self.channel = channel
        self.sent: list[dict] = []

    def send(self, request: dict) -> dict:
        row = {"to": request.get("phone") or request.get("email"), "body": request["body"], "channel": self.channel}
        self.sent.append(row)
        return {"ok": True, "message_id": f"{self.channel}-{len(self.sent)}", "provider": "memory"}


class WhatsAppCloud:
    """Meta WhatsApp Business Cloud API. Outside the 24h service window only approved templates may be sent."""

    def __init__(self, token: str, phone_number_id: str):
        if not token or not phone_number_id:
            raise MissingCredentials("WHATSAPP_TOKEN/WHATSAPP_PHONE_NUMBER_ID")
        self.token = token
        self.phone_number_id = phone_number_id

    def send(self, request: dict) -> dict:
        import httpx

        template = request.get("template")
        if template:
            message = {
                "type": "template",
                "template": {
                    "name": template["name"],
                    "language": {"code": template.get("language", "en")},
                    "components": template.get("components", []),
                },
            }
        else:
            message = {"type": "text", "text": {"body": request["body"]}}
        response = httpx.post(
            f"https://graph.facebook.com/v20.0/{self.phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"messaging_product": "whatsapp", "to": request["phone"], **message},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return {"ok": True, "message_id": (data.get("messages") or [{}])[0].get("id", ""), "provider": "whatsapp"}


class TwilioSms:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        if not account_sid or not auth_token or not from_number:
            raise MissingCredentials("TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER")
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    def send(self, request: dict) -> dict:
        import httpx

        response = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
            auth=(self.account_sid, self.auth_token),
            data={"To": request["phone"], "From": self.from_number, "Body": request["body"]},
            timeout=30,
        )
        response.raise_for_status()
        return {"ok": True, "message_id": response.json().get("sid", ""), "provider": "twilio"}


class VapiVoice:
    """Outbound AI call; the assistant's first message is the disclosure the guard already enforced."""

    def __init__(self, api_key: str, assistant_id: str, phone_number_id: str):
        if not api_key or not assistant_id or not phone_number_id:
            raise MissingCredentials("VAPI_API_KEY/VAPI_ASSISTANT_ID/VAPI_PHONE_NUMBER_ID")
        self.api_key = api_key
        self.assistant_id = assistant_id
        self.phone_number_id = phone_number_id

    def send(self, request: dict) -> dict:
        import httpx

        response = httpx.post(
            "https://api.vapi.ai/call",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "assistantId": self.assistant_id,
                "phoneNumberId": self.phone_number_id,
                "customer": {"number": request["phone"]},
                "assistantOverrides": {
                    "firstMessage": request["body"],
                    "metadata": {"tenant_id": request.get("tenant_id"), "email": request.get("email")},
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        return {"ok": True, "call_id": response.json().get("id", ""), "provider": "vapi"}


def channel_senders(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    senders: dict = {}
    try:
        senders["whatsapp"] = WhatsAppCloud(settings.whatsapp_token, settings.whatsapp_phone_number_id)
    except MissingCredentials:
        senders["whatsapp"] = MemoryChannel("whatsapp")
    try:
        senders["sms"] = TwilioSms(settings.twilio_account_sid, settings.twilio_auth_token, settings.twilio_from_number)
    except MissingCredentials:
        senders["sms"] = MemoryChannel("sms")
    try:
        senders["voice"] = VapiVoice(settings.vapi_api_key, settings.vapi_assistant_id, settings.vapi_phone_number_id)
    except MissingCredentials:
        senders["voice"] = MemoryChannel("voice")
    return senders


def channel_status(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    return {
        "email": {"live": settings.email_provider == "instantly" and bool(settings.instantly_api_key), "provider": settings.email_provider},
        "whatsapp": {"live": bool(settings.whatsapp_token and settings.whatsapp_phone_number_id), "provider": "whatsapp_cloud"},
        "sms": {"live": bool(settings.twilio_account_sid and settings.twilio_auth_token), "provider": "twilio"},
        "voice": {"live": bool(settings.vapi_api_key and settings.vapi_assistant_id), "provider": "vapi"},
        "calendar": {"live": bool(settings.calcom_api_key), "provider": "calcom"},
        "esign": {
            "live": settings.esign_provider == "documenso" and bool(settings.documenso_api_key and settings.documenso_template_id),
            "provider": settings.esign_provider,
        },
        "payments": {
            "live": bool(settings.stripe_secret_key or settings.razorpay_key_id),
            "provider": settings.payment_provider,
        },
    }
