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
