from core.config import get_settings
from core.notify import NotifierHub


def crm_handoff(package: dict, tenant_id: str, notifier: NotifierHub | None = None) -> dict:
    settings = get_settings()
    webhook = settings.crm_webhook_url or ""
    payload = {
        "tenant_id": tenant_id,
        "briefing": package.get("briefing"),
        "message": package.get("message"),
        "notify": package.get("notify"),
    }
    briefing = package.get("briefing") or {}
    lead = briefing.get("lead", "client")
    owner_note = briefing.get("one_page") or briefing.get("transcript", [])
    if isinstance(owner_note, list):
        owner_note = " ".join(owner_note[-3:])
    notifier = notifier or NotifierHub()
    notify_channels = package.get("notify_channels")
    notifier.alert(
        f"Handoff ready for {lead} (tenant {tenant_id}).\n{owner_note}",
        channels=notify_channels,
    )
    if not webhook:
        return {"delivered": False, "reason": "crm webhook not configured", "payload": payload, "owner_notified": True}
    import httpx

    response = httpx.post(webhook, json=payload, timeout=20)
    response.raise_for_status()
    return {"delivered": True, "status": response.status_code, "payload": payload, "owner_notified": True}
