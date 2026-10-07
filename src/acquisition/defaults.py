"""Approved Northwind profile used when the owner has not saved one yet."""

DEFAULT_PROFILE = {
    "business_name": "Northwind",
    "services": ["checkout audit"],
    "proof_points": ["A shop fixed shipping rates before account creation."],
    "price_floor": 50000,
    "list_price": 80000,
    "discount_limit": 0.1,
    "conversion_definition": "qualified_meeting",
    "human_name": "Mina",
    "faq": ["Audits cover cart to paid."],
    "faq_terms": ["audit", "checkout"],
    "objections": {"price": "The floor for this audit is published in the profile."},
    "version": 1,
}


def ensure_ready_profile(repo, tenant_id: str) -> dict:
    profile = repo.get_profile(tenant_id)
    if profile is None:
        repo.save_profile(tenant_id, dict(DEFAULT_PROFILE), approved=True)
        profile = repo.get_profile(tenant_id)
    elif not repo.is_profile_approved(tenant_id):
        repo.approve_profile(tenant_id)
        profile = repo.get_profile(tenant_id)
    return profile
