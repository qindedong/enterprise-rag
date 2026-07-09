# Prompt 模板技能 (Prompt)

## 描述
当用户需要设计、优化或管理 RAG 系统中使用的 Prompt 模板时，提供专业的 Prompt 工程指导。

## 触发条件
- 用户提到"Prompt"、"提示词"、"提示模板"
- 用户需要编写 LLM 调用提示
- 用户询问如何提升生成质量

## Prompt 模板管理

### RAG 核心 Prompt 模板

#### 1. 标准 RAG 问答模板
```python
RAG_QA_PROMPT = """你是一个专业的企业知识库助手。请严格基于以下提供的参考资料回答用户问题。

## 回答规则
1. **严格基于资料**：只能使用下面提供的参考资料来回答问题
2. **引用来源**：每个关键信息后标注来源编号，如 [1]、[2]
3. **诚实回答**：如果资料中没有相关信息，请明确说"根据现有资料，无法回答这个问题"
4. **结构化输出**：使用清晰的段落和列表组织回答
5. **保持专业**：使用准确、专业的语言

## 参考资料
{context}

## 用户问题
{question}

## 回答
"""
```

#### 2. 多轮对话 RAG 模板
```python
MULTI_TURN_RAG_PROMPT = """你是一个专业的企业知识库助手。请结合对话历史和参考资料回答用户问题。

## 对话历史
{chat_history}

## 参考资料
{context}

## 当前问题
{question}

## 回答规则
1. 结合对话历史理解用户的真实意图
2. 严格基于参考资料回答
3. 标注引用来源 [N]
4. 如果当前问题是对上一轮回答的追问，直接补充说明，无需重复已说过的内容

## 回答
"""
```

#### 3. 查询改写 Prompt
```python
QUERY_REWRITE_PROMPT = """你是一个查询优化专家。请将用户的原始问题改写为更适合检索的查询语句。

## 改写规则
1. 将口语化表达转为正式书面表达
2. 补充上下文中隐含的关键信息
3. 提取并突出核心实体和概念
4. 生成 {num_variants} 个不同角度的查询变体

## 对话历史
{chat_history}

## 原始问题
{question}

## 改写结果（JSON 格式）
{{
    "main_query": "主要的改写查询",
    "variants": ["变体1", "变体2"],
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "intent": "事实查询 | 分析推理 | 操作指导 | 闲聊其他"
}}
"""
```

#### 4. 文档摘要 Prompt
```python
DOCUMENT_SUMMARY_PROMPT = """你是一个文档分析专家。请为以下文档内容生成摘要。

## 摘要要求
1. 提取文档的核心主题和关键信息
2. 保留重要的事实、数据、日期
3. 识别文档类型和适用场景
4. 摘要长度控制在 {max_length} 字以内

## 文档内容
{content}

## 摘要
"""
```

#### 5. 答案验证 Prompt
```python
ANSWER_VERIFICATION_PROMPT = """你是一个答案质量审核专家。请验证以下 AI 生成的回答是否忠实于提供的参考资料。

## 参考资料
{context}

## AI 回答
{answer}

## 验证要求
逐条检查 AI 回答中的每个事实声明：
1. 是否能在参考资料中找到支持
2. 是否存在编造或曲解
3. 引用的来源编号是否准确

## 验证结果（JSON 格式）
{{
    "is_faithful": true/false,
    "hallucinations": [
        {{
            "claim": "编造的声明内容",
            "reason": "为什么这是幻觉",
            "severity": "critical | major | minor"
        }}
    ],
    "missing_context": ["应该引用但未引用的信息"],
    "overall_score": 0-100,
    "suggestions": "改进建议"
}}
"""
```

#### 6. 来源归因 Prompt
```python
ATTRIBUTION_PROMPT = """你是一个内容溯源专家。请为 AI 回答中的每个事实声明标注信息来源。

## 回答内容
{answer}

## 参考资料（带编号）
{context_with_ids}

## 归因要求
1. 为每个事实声明标注最匹配的来源编号
2. 如果某个声明找不到来源，标注为 [无来源]
3. 确保引用的内容与声明确实相关

## 归因结果
{answer_with_citations}
"""
```

### Prompt 模板变量管理

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class PromptTemplate:
    """Prompt 模板数据结构"""
    name: str
    template: str
    version: str
    variables: list[str]
    description: str
    created_at: str
    updated_at: str

class PromptRegistry:
    """Prompt 模板注册中心"""
    
    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}
    
    def register(self, template: PromptTemplate) -> None:
        self._templates[template.name] = template
    
    def get(self, name: str) -> PromptTemplate:
        if name not in self._templates:
            raise ValueError(f"Prompt 模板 '{name}' 不存在")
        return self._templates[name]
    
    def render(
        self,
        name: str,
        version: Optional[str] = None,
        **kwargs
    ) -> str:
        """渲染 Prompt 模板"""
        template = self.get(name)
        
        # 验证必需变量
        missing_vars = set(template.variables) - set(kwargs.keys())
        if missing_vars:
            raise ValueError(f"缺少必需变量: {missing_vars}")
        
        return template.template.format(**kwargs)
```

### Prompt 优化原则

#### 1. 结构清晰
- 使用分隔符（`##`、`###`）划分不同区域
- 用 Markdown 格式提高可读性
- 关键指令放在开头或结尾

#### 2. 角色设定
- 明确 AI 的角色定位
- 定义能力边界和限制

#### 3. 示例驱动（Few-Shot）
- 提供 2-3 个高质量输入输出示例
- 示例要覆盖边界情况

#### 4. 输出格式约束
- 明确指定输出格式（JSON、Markdown、纯文本）
- 提供格式模板或 Schema

#### 5. 错误处理
- 指示 LLM 如何处理信息不足的情况
- 定义降级策略

#### 6. Token 优化
- System Prompt 尽可能精简
- 历史对话摘要后再传入
- 参考资料只传最相关的部分
