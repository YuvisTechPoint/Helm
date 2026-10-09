from core.config import get_settings


class MemoryRedis:
    def __init__(self):
        self.data: dict[str, int] = {}

    def incr(self, key: str, amount: int = 1) -> int:
        self.data[key] = self.data.get(key, 0) + amount
        return self.data[key]

    def get(self, key: str) -> int:
        return self.data.get(key, 0)

    def set(self, key: str, value: int) -> None:
        self.data[key] = value


class RedisStore:
    def __init__(self, url: str):
        import redis

        self.client = redis.from_url(url, decode_responses=True)

    def incr(self, key: str, amount: int = 1) -> int:
        return int(self.client.incrby(key, amount))

    def get(self, key: str) -> int:
        value = self.client.get(key)
        return int(value or 0)

    def set(self, key: str, value: int) -> None:
        self.client.set(key, value)


def get_redis():
    settings = get_settings()
    try:
        import redis

        client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_connect_timeout_s,
        )
        client.ping()
        return RedisStore(settings.redis_url)
    except Exception:
        return MemoryRedis()


class RateLimiter:
    def __init__(self, store=None):
        self.store = store or get_redis()

    def allow(self, key: str, limit: int) -> bool:
        current = self.store.incr(key)
        return current <= limit

    def remaining(self, key: str, limit: int) -> int:
        return max(0, limit - self.store.get(key))
