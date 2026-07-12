from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.departments.models import Department
from app.modules.departments.repository import DepartmentRepository
from app.modules.departments.schemas import DepartmentCreate, DepartmentUpdate


class DepartmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DepartmentRepository(session)

    async def get_department(self, department_id: UUID) -> Department | None:
        return await self.repository.get_by_id(department_id)

    async def get_department_by_name(self, name: str) -> Department | None:
        return await self.repository.get_by_name(name)

    async def list_departments(self, *, offset: int = 0, limit: int = 100) -> list[Department]:
        return await self.repository.list(offset=offset, limit=limit)

    async def create_department(self, data: DepartmentCreate) -> Department:
        department = Department(**data.model_dump())
        department = await self.repository.create(department)
        await self.session.commit()
        await self.session.refresh(department, attribute_names=["head", "parent_department"])
        return department

    async def update_department(self, department: Department, data: DepartmentUpdate) -> Department:
        updates = data.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(department, field_name, value)

        await self.session.commit()
        await self.session.refresh(department, attribute_names=["head", "parent_department"])
        return department

    async def delete_department(self, department: Department) -> None:
        await self.repository.delete(department)
        await self.session.commit()
