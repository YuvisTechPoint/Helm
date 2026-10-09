import pytest

from core.errors import InvalidTransition
from core.outbox import Outbox
from core.state_machine import StateMachine
from core.webhook_dedup import WebhookDedup
from youtube.topic_state import TOPIC_MACHINE


def test_topic_machine_failure_recovery():
    change = TOPIC_MACHINE.transition("gating", "retryable_failure")
    assert change.to_state == "retryable_failure"
    TOPIC_MACHINE.transition("retryable_failure", "gating")


def test_outbox_publish_and_drain():
    outbox = Outbox(None)
    outbox.publish(
        event_type="video_published",
        aggregate_type="video",
        aggregate_id="vid-1",
        payload={"video_id": "vid-1"},
        tenant_id="local",
    )
    result = outbox.drain()
    assert result["published"] >= 1


def test_webhook_dedup():
    dedup = WebhookDedup(None)
    body = b'{"id":"evt-1"}'
    first = dedup.record("youtube", "evt-1", body)
    second = dedup.record("youtube", "evt-1", body)
    assert first["duplicate"] is False
    assert second["duplicate"] is True


def test_state_machine_self_transition():
    machine = StateMachine("test", {"open": {"closed"}}, terminal=set())
    assert machine.can_transition("open", "open") is True


def test_topic_machine_rejects_invalid_transition():
    with pytest.raises(InvalidTransition):
        TOPIC_MACHINE.transition("published", "researching")
