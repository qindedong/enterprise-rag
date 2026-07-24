/**
 * SSO 回调页：接收后端重定向携带的 token，写入登录态后跳转首页
 */

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Loading } from '../components/common/Loading'

export function SSOCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { login: doLogin } = useAuth()
  const [error, setError] = useState('')

  useEffect(() => {
    const accessToken = searchParams.get('access_token')
    const refreshToken = searchParams.get('refresh_token')
    if (!accessToken || !refreshToken) {
      setError('SSO 登录失败：回调缺少令牌')
      return
    }
    doLogin(accessToken, refreshToken)
      .then(() => navigate('/kbs', { replace: true }))
      .catch(() => setError('SSO 登录失败：无法获取用户信息'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      {error ? (
        <div role="alert" className="card p-6 bg-err-soft text-err text-sm">{error}</div>
      ) : (
        <Loading text="SSO 登录中..." />
      )}
    </div>
  )
}
