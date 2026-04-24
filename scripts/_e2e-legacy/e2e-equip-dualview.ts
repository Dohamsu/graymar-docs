import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-equip-dualview';
const EMAIL = 'playtest_1776660357@test.com';
const PASSWORD = 'Test1234!!';

async function openInventoryAndEquip(page: any, label: string) {
  console.log(`\n=== [${label}] ===`);
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

  await page.screenshot({ path: `${DIR}/${label}_01_menu.png`, fullPage: true });

  const resumeBtn = page.getByRole('button', { name: /이어하기/ });
  if (await resumeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await resumeBtn.click();
    await page.waitForTimeout(8000);
  }

  await page.screenshot({ path: `${DIR}/${label}_02_game.png`, fullPage: true });

  // 모바일이면 햄버거/하단 네비로 사이드 패널 열기
  const isMobile = label === 'mobile';
  if (isMobile) {
    console.log('▶ 모바일 — 하단 네비/햄버거 탐색');
    const menuBtn = page.locator('[aria-label*="메뉴"], [aria-label*="menu"], button:has(svg.lucide-menu)').first();
    if (await menuBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await menuBtn.click();
      await page.waitForTimeout(600);
    }
  }

  await page.screenshot({ path: `${DIR}/${label}_03_opened.png`, fullPage: true });

  // 인벤토리 탭 찾기
  console.log('▶ 인벤토리 탭 클릭');
  const invTab = page.getByRole('button', { name: /소지품|인벤토리|가방/ }).first();
  if (await invTab.isVisible({ timeout: 3000 }).catch(() => false)) {
    await invTab.click();
    await page.waitForTimeout(800);
  } else {
    const bagBtn = page.locator('button:has([data-lucide="backpack"]), [aria-label*="소지품"], [aria-label*="가방"]').first();
    if (await bagBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await bagBtn.click();
      await page.waitForTimeout(800);
    }
  }

  await page.screenshot({ path: `${DIR}/${label}_04_inventory.png`, fullPage: true });

  // 미장착 장비로 스크롤
  const equipSection = page.getByText(/미장착 장비/).first();
  if (await equipSection.isVisible({ timeout: 2000 }).catch(() => false)) {
    await equipSection.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
  }

  await page.screenshot({ path: `${DIR}/${label}_05_equip_section.png`, fullPage: true });

  // 장착 버튼 클릭 → 교체 모달 유도
  console.log('▶ 장착 버튼 클릭 (교체 모달 유도)');
  const equipBtn = page.getByRole('button', { name: /^장착$/ }).first();
  if (await equipBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await equipBtn.click();
    await page.waitForTimeout(1000);
  }

  await page.screenshot({ path: `${DIR}/${label}_06_modal.png`, fullPage: true });

  // 모달 닫기 (만약 열렸다면)
  const cancelBtn = page.getByRole('button', { name: /^취소$/ }).first();
  if (await cancelBtn.isVisible({ timeout: 1500 }).catch(() => false)) {
    await cancelBtn.click();
    await page.waitForTimeout(300);
  }

  // 텍스트 dump
  const bodyText = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(`${DIR}/${label}_text.txt`, bodyText);
}

async function run() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });

  // 데스크톱
  const desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const desktopPage = await desktopCtx.newPage();
  await openInventoryAndEquip(desktopPage, 'desktop');
  await desktopCtx.close();

  // 모바일 (iPhone 14 Pro 393x852)
  const mobileCtx = await browser.newContext({
    viewport: { width: 393, height: 852 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
    isMobile: true,
    hasTouch: true,
  });
  const mobilePage = await mobileCtx.newPage();
  await openInventoryAndEquip(mobilePage, 'mobile');
  await mobileCtx.close();

  await browser.close();
  console.log('\n✓ 모든 스크린샷 완료:', DIR);
}

run().catch((e) => { console.error(e); process.exit(1); });
