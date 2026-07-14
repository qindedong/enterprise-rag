"""Repository 层扩展测试 — DocumentRepository, ConversationRepository, MessageRepository"""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.document import Document, DocType, DocStatus, DocumentChunk
from app.models.database.conversation import Conversation, ConvStatus
from app.models.database.knowledge_base import KnowledgeBase
from app.repositories.document_repository import DocumentRepository, ChunkRepository
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.repositories.kb_repository import KBRepository


@pytest.mark.unit
class TestDocumentRepository:
    """DocumentRepository 测试"""

    @pytest.mark.asyncio
    async def test_create_and_find_by_id(self, db_session: AsyncSession):
        """测试：创建和按 ID 查找文档"""
        kb = await _create_test_kb(db_session)
        repo = DocumentRepository(db_session)

        doc = await repo.create(kb_id=kb.id, title="测试文档.md", file_type="md", file_size=100)
        await db_session.commit()

        found = await repo.find_by_id(doc.id)
        assert found is not None
        assert found.title == "测试文档.md"
        assert found.file_type == DocType.MD

    @pytest.mark.asyncio
    async def test_find_by_hash_dedup(self, db_session: AsyncSession):
        """测试：按内容哈希去重"""
        kb = await _create_test_kb(db_session)
        repo = DocumentRepository(db_session)

        await repo.create(kb_id=kb.id, title="doc1.md", file_type="md", content_hash="abc123")
        await db_session.commit()

        found = await repo.find_by_hash(kb.id, "abc123")
        assert found is not None

        not_found = await repo.find_by_hash(kb.id, "nonexistent")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_update_status(self, db_session: AsyncSession):
        """测试：更新文档状态"""
        kb = await _create_test_kb(db_session)
        repo = DocumentRepository(db_session)

        doc = await repo.create(kb_id=kb.id, title="doc.md", file_type="md")
        await db_session.commit()

        await repo.update_status(doc.id, DocStatus.PROCESSING)
        await db_session.commit()

        updated = await repo.find_by_id(doc.id)
        assert updated.status == DocStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_list_by_kb_with_filters(self, db_session: AsyncSession):
        """测试：分页 + 状态 + 类型 + 搜索过滤"""
        kb = await _create_test_kb(db_session)
        repo = DocumentRepository(db_session)

        await repo.create(kb_id=kb.id, title="手册.pdf", file_type="pdf")
        await repo.create(kb_id=kb.id, title="说明.md", file_type="md")
        await repo.create(kb_id=kb.id, title="README.txt", file_type="txt")
        await db_session.commit()

        # 全部
        items, total = await repo.list_by_kb(kb.id, page=1, page_size=10)
        assert total == 3

        # 按类型过滤
        items, total = await repo.list_by_kb(kb.id, file_type="pdf")
        assert total == 1
        assert items[0].title == "手册.pdf"

        # 按搜索过滤
        items, total = await repo.list_by_kb(kb.id, search="说明")
        assert total == 1
        assert items[0].title == "说明.md"

    @pytest.mark.asyncio
    async def test_soft_delete(self, db_session: AsyncSession):
        """测试：软删除"""
        kb = await _create_test_kb(db_session)
        repo = DocumentRepository(db_session)

        doc = await repo.create(kb_id=kb.id, title="要删除的.md", file_type="md")
        await db_session.commit()

        await repo.soft_delete(doc.id)
        await db_session.commit()

        # 软删除后 list 不包含它
        items, total = await repo.list_by_kb(kb.id)
        assert total == 0


@pytest.mark.unit
class TestChunkRepository:
    """ChunkRepository 测试"""

    @pytest.mark.asyncio
    async def test_bulk_insert_and_get_by_document(self, db_session: AsyncSession):
        """测试：批量插入分块 + 按文档获取"""
        kb = await _create_test_kb(db_session)
        doc_repo = DocumentRepository(db_session)
        chunk_repo = ChunkRepository(db_session)

        doc = await doc_repo.create(kb_id=kb.id, title="doc.md", file_type="md")
        await db_session.commit()

        chunks = await chunk_repo.bulk_insert(
            doc.id, kb.id,
            chunks=["第一段", "第二段", "第三段"],
            token_counts=[5, 8, 6],
        )
        await db_session.commit()

        assert len(chunks) == 3
        assert chunks[0].chunk_index == 0
        assert chunks[0].content == "第一段"

        # get_by_document
        retrieved = await chunk_repo.get_by_document(doc.id)
        assert len(retrieved) == 3

        # get_chunk_ids
        ids = await chunk_repo.get_chunk_ids_by_document(doc.id)
        assert len(ids) == 3


@pytest.mark.unit
class TestConversationRepository:
    """ConversationRepository 测试"""

    @pytest.mark.asyncio
    async def test_create_and_find_by_id(self, db_session: AsyncSession):
        """测试：创建和查找对话"""
        kb = await _create_test_kb(db_session)
        repo = ConversationRepository(db_session)

        conv = await repo.create(kb_id=kb.id, user_id=uuid4(), title="测试对话")
        await db_session.commit()

        found = await repo.find_by_id(conv.id)
        assert found is not None
        assert found.title == "测试对话"

    @pytest.mark.asyncio
    async def test_list_by_user(self, db_session: AsyncSession):
        """测试：按用户分页查询对话"""
        kb = await _create_test_kb(db_session)
        user_id = uuid4()
        repo = ConversationRepository(db_session)

        await repo.create(kb_id=kb.id, user_id=user_id, title="对话1")
        await repo.create(kb_id=kb.id, user_id=user_id, title="对话2")
        await db_session.commit()

        convs, total = await repo.list_by_user(user_id, kb_id=kb.id, page=1, page_size=10)
        assert total == 2

        convs_no_kb, total = await repo.list_by_user(user_id, page=1, page_size=10)
        assert total == 2

    @pytest.mark.asyncio
    async def test_delete(self, db_session: AsyncSession):
        """测试：软删除对话"""
        kb = await _create_test_kb(db_session)
        user_id = uuid4()
        repo = ConversationRepository(db_session)

        conv = await repo.create(kb_id=kb.id, user_id=user_id, title="要删的")
        await db_session.commit()

        await repo.delete(conv.id)
        await db_session.commit()

        # 删除后列表为空
        convs, total = await repo.list_by_user(user_id)
        assert total == 0

    @pytest.mark.asyncio
    async def test_update_message_count(self, db_session: AsyncSession):
        """测试：更新消息计数"""
        kb = await _create_test_kb(db_session)
        conv_repo = ConversationRepository(db_session)
        msg_repo = MessageRepository(db_session)

        conv = await conv_repo.create(kb_id=kb.id, user_id=uuid4(), title="计数测试")
        await db_session.commit()

        await msg_repo.create(conversation_id=conv.id, role="user", content="你好")
        await msg_repo.create(conversation_id=conv.id, role="assistant", content="你好！有什么可以帮你的？")
        await db_session.commit()

        await conv_repo.update_message_count(conv.id)
        await db_session.commit()

        # 重新查找验证
        updated = await conv_repo.find_by_id(conv.id)
        assert updated.message_count == 2


@pytest.mark.unit
class TestMessageRepository:
    """MessageRepository 测试"""

    @pytest.mark.asyncio
    async def test_create_and_get_by_conversation(self, db_session: AsyncSession):
        """测试：创建消息 + 按对话获取"""
        kb = await _create_test_kb(db_session)
        conv_repo = ConversationRepository(db_session)
        msg_repo = MessageRepository(db_session)

        conv = await conv_repo.create(kb_id=kb.id, user_id=uuid4(), title="test")
        await db_session.commit()

        await msg_repo.create(conversation_id=conv.id, role="user", content="问题1")
        await msg_repo.create(conversation_id=conv.id, role="assistant", content="回答1",
                              citations=[{"idx": 1}], token_usage={"total": 50})
        await db_session.commit()

        msgs = await msg_repo.get_by_conversation(conv.id)
        assert len(msgs) == 2
        assert msgs[0].role.value == "user"
        assert msgs[1].role.value == "assistant"

    @pytest.mark.asyncio
    async def test_set_feedback(self, db_session: AsyncSession):
        """测试：设置消息反馈"""
        kb = await _create_test_kb(db_session)
        conv_repo = ConversationRepository(db_session)
        msg_repo = MessageRepository(db_session)

        conv = await conv_repo.create(kb_id=kb.id, user_id=uuid4(), title="test")
        await db_session.commit()

        msg = await msg_repo.create(conversation_id=conv.id, role="assistant", content="回答")
        await db_session.commit()

        await msg_repo.set_feedback(msg.id, "positive", "很有帮助")
        await db_session.commit()

        msgs = await msg_repo.get_by_conversation(conv.id)
        assert msgs[0].feedback.value == "positive"
        assert msgs[0].feedback_comment == "很有帮助"

    @pytest.mark.asyncio
    async def test_set_feedback_none(self, db_session: AsyncSession):
        """测试：取消反馈"""
        kb = await _create_test_kb(db_session)
        conv_repo = ConversationRepository(db_session)
        msg_repo = MessageRepository(db_session)

        conv = await conv_repo.create(kb_id=kb.id, user_id=uuid4(), title="test")
        await db_session.commit()

        msg = await msg_repo.create(conversation_id=conv.id, role="assistant", content="回答")
        await db_session.commit()

        await msg_repo.set_feedback(msg.id, "positive")
        await db_session.commit()
        await msg_repo.set_feedback(msg.id, None)
        await db_session.commit()

        msgs = await msg_repo.get_by_conversation(conv.id)
        assert msgs[0].feedback is None


async def _create_test_kb(db_session: AsyncSession) -> KnowledgeBase:
    """辅助函数：创建测试用知识库"""
    repo = KBRepository(db_session)
    kb = await repo.create(name="测试库", owner_id=uuid4())
    await db_session.commit()
    return kb
