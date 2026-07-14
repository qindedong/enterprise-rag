/**
 * 认证相关 API
 */

import apiClient from './client'
import type { APIResponse, TokenResponse, User } from '../types'

/** 用户注册 */
export async function register(data: {
  username: string
  email: string
  password: string
}): Promise<APIResponse<TokenResponse>> {
  const res = await apiClient.post('/auth/register', data)
  return res.data
}

/** 用户登录 */
export async function login(data: {
  email: string
  password: string
}): Promise<APIResponse<TokenResponse>> {
  const res = await apiClient.post('/auth/login', data)
  return res.data
}

/** 刷新 Token */
export async function refreshToken(
  refreshToken: string,
): Promise<APIResponse<TokenResponse>> {
  const res = await apiClient.post('/auth/refresh', { refresh_token: refreshToken })
  return res.data
}

/** 获取当前用户信息 */
export async function getMe(): Promise<APIResponse<User>> {
  const res = await apiClient.get('/auth/me')
  return res.data
}
