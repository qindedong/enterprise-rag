/**
 * 文档状态标签
 */

import { DOC_STATUS_MAP } from '../../utils/constants'

export function DocStatusBadge({ status }: { status: string }) {
  const info = DOC_STATUS_MAP[status] || { label: status, color: 'bg-gray-100 text-gray-800' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${info.color}`}>
      {info.label}
    </span>
  )
}
