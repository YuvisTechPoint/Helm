from core.config import get_settings
from core.errors import MissingCredentials


class MemoryCalendar:
    def book(self, email: str, slot: str) -> dict:
        return {"id": f"evt-{email}-{slot}", "email": email, "slot": slot, "provider": "memory"}


class CalcomCalendar:
    def __init__(self, api_key: str):
        if not api_key:
            raise MissingCredentials("CALCOM_API_KEY")
        self.api_key = api_key

    def book(self, email: str, slot: str) -> dict:
        import httpx

        response = httpx.post(
            "https://api.cal.com/v1/bookings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"eventTypeId": 1, "start": slot, "responses": {"email": email}},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return {"id": str(data.get("id", "cal-1")), "email": email, "slot": slot, "provider": "calcom"}


def calendar_client():
    settings = get_settings()
    if settings.calcom_api_key:
        try:
            return CalcomCalendar(settings.calcom_api_key)
        except MissingCredentials:
            pass
    return MemoryCalendar()
