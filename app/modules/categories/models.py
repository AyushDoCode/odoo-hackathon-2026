from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import AuditMixin, Base


class AssetCategory(AuditMixin, Base):
    __tablename__ = "asset_categories"
    __mapper_args__ = {"eager_defaults": True}

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
