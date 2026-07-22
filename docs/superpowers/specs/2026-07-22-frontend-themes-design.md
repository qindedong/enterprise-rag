# 前端主题系统与界面美化设计

日期：2026-07-22
状态：已确认（用户逐节审批通过）

## 1. 背景与目标

现有前端（React 19 + Tailwind CSS 4 + Vite）样式是 Tailwind 默认风格，硬编码了大量 `bg-gray-50`、`blue-600` 这类具体色值，观感朴素。目标：

- 主方向：内部工具应有的**干净、专业**观感
- 同时提供**两套主题族**——简约（minimal）与杂志（editorial），每套都有**明/暗**两个模式，共四种组合
- 页面上提供**主题切换按钮**，可随时切换，选择持久化

## 2. 范围

全部五个页面：登录、注册、知识库列表、知识库详情、聊天页；以及共享组件（`MainLayout`、`Loading`、`Empty`、`ErrorState`、`Pagination`、`DocStatusBadge`）和全局样式（`index.css` 中的 body、markdown-body、滚动条、流式光标）。

不涉及后端，不新增任何运行时依赖。

## 3. 已确认的关键决策

| 决策点 | 结论 |
|---|---|
| 主题族 | minimal（默认）+ editorial |
| 明暗 | 每族各一明一暗，共四组合 |
| editorial 风格方向 | 编辑杂志风（纸底、墨框、衬线标题、朱红强调） |
| 技术方案 | CSS 变量令牌 + `<html>` data 属性切换，不引入组件库、不写双套样式表 |
| 字体 | 正文两族均用系统无衬线栈；editorial 标题用**系统**衬线栈（Georgia / Songti SC / SimSun），**不加载网络字体**（中文衬线网字体积以 MB 计，不划算） |
| 改造范围 | 全部页面与共享组件 |

## 4. 主题系统架构

### 4.1 语义令牌

在 `frontend/src/index.css` 定义 CSS 自定义属性：

- `--surface`：页面底色
- `--surface-raised`：卡片/浮层底色
- `--ink`：主文字色
- `--ink-muted`：次要文字色
- `--line`：主边框色
- `--line-soft`：弱分隔线/表格线色
- `--accent`：强调色
- `--accent-ink`：强调色上的文字色
- `--font-display`：标题字体栈
- `--font-body`：正文字体栈
- `--radius`：圆角
- `--shadow`：卡片投影

### 4.2 四套主题的挂载方式

`<html>` 元素上挂两个属性：`data-theme="minimal|editorial"` × `data-mode="light|dark"`。在 `index.css` 中用四个属性选择器分别给出变量值，默认（无属性时）等同 `minimal + light`。

通过 Tailwind 4 的 `@theme inline` 把变量映射为语义工具类（`bg-surface`、`bg-surface-raised`、`text-ink`、`text-ink-muted`、`border-line`、`border-line-soft`、`bg-accent`、`text-accent`、`font-display`、`font-body`、`rounded-theme`、`shadow-theme` 等）。组件一律使用语义类，禁止再出现 `bg-white`、`text-gray-900`、`blue-600` 这类硬编码色值。

### 4.3 状态管理与持久化

新建 `frontend/src/contexts/ThemeContext.tsx`：

- 状态：`{ theme: 'minimal' | 'editorial', mode: 'light' | 'dark' }`
- 初始化：读 `localStorage` 键 `app-theme`，存储格式为 JSON，如 `{"theme":"editorial","mode":"dark"}`；无记录时 `theme='minimal'`，`mode` 跟随 `prefers-color-scheme`
- 变更时：写入 `localStorage`，并同步设置 `document.documentElement` 的两个 data 属性
- 导出 `useTheme()` hook

### 4.4 防闪烁

`frontend/index.html` 的 `<head>` 内联一段同步小脚本：在 React 挂载前从 `localStorage` 读出主题（无则用系统明暗偏好）写到 `<html>` 属性，避免首屏先亮后暗的闪烁。

### 4.5 切换控件

新建 `frontend/src/components/common/ThemeSwitcher.tsx`，放在 `MainLayout` 顶栏右侧：

- 主题族切换：segmented 控件「简约 / 杂志」
- 明暗切换：太阳/月亮单图标按钮（lucide-react 已有）
- 控件本身也用令牌着色，随主题变化

## 5. 视觉规范

### 5.1 minimal（简约）

| 令牌 | 浅色 | 深色 |
|---|---|---|
| `--surface` | `#f8fafc` | `#0f172a` |
| `--surface-raised` | `#ffffff` | `#1e293b` |
| `--ink` | `#0f172a` | `#f1f5f9` |
| `--ink-muted` | `#64748b` | `#94a3b8` |
| `--line` | `#e2e8f0` | `#334155` |
| `--line-soft` | `#f1f5f9` | `#24304a` |
| `--accent` | `#2563eb` | `#3b82f6` |
| `--accent-ink` | `#ffffff` | `#ffffff` |
| `--radius` | `10px` | `10px` |
| `--shadow` | `0 1px 3px rgb(15 23 42 / .06)` | 无 |

语言：中性灰底、细边框、柔和投影、统一蓝色、系统无衬线。即"现有界面收拾干净"的版本。

### 5.2 editorial（杂志）

| 令牌 | 浅色（纸面） | 深色（暖墨） |
|---|---|---|
| `--surface` | `#f7f3ec` | `#1a1815` |
| `--surface-raised` | `#fffdf9` | `#24211a` |
| `--ink` | `#1a1a1a` | `#f2ede4` |
| `--ink-muted` | `#6b6255` | `#a39a89` |
| `--line` | `#1a1a1a` | `#4a4438` |
| `--line-soft` | `#d8d0c0` | `#38322a` |
| `--accent` | `#d43d2a` | `#e85d4a` |
| `--accent-ink` | `#f7f3ec` | `#1a1815` |
| `--radius` | `2px` | `2px` |
| `--shadow` | 无 | 无 |

语言：纸色底、墨色边框（2px）、锐利小圆角、朱红单点强调、宽字距小号大写式标签、衬线标题。

字体栈：

- `--font-body`（两族相同）：`-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`
- `--font-display`：minimal 同 body；editorial 为 `Georgia, "Songti SC", "STSong", "SimSun", "Noto Serif CJK SC", serif`

## 6. 逐页面改造要点

统一动作：所有页面/组件把硬编码色值类替换为第 4.2 节的语义类；布局结构基本不动。

- **index.css**：定义令牌与四组合取值；`@theme inline` 映射；body、`.markdown-body`（引用条用 `--accent`、代码块用 `--surface-raised`/`--ink` 等）、滚动条、`.streaming-cursor` 全部改为令牌驱动
- **MainLayout**：顶栏令牌化，右侧放 `ThemeSwitcher`；editorial 下品牌名用 `font-display` + `--line-soft` 细分隔线
- **登录 / 注册页**：居中卡片语义化；editorial = 衬线 Logo 标题 + 2px 墨框卡片 + 红色小装饰线
- **知识库列表页**：卡片网格令牌化；editorial = 墨框锐角卡 + 衬线库名 + 宽字距元信息 + 标题下红色短划线
- **知识库详情页**：文档列表、上传区令牌化；`DocStatusBadge` 出两套变体（minimal 柔和底色胶囊 / editorial 墨框锐角描边）
- **聊天页**：消息气泡、输入框令牌化；用户气泡用 `--accent`，AI 气泡用 `--surface-raised` + `--line`；markdown 样式随主题
- **共享组件**：Loading 转圈用 `--accent`；Empty/ErrorState 文字用 `--ink-muted`；Pagination 按钮令牌化

## 7. 验证与测试

- `npm run build`（tsc + vite）与 `npm run lint`（oxlint）必须通过
- 新增 Playwright e2e 冒烟（项目已有 `@playwright/test`）：遍历各页面，切换主题族 × 明暗，断言 `<html>` 的 `data-theme`/`data-mode` 属性与 `localStorage` 持久化
- 实施过程中用 Playwright 截图逐页 × 四组合人工核对观感

## 8. 非目标（YAGNI）

- 不引入组件库（AntD / shadcn 等）
- 不加载网络字体
- 不做主题色自定义、不做跟随系统自动切换的定时逻辑
- 不改后端 API 与数据结构
