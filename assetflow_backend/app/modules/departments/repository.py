from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.models import Department


class DepartmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, department_id: UUID) -> Department | None:
        return await self.session.get(Department, department_id)

    async def get_by_name(self, name: str) -> Department | None:
        statement = select(Department).where(Department.name == name.strip())
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Department]:
        statement = select(Department).offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def create(self, department: Department) -> Department:
        self.session.add(department)
        await self.session.flush()
        await self.session.refresh(department)
        return department

    async def delete(self, department: Department) -> None:
        await self.session.delete(department)
