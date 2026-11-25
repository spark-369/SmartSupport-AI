// One-shot browser E2E: login → dashboard → product → chat → live SSE answer.
// Run: node scripts/e2e-browser.mjs  (from frontend/)
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASE = 'http://localhost:5173'
const shots = 'e2e-shots'
fs.mkdirSync(shots, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const logs = []
page.on('console', (msg) => logs.push(`[console.${msg.type()}] ${msg.text()}`))
page.on('pageerror', (err) => logs.push(`[pageerror] ${err.message}`))

try {
  // 1) Login page
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.screenshot({ path: `${shots}/01-login.png` })

  // 2) Sign in as seeded admin
  await page.getByPlaceholder('you@company.io').fill('admin@smartsupport.io')
  await page.getByPlaceholder('••••••••').fill('Admin12345!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(`${BASE}/`, { timeout: 15000 })
  await page.getByText('Aurora Coffee Maker X100').first().waitFor({ timeout: 15000 })
  await page.screenshot({ path: `${shots}/02-dashboard.png` })

  // 3) Open product page (documents table)
  await page.getByText('Aurora Coffee Maker X100').first().click()
  await page.getByText('aurora_coffee_maker_x100_manual.md').first().waitFor({ timeout: 15000 })
  await page.screenshot({ path: `${shots}/03-product.png` })

  // 4) Chat page → send a question, expect the grounded answer to stream in
  await page.getByRole('link', { name: 'Support chat', exact: true }).click()
  await page.waitForURL(/\/chat/, { timeout: 15000 })
  await page.getByPlaceholder(/Ask about setup/i).fill('What error codes can the machine show and what does E1 mean?')
  await page.keyboard.press('Enter')

  // The streaming panel should appear first…
  await page.getByText(/Composing a grounded answer|Searching the manual|Understanding the question/).first().waitFor({ timeout: 20000 })
  await page.screenshot({ path: `${shots}/04-chat-streaming.png` })

  // …and the final assistant bubble must contain grounded text + sources.
  await page.getByText(/E1/).first().waitFor({ timeout: 90000 })
  await page.getByText(/Cited manual excerpts/i).first().waitFor({ timeout: 30000 })
  await page.screenshot({ path: `${shots}/05-chat-answer.png`, fullPage: false })

  console.log('E2E PASS ✓ — all screenshots in frontend/e2e-shots/')
} catch (error) {
  await page.screenshot({ path: `${shots}/99-failure.png` }).catch(() => {})
  console.error('E2E FAIL ✗ —', error.message)
  console.error(logs.slice(-15).join('\n'))
  process.exitCode = 1
} finally {
  await browser.close()
}
