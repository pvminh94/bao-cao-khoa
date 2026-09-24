# -*- coding: utf-8 -*-
"""Tổng hợp nhiều khoa cho ban giám đốc."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Department
from .report import build_report


def _collect(report: dict | None) -> dict:
    if not report or not report.get("structure"):
        return {
            "kham": 0.0, "vao": 0.0, "ra": 0.0,
            "tu_vong": 0.0, "hien_con": 0.0, "tong_chi_tieu": 0.0,
        }
    cols = sorted(report["structure"]["columns"], key=lambda c: (c.sort_order, c.id))
    grand_key = None
    for c in cols:
        if c.col_key == "tong":
            grand_key = "tong"
    if grand_key is None:
        calcs = [c for c in cols if c.kind == "calc"]
        if calcs:
            grand_key = calcs[-1].col_key
    input_keys = [c.col_key for c in cols if c.kind == "input"]

    def row_total(rid: int) -> float:
        if grand_key:
            return float(report["values"].get((rid, grand_key), 0) or 0)
        return float(sum(report["values"].get((rid, k), 0) or 0 for k in input_keys))

    all_rows = []
    for sec in report["structure"]["sections"]:
        for b in sec["blocks"]:
            all_rows.extend(b["rows"])
        all_rows.extend(sec["loose_rows"])

    kham = vao = ra = tu_vong = hien_con = tong = 0.0
    for r in all_rows:
        lab = (r.row_label or "").lower()
        total = row_total(r.id)
        if r.agg == "sum":
            tong += total
        if "khám" in lab:
            kham += total
        if lab == "vào" or lab.startswith("vào"):
            vao += total
        if "ra viện" in lab or lab == "ra":
            ra += total
        if "tử vong" in lab:
            tu_vong += total
        if "hiện còn" in lab:
            hien_con += total
    # số liệu thuộc cấu trúc ĐÃ NGỪNG vẫn tính đầy đủ vào tổng
    for it in report.get("legacy") or []:
        lab = (it.get("row_label") or "").lower()
        total = float(it.get("total") or 0)
        if it.get("agg") == "sum":
            tong += total
        if "khám" in lab:
            kham += total
        if lab == "vào" or lab.startswith("vào"):
            vao += total
        if "ra viện" in lab or lab == "ra":
            ra += total
        if "tử vong" in lab:
            tu_vong += total
        if "hiện còn" in lab:
            hien_con += total
    return {
        "kham": kham, "vao": vao, "ra": ra,
        "tu_vong": tu_vong, "hien_con": hien_con, "tong_chi_tieu": tong,
    }


def build_summary(db: Session, date_from: date, date_to: date) -> list[dict]:
    depts = db.scalars(
        select(Department).where(Department.active.is_(True)).order_by(Department.name)
    ).all()
    rows = []
    for d in depts:
        report = build_report(db, d.id, date_from, date_to)
        metrics = _collect(report)
        rows.append({"id": d.id, "code": d.code, "name": d.name, **metrics})
    return rows
