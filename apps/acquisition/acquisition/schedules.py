import asyncio

from core.config import get_settings


def schedule_specs(tenant_id: str) -> list[tuple[str, str, dict, str]]:
    payload = {"tenant_id": tenant_id}
    return [
        (f"acq-daily-{tenant_id}", "AcquisitionDailyWorkflow", payload, "30 2 * * 1-5"),
        (f"acq-sweep-{tenant_id}", "AcquisitionSweepWorkflow", payload, "*/15 * * * *"),
        (f"acq-weekly-learning-{tenant_id}", "WeeklyLearningWorkflow", {**payload, "min_sends": 20}, "0 1 * * 1"),
        (f"acq-monthly-report-{tenant_id}", "MonthlyReportWorkflow", payload, "0 3 1 * *"),
    ]


async def ensure_schedules() -> list[dict]:
    from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleAlreadyRunningError, ScheduleSpec

    settings = get_settings()
    client = await Client.connect(settings.temporal_address)
    created = []
    for schedule_id, workflow, payload, cron in schedule_specs(settings.acquisition_tenant_id):
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
            created.append({"id": schedule_id, "workflow": workflow, "cron": cron, "status": "created"})
        except ScheduleAlreadyRunningError:
            created.append({"id": schedule_id, "workflow": workflow, "cron": cron, "status": "exists"})
        except Exception as exc:
            created.append({"id": schedule_id, "error": str(exc)})
    return created


def bootstrap_schedules() -> list[dict]:
    from core.temporal_gw import temporal_available

    specs = schedule_specs(get_settings().acquisition_tenant_id)
    if not temporal_available():
        return [
            {"id": sid, "workflow": wf, "cron": cron, "mode": "in_process", "status": "autopilot"}
            for sid, wf, _payload, cron in specs
        ]
    try:
        return asyncio.run(ensure_schedules())
    except Exception:
        return [
            {"id": sid, "workflow": wf, "cron": cron, "mode": "in_process", "status": "autopilot"}
            for sid, wf, _payload, cron in specs
        ]
