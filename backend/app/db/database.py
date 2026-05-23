from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Base(DeclarativeBase):
    pass


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def database_url() -> str:
    _load_env()
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("SQLITE_DATABASE_URL")
        or "sqlite:///./smartguard.db"
    )


@lru_cache(maxsize=1)
def get_engine():
    url = database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_database_engine_cache() -> None:
    get_session_factory.cache_clear()
    get_engine.cache_clear()
