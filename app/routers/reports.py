# -*- coding: utf-8 -*-
"""Xem & xuất báo cáo — phân quyền theo khoa."""
from __future__ import annotations

import re
import urllib.parse
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, resolve_dept_id
from ..excel_export import export_report_xlsx
from ..models import User
from ..report import build_report, list_departments, resolve_range

router = APIRouter(tags=["reports"])

_ALL_FALLBACK_KEYS: list[str] = []  # cells điền theo cols trong template


def _flat_row(r, values, stt):
    return {
        "type": "row",
        "stt": stt,
        "group": r.group_label,
        "label": r.row_label,
        "agg": r.agg,
        "id": r.id,
        "cells": dict(values),  # full map col_key → value cho hàng này
    }


def _col_header_rows(cols):
    row1 = []
    i = 0
    while i < len(cols):
        g = cols[i].group_label
        if g:
            j = i
            grp = []
            while j < len(cols) and cols[j].group_label == g:
                grp.append(cols[j])
                j += 1
            row1.append({"label": g, "span": len(grp), "group": True})
            i = j
        else:
            row1.append({"label": cols[i].label, "span": 1, "group": False})
            i += 1
    return {"row1": row1}


@router.get("/bao-cao", response_class=HTMLResponse)
def bao_cao(
    request: Request,
    khoa: int | None = None,
    mode: str = "day",
    ref: str | None = None,
    tu: str | None = None,
    den: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pairs = list_departments(db, user.role, user.dept_id)
    default_id = pairs[0][0].id if pairs else None
    dept_id = resolve_dept_id(user, khoa, default_id)
    ref_d = date.fromisoformat(ref) if ref else date.today()
    dfrom, dto, label = resolve_range(mode, ref_d, tu, den)
    report = build_report(db, dept_id, dfrom, dto)
    if report is None:
        raise HTTPException(status_code=404, detail="Không thấy khoa.")

    rows_view = []
    cols = []
    col_header = {"row1": []}
    if report.get("structure"):
        st = report["structure"]
        cols = sorted(st["columns"], key=lambda c: (c.sort_order, c.id))
        col_header = _col_header_rows(cols)
        stt = 0
        for sec in st["sections"]:
            rows_view.append({"type": "section", "title": sec["title"]})
            for b in sec["blocks"]:
                rows_view.append({"type": "block", "label": b["label"]})
                for r in b["rows"]:
                    stt += 1
                    row_cells = {c.col_key: report["values"].get((r.id, c.col_key), 0) for c in cols}
                    rows_view.append(_flat_row(r, row_cells, stt))
            for r in sec["loose_rows"]:
                stt += 1
                row_cells = {c.col_key: report["values"].get((r.id, c.col_key), 0) for c in cols}
                rows_view.append(_flat_row(r, row_cells, stt))

    qs_parts = [f"khoa={dept_id}", f"mode={mode}"]
    if ref:
        qs_parts.append(f"ref={ref}")
    if tu:
        qs_parts.append(f"tu={tu}")
    if den:
        qs_parts.append(f"den={den}")
    qs_base = "&".join(qs_parts)

    return request.app.state.templates.TemplateResponse(
        request,
        "report.html",
        {
            "user": user,
            "pairs": pairs,
            "dept_id": dept_id,
            "mode": mode,
            "ref": ref_d,
            "tu": tu,
            "den": den,
            "label": label,
            "dfrom": dfrom,
            "dto": dto,
            "report": report,
            "rows_view": rows_view,
            "cols": cols,
            "col_header_rows": col_header,
            "qs_base": qs_base,
            "today": date.today(),
        },
    )


@router.get("/xuat-pdf")
def xuat_pdf(
    khoa: int | None = None,
    mode: str = "day",
    ref: str | None = None,
    tu: str | None = None,
    den: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..pdf_export import export_report_pdf

    pairs = list_departments(db, user.role, user.dept_id)
    default_id = pairs[0][0].id if pairs else None
    dept_id = resolve_dept_id(user, khoa, default_id)
    ref_d = date.fromisoformat(ref) if ref else date.today()
    dfrom, dto, label = resolve_range(mode, ref_d, tu, den)
    report = build_report(db, dept_id, dfrom, dto)
    if not report or not report.get("structure"):
        raise HTTPException(status_code=404, detail="Không có dữ liệu báo cáo.")
    data = export_report_pdf(report, label)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", report["dept"].name).strip("_") or "khoa"
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="BaoCao_{slug}_{dfrom.isoformat()}_{dto.isoformat()}.pdf"'
            )
        },
    )


@router.get("/xuat-excel")
def xuat_excel(
    khoa: int | None = None,
    mode: str = "day",
    ref: str | None = None,
    tu: str | None = None,
    den: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pairs = list_departments(db, user.role, user.dept_id)
    default_id = pairs[0][0].id if pairs else None
    dept_id = resolve_dept_id(user, khoa, default_id)
    ref_d = date.fromisoformat(ref) if ref else date.today()
    dfrom, dto, label = resolve_range(mode, ref_d, tu, den)
    report = build_report(db, dept_id, dfrom, dto)
    if not report or not report.get("structure"):
        raise HTTPException(status_code=404, detail="Không có dữ liệu báo cáo.")
    data = export_report_xlsx(report, label)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", report["dept"].name).strip("_") or "khoa"
    ascii_name = f"BaoCao_{slug}_{dfrom.isoformat()}_{dto.isoformat()}.xlsx"
    utf8_name = (
        f"Bao cao {report['dept'].name} {dfrom.isoformat()}_{dto.isoformat()}.xlsx"
    )
    disp = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{urllib.parse.quote(utf8_name)}"
    )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": disp},
    )
