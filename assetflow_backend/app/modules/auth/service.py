from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.schemas import LoginRequest, RegisterRequest, Token
from app.modules.auth.security import create_access_token, hash_password, verify_password
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository


class AuthError(ValueError):
    """Raised for invalid credentials or duplicate signup."""


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def signup(self, data: RegisterRequest) -> User:
        existing = await self.users.get_by_email(data.email)
        if existing is not None:
            raise AuthError("Email is already registered")

        user = User(
            name=data.name.strip(),
            email=data.email.strip().lower(),
            hashed_password=hash_password(data.password),
            role=UserRole.EMPLOYEE,
            is_active=True,
        )
        user = await self.users.create(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def login(self, data: LoginRequest) -> Token:
        user = await self.users.get_by_email(data.email)
        if (
            user is None
            or not user.is_active
            or not verify_password(data.password, user.hashed_password)
        ):
            raise AuthError("Invalid email or password")

        access_token = create_access_token(subject=str(user.id), role=user.role.value)
        return Token(access_token=access_token)
