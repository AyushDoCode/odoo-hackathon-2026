from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().lower()
        statement = select(User).where(User.email == normalized_email)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_reset_token_hash(self, token_hash: str) -> User | None:
        statement = select(User).where(User.password_reset_token_hash == token_hash)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        department_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[User]:
        statement = select(User)
        if department_id is not None:
            statement = statement.where(User.department_id == department_id)
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def existing_ids(self, user_ids: list[UUID]) -> set[UUID]:
        if not user_ids:
            return set()
        statement = select(User.id).where(User.id.in_(user_ids))
        result = await self.session.execute(statement)
        return set(result.scalars().all())

    async def count_active_in_department(self, department_id: UUID) -> int:
        statement = select(func.count()).select_from(User).where(
            User.department_id == department_id, User.is_active.is_(True)
        )
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
