# -*- coding: utf-8 -*-
"""Cấu hình ứng dụng — đọc từ .env / biến môi trường."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

APP_NAME = os.getenv("APP_NAME", "Báo cáo công tác khoa")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'bao_cao.db'}",
)
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
BASE_URL = os.getenv("BASE_URL", "")

# Tự seed admin mặc định lần đầu (chỉ khi DB trống)
SEED_ADMIN_USER = os.getenv("SEED_ADMIN_USER", "admin")
SEED_ADMIN_PASS = os.getenv("SEED_ADMIN_PASS", "Admin@123")
