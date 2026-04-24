/**
 * perf.ts — LLM latency / 파이프라인 성능 측정
 *
 * 목적: 성능 회귀 감지. 서버 로그에 의존하지 않고 API 응답 시간만으로 측정.
 * 범위:
 *  1. N턴 (기본 10턴) 실행
 *  2. 각 턴: 제출 시각 → LLM DONE 시각까지 ms 측정
 *  3. percentile 계산 (p50/p75/p95/max)
 *  4. prompt token 누적 시 latency 증가 관찰
 *
 * 실행:
 *   pnpm exec tsx scripts/e2e/perf.ts
 *   TURNS=20 pnpm exec tsx scripts/e2e/perf.ts
 */

import {
  ApiClient,
  pickTurnInput,
  type TurnLog,
} from "./_helpers.js";

const TURNS = Number(process.env.TURNS ?? 10);
const PRESET = process.env.PRESET ?? "DESERTER";
const GENDER = (process.env.GENDER ?? "male") as "male" | "female";

function percentile(arr: number[], p: number) {
  if (!arr.length) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.floor((p / 100) * sorted.length));
  return sorted[idx];
}

async function main() {
  const start = Date.now();
  console.log(`═══ perf ${TURNS}턴 ═══`);

  const api = new ApiClient();
  const email = `e2e_perf_${Date.now()}@test.com`;
  await api.register(email);
  const runResp = await api.createRun(PRESET, GENDER);
  const runId = runResp.run.id;

  const turnLogs: TurnLog[] = [];
  let locIdx = 0;
  let locTurns = 0;
  let lastResult = runResp.lastResult ?? {};

  for (let i = 0; i < TURNS; i++) {
    const state = await api.getRun(runId);
    if (state.run?.status === "RUN_ENDED") break;

    const { body, description } = pickTurnInput(state, lastResult, {
      locIdx,
      locTurns,
      locLimit: 4,
      choiceRate: 0.25,
    });

    const submitStart = Date.now();
    let submit = await api.submitTurn(runId, body);
    if (submit.status === 409) {
      body.expectedNextTurnNo = submit.body?.details?.expected;
      submit = await api.submitTurn(runId, body);
    }
    if (submit.status !== 200 && submit.status !== 201) {
      console.log(`  T${i + 1} ERROR ${submit.status}`);
      continue;
    }
    const submitElapsed = Date.now() - submitStart;
    const submitted = submit.body.turnNo ?? state.run.currentTurnNo + 1;
    const llm = await api.pollLlm(runId, submitted, 90_000);

    const serverResult = submit.body.serverResult ?? {};
    const events = (serverResult.events ?? []).map((e: any) => e.kind ?? "");
    const resolve = serverResult.ui?.resolveOutcome ?? null;

    turnLogs.push({
      turn: i + 1,
      nodeType: state.currentNode?.nodeType ?? "",
      input: description,
      eventId: "",
      resolveOutcome: resolve,
      nodeOutcome: submit.body.meta?.nodeOutcome ?? "",
      events,
      narrative: llm.output,
      npcPortrait: null,
      rawInput: body.input?.text ?? "",
      latencyMs: llm.elapsedMs,
    });

    const mark = (llm.elapsedMs ?? 0) < 5000 ? "✓" : (llm.elapsedMs ?? 0) < 10_000 ? "△" : "✗";
    console.log(`  T${String(i + 1).padStart(2, "0")} ${mark} submit=${submitElapsed}ms  llm=${llm.elapsedMs}ms  ${(serverResult?.events?.length ?? 0)}evt`);

    if (body.input.type === "CHOICE") lastResult = serverResult;
    if (state.currentNode?.nodeType === "LOCATION") locTurns++;
    if (submit.body.meta?.nodeOutcome === "NODE_ENDED") {
      if (state.currentNode?.nodeType !== "HUB") locIdx++;
      locTurns = 0;
    }
  }

  // 분석
  const latencies = turnLogs.map((t) => t.latencyMs ?? 0).filter((x) => x > 0);
  const total = Date.now() - start;

  console.log("\n═══ perf 결과 ═══");
  console.log(`턴 수:        ${turnLogs.length}`);
  console.log(`총 시간:      ${(total / 1000).toFixed(1)}s`);
  console.log(`턴당 평균:    ${(total / turnLogs.length / 1000).toFixed(1)}s`);
  console.log("");
  console.log("── LLM latency 분포 ──");
  console.log(`  avg:  ${Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)}ms`);
  console.log(`  min:  ${Math.min(...latencies)}ms`);
  console.log(`  p50:  ${percentile(latencies, 50)}ms`);
  console.log(`  p75:  ${percentile(latencies, 75)}ms`);
  console.log(`  p95:  ${percentile(latencies, 95)}ms`);
  console.log(`  max:  ${Math.max(...latencies)}ms`);

  // UX 기준 (CLAUDE.md · feedback_latency_under_10s: 10s 미만 필수)
  const over10s = latencies.filter((x) => x >= 10_000).length;
  const over5s = latencies.filter((x) => x >= 5_000).length;
  console.log("");
  console.log("── UX 기준 ──");
  console.log(`  < 5s:   ${latencies.length - over5s} / ${latencies.length}  (${Math.round(((latencies.length - over5s) / latencies.length) * 100)}%)`);
  console.log(`  5~10s:  ${over5s - over10s} / ${latencies.length}`);
  console.log(`  ≥ 10s:  ${over10s} / ${latencies.length}  ${over10s > 0 ? "❌" : "✅"}`);

  if (over10s > 0) {
    console.log("\n⚠️  10초 초과 턴 존재 — feedback_latency_under_10s 위배");
    process.exit(1);
  }
  console.log("\n✅ perf PASS");
}

main().catch((e) => {
  console.error("❌ perf 예외:", e);
  process.exit(1);
});
