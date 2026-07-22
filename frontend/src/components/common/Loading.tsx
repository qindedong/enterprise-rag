/**
 * 通用 Loading 组件
 */

export function Loading({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-ink-muted">
      <svg
        className="animate-spin h-10 w-10 mb-4 text-accent"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12" cy="12" r="10"
          stroke="currentColor" strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <span className="text-sm">{text}</span>
    </div>
  )
}

/** 全屏 Loading */
export function PageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loading text="页面加载中..." />
    </div>
  )
}
