# PDF 复杂场景处理方案

## 当前能力与差距

当前 `pdf_parser.py` 仅用 `page.get_text()` 做纯文本提取，不感知页面布局。面对复杂 PDF 时存在以下问题：

| 场景 | 当前问题 | 影响 |
|------|----------|------|
| **目录** | 未调用 `doc.get_toc()` | 丢失文档结构，检索无法按章节过滤 |
| **页眉页脚** | 无过滤机制 | 每页重复的公司名/页码混入正文，干扰分块 |
| **多栏排版** | 文字按提取顺序拼接 | 左栏末句与右栏首句连成一句话，语义断裂 |
| **表格** | 变成连续纯文本 | 行列关系丢失，LLM 无法理解表格数据 |
| **流程图/图片** | 完全忽略 | 重要信息丢失 |
| **合同条款** | 无专用分块策略 | "第X条" 被从中间切断，法律效力上下文断裂 |
| **扫描件** | 提取为空，仅记录 warning | 完全无法使用 |
| **加密 PDF** | 已检测并抛异常 | ✅ 当前正常 |

## 解决方案（分优先级落地）

### P0 - 立即可做（影响最大，代码量小）

1. **启用 PyMuPDF 块级提取** (`page.get_text("blocks")`)
   - 利用 bbox 坐标过滤页眉页脚
   - 按阅读顺序重组多栏文本

2. **提取目录结构** (`doc.get_toc()`)
   - 作为 chunk 元数据写入 Qdrant，支持按章节检索

3. **扫描件 OCR 降级**
   - 检测无文字层/图片型 PDF → 自动调用 OCR
   - 推荐 `pytesseract` + Tesseract-OCR 引擎（轻量方案）

### P1 - 近期优化（1~2 天开发量）

4. **表格结构化提取**
   - PyMuPDF 1.23+ 的 `page.find_tables()` 提取为 Markdown 格式
   - Markdown 表格可被 LLM 直接理解

5. **合同文档专用分块策略**
   - TextSplitter 增加合同分隔符："第X条"、"第X章"、"甲方/乙方" 等
   - 避免条款在 chunk 边界处被截断

### P2 - 高级能力（需要外部服务）

6. **图片/流程图理解**
   - 提取 PDF 中的图片 → 调用多模态模型（GPT-4o / Claude 3）生成文字描述
   - 描述文本作为 chunk 写入向量库

7. **版面分析（杂志/研报级排版）**
   - 引入 `pdfplumber` 或 `Unstructured` 做更精细的版面分析
   - 识别标题层级、正文区块、侧边栏、注释等

## 关键依赖

```bash
# 基础依赖（已有）
pip install PyMuPDF

# OCR 支持
pip install pytesseract Pillow
# 同时需要安装 Tesseract-OCR 引擎：
#   - Windows: https://github.com/UB-Mannheim/tesseract/wiki
#   - macOS: brew install tesseract tesseract-lang  (chi_sim 中文包)
#   - Ubuntu: apt-get install tesseract-ocr tesseract-ocr-chi-sim

# 表格处理（可选，PyMuPDF 1.23+ 已内置 find_tables）
pip install pandas  # 用于 to_markdown()
```

## 配置项建议（加入 .env）

```bash
# PDF 解析配置
PDF_OCR_ENABLED=true
PDF_OCR_LANG=chi_sim+eng          # Tesseract 语言包
PDF_HEADER_RATIO=0.08             # 页眉占页面高度比例
PDF_FOOTER_RATIO=0.08             # 页脚占页面高度比例
PDF_SCANNED_THRESHOLD=0.03        # 文字覆盖面积低于3%视为扫描件
```

## 核心设计

### 1. 解析流程图

```
PDF 文件
  │
  ▼
fitz.open()
  │
  ├──► get_toc() ────────► 目录元数据
  │
  ▼
逐页处理
  │
  ├──► 扫描件检测？ ──Yes──► OCR 提取文字
  │                    No
  │                     │
  ▼                     ▼
get_text("blocks")   page.find_tables()
  │                     │
  ├──► 页眉页脚过滤     ├──► 表格 → Markdown
  │   (bbox 坐标判断)   │
  ▼                     ▼
阅读顺序重组         合并结果
  │   (多栏排序)       │
  ▼                     ▼
    纯文本 + 表格 Markdown + 目录
              │
              ▼
        TextSplitter 分块
              │
              ▼
        写入 Qdrant（含 page_number、section_title 等元数据）
```

### 2. 多栏排版阅读顺序重组

```
原始提取顺序（PyMuPDF默认）        重组后阅读顺序
┌─────────┬─────────┐            ┌─────────┬─────────┐
│ 块1     │ 块2     │            │ 块1     │ 块3     │
│ 块3     │ 块4     │     →      │ 块5     │ 块7     │
│ 块5     │ 块6     │            │         │         │
│ 块7     │ 块8     │            │ 块2     │ 块4     │
└─────────┴─────────┘            │ 块6     │ 块8     │
                                 └─────────┴─────────┘
```

算法：
1. 按 y 坐标（行）分组，同一水平线内的块按 x 坐标（从左到右）排序
2. 先输出左栏整行，再输出右栏整行

### 3. 页眉页脚过滤规则

| 区域 | 判断条件 | 处理方式 |
|------|----------|----------|
| 页眉 | y < 页面高度×8% 且 文本长度 < 150 | 丢弃 |
| 页脚 | y > 页面高度×92% 且 匹配页码模式 | 丢弃 |
| 页码模式 | `^\d+$`、`第X页`、`X / Y` 等正则 | 丢弃 |

### 4. 合同专用分块

在 `TextSplitter` 分隔符列表前插入：

```python
CONTRACT_SEPARATORS = [
    r"\n第[一二三四五六七八九十百零\\d]+条",      # 第X条
    r"\n第[一二三四五六七八九十百零\\d]+章",      # 第X章  
    r"\n第[一二三四五六七八九十百零\\d]+节",      # 第X节
    r"\n[甲乙丙丁]方[：:]",                        # 甲方/乙方
    r"\n\\d+\\.\\s",                             # 1. 2. 3.
    # ... 原有分隔符
]
```

## 文件变更清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `app/parsers/pdf_layout.py` | 新增 | 布局分析：页眉页脚过滤、多栏检测、阅读顺序重组、扫描件检测 |
| `app/parsers/pdf_parser.py` | 重写 | 集成布局分析、目录提取、表格提取、OCR |
| `app/utils/text_splitter.py` | 修改 | 增加合同专用分隔符（可选模式） |
| `app/core/config.py` | 修改 | 新增 PDF 相关配置项 |
| `tests/unit/test_pdf_parser.py` | 新增 | 覆盖复杂场景的单元测试 |
