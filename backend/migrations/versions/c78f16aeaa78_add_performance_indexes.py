"""补充关键性能索引

- documents: kb_id + status 复合索引
- conversations: user_id / kb_id+user_id 索引
- messages: conversation_id 索引
- kb_members: 联合唯一约束 + user_id 索引
- knowledge_bases: owner_id + status 索引
- api_keys: user_id 索引

Revision ID: c78f16aeaa78
Revises: c3d9e2f1a4b5
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op

revision: str = "c78f16aeaa78"
down_revision = "c3d9e2f1a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === documents: kb_id + status ===
    op.create_index("ix_documents_kb_id_status", "documents", ["kb_id", "status"])

    # === conversations ===
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_kb_id_user_id", "conversations", ["kb_id", "user_id"])

    # === messages（最高频关联） ===
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # === kb_members（权限校验高频） ===
    op.create_unique_constraint("uq_kb_members_kb_user", "kb_members", ["kb_id", "user_id"])
    op.create_index("ix_kb_members_user_id", "kb_members", ["user_id"])

    # === knowledge_bases ===
    op.create_index("ix_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"])
    op.create_index("ix_knowledge_bases_status", "knowledge_bases", ["status"])

    # === api_keys ===
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_knowledge_bases_status", table_name="knowledge_bases")
    op.drop_index("ix_knowledge_bases_owner_id", table_name="knowledge_bases")
    op.drop_index("ix_kb_members_user_id", table_name="kb_members")
    op.drop_constraint("uq_kb_members_kb_user", "kb_members", type_="unique")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_index("ix_conversations_kb_id_user_id", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_index("ix_documents_kb_id_status", table_name="documents")
