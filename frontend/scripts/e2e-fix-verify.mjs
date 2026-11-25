// One-shot verification of the new production UI surfaces.
// Run: node scripts/e2e-fix-verify.mjs  (from frontend/)
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
  // 1) Sign in
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await page.getByPlaceholder('you@company.io').fill('admin@smartsupport.io')
  await page.getByPlaceholder('••••••••').fill('Admin12345!')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL(`${BASE}/`, { timeout: 15000 })

  // 2) Settings page — profile + password forms
  await page.getByRole('link', { name: 'Settings' }).click()
  await page.waitForURL(/\/settings/, { timeout: 10000 })
  await page.getByText('Workspace', { exact: false }).first().waitFor({ timeout: 10000 })
  await page.screenshot({ path: `${shots}/20-settings.png` })

  // Rename via profile form (unique value so the form is dirty)
  const unique = Date.now().toString().slice(-6)
  const nameInput = page.getByPlaceholder('Ada Lovelace')
  await nameInput.fill(`Support Admin ${unique}`)
  await page.getByRole('button', { name: 'Save' }).click()
  await page.getByText('Profile updated').waitFor({ timeout: 8000 })
  console.log('PASS: profile update')

  // 3) 404 page
  await page.goto(`${BASE}/definitely-not-a-page`, { waitUntil: 'networkidle' })
  await page.getByText('Error 404').waitFor({ timeout: 8000 })
  await page.screenshot({ path: `${shots}/21-notfound.png` })
  console.log('PASS: 404 page')

  // 4) Product edit dialog
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  await page.getByText('Aurora Coffee Maker X100').first().click()
  await page.getByRole('button', { name: 'Edit' }).click()
  await page.getByText('Edit product').waitFor({ timeout: 8000 })
  await page.screenshot({ path: `${shots}/22-product-edit.png` })
  await page.keyboard.press('Escape')
  console.log('PASS: product edit dialog')

  // 5) Chat: ensure a conversation exists, then row rename via the row menu
  await page.goto(`${BASE}/chat`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  const existingRows = await page.locator('div[role="button"]').filter({ hasText: /Aurora Coffee Maker X100/i }).count()
  if (existingRows === 0) {
    await page.getByRole('button', { name: 'New', exact: true }).click()
    await page.getByRole('button', { name: /Aurora Coffee Maker X100/ }).first().click()
    await page.waitForTimeout(800)
  }
  const row = page.locator('div[role="button"]').filter({ hasText: /Aurora Coffee Maker X100/i }).first()
  await row.hover()
  await row.getByRole('button', { name: /Actions for/ }).click()
  await page.getByRole('menuitem', { name: 'Rename' }).click()
  await page.getByLabel('Conversation title').fill(`Espresso deep-dive ${unique}`)
  await page.getByRole('button', { name: 'Save' }).click()
  await page.getByText('Conversation renamed').waitFor({ timeout: 8000 })
  await page.getByText(`Espresso deep-dive ${unique}`).first().waitFor({ timeout: 8000 })
  console.log('PASS: conversation rename')

  // 5b) Header rename for the active conversation
  await page.getByRole('button', { name: 'Conversation actions' }).click()
  await page.getByRole('menuitem', { name: 'Rename' }).click()
  await page.getByLabel('Conversation title').fill(`Header rename ${unique}`)
  await page.getByRole('button', { name: 'Save' }).click()
  await page.getByText('Conversation renamed').waitFor({ timeout: 8000 })
  await page.getByText(`Header rename ${unique}`).first().waitFor({ timeout: 8000 })
  console.log('PASS: header rename')

  // 5c) Header delete of a fresh conversation → falls back to most recent
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('button', { name: /Aurora Coffee Maker X100/ }).first().click()
  await page.waitForTimeout(900)
  await page.getByRole('button', { name: 'Conversation actions' }).click()
  await page.getByRole('menuitem', { name: 'Delete' }).click()
  await page.getByText('Delete this conversation?').waitFor({ timeout: 8000 })
  await page.screenshot({ path: `${shots}/25-delete-confirm.png` })
  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await page.getByText('Conversation deleted').waitFor({ timeout: 8000 })
  await page.getByText('Switched to your most recent conversation').waitFor({ timeout: 8000 })
  console.log('PASS: header delete + fallback selection')

  // 5d) AI Insights page (admin)
  await page.getByRole('link', { name: 'AI Insights' }).click()
  await page.waitForURL(/\/insights/, { timeout: 10000 })
  await page.getByRole('heading', { name: /Support/ }).waitFor({ timeout: 10000 })
  await page.getByText('Grounding rate').waitFor({ timeout: 10000 })
  await page.screenshot({ path: `${shots}/26-insights.png` })
  console.log('PASS: insights page')

  // 5e) Manual search page — live semantic search
  await page.getByRole('link', { name: 'Manual Search' }).click()
  await page.waitForURL(/\/search/, { timeout: 10000 })
  await page.getByLabel('Search manuals').fill('descale')
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByText(/result/).first().waitFor({ timeout: 30000 })
  await page.getByText('% match').first().waitFor({ timeout: 15000 })
  await page.screenshot({ path: `${shots}/27-search.png` })
  console.log('PASS: semantic search page')

  // 5f) Ticket triage — created FROM the support chat
  await page.getByRole('link', { name: 'Support Chat' }).click()
  await page.waitForURL(/\/chat/, { timeout: 10000 })
  await page.getByRole('button', { name: 'New', exact: true }).click()
  await page.getByRole('button', { name: /Aurora Coffee Maker X100/ }).first().click()
  await page.waitForTimeout(800)
  await page.getByPlaceholder(/Ask about setup/i).fill('The steam wand is leaking water, what should I do?')
  await page.keyboard.press('Enter')
  await page.getByText(/Grounded in manual|Not found in the manual/).first().waitFor({ timeout: 90000 })
  await page.getByRole('button', { name: 'Conversation actions' }).click()
  await page.getByRole('menuitem', { name: 'Create support ticket' }).click()
  await page.getByText('Ticket created from this chat').waitFor({ timeout: 60000 })
  await page.getByRole('button', { name: 'View queue' }).click()
  await page.waitForURL(/\/tickets/, { timeout: 10000 })

  // Production desk: live stat strip + tab counts + queue row with creator
  await page.getByText('Needs human', { exact: true }).first().waitFor({ timeout: 10000 })
  await page.getByText('via Support Admin', { exact: false }).first().waitFor({ timeout: 10000 })
  await page.screenshot({ path: `${shots}/28-triage-from-chat.png` })
  console.log('PASS: ticket created from chat + stat strip + queue')

  // Resolve flow with resolution note
  const queueRow = page.locator('button').filter({ hasText: 'steam wand' }).first()
  await queueRow.click()
  await page.getByText('Extracted data').waitFor({ timeout: 10000 })
  await page.getByRole('button', { name: 'Mark resolved' }).click()
  await page.getByText('Resolve ticket').waitFor({ timeout: 8000 })
  await page.getByLabel('Resolution note').fill('Replacement wand seal shipped to the customer.')
  await page.getByRole('button', { name: 'Confirm resolved' }).click()
  await page.getByText('Ticket resolved').waitFor({ timeout: 8000 })
  await page.getByText('Resolution note').first().waitFor({ timeout: 8000 })
  await page.screenshot({ path: `${shots}/29-triage-resolved.png` })
  console.log('PASS: resolution-note workflow')

  // 6) Mobile layout — dashboard + chat drawer
  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await mobile.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await mobile.getByPlaceholder('you@company.io').fill('admin@smartsupport.io')
  await mobile.getByPlaceholder('••••••••').fill('Admin12345!')
  await mobile.getByRole('button', { name: 'Sign in' }).click()
  await mobile.waitForURL(`${BASE}/`, { timeout: 15000 })
  await mobile.waitForTimeout(600)
  await mobile.screenshot({ path: `${shots}/23-mobile-dashboard.png` })
  await mobile.goto(`${BASE}/chat`, { waitUntil: 'networkidle' })
  await mobile.waitForTimeout(600)
  await mobile.getByRole('button', { name: 'Open conversations' }).click()
  await mobile.getByRole('heading', { name: 'Conversations' }).waitFor({ timeout: 8000 })
  await mobile.waitForTimeout(700) // let the slide-in animation settle
  await mobile.screenshot({ path: `${shots}/24-mobile-chat-drawer.png` })
  console.log('PASS: mobile layout')

  console.log('VERIFY PASS ✓')
} catch (error) {
  await page.screenshot({ path: `${shots}/99-fix-verify-failure.png` }).catch(() => {})
  console.error('VERIFY FAIL ✗ —', error.message)
  console.error(logs.slice(-10).join('\n'))
  process.exitCode = 1
} finally {
  await browser.close()
}
