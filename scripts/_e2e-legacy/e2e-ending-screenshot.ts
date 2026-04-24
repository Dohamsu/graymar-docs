import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-ending-result';
const EMAIL = 'playtest_1776648697@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.mkdirSync(DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  // 데스크톱 뷰포트로 엔딩 레이아웃 전체 캡처
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  console.log('▶ /play 접속');
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(3000);

  // "시작하기" 버튼 클릭 (랜딩 → 게임 라우팅)
  const startBtn = page.getByRole('button', { name: /시작하기/ });
  if (await startBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    console.log('▶ "시작하기" 클릭');
    await startBtn.click();
    await page.waitForTimeout(3000);
  }

  // 로그인 폼 등장 대기
  console.log('▶ 로그인 시도');
  const emailInput = page.locator('input[name="email"], input[type="email"]').first();
  const emailVisible = await emailInput.isVisible({ timeout: 5000 }).catch(() => false);
  if (emailVisible) {
    await emailInput.fill(EMAIL);
    await page.locator('input[name="password"], input[type="password"]').first().fill(PASSWORD);
    await page.waitForTimeout(500);

    const loginBtns = page.locator('button:has-text("로그 인"), button:has-text("로그인"), button[type="submit"]');
    const count = await loginBtns.count();
    if (count >= 1) {
      await loginBtns.nth(count - 1).click();
    }
    await page.waitForTimeout(6000);
  } else {
    console.log('⚠️  로그인 폼 미감지 — 이미 세션 존재 가능');
  }

  // 로그인 후 상태 스크린샷
  await page.screenshot({ path: `${DIR}/01_after_login.png`, fullPage: true });
  console.log(`📸 01_after_login.png  URL=${page.url()}`);

  // "이어하기" 버튼이 있으면 클릭 (RUN_ENDED 상태에서도 지난 런 진입 경로)
  const continueBtn = page.getByText(/이어하기|결과 보기|지난 런|여정의 끝/).first();
  if (await continueBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    console.log('▶ "이어하기/결과 보기" 클릭');
    await continueBtn.click();
    await page.waitForTimeout(4000);
  }

  // 엔딩 화면 감지 - "여정의 끝", "여정 완료" 등
  const endingTitle = page.getByText(/여정의 끝|여정 완료/);
  const hasEnding = await endingTitle.isVisible({ timeout: 5000 }).catch(() => false);
  console.log(`▶ 엔딩 화면 감지: ${hasEnding}`);

  // 엔딩 화면 전체 캡처
  await page.screenshot({ path: `${DIR}/02_ending_full.png`, fullPage: true });
  console.log('📸 02_ending_full.png');

  // 스크롤 상/중/하
  await page.evaluate(() => {
    const scrollable = document.querySelector('[class*="overflow-y-auto"]');
    if (scrollable) (scrollable as HTMLElement).scrollTop = 0;
    else window.scrollTo(0, 0);
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/03_ending_top.png`, fullPage: false });
  console.log('📸 03_ending_top.png');

  await page.evaluate(() => {
    const scrollable = document.querySelector('[class*="overflow-y-auto"]');
    if (scrollable) {
      const el = scrollable as HTMLElement;
      el.scrollTop = el.scrollHeight / 2;
    } else {
      window.scrollTo(0, document.body.scrollHeight / 2);
    }
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/04_ending_mid.png`, fullPage: false });
  console.log('📸 04_ending_mid.png');

  await page.evaluate(() => {
    const scrollable = document.querySelector('[class*="overflow-y-auto"]');
    if (scrollable) {
      const el = scrollable as HTMLElement;
      el.scrollTop = el.scrollHeight;
    } else {
      window.scrollTo(0, document.body.scrollHeight);
    }
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${DIR}/05_ending_bottom.png`, fullPage: false });
  console.log('📸 05_ending_bottom.png');

  // 페이지 HTML 덤프 (디버그용)
  const html = await page.content();
  fs.writeFileSync(`${DIR}/page.html`, html);

  // 페이지 내 주요 텍스트 추출 (엔딩 타이틀/에필로그)
  const bodyText = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(`${DIR}/ending_text.txt`, bodyText);
  const preview = bodyText.slice(0, 400);
  console.log(`\n=== 엔딩 화면 텍스트 프리뷰 ===\n${preview}\n...`);

  await browser.close();
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
