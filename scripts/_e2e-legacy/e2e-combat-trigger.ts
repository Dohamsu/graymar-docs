import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-combat-trigger';
const EMAIL = 'playtest_1776660357@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const closeModal = async () => {
    await page.keyboard.press('Escape').catch(() => {});
    await page.waitForTimeout(300);
    const xBtn = page.locator('[aria-label="닫기"]').first();
    if (await xBtn.isVisible({ timeout: 500 }).catch(() => false)) {
      await xBtn.click().catch(() => {});
      await page.waitForTimeout(300);
    }
  };

  await page.goto(`${BASE}/play`);
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
    await page.waitForTimeout(8000);
  }

  await closeModal();
  await page.screenshot({ path: `${DIR}/00_game_start.png`, fullPage: true });

  // 공격적 행동 반복 — 전투 트리거 시도
  const aggressiveInputs = [
    '경비대로 이동한다',
    '경비병에게 시비를 걸며 주먹을 휘두른다',
    '경비병을 공격한다',
    '경비병에게 돌진한다',
    '강하게 공격한다',
    '칼을 뽑아 휘두른다',
    '경비병을 무력으로 제압한다',
    '검을 뽑아 경비병을 겨눈다',
  ];

  let combatDetected = false;
  for (let i = 0; i < aggressiveInputs.length && !combatDetected; i++) {
    const input = aggressiveInputs[i];
    console.log(`\n▶ ${i + 1}: "${input}"`);
    await closeModal();

    const textarea = page.locator('textarea, input[placeholder*="행동"]').first();
    if (!(await textarea.isVisible({ timeout: 3000 }).catch(() => false))) {
      console.log('  ⚠️ 입력창 없음');
      continue;
    }
    await textarea.fill(input);
    const submitBtn = page.locator('button:has-text("실행")').last();
    if (await submitBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await submitBtn.click();
    } else {
      await textarea.press('Enter');
    }

    await page.waitForTimeout(15000);
    await closeModal();

    // 전투 패널 탐지
    const battlePanel = page.locator('text=/적$/').first();
    const enemyCards = page.locator('[class*="border-[var(--hp-red)]"]');
    if (
      (await battlePanel.isVisible({ timeout: 1000 }).catch(() => false)) ||
      (await enemyCards.count()) > 0
    ) {
      combatDetected = true;
      console.log('  🎯 COMBAT 감지됨');
    }

    await page.screenshot({
      path: `${DIR}/pre_combat_${String(i + 1).padStart(2, '0')}.png`,
      fullPage: true,
    });
  }

  if (!combatDetected) {
    console.log('\n⚠️ 공격적 행동 8회 시도했으나 전투 미트리거');
    // 최종 스크린샷
    await page.screenshot({ path: `${DIR}/FINAL_no_combat.png`, fullPage: true });
    await browser.close();
    return;
  }

  // 전투 진입 — 창의 입력 테스트
  await page.screenshot({ path: `${DIR}/combat_01_entry.png`, fullPage: true });
  console.log('\n=== 전투 돌입 — 창의 입력 테스트 ===');

  const combatInputs = [
    { input: '의자를 집어 던진다', label: 'Tier1_chair' },
    { input: '드래곤 브레스!', label: 'Tier4_fantasy' },
    { input: 'HP를 회복한다', label: 'Tier5_abstract' },
    { input: '정면에서 검을 휘두른다', label: 'Tier3_normal' },
  ];

  for (let i = 0; i < combatInputs.length; i++) {
    const { input, label } = combatInputs[i];
    console.log(`\n▶ 전투 턴 ${i + 1} [${label}]: "${input}"`);
    await closeModal();

    const textarea = page.locator('textarea, input[placeholder*="행동"]').first();
    if (!(await textarea.isVisible({ timeout: 3000 }).catch(() => false))) break;
    await textarea.fill(input);
    const submitBtn = page.locator('button:has-text("실행")').last();
    if (await submitBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await submitBtn.click();
    } else {
      await textarea.press('Enter');
    }
    await page.waitForTimeout(15000);
    await closeModal();
    await page.screenshot({
      path: `${DIR}/combat_${String(i + 2).padStart(2, '0')}_${label}.png`,
      fullPage: true,
    });
  }

  await browser.close();
  console.log('\n✓ 완료:', DIR);
}

run().catch((e) => { console.error(e); process.exit(1); });
