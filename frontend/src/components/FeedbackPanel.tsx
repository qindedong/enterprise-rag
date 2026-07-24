/**
 * 反馈分析面板
 *
 * 展示知识库问答反馈：满意率、近 30 天趋势、最近负反馈明细。
 */

import { useEffect, useState } from 'react'
import {
  LucideThumbsUp,
  LucideThumbsDown,
  LucideChartBar,
  LucideChevronDown,
  LucideChevronUp,
} from 'lucide-react'
import { getFeedbackStats, type FeedbackStats } from '../api/feedback'
import { Loading } from './common/Loading'

interface Props {
  kbId: string
}

export function FeedbackPanel({ kbId }: Props) {
  const [stats, setStats] = useState<FeedbackStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await getFeedbackStats(kbId)
        if (!cancelled) setStats(res.data)
      } catch {
        if (!cancelled) setStats(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [kbId])

  const maxDaily = stats
    ? Math.max(1, ...stats.daily.map((d) => d.positive + d.negative))
    : 1

  return (
    <div className="card p-5 mb-6">
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="flex items-center justify-between w-full text-left"
      >
        <h2 className="flex items-center gap-2 font-display text-base font-semibold text-ink">
          <LucideChartBar className="h-4 w-4 text-accent" />
          反馈分析
          {stats && stats.satisfaction_rate !== null && (
            <span className="meta-label font-normal">
              满意率 {stats.satisfaction_rate}%
            </span>
          )}
        </h2>
        {collapsed ? (
          <LucideChevronDown className="h-4 w-4 text-ink-muted" />
        ) : (
          <LucideChevronUp className="h-4 w-4 text-ink-muted" />
        )}
      </button>

      {!collapsed && (
        <div className="mt-4">
          {loading ? (
            <Loading text="加载反馈统计..." />
          ) : !stats || stats.total === 0 ? (
            <p className="text-sm text-ink-muted">暂无反馈数据，用户点赞/点踩后会在这里汇总。</p>
          ) : (
            <div className="space-y-5">
              {/* 总览 */}
              <div className="flex items-center gap-6">
                <div>
                  <p className="font-display text-2xl font-bold text-ink">
                    {stats.satisfaction_rate !== null ? `${stats.satisfaction_rate}%` : '—'}
                  </p>
                  <p className="meta-label">满意率（{stats.total} 条反馈）</p>
                </div>
                <div className="flex items-center gap-1.5 text-sm text-ok">
                  <LucideThumbsUp className="h-4 w-4" />
                  {stats.positive}
                </div>
                <div className="flex items-center gap-1.5 text-sm text-err">
                  <LucideThumbsDown className="h-4 w-4" />
                  {stats.negative}
                </div>
              </div>

              {/* 趋势（近 30 天，堆叠柱状） */}
              {stats.daily.length > 0 && (
                <div>
                  <p className="meta-label mb-2">近 30 天反馈趋势</p>
                  <div className="flex items-end gap-[3px] h-20">
                    {stats.daily.map((d) => {
                      const total = d.positive + d.negative
                      const posH = (d.positive / maxDaily) * 100
                      const negH = (d.negative / maxDaily) * 100
                      return (
                        <div
                          key={d.date}
                          title={`${d.date}：👍 ${d.positive} / 👎 ${d.negative}`}
                          className="flex-1 flex flex-col justify-end gap-px min-w-[4px]"
                        >
                          {d.negative > 0 && (
                            <div className="bg-err rounded-sm" style={{ height: `${negH}%` }} />
                          )}
                          {d.positive > 0 && (
                            <div className="bg-ok rounded-sm" style={{ height: `${posH}%` }} />
                          )}
                          {total === 0 && <div className="h-px bg-line-soft" />}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* 最近负反馈 */}
              {stats.recent_negative.length > 0 && (
                <div>
                  <p className="meta-label mb-2">最近负反馈（{stats.recent_negative.length}）</p>
                  <ul className="space-y-2">
                    {stats.recent_negative.map((item) => (
                      <li
                        key={item.message_id}
                        className="border border-line-soft rounded-theme p-3 text-sm"
                      >
                        <p className="text-ink line-clamp-2">{item.answer_preview}</p>
                        {item.comment && (
                          <p className="text-err mt-1">反馈备注：{item.comment}</p>
                        )}
                        <p className="meta-label mt-1">
                          {new Date(item.created_at).toLocaleString('zh-CN')}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
