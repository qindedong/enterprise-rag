/**
 * RAG 问答相关 API
 */

import { API_BASE, ACCESS_TOKEN_KEY } from '../utils/constants'
import apiClient from './client'
import type { APIResponse, RAGResponse } from '../types'

/** SSE 流式 RAG 问答 — 返回 EventSource 实例 */
export function createChatStream(
  kbId: string,
  question: string,
  conversationId?: string,
): EventSource {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  const params = new URLSearchParams({
    question,
    ...(conversationId && { conversation_id: conversationId }),
  })

  const url = `${API_BASE}/knowledge-bases/${kbId}/chat?${params.toString()}`

  // EventSource 不支持自定义请求头，改用 fetch + ReadableStream
  // 这里用 EventSource polyfill 模式：URL 中带 token
  const urlWithToken = `${url}&token=${token}`
  return new EventSource(urlWithToken)
}

/** 非流式 RAG 问答 */
export async function chatSync(
  kbId: string,
  question: string,
  conversationId?: string,
): Promise<APIResponse<RAGResponse>> {
  const res = await apiClient.post(`/knowledge-bases/${kbId}/chat/sync`, {
    question,
    ...(conversationId && { conversation_id: conversationId }),
  })
  return res.data
}

/**
 * SSE 流式 RAG 问答 — 基于 fetch + ReadableStream
 *
 * 回调：
 *   onStatus(status: {phase: string, count?: number}) — 处理阶段状态
 *   onToken(token: string)          — 收到文本片段
 *   onCitations(citations: Citation[]) — 收到引用列表
 *   onDone(meta: object)            — 完成
 *   onError(err: {code, message})   — 错误
 */
export async function chatStream(
  kbId: string,
  question: string,
  callbacks: {
    onStatus?: (status: { phase: string; count?: number }) => void
    onToken: (token: string) => void
    onCitations: (citations: unknown[]) => void
    onDone: (meta: Record<string, unknown>) => void
    onError: (err: { code: number; message: string }) => void
  },
  conversationId?: string,
): Promise<void> {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY)
  if (!token) {
    callbacks.onError({ code: 401, message: '请先登录' })
    return
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => {
    controller.abort()
    callbacks.onError({ code: 408, message: '请求超时' })
  }, 60000)

  try {
    const response = await fetch(
      `${API_BASE}/knowledge-bases/${kbId}/chat`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          question,
          ...(conversationId && { conversation_id: conversationId }),
        }),
        signal: controller.signal,
      },
    )

    if (!response.ok) {
      callbacks.onError({ code: response.status, message: `请求失败 (${response.status})` })
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      callbacks.onError({ code: 500, message: '无法读取响应流' })
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let currentEvent = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            switch (currentEvent) {
              case 'status':
                callbacks.onStatus?.(data)
                break
              case 'token':
                callbacks.onToken(data.content)
                break
              case 'citation':
                callbacks.onCitations(data.citations || [])
                break
              case 'done':
                callbacks.onDone(data)
                break
              case 'error':
                callbacks.onError(data)
                break
            }
          } catch {
            // 非 JSON 行，跳过
          }
        }
      }
    }
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      callbacks.onError({ code: 408, message: '请求超时' })
    } else {
      callbacks.onError({
        code: 500,
        message: err instanceof Error ? err.message : '网络错误',
      })
    }
  } finally {
    clearTimeout(timeout)
  }
}
