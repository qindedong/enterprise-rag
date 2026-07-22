# 前端主题系统与界面美化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为前端建立「简约 / 杂志 × 明 / 暗」四套主题，全部页面与共享组件改用语义化设计令牌，并提供可持久化的主题切换按钮。

**Architecture:** CSS 自定义属性承载令牌，`<html>` 的 `data-theme` / `data-mode` 属性切换四组取值；Tailwind 4 `@theme inline` 把令牌映射为语义工具类；React Context 管理状态并持久化到 localStorage；`index.html` 内联脚本防首屏闪烁。

**Tech Stack:** React 19、Tailwind CSS 4（@tailwindcss/vite）、Vite 8、Playwright（e2e）、lucide-react。

**设计规格：** `docs/superpowers/specs/2026-07-22-frontend-themes-design.md`

**⚠️ 工作区警示：** 执行前 `git status` 可见若干与本任务无关的未提交改动（backend/*、frontend/src/api/*、frontend/src/pages/ChatPage.tsx、frontend/vite.config.ts）。**每个提交步骤只 `git add` 本任务列出的文件**，严禁 `git add -A`。Task 10 要改的 ChatPage.tsx 本身已有未提交改动，提交前先 `git diff frontend/src/pages/ChatPage.tsx` 把现状展示给用户确认。

---

## 通用替换映射表（Task 6–10 的词典）

所有页面/组件按此表把硬编码色值类替换为语义类。完成标准：对每个改动文件执行下面的 grep 应返回 0 匹配：

```bash
grep -nE "(gray|blue|red|green|yellow|amber|emerald|rose|orange|purple|indigo|sky)-[0-9]{2,3}|bg-white|text-white" <文件>
```

例外（允许保留）：`bg-black/30` 这类遮罩透明度色、`text-white` 出现在 `bg-accent` 之上时应改为 `text-accent-ink`（见下表）。

| 场景 | 旧写法 | 新写法 |
|---|---|---|
| 页面底色 | `bg-gray-50` | `bg-surface` |
| 卡片/面板/弹窗容器 | `bg-white rounded-xl border border-gray-200 shadow-sm` 等 | `card`（组件类，见 Task 1） |
| 主按钮 | `bg-blue-500 text-white rounded-lg ... hover:bg-blue-600` | `btn-primary`（组件类） |
| 次要/取消按钮 | `text-gray-600 hover:bg-gray-100 rounded-lg` | `btn-ghost`（组件类） |
| 输入框/文本域 | `border border-gray-300 rounded-lg ... focus:ring-blue-500` | `input`（组件类） |
| 主标题文字 | `text-gray-900` / `text-gray-800` / `text-gray-700` | `text-ink`（标题另加 `font-display`） |
| 次要文字 | `text-gray-600` / `text-gray-500` / `text-gray-400` | `text-ink-muted` |
| 元信息小字 | `text-xs text-gray-400` | `meta-label`（组件类） |
| 边框（卡片、侧栏、表格） | `border-gray-200` / `border-gray-300` | `border-line` |
| 弱分隔线、hover 底色 | `bg-gray-100` / `hover:bg-gray-100` / `divide-gray-100` | `bg-line-soft` / `hover:bg-line-soft` / `divide-line-soft` |
| 链接 | `text-blue-600 hover:underline` | `text-accent hover:underline` |
| 强调浅底（图标盒、激活导航） | `bg-blue-50 text-blue-700` / `bg-blue-50` + `text-blue-500` | `bg-accent/10 text-accent` |
| 错误提示条 | `bg-red-50 text-red-600` | `bg-err-soft text-err` |
| 强调按钮上的白字 | `text-white`（在 `bg-blue-500` 上） | `text-accent-ink`（随 `btn-primary` 自带） |
| 圆角 | `rounded-lg` / `rounded-xl` / `rounded-md` | `rounded-theme` |
| 阴影 | `shadow-sm` / `shadow-md` / `shadow-xl` | `shadow-theme`（`card` 已含） |

---

## Task 1: 主题令牌与全局样式（index.css 重写）

**Files:**
- Modify: `frontend/src/index.css`（整文件替换）

- [ ] **Step 1: 整文件替换 `frontend/src/index.css`**

```css
@import "tailwindcss";

/* ============================================
 * 主题令牌：data-theme × data-mode 四组合
 * 组件只使用语义工具类，不写具体色值
 * 默认（无属性）= minimal + light
 * ============================================ */

:root {
  --surface: #f8fafc;
  --surface-raised: #ffffff;
  --ink: #0f172a;
  --ink-muted: #64748b;
  --line: #e2e8f0;
  --line-soft: #f1f5f9;
  --accent: #2563eb;
  --accent-ink: #ffffff;
  --ok: #16a34a;
  --ok-soft: #dcfce7;
  --warn: #b45309;
  --warn-soft: #fef3c7;
  --err: #dc2626;
  --err-soft: #fee2e2;
  --info: #2563eb;
  --info-soft: #dbeafe;
  --display-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  --body-font: var(--display-font);
  --radius: 10px;
  --shadow: 0 1px 3px rgb(15 23 42 / 0.06);
  --meta-tracking: 0.02em;
}

[data-theme='minimal'][data-mode='dark'] {
  --surface: #0f172a;
  --surface-raised: #1e293b;
  --ink: #f1f5f9;
  --ink-muted: #94a3b8;
  --line: #334155;
  --line-soft: #24304a;
  --accent: #3b82f6;
  --accent-ink: #ffffff;
  --ok: #4ade80;
  --ok-soft: rgb(74 222 128 / 0.12);
  --warn: #fbbf24;
  --warn-soft: rgb(251 191 36 / 0.12);
  --err: #f87171;
  --err-soft: rgb(248 113 113 / 0.12);
  --info: #60a5fa;
  --info-soft: rgb(96 165 250 / 0.12);
  --radius: 10px;
  --shadow: none;
  --meta-tracking: 0.02em;
}

[data-theme='editorial'][data-mode='light'] {
  --surface: #f7f3ec;
  --surface-raised: #fffdf9;
  --ink: #1a1a1a;
  --ink-muted: #6b6255;
  --line: #1a1a1a;
  --line-soft: #d8d0c0;
  --accent: #d43d2a;
  --accent-ink: #f7f3ec;
  --ok: #3d7a52;
  --ok-soft: #e4ebdd;
  --warn: #a36b1f;
  --warn-soft: #f2e8d5;
  --err: #d43d2a;
  --err-soft: #f5ddd5;
  --info: #3f5f8a;
  --info-soft: #dde4ea;
  --display-font: Georgia, "Songti SC", "STSong", "SimSun", "Noto Serif CJK SC", serif;
  --body-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  --radius: 2px;
  --shadow: none;
  --meta-tracking: 0.18em;
}

[data-theme='editorial'][data-mode='dark'] {
  --surface: #1a1815;
  --surface-raised: #24211a;
  --ink: #f2ede4;
  --ink-muted: #a39a89;
  --line: #4a4438;
  --line-soft: #38322a;
  --accent: #e85d4a;
  --accent-ink: #1a1815;
  --ok: #7fb08a;
  --ok-soft: rgb(127 176 138 / 0.14);
  --warn: #d9a75e;
  --warn-soft: rgb(217 167 94 / 0.14);
  --err: #e85d4a;
  --err-soft: rgb(232 93 74 / 0.14);
  --info: #7f9cc4;
  --info-soft: rgb(127 156 196 / 0.14);
  --display-font: Georgia, "Songti SC", "STSong", "SimSun", "Noto Serif CJK SC", serif;
  --body-font: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  --radius: 2px;
  --shadow: none;
  --meta-tracking: 0.18em;
}

/* ===== 令牌 → Tailwind 语义工具类 ===== */
@theme inline {
  --color-surface: var(--surface);
  --color-surface-raised: var(--surface-raised);
  --color-ink: var(--ink);
  --color-ink-muted: var(--ink-muted);
  --color-line: var(--line);
  --color-line-soft: var(--line-soft);
  --color-accent: var(--accent);
  --color-accent-ink: var(--accent-ink);
  --color-ok: var(--ok);
  --color-ok-soft: var(--ok-soft);
  --color-warn: var(--warn);
  --color-warn-soft: var(--warn-soft);
  --color-err: var(--err);
  --color-err-soft: var(--err-soft);
  --color-info: var(--info);
  --color-info-soft: var(--info-soft);
  --font-display: var(--display-font);
  --font-body: var(--body-font);
  --radius-theme: var(--radius);
  --shadow-theme: var(--shadow);
  --tracking-meta: var(--meta-tracking);
}

/* ===== 基础样式 ===== */
body {
  @apply bg-surface text-ink font-body antialiased;
  margin: 0;
}

/* ===== 可复用组件类 ===== */
@layer components {
  /* 卡片/面板/弹窗容器（editorial 下自动变为 2px 墨框锐角） */
  .card {
    @apply bg-surface-raised border border-line rounded-theme shadow-theme;
  }

  /* 主按钮 */
  .btn-primary {
    @apply inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-accent text-accent-ink rounded-theme text-sm font-medium transition-all hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed;
  }

  /* 次要按钮 */
  .btn-ghost {
    @apply inline-flex items-center justify-center gap-2 px-4 py-2 text-sm text-ink-muted rounded-theme transition-colors hover:bg-line-soft hover:text-ink;
  }

  /* 输入框 */
  .input {
    @apply w-full px-3 py-2.5 bg-surface-raised border border-line rounded-theme text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent;
  }

  /* 元信息小字（editorial 下自动加宽字距） */
  .meta-label {
    @apply text-xs text-ink-muted tracking-meta;
  }
}

[data-theme='editorial'] .card {
  border-width: 2px;
}

/* ===== Markdown 渲染样式 ===== */
.markdown-body h1 { @apply font-display text-2xl font-bold mb-4 mt-6; }
.markdown-body h2 { @apply font-display text-xl font-semibold mb-3 mt-5; }
.markdown-body h3 { @apply font-display text-lg font-medium mb-2 mt-4; }
.markdown-body p { @apply mb-3 leading-relaxed; }
.markdown-body ul { @apply list-disc pl-6 mb-3; }
.markdown-body ol { @apply list-decimal pl-6 mb-3; }
.markdown-body li { @apply mb-1; }
.markdown-body code { @apply bg-line-soft text-err px-1.5 py-0.5 rounded-theme text-sm font-mono; }
.markdown-body pre { @apply bg-ink text-surface p-4 rounded-theme mb-4 overflow-x-auto; }
.markdown-body pre code { @apply bg-transparent text-surface p-0; }
.markdown-body blockquote { @apply border-l-4 border-accent pl-4 italic text-ink-muted mb-3; }
.markdown-body table { @apply w-full border-collapse mb-4; }
.markdown-body th { @apply border border-line bg-line-soft px-3 py-2 text-left font-semibold; }
.markdown-body td { @apply border border-line-soft px-3 py-2; }
.markdown-body a { @apply text-accent underline hover:brightness-110; }

/* ===== 滚动条美化 ===== */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { @apply bg-transparent; }
::-webkit-scrollbar-thumb { @apply bg-line rounded-full; }
::-webkit-scrollbar-thumb:hover { @apply bg-ink-muted; }

/* ===== SSE 流式光标动画 ===== */
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.streaming-cursor::after {
  content: "▊";
  animation: blink 1s infinite;
  @apply text-accent;
}
```

- [ ] **Step 2: 验证构建**

Run: `cd frontend && npm run build`
Expected: 成功（tsc + vite 均无报错）。若 Tailwind 报未知工具类，检查 `@theme inline` 块是否拼写正确。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat(frontend): 主题令牌体系 — 双主题 × 明暗四套 CSS 变量 + 语义工具类"
```

> **审查修订（已落地，commit ef9fbb3）：** 代码质量审查后对本任务的 CSS 做了四处修正，以上代码块为修订前版本，以仓库实现为准：
> 1. 新增 `--code-bg`/`--code-ink` 令牌（四主题各一组恒深值），`.markdown-body pre` 改用 `bg-code-bg text-code-ink`，不再随主题反转
> 2. 新增 `--card-border-width` 令牌（1px/1px/2px/2px），`.card` 内 `border-width: var(--card-border-width)`；删除未分层的 `[data-theme='editorial'] .card` 覆盖规则
> 3. 三处 `--shadow: none` 改为 `--shadow: 0 0 #0000`
> 4. `.btn-primary` 追加 `disabled:hover:brightness-100`

---

## Task 2: ThemeContext + 防闪烁脚本 + Provider 接线

**Files:**
- Create: `frontend/src/contexts/ThemeContext.tsx`
- Modify: `frontend/index.html`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 `frontend/src/contexts/ThemeContext.tsx`**

```tsx
/**
 * 主题上下文
 *
 * 管理「主题族 × 明暗」状态：
 * - theme: minimal（简约）/ editorial（杂志）
 * - mode: light / dark
 * 选择持久化到 localStorage（键 app-theme，JSON 格式），
 * 并同步到 <html> 的 data-theme / data-mode 属性。
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

export type ThemeName = 'minimal' | 'editorial'
export type ThemeMode = 'light' | 'dark'

interface ThemeState {
  theme: ThemeName
  mode: ThemeMode
  setTheme: (theme: ThemeName) => void
  toggleMode: () => void
}

const STORAGE_KEY = 'app-theme'

const ThemeContext = createContext<ThemeState | undefined>(undefined)

/** 读取持久化主题；无记录时默认简约 + 跟随系统明暗 */
function readStoredTheme(): { theme: ThemeName; mode: ThemeMode } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (
        (parsed.theme === 'minimal' || parsed.theme === 'editorial') &&
        (parsed.mode === 'light' || parsed.mode === 'dark')
      ) {
        return parsed
      }
    }
  } catch {
    // 数据损坏则回落默认值
  }
  return {
    theme: 'minimal',
    mode: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(readStoredTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = state.theme
    document.documentElement.dataset.mode = state.mode
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])

  const setTheme = useCallback(
    (theme: ThemeName) => setState((s) => ({ ...s, theme })),
    [],
  )
  const toggleMode = useCallback(
    () => setState((s) => ({ ...s, mode: s.mode === 'light' ? 'dark' : 'light' })),
    [],
  )

  return (
    <ThemeContext.Provider value={{ ...state, setTheme, toggleMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

/** 使用主题上下文 Hook */
export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme 必须在 ThemeProvider 内部使用')
  }
  return ctx
}
```

- [ ] **Step 2: `frontend/index.html` 加防闪烁脚本**

在 `<title>企业知识库 RAG</title>` 之后插入（必须在 `/src/main.tsx` 加载前同步执行）：

```html
    <script>
      // 防主题闪烁：React 挂载前恢复已保存的主题
      (function () {
        try {
          var raw = localStorage.getItem('app-theme')
          var t = raw ? JSON.parse(raw) : null
          document.documentElement.dataset.theme =
            t && (t.theme === 'minimal' || t.theme === 'editorial') ? t.theme : 'minimal'
          document.documentElement.dataset.mode =
            t && (t.mode === 'light' || t.mode === 'dark')
              ? t.mode
              : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
        } catch (e) { /* 忽略损坏数据 */ }
      })()
    </script>
```

- [ ] **Step 3: `frontend/src/App.tsx` 接入 ThemeProvider**

在 `import { AuthProvider } from './contexts/AuthContext'` 后加一行 `import { ThemeProvider } from './contexts/ThemeContext'`，并把 `<AuthProvider ...>` 外层包上 `<ThemeProvider>`：

```tsx
      <ThemeProvider>
        <AuthProvider key={ready ? 'ready' : 'init'}>
          ...
        </AuthProvider>
      </ThemeProvider>
```

- [ ] **Step 4: 验证构建与 lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/ThemeContext.tsx frontend/index.html frontend/src/App.tsx
git commit -m "feat(frontend): ThemeContext + 防闪烁脚本 + Provider 接线"
```

---

## Task 3: Playwright 环境 + 主题切换 e2e（先写，当前应失败）

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/theme.spec.ts`
- Modify: `frontend/package.json`（加 script）
- Modify: `frontend/.gitignore`（追加 Playwright 产物目录）

- [ ] **Step 1: 创建 `frontend/playwright.config.ts`**

```ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: 'http://localhost:3000',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
```

- [ ] **Step 2: 创建 `frontend/e2e/theme.spec.ts`**

登录态通过 mock 实现：预置 token + 拦截 `GET /api/v1/auth/me` 与知识库列表接口，不依赖真实后端。

```ts
import { test, expect } from '@playwright/test'

const MOCK_USER = {
  code: 0,
  message: 'ok',
  data: {
    id: 'u1',
    username: '测试用户',
    email: 'test@example.com',
    created_at: '2026-01-01T00:00:00Z',
  },
}

const MOCK_KB_LIST = {
  code: 0,
  message: 'ok',
  data: {
    items: [],
    page_info: { page: 1, page_size: 12, total: 0, total_pages: 0 },
  },
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('rag_access_token', 'fake-token-for-e2e')
  })
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_USER) }),
  )
  await page.route('**/api/v1/knowledge-bases**', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_KB_LIST) }),
  )
})

test('默认主题为 minimal', async ({ page }) => {
  await page.goto('/kbs')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'minimal')
})

test('切换主题族与明暗并持久化', async ({ page }) => {
  await page.goto('/kbs')

  // 切换到杂志主题
  await page.getByRole('radio', { name: '杂志' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'editorial')

  // 切换明暗
  await page
    .getByRole('button', { name: /切换到深色模式|切换到浅色模式/ })
    .click()
  const mode = await page.locator('html').getAttribute('data-mode')

  // localStorage 持久化
  const stored = await page.evaluate(() => localStorage.getItem('app-theme'))
  expect(JSON.parse(stored!)).toEqual({ theme: 'editorial', mode })

  // 刷新后保持
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'editorial')
  await expect(page.locator('html')).toHaveAttribute('data-mode', mode!)
})
```

- [ ] **Step 3: `frontend/package.json` 的 `scripts` 中加一行**

```json
    "test:e2e": "playwright test"
```

并在 `frontend/.gitignore` 末尾追加（如已存在则跳过）：

```
test-results/
playwright-report/
```

- [ ] **Step 4: 安装浏览器并运行测试，确认失败**

Run: `cd frontend && npx playwright install chromium && npx playwright test`
Expected: 第 1 个测试通过（`data-theme=minimal` 已由 Task 2 保证）；第 2 个测试**失败**——`getByRole('radio', { name: '杂志' })` 找不到元素，因为 ThemeSwitcher 还不存在。

- [ ] **Step 5: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e/theme.spec.ts frontend/package.json frontend/.gitignore
git commit -m "test(frontend): Playwright 环境 + 主题切换 e2e（当前失败，待 ThemeSwitcher）"
```

---

## Task 4: ThemeSwitcher 组件 + MainLayout 令牌化（e2e 转绿）

**Files:**
- Create: `frontend/src/components/common/ThemeSwitcher.tsx`
- Modify: `frontend/src/components/common/index.ts`
- Modify: `frontend/src/components/layout/MainLayout.tsx`（整文件替换）

- [ ] **Step 1: 创建 `frontend/src/components/common/ThemeSwitcher.tsx`**

```tsx
/**
 * 主题切换控件：主题族（简约/杂志）+ 明暗切换
 */

import { LucideMoon, LucideSun } from 'lucide-react'
import { useTheme, type ThemeName } from '../../contexts/ThemeContext'

const THEME_OPTIONS: { value: ThemeName; label: string }[] = [
  { value: 'minimal', label: '简约' },
  { value: 'editorial', label: '杂志' },
]

export function ThemeSwitcher() {
  const { theme, mode, setTheme, toggleMode } = useTheme()

  return (
    <div className="flex items-center gap-2">
      {/* 主题族 segmented 控件 */}
      <div
        className="flex rounded-theme border border-line overflow-hidden"
        role="radiogroup"
        aria-label="主题风格"
      >
        {THEME_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={theme === opt.value}
            onClick={() => setTheme(opt.value)}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              theme === opt.value
                ? 'bg-accent text-accent-ink'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* 明暗切换 */}
      <button
        type="button"
        onClick={toggleMode}
        aria-label={mode === 'light' ? '切换到深色模式' : '切换到浅色模式'}
        className="p-2 rounded-theme text-ink-muted hover:text-ink hover:bg-line-soft transition-colors"
      >
        {mode === 'light' ? (
          <LucideMoon className="h-4 w-4" />
        ) : (
          <LucideSun className="h-4 w-4" />
        )}
      </button>
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/components/common/index.ts` 加导出**

在文件末尾追加：

```ts
export { ThemeSwitcher } from './ThemeSwitcher'
```

（先读该文件确认现有导出风格，保持一致。）

- [ ] **Step 3: 整文件替换 `frontend/src/components/layout/MainLayout.tsx`**

要点：全部语义类；品牌名用 `font-display`；顶栏右侧放 `ThemeSwitcher`。

```tsx
/**
 * 主布局组件（Header + Sidebar + 内容区）
 */

import { useState } from 'react'
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom'
import {
  LucideDatabase,
  LucideMessageSquare,
  LucideLogOut,
  LucideMenu,
  LucideUser,
  LucideBookOpen,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { ThemeSwitcher } from '../common'

export function MainLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { path: '/kbs', label: '知识库', icon: LucideDatabase },
    { path: '/chat', label: 'AI 问答', icon: LucideMessageSquare },
  ]

  return (
    <div className="min-h-screen flex bg-surface">
      {/* ===== 移动端遮罩 ===== */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ===== 侧边栏 ===== */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50 w-60 bg-surface-raised border-r border-line
          flex flex-col transition-transform duration-200
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-5 border-b border-line">
          <div className="h-8 w-8 bg-accent rounded-theme flex items-center justify-center">
            <LucideBookOpen className="h-4 w-4 text-accent-ink" />
          </div>
          <span className="font-display font-bold text-ink">知识库 RAG</span>
        </div>

        {/* 导航 */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ path, label, icon: Icon }) => {
            const isActive = location.pathname.startsWith(path)
            return (
              <Link
                key={path}
                to={path}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-theme text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-accent/10 text-accent'
                    : 'text-ink-muted hover:bg-line-soft hover:text-ink'
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* 底部用户信息 */}
        <div className="p-4 border-t border-line">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-8 w-8 bg-line-soft rounded-full flex items-center justify-center">
              <LucideUser className="h-4 w-4 text-ink-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-ink truncate">
                {user?.username || '用户'}
              </p>
              <p className="meta-label truncate">
                {user?.email || ''}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-ink-muted hover:text-err hover:bg-err-soft rounded-theme transition-colors"
          >
            <LucideLogOut className="h-4 w-4" />
            退出登录
          </button>
        </div>
      </aside>

      {/* ===== 主内容区 ===== */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部导航栏 */}
        <header className="h-16 bg-surface-raised border-b border-line flex items-center px-4 lg:px-6 shrink-0">
          <button
            className="lg:hidden p-2 -ml-2 mr-2 rounded-theme hover:bg-line-soft"
            onClick={() => setSidebarOpen(true)}
          >
            <LucideMenu className="h-5 w-5 text-ink-muted" />
          </button>
          <button
            className="hidden lg:flex p-2 -ml-2 mr-2 rounded-theme hover:bg-line-soft"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <LucideMenu className="h-5 w-5 text-ink-muted" />
          </button>
          <h1 className="font-display text-lg font-semibold text-ink flex-1 truncate">
            {navItems.find((n) => location.pathname.startsWith(n.path))?.label || '企业知识库'}
          </h1>
          <ThemeSwitcher />
        </header>

        {/* 内容 */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: 运行 e2e，确认转绿**

Run: `cd frontend && npx playwright test`
Expected: 2 个测试全部通过。

- [ ] **Step 5: 构建 + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: 通过。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/common/ThemeSwitcher.tsx frontend/src/components/common/index.ts frontend/src/components/layout/MainLayout.tsx
git commit -m "feat(frontend): ThemeSwitcher 组件 + MainLayout 语义化改造"
```

---

## Task 5: 共享组件与状态色令牌化

**Files:**
- Modify: `frontend/src/utils/constants.ts`（DOC_STATUS_MAP）
- Modify: `frontend/src/components/common/DocStatusBadge.tsx`（整文件替换）
- Modify: `frontend/src/components/common/Loading.tsx`
- Modify: `frontend/src/components/common/Empty.tsx`
- Modify: `frontend/src/components/common/ErrorState.tsx`（整文件替换）
- Modify: `frontend/src/components/common/Pagination.tsx`（整文件替换）

- [ ] **Step 1: `frontend/src/utils/constants.ts` 替换 DOC_STATUS_MAP**

```ts
/** 文档状态中文映射（颜色用语义状态类，随主题切换） */
export const DOC_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'bg-warn-soft text-warn' },
  processing: { label: '处理中', color: 'bg-info-soft text-info' },
  completed: { label: '已完成', color: 'bg-ok-soft text-ok' },
  failed: { label: '失败', color: 'bg-err-soft text-err' },
}
```

- [ ] **Step 2: 整文件替换 `frontend/src/components/common/DocStatusBadge.tsx`**

```tsx
/**
 * 文档状态标签
 */

import { DOC_STATUS_MAP } from '../../utils/constants'

export function DocStatusBadge({ status }: { status: string }) {
  const info = DOC_STATUS_MAP[status] || { label: status, color: 'bg-line-soft text-ink-muted' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-theme text-xs font-medium ${info.color}`}>
      {info.label}
    </span>
  )
}
```

- [ ] **Step 3: `frontend/src/components/common/Loading.tsx` 两处替换**

- 外层容器 `text-gray-400` → `text-ink-muted`
- 转圈 SVG `text-blue-500` → `text-accent`

- [ ] **Step 4: `frontend/src/components/common/Empty.tsx` 三处替换**

- 外层容器 `text-gray-400` → `text-ink-muted`
- 标题 `text-gray-500` → `text-ink`
- 描述 `text-gray-400` → `text-ink-muted`

- [ ] **Step 5: 整文件替换 `frontend/src/components/common/ErrorState.tsx`**

```tsx
/**
 * 错误状态组件
 */

import { LucideAlertTriangle } from 'lucide-react'

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
}

export function ErrorState({
  message = '加载失败，请稍后重试',
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <LucideAlertTriangle className="h-16 w-16 text-err mb-4" />
      <p className="font-display text-lg font-medium text-ink mb-2">出错了</p>
      <p className="text-sm text-ink-muted mb-6 max-w-sm text-center">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-primary">
          重试
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 6: 整文件替换 `frontend/src/components/common/Pagination.tsx`**

```tsx
/**
 * 分页组件
 */

import { LucideChevronLeft, LucideChevronRight } from 'lucide-react'
import type { PageInfo } from '../../types'

interface PaginationProps {
  pageInfo: PageInfo
  onPageChange: (page: number) => void
}

export function Pagination({ pageInfo, onPageChange }: PaginationProps) {
  const { page, total_pages, total } = pageInfo

  if (total_pages <= 1) return null

  const pages: number[] = []
  const maxShow = 5
  let start = Math.max(1, page - Math.floor(maxShow / 2))
  const end = Math.min(total_pages, start + maxShow - 1)
  start = Math.max(1, end - maxShow + 1)

  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-line">
      <span className="meta-label">
        共 {total} 条
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="p-1.5 rounded-theme text-ink-muted hover:bg-line-soft disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <LucideChevronLeft className="h-4 w-4" />
        </button>
        {pages.map((p) => (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={`min-w-[32px] h-8 rounded-theme text-sm font-medium transition-colors ${
              p === page
                ? 'bg-accent text-accent-ink'
                : 'text-ink-muted hover:bg-line-soft'
            }`}
          >
            {p}
          </button>
        ))}
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= total_pages}
          className="p-1.5 rounded-theme text-ink-muted hover:bg-line-soft disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <LucideChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: 验证**

Run: `cd frontend && grep -rnE "(gray|blue|red|green|yellow)-[0-9]{2,3}|bg-white|text-white" src/components/common src/utils/constants.ts; npm run build && npm run lint`
Expected: grep 无输出；build 与 lint 通过。

- [ ] **Step 8: Commit**

```bash
git add frontend/src/utils/constants.ts frontend/src/components/common/
git commit -m "feat(frontend): 共享组件与文档状态色语义化"
```

---

## Task 6: 登录页令牌化（整文件替换，作为页面改造范本）

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`（整文件替换）

- [ ] **Step 1: 整文件替换 `frontend/src/pages/LoginPage.tsx`**

品牌区：`font-display` 标题 + accent 短划线（editorial 下自动变衬线/朱红）；表单容器用 `card` + `input` + `btn-primary`。

```tsx
/**
 * 登录页面
 */

import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LucideBookOpen, LucideEye, LucideEyeOff } from 'lucide-react'
import { login } from '../api/auth'
import { useAuth } from '../contexts/AuthContext'

export function LoginPage() {
  const navigate = useNavigate()
  const { login: doLogin } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email.trim()) { setError('请输入邮箱'); return }
    if (!password) { setError('请输入密码'); return }

    setLoading(true)
    try {
      const res = await login({ email: email.trim(), password })
      await doLogin(res.data.access_token, res.data.refresh_token)
      navigate('/kbs', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      setError(msg || '登录失败，请检查邮箱和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex h-14 w-14 bg-accent rounded-theme items-center justify-center mb-4">
            <LucideBookOpen className="h-7 w-7 text-accent-ink" />
          </div>
          <h1 className="font-display text-2xl font-bold text-ink">企业知识库 RAG</h1>
          <div className="h-1 w-10 bg-accent mx-auto mt-3" />
          <p className="meta-label mt-3">登录以继续使用</p>
        </div>

        {/* 表单 */}
        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          {error && (
            <div className="bg-err-soft text-err text-sm px-4 py-3 rounded-theme">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-ink mb-1">邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="请输入邮箱地址"
              className="input"
              autoComplete="email"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink mb-1">密码</label>
            <div className="relative">
              <input
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                className="input pr-10"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPwd(!showPwd)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
              >
                {showPwd ? <LucideEyeOff className="h-4 w-4" /> : <LucideEye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full"
          >
            {loading ? '登录中...' : '登 录'}
          </button>
        </form>

        <p className="text-center text-sm text-ink-muted mt-6">
          还没有账号？{' '}
          <Link to="/register" className="text-accent hover:underline font-medium">
            立即注册
          </Link>
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 验证**

Run: `cd frontend && npm run build && npm run lint`
Expected: 通过。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "feat(frontend): 登录页语义化改造"
```

---

## Task 7: 注册页令牌化

**Files:**
- Modify: `frontend/src/pages/RegisterPage.tsx`

- [ ] **Step 1: 按 Task 6 的同一模式改造**

结构与 LoginPage 相同（多「用户名」「确认密码」两个字段和密码提示小字）。逐处替换（行号基于改造前版本，以内容匹配为准）：

| 位置（原内容特征） | 改法 |
|---|---|
| `min-h-screen bg-gray-50 flex items-center justify-center p-4` | `bg-gray-50` → `bg-surface` |
| Logo 图标盒 `h-14 w-14 bg-blue-500 rounded-xl` | → `h-14 w-14 bg-accent rounded-theme`；内部图标 `text-white` → `text-accent-ink` |
| `<h1 ... text-gray-800">创建账号</h1>` | → `<h1 className="font-display text-2xl font-bold text-ink">创建账号</h1>`，并在 h1 后加 `<div className="h-1 w-10 bg-accent mx-auto mt-3" />` |
| 副标题 `text-sm text-gray-500 mt-1` | → `meta-label mt-3` |
| `<form ... className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">` | → `className="card p-6 space-y-4"` |
| 错误条 `bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg` | → `bg-err-soft text-err text-sm px-4 py-3 rounded-theme` |
| 全部 `<label className="block text-sm font-medium text-gray-700 mb-1">` | → `text-ink` |
| 全部输入框 `w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent` | → `className="input"`（密码框保留 `pr-10`：`className="input pr-10"`，并去掉 `focus:border-transparent` 重复部分） |
| 眼睛按钮 `text-gray-400 hover:text-gray-600` | → `text-ink-muted hover:text-ink` |
| 密码提示 `text-xs text-gray-400 mt-1` | → `meta-label mt-1` |
| 提交按钮 `w-full py-2.5 bg-blue-500 text-white rounded-lg ...` | → `className="btn-primary w-full"` |
| 底部 `text-center text-sm text-gray-500 mt-6` | → `text-ink-muted`；链接 `text-blue-600` → `text-accent` |

- [ ] **Step 2: 验证**

Run: `cd frontend && grep -nE "(gray|blue|red)-[0-9]{2,3}|bg-white|text-white" src/pages/RegisterPage.tsx; npm run build && npm run lint`
Expected: grep 无输出；build 与 lint 通过。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/RegisterPage.tsx
git commit -m "feat(frontend): 注册页语义化改造"
```

---

## Task 8: 知识库列表页令牌化

**Files:**
- Modify: `frontend/src/pages/KBListPage.tsx`

- [ ] **Step 1: 按「通用替换映射表」改造，重点位置如下**（行号基于改造前版本，以内容匹配为准）

| 位置 | 改法 |
|---|---|
| 搜索图标 `text-gray-400` | → `text-ink-muted` |
| 搜索输入框 `w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500` | → `className="input pl-9"` |
| 「新建知识库」按钮 `flex items-center gap-2 px-4 py-2.5 bg-blue-500 text-white rounded-lg ...` | → `className="btn-primary shrink-0"` |
| 空状态里的 `px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600` | → `className="btn-primary"` |
| 知识库卡片 `bg-white rounded-xl border border-gray-200 p-5 cursor-pointer hover:shadow-md hover:border-blue-200 transition-all` | → `className="card p-5 cursor-pointer hover:border-accent transition-colors"` |
| 卡片图标盒 `h-10 w-10 bg-blue-50 rounded-lg` + 图标 `text-blue-500` | → `bg-accent/10 rounded-theme` + `text-accent` |
| 库名 `<h3 className="font-semibold text-gray-800 truncate">` | → `className="font-display font-semibold text-ink truncate"` |
| 描述 `text-xs text-gray-400 mt-0.5 line-clamp-2` | → `meta-label mt-0.5 line-clamp-2` |
| 底部元信息 `flex items-center gap-4 text-xs text-gray-400` | → `flex items-center gap-4 meta-label` |
| 分页容器 `mt-6 bg-white rounded-xl border border-gray-200 overflow-hidden` | → `mt-6 card overflow-hidden` |
| 弹窗 `relative bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-md p-6` | → `relative card w-full max-w-md p-6` |
| 弹窗标题 `text-lg font-semibold text-gray-800 mb-4` | → `font-display text-lg font-semibold text-ink mb-4` |
| 弹窗错误条 `bg-red-50 text-red-600 ...` | → `bg-err-soft text-err text-sm px-3 py-2 rounded-theme mb-3` |
| 弹窗 label / 输入框 / 文本域 | 同 Task 7 的 label、`input` 改法 |
| 取消按钮 `px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg` | → `className="btn-ghost"` |
| 创建按钮 `px-4 py-2 bg-blue-500 text-white rounded-lg ...` | → `className="btn-primary"` |

保留不动：遮罩 `bg-black/30`。页面顶部如有 `text-gray-800` 大标题类元素，一并按映射表替换。

- [ ] **Step 2: 验证**

Run: `cd frontend && grep -nE "(gray|blue|red)-[0-9]{2,3}|bg-white|text-white" src/pages/KBListPage.tsx; npm run build && npm run lint`
Expected: grep 无输出；build 与 lint 通过。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/KBListPage.tsx
git commit -m "feat(frontend): 知识库列表页语义化改造"
```

---

## Task 9: 知识库详情页令牌化

**Files:**
- Modify: `frontend/src/pages/KBDetailPage.tsx`

- [ ] **Step 1: 枚举全部待改位置**

Run: `cd frontend && grep -nE "(gray|blue|red|green|yellow|amber|emerald)-[0-9]{2,3}|bg-white|text-white" src/pages/KBDetailPage.tsx`
Expected: 约 62 行输出——这就是本任务的完整清单。

- [ ] **Step 2: 按「通用替换映射表」逐处替换**

该页包含：返回链接、库信息头部、统计卡片、上传区、文档列表/表格、删除确认等。规则：

- 页面大标题/库名加 `font-display`，描述与统计小字用 `meta-label`
- 统计卡片、列表容器、上传区容器 → `card`
- 表格：`border-gray-200` → `border-line`；表头底色 `bg-gray-50` → `bg-line-soft`；行分隔 `divide-gray-200` / `border-gray-100` → `divide-line-soft` / `border-line-soft`；行 hover `hover:bg-gray-50` → `hover:bg-line-soft`
- 上传按钮/主操作 → `btn-primary`；次要按钮 → `btn-ghost`
- 上传拖拽区虚线框 `border-dashed border-gray-300` → `border-dashed border-line`，拖拽高亮 `border-blue-400 bg-blue-50` → `border-accent bg-accent/10`
- 状态徽章由 `DocStatusBadge` 渲染，本文件内不应再出现状态色（Task 5 已处理）；若有行内状态色，改用 `bg-ok-soft text-ok` 等语义状态类
- 进度条 `bg-blue-500` → `bg-accent`；错误提示 → `bg-err-soft text-err`

- [ ] **Step 3: 验证**

Run: `cd frontend && grep -nE "(gray|blue|red|green|yellow|amber|emerald)-[0-9]{2,3}|bg-white|text-white" src/pages/KBDetailPage.tsx; npm run build && npm run lint`
Expected: grep 无输出；build 与 lint 通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/KBDetailPage.tsx
git commit -m "feat(frontend): 知识库详情页语义化改造"
```

---

## Task 10: 聊天页令牌化

> ⚠️ 该文件在工作区已有未提交改动。开始本任务前先 `git diff frontend/src/pages/ChatPage.tsx` 查看现状，把改动内容告知用户确认后再动手；提交时只 `git add` 这一个文件。

**Files:**
- Modify: `frontend/src/pages/ChatPage.tsx`

- [ ] **Step 1: 枚举全部待改位置**

Run: `cd frontend && grep -nE "(gray|blue|red|green|yellow|amber|emerald)-[0-9]{2,3}|bg-white|text-white" src/pages/ChatPage.tsx`
Expected: 约 74 行输出——本任务完整清单。

- [ ] **Step 2: 按「通用替换映射表」逐处替换**

该页包含：会话侧栏、消息列表、用户/AI 气泡、引用来源卡片、输入框、发送按钮。规则：

- 会话列表容器/项：容器 → `bg-surface-raised border-line`；选中项 `bg-blue-50 text-blue-700` → `bg-accent/10 text-accent`；普通项 hover → `hover:bg-line-soft`
- 用户气泡 `bg-blue-500 text-white` → `bg-accent text-accent-ink`
- AI 气泡 `bg-white border border-gray-200` → `card`（保留原有 padding/圆角类冲突时以 `card` 为准）
- 引用来源卡片 `bg-gray-50 border border-gray-200` → `bg-line-soft border border-line-soft`，来源序号徽章 `bg-blue-100 text-blue-700` → `bg-accent/10 text-accent`
- 输入框 → `input`；发送按钮 → `btn-primary`
- 空状态提示文字 → `text-ink-muted`
- `.markdown-body` 样式已在 Task 1 全局替换，本文件无需处理

- [ ] **Step 3: 验证**

Run: `cd frontend && grep -nE "(gray|blue|red|green|yellow|amber|emerald)-[0-9]{2,3}|bg-white|text-white" src/pages/ChatPage.tsx; npm run build && npm run lint`
Expected: grep 无输出；build 与 lint 通过。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChatPage.tsx
git commit -m "feat(frontend): 聊天页语义化改造"
```

---

## Task 11: 最终验证（四主题组合截图 + 全量检查）

**Files:**
- Create: `frontend/e2e/visual.spec.ts`（截图脚本，可留作回归用）

- [ ] **Step 1: 创建 `frontend/e2e/visual.spec.ts`**

```ts
import { test } from '@playwright/test'

const MOCK_USER = {
  code: 0,
  message: 'ok',
  data: { id: 'u1', username: '测试用户', email: 'test@example.com', created_at: '2026-01-01T00:00:00Z' },
}

const MOCK_KB_LIST = {
  code: 0,
  message: 'ok',
  data: {
    items: [
      {
        id: 'kb1',
        name: '产品研发流程',
        description: '产品从立项到发布的完整流程文档',
        owner_id: 'u1',
        chunk_size: 512,
        chunk_overlap: 50,
        doc_count: 12,
        chunk_count: 380,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    ],
    page_info: { page: 1, page_size: 12, total: 1, total_pages: 1 },
  },
}

const combos = [
  ['minimal', 'light'],
  ['minimal', 'dark'],
  ['editorial', 'light'],
  ['editorial', 'dark'],
] as const

for (const [theme, mode] of combos) {
  test(`截图：${theme} + ${mode}`, async ({ page }) => {
    await page.addInitScript(
      ([t, m]) => {
        localStorage.setItem('rag_access_token', 'fake-token-for-e2e')
        localStorage.setItem('app-theme', JSON.stringify({ theme: t, mode: m }))
      },
      [theme, mode] as const,
    )
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_USER) }),
    )
    await page.route('**/api/v1/knowledge-bases**', (route) =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_KB_LIST) }),
    )

    await page.goto('/login')
    await page.screenshot({ path: `e2e/shots/login-${theme}-${mode}.png`, fullPage: true })

    await page.goto('/kbs')
    await page.screenshot({ path: `e2e/shots/kbs-${theme}-${mode}.png`, fullPage: true })
  })
}
```

并在 `frontend/.gitignore` 追加：

```
e2e/shots/
```

- [ ] **Step 2: 全量验证**

Run: `cd frontend && npm run build && npm run lint && npx playwright test`
Expected: build 通过、lint 通过、6 个 e2e（2 主题切换 + 4 截图）全部通过。

- [ ] **Step 3: 人工核对 8 张截图**

用图像查看工具逐一查看 `frontend/e2e/shots/` 下 8 张截图，核对：

- 无白色/灰色的"裸"组件残留（所有元素都跟随主题）
- editorial 浅色 = 纸底墨框衬线标题；editorial 深色 = 暖墨底、文字清晰可读
- minimal 深色下状态徽章、错误条不发白刺眼
- 暗色组合下 markdown 代码块为恒深底（非刺眼亮块）
- 切换按钮在顶栏右侧，四种组合下自身也可读
- 激活导航/徽章的 `bg-accent/10 text-accent` 小字可读性（审查提示：对比度约 3.9–4.4:1，需显式拍板是否接受）
- editorial accent 按钮白字（约 4.2:1）是否接受，或把 accent 压暗到 #c23423
- markdown 表格 th（border-line）/td（border-line-soft）网格线不对称是意图还是笔误，截图确认

如发现问题：回到对应 Task 修样式，再重跑本 Task 的 Step 2。

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/visual.spec.ts frontend/.gitignore
git commit -m "test(frontend): 四主题组合截图回归脚本"
```
