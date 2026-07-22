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
