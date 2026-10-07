from datetime import date

from core.redis_store import RateLimiter, get_redis


class TenantOutreachCap:
    def __init__(self, limiter: RateLimiter | None = None, daily_cap: int = 200):
        self.limiter = limiter or RateLimiter(get_redis())
        self.daily_cap = daily_cap

    def key(self, tenant_id: str) -> str:
        return f"tenant:outreach:{tenant_id}:{date.today().isoformat()}"

    def allow(self, tenant_id: str) -> bool:
        return self.limiter.allow(self.key(tenant_id), self.daily_cap)

    def sent(self, tenant_id: str) -> int:
        return self.limiter.store.get(self.key(tenant_id))
