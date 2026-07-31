# PDF 处理四层架构设计

> **文档版本**: v1.0
> **创建日期**: 2026-07-31
> **关联文档**: [pdf_parser_roadmap.md](./pdf_parser_roadmap.md)（本文档取代其中的分期规划） | [ARCHITECTURE.md](./ARCHITECTURE.md) | [DATABASE.md](./DATABASE.md)
> **现状**: 当前 `pdf_parser.py` 仅 67 行，`page.get_text()` 纯文本抽取 → `RecursiveCharacterTextSplitter` 按 500 token 硬切，无页码、无结构、无表格/图片感知

---

## 总览

```
┌─────────────────────────────────────────────────────────────┐
│ L4  Agent 工具层   search_pdf / read_page / extract_table / │
│                    analyze_chart / quote_source             │
├─────────────────────────────────────────────────────────────┤
│ L3  切片与索引层   语义切片 + 结构化表格 + 图表摘要 +         │
│                    全量 metadata + Contextual Retrieval     │
├─────────────────────────────────────────────────────────────┤
│ L2  结构还原层     页码 / 标题层级 / 章节 / 段落 / 表格 /     │
│                    图注 / 脚注 / 页眉页脚                   │
├─────────────────────────────────────────────────────────────┤
│ L1  解析层         PDF 分类（原生 / 扫描 / 图文混排）→       │
│                    文本抽取 / OCR / 视觉理解                 │
└─────────────────────────────────────────────────────────────┘
          ↓ 贯穿四层的两条生产级要求 ↓
   可追溯引用（页码+章节+原文片段）   分层评测（不仅看最终答案）
```

核心原则：**PDF 不是纯文本，而是带坐标的结构化版面**。每一层的输出都是下一层的结构化输入，任何一层都不把上游信息压扁成字符串。

---

## L1 解析层：先分类，再分流

### 1.1 PDF 类型判定

`app/parsers/pdf/classifier.py`（新增）— 对每页分类，而不是对整个文档一刀切：

| 类型 | 判定信号（PyMuPDF） | 处理策略 |
|------|---------------------|----------|
| **原生文本页** | `page.get_text()` 字符数 > 阈值（~50）且覆盖率正常 | 块级抽取 `page.get_text("blocks")` |
| **扫描页** | 文字层为空/极薄 + `page.get_images()` 有整页大图 | 走 OCR |
| **图文混排页** | 有文字层，但含图片/矢量图区域 | 文字走块级抽取，图像区域单独裁剪送视觉理解 |

判定输出 `PageProfile { page_no, page_type, text_coverage, image_regions, has_vector_drawing }`，逐页驱动后续策略——合同可能全文原生，财报往往封面扫描+正文原生+图表页混排。

### 1.2 三条抽取路径

1. **原生路径**：`page.get_text("blocks")` 带 bbox 坐标抽取，保留块顺序与位置（供 L2 做页眉页脚过滤和多栏重组）
2. **OCR 路径**：页面渲染为 300 DPI 图像 → OCR 引擎
   - 首选 PaddleOCR（中文准确率高、可离线）；备选 RapidOCR（纯 ONNX，镜像体积小）
   - OCR 结果同样带 bbox，与原生路径输出同构，下游无感知
3. **视觉理解路径**：流程图、截图、复杂表格（合并单元格、无线表）不能只抽文字
   - 图像区域裁剪 → 多模态模型（GPT-4o / Qwen-VL / Claude）生成结构化描述
   - 复杂表格 → 视觉模型直接输出 Markdown/JSON 表格，比纯文本抽取的行列关系可靠得多

### 1.3 输出契约

```python
# L1 输出：每页一个 PageContent，块级粒度，全部带坐标
PageContent {
    page_no: int
    page_type: "native" | "scanned" | "mixed"
    blocks: [Block { kind: "text"|"image"|"table_candidate",
                     bbox: (x0,y0,x1,y1), text: str, image_ref: str|None }]
    ocr_confidence: float | None   # 仅 OCR 页
}
```

---

## L2 结构还原层：把 PDF 还原成文档树

输入 L1 的 PageContent 流，输出一棵 `DocumentStructure` 树。**这一层决定引用能不能精确到"第几章第几条第几页"。**

### 2.1 要还原的结构

| 结构 | 还原手段 | 价值场景 |
|------|----------|----------|
| **页码** | 每页天然带 `page_no`，贯穿到最终引用 | 所有引用定位 |
| **标题层级** | 优先 `doc.get_toc()`；无书签时按字号/粗体/编号模式（"第X章"、"一、"、"1.1"）启发式识别 | 章节导航、按章检索 |
| **章节/条款** | 合同类：正则 `第[一二三\d]+章` / `第\d+条` / `\d+\.\d+` 锚定条款边界 | 合同切片知道"第几章第几条" |
| **段落** | 块合并：同栏相邻同字号块按阅读顺序合并 | 语义完整性 |
| **表格** | 原生表格用 `page.find_tables()`；复杂表格已在 L1 视觉路径结构化 | 财报数字溯源到"哪张表哪个指标哪年" |
| **图片说明** | 图注模式匹配（"图 3-1"、"Figure 2"）+ 与图片块的空间邻近关联 | 图表引用 |
| **脚注** | 页底小字号块 + 上标编号关联 | 财报附注不可丢 |
| **页眉页脚** | 跨页同位置同文本的块（y 坐标 top<8% 或 bottom>92% 且重复 ≥3 页）→ 剔除 | 去噪 |
| **多栏** | 按 bbox x 坐标聚类分栏，栏内按 y 排序，栏间按 x 排序 | 阅读顺序正确 |

### 2.2 输出契约

```python
DocumentStructure {
    doc_id: UUID
    toc: [TocNode { level, title, page_no }]          # 文档目录树
    nodes: [StructNode]                                # 有序结构节点流
}

StructNode {
    kind: "heading"|"paragraph"|"table"|"figure"|"footnote"|"clause"
    level: int                    # 标题层级，其余为 0
    text: str                     # 段落文本 / 图注 / 脚注
    page_start: int; page_end: int
    section_path: list[str]       # 章节路径，如 ["第三章", "3.2 违约责任"]
    clause_no: str | None         # 合同条款号，如 "第12条"
    table: StructuredTable | None # 结构化表格（行列 + 表头 + 单位）
    figure: FigureRef | None      # 图片引用 + L1 生成的描述
}

StructuredTable {
    table_id: str                 # "表 2-1" 或序号
    caption: str | None
    headers: list[str]            # 列头（含年份/指标名）
    rows: list[list[str]]
    page_no: int
}
```

**财报示例**：数字 "2023 年营收 152.3 亿" 还原后挂在 `StructuredTable{ caption:"合并利润表", headers:["指标","2022","2023"], ... }` 上，切片时行列语义完整保留。

---

## L3 切片与索引层：按语义结构切，带全量 metadata

### 3.1 语义切片规则（取代 500 token 硬切）

| 节点类型 | 切片策略 |
|----------|----------|
| 标题下段落组 | 同一标题下的连续段落合并为一个 chunk（超 800 token 再在段落边界二次切，绝不跨标题） |
| 表格 | **单独成 chunk**：转结构化文本（Markdown 表 + 逐行"指标:值(年份)"展开），长表按行分组但每组重复表头 |
| 图片/图表 | 不成文本 chunk，而是生成**摘要 chunk**：图注 + L1 视觉描述 + 所在章节 |
| 条款（合同） | 以"第 X 条"为边界，一条一 chunk，条款号写入 metadata |
| 脚注 | 附入所属段落 chunk，不单独切 |

### 3.2 Chunk metadata 全量 schema

现有 `document_chunks` 表已有 `page_number` / `section_title` / `metadata` JSON 列（建表预留，一直未用），无需迁移即可落地：

```json
{
  "doc_id": "uuid",
  "chunk_index": 12,
  "page_start": 15, "page_end": 16,
  "section_path": ["第三章 双方责任", "3.2 乙方义务"],
  "clause_no": "第12条",
  "kind": "paragraph | table | figure_summary | clause",
  "table_id": "表 3-1",
  "figure_desc": "流程图：审批流从部门经理到总监两级",
  "doc_version": "2024 年报",
  "effective_date": "2024-01-01",
  "source_page_label": "第 15 页"
}
```

Qdrant payload 同步扩展（当前只有 7 个字段），`page_start` / `section_path` / `kind` 建 payload 索引，支持"只看表格"、"限定章节"过滤检索。

### 3.3 Contextual Retrieval（Anthropic 思路）

每个 chunk 入库前，由 LLM 生成 1-2 句**上下文说明**并前置拼接到 chunk 文本：

```
[本文档为《XX 公司 2024 年员工考勤制度》第三章"考勤规则"，本条款规定迟到认定与处罚标准。]
一、迟到：每月迟到累计 3 次以内，每次扣款 50 元……
```

- 向量化的是"上下文 + 原文"，BM25 索引同步生效，歧义片段（"第三条"、"如上所述"）召回率显著提升
- 生成上下文是文档入库时的一次性成本，查询零额外延迟
- 存入 `metadata.context_prefix`，回答展示时可剥离

### 3.4 双写一致性

沿用现有架构：`document_chunks`（PG，BM25 + 结构化过滤）与 Qdrant 点 ID 一一对应，删除文档时两边同步（US-10 已验证的机制直接复用）。

---

## L4 Agent 工具层：PDF 能力工具化

**不把整个 PDF 塞进上下文**，而是把 PDF 能力封装成一组工具，Agent 按需调用、规划阅读顺序。

### 4.1 工具定义 `app/agent/tools/`（新增模块）

| 工具 | 签名 | 用途 |
|------|------|------|
| `search_pdf` | `(query, kb_id, filters={kind, section, pages}) → [chunk+meta]` | 语义检索相关片段（复用现有 hybrid pipeline + metadata 过滤） |
| `read_page` | `(doc_id, page_no) → PageContent` | 读取指定页完整内容（精读） |
| `extract_table` | `(doc_id, table_id 或 page_no) → StructuredTable` | 抽取结构化表格，返回行列 JSON 而非文本 |
| `analyze_chart` | `(doc_id, figure_ref) → 分析文本` | 对图表调视觉模型做深度分析（趋势、对比、异常点） |
| `quote_source` | `(chunk_id) → {page, section, snippet}` | 返回可展示引用：页码 + 章节 + 原文片段 |

### 4.2 路由策略

| 用户意图 | 路由 |
|----------|------|
| 简单事实（"迟到扣多少钱"） | `search_pdf` 向量/hybrid 召回 → 直接生成（现有路径，零改动） |
| 复杂对比（"对比第三章和第五章的违约责任"） | Agent 规划：`search_pdf` 多轮检索多个章节 → `read_page` 精读 → 综合 |
| 表格/图表问题（"2023 年各项费用占比"） | `extract_table` / `analyze_chart` 专用工具，不让模型猜文本化表格 |
| 溯源请求（"这句话出自哪里"） | `quote_source` 返回精确引用 |

实现方式：在现有 `RAGService` 之上加薄 Agent 编排层（LLM function-calling），简单问题直通现有管线不增加延迟；只有复杂意图才进入多步工具循环，步数上限（如 6 步）兜底。

---

## 生产级要求（贯穿四层）

### A. 可追溯引用

- 回答中每条引用携带：**页码 + 章节路径 + 原文片段**（现有 `citations` 只有 chunk 内容，需扩展 `page_start` / `section_path`）
- 前端引用卡片点击可跳到文档对应页（`read_page` 支撑）
- 现有 `QualityChecker` 的引用越界检测直接复用，防止模型编造不存在的引用

### B. 分层评测（不只看最终答案）

扩展 `eval/run_eval.py`，按层设指标：

| 层 | 指标 | 方法 |
|----|------|------|
| L1 | OCR 字符错误率（CER）、页面分类准确率 | 扫描样本集人工校对 |
| L2 | 标题层级还原 F1、表格结构正确率（行列对齐） | 标注文档对比 |
| L3 | 检索片段命中率、页码精准率（引用页码 ∈ 正确页集合） | 现有标注数据集扩展页码标注 |
| L4 | 图表理解正确率、工具调用合理性 | 图表问答测试集 |
| 端到端 | 答案正确率 + 引用完整率 | 现有 eval 流程 |

---

## 落地分期

| 阶段 | 内容 | 依赖变化 | 验收 |
|------|------|----------|------|
| **P0** ✅（2026-07-31 完成，258 单测全过）| L1 块级抽取 + 页面分类器；L2 页眉页脚过滤 + 多栏重组 + TOC 提取；L3 结构 metadata 入库（page/section/kind） | 无新依赖 | 合同 PDF 切片带"第几章第几条第几页" |
| **P1** ✅（2026-07-31 完成，267 单测全过）| L2 表格结构化（find_tables）+ 条款边界；L3 语义切片器取代硬切；引用带页码 | 无新依赖 | 财报表格 chunk 行列完整，引用可跳页 |
| **P2** | L1 OCR 路径；L3 Contextual Retrieval 上下文生成 | +PaddleOCR/RapidOCR（镜像 +~500MB） | 扫描件可检索，OCR CER 达标 |
| **P3** | L1 视觉理解路径；L4 Agent 工具层全套；分层评测集 | +多模态模型 API | 图表问题走 analyze_chart，复杂对比多步规划 |

**关键设计决策**：
1. OCR 与视觉理解放 P2/P3 —— 它们是镜像体积和 API 成本的主要来源，先把零成本的结构收益（P0/P1）拿到手
2. 本地 Embedding 路线不变（bge-small-zh），切片策略变化需要**重建索引**（提供 reindex 脚本，现有 `reprocess` 端点可复用）
3. L4 不引入重型 Agent 框架，在现有 RAGService 上加 function-calling 薄层，简单问题路径零改动

---

## 模块布局（目标态）

```
backend/app/
├── parsers/
│   ├── pdf/                      # 新增子包
│   │   ├── classifier.py         # L1 页面分类
│   │   ├── native_extractor.py   # L1 原生块级抽取
│   │   ├── ocr_extractor.py      # L1 OCR 路径 (P2)
│   │   ├── vision_extractor.py   # L1 视觉理解 (P3)
│   │   ├── structure.py          # L2 结构还原 → DocumentStructure
│   │   └── tables.py             # L2 表格结构化
│   └── pdf_parser.py             # 门面：编排 L1→L2，保持 BaseParser 接口
├── rag/
│   ├── semantic_chunker.py       # L3 语义切片器（取代 text_splitter 对 PDF 的硬切）
│   ├── contextual.py             # L3 Contextual Retrieval 上下文生成 (P2)
│   └── ...（现有检索管线不变）
└── agent/
    ├── tools/                    # L4 五个 PDF 工具 (P3)
    └── planner.py                # L4 意图路由与多步规划 (P3)
```
