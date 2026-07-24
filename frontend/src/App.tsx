/**
 * 应用路由入口
 *
 * 路由结构：
 *   /login          — 登录页
 *   /register       — 注册页
 *   /kbs            — 知识库列表（需登录）
 *   /kbs/:id        — 知识库详情（需登录）
 *   /chat           — AI 问答（需登录）
 *   /               — 默认跳转到 /kbs
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { MainLayout, ProtectedRoute } from './components/layout'
import { LoginPage, RegisterPage, KBListPage, KBDetailPage, ChatPage, AnalyticsPage, SSOCallbackPage } from './pages'

export default function App() {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    setReady(true)
  }, [])

  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider key={ready ? 'ready' : 'init'}>
          <Routes>
            {/* 公开路由 */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/sso/callback" element={<SSOCallbackPage />} />

            {/* 受保护路由（需登录） */}
            <Route
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/kbs" element={<KBListPage />} />
              <Route path="/kbs/:id" element={<KBDetailPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
            </Route>

            {/* 默认跳转 */}
            <Route path="/" element={<Navigate to="/kbs" replace />} />
            <Route path="*" element={<Navigate to="/kbs" replace />} />
          </Routes>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
