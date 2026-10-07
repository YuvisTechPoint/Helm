from datetime import date

from core.errors import QuotaExceeded
from core.redis_store import get_redis

DAILY_LIMIT = 10_000
UPLOAD_UNITS = 1_600
SEARCH_UNITS = 100


class QuotaLedger:
    def __init__(self, daily_limit: int = DAILY_LIMIT, upload_cost: int = UPLOAD_UNITS, redis=None):
        self.daily_limit = daily_limit
        self.upload_cost = upload_cost
        self.redis = redis
        self._mem_used = 0
        self._mem_reserved = 0

    @classmethod
    def from_env(cls, daily_limit: int = DAILY_LIMIT) -> "QuotaLedger":
        return cls(daily_limit=daily_limit, redis=get_redis())

    def _prefix(self) -> str:
        return f"yt:quota:{date.today().isoformat()}"

    @property
    def used(self) -> int:
        if self.redis is None:
            return self._mem_used
        return self.redis.get(f"{self._prefix()}:used")

    @used.setter
    def used(self, value: int) -> None:
        if self.redis is None:
            self._mem_used = value
        else:
            self.redis.set(f"{self._prefix()}:used", value)

    @property
    def reserved(self) -> int:
        if self.redis is None:
            return self._mem_reserved
        return self.redis.get(f"{self._prefix()}:reserved")

    @reserved.setter
    def reserved(self, value: int) -> None:
        if self.redis is None:
            self._mem_reserved = value
        else:
            self.redis.set(f"{self._prefix()}:reserved", value)

    def reserve_for_scheduled_uploads(self, count: int) -> int:
        need = count * self.upload_cost
        if self.used + self.reserved + need > self.daily_limit:
            raise QuotaExceeded("not enough quota to reserve uploads")
        self.reserved = self.reserved + need
        return self.reserved

    def allow_research(self, units: int) -> None:
        if units < 0:
            raise QuotaExceeded("units must be positive")
        if self.used + units + self.reserved > self.daily_limit:
            raise QuotaExceeded("research call would consume reserved upload quota")
        self.used = self.used + units

    def consume_upload(self) -> None:
        if self.reserved >= self.upload_cost:
            self.reserved = self.reserved - self.upload_cost
            self.used = self.used + self.upload_cost
            return
        if self.used + self.upload_cost + self.reserved > self.daily_limit:
            raise QuotaExceeded("upload exceeds daily quota")
        self.used = self.used + self.upload_cost

    @property
    def remaining(self) -> int:
        return self.daily_limit - self.used - self.reserved
