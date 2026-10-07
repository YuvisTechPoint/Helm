from statistics import median

from core.errors import TermsViolation

CHANNEL_CAP = 100
OUTLIER_RATIO = 3.0


def download_competitor_video(*_args, **_kwargs):
    raise TermsViolation("YouTube Terms forbid downloading or reuploading other creators' videos")


def add_channel(tracked: list[dict], channel: dict) -> None:
    if any(row["channel_id"] == channel["channel_id"] for row in tracked):
        return
    if len(tracked) >= CHANNEL_CAP:
        raise ValueError("tracked channel cap is 100")
    tracked.append({"channel_id": channel["channel_id"], "title": channel.get("title", ""), "subscriber_count": channel.get("subscriber_count", 0)})


def outlier_ratio(views: float, same_age_views: list[float]) -> float:
    sample = list(same_age_views)[-20:]
    if not sample:
        return 0.0
    baseline = median(sample)
    if baseline <= 0:
        return 0.0
    return views / baseline


def is_outlier(ratio: float) -> bool:
    return ratio >= OUTLIER_RATIO


def label_title(title: str) -> str:
    lowered = title.lower().strip()
    if lowered.startswith("why "):
        return "why_question"
    if "psychology of" in lowered:
        return "psychology_of"
    if lowered.endswith("?"):
        return "question"
    return "statement"


def pattern_report(videos: list[dict]) -> dict:
    """videos items need title, views, same_age_views, thumbnail_url. No media files."""
    outliers = []
    for video in videos:
        if video.get("caption_path") or video.get("file_path"):
            raise TermsViolation("analyst accepts public metadata and thumbnail URLs only")
        ratio = outlier_ratio(video["views"], video.get("same_age_views", []))
        if is_outlier(ratio):
            outliers.append(
                {
                    "video_id": video.get("video_id"),
                    "title": video["title"],
                    "ratio": round(ratio, 3),
                    "title_structure": label_title(video["title"]),
                    "thumbnail_url": video.get("thumbnail_url"),
                    "duration_seconds": video.get("duration_seconds"),
                }
            )
    structures: dict[str, int] = {}
    for row in outliers:
        structures[row["title_structure"]] = structures.get(row["title_structure"], 0) + 1
    return {"outliers": outliers, "title_structures": structures, "tracked_media": "metadata_only"}
