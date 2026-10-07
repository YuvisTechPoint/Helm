import hashlib
import hmac
import json
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, Response

from acquisition.policy import AI_DISCLOSURE
from acquisition.providers.closing import verify_hmac_hex, verify_stripe_signature
from core.webhook_dedup import WebhookDedup
from core.webhook_verify import require_webhook_auth, verify_meta_signature, verify_twilio_signature


def router(app) -> APIRouter:
    api = APIRouter(prefix="/webhooks", tags=["webhooks"])
    settings = app.state.settings
    acquisition = app.state.acquisition
    pipeline = acquisition.pipeline
    tenant = settings.acquisition_tenant_id
    dedup = WebhookDedup(app.state.session)

    def _conflict(call, *args, **kwargs):
        try:
            return call(*args, **kwargs)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    def _event_id(provider: str, body: bytes, payload: dict | None = None) -> str:
        if payload:
            for key in ("id", "event_id", "eventId", "uid"):
                if payload.get(key):
                    return f"{provider}:{payload[key]}"
        return f"{provider}:{hashlib.sha256(body).hexdigest()[:32]}"

    async def _guard(provider: str, request: Request, secret: str | None) -> bytes:
        body = await request.body()
        require_webhook_auth(
            provider,
            header=request.headers.get("x-webhook-secret") or request.headers.get("x-api-key"),
            secret=secret,
            settings=settings,
        )
        return body

    @api.post("/inbound/email")
    async def inbound_email(request: Request):
        body = await _guard("inbound_email", request, settings.inbound_email_webhook_secret or settings.webhook_shared_secret)
        payload = json.loads(body)
        event_id = _event_id("inbound_email", body, payload)
        if dedup.record("inbound_email", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        email = payload.get("from") or payload.get("email")
        text = payload.get("text") or payload.get("body", "")
        if not email or not text:
            raise HTTPException(400, "from/email and text/body required")
        return _conflict(pipeline.handle_reply, tenant, email, text)

    @api.post("/email-events")
    async def email_events(request: Request):
        body = await _guard("email_events", request, settings.email_events_webhook_secret or settings.webhook_shared_secret)
        payload = json.loads(body)
        event_id = _event_id("email_events", body, payload if isinstance(payload, dict) else None)
        if dedup.record("email_events", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        events = payload if isinstance(payload, list) else payload.get("events", [payload])
        results = []
        for event in events:
            kind = event.get("type") or event.get("event") or event.get("event_type")
            email = event.get("email") or event.get("recipient") or event.get("to")
            if not kind or not email:
                continue
            results.append(pipeline.record_email_event(tenant, kind, email, event.get("mailbox") or event.get("from")))
        return {"processed": len(results), "results": results}

    @api.post("/stripe")
    async def stripe_webhook(request: Request):
        secret = settings.stripe_webhook_secret
        if not secret:
            raise HTTPException(503, "STRIPE_WEBHOOK_SECRET not configured")
        body = await request.body()
        if not verify_stripe_signature(body, request.headers.get("stripe-signature", ""), secret):
            raise HTTPException(400, "invalid signature")
        event = json.loads(body)
        event_id = _event_id("stripe", body, event)
        if dedup.record("stripe", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        if event.get("type") in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            session = event["data"]["object"]
            if session.get("payment_status") not in {None, "paid"}:
                return {"received": True, "status": session.get("payment_status")}
            metadata = session.get("metadata") or {}
            email = metadata.get("email") or session.get("customer_email") or (session.get("customer_details") or {}).get("email")
            if email:
                return _conflict(pipeline.mark_paid, metadata.get("tenant_id", tenant), email, int(session.get("amount_total", 0)), session.get("id", ""))
        return {"received": True}

    @api.post("/razorpay")
    async def razorpay_webhook(request: Request):
        secret = settings.razorpay_webhook_secret
        if not secret:
            raise HTTPException(503, "RAZORPAY_WEBHOOK_SECRET not configured")
        body = await request.body()
        if not verify_hmac_hex(body, request.headers.get("x-razorpay-signature", ""), secret):
            raise HTTPException(400, "invalid signature")
        event = json.loads(body)
        event_id = _event_id("razorpay", body, event)
        if dedup.record("razorpay", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        kind = event.get("event")
        entities = event.get("payload", {})
        payment = entities.get("payment", {}).get("entity", {})
        link = entities.get("payment_link", {}).get("entity", {})
        notes = link.get("notes") or payment.get("notes") or {}
        email = notes.get("email") or payment.get("email")
        if kind == "payment_link.paid" or (kind == "payment.captured" and payment.get("status") == "captured"):
            amount = int(link.get("amount_paid") or payment.get("amount", 0))
            if email:
                return _conflict(pipeline.mark_paid, notes.get("tenant_id", tenant), email, amount, payment.get("id") or link.get("id", ""))
        return {"received": True}

    @api.post("/esign")
    async def esign_webhook(request: Request):
        secret = settings.esign_webhook_secret
        body = await request.body()
        if secret and not hmac.compare_digest(request.headers.get("x-documenso-secret", "") or request.headers.get("x-webhook-secret", ""), secret):
            raise HTTPException(401, "invalid webhook secret")
        payload = json.loads(body)
        event_id = _event_id("esign", body, payload)
        if dedup.record("esign", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        event = str(payload.get("event") or payload.get("status") or "").lower()
        status = {
            "document_completed": "completed",
            "document_signed": "signed",
            "document_rejected": "declined",
            "document_opened": "viewed",
        }.get(event, event)
        document = payload.get("payload") or {}
        envelope_id = str(payload.get("envelope_id") or document.get("id") or "")
        email = payload.get("email")
        if not status or not (envelope_id or email):
            raise HTTPException(400, "status and envelope_id or email required")
        return _conflict(pipeline.handle_esign_event, tenant, status, envelope_id=envelope_id or None, email=email)

    @api.post("/calcom")
    async def calcom_webhook(request: Request):
        body = await _guard("calcom", request, settings.calcom_webhook_secret or settings.webhook_shared_secret)
        payload = json.loads(body)
        event_id = _event_id("calcom", body, payload)
        if dedup.record("calcom", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        inner = payload.get("payload") or payload
        attendees = inner.get("attendees") or [{}]
        email = attendees[0].get("email") or inner.get("email")
        slot = inner.get("startTime") or inner.get("slot")
        if not email or not slot:
            raise HTTPException(400, "email and slot required")
        kind = payload.get("triggerEvent") or "BOOKING_CREATED"
        return _conflict(pipeline.handle_calendar_event, tenant, email, slot, kind, str(inner.get("uid", "")))

    @api.get("/whatsapp")
    async def whatsapp_verify(request: Request):
        params = request.query_params
        if params.get("hub.mode") == "subscribe" and settings.whatsapp_verify_token and params.get("hub.verify_token") == settings.whatsapp_verify_token:
            return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
        raise HTTPException(403, "verification failed")

    @api.post("/whatsapp")
    async def whatsapp_inbound(request: Request):
        body = await request.body()
        if settings.whatsapp_token and not verify_meta_signature(body, request.headers.get("x-hub-signature-256"), settings.whatsapp_token):
            if settings.engine_mode == "production":
                raise HTTPException(401, "invalid whatsapp signature")
        payload = json.loads(body)
        event_id = _event_id("whatsapp", body, payload)
        if dedup.record("whatsapp", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        handled = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                names = {contact.get("wa_id"): contact.get("profile", {}).get("name", "") for contact in value.get("contacts", [])}
                for message in value.get("messages", []):
                    text = (message.get("text") or {}).get("body") or (message.get("button") or {}).get("text", "")
                    if not text:
                        continue
                    phone = "+" + message["from"].lstrip("+")
                    handled.append(pipeline.handle_channel_message(tenant, "whatsapp", phone, text, names.get(message["from"], "")))
        return {"handled": len(handled), "results": handled}

    @api.post("/twilio/sms")
    async def twilio_sms(request: Request):
        body = await request.body()
        form = {key: values[0] for key, values in parse_qs(body.decode()).items()}
        url = str(request.url)
        signature = request.headers.get("x-twilio-signature")
        if settings.twilio_auth_token:
            if not verify_twilio_signature(url, form, signature, settings.twilio_auth_token):
                raise HTTPException(401, "invalid twilio signature")
        else:
            require_webhook_auth("twilio", header=request.headers.get("x-webhook-secret"), secret=settings.webhook_shared_secret, settings=settings)
        event_id = _event_id("twilio", body, form)
        if dedup.record("twilio", event_id, body)["duplicate"]:
            return Response(content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>", media_type="application/xml")
        phone, text = form.get("From"), form.get("Body", "")
        if not phone or not text:
            raise HTTPException(400, "From and Body required")
        pipeline.handle_channel_message(tenant, "sms", phone, text)
        return Response(content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>", media_type="application/xml")

    @api.post("/vapi")
    async def vapi_webhook(request: Request):
        body = await _guard("vapi", request, settings.vapi_webhook_secret or settings.webhook_shared_secret)
        payload = json.loads(body)
        event_id = _event_id("vapi", body, payload)
        if dedup.record("vapi", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        message = payload.get("message", payload)
        kind = message.get("type")
        profile = acquisition.repo.get_profile(tenant) or {}
        if kind == "assistant-request":
            business = profile.get("business_name", "our team")
            return {
                "assistantId": settings.vapi_assistant_id or None,
                "assistantOverrides": {
                    "firstMessage": f"{AI_DISCLOSURE} {business}. How can I help you today?",
                    "variableValues": {"business": business, "faq": " ".join(profile.get("faq", [])[:5])},
                },
            }
        if kind == "end-of-call-report":
            call = message.get("call", {})
            phone = (call.get("customer") or message.get("customer") or {}).get("number", "")
            transcript = message.get("transcript") or (message.get("artifact") or {}).get("transcript", "")
            summary = message.get("summary") or (message.get("analysis") or {}).get("summary", "")
            if not phone:
                raise HTTPException(400, "customer number required")
            return pipeline.handle_call_report(tenant, phone, transcript, summary)
        return {"received": True, "type": kind}

    @api.post("/youtube/policy")
    async def youtube_policy(request: Request):
        body = await _guard("youtube_policy", request, settings.youtube_policy_webhook_secret or settings.webhook_shared_secret)
        payload = json.loads(body)
        event_id = _event_id("youtube_policy", body, payload)
        if dedup.record("youtube_policy", event_id, body)["duplicate"]:
            return {"received": True, "duplicate": True}
        kind = payload.get("kind", "policy_alert")
        message = payload.get("message", "YouTube policy alert")
        app.state.youtube.exceptions.add(kind, message, scope="youtube")
        if payload.get("strike"):
            app.state.youtube.kill.set("youtube", True, message)
        return {"received": True, "recorded": True}

    return api
