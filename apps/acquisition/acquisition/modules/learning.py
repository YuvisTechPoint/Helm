"""M12 learning loop: score retraining (FR-5.2), look-alikes (FR-2.4), client-list seeding (FR-1.4),
volume planning, and the owner's monthly report (FR-12.3)."""

import math
import re

from core.timeutil import utcnow

DEFAULT_WEIGHTS = {"fit": 1.0, "intent": 1.0, "reach": 1.0}
CONTACTED_STAGES = {"contacted", "replied", "positive", "qualified", "converted", "nurture", "unsubscribed"}
SUCCESS_STAGES = {"positive", "qualified", "converted"}
MIN_TRAINING_SAMPLES = 20
LOOKALIKE_BLEND = 0.3
LOOKALIKE_MIN_CLIENTS = 3
PRIOR_QUALIFIED_RATE = 0.03


def weighted_score(fit: float, intent: float, reach: float, weights: dict | None = None) -> float:
    weights = weights or DEFAULT_WEIGHTS
    if fit <= 0 or intent <= 0 or reach <= 0:
        return 0.0
    return (fit ** weights.get("fit", 1.0)) * (intent ** weights.get("intent", 1.0)) * (reach ** weights.get("reach", 1.0))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, value))))


def retrain_score_weights(leads: list[dict], current: dict | None = None, iterations: int = 600, rate: float = 0.5) -> dict:
    """Logistic regression on log(fit), log(intent) against reply/qualify/convert outcomes.

    The learned coefficients become exponents in fit^a × intent^b × reach, normalised to mean 1 and
    clamped to [0.5, 2] so one noisy week cannot zero out a factor.
    """
    current = {**DEFAULT_WEIGHTS, **(current or {})}
    rows = [
        (math.log(max(lead.get("fit", 0.5), 1e-3)), math.log(max(lead.get("intent", 0.5), 1e-3)), 1.0 if lead.get("stage") in SUCCESS_STAGES else 0.0)
        for lead in leads
        if lead.get("stage") in CONTACTED_STAGES
    ]
    positives = sum(1 for row in rows if row[2])
    if len(rows) < MIN_TRAINING_SAMPLES or positives == 0 or positives == len(rows):
        return {**current, "status": "skipped", "samples": len(rows), "positives": positives, "trained_at": utcnow().isoformat()}
    coef_fit, coef_intent, bias = 1.0, 1.0, 0.0
    count = len(rows)
    for _ in range(iterations):
        grad_fit = grad_intent = grad_bias = 0.0
        for x_fit, x_intent, label in rows:
            error = _sigmoid(coef_fit * x_fit + coef_intent * x_intent + bias) - label
            grad_fit += error * x_fit
            grad_intent += error * x_intent
            grad_bias += error
        coef_fit -= rate * grad_fit / count
        coef_intent -= rate * grad_intent / count
        bias -= rate * grad_bias / count
    raw_fit, raw_intent = max(coef_fit, 0.05), max(coef_intent, 0.05)
    mean = (raw_fit + raw_intent) / 2
    weights = {
        "fit": round(min(2.0, max(0.5, raw_fit / mean)), 3),
        "intent": round(min(2.0, max(0.5, raw_intent / mean)), 3),
        "reach": 1.0,
    }
    return {
        **weights,
        "status": "trained",
        "samples": count,
        "positives": positives,
        "previous": {key: current.get(key, 1.0) for key in DEFAULT_WEIGHTS},
        "trained_at": utcnow().isoformat(),
    }


def _tokens(record: dict) -> set[str]:
    tokens: set[str] = set()
    for key in ("industry", "geo", "geography", "country", "size", "size_band"):
        value = record.get(key)
        if value:
            tokens.add(f"{key}:{str(value).lower()}")
    for word in re.findall(r"[a-z]+", str(record.get("title") or record.get("role") or "").lower()):
        tokens.add(f"role:{word}")
    for tech in record.get("tech_stack", []) or []:
        tokens.add(f"tech:{str(tech).lower()}")
    return tokens


def lookalike_similarity(lead: dict, converted: list[dict]) -> float:
    """Max Jaccard similarity of firmographic/technographic tokens against converted clients."""
    lead_tokens = _tokens(lead)
    if not lead_tokens or not converted:
        return 0.0
    best = 0.0
    for client in converted:
        client_tokens = _tokens(client)
        if not client_tokens:
            continue
        best = max(best, len(lead_tokens & client_tokens) / len(lead_tokens | client_tokens))
    return round(best, 4)


def blend_lookalike(fit: float, lead: dict, converted: list[dict]) -> tuple[float, float]:
    if len(converted) < LOOKALIKE_MIN_CLIENTS:
        return fit, 0.0
    similarity = lookalike_similarity(lead, converted)
    return round((1 - LOOKALIKE_BLEND) * fit + LOOKALIKE_BLEND * similarity, 4), similarity


def seed_from_client_list(profile: dict, clients: list[dict]) -> dict:
    """Turn past won/lost deals into ICP cells with informed bandit priors."""
    groups: dict[tuple[str, str], dict] = {}
    won_names: list[str] = []
    for client in clients:
        industry = (client.get("industry") or "general").strip().lower()
        geo = (client.get("geo") or client.get("geography") or (profile.get("geographies") or ["any"])[0]).strip().lower()
        cell = groups.setdefault(
            (industry, geo),
            {
                "name": f"seed-{re.sub(r'[^a-z0-9]+', '-', industry)}-{re.sub(r'[^a-z0-9]+', '-', geo)}",
                "industry": industry,
                "geo": geo,
                "roles": [],
                "size": client.get("size", ""),
                "trigger": "",
                "pain": "",
                "offer_angle": (profile.get("services") or [""])[0],
                "successes": 0,
                "failures": 0,
                "source": "client_list",
            },
        )
        role = client.get("role") or client.get("title")
        if role and role not in cell["roles"]:
            cell["roles"].append(role)
        if str(client.get("outcome", "won")).lower() in {"won", "client", "converted"}:
            cell["successes"] += 1
            if client.get("company"):
                won_names.append(client["company"])
        else:
            cell["failures"] += 1
    return {"cells": list(groups.values()), "existing_clients": won_names, "converted_examples": [c for c in clients if str(c.get("outcome", "won")).lower() in {"won", "client", "converted"}]}


def plan_volume(leads: list[dict], target_qualified_per_week: int, daily_cap: int, business_days: int = 5) -> dict:
    """Size the daily sourcing batch from the observed contacted→qualified rate, with a Wilson interval."""
    from core.stats import posterior_rate, wilson_interval

    contacted = [lead for lead in leads if lead.get("stage") in CONTACTED_STAGES]
    qualified = [lead for lead in leads if lead.get("stage") in {"qualified", "converted"}]
    observed = len(contacted) >= 10 and bool(qualified)
    rate = len(qualified) / len(contacted) if observed else PRIOR_QUALIFIED_RATE
    lower, centre, upper = wilson_interval(len(qualified), len(contacted)) if observed else (0.0, rate, 1.0)
    planning_rate = max(rate, 1e-3)
    weekly_contacts = math.ceil(target_qualified_per_week / planning_rate)
    daily = math.ceil(weekly_contacts / business_days)
    posterior = posterior_rate(len(qualified), len(contacted), prior_alpha=1.5, prior_beta=48.5) if observed else posterior_rate(0, 0, 1.5, 48.5)
    return {
        "target_qualified_per_week": target_qualified_per_week,
        "observed_rate": round(rate, 4),
        "rate_ci95": {"lower": round(lower, 4), "centre": round(centre, 4), "upper": round(upper, 4)},
        "posterior": posterior,
        "weekly_contacts_needed": weekly_contacts,
        "daily_contacts_planned": min(daily, daily_cap),
        "capacity_limited": daily > daily_cap,
        "daily_cap": daily_cap,
        "sample_contacted": len(contacted),
        "sample_qualified": len(qualified),
        "using_prior": not observed,
    }


def build_monthly_report(month: str, funnel: dict, by_icp: dict, money: dict, changes: list[dict], weights: dict) -> dict:
    lines = [f"Acquisition report for {month}."]
    sourced = funnel.get("sourced", 0) + sum(funnel.get(stage, 0) for stage in ("contacted", "replied", "positive", "qualified", "converted"))
    lines.append(
        f"Pipeline: {funnel.get('contacted', 0)} contacted, {funnel.get('positive', 0)} positive, "
        f"{funnel.get('qualified', 0)} qualified, {funnel.get('converted', 0)} converted from {sourced} sourced."
    )
    if money.get("cpcc_cents") is not None:
        lines.append(f"Cost per converted client: {money['cpcc_cents'] / 100:.2f}.")
    best = None
    for cell, counts in by_icp.items():
        if not cell or cell == "unassigned":
            continue
        contacted = sum(counts.get(stage, 0) for stage in ("contacted", "replied", "positive", "qualified", "converted"))
        wins = counts.get("positive", 0) + counts.get("qualified", 0) + counts.get("converted", 0)
        if contacted and (best is None or wins / contacted > best[1]):
            best = (cell, wins / contacted)
    if best:
        lines.append(f"Best segment: {best[0]} ({best[1]:.0%} positive or better), so it received more volume.")
    if changes:
        for change in changes:
            lines.append(f"Changed: {change['summary']} — why: {change['why']}")
    else:
        lines.append("No experiment reached enough sends to promote a winner this month.")
    if weights.get("status") == "trained":
        lines.append(
            f"Lead scoring now weights fit at {weights['fit']} and intent at {weights['intent']} "
            f"based on {weights['samples']} contacted leads."
        )
    return {"month": month, "text": " ".join(lines), "lines": lines, "generated_at": utcnow().isoformat()}
