"""M5 — fit × intent × reachability with look-alike blend and an explainable breakdown."""

from acquisition.funnel import score_lead
from core.stats import clamp, jaccard


def _tokens(values) -> set[str]:
    if not values:
        return set()
    if isinstance(values, str):
        values = [values]
    return {str(item).strip().lower() for item in values if str(item).strip()}


def fit_breakdown(lead: dict, icp: dict, profile: dict) -> dict[str, float]:
    parts: dict[str, float] = {"base": 0.4}
    anti = [token.lower() for token in profile.get("anti_ideal_clients", []) if token]
    company = str(lead.get("company") or "").lower()
    if anti and any(token in company for token in anti):
        return {"anti_ideal": 0.1}

    if icp.get("industry") and str(lead.get("industry") or "").lower() == str(icp["industry"]).lower():
        parts["industry"] = 0.18
    roles = icp.get("roles") or []
    title = str(lead.get("title") or "")
    if title and any(role.lower() in title.lower() for role in roles):
        parts["role"] = 0.16
    geos = _tokens(profile.get("geographies") or []) | _tokens([icp.get("geo"), icp.get("region"), icp.get("geography")])
    lead_geo = _tokens([lead.get("geo"), lead.get("geography"), lead.get("country")])
    if geos and lead_geo and geos & lead_geo:
        parts["geo"] = 0.1
    sizes = _tokens([icp.get("size"), icp.get("size_band")])
    lead_size = _tokens([lead.get("size"), lead.get("size_band")])
    if sizes and lead_size and sizes & lead_size:
        parts["size"] = 0.06
    tech_overlap = jaccard(_tokens(lead.get("tech_stack")), _tokens(icp.get("tech_stack") or profile.get("tech_stack")))
    if tech_overlap:
        parts["tech"] = round(0.1 * tech_overlap, 4)
    ideal = [token.lower() for token in profile.get("ideal_clients", []) if token]
    if ideal and any(token in company for token in ideal):
        parts["ideal"] = 0.12
    return parts


def fit_from_icp(lead: dict, icp: dict, profile: dict) -> float:
    parts = fit_breakdown(lead, icp, profile)
    if "anti_ideal" in parts:
        return 0.1
    return min(1.0, sum(parts.values()))


def compute_scores(
    lead: dict,
    icp: dict,
    profile: dict,
    verification: str,
    triggers: list[dict],
    weights: dict | None = None,
    converted: list[dict] | None = None,
) -> dict:
    from acquisition.modules.learning import blend_lookalike, weighted_score
    from acquisition.modules.triggers import intent_from_triggers

    parts = {}
    if icp:
        fit = fit_from_icp(lead, icp, profile)
        parts = fit_breakdown(lead, icp, profile)
    else:
        fit = float(lead.get("fit", 0.5))
        parts = {"supplied": fit}
    fit, lookalike = blend_lookalike(fit, lead, converted or [])
    intent = float(lead.get("intent", 0.6))
    trigger_intent = intent_from_triggers(triggers) if triggers else intent
    intent = max(intent, trigger_intent)
    reach = 1.0 if verification == "valid" else 0.0
    score = weighted_score(fit, intent, reach, weights) if weights else score_lead(fit, intent, reach)
    return {
        "fit": round(clamp(fit), 4),
        "intent": round(clamp(intent), 4),
        "reach": reach,
        "lookalike": lookalike,
        "score": round(score, 4),
        "explain": {
            "fit_parts": parts,
            "lookalike": lookalike,
            "trigger_intent": round(trigger_intent, 4),
            "verification": verification,
            "weights": {key: weights.get(key) for key in ("fit", "intent", "reach")} if weights else {"fit": 1, "intent": 1, "reach": 1},
        },
    }
