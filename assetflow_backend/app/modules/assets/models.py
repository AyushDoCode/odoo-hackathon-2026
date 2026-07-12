from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.database.base import AuditMixin, Base


class AssetStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ALLOCATED = "ALLOCATED"
    RESERVED = "RESERVED"
    MAINTENANCE = "MAINTENANCE"
    LOST = "LOST"
    RETIRED = "RETIRED"
    DISPOSED = "DISPOSED"


class Asset(AuditMixin, Base):
    __tablename__ = "assets"
    __mapper_args__ = {"eager_defaults": True}

    tag: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("asset_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[AssetStatus] = mapped_column(
        SQLEnum(
            AssetStatus,
            name="asset_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=32,
        ),
        nullable=False,
        default=AssetStatus.AVAILABLE,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    qr_code: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    acquisition_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_bookable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_service_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    category = relationship("AssetCategory", lazy="raise")
