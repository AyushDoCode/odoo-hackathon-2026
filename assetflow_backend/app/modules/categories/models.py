from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, DateTime, JSON, String, func, textfrom sqlalchemy.types import Uuid

from app.database.base import Base


class AssetCategory(Base):
    __tablename__ = "asset_categories"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.utc_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.utc_timestamp(),
        server_onupdate=func.utc_timestamp(),
    )
