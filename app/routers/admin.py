# -*- coding: utf-8 -*-
"""Quản trị: cấu hình mẫu (mục/dòng/đối tượng) + người dùng — CHỈ ADMIN."""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import AuditLog, Block, ColumnDef, Department, ReportTemplate, RptRow, Section, User
from ..backup import (
    backup_dir,
    create_backup,
    list_backups,
    load_backup_file,
    read_uploaded,
    restore_payload,
    NAME_RE,
)
from ..report import get_structure, slugify_col_key
from ..security import hash_password

router = APIRouter(prefix="/cau-hinh", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/lich-su", response_class=HTMLResponse)
def lich_su(
    request: Request,
    dept_id: int | None = None,
    tu: str | None = None,
    den: str | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from datetime import date as _date, timedelta as _td

    stmt = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(500)
    )
    if dept_id:
        stmt = stmt.where(AuditLog.dept_id == dept_id)
    if tu:
        stmt = stmt.where(AuditLog.created_at >= _date.fromisoformat(tu))
    if den:
        stmt = stmt.where(AuditLog.created_at < _date.fromisoformat(den) + _td(days=1))
    logs = db.scalars(stmt).all()
    depts = db.scalars(
        select(Department).where(Department.active.is_(True)).order_by(Department.name)
    ).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "audit.html",
        {
            "user": user,
            "logs": logs,
            "depts": depts,
            "dept_id": dept_id,
            "tu": tu,
            "den": den,
        },
    )


def _admin_payload(db: Session, khoa_id: int | None = None) -> list[dict]:
    q = select(Department).where(Department.active.is_(True))
    if khoa_id:
        q = q.where(Department.id == khoa_id)
    depts = db.scalars(q.order_by(Department.name)).all()
    out = []
    for d in depts:
        tmpl = db.scalar(
            select(ReportTemplate)
            .where(ReportTemplate.dept_id == d.id, ReportTemplate.active.is_(True))
            .limit(1)
        )
        st = get_structure(db, tmpl.id, include_archived=True) if tmpl else {"sections": [], "columns": []}
        out.append({"dept": d, "tmpl": tmpl, "structure": st})
    return out


def _sec_href(db: Session, sec_id: int | None) -> str:
    """URL quay lại đúng chỗ vừa sửa (khoa + anchor mục) — không nhảy về đầu trang."""
    if not sec_id:
        return "/cau-hinh"
    sec = db.get(Section, sec_id)
    if not sec:
        return "/cau-hinh"
    dept_id = sec.template.dept_id if sec.template else None
    return f"/cau-hinh?tab=mau&khoa={dept_id}#sec-{sec_id}"


def _col_href(db: Session, tmpl_id: int | None) -> str:
    if not tmpl_id:
        return "/cau-hinh?tab=doi-tuong"
    tmpl = db.get(ReportTemplate, tmpl_id)
    dept_id = tmpl.dept_id if tmpl else None
    return f"/cau-hinh?tab=doi-tuong&khoa={dept_id}#tmpl-{tmpl_id}"


@router.get("", response_class=HTMLResponse)
def cau_hinh(
    request: Request,
    tab: str = "mau",
    khoa: int | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = _admin_payload(db, khoa)
    users = db.scalars(select(User).order_by(User.username)).all()
    depts = db.scalars(
        select(Department).where(Department.active.is_(True)).order_by(Department.name)
    ).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "admin.html",
        {"user": user, "data": data, "users": users, "depts": depts, "tab": tab, "khoa_sel": khoa},
    )


# ---------------- khoa ----------------
@router.post("/khoa")
def them_khoa(
    ten: str = Form(...),
    ma: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dept = Department(code=ma.upper().strip(), name=ten.strip())
    db.add(dept)
    db.flush()
    tmpl = ReportTemplate(dept_id=dept.id, name=f"Mẫu - {ten.strip()}")
    db.add(tmpl)
    db.flush()
    from ..seed import add_default_objects

    add_default_objects(db, tmpl.id)
    s = Section(tmpl_id=tmpl.id, title="1. Mục mới", sort_order=1)
    db.add(s)
    db.flush()
    db.add(
        RptRow(
            section_id=s.id,
            group_label="",
            row_label="Dòng mới",
            agg="sum",
            sort_order=0,
        )
    )
    db.commit()
    return RedirectResponse(_sec_href(db, s.id), status_code=303)


@router.post("/khoa/{dept_id}/xoa")
def xoa_khoa(
    dept_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dept = db.get(Department, dept_id)
    if dept:
        dept.active = False
        for t in dept.templates:
            t.active = False
        db.commit()
    return RedirectResponse("/cau-hinh", status_code=303)


@router.post("/khoa/{dept_id}/ten")
def doi_ten_khoa(
    dept_id: int,
    name: str = Form(...),
    hospital: str = Form(...),
    report_code: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    dept = db.get(Department, dept_id)
    if not dept:
        raise HTTPException(status_code=404)
    dept.name = name.strip()
    dept.hospital = hospital.strip()
    dept.report_code = report_code.strip()
    db.commit()
    return RedirectResponse(f"/cau-hinh?tab=mau&khoa={dept_id}#dept-{dept_id}", status_code=303)


# ---------------- mục / dòng ----------------
@router.post("/muc")
def them_muc(
    tmpl_id: int = Form(...),
    title: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tmpl = db.get(ReportTemplate, tmpl_id)
    if not tmpl:
        raise HTTPException(status_code=404)
    mx = (
        db.scalar(
            select(Section.sort_order)
            .where(Section.tmpl_id == tmpl_id)
            .order_by(Section.sort_order.desc())
            .limit(1)
        )
        or 0
    )
    s = Section(tmpl_id=tmpl_id, title=title.strip(), sort_order=mx + 1)
    db.add(s)
    db.commit()
    return RedirectResponse(_sec_href(db, s.id), status_code=303)


@router.post("/muc/{sec_id}/sua")
def sua_muc(
    sec_id: int,
    title: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sec = db.get(Section, sec_id)
    if sec:
        sec.title = title.strip()
        db.commit()
    return RedirectResponse(_sec_href(db, sec_id), status_code=303)


@router.post("/muc/{sec_id}/xoa")
def xoa_muc(
    sec_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sec = db.get(Section, sec_id)
    if sec:
        # NGỪNG sử dụng thay vì xóa — giữ nguyên số liệu lịch sử
        sec.archived = True
        db.commit()
    return RedirectResponse(_sec_href(db, sec_id), status_code=303)


@router.post("/muc/{sec_id}/khoi-phuc")
def khoi_phuc_muc(
    sec_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sec = db.get(Section, sec_id)
    if sec:
        sec.archived = False
        db.commit()
    return RedirectResponse(_sec_href(db, sec_id), status_code=303)


# ---------------- nhóm dòng (Block: vd "1.1. Trong giờ") ----------------
@router.post("/nhom")
def them_nhom(
    section_id: int = Form(...),
    label: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sec = db.get(Section, section_id)
    if not sec:
        raise HTTPException(status_code=404)
    mx = (
        db.scalar(
            select(Block.sort_order)
            .where(Block.section_id == section_id)
            .order_by(Block.sort_order.desc())
            .limit(1)
        )
        or 0
    )
    db.add(Block(section_id=section_id, label=label.strip(), sort_order=mx + 1))
    db.commit()
    return RedirectResponse(_sec_href(db, section_id), status_code=303)


@router.post("/nhom/{b_id}/sua")
def sua_nhom(
    b_id: int,
    label: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    b = db.get(Block, b_id)
    if b:
        b.label = label.strip()
        db.commit()
    return RedirectResponse(_sec_href(db, b.section_id if b else None), status_code=303)


@router.post("/nhom/{b_id}/xoa")
def xoa_nhom(
    b_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    b = db.get(Block, b_id)
    if b:
        b.archived = True  # ngừng dùng — số liệu giữ nguyên
        db.commit()
    return RedirectResponse(_sec_href(db, b.section_id if b else None), status_code=303)


@router.post("/nhom/{b_id}/khoi-phuc")
def khoi_phuc_nhom(
    b_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    b = db.get(Block, b_id)
    if b:
        b.archived = False
        db.commit()
    return RedirectResponse(_sec_href(db, b.section_id if b else None), status_code=303)


@router.post("/nhom/{b_id}/len")
def len_nhom(
    b_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    b = db.get(Block, b_id)
    if b:
        prev = db.scalar(
            select(Block)
            .where(Block.section_id == b.section_id, Block.sort_order < b.sort_order)
            .order_by(Block.sort_order.desc())
            .limit(1)
        )
        if prev:
            prev.sort_order, b.sort_order = b.sort_order, prev.sort_order
            db.commit()
    return RedirectResponse(_sec_href(db, b.section_id if b else None), status_code=303)


@router.post("/nhom/{b_id}/xuong")
def xuong_nhom(
    b_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    b = db.get(Block, b_id)
    if b:
        nxt = db.scalar(
            select(Block)
            .where(Block.section_id == b.section_id, Block.sort_order > b.sort_order)
            .order_by(Block.sort_order.asc())
            .limit(1)
        )
        if nxt:
            nxt.sort_order, b.sort_order = b.sort_order, nxt.sort_order
            db.commit()
    return RedirectResponse(_sec_href(db, b.section_id if b else None), status_code=303)


@router.post("/dong")
def them_dong(
    section_id: int = Form(...),
    block_id: int | None = Form(None),
    group_label: str = Form(""),
    row_label: str = Form(...),
    agg: str = Form("sum"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sec = db.get(Section, section_id)
    if not sec:
        raise HTTPException(status_code=404)
    if block_id is not None:
        blk = db.get(Block, block_id)
        if not blk or blk.section_id != section_id:
            raise HTTPException(status_code=400, detail="Nhóm không thuộc mục này.")
    mx = (
        db.scalar(
            select(RptRow.sort_order)
            .where(RptRow.section_id == section_id)
            .order_by(RptRow.sort_order.desc())
            .limit(1)
        )
        or 0
    )
    db.add(
        RptRow(
            section_id=section_id,
            block_id=block_id,
            group_label=group_label.strip(),
            row_label=row_label.strip(),
            agg=agg if agg in ("sum", "first", "last") else "sum",
            sort_order=mx + 1,
        )
    )
    db.commit()
    return RedirectResponse(_sec_href(db, section_id), status_code=303)


@router.post("/dong/{row_id}/sua")
def sua_dong(
    row_id: int,
    group_label: str = Form(""),
    row_label: str = Form(...),
    agg: str = Form("sum"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    r = db.get(RptRow, row_id)
    if r:
        r.group_label = group_label.strip()
        r.row_label = row_label.strip()
        r.agg = agg if agg in ("sum", "first", "last") else "sum"
        db.commit()
    return RedirectResponse(_sec_href(db, r.section_id if r else None), status_code=303)


@router.post("/dong/{row_id}/xoa")
def xoa_dong(
    row_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    r = db.get(RptRow, row_id)
    if r:
        r.archived = True  # ngừng dùng — số liệu lịch sử giữ nguyên
        db.commit()
    return RedirectResponse(_sec_href(db, r.section_id if r else None), status_code=303)


@router.post("/dong/{row_id}/khoi-phuc")
def khoi_phuc_dong(
    row_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    r = db.get(RptRow, row_id)
    if r:
        r.archived = False
        db.commit()
    return RedirectResponse(_sec_href(db, r.section_id if r else None), status_code=303)


@router.post("/dong/{row_id}/len")
def len_dong(
    row_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    r = db.get(RptRow, row_id)
    if r:
        # chỉ đổi chỗ trong CÙNG nhóm (nếu dòng thuộc nhóm)
        if r.block_id is None:
            scope = [RptRow.section_id == r.section_id, RptRow.block_id.is_(None)]
        else:
            scope = [RptRow.block_id == r.block_id]
        prev = db.scalar(
            select(RptRow).where(*scope, RptRow.sort_order < r.sort_order)
            .order_by(RptRow.sort_order.desc()).limit(1)
        )
        if prev:
            prev.sort_order, r.sort_order = r.sort_order, prev.sort_order
            db.commit()
    return RedirectResponse(_sec_href(db, r.section_id if r else None), status_code=303)


@router.post("/dong/{row_id}/xuong")
def xuong_dong(
    row_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    r = db.get(RptRow, row_id)
    if r:
        if r.block_id is None:
            scope = [RptRow.section_id == r.section_id, RptRow.block_id.is_(None)]
        else:
            scope = [RptRow.block_id == r.block_id]
        nxt = db.scalar(
            select(RptRow).where(*scope, RptRow.sort_order > r.sort_order)
            .order_by(RptRow.sort_order.asc()).limit(1)
        )
        if nxt:
            nxt.sort_order, r.sort_order = r.sort_order, nxt.sort_order
            db.commit()
    return RedirectResponse(_sec_href(db, r.section_id if r else None), status_code=303)


# ---------------- đối tượng (cột) — khai báo linh hoạt ----------------
@router.post("/doi-tuong")
def them_doi_tuong(
    tmpl_id: int = Form(...),
    label: str = Form(...),
    group_label: str = Form(""),
    kind: str = Form("input"),
    formula: str = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tmpl = db.get(ReportTemplate, tmpl_id)
    if not tmpl:
        raise HTTPException(status_code=404)
    existing = set(
        db.scalars(
            select(ColumnDef.col_key).where(ColumnDef.tmpl_id == tmpl_id)
        ).all()
    )
    col_key = slugify_col_key(label, existing)
    if kind == "calc":
        # validate công thức: chỉ identifier + toán tử
        if not re.fullmatch(r"[a-zA-Z0-9_+\-*/(). ]*", formula or ""):
            raise HTTPException(status_code=400, detail="Công thức không hợp lệ.")
        group_label = group_label.strip()
    mx = (
        db.scalar(
            select(ColumnDef.sort_order)
            .where(ColumnDef.tmpl_id == tmpl_id)
            .order_by(ColumnDef.sort_order.desc())
            .limit(1)
        )
        or 0
    )
    db.add(
        ColumnDef(
            tmpl_id=tmpl_id,
            col_key=col_key,
            label=label.strip(),
            group_label=group_label.strip(),
            kind=kind if kind in ("input", "calc") else "input",
            formula=(formula or "").strip() if kind == "calc" else "",
            sort_order=mx + 1,
        )
    )
    db.commit()
    return RedirectResponse(_col_href(db, tmpl_id), status_code=303)


@router.post("/doi-tuong/{col_id}/sua")
def sua_doi_tuong(
    col_id: int,
    label: str = Form(...),
    group_label: str = Form(""),
    kind: str = Form("input"),
    formula: str = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = db.get(ColumnDef, col_id)
    if not c:
        raise HTTPException(status_code=404)
    c.label = label.strip()
    c.group_label = group_label.strip()
    if c.kind == "calc":
        # giữ col_key cũ để công thức khác không vỡ
        c.formula = (formula or "").strip()
    db.commit()
    return RedirectResponse(_col_href(db, c.tmpl_id if c else None), status_code=303)


@router.post("/doi-tuong/{col_id}/xoa")
def xoa_doi_tuong(
    col_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = db.get(ColumnDef, col_id)
    if c:
        # ngừng dùng thay vì xóa — số liệu cũ vẫn còn và vẫn tính cho kỳ cũ
        c.archived = True
        db.commit()
    return RedirectResponse(_col_href(db, c.tmpl_id if c else None), status_code=303)


@router.post("/doi-tuong/{col_id}/khoi-phuc")
def khoi_phuc_doi_tuong(
    col_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    c = db.get(ColumnDef, col_id)
    if c:
        c.archived = False
        db.commit()
    return RedirectResponse(_col_href(db, c.tmpl_id if c else None), status_code=303)


# ---------------- người dùng ----------------
@router.get("/nguoi-dung", response_class=HTMLResponse)
def nguoi_dung(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.scalars(select(User).order_by(User.username)).all()
    depts = db.scalars(
        select(Department).where(Department.active.is_(True)).order_by(Department.name)
    ).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "users.html",
        {"user": user, "users": users, "depts": depts},
    )


@router.post("/nguoi-dung")
def them_nguoi_dung(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    role: str = Form("user"),
    dept_id: str = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    username = username.strip()
    if not username or len(password) < 6:
        raise HTTPException(status_code=400, detail="Username và mật khẩu (≥6 ký tự) là bắt buộc.")
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(status_code=400, detail="Username đã tồn tại.")
    role_v = role if role in ("admin", "user") else "user"
    did = int(dept_id) if dept_id and role_v == "user" else None
    if role_v == "user" and did is None:
        raise HTTPException(status_code=400, detail="Tài khoản user phải chọn khoa.")
    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            role=role_v,
            dept_id=did,
            active=True,
        )
    )
    db.commit()
    return RedirectResponse("/cau-hinh/nguoi-dung", status_code=303)


@router.post("/nguoi-dung/{uid}/khoa")
def doi_khoa_nguoi_dung(
    uid: int,
    dept_id: str = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status_code=404)
    if u.id == user.id and u.role == "admin":
        return RedirectResponse("/cau-hinh/nguoi-dung", status_code=303)
    u.dept_id = int(dept_id) if dept_id else None
    db.commit()
    return RedirectResponse("/cau-hinh/nguoi-dung", status_code=303)


@router.post("/nguoi-dung/{uid}/mat-khau")
def doi_mat_khau(
    uid: int,
    password: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(status_code=404)
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Mật khẩu ≥ 6 ký tự.")
    u.password_hash = hash_password(password)
    db.commit()
    return RedirectResponse("/cau-hinh/nguoi-dung", status_code=303)


@router.post("/nguoi-dung/{uid}/toggle")
def toggle_nguoi_dung(
    uid: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    u = db.get(User, uid)
    if u and u.id != user.id:
        u.active = not u.active
        db.commit()
    return RedirectResponse("/cau-hinh/nguoi-dung", status_code=303)


# ---------------- sao lưu / phục hồi (chỉ admin) ----------------
def _audit_action(db: Session, user, action: str, label: str) -> None:
    db.add(
        AuditLog(
            user_id=user.id,
            username=user.username,
            dept_id=user.dept_id,
            row_label=label,
            col_key="*",
            action=action,
        )
    )
    db.commit()


@router.get("/sao-luu", response_class=HTMLResponse)
def sao_luu(
    request: Request,
    da_phuc_hoi: str | None = None,
    loi: str | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    depts = db.scalars(select(Department).order_by(Department.name)).all()
    return request.app.state.templates.TemplateResponse(
        request,
        "admin.html",
        {
            "user": user,
            "tab": "sao-luu",
            "backups": list_backups(),
            "backup_dir": str(backup_dir()),
            "da_phuc_hoi": da_phuc_hoi,
            "loi": loi,
            "data": [],
            "depts": depts,
            "users": [],
            "khoa_sel": None,
        },
    )


@router.post("/sao-luu/tao")
def sao_luu_tao(
    note: str = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    fname = create_backup(db, note=(note or "").strip())
    _audit_action(db, user, "backup", f"Tạo bản sao lưu {fname}")
    return RedirectResponse("/cau-hinh/sao-luu", status_code=303)


def _safe_backup_path(name: str) -> Path:
    if not NAME_RE.fullmatch(name or "") or ".." in name:
        raise HTTPException(status_code=400, detail="Tên file bản sao lưu không hợp lệ.")
    path = (backup_dir() / name).resolve()
    if path.parent != backup_dir().resolve() or not path.exists():
        raise HTTPException(status_code=404, detail="Không thấy bản sao lưu.")
    return path


@router.get("/sao-luu/{name}/tai")
def sao_luu_tai(name: str, user: User = Depends(require_admin)):
    path = _safe_backup_path(name)
    data = path.read_bytes()
    return Response(
        content=data,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/sao-luu/xoa")
def sao_luu_xoa(
    name: str = Form(...),
    user: User = Depends(require_admin),
):
    path = _safe_backup_path(name)
    path.unlink()
    return RedirectResponse("/cau-hinh/sao-luu", status_code=303)


def _do_restore(db: Session, user, payload: dict, src_label: str) -> None:
    # bản sao lưu an toàn TRƯỚC khi ghi đè
    safe = create_backup(db, note="Tự động trước khi phục hồi")
    counts = restore_payload(db, payload)
    _audit_action(
        db,
        user,
        "restore",
        f"Phục hồi từ {src_label} (sao lưu an toàn: {safe})",
    )
    print(f"[restore] {src_label} → {counts}")


@router.post("/sao-luu/phuc-hoi")
def sao_luu_phuc_hoi(
    name: str = Form(...),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    path = _safe_backup_path(name)
    try:
        payload = load_backup_file(path)
    except (ValueError, OSError) as e:
        from urllib.parse import quote

        return RedirectResponse(
            f"/cau-hinh/sao-luu?loi={quote(f'File không đọc được: {e}'[:300])}",
            status_code=303,
        )
    try:
        _do_restore(db, user, payload, name)
    except Exception as e:
        db.rollback()  # dữ liệu hiện tại giữ nguyên
        from urllib.parse import quote

        return RedirectResponse(
            f"/cau-hinh/sao-luu?loi={quote(f'{type(e).__name__}: {e}'[:300])}",
            status_code=303,
        )
    return RedirectResponse(f"/cau-hinh/sao-luu?da_phuc_hoi={name}", status_code=303)


@router.post("/sao-luu/tai-len")
async def sao_luu_tai_len(
    file: UploadFile,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = await file.read()
    try:
        payload = read_uploaded(data)
    except (ValueError, UnicodeDecodeError) as e:
        from urllib.parse import quote

        return RedirectResponse(
            f"/cau-hinh/sao-luu?loi={quote(f'File tải lên không hợp lệ: {e}'[:300])}",
            status_code=303,
        )
    try:
        _do_restore(db, user, payload, f"tải lên: {file.filename}")
    except Exception as e:
        db.rollback()
        from urllib.parse import quote

        return RedirectResponse(
            f"/cau-hinh/sao-luu?loi={quote(f'{type(e).__name__}: {e}'[:300])}",
            status_code=303,
        )
    return RedirectResponse(
        f"/cau-hinh/sao-luu?da_phuc_hoi={file.filename}", status_code=303
    )
