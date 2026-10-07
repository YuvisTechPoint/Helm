from datetime import datetime, timedelta

SNAPSHOTS = [
    ("2h", timedelta(hours=2)),
    ("24h", timedelta(hours=24)),
    ("48h", timedelta(hours=48)),
    ("7d", timedelta(days=7)),
    ("28d", timedelta(days=28)),
]

def blank_metrics() -> dict:
    return {
        "views": 0,
        "averageViewDuration": 0,
        "likes": 0,
        "subscribersGained": 0,
        "subscribersLost": 0,
        "videoThumbnailImpressions": 0,
        "videoThumbnailImpressionsClickRate": 0,
        "trafficSources": [],
        "retentionCurve": [],
        "audienceGeography": [],
    }


ANALYTICS_METRICS = [
    "views",
    "averageViewDuration",
    "likes",
    "subscribersGained",
    "subscribersLost",
    "videoThumbnailImpressions",
    "videoThumbnailImpressionsClickRate",
]


def snapshot_plan(published_at: datetime) -> list[dict]:
    return [{"label": label, "at": (published_at + delta).isoformat()} for label, delta in SNAPSHOTS]


def record_snapshot(store: dict, video_id: str, label: str, metrics: dict, captured_at: str) -> dict:
    key = (video_id, label)
    if key in store:
        return store[key]
    row = {"video_id": video_id, "label": label, "metrics": metrics, "captured_at": captured_at}
    store[key] = row
    return row


def learn_publish_hour(snapshots: list[dict]) -> int | None:
    if not snapshots:
        return None
    best = max(snapshots, key=lambda row: row.get("views", 0))
    return int(best["hour"])


def metrics_from_analytics_api(response: dict) -> dict:
    """Parse a YouTube Analytics API report into the internal metrics shape."""
    metrics = blank_metrics()
    headers = response.get("columnHeaders") or []
    rows = response.get("rows") or []
    if not rows:
        return metrics
    names = [header.get("name", "") for header in headers]
    values = rows[0]
    for name, value in zip(names, values):
        if name in metrics:
            metrics[name] = value
    impressions = metrics.get("videoThumbnailImpressions") or 0
    ctr = metrics.get("videoThumbnailImpressionsClickRate") or 0
    if impressions and ctr and not metrics.get("views"):
        metrics["views"] = int(impressions * ctr)
    return metrics


def funnel_from_metrics(metrics: dict, *, age_hours: float, channel_median_views: float) -> dict:
    """Build diagnostician funnel inputs from collected analytics."""
    impressions = float(metrics.get("videoThumbnailImpressions") or 0)
    views = float(metrics.get("views") or 0)
    ctr = float(metrics.get("videoThumbnailImpressionsClickRate") or 0)
    avg_duration = float(metrics.get("averageViewDuration") or 0)
    retention_first_30 = min(1.0, avg_duration / 30.0) if avg_duration else 0.35
    subs_gained = float(metrics.get("subscribersGained") or 0)
    subs_per_1000 = (subs_gained / views * 1000.0) if views else 0.0
    impressions_ratio = (impressions / channel_median_views) if channel_median_views else 1.0
    return {
        "age_hours": age_hours,
        "views": views,
        "channel_median_views": channel_median_views,
        "impressions_ratio": impressions_ratio,
        "ctr": ctr,
        "retention_first_30": retention_first_30,
        "retention_mid": max(0.1, retention_first_30 * 0.8),
        "subscribers_per_1000": subs_per_1000,
        "low_rpm_traffic_share": 0.1,
    }
