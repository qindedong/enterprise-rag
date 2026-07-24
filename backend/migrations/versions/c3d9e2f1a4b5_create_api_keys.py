"""create api_keys table

开放 API Key：第三方系统凭据，只存 SHA-256 哈希。

Revision ID: c3d9e2f1a4b5
Revises: b2f8c1d4e5a6
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d9e2f1a4b5"
down_revision = "b2f8c1d4e5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("prefix", sa.String(length=20), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")
