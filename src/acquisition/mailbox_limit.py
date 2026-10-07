from datetime import date

from core.redis_store import RateLimiter, get_redis


class MailboxLimiter:
    def __init__(self, limiter: RateLimiter | None = None):
        self.limiter = limiter or RateLimiter(get_redis())

    def key(self, mailbox: str) -> str:
        return f"mailbox:{mailbox}:{date.today().isoformat()}"

    def allow(self, mailbox: str, daily_cap: int) -> bool:
        return self.limiter.allow(self.key(mailbox), daily_cap)

    def sent(self, mailbox: str) -> int:
        return self.limiter.store.get(self.key(mailbox))
