import os
from functools import lru_cache

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session, sessionmaker

from core.config import Settings, get_settings
from core.db import Base, make_engine
from core.vault import MemoryVault, SqlVault


def _run_migrations(url: str) -> bool:
    if os.environ.get("RUN_MIGRATIONS", "").lower() not in {"1", "true", "yes"} and get_settings().engine_mode != "production":
        return False
    try:
        from alembic import command
        from alembic.config import Config

        from core.paths import ALEMBIC_INI

        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        return True
    except Exception:
        return False


def ensure_schema(url: str):
    import acquisition.models  # noqa: F401
    import youtube.models  # noqa: F401

    settings = get_settings()
    engine = make_engine(url, pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow)
    if not _run_migrations(url):
        Base.metadata.create_all(engine)
    return engine


def _db_url(url: str | None = None) -> str:
    settings = get_settings()
    target = url or settings.database_url
    if target.startswith("postgresql") and os.environ.get("USE_SQLITE", "").lower() == "true":
        from core.paths import DATA_DIR

        default_sqlite = f"sqlite:///{(DATA_DIR / 'engine.db').as_posix()}"
        target = os.environ.get("SQLITE_URL", default_sqlite)
    return target


@lru_cache
def session_factory(resolved_url: str):
    engine = ensure_schema(resolved_url)
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
    return session_factory(_db_url(url))()
