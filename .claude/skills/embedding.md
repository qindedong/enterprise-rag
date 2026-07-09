# Embedding 策略技能 (Embedding)

## 描述
当用户需要选择、配置或优化 Embedding 模型时，提供专业的 Embedding 策略指导。

## 触发条件
- 用户提到"Embedding"、"向量化"、"嵌入模型"、"文本向量"
- 用户需要选择或切换 Embedding 模型
- 用户询问如何提升向量检索效果

## Embedding 模型选型

### 主流模型对比

| 模型 | 维度 | 最大长度 | 中文效果 | 成本 | 适用场景 |
|------|------|---------|---------|------|---------|
| text-embedding-3-large (OpenAI) | 3072/256/1024 | 8191 | ★★★★ | 中 | 通用、高精度需求 |
| text-embedding-3-small (OpenAI) | 1536/512 | 8191 | ★★★☆ | 低 | 通用、成本敏感 |
| bge-large-zh-v1.5 (BAAI) | 1024 | 512 | ★★★★★ | 免费 | 中文专用、本地部署 |
| bge-m3 (BAAI) | 1024 | 8192 | ★★★★★ | 免费 | 多语言、长文本 |
| m3e-large (Moka-AI) | 1024 | 512 | ★★★★☆ | 免费 | 中文、本地部署 |
| GTE-Qwen2-7B-instruct | 3584 | 32768 | ★★★★★ | 免费 | 高精度、长文本 |
| jina-embeddings-v3 | 1024 | 8192 | ★★★★ | 中 | 多语言、任务特定 |
| Cohere Embed v3 | 1024 | 512 | ★★★★ | 中 | 多语言、企业级 |

### 选型决策树

```
是否需要本地部署？
├── 是 → 是否有 GPU？
│   ├── 是 → GTE-Qwen2-7B（最高精度）或 bge-m3（平衡）
│   └── 否 → bge-large-zh-v1.5（CPU 可运行）
└── 否 → 预算充足？
    ├── 是 → text-embedding-3-large（高精度 + 维度可调）
    └── 否 → text-embedding-3-small（性价比最优）
```

## Embedding 使用最佳实践

### 1. 文本预处理
```python
def preprocess_for_embedding(text: str, model_type: str = "bge") -> str:
    """Embedding 前的文本预处理"""
    # BGE 系列模型推荐添加 instruction 前缀
    if model_type == "bge":
        text = f"为这个句子生成表示以用于检索相关文章：{text}"
    
    # 通用预处理
    text = text.replace("\n", " ")      # 去除换行
    text = text.replace("\r", " ")      # 去除回车
    text = " ".join(text.split())       # 合并多余空白
    
    # 截断过长的文本
    if len(text) > 8000:
        text = text[:8000]
    
    return text
```

### 2. 批量处理策略
```python
async def batch_embed(
    texts: list[str],
    model,
    batch_size: int = 32,
    max_retries: int = 3
) -> list[list[float]]:
    """批量向量化处理"""
    embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        for attempt in range(max_retries):
            try:
                batch_embeddings = await model.aembed_documents(batch)
                embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # 指数退避
    
    return embeddings
```

### 3. 向量维度选择
```python
# OpenAI text-embedding-3 支持维度缩减
# 维度越小，存储和检索越快，但精度会下降

DIMENSION_TRADEOFF = {
    3072: "最高精度，适合高精度要求场景",
    1536: "精度 > 99%，存储减半，推荐平衡选择",
    1024: "精度 > 98%，大幅降低存储成本",
    512:  "精度 > 95%，适合大规模数据、速度优先",
    256:  "精度 > 90%，适合粗略召回、第一路检索",
}
```

### 4. 向量归一化
```python
import numpy as np

def normalize_embedding(embedding: list[float]) -> list[float]:
    """L2 归一化，用于余弦相似度计算"""
    vec = np.array(embedding)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()
```

### 5. 相似度计算
```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度（假定向量已归一化则为点积）"""
    return np.dot(a, b)

def euclidean_distance(a: list[float], b: list[float]) -> float:
    """欧氏距离"""
    return np.linalg.norm(np.array(a) - np.array(b))
```

### 6. 模型切换时的迁移策略
```python
class EmbeddingMigration:
    """Embedding 模型切换迁移"""
    
    async def migrate(
        self,
        old_model: str,
        new_model: str,
        documents: list[Document]
    ) -> None:
        """从旧模型迁移到新模型"""
        # 方案1：全量重新向量化（推荐）
        texts = [doc.content for doc in documents]
        new_embeddings = await batch_embed(texts, new_model)
        
        # 方案2：双写过渡期（零停机）
        # 同时用新旧模型向量化，逐步切换
        
        # 方案3：训练映射矩阵（维度不同时）
        # 从 old_dim → new_dim 学习线性映射
```

### 7. 评估 Embedding 效果
```python
def evaluate_embedding_model(
    model,
    test_pairs: list[tuple[str, str, float]],  # (text1, text2, human_score)
) -> dict:
    """评估 Embedding 模型在语义相似度任务上的表现"""
    predictions = []
    labels = []
    
    for text1, text2, human_score in test_pairs:
        emb1 = model.encode(text1)
        emb2 = model.encode(text2)
        sim = cosine_similarity(emb1, emb2)
        predictions.append(sim)
        labels.append(human_score)
    
    # Spearman 相关系数
    from scipy.stats import spearmanr
    correlation, p_value = spearmanr(predictions, labels)
    
    return {
        "spearman_correlation": correlation,
        "p_value": p_value,
        "num_samples": len(test_pairs),
    }
```
