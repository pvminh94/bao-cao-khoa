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
    """Tạo bảng nếu chưa có + nâng cấp nhẹ (thêm cột) cho DB phiên bản cũ."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_light()


def _migrate_light() -> None:
    """DB tạo từ phiên bản cũ thiếu cột 'archived' → tự thêm (SQLite & PostgreSQL).

    Xóa dòng/mục/nhóm/đối tượng = chỉ ĐÁNH DẤU archived, không xóa số liệu →
    thống kê các kỳ trước vẫn chính xác.
    """
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    dflt = "FALSE" if engine.dialect.name == "postgresql" else "0"
    plans = [
        ("sections", "archived"),
        ("blocks", "archived"),
        ("rpt_rows", "archived"),
        ("columns_def", "archived"),
    ]
    with engine.begin() as conn:
        for tbl, col in plans:
            if tbl not in insp.get_table_names():
                continue
            cols = {c["name"] for c in insp.get_columns(tbl)}
            if col not in cols:
                conn.execute(
                    text(f"ALTER TABLE {tbl} ADD COLUMN {col} BOOLEAN NOT NULL DEFAULT {dflt}")
                )
