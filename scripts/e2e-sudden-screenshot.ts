/**
 * 돌발행동 전후 스크린샷 — 기존 E2E 런 재접속
 */
import * as fs from 'fs';
import { chromium } from 'playwright';

const CLIENT = 'http://localhost:3001';
const DIR = '/tmp/e2e-sudden-screenshot';
const EMAIL = 'sudden_test_1776836027286@test.com';
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
    await page.waitForTimeout(15000);
  }
  for (let i = 0; i < 3; i++) {
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
  }

  // 최종 상태 (현재 COMBAT — T8 이후)
  await page.screenshot({ path: `${DIR}/01_combat_after_stab.png`, fullPage: true });
  console.log('📸 01_combat_after_stab.png');

  // 서술 패널 위로 스크롤해 T7 공격 순간 보기
  const narrativeScroll = page.locator('[class*="narrative"]').first();
  // 전체 페이지 스크롤 업
  await page.evaluate(() => {
    const scrollables = document.querySelectorAll('div');
    scrollables.forEach(el => {
      if (el.scrollHeight > el.clientHeight) el.scrollTop = 0;
    });
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/02_scrolled_top.png`, fullPage: true });
  console.log('📸 02_scrolled_top.png');

  // 중간 스크롤
  await page.evaluate(() => {
    const scrollables = document.querySelectorAll('div');
    scrollables.forEach(el => {
      if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight / 2;
    });
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/03_mid_scroll.png`, fullPage: true });
  console.log('📸 03_mid_scroll.png');

  // 하단 (최신)
  await page.evaluate(() => {
    const scrollables = document.querySelectorAll('div');
    scrollables.forEach(el => {
      if (el.scrollHeight > el.clientHeight) el.scrollTop = el.scrollHeight;
    });
  });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${DIR}/04_bottom.png`, fullPage: true });
  console.log('📸 04_bottom.png');

  await browser.close();
  console.log('✓ 완료');
}

run().catch(e => { console.error(e); process.exit(1); });
