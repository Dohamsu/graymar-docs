/**
 * 문단 분리 수정 확인 — 턴 제출 후 타이핑 중 스크린샷 여러 장 캡처해 문단 분리 시점 확인
 */
import { chromium } from 'playwright';
import * as fs from 'fs';

const CLIENT = 'http://localhost:3001';
const DIR = '/tmp/e2e-paragraph-check';
const EMAIL = 'combat_test_1776815543320@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });

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
    await page.waitForTimeout(12000);
  }
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
  }

  // 전투가 끝난 상태면 HUB/LOCATION일 가능성. 어쨌든 입력창에 "주변을 살펴본다" 입력
  await page.screenshot({ path: `${DIR}/00_initial.png`, fullPage: true });

  const textarea = page.locator('textarea, input[placeholder*="행동"], input[placeholder*="전투"]').first();
  if (await textarea.isVisible({ timeout: 3000 }).catch(() => false)) {
    await textarea.fill('주변을 주의깊게 살펴본다');
    const submitBtn = page.locator('button:has-text("실행")').last();
    if (await submitBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await submitBtn.click({ force: true }).catch(() => {});
    } else {
      await textarea.press('Enter');
    }
  }

  // 타이핑 중 여러 시점 캡처
  for (let t = 1; t <= 8; t++) {
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${DIR}/t${String(t).padStart(2, '0')}_typing.png`, fullPage: true });
    console.log(`📸 t${t.toString().padStart(2, '0')}_typing.png`);
  }

  // 최종 상태
  await page.waitForTimeout(5000);
  await page.screenshot({ path: `${DIR}/final.png`, fullPage: true });

  await browser.close();
  console.log('✓ 완료');
}

run().catch((e) => { console.error(e); process.exit(1); });
