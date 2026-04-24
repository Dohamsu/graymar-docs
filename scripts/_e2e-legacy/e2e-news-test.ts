import { chromium, type Page } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const API = 'http://localhost:3000/v1';
const DIR = '/tmp/e2e-news';
let stepNum = 0;

async function ss(page: Page, name: string) {
  stepNum++;
  const filename = `${String(stepNum).padStart(2, '0')}_${name}`;
  await page.screenshot({ path: `${DIR}/${filename}.png`, fullPage: true });
  console.log(`  📸 ${filename}.png`);
}

async function clickText(page: Page, text: string, opts?: { force?: boolean; timeout?: number }) {
  try {
    const btn = page.getByText(text, { exact: false });
    if (await btn.isVisible({ timeout: opts?.timeout ?? 3000 }).catch(() => false)) {
      if (await btn.isDisabled().catch(() => false)) return false;
      await btn.click({ force: opts?.force, timeout: 5000 });
      await page.waitForTimeout(1000);
      return true;
    }
  } catch {}
  return false;
}

async function apiCall(method: string, path: string, token: string, body?: unknown) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return res.json() as Promise<Record<string, unknown>>;
}

async function pollLlm(runId: string, turnNo: number, token: string, maxWait = 90) {
  const start = Date.now();
  while (Date.now() - start < maxWait * 1000) {
    const data = await apiCall('GET', `/runs/${runId}/turns/${turnNo}`, token);
    const status = (data.llm as Record<string, unknown>)?.status as string;
    if (status === 'DONE' || status === 'FAILED' || status === 'SKIPPED') return status;
    await new Promise(r => setTimeout(r, 3000));
  }
  return 'TIMEOUT';
}

async function run() {
  fs.mkdirSync(DIR, { recursive: true });
  for (const f of fs.readdirSync(DIR)) {
    if (f.endsWith('.png')) fs.unlinkSync(`${DIR}/${f}`);
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const email = `e2e_${Date.now()}@test.com`;
  const password = 'Test1234!!';

  console.log('=== E2E 호외/posture 테스트 ===\n');

  // 회원가입
  console.log('[1] 회원가입...');
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(2000);
  await clickText(page, '시작하기', { force: true });
  await page.waitForTimeout(1000);
  await clickText(page, '회원가입');
  await page.waitForTimeout(500);
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  const nicknameInput = page.locator('input[name="nickname"]');
  if (await nicknameInput.isVisible({ timeout: 1000 }).catch(() => false)) {
    await nicknameInput.fill('호외테스터');
  }
  await clickText(page, '가입하기');
  await page.waitForTimeout(3000);

  const token = await page.evaluate(() => localStorage.getItem('graymar_auth_token')) ?? '';
  if (!token) { console.log('❌ 토큰 없음'); await browser.close(); return; }
  console.log(`  토큰: ${token.slice(0, 20)}...`);

  // 캐릭터 생성
  console.log('[2] 캐릭터 생성...');
  await clickText(page, '새 게임');
  await page.waitForTimeout(2000);

  const presets = page.locator('button, [role="button"]');
  const cnt = await presets.count();
  for (let i = 0; i < Math.min(cnt, 15); i++) {
    const txt = await presets.nth(i).textContent() ?? '';
    if (txt.includes('탈영') || txt.includes('부두')) {
      await presets.nth(i).click();
      break;
    }
  }
  await page.waitForTimeout(1000);
  await clickText(page, '남성');
  await page.waitForTimeout(500);

  for (let step = 0; step < 10; step++) {
    const bodyText = await page.textContent('body') ?? '';
    if (bodyText.includes('행동을 입력') || bodyText.includes('무엇을 하겠는가')) break;
    for (const btn of ['모험 시작', '모험', '다 음', '다음', '건너뛰기', '결정', '이 초상화', '확인']) {
      if (await clickText(page, btn, { timeout: 800 })) {
        await page.waitForTimeout(1500);
        break;
      }
    }
  }
  await page.waitForTimeout(5000);

  // 런 정보
  const runsData = await apiCall('GET', '/runs', token) as { runId?: string; currentTurnNo?: number };
  const runId = runsData.runId;
  if (!runId) { console.log('❌ 활성 런 없음'); await browser.close(); return; }
  let currentTurn = runsData.currentTurnNo ?? 0;
  console.log(`  RunID: ${runId}, 현재 턴: ${currentTurn}`);

  // 10턴 플레이 — NPC와 적극적 상호작용하여 posture 변화 유도
  const ACTIONS = [
    '사람들에게 말을 건다',
    '위협한다',
    '도움을 준다',
    '뇌물을 건넨다',
    '수상한 곳을 조사한다',
    '싸움을 건다',
    '설득한다',
    '주변을 살펴본다',
  ];
  const LOCATIONS = ['go_market', 'go_guard', 'go_harbor', 'go_slums'];
  let locIdx = 0;
  let locTurns = 0;

  const MAX_TURNS = 10;
  for (let i = 0; i < MAX_TURNS; i++) {
    const stateRes = await apiCall('GET', `/runs/${runId}`, token) as {
      run?: { currentTurnNo: number; status: string };
      currentNode?: { nodeType: string };
      lastResult?: { choices?: { id: string }[] };
    };
    currentTurn = stateRes.run?.currentTurnNo ?? currentTurn;
    const nodeType = stateRes.currentNode?.nodeType ?? 'HUB';
    const choices = stateRes.lastResult?.choices ?? [];

    if (stateRes.run?.status === 'RUN_ENDED') break;

    const turnNo = currentTurn + 1;
    let input: Record<string, unknown>;
    let desc: string;

    if (nodeType === 'HUB') {
      const questChoice = choices.find(c => c.id === 'accept_quest');
      const goChoices = choices.filter(c => c.id.startsWith('go_'));
      if (questChoice && i === 0) {
        input = { type: 'CHOICE', choiceId: questChoice.id };
        desc = `HUB:${questChoice.id}`;
      } else if (goChoices.length > 0) {
        const pick = goChoices[locIdx % goChoices.length];
        input = { type: 'CHOICE', choiceId: pick.id };
        desc = `HUB:${pick.id}`;
        locIdx++;
      } else {
        input = { type: 'CHOICE', choiceId: LOCATIONS[locIdx % LOCATIONS.length] };
        desc = `HUB:fallback`;
        locIdx++;
      }
      locTurns = 0;
    } else {
      locTurns++;
      // 적극적 행동으로 posture 변화 유도
      const action = ACTIONS[i % ACTIONS.length];
      input = { type: 'ACTION', text: action };
      desc = `LOC:${action.slice(0, 6)}`;
    }

    console.log(`\n[턴 ${i + 1}/${MAX_TURNS}] ${desc} (T${turnNo}, ${nodeType})...`);

    const submitRes = await apiCall('POST', `/runs/${runId}/turns`, token, {
      input,
      expectedNextTurnNo: turnNo,
      idempotencyKey: crypto.randomUUID(),
    });

    if ((submitRes as { statusCode?: number }).statusCode === 409) {
      console.log('  ⚠️ 409');
      const st = await apiCall('GET', `/runs/${runId}`, token) as { run?: { currentTurnNo: number } };
      currentTurn = st.run?.currentTurnNo ?? currentTurn;
      continue;
    }

    const submitted = (submitRes as { turnNo?: number }).turnNo ?? turnNo;
    console.log(`  제출 (turnNo=${submitted})`);

    console.log('  LLM 대기...');
    const llmStatus = await pollLlm(runId, submitted, token);
    console.log(`  LLM: ${llmStatus}`);
    currentTurn = submitted;

    // UI 확인 — 새로고침 후 이어하기
    await page.reload();
    await page.waitForTimeout(3000);
    await clickText(page, '이어하기', { timeout: 3000 });
    await page.waitForTimeout(3000);

    // 호외 모달이 떴는지 확인
    const hasNews = await page.locator('text=그레이마르 호외').isVisible({ timeout: 2000 }).catch(() => false);
    if (hasNews) {
      console.log('  📰 호외 모달 감지!');
      await ss(page, `turn_${i + 1}_NEWS`);
      // 호외 닫기
      await clickText(page, '닫기', { timeout: 2000 });
      await page.waitForTimeout(1000);
    }

    // 타이핑 애니메이션 대기
    await page.waitForTimeout(5000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await ss(page, `turn_${i + 1}_${desc.replace(/[^a-zA-Z0-9가-힣]/g, '_')}`);

    // posture 변화 텍스트 확인
    const bodyText = await page.textContent('body') ?? '';
    const postureMatch = bodyText.match(/태도가 변했다/);
    if (postureMatch) {
      console.log('  🔄 Posture 변화 감지!');
    }

    // 시그널 피드 확인
    const turnData = await apiCall('GET', `/runs/${runId}/turns/${submitted}`, token) as {
      serverResult?: { ui?: { signalFeed?: Array<{ id: string; text: string; severity: number }> } };
    };
    const signals = turnData.serverResult?.ui?.signalFeed ?? [];
    const important = signals.filter(s => s.severity >= 3);
    if (important.length > 0) {
      console.log(`  📰 중요 시그널 ${important.length}건: ${important.map(s => s.text.slice(0, 30)).join(' | ')}`);
    }
  }

  // 최종 캡처
  console.log('\n[최종]');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await ss(page, 'final');

  await browser.close();
  console.log(`\n=== 완료 ===\n스크린샷: ${DIR}/`);
}

run().catch(console.error);
