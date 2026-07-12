from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, Enum as SQLEnum, String, text

from app.database.base import AuditMixin, Base


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    ASSET_MANAGER = "ASSET_MANAGER"
    DEPARTMENT_HEAD = "DEPARTMENT_HEAD"
    EMPLOYEE = "EMPLOYEE"


class User(AuditMixin, Base):
    __tablename__ = "users"
    __mapper_args__ = {"eager_defaults": True}

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            length=32,
        ),
        nullable=False,
        default=UserRole.EMPLOYEE,
        server_default=text(f"'{UserRole.EMPLOYEE.value}'"),
    )
    department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True),
        nullable=False,
        default=True,
        server_default=text("1"),
    )
