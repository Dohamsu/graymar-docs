/**
 * NPA Audit — CLI 엔진.
 *
 * 실행:
 *   pnpm exec tsx scripts/e2e/audit/audit.ts --scenario dialog-handoff
 *   pnpm exec tsx scripts/e2e/audit/audit.ts --scenario dialog-handoff --output playtest-reports/foo
 *
 * 설계: architecture/47_dialogue_quality_audit.md.
 */

import * as fs from "node:fs";
import * as path from "node:path";

import {
  ApiClient,
  randomUuid,
  sleep,
  SERVER_BASE,
} from "../_helpers.js";
import { computeDialogueQuality } from "./dialogue-quality.js";
import { buildDialoguePair, type RawTurnSources } from "./pipeline-trace.js";
import { printConsoleSummary, writeReport } from "./reporter.js";
import { verify } from "./auto-verifier.js";
import type {
  AuditReport,
  AuditScenario,
  DialoguePair,
  SetupStep,
} from "./types.js";

// ──────────────────────────────────────────────────────────────
// CLI 인자 파싱
// ──────────────────────────────────────────────────────────────
interface CliArgs {
  scenarioId: string;
  outputBase: string;
  pollMaxWaitMs: number;
}

function parseArgs(): CliArgs {
  const argv = process.argv.slice(2);
  let scenarioId = "dialog-handoff";
  let output = "";
  let pollMaxWaitMs = 90_000;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--scenario") scenarioId = argv[++i];
    else if (a === "--output") output = argv[++i];
    else if (a === "--poll-timeout") pollMaxWaitMs = Number(argv[++i]);
  }
  if (!output) {
    const ts = new Date()
      .toISOString()
      .replace(/[-:]/g, "")
      .replace(/\..+$/, "")
      .replace("T", "_");
    output = `playtest-reports/audit_${scenarioId}_${ts}.md`;
  }
  return { scenarioId, outputBase: output, pollMaxWaitMs };
}

async function loadScenario(id: string): Promise<AuditScenario> {
  // scripts/e2e/audit/scenarios/<id>.ts 동적 import
  const mod = await import(`./scenarios/${id}.js`);
  const scen: AuditScenario = mod.scenario ?? mod.default;
  if (!scen) throw new Error(`scenarios/${id}.ts에 scenario export가 없습니다`);
  return scen;
}

// ──────────────────────────────────────────────────────────────
// 서버 버전 조회 (best-effort)
// ──────────────────────────────────────────────────────────────
async function getServerVersion(): Promise<string> {
  try {
    const res = await fetch(`${SERVER_BASE}/version`);
    if (!res.ok) return "unknown";
    const j = (await res.json()) as { gitHash?: string; startedAt?: string };
    return j.gitHash
      ? `${j.gitHash.slice(0, 7)}${j.startedAt ? ` (${j.startedAt})` : ""}`
      : "unknown";
  } catch {
    return "unknown";
  }
}

// ──────────────────────────────────────────────────────────────
// 1턴 실행 → DialoguePair
// ──────────────────────────────────────────────────────────────

async function runStep(
  api: ApiClient,
  runId: string,
  turn: number,
  body: any,
  pollMaxWaitMs: number,
): Promise<RawTurnSources | null> {
  const t0 = Date.now();
  let submit = await api.submitTurn(runId, body);
  if (submit.status === 409) {
    const expected = submit.body?.details?.expected;
    if (expected) {
      body.expectedNextTurnNo = expected;
      submit = await api.submitTurn(runId, body);
    }
  }
  if (submit.status !== 200 && submit.status !== 201) {
    console.error(
      `  T${turn} 제출 실패 ${submit.status}: ${JSON.stringify(submit.body).slice(0, 200)}`,
    );
    return null;
  }
  const submittedTurnNo: number = submit.body.turnNo ?? turn;

  // LLM 폴링 — DONE 또는 FAILED까지
  const pollStart = Date.now();
  let llmStatus = "PENDING";
  let llmOutput = "";
  while (Date.now() - pollStart < pollMaxWaitMs) {
    const data = await api.getTurn(runId, submittedTurnNo);
    const llm = data?.llm ?? {};
    if (llm.status === "DONE") {
      llmStatus = "DONE";
      llmOutput = llm.output ?? "";
      break;
    }
    if (llm.status === "FAILED" || llm.status === "SKIPPED") {
      llmStatus = llm.status;
      llmOutput = `[LLM_${llm.status}]`;
      break;
    }
    await sleep(1500);
  }
  if (!llmStatus || llmStatus === "PENDING") {
    llmOutput = "[LLM_TIMEOUT]";
  }

  // includeDebug=true 호출로 llmPrompt 획득
  const debugData = await api.getTurn(runId, submittedTurnNo, {
    includeDebug: true,
  });
  const llmPrompt = debugData?.debug?.llmPrompt ?? null;

  return {
    turn: submittedTurnNo,
    userInput:
      body.input?.text ??
      (body.input?.type === "CHOICE" ? `(CHOICE:${body.input?.choiceId})` : ""),
    inputKind: body.input?.type === "CHOICE" ? "CHOICE" : "ACTION",
    serverResult: debugData?.serverResult ?? submit.body.serverResult ?? {},
    llmOutput,
    llmLatencyMs: Date.now() - t0,
    llmPrompt,
  };
}

function buildSubmitBody(
  step: SetupStep | { type: "ACTION"; text: string },
  expectedNextTurnNo: number,
) {
  const idem = randomUuid();
  if (step.type === "CHOICE") {
    return {
      input: { type: "CHOICE", choiceId: step.choiceId },
      expectedNextTurnNo,
      idempotencyKey: idem,
    };
  }
  return {
    input: { type: "ACTION", text: step.text },
    expectedNextTurnNo,
    idempotencyKey: idem,
  };
}

// ──────────────────────────────────────────────────────────────
// main
// ──────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs();
  const startedAt = new Date().toISOString();
  const t0 = Date.now();

  console.log(`═══ NPA: ${args.scenarioId} ═══`);

  const scenario = await loadScenario(args.scenarioId);
  console.log(`시나리오: ${scenario.name} (${scenario.preset}/${scenario.gender})`);
  console.log(`의도: ${scenario.intent}`);
  console.log("");

  const api = new ApiClient();
  const email = `audit_${args.scenarioId}_${Date.now()}@test.com`;
  await api.register(email);
  const runResp = await api.createRun(scenario.preset, scenario.gender);
  const runId = runResp.run.id;
  console.log(`Run: ${runId}`);
  console.log("");

  const pairs: DialoguePair[] = [];
  let nextTurnNo = (runResp.run?.currentTurnNo ?? 0) + 1;

  // ── setup 실행 ─────────────────────────────────
  console.log("── setup ──");
  for (let i = 0; i < scenario.setup.length; i++) {
    const step = scenario.setup[i];
    const desc =
      step.type === "CHOICE" ? `CHOICE:${step.choiceId}` : `ACTION:${step.text}`;
    process.stdout.write(`  [${i + 1}/${scenario.setup.length}] ${desc} ... `);
    const body = buildSubmitBody(step, nextTurnNo);
    const src = await runStep(api, runId, nextTurnNo, body, args.pollMaxWaitMs);
    if (!src) {
      console.log("실패");
      process.exit(1);
    }
    const pair = buildDialoguePair({ ...src, isSetup: true });
    pairs.push(pair);
    console.log(
      `T${pair.turn} ${pair.detectedMode} ${pair.speakerDisplayName ?? "-"} (${pair.llmLatencyMs}ms)`,
    );
    nextTurnNo = pair.turn + 1;
  }

  // ── 평가 턴 실행 ─────────────────────────────────
  console.log("");
  console.log("── 평가 턴 ──");
  for (let i = 0; i < scenario.turns.length; i++) {
    const auditTurn = scenario.turns[i];
    const isChoice = auditTurn.type === "CHOICE" && auditTurn.choiceId;
    const desc = isChoice
      ? `CHOICE:${auditTurn.choiceId}`
      : auditTurn.input;
    process.stdout.write(
      `  [${i + 1}/${scenario.turns.length}] ${desc} ... `,
    );
    const body = buildSubmitBody(
      isChoice
        ? { type: "CHOICE", choiceId: auditTurn.choiceId! }
        : { type: "ACTION", text: auditTurn.input },
      nextTurnNo,
    );
    const src = await runStep(api, runId, nextTurnNo, body, args.pollMaxWaitMs);
    if (!src) {
      console.log("실패 — 다음 턴 진행");
      continue;
    }
    const pair = buildDialoguePair(src);
    pairs.push(pair);
    const expected =
      auditTurn.expectMode && auditTurn.expectMode === pair.detectedMode
        ? "✓"
        : auditTurn.expectMode
          ? `✗(${auditTurn.expectMode})`
          : "";
    console.log(
      `T${pair.turn} ${pair.detectedMode}${expected} ${pair.speakerDisplayName ?? "-"} (${pair.llmLatencyMs}ms, ${pair.prompt.totalTokens}t)`,
    );
    nextTurnNo = pair.turn + 1;
  }

  // 디버그: 종료 시점 runState.discoveredQuestFacts 캡처
  try {
    const finalState = await api.getRun(runId);
    const discovered = finalState?.runState?.discoveredQuestFacts ?? [];
    console.log("");
    console.log(`(debug) 최종 discoveredQuestFacts: [${discovered.join(", ")}]`);
  } catch {}

  // ── 분석 ─────────────────────────────────
  const quality = computeDialogueQuality(pairs);
  const findings = verify(scenario, pairs, quality);
  const flow = pairs.map((p) => ({
    turn: p.turn,
    speaker: p.speakerDisplayName ?? "(없음)",
    text: p.npcUtterances.map((u) => u.text).join(" ") || p.narration.slice(0, 80),
  }));

  const report: AuditReport = {
    scenario,
    startedAt,
    totalElapsedMs: Date.now() - t0,
    serverVersion: await getServerVersion(),
    runId,
    pairs,
    dialogueQuality: quality,
    findings,
    flow,
  };

  const { mdPath, jsonPath } = writeReport(report, args.outputBase);
  printConsoleSummary(report);
  console.log("");
  console.log(`저장:`);
  console.log(`  📄 ${path.relative(process.cwd(), mdPath)}`);
  console.log(`  📦 ${path.relative(process.cwd(), jsonPath)}`);

  // exit code: ERROR 있으면 1
  if (findings.errors.length > 0) {
    console.log("");
    console.log("⚠️  ERROR 발생 — exit 1");
    process.exit(1);
  }
}

main().catch((e) => {
  console.error("");
  console.error("❌ NPA 예외:");
  console.error(e?.stack ?? e);
  process.exit(1);
});

// 미사용 import 경고 방지
void fs;
