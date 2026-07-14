/**
 * Axios 客户端封装
 *
 * 功能：
 * - 自动附加 Access Token
 * - 401 时自动刷新 Token
 * - 统一错误处理
 */

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { API_BASE, ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '../utils/constants'

/** 创建 axios 实例 */
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

/** 是否正在刷新 Token（防止并发刷新） */
let isRefreshing = false
/** 等待刷新的请求队列 */
let refreshQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []

/**
 * 处理队列中的请求
 */
function processQueue(error: unknown, token: string | null = null) {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error)
    } else {
      resolve(token!)
    }
  })
  refreshQueue = []
}

/** ===== 请求拦截器：附加 Token ===== */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

/** ===== 响应拦截器：401 自动刷新 ===== */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // 非 401 或已重试过，直接抛错
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    // 刷新 Token 的请求本身 401，直接登出
    if (originalRequest.url?.includes('/auth/refresh')) {
      localStorage.removeItem(ACCESS_TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // 如果正在刷新，加入等待队列
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        refreshQueue.push({ resolve, reject })
      }).then((token) => {
        originalRequest.headers!.Authorization = `Bearer ${token}`
        return apiClient(originalRequest)
      })
    }

    // 开始刷新
    originalRequest._retry = true
    isRefreshing = true

    try {
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
      if (!refreshToken) throw new Error('无 Refresh Token')

      const { data } = await axios.post(`${API_BASE}/auth/refresh`, {
        refresh_token: refreshToken,
      })

      const newAccessToken = data.data.access_token
      const newRefreshToken = data.data.refresh_token

      localStorage.setItem(ACCESS_TOKEN_KEY, newAccessToken)
      localStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken)

      processQueue(null, newAccessToken)
      originalRequest.headers!.Authorization = `Bearer ${newAccessToken}`

      return apiClient(originalRequest)
    } catch (refreshError) {
      processQueue(refreshError, null)
      localStorage.removeItem(ACCESS_TOKEN_KEY)
      localStorage.removeItem(REFRESH_TOKEN_KEY)
      window.location.href = '/login'
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

export default apiClient
