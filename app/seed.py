# -*- coding: utf-8 -*-
"""Seed dữ liệu ban đầu: admin + khoa mẫu + đối tượng khai báo + dữ liệu demo."""
from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import SEED_ADMIN_PASS, SEED_ADMIN_USER
from .models import (
    ColumnDef,
    Department,
    Entry,
    ReportTemplate,
    RptRow,
    Section,
    User,
)
from .security import hash_password


DEFAULT_OBJECTS = [
    # đối tượng/cột khai báo mặc định cho mẫu BHYT — admin có thể sửa/bớt sau
    dict(col_key="hs", label="HS", group_label="BHYT", kind="input", formula="", sort_order=1),
    dict(col_key="tq", label="TQ", group_label="BHYT", kind="input", formula="", sort_order=2),
    dict(col_key="te", label="TE", group_label="BHYT", kind="input", formula="", sort_order=3),
    dict(col_key="khac", label="Khác", group_label="BHYT", kind="input", formula="", sort_order=4),
    dict(col_key="bhyt_tong", label="Tổng", group_label="BHYT", kind="calc", formula="hs+tq+te+khac", sort_order=5),
    dict(col_key="dich_vu", label="Dịch vụ", group_label="", kind="input", formula="", sort_order=6),
    dict(col_key="tong", label="Tổng", group_label="", kind="calc", formula="bhyt_tong+dich_vu", sort_order=7),
]


def add_default_objects(db: Session, tmpl_id: int) -> None:
    for o in DEFAULT_OBJECTS:
        db.add(ColumnDef(tmpl_id=tmpl_id, **o))


def ensure_seed(db: Session) -> None:
    """Tạo admin + dữ liệu mẫu nếu DB trống."""
    has_user = db.scalar(select(User).limit(1))
    if has_user:
        return

    # --- admin ---
    db.add(
        User(
            username=SEED_ADMIN_USER,
            password_hash=hash_password(SEED_ADMIN_PASS),
            full_name="Quản trị viên",
            role="admin",
            dept_id=None,
            active=True,
        )
    )

    # --- khoa + mẫu ---
    kpk = Department(code="KPK", name="Khu Phẫu khoái", hospital="BỆNH VIỆN QUÂN Y 4", report_code="B4")
    ngoai = Department(code="NGOAI", name="Khoa Ngoại", hospital="BỆNH VIỆN QUÂN Y 4", report_code="B4")
    noi = Department(code="NOI", name="Khoa Nội tổng hợp", hospital="BỆNH VIỆN QUÂN Y 4", report_code="B4")
    db.add_all([kpk, ngoai, noi])
    db.flush()

    # users theo khoa (đăng nhập được ngay)
    for uname, dept in [("kpk", kpk), ("ngoai", ngoai), ("noi", noi)]:
        db.add(
            User(
                username=uname,
                password_hash=hash_password("Khoa@123"),
                full_name=f"Tài khoản {dept.name}",
                role="user",
                dept_id=dept.id,
                active=True,
            )
        )

    # --- mẫu KPhẫu khoái (đúng ảnh Excel) ---
    t1 = ReportTemplate(dept_id=kpk.id, name="Báo cáo công tác chuyên môn - Khu Phẫu khoái")
    db.add(t1)
    db.flush()
    add_default_objects(db, t1.id)

    s1 = Section(tmpl_id=t1.id, title="1. Tổng kê khám bệnh Khu Phẫu khoái", sort_order=1)
    s2 = Section(tmpl_id=t1.id, title="2. Tình hình khám và tiêm ngừa (Phòng 32)", sort_order=2)
    s3 = Section(tmpl_id=t1.id, title="3. Tình hình bệnh nhân nội trú", sort_order=3)
    db.add_all([s1, s2, s3])
    db.flush()

    from .models import Block

    blocks_spec = [
        ("1.1. Trong giờ", [("Nhi khoa", "Khám bệnh"), ("Nhi khoa", "Vào viện")]),
        ("1.2. Ngoài giờ", [("Nhi khoa", "Khám bệnh"), ("Nhi khoa", "Vào viện")]),
        ("1.3. Cấp cứu nhi khoa", [("Nhi khoa", "Khám bệnh"), ("Nhi khoa", "Vào viện")]),
        ("1.4. Chuyển viện", [("Nhi khoa", "Tự túc"), ("Nhi khoa", "Hộ tống")]),
    ]
    for i, (label, rows) in enumerate(blocks_spec):
        b = Block(section_id=s1.id, label=label, sort_order=i)
        db.add(b)
        db.flush()
        for g, r in rows:
            db.add(RptRow(section_id=s1.id, block_id=b.id, group_label=g, row_label=r, agg="sum", sort_order=0))

    for i, r in enumerate(["Khám bệnh", "Tiêm ngừa"]):
        db.add(RptRow(section_id=s2.id, group_label="", row_label=r, agg="sum", sort_order=i))

    for i, (r, agg) in enumerate(
        [
            ("Cũ", "first"),
            ("Vào", "sum"),
            ("Chuyển khoa đến", "sum"),
            ("Chuyển khoa đi", "sum"),
            ("Chuyển viện", "sum"),
            ("Tử vong", "sum"),
            ("Ra viện", "sum"),
            ("Hiện còn", "last"),
        ]
    ):
        db.add(RptRow(section_id=s3.id, group_label="", row_label=r, agg=agg, sort_order=i))

    # --- mẫu Khoa Ngoại ---
    t2 = ReportTemplate(dept_id=ngoai.id, name="Báo cáo phẫu thuật - Khoa Ngoại")
    db.add(t2)
    db.flush()
    add_default_objects(db, t2.id)
    ns1 = Section(tmpl_id=t2.id, title="1. Phẫu thuật trong ngày", sort_order=1)
    ns2 = Section(tmpl_id=t2.id, title="2. Bệnh nhân nội trú", sort_order=2)
    db.add_all([ns1, ns2])
    db.flush()
    for i, r in enumerate(["Phẫu thuật lớn", "Phẫu thuật nhỏ", "Can thiệp tối thiểu"]):
        db.add(RptRow(section_id=ns1.id, group_label="", row_label=r, agg="sum", sort_order=i))
    for i, (r, agg) in enumerate(
        [("Cũ", "first"), ("Vào viện", "sum"), ("Ra viện", "sum"), ("Hiện còn", "last")]
    ):
        db.add(RptRow(section_id=ns2.id, group_label="", row_label=r, agg=agg, sort_order=i))

    # --- mẫu Nội ---
    t3 = ReportTemplate(dept_id=noi.id, name="Báo cáo khám & điều trị - Nội tổng hợp")
    db.add(t3)
    db.flush()
    add_default_objects(db, t3.id)
    i1 = Section(tmpl_id=t3.id, title="1. Khám bệnh", sort_order=1)
    i2 = Section(tmpl_id=t3.id, title="2. Điều trị nội trú", sort_order=2)
    db.add_all([i1, i2])
    db.flush()
    for i, (g, r) in enumerate(
        [("Nội tim mạch", "Khám bệnh"), ("Nội hô hấp", "Khám bệnh"), ("Nội tiêu hóa", "Khám bệnh")]
    ):
        db.add(RptRow(section_id=i1.id, group_label=g, row_label=r, agg="sum", sort_order=i))
    for i, (r, agg) in enumerate(
        [("Cũ", "first"), ("Vào", "sum"), ("Ra viện", "sum"), ("Tử vong", "sum"), ("Hiện còn", "last")]
    ):
        db.add(RptRow(section_id=i2.id, group_label="", row_label=r, agg=agg, sort_order=i))

    db.flush()
    _sample_entries(db)
    db.commit()


def _sample_value(row_label: str) -> int:
    r = row_label.lower()
    if any(k in r for k in ["cũ", "hiện còn"]):
        return random.randint(40, 70)
    if any(k in r for k in ["tử vong", "chuyển viện", "hộ tống"]):
        return random.randint(0, 2)
    if "khám" in r or "tiêm" in r:
        return random.randint(15, 60)
    if "phẫu" in r or "can thiệp" in r:
        return random.randint(1, 8)
    if any(k in r for k in ["vào", "ra viện", "chuyển khoa"]):
        return random.randint(3, 15)
    return random.randint(1, 10)


def _sample_entries(db: Session, days: int = 40) -> None:
    random.seed(42)
    today = date.today()
    rows = db.execute(
        select(RptRow.id, RptRow.row_label, ReportTemplate.id)
        .join(Section, RptRow.section_id == Section.id)
        .join(ReportTemplate, Section.tmpl_id == ReportTemplate.id)
    ).all()
    input_keys = ["hs", "tq", "te", "khac", "dich_vu"]
    for d in range(days, -1, -1):
        day = today - timedelta(days=d)
        for row_id, label, tmpl_id in rows:
            if random.random() < 0.08:
                continue
            base = _sample_value(label)
            vals = {
                "hs": int(base * random.uniform(0.4, 0.7)),
                "tq": int(base * random.uniform(0.05, 0.15)),
                "te": int(base * random.uniform(0.1, 0.25)),
                "khac": int(base * random.uniform(0.0, 0.1)),
                "dich_vu": int(base * random.uniform(0.0, 0.15)),
            }
            for k in input_keys:
                db.add(
                    Entry(
                        tmpl_id=tmpl_id,
                        row_id=row_id,
                        col_key=k,
                        entry_date=day,
                        value=float(vals[k]),
                    )
                )
    db.flush()
