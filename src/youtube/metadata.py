"""Apply allowed metadata changes from the diagnostician and push to YouTube when configured."""

ALLOWED = {"title", "thumbnail", "description", "tags", "chapters", "playlist", "end_screen", "publish_time"}


def apply_metadata_change(video_id: str, lever: str, new_value: str, current: dict) -> dict:
    if lever not in ALLOWED:
        raise ValueError(f"lever {lever} is not allowed")
    updated = dict(current)
    if lever == "title":
        updated["title"] = new_value
    elif lever == "description":
        updated["description"] = new_value
    elif lever == "tags":
        updated["tags"] = new_value.split(",") if isinstance(new_value, str) else new_value
    elif lever == "thumbnail":
        updated["thumbnail_variant"] = new_value
    elif lever == "playlist":
        updated["playlist_id"] = new_value
    elif lever == "publish_time":
        updated["publish_at"] = new_value
    else:
        updated[lever] = new_value
    updated["video_id"] = video_id
    updated["applied_lever"] = lever
    return updated


def push_metadata_change(
    client,
    video_id: str,
    lever: str,
    new_value: str,
    current: dict,
    *,
    thumbnail_bytes: bytes | None = None,
) -> dict:
    """Update local metadata model and push allowed levers to the YouTube Data API."""
    updated = apply_metadata_change(video_id, lever, new_value, current)
    api: dict = {"pushed": False, "lever": lever}
    if client is None:
        api["reason"] = "no client configured"
        return {"updated": updated, "api": api}

    if lever in {"title", "description", "tags"} and hasattr(client, "update_video"):
        snippet: dict = {}
        if lever == "title":
            snippet["title"] = new_value
        elif lever == "description":
            snippet["description"] = new_value
        elif lever == "tags":
            snippet["tags"] = updated.get("tags", [])
        try:
            api = {"pushed": True, "result": client.update_video(video_id, snippet=snippet)}
        except Exception as exc:
            api = {"pushed": False, "error": str(exc), "lever": lever}

    if lever == "thumbnail" and hasattr(client, "set_thumbnail"):
        if thumbnail_bytes is None and isinstance(new_value, str):
            try:
                with open(new_value, "rb") as handle:
                    thumbnail_bytes = handle.read()
            except OSError:
                thumbnail_bytes = None
        if thumbnail_bytes:
            try:
                api = {"pushed": True, "result": client.set_thumbnail(video_id, thumbnail_bytes)}
            except Exception as exc:
                api = {"pushed": False, "error": str(exc), "lever": lever}
        else:
            api = {"pushed": False, "reason": "thumbnail bytes missing", "lever": lever}

    if lever == "publish_time" and hasattr(client, "update_video"):
        try:
            api = {"pushed": True, "result": client.update_video(video_id, status={"publishAt": new_value})}
        except Exception as exc:
            api = {"pushed": False, "error": str(exc), "lever": lever}

    return {"updated": updated, "api": api}
