# -*- coding: utf-8 -*-
"""Sao lưu / phục hồi toàn bộ CSDL bằng SQLAlchemy — chạy được với cả SQLite & PostgreSQL.

Định dạng bản sao lưu: JSON (tất cả bảng, giữ nguyên id) nén gzip → *.json.gz
Phục hồi: xóa dữ liệu (đúng thứ tự khóa ngoại) → chèn lại → đặt lại sequence (PostgreSQL).
"""
from __future__ import annotations

import gzip
import json
import re
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .config import BACKUP_DIR
from .models import (
    AuditLog,
    Block,
    ColumnDef,
    Department,
    Entry,
    ReportTemplate,
    RptRow,
    Section,
    User,
)

# cha → con (chèn theo thứ tự này; xóa theo thứ tự ngược lại)
TABLE_ORDER: list[type] = [
    Department,
    User,
    ReportTemplate,
    Section,
    Block,
    RptRow,
    ColumnDef,
    Entry,
    AuditLog,
]
TABLE_NAMES = [m.__tablename__ for m in TABLE_ORDER]

# tên file bản sao lưu hợp lệ (chống path traversal)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*\.json\.gz$")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


def backup_dir() -> Path:
    d = Path(BACKUP_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_backups() -> list[dict]:
    out = []
    for f in sorted(backup_dir().glob("*.json.gz"), reverse=True):
        out.append(
            {
                "name": f.name,
                "size": f.stat().st_size,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime),
            }
        )
    return out


def _serialize(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _parse(col, v):
    if v is None:
        return None
    py = getattr(col.type, "python_type", None)
    try:
        if py is date and not isinstance(v, date):
            return date.fromisoformat(v)
        if py is datetime and not isinstance(v, datetime):
            return datetime.fromisoformat(v)
        if py is bool:
            return bool(v)
        if py is float:
            return float(v)
        if py is int:
            return int(v)
        if py is str:
            return str(v)
    except (TypeError, ValueError):
        return v
    return v


def create_backup(db: Session, note: str = "") -> str:
    """Xuất toàn bộ bảng ra file .json.gz. Trả về tên file."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"sao-luu_{stamp}.json.gz"
    payload: dict = {"_app": "bao-cao-khoa", "_version": 2, "_note": note, "_tables": TABLE_NAMES}
    for m in TABLE_ORDER:
        cols = [c.key for c in inspect(m).mapper.column_attrs]
        rows = [
            {c: _serialize(getattr(r, c)) for c in cols}
            for r in db.query(m).all()
        ]
        payload[m.__tablename__] = rows
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path = backup_dir() / fname
    path.write_bytes(gzip.compress(raw, compresslevel=6))
    return fname


def validate_payload(payload: dict) -> None:
    if not isinstance(payload, dict) or "_app" not in payload or payload.get("_app") != "bao-cao-khoa":
        raise ValueError("File không phải bản sao lưu của hệ thống Báo cáo Công tác Khoa.")
    for tn in TABLE_NAMES:
        if tn not in payload or not isinstance(payload[tn], list):
            raise ValueError(f"Dữ liệu thiếu/không hợp lệ ở bảng '{tn}'.")


def load_backup_file(path: Path) -> dict:
    payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    validate_payload(payload)
    return payload


def restore_payload(db: Session, payload: dict) -> dict:
    """Xóa sạch + chèn lại theo payload. Ngoại lệ → rollback, CSDL không đổi."""
    validate_payload(payload)
    from .database import engine

    is_pg = engine.dialect.name == "postgresql"
    counts: dict[str, int] = {}

    try:
        for m in reversed(TABLE_ORDER):
            db.query(m).delete()
            db.flush()

        for m in TABLE_ORDER:
            insp = inspect(m)
            cols = [c.key for c in insp.mapper.column_attrs]
            rows = payload[m.__tablename__]
            for row in rows:
                obj = m(
                    **{
                        c: _parse(insp.attrs[c].columns[0], row.get(c))
                        for c in cols
                        if c in row
                    }
                )
                db.add(obj)
            db.flush()
            counts[m.__tablename__] = len(rows)

        if is_pg:
            with db.connection() as conn:
                for m in TABLE_ORDER:
                    tn = m.__tablename__
                    conn.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{tn}','id'), "
                            f"COALESCE((SELECT MAX(id) FROM {tn}), 1))"
                        )
                    )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return counts


def read_uploaded(data: bytes) -> dict:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("File quá lớn (giới hạn 200 MB).")
    try:
        raw = gzip.decompress(data)
    except OSError:
        raw = data  # cho phép .json chưa nén
    payload = json.loads(raw.decode("utf-8"))
    validate_payload(payload)
    return payload
