from datetime import date, timedelta

from core.errors import CadenceCap, RepeatTopic

MAX_LONG = 3
MAX_SHORTS = 5
LONG_WEEKDAYS = {0, 2, 4}
SHORT_WEEKDAYS = {0, 1, 2, 3, 4}


def topic_score(demand: float, gap: float, fit: float) -> float:
    return demand * gap * fit


def rank_topics(topics: list[dict]) -> list[dict]:
    return sorted(topics, key=lambda topic: topic_score(topic["demand"], topic["gap"], topic["fit"]), reverse=True)


def add_topic(backlog: list[dict], topic: dict, covered: set[str]) -> None:
    if topic["slug"] in covered or any(row["slug"] == topic["slug"] for row in backlog):
        raise RepeatTopic(topic["slug"])
    backlog.append(topic)


def assert_cadence(week_counts: dict, kind: str) -> None:
    if kind == "long" and week_counts.get("long", 0) >= MAX_LONG:
        raise CadenceCap("long-form cap is 3 per week")
    if kind == "short" and week_counts.get("short", 0) >= MAX_SHORTS:
        raise CadenceCap("Shorts cap is 5 per week")


def build_calendar(start: date, topics: list[dict]) -> list[dict]:
    """Schedule at most 3 long-form and 5 Shorts each week for 30 days."""
    if start.weekday() != 0:
        start = start - timedelta(days=start.weekday())
    ranked = rank_topics(topics)
    cursor = start
    end = start + timedelta(days=30)
    calendar = []
    used: set[str] = set()
    week_key = None
    counts = {"long": 0, "short": 0}
    pool = list(ranked)
    while cursor < end and pool:
        key = cursor.isocalendar()[:2]
        if key != week_key:
            week_key = key
            counts = {"long": 0, "short": 0}
        placed = False
        for kind, allowed_days, cap in (("long", LONG_WEEKDAYS, MAX_LONG), ("short", SHORT_WEEKDAYS, MAX_SHORTS)):
            if cursor.weekday() not in allowed_days or counts[kind] >= cap:
                continue
            match = next((topic for topic in pool if topic["kind"] == kind and topic["slug"] not in used), None)
            if match is None:
                continue
            calendar.append({**match, "planned_on": cursor.isoformat(), "series": match["cluster"]})
            used.add(match["slug"])
            pool.remove(match)
            counts[kind] += 1
            placed = True
            break
        cursor += timedelta(days=1)
        if not placed:
            continue
    return calendar
