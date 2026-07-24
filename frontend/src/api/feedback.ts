/**
 * 反馈分析 API
 */

import apiClient from './client'
import type { APIResponse } from '../types'

export interface FeedbackDaily {
  date: string
  positive: number
  negative: number
}

export interface NegativeFeedbackItem {
  message_id: string
  conversation_id: string
  answer_preview: string
  comment: string | null
  created_at: string
}

export interface FeedbackStats {
  total: number
  positive: number
  negative: number
  satisfaction_rate: number | null
  daily: FeedbackDaily[]
  recent_negative: NegativeFeedbackItem[]
}

/** 获取知识库反馈统计 */
export async function getFeedbackStats(
  kbId: string,
  days = 30,
): Promise<APIResponse<FeedbackStats>> {
  const res = await apiClient.get(`/knowledge-bases/${kbId}/feedback/stats`, {
    params: { days },
  })
  return res.data
}
