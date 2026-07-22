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

/** 读取持久化主题；逐字段校验，不合法/损坏的字段各自回落默认 */
function readStoredTheme(): { theme: ThemeName; mode: ThemeMode } {
  let parsed: { theme?: unknown; mode?: unknown } | null = null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      parsed = JSON.parse(raw)
    }
  } catch {
    // 数据损坏则按无记录处理
    parsed = null
  }
  const systemMode: ThemeMode = window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
  return {
    theme:
      parsed?.theme === 'minimal' || parsed?.theme === 'editorial'
        ? parsed.theme
        : 'minimal',
    mode: parsed?.mode === 'light' || parsed?.mode === 'dark' ? parsed.mode : systemMode,
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
