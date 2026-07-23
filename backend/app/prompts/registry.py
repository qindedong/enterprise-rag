"""
Prompt 模板注册中心

统一管理所有 Prompt 模板，支持变量渲染和版本管理.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class PromptTemplate:
    """Prompt 模板"""

    name: str
    template: str
    variables: list[str]
    description: str = ""


class PromptRegistry:
    """Prompt 模板注册中心"""

    _templates: ClassVar[dict[str, PromptTemplate]] = {}

    @classmethod
    def register(cls, template: PromptTemplate) -> None:
        """注册模板"""
        cls._templates[template.name] = template

    @classmethod
    def get(cls, name: str) -> PromptTemplate:
        """获取模板"""
        if name not in cls._templates:
            raise ValueError(f"Prompt 模板 '{name}' 不存在。可用: {list(cls._templates.keys())}")
        return cls._templates[name]

    @classmethod
    def render(cls, name: str, **kwargs) -> str:
        """渲染模板（替换变量）"""
        template = cls.get(name)
        missing = set(template.variables) - set(kwargs.keys())
        if missing:
            raise ValueError(f"模板 '{name}' 缺少变量: {missing}")
        return template.template.format(**kwargs)


# ===== 注册 RAG 标准 Prompt =====

RAG_SYSTEM_TEMPLATE = PromptTemplate(
    name="rag_system",
    description="RAG 问答 System Prompt — 强制引用来源",
    variables=[],
    template="""你是一个严谨的企业知识库助手。你必须严格遵守以下规则：

## 核心规则
1. **仅基于参考资料回答**：你的回答必须 100% 基于提供的「参考资料」
2. **必须标注引用**：每个事实声明后必须标注来源编号，格式为 [1]、[2]
3. **禁止编造**：如果资料中没有相关信息，必须明确说"根据现有资料，无法回答这个问题"
4. **逐条引用**：每条信息都能找到对应的原文支持

## 回答格式
- 使用 Markdown 组织回答
- 关键信息后紧跟 [N] 引用标记
- 在末尾列出「参考资料」汇总
""",
)

RAG_USER_TEMPLATE = PromptTemplate(
    name="rag_user",
    description="RAG 问答 User Prompt — 组装 Context 和 Question",
    variables=["context", "question"],
    template="""## 参考资料
{context}

## 用户问题
{question}

请基于以上参考资料回答问题。记住：回答中必须包含引用标记 [N]，无相关信息请明确说明无法回答。""",
)

QUERY_REWRITE_TEMPLATE = PromptTemplate(
    name="query_rewrite",
    description="查询改写 Prompt — 口语化→检索优化",
    variables=["question"],
    template="""你是一个查询优化专家。将以下口语化问题改写为更适合文档检索的查询语句：

规则：
1. 补充隐含的上下文
2. 提取核心概念和关键词
3. 使用正式书面表达

原始问题：{question}

请只输出改写后的查询语句，不要输出其他内容。""",
)

QUERY_REWRITE_WITH_HISTORY_TEMPLATE = PromptTemplate(
    name="query_rewrite_with_history",
    description="带对话历史的查询改写 — 指代消解 + 上下文补全",
    variables=["history", "question"],
    template="""你是一个查询优化专家。以下是一段多轮对话的历史和用户的最新问题。

请结合对话历史，将最新问题改写为**独立完整**的检索查询语句：
1. 解析指代（"它"、"这个"、"那"、"上面说的"等），替换为具体对象
2. 补全省略的主语和上下文
3. 提取核心概念和关键词，使用正式书面表达
4. 如果问题本身已完整独立，直接输出原问题

## 对话历史
{history}

## 最新问题
{question}

请只输出改写后的查询语句，不要输出其他内容。""",
)

# 注册全部模板
PromptRegistry.register(RAG_SYSTEM_TEMPLATE)
PromptRegistry.register(RAG_USER_TEMPLATE)
PromptRegistry.register(QUERY_REWRITE_TEMPLATE)
PromptRegistry.register(QUERY_REWRITE_WITH_HISTORY_TEMPLATE)
