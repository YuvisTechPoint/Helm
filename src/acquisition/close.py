from core.errors import PolicyDenied
from core.timeutil import utcnow
from acquisition.policy import AI_DISCLOSURE, PolicyGuard


def quote_price(list_price: float, discount: float, floor: float, discount_limit: float) -> float:
    if discount - discount_limit > 1e-9:
        raise PolicyDenied("discount is above the approved authority")
    price = round(list_price * (1 - discount), 2)
    if price < floor:
        raise PolicyDenied("price is below the floor")
    return price


def build_proposal(profile: dict, discount: float = 0.0) -> dict:
    price = quote_price(profile["list_price"], discount, profile["price_floor"], profile["discount_limit"])
    return {
        "services": list(profile["services"]),
        "price": price,
        "promises": list(profile.get("guarantees", [])),
        "profile_version": profile["version"],
    }


def mark_signed(deal: dict, profile: dict) -> dict:
    if deal["price"] < profile["price_floor"]:
        raise PolicyDenied("signed price is below the floor")
    deal["status"] = "signed"
    deal["converted_at"] = utcnow().isoformat()
    return deal


def mark_paid(deal: dict, profile: dict) -> dict:
    if deal["price"] < profile["price_floor"]:
        raise PolicyDenied("paid price is below the floor")
    deal["status"] = "paid"
    deal["converted_at"] = utcnow().isoformat()
    return deal


def send_whatsapp(guard: PolicyGuard, request: dict, sender) -> dict:
    request = {**request, "channel": "whatsapp"}
    return guard.send(request, sender)


def place_outbound_call(guard: PolicyGuard, request: dict, dialer) -> dict:
    request = {**request, "channel": "voice", "direction": "outbound"}
    if not request.get("body", "").startswith(AI_DISCLOSURE):
        request["body"] = f"{AI_DISCLOSURE} {request.get('business_name', 'the business')}. " + request.get("body", "")
    return guard.send(request, dialer)


def promote_experiment(variants: list[dict], min_sends: int = 20) -> dict | None:
    """Promote the variant with the highest Wilson lower bound, not the raw sample rate."""
    from core.stats import wilson_lower_bound

    eligible = [variant for variant in variants if variant.get("sends", 0) >= min_sends]
    if not eligible:
        return None
    winner = max(
        eligible,
        key=lambda variant: (
            wilson_lower_bound(int(variant.get("positive", 0)), int(variant["sends"])),
            variant["positive"] / variant["sends"],
        ),
    )
    for variant in variants:
        variant["active"] = variant is winner
        if not variant["active"] and variant.get("sends", 0) >= min_sends:
            variant["retired"] = True
        variant["wilson_lb"] = round(wilson_lower_bound(int(variant.get("positive", 0)), int(variant.get("sends", 0) or 0)), 4)
    return winner


def monthly_report(changes: list[str], month: str) -> str:
    lines = [f"Monthly acquisition report for {month}."]
    if not changes:
        lines.append("No experiment was promoted.")
    else:
        lines.extend(f"Changed: {change}" for change in changes)
    return " ".join(lines)


class MemoryCalendar:
    def __init__(self):
        self.events: list[dict] = []

    def book(self, email: str, slot: str) -> dict:
        event = {"id": f"evt-{len(self.events) + 1}", "email": email, "slot": slot}
        self.events.append(event)
        return event


class StripePayments:
    def __init__(self, secret_key: str):
        from core.errors import MissingCredentials

        if not secret_key:
            raise MissingCredentials("STRIPE_SECRET_KEY")
        self.secret_key = secret_key

    def payment_link(self, amount_cents: int, currency: str = "usd") -> dict:
        import httpx

        response = httpx.post(
            "https://api.stripe.com/v1/payment_links",
            auth=(self.secret_key, ""),
            data={"line_items[0][price]": amount_cents, "line_items[0][quantity]": 1},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
