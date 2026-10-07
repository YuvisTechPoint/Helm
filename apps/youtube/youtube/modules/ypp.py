SUBSCRIBER_TARGET = 1000
WATCH_HOUR_TARGET = 4000


def ypp_progress(subscribers: int, public_watch_hours: float) -> dict:
    eligible = subscribers >= SUBSCRIBER_TARGET and public_watch_hours >= WATCH_HOUR_TARGET
    return {
        "subscribers": subscribers,
        "subscriber_target": SUBSCRIBER_TARGET,
        "public_watch_hours": public_watch_hours,
        "watch_hour_target": WATCH_HOUR_TARGET,
        "eligible": eligible,
        "human_application_required": True,
        "auto_apply": False,
        "checklist": [
            "Confirm the channel is in good standing with zero strikes.",
            "Confirm 1,000 subscribers and 4,000 public watch hours.",
            "A person submits the YouTube Partner Program application once.",
        ],
    }


def apply_for_partner_program(_progress: dict):
    raise RuntimeError("Partner Program application is a one-time human step")
