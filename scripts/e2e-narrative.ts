import { chromium, type Page } from 'playwright';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const API = 'http://localhost:3000/v1';
const SCREENSHOT_DIR = '/tmp/e2e-screenshots';
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
  } catch { /* skip */ }
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

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  const email = `e2e_${Date.now()}@test.com`;
  const password = 'Test1234!!';

  console.log('=== E2E 5턴 플레이 테스트 ===\n');

  // === 1. 회원가입 (UI) ===
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
    await nicknameInput.fill('E2E테스터');
  }
  await clickText(page, '가입하기');
  await page.waitForTimeout(3000);
  await ss(page, 'registered');

  // 토큰 추출
  const token = await page.evaluate(() => localStorage.getItem('graymar_auth_token')) ?? '';
  if (!token) { console.log('❌ 토큰 없음'); await browser.close(); return; }
  console.log(`  토큰: ${token.slice(0, 20)}...`);

  // === 2. 캐릭터 생성 (UI) ===
  console.log('[2] 캐릭터 생성...');
  await clickText(page, '새 게임');
  await page.waitForTimeout(2000);

  // 프리셋 선택
  const presetCards = page.locator('button, [role="button"]');
  const cardCount = await presetCards.count();
  for (let i = 0; i < Math.min(cardCount, 15); i++) {
    const txt = await presetCards.nth(i).textContent() ?? '';
    if (txt.includes('탈영') || txt.includes('부두')) {
      await presetCards.nth(i).click();
      console.log(`  프리셋: "${txt.slice(0, 20)}"`);
      break;
    }
  }
  await page.waitForTimeout(1000);
  await clickText(page, '남성');
  await page.waitForTimeout(500);

  // 캐릭터 생성 단계 진행
  for (let step = 0; step < 10; step++) {
    const pageText = await page.textContent('body') ?? '';
    if (pageText.includes('행동을 입력') || pageText.includes('무엇을 하겠는가')) break;

    for (const btn of ['모험 시작', '모험', '다 음', '다음', '건너뛰기', '결정', '이 초상화', '확인']) {
      if (await clickText(page, btn, { timeout: 800 })) {
        console.log(`  Step ${step}: "${btn}"`);
        await page.waitForTimeout(1500);
        break;
      }
    }
  }
  await page.waitForTimeout(5000);
  await ss(page, 'game_entered');

  // === 3. 런 정보 확인 (API) ===
  const runsData = await apiCall('GET', '/runs', token) as { runId?: string; currentTurnNo?: number };
  const runId = runsData.runId;
  if (!runId) { console.log('❌ 활성 런 없음', JSON.stringify(runsData).slice(0, 200)); await browser.close(); return; }
  let currentTurn = runsData.currentTurnNo ?? 0;
  console.log(`  RunID: ${runId}, 현재 턴: ${currentTurn}`);

  // === 4. 5턴 플레이 (API 제출 + UI 확인) ===
  // 30턴 스피드런 — HUB/LOCATION 자동 판단, LLM 선택지 활용
  const LOCATION_ACTIONS = [
    '주변을 살펴본다', '사람들에게 말을 건다', '수상한 곳을 조사한다',
    '조심스럽게 잠입한다', '거래를 시도한다', '도움을 준다', '소문의 진위를 확인한다',
  ];
  const LOCATIONS = ['go_market', 'go_guard', 'go_harbor', 'go_slums'];
  const MAX_TURNS = 30;

  const issues: string[] = [];
  let locIdx = 0;
  let locTurns = 0;

  for (let i = 0; i < MAX_TURNS; i++) {
    // 런 상태 조회
    const stateRes = await apiCall('GET', `/runs/${runId}`, token) as {
      run?: { currentTurnNo: number; status: string };
      currentNode?: { nodeType: string };
      lastResult?: { choices?: { id: string }[] };
      runState?: { questState?: string; discoveredQuestFacts?: string[] };
    };
    currentTurn = stateRes.run?.currentTurnNo ?? currentTurn;
    const nodeType = stateRes.currentNode?.nodeType ?? 'HUB';
    const choices = stateRes.lastResult?.choices ?? [];
    const questState = stateRes.runState?.questState ?? '?';

    if (stateRes.run?.status === 'RUN_ENDED') { console.log('  🏁 [RUN_ENDED]'); break; }

    const turnNo = currentTurn + 1;
    let input: Record<string, unknown>;
    let desc: string;

    if (nodeType === 'HUB') {
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
        desc = `HUB:fallback`;
        locIdx++;
      }
      locTurns = 0;
    } else {
      locTurns++;
      if (locTurns > 5) {
        input = { type: 'ACTION', text: '다른 장소로 이동한다' };
        desc = 'LOC:이동';
        locTurns = 0;
        locIdx++;
      } else if (choices.length > 0) {
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
      console.log('  ⚠️ 409');
      const st = await apiCall('GET', `/runs/${runId}`, token) as { run?: { currentTurnNo: number } };
      currentTurn = st.run?.currentTurnNo ?? currentTurn;
      continue;
    }

    const submittedTurn = (submitRes as { turnNo?: number }).turnNo ?? turnNo;
    console.log(`  제출 (turnNo=${submittedTurn})`);

    console.log('  LLM 대기...');
    const llmStatus = await pollLlm(runId, submittedTurn, token);
    console.log(`  LLM: ${llmStatus}`);

    currentTurn = submittedTurn;

    // UI 새로고침 → "이어하기" 클릭 → 게임 화면 진입 → 스크린샷
    await page.reload();
    await page.waitForTimeout(3000);
    await clickText(page, '이어하기', { timeout: 3000 });
    await page.waitForTimeout(8000); // 타이핑 애니메이션 대기
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000);
    await ss(page, `turn_${i + 1}_${desc}`);

    // 검증
    const pageText = await page.textContent('body') ?? '';
    const atTag = (pageText.match(/@\[/g) ?? []).length;
    const npcId = (pageText.match(/@NPC_/g) ?? []).length;
    const portraitUrl = (pageText.match(/npc-portraits\//g) ?? []).length;
    const metaNarr = /이전 턴에|플레이어가|턴 \d+에서/.test(pageText);

    console.log(`  검증: @태그=${atTag} @NPC_=${npcId} portrait=${portraitUrl} 메타=${metaNarr ? 'Y' : 'N'}`);

    if (atTag > 0) issues.push(`턴${i + 1}: @태그 ${atTag}건 노출`);
    if (npcId > 0) issues.push(`턴${i + 1}: @NPC_ ${npcId}건 노출`);
    if (portraitUrl > 0) issues.push(`턴${i + 1}: portrait URL ${portraitUrl}건 노출`);
    if (metaNarr) issues.push(`턴${i + 1}: 메타 서술`);
  }

  // === 5. 최종 검증 ===
  console.log('\n[최종] 전체 화면 캡처...');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(1000);
  await ss(page, 'final_top');

  // 중간으로 스크롤
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
  await page.waitForTimeout(500);
  await ss(page, 'final_mid');

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await ss(page, 'final_bottom');

  // 이슈 요약
  if (issues.length > 0) {
    console.log('\n━━ 발견된 이슈 ━━');
    for (const issue of issues) console.log(`  ❌ ${issue}`);
  } else {
    console.log('\n━━ 이슈 없음 ✅ ━━');
  }

  console.log('\n=== E2E 테스트 완료 ===');
  console.log(`스크린샷: ${SCREENSHOT_DIR}/`);

  await browser.close();
}

run().catch(console.error);
