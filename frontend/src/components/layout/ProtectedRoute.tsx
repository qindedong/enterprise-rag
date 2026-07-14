/**
 * 路由守卫：未登录时重定向到登录页
 */

import { Navigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { PageLoading } from '../common/Loading'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <PageLoading />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
