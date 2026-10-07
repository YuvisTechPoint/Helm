import asyncio

from core.config import get_settings


async def ensure_schedules() -> list[dict]:
    from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec

    settings = get_settings()
    client = await Client.connect(settings.temporal_address)
    created = []
    specs = [
        ("weekly-plan", "WeeklyPlanWorkflow", {}, "0 9 * * 1"),
        ("private-dry-run", "ProducePrivateWorkflow", {}, "0 2 * * *"),
        ("metrics-sweep", "CollectMetricsWorkflow", {"video_id": "latest", "published_at": "2026-01-01T00:00:00+00:00"}, "0 */6 * * *"),
    ]
    for schedule_id, workflow, payload, cron in specs:
        try:
            await client.create_schedule(
                schedule_id,
                Schedule(
                    action=ScheduleActionStartWorkflow(
                        workflow,
                        payload,
                        id=f"{schedule_id}-run",
                        task_queue=settings.temporal_task_queue,
                    ),
                    spec=ScheduleSpec(cron_expressions=[cron]),
                ),
            )
            created.append({"id": schedule_id, "workflow": workflow, "cron": cron})
        except Exception as exc:
            created.append({"id": schedule_id, "error": str(exc)})
    return created


def bootstrap_schedules() -> list[dict]:
    from core.temporal_gw import temporal_available

    specs = [
        ("weekly-plan", "WeeklyPlanWorkflow", "0 9 * * 1"),
        ("private-dry-run", "ProducePrivateWorkflow", "0 2 * * *"),
        ("metrics-sweep", "CollectMetricsWorkflow", "0 */6 * * *"),
    ]
    if not temporal_available():
        return [{"id": sid, "workflow": wf, "cron": cron, "mode": "in_process", "status": "autopilot"} for sid, wf, cron in specs]
    try:
        return asyncio.run(ensure_schedules())
    except Exception:
        return [{"id": sid, "workflow": wf, "cron": cron, "mode": "in_process", "status": "autopilot"} for sid, wf, cron in specs]
