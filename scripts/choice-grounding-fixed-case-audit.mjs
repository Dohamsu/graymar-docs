import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { pathToFileURL } from "node:url";
import { extractFinalNanoChoiceEvidence } from "./choice-grounding-evidence.mjs";

function normalizeShadowTurns(shadowAudit, shadowFormat) {
  if (!shadowAudit || typeof shadowAudit !== "object" || Array.isArray(shadowAudit)) {
    throw new Error("shadow audit must be an object");
  }
  let turnKey;
  if (shadowFormat === "followup-v1") {
    if (Object.hasOwn(shadowAudit, "schemaVersion")) {
      throw new Error("shadow format conflicts with schema version");
    }
    turnKey = "serverTurnNo";
  } else if (shadowFormat === undefined && [1, 2].includes(shadowAudit.schemaVersion)) {
    turnKey = "turnNo";
  } else {
    throw new Error("unsupported shadow format or schema version");
  }
  if (!Array.isArray(shadowAudit.turns) || shadowAudit.turns.length === 0) {
    throw new Error("shadow turns are missing or empty");
  }

  const seenTurns = new Set();
  return shadowAudit.turns.map((turn) => {
    const wrongTurnKey = turnKey === "turnNo" ? "serverTurnNo" : "turnNo";
    if (
      !turn ||
      typeof turn !== "object" ||
      typeof turn.runId !== "string" ||
      turn.runId.trim() === "" ||
      !Object.hasOwn(turn, turnKey) ||
      Object.hasOwn(turn, wrongTurnKey) ||
      !Number.isSafeInteger(turn[turnKey]) ||
      turn[turnKey] <= 0 ||
      !Array.isArray(turn.records) ||
      turn.records.length === 0
    ) {
      throw new Error("shadow turn is malformed");
    }
    const turnNo = turn[turnKey];
    const turnId = JSON.stringify([turn.runId, turnNo]);
    if (seenTurns.has(turnId)) throw new Error(`duplicate shadow turn: ${turnId}`);
    seenTurns.add(turnId);

    const seenChoices = new Set();
    const records = turn.records.map((record) => {
      if (
        !record ||
        typeof record !== "object" ||
        typeof record.choiceId !== "string" ||
        record.choiceId.trim() === "" ||
        typeof record.finalLabel !== "string" ||
        record.finalLabel.trim() === "" ||
        !record.payload ||
        typeof record.payload !== "object" ||
        Array.isArray(record.payload)
      ) {
        throw new Error(`shadow record is malformed: ${turnId}`);
      }
      if (seenChoices.has(record.choiceId)) {
        throw new Error(`duplicate shadow choice: ${turnId}:${record.choiceId}`);
      }
      seenChoices.add(record.choiceId);
      if (
        shadowFormat === "followup-v1" &&
        (
          record.finalChoice?.id !== record.choiceId ||
          record.finalChoice?.label !== record.finalLabel ||
          record.finalChoice?.action?.type !== "CHOICE" ||
          !isDeepStrictEqual(record.finalChoice?.action?.payload, record.payload)
        )
      ) {
        throw new Error(`shadow final choice mismatch: ${turnId}:${record.choiceId}`);
      }
      return {
        choiceId: record.choiceId,
        finalLabel: record.finalLabel,
        payload: record.payload,
      };
    });
    return { runId: turn.runId, turnNo, records };
  });
}

function verifyShadowFinalSurfaces(shadowTurns, sourceReports) {
  const total = shadowTurns.reduce((count, turn) => count + turn.records.length, 0);
  if (sourceReports === undefined) {
    return { status: "UNVERIFIED", total, verified: 0 };
  }
  if (!Array.isArray(sourceReports) || sourceReports.length === 0) {
    throw new Error("shadow source reports are missing");
  }
  const evidenceByRun = new Map();
  for (const report of sourceReports) {
    if (typeof report?.runId !== "string" || !report.runId || evidenceByRun.has(report.runId)) {
      throw new Error("shadow source report run is missing or duplicate");
    }
    evidenceByRun.set(report.runId, extractFinalNanoChoiceEvidence(report));
  }
  const shadowRuns = new Set(shadowTurns.map((turn) => turn.runId));
  if (
    evidenceByRun.size !== shadowRuns.size ||
    [...evidenceByRun.keys()].some((runId) => !shadowRuns.has(runId))
  ) {
    throw new Error("shadow source report run mismatch");
  }
  for (const turn of shadowTurns) {
    const finalChoices = evidenceByRun.get(turn.runId).filter(
      (entry) => entry.turnNo === turn.turnNo,
    );
    if (
      finalChoices.length !== turn.records.length ||
      turn.records.some((record) => {
        const final = finalChoices.find((entry) => entry.choiceId === record.choiceId);
        return !final ||
          final.label !== record.finalLabel ||
          !isDeepStrictEqual(final.payload, record.payload);
      })
    ) {
      throw new Error(`shadow final surface mismatch: ${turn.runId}:${turn.turnNo}`);
    }
  }
  return { status: "VERIFIED", total, verified: total };
}

function readDeclaredShadowSources(shadowAudit, shadowFormat) {
  if (shadowFormat === "followup-v1") {
    if (!Array.isArray(shadowAudit.runs) || shadowAudit.runs.length === 0) {
      throw new Error("shadow source reports are missing");
    }
    return shadowAudit.runs.map((run) => {
      if (typeof run?.runId !== "string" || typeof run.playtestFile !== "string" || !run.playtestFile) {
        throw new Error("shadow source report path is missing");
      }
      const report = JSON.parse(readFileSync(run.playtestFile, "utf8"));
      if (report.runId !== run.runId) throw new Error("shadow source report run mismatch");
      return report;
    });
  }
  if (shadowAudit.schemaVersion === 1 && !Object.hasOwn(shadowAudit, "sourceReports")) {
    return undefined;
  }
  if (!Array.isArray(shadowAudit.sourceReports) || shadowAudit.sourceReports.length === 0) {
    throw new Error("shadow source reports are missing");
  }
  return shadowAudit.sourceReports.map((path) => {
    if (typeof path !== "string" || !path) {
      throw new Error("shadow source report path is missing");
    }
    return JSON.parse(readFileSync(path, "utf8"));
  });
}

/** 고정 표의 기대 판정과 실제 완료된 최종 Nano 선택지 증거를 분리해 센다. */
export function auditFixedCaseEvidence(
  markdown,
  samples,
  { shadowAudit, sourceReports, shadowFormat, shadowSourceReports } = {},
) {
  const shadowTurns = shadowAudit === undefined
    ? undefined
    : normalizeShadowTurns(shadowAudit, shadowFormat);
  const shadowFinalSurfaceVerification = shadowTurns
    ? verifyShadowFinalSurfaces(shadowTurns, shadowSourceReports)
    : undefined;
  const cases = new Map();
  for (const line of markdown.split("\n")) {
    const match =
      /^\|\s*([GS]\d{2})\s*\|(?:[^|]*\|){3}\s*(거부|허용)\s*\|/.exec(line);
    if (!match) continue;
    const [, id, expected] = match;
    if (cases.has(id)) throw new Error(`duplicate fixed case: ${id}`);
    cases.set(id, expected);
  }

  const linked = [];
  const linkedIds = new Set();
  const evidenceOf = (report, expected) =>
    extractFinalNanoChoiceEvidence(report).find(
      (entry) =>
        entry.runId === expected.runId &&
        entry.turnNo === expected.turnNo &&
        entry.choiceId === expected.choiceId,
    );
  const comparableEvidence = (record) =>
    record && {
      runId: record.runId,
      turnNo: record.turnNo,
      choiceId: record.choiceId,
      label: record.label,
      payload: record.payload,
      clickStatus: record.clickStatus,
      nextTurnNo: record.nextTurnNo,
    };
  for (const sample of samples) {
    const { caseId, expected, reportExcerpt, sourceReport } = sample;
    if (!cases.has(caseId)) throw new Error(`unknown fixed case: ${caseId}`);
    if (linkedIds.has(caseId)) throw new Error(`duplicate sample: ${caseId}`);
    linkedIds.add(caseId);
    const record = evidenceOf(reportExcerpt, expected);
    if (
      !record ||
      record.label !== expected.label ||
      !isDeepStrictEqual(record.payload, expected.payload)
    ) {
      throw new Error(`final surface mismatch: ${caseId}`);
    }
    if (sourceReports) {
      const source = sourceReports.get(sourceReport);
      if (!source) throw new Error(`missing source report: ${caseId}`);
      if (
        !isDeepStrictEqual(
          comparableEvidence(record),
          comparableEvidence(evidenceOf(source, expected)),
        )
      ) {
        throw new Error(`source report mismatch: ${caseId}`);
      }
    }
    linked.push({ caseId, clickStatus: record.clickStatus });
  }

  const statuses = linked.map((entry) => entry.clickStatus);
  const fixedRuns = new Set(samples.map(({ expected }) => expected.runId));
  const sharedRunIds = shadowTurns
    ? new Set(shadowTurns.map((turn) => turn.runId).filter((runId) => fixedRuns.has(runId))).size
    : undefined;
  const sameRunTurnSamples = shadowTurns
    ? samples.filter(({ expected }) => shadowTurns.some(
        (turn) => turn.runId === expected.runId && turn.turnNo === expected.turnNo,
      )).length
    : undefined;
  const sameSurfaceShadow = shadowTurns
    ? samples.filter(({ expected }) =>
        shadowTurns.some(
          (turn) =>
            turn.runId === expected.runId &&
            turn.turnNo === expected.turnNo &&
            turn.records.some(
              (record) =>
                record.choiceId === expected.choiceId &&
                record.finalLabel === expected.label &&
                isDeepStrictEqual(record.payload, expected.payload),
            ),
        ),
      ).length
    : undefined;
  return {
    fixedCases: cases.size,
    expectedReject: [...cases.values()].filter((value) => value === "거부")
      .length,
    expectedAllow: [...cases.values()].filter((value) => value === "허용")
      .length,
    exactFinalNano: linked.length,
    linkedReject: linked.filter((entry) => cases.get(entry.caseId) === "거부")
      .length,
    linkedAllow: linked.filter((entry) => cases.get(entry.caseId) === "허용")
      .length,
    clicked: statuses.filter((value) => value === "CLICKED").length,
    clickedReject: linked.filter(
      (entry) =>
        entry.clickStatus === "CLICKED" && cases.get(entry.caseId) === "거부",
    ).length,
    clickedAllow: linked.filter(
      (entry) =>
        entry.clickStatus === "CLICKED" && cases.get(entry.caseId) === "허용",
    ).length,
    exposedNotClicked: statuses.filter((value) => value === "NOT_CLICKED")
      .length,
    clickUnobserved: statuses.filter((value) => value === "UNOBSERVED").length,
    unlinked: cases.size - linked.length,
    ...(sourceReports ? { sourceVerified: linked.length } : {}),
    ...(shadowTurns ? {
      sharedRunIds,
      sameRunTurnSamples,
      sameSurfaceShadow,
      shadowFinalSurfaceVerification,
    } : {}),
    linked,
    unlinkedCaseIds: [...cases.keys()].filter((id) => !linkedIds.has(id)),
  };
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const args = process.argv.slice(2);
  const verifySource = args.includes("--verify-source");
  const formatFlags = args.filter((arg) => arg.startsWith("--shadow-format="));
  const unknownFlags = args.filter(
    (arg) => arg.startsWith("--") && arg !== "--verify-source" && arg !== "--shadow-format=followup-v1",
  );
  if (unknownFlags.length > 0 || formatFlags.length > 1) {
    throw new Error(`unknown or duplicate audit flag: ${[...unknownFlags, ...formatFlags].join(", ")}`);
  }
  const shadowFormat = formatFlags.length === 1 ? "followup-v1" : undefined;
  const paths = args.filter((arg) => !arg.startsWith("--"));
  const [fixedCasePath, samplePath, shadowPath] = paths;
  if (paths.length > 3 || (shadowFormat && !shadowPath)) {
    throw new Error("shadow format requires one shadow audit path");
  }
  if (!fixedCasePath || !samplePath) {
    process.stderr.write(
      "사용법: node scripts/choice-grounding-fixed-case-audit.mjs <fixed-cases.md> <evidence.json> [shadow-audit.json] [--verify-source] [--shadow-format=followup-v1]\n",
    );
    process.exitCode = 2;
  } else {
    const fixedCases = readFileSync(fixedCasePath, "utf8");
    const { samples } = JSON.parse(readFileSync(samplePath, "utf8"));
    const shadowAudit = shadowPath
      ? JSON.parse(readFileSync(shadowPath, "utf8"))
      : undefined;
    const shadowSourceReports = verifySource && shadowAudit
      ? readDeclaredShadowSources(shadowAudit, shadowFormat)
      : undefined;
    const sourceReports = verifySource
      ? new Map(
          samples.map(({ sourceReport }) => [
            sourceReport,
            JSON.parse(readFileSync(sourceReport, "utf8")),
          ]),
        )
      : undefined;
    process.stdout.write(
      `${JSON.stringify(auditFixedCaseEvidence(fixedCases, samples, {
        shadowAudit,
        sourceReports,
        shadowFormat,
        shadowSourceReports,
      }), null, 2)}\n`,
    );
  }
}
