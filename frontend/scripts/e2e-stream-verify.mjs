// One-shot verification of the streaming chatbot UX.
// Run: node scripts/e2e-stream-verify.mjs  (from frontend/)
import { chromium } from 'playwright'
import fs from 'node:fs'

const BASE = 'http://localhost:5173'
const shots = 'e2e-shots'
fs.mkdirSync(shots, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const logs = []
page.on('pageerror', (err) => logs.push(`[pageerror] ${err.message}`))

try {
  // 1) Sign in → chat
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('you@company.io').fill('admin@smartsupport.io')
  await page.getByPlaceholder('••••••••').fill('Admin12345!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(`${BASE}/`, { timeout: 15000 })
  await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)

  // 2) Fresh conversation via the product picker
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByText('Pick the product you need help with.').waitFor({ timeout: 8000 })
  await page.getByRole('button', { name: /Aurora Coffee Maker X100/ }).first().click()
  await page.waitForTimeout(800)

  // Starter prompts should be visible on a fresh conversation.
  await page.getByText('Try asking').waitFor({ timeout: 8000 })
  await page.screenshot({ path: `${shots}/30-chat-starters.png` })
  console.log('PASS: starter prompts visible')

  // 3) Send a question; the optimistic user bubble must appear instantly.
  await page.getByPlaceholder(/Ask about setup/i).fill('How do I descale the machine and how often?')
  await page.keyboard.press('Enter')
  await page.getByText('How do I descale the machine and how often?').first().waitFor({ timeout: 8000 })
  console.log('PASS: optimistic user bubble')

  // 4) Mid-stream: sources arrive first, then the answer streams in as tokens.
  await page.getByText(/excerpt|Understanding|Searching/).first().waitFor({ timeout: 20000 })
  // Poll until the live draft has accumulated some prose (token events flowing).
  await page.waitForFunction(
    () => {
      const panels = [...document.querySelectorAll('div.rounded-md.border')]
      return panels.some((el) => (el.textContent ?? '').length > 220 && el.textContent?.includes('…'))
    },
    { timeout: 30000 },
  )
  await page.waitForTimeout(1200) // let a few more tokens paint
  await page.screenshot({ path: `${shots}/31-chat-streaming-tokens.png` })
  console.log('PASS: token streaming draft visible mid-generation')

  // 5) Completion: the final grounded bubble replaces the draft.
  await page.getByText(/Grounded in manual|Not found in the manual/).first().waitFor({ timeout: 90000 })
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${shots}/32-chat-final-followups.png` })
  const followUps = await page.getByText('Suggested follow-ups').count()
  console.log(followUps > 0 ? 'PASS: follow-up chips rendered' : 'INFO: model produced no follow-ups this run')

  console.log('STREAM VERIFY PASS ✓')
} catch (error) {
  await page.screenshot({ path: `${shots}/99-stream-failure.png` }).catch(() => {})
  console.error('STREAM VERIFY FAIL ✗ —', error.message)
  console.error(logs.slice(-10).join('\n'))
  process.exitCode = 1
} finally {
  await browser.close()
}
