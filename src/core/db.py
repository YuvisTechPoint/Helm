import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _is_ephemeral_sqlite(url: str) -> bool:
    return url.startswith("sqlite") and (":memory:" in url or url.rstrip("/") in {"sqlite:", "sqlite:/", "sqlite://"})


def make_engine(url: str, *, pool_size: int = 10, max_overflow: int = 20):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {"connect_timeout": 3}
    if _is_ephemeral_sqlite(url):
        from sqlalchemy.pool import StaticPool

        target = url if ":memory:" in url else "sqlite:///:memory:"
        return create_engine(target, connect_args=connect_args, poolclass=StaticPool)
    if url.startswith("sqlite"):
        if os.environ.get("PYTEST_CURRENT_TEST"):
            from sqlalchemy.pool import NullPool

            return create_engine(url, connect_args=connect_args, poolclass=NullPool)
        return create_engine(url, connect_args=connect_args)
    return create_engine(
        url,
        connect_args=connect_args,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def make_session_factory(url: str):
    return sessionmaker(bind=make_engine(url), expire_on_commit=False)
