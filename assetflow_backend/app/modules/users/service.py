from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdatefrom app.modules.users.schemas import UserCreate, UserUpdate


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def get_user(self, user_id: UUID) -> User | None:
        return await self.repository.get_by_id(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.repository.get_by_email(email)

    async def list_users(self, *, offset: int = 0, limit: int = 100) -> list[User]:
        return await self.repository.list(offset=offset, limit=limit)

    async def create_user(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        return await self.repository.create(user)

    async def update_user(self, user: User, data: UserUpdate) -> User:
        updates = data.model_dump(exclude_unset=True)
        for field_name, value in updates.items():
            setattr(user, field_name, value)

        await self.repository.session.flush()
        await self.repository.session.refresh(user)
        return user

    async def delete_user(self, user: User) -> None:
        await self.repository.delete(user)