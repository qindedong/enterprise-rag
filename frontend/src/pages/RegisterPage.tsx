/**
 * 注册页面
 */

import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LucideBookOpen, LucideEye, LucideEyeOff } from 'lucide-react'
import { register, login } from '../api/auth'
import { useAuth } from '../contexts/AuthContext'

export function RegisterPage() {
  const navigate = useNavigate()
  const { login: doLogin } = useAuth()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')

    if (!username.trim()) { setError('请输入用户名'); return }
    if (username.trim().length < 2) { setError('用户名至少 2 个字符'); return }
    if (!email.trim()) { setError('请输入邮箱'); return }
    if (!/\S+@\S+\.\S+/.test(email)) { setError('请输入有效的邮箱地址'); return }
    if (password.length < 8) { setError('密码至少 8 个字符'); return }
    if (password !== confirmPwd) { setError('两次输入的密码不一致'); return }

    setLoading(true)
    try {
      await register({
        username: username.trim(),
        email: email.trim(),
        password,
      })
      // 注册成功后自动登录
      const loginRes = await login({ email: email.trim(), password })
      await doLogin(loginRes.data.access_token, loginRes.data.refresh_token)
      navigate('/kbs', { replace: true })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      setError(msg || '注册失败，请稍后重试')
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
          <h1 className="font-display text-2xl font-bold text-ink">创建账号</h1>
          <div className="h-1 w-10 bg-accent mx-auto mt-3" aria-hidden="true" />
          <p className="meta-label mt-3">注册后即可使用企业知识库</p>
        </div>

        {/* 表单 */}
        <form onSubmit={handleSubmit} className="card p-6 space-y-4">
          {error && (
            <div role="alert" className="bg-err-soft text-err text-sm px-4 py-3 rounded-theme">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="register-username" className="block text-sm font-medium text-ink mb-1">用户名</label>
            <input
              id="register-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名（2-20个字符）"
              className="input"
              autoComplete="username"
            />
          </div>

          <div>
            <label htmlFor="register-email" className="block text-sm font-medium text-ink mb-1">邮箱</label>
            <input
              id="register-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="请输入邮箱地址"
              className="input"
              autoComplete="email"
            />
          </div>

          <div>
            <label htmlFor="register-password" className="block text-sm font-medium text-ink mb-1">密码</label>
            <div className="relative">
              <input
                id="register-password"
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 8 个字符"
                className="input pr-10"
                autoComplete="new-password"
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
            <p className="meta-label mt-1">密码至少 8 个字符</p>
          </div>

          <div>
            <label htmlFor="register-password-confirm" className="block text-sm font-medium text-ink mb-1">确认密码</label>
            <input
              id="register-password-confirm"
              type="password"
              value={confirmPwd}
              onChange={(e) => setConfirmPwd(e.target.value)}
              placeholder="请再次输入密码"
              className="input"
              autoComplete="new-password"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full"
          >
            {loading ? '注册中...' : '注 册'}
          </button>
        </form>

        <p className="text-center text-sm text-ink-muted mt-6">
          已有账号？{' '}
          <Link to="/login" className="text-accent hover:underline font-medium">
            立即登录
          </Link>
        </p>
      </div>
    </div>
  )
}
