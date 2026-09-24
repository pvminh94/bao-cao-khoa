# -*- coding: utf-8 -*-
"""Tổng hợp báo cáo theo kỳ — đọc cấu hình ĐỐI TƯỢNG (columns_def) động."""
from __future__ import annotations

import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Block, ColumnDef, Department, Entry, ReportTemplate, RptRow, Section


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def week_range(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    return start, start + timedelta(days=6)


def month_range(d: date) -> tuple[date, date]:
    start = d.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start, end


def resolve_range(mode: str, ref: date, dfrom: str | None, dto: str | None) -> tuple[date, date, str]:
    if mode == "day":
        return ref, ref, f"Ngày {ref.day}/{ref.month}/{ref.year}"
    if mode == "yesterday":
        y = ref - timedelta(days=1)
        return y, y, f"Ngày {y.day}/{y.month}/{y.year}"
    if mode == "week":
        a, b = week_range(ref)
        return a, b, f"Tuần từ {a.day}/{a.month}/{a.year} đến {b.day}/{b.month}/{b.year}"
    if mode == "month":
        a, b = month_range(ref)
        return a, b, f"Tháng {a.month}/{a.year}"
    if mode == "range" and dfrom and dto:
        a, b = parse_date(dfrom), parse_date(dto)
        if b < a:
            a, b = b, a
        return a, b, f"Từ ngày {a.day}/{a.month}/{a.year} đến {b.day}/{b.month}/{b.year}"
    return ref, ref, f"Ngày {ref.day}/{ref.month}/{ref.year}"


def get_template_for_dept(db: Session, dept_id: int) -> ReportTemplate | None:
    return db.scalar(
        select(ReportTemplate)
        .where(ReportTemplate.dept_id == dept_id, ReportTemplate.active.is_(True))
        .limit(1)
    )


def list_departments(db: Session, user_role: str, user_dept_id: int | None):
    stmt = (
        select(Department, ReportTemplate)
        .join(ReportTemplate, ReportTemplate.dept_id == Department.id, isouter=True)
        .where(Department.active.is_(True))
        .order_by(Department.name)
    )
    rows = db.execute(stmt).all()
    if user_role != "admin" and user_dept_id is not None:
        rows = [r for r in rows if r[0].id == user_dept_id]
    # chỉ giữ template active đầu tiên mỗi dept
    seen: set[int] = set()
    out = []
    for dept, tmpl in rows:
        if dept.id in seen:
            continue
        if tmpl is not None and not tmpl.active:
            tmpl = None
        seen.add(dept.id)
        out.append((dept, tmpl))
    return out


def get_structure(db: Session, tmpl_id: int, include_archived: bool = False) -> dict:
    """Cấu trúc mẫu. Mặc định chỉ trả phần ĐANG DÙNG (archived=False);
    truyền include_archived=True (trang cấu hình) để thấy cả phần đã ngừng."""
    sec_f = [Section.tmpl_id == tmpl_id]
    blk_f = [Section.tmpl_id == tmpl_id]
    row_f = [Section.tmpl_id == tmpl_id]
    col_f = [ColumnDef.tmpl_id == tmpl_id]
    if not include_archived:
        sec_f.append(Section.archived.is_(False))
        blk_f.append(Block.archived.is_(False))
        row_f.append(RptRow.archived.is_(False))
        col_f.append(ColumnDef.archived.is_(False))
    sections = db.scalars(
        select(Section).where(*sec_f).order_by(Section.sort_order, Section.id)
    ).all()
    cols = db.scalars(
        select(ColumnDef)
        .where(*col_f)
        .order_by(ColumnDef.sort_order, ColumnDef.id)
    ).all()
    blocks = db.scalars(
        select(Block)
        .join(Section, Block.section_id == Section.id)
        .where(*blk_f)
        .order_by(Block.sort_order, Block.id)
    ).all()
    rows = db.scalars(
        select(RptRow)
        .join(Section, RptRow.section_id == Section.id)
        .where(*row_f)
        .order_by(RptRow.sort_order, RptRow.id)
    ).all()

    blocks_by_sec: dict[int, list] = {}
    for b in blocks:
        blocks_by_sec.setdefault(b.section_id, []).append(b)
    rows_by_block: dict[int | None, list] = {}
    rows_by_sec: dict[int, list] = {}
    for r in rows:
        rows_by_sec.setdefault(r.section_id, []).append(r)
        rows_by_block.setdefault(r.block_id, []).append(r)

    sec_out = []
    for s in sections:
        sec_blocks = [
            {"id": b.id, "label": b.label, "archived": b.archived, "rows": rows_by_block.get(b.id, [])}
            for b in blocks_by_sec.get(s.id, [])
        ]
        loose = [r for r in rows_by_sec.get(s.id, []) if r.block_id is None]
        sec_out.append(
            {
                "id": s.id,
                "title": s.title,
                "sort_order": s.sort_order,
                "archived": s.archived,
                "blocks": sec_blocks,
                "loose_rows": loose,
            }
        )
    return {"sections": sec_out, "columns": list(cols)}


def _calc_formula(formula: str, values: dict[str, float]) -> float:
    expr = re.sub(
        r"[a-zA-Z_][a-zA-Z0-9_]*",
        lambda m: str(values.get(m.group(0), 0)),
        formula,
    )
    if not re.fullmatch(r"[0-9+\-*/().\s]+", expr or ""):
        return 0.0
    try:
        return float(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 — chỉ số & phép toán
    except Exception:
        return 0.0


def load_values(
    db: Session, tmpl_id: int, date_from: date, date_to: date, input_keys: list[str]
) -> dict[tuple[int, str], float]:
    rows = db.execute(
        select(RptRow.id, RptRow.agg)
        .join(Section, RptRow.section_id == Section.id)
        .where(Section.tmpl_id == tmpl_id)
    ).all()
    entries = db.execute(
        select(Entry.row_id, Entry.col_key, Entry.entry_date, Entry.value).where(
            Entry.tmpl_id == tmpl_id,
            Entry.entry_date >= date_from,
            Entry.entry_date <= date_to,
        )
    ).all()
    by_row_col: dict[tuple[int, str], list[tuple[date, float]]] = {}
    for row_id, col_key, ed, val in entries:
        by_row_col.setdefault((row_id, col_key), []).append((ed, val))

    out: dict[tuple[int, str], float] = {}
    for rid, agg in rows:
        for col in input_keys:
            series = sorted(by_row_col.get((rid, col), []))
            if not series:
                out[(rid, col)] = 0.0
                continue
            if agg == "first":
                out[(rid, col)] = float(series[0][1])
            elif agg == "last":
                out[(rid, col)] = float(series[-1][1])
            else:
                out[(rid, col)] = float(sum(v for _, v in series))
    return out


def _grand_key(cols) -> str | None:
    """Chọn cột 'tổng đại' để lấy tổng của 1 dòng: ưu tiên col_key='tong', else calc cuối."""
    for c in cols:
        if c.col_key == "tong":
            return "tong"
    calcs = [c for c in cols if c.kind == "calc"]
    return calcs[-1].col_key if calcs else None


def build_report(db: Session, dept_id: int, date_from: date, date_to: date) -> dict | None:
    dept = db.get(Department, dept_id)
    if not dept or not dept.active:
        return None
    tmpl = get_template_for_dept(db, dept_id)
    if not tmpl:
        return {"dept": dept, "template": None, "structure": None, "values": {}, "legacy": []}

    structure = get_structure(db, tmpl.id)  # chỉ phần ĐANG DÙNG
    display_cols = structure["columns"]
    # cột input đã NGỪNG vẫn nạp giá trị để công thức calc tham chiếu không sai
    archived_cols = db.scalars(
        select(ColumnDef).where(ColumnDef.tmpl_id == tmpl.id, ColumnDef.archived.is_(True))
    ).all()
    input_keys = [c.col_key for c in display_cols if c.kind == "input"] + [
        c.col_key for c in archived_cols if c.kind == "input"
    ]
    calc_cols = [c for c in display_cols if c.kind == "calc"]
    raw = load_values(db, tmpl.id, date_from, date_to, input_keys)

    # tính cột calc theo thứ tự sort (công thức tham chiếu key input/đã tính)
    row_ids: set[int] = set()
    for sec in structure["sections"]:
        for b in sec["blocks"]:
            for r in b["rows"]:
                row_ids.add(r.id)
        for r in sec["loose_rows"]:
            row_ids.add(r.id)
    for rid in row_ids:
        vals = {k: raw.get((rid, k), 0.0) for k in input_keys}
        for c in sorted(calc_cols, key=lambda x: (x.sort_order, x.id)):
            v = _calc_formula(c.formula, vals)
            vals[c.col_key] = v
            raw[(rid, c.col_key)] = v

    # ---- Số liệu thuộc cấu trúc ĐÃ NGỪNG nhưng kỳ này còn số liệu ----
    all_secs = db.scalars(select(Section).where(Section.tmpl_id == tmpl.id)).all()
    all_blks = db.scalars(
        select(Block).join(Section, Block.section_id == Section.id).where(Section.tmpl_id == tmpl.id)
    ).all()
    all_rows = db.scalars(
        select(RptRow).join(Section, RptRow.section_id == Section.id).where(Section.tmpl_id == tmpl.id)
    ).all()
    dead_sec = {s.id for s in all_secs if s.archived}
    dead_blk = {b.id for b in all_blks if b.archived}
    sec_title = {s.id: s.title for s in all_secs}
    blk_label = {b.id: b.label for b in all_blks}
    grand = _grand_key(display_cols)

    legacy = []
    for r in all_rows:
        if r.id in row_ids:  # đang dùng
            continue
        is_dead = r.archived or r.section_id in dead_sec or (r.block_id is not None and r.block_id in dead_blk)
        if not is_dead:
            continue
        vals = {k: raw.get((r.id, k), 0.0) for k in input_keys}
        for c in sorted(calc_cols, key=lambda x: (x.sort_order, x.id)):
            v = _calc_formula(c.formula, vals)
            vals[c.col_key] = v  # calc sau có thể tham chiếu calc trước (vd: bhyt_tong)
            raw[(r.id, c.col_key)] = v
        cells = {c.col_key: raw.get((r.id, c.col_key), 0.0) for c in display_cols}
        if not any(abs(float(v)) > 1e-9 for v in cells.values()):
            continue  # kỳ này không còn số liệu → không hiển thị
        if grand:
            total = float(cells.get(grand, 0) or 0)
        else:
            total = float(sum(cells.get(c.col_key, 0) or 0 for c in display_cols if c.kind == "input"))
        legacy.append(
            {
                "row_id": r.id,
                "section_title": sec_title.get(r.section_id, ""),
                "block_label": blk_label.get(r.block_id, "") if r.block_id else "",
                "group_label": r.group_label,
                "row_label": r.row_label,
                "agg": r.agg,
                "cells": cells,
                "total": total,
            }
        )

    return {
        "dept": dept,
        "template": tmpl,
        "structure": structure,
        "values": raw,
        "legacy": legacy,
        "date_from": date_from,
        "date_to": date_to,
    }


def save_entry(
    db: Session,
    tmpl_id: int,
    row_id: int,
    col_key: str,
    entry_date: date,
    value: float,
    user_id: int | None,
    *,
    username: str = "",
    dept_id: int | None = None,
    row_label: str = "",
    skip_audit: bool = False,
) -> None:
    existing = db.scalar(
        select(Entry).where(
            Entry.tmpl_id == tmpl_id,
            Entry.row_id == row_id,
            Entry.col_key == col_key,
            Entry.entry_date == entry_date,
        )
    )
    if existing:
        old = existing.value
        existing.value = value
        existing.updated_by = user_id
        if not skip_audit and old != value:
            _audit(
                db,
                user_id=user_id,
                username=username,
                dept_id=dept_id,
                tmpl_id=tmpl_id,
                row_id=row_id,
                row_label=row_label,
                col_key=col_key,
                entry_date=entry_date,
                old_value=old,
                new_value=value,
                action="update",
            )
    else:
        db.add(
            Entry(
                tmpl_id=tmpl_id,
                row_id=row_id,
                col_key=col_key,
                entry_date=entry_date,
                value=value,
                updated_by=user_id,
            )
        )
        if not skip_audit and value != 0:
            _audit(
                db,
                user_id=user_id,
                username=username,
                dept_id=dept_id,
                tmpl_id=tmpl_id,
                row_id=row_id,
                row_label=row_label,
                col_key=col_key,
                entry_date=entry_date,
                old_value=None,
                new_value=value,
                action="create",
            )


def _audit(
    db: Session,
    *,
    user_id: int | None,
    username: str,
    dept_id: int | None,
    tmpl_id: int,
    row_id: int,
    row_label: str,
    col_key: str,
    entry_date: date,
    old_value: float | None,
    new_value: float | None,
    action: str,
) -> None:
    from .models import AuditLog

    db.add(
        AuditLog(
            user_id=user_id,
            username=username or "",
            dept_id=dept_id,
            tmpl_id=tmpl_id,
            row_id=row_id,
            row_label=row_label or "",
            col_key=col_key,
            entry_date=entry_date,
            old_value=old_value,
            new_value=new_value,
            action=action,
        )
    )


def copy_day(
    db: Session, tmpl_id: int, src_date: date, dst_date: date, user_id: int | None
) -> int:
    from .models import AuditLog, RptRow

    recs = db.scalars(select(Entry).where(Entry.tmpl_id == tmpl_id, Entry.entry_date == src_date)).all()
    n = 0
    for r in recs:
        # nhân bản — ghi audit 1 dòng tổng, không spam từng ô
        save_entry(
            db, tmpl_id, r.row_id, r.col_key, dst_date, r.value, user_id, skip_audit=True
        )
        n += 1
    if n:
        row_label = ""
        # label chung cho log copy
        db.add(
            AuditLog(
                user_id=user_id,
                username="",
                dept_id=None,
                tmpl_id=tmpl_id,
                row_id=None,
                row_label=f"Nhân bản {n} ô từ {src_date.isoformat()}",
                col_key="*",
                entry_date=dst_date,
                old_value=None,
                new_value=float(n),
                action="copy",
            )
        )
    return n


def slugify_col_key(label: str, existing: set[str]) -> str:
    """Sinh col_key từ tên đối tượng: 'Dịch vụ' → dich_vu; tránh trùng."""
    import unicodedata

    s = unicodedata.normalize("NFD", label.lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # bỏ dấu
    s = s.replace("đ", "d").replace("Đ", "D")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "col"
    base = s
    i = 1
    while s in existing:
        i += 1
        s = f"{base}_{i}"
    return s
