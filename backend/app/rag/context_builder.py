"""
对话上下文构建器

多轮对话的上下文管理：
- Token 预算裁剪：保留最近 N 轮，总 Token 不超预算（超出则丢弃最早轮次）
- 历史格式化：供查询改写（指代消解）与生成 Prompt 使用
"""

from app.core.logger import get_logger

logger = get_logger(__name__)

MAX_HISTORY_TOKENS = 1500  # 历史消息 Token 预算
MAX_HISTORY_TURNS = 6  # 最多保留轮数（1 轮 = 1 问 1 答）

# tiktoken 延迟加载（加载失败时降级为字符估算）
_encoder = None
_encoder_failed = False


def _count_tokens(text: str) -> int:
    """Token 计数：优先 tiktoken，降级为字符数 / 1.5 估算"""
    global _encoder, _encoder_failed

    if not _encoder_failed:
        try:
            if _encoder is None:
                import tiktoken

                _encoder = tiktoken.get_encoding("cl100k_base")
            return len(_encoder.encode(text))
        except Exception:
            _encoder_failed = True
            logger.warning("tiktoken 不可用，降级为字符估算 Token 数")

    return int(len(text) / 1.5)  # 中文约 1.5 字符 / token


def trim_history(
    messages: list[dict],
    max_tokens: int = MAX_HISTORY_TOKENS,
    max_turns: int = MAX_HISTORY_TURNS,
) -> list[dict]:
    """
    按 Token 预算裁剪对话历史

    策略：从最新消息向回保留完整轮次（user+assistant 成对），
    同时受 max_tokens 与 max_turns 双重约束。

    Args:
        messages: 历史消息 [{"role": "user"|"assistant", "content": "..."}]，时间升序
        max_tokens: Token 预算
        max_turns: 最大保留轮数

    Returns:
        裁剪后的历史（时间升序）
    """
    if not messages:
        return []

    # 只保留 user/assistant 文本消息
    valid = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]

    kept: list[dict] = []
    budget = max_tokens
    # 从最新向回遍历，预算耗尽即停
    for msg in reversed(valid):
        cost = _count_tokens(msg["content"]) + 4  # 4 ≈ role 标记开销
        if cost > budget:
            break
        kept.insert(0, msg)
        budget -= cost

    # 轮数约束：1 轮 = 2 条，从末尾保留
    kept = kept[-(max_turns * 2) :]

    # 保证首条是 user（避免孤儿 assistant 消息开头）
    while kept and kept[0]["role"] != "user":
        kept.pop(0)

    if len(kept) < len(valid):
        logger.info(f"历史裁剪: {len(valid)} → {len(kept)} 条 (预算 {max_tokens} tokens)")

    return kept


def format_history_for_rewrite(messages: list[dict]) -> str:
    """格式化为纯文本（供指代消解 Prompt 使用）"""
    lines = []
    for m in messages:
        role = "用户" if m["role"] == "user" else "助手"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def history_to_chat_messages(messages: list[dict]) -> list[dict]:
    """转换为 OpenAI chat 消息格式（供 LLM 生成使用）"""
    return [{"role": m["role"], "content": m["content"]} for m in messages]
