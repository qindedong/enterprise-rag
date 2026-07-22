/**
 * 空状态组件
 */

import { LucideFileX } from 'lucide-react'

interface EmptyProps {
  title?: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
}

export function Empty({
  title = '暂无数据',
  description = '',
  icon,
  action,
}: EmptyProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-ink-muted">
      <div className="mb-4">
        {icon || <LucideFileX className="h-16 w-16" />}
      </div>
      <p className="text-lg font-medium text-ink mb-2">{title}</p>
      {description && (
        <p className="text-sm text-ink-muted mb-4 max-w-sm text-center">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
