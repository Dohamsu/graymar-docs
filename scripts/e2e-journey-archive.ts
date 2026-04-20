import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-journey';
const EMAIL = 'playtest_1776648697@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.mkdirSync(DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') {
      console.log(`[browser/${type}]`, msg.text().slice(0, 200));
    }
  });

  console.log('▶ /play 접속');
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(3000);

  const startBtn = page.getByRole('button', { name: /시작하기/ });
  if (await startBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await startBtn.click();
    await page.waitForTimeout(3000);
  }

  console.log('▶ 로그인');
  const emailInput = page.locator('input[name="email"], input[type="email"]').first();
  if (await emailInput.isVisible({ timeout: 5000 }).catch(() => false)) {
    await emailInput.fill(EMAIL);
    await page.locator('input[name="password"], input[type="password"]').first().fill(PASSWORD);
    const loginBtns = page.locator('button:has-text("로그 인"), button:has-text("로그인"), button[type="submit"]');
    await loginBtns.nth((await loginBtns.count()) - 1).click();
    await page.waitForTimeout(5000);
  }

  await page.screenshot({ path: `${DIR}/01_title_menu.png`, fullPage: true });
  console.log('📸 01_title_menu.png (여정 기록 버튼 확인)');

  // "여정 기록" 버튼 감지
  const archiveBtn = page.getByText(/여정 기록/);
  const hasArchiveBtn = await archiveBtn.isVisible({ timeout: 3000 }).catch(() => false);
  console.log(`▶ 여정 기록 버튼 노출: ${hasArchiveBtn}`);

  if (!hasArchiveBtn) {
    console.log('⚠️  여정 기록 버튼이 표시되지 않음 — endingsCount 또는 노출 로직 확인 필요');
    const pageText = await page.evaluate(() => document.body.innerText);
    console.log('현재 페이지 텍스트:', pageText.slice(0, 500));
    await browser.close();
    return;
  }

  console.log('▶ 여정 기록 버튼 클릭');
  await archiveBtn.click();
  await page.waitForTimeout(2500);

  await page.screenshot({ path: `${DIR}/02_endings_list.png`, fullPage: true });
  console.log('📸 02_endings_list.png (엔딩 목록)');

  // 리스트 카드 클릭
  console.log('▶ 리스트의 첫 카드 클릭');
  const firstCard = page.locator('[role="button"], button, div[class*="cursor-pointer"]').filter({ hasText: /황금빛|일\s|턴/ }).first();
  const cardVisible = await firstCard.isVisible({ timeout: 3000 }).catch(() => false);
  if (cardVisible) {
    await firstCard.click();
  } else {
    // fallback: 모든 카드/버튼
    const anyCard = page.getByText('황금빛 그림자').first();
    if (await anyCard.isVisible({ timeout: 2000 }).catch(() => false)) {
      await anyCard.click();
    }
  }
  await page.waitForTimeout(3500);

  await page.screenshot({ path: `${DIR}/03_journey_summary_top.png`, fullPage: false });
  console.log('📸 03_journey_summary_top.png (상단)');

  // 스크롤 middle / bottom
  await page.evaluate(() => {
    const scrollable = document.querySelector('[class*="overflow-y-auto"]');
    if (scrollable) {
      const el = scrollable as HTMLElement;
      el.scrollTop = el.scrollHeight / 2;
    } else {
      window.scrollTo(0, document.body.scrollHeight / 2);
    }
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${DIR}/04_journey_summary_mid.png`, fullPage: false });
  console.log('📸 04_journey_summary_mid.png (중간)');

  await page.evaluate(() => {
    const scrollable = document.querySelector('[class*="overflow-y-auto"]');
    if (scrollable) {
      const el = scrollable as HTMLElement;
      el.scrollTop = el.scrollHeight;
    } else {
      window.scrollTo(0, document.body.scrollHeight);
    }
  });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${DIR}/05_journey_summary_bottom.png`, fullPage: false });
  console.log('📸 05_journey_summary_bottom.png (하단)');

  // 전체 페이지 캡처
  await page.screenshot({ path: `${DIR}/06_journey_summary_full.png`, fullPage: true });
  console.log('📸 06_journey_summary_full.png');

  // 텍스트 덤프
  const bodyText = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(`${DIR}/journey_text.txt`, bodyText);
  console.log('\n=== 여정 요약 텍스트 프리뷰 ===');
  console.log(bodyText.slice(0, 800));

  await browser.close();
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
