# -*- coding: utf-8 -*-
"""SQLAlchemy engine/session — hỗ trợ PostgreSQL (production) và SQLite (test)."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL

IS_SQLITE = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False} if IS_SQLITE else {}
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
    connect_args=connect_args,
)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_models() -> None:
    """Tạo bảng nếu chưa có."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
