from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Date, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database.base import AuditMixin, Base


class AllocationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RETURNED = "RETURNED"
    TRANSFER_REQUESTED = "TRANSFER_REQUESTED"
    TRANSFER_APPROVED = "TRANSFER_APPROVED"
    RETURN_REQUESTED = "RETURN_REQUESTED"


class Allocation(AuditMixin, Base):
    __tablename__ = "allocations"
    __mapper_args__ = {"eager_defaults": True}

    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    to_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AllocationStatus] = mapped_column(
        SQLEnum(
            AllocationStatus,
            name="allocation_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=32,
        ),
        nullable=False,
        default=AllocationStatus.ACTIVE,
    )
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_condition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transfer_to_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    asset = relationship("Asset", lazy="raise")
    from_user = relationship("User", foreign_keys=[from_user_id], lazy="raise")
    to_user = relationship("User", foreign_keys=[to_user_id], lazy="raise")
    transfer_to_user = relationship("User", foreign_keys=[transfer_to_user_id], lazy="raise")
    department = relationship("Department", lazy="raise")
