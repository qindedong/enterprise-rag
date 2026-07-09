# 检索优化技能 (Retrieval)

## 描述
当用户需要优化 RAG 系统的检索效果时，提供全面的检索策略优化指导。

## 触发条件
- 用户提到"检索优化"、"召回率"、"搜索不准"、"检索效果"
- 用户需要提升文档检索的相关性
- 用户询问混合检索、重排序等策略

## 检索优化策略

### 1. 查询端优化

#### 查询改写（Query Rewriting）
```python
# 使用 LLM 改写用户查询
REWRITE_PROMPT = """
你是一个查询改写助手。请将以下用户问题改写为更适合检索的查询语句：
1. 补充隐含的上下文信息
2. 将口语化表达转为正式表达
3. 提取关键实体和概念
4. 生成 2-3 个不同角度的查询变体

原始问题：{question}
对话历史：{history}
"""
```

#### HyDE（假设文档嵌入）
```python
# 先生成假设答案，再用假设答案的向量去检索
HYDE_PROMPT = """
请根据以下问题，生成一个假设的答案段落。
这个段落不需要完全正确，只需要包含可能的关键信息和术语。

问题：{question}
假设答案：
"""
```

#### 多角度查询
- 对同一问题生成多个查询角度
- 每个角度独立检索
- 合并去重所有检索结果

### 2. 索引端优化

#### 分块策略优化
| 场景 | 推荐分块大小 | 重叠比例 | 备注 |
|------|-------------|---------|------|
| FAQ 问答 | 128-256 tokens | 10% | 短文本，精确匹配 |
| 技术文档 | 512-1024 tokens | 15% | 中等长度，保留完整性 |
| 长篇文章 | 1024-2048 tokens | 20% | 长文，保证语义连贯 |
| 法律法规 | 按条款分块 | - | 保留条款引用信息 |

#### 元数据增强
```python
# 为每个 chunk 存储丰富的元数据
chunk_metadata = {
    "document_id": "doc_001",
    "document_title": "员工手册 v2.0",
    "chunk_index": 5,
    "total_chunks": 20,
    "section_title": "第三章 考勤制度",
    "page_number": 12,
    "document_type": "policy",
    "created_date": "2024-01-15",
    "tags": ["考勤", "请假", "工时"],
    "entities": ["人力资源部", "弹性工作制"],
    "summary": "本章规定了员工的考勤要求和请假流程"
}
```

#### 父子文档索引
- **父文档**：完整的段落或章节
- **子文档**：细粒度的句子或小段
- 检索时用子文档匹配，返回父文档作为上下文

### 3. 混合检索实现

```python
class HybridRetriever:
    """混合检索器：融合向量检索和关键词检索"""
    
    def __init__(
        self,
        vector_store,       # 向量数据库
        bm25_index,         # BM25 索引
        vector_weight=0.7,  # 向量检索权重
        keyword_weight=0.3, # 关键词检索权重
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        fusion_method: str = "rrf"  # "rrf" | "weighted" | "hybrid"
    ) -> list[Document]:
        # 并行执行两路检索
        vector_results = await self._vector_search(query, top_k * 2)
        keyword_results = await self._keyword_search(query, top_k * 2)
        
        if fusion_method == "rrf":
            return self._rrf_fusion(vector_results, keyword_results, top_k)
        elif fusion_method == "weighted":
            return self._weighted_fusion(vector_results, keyword_results, top_k)
        else:
            return self._hybrid_merge(vector_results, keyword_results, top_k)
    
    def _rrf_fusion(
        self,
        ranked_a: list[Document],
        ranked_b: list[Document],
        top_k: int,
        k: int = 60
    ) -> list[Document]:
        """RRF 融合算法"""
        scores = {}
        for rank, doc in enumerate(ranked_a):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank + 1)
        for rank, doc in enumerate(ranked_b):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (k + rank + 1)
        
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc_id, _ in sorted_docs[:top_k]]
```

### 4. 重排序优化

```python
class Reranker:
    """重排序器"""
    
    async def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
        method: str = "cross_encoder"
    ) -> list[Document]:
        if method == "cross_encoder":
            return await self._cross_encoder_rerank(query, documents, top_k)
        elif method == "llm":
            return await self._llm_rerank(query, documents, top_k)
        elif method == "mmr":
            return self._mmr_rerank(query, documents, top_k)
    
    def _mmr_rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int,
        lambda_param: float = 0.7
    ) -> list[Document]:
        """MMR（最大边际相关性）重排序，兼顾相关性和多样性"""
        selected = []
        remaining = list(documents)
        
        while len(selected) < top_k and remaining:
            scores = []
            for doc in remaining:
                relevance = doc.score  # 与查询的相关性
                if selected:
                    # 与已选文档的最大相似度（惩罚冗余）
                    redundancy = max(
                        cosine_similarity(doc.embedding, s.embedding)
                        for s in selected
                    )
                else:
                    redundancy = 0
                mmr_score = lambda_param * relevance - (1 - lambda_param) * redundancy
                scores.append(mmr_score)
            
            best_idx = scores.index(max(scores))
            selected.append(remaining.pop(best_idx))
        
        return selected
```

### 5. 检索效果评估

```python
def evaluate_retrieval(
    queries: list[str],
    ground_truth: dict[str, list[str]],  # query -> relevant_doc_ids
    retriever,
    k_values: list[int] = [1, 3, 5, 10]
) -> dict:
    """评估检索效果"""
    metrics = {}
    
    for k in k_values:
        recall_sum = 0
        mrr_sum = 0
        
        for query in queries:
            results = retriever.retrieve(query, top_k=k)
            result_ids = [doc.id for doc in results]
            relevant_ids = ground_truth.get(query, [])
            
            # Recall@K
            hits = len(set(result_ids) & set(relevant_ids))
            recall = hits / len(relevant_ids) if relevant_ids else 0
            recall_sum += recall
            
            # MRR
            for rank, doc_id in enumerate(result_ids):
                if doc_id in relevant_ids:
                    mrr_sum += 1 / (rank + 1)
                    break
        
        metrics[f"Recall@{k}"] = recall_sum / len(queries)
        metrics[f"MRR@{k}"] = mrr_sum / len(queries)
    
    return metrics
```
