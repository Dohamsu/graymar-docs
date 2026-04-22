import * as fs from 'fs';
import { chromium } from 'playwright';

const API = 'http://localhost:3000';
const CLIENT = 'http://localhost:3001';
const DIR = '/tmp/e2e-combat-api';
const EMAIL = 'playtest_1776660357@test.com';
const PASSWORD = 'Test1234!!';

async function post(path: string, body: unknown, token?: string) {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json().catch(() => null) };
}

async function get(path: string, token?: string) {
  const res = await fetch(`${API}${path}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  return { status: res.status, body: await res.json().catch(() => null) };
}

async function main() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });

  console.log('▶ 로그인');
  const login = await post('/v1/auth/login', { email: EMAIL, password: PASSWORD });
  const token = (login.body as { token?: string })?.token;
  if (!token) throw new Error('로그인 실패');

  console.log('▶ 활성 런 조회');
  const runsRes = await get('/v1/runs', token);
  const data = runsRes.body as { runId?: string; currentTurnNo?: number } | null;
  if (!data?.runId) throw new Error('활성 런 없음');
  const runId = data.runId;
  console.log(`  runId: ${runId}`);

  let expectedNextTurnNo = data.currentTurnNo ?? 0;
  console.log(`  현재 턴: ${expectedNextTurnNo}`);

  const submitTurn = async (rawInput: string) => {
    expectedNextTurnNo += 1;
    const idempotencyKey = `creative_test_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const res = await post(
      `/v1/runs/${runId}/turns`,
      {
        input: { type: 'ACTION', rawInput },
        idempotencyKey,
        expectedNextTurnNo,
      },
      token,
    );
    // 실패 시 턴 번호 복구
    if (res.status >= 400) expectedNextTurnNo -= 1;
    // transition 있으면 +1 추가
    const body = res.body as { transition?: { enterTurnNo?: number } };
    if (body?.transition?.enterTurnNo) {
      expectedNextTurnNo = body.transition.enterTurnNo;
    }
    return res;
  };

  const lastTurn = expectedNextTurnNo;

  // 1) FIGHT 시도 반복 → 전투 트리거
  console.log('\n=== Phase 1: 공격적 행동 반복 → 전투 트리거 시도 ===');
  const aggressiveInputs = [
    '경비대로 이동한다',
    '경비병에게 덤벼든다',
    '경비병을 공격한다',
    '검을 뽑아 경비병을 겨눈다',
    '경비병을 주먹으로 친다',
    '경비병을 무력으로 제압하려 한다',
    '경비병에게 달려든다',
    '적을 공격한다',
    '칼을 휘두른다',
    '경비병에게 검을 휘두른다',
  ];

  let combatTurn: number | null = null;
  for (let i = 0; i < aggressiveInputs.length; i++) {
    const input = aggressiveInputs[i];
    console.log(`\n[${i + 1}/${aggressiveInputs.length}] "${input}"`);
    const res = await submitTurn(input);
    const data = res.body as {
      transition?: { nextNodeType?: string };
      meta?: { nodeOutcome?: string };
    };
    console.log(`  status: ${res.status}, nextNodeType: ${data?.transition?.nextNodeType ?? 'N/A'}`);
    if (data?.transition?.nextNodeType === 'COMBAT') {
      console.log('  🎯 COMBAT 트리거 성공!');
      combatTurn = (lastTurn as number) + i + 2;
      break;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }

  if (!combatTurn) {
    console.log('\n⚠️ 전투 트리거 실패 — FIGHT 10회 시도');
    fs.writeFileSync(`${DIR}/result.txt`, '전투 트리거 실패');
    process.exit(1);
  }

  // 2) 전투 중 창의 입력
  console.log('\n=== Phase 2: 전투 중 창의 입력 ===');
  await new Promise((r) => setTimeout(r, 3000));

  const creativeInputs = [
    { input: '의자를 집어 던진다', label: 'Tier1_chair' },
    { input: '드래곤 브레스!', label: 'Tier4_fantasy' },
    { input: 'HP를 회복한다', label: 'Tier5_abstract' },
    { input: '정면에서 검을 휘두른다', label: 'Tier3_normal' },
  ];

  const results: Array<{ input: string; label: string; turnNo?: number }> = [];
  for (const { input, label } of creativeInputs) {
    console.log(`\n▶ [${label}] "${input}"`);
    const res = await submitTurn(input);
    const data = res.body as { turnNo?: number };
    console.log(`  status: ${res.status}, turnNo: ${data?.turnNo}`);
    results.push({ input, label, turnNo: data?.turnNo });
    await new Promise((r) => setTimeout(r, 6000)); // LLM 대기
  }

  // 3) 클라이언트 스크린샷 (현재 상태)
  console.log('\n=== Phase 3: 클라이언트 스크린샷 ===');
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
    await page.waitForTimeout(8000);
  }

  // 모달 제거
  await page.keyboard.press('Escape').catch(() => {});
  await page.waitForTimeout(500);

  await page.screenshot({ path: `${DIR}/client_current_state.png`, fullPage: true });
  console.log(`📸 ${DIR}/client_current_state.png`);

  await browser.close();

  fs.writeFileSync(
    `${DIR}/result.json`,
    JSON.stringify({ runId, combatTurn, results }, null, 2),
  );
  console.log('\n✓ 완료:', DIR);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
