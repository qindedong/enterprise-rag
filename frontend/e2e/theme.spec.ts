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
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'minimal')
})

test('切换主题族与明暗并持久化', async ({ page }) => {
  await page.goto('/kbs')

  // 切换到杂志主题
  await page.getByRole('radio', { name: '杂志' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'editorial')

  // 切换明暗
  await page
    .getByRole('button', { name: /切换到深色模式|切换到浅色模式/ })
    .click()
  const mode = await page.locator('html').getAttribute('data-mode')

  // localStorage 持久化
  const stored = await page.evaluate(() => localStorage.getItem('app-theme'))
  expect(JSON.parse(stored!)).toEqual({ theme: 'editorial', mode })

  // 刷新后保持
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'editorial')
  await expect(page.locator('html')).toHaveAttribute('data-mode', mode!)
})
