"""add BM25 full-text search support to document_chunks

为 document_chunks 表增加：
- content_segmented 列（jieba 分词结果，空格连接）
- search_vector 生成列（tsvector，基于 content_segmented）
- GIN 索引（全文检索）

search_vector 为 PostgreSQL 生成列，不进 ORM（保持 SQLite 测试兼容）。

Revision ID: b2f8c1d4e5a6
Revises: ed0afde051b0
Create Date: 2026-07-24
"""

import sqlalchemy as sa
from alembic import op

revision = "b2f8c1d4e5a6"
down_revision = "ed0afde051b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("content_segmented", sa.Text(), nullable=True),
    )
    # 'simple' 配置按空格/标点切分，与 jieba 预分词配合；
    # 双参数 to_tsvector 是 IMMUTABLE，可用于生成列
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content_segmented, ''))) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_search_vector ON document_chunks USING GIN (search_vector)"
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_kb_id ON document_chunks (kb_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_kb_id")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_search_vector")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_vector")
    op.drop_column("document_chunks", "content_segmented")
