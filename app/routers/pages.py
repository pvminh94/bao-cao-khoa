# -*- coding: utf-8 -*-
"""Trang chủ tổng quan."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Entry, User
from ..report import list_departments

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pairs = list_departments(db, user.role, user.dept_id)
    today = date.today()
    # bộ lọc: nếu user chỉ 1 khoa thì tính theo khoa đó
    recent = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        cnt = db.scalar(
            select(func.count(Entry.id)).where(Entry.entry_date == d)
        ) or 0
        recent.append({"date": d, "count": int(cnt)})
    max_count = max((r["count"] for r in recent), default=1) or 1
    for r in recent:
        r["pct"] = round(r["count"] * 100 / max_count)
    total = db.scalar(select(func.count(Entry.id))) or 0
    return request.app.state.templates.TemplateResponse(
        request,
        "home.html",
        {
            "user": user,
            "pairs": pairs,
            "recent": recent,
            "total_entries": int(total),
            "today": today,
        },
    )
