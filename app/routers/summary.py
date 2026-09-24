# -*- coding: utf-8 -*-
"""Tổng hợp toàn viện (ban giám đốc) + xuất PDF — CHỈ ADMIN."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import Department, User
from ..pdf_export import export_summary_pdf
from ..report import resolve_range
from ..summary import build_summary

router = APIRouter(tags=["summary"])


def _hospital(db: Session) -> str:
    dept0 = db.scalars(
        select(Department).where(Department.active.is_(True)).limit(1)
    ).first()
    return dept0.hospital if dept0 else "BỆNH VIỆN"


@router.get("/tong-hop", response_class=HTMLResponse)
def tong_hop(
    request: Request,
    mode: str = "month",
    ref: str | None = None,
    tu: str | None = None,
    den: str | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ref_d = date.fromisoformat(ref) if ref else date.today()
    dfrom, dto, label = resolve_range(mode, ref_d, tu, den)
    rows = build_summary(db, dfrom, dto)
    hospital = _hospital(db)
    totals = {
        "kham": sum(r["kham"] for r in rows),
        "vao": sum(r["vao"] for r in rows),
        "ra": sum(r["ra"] for r in rows),
        "tu_vong": sum(r["tu_vong"] for r in rows),
        "hien_con": sum(r["hien_con"] for r in rows),
        "tong_chi_tieu": sum(r["tong_chi_tieu"] for r in rows),
    }
    qs = [f"mode={mode}"]
    if ref:
        qs.append(f"ref={ref}")
    if tu:
        qs.append(f"tu={tu}")
    if den:
        qs.append(f"den={den}")
    return request.app.state.templates.TemplateResponse(
        request,
        "summary.html",
        {
            "user": user,
            "mode": mode,
            "ref": ref_d,
            "tu": tu,
            "den": den,
            "label": label,
            "dfrom": dfrom,
            "dto": dto,
            "rows": rows,
            "totals": totals,
            "hospital": hospital,
            "qs_base": "&".join(qs),
            "today": date.today(),
        },
    )


@router.get("/tong-hop/xuat-pdf")
def tong_hop_pdf(
    mode: str = "month",
    ref: str | None = None,
    tu: str | None = None,
    den: str | None = None,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ref_d = date.fromisoformat(ref) if ref else date.today()
    dfrom, dto, label = resolve_range(mode, ref_d, tu, den)
    rows = build_summary(db, dfrom, dto)
    data = export_summary_pdf(rows, label, _hospital(db))
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="TongHopToanVien_{dfrom.isoformat()}_{dto.isoformat()}.pdf"'
            )
        },
    )
