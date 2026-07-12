from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import logging
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

from app.modules.auth.schemas import LoginRequest, RegisterRequest, ResetPasswordRequest, Token
from app.modules.auth.security import create_access_token, hash_password, verify_password
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


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

    async def create_password_reset(self, email: str) -> None:
        """Issues a reset token if the email matches an active account. The token is
        never returned to the caller -- it must be delivered out-of-band (e.g. email)
        so that knowing an address alone can't be used to take over the account.
        """
        token = secrets.token_urlsafe(32)
        user = await self.users.get_by_email(email)
        if user is not None and user.is_active:
            user.password_reset_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            user.password_reset_expires_at = datetime.now(UTC) + timedelta(
                minutes=settings.password_reset_expire_minutes
            )
            await self.session.commit()
            # No email/SMS provider is wired up for this hackathon build -- log the
            # token server-side so a developer/demo operator can retrieve it instead
            # of exposing it over the API.
            logger.info("Password reset requested for %s: token=%s", user.email, token)

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        token_hash = hashlib.sha256(data.reset_token.encode("utf-8")).hexdigest()
        user = await self.users.get_by_reset_token_hash(token_hash)
        now = datetime.now(UTC)
        if (
            user is None
            or user.password_reset_expires_at is None
            or user.password_reset_expires_at.replace(tzinfo=UTC) <= now
        ):
            raise AuthError("Reset token is invalid or expired")
        user.hashed_password = hash_password(data.new_password)
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        await self.session.commit()
