from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database.session import get_db
from app.modules.auth.schemas import LoginRequest, RegisterRequest, Token
from app.modules.auth.service import AuthError, AuthService
from app.modules.users.models import User
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(
    data: RegisterRequest, session: AsyncSession = Depends(get_db)
) -> UserRead:
    """Creates an Employee account only. No role selection at signup."""
    service = AuthService(session)
    try:
        user = await service.signup(data)
    except AuthError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
async def login(data: LoginRequest, session: AsyncSession = Depends(get_db)) -> Token:
    service = AuthService(session)
    try:
        return await service.login(data)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
