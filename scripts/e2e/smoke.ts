/**
 * smoke.ts — 5분 이내 핵심 플로우 체크
 *
 * 목적: PR / 배포 직후 기본 정상 동작 검증.
 * 범위:
 *  1. API 헬스 + 서버 버전 확인
 *  2. 회원가입 → 로그인 → 런 생성 → 3턴 실행
 *  3. 서술/이벤트/판정 최소 1건 이상 생성되는지 확인
 *  4. (선택) 브라우저 진입 · 타이틀 렌더 · 버튼 가시성
 *
 * 실행:
 *   pnpm exec tsx scripts/e2e/smoke.ts
 *   HEADLESS=false SERVER_BASE=https://api.dimtale.com/v1 CLIENT_BASE=https://dimtale.com pnpm exec tsx scripts/e2e/smoke.ts
 */

import {
  ApiClient,
  launchBrowser,
  pickTurnInput,
  SERVER_BASE,
  CLIENT_BASE,
  sleep,
  type TurnLog,
} from "./_helpers.js";

async function main() {
  const start = Date.now();
  console.log("═══ smoke.ts 시작 ═══");
  console.log(`SERVER_BASE: ${SERVER_BASE}`);
  console.log(`CLIENT_BASE: ${CLIENT_BASE}`);

  // 1. 서버 버전
  const version = await fetch(`${SERVER_BASE.replace(/\/v1$/, "")}/v1/version`).then((r) => r.json()).catch(() => null);
  if (!version) throw new Error("서버 버전 조회 실패");
  console.log(`✅ 서버: ${version.server} · uptime ${version.uptime}s`);

  // 2. 신규 회원가입 → 런 생성
  const api = new ApiClient();
  const email = `smoke_${Date.now()}@test.com`;
  await api.register(email);
  console.log(`✅ 회원가입: ${email}`);

  const runResp = await api.createRun("DESERTER", "male");
  const runId = runResp.run.id;
  console.log(`✅ 런 생성: ${runId} · node=${runResp.currentNode?.nodeType}`);

  // 3. 3턴 실행
  const turnLogs: TurnLog[] = [];
  let locIdx = 0;
  let locTurns = 0;
  let lastResult = runResp.lastResult ?? {};

  for (let i = 0; i < 3; i++) {
    const state = await api.getRun(runId);
    if (state.run?.status === "RUN_ENDED") break;
    const { body, description } = pickTurnInput(state, lastResult, { locIdx, locTurns, locLimit: 4, choiceRate: 0.3 });
    const submit = await api.submitTurn(runId, body);
    if (submit.status !== 200 && submit.status !== 201) {
      console.log(`❌ T${i + 1} 턴 제출 실패: ${submit.status}`);
      continue;
    }
    const submitted = submit.body.turnNo ?? state.run.currentTurnNo + 1;
    const llm = await api.pollLlm(runId, submitted, 60_000);
    const serverResult = submit.body.serverResult ?? {};
    const events = (serverResult.events ?? []).map((e: any) => e.kind ?? "");
    const resolve = serverResult.ui?.resolveOutcome ?? null;
    const nodeOutcome = submit.body.meta?.nodeOutcome ?? "";
    const portrait = serverResult.ui?.npcPortrait ?? null;
    turnLogs.push({
      turn: i + 1,
      nodeType: state.currentNode?.nodeType ?? "",
      input: description,
      eventId: serverResult.ui?.actionContext?.eventId ?? "",
      resolveOutcome: resolve,
      nodeOutcome,
      events,
      narrative: llm.output,
      npcPortrait: portrait,
      rawInput: body.input?.text ?? "",
      latencyMs: llm.elapsedMs,
    });
    console.log(`  T${i + 1} [${state.currentNode?.nodeType}] ${description.padEnd(30).slice(0, 30)} resolve=${resolve ?? "-"} events=${events.length} llm=${llm.elapsedMs}ms`);
    if (body.input.type === "CHOICE") {
      lastResult = submit.body.serverResult ?? lastResult;
    }
    if (state.currentNode?.nodeType === "LOCATION") locTurns++;
    if (nodeOutcome === "NODE_ENDED" && state.currentNode?.nodeType !== "HUB") {
      locIdx++;
      locTurns = 0;
    }
  }

  // 4. 필수 조건 assert
  const failures: string[] = [];
  if (turnLogs.length < 3) failures.push(`턴 수 부족: ${turnLogs.length}/3`);
  const anyNarrative = turnLogs.some((t) => t.narrative && t.narrative.length > 50);
  if (!anyNarrative) failures.push("서술 전혀 생성 안됨");
  const anyEvent = turnLogs.some((t) => t.events.length > 0);
  if (!anyEvent) failures.push("이벤트 전혀 생성 안됨");
  const anyResolve = turnLogs.some((t) => t.resolveOutcome);
  if (!anyResolve) failures.push("resolveOutcome 전혀 없음");
  const latencies = turnLogs.map((t) => t.latencyMs ?? 0).filter((x) => x > 0);
  const avgLatency = latencies.length ? latencies.reduce((a, b) => a + b, 0) / latencies.length : 0;
  if (avgLatency > 10_000) failures.push(`LLM 평균 latency ${Math.round(avgLatency)}ms > 10s`);

  // 5. (선택) 브라우저 가시성 — SMOKE_NO_BROWSER=1 이면 스킵
  let browserOk: boolean | null = null;
  if (process.env.SMOKE_NO_BROWSER !== "1") {
    try {
      const { browser, page } = await launchBrowser();
      await page.goto(`${CLIENT_BASE}/play`, { timeout: 20_000, waitUntil: "domcontentloaded" });
      await sleep(3500);
      const bodyText = await page.innerText("body").catch(() => "");
      browserOk = bodyText.length > 10 && !bodyText.includes("404");
      console.log(`✅ 클라이언트 렌더: ${browserOk ? "OK" : "문제"} (text ${bodyText.length}자)`);
      await browser.close();
    } catch (e) {
      browserOk = false;
      console.log(`⚠️  클라이언트 렌더 실패: ${e}`);
    }
  }

  // 6. 결과
  const elapsed = (Date.now() - start) / 1000;
  console.log("\n═══ smoke 결과 ═══");
  console.log(`총 시간: ${elapsed.toFixed(1)}s`);
  console.log(`턴: ${turnLogs.length} · 이벤트 ${turnLogs.reduce((a, t) => a + t.events.length, 0)}개 · 평균 LLM ${Math.round(avgLatency)}ms`);
  if (browserOk !== null) console.log(`클라이언트: ${browserOk ? "PASS" : "FAIL"}`);
  if (failures.length) {
    console.log("\n❌ 실패:");
    failures.forEach((f) => console.log(`  - ${f}`));
    process.exit(1);
  }
  console.log("\n✅ smoke PASS");
}

main().catch((e) => {
  console.error("❌ smoke 예외:", e);
  process.exit(1);
});
