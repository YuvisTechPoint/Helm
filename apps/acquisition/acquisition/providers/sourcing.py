from core.config import get_settings


FIXTURE_LEADS = [
    {
        "email": "priya@shopifybrand.example",
        "first_name": "Priya",
        "company": "Shopify Brand Co",
        "reason": "checkout asks for account creation before shipping rates",
        "fit": 0.82,
        "intent": 0.71,
    },
    {
        "email": "marcus@homegoods.example",
        "first_name": "Marcus",
        "company": "Home Goods Direct",
        "reason": "mobile cart abandonment is above category average",
        "fit": 0.76,
        "intent": 0.65,
    },
]


class ApolloSource:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, icp: dict) -> list[dict]:
        import httpx

        response = httpx.post(
            "https://api.apollo.io/api/v1/mixed_people/search",
            headers={"x-api-key": self.api_key},
            json={"person_titles": icp.get("roles", ["Head of Ecommerce"]), "page": 1, "per_page": 5},
            timeout=30,
        )
        response.raise_for_status()
        people = response.json().get("people", [])
        leads = []
        for person in people:
            leads.append(
                {
                    "email": person.get("email"),
                    "first_name": person.get("first_name", "there"),
                    "company": person.get("organization", {}).get("name", "your company"),
                    "reason": icp.get("angle", "your checkout flow may be leaking conversions"),
                    "fit": 0.75,
                    "intent": 0.6,
                }
            )
        return [lead for lead in leads if lead.get("email")]


def source_leads(icp: dict | None = None) -> list[dict]:
    settings = get_settings()
    icp = icp or {"roles": ["Head of Ecommerce"], "angle": "checkout friction may be costing conversions"}
    if settings.apollo_api_key:
        try:
            return ApolloSource(settings.apollo_api_key).search(icp)
        except Exception:
            pass
    return list(FIXTURE_LEADS)
