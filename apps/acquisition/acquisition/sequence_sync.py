"""Synchronous fallback for multi-touch lead sequences when Temporal is unavailable."""


def run_lead_sequence_sync(payload: dict) -> dict:
    from acquisition.activities import (
        acq_follow_up,
        acq_first_touch,
        acq_sequence_plan,
        sequence_should_continue,
    )

    tenant_id = payload.get("tenant_id", "local")
    email = (payload.get("email") or payload["lead"]["email"]).lower()
    ref = {"tenant_id": tenant_id, "email": email}
    plan = acq_sequence_plan(ref)
    first = acq_first_touch({**ref, "force": payload.get("force", False)})
    if first.get("status") != "contacted":
        return {
            "sent": False,
            "status": first.get("status"),
            "reason": first.get("reason"),
            "mode": "sync",
            "plan": plan,
        }

    touches = 1
    for index in range(1, len(plan["offsets"])):
        gate = sequence_should_continue(ref)
        if not gate.get("continue"):
            return {
                "sent": True,
                "touches": touches,
                "stopped": gate.get("reason"),
                "mode": "sync",
                "plan": plan,
            }
        result = acq_follow_up({**ref, "index": index})
        if result.get("status") == "sent":
            touches += 1
        elif result.get("status") == "stopped":
            return {
                "sent": True,
                "touches": touches,
                "stopped": result.get("reason"),
                "mode": "sync",
                "plan": plan,
            }
    return {"sent": True, "touches": touches, "mode": "sync", "plan": plan}
