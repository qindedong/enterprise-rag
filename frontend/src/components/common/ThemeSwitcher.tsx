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
