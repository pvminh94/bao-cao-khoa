# -*- coding: utf-8 -*-
"""Bảo mật: hash mật khẩu (PBKDF2), phiên đăng nhập, phân quyền."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any

from .config import SESSION_HOURS

PBKDF2_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except Exception:
        return False


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def session_max_age_seconds() -> int:
    return SESSION_HOURS * 3600


# --- helpers cho dict session ---
def set_login(session: Any, user_id: int, role: str, dept_id: int | None, username: str) -> None:
    session.clear()
    session["uid"] = user_id
    session["role"] = role
    session["dept_id"] = dept_id
    session["username"] = username


def clear_login(session: Any) -> None:
    session.clear()
