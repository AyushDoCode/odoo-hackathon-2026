from __future__ import annotations

from uuid import UUID

from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Boolean, ForeignKey, String, text

from app.database.base import AuditMixin, Base


class Department(AuditMixin, Base):
    __tablename__ = "departments"
    __mapper_args__ = {"eager_defaults": True}

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
