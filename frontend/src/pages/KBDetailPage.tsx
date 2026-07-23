/**
 * 知识库详情页面
 *
 * 功能：
 * - 文档列表 + 统计
 * - 文档上传（拖拽 + 进度条）
 * - 文档搜索/筛选
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  LucideUpload,
  LucideFileText,
  LucideHash,
  LucideMessageSquare,
  LucideTrash2,
  LucideRefreshCw,
  LucideArrowLeft,
} from 'lucide-react'
import { getKB, getKBStats, deleteKB } from '../api/knowledgeBases'
import { listDocuments, uploadDocument, deleteDocument, reprocessDocument } from '../api/documents'
import { Loading } from '../components/common/Loading'
import { Empty } from '../components/common/Empty'
import { ErrorState } from '../components/common/ErrorState'
import { Pagination } from '../components/common/Pagination'
import { DocStatusBadge } from '../components/common/DocStatusBadge'
import { useDebounce } from '../hooks'
import { FILE_TYPE_ICONS, DOC_STATUS_MAP } from '../utils/constants'
import type { KnowledgeBase, KBStats, Document, PageInfo } from '../types'

/** 允许的文件扩展名 */
const ALLOWED_EXTENSIONS = ['pdf', 'md', 'txt']

export function KBDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // KB 信息
  const [kb, setKb] = useState<KnowledgeBase | null>(null)
  const [stats, setStats] = useState<KBStats | null>(null)
  const [kbLoading, setKbLoading] = useState(true)
  const [kbError, setKbError] = useState<string | null>(null)

  // 文档列表
  const [docs, setDocs] = useState<Document[]>([])
  const [pageInfo, setPageInfo] = useState<PageInfo | null>(null)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [docsLoading, setDocsLoading] = useState(false)

  // 上传
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragOver, setDragOver] = useState(false)
  const [uploadError, setUploadError] = useState('')

  // 删除 KB
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const debouncedKeyword = useDebounce(keyword, 300)

  /** 加载 KB 信息 */
  const loadKB = useCallback(async () => {
    if (!id) return
    setKbLoading(true)
    setKbError(null)
    try {
      const [kbRes, statsRes] = await Promise.all([
        getKB(id),
        getKBStats(id).catch(() => null),
      ])
      setKb(kbRes.data)
      if (statsRes) setStats(statsRes.data)
    } catch {
      setKbError('获取知识库信息失败')
    } finally {
      setKbLoading(false)
    }
  }, [id])

  /** 加载文档列表 */
  const loadDocs = useCallback(async () => {
    if (!id) return
    setDocsLoading(true)
    try {
      const res = await listDocuments(id, {
        page,
        page_size: 20,
        keyword: debouncedKeyword || undefined,
        status: statusFilter || undefined,
      })
      setDocs(res.data.items)
      setPageInfo(res.data.page_info)
    } catch {
      // 静默处理
    } finally {
      setDocsLoading(false)
    }
  }, [id, page, debouncedKeyword, statusFilter])

  useEffect(() => { loadKB() }, [loadKB])
  useEffect(() => { loadDocs() }, [loadDocs])

  /** 处理文件上传 */
  const handleUpload = async (file: File) => {
    if (!id) return
    // 格式校验
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError('仅支持 PDF、Markdown、TXT 格式')
      return
    }

    setUploadError('')
    setUploading(true)
    setUploadProgress(0)
    try {
      await uploadDocument(id, file, setUploadProgress)
      setUploadProgress(100)
      loadDocs()
      loadKB()
    } catch {
      setUploadError('上传失败，请重试')
    } finally {
      setUploading(false)
      setTimeout(() => setUploadProgress(0), 2000)
    }
  }

  /** 删除文档 */
  const handleDeleteDoc = async (docId: string) => {
    if (!confirm('确定删除该文档？')) return
    try {
      await deleteDocument(docId)
      loadDocs()
      loadKB()
    } catch { /* */ }
  }

  /** 重处理文档 */
  const handleReprocess = async (docId: string) => {
    try {
      await reprocessDocument(docId)
      loadDocs()
    } catch { /* */ }
  }

  /** 删除知识库 */
  const handleDeleteKB = async () => {
    if (!id || !confirm('确定删除该知识库？所有文档将被永久删除！')) return
    setDeleting(true)
    try {
      await deleteKB(id)
      navigate('/kbs', { replace: true })
    } catch {
      setDeleting(false)
    }
  }

  if (kbLoading) return <Loading text="加载知识库..." />
  if (kbError) return <ErrorState message={kbError} onRetry={loadKB} />
  if (!kb) return <ErrorState message="知识库不存在" />

  return (
    <div className="p-4 lg:p-6 max-w-6xl">
      {/* 返回按钮 */}
      <button
        onClick={() => navigate('/kbs')}
        className="flex items-center gap-2 text-sm text-ink-muted hover:text-ink mb-4"
      >
        <LucideArrowLeft className="h-4 w-4" />
        返回知识库列表
      </button>

      {/* KB 头部 */}
      <div className="card p-5 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-display text-xl font-bold text-ink">{kb.name}</h1>
            {kb.description && (
              <p className="meta-label mt-1">{kb.description}</p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/chat?kb=${id}`)}
              className="btn-primary"
            >
              <LucideMessageSquare className="h-4 w-4" />
              AI 问答
            </button>
            <button
              onClick={() => setDeleteConfirm(true)}
              className="p-2 text-ink-muted hover:text-err hover:bg-err-soft rounded-theme transition-colors"
              title="删除知识库"
            >
              <LucideTrash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
        {/* 统计 */}
        {stats && (
          <div className="flex items-center gap-5 mt-4 pt-4 border-t border-line-soft">
            <div className="flex items-center gap-1.5 meta-label">
              <LucideFileText className="h-4 w-4" />
              {stats.doc_count} 个文档
            </div>
            <div className="flex items-center gap-1.5 meta-label">
              <LucideHash className="h-4 w-4" />
              {stats.chunk_count} 个分块
            </div>
            <div className="flex items-center gap-1.5 meta-label">
              <LucideMessageSquare className="h-4 w-4" />
              {stats.total_questions} 次问答
            </div>
          </div>
        )}
      </div>

      {/* ===== 上传区 ===== */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          const file = e.dataTransfer.files[0]
          if (file) handleUpload(file)
        }}
        onClick={() => fileInputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-theme p-6 mb-6 text-center cursor-pointer transition-colors
          ${dragOver ? 'border-accent bg-accent/10' : 'border-line hover:border-accent hover:bg-line-soft'}
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.md,.txt"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleUpload(file)
            e.target.value = ''
          }}
        />
        {uploading ? (
          <div className="space-y-3">
            <LucideUpload className="h-8 w-8 mx-auto text-accent animate-bounce" />
            <p className="text-sm text-ink-muted">正在上传处理中...</p>
            <div className="w-full max-w-xs mx-auto bg-line-soft rounded-full h-2">
              <div
                className="h-2 bg-accent rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="meta-label">{uploadProgress}%</p>
          </div>
        ) : (
          <div className="space-y-2">
            <LucideUpload className="h-8 w-8 mx-auto text-ink-muted" />
            <p className="text-sm text-ink-muted">
              <span className="text-accent font-medium">点击上传</span> 或拖拽文件到此处
            </p>
            <p className="meta-label">支持 PDF、Markdown、TXT 格式</p>
          </div>
        )}
        {uploadError && (
          <p role="alert" className="text-sm text-err mt-2">{uploadError}</p>
        )}
      </div>

      {/* ===== 文档列表筛选 ===== */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          value={keyword}
          onChange={(e) => { setKeyword(e.target.value); setPage(1) }}
          placeholder="搜索文档..."
          aria-label="搜索文档"
          className="input flex-1"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          aria-label="按状态筛选"
          className="px-3 py-2 bg-surface-raised border border-line rounded-theme text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent"
        >
          <option value="">全部状态</option>
          {Object.entries(DOC_STATUS_MAP).map(([k, v]) => (
            <option key={k} value={k}>{v.label}</option>
          ))}
        </select>
      </div>

      {/* ===== 文档列表 ===== */}
      {docsLoading ? (
        <Loading text="加载文档..." />
      ) : docs.length === 0 ? (
        <Empty
          title="暂无文档"
          description="拖拽文件到上方区域或点击上传"
          icon={<LucideFileText className="h-12 w-12" />}
        />
      ) : (
        <div className="card overflow-hidden">
          <div className="divide-y divide-line-soft">
            {docs.map((doc) => (
              <div key={doc.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-line-soft transition-colors">
                {/* 图标 */}
                <span className="text-2xl">{FILE_TYPE_ICONS[doc.file_type] || '📄'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-ink truncate">{doc.title}</p>
                    <DocStatusBadge status={doc.doc_status} />
                  </div>
                  <p className="meta-label mt-0.5">
                    {doc.file_type.toUpperCase()} · {(doc.file_size / 1024).toFixed(1)} KB · {doc.chunk_count} 个分块 · {new Date(doc.created_at).toLocaleDateString('zh-CN')}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {doc.doc_status === 'failed' && (
                    <button
                      onClick={() => handleReprocess(doc.id)}
                      className="p-1.5 text-ink-muted hover:text-accent hover:bg-accent/10 rounded-theme transition-colors"
                      title="重新处理"
                    >
                      <LucideRefreshCw className="h-4 w-4" />
                    </button>
                  )}
                  <button
                    onClick={() => handleDeleteDoc(doc.id)}
                    className="p-1.5 text-ink-muted hover:text-err hover:bg-err-soft rounded-theme transition-colors"
                    title="删除"
                  >
                    <LucideTrash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          {pageInfo && (
            <Pagination pageInfo={pageInfo} onPageChange={setPage} />
          )}
        </div>
      )}

      {/* ===== 删除 KB 确认弹窗 ===== */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDeleteConfirm(false)} />
          <div className="relative card w-full max-w-sm p-6">
            <h2 className="font-display text-lg font-semibold text-ink mb-2">删除知识库</h2>
            <p className="text-sm text-ink-muted mb-4">
              确定要删除「{kb.name}」吗？该知识库下的所有文档和问答记录将被永久删除，且不可恢复。
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteConfirm(false)}
                className="btn-ghost"
              >
                取消
              </button>
              <button
                onClick={handleDeleteKB}
                disabled={deleting}
                className="bg-err text-accent-ink rounded-theme px-4 py-2 text-sm font-medium transition-all hover:brightness-110 disabled:opacity-60"
              >
                {deleting ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
