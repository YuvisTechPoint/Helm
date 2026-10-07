"""Shared inference helpers: Wilson intervals, Beta posteriors, Thompson mixing."""

from __future__ import annotations

import math
import random


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float, float]:
    """Return (lower, centre, upper) of a Wilson score interval for a binomial rate."""
    if trials <= 0:
        return 0.0, 0.0, 1.0
    p = successes / trials
    z2 = z * z
    denom = 1.0 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denom
    margin = (z * math.sqrt((p * (1 - p) + z2 / (4 * trials)) / trials)) / denom
    return clamp(centre - margin), clamp(centre), clamp(centre + margin)


def wilson_lower_bound(successes: int, trials: int, z: float = 1.96) -> float:
    return wilson_interval(successes, trials, z)[0]


def beta_mean(alpha: float, beta: float) -> float:
    total = alpha + beta
    return alpha / total if total else 0.5


def beta_variance(alpha: float, beta: float) -> float:
    total = alpha + beta
    if total <= 0:
        return 0.25
    return (alpha * beta) / (total * total * (total + 1))


def posterior_rate(successes: int, trials: int, prior_alpha: float = 3.0, prior_beta: float = 97.0) -> dict:
    """Beta-Binomial posterior for a conversion/CTR-like rate with a weakly informative prior."""
    alpha = prior_alpha + max(0, successes)
    beta = prior_beta + max(0, trials - successes)
    mean = beta_mean(alpha, beta)
    variance = beta_variance(alpha, beta)
    std = math.sqrt(variance)
    return {
        "alpha": round(alpha, 4),
        "beta": round(beta, 4),
        "mean": round(mean, 6),
        "std": round(std, 6),
        "p05": round(clamp(mean - 1.645 * std), 6),
        "p95": round(clamp(mean + 1.645 * std), 6),
        "samples": trials,
    }


def thompson_shares(cells: list[dict], rng: random.Random | None = None, exploration_floor: float = 0.08) -> list[float]:
    """Thompson sampling over Beta(1+s, 1+f) with a floor so new cells keep exploring."""
    if not cells:
        return []
    rng = rng or random.Random(0)
    draws = [rng.betavariate(1 + cell.get("successes", 0), 1 + cell.get("failures", 0)) for cell in cells]
    total = sum(draws) or 1.0
    raw = [draw / total for draw in draws]
    count = len(raw)
    floor = min(exploration_floor, 1.0 / count)
    remaining = 1.0 - floor * count
    if remaining <= 0:
        return [1.0 / count] * count
    mixed = [floor + remaining * share for share in raw]
    renormal = sum(mixed) or 1.0
    return [share / renormal for share in mixed]


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
