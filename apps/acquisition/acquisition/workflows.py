from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

with workflow.unsafe.imports_passed_through():
    from temporalio.workflow import ParentClosePolicy

ACTIVITY_TIMEOUT = timedelta(minutes=5)
RETRY = RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=30))
RETRYABLE_BLOCKS = ("outside business hours", "tenant daily outreach cap reached", "no warmed, unpaused mailbox available")


async def _act(name: str, payload: dict, timeout: timedelta = ACTIVITY_TIMEOUT):
    return await workflow.execute_activity(name, payload, start_to_close_timeout=timeout, retry_policy=RETRY)


@workflow.defn
class LeadSequenceWorkflow:
    """One long-lived workflow per lead: first touch plus value-adding follow-ups over ~14 days."""

    @workflow.run
    async def run(self, payload: dict) -> dict:
        tenant_id = payload.get("tenant_id", "local")
        email = (payload.get("email") or payload["lead"]["email"]).lower()
        ref = {"tenant_id": tenant_id, "email": email}
        plan = await _act("acq_sequence_plan", ref)
        window = {"timezone": plan["timezone"], "send_time": plan["send_time"]}

        first: dict = {}
        for _ in range(6):
            delay = await _act("acq_send_window_delay", window)
            await workflow.sleep(timedelta(seconds=delay))
            first = await _act("acq_first_touch", ref)
            if first.get("status") != "blocked" or first.get("reason") not in RETRYABLE_BLOCKS:
                break
            await workflow.sleep(timedelta(hours=4))
        if first.get("status") != "contacted":
            return {"sent": False, "status": first.get("status"), "reason": first.get("reason")}

        touches = 1
        offsets = plan["offsets"]
        for index in range(1, len(offsets)):
            await workflow.sleep(timedelta(days=offsets[index] - offsets[index - 1]))
            delay = await _act("acq_send_window_delay", window)
            await workflow.sleep(timedelta(seconds=delay))
            gate = await _act("sequence_should_continue", ref)
            if not gate.get("continue"):
                return {"sent": True, "touches": touches, "stopped": gate.get("reason")}
            result = await _act("acq_follow_up", {**ref, "index": index})
            if result.get("status") == "sent":
                touches += 1
            elif result.get("status") == "stopped":
                return {"sent": True, "touches": touches, "stopped": result.get("reason")}
        return {"sent": True, "touches": touches}


@workflow.defn
class InboundReplyWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        return await _act("classify_inbound", payload)


@workflow.defn
class AcquisitionDailyWorkflow:
    """Always-on sourcing sized to the weekly target; each ready lead gets its own sequence workflow."""

    @workflow.run
    async def run(self, payload: dict) -> dict:
        tenant_id = payload["tenant_id"]
        daily = await _act("acq_run_daily", {"tenant_id": tenant_id}, timeout=timedelta(minutes=30))
        started = []
        for email in daily.get("ready", []):
            try:
                await workflow.start_child_workflow(
                    LeadSequenceWorkflow.run,
                    {"tenant_id": tenant_id, "email": email},
                    id=f"lead-seq-{tenant_id}-{email}",
                    parent_close_policy=ParentClosePolicy.ABANDON,
                )
                started.append(email)
            except WorkflowAlreadyStartedError:
                continue
        return {"plan": daily.get("plan"), "started": started, "status": daily.get("status")}


@workflow.defn
class WeeklyLearningWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        return await _act("acq_weekly_learning", payload, timeout=timedelta(minutes=30))


@workflow.defn
class MonthlyReportWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        return await _act("acq_monthly_report", payload, timeout=timedelta(minutes=15))


@workflow.defn
class AcquisitionSweepWorkflow:
    """Calls, re-contacts, meeting reminders, closing follow-ups and the escalation SLA."""

    @workflow.run
    async def run(self, payload: dict) -> dict:
        return await _act("acq_sweep", payload, timeout=timedelta(minutes=15))


ACQUISITION_WORKFLOWS = [
    LeadSequenceWorkflow,
    InboundReplyWorkflow,
    AcquisitionDailyWorkflow,
    WeeklyLearningWorkflow,
    MonthlyReportWorkflow,
    AcquisitionSweepWorkflow,
]
