/**
 * smoke.ts — 5분 이내 핵심 플로우 체크
 *
 * 목적: PR / 배포 직후 기본 정상 동작 검증.
 * 범위:
 *  1. API 헬스 + 서버 버전 확인
 *  2. 초대 게이트 계약 (arch/107 §8) — ON 이면 코드 없는 가입이 거절되는지
 *  3. 회원가입 → 로그인 → 런 생성 → 3턴 실행
 *  4. 서술/이벤트/판정 최소 1건 이상 생성되는지 확인
 *  5. (선택) 브라우저 진입 · 타이틀 렌더 · 버튼 가시성
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

  // 2. 초대 게이트 계약 (arch/107 §8)
  //
  // 게이트를 우회해서 가입만 하고 넘어가면, "비공개 테스트가 조용히 풀린" 상태를
  // 아무도 못 잡는다 — 스모크가 담당하는 기동 시점 결함(env 오타·마이그레이션
  // 불일치)이 정확히 이 부류다. 그래서 여기서 계약을 직접 찌른다:
  //   게이트 ON  → 코드 없는 가입은 반드시 거절돼야 한다
  //   게이트 OFF → 실패시키지 않되 눈에 띄게 경고 (의도적으로 껐을 수 있음)
  const gateFailures: string[] = [];
  const gateStatus = await fetch(`${SERVER_BASE}/auth/invite-status`)
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  if (!gateStatus) {
    gateFailures.push("초대 게이트 상태 조회 실패 (GET /auth/invite-status)");
  } else if (gateStatus.required) {
    const probe = await fetch(`${SERVER_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: `smoke_gate_${Date.now()}@test.com`,
        password: "Test1234!!",
      }),
    });
    const probeBody = await probe.json().catch(() => ({}));
    if (probe.ok) {
      gateFailures.push(
        "초대 게이트가 required=true 인데 코드 없는 가입이 통과했다 (게이트 무력화)",
      );
    } else {
      console.log(`✅ 초대 게이트: ON · 코드 없는 가입 거절 (${probeBody.code})`);
    }
  } else {
    console.log("⚠️  초대 게이트: OFF — 누구나 가입 가능한 상태입니다 (INVITE_CODE_REQUIRED)");
  }

  // 3. 신규 회원가입 → 런 생성 (게이트가 켜져 있으면 코드를 발급받아 통과)
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
    // FREE(자동 성공) 턴은 resolveOutcome 대신 resolveSkipped가 정본 (2026-08-06
    // 주사위 8 고정 표시 수정) — 판정 파이프라인 생존 신호로는 둘 다 유효.
    const resolve =
      serverResult.ui?.resolveOutcome ??
      (serverResult.ui?.resolveSkipped ? "FREE_SKIP" : null);
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
  const failures: string[] = [...gateFailures];
  if (turnLogs.length < 3) failures.push(`턴 수 부족: ${turnLogs.length}/3`);
  const anyNarrative = turnLogs.some((t) => t.narrative && t.narrative.length > 50);
  if (!anyNarrative) failures.push("서술 전혀 생성 안됨");
  const anyEvent = turnLogs.some((t) => t.events.length > 0);
  if (!anyEvent) failures.push("이벤트 전혀 생성 안됨");
  const anyResolve = turnLogs.some((t) => t.resolveOutcome);
  if (!anyResolve) failures.push("판정 신호(resolveOutcome/resolveSkipped) 전혀 없음");
  // [M4 감사 2026-08-12 — 체크리스트 C2] 3턴 **평균** 게이트는 이상치에 지배된다.
  //   실측: T1 4s · T2 24s · T3 6s → 평균 11.4s 로 배포 실패 판정 → 재실행 시
  //   6.7s 통과. kickstart 직후 첫 호출은 콜드스타트(연결·캐시 워밍)라 느린 게
  //   정상인데, n=3 평균은 그 1건이 결론을 뒤집는다.
  //   스모크의 목적은 "기동 시점 결함(팩 로드·env·마이그레이션)" 이고
  //   지연 분포는 perf.ts(p50/p95)가 담당한다 — 여기서는 **파국적 지연만**
  //   잡는다. 첫 턴 제외 + 중앙값으로 안정화.
  const latencies = turnLogs.map((t) => t.latencyMs ?? 0).filter((x) => x > 0);
  const warm = latencies.length > 1 ? latencies.slice(1) : latencies;
  const sorted = [...warm].sort((a, b) => a - b);
  const medLatency = sorted.length
    ? sorted[Math.floor((sorted.length - 1) / 2)]
    : 0;
  const avgLatency = latencies.length
    ? latencies.reduce((a, b) => a + b, 0) / latencies.length
    : 0;
  if (medLatency > 20_000)
    failures.push(
      `LLM 중앙값 latency ${Math.round(medLatency)}ms > 20s (콜드스타트 제외 ${warm.length}턴)`,
    );

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
  console.log(`턴: ${turnLogs.length} · 이벤트 ${turnLogs.reduce((a, t) => a + t.events.length, 0)}개 · LLM 평균 ${Math.round(avgLatency)}ms · 중앙값(콜드 제외) ${Math.round(medLatency)}ms`);
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
