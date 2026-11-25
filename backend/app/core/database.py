"""Database engine configuration, session dependency, and SQLite helper init."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy import URL
from sqlmodel import SQLModel, Session, create_engine

from app.core import config as _config  # noqa: F401 - loads .env before reading env vars


def _build_engine():
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        connect_args = (
            {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        )
        return create_engine(database_url, connect_args=connect_args)

    port_raw = os.getenv("MYSQL_PORT") or "3306"
    try:
        port = int(port_raw)
    except ValueError:
        port = 3306

    mysql_url = URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("MYSQL_USER") or "cmt_user",
        password=os.getenv("MYSQL_PASSWORD") or "",
        host=os.getenv("MYSQL_HOST") or "localhost",
        port=port,
        database=os.getenv("MYSQL_DATABASE") or "cmt",
    )
    return create_engine(mysql_url)


engine = _build_engine()


def is_sqlite_engine() -> bool:
    """Return True if the active engine uses SQLite."""
    return engine.url.get_backend_name() == "sqlite"


def init_db() -> None:
    """Create database tables automatically when running against a local SQLite DB."""
    if is_sqlite_engine():
        from app.models import models  # noqa: F401 - register SQLModel tables

        SQLModel.metadata.create_all(engine)


def get_session():
    """Yield a scoped SQLModel database session."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
