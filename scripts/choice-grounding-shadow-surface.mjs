import { readFileSync } from "node:fs";
import { isDeepStrictEqual } from "node:util";
import { pathToFileURL } from "node:url";
import { extractFinalNanoChoiceEvidence } from "./choice-grounding-evidence.mjs";

/** B1 shadow와 실제 DONE 최종 선택지의 정확한 표면을 연결한다. 사람 판정은 하지 않는다. */
export function auditShadowSurfaces(shadowAudit, reports) {
  const reportByRun = new Map();
  for (const report of reports) {
    if (!report?.runId || reportByRun.has(report.runId)) {
      throw new Error(`duplicate or missing report run: ${report?.runId}`);
    }
    reportByRun.set(report.runId, extractFinalNanoChoiceEvidence(report));
  }

  const seenTurns = new Set();
  const rows = [];
  for (const turn of shadowAudit?.turns ?? []) {
    const turnKey = `${turn.runId}:${turn.turnNo}`;
    if (seenTurns.has(turnKey)) throw new Error(`duplicate shadow turn: ${turnKey}`);
    seenTurns.add(turnKey);
    if (!Array.isArray(turn.publicRefIds) || turn.catalogTurnNo !== turn.turnNo) {
      throw new Error(`missing public refs or catalog turn mismatch: ${turnKey}`);
    }
    const evidence = reportByRun.get(turn.runId)?.filter(
      (entry) => entry.turnNo === turn.turnNo,
    );
    if (!evidence || evidence.length !== turn.finalNanoCount) {
      throw new Error(`final Nano count mismatch: ${turnKey}`);
    }
    if (!Array.isArray(turn.records) || turn.records.length !== evidence.length) {
      throw new Error(`shadow record count mismatch: ${turnKey}`);
    }
    const seenChoices = new Set();
    for (const record of turn.records) {
      const key = `${turnKey}:${record.choiceId}`;
      if (seenChoices.has(record.choiceId)) throw new Error(`duplicate shadow choice: ${key}`);
      seenChoices.add(record.choiceId);
      if (
        typeof record.candidateAffordance !== "string" ||
        record.candidateAffordance.length === 0 ||
        typeof record.proposal?.intent !== "string" ||
        record.proposal.intent.length === 0
      ) {
        throw new Error(`missing candidate affordance or proposal intent: ${key}`);
      }
      const final = evidence.find((entry) => entry.choiceId === record.choiceId);
      if (
        !final ||
        final.label !== record.finalLabel ||
        !isDeepStrictEqual(final.payload, record.payload)
      ) {
        throw new Error(`final surface mismatch: ${key}`);
      }
      rows.push({
        runId: turn.runId,
        packId: turn.packId,
        turnNo: turn.turnNo,
        choiceId: record.choiceId,
        label: final.label,
        payload: final.payload,
        candidateAffordance: record.candidateAffordance ?? null,
        proposalIntent: record.proposal?.intent ?? null,
        status: record.status,
        reasons: record.reasons,
        publicRefIds: turn.publicRefIds,
        clickStatus: final.clickStatus,
        nextTurnNo: final.nextTurnNo,
      });
    }
  }

  const count = (predicate) => rows.filter(predicate).length;
  return {
    summary: {
      turns: seenTurns.size,
      finalNano: rows.length,
      clicked: count((r) => r.clickStatus === "CLICKED"),
      exposedNotClicked: count((r) => r.clickStatus === "NOT_CLICKED"),
      clickUnobserved: count((r) => r.clickStatus === "UNOBSERVED"),
      contradicted: count((r) => r.status === "CONTRADICTED"),
      structureMatch: count((r) => r.status === "STRUCTURE_MATCH"),
      unresolved: count((r) => r.status === "UNRESOLVED"),
      missing: count((r) => r.status === "MISSING"),
      malformed: count((r) => r.status === "MALFORMED"),
      proposalCandidateAffordanceChanged: count(
        (r) =>
          r.proposalIntent !== null &&
          r.candidateAffordance !== null &&
          r.proposalIntent !== r.candidateAffordance,
      ),
      candidatePayloadAffordanceChanged: count(
        (r) =>
          r.candidateAffordance !== null &&
          r.candidateAffordance !== r.payload?.affordance,
      ),
    },
    rows,
  };
}

/** 보관한 원시 로그와 원본 보고서를 발췌·요약본에서 독립적으로 다시 읽는다. */
export function verifyShadowSources(shadowAudit, sourceReports, rawStdout) {
  const rawTurns = rawStdout.split("\n").filter(Boolean).map((line) => {
    const match = /\[ChoiceGroundingShadow\] run=(\S+) pack=(\S+) turn=(\d+) (\{.*\})\r?$/.exec(line);
    if (!match) throw new Error("unparseable server stdout shadow line");
    return {
      runId: match[1],
      packId: match[2],
      turnNo: Number(match[3]),
      ...JSON.parse(match[4]),
    };
  });
  if (!isDeepStrictEqual(rawTurns, shadowAudit.turns)) {
    throw new Error("server stdout mismatch");
  }
  const sourceByRun = new Map(sourceReports.map((report) => [report.runId, report]));
  const excerptRunIds = Array.isArray(shadowAudit.reportExcerpts)
    ? shadowAudit.reportExcerpts.map((report) => report.runId)
    : [];
  const excerptRuns = new Set(excerptRunIds);
  const shadowRuns = new Set(shadowAudit.turns.map((turn) => turn.runId));
  if (
    sourceByRun.size !== sourceReports.length ||
    !Array.isArray(shadowAudit.reportExcerpts) ||
    shadowAudit.reportExcerpts.length !== sourceReports.length ||
    excerptRuns.size !== sourceByRun.size ||
    shadowRuns.size !== sourceByRun.size ||
    [...sourceByRun.keys()].some(
      (runId) => !excerptRuns.has(runId) || !shadowRuns.has(runId),
    )
  ) {
    throw new Error("source report excerpt mismatch: run count");
  }
  for (const excerpt of shadowAudit.reportExcerpts) {
    const source = sourceByRun.get(excerpt.runId);
    if (!source || !Array.isArray(excerpt.turns)) {
      throw new Error(`source report excerpt mismatch: ${excerpt.runId}`);
    }
    const shadowTurns = new Set(
      shadowAudit.turns
        .filter((turn) => turn.runId === excerpt.runId)
        .map((turn) => turn.turnNo),
    );
    const keptTurns = new Set([
      ...shadowTurns,
      ...[...shadowTurns].map((turnNo) => turnNo + 1),
    ]);
    const expectedTurns = source.turns
      .filter((turn) => keptTurns.has(turn.turnNo))
      .map((turn) => ({
        turn: turn.turn,
        turnNo: turn.turnNo,
        input: turn.input,
        llmStatus: turn.llmStatus,
        ...(shadowTurns.has(turn.turnNo)
          ? {
              narrative: turn.narrative,
              llmChoices: (turn.llmChoices ?? [])
                .filter((choice) => choice.id?.startsWith("nano_"))
                .map((choice) => ({
                  id: choice.id,
                  label: choice.label,
                  action: {
                    type: choice.action?.type,
                    payload: choice.action?.payload,
                  },
                })),
            }
          : {}),
      }));
    if (!isDeepStrictEqual(expectedTurns, excerpt.turns)) {
      throw new Error(`source report excerpt mismatch: ${excerpt.runId}`);
    }
  }
  return auditShadowSurfaces(shadowAudit, sourceReports);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const verifySource = process.argv.includes("--verify-source");
  const [shadowPath, ...reportPaths] = process.argv.slice(2).filter((arg) => arg !== "--verify-source");
  if (!shadowPath) {
    process.stderr.write(
      "사용법: node scripts/choice-grounding-shadow-surface.mjs <shadow-audit.json> [playtest-report.json ...] [--verify-source]\n",
    );
    process.exitCode = 2;
  } else {
    const shadow = JSON.parse(readFileSync(shadowPath, "utf8"));
    const sourcePaths = reportPaths.length > 0 ? reportPaths : shadow.sourceReports;
    const reports = verifySource
      ? sourcePaths?.map((path) => JSON.parse(readFileSync(path, "utf8")))
      : reportPaths.length > 0
        ? reportPaths.map((path) => JSON.parse(readFileSync(path, "utf8")))
        : shadow.reportExcerpts;
    if (!Array.isArray(reports) || reports.length === 0) {
      throw new Error("report excerpts missing: provide original playtest report paths");
    }
    const result = verifySource
      ? verifyShadowSources(shadow, reports, readFileSync(shadow.sourceLog, "utf8"))
      : auditShadowSurfaces(shadow, reports);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  }
}
