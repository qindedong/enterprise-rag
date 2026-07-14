/**
 * 文档相关 API
 */

import apiClient from './client'
import type { APIResponse, Document, DocumentChunk, PaginatedResponse } from '../types'

/** 上传文档 */
export async function uploadDocument(
  kbId: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<APIResponse<Document>> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await apiClient.post(`/knowledge-bases/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (event.total && onProgress) {
        onProgress(Math.round((event.loaded * 100) / event.total))
      }
    },
  })
  return res.data
}

/** 获取文档列表 */
export async function listDocuments(
  kbId: string,
  params?: {
    page?: number
    page_size?: number
    keyword?: string
    status?: string
    file_type?: string
  },
): Promise<APIResponse<PaginatedResponse<Document>>> {
  const res = await apiClient.get(`/knowledge-bases/${kbId}/documents`, { params })
  return res.data
}

/** 获取文档详情 */
export async function getDocument(id: string): Promise<APIResponse<Document>> {
  const res = await apiClient.get(`/documents/${id}`)
  return res.data
}

/** 获取文档分块 */
export async function getDocumentChunks(
  id: string,
  params?: { page?: number; page_size?: number },
): Promise<APIResponse<PaginatedResponse<DocumentChunk>>> {
  const res = await apiClient.get(`/documents/${id}/chunks`, { params })
  return res.data
}

/** 删除文档 */
export async function deleteDocument(id: string): Promise<APIResponse<null>> {
  const res = await apiClient.delete(`/documents/${id}`)
  return res.data
}

/** 重新处理文档 */
export async function reprocessDocument(id: string): Promise<APIResponse<Document>> {
  const res = await apiClient.post(`/documents/${id}/reprocess`)
  return res.data
}
