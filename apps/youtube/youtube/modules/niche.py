from dataclasses import dataclass

WEIGHTS = {
    "rpm": 0.20,
    "demand": 0.20,
    "competition_gap": 0.20,
    "original": 0.20,
    "policy": 0.10,
    "evergreen": 0.10,
}

# Factor scores are 1-5. Policy stores risk; the score uses the inverse.
CANDIDATES = [
    {"slug": "applied-psychology", "rpm": 4, "demand": 4, "competition_gap": 4, "original": 5, "policy_risk": 2, "evergreen": 4},
    {"slug": "personal-finance", "rpm": 5, "demand": 4, "competition_gap": 2, "original": 5, "policy_risk": 5, "evergreen": 4},
    {"slug": "history-mini-docs", "rpm": 3, "demand": 4, "competition_gap": 3, "original": 4, "policy_risk": 3, "evergreen": 4},
    {"slug": "literary-analysis", "rpm": 3, "demand": 3, "competition_gap": 4, "original": 3, "policy_risk": 2, "evergreen": 4},
    {"slug": "horror-narration", "rpm": 2, "demand": 3, "competition_gap": 3, "original": 2, "policy_risk": 4, "evergreen": 2},
    {"slug": "sleep-ambience", "rpm": 3, "demand": 3, "competition_gap": 2, "original": 1, "policy_risk": 5, "evergreen": 3},
]


@dataclass
class NicheChoice:
    slug: str
    score: float
    scores: dict[str, float]


def _clamp(value: float) -> float:
    return max(1.0, min(5.0, value))


def score_candidate(row: dict) -> float:
    policy = 6 - row["policy_risk"]
    parts = {
        "rpm": row["rpm"],
        "demand": row["demand"],
        "competition_gap": row["competition_gap"],
        "original": row["original"],
        "policy": policy,
        "evergreen": row["evergreen"],
    }
    return round(sum(parts[key] * WEIGHTS[key] for key in WEIGHTS), 3)


def competition_gap_from_videos(videos: list[dict]) -> float | None:
    if not videos:
        return None
    small = sum(1 for video in videos if int(video.get("channel_subscribers", 0)) < 50_000)
    share = small / len(videos)
    return _clamp(1 + 4 * share)


def scout(videos_by_slug: dict[str, list[dict]] | None = None) -> NicheChoice:
    videos_by_slug = videos_by_slug or {}
    ranked: list[tuple[float, dict]] = []
    table: dict[str, float] = {}
    for row in CANDIDATES:
        current = dict(row)
        live_gap = competition_gap_from_videos(videos_by_slug.get(row["slug"], []))
        if live_gap is not None:
            current["competition_gap"] = live_gap
        value = score_candidate(current)
        table[row["slug"]] = value
        ranked.append((value, current))
    ranked.sort(key=lambda item: item[0], reverse=True)
    winner = ranked[0][1]
    return NicheChoice(slug=winner["slug"], score=table[winner["slug"]], scores=table)


def quarterly_due(last_run_ordinal: int, today_ordinal: int) -> bool:
    return today_ordinal - last_run_ordinal >= 90
