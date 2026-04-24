/**
 * 새 전투 UI (architecture/42) — 버튼형 Action Bar 확인
 * 이미 COMBAT 상태인 run(5f543009)에 로그인 후 스크린샷
 */
import * as fs from 'fs';
import { chromium } from 'playwright';

const CLIENT = 'http://localhost:3001';
const DIR = '/tmp/e2e-combat-ui-new';
const EMAIL = 'combat_test_1776815543320@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  for (const [label, vp] of [
    ['desktop', { width: 1440, height: 900 }],
    ['mobile', { width: 393, height: 852 }],
  ] as const) {
    const ctx = await browser.newContext({
      viewport: vp,
      ...(label === 'mobile'
        ? {
            userAgent:
              'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
            isMobile: true,
            hasTouch: true,
          }
        : {}),
    });
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

    await page.screenshot({ path: `${DIR}/${label}_01_default.png`, fullPage: true });
    console.log(`📸 ${label}_01_default.png`);

    // 특수 버튼 클릭해 펼침 캡처
    const specialBtn = page.locator('button:has-text("특수")').first();
    if (await specialBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await specialBtn.click({ force: true }).catch(() => {});
      await page.waitForTimeout(600);
      await page.screenshot({ path: `${DIR}/${label}_02_special_open.png`, fullPage: true });
      console.log(`📸 ${label}_02_special_open.png`);
      await specialBtn.click({ force: true }).catch(() => {}); // 닫기
      await page.waitForTimeout(400);
    }

    // 적 카드 클릭해 타겟 전환 확인 (2번째 적)
    const enemyButtons = page.locator('[aria-label*="선택"], [aria-pressed]').filter({ hasText: /건달|칼잡이/ });
    const count = await enemyButtons.count();
    if (count >= 2) {
      await enemyButtons.nth(1).click({ force: true }).catch(() => {});
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${DIR}/${label}_03_target_switched.png`, fullPage: true });
      console.log(`📸 ${label}_03_target_switched.png`);
    }

    // 아이템 모달 열기
    const itemBtn = page.locator('button:has-text("아이템")').first();
    if (await itemBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await itemBtn.click({ force: true }).catch(() => {});
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${DIR}/${label}_04_item_modal.png`, fullPage: true });
      console.log(`📸 ${label}_04_item_modal.png`);
    }

    await ctx.close();
  }

  await browser.close();
  console.log('✓ 완료');
}

run().catch((e) => { console.error(e); process.exit(1); });
