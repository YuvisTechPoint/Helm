from datetime import datetime, timezone

from youtube.models import TrackedChannel, VideoSnapshot


def discover_channels(client, keywords: list[str], cap: int = 100) -> list[dict]:
    channels: dict[str, dict] = {}
    for keyword in keywords:
        for item in client.search(keyword, max_results=10):
            channel_id = item.get("snippet", {}).get("channelId") or item.get("id", {}).get("channelId")
            if not channel_id or channel_id in channels:
                continue
            channels[channel_id] = {
                "channel_id": channel_id,
                "title": item.get("snippet", {}).get("channelTitle", ""),
                "subscriber_count": 0,
            }
            if len(channels) >= cap:
                break
        if len(channels) >= cap:
            break
    return list(channels.values())


def collect_snapshots(client, channel_id: str, video_ids: list[str], session=None) -> list[dict]:
    rows = []
    if not video_ids:
        return rows
    for item in client.list_videos(video_ids[:50]):
        video_id = item["id"]
        views = int(item.get("statistics", {}).get("viewCount", 0))
        title = item.get("snippet", {}).get("title", "")
        row = {
            "video_id": video_id,
            "channel_id": channel_id,
            "title": title,
            "age_label": "live",
            "views": views,
            "payload": item,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(row)
        if session is not None:
            session.add(
                VideoSnapshot(
                    video_id=video_id,
                    channel_id=channel_id,
                    title=title,
                    age_label="live",
                    views=views,
                    payload=item,
                )
            )
    if session is not None:
        session.commit()
    return rows


def persist_channels(session, channels: list[dict]) -> int:
    count = 0
    for channel in channels:
        existing = session.query(TrackedChannel).filter_by(channel_id=channel["channel_id"]).one_or_none()
        if existing is None:
            session.add(
                TrackedChannel(
                    channel_id=channel["channel_id"],
                    title=channel.get("title", ""),
                    subscriber_count=int(channel.get("subscriber_count", 0)),
                )
            )
            count += 1
    session.commit()
    return count
