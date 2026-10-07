"""YouTube topic / video production lifecycle."""

from __future__ import annotations

from core.state_machine import StateMachine

TOPIC_MACHINE = StateMachine(
    "youtube_topic",
    {
        "backlog": {"planned", "cancelled"},
        "planned": {"researching", "cancelled"},
        "researching": {"scripting", "retryable_failure", "cancelled"},
        "scripting": {"gating", "retryable_failure", "cancelled"},
        "gating": {"rendering", "blocked", "retryable_failure", "cancelled"},
        "rendering": {"publishing", "retryable_failure", "cancelled"},
        "publishing": {"published", "retryable_failure", "permanent_failure"},
        "retryable_failure": {"researching", "scripting", "gating", "rendering", "publishing", "cancelled"},
        "blocked": {"gating", "cancelled"},
        "published": set(),
        "permanent_failure": set(),
        "cancelled": set(),
    },
    terminal={"published", "permanent_failure", "cancelled"},
)
