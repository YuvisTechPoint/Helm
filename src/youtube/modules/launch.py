from datetime import datetime

from core.errors import PublishingBlocked
from youtube.modules.planner import assert_cadence


def schedule_publication(
    *,
    audit_approved: bool,
    week_counts: dict,
    kind: str,
    when: datetime,
) -> dict:
    if not audit_approved:
        raise PublishingBlocked("public scheduling waits for the API compliance audit")
    assert_cadence(week_counts, kind)
    return {"privacy_status": "public", "kind": kind, "when": when.isoformat()}
