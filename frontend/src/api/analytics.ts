/**
 * 数据分析 API
 */

import apiClient from './client'
import type { APIResponse } from '../types'

export interface AnalyticsTotals {
  kb_count: number
  doc_count: number
  conversation_count: number
  question_count: number
  positive: number
  negative: number
  satisfaction_rate: number | null
}

export interface DailyQuestion {
  date: string
  count: number
}

export interface KBBreakdown {
  kb_id: string
  name: string
  doc_count: number
  question_count: number
  satisfaction_rate: number | null
}

export interface AnalyticsOverview {
  totals: AnalyticsTotals
  daily_questions: DailyQuestion[]
  kb_breakdown: KBBreakdown[]
}

/** 获取数据总览 */
export async function getAnalyticsOverview(
  days = 30,
): Promise<APIResponse<AnalyticsOverview>> {
  const res = await apiClient.get('/analytics/overview', { params: { days } })
  return res.data
}
