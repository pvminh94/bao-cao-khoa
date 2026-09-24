# -*- coding: utf-8 -*-
"""Đăng nhập / đăng xuất."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..security import clear_login, set_login, verify_password

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("uid"):
        return RedirectResponse("/", status_code=303)
    return request.app.state.templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "username": ""},
    )


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.username == username.strip()))
    if not user or not user.active or not verify_password(password, user.password_hash):
        return request.app.state.templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Sai tài khoản hoặc mật khẩu.", "username": username},
            status_code=401,
        )
    set_login(request.session, user.id, user.role, user.dept_id, user.username)
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    clear_login(request.session)
    return RedirectResponse("/login", status_code=303)
