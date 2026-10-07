from core.config import get_settings


def enrich_lead(lead: dict) -> dict:
    """Waterfall: Apollo org hint -> domain guess -> fixture fields."""
    settings = get_settings()
    enriched = dict(lead)
    if enriched.get("company") and not enriched.get("domain"):
        slug = enriched["company"].lower().replace(" ", "").replace(",", "")[:24]
        enriched["domain"] = f"{slug}.example"
    if settings.apollo_api_key and enriched.get("email"):
        try:
            import httpx

            response = httpx.get(
                "https://api.apollo.io/api/v1/people/match",
                headers={"x-api-key": settings.apollo_api_key},
                params={"email": enriched["email"]},
                timeout=20,
            )
            if response.status_code == 200:
                person = response.json().get("person") or {}
                org = person.get("organization") or {}
                enriched["title"] = person.get("title") or enriched.get("title", "")
                enriched["company"] = org.get("name") or enriched.get("company", "")
                enriched["domain"] = org.get("primary_domain") or enriched.get("domain")
                enriched["employee_count"] = org.get("estimated_num_employees")
        except Exception:
            pass
    enriched.setdefault("title", "Head of Ecommerce")
    enriched.setdefault("employee_count", 50)
    return enriched
