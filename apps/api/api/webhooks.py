import hmac
import json
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, Response

from acquisition.policy import AI_DISCLOSURE
from acquisition.providers.closing import verify_hmac_hex, verify_stripe_signature


def router(app) -> APIRouter:
    api = APIRouter(prefix="/webhooks", tags=["webhooks"])
    settings = app.state.settings
    acquisition = app.state.acquisition
    pipeline = acquisition.pipeline
    tenant = settings.acquisition_tenant_id

    def _conflict(call, *args, **kwargs):
        try:
            return call(*args, **kwargs)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @api.post("/inbound/email")
    async def inbound_email(request: Request):
        payload = await request.json()
        email = payload.get("from") or payload.get("email")
        text = payload.get("text") or payload.get("body", "")
        if not email or not text:
            raise HTTPException(400, "from/email and text/body required")
        return _conflict(pipeline.handle_reply, tenant, email, text)

    @api.post("/email-events")
    async def email_events(request: Request):
        """Bounce / complaint / delivery feedback from the sending provider (single event or a list)."""
        payload = await request.json()
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
        if secret and not hmac.compare_digest(request.headers.get("x-documenso-secret", "") or request.headers.get("x-webhook-secret", ""), secret):
            raise HTTPException(401, "invalid webhook secret")
        payload = await request.json()
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
        payload = await request.json()
        body = payload.get("payload") or payload
        attendees = body.get("attendees") or [{}]
        email = attendees[0].get("email") or body.get("email")
        slot = body.get("startTime") or body.get("slot")
        if not email or not slot:
            raise HTTPException(400, "email and slot required")
        kind = payload.get("triggerEvent") or "BOOKING_CREATED"
        return _conflict(pipeline.handle_calendar_event, tenant, email, slot, kind, str(body.get("uid", "")))

    @api.get("/whatsapp")
    async def whatsapp_verify(request: Request):
        params = request.query_params
        if params.get("hub.mode") == "subscribe" and settings.whatsapp_verify_token and params.get("hub.verify_token") == settings.whatsapp_verify_token:
            return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
        raise HTTPException(403, "verification failed")

    @api.post("/whatsapp")
    async def whatsapp_inbound(request: Request):
        payload = await request.json()
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
        form = {key: values[0] for key, values in parse_qs((await request.body()).decode()).items()}
        phone, text = form.get("From"), form.get("Body", "")
        if not phone or not text:
            raise HTTPException(400, "From and Body required")
        pipeline.handle_channel_message(tenant, "sms", phone, text)
        return Response(content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>", media_type="application/xml")

    @api.post("/vapi")
    async def vapi_webhook(request: Request):
        payload = await request.json()
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
        payload = await request.json()
        kind = payload.get("kind", "policy_alert")
        message = payload.get("message", "YouTube policy alert")
        app.state.youtube.exceptions.add(kind, message, scope="youtube")
        if payload.get("strike"):
            app.state.youtube.kill.set("youtube", True, message)
        return {"received": True, "recorded": True}

    return api
