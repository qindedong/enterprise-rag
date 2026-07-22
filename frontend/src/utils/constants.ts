/**
 * 全局常量
 */

/** API 基础路径（开发环境通过 Vite proxy 转发） */
export const API_BASE = '/api/v1'

/** Token 存储 key */
export const ACCESS_TOKEN_KEY = 'rag_access_token'
export const REFRESH_TOKEN_KEY = 'rag_refresh_token'

/** 文档状态中文映射（颜色用语义状态类，随主题切换） */
export const DOC_STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待处理', color: 'bg-warn-soft text-warn' },
  processing: { label: '处理中', color: 'bg-info-soft text-info' },
  completed: { label: '已完成', color: 'bg-ok-soft text-ok' },
  failed: { label: '失败', color: 'bg-err-soft text-err' },
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
