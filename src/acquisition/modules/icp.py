import json
import random

from acquisition.funnel import thompson_shares
from acquisition.providers.sourcing import source_leads

HYPOTHESIS_TEMPLATES = [
    {"name": "ecom-heads", "roles": ["Head of Ecommerce", "VP Growth"], "industry": "ecommerce", "angle": "checkout friction"},
    {"name": "founders", "roles": ["Founder", "CEO"], "industry": "dtc", "angle": "conversion leak"},
    {"name": "ops-leads", "roles": ["COO", "Head of Operations"], "industry": "retail", "angle": "operational efficiency"},
    {"name": "marketing", "roles": ["CMO", "Head of Marketing"], "industry": "ecommerce", "angle": "CAC reduction"},
    {"name": "local-retail", "roles": ["Owner"], "industry": "local retail", "angle": "local demand capture"},
]


def generate_icp_hypotheses(profile: dict, llm=None, count: int = 4) -> list[dict]:
    region = profile.get("region", "india")
    service = profile["services"][0] if profile.get("services") else "conversion audit"
    cells = []
    for template in HYPOTHESIS_TEMPLATES[:count]:
        cell = {
            **template,
            "region": region,
            "angle": service,
            "market_size_estimate": 5000,
            "sources": ["profile://services", "fixture://market"],
            "successes": 0,
            "failures": 0,
            "budget_share": 0.0,
        }
        cells.append(cell)
    if llm is not None:
        try:
            raw = llm.complete(
                "Return JSON array of 4 ICP cells with keys name, roles, industry, region, angle, market_size_estimate, pain.",
                json.dumps({"profile": profile}),
            )
            data = json.loads(raw)
            if isinstance(data, list) and data:
                cells = [{**c, "successes": 0, "failures": 0, "budget_share": 0.0, "sources": ["llm://hypothesis"]} for c in data[:count]]
        except Exception:
            pass
    return cells


def allocate_bandit(cells: list[dict], rng: random.Random | None = None) -> list[dict]:
    shares = thompson_shares(cells, rng)
    allocated = []
    for cell, share in zip(cells, shares):
        allocated.append({**cell, "budget_share": round(share, 4)})
    return allocated


def pick_cell(cells: list[dict], rng: random.Random | None = None) -> dict:
    allocated = allocate_bandit(cells, rng)
    rng = rng or random.Random()
    weights = [cell["budget_share"] for cell in allocated]
    return rng.choices(allocated, weights=weights, k=1)[0]


def sample_leads_for_cell(cell: dict, limit: int = 5) -> list[dict]:
    leads = []
    for lead in source_leads(cell)[:limit]:
        stamped = {
            **lead,
            "industry": lead.get("industry") or cell.get("industry", ""),
            "title": lead.get("title") or (cell.get("roles") or [""])[0],
            "geo": lead.get("geo") or cell.get("geo") or cell.get("region", ""),
            "icp_cell": cell.get("name"),
        }
        leads.append(stamped)
    return leads


def record_outcome(cell: dict, positive: bool) -> dict:
    if positive:
        cell["successes"] = cell.get("successes", 0) + 1
    else:
        cell["failures"] = cell.get("failures", 0) + 1
    return cell


def generate_icp(profile: dict, llm=None) -> dict:
    """Backward-compatible single-cell ICP for activities and tests."""
    cells = generate_icp_hypotheses(profile, llm, count=1)
    return cells[0] if cells else {"roles": ["Head of Ecommerce"], "industry": "ecommerce", "angle": profile.get("services", ["audit"])[0]}
