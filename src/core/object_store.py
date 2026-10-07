from core.config import get_settings
from core.errors import MissingCredentials
from core.storage import MemoryObjectStore, MinioStore


class FallbackObjectStore:
    def __init__(self, primary, fallback: MemoryObjectStore):
        self.primary = primary
        self.fallback = fallback
        self.use_fallback = False

    def put(self, key: str, data: bytes) -> str:
        if self.use_fallback:
            return self.fallback.put(key, data)
        try:
            return self.primary.put(key, data)
        except Exception:
            self.use_fallback = True
            return self.fallback.put(key, data)

    def get(self, key: str) -> bytes:
        if self.use_fallback or key in self.fallback.objects:
            return self.fallback.get(key)
        try:
            return self.primary.get(key)
        except Exception:
            self.use_fallback = True
            return self.fallback.get(key)


def object_store(settings=None):
    settings = settings or get_settings()
    fallback = MemoryObjectStore()
    try:
        primary = MinioStore(
            settings.s3_endpoint,
            settings.s3_access_key,
            settings.s3_secret_key,
            settings.s3_bucket,
        )
        return FallbackObjectStore(primary, fallback)
    except MissingCredentials:
        return fallback
