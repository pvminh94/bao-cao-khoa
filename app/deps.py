# -*- coding: utf-8 -*-
"""FastAPI dependencies: đăng nhập bắt buộc, phân quyền admin / theo khoa."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = request.session.get("uid")
    if not uid:
        raise HTTPException(status_code=301, headers={"Location": "/login"})
    user = db.get(User, uid)
    if not user or not user.active:
        request.session.clear()
        raise HTTPException(status_code=301, headers={"Location": "/login"})
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Chỉ tài khoản ADMIN mới được cấu hình.")
    return user


def resolve_dept_id(user: User, requested: int | None, default_dept_id: int | None = None) -> int:
    """
    user.admin → requested hoặc default_dept_id (khoa đầu tiên) nếu None.
    user.user  → ép về dept_id của chính họ; requested khác khoa mình → 403.
    """
    if user.role == "admin":
        if requested is not None:
            return requested
        if default_dept_id is not None:
            return default_dept_id
        raise HTTPException(status_code=400, detail="Chưa có khoa nào trong hệ thống.")
    if user.dept_id is None:
        raise HTTPException(status_code=403, detail="Tài khoản chưa gắn khoa.")
    if requested is not None and requested != user.dept_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập khoa này.")
    return user.dept_id
