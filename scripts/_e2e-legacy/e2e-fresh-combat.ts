/**
 * Fresh run → LOC_SLUMS 강제 이동 → FIGHT → combat 트리거 → 창의 입력
 */
import * as fs from 'fs';
import { chromium } from 'playwright';

const API = 'http://localhost:3000';
const CLIENT = 'http://localhost:3001';
const DIR = '/tmp/e2e-fresh-combat';

const EMAIL = `combat_test_${Date.now()}@test.com`;
const PASSWORD = 'Test1234!!';
const NICKNAME = `전투테스트${Date.now() % 10000}`;

let token = '';
let runId = '';

async function api<T = unknown>(
  method: 'GET' | 'POST',
  path: string,
  body?: unknown,
) {
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

async function getInfo() {
  const r = await fetch(`${API}/v1/runs/${runId}?turnsLimit=1`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const d = (await r.json()) as {
    run?: { currentTurnNo: number };
    currentNode?: { nodeType: string };
  };
  return {
    turn: d.run?.currentTurnNo ?? 0,
    nodeType: d.currentNode?.nodeType,
  };
}

async function submitAction(text: string, expected: number) {
  return api('POST', `/v1/runs/${runId}/turns`, {
    input: { type: 'ACTION', text },
    idempotencyKey: `t_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    expectedNextTurnNo: expected,
  });
}
async function submitChoice(choiceId: string, expected: number) {
  return api('POST', `/v1/runs/${runId}/turns`, {
    input: { type: 'CHOICE', choiceId },
    idempotencyKey: `c_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    expectedNextTurnNo: expected,
  });
}

async function main() {
  fs.rmSync(DIR, { recursive: true, force: true });
  fs.mkdirSync(DIR, { recursive: true });

  console.log('▶ 회원가입');
  const reg = await api<{ token: string }>('POST', '/v1/auth/register', {
    email: EMAIL,
    password: PASSWORD,
    nickname: NICKNAME,
  });
  if (!reg.body?.token) {
    console.log('등록 실패:', reg.status, reg.body);
    process.exit(1);
  }
  token = reg.body.token;
  console.log(`  ${EMAIL}`);

  console.log('\n▶ 런 생성 (DESERTER — 균형 전투형)');
  const r = await api<{ run: { id: string } }>('POST', '/v1/runs', {
    presetId: 'DESERTER',
    gender: 'male',
    characterName: '전투테스터',
  });
  if (!r.body?.run?.id) {
    console.log('런 생성 실패:', r.status, r.body);
    process.exit(1);
  }
  runId = r.body.run.id;
  console.log(`  runId=${runId}`);

  // HUB → SLUMS 이동 (BLOCK 무조건 이벤트: EVT_SLUMS_AMBUSH)
  let info = await getInfo();
  console.log(`\n▶ 초기 상태: turn=${info.turn}, node=${info.nodeType}`);

  let combatTriggered = false;
  let combatTurnNo: number | null = null;
  const MAX_ATTEMPTS = 40;

  for (let i = 0; i < MAX_ATTEMPTS && !combatTriggered; i++) {
    info = await getInfo();
    console.log(`[${i + 1}] turn=${info.turn}, node=${info.nodeType}`);

    let res: Awaited<ReturnType<typeof submitAction>>;
    if (info.nodeType === 'HUB') {
      // 빈민가로 이동 (EVT_SLUMS_AMBUSH 있음)
      console.log('  → HUB: go_slums');
      res = await submitChoice('go_slums', info.turn + 1);
    } else if (info.nodeType === 'LOCATION') {
      const actions = [
        '가장 가까운 깡패를 공격한다',
        '강하게 주먹을 휘두른다',
        '칼을 뽑아 덤벼든다',
        '위협적으로 다가간다',
      ];
      const act = actions[i % actions.length];
      console.log(`  → LOCATION: "${act}"`);
      res = await submitAction(act, info.turn + 1);
    } else if (info.nodeType === 'COMBAT') {
      combatTriggered = true;
      combatTurnNo = info.turn;
      console.log(`  🎯 COMBAT 감지! turn=${info.turn}`);
      break;
    } else {
      console.log(`  ⚠️ unexpected node: ${info.nodeType}`);
      break;
    }

    if (res.status >= 400) {
      console.log(`    ⚠️ ${res.status}: ${JSON.stringify(res.body)?.slice(0, 140)}`);
      await new Promise((r) => setTimeout(r, 1000));
      continue;
    }
    const data = res.body as {
      transition?: { nextNodeType?: string; enterTurnNo?: number };
    };
    if (data?.transition?.nextNodeType === 'COMBAT') {
      combatTriggered = true;
      combatTurnNo = data.transition.enterTurnNo ?? info.turn + 2;
      console.log(`    🎯 COMBAT 트리거! turn=${combatTurnNo}`);
      break;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }

  if (!combatTriggered) {
    console.log('\n⚠️ MAX_ATTEMPTS 소진 — combat 미트리거');
    fs.writeFileSync(`${DIR}/result.txt`, 'no combat');
    process.exit(1);
  }

  // Phase 2: Playwright 스크린샷 + 창의 입력
  console.log('\n=== Phase 2: Playwright + 창의 입력 ===');
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
    await page.waitForTimeout(12000);
  }

  const closeModal = async () => {
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press('Escape').catch(() => {});
      await page.waitForTimeout(400);
    }
  };
  await closeModal();

  await page.screenshot({ path: `${DIR}/01_combat_fresh_ui.png`, fullPage: true });
  console.log('📸 01_combat_fresh_ui.png');

  // 창의 입력 테스트
  const creatives = [
    { input: '의자를 집어 던진다', label: 'Tier1_chair' },
    { input: '드래곤 브레스!', label: 'Tier4_fantasy' },
    { input: 'HP를 회복한다', label: 'Tier5_abstract' },
  ];

  const enterGameAgain = async () => {
    await page.goto(`${CLIENT}/play`);
    await page.waitForTimeout(2500);
    const resume2 = page.getByRole('button', { name: /이어하기/ });
    if (await resume2.isVisible({ timeout: 3000 }).catch(() => false)) {
      await resume2.click();
      await page.waitForTimeout(12000);
    }
    await closeModal();
  };

  for (const { input, label } of creatives) {
    info = await getInfo();
    if (info.nodeType !== 'COMBAT') {
      console.log(`  ${label} 스킵 (node=${info.nodeType})`);
      break;
    }
    console.log(`\n▶ [${label}] "${input}" (turn=${info.turn + 1})`);
    const res = await submitAction(input, info.turn + 1);
    if (res.status >= 400) {
      console.log(`  ⚠️ ${res.status}: ${JSON.stringify(res.body)?.slice(0, 120)}`);
      continue;
    }
    // LLM 응답 대기
    await new Promise((r) => setTimeout(r, 14000));
    // SPA 재진입
    await enterGameAgain();
    await page.screenshot({ path: `${DIR}/02_${label}.png`, fullPage: true });
    console.log(`  📸 02_${label}.png`);
  }

  await browser.close();
  fs.writeFileSync(
    `${DIR}/result.json`,
    JSON.stringify({ runId, combatTurnNo, email: EMAIL }, null, 2),
  );
  console.log('\n✓ 완료:', DIR);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
