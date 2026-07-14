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
      <LucideAlertTriangle className="h-16 w-16 text-red-400 mb-4" />
      <p className="text-lg font-medium text-gray-700 mb-2">出错了</p>
      <p className="text-sm text-gray-500 mb-6 max-w-sm text-center">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm"
        >
          重试
        </button>
      )}
    </div>
  )
}
