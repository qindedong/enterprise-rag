import { test } from '@playwright/test'

const MOCK_USER = {
  code: 0,
  message: 'ok',
  data: { id: 'u1', username: '测试用户', email: 'test@example.com', created_at: '2026-01-01T00:00:00Z' },
}

const MOCK_KB_LIST = {
  code: 0,
  message: 'ok',
  data: {
    items: [
      {
        id: 'kb1',
        name: '产品研发流程',
        description: '产品从立项到发布的完整流程文档',
        owner_id: 'u1',
        chunk_size: 512,
        chunk_overlap: 50,
        doc_count: 12,
        chunk_count: 380,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z',
      },
    ],
    page_info: { page: 1, page_size: 12, total: 1, total_pages: 1 },
  },
}

const combos = [
  ['minimal', 'light'],
  ['minimal', 'dark'],
  ['editorial', 'light'],
  ['editorial', 'dark'],
] as const

for (const [theme, mode] of combos) {
  test(`截图：${theme} + ${mode}`, async ({ page }) => {
    await page.addInitScript(
      ([t, m]) => {
        localStorage.setItem('rag_access_token', 'fake-token-for-e2e')
        localStorage.setItem('app-theme', JSON.stringify({ theme: t, mode: m }))
      },
      [theme, mode] as const,
    )
    await page.route('**/api/v1/auth/me', (route) =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_USER) }),
    )
    await page.route('**/api/v1/knowledge-bases**', (route) =>
      route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_KB_LIST) }),
    )

    await page.goto('/login')
    await page.screenshot({ path: `e2e/shots/login-${theme}-${mode}.png`, fullPage: true })

    await page.goto('/kbs')
    await page.screenshot({ path: `e2e/shots/kbs-${theme}-${mode}.png`, fullPage: true })
  })
}
