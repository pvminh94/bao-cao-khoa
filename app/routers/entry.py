# -*- coding: utf-8 -*-
"""Nhập liệu theo ngày — phân quyền theo khoa."""
from __future__ import annotations

import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, resolve_dept_id
from ..models import Entry, RptRow, User
from ..report import (
    copy_day,
    get_structure,
    get_template_for_dept,
    list_departments,
    save_entry,
)

router = APIRouter(prefix="/nhap", tags=["entry"])

INPUT_KIND = "input"


@router.get("", response_class=HTMLResponse)
def nhap_form(
    request: Request,
    khoa: int | None = None,
    ngay: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dept_id = resolve_dept_id(
        user,
        khoa,
        pairs[0][0].id if (pairs := list_departments(db, user.role, user.dept_id)) else None,
    )
    day = date.fromisoformat(ngay) if ngay else date.today()
    tmpl = get_template_for_dept(db, dept_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Khoa chưa có mẫu báo cáo.")
    structure = get_structure(db, tmpl.id)
    input_keys = [c.col_key for c in structure["columns"] if c.kind == INPUT_KIND]
    recs = db.execute(
        select(Entry.row_id, Entry.col_key, Entry.value).where(
            Entry.tmpl_id == tmpl.id, Entry.entry_date == day
        )
    ).all()
    vals = {(r.row_id, r.col_key): r.value for r in recs}
    has_data = bool(vals)
    return request.app.state.templates.TemplateResponse(
        request,
        "entry.html",
        {
            "user": user,
            "pairs": pairs,
            "dept_id": dept_id,
            "day": day,
            "tmpl": tmpl,
            "structure": structure,
            "input_keys": input_keys,
            "vals": vals,
            "has_data": has_data,
            "prev_day": day - timedelta(days=1),
            "next_day": day + timedelta(days=1),
        },
    )


@router.post("")
def nhap_save(
    request: Request,
    khoa: int = Form(...),
    ngay: str = Form(...),
    payload: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dept_id = resolve_dept_id(user, khoa)
    tmpl = get_template_for_dept(db, dept_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Khoa chưa có mẫu báo cáo.")
    structure = get_structure(db, tmpl.id)
    input_keys = {c.col_key for c in structure["columns"] if c.kind == INPUT_KIND}
    day = date.fromisoformat(ngay)
    data = json.loads(payload)
    n = 0
    for row_id_s, cols in data.items():
        try:
            row_id = int(row_id_s)
        except ValueError:
            continue
        for col_key, val in cols.items():
            if col_key not in input_keys:
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                v = 0.0
            row = db.get(RptRow, row_id)
            row_label = f"{row.group_label} — {row.row_label}" if row and row.group_label else (row.row_label if row else "")
            save_entry(
                db,
                tmpl.id,
                row_id,
                col_key,
                day,
                v,
                user.id,
                username=user.username,
                dept_id=dept_id,
                row_label=row_label,
            )
            n += 1
    db.commit()
    return {"ok": True, "saved": n, "date": ngay}


@router.post("/nhan-ban")
def nhap_copy(
    khoa: int = Form(...),
    ngay: str = Form(...),
    tu_ngay: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dept_id = resolve_dept_id(user, khoa)
    tmpl = get_template_for_dept(db, dept_id)
    if tmpl:
        copy_day(
            db,
            tmpl.id,
            date.fromisoformat(tu_ngay),
            date.fromisoformat(ngay),
            user.id,
        )
        db.commit()
    return RedirectResponse(f"/nhap?khoa={dept_id}&ngay={ngay}", status_code=303)
