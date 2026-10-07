"""Cold-start bootstrap: profile, mailboxes, ICP bandit, volume plan — idempotent."""

from __future__ import annotations

from acquisition.defaults import ensure_ready_profile
from acquisition.modules.icp import allocate_bandit, generate_icp_hypotheses


def bootstrap_tenant(container) -> dict:
    """Prepare a tenant so every dashboard action works without manual setup."""
    settings = container.settings
    tenant = settings.acquisition_tenant_id
    acq = container.acquisition
    pipeline = acq.pipeline
    repo = acq.repo

    profile = ensure_ready_profile(repo, tenant)
    mailbox = pipeline.mailboxes.ensure_default(tenant)
    pipeline.mailboxes.add_mailbox(
        tenant,
        mailbox["address"],
        mailbox["domain"],
        mailbox["daily_cap"],
        warmed=True,
    )

    volume = repo.get_state(tenant, "volume", {})
    if not volume.get("weekly_qualified_target"):
        repo.set_state(tenant, "volume", {"weekly_qualified_target": settings.acquisition_weekly_qualified_target})
        volume = repo.get_state(tenant, "volume")

    cells_created = 0
    if not repo.list_icp_cells(tenant):
        llm = getattr(acq, "llm", None)
        cells = allocate_bandit(generate_icp_hypotheses(profile, llm))
        for cell in cells:
            body = {key: value for key, value in cell.items() if key != "body"}
            repo.save_icp_cell(tenant, cell["name"], body, cell.get("successes", 0), cell.get("failures", 0))
            cells_created += 1

    plan = pipeline.plan_daily_volume(tenant)
    return {
        "tenant_id": tenant,
        "profile_approved": repo.is_profile_approved(tenant),
        "mailbox": mailbox["address"],
        "icp_cells": len(repo.list_icp_cells(tenant)),
        "icp_seeded": cells_created,
        "weekly_target": volume.get("weekly_qualified_target"),
        "daily_contacts_planned": plan.get("daily_contacts_planned"),
    }
