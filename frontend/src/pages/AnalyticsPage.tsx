/**
 * 数据分析看板页
 *
 * 跨知识库总览：总量卡片、近 30 天问答趋势、各知识库明细表。
 */

import { useEffect, useState } from 'react'
import {
  LucideChartBar,
  LucideDatabase,
  LucideFileText,
  LucideMessageSquare,
  LucideThumbsUp,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getAnalyticsOverview, type AnalyticsOverview } from '../api/analytics'
import { Loading } from '../components/common/Loading'
import { ErrorState } from '../components/common/ErrorState'
import { Empty } from '../components/common/Empty'

export function AnalyticsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<AnalyticsOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await getAnalyticsOverview()
      setData(res.data)
    } catch {
      setError('加载数据看板失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <Loading text="加载数据看板..." />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!data) return <Empty title="暂无数据" />

  const { totals, daily_questions, kb_breakdown } = data
  const maxDaily = Math.max(1, ...daily_questions.map((d) => d.count))

  const cards = [
    { label: '知识库', value: totals.kb_count, icon: LucideDatabase },
    { label: '文档', value: totals.doc_count, icon: LucideFileText },
    { label: '问答次数', value: totals.question_count, icon: LucideMessageSquare },
    {
      label: '满意率',
      value: totals.satisfaction_rate !== null ? `${totals.satisfaction_rate}%` : '—',
      icon: LucideThumbsUp,
    },
  ]

  return (
    <div className="p-4 lg:p-6 max-w-6xl">
      <h1 className="flex items-center gap-2 font-display text-xl font-bold text-ink mb-6">
        <LucideChartBar className="h-5 w-5 text-accent" />
        数据分析看板
      </h1>

      {/* 总量卡片 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {cards.map(({ label, value, icon: Icon }) => (
          <div key={label} className="card p-4">
            <div className="flex items-center gap-2 meta-label mb-2">
              <Icon className="h-4 w-4" />
              {label}
            </div>
            <p className="font-display text-2xl font-bold text-ink">{value}</p>
          </div>
        ))}
      </div>

      {/* 问答趋势 */}
      <div className="card p-5 mb-6">
        <h2 className="font-display text-base font-semibold text-ink mb-4">近 30 天问答趋势</h2>
        {daily_questions.length === 0 ? (
          <p className="text-sm text-ink-muted">近 30 天暂无问答记录</p>
        ) : (
          <div className="flex items-end gap-[3px] h-32">
            {daily_questions.map((d) => (
              <div
                key={d.date}
                title={`${d.date}：${d.count} 次`}
                className="flex-1 flex flex-col justify-end min-w-[4px]"
              >
                <div
                  className="bg-accent rounded-sm transition-all"
                  style={{ height: `${(d.count / maxDaily) * 100}%` }}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 各知识库明细 */}
      <div className="card p-5">
        <h2 className="font-display text-base font-semibold text-ink mb-4">各知识库明细</h2>
        {kb_breakdown.length === 0 ? (
          <p className="text-sm text-ink-muted">暂无知识库</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left meta-label border-b border-line-soft">
                  <th className="pb-2 font-normal">知识库</th>
                  <th className="pb-2 font-normal text-right">文档数</th>
                  <th className="pb-2 font-normal text-right">问答次数</th>
                  <th className="pb-2 font-normal text-right">满意率</th>
                </tr>
              </thead>
              <tbody>
                {kb_breakdown.map((kb) => (
                  <tr
                    key={kb.kb_id}
                    onClick={() => navigate(`/kbs/${kb.kb_id}`)}
                    className="border-b border-line-soft last:border-0 cursor-pointer hover:bg-line-soft/50 transition-colors"
                  >
                    <td className="py-2.5 text-ink">{kb.name}</td>
                    <td className="py-2.5 text-right text-ink-muted">{kb.doc_count}</td>
                    <td className="py-2.5 text-right text-ink-muted">{kb.question_count}</td>
                    <td className="py-2.5 text-right">
                      {kb.satisfaction_rate !== null ? (
                        <span
                          className={
                            kb.satisfaction_rate >= 80
                              ? 'text-ok'
                              : kb.satisfaction_rate >= 50
                                ? 'text-ink'
                                : 'text-err'
                          }
                        >
                          {kb.satisfaction_rate}%
                        </span>
                      ) : (
                        <span className="text-ink-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
