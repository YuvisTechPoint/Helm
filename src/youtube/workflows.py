from datetime import timedelta

from temporalio import workflow


@workflow.defn
class ProduceOneWorkflow:
    @workflow.run
    async def run(self, topic: dict) -> dict:
        brief = await workflow.execute_activity(
            "m5_research",
            {"slug": topic["slug"].replace("-short", "")},
            start_to_close_timeout=timedelta(minutes=10),
        )
        previous = topic.get("previous_format")
        competitors = topic.get("competitor_titles", ["scary stories compilation volume twelve"])
        script = None
        gate = {"reasons": [], "decision": "rewrite"}
        for attempt in range(3):
            script = await workflow.execute_activity(
                "m6_script",
                {
                    "topic": topic,
                    "brief": brief,
                    "previous_format": previous,
                    "rewrite_notes": None if attempt == 0 else gate["reasons"],
                },
                start_to_close_timeout=timedelta(minutes=10),
            )
            gate = await workflow.execute_activity(
                "m7_quality_gate",
                {
                    "script": script,
                    "brief": brief,
                    "competitor_titles": competitors,
                    "past_scripts": topic.get("past_scripts", []),
                    "previous_format": previous,
                },
                start_to_close_timeout=timedelta(minutes=5),
            )
            if gate["decision"] == "pass":
                break
            if gate["decision"] == "reject" or attempt == 2:
                await workflow.execute_activity(
                    "m14_record_exception",
                    {"kind": "quality_gate", "message": f"dropped {topic['slug']}"},
                    start_to_close_timeout=timedelta(minutes=1),
                )
                return {"status": "dropped", "slug": topic["slug"], "gate": gate}
        voice = await workflow.execute_activity(
            "m8_voice",
            {"narration": script["hook"] + " " + script["body"], "destination": f"{topic['slug']}.wav"},
            start_to_close_timeout=timedelta(minutes=10),
        )
        rendered = await workflow.execute_activity(
            "m9_render",
            {
                "topic": topic,
                "script": script,
                "target_seconds": max(30, int(topic.get("target_seconds", 120)) // 4),
                "assets": [{"key": f"{topic['slug']}-diagram", "kind": "diagram", "licence": "original", "synthetic": False}],
            },
            start_to_close_timeout=timedelta(minutes=30),
        )
        packaging = await workflow.execute_activity(
            "m10_packaging",
            {"title": script["title"], "slug": topic["slug"], "competitor_titles": competitors},
            start_to_close_timeout=timedelta(minutes=5),
        )
        published = await workflow.execute_activity(
            "m11_publish",
            {
                "idempotency_key": f"activity-{topic['slug']}",
                "title": packaging["titles"][0]["title"],
                "description": script["ending"],
                "uses_ai_voice": voice["synthetic"],
                "provisional_research": brief["provisional"],
                "asset_key": rendered["key"],
                "kind": topic.get("kind", "long"),
                "thumbnail_path": packaging["thumbnails"][0].get("path") if packaging.get("thumbnails") else None,
            },
            start_to_close_timeout=timedelta(minutes=20),
        )
        return {
            "status": "published_private",
            "slug": topic["slug"],
            "youtube_id": published["youtube_id"],
            "privacy_status": published["privacy_status"],
            "scenes": rendered.get("scenes", 0),
            "bytes": rendered.get("bytes", 0),
            "format_name": script["format_name"],
        }


@workflow.defn
class ProducePrivateWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        return await workflow.execute_activity(
            "m14_private_dry_run",
            payload,
            start_to_close_timeout=timedelta(hours=2),
        )


@workflow.defn
class WeeklyPlanWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        niche = await workflow.execute_activity(
            "m2_niche_scout",
            payload,
            start_to_close_timeout=timedelta(minutes=10),
        )
        discovered = await workflow.execute_activity(
            "m3_discover_competitors",
            {"keywords": payload.get("keywords", ["applied psychology"]), "cap": 20},
            start_to_close_timeout=timedelta(minutes=20),
        )
        report = await workflow.execute_activity(
            "m3_competitor_report",
            payload.get("competitor_payload", {"videos": []}),
            start_to_close_timeout=timedelta(minutes=10),
        )
        return {"niche": niche, "discovered": discovered, "outliers": len(report.get("outliers", []))}


@workflow.defn
class CollectMetricsWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        plan = await workflow.execute_activity(
            "m12_snapshot_plan",
            {"published_at": payload["published_at"]},
            start_to_close_timeout=timedelta(minutes=5),
        )
        captured = []
        for point in plan["plan"]:
            row = await workflow.execute_activity(
                "m12_collect_metrics",
                {
                    "video_id": payload["video_id"],
                    "label": point["label"],
                    "start_date": payload.get("start_date", "2026-01-01"),
                    "end_date": payload.get("end_date", "2026-12-31"),
                    "metrics": payload.get("metrics", {}),
                },
                start_to_close_timeout=timedelta(minutes=10),
            )
            captured.append(row)
        return {"video_id": payload["video_id"], "snapshots": captured}


@workflow.defn
class OptimizeVideoWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        diagnosis = await workflow.execute_activity(
            "m13_diagnose",
            {"funnel": payload["funnel"]},
            start_to_close_timeout=timedelta(minutes=5),
        )
        if diagnosis.get("action") != "fix":
            return diagnosis
        return await workflow.execute_activity(
            "m13_apply_fix",
            {
                "video_id": payload["video_id"],
                "funnel": payload["funnel"],
                "new_value": payload.get("new_value", "next-ranked"),
                "current_metadata": payload.get("current_metadata", {}),
            },
            start_to_close_timeout=timedelta(minutes=10),
        )
