import { chromium } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const DIR = '/tmp/e2e-combat-real';
// A2 검증 런 — 현재 COMBAT 상태
const EMAIL = 'playtest_1776730494@test.com';
const PASSWORD = 'Test1234!!';

async function run() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const closeModal = async () => {
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press('Escape').catch(() => {});
      await page.waitForTimeout(300);
    }
    // 호외 / 알림 모달 닫기 — 여러 셀렉터 시도
    const closers = [
      'button[aria-label="닫기"]',
      'button:has-text("확인")',
      'button:has-text("닫기")',
      '.bg-black\\/80',
    ];
    for (const sel of closers) {
      const el = page.locator(sel).first();
      if (await el.isVisible({ timeout: 300 }).catch(() => false)) {
        try {
          await el.click({ timeout: 1000, force: true });
        } catch {}
        await page.waitForTimeout(300);
      }
    }
  };

  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(2500);
  const startBtn = page.getByRole('button', { name: /시작하기/ });
  if (await startBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await startBtn.click();
    await page.waitForTimeout(2500);
  }

  console.log('▶ 로그인:', EMAIL);
  const emailInput = page.locator('input[name="email"]').first();
  if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
    await emailInput.fill(EMAIL);
    await page.locator('input[name="password"]').first().fill(PASSWORD);
    await page.locator('button[type="submit"], button:has-text("로그인")').last().click();
    await page.waitForTimeout(5000);
  }

  await page.screenshot({ path: `${DIR}/00_title.png`, fullPage: true });

  const resumeBtn = page.getByRole('button', { name: /이어하기/ });
  if (await resumeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    console.log('▶ 이어하기 클릭');
    await resumeBtn.click();
    await page.waitForTimeout(10000);
  }

  await closeModal();
  await page.screenshot({ path: `${DIR}/01_combat_entry.png`, fullPage: true });
  console.log('📸 01_combat_entry.png');

  // 창의 입력 시도
  const creativeInputs = [
    { input: '정면에서 검을 휘두른다', label: 'Tier3_normal' },
    { input: '의자를 집어 던진다', label: 'Tier1_chair' },
    { input: '드래곤 브레스!', label: 'Tier4_fantasy' },
  ];

  for (let i = 0; i < creativeInputs.length; i++) {
    const { input, label } = creativeInputs[i];
    console.log(`\n▶ [${label}] "${input}"`);
    await closeModal();

    const textarea = page.locator('textarea, input[placeholder*="행동"]').first();
    if (!(await textarea.isVisible({ timeout: 3000 }).catch(() => false))) {
      console.log('  입력창 없음 — 전투 종료?');
      break;
    }
    await textarea.fill(input);

    const submitBtn = page.locator('button:has-text("실행")').last();
    if (await submitBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      try {
        await submitBtn.click({ timeout: 5000, force: true });
      } catch (e) {
        console.log('  submit click 실패, Enter로 시도');
        await textarea.press('Enter');
      }
    } else {
      await textarea.press('Enter');
    }

    await page.waitForTimeout(15000);
    await closeModal();
    await page.screenshot({
      path: `${DIR}/${String(i + 2).padStart(2, '0')}_${label}.png`,
      fullPage: true,
    });
    console.log(`  📸 ${String(i + 2).padStart(2, '0')}_${label}.png`);
  }

  // 최종 바디 텍스트 덤프
  const bodyText = await page.evaluate(() => document.body.innerText);
  fs.writeFileSync(`${DIR}/body.txt`, bodyText);

  await browser.close();
  console.log('\n✓ 완료');
}

run().catch((e) => { console.error(e); process.exit(1); });
