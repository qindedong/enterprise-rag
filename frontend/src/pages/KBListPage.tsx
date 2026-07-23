/**
 * 知识库列表页面
 *
 * 功能：
 * - 卡片列表展示
 * - 搜索
 * - 创建弹窗
 */

import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { LucidePlus, LucideSearch, LucideDatabase, LucideFileText, LucideHash } from 'lucide-react'
import { listKBs, createKB } from '../api/knowledgeBases'
import { Loading } from '../components/common/Loading'
import { Empty } from '../components/common/Empty'
import { ErrorState } from '../components/common/ErrorState'
import { Pagination } from '../components/common/Pagination'
import { useDebounce } from '../hooks'
import type { KnowledgeBase, PageInfo } from '../types'

export function KBListPage() {
  const navigate = useNavigate()
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [pageInfo, setPageInfo] = useState<PageInfo | null>(null)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 创建弹窗
  const [showModal, setShowModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState('')

  const debouncedKeyword = useDebounce(keyword, 300)

  const fetchList = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await listKBs({ page, page_size: 12, keyword: debouncedKeyword || undefined })
      setKbList(res.data.items)
      setPageInfo(res.data.page_info)
    } catch {
      setError('获取知识库列表失败')
    } finally {
      setLoading(false)
    }
  }, [page, debouncedKeyword])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  // 搜索时重置到第一页
  useEffect(() => {
    setPage(1)
  }, [debouncedKeyword])

  const handleCreate = async () => {
    if (!newName.trim()) { setCreateError('请输入知识库名称'); return }
    setCreateLoading(true)
    setCreateError('')
    try {
      const res = await createKB({ name: newName.trim(), description: newDesc.trim() || undefined })
      setShowModal(false)
      setNewName('')
      setNewDesc('')
      navigate(`/kbs/${res.data.id}`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      setCreateError(msg || '创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  return (
    <div className="p-4 lg:p-6">
      {/* 顶部搜索栏 */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-6">
        <div className="relative flex-1 w-full">
          <LucideSearch className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-muted" />
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="搜索知识库..."
            aria-label="搜索知识库"
            className="input pl-9"
          />
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="btn-primary shrink-0"
        >
          <LucidePlus className="h-4 w-4" />
          创建知识库
        </button>
      </div>

      {/* 内容区 */}
      {loading ? (
        <Loading text="加载知识库..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchList} />
      ) : kbList.length === 0 ? (
        <Empty
          title="暂无知识库"
          description={keyword ? '没有匹配的知识库，试试其他关键词' : '点击右上角「创建知识库」开始使用'}
          action={
            !keyword && (
              <button
                onClick={() => setShowModal(true)}
                className="btn-primary"
              >
                创建第一个知识库
              </button>
            )
          }
        />
      ) : (
        <>
          {/* 卡片网格 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {kbList.map((kb) => (
              <div
                key={kb.id}
                onClick={() => navigate(`/kbs/${kb.id}`)}
                className="card p-5 cursor-pointer hover:border-accent transition-colors"
              >
                <div className="flex items-start gap-3 mb-3">
                  <div className="h-10 w-10 bg-accent/10 rounded-theme flex items-center justify-center shrink-0">
                    <LucideDatabase className="h-5 w-5 text-accent" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-semibold text-ink truncate">{kb.name}</h3>
                    {kb.description && (
                      <p className="meta-label mt-0.5 line-clamp-2">{kb.description}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-4 meta-label">
                  <span className="flex items-center gap-1">
                    <LucideFileText className="h-3 w-3" />
                    {kb.doc_count || 0} 个文档
                  </span>
                  <span className="flex items-center gap-1">
                    <LucideHash className="h-3 w-3" />
                    {kb.chunk_count || 0} 个分块
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* 分页 */}
          {pageInfo && pageInfo.total_pages > 1 && (
            <div className="mt-6 card overflow-hidden">
              <Pagination pageInfo={pageInfo} onPageChange={setPage} />
            </div>
          )}
        </>
      )}

      {/* ===== 创建弹窗 ===== */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShowModal(false)} />
          <div className="relative card w-full max-w-md p-6">
            <h2 className="font-display text-lg font-semibold text-ink mb-4">创建知识库</h2>
            {createError && (
              <div role="alert" className="bg-err-soft text-err text-sm px-3 py-2 rounded-theme mb-3">{createError}</div>
            )}
            <div className="space-y-3">
              <div>
                <label htmlFor="kb-name" className="block text-sm font-medium text-ink mb-1">名称 *</label>
                <input
                  id="kb-name"
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="例如：员工手册、技术文档"
                  className="input"
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                />
              </div>
              <div>
                <label htmlFor="kb-desc" className="block text-sm font-medium text-ink mb-1">描述（可选）</label>
                <textarea
                  id="kb-desc"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="简单描述这个知识库的内容..."
                  rows={3}
                  className="input resize-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-5">
              <button
                onClick={() => { setShowModal(false); setCreateError('') }}
                className="btn-ghost"
              >
                取消
              </button>
              <button
                onClick={handleCreate}
                disabled={createLoading}
                className="btn-primary"
              >
                {createLoading ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
