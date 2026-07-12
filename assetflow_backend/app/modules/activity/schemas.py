from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    actor_id: UUID | None
    action_type: str
    category: str
    target_type: str
    target_id: UUID | None
    message: str
    is_read: bool
    created_at: datetime
