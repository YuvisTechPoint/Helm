"""Run both engines end-to-end without the dashboard."""

import json
import uuid

from scripts._bootstrap import ensure_sqlite_dev, install


def main() -> int:
    install()
    ensure_sqlite_dev()

    from acquisition.pipeline_e2e import LeadPipeline
    from acquisition.repository import AcquisitionRepository
    from youtube.pipeline_e2e import YouTubePipeline

    repo = AcquisitionRepository()
    pipeline = LeadPipeline(repo)
    profile = {
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
    lead = {
        "email": f"lead-{uuid.uuid4().hex[:8]}@buyer.example",
        "first_name": "Ada",
        "company": "Example Co",
        "reason": "checkout hides shipping rates until account creation",
        "fit": 0.8,
        "intent": 0.7,
    }
    acquisition = pipeline.run_demo(
        "local",
        profile,
        lead,
        "Interested — let's talk next week.",
        "2026-10-15T10:00:00+05:30",
    )
    youtube = YouTubePipeline().run_cycle()
    print(json.dumps({"acquisition": acquisition, "youtube": youtube}, indent=2, default=str))
    ok = acquisition.get("status") == "converted" and youtube["dry_run"]["passed"] >= 10
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
