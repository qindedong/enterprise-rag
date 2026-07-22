import { test, expect } from '@playwright/test'

const MOCK_USER = {
  code: 0,
  message: 'ok',
  data: {
    id: 'u1',
    username: '测试用户',
    email: 'test@example.com',
    created_at: '2026-01-01T00:00:00Z',
  },
}

const MOCK_KB_LIST = {
  code: 0,
  message: 'ok',
  data: {
    items: [],
    page_info: { page: 1, page_size: 12, total: 0, total_pages: 0 },
  },
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('rag_access_token', 'fake-token-for-e2e')
  })
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_USER) }),
  )
  await page.route('**/api/v1/knowledge-bases**', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(MOCK_KB_LIST) }),
  )
})

test('默认主题为 minimal', async ({ page }) => {
  await page.goto('/kbs')
  await expect(page).toHaveURL(/\/kbs/)
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'minimal')
})

test('切换主题族与明暗并持久化', async ({ page }) => {
  await page.goto('/kbs')

  // 切换到杂志主题
  await page.getByRole('radio', { name: '杂志' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'editorial')

  // 切换明暗（断言真正翻转，且用自动重试消除竞态）
  const html = page.locator('html')
  const before = await html.getAttribute('data-mode')
  await page
    .getByRole('button', { name: /切换到深色模式|切换到浅色模式/ })
    .click()
  const flipped = before === 'dark' ? 'light' : 'dark'
  await expect(html).toHaveAttribute('data-mode', flipped)

  // localStorage 持久化
  const stored = await page.evaluate(() => localStorage.getItem('app-theme'))
  expect(JSON.parse(stored!)).toEqual({ theme: 'editorial', mode: flipped })

  // 刷新后保持
  await page.reload()
  await expect(html).toHaveAttribute('data-theme', 'editorial')
  await expect(html).toHaveAttribute('data-mode', flipped)
})
