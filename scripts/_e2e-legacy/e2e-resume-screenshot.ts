/**
 * 기존 창의 전투 런의 최종 상태 스크린샷
 */
import * as fs from 'fs';
import { chromium } from 'playwright';

const CLIENT = 'http://localhost:3001';
const DIR = '/tmp/e2e-fresh-combat';
const EMAIL = 'combat_test_1776815543320@test.com';
const PASSWORD = 'Test1234!!';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  await page.goto(`${CLIENT}/play`);
  await page.waitForTimeout(2500);

  const startBtn = page.getByRole('button', { name: /시작하기/ });
  if (await startBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await startBtn.click();
    await page.waitForTimeout(2500);
  }
  const emailInput = page.locator('input[name="email"]').first();
  if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await emailInput.fill(EMAIL);
    await page.locator('input[name="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"], button:has-text("로그인")').last().click();
    await page.waitForTimeout(5000);
  }
  const resumeBtn = page.getByRole('button', { name: /이어하기/ });
  if (await resumeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await resumeBtn.click();
    await page.waitForTimeout(15000);
  }
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
  }

  // 현재 상태 = T38 (HP 회복한다 실행 후)
  await page.screenshot({ path: `${DIR}/03_final_state.png`, fullPage: true });
  console.log('📸 03_final_state.png (최종 상태, T38 후)');

  // 스크롤해서 turn history 보기
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/04_top_scroll.png`, fullPage: true });
  console.log('📸 04_top_scroll.png');

  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
