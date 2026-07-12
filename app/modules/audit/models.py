from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database.base import AuditMixin, Base


class AuditCycleStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class VerificationResult(StrEnum):
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    DAMAGED = "DAMAGED"


class AuditCycle(AuditMixin, Base):
    __tablename__ = "audit_cycles"
    __mapper_args__ = {"eager_defaults": True}

    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    auditor_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[AuditCycleStatus] = mapped_column(
        SQLEnum(
            AuditCycleStatus,
            name="audit_cycle_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=False,
        default=AuditCycleStatus.OPEN,
    )

    department = relationship("Department", lazy="raise")
    items = relationship(
        "AuditItem", back_populates="cycle", lazy="raise", cascade="all, delete-orphan"
    )


class AuditItem(AuditMixin, Base):
    __tablename__ = "audit_items"
    __mapper_args__ = {"eager_defaults": True}

    cycle_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("audit_cycles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expected_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification: Mapped[VerificationResult | None] = mapped_column(
        SQLEnum(
            VerificationResult,
            name="audit_verification",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=16,
        ),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    cycle = relationship("AuditCycle", back_populates="items", lazy="raise")
    asset = relationship("Asset", lazy="raise")
    resolution_approver = relationship(
        "User", foreign_keys=[resolution_approved_by], lazy="raise"
    )
