/**
 * 知识库相关 API
 */

import apiClient from './client'
import type { APIResponse, KnowledgeBase, KBStats, KBMember, PaginatedResponse } from '../types'

/** 创建知识库 */
export async function createKB(data: {
  name: string
  description?: string
  chunk_size?: number
  chunk_overlap?: number
}): Promise<APIResponse<KnowledgeBase>> {
  const res = await apiClient.post('/knowledge-bases', data)
  return res.data
}

/** 获取知识库列表 */
export async function listKBs(params?: {
  page?: number
  page_size?: number
  keyword?: string
}): Promise<APIResponse<PaginatedResponse<KnowledgeBase>>> {
  const res = await apiClient.get('/knowledge-bases', { params })
  return res.data
}

/** 获取知识库详情 */
export async function getKB(id: string): Promise<APIResponse<KnowledgeBase>> {
  const res = await apiClient.get(`/knowledge-bases/${id}`)
  return res.data
}

/** 更新知识库 */
export async function updateKB(
  id: string,
  data: { name?: string; description?: string },
): Promise<APIResponse<KnowledgeBase>> {
  const res = await apiClient.put(`/knowledge-bases/${id}`, data)
  return res.data
}

/** 删除知识库 */
export async function deleteKB(id: string): Promise<APIResponse<null>> {
  const res = await apiClient.delete(`/knowledge-bases/${id}`)
  return res.data
}

/** 获取知识库统计 */
export async function getKBStats(id: string): Promise<APIResponse<KBStats>> {
  const res = await apiClient.get(`/knowledge-bases/${id}/stats`)
  return res.data
}

/** 获取知识库成员列表 */
export async function listKBMembers(
  kbId: string,
): Promise<APIResponse<PaginatedResponse<KBMember>>> {
  const res = await apiClient.get(`/knowledge-bases/${kbId}/members`)
  return res.data
}

/** 添加知识库成员 */
export async function addKBMember(
  kbId: string,
  data: { user_id: string; role: string },
): Promise<APIResponse<KBMember>> {
  const res = await apiClient.post(`/knowledge-bases/${kbId}/members`, data)
  return res.data
}

/** 移除知识库成员 */
export async function removeKBMember(
  kbId: string,
  userId: string,
): Promise<APIResponse<null>> {
  const res = await apiClient.delete(`/knowledge-bases/${kbId}/members/${userId}`)
  return res.data
}
