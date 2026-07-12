"""complete required workflows

Revision ID: 8f4d2a1c9b70
Revises: 32bc8f422613
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f4d2a1c9b70"
down_revision: str | Sequence[str] | None = "32bc8f422613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_reset_token_hash", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_password_reset_token_hash", "users", ["password_reset_token_hash"], unique=False)

    op.add_column("assets", sa.Column("document_urls", sa.JSON(), nullable=True))
    op.execute("UPDATE assets SET document_urls = JSON_ARRAY() WHERE document_urls IS NULL")
    op.alter_column("assets", "document_urls", existing_type=sa.JSON(), nullable=False)

    op.add_column("activity_logs", sa.Column("recipient_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_activity_logs_recipient_id_users",
        "activity_logs",
        "users",
        ["recipient_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_activity_logs_recipient_id", "activity_logs", ["recipient_id"], unique=False)

    op.add_column("audit_items", sa.Column("resolution_notes", sa.Text(), nullable=True))
    op.add_column("audit_items", sa.Column("resolution_approved_by", sa.Uuid(), nullable=True))
    op.add_column("audit_items", sa.Column("resolution_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_audit_items_resolution_approved_by_users",
        "audit_items",
        "users",
        ["resolution_approved_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("allocation_status", "allocations", type_="check")
    op.create_check_constraint(
        "allocation_status",
        "allocations",
        "status IN ('ACTIVE','RETURNED','TRANSFER_REQUESTED','TRANSFER_APPROVED','RETURN_REQUESTED')",
    )


def downgrade() -> None:
    op.drop_constraint("allocation_status", "allocations", type_="check")
    op.create_check_constraint(
        "allocation_status",
        "allocations",
        "status IN ('ACTIVE','RETURNED','TRANSFER_REQUESTED','TRANSFER_APPROVED')",
    )
    op.drop_constraint("fk_audit_items_resolution_approved_by_users", "audit_items", type_="foreignkey")
    op.drop_column("audit_items", "resolution_approved_at")
    op.drop_column("audit_items", "resolution_approved_by")
    op.drop_column("audit_items", "resolution_notes")
    op.drop_index("ix_activity_logs_recipient_id", table_name="activity_logs")
    op.drop_constraint("fk_activity_logs_recipient_id_users", "activity_logs", type_="foreignkey")
    op.drop_column("activity_logs", "recipient_id")
    op.drop_column("assets", "document_urls")
    op.drop_index("ix_users_password_reset_token_hash", table_name="users")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token_hash")
