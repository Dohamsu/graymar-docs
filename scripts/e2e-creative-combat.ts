import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-creative-combat';
const EMAIL = 'playtest_1776660357@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

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
    await page.locator('button[type="submit"], button:has-text("로그인")').last().click();
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
    console.log('⚠️  이어하기 없음 — 새 런 필요');
  }

  await page.screenshot({ path: `${DIR}/02_game_main.png`, fullPage: true });
  console.log('📸 02_game_main.png');

  // 5턴 플레이: 평범한 행동 + 창의 행동 혼합
  const turns = [
    { input: '주변을 살펴본다', label: '평범한 탐색' },
    { input: '의자를 집어 던진다', label: 'Tier 1 프롭 (의자)' },
    { input: '드래곤 브레스!', label: 'Tier 4 환상 재해석' },
    { input: 'HP를 회복한다', label: 'Tier 5 추상' },
    { input: '조용히 지켜본다', label: '평범한 행동' },
  ];

  // 모달 닫기 (호외 등)
  const closeModal = async () => {
    // ESC 키 누르기
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
    // X 버튼 시도
    const xBtn = page.locator('[aria-label="닫기"], button:has-text("×"), button:has-text("✕")').first();
    if (await xBtn.isVisible({ timeout: 500 }).catch(() => false)) {
      await xBtn.click().catch(() => {});
      await page.waitForTimeout(300);
    }
    // 모달 백드롭 클릭
    const backdrop = page.locator('.bg-black\\/80, .fixed.inset-0.bg-black\\/70').first();
    if (await backdrop.isVisible({ timeout: 500 }).catch(() => false)) {
      await backdrop.click({ position: { x: 10, y: 10 } }).catch(() => {});
      await page.waitForTimeout(300);
    }
  };

  await closeModal();
  await page.screenshot({ path: `${DIR}/02b_after_modal_close.png`, fullPage: true });

  for (let i = 0; i < turns.length; i++) {
    const { input, label } = turns[i];
    console.log(`\n▶ 턴 ${i + 1}: ${label} — "${input}"`);

    await closeModal();
    const textarea = page.locator('textarea, input[placeholder*="행동"]').first();
    if (!(await textarea.isVisible({ timeout: 3000 }).catch(() => false))) {
      console.log('  ⚠️ 입력창 없음, 건너뛰기');
      continue;
    }
    await textarea.fill(input);
    const submitBtn = page.locator('button:has-text("실행"), button[type="submit"]').last();
    if (await submitBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await submitBtn.click();
    } else {
      await textarea.press('Enter');
    }

    // LLM 응답 대기 (최대 30초)
    await page.waitForTimeout(12000);

    await page.screenshot({
      path: `${DIR}/03_turn${i + 1}_${label.replace(/\s/g, '_')}.png`,
      fullPage: true,
    });
    console.log(`  📸 03_turn${i + 1}_${label.replace(/\s/g, '_')}.png`);
  }

  // 텍스트 덤프
  const bodyText = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(`${DIR}/final_body.txt`, bodyText);

  await browser.close();
  console.log('\n✓ 완료:', DIR);
}

run().catch((e) => { console.error(e); process.exit(1); });
