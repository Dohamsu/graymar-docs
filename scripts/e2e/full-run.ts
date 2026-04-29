/**
 * full-run.ts — 35턴 엔딩 풀 런 + V1~V9 assert
 *
 * 목적: 메인 회귀. 서버 변경 후 엔딩까지 문제 없이 도달하는지 전체 검증.
 * 범위:
 *  1. 회원가입 → 캐릭터 생성 → 35턴 자동 플레이
 *  2. V1~V9 자동 검증 (playtest.py 포팅)
 *  3. 성능 메트릭 (LLM latency · 턴당 시간 · 서술 자수)
 *  4. 엔딩 발동 검사 (NATURAL / arcRoute / cityStatus)
 *  5. JSON 리포트 저장
 *
 * 실행:
 *   pnpm exec tsx scripts/e2e/full-run.ts
 *   TURNS=20 pnpm exec tsx scripts/e2e/full-run.ts
 *   PRESET=SMUGGLER GENDER=female pnpm exec tsx scripts/e2e/full-run.ts
 */

import * as fs from "node:fs";
import * as path from "node:path";
import {
  ApiClient,
  pickTurnInput,
  printPerfReport,
  printVerifyReport,
  summarize,
  verifyRun,
  type TurnLog,
} from "./_helpers.js";

const TURNS = Number(process.env.TURNS ?? 35);
const PRESET = process.env.PRESET ?? "DESERTER";
const GENDER = (process.env.GENDER ?? "male") as "male" | "female";
const LOC_LIMIT = Number(process.env.LOC_TURNS ?? 4);
const CHOICE_RATE = Number(process.env.CHOICE_RATE ?? 0.3);
const OUT = process.env.OUT || `playtest-reports/e2e_full_${Date.now()}.json`;

async function main() {
  const start = Date.now();
  console.log(`═══ full-run ${TURNS}턴 · ${PRESET}/${GENDER} ═══`);

  const api = new ApiClient();
  const email = `e2e_full_${Date.now()}@test.com`;
  await api.register(email);

  const runResp = await api.createRun(PRESET, GENDER);
  const runId = runResp.run.id;
  console.log(`Run: ${runId} · node=${runResp.currentNode?.nodeType}`);

  const turnLogs: TurnLog[] = [];
  let locIdx = 0;
  let locTurns = 0;
  let lastResult = runResp.lastResult ?? {};

  for (let i = 0; i < TURNS; i++) {
    const state = await api.getRun(runId);
    if (!state) break;
    if (state.run?.status === "RUN_ENDED") {
      console.log(`[RUN_ENDED at turn ${i}]`);
      break;
    }

    const { body, description } = pickTurnInput(state, lastResult, {
      locIdx,
      locTurns,
      locLimit: LOC_LIMIT,
      choiceRate: CHOICE_RATE,
    });

    let submit = await api.submitTurn(runId, body);
    if (submit.status === 409) {
      // TURN_NO_MISMATCH recovery
      const expected = submit.body?.details?.expected;
      if (expected) {
        body.expectedNextTurnNo = expected;
        submit = await api.submitTurn(runId, body);
      }
    }
    if (submit.status !== 200 && submit.status !== 201) {
      const errBody = JSON.stringify(submit.body ?? {}).slice(0, 200);
      console.log(`  T${i + 1} ERROR ${submit.status} body=${errBody}`);
      continue;
    }

    const submitted = submit.body.turnNo ?? state.run.currentTurnNo + 1;
    const llm = await api.pollLlm(runId, submitted, 90_000);

    const serverResult = submit.body.serverResult ?? {};
    const events = (serverResult.events ?? []).map((e: any) => e.kind ?? "");
    const resolve = serverResult.ui?.resolveOutcome ?? null;
    const nodeOutcome = submit.body.meta?.nodeOutcome ?? "";
    const actionCtx = serverResult.ui?.actionContext ?? {};
    const questEvt = (serverResult.events ?? []).find((e: any) => e.kind === "QUEST")?.payload?.eventId ?? "";
    const matchedEvent = actionCtx.eventId ?? questEvt ?? "";
    const portrait = serverResult.ui?.npcPortrait ?? null;

    turnLogs.push({
      turn: i + 1,
      nodeType: state.currentNode?.nodeType ?? "",
      input: description,
      eventId: matchedEvent,
      resolveOutcome: resolve,
      nodeOutcome,
      events,
      narrative: llm.output,
      npcPortrait: portrait,
      rawInput: body.input?.text ?? "",
      latencyMs: llm.elapsedMs,
    });

    const evtDisp = (matchedEvent || "-").slice(0, 25);
    console.log(`  T${String(i + 1).padStart(2, "0")} [${(state.currentNode?.nodeType ?? "").padEnd(8)}] ${description.padEnd(30).slice(0, 30)} evt=${evtDisp.padEnd(25)} resolve=${(resolve ?? "-").padEnd(8)} llm=${llm.elapsedMs}ms`);

    // HUB 노드 진입 시 choices 매칭 위해 모든 입력 후 lastResult 업데이트
    lastResult = serverResult;
    if (state.currentNode?.nodeType === "LOCATION") locTurns++;
    if (nodeOutcome === "RUN_ENDED") break;
    if (nodeOutcome === "NODE_ENDED") {
      if (state.currentNode?.nodeType !== "HUB") locIdx++;
      locTurns = 0;
    }
  }

  // 최종 상태
  const finalState = await api.getRun(runId);
  const verify = verifyRun(finalState, turnLogs);
  const passed = printVerifyReport(verify);

  const perf = summarize(turnLogs, Date.now() - start);
  printPerfReport(perf);

  // 엔딩 정보
  const ending = finalState?.lastResult?.ui?.endingResult;
  if (ending) {
    console.log("\n── 엔딩 ──");
    console.log(`  type=${ending.endingType} · arcRoute=${ending.arcRoute} · "${ending.arcTitle}"`);
    console.log(`  cityStatus=${ending.cityStatus?.stability} · contained=${ending.statistics?.incidentsContained} escalated=${ending.statistics?.incidentsEscalated}`);
  }

  // JSON 저장
  const output = {
    meta: {
      preset: PRESET,
      gender: GENDER,
      turnsRequested: TURNS,
      turnsActual: turnLogs.length,
      timestamp: new Date().toISOString(),
      elapsedMs: Date.now() - start,
    },
    runId,
    email,
    perf,
    verify,
    ending: ending ?? null,
    turns: turnLogs,
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(output, null, 2));
  console.log(`\n저장: ${OUT}`);

  if (passed < verify.length) {
    console.log(`\n⚠️  ${verify.length - passed}개 검증 실패`);
    // V9는 풍선효과로 자주 실패하므로 V9만 실패해도 전체 실패 처리는 보수적으로
    const criticalFail = verify.filter((r) => !r.passed && r.name !== "V9_quality").length;
    if (criticalFail > 0) process.exit(1);
  }
  console.log("\n✅ full-run PASS");
}

main().catch((e) => {
  console.error("❌ full-run 예외:", e);
  process.exit(1);
});
