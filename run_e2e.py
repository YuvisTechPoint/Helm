"""Run both engines end-to-end without the dashboard."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for rel in ("packages/core", "apps/youtube", "apps/acquisition", "apps/api"):
    sys.path.insert(0, str(ROOT / rel))

os.environ.setdefault("USE_SQLITE", "true")

from acquisition.pipeline_e2e import LeadPipeline
from acquisition.repository import AcquisitionRepository
from youtube.pipeline_e2e import YouTubePipeline


def main() -> int:
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
        "email": f"lead-{__import__('uuid').uuid4().hex[:8]}@buyer.example",
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
