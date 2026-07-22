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
