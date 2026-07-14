/**
 * 主布局组件（Header + Sidebar + 内容区）
 */

import { useState } from 'react'
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom'
import {
  LucideDatabase,
  LucideMessageSquare,
  LucideLogOut,
  LucideMenu,
  LucideUser,
  LucideBookOpen,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

export function MainLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { path: '/kbs', label: '知识库', icon: LucideDatabase },
    { path: '/chat', label: 'AI 问答', icon: LucideMessageSquare },
  ]

  return (
    <div className="min-h-screen flex bg-gray-50">
      {/* ===== 移动端遮罩 ===== */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ===== 侧边栏 ===== */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50 w-60 bg-white border-r border-gray-200
          flex flex-col transition-transform duration-200
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className="h-16 flex items-center gap-3 px-5 border-b border-gray-200">
          <div className="h-8 w-8 bg-blue-500 rounded-lg flex items-center justify-center">
            <LucideBookOpen className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold text-gray-800">知识库 RAG</span>
        </div>

        {/* 导航 */}
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map(({ path, label, icon: Icon }) => {
            const isActive = location.pathname.startsWith(path)
            return (
              <Link
                key={path}
                to={path}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* 底部用户信息 */}
        <div className="p-4 border-t border-gray-200">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-8 w-8 bg-gray-200 rounded-full flex items-center justify-center">
              <LucideUser className="h-4 w-4 text-gray-500" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-700 truncate">
                {user?.username || '用户'}
              </p>
              <p className="text-xs text-gray-400 truncate">
                {user?.email || ''}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <LucideLogOut className="h-4 w-4" />
            退出登录
          </button>
        </div>
      </aside>

      {/* ===== 主内容区 ===== */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部导航栏 */}
        <header className="h-16 bg-white border-b border-gray-200 flex items-center px-4 lg:px-6 shrink-0">
          <button
            className="lg:hidden p-2 -ml-2 mr-2 rounded-md hover:bg-gray-100"
            onClick={() => setSidebarOpen(true)}
          >
            <LucideMenu className="h-5 w-5 text-gray-600" />
          </button>
          <button
            className="hidden lg:flex p-2 -ml-2 mr-2 rounded-md hover:bg-gray-100"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <LucideMenu className="h-5 w-5 text-gray-600" />
          </button>
          <h1 className="text-lg font-semibold text-gray-800 flex-1 truncate">
            {navItems.find((n) => location.pathname.startsWith(n.path))?.label || '企业知识库'}
          </h1>
        </header>

        {/* 内容 */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
