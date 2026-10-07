"""M1.2 — draft Service Profile from a public website."""

import json
import re

from urllib.parse import urlparse


def draft_profile_from_url(url: str, llm=None) -> dict:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    domain = parsed.netloc or parsed.path
    slug = domain.split(".")[0].replace("-", " ").title()
    draft = {
        "business_name": slug,
        "services": ["Consulting and delivery services"],
        "proof_points": [f"Public site at {domain} describes the offer."],
        "price_floor": 50000,
        "list_price": 100000,
        "discount_limit": 0.1,
        "conversion_definition": "qualified_meeting",
        "human_name": "Owner",
        "faq": ["We scope work after a short discovery call."],
        "faq_terms": ["scope", "discovery"],
        "objections": {},
        "ideal_clients": [],
        "anti_ideal_clients": ["competitor"],
        "geographies": ["india"],
        "languages": ["en"],
        "guarantees": [],
        "testimonials": [],
        "calendar_link": "",
        "timezone": "Asia/Kolkata",
        "source_url": url,
        "drafted_from": "website",
    }
    if llm is not None:
        try:
            raw = llm.complete(
                "Return JSON service profile with business_name, services[], proof_points[], price_floor, list_price, human_name, faq[].",
                json.dumps({"url": url, "domain": domain}),
            )
            data = json.loads(raw)
            draft.update({key: data[key] for key in draft if key in data})
        except Exception:
            pass
    return draft


def draft_profile_from_text(text: str, llm=None) -> dict:
    sentences = [part.strip() for part in re.split(r"[.!?]\s+", text) if part.strip()]
    return {
        "business_name": sentences[0][:80] if sentences else "New business",
        "services": sentences[1:3] or ["Advisory services"],
        "proof_points": sentences[3:5] or ["Past proposals supplied by the owner."],
        "price_floor": 50000,
        "list_price": 100000,
        "discount_limit": 0.1,
        "conversion_definition": "qualified_meeting",
        "human_name": "Owner",
        "faq": sentences[5:7] or ["Happy to share scope on a call."],
        "drafted_from": "interview",
    }
