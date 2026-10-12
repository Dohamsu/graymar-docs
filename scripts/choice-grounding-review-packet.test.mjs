import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { writeReviewPacket } from "./choice-grounding-review-packet.mjs";

const script = new URL("./choice-grounding-review-packet.mjs", import.meta.url).pathname;
const hash = (value) => createHash("sha256").update(value).digest("hex");

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), "graymar-review-packet-"));
  const captureDir = join(root, "capture");
  const outputDir = join(root, "output");
  mkdirSync(captureDir, { mode: 0o700 });
  mkdirSync(outputDir, { mode: 0o700 });
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const choices = [
    { id: "nano_7_0", label: "비밀 손거울을 본다", action: { type: "CHOICE", payload: { affordance: "OBSERVE", targetId: "MIRROR" } } },
    { id: "nano_7_1", label: "회계사와 대화한다", action: { type: "CHOICE", payload: { affordance: "TALK", sourceNpcId: "EDRIC" } } },
    { id: "go_hub", label: "돌아간다", action: { type: "ACTION", payload: { affordance: "MOVE" } } },
  ];
  const runtimeConfig = {
    llm: { provider: "mock", openaiModel: "model-a", openaiApiKeySet: false },
    runtimeFlags: [{ key: "LLM_LIGHT_MODEL", effective: "nano-a" }],
    directFlags: { CHOICE_GROUNDING_PROPOSAL_EXPERIMENT: "true", JEV_MODEL: "jev-a" },
  };
  const runtimeReceipt = {
    schemaVersion: 2,
    bootId: "boot-a",
    artifactSha256: "a".repeat(64),
    contentSha256: "b".repeat(64),
    configSha256: hash(JSON.stringify(runtimeConfig)),
    config: runtimeConfig,
  };
  const publicReceipt = (({ schemaVersion, bootId, artifactSha256, contentSha256, configSha256 }) =>
    ({ schemaVersion, bootId, artifactSha256, contentSha256, configSha256 }))(runtimeReceipt);
  const capture = {
    schemaVersion: 2,
    runtimeReceipt,
    runId: "run-1",
    packId: "graymar_v1",
    turnNo: 7,
    catalog: { turnNo: 7, refs: [{ refId: "ITEM:MIRROR", kind: "ITEM", label: "손거울", disclosure: "SERVER_ONLY" }], unresolvedKinds: ["SCENE_OBJECT"] },
    finalChoices: choices,
    narrative: "비밀 손거울이 놓여 있다.",
  };
  const report = {
    meta: { scenario: capture.packId, b1RuntimeReceipt: { start: publicReceipt, end: publicReceipt } },
    runId: "run-1",
    turns: [
      { turnNo: 7, nodeType: "LOCATION", llmStatus: "DONE", llmChoices: structuredClone(choices), narrative: capture.narrative },
      { turnNo: 8, input: "AGENT:nano_7_0" },
    ],
  };
  const inventory = {
    schemaVersion: 1,
    runs: [{
      runId: capture.runId,
      packId: capture.packId,
      turns: [{
        turnNo: capture.turnNo,
        nodeType: "LOCATION",
        llmStatus: "DONE",
        llmModelUsed: "narrative-model-a",
        llmChoices: structuredClone(choices),
        narrative: capture.narrative,
      }],
    }],
  };
  const capturePath = join(captureDir, `${hash(JSON.stringify([capture.runId, capture.turnNo]))}.json`);
  const reportPath = join(root, "report.json");
  const inventoryPath = join(root, "inventory.json");
  const write = () => {
    writeFileSync(capturePath, JSON.stringify(capture), { mode: 0o600 });
    writeFileSync(reportPath, JSON.stringify(report), { mode: 0o600 });
    writeFileSync(inventoryPath, JSON.stringify(inventory), { mode: 0o600 });
  };
  const runReports = (reports, ...args) => spawnSync(process.execPath, [script, captureDir, outputDir, ...reports, `--inventory=${inventoryPath}`, ...args], { encoding: "utf8" });
  const run = (...args) => runReports([reportPath], ...args);
  write();
  return { root, captureDir, outputDir, capturePath, reportPath, inventoryPath, inventory, capture, report, choices, runtimeReceipt, publicReceipt, write, run, runReports };
}

test("실제 private capture와 원본 DONE 선택지가 일치할 때만 비공개 packet·빈 ledger를 만든다", (t) => {
  const f = fixture(t);
  const result = f.run();
  assert.equal(result.status, 0, result.stderr);
  assert.doesNotMatch(result.stdout, /비밀 손거울|ITEM:MIRROR|run-1/);
  const packetPath = join(f.outputDir, "choice-grounding-review-packet.json");
  const ledgerPath = join(f.outputDir, "choice-grounding-human-label-ledger.json");
  const preservedSource = `source-report-${hash(readFileSync(f.reportPath))}.json`;
  const preservedInventory = `db-inventory-${hash(readFileSync(f.inventoryPath))}.json`;
  assert.deepEqual(readdirSync(f.outputDir).sort(), ["choice-grounding-human-label-ledger.json", "choice-grounding-review-packet.json", preservedSource, preservedInventory].sort());
  assert.equal(statSync(packetPath).mode & 0o777, 0o600);
  assert.equal(statSync(ledgerPath).mode & 0o777, 0o600);
  assert.equal(statSync(join(f.outputDir, preservedSource)).mode & 0o777, 0o600);
  assert.equal(statSync(join(f.outputDir, preservedInventory)).mode & 0o777, 0o600);
  assert.deepEqual(readFileSync(join(f.outputDir, preservedSource)), readFileSync(f.reportPath));
  assert.deepEqual(readFileSync(join(f.outputDir, preservedInventory)), readFileSync(f.inventoryPath));
  const packet = JSON.parse(readFileSync(packetPath, "utf8"));
  const ledger = JSON.parse(readFileSync(ledgerPath, "utf8"));
  assert.equal(packet.cases.length, 2);
  assert.equal(packet.cases[0].clickStatus, "CLICKED");
  assert.equal(packet.cases[0].nextTurnNo, 8);
  assert.equal(packet.cases[1].clickStatus, "NOT_CLICKED");
  assert.equal(packet.cases[1].nextTurnNo, null);
  assert.deepEqual(packet.cases[0].catalog, f.capture.catalog);
  assert.deepEqual(packet.cases[0].finalChoice, f.choices[0]);
  assert.equal(packet.cases[0].narrative, f.capture.narrative);
  assert.equal(packet.cases[0].narrativeModelUsed, "narrative-model-a");
  assert.equal(packet.cases[0].nanoChoiceModelStatus, "UNVERIFIED");
  assert.equal(packet.cases[0].captureSha256, hash(readFileSync(f.capturePath)));
  assert.equal(packet.cases[0].sourceSha256, hash(readFileSync(f.reportPath)));
  assert.equal(packet.cases[0].sourceReportFile, preservedSource);
  assert.equal(packet.cases[0].inventoryFile, preservedInventory);
  assert.equal(packet.cases[0].inventorySha256, hash(readFileSync(f.inventoryPath)));
  assert.deepEqual(packet.cases[0].runtimeReceipt, f.runtimeReceipt);
  assert.equal(packet.schemaVersion, 2);
  assert.match(packet.cases[0].evidenceId, /^[a-f0-9]{64}$/);
  assert.ok(packet.cases.every(({ shadow, semantic, jev }) => shadow === undefined && semantic === undefined && jev === undefined));
  assert.deepEqual(ledger.labels.map(({ verdict }) => verdict), [null, null]);
  assert.deepEqual(ledger.labels.map(({ evidenceId }) => evidenceId), packet.cases.map(({ evidenceId }) => evidenceId));
  assert.doesNotMatch(result.stdout, /PASS|20건 충족/);
  assert.equal(f.run().status, 0, "동일 결과 재실행은 멱등이어야 한다");
  writeFileSync(join(f.outputDir, preservedSource), "changed source bytes");
  assert.notEqual(f.run().status, 0, "보존 원본의 다른 바이트를 덮어쓰지 않는다");
});

test("v3의 원 후보·판정 신호는 검증하되 사람 검토 packet에는 노출하지 않는다", (t) => {
  const f = fixture(t);
  f.capture.schemaVersion = 3;
  f.capture.privateShadow = {
    generated: f.choices.slice(0, 2).map((choice) => ({
      choiceId: choice.id,
      raw: { label: `원문: ${choice.label}`, affordance: choice.action.payload.affordance },
      built: structuredClone(choice),
    })),
    structural: {
      catalogTurnNo: 7,
      finalNanoCount: 2,
      records: f.choices.slice(0, 2).map((choice) => ({ choiceId: choice.id, status: "UNRESOLVED" })),
    },
    semantic: {
      status: "EVALUATED",
      latencyMs: 12,
      costUsd: 0.001,
      findings: f.choices.slice(0, 2).map((choice) => ({ choiceId: choice.id, verdict: "UNRESOLVED" })),
    },
  };
  f.write();
  assert.equal(f.run().status, 0);
  const packet = JSON.parse(readFileSync(join(f.outputDir, "choice-grounding-review-packet.json"), "utf8"));
  assert.equal(packet.cases.length, 2);
  for (const reviewCase of packet.cases) {
    assert.equal(reviewCase.privateShadow, undefined);
    assert.equal(reviewCase.generated, undefined);
    assert.equal(reviewCase.structural, undefined);
    assert.equal(reviewCase.semantic, undefined);
    assert.doesNotMatch(JSON.stringify(reviewCase), /원문:/);
  }

  f.capture.privateShadow.semantic.findings.pop();
  f.write();
  assert.notEqual(f.run().status, 0, "의미 판정에 최종 Nano ID가 빠지면 거부한다");
  f.capture.privateShadow.semantic.findings.push({ choiceId: f.choices[1].id, verdict: "UNRESOLVED" });
  f.capture.privateShadow.generated.pop();
  f.write();
  assert.notEqual(f.run().status, 0, "최종 Nano의 원 후보가 빠지면 거부한다");
});

test("v4의 탈락 생성 후보와 대상 제안은 검증하되 공개 packet에는 복사하지 않는다", (t) => {
  const f = fixture(t);
  f.runtimeReceipt.config.directFlags.CHOICE_ACTION_TARGET_SHADOW = "true";
  f.runtimeReceipt.configSha256 = hash(JSON.stringify(f.runtimeReceipt.config));
  f.publicReceipt.configSha256 = f.runtimeReceipt.configSha256;
  f.capture.schemaVersion = 4;
  f.capture.privateShadow = {
    generated: [
      ...f.choices.slice(0, 2).map((choice) => ({
        choiceId: choice.id,
        raw: { label: `원문: ${choice.label}`, affordance: choice.action.payload.affordance },
        built: structuredClone(choice),
      })),
      { choiceId: "nano_7_2", raw: { label: "탈락한 후보", affordance: "OBSERVE" }, built: { ...structuredClone(f.choices[0]), id: "nano_7_2" } },
    ],
    actionTargets: {
      schemaVersion: 4,
      catalogTurnNo: 7,
      finalNanoCount: 2,
      droppedGeneratedCount: 1,
      records: f.choices.slice(0, 2).map((choice) => ({ choiceId: choice.id, proposedActionTarget: { kind: "SCENE_OBJECT", labelSpan: "비공개 제안" } })),
    },
    semantic: { status: "DISABLED", latencyMs: null, costUsd: null, findings: [] },
  };
  f.write();
  assert.equal(f.run().status, 0);
  const packet = JSON.parse(readFileSync(join(f.outputDir, "choice-grounding-review-packet.json"), "utf8"));
  assert.equal(packet.cases.length, 2);
  for (const reviewCase of packet.cases) {
    assert.equal(reviewCase.privateShadow, undefined);
    assert.equal(reviewCase.actionTargets, undefined);
    assert.doesNotMatch(JSON.stringify(reviewCase), /비공개 제안|탈락한 후보|원문:/);
  }
  f.capture.privateShadow.actionTargets.records.pop();
  f.write();
  assert.notEqual(f.run().status, 0, "최종 Nano 레코드가 누락되면 거부한다");
});

test("DB의 자동 생성 0번 HUB 턴은 보존하되 Nano 캡처 대상에서 제외한다", (t) => {
  const f = fixture(t);
  f.inventory.runs[0].turns.unshift({
    turnNo: 0,
    nodeType: "HUB",
    llmStatus: "SKIPPED",
    llmModelUsed: null,
    llmChoices: null,
    narrative: null,
  });
  f.write();
  assert.equal(f.run().status, 0);
});

test("스키마·실행 영수증·턴·전체 최종 선택지·출처가 틀리면 실패한다", (t) => {
  const f = fixture(t);
  const baseline = structuredClone(f.capture);
  for (const change of [
    (value) => { value.schemaVersion = 1; },
    (value) => { delete value.runtimeReceipt; },
    (value) => { value.runtimeReceipt.config.directFlags.JEV_MODEL = "jev-b"; },
    (value) => { value.catalog.turnNo = 8; },
    (value) => { value.finalChoices[0].label = "달라짐"; },
    (value) => { value.finalChoices.push(structuredClone(value.finalChoices[0])); },
    (value) => { value.runId = "other-run"; },
  ]) {
    Object.assign(f.capture, structuredClone(baseline));
    change(f.capture);
    f.write();
    assert.notEqual(f.run().status, 0);
  }
  Object.assign(f.capture, baseline);
  f.write();
  f.report.turns[0].llmChoices[0].action.payload.affordance = "TALK";
  f.write();
  assert.notEqual(f.run().status, 0);
  f.report.turns[0].llmChoices = structuredClone(baseline.finalChoices);
  f.report.turns[0].narrative = "다른 서술";
  f.write();
  assert.notEqual(f.run().status, 0);
  f.report.turns = [];
  f.write();
  assert.notEqual(f.run().status, 0);
});

test("중복 캡처 키와 안전하지 않은 파일·디렉터리·잘못된 이름을 거부한다", (t) => {
  const f = fixture(t);
  const duplicate = join(f.captureDir, "f".repeat(64) + ".json");
  writeFileSync(duplicate, JSON.stringify(f.capture), { mode: 0o600 });
  assert.notEqual(f.run().status, 0);
  rmSync(duplicate);
  chmodSync(f.capturePath, 0o644);
  assert.notEqual(f.run().status, 0);
  chmodSync(f.capturePath, 0o600);
  chmodSync(f.outputDir, 0o755);
  assert.notEqual(f.run().status, 0);
  chmodSync(f.outputDir, 0o700);
  rmSync(f.capturePath);
  assert.notEqual(f.run().status, 0);
});

test("선택적 사람 판정 재검증은 정확한 evidenceId만 연결하고 누락·null은 PENDING으로 센다", (t) => {
  const f = fixture(t);
  assert.equal(f.run().status, 0);
  const template = JSON.parse(readFileSync(join(f.outputDir, "choice-grounding-human-label-ledger.json"), "utf8"));
  const ledgerPath = join(f.outputDir, "filled-ledger.json");
  const label = { ...template.labels[0], verdict: "ALLOW", reviewer: "reviewer-1", reason: "정본의 물건에 근거함", evidenceRef: "ITEM:MIRROR" };
  writeFileSync(ledgerPath, JSON.stringify({ ...template, labels: [label] }), { mode: 0o600 });
  const originalLedger = readFileSync(ledgerPath);
  const result = f.run(`--ledger=${ledgerPath}`);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readFileSync(ledgerPath), originalLedger, "입력 ledger는 덮어쓰지 않는다");
  assert.deepEqual(JSON.parse(result.stdout).labels, { ALLOW: 1, REJECT: 0, INSUFFICIENT: 0, PENDING: 1 });
  for (const changed of [
    { ...label, evidenceId: "wrong" },
    { ...label, verdict: "PASS" },
    { ...label, reviewer: "" },
    { ...label, evidenceRef: "" },
  ]) {
    writeFileSync(ledgerPath, JSON.stringify({ ...template, labels: [changed] }), { mode: 0o600 });
    assert.notEqual(f.run(`--ledger=${ledgerPath}`).status, 0);
  }
});

test("두 팩의 캡처는 runId별 원본과 합쳐 검증하고 한 빌드만 한 packet에 담는다", (t) => {
  const f = fixture(t);
  const second = structuredClone(f.capture);
  second.runId = "run-2";
  second.packId = "star_sand_v1";
  second.turnNo = 4;
  second.catalog.turnNo = 4;
  second.finalChoices[0].id = "nano_4_0";
  second.finalChoices[1].id = "nano_4_1";
  second.narrative = "별모래 여관에 이렌이 서 있다.";
  const secondPath = join(f.captureDir, `${hash(JSON.stringify([second.runId, second.turnNo]))}.json`);
  const secondReport = {
    meta: { scenario: second.packId, b1RuntimeReceipt: { start: f.publicReceipt, end: f.publicReceipt } },
    runId: second.runId,
    turns: [
      { turnNo: 4, nodeType: "LOCATION", llmStatus: "DONE", narrative: second.narrative, llmChoices: structuredClone(second.finalChoices) },
      { turnNo: 5, input: "CHOICE:nano_4_1" },
    ],
  };
  const secondReportPath = join(f.root, "second-report.json");
  const writeSecond = () => {
    writeFileSync(secondPath, JSON.stringify(second), { mode: 0o600 });
    writeFileSync(secondReportPath, JSON.stringify(secondReport), { mode: 0o600 });
    f.inventory.runs[1] = {
      runId: second.runId,
      packId: second.packId,
      turns: [{ turnNo: second.turnNo, nodeType: "LOCATION", llmStatus: "DONE", llmModelUsed: "narrative-model-b", llmChoices: structuredClone(second.finalChoices), narrative: second.narrative }],
    };
    f.write();
  };
  writeSecond();
  const success = f.runReports([f.reportPath, secondReportPath]);
  assert.equal(success.status, 0, success.stderr);
  assert.doesNotMatch(success.stdout, /별모래|손거울|run-2/);
  const packet = JSON.parse(readFileSync(join(f.outputDir, "choice-grounding-review-packet.json"), "utf8"));
  assert.equal(packet.cases.length, 4);
  assert.deepEqual(new Set(packet.cases.map((entry) => entry.packId)), new Set(["graymar_v1", "star_sand_v1"]));
  assert.equal(packet.cases.find((entry) => entry.runId === "run-2" && entry.choiceId === "nano_4_1").nextTurnNo, 5);
  for (const reportPath of [f.reportPath, secondReportPath]) {
    const preserved = `source-report-${hash(readFileSync(reportPath))}.json`;
    assert.equal(statSync(join(f.outputDir, preserved)).mode & 0o777, 0o600);
    assert.deepEqual(readFileSync(join(f.outputDir, preserved)), readFileSync(reportPath));
    assert.ok(packet.cases.some((entry) => entry.sourceReportFile === preserved));
  }
  assert.notEqual(f.runReports([f.reportPath]).status, 0, "두 번째 런의 출처 누락");
  assert.notEqual(f.runReports([f.reportPath, f.reportPath]).status, 0, "원본 runId 중복");
  second.runtimeReceipt.artifactSha256 = "b".repeat(64);
  writeSecond();
  assert.notEqual(f.runReports([f.reportPath, secondReportPath]).status, 0, "한 packet의 빌드 혼합");
});

test("기본 ledger template을 직접 채웠다면 --ledger로 읽기만 하고 덮어쓰지 않는다", (t) => {
  const f = fixture(t);
  assert.equal(f.run().status, 0);
  const ledgerPath = join(f.outputDir, "choice-grounding-human-label-ledger.json");
  const filled = JSON.parse(readFileSync(ledgerPath, "utf8"));
  filled.labels[0] = {
    ...filled.labels[0], verdict: "REJECT", reviewer: "reviewer-2",
    reason: "정본이 허용하지 않음", evidenceRef: "ITEM:MIRROR",
  };
  writeFileSync(ledgerPath, JSON.stringify(filled));
  const before = readFileSync(ledgerPath);
  const result = f.run(`--ledger=${ledgerPath}`);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readFileSync(ledgerPath), before);
  assert.deepEqual(JSON.parse(result.stdout).labels, { ALLOW: 0, REJECT: 1, INSUFFICIENT: 0, PENDING: 1 });
});

test("원본의 다른 DONE LOCATION Nano 턴이 캡처에서 빠지면 부분 packet을 만들지 않는다", (t) => {
  const f = fixture(t);
  f.report.turns.push({
    turnNo: 9,
    nodeType: "LOCATION",
    llmStatus: "DONE",
    narrative: "다음 장소의 장면",
    llmChoices: [
      { id: "nano_9_0", label: "다음 장면을 본다", action: { type: "CHOICE", payload: { affordance: "OBSERVE" } } },
    ],
  });
  f.write();
  const result = f.run();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /INVENTORY_SOURCE_MISMATCH/);
  assert.deepEqual(readdirSync(f.outputDir), []);
});

test("DB에만 있는 최종 Nano 턴을 보고서가 빠뜨려도 packet을 만들지 않는다", (t) => {
  const f = fixture(t);
  f.inventory.runs[0].turns.push({
    turnNo: 9,
    nodeType: "LOCATION",
    llmStatus: "DONE",
    llmModelUsed: "narrative-model-a",
    llmChoices: [{ id: "nano_9_0", label: "다음 장면을 본다", action: { type: "CHOICE", payload: { affordance: "OBSERVE" } } }],
    narrative: "다음 장소의 장면",
  });
  f.write();
  const result = f.run();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /INVENTORY_SOURCE_COVERAGE_MISMATCH/);
  assert.deepEqual(readdirSync(f.outputDir), []);
});

test("DB의 최종 payload·서술·팩이 캡처 또는 보고서와 다르면 실패한다", (t) => {
  const f = fixture(t);
  const baseline = structuredClone(f.inventory);
  for (const change of [
    (value) => { value.runs[0].turns[0].llmChoices[0].action.payload.targetId = "OTHER"; },
    (value) => { value.runs[0].turns[0].narrative = "다른 서술"; },
    (value) => { value.runs[0].packId = "other_pack"; },
  ]) {
    Object.assign(f.inventory, structuredClone(baseline));
    change(f.inventory);
    f.write();
    assert.notEqual(f.run().status, 0);
    assert.deepEqual(readdirSync(f.outputDir), []);
  }
});

test("최종 Nano 턴의 실제 서술 모델이 DB에 없으면 평가 자료를 거부한다", (t) => {
  const f = fixture(t);
  f.inventory.runs[0].turns[0].llmModelUsed = null;
  f.write();
  assert.match(f.run().stderr, /INVENTORY_MODEL_MISSING/);
  assert.deepEqual(readdirSync(f.outputDir), []);
});

test("inventory 인자가 없거나 비공개 파일이 아니면 실패한다", (t) => {
  const f = fixture(t);
  const missing = spawnSync(process.execPath, [script, f.captureDir, f.outputDir, f.reportPath], { encoding: "utf8" });
  assert.match(missing.stderr, /USAGE/);
  chmodSync(f.inventoryPath, 0o644);
  assert.match(f.run().stderr, /INVENTORY_FILE_UNSAFE/);
  assert.deepEqual(readdirSync(f.outputDir), []);
});

test("플레이테스트 시작·종료 영수증이 캡처와 다르면 실패한다", (t) => {
  const f = fixture(t);
  f.report.meta.b1RuntimeReceipt.end = { ...f.publicReceipt, bootId: "other-boot" };
  f.write();
  assert.match(f.run().stderr, /SOURCE_RUNTIME_RECEIPT_MISMATCH/);
  assert.deepEqual(readdirSync(f.outputDir), []);
  f.report.meta.b1RuntimeReceipt.end = f.publicReceipt;
  delete f.report.meta.b1RuntimeReceipt.start;
  f.write();
  assert.match(f.run().stderr, /SOURCE_RUNTIME_RECEIPT_MISMATCH/);
  f.report.meta.b1RuntimeReceipt.start = { ...f.publicReceipt, contentSha256: "c".repeat(64) };
  f.write();
  assert.match(f.run().stderr, /SOURCE_RUNTIME_RECEIPT_MISMATCH/);
});

test("쓰기 도중 두 번째 출력이 충돌하면 먼저 만든 파일을 되돌린다", (t) => {
  const f = fixture(t);
  assert.throws(() => writeReviewPacket(
    f.outputDir,
    { schemaVersion: 1, cases: [] },
    { schemaVersion: 1, labels: [] },
    [
      { filename: "same.json", bytes: Buffer.from("first") },
      { filename: "same.json", bytes: Buffer.from("second") },
    ],
  ), /OUTPUT_CONFLICT/);
  assert.deepEqual(readdirSync(f.outputDir), []);
});

test("기존 packet 충돌은 새 source copy를 남기기 전에 검출한다", (t) => {
  const f = fixture(t);
  assert.equal(f.run().status, 0);
  const oldPacket = readFileSync(join(f.outputDir, "choice-grounding-review-packet.json"));
  const oldSources = readdirSync(f.outputDir).filter((name) => name.startsWith("source-report-"));
  f.report.turns[1].input = "CHOICE:nano_7_1";
  f.write();
  const newSourceName = `source-report-${hash(readFileSync(f.reportPath))}.json`;
  assert.ok(!oldSources.includes(newSourceName));
  const result = f.run();
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /OUTPUT_CONFLICT/);
  assert.ok(!readdirSync(f.outputDir).includes(newSourceName));
  assert.deepEqual(readFileSync(join(f.outputDir, "choice-grounding-review-packet.json")), oldPacket);
});
