# -*- coding: utf-8 -*-
"""CLI: python -m app.cli create-admin|init-db|seed"""
from __future__ import annotations

import sys

from sqlalchemy import select

from .database import SessionLocal, init_models
from .models import User
from .security import hash_password
from .seed import ensure_seed


def init_db(with_seed: bool = True) -> None:
    init_models()
    if with_seed:
        db = SessionLocal()
        try:
            ensure_seed(db)
        finally:
            db.close()


def create_admin(username: str, password: str, full_name: str = "Quản trị viên") -> None:
    init_models()
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.username == username))
        if existing:
            existing.password_hash = hash_password(password)
            existing.role = "admin"
            existing.active = True
            print(f"Đã cập nhật mật khẩu cho admin '{username}'.")
        else:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    full_name=full_name,
                    role="admin",
                    active=True,
                )
            )
            print(f"Đã tạo admin '{username}'.")
        db.commit()
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        print("Usage: python -m app.cli init-db | create-admin <user> <pass> | seed")
        return 1
    cmd = argv[0]
    if cmd == "init-db":
        init_db(with_seed=True)
        print("DB đã khởi tạo + seed (nếu trống).")
        return 0
    if cmd == "seed":
        init_models()
        db = SessionLocal()
        try:
            ensure_seed(db)
        finally:
            db.close()
        print("Seed hoàn tất (bỏ qua nếu đã có dữ liệu).")
        return 0
    if cmd == "create-admin":
        if len(argv) < 3:
            print("Usage: python -m app.cli create-admin <username> <password>")
            return 1
        create_admin(argv[1], argv[2])
        return 0
    print(f"Lệnh không hợp lệ: {cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
