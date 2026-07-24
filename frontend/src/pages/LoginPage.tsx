/**
 * 登录页面
 */

import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LucideBookOpen, LucideEye, LucideEyeOff } from 'lucide-react'
import { login, getSSOLoginUrl } from '../api/auth'
import { useAuth } from '../contexts/AuthContext'

export function LoginPage() {
  const navigate = useNavigate()
  const { login: doLogin } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [ssoLoading, setSsoLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!email.trim()) { setError('请输入邮箱'); return }
    if (!password) { setError('请输入密码'); return }

    setLoading(true)
    try {
      const res = await login({ email: email.trim(), password })
      await doLogin(res.data.access_token, res.data.refresh_token)
      navigate('/kbs', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      setError(msg || '登录失败，请检查邮箱和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex h-14 w-14 bg-accent rounded-theme items-center justify-center mb-4">
            <LucideBookOpen className="h-7 w-7 text-accent-ink" />
          </div>
          <h1 className="font-display text-2xl font-bold text-ink">企业知识库 RAG</h1>
          <div className="h-1 w-10 bg-accent mx-auto mt-3" aria-hidden="true" />
          <p className="meta-label mt-3">登录以继续使用</p>
        </div>

        {/* 表单 */}
        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          {error && (
            <div role="alert" className="bg-err-soft text-err text-sm px-4 py-3 rounded-theme">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-ink mb-1">邮箱</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="请输入邮箱地址"
              className="input"
              autoComplete="email"
            />
          </div>

          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-ink mb-1">密码</label>
            <div className="relative">
              <input
                id="login-password"
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                className="input pr-10"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPwd(!showPwd)}
                aria-label={showPwd ? '隐藏密码' : '显示密码'}
                aria-pressed={showPwd}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
              >
                {showPwd ? <LucideEyeOff className="h-4 w-4" /> : <LucideEye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full"
          >
            {loading ? '登录中...' : '登 录'}
          </button>

          <div className="flex items-center gap-3 text-ink-muted">
            <div className="flex-1 h-px bg-line-soft" />
            <span className="meta-label">或</span>
            <div className="flex-1 h-px bg-line-soft" />
          </div>

          <button
            type="button"
            disabled={ssoLoading}
            onClick={async () => {
              setError('')
              setSsoLoading(true)
              try {
                const res = await getSSOLoginUrl()
                window.location.href = res.data.authorization_url
              } catch (err: unknown) {
                const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
                setError(msg || 'SSO 未启用或配置不完整')
                setSsoLoading(false)
              }
            }}
            className="w-full border border-line rounded-theme px-4 py-2 text-sm font-medium text-ink hover:bg-line-soft transition-colors disabled:opacity-60"
          >
            {ssoLoading ? '跳转中...' : '🔐 使用 SSO 单点登录'}
          </button>
        </form>

        <p className="text-center text-sm text-ink-muted mt-6">
          还没有账号？{' '}
          <Link to="/register" className="text-accent hover:underline font-medium">
            立即注册
          </Link>
        </p>
      </div>
    </div>
  )
}
