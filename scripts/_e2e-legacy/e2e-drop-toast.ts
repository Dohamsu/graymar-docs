import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-drop-toast';
const EMAIL = 'playtest_1776660357@test.com';
const PASSWORD = 'Test1234!!';

// GOLD_ACTIONS 계열 행동 — 드랍 발생 확률 있는 것들
const GOLD_ACTIONS = [
  '창고를 뒤진다',
  '수상한 상자를 조사한다',
  '물건을 훔친다',
  '지나는 사내에게 시비를 건다',
  '숨은 곳을 찾는다',
];

async function run() {
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

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
    const btns = page.locator('button[type="submit"], button:has-text("로그인"), button:has-text("로그 인")');
    await btns.last().click();
    await page.waitForTimeout(5000);
  }

  const resumeBtn = page.getByRole('button', { name: /이어하기/ });
  if (await resumeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await resumeBtn.click();
    await page.waitForTimeout(10000);
  } else {
    console.log('⚠️  이어하기 없음');
    await browser.close();
    return;
  }

  let dropCaptured = false;

  for (let i = 0; i < GOLD_ACTIONS.length && !dropCaptured; i++) {
    const action = GOLD_ACTIONS[i];
    console.log(`\n▶ 턴 ${i + 1}: "${action}" 제출`);

    const input = page.locator('input[placeholder*="행동"], textarea[placeholder*="행동"]').first();
    if (!(await input.isVisible({ timeout: 2000 }).catch(() => false))) {
      console.log('   입력창 미감지, 다음 턴 대기');
      await page.waitForTimeout(2000);
      continue;
    }

    await input.fill(action);
    await page.waitForTimeout(300);
    const runBtn = page.getByRole('button', { name: /실행/ }).first();
    if (await runBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await runBtn.click();
    } else {
      await input.press('Enter');
    }

    // LLM 응답 대기 — 토스트는 서버 응답 받자마자 나타남 (LLM 전)
    // 응답 감지: equipmentBag 변화 감지. 여기선 타임 슬롯으로 연속 캡처
    for (let t = 0; t < 8 && !dropCaptured; t++) {
      await page.waitForTimeout(2000);
      const toast = page.getByText(/장비 획득/);
      const visible = await toast.isVisible({ timeout: 300 }).catch(() => false);
      if (visible) {
        console.log(`   📸 토스트 감지! (${2 * (t + 1)}초)`);
        await page.screenshot({ path: `${DIR}/toast_turn${i + 1}.png`, fullPage: false });
        dropCaptured = true;
        break;
      }
    }

    if (!dropCaptured) {
      console.log(`   턴 ${i + 1} 드랍 없음, 다음 액션`);
      // LLM 응답 완전 수신까지 추가 대기
      await page.waitForTimeout(10000);
    }
  }

  if (!dropCaptured) {
    console.log('\n⚠️  5턴 내 장비 드랍 미감지 (확률 이슈). 인벤토리 상태만 캡처.');
    await page.screenshot({ path: `${DIR}/no_drop_final.png`, fullPage: true });
  }

  await browser.close();
}

run().catch((e) => { console.error(e); process.exit(1); });
