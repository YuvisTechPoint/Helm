from typing import Any

from core.temporal_gw import dispatch


def start_workflow(workflow: str, payload: dict, workflow_id: str | None = None) -> dict:
    return dispatch(workflow, payload, workflow_id, run_sync_workflow)


def run_sync_workflow(name: str, payload: dict) -> Any:
    if name == "ProducePrivateWorkflow":
        from youtube.activities import m14_private_dry_run

        return m14_private_dry_run(payload)
    if name == "ProduceOneWorkflow":
        from youtube.activities import (
            m10_packaging,
            m11_publish,
            m5_research,
            m6_script,
            m7_quality_gate,
            m8_voice,
            m9_visuals,
        )

        brief = m5_research({"slug": payload["slug"]})
        script = m6_script({"topic": payload, "brief": brief, "previous_format": None, "rewrite_notes": None})
        gate = m7_quality_gate(
            {
                "script": script,
                "brief": brief,
                "competitor_titles": payload.get("competitor_titles", []),
                "past_scripts": [],
                "previous_format": None,
            }
        )
        if gate["decision"] != "pass":
            return {"status": "dropped", "gate": gate}
        voice = m8_voice({"narration": script["hook"] + " " + script["body"], "destination": f"{payload['slug']}.wav"})
        visuals = m9_visuals(
            {
                "slug": payload["slug"],
                "target_seconds": max(30, int(payload.get("target_seconds", 120)) // 4),
                "assets": [{"key": f"{payload['slug']}-diagram", "kind": "diagram", "licence": "original", "synthetic": False}],
            }
        )
        packaging = m10_packaging({"title": script["title"], "competitor_titles": payload.get("competitor_titles", [])})
        published = m11_publish(
            {
                "idempotency_key": f"sync-{payload['slug']}",
                "title": packaging["titles"][0]["title"],
                "description": script["ending"],
                "uses_ai_voice": voice["synthetic"],
                "provisional_research": brief["provisional"],
            }
        )
        return {"status": "published_private", "published": published, "scenes": visuals["scenes"]}
    if name == "WeeklyPlanWorkflow":
        from youtube.activities import m2_niche_scout, m3_competitor_report

        return {"niche": m2_niche_scout(payload), "report": m3_competitor_report(payload.get("competitor_payload", {"videos": []}))}
    if name == "CollectMetricsWorkflow":
        from youtube.activities import m12_collect_metrics, m12_snapshot_plan

        plan = m12_snapshot_plan({"published_at": payload.get("published_at") or __import__("core.timeutil", fromlist=["utcnow"]).utcnow().isoformat()})
        snapshots = []
        for point in plan["plan"]:
            snapshots.append(
                m12_collect_metrics(
                    {
                        "video_id": payload["video_id"],
                        "label": point["label"],
                        "start_date": point.get("start_date", ""),
                        "end_date": point.get("end_date", ""),
                        "metrics": payload.get("metrics") or {},
                    }
                )
            )
        return {"video_id": payload["video_id"], "snapshots": snapshots}
    if name == "OptimizeVideoWorkflow":
        from youtube.activities import m13_diagnose, m13_apply_fix

        funnel = payload.get("funnel") or {
            "age_hours": 72,
            "views": 80,
            "channel_median_views": 120,
            "impressions_ratio": 1.0,
            "ctr": 0.02,
            "retention_first_30": 0.5,
            "retention_mid": 0.5,
            "subscribers_per_1000": 4,
            "low_rpm_traffic_share": 0.1,
        }
        diagnosis = m13_diagnose({"funnel": funnel})
        if diagnosis.get("action") != "fix":
            return {"diagnosis": diagnosis}
        fix = m13_apply_fix({"video_id": payload["video_id"], "funnel": funnel, "new_value": payload.get("new_value", "next")})
        return {"diagnosis": diagnosis, "fix": fix}
    raise ValueError(f"unknown workflow {name}")
