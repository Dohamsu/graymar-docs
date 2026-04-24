import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-ending';

async function run() {
  fs.mkdirSync(DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();

  // 1. 로그인 페이지
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(3000);

  // "시작하기" 오버레이 클릭
  const overlay = page.getByText('시작하기', { exact: false });
  if (await overlay.isVisible({ timeout: 2000 }).catch(() => false)) {
    await overlay.click({ force: true });
    await page.waitForTimeout(1000);
  }

  // 이메일/비번 입력
  const emailInput = page.locator('input[name="email"]');
  if (await emailInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await emailInput.fill('e2e_1775993715673@test.com');
    await page.locator('input[name="password"]').fill('Test1234!!');
    // 로그인 버튼 클릭
    await page.waitForTimeout(500);
    const loginBtns = page.locator('button:has-text("로그 인"), button:has-text("로그인")');
    const count = await loginBtns.count();
    // 마지막 버튼이 submit 버튼 (첫 번째는 탭)
    if (count > 1) {
      await loginBtns.nth(count - 1).click();
    } else if (count === 1) {
      await loginBtns.first().click();
    }
    await page.waitForTimeout(4000);
  }

  await page.screenshot({ path: `${DIR}/01_after_login.png`, fullPage: true });
  console.log('📸 01_after_login.png');

  // 2. "이어하기" 클릭 시도
  const continueBtn = page.getByText('이어하기', { exact: false });
  if (await continueBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await continueBtn.click();
    await page.waitForTimeout(8000);
  } else {
    // 이미 게임 화면일 수 있음
    await page.waitForTimeout(5000);
  }

  await page.screenshot({ path: `${DIR}/02_game_screen.png`, fullPage: true });
  console.log('📸 02_game_screen.png');

  // 3. 스크롤 캡처
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/03_top.png`, fullPage: false });
  console.log('📸 03_top.png');

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/04_mid.png`, fullPage: false });
  console.log('📸 04_mid.png');

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/05_bottom.png`, fullPage: false });
  console.log('📸 05_bottom.png');

  // 전체
  await page.screenshot({ path: `${DIR}/06_fullpage.png`, fullPage: true });
  console.log('📸 06_fullpage.png');

  // URL 확인
  console.log(`\nURL: ${page.url()}`);

  await browser.close();
}

run().catch(console.error);
