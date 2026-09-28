import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

/** playtest 원문의 DONE 최종 Nano 선택지와 바로 다음 턴 입력만 연결한다. */
export function extractFinalNanoChoiceEvidence(report) {
  const turns = Array.isArray(report?.turns) ? report.turns : [];
  const evidence = [];
  for (const [index, turn] of turns.entries()) {
    if (turn?.llmStatus !== "DONE" || !Array.isArray(turn.llmChoices)) continue;
    const turnNo = turn.turnNo ?? turn.turn;
    const following = turns[index + 1];
    const nextTurnNo = following?.turnNo ?? following?.turn;
    const hasNextTurn = Number.isInteger(turnNo) && nextTurnNo === turnNo + 1;
    const selectedId = hasNextTurn
      ? /^(?:AGENT|CHOICE):([^\s]+)(?: \((?:preferred|arc|sequence \d+\/\d+)\))?$/.exec(
          following.input ?? "",
        )?.[1]
      : null;
    for (const choice of turn.llmChoices) {
      if (typeof choice?.id !== "string" || !choice.id.startsWith("nano_")) {
        continue;
      }
      const clicked = selectedId === choice.id;
      evidence.push({
        runId: report.runId ?? null,
        playtestTurn: turn.turn ?? null,
        turnNo,
        choiceId: choice.id,
        label: choice.label ?? null,
        payload: choice.action?.payload ?? null,
        clickStatus: !hasNextTurn
          ? "UNOBSERVED"
          : clicked
            ? "CLICKED"
            : "NOT_CLICKED",
        nextTurnNo: clicked ? nextTurnNo : null,
      });
    }
  }
  return evidence;
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const file = process.argv[2];
  if (!file) {
    process.stderr.write(
      "사용법: node scripts/choice-grounding-evidence.mjs <playtest-report.json>\n",
    );
    process.exitCode = 2;
  } else {
    const report = JSON.parse(readFileSync(file, "utf8"));
    process.stdout.write(
      `${JSON.stringify(extractFinalNanoChoiceEvidence(report), null, 2)}\n`,
    );
  }
}
