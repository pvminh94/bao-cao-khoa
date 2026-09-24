# -*- coding: utf-8 -*-
"""Xuất PDF (reportlab) — font DejaVu hỗ trợ tiếng Việt."""
from __future__ import annotations

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT = "DejaVu"
_FONT_B = "DejaVu-Bold"
_fonts_ready = False


def _ensure_fonts() -> None:
    global _fonts_ready, _FONT, _FONT_B
    if _fonts_ready:
        return
    if os.path.exists(_FONT_REG):
        pdfmetrics.registerFont(TTFont(_FONT, _FONT_REG))
        if os.path.exists(_FONT_BOLD):
            pdfmetrics.registerFont(TTFont(_FONT_B, _FONT_BOLD))
        else:
            pdfmetrics.registerFont(TTFont(_FONT_B, _FONT_REG))
    else:
        _FONT = "Helvetica"
        _FONT_B = "Helvetica-Bold"
    _fonts_ready = True


def _styles():
    _ensure_fonts()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "VNTitle", parent=styles["Heading1"], fontName=_FONT_B, fontSize=14,
        alignment=TA_CENTER, spaceAfter=4,
    )
    center = ParagraphStyle(
        "VNCtr", parent=styles["Normal"], fontName=_FONT, fontSize=10, alignment=TA_CENTER,
    )
    left = ParagraphStyle(
        "VNLeft", parent=styles["Normal"], fontName=_FONT, fontSize=9, alignment=TA_LEFT,
    )
    bold = ParagraphStyle(
        "VNBold", parent=styles["Normal"], fontName=_FONT_B, fontSize=9, alignment=TA_LEFT,
    )
    return title, center, left, bold


def _fmt(v) -> str:
    try:
        fv = float(v)
        if fv.is_integer():
            return str(int(fv))
        return f"{fv:.1f}"
    except Exception:
        return str(v)


def export_report_pdf(report: dict, period_label: str) -> bytes:
    title_st, center_st, left_st, bold_st = _styles()
    dept = report["dept"]
    structure = report["structure"]
    values = report["values"]
    all_cols = sorted(structure["columns"], key=lambda c: (c.sort_order, c.id))
    n_cols = max(len(all_cols), 1)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )

    story = [
        Paragraph(dept.hospital, bold_st),
        Paragraph("Số ....../2026", left_st),
        Paragraph(report["template"].title if report["template"] else "BÁO CÁO", title_st),
        Paragraph(f"<b>{period_label}</b>", center_st),
        Paragraph(f"Khoa: {dept.name} · {dept.report_code}", center_st),
        Spacer(1, 6),
    ]

    data = [
        [Paragraph("<b>STT</b>", left_st), Paragraph("<b>Danh mục</b>", left_st)]
        + [
            Paragraph(
                f"<b>{(c.group_label + ':' + c.label) if c.group_label else c.label}</b>",
                center_st,
            )
            for c in all_cols
        ]
    ]

    stt = 0

    def add_row(label: str, rid: int, stt_val: str):
        data.append(
            [stt_val, label]
            + [_fmt(values.get((rid, c.col_key), 0)) for c in all_cols]
        )

    section_row_idx: list[int] = []
    block_row_idx: list[int] = []
    for sec in structure["sections"]:
        section_row_idx.append(len(data))
        data.append(
            [Paragraph(f"<b>{sec['title']}</b>", bold_st)] + [""] * (1 + len(all_cols))
        )
        for b in sec["blocks"]:
            block_row_idx.append(len(data))
            data.append(
                [Paragraph(f"▸ {b['label']}", left_st)] + [""] * (1 + len(all_cols))
            )
            for r in b["rows"]:
                stt += 1
                lab = f"{r.group_label} — {r.row_label}" if r.group_label else r.row_label
                add_row(lab, r.id, "")
        for r in sec["loose_rows"]:
            stt += 1
            lab = f"{r.group_label} — {r.row_label}" if r.group_label else r.row_label
            add_row(lab, r.id, str(stt))

    page_w = landscape(A4)[0] - 24 * mm
    w_stt, w_label = 12 * mm, 60 * mm
    w_cell = (page_w - w_stt - w_label) / n_cols
    col_widths = [w_stt, w_label] + [w_cell] * n_cols

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.9, 0.98)),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for i in section_row_idx:
        style_cmds += [
            ("BACKGROUND", (0, i), (-1, i), colors.Color(0.93, 0.94, 0.96)),
            ("SPAN", (0, i), (-1, i)),
        ]
    for i in block_row_idx:
        style_cmds += [
            ("BACKGROUND", (0, i), (-1, i), colors.Color(0.97, 0.97, 0.98)),
            ("SPAN", (0, i), (-1, i)),
        ]
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    today = date.today()
    story.append(Spacer(1, 14))
    story.append(
        Paragraph(f"Ngày {today.day} tháng {today.month} năm {today.year}", center_st)
    )
    doc.build(story)
    return buf.getvalue()


def export_summary_pdf(summary_rows: list[dict], period_label: str, hospital: str) -> bytes:
    title_st, center_st, left_st, bold_st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
    )
    story = [
        Paragraph(hospital, bold_st),
        Paragraph("BÁO CÁO TỔNG HỢP TOÀN VIỆN", title_st),
        Paragraph(f"<b>{period_label}</b>", center_st),
        Spacer(1, 8),
    ]

    headers = ["STT", "Mã", "Khoa", "Khám bệnh", "Vào viện", "Ra viện", "Tử vong", "Hiện còn", "Tổng chỉ tiêu"]
    data = [[Paragraph(f"<b>{h}</b>", center_st) for h in headers]]
    for i, r in enumerate(summary_rows, 1):
        data.append(
            [
                str(i), r["code"], r["name"],
                str(int(r["kham"])), str(int(r["vao"])), str(int(r["ra"])),
                str(int(r["tu_vong"])), str(int(r["hien_con"])), str(int(r["tong_chi_tieu"])),
            ]
        )
    data.append(
        [
            "", "", Paragraph("<b>TỔNG CỘNG</b>", bold_st),
            str(int(sum(r["kham"] for r in summary_rows))),
            str(int(sum(r["vao"] for r in summary_rows))),
            str(int(sum(r["ra"] for r in summary_rows))),
            str(int(sum(r["tu_vong"] for r in summary_rows))),
            str(int(sum(r["hien_con"] for r in summary_rows))),
            str(int(sum(r["tong_chi_tieu"] for r in summary_rows))),
        ]
    )

    page_w = landscape(A4)[0] - 24 * mm
    widths = [12 * mm, 20 * mm, 70 * mm]
    rest = page_w - sum(widths)
    widths += [rest / 6] * 6

    tbl = Table(data, colWidths=widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.9, 0.98)),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "LEFT"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.Color(0.93, 0.94, 0.96)),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(tbl)
    today = date.today()
    story.append(Spacer(1, 14))
    story.append(Paragraph(f"Ngày {today.day} tháng {today.month} năm {today.year}", center_st))
    doc.build(story)
    return buf.getvalue()
