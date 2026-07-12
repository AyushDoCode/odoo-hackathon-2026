from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.departments.models import Department


class DepartmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _eager(self):
        return select(Department).options(
            selectinload(Department.head), selectinload(Department.parent_department)
        )

    async def get_by_id(self, department_id: UUID) -> Department | None:
        statement = self._eager().where(Department.id == department_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Department | None:
        statement = select(Department).where(Department.name == name.strip())
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Department]:
        statement = self._eager().offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def find_by_head(self, head_id: UUID) -> list[Department]:
        statement = select(Department).where(Department.head_id == head_id)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(self, department: Department) -> Department:
        self.session.add(department)
        await self.session.flush()
        await self.session.refresh(department, attribute_names=["head", "parent_department"])
        return department

    async def delete(self, department: Department) -> None:
        await self.session.delete(department)
