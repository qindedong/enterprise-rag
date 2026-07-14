/**
 * 认证上下文
 *
 * 管理全局登录状态：
 * - 用户信息
 * - Token 存储与自动刷新
 * - 登录/登出
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import { getMe } from '../api/auth'
import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from '../utils/constants'
import type { User } from '../types'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (accessToken: string, refreshToken: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  /** 初始化：检查本地 Token 并获取用户信息 */
  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_KEY)
    if (!token) {
      setIsLoading(false)
      return
    }
    getMe()
      .then((res) => setUser(res.data))
      .catch(() => {
        // Token 无效，清除
        localStorage.removeItem(ACCESS_TOKEN_KEY)
        localStorage.removeItem(REFRESH_TOKEN_KEY)
      })
      .finally(() => setIsLoading(false))
  }, [])

  /** 登录：存储 Token 并获取用户信息 */
  const login = useCallback(async (accessToken: string, refreshToken: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
    try {
      const res = await getMe()
      setUser(res.data)
    } catch {
      setUser(null)
    }
  }, [])

  /** 登出 */
  const logout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    setUser(null)
  }, [])

  /** 刷新用户信息 */
  const refreshUser = useCallback(async () => {
    try {
      const res = await getMe()
      setUser(res.data)
    } catch {
      // 静默失败
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

/** 使用认证上下文 Hook */
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth 必须在 AuthProvider 内部使用')
  }
  return ctx
}
