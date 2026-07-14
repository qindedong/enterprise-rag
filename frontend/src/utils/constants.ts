/**
 * 全局常量
 */

/** API 基础路径（开发环境通过 Vite proxy 转发） */
export const API_BASE = '/api/v1'

/** Token 存储 key */
export const ACCESS_TOKEN_KEY = 'rag_access_token'
export const REFRESH_TOKEN_KEY = 'rag_refresh_token'

/** 文档状态中文映射 */
export const DOC_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'bg-yellow-100 text-yellow-800' },
  processing: { label: '处理中', color: 'bg-blue-100 text-blue-800' },
  completed: { label: '已完成', color: 'bg-green-100 text-green-800' },
  failed: { label: '失败', color: 'bg-red-100 text-red-800' },
}

/** 文件类型图标映射 */
export const FILE_TYPE_ICONS: Record<string, string> = {
  pdf: '📄',
  markdown: '📝',
  txt: '📃',
}

/** 知识库角色中文映射 */
export const KB_ROLE_MAP: Record<string, string> = {
  admin: '管理员',
  editor: '编辑者',
  viewer: '观察者',
}
