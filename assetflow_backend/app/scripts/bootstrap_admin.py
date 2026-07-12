from __future__ import annotations

import asyncio
import os
from dotenv import load_dotenv

from app.database.session import AsyncSessionLocal
from app.modules.auth.security import hash_password
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository


async def bootstrap() -> None:
    load_dotenv()
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    name = os.environ.get("BOOTSTRAP_ADMIN_NAME", "AssetFlow Admin").strip()
    if not email or len(password) < 8:
        raise SystemExit(
            "Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD (minimum 8 characters)."
        )

    async with AsyncSessionLocal() as session:
        repository = UserRepository(session)
        user = await repository.get_by_email(email)
        if user is None:
            user = User(
                name=name,
                email=email,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            await repository.create(user)
        else:
            user.name = name
            user.hashed_password = hash_password(password)
            user.role = UserRole.ADMIN
            user.is_active = True
        await session.commit()
        print(f"Admin ready: {email}")


if __name__ == "__main__":
    asyncio.run(bootstrap())
