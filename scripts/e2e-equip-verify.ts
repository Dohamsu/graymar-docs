import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-equip';
const EMAIL = 'playtest_1776660357@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log('▶ /play 접속');
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(2500);
  const startBtn = page.getByRole('button', { name: /시작하기/ });
  if (await startBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await startBtn.click();
    await page.waitForTimeout(2500);
  }

  console.log('▶ 로그인');
  const emailInput = page.locator('input[name="email"], input[type="email"]').first();
  if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await emailInput.fill(EMAIL);
    await page.locator('input[name="password"]').first().fill(PASSWORD);
    const btns = page.locator('button[type="submit"], button:has-text("로그인"), button:has-text("로그 인")');
    await btns.last().click();
    await page.waitForTimeout(5000);
  }

  await page.screenshot({ path: `${DIR}/01_title_menu.png`, fullPage: true });
  console.log('📸 01_title_menu.png');

  console.log('▶ "이어하기" 클릭');
  const resumeBtn = page.getByRole('button', { name: /이어하기/ });
  if (await resumeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await resumeBtn.click();
    await page.waitForTimeout(8000);
  } else {
    console.log('⚠️  이어하기 버튼 없음');
  }

  await page.screenshot({ path: `${DIR}/02_game_screen.png`, fullPage: true });
  console.log('📸 02_game_screen.png');

  // 데스크톱 SidePanel의 인벤토리 탭 찾기
  console.log('▶ 인벤토리 탭 클릭');
  const invTab = page.getByRole('button', { name: /소지품|인벤토리|가방/ }).first();
  if (await invTab.isVisible({ timeout: 3000 }).catch(() => false)) {
    await invTab.click();
    await page.waitForTimeout(1000);
  } else {
    // data-testid 또는 아이콘 버튼
    const bagBtn = page.locator('button:has([data-lucide="backpack"]), [aria-label*="소지품"], [aria-label*="가방"]').first();
    if (await bagBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await bagBtn.click();
      await page.waitForTimeout(1000);
    }
  }

  await page.screenshot({ path: `${DIR}/03_inventory_tab.png`, fullPage: true });
  console.log('📸 03_inventory_tab.png');

  // 미장착 장비 섹션 스크롤해 포커스
  const equipSection = page.getByText(/미장착 장비/).first();
  if (await equipSection.isVisible({ timeout: 2000 }).catch(() => false)) {
    await equipSection.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
  }

  await page.screenshot({ path: `${DIR}/04_inventory_equipment.png`, fullPage: true });
  console.log('📸 04_inventory_equipment.png');

  // 장착 버튼 클릭 테스트 (첫 장비)
  console.log('▶ 첫 장비 "장착" 버튼 클릭 (교체 모달 유도)');
  const equipBtn = page.getByRole('button', { name: /^장착$/ }).first();
  if (await equipBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await equipBtn.click();
    await page.waitForTimeout(1500);
  }

  await page.screenshot({ path: `${DIR}/05_equip_modal_or_applied.png`, fullPage: true });
  console.log('📸 05_equip_modal_or_applied.png');

  // 텍스트 덤프
  const bodyText = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(`${DIR}/inventory_text.txt`, bodyText);
  console.log('\n=== 인벤토리 텍스트 프리뷰 ===');
  const lines = bodyText.split('\n').filter((l) => l.trim());
  console.log(lines.slice(-60).join('\n'));

  await browser.close();
}

run().catch((e) => { console.error(e); process.exit(1); });
