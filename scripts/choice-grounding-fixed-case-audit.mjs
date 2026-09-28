import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { pathToFileURL } from "node:url";
import { extractFinalNanoChoiceEvidence } from "./choice-grounding-evidence.mjs";

/** 고정 표의 기대 판정과 실제 완료된 최종 Nano 선택지 증거를 분리해 센다. */
export function auditFixedCaseEvidence(
  markdown,
  samples,
  shadowAudit,
  sourceReports,
) {
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
  const sameSurfaceShadow = shadowAudit
    ? samples.filter(({ expected }) =>
        shadowAudit.turns?.some(
          (turn) =>
            turn.runId === expected.runId &&
            turn.turnNo === expected.turnNo &&
            turn.records?.some(
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
    ...(shadowAudit ? { sameSurfaceShadow } : {}),
    linked,
    unlinkedCaseIds: [...cases.keys()].filter((id) => !linkedIds.has(id)),
  };
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const verifySource = process.argv.includes("--verify-source");
  const [fixedCasePath, samplePath, shadowPath] = process.argv
    .slice(2)
    .filter((arg) => arg !== "--verify-source");
  if (!fixedCasePath || !samplePath) {
    process.stderr.write(
      "사용법: node scripts/choice-grounding-fixed-case-audit.mjs <fixed-cases.md> <evidence.json> [shadow-audit.json] [--verify-source]\n",
    );
    process.exitCode = 2;
  } else {
    const fixedCases = readFileSync(fixedCasePath, "utf8");
    const { samples } = JSON.parse(readFileSync(samplePath, "utf8"));
    const shadowAudit = shadowPath
      ? JSON.parse(readFileSync(shadowPath, "utf8"))
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
      `${JSON.stringify(auditFixedCaseEvidence(fixedCases, samples, shadowAudit, sourceReports), null, 2)}\n`,
    );
  }
}
