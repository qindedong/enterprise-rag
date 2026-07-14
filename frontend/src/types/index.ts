/**
 * 全局类型定义
 */

/** 统一 API 响应结构 */
export interface APIResponse<T> {
  code: number
  message: string
  data: T
}

/** 分页信息 */
export interface PageInfo {
  page: number
  page_size: number
  total: number
  total_pages: number
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[]
  page_info: PageInfo
}

/** 用户 */
export interface User {
  id: string
  username: string
  email: string
  avatar?: string
  created_at: string
}

/** 知识库 */
export interface KnowledgeBase {
  id: string
  name: string
  description: string
  owner_id: string
  chunk_size: number
  chunk_overlap: number
  doc_count: number
  chunk_count: number
  created_at: string
  updated_at: string
}

/** 知识库成员 */
export interface KBMember {
  id: string
  user_id: string
  username: string
  email: string
  role: 'admin' | 'editor' | 'viewer'
  joined_at: string
}

/** 文档 */
export interface Document {
  id: string
  kb_id: string
  title: string
  file_type: 'pdf' | 'markdown' | 'txt'
  file_size: number
  doc_status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message?: string
  chunk_count: number
  content_hash: string
  created_at: string
  updated_at: string
}

/** 文档分块 */
export interface DocumentChunk {
  id: string
  document_id: string
  chunk_index: number
  content: string
  token_count: number
  page_number?: number
}

/** 对话 */
export interface Conversation {
  id: string
  kb_id: string
  user_id: string
  title: string
  is_archived: boolean
  message_count: number
  created_at: string
  updated_at: string
}

/** 消息 */
export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  token_usage?: TokenUsage
  feedback?: 'positive' | 'negative' | null
  created_at: string
}

/** 引用 */
export interface Citation {
  index: number
  document_title: string
  chunk_id: string
  content_snippet: string
  page_number?: number
  relevance_score: number
}

/** Token 用量 */
export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

/** RAG 问答响应（非流式） */
export interface RAGResponse {
  answer: string
  citations: Citation[]
  token_usage: TokenUsage
  processing_time_ms: number
}

/** 知识库统计 */
export interface KBStats {
  doc_count: number
  chunk_count: number
  total_questions: number
}

/** 登录请求 */
export interface LoginRequest {
  email: string
  password: string
}

/** 注册请求 */
export interface RegisterRequest {
  username: string
  email: string
  password: string
}

/** Token 响应 */
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}
