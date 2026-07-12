"""Imports every ORM model module so SQLAlchemy's mapper registry is fully
populated before configure_mappers() runs (app startup, Alembic autogenerate).
Add new modules here as they're built.
"""

import app.modules.categories.models  # noqa: F401
import app.modules.departments.models  # noqa: F401
import app.modules.users.models  # noqa: F401
import app.modules.assets.models  # noqa: F401
