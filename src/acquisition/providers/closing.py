"""Closer providers: e-signature envelopes and payment links (FR-10.2, FR-10.3)."""

import hashlib
import hmac
import uuid

from core.config import Settings, get_settings
from core.errors import MissingCredentials


class MemoryESign:
    """Local envelope store; the owner or a test marks envelopes completed via the webhook."""

    name = "memory"

    def __init__(self):
        self.envelopes: dict[str, dict] = {}

    def send(self, *, email: str, name: str, title: str, proposal: dict, metadata: dict) -> dict:
        envelope_id = f"env-{uuid.uuid4().hex[:10]}"
        row = {
            "envelope_id": envelope_id,
            "email": email,
            "title": title,
            "status": "sent",
            "sign_url": f"https://sign.local/{envelope_id}",
            "provider": self.name,
            "metadata": metadata,
            "proposal": proposal,
        }
        self.envelopes[envelope_id] = row
        return row

    def remind(self, envelope_id: str) -> dict:
        return {"envelope_id": envelope_id, "reminded": True, "provider": self.name}


class DocumensoESign:
    """Documenso API v1: generate a document from an approved template, then send it."""

    name = "documenso"

    def __init__(self, api_key: str, base_url: str, template_id: str):
        if not api_key:
            raise MissingCredentials("DOCUMENSO_API_KEY")
        if not template_id:
            raise MissingCredentials("DOCUMENSO_TEMPLATE_ID")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.template_id = template_id

    def _client(self):
        import httpx

        return httpx.Client(base_url=self.base_url, headers={"Authorization": self.api_key}, timeout=30)

    def send(self, *, email: str, name: str, title: str, proposal: dict, metadata: dict) -> dict:
        with self._client() as client:
            created = client.post(
                f"/templates/{self.template_id}/generate-document",
                json={
                    "title": title,
                    "externalId": metadata.get("external_id", email),
                    "recipients": [{"name": name or email, "email": email, "role": "SIGNER"}],
                    "meta": {"subject": title, "message": "Please review and sign the attached proposal."},
                    "formValues": {
                        "services": ", ".join(proposal.get("services", [])),
                        "price": str(proposal.get("price", "")),
                    },
                },
            )
            created.raise_for_status()
            document = created.json()
            document_id = document.get("documentId") or document.get("id")
            sent = client.post(f"/documents/{document_id}/send", json={"sendEmail": True})
            sent.raise_for_status()
        recipients = document.get("recipients") or [{}]
        return {
            "envelope_id": str(document_id),
            "email": email,
            "title": title,
            "status": "sent",
            "sign_url": recipients[0].get("signingUrl", ""),
            "provider": self.name,
            "metadata": metadata,
        }

    def remind(self, envelope_id: str) -> dict:
        with self._client() as client:
            response = client.post(f"/documents/{envelope_id}/resend", json={})
            response.raise_for_status()
        return {"envelope_id": envelope_id, "reminded": True, "provider": self.name}


class MemoryPayments:
    name = "memory"

    def __init__(self):
        self.links: dict[str, dict] = {}

    def payment_link(self, *, amount_cents: int, currency: str, email: str, description: str, metadata: dict) -> dict:
        link_id = f"pay-{uuid.uuid4().hex[:10]}"
        row = {
            "link_id": link_id,
            "url": f"https://pay.local/{link_id}",
            "amount_cents": amount_cents,
            "currency": currency,
            "email": email,
            "provider": self.name,
            "metadata": metadata,
        }
        self.links[link_id] = row
        return row


class StripeCheckout:
    """One-off Checkout Session with inline price data; metadata routes the webhook back to the lead."""

    name = "stripe"

    def __init__(self, secret_key: str, success_url: str):
        if not secret_key:
            raise MissingCredentials("STRIPE_SECRET_KEY")
        self.secret_key = secret_key
        self.success_url = success_url

    def payment_link(self, *, amount_cents: int, currency: str, email: str, description: str, metadata: dict) -> dict:
        import httpx

        data = {
            "mode": "payment",
            "success_url": self.success_url,
            "customer_email": email,
            "line_items[0][quantity]": 1,
            "line_items[0][price_data][currency]": currency,
            "line_items[0][price_data][unit_amount]": amount_cents,
            "line_items[0][price_data][product_data][name]": description,
        }
        for key, value in metadata.items():
            data[f"metadata[{key}]"] = value
        response = httpx.post("https://api.stripe.com/v1/checkout/sessions", auth=(self.secret_key, ""), data=data, timeout=30)
        response.raise_for_status()
        session = response.json()
        return {
            "link_id": session["id"],
            "url": session["url"],
            "amount_cents": amount_cents,
            "currency": currency,
            "email": email,
            "provider": self.name,
            "metadata": metadata,
        }


class RazorpayLinks:
    name = "razorpay"

    def __init__(self, key_id: str, key_secret: str):
        if not key_id or not key_secret:
            raise MissingCredentials("RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET")
        self.auth = (key_id, key_secret)

    def payment_link(self, *, amount_cents: int, currency: str, email: str, description: str, metadata: dict) -> dict:
        import httpx

        response = httpx.post(
            "https://api.razorpay.com/v1/payment_links",
            auth=self.auth,
            json={
                "amount": amount_cents,
                "currency": currency.upper(),
                "description": description,
                "customer": {"email": email},
                "notify": {"email": True},
                "reminder_enable": True,
                "notes": metadata,
            },
            timeout=30,
        )
        response.raise_for_status()
        link = response.json()
        return {
            "link_id": link["id"],
            "url": link["short_url"],
            "amount_cents": amount_cents,
            "currency": currency,
            "email": email,
            "provider": self.name,
            "metadata": metadata,
        }


def esign_client(settings: Settings | None = None):
    settings = settings or get_settings()
    if settings.esign_provider == "documenso":
        try:
            return DocumensoESign(settings.documenso_api_key, settings.documenso_base_url, settings.documenso_template_id)
        except MissingCredentials:
            pass
    return MemoryESign()


def payments_client(settings: Settings | None = None):
    settings = settings or get_settings()
    choice = settings.payment_provider
    if choice == "auto":
        if settings.acquisition_region == "india" and settings.razorpay_key_id:
            choice = "razorpay"
        elif settings.stripe_secret_key:
            choice = "stripe"
        elif settings.razorpay_key_id:
            choice = "razorpay"
        else:
            choice = "memory"
    try:
        if choice == "stripe":
            return StripeCheckout(settings.stripe_secret_key, settings.payment_success_url)
        if choice == "razorpay":
            return RazorpayLinks(settings.razorpay_key_id, settings.razorpay_key_secret)
    except MissingCredentials:
        pass
    return MemoryPayments()


def verify_stripe_signature(body: bytes, header: str, secret: str, tolerance_s: int = 300) -> bool:
    import time

    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts.setdefault(key.strip(), []).append(value.strip())
    timestamp = (parts.get("t") or [""])[0]
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > tolerance_s:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", []))


def verify_hmac_hex(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
