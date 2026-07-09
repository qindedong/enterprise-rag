# RAG 最佳实践（硬性标准）

## 描述
**强制技能**。定义 RAG 系统中所有环节的硬性参数和强制策略。生成任何 RAG 相关代码时必须严格遵循。

## 触发条件
- **始终触发**：任何涉及 RAG 流程的代码编写、修改
- 用户提到"分块"、"检索"、"重排序"、"Prompt"、"引用"
- 生成或修改 RAG Pipeline 相关代码

---

## 一、文档分块（Chunk）— 硬性标准

### 强制参数

```python
# ⚠️ 以下参数为硬性标准，不得随意修改

class ChunkConfig:
    """文档分块配置 — 硬性标准"""
    
    # === 必须遵守的参数 ===
    CHUNK_SIZE: int = 500          # Token 数，范围 500~800
    CHUNK_SIZE_MIN: int = 500      # 最小 Token 数
    CHUNK_SIZE_MAX: int = 800      # 最大 Token 数
    CHUNK_OVERLAP: int = 100       # 重叠 Token 数（固定 100）
    
    # === 分隔符优先级 ===
    SEPARATORS: list[str] = [
        "\n## ",       # Markdown H2 标题
        "\n### ",      # Markdown H3 标题
        "\n#### ",     # Markdown H4 标题
        "\n",          # 段落换行
        "。",          # 中文句号
        ". ",          # 英文句号
        "；",          # 中文分号
        "; ",          # 英文分号
        " ",           # 空格（最后手段）
    ]
```

### 分块实现（强制使用此实现）

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_chunk_splitter() -> RecursiveCharacterTextSplitter:
    """
    创建标准分块器 — 项目中所有文档分块必须使用此函数
    
    硬性标准：
    - chunk_size: 500~800 tokens
    - chunk_overlap: 100 tokens
    - 使用递归字符分割，按标题→段落→句子优先级
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=500,               # 固定 500 tokens
        chunk_overlap=100,            # 固定 100 tokens
        separators=ChunkConfig.SEPARATORS,
        length_function=token_counter,  # 使用 token 计数器而非字符数
        is_separator_regex=False,
    )


def token_counter(text: str) -> int:
    """
    Token 计数 — 使用 tiktoken 精确计数
    
    注意：
    - 中文一个汉字约等于 1~2 个 token（取决于编码）
    - 英文一个单词约等于 1~2 个 token
    - 使用 cl100k_base 编码（与 text-embedding-3 系列一致）
    """
    import tiktoken
    encoder = tiktoken.get_encoding("cl100k_base")
    return len(encoder.encode(text))
```

### 分块质量检查

```python
def validate_chunks(chunks: list[str]) -> list[str]:
    """
    验证分块质量 — 处理完必须调用
    
    检查项：
    1. 每个 chunk 在 500~800 token 范围内
    2. 相邻 chunk 之间有内容重叠
    3. 没有空 chunk
    """
    validated = []
    for i, chunk in enumerate(chunks):
        token_count = token_counter(chunk)
        
        # 空 chunk 过滤
        if token_count == 0:
            logger.warning(f"发现空 chunk，已跳过: index={i}")
            continue
        
        # 过长 chunk 告警
        if token_count > ChunkConfig.CHUNK_SIZE_MAX:
            logger.warning(f"Chunk 过长 ({token_count} tokens)，建议检查: index={i}")
        
        validated.append(chunk)
    
    logger.info(f"分块验证完成: {len(chunks)} → {len(validated)} (过滤 {len(chunks) - len(validated)} 个)")
    return validated
```

---

## 二、检索策略 — 硬性标准

### 混合检索必须开启（Hybrid Search）

```python
class HybridRetriever:
    """
    混合检索器 — 项目中所有检索必须使用混合检索
    
    硬性标准：
    - 向量检索（Dense）和关键词检索（Sparse）必须同时开启
    - 融合算法使用 RRF（Reciprocal Rank Fusion）
    - Top-K 返回 50 条候选
    """
    
    # ⚠️ 以下参数为硬性标准
    TOP_K_CANDIDATE: int = 50        # 融合后候选数（固定 50）
    VECTOR_TOP_K: int = 50          # 向量检索召回数
    KEYWORD_TOP_K: int = 50         # 关键词检索召回数
    RRF_K: int = 60                 # RRF 融合参数
    
    def __init__(
        self,
        vector_store,      # 向量数据库
        bm25_index,        # BM25 关键词索引
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
    
    async def retrieve(self, query: str) -> list[Document]:
        """
        混合检索 — 必须同时执行向量检索和关键词检索
        
        返回:
            50 条候选文档（用于后续重排序）
        """
        # 第一步：双路并行检索（必须两路都执行）
        vector_results, keyword_results = await asyncio.gather(
            self._vector_retrieve(query, top_k=self.VECTOR_TOP_K),
            self._keyword_retrieve(query, top_k=self.KEYWORD_TOP_K),
        )
        
        # 第二步：RRF 融合
        fused = self._rrf_fusion(vector_results, keyword_results)
        
        # 第三步：取 Top-50 候选
        candidates = fused[:self.TOP_K_CANDIDATE]
        
        logger.info(
            f"混合检索完成: 向量={len(vector_results)}, 关键词={len(keyword_results)}, "
            f"融合后={len(fused)}, 候选={len(candidates)}"
        )
        
        return candidates
    
    def _rrf_fusion(
        self,
        ranked_a: list[Document],
        ranked_b: list[Document],
    ) -> list[Document]:
        """
        RRF 融合算法
        
        score = Σ 1 / (k + rank_i)
        其中 k = 60
        """
        scores: dict[str, float] = {}
        
        for rank, doc in enumerate(ranked_a):
            scores[doc.id] = scores.get(doc.id, 0) + 1.0 / (self.RRF_K + rank + 1)
        
        for rank, doc in enumerate(ranked_b):
            scores[doc.id] = scores.get(doc.id, 0) + 1.0 / (self.RRF_K + rank + 1)
        
        # 按融合分数降序排列
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # 还原 Document 对象
        id_to_doc = {doc.id: doc for doc in ranked_a + ranked_b}
        return [id_to_doc[doc_id] for doc_id, _ in sorted_ids if doc_id in id_to_doc]
```

### 禁用选项

```python
# ❌ 禁止：纯向量检索（不开启关键词检索）
# ❌ 禁止：纯关键词检索（不开启向量检索）
# ❌ 禁止：跳过 RRF 融合直接返回结果
# ❌ 禁止：融合后候选数不等于 50（除非文档总数不足 50）
```

---

## 三、重排序（Rerank）— 硬性标准

### Top-50 → Top-10（强制）

```python
class Reranker:
    """
    重排序器 — 必须对检索候选进行重排序
    
    硬性标准：
    - 输入：检索返回的 50 条候选
    - 输出：重排序后的 10 条结果
    - 方法：Cross-Encoder 模型（优先级高于 LLM 重排序）
    """
    
    # ⚠️ 以下参数为硬性标准
    CANDIDATE_COUNT: int = 50    # 输入候选数（检索阶段返回的）
    RESULT_COUNT: int = 10       # 输出结果数（重排序后返回的）
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        from FlagEmbedding import FlagReranker
        self.model = FlagReranker(model_name, use_fp16=True)
    
    async def rerank(
        self,
        query: str,
        candidates: list[Document],
    ) -> list[Document]:
        """
        重排序 — 从 50 条候选中精选 10 条
        
        Args:
            query: 用户查询
            candidates: 检索返回的 50 条候选文档
        
        Returns:
            重排序后的 10 条最相关文档
        
        Raises:
            ValueError: 如果输入候选数不等于 50
        """
        # ⚠️ 硬性校验
        if len(candidates) != self.CANDIDATE_COUNT:
            logger.warning(
                f"重排序输入候选数不符: 期望 {self.CANDIDATE_COUNT}, 实际 {len(candidates)}"
            )
        
        # 构建 query-document 对
        pairs = [[query, doc.content] for doc in candidates]
        
        # Cross-Encoder 打分
        scores = self.model.compute_score(pairs, normalize=True)
        
        # 按分数降序排列
        scored = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 返回 Top-10
        results = [doc for doc, score in scored[:self.RESULT_COUNT]]
        
        logger.info(
            f"重排序完成: {len(candidates)} → {len(results)}, "
            f"最高分={scored[0][1]:.4f}, 最低分={scored[self.RESULT_COUNT-1][1]:.4f}"
        )
        
        return results
```

### 多样性保障

```python
def ensure_diversity(
    documents: list[Document],
    similarity_threshold: float = 0.95,
) -> list[Document]:
    """
    多样性过滤 — 移除高度重复的文档
    
    如果两个文档的相似度 > 0.95，保留分数更高的那个
    """
    filtered = []
    for doc in documents:
        is_duplicate = False
        for kept in filtered:
            sim = cosine_similarity(doc.embedding, kept.embedding)
            if sim > similarity_threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            filtered.append(doc)
    
    if len(filtered) < len(documents):
        logger.info(f"多样性过滤: {len(documents)} → {len(filtered)} (移除 {len(documents) - len(filtered)} 条重复)")
    
    return filtered
```

---

## 四、引用来源 — 硬性标准

### 回答必须包含引用

```python
# ⚠️ 硬性规定：每个 RAG 回答必须标注引用来源

@dataclass
class Citation:
    """引用来源 — 必须返回"""
    index: int              # 引用编号 [1], [2], ...
    document_title: str     # 文档标题
    chunk_id: str           # 分块 ID
    content_snippet: str    # 引用的原文片段（前 200 字符）
    page_number: int | None # 页码（PDF 文档）
    relevance_score: float  # 相关性分数

@dataclass  
class RAGResponse:
    """RAG 响应 — 标准格式"""
    answer: str                    # LLM 生成的回答（含 [N] 引用标记）
    citations: list[Citation]      # ⚠️ 必须返回，不允许为空列表
    conversation_id: str
    token_usage: dict[str, int]
    processing_time_ms: float
```

### Prompt 中必须引用 Context

```python
# ⚠️ 以下是标准的 RAG Prompt 模板（硬性标准，不得偏离）

RAG_SYSTEM_PROMPT = """你是一个严谨的企业知识库助手。你必须严格遵守以下规则：

## 核心规则（违反即为错误）
1. **仅基于参考资料回答**：你的回答必须 100% 基于下方「参考资料」提供的信息
2. **必须标注引用**：每个事实声明后必须标注来源编号，格式为 [1]、[2]、[3] 等
3. **禁止编造**：如果参考资料中没有相关信息，你必须明确说"根据现有资料，无法回答这个问题"，**绝对不能猜测或编造**
4. **逐条引用**：回答中包含的每条信息，都必须能在参考资料中找到对应的原文

## 回答格式要求
- 使用 Markdown 格式组织回答
- 每个关键信息点后必须紧跟引用标记
- 在回答末尾列出「参考资料」章节，汇总所有引用

## 示例
用户问题：公司年假有多少天？
回答：根据公司考勤制度，员工每年享有 **5天** 年假，工作满1年后可申请 [1]。

参考资料
[1] 《员工手册》第三章第2节 — "员工入职满一年后，每年享有5天带薪年假"
"""

RAG_USER_PROMPT = """## 参考资料
{context}

## 用户问题
{question}

请基于以上参考资料回答问题。记住：
- 回答中必须包含引用标记 [N]
- 如果资料中没有相关信息，请明确说明无法回答"""
```

### 引用完整性校验

```python
async def validate_citations(
    answer: str,
    citations: list[Citation],
    context_docs: list[Document],
) -> tuple[bool, list[str]]:
    """
    引用完整性校验 — 回答生成后必须调用
    
    检查项：
    1. 回答中出现的引用编号在 citations 中都存在
    2. citations 中的内容确实来自 context_docs
    3. 引用的内容与声明确实相关
    
    Returns:
        (是否通过校验, 问题列表)
    """
    issues = []
    
    # 检查引用编号是否都存在
    import re
    cited_nums = set(int(n) for n in re.findall(r'\[(\d+)\]', answer))
    available_nums = set(c.index for c in citations)
    
    missing = cited_nums - available_nums
    if missing:
        issues.append(f"回答中引用了不存在的编号: {missing}")
    
    # 检查是否提到了无法回答的情况
    if "无法回答" in answer and len(citations) > 0:
        issues.append("声明'无法回答'但同时返回了引用，存在矛盾")
    
    # 如果没有引用，检查是否明确说了无法回答
    if len(citations) == 0 and "无法回答" not in answer:
        issues.append("回答有实质内容但没有标注任何引用来源")
    
    is_valid = len(issues) == 0
    if not is_valid:
        logger.warning(f"引用完整性校验不通过: {issues}")
    
    return is_valid, issues
```

---

## 五、RAG Pipeline 编排（强制流程）

```python
class RAGPipeline:
    """
    RAG 完整管线 — 项目中唯一的 RAG 入口
    
    硬性流程（不可跳过任何步骤）：
    Query → 查询改写 → 混合检索(Top-50) → 重排序(Top-10) → 上下文组装 → LLM生成 → 引用校验 → 返回
    """
    
    async def execute(self, query: RAGQuery) -> RAGResponse:
        """
        执行完整的 RAG 流程
        
        ⚠️ 每一步都是强制的，不可跳过
        """
        start_time = time.time()
        
        # Step 1: 查询改写（必须）
        rewritten_query = await self._rewrite_query(query)
        logger.info(f"查询改写: '{query.question}' → '{rewritten_query}'")
        
        # Step 2: 混合检索 — Top-50（必须，两路检索）
        candidates = await self.hybrid_retriever.retrieve(rewritten_query)
        assert len(candidates) <= 50, f"检索候选数 {len(candidates)} 超过上限 50"
        
        # Step 3: 重排序 — Top-10（必须）
        top_docs = await self.reranker.rerank(query.question, candidates)
        assert len(top_docs) <= 10, f"重排序结果 {len(top_docs)} 超过上限 10"
        
        # Step 4: 多样性过滤（必须）
        top_docs = ensure_diversity(top_docs)
        
        # Step 5: 上下文组装（必须）
        context = self._assemble_context(top_docs)
        
        # Step 6: LLM 生成（必须 — 使用标准 RAG Prompt）
        answer = await self.llm_service.generate(
            system_prompt=RAG_SYSTEM_PROMPT,
            user_prompt=RAG_USER_PROMPT.format(
                context=context,
                question=query.question,
            ),
        )
        
        # Step 7: 引用提取与校验（必须）
        citations = self._extract_citations(answer, top_docs)
        is_valid, issues = await validate_citations(answer, citations, top_docs)
        
        if not is_valid:
            logger.error(f"引用校验失败: {issues}")
            # 触发重新生成或返回错误
            raise CitationValidationException(str(issues))
        
        # Step 8: 组装响应
        processing_time = (time.time() - start_time) * 1000
        logger.info(f"RAG 流程完成: 耗时 {processing_time:.0f}ms")
        
        return RAGResponse(
            answer=answer,
            citations=citations,
            conversation_id=query.conversation_id or str(uuid.uuid4()),
            token_usage=self.llm_service.last_usage,
            processing_time_ms=processing_time,
        )
```

---

## 六、Iron Law（铁律检查清单）

生成或修改任何 RAG 相关代码时，**必须逐条核对**：

### 分块
- [ ] chunk_size 是否在 500~800 范围内？
- [ ] chunk_overlap 是否为 100？
- [ ] 是否使用了递归字符分割器？
- [ ] 分块结果是否经过了 validate_chunks 校验？

### 检索
- [ ] 是否同时开启了向量检索和关键词检索？
- [ ] 是否使用了 RRF 融合算法（k=60）？
- [ ] 融合后候选数是否为 50 条？
- [ ] 是否禁止了纯向量/纯关键词检索？

### 重排序
- [ ] 是否对 50 条候选进行了重排序？
- [ ] 重排序后返回数是否为 10 条？
- [ ] 是否使用了 Cross-Encoder 模型？
- [ ] 是否执行了多样性过滤？

### 引用
- [ ] Prompt 是否包含了"必须引用 Context"的严格要求？
- [ ] 响应中是否包含了 citations 列表？
- [ ] citations 列表是否不为空（除非确实无法回答）？
- [ ] 是否对引用完整性进行了校验？

### 整体
- [ ] RAG Pipeline 是否按 7 个步骤严格顺序执行？
- [ ] 是否有跳过任何步骤的情况？
- [ ] 日志是否记录了每步的关键指标？
