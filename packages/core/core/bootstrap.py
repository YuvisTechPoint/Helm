import os
from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session, sessionmaker

from core.config import Settings, get_settings
from core.db import Base, make_engine
from core.vault import MemoryVault, SqlVault


def ensure_schema(url: str):
    import acquisition.models  # noqa: F401
    import youtube.models  # noqa: F401

    settings = get_settings()
    engine = make_engine(url, pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow)
    Base.metadata.create_all(engine)
    return engine


@lru_cache
def session_factory(url: str | None = None):
    settings = get_settings()
    target = url or settings.database_url
    if target.startswith("postgresql") and os.environ.get("USE_SQLITE", "").lower() == "true":
        target = os.environ.get("SQLITE_URL", "sqlite:///./data/engine.db")
    engine = ensure_schema(target)
    return sessionmaker(bind=engine, expire_on_commit=False)


def vault_for(session: Session | None, settings: Settings | None = None):
    settings = settings or get_settings()
    key = settings.vault_fernet_key
    if not key:
        key = Fernet.generate_key().decode()
    if session is None:
        return MemoryVault(key)
    return SqlVault(session, key)


def db_session(url: str | None = None) -> Session:
    return session_factory(url)()
