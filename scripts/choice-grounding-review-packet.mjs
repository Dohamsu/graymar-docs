import { createHash, randomUUID } from "node:crypto";
import { chmodSync, linkSync, lstatSync, readFileSync, readdirSync, rmSync, unlinkSync, writeFileSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { pathToFileURL } from "node:url";
import { extractFinalNanoChoiceEvidence } from "./choice-grounding-evidence.mjs";

const CAPTURE_NAME = /^[a-f0-9]{64}\.json$/;
const PACKET_NAME = "choice-grounding-review-packet.json";
const LEDGER_NAME = "choice-grounding-human-label-ledger.json";
const INVENTORY_PREFIX = "db-inventory-";
const VERDICTS = ["ALLOW", "REJECT", "INSUFFICIENT"];
const hash = (contents) => createHash("sha256").update(contents).digest("hex");
const keyOf = (runId, turnNo) => JSON.stringify([runId, turnNo]);
const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const nonempty = (value) => typeof value === "string" && value.trim().length > 0;

function fail(code) {
  throw new Error(code);
}

function checkOwnedFile(path, mode, kind) {
  let entry;
  try {
    entry = lstatSync(path);
  } catch {
    fail(`${kind}_MISSING`);
  }
  if (
    !entry.isFile() ||
    (entry.mode & 0o777) !== mode ||
    (process.getuid && entry.uid !== process.getuid())
  ) fail(`${kind}_UNSAFE`);
}

function checkPrivateDirectory(path, kind) {
  if (!isAbsolute(path)) fail(`${kind}_UNSAFE`);
  let entry;
  try {
    entry = lstatSync(path);
  } catch {
    fail(`${kind}_MISSING`);
  }
  if (
    !entry.isDirectory() ||
    (entry.mode & 0o777) !== 0o700 ||
    (process.getuid && entry.uid !== process.getuid())
  ) fail(`${kind}_UNSAFE`);
}

function readJson(bytes, kind) {
  try {
    return JSON.parse(bytes.toString("utf8"));
  } catch {
    fail(`${kind}_MALFORMED`);
  }
}

function checkChoices(choices, kind) {
  if (!Array.isArray(choices) || choices.length === 0) fail(`${kind}_MALFORMED`);
  const seen = new Set();
  for (const choice of choices) {
    if (
      !isObject(choice) || !nonempty(choice.id) || !nonempty(choice.label) ||
      !isObject(choice.action) || !["ACTION", "CHOICE", "SYSTEM"].includes(choice.action.type) ||
      !isObject(choice.action.payload)
    ) fail(`${kind}_MALFORMED`);
    if (seen.has(choice.id)) fail(`${kind}_DUPLICATE_CHOICE`);
    seen.add(choice.id);
  }
}

function publicReceipt(receipt) {
  const { schemaVersion, bootId, artifactSha256, contentSha256, configSha256 } = receipt;
  return { schemaVersion, bootId, artifactSha256, contentSha256, configSha256 };
}

function checkRuntimeReceipt(receipt) {
  if (
    !isObject(receipt) || receipt.schemaVersion !== 2 || !nonempty(receipt.bootId) ||
    !/^[a-f0-9]{64}$/.test(receipt.artifactSha256) ||
    !/^[a-f0-9]{64}$/.test(receipt.contentSha256) ||
    !/^[a-f0-9]{64}$/.test(receipt.configSha256) ||
    !isObject(receipt.config) || !isObject(receipt.config.llm) ||
    !Array.isArray(receipt.config.runtimeFlags) || !isObject(receipt.config.directFlags) ||
    hash(JSON.stringify(receipt.config)) !== receipt.configSha256
  ) fail("CAPTURE_RUNTIME_RECEIPT_MALFORMED");
}

function checkPrivateShadow(shadow, finalChoices, turnNo, schemaVersion) {
  if (schemaVersion === 4) {
    if (
      !isObject(shadow) || !Array.isArray(shadow.generated) ||
      !isObject(shadow.actionTargets) || !isObject(shadow.semantic)
    ) fail("CAPTURE_SHADOW_MALFORMED");
    const finalIds = finalChoices.filter((choice) => choice.id.startsWith("nano_")).map((choice) => choice.id);
    const generatedIds = shadow.generated.map((entry) => entry?.choiceId);
    const records = shadow.actionTargets.records;
    const recordIds = Array.isArray(records) ? records.map((entry) => entry?.choiceId) : [];
    const unique = (ids) => new Set(ids).size === ids.length;
    if (
      shadow.actionTargets.schemaVersion !== 4 ||
      shadow.actionTargets.catalogTurnNo !== turnNo ||
      shadow.actionTargets.finalNanoCount !== finalIds.length ||
      !unique(generatedIds) || !unique(finalIds) || !unique(recordIds) ||
      generatedIds.some((id) => !nonempty(id) || !id.startsWith("nano_")) ||
      shadow.generated.some((entry) =>
        !isObject(entry) || !isObject(entry.raw) || !nonempty(entry.raw.label) ||
        !isObject(entry.built) || entry.built.id !== entry.choiceId
      ) ||
      recordIds.length !== finalIds.length ||
      finalIds.some((id) => !generatedIds.includes(id) || !recordIds.includes(id)) ||
      shadow.actionTargets.droppedGeneratedCount !== generatedIds.length - finalIds.length ||
      shadow.semantic.status !== "DISABLED" ||
      !Array.isArray(shadow.semantic.findings) || shadow.semantic.findings.length !== 0
    ) fail("CAPTURE_SHADOW_MALFORMED");
    return;
  }
  if (
    !isObject(shadow) || !Array.isArray(shadow.generated) ||
    !isObject(shadow.structural) || !isObject(shadow.semantic)
  ) fail("CAPTURE_SHADOW_MALFORMED");
  const finalIds = finalChoices.filter((choice) => choice.id.startsWith("nano_")).map((choice) => choice.id);
  const sameIds = (ids) =>
    ids.length === finalIds.length && new Set(ids).size === ids.length &&
    ids.every((id) => finalIds.includes(id));
  const generatedIds = shadow.generated.map((entry) => entry?.choiceId);
  if (
    shadow.structural.catalogTurnNo !== turnNo ||
    shadow.structural.finalNanoCount !== finalIds.length ||
    !Array.isArray(shadow.structural.records) ||
    !sameIds(shadow.structural.records.map((record) => record?.choiceId)) ||
    !sameIds(generatedIds) ||
    shadow.generated.some((entry) =>
      !isObject(entry) || !nonempty(entry.choiceId) ||
      !isObject(entry.raw) || !nonempty(entry.raw.label) ||
      !isObject(entry.built) || entry.built.id !== entry.choiceId
    ) ||
    !["DISABLED", "EVALUATED", "SKIPPED", "UNAVAILABLE", "ERROR"].includes(shadow.semantic.status) ||
    !Array.isArray(shadow.semantic.findings) ||
    (shadow.semantic.status === "EVALUATED"
      ? !sameIds(shadow.semantic.findings.map((finding) => finding?.choiceId))
      : shadow.semantic.findings.length !== 0)
  ) fail("CAPTURE_SHADOW_MALFORMED");
}

function checkCapture(capture, filename) {
  if (
    !isObject(capture) || ![2, 3, 4].includes(capture.schemaVersion) ||
    !nonempty(capture.runId) ||
    !nonempty(capture.packId) || !Number.isSafeInteger(capture.turnNo) ||
    capture.turnNo <= 0 || !isObject(capture.catalog) ||
    capture.catalog.turnNo !== capture.turnNo ||
    !Array.isArray(capture.catalog.refs) ||
    capture.catalog.refs.some((ref) =>
      !isObject(ref) || !nonempty(ref.refId) || !nonempty(ref.label) ||
      !["FACT", "EVENT", "NPC", "LOCATION", "ITEM", "SCENE_OBJECT"].includes(ref.kind) ||
      !["PUBLIC", "SERVER_ONLY"].includes(ref.disclosure)
    ) ||
    !Array.isArray(capture.catalog.unresolvedKinds) ||
    capture.catalog.unresolvedKinds.some((kind) => kind !== "SCENE_OBJECT") ||
    typeof capture.narrative !== "string"
  ) fail("CAPTURE_MALFORMED");
  checkRuntimeReceipt(capture.runtimeReceipt);
  if (capture.schemaVersion === 4 && (
    capture.runtimeReceipt.config.directFlags.CHOICE_GROUNDING_PROPOSAL_EXPERIMENT !== "true" ||
    capture.runtimeReceipt.config.directFlags.CHOICE_ACTION_TARGET_SHADOW !== "true"
  )) fail("CAPTURE_RUNTIME_RECEIPT_MALFORMED");
  checkChoices(capture.finalChoices, "CAPTURE");
  if (!capture.finalChoices.some((choice) => choice.id.startsWith("nano_"))) {
    fail("CAPTURE_NO_NANO");
  }
  if (capture.finalChoices.some((choice) => choice.id.startsWith("nano_") && choice.action.type !== "CHOICE")) {
    fail("CAPTURE_MALFORMED");
  }
  if (capture.schemaVersion === 3 || capture.schemaVersion === 4) {
    checkPrivateShadow(capture.privateShadow, capture.finalChoices, capture.turnNo, capture.schemaVersion);
  }
  if (capture.schemaVersion === 2 && capture.privateShadow !== undefined) fail("CAPTURE_SHADOW_MALFORMED");
  if (`${hash(keyOf(capture.runId, capture.turnNo))}.json` !== filename) {
    fail("CAPTURE_KEY_MISMATCH");
  }
}

function readOwnerControlledSourceReport(path) {
  const groupOrOtherWriteBits = 0o022;
  let entry;
  try {
    entry = lstatSync(path);
  } catch {
    fail("SOURCE_MISSING");
  }
  if (
    !entry.isFile() || (entry.mode & groupOrOtherWriteBits) !== 0 ||
    (process.getuid && entry.uid !== process.getuid())
  ) fail("SOURCE_UNSAFE");
  const bytes = readFileSync(path);
  const report = readJson(bytes, "SOURCE");
  if (!isObject(report) || !nonempty(report.runId) || !Array.isArray(report.turns)) {
    fail("SOURCE_MALFORMED");
  }
  return { report, bytes, sha256: hash(bytes) };
}

function readInventory(path) {
  if (!isAbsolute(path)) fail("INVENTORY_UNSAFE");
  checkOwnedFile(path, 0o600, "INVENTORY_FILE");
  const bytes = readFileSync(path);
  const inventory = readJson(bytes, "INVENTORY");
  if (!isObject(inventory) || inventory.schemaVersion !== 1 || !Array.isArray(inventory.runs) || inventory.runs.length === 0) {
    fail("INVENTORY_MALFORMED");
  }
  const runs = new Map();
  const eligibleTurns = new Set();
  for (const run of inventory.runs) {
    if (!isObject(run) || !nonempty(run.runId) || !nonempty(run.packId) || !Array.isArray(run.turns)) {
      fail("INVENTORY_MALFORMED");
    }
    if (runs.has(run.runId)) fail("INVENTORY_DUPLICATE_RUN");
    const turns = new Map();
    for (const turn of run.turns) {
      if (
        !isObject(turn) || !Number.isSafeInteger(turn.turnNo) || turn.turnNo < 0 ||
        !nonempty(turn.nodeType) || !nonempty(turn.llmStatus) ||
        !(turn.llmModelUsed === null || typeof turn.llmModelUsed === "string") ||
        !(turn.llmChoices === null || Array.isArray(turn.llmChoices)) ||
        !(turn.narrative === null || typeof turn.narrative === "string")
      ) fail("INVENTORY_MALFORMED");
      if (turns.has(turn.turnNo)) fail("INVENTORY_DUPLICATE_TURN");
      turns.set(turn.turnNo, turn);
      if (
        turn.llmStatus === "DONE" && turn.nodeType === "LOCATION" &&
        Array.isArray(turn.llmChoices) &&
        turn.llmChoices.some((choice) => typeof choice?.id === "string" && choice.id.startsWith("nano_"))
      ) {
        checkChoices(turn.llmChoices, "INVENTORY");
        if (!nonempty(turn.llmModelUsed)) fail("INVENTORY_MODEL_MISSING");
        eligibleTurns.add(keyOf(run.runId, turn.turnNo));
      }
    }
    runs.set(run.runId, { packId: run.packId, turns });
  }
  const sha256 = hash(bytes);
  return { runs, eligibleTurns, bytes, sha256, filename: `${INVENTORY_PREFIX}${sha256}.json` };
}

export function buildReviewPacket(captureDir, reportPaths, inventoryPath) {
  checkPrivateDirectory(captureDir, "CAPTURE_DIRECTORY");
  if (!Array.isArray(reportPaths) || reportPaths.length === 0) fail("SOURCE_MISSING");
  const inventory = readInventory(inventoryPath);
  const sources = new Map();
  for (const reportPath of reportPaths) {
    const source = readOwnerControlledSourceReport(reportPath);
    if (sources.has(source.report.runId)) fail("SOURCE_DUPLICATE_RUN");
    const sourceTurns = new Map();
    for (const turn of source.report.turns) {
      if (!Number.isSafeInteger(turn?.turnNo) || turn.turnNo <= 0) fail("SOURCE_TURN_MALFORMED");
      if (sourceTurns.has(turn.turnNo)) fail("SOURCE_DUPLICATE_TURN");
      sourceTurns.set(turn.turnNo, turn);
    }
    sources.set(source.report.runId, {
      ...source,
      turns: sourceTurns,
      finalEvidence: extractFinalNanoChoiceEvidence(source.report),
    });
  }
  if (
    sources.size !== inventory.runs.size ||
    [...sources.keys()].some((runId) => !inventory.runs.has(runId))
  ) fail("INVENTORY_RUN_MISMATCH");
  const files = readdirSync(captureDir).filter((name) => CAPTURE_NAME.test(name)).sort();
  if (files.length === 0) fail("CAPTURE_MISSING");
  const seenTurns = new Set();
  const capturedRuns = new Set();
  const seenEvidenceIds = new Set();
  let runtimeReceipt;
  const cases = [];
  for (const filename of files) {
    const path = join(captureDir, filename);
    checkOwnedFile(path, 0o600, "CAPTURE_FILE");
    const bytes = readFileSync(path);
    const capture = readJson(bytes, "CAPTURE");
    checkCapture(capture, filename);
    const key = keyOf(capture.runId, capture.turnNo);
    if (seenTurns.has(key)) fail("CAPTURE_DUPLICATE_TURN");
    seenTurns.add(key);
    capturedRuns.add(capture.runId);
    if (runtimeReceipt === undefined) runtimeReceipt = capture.runtimeReceipt;
    else if (!isDeepStrictEqual(runtimeReceipt, capture.runtimeReceipt)) fail("CAPTURE_MIXED_RUNTIME");
    const source = sources.get(capture.runId);
    if (!source) fail("SOURCE_RUN_MISSING");
    const reportReceipt = source.report.meta?.b1RuntimeReceipt;
    if (
      !isObject(reportReceipt) ||
      !isDeepStrictEqual(reportReceipt.start, publicReceipt(capture.runtimeReceipt)) ||
      !isDeepStrictEqual(reportReceipt.end, publicReceipt(capture.runtimeReceipt))
    ) fail("SOURCE_RUNTIME_RECEIPT_MISMATCH");
    const dbRun = inventory.runs.get(capture.runId);
    const dbTurn = dbRun?.turns.get(capture.turnNo);
    if (!dbTurn || !inventory.eligibleTurns.has(key)) fail("INVENTORY_CAPTURE_MISMATCH");
    if (dbRun.packId !== capture.packId) fail("INVENTORY_PACK_MISMATCH");
    if (!isDeepStrictEqual(dbTurn.llmChoices, capture.finalChoices) || dbTurn.narrative !== capture.narrative) {
      fail("INVENTORY_CAPTURE_MISMATCH");
    }
    const sourceTurn = source.turns.get(capture.turnNo);
    if (!sourceTurn || sourceTurn.llmStatus !== "DONE") fail("SOURCE_TURN_MISSING");
    if (sourceTurn.narrative !== capture.narrative) fail("SOURCE_NARRATIVE_MISMATCH");
    if (sourceTurn.nodeType && sourceTurn.nodeType !== "LOCATION") fail("SOURCE_NODE_MISMATCH");
    if (source.report.meta?.scenario && source.report.meta.scenario !== capture.packId) fail("SOURCE_PACK_MISMATCH");
    checkChoices(sourceTurn.llmChoices, "SOURCE");
    if (!isDeepStrictEqual(capture.finalChoices, sourceTurn.llmChoices)) {
      fail("SOURCE_FINAL_CHOICES_MISMATCH");
    }
    const nanoChoices = capture.finalChoices.filter((choice) => choice.id.startsWith("nano_"));
    const observations = source.finalEvidence.filter((entry) => entry.turnNo === capture.turnNo);
    if (observations.length !== nanoChoices.length) fail("SOURCE_NANO_MISMATCH");
    const captureSha256 = hash(bytes);
    for (const choice of nanoChoices) {
      const observation = observations.find((entry) => entry.choiceId === choice.id);
      if (!observation) fail("SOURCE_NANO_MISMATCH");
      const evidenceId = hash(JSON.stringify([
        2, capture.runId, capture.turnNo, choice.id, captureSha256, source.sha256, inventory.sha256,
      ]));
      if (seenEvidenceIds.has(evidenceId)) fail("DUPLICATE_EVIDENCE_ID");
      seenEvidenceIds.add(evidenceId);
      cases.push({
        evidenceId,
        runtimeReceipt: capture.runtimeReceipt,
        runId: capture.runId,
        packId: capture.packId,
        turnNo: capture.turnNo,
        choiceId: choice.id,
        catalog: capture.catalog,
        finalChoice: choice,
        narrative: capture.narrative,
        narrativeModelUsed: dbTurn.llmModelUsed,
        nanoChoiceModelStatus: "UNVERIFIED",
        clickStatus: observation.clickStatus,
        nextTurnNo: observation.nextTurnNo,
        captureSha256,
        sourceSha256: source.sha256,
        sourceReportFile: `source-report-${source.sha256}.json`,
        inventorySha256: inventory.sha256,
        inventoryFile: inventory.filename,
      });
    }
  }
  if (capturedRuns.size !== sources.size) fail("SOURCE_RUN_UNMATCHED");
  const expectedTurns = new Set();
  for (const [runId, source] of sources) {
    const dbRun = inventory.runs.get(runId);
    if (source.report.meta?.scenario && source.report.meta.scenario !== dbRun.packId) {
      fail("INVENTORY_PACK_MISMATCH");
    }
    for (const [turnNo, turn] of source.turns) {
      if (
        turn.llmStatus === "DONE" && turn.nodeType === "LOCATION" &&
        Array.isArray(turn.llmChoices) &&
        turn.llmChoices.some((choice) => typeof choice?.id === "string" && choice.id.startsWith("nano_"))
      ) {
        const key = keyOf(runId, turnNo);
        expectedTurns.add(key);
        if (!inventory.eligibleTurns.has(key)) fail("INVENTORY_SOURCE_MISMATCH");
        const dbTurn = dbRun.turns.get(turnNo);
        if (
          !isDeepStrictEqual(dbTurn.llmChoices, turn.llmChoices) ||
          dbTurn.narrative !== turn.narrative
        ) fail("INVENTORY_SOURCE_MISMATCH");
      }
    }
  }
  if (
    inventory.eligibleTurns.size !== expectedTurns.size ||
    [...inventory.eligibleTurns].some((key) => !expectedTurns.has(key))
  ) fail("INVENTORY_SOURCE_COVERAGE_MISMATCH");
  if (
    expectedTurns.size !== seenTurns.size ||
    [...expectedTurns].some((key) => !seenTurns.has(key))
  ) fail("SOURCE_CAPTURE_COVERAGE_MISMATCH");
  if (cases.length === 0) fail("EVIDENCE_MISSING");
  return {
    packet: { schemaVersion: 2, cases },
    ledgerTemplate: {
      schemaVersion: 1,
      labels: cases.map(({ evidenceId }) => ({
        evidenceId, verdict: null, reviewer: null, reason: null, evidenceRef: null,
      })),
    },
    turns: seenTurns.size,
    sourceCopies: [...sources.values()].map(({ sha256, bytes }) => ({
      filename: `source-report-${sha256}.json`,
      bytes,
    })).concat([{ filename: inventory.filename, bytes: inventory.bytes }]),
  };
}

export function verifyReviewLedger(ledger, packet) {
  if (!isObject(ledger) || ledger.schemaVersion !== 1 || !Array.isArray(ledger.labels)) {
    fail("LEDGER_MALFORMED");
  }
  const cases = new Set(packet.cases.map(({ evidenceId }) => evidenceId));
  const seen = new Set();
  const labels = { ALLOW: 0, REJECT: 0, INSUFFICIENT: 0, PENDING: 0 };
  for (const label of ledger.labels) {
    if (!isObject(label) || !cases.has(label.evidenceId)) fail("LEDGER_EVIDENCE_ID_MISMATCH");
    if (seen.has(label.evidenceId)) fail("LEDGER_DUPLICATE_EVIDENCE_ID");
    seen.add(label.evidenceId);
    if (label.verdict === null) {
      if (label.reviewer !== null || label.reason !== null || label.evidenceRef !== null) {
        fail("LEDGER_PENDING_MALFORMED");
      }
      labels.PENDING++;
    } else if (
      VERDICTS.includes(label.verdict) && nonempty(label.reviewer) &&
      nonempty(label.reason) && nonempty(label.evidenceRef)
    ) {
      labels[label.verdict]++;
    } else {
      fail("LEDGER_LABEL_MALFORMED");
    }
  }
  labels.PENDING += cases.size - seen.size;
  return labels;
}

function writeImmutable(path, contents) {
  const temp = `${path}.${randomUUID()}.tmp`;
  try {
    writeFileSync(temp, contents, { flag: "wx", mode: 0o600 });
    chmodSync(temp, 0o600);
    const identity = lstatSync(temp);
    try {
      linkSync(temp, path);
      return { dev: identity.dev, ino: identity.ino };
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      checkOwnedFile(path, 0o600, "OUTPUT_FILE");
      if (!readFileSync(path).equals(contents)) fail("OUTPUT_CONFLICT");
      return null;
    }
  } finally {
    rmSync(temp, { force: true });
  }
}

function preflightOutput(path, contents) {
  let entry;
  try {
    entry = lstatSync(path);
  } catch (error) {
    if (error.code === "ENOENT") return;
    fail("OUTPUT_FILE_UNSAFE");
  }
  if (
    !entry.isFile() || (entry.mode & 0o777) !== 0o600 ||
    (process.getuid && entry.uid !== process.getuid())
  ) fail("OUTPUT_FILE_UNSAFE");
  if (!readFileSync(path).equals(contents)) fail("OUTPUT_CONFLICT");
}

export function writeReviewPacket(outputDir, packet, ledgerTemplate, sourceCopies, { preserveLedgerTemplate = false } = {}) {
  checkPrivateDirectory(outputDir, "OUTPUT_DIRECTORY");
  const outputs = sourceCopies.map(({ filename, bytes }) => ({ path: join(outputDir, filename), contents: bytes }));
  outputs.push({
    path: join(outputDir, PACKET_NAME),
    contents: Buffer.from(JSON.stringify(packet, null, 2) + "\n"),
  });
  if (!preserveLedgerTemplate) {
    outputs.push({
      path: join(outputDir, LEDGER_NAME),
      contents: Buffer.from(JSON.stringify(ledgerTemplate, null, 2) + "\n"),
    });
  }
  for (const { path, contents } of outputs) preflightOutput(path, contents);
  const created = [];
  try {
    for (const output of outputs) {
      const identity = writeImmutable(output.path, output.contents);
      if (identity) created.push({ ...output, identity });
    }
  } catch (error) {
    const cleanupErrors = [];
    for (const { path, contents, identity } of created.reverse()) {
      try {
        const entry = lstatSync(path);
        if (
          entry.dev === identity.dev && entry.ino === identity.ino &&
          entry.isFile() && (entry.mode & 0o777) === 0o600 &&
          (!process.getuid || entry.uid === process.getuid()) &&
          readFileSync(path).equals(contents)
        ) unlinkSync(path);
      } catch (cleanupError) {
        cleanupErrors.push(cleanupError);
      }
    }
    if (cleanupErrors.length > 0) {
      throw new AggregateError([error, ...cleanupErrors], "OUTPUT_ROLLBACK_FAILED");
    }
    throw error;
  }
}

function main(args) {
  const positional = args.filter((arg) => !arg.startsWith("--"));
  const flags = args.filter((arg) => arg.startsWith("--"));
  if (
    positional.length < 3 || flags.length < 1 || flags.length > 2 ||
    flags.some((arg) => !/^(?:--inventory|--ledger)=.+$/.test(arg)) ||
    flags.filter((arg) => arg.startsWith("--inventory=")).length !== 1 ||
    flags.filter((arg) => arg.startsWith("--ledger=")).length > 1
  ) fail("USAGE");
  const [captureDir, outputDir, ...reportPaths] = positional;
  const inventoryPath = flags.find((arg) => arg.startsWith("--inventory=")).slice("--inventory=".length);
  const { packet, ledgerTemplate, sourceCopies, turns } = buildReviewPacket(captureDir, reportPaths, inventoryPath);
  let labels = { ALLOW: 0, REJECT: 0, INSUFFICIENT: 0, PENDING: packet.cases.length };
  let preserveLedgerTemplate = false;
  const ledgerFlag = flags.find((arg) => arg.startsWith("--ledger="));
  if (ledgerFlag) {
    const path = ledgerFlag.slice("--ledger=".length);
    checkOwnedFile(path, 0o600, "LEDGER_FILE");
    labels = verifyReviewLedger(readJson(readFileSync(path), "LEDGER"), packet);
    preserveLedgerTemplate = resolve(path) === resolve(outputDir, LEDGER_NAME);
  }
  writeReviewPacket(outputDir, packet, ledgerTemplate, sourceCopies, { preserveLedgerTemplate });
  process.stdout.write(`${JSON.stringify({
    turns,
    cases: packet.cases.length,
    labels,
    packetFile: PACKET_NAME,
    ledgerTemplateFile: LEDGER_NAME,
  })}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    const kind = error instanceof Error && /^[A-Z_]+$/.test(error.message)
      ? error.message
      : "IO_FAILURE";
    process.stderr.write(`choice-grounding-review-packet: ${kind}\n`);
    process.exitCode = 1;
  }
}
