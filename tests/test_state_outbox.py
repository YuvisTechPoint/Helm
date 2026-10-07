import pytest

from acquisition.lead_state import DEAL_MACHINE, LEAD_MACHINE
from acquisition.repository import AcquisitionRepository
from core.errors import InvalidTransition
from core.outbox import Outbox
from core.state_machine import StateMachine
from core.webhook_dedup import WebhookDedup
from youtube.topic_state import TOPIC_MACHINE


def test_lead_machine_rejects_invalid_transition():
    with pytest.raises(InvalidTransition):
        LEAD_MACHINE.transition("converted", "contacted")


def test_lead_machine_allows_valid_path():
    change = LEAD_MACHINE.transition("sourced", "contacted")
    assert change.to_state == "contacted"


def test_deal_machine_terminal():
    with pytest.raises(InvalidTransition):
        DEAL_MACHINE.transition("paid", "proposal_sent")


def test_topic_machine_failure_recovery():
    change = TOPIC_MACHINE.transition("gating", "retryable_failure")
    assert change.to_state == "retryable_failure"
    TOPIC_MACHINE.transition("retryable_failure", "gating")


def test_repository_update_stage_enforces_fsm():
    repo = AcquisitionRepository(None)
    repo.upsert_lead("local", "lead@example.com", {"stage": "sourced"})
    repo.update_stage("local", "lead@example.com", "contacted")
    with pytest.raises(InvalidTransition):
        repo.update_stage("local", "lead@example.com", "converted")


def test_outbox_publish_and_drain():
    outbox = Outbox(None)
    outbox.publish(
        event_type="lead_contacted",
        aggregate_type="lead",
        aggregate_id="lead@example.com",
        payload={"email": "lead@example.com"},
        tenant_id="local",
    )
    result = outbox.drain()
    assert result["published"] >= 1


def test_webhook_dedup():
    dedup = WebhookDedup(None)
    body = b'{"id":"evt-1"}'
    first = dedup.record("stripe", "evt-1", body)
    second = dedup.record("stripe", "evt-1", body)
    assert first["duplicate"] is False
    assert second["duplicate"] is True


def test_state_machine_self_transition():
    machine = StateMachine("test", {"open": {"closed"}}, terminal=set())
    assert machine.can_transition("open", "open") is True
