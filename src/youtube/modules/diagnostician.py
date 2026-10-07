from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.errors import OneChangeError, PublishingBlocked

ALLOWED_LEVERS = {
    "title",
    "thumbnail",
    "description",
    "tags",
    "chapters",
    "playlist",
    "end_screen",
    "publish_time",
    "topic_weight",
    "hook_threshold",
}
FORBIDDEN_LEVERS = {"delete_reupload", "mass_metadata_rewrite", "fake_engagement", "paid_bot_promotion"}
PACKAGING_LEVERS = {"title", "thumbnail"}


@dataclass
class Funnel:
    age_hours: float
    views: float
    channel_median_views: float
    impressions_ratio: float
    ctr: float
    retention_first_30: float
    retention_mid: float
    subscribers_per_1000: float
    low_rpm_traffic_share: float
    channel_wide_drop: bool = False
    competitors_also_dropped: bool = False
    strike: bool = False
    limited_ads: bool = False


@dataclass
class Change:
    video_id: str
    lever: str
    baseline: float
    status: str
    recheck_at: datetime | None = None
    recheck_uploads: int | None = None
    previous_value: str = ""
    new_value: str = ""


@dataclass
class Optimizer:
    changes: list[Change] = field(default_factory=list)
    topic_weights: dict[str, float] = field(default_factory=dict)
    hook_threshold: float = 0.0
    missed_cycles: list[bool] = field(default_factory=list)
    pivot: dict | None = None

    def open_change(self, video_id: str) -> Change | None:
        for change in self.changes:
            if change.video_id == video_id and change.status == "open":
                return change
        return None


def _funnel_stats(funnel: Funnel) -> dict:
    from core.stats import posterior_rate

    impressions = max(funnel.impressions_ratio * max(funnel.views, 1.0) / max(funnel.ctr, 1e-6), funnel.views)
    clicks = funnel.ctr * impressions
    ctr_post = posterior_rate(int(round(clicks)), int(round(impressions)), prior_alpha=3, prior_beta=97)
    relative_views = funnel.views / funnel.channel_median_views if funnel.channel_median_views else 1.0
    return {
        "ctr_posterior": ctr_post,
        "relative_views": round(relative_views, 3),
        "retention_gap": round(funnel.retention_first_30 - funnel.retention_mid, 3),
    }


def diagnose(funnel: Funnel, history: list[Change]) -> dict:
    stats = _funnel_stats(funnel) if funnel.age_hours >= 0 else {}
    if funnel.age_hours < 48:
        return {"action": "hold", "lever": None, "reason": "nothing is judged before 48 hours", "stats": stats}
    if funnel.channel_wide_drop:
        if funnel.strike or funnel.limited_ads:
            return {"action": "kill_switch", "lever": None, "reason": "strike or limited ads", "stats": stats}
        if funnel.competitors_also_dropped:
            return {"action": "hold", "lever": None, "reason": "competitors dropped too", "stats": stats}
        return {"action": "exception", "lever": None, "reason": "channel drop needs a policy check", "stats": stats}

    impressions_low = funnel.impressions_ratio < 0.5
    ctr_ok = funnel.ctr >= 0.03
    retention_ok = funnel.retention_first_30 >= 0.30
    if impressions_low and ctr_ok and retention_ok:
        return {"action": "fix", "lever": "topic_weight", "reason": "low demand or weak audience match", "stats": stats}
    if funnel.ctr < 0.03:
        lever = "title"
        if any(change.lever == "title" and change.status != "rolled_back" for change in history):
            lever = "thumbnail"
        return {"action": "fix", "lever": lever, "reason": "packaging CTR under 3%", "stats": stats}
    if funnel.ctr >= 0.05 and funnel.retention_first_30 < 0.30:
        return {"action": "fix", "lever": "hook_threshold", "reason": "hook does not confirm the promise", "stats": stats}
    if funnel.retention_first_30 >= 0.30 and funnel.retention_mid < 0.40:
        return {"action": "fix", "lever": "description", "reason": "mid-video drop; shorten future videos in this cluster", "stats": stats}
    strong_views = funnel.channel_median_views <= 0 or funnel.views >= funnel.channel_median_views
    if strong_views and funnel.subscribers_per_1000 < 3:
        return {"action": "fix", "lever": "end_screen", "reason": "views without a reason to subscribe", "stats": stats}
    if funnel.low_rpm_traffic_share > 0.5:
        return {"action": "fix", "lever": "topic_weight", "reason": "traffic skews to low-RPM countries", "stats": stats}
    return {"action": "none", "lever": None, "reason": "funnel is inside thresholds", "stats": stats}


def assert_allowed_lever(lever: str) -> None:
    if lever in FORBIDDEN_LEVERS or lever not in ALLOWED_LEVERS:
        raise PublishingBlocked(f"lever {lever} is not allowed")


def apply_fix(optimizer: Optimizer, video_id: str, funnel: Funnel, now: datetime, *, cluster: str = "general", new_value: str = "next") -> Change:
    diagnosis = diagnose(funnel, [change for change in optimizer.changes if change.video_id == video_id])
    lever = diagnosis["lever"]
    if diagnosis["action"] == "kill_switch":
        raise PublishingBlocked(diagnosis["reason"])
    if diagnosis["action"] != "fix" or lever is None:
        raise OneChangeError(diagnosis["reason"])
    assert_allowed_lever(lever)
    if optimizer.open_change(video_id):
        raise OneChangeError("one open change per video")
    if lever in PACKAGING_LEVERS:
        recheck_at = now + timedelta(hours=72)
        recheck_uploads = None
        baseline = funnel.ctr
    else:
        recheck_at = None
        recheck_uploads = 3
        baseline = funnel.retention_first_30 if lever == "hook_threshold" else funnel.views
    change = Change(
        video_id=video_id,
        lever=lever,
        baseline=baseline,
        status="open",
        recheck_at=recheck_at,
        recheck_uploads=recheck_uploads,
        previous_value="current",
        new_value=new_value,
    )
    optimizer.changes.append(change)
    if lever == "topic_weight":
        optimizer.topic_weights[cluster] = optimizer.topic_weights.get(cluster, 1.0) * 0.7
    if lever == "hook_threshold":
        optimizer.hook_threshold += 0.1
    return change


def review_change(change: Change, now: datetime, metric: float, uploads_since: int = 0) -> str:
    if change.status != "open":
        return change.status
    if change.recheck_at is not None and now < change.recheck_at:
        return "waiting"
    if change.recheck_uploads is not None and uploads_since < change.recheck_uploads:
        return "waiting"
    if metric <= change.baseline:
        change.status = "rolled_back"
        return "rolled_back"
    change.status = "kept"
    return "kept"


def record_cycle(optimizer: Optimizer, met_targets: bool) -> None:
    optimizer.missed_cycles.append(not met_targets)
    optimizer.missed_cycles = optimizer.missed_cycles[-3:]


def propose_pivot(optimizer: Optimizer, now: datetime, from_slug: str, to_slug: str) -> dict | None:
    if len(optimizer.missed_cycles) < 3 or not all(optimizer.missed_cycles):
        return None
    optimizer.pivot = {
        "from_slug": from_slug,
        "to_slug": to_slug,
        "proposed_at": now,
        "veto_until": now + timedelta(hours=72),
        "vetoed": False,
        "executed": False,
    }
    return optimizer.pivot


def veto_pivot(optimizer: Optimizer) -> None:
    if optimizer.pivot:
        optimizer.pivot["vetoed"] = True


def execute_pivot(optimizer: Optimizer, now: datetime) -> bool:
    pivot = optimizer.pivot
    if not pivot or pivot["vetoed"] or pivot["executed"]:
        return False
    if now < pivot["veto_until"]:
        return False
    pivot["executed"] = True
    return True
