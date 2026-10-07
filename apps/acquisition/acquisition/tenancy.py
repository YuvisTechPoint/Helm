from core.errors import BudgetExceeded, IsolationError

REGIONS = {"india", "eu", "us"}


class TenantDirectory:
    def __init__(self):
        self.tenants: dict[str, dict] = {}
        self.domains: dict[str, str] = {}

    def create(self, tenant_id: str, region: str) -> dict:
        if region not in REGIONS:
            raise ValueError("region must be india, eu, or us")
        row = {"tenant_id": tenant_id, "region": region, "leads": [], "kill": False, "budget_cap": 0, "spent": 0}
        self.tenants[tenant_id] = row
        return row

    def assign_domain(self, tenant_id: str, domain: str) -> None:
        owner = self.domains.get(domain)
        if owner is not None and owner != tenant_id:
            raise IsolationError(f"{domain} already belongs to {owner}")
        self.domains[domain] = tenant_id

    def leads_for(self, actor_tenant: str, resource_tenant: str) -> list:
        if actor_tenant != resource_tenant:
            raise IsolationError("tenant data is isolated")
        return list(self.tenants[resource_tenant]["leads"])

    def set_budget(self, tenant_id: str, cap: int) -> None:
        self.tenants[tenant_id]["budget_cap"] = cap

    def spend(self, tenant_id: str, amount: int) -> None:
        row = self.tenants[tenant_id]
        if row["spent"] + amount > row["budget_cap"]:
            raise BudgetExceeded("tenant budget hard stop")
        row["spent"] += amount

    def kill(self, tenant_id: str) -> None:
        self.tenants[tenant_id]["kill"] = True

    def record_invoice(self, tenant_id: str, amount_cents: int, memo: str) -> dict:
        if tenant_id not in self.tenants:
            raise IsolationError("unknown tenant")
        invoice = {"tenant_id": tenant_id, "amount_cents": amount_cents, "memo": memo}
        self.tenants[tenant_id].setdefault("invoices", []).append(invoice)
        return invoice
