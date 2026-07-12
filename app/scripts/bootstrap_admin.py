from __future__ import annotations

import asyncio
import os
from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email

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
    try:
        # This script writes the User row directly, bypassing the EmailStr-validated
        # request schemas that /auth/login enforces -- without this check, a reserved
        # TLD like ".local"/".test" would create an admin account that can never
        # actually log in, and the mismatch would only surface at login time.
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise SystemExit(f"BOOTSTRAP_ADMIN_EMAIL {email!r} is not usable: {exc}") from exc

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
