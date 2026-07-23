/**
 * 对话相关 API
 */

import apiClient from './client'
import type { APIResponse, Conversation, Message, PaginatedResponse } from '../types'

/** 创建对话 */
export async function createConversation(data: {
  kb_id: string
  question: string
}): Promise<APIResponse<Conversation>> {
  const res = await apiClient.post(`/knowledge-bases/${data.kb_id}/conversations`, null, {
    params: { question: data.question },
  })
  return res.data
}

/** 获取对话列表 */
export async function listConversations(params?: {
  kb_id?: string
  page?: number
  page_size?: number
}): Promise<APIResponse<PaginatedResponse<Conversation>>> {
  const res = await apiClient.get('/conversations', { params })
  return res.data
}

/** 获取对话详情 */
export async function getConversation(id: string): Promise<APIResponse<Conversation>> {
  const res = await apiClient.get(`/conversations/${id}`)
  return res.data
}

/** 获取对话消息列表 */
export async function listMessages(
  convId: string,
  params?: { page?: number; page_size?: number },
): Promise<APIResponse<PaginatedResponse<Message>>> {
  const res = await apiClient.get(`/conversations/${convId}/messages`, { params })
  return res.data
}

/** 删除对话 */
export async function deleteConversation(id: string): Promise<APIResponse<null>> {
  const res = await apiClient.delete(`/conversations/${id}`)
  return res.data
}

/** 提交消息反馈 */
export async function submitFeedback(
  messageId: string,
  feedback: 'positive' | 'negative' | null,
): Promise<APIResponse<null>> {
  const res = await apiClient.post(`/messages/${messageId}/feedback`, { feedback })
  return res.data
}
