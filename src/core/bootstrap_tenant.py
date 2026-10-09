"""Cold-start bootstrap for the YouTube channel engine — idempotent."""

from __future__ import annotations


def bootstrap_channel(container) -> dict:
    youtube = container.youtube
    return {
        "audit_approved": youtube.audit_approved,
        "quota_remaining": youtube.ledger.remaining,
        "uploads": len(youtube.store.list_all()) if hasattr(youtube.store, "list_all") else 0,
    }


# Backward-compatible alias for any stale imports
bootstrap_tenant = bootstrap_channel
