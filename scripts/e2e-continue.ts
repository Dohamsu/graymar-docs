import { chromium, type Page } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const API = 'http://localhost:3000/v1';
const SCREENSHOT_DIR = '/tmp/e2e-screenshots-continue';
let stepNum = 0;

async function ss(page: Page, name: string) {
  stepNum++;
  const filename = `${String(stepNum).padStart(2, '0')}_${name}`;
  await page.screenshot({ path: `${SCREENSHOT_DIR}/${filename}.png`, fullPage: true });
  console.log(`  📸 ${filename}.png`);
}

async function clickText(page: Page, text: string, options?: { force?: boolean; timeout?: number }) {
  try {
    const btn = page.getByText(text, { exact: false });
    if (await btn.isVisible({ timeout: options?.timeout ?? 3000 }).catch(() => false)) {
      const isDisabled = await btn.isDisabled().catch(() => false);
      if (isDisabled) return false;
      await btn.click({ force: options?.force, timeout: 5000 });
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
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  for (const f of fs.readdirSync(SCREENSHOT_DIR)) {
    if (f.endsWith('.png')) fs.unlinkSync(`${SCREENSHOT_DIR}/${f}`);
  }

  const email = 'e2e_1775993715673@test.com';
  const password = 'Test1234!!';
  const runId = '084eeaa6-1aec-4242-8d15-1b1cf18627a0';

  // 로그인
  const loginRes = await apiCall('POST', '/auth/login', '', { email, password }) as { token?: string };
  const token = loginRes.token ?? '';
  if (!token) { console.log('❌ 로그인 실패'); return; }

  // 현재 턴 확인
  const runState = await apiCall('GET', `/runs/${runId}`, token) as { run?: { currentTurnNo: number; status: string } };
  let currentTurn = runState.run?.currentTurnNo ?? 9;
  console.log(`=== 이어하기 10턴 (현재 T${currentTurn}) ===\n`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();

  // 로그인 + 이어하기
  await page.goto(`${BASE}/play`);
  await page.waitForTimeout(2000);
  await clickText(page, '시작하기', { force: true });
  await page.waitForTimeout(1000);
  // 로그인 탭
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await clickText(page, '로그인', { timeout: 2000 });
  await page.waitForTimeout(3000);
  await clickText(page, '이어하기');
  await page.waitForTimeout(5000);
  await ss(page, 'resumed');

  const LOCATION_ACTIONS = [
    '주변을 살펴본다', '사람들에게 말을 건다', '수상한 곳을 조사한다',
    '위협한다', '조심스럽게 잠입한다', '거래를 시도한다',
    '도움을 준다', '소문의 진위를 확인한다',
  ];
  const LOCATIONS = ['go_market', 'go_guard', 'go_harbor', 'go_slums'];
  let locIdx = 0;
  let locTurns = 0;

  const issues: string[] = [];

  const MAX_TURNS = 10;
  for (let i = 0; i < MAX_TURNS; i++) {
    // 런 상태 조회 — HUB vs LOCATION 판단
    const stateRes = await apiCall('GET', `/runs/${runId}`, token) as {
      run?: { currentTurnNo: number; status: string };
      currentNode?: { nodeType: string };
      lastResult?: { choices?: { id: string }[] };
      runState?: { questState?: string };
    };
    currentTurn = stateRes.run?.currentTurnNo ?? currentTurn;
    const nodeType = stateRes.currentNode?.nodeType ?? 'HUB';
    const choices = stateRes.lastResult?.choices ?? [];
    const questState = stateRes.runState?.questState ?? '?';

    if (stateRes.run?.status === 'RUN_ENDED') { console.log('  🏁 [RUN_ENDED] — 엔딩 도달!'); break; }

    const turnNo = currentTurn + 1;
    let input: Record<string, unknown>;
    let desc: string;

    if (nodeType === 'HUB') {
      // HUB: CHOICE로 장소 이동
      // 장소 순환: 퀘스트 수락 → 다양한 장소 순환
      const questChoice = choices.find(c => c.id === 'accept_quest');
      const goChoices = choices.filter(c => c.id.startsWith('go_'));
      if (questChoice && locIdx === 0) {
        input = { type: 'CHOICE', choiceId: questChoice.id };
        desc = `HUB:${questChoice.id}`;
      } else if (goChoices.length > 0) {
        const pick = goChoices[locIdx % goChoices.length];
        input = { type: 'CHOICE', choiceId: pick.id };
        desc = `HUB:${pick.id}`;
        locIdx++;
      } else if (choices.length > 0) {
        input = { type: 'CHOICE', choiceId: choices[0].id };
        desc = `HUB:${choices[0].id}`;
      } else {
        input = { type: 'CHOICE', choiceId: LOCATIONS[locIdx % LOCATIONS.length] };
        desc = `HUB:${LOCATIONS[locIdx % LOCATIONS.length]}`;
        locIdx++;
      }
      locTurns = 0;
    } else {
      // LOCATION: LLM 생성 선택지 우선 사용 (스피드런)
      locTurns++;
      if (locTurns > 5) {
        input = { type: 'ACTION', text: '다른 장소로 이동한다' };
        desc = 'LOC:이동';
        locTurns = 0;
        locIdx++;
      } else if (choices.length > 0) {
        // LLM 선택지 중 go_hub 제외하고 랜덤 선택
        const filtered = choices.filter(c => c.id !== 'go_hub');
        const pick = filtered.length > 0
          ? filtered[Math.floor(Math.random() * filtered.length)]
          : choices[0];
        input = { type: 'CHOICE', choiceId: pick.id };
        desc = `LOC:${pick.id.slice(0, 12)}`;
      } else {
        const action = LOCATION_ACTIONS[(i + locTurns) % LOCATION_ACTIONS.length];
        input = { type: 'ACTION', text: action };
        desc = `LOC:${action.slice(0, 6)}`;
      }
    }

    console.log(`\n[턴 ${i + 1}/${MAX_TURNS}] ${desc} (T${turnNo}, ${nodeType}, ${questState})...`);

    const submitRes = await apiCall('POST', `/runs/${runId}/turns`, token, {
      input,
      expectedNextTurnNo: turnNo,
      idempotencyKey: crypto.randomUUID(),
    });

    if ((submitRes as { statusCode?: number }).statusCode === 409) {
      console.log('  ⚠️ 409 — 턴 번호 재조회');
      const st = await apiCall('GET', `/runs/${runId}`, token) as { run?: { currentTurnNo: number } };
      currentTurn = st.run?.currentTurnNo ?? currentTurn;
      continue;
    }

    const submitted = (submitRes as { turnNo?: number }).turnNo ?? turnNo;
    console.log(`  제출 (turnNo=${submitted})`);

    const llmStatus = await pollLlm(runId, submitted, token);
    console.log(`  LLM: ${llmStatus}`);
    currentTurn = submitted;

    // UI 확인
    await page.reload();
    await page.waitForTimeout(2000);
    await clickText(page, '이어하기', { timeout: 2000 });
    await page.waitForTimeout(8000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);
    await ss(page, `turn_${i + 1}_${desc}`);

    // 검증
    const pageText = await page.textContent('body') ?? '';
    const atTag = (pageText.match(/@\[/g) ?? []).length;
    const npcId = (pageText.match(/@NPC_/g) ?? []).length;
    const portrait = (pageText.match(/npc-portraits\//g) ?? []).length;
    const meta = /이전 턴에|플레이어가|턴 \d+에서/.test(pageText);
    console.log(`  검증: @태그=${atTag} @NPC_=${npcId} portrait=${portrait} 메타=${meta ? 'Y' : 'N'}`);

    if (atTag > 0) issues.push(`T${submitted}: @태그 ${atTag}건`);
    if (npcId > 0) issues.push(`T${submitted}: @NPC_ ${npcId}건`);
    if (portrait > 0) issues.push(`T${submitted}: portrait ${portrait}건`);
    if (meta) issues.push(`T${submitted}: 메타`);
  }

  // 최종
  await page.evaluate(() => window.scrollTo(0, 0));
  await ss(page, 'final_top');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await ss(page, 'final_bottom');

  if (issues.length > 0) {
    console.log('\n━━ 이슈 ━━');
    for (const issue of issues) console.log(`  ❌ ${issue}`);
  } else {
    console.log('\n━━ 이슈 없음 ✅ ━━');
  }

  console.log(`\n=== 완료 (총 ${currentTurn}턴) ===`);
  await browser.close();
}

run().catch(console.error);
