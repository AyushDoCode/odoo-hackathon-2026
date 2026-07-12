from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetimert UUID, uuid4

from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, textrom sqlalchemy.types import Uuid

from app.database.base import Base


class Department(Base):
    __tablename__ = "departments"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    parent_department_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    head_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
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

    parent_department: Mapped[Department | None] = relationship(
        "Department",
        remote_side="Department.id",
        back_populates="child_departments",
        foreign_keys=[parent_department_id],
    )
    child_departments: Mapped[list[Department]] = relationship(
        "Department",
        back_populates="parent_department",
        foreign_keys=[parent_department_id],
    )
    head = relationship("User", foreign_keys=[head_id])
