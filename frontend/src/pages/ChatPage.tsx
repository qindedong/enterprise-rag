/**
 * AI 问答页面（Chat UI）
 *
 * 功能：
 * - SSE 流式接收
 * - Markdown 渲染（含代码高亮）
 * - 引用卡片
 * - 对话历史侧边栏
 * - 知识库选择器
 */

import { useState, useRef, useEffect, useCallback, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  LucideSend,
  LucideBookOpen,
  LucidePlus,
  LucidePanelRightClose,
  LucidePanelRightOpen,
  LucideFileText,
  LucideThumbsUp,
  LucideThumbsDown,
  LucideChevronDown,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { chatStream } from '../api/rag'
import { listKBs } from '../api/knowledgeBases'
import { listConversations, createConversation, listMessages } from '../api/conversations'
import type { KnowledgeBase, Conversation, Citation } from '../types'

/** 单条消息 */
interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  isStreaming?: boolean
}

export function ChatPage() {
  const [searchParams] = useSearchParams()
  const initialKbId = searchParams.get('kb') || ''

  // 知识库列表
  const [kbList, setKbList] = useState<KnowledgeBase[]>([])
  const [selectedKbId, setSelectedKbId] = useState(initialKbId)
  const [showKbSelector, setShowKbSelector] = useState(false)

  // 对话
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [showSidebar, setShowSidebar] = useState(true)

  /** 当前处理阶段状态 */
  const [status, setStatus] = useState<{ phase: string; count?: number } | null>(null)

  const STATUS_MAP: Record<string, { icon: string; text: string | ((c?: number) => string) }> = {
    searching: { icon: '🔍', text: '正在检索知识库...' },
    found: { icon: '📄', text: (c?: number) => `找到 ${c || 0} 份相关文档` },
    generating: { icon: '🧠', text: '正在生成答案...' },
  }

  // 引用面板
  const [showCitations, setShowCitations] = useState(false)
  const [activeCitations, setActiveCitations] = useState<Citation[]>([])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  /** 自动滚动到底部 */
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, scrollToBottom])

  /** 加载知识库列表 */
  useEffect(() => {
    listKBs({ page_size: 100 }).then((res) => {
      setKbList(res.data.items)
      if (!initialKbId && res.data.items.length > 0) {
        setSelectedKbId(res.data.items[0].id)
      }
    })
  }, [initialKbId])

  /** 加载对话列表 */
  const loadConversations = useCallback(async () => {
    if (!selectedKbId) return
    try {
      const res = await listConversations({ kb_id: selectedKbId, page_size: 50 })
      setConversations(res.data.items)
    } catch { /* */ }
  }, [selectedKbId])

  useEffect(() => { loadConversations() }, [loadConversations])

  /** 新建对话 */
  const handleNewChat = async () => {
    if (!selectedKbId) return
    try {
      const res = await createConversation({ kb_id: selectedKbId, question: '新对话' })
      setConversations((prev) => [res.data, ...prev])
      setActiveConvId(res.data.id)
      setMessages([])
      setShowSidebar(false)
    } catch { /* */ }
  }

  /** 切换对话 */
  const handleSelectConv = async (convId: string) => {
    setActiveConvId(convId)
    try {
      const res = await listMessages(convId, { page_size: 100 })
      setMessages(
        res.data.items.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          citations: m.citations,
        })).reverse(),
      )
    } catch { /* */ }
    setShowSidebar(false)
  }

  /** 发送消息 */
  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || !selectedKbId || isGenerating) return

    const question = input.trim()
    setInput('')

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
    }
    setMessages((prev) => [...prev, userMsg])

    // 添加 AI 占位消息
    const aiMsgId = `ai-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      { id: aiMsgId, role: 'assistant', content: '', isStreaming: true },
    ])
    setIsGenerating(true)
    setStatus({ phase: 'searching' })

    // 流式接收
    await chatStream(
      selectedKbId,
      question,
      {
        onStatus: (s) => setStatus(s),
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId ? { ...m, content: m.content + token } : m,
            ),
          )
        },
        onCitations: (citations) => {
          const typedCitations = citations as Citation[]
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId ? { ...m, citations: typedCitations } : m,
            ),
          )
          setActiveCitations(typedCitations)
        },
        onDone: () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId ? { ...m, isStreaming: false } : m,
            ),
          )
          setIsGenerating(false)
          setStatus(null)
          loadConversations()
        },
        onError: (err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: m.content || `❌ ${err.message}`, isStreaming: false }
                : m,
            ),
          )
          setIsGenerating(false)
          setStatus(null)
        },
      },
      activeConvId || undefined,
    )
  }

  /** 快捷键发送（Enter，Shift+Enter 换行） */
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const currentKb = kbList.find((k) => k.id === selectedKbId)

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* ===== 对话历史侧边栏 ===== */}
      {showSidebar && (
        <aside className="w-64 bg-surface-raised border-r border-line flex flex-col shrink-0">
          <div className="p-4 border-b border-line">
            <button
              onClick={handleNewChat}
              className="btn-primary w-full"
            >
              <LucidePlus className="h-4 w-4" />
              新建对话
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {conversations.length === 0 ? (
              <p className="meta-label text-center py-8">暂无对话</p>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConv(conv.id)}
                  className={`px-3 py-2.5 rounded-theme text-sm cursor-pointer truncate transition-colors mb-0.5 ${
                    activeConvId === conv.id
                      ? 'bg-accent/10 text-accent'
                      : 'text-ink hover:bg-line-soft'
                  }`}
                >
                  {conv.title || '新对话'}
                </div>
              ))
            )}
          </div>
        </aside>
      )}

      {/* ===== 主聊天区 ===== */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部工具栏 */}
        <div className="h-14 border-b border-line flex items-center gap-3 px-4 bg-surface-raised shrink-0">
          {/* 侧边栏切换 */}
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="p-1.5 text-ink-muted hover:text-ink hover:bg-line-soft rounded-theme transition-colors"
          >
            {showSidebar ? <LucidePanelRightClose className="h-4 w-4" /> : <LucidePanelRightOpen className="h-4 w-4" />}
          </button>

          {/* 知识库选择器 */}
          <div className="relative">
            <button
              onClick={() => setShowKbSelector(!showKbSelector)}
              className="flex items-center gap-2 px-3 py-1.5 bg-surface-raised rounded-theme text-sm text-ink hover:bg-line-soft transition-colors border border-line"
            >
              <LucideBookOpen className="h-3.5 w-3.5 text-accent" />
              <span className="max-w-[120px] truncate">{currentKb?.name || '选择知识库'}</span>
              <LucideChevronDown className="h-3.5 w-3.5 text-ink-muted" />
            </button>
            {showKbSelector && (
              <div className="absolute top-full left-0 mt-1 w-56 bg-surface-raised rounded-theme shadow-lg border border-line z-40 overflow-hidden">
                {kbList.map((kb) => (
                  <button
                    key={kb.id}
                    onClick={() => { setSelectedKbId(kb.id); setShowKbSelector(false); setActiveConvId(null); setMessages([]) }}
                    className={`w-full text-left px-4 py-2.5 text-sm hover:bg-line-soft transition-colors ${
                      selectedKbId === kb.id ? 'bg-accent/10 text-accent' : 'text-ink'
                    }`}
                  >
                    {kb.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 引用开关 */}
          <button
            onClick={() => setShowCitations(!showCitations)}
            className={`ml-auto p-1.5 rounded-theme transition-colors ${
              showCitations ? 'bg-accent/10 text-accent' : 'text-ink-muted hover:text-ink hover:bg-line-soft'
            }`}
          >
            <LucideFileText className="h-4 w-4" />
          </button>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-ink-muted px-4">
              <LucideBookOpen className="h-16 w-16 mb-4 text-ink-muted" />
              <p className="text-lg font-medium text-ink-muted mb-2">
                {currentKb ? `向「${currentKb.name}」提问` : '选择一个知识库开始对话'}
              </p>
              <p className="text-sm text-ink-muted">基于知识库文档进行智能问答，每个回答都有据可查</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  {msg.role === 'assistant' && (
                    <div className="h-8 w-8 bg-accent rounded-theme flex items-center justify-center shrink-0 mt-1">
                      <span className="text-accent-ink text-xs font-bold">AI</span>
                    </div>
                  )}
                  <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-first' : ''}`}>
                    {msg.role === 'user' ? (
                      <div className="bg-accent text-accent-ink rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </div>
                    ) : (
                      <div className={`bg-surface-raised border border-line rounded-2xl rounded-bl-md px-5 py-3.5 ${
                        msg.isStreaming && msg.content ? 'streaming-cursor' : ''
                      }`}>
                        {msg.isStreaming && !msg.content && status ? (
                          <div className="flex items-center gap-2 text-sm text-ink-muted py-1">
                            <span>{STATUS_MAP[status.phase]?.icon || '⏳'}</span>
                            <span>
                              {(() => {
                                const statusText = STATUS_MAP[status.phase]?.text
                                return typeof statusText === 'function'
                                  ? statusText(status.count)
                                  : statusText || '处理中...'
                              })()}
                            </span>
                            <span className="animate-spin text-xs text-ink-muted">●</span>
                          </div>
                        ) : (
                          <div className="markdown-body text-sm">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.content || '…'}
                            </ReactMarkdown>
                          </div>
                        )}
                        {/* 引用 */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-line-soft">
                            <p className="meta-label mb-2">
                              参考来源（{msg.citations.length}）：
                            </p>
                            <div className="space-y-1.5">
                              {msg.citations.slice(0, 5).map((c) => (
                                <div key={c.index} className="text-xs text-ink-muted flex items-start gap-2">
                                  <span className="text-accent font-medium shrink-0">[{c.index}]</span>
                                  <span className="truncate">{c.document_title}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {/* 反馈按钮 */}
                        {!msg.isStreaming && msg.content && (
                          <div className="flex items-center gap-2 mt-3 pt-2 border-t border-line-soft">
                            <button className="p-1 text-ink-muted hover:text-ok transition-colors">
                              <LucideThumbsUp className="h-3.5 w-3.5" />
                            </button>
                            <button className="p-1 text-ink-muted hover:text-err transition-colors">
                              <LucideThumbsDown className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="h-8 w-8 bg-line-soft rounded-full flex items-center justify-center shrink-0 mt-1">
                      <span className="text-ink-muted text-xs font-bold">我</span>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 输入区 */}
        <div className="border-t border-line bg-surface-raised p-4 shrink-0">
          <form onSubmit={handleSend} className="max-w-3xl mx-auto flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedKbId ? '输入问题，Enter 发送，Shift+Enter 换行' : '请先选择知识库'}
              disabled={!selectedKbId || isGenerating}
              rows={1}
              className="flex-1 resize-none input disabled:bg-line-soft disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={!input.trim() || !selectedKbId || isGenerating}
              className="btn-primary shrink-0"
            >
              <LucideSend className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>

      {/* ===== 引用面板 ===== */}
      {showCitations && activeCitations.length > 0 && (
        <aside className="w-72 bg-surface-raised border-l border-line overflow-y-auto shrink-0 p-4">
          <h3 className="text-sm font-semibold text-ink mb-3">引用来源</h3>
          <div className="space-y-3">
            {activeCitations.map((c) => (
              <div key={c.index} className="bg-line-soft rounded-theme p-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-bold text-accent bg-accent/10 px-1.5 py-0.5 rounded-theme">
                    [{c.index}]
                  </span>
                  <span className="text-xs font-medium text-ink truncate">
                    {c.document_title}
                  </span>
                </div>
                {c.page_number && (
                  <p className="meta-label mb-1">页码：{c.page_number}</p>
                )}
                <p className="text-xs text-ink-muted line-clamp-3 leading-relaxed">{c.content_snippet}</p>
                <p className="meta-label mt-1">
                  相关度：{(c.relevance_score * 100).toFixed(0)}%
                </p>
              </div>
            ))}
          </div>
        </aside>
      )}
    </div>
  )
}
