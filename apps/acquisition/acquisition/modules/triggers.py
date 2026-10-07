"""M3 — trigger-based sourcing signals."""

TRIGGER_KEYWORDS = {
    "funding": ("raised", "funding", "series"),
    "hiring": ("hiring", "head of", "we're growing"),
    "tech_change": ("migrat", "replatform", "new stack"),
    "expansion": ("new location", "opened", "launching"),
    "reviews": ("negative review", "complaints", "trustpilot"),
    "performance": ("slow site", "checkout", "abandonment", "shipping rates"),
}


def detect_triggers(text: str, profile: dict) -> list[dict]:
    lowered = text.lower()
    hits = []
    for name, keywords in TRIGGER_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            hits.append({"kind": name, "trigger": name, "strength": 0.8, "source": "text_scan"})
    for service in profile.get("services", []):
        if service.lower() in lowered:
            hits.append({"kind": "service_match", "trigger": "service_match", "strength": 0.7, "source": "profile_map"})
    return hits


def intent_from_triggers(triggers: list[dict]) -> float:
    if not triggers:
        return 0.5
    strength = sum(float(item.get("strength", 0.6)) for item in triggers)
    return min(1.0, 0.45 + 0.12 * strength)


def outreach_reason(lead: dict, brief_facts: list[dict]) -> str:
    if lead.get("reason"):
        return lead["reason"]
    if brief_facts:
        return brief_facts[0]["text"]
    return "your funnel may have a conversion leak we can quantify"
