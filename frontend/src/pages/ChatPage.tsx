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
      const res = await createConversation({ kb_id: selectedKbId, title: '新对话' })
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

    // 流式接收
    await chatStream(
      selectedKbId,
      question,
      {
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
        <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shrink-0">
          <div className="p-4 border-b border-gray-200">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
            >
              <LucidePlus className="h-4 w-4" />
              新建对话
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {conversations.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-8">暂无对话</p>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConv(conv.id)}
                  className={`px-3 py-2.5 rounded-lg text-sm cursor-pointer truncate transition-colors mb-0.5 ${
                    activeConvId === conv.id
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
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
        <div className="h-14 border-b border-gray-200 flex items-center gap-3 px-4 bg-white shrink-0">
          {/* 侧边栏切换 */}
          <button
            onClick={() => setShowSidebar(!showSidebar)}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
          >
            {showSidebar ? <LucidePanelRightClose className="h-4 w-4" /> : <LucidePanelRightOpen className="h-4 w-4" />}
          </button>

          {/* 知识库选择器 */}
          <div className="relative">
            <button
              onClick={() => setShowKbSelector(!showKbSelector)}
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg text-sm text-gray-700 hover:bg-gray-100 transition-colors border border-gray-200"
            >
              <LucideBookOpen className="h-3.5 w-3.5 text-blue-500" />
              <span className="max-w-[120px] truncate">{currentKb?.name || '选择知识库'}</span>
              <LucideChevronDown className="h-3.5 w-3.5 text-gray-400" />
            </button>
            {showKbSelector && (
              <div className="absolute top-full left-0 mt-1 w-56 bg-white rounded-lg shadow-lg border border-gray-200 z-40 overflow-hidden">
                {kbList.map((kb) => (
                  <button
                    key={kb.id}
                    onClick={() => { setSelectedKbId(kb.id); setShowKbSelector(false); setActiveConvId(null); setMessages([]) }}
                    className={`w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 transition-colors ${
                      selectedKbId === kb.id ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
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
            className={`ml-auto p-1.5 rounded-md transition-colors ${
              showCitations ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
            }`}
          >
            <LucideFileText className="h-4 w-4" />
          </button>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 px-4">
              <LucideBookOpen className="h-16 w-16 mb-4 text-gray-300" />
              <p className="text-lg font-medium text-gray-500 mb-2">
                {currentKb ? `向「${currentKb.name}」提问` : '选择一个知识库开始对话'}
              </p>
              <p className="text-sm text-gray-400">基于知识库文档进行智能问答，每个回答都有据可查</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                  {msg.role === 'assistant' && (
                    <div className="h-8 w-8 bg-blue-500 rounded-lg flex items-center justify-center shrink-0 mt-1">
                      <span className="text-white text-xs font-bold">AI</span>
                    </div>
                  )}
                  <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-first' : ''}`}>
                    {msg.role === 'user' ? (
                      <div className="bg-blue-500 text-white rounded-2xl rounded-br-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </div>
                    ) : (
                      <div className={`bg-white border border-gray-200 rounded-2xl rounded-bl-md px-5 py-3.5 ${
                        msg.isStreaming ? 'streaming-cursor' : ''
                      }`}>
                        <div className="markdown-body text-sm">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content || '…'}
                          </ReactMarkdown>
                        </div>
                        {/* 引用 */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-gray-100">
                            <p className="text-xs text-gray-400 mb-2">
                              参考来源（{msg.citations.length}）：
                            </p>
                            <div className="space-y-1.5">
                              {msg.citations.slice(0, 5).map((c) => (
                                <div key={c.index} className="text-xs text-gray-500 flex items-start gap-2">
                                  <span className="text-blue-500 font-medium shrink-0">[{c.index}]</span>
                                  <span className="truncate">{c.document_title}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {/* 反馈按钮 */}
                        {!msg.isStreaming && msg.content && (
                          <div className="flex items-center gap-2 mt-3 pt-2 border-t border-gray-100">
                            <button className="p-1 text-gray-300 hover:text-green-500 transition-colors">
                              <LucideThumbsUp className="h-3.5 w-3.5" />
                            </button>
                            <button className="p-1 text-gray-300 hover:text-red-500 transition-colors">
                              <LucideThumbsDown className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && (
                    <div className="h-8 w-8 bg-gray-200 rounded-full flex items-center justify-center shrink-0 mt-1">
                      <span className="text-gray-500 text-xs font-bold">我</span>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* 输入区 */}
        <div className="border-t border-gray-200 bg-white p-4 shrink-0">
          <form onSubmit={handleSend} className="max-w-3xl mx-auto flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={selectedKbId ? '输入问题，Enter 发送，Shift+Enter 换行' : '请先选择知识库'}
              disabled={!selectedKbId || isGenerating}
              rows={1}
              className="flex-1 resize-none px-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={!input.trim() || !selectedKbId || isGenerating}
              className="p-3 bg-blue-500 text-white rounded-xl hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              <LucideSend className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>

      {/* ===== 引用面板 ===== */}
      {showCitations && activeCitations.length > 0 && (
        <aside className="w-72 bg-white border-l border-gray-200 overflow-y-auto shrink-0 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">引用来源</h3>
          <div className="space-y-3">
            {activeCitations.map((c) => (
              <div key={c.index} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-xs font-bold text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded">
                    [{c.index}]
                  </span>
                  <span className="text-xs font-medium text-gray-700 truncate">
                    {c.document_title}
                  </span>
                </div>
                {c.page_number && (
                  <p className="text-xs text-gray-400 mb-1">页码：{c.page_number}</p>
                )}
                <p className="text-xs text-gray-500 line-clamp-3 leading-relaxed">{c.content_snippet}</p>
                <p className="text-xs text-gray-300 mt-1">
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
