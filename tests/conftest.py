from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.database.models_registry  # noqa: F401 - populate ORM mapper registry
from app.core.config import settings
from app.modules.assets.models import Asset, AssetStatus
from app.modules.categories.models import AssetCategory
from app.modules.users.models import User, UserRole


@pytest_asyncio.fixture
async def session_factory():
    """A fresh engine per test, bound to that test's own event loop -- the shared
    app.database.session engine is a module-level singleton whose pooled connections
    get bound to whichever event loop created them, which breaks across test functions
    since pytest-asyncio gives each test its own loop.
    """
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False, autocommit=False
    )
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncGenerator:
    async with session_factory() as session:
        yield session


async def make_user(session, *, role: UserRole = UserRole.EMPLOYEE) -> User:
    user = User(
        name="Test User",
        email=f"test-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="not-a-real-hash",
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def make_asset(
    session, *, is_bookable: bool = False, status: AssetStatus = AssetStatus.AVAILABLE
) -> tuple[AssetCategory, Asset]:
    category = AssetCategory(name=f"TestCat-{uuid.uuid4().hex[:10]}")
    session.add(category)
    await session.flush()

    asset = Asset(
        tag=f"TEST-{uuid.uuid4().hex[:10]}",
        name="Test Asset",
        category_id=category.id,
        status=status,
        is_bookable=is_bookable,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return category, asset


async def cleanup(session, *, asset_ids=(), category_ids=(), user_ids=()):
    """Best-effort teardown against the shared dev DB -- deletes in dependency order."""
    from sqlalchemy import delete

    from app.modules.allocations.models import Allocation
    from app.modules.bookings.models import Booking
    from app.modules.maintenance.models import MaintenanceRequest

    if asset_ids:
        await session.execute(delete(Allocation).where(Allocation.asset_id.in_(asset_ids)))
        await session.execute(delete(Booking).where(Booking.resource_id.in_(asset_ids)))
        await session.execute(
            delete(MaintenanceRequest).where(MaintenanceRequest.asset_id.in_(asset_ids))
        )
        await session.execute(delete(Asset).where(Asset.id.in_(asset_ids)))
    if category_ids:
        await session.execute(delete(AssetCategory).where(AssetCategory.id.in_(category_ids)))
    if user_ids:
        await session.execute(delete(User).where(User.id.in_(user_ids)))
    await session.commit()
