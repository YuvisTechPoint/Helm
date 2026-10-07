"""Lead, deal, and conversation lifecycle state machines."""

from __future__ import annotations

from core.state_machine import StateMachine

LEAD_MACHINE = StateMachine(
    "lead",
    {
        "unknown": {"sourced", "contacted"},
        "sourced": {"contacted", "replied", "positive", "qualified", "nurture", "unsubscribed"},
        "contacted": {"replied", "positive", "qualified", "nurture", "unsubscribed"},
        "replied": {"positive", "qualified", "nurture", "unsubscribed"},
        "positive": {"qualified", "proposal_sent", "nurture", "unsubscribed"},
        "qualified": {"proposal_sent", "payment_pending", "nurture", "unsubscribed"},
        "proposal_sent": {"payment_pending", "converted", "nurture", "unsubscribed"},
        "payment_pending": {"converted", "nurture", "unsubscribed"},
        "nurture": {"contacted", "replied", "positive", "unsubscribed"},
    },
    terminal={"converted", "unsubscribed"},
)

DEAL_MACHINE = StateMachine(
    "deal",
    {
        "unknown": {"proposal_sent"},
        "proposal_sent": {"signed", "declined", "payment_pending"},
        "signed": {"payment_pending", "paid"},
        "payment_pending": {"paid", "declined"},
        "paid": set(),
        "declined": set(),
    },
    terminal={"paid", "declined"},
)

CONVERSATION_MACHINE = StateMachine(
    "conversation",
    {
        "open": {"closed", "handed_off"},
        "closed": {"open"},
        "handed_off": set(),
    },
    terminal={"handed_off"},
)
