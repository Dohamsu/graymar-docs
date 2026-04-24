import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-char-tab';
const EMAIL = 'playtest_1776660357@test.com';
const PASSWORD = 'Test1234!!';

async function captureCharTab(page: any, label: string) {
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(2500);

  const startBtn = page.getByRole('button', { name: /시작하기/ });
  if (await startBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await startBtn.click();
    await page.waitForTimeout(2500);
  }

  const emailInput = page.locator('input[name="email"], input[type="email"]').first();
  if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await emailInput.fill(EMAIL);
    await page.locator('input[name="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"], button:has-text("로그인")').last().click();
    await page.waitForTimeout(5000);
  }

  const resumeBtn = page.getByRole('button', { name: /이어하기/ });
  if (await resumeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await resumeBtn.click();
    await page.waitForTimeout(8000);
  }

  // 모바일 — 햄버거 메뉴 열기
  if (label === 'mobile') {
    const hamburger = page.locator('button:has(svg.lucide-menu), [aria-label*="메뉴"]').first();
    if (await hamburger.isVisible({ timeout: 2000 }).catch(() => false)) {
      await hamburger.click();
      await page.waitForTimeout(600);
    }
  }

  // "캐릭터" 탭/링크/버튼 어느 것이든 클릭
  const charItem = page.locator('text=/^캐릭터$/').first();
  if (await charItem.isVisible({ timeout: 3000 }).catch(() => false)) {
    await charItem.click();
    await page.waitForTimeout(800);
  }

  await page.screenshot({ path: `${DIR}/${label}_character.png`, fullPage: true });
  console.log(`✓ ${label}_character.png`);
}

async function run() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  const desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const desktopPage = await desktopCtx.newPage();
  await captureCharTab(desktopPage, 'desktop');
  await desktopCtx.close();

  const mobileCtx = await browser.newContext({
    viewport: { width: 393, height: 852 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
    isMobile: true,
    hasTouch: true,
  });
  const mobilePage = await mobileCtx.newPage();
  await captureCharTab(mobilePage, 'mobile');
  await mobileCtx.close();

  await browser.close();
  console.log('Done');
}

run().catch((e) => { console.error(e); process.exit(1); });
