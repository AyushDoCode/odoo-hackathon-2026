from __future__ import annotations

from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.users.models import UserRole


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_name(value: str) -> str:
    return value.strip()


class UserSummary(BaseModel):
    """Minimal display info for embedding a user reference in another resource
    (e.g. a department's head, a maintenance request's technician)."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    hashed_password: str = Field(min_length=1)
    role: UserRole = Field(default=UserRole.EMPLOYEE)
    department_id: UUID | None = None
    is_active: bool = Field(default=True)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_name(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return _normalize_email(str(value))


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    name: str
    email: EmailStr
    role: UserRole
    department_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    role: UserRole | None = None
    department_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_name(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return None if value is None else _normalize_email(str(value))
