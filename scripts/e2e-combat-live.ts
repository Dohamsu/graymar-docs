/**
 * 창의 전투 LIVE 검증
 * 1) API로 전투 트리거 시도 (많은 FIGHT 입력)
 * 2) COMBAT 노드 진입 감지되면 창의 입력 전송
 * 3) Playwright로 각 단계 스크린샷
 */
import * as fs from 'fs';
import { chromium } from 'playwright';

const API = 'http://localhost:3000';
const CLIENT = 'http://localhost:3001';
const DIR = '/tmp/e2e-combat-live';
const EMAIL = 'playtest_1776735011@test.com'; // 36cf1680 — C2 run
const PASSWORD = 'Test1234!!';

let nextTurn = 0;
let token = '';
let runId = '';

async function api<T = unknown>(
  method: 'GET' | 'POST',
  path: string,
  body?: unknown,
): Promise<{ status: number; body: T | null }> {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return {
    status: res.status,
    body: (await res.json().catch(() => null)) as T,
  };
}

async function submit(rawInput: string, expectedNext?: number) {
  if (expectedNext === undefined) {
    expectedNext = nextTurn + 1;
  }
  const idempotencyKey = `live_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const res = await api<{
    turnNo?: number;
    transition?: { nextNodeType?: string; enterTurnNo?: number };
    meta?: { nodeOutcome?: string };
  }>('POST', `/v1/runs/${runId}/turns`, {
    input: { type: 'ACTION', text: rawInput },
    idempotencyKey,
    expectedNextTurnNo: expectedNext,
  });
  return res;
}

async function submitChoice(choiceId: string, expectedNext?: number) {
  if (expectedNext === undefined) {
    expectedNext = nextTurn + 1;
  }
  const idempotencyKey = `live_c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const res = await api<{
    turnNo?: number;
    transition?: { nextNodeType?: string; enterTurnNo?: number };
  }>('POST', `/v1/runs/${runId}/turns`, {
    input: { type: 'CHOICE', choiceId },
    idempotencyKey,
    expectedNextTurnNo: expectedNext,
  });
  return res;
}

async function getLastTurnInfo() {
  const r = await fetch(`${API}/v1/runs/${runId}?turnsLimit=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = (await r.json()) as {
    run?: { currentTurnNo: number };
    currentNode?: { nodeType: string };
    turns?: Array<{ turnNo: number; nodeType: string }>;
  };
  return {
    currentTurnNo:
      data.run?.currentTurnNo ?? data.turns?.[0]?.turnNo ?? 0,
    nodeType: data.currentNode?.nodeType ?? data.turns?.[0]?.nodeType,
  };
}

async function fetchRunInfo() {
  const r = await api<{ runId: string; currentTurnNo: number }>('GET', '/v1/runs');
  return r.body;
}

async function detectCombat(): Promise<{
  inCombat: boolean;
  currentTurnNo: number;
}> {
  const info = await getLastTurnInfo();
  return {
    inCombat: info.nodeType === 'COMBAT',
    currentTurnNo: info.currentTurnNo,
  };
}

async function main() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });

  console.log('▶ 로그인');
  const login = await api<{ token: string }>('POST', '/v1/auth/login', {
    email: EMAIL,
    password: PASSWORD,
  });
  token = login.body?.token ?? '';
  if (!token) throw new Error('로그인 실패');

  const runInfo = await fetchRunInfo();
  if (!runInfo) throw new Error('활성 런 없음');
  runId = runInfo.runId;
  nextTurn = runInfo.currentTurnNo;
  console.log(`▶ 런: ${runId}, 현재 턴: ${nextTurn}`);

  // Phase 1: 전투 트리거 — HUB CHOICE + LOCATION ACTION 반복
  console.log('\n=== Phase 1: 전투 트리거 시도 (HUB/LOCATION 노드 감지) ===');

  const hostileLocations = ['go_harbor', 'go_slums', 'go_guard']; // ambush 이벤트 있는 장소
  const aggressiveActions = [
    '깡패를 공격한다',
    '검을 휘두른다',
    '강하게 공격한다',
    '상대를 제압하려 덤벼든다',
    '주먹으로 때린다',
  ];

  let combatTurnNo: number | null = null;
  const MAX_ATTEMPTS = 20;

  for (let i = 0; i < MAX_ATTEMPTS; i++) {
    const info = await getLastTurnInfo();
    nextTurn = info.currentTurnNo;
    const nodeType = info.nodeType;
    console.log(`[${i + 1}] turn=${nextTurn}, nodeType=${nodeType}`);

    let res: Awaited<ReturnType<typeof submit>>;
    if (nodeType === 'HUB') {
      // 적대 장소 순환 이동
      const loc = hostileLocations[i % hostileLocations.length];
      console.log(`  → HUB: ${loc} 선택`);
      res = await submitChoice(loc);
    } else if (nodeType === 'LOCATION') {
      const act = aggressiveActions[i % aggressiveActions.length];
      console.log(`  → LOCATION: "${act}"`);
      res = await submit(act);
    } else if (nodeType === 'COMBAT') {
      console.log(`  🎯 이미 COMBAT — 진행`);
      combatTurnNo = nextTurn;
      break;
    } else {
      console.log(`  ⚠️ 알 수 없는 노드: ${nodeType}`);
      break;
    }

    if (res.status >= 400) {
      console.log(`    ⚠️ ${res.status}: ${JSON.stringify(res.body)?.slice(0, 120)}`);
      await new Promise((r) => setTimeout(r, 2000));
      continue;
    }
    const data = res.body as {
      turnNo?: number;
      transition?: { nextNodeType?: string; enterTurnNo?: number };
    };
    if (data.transition?.nextNodeType === 'COMBAT') {
      console.log(`    🎯 COMBAT 트리거! turn=${data.transition.enterTurnNo}`);
      combatTurnNo = data.transition.enterTurnNo ?? nextTurn + 2;
      break;
    }
    await new Promise((r) => setTimeout(r, 2500));
  }

  if (!combatTurnNo) {
    console.log('\n⚠️ 전투 트리거 실패. DB에서 최근 node_type 확인...');
    const det = await detectCombat();
    console.log(`  inCombat=${det.inCombat}, currentTurnNo=${det.currentTurnNo}`);
    if (!det.inCombat) {
      fs.writeFileSync(`${DIR}/result.txt`, 'COMBAT trigger 실패');
      return;
    }
    combatTurnNo = det.currentTurnNo;
  }

  // Playwright로 이 상태 스크린샷
  console.log('\n=== Phase 2: Playwright 스크린샷 + 창의 입력 ===');
  await new Promise((r) => setTimeout(r, 3000));

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
    await page.waitForTimeout(10000);
  }

  const closeModal = async () => {
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press('Escape').catch(() => {});
      await page.waitForTimeout(300);
    }
    const xBtn = page.locator('button[aria-label="닫기"]').first();
    if (await xBtn.isVisible({ timeout: 500 }).catch(() => false)) {
      await xBtn.click({ force: true }).catch(() => {});
      await page.waitForTimeout(300);
    }
  };

  await closeModal();
  await page.screenshot({ path: `${DIR}/01_combat_ui.png`, fullPage: true });
  console.log('📸 01_combat_ui.png');

  // Phase 3: 창의 입력 submit via API + 스크린샷
  const creatives = [
    { input: '의자를 집어 던진다', label: 'Tier1_chair' },
    { input: '드래곤 브레스!', label: 'Tier4_fantasy' },
    { input: 'HP를 회복한다', label: 'Tier5_abstract' },
  ];

  for (const { input, label } of creatives) {
    // Check if still in combat
    const det = await detectCombat();
    if (!det.inCombat) {
      console.log(`  전투 종료 — ${label} 스킵`);
      break;
    }
    nextTurn = det.currentTurnNo;

    console.log(`\n▶ [${label}] "${input}" (turn=${nextTurn + 1})`);
    const res = await submit(input);
    if (res.status >= 400) {
      console.log(`  ⚠️ ${res.status}: ${JSON.stringify(res.body)?.slice(0, 150)}`);
      continue;
    }

    // LLM 응답 대기
    await new Promise((r) => setTimeout(r, 12000));

    // Playwright 새로고침 (서버 상태 반영)
    await page.reload();
    await page.waitForTimeout(6000);
    await closeModal();

    await page.screenshot({
      path: `${DIR}/02_${label}.png`,
      fullPage: true,
    });
    console.log(`  📸 02_${label}.png`);
  }

  await browser.close();
  console.log('\n✓ 완료:', DIR);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
