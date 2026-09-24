# -*- coding: utf-8 -*-
"""ORM models — production."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(128), default="")
    # admin: toàn quyền; user: chỉ khoa được gán
    role: Mapped[str] = mapped_column(String(16), default="user")  # admin | user
    dept_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    dept: Mapped[Department | None] = relationship("Department", lazy="selectin")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    hospital: Mapped[str] = mapped_column(String(160), default="BỆNH VIỆN QUÂN Y 4")
    report_code: Mapped[str] = mapped_column(String(16), default="B4")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    templates: Mapped[list[ReportTemplate]] = relationship(
        "ReportTemplate", back_populates="dept", cascade="all, delete-orphan"
    )


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dept_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160), default="BÁO CÁO CÔNG TÁC CHUYÊN MÔN")
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    dept: Mapped[Department] = relationship("Department", back_populates="templates")
    sections: Mapped[list[Section]] = relationship(
        "Section",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="Section.sort_order",
    )
    columns_: Mapped[list[ColumnDef]] = relationship(
        "ColumnDef",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ColumnDef.sort_order",
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmpl_id: Mapped[int] = mapped_column(
        ForeignKey("report_templates.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    template: Mapped[ReportTemplate] = relationship("ReportTemplate", back_populates="sections")
    blocks: Mapped[list[Block]] = relationship(
        "Block", back_populates="section", cascade="all, delete-orphan", order_by="Block.sort_order"
    )
    rows: Mapped[list[RptRow]] = relationship(
        "RptRow", back_populates="section", cascade="all, delete-orphan", order_by="RptRow.sort_order"
    )


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped[Section] = relationship("Section", back_populates="blocks")
    rows: Mapped[list[RptRow]] = relationship(
        "RptRow", back_populates="block", cascade="all, delete-orphan"
    )


class RptRow(Base):
    __tablename__ = "rpt_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("sections.id", ondelete="CASCADE"), index=True
    )
    block_id: Mapped[int | None] = mapped_column(
        ForeignKey("blocks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    group_label: Mapped[str] = mapped_column(String(120), default="")
    row_label: Mapped[str] = mapped_column(String(160))
    agg: Mapped[str] = mapped_column(String(8), default="sum")  # sum | first | last
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped[Section] = relationship("Section", back_populates="rows")
    block: Mapped[Block | None] = relationship("Block", back_populates="rows")


class ColumnDef(Base):
    """Đối tượng / cột số liệu của mẫu báo cáo — khai báo linh hoạt (không set cứng)."""

    __tablename__ = "columns_def"
    __table_args__ = (UniqueConstraint("tmpl_id", "col_key", name="uq_tmpl_colkey"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmpl_id: Mapped[int] = mapped_column(
        ForeignKey("report_templates.id", ondelete="CASCADE"), index=True
    )
    col_key: Mapped[str] = mapped_column(String(48))  # slug: hs, tq, dich_vu...
    label: Mapped[str] = mapped_column(String(80))  # hiển thị: HS, TQ, Dịch vụ
    group_label: Mapped[str] = mapped_column(String(80), default="")  # 'BHYT' hoặc ''
    kind: Mapped[str] = mapped_column(String(8), default="input")  # input | calc
    formula: Mapped[str] = mapped_column(String(200), default="")  # calc: hs+tq+te
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    template: Mapped[ReportTemplate] = relationship(
        "ReportTemplate", back_populates="columns_"
    )


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("tmpl_id", "row_id", "col_key", "entry_date", name="uq_entry"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tmpl_id: Mapped[int] = mapped_column(
        ForeignKey("report_templates.id", ondelete="CASCADE"), index=True
    )
    row_id: Mapped[int] = mapped_column(
        ForeignKey("rpt_rows.id", ondelete="CASCADE"), index=True
    )
    col_key: Mapped[str] = mapped_column(String(48))
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float, default=0)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """Lịch sử sửa số liệu — ai sửa ô nào, từ gì → gì."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username: Mapped[str] = mapped_column(String(64), default="")
    dept_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tmpl_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    row_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    row_label: Mapped[str] = mapped_column(String(160), default="")
    col_key: Mapped[str] = mapped_column(String(48), default="")
    entry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    old_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    new_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    action: Mapped[str] = mapped_column(String(16), default="update")  # create|update
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    dept: Mapped[Department | None] = relationship("Department", lazy="selectin")
