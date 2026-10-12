import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const VERDICTS = new Set([
  'ALLOW',
  'REJECT',
  'UNCLEAR',
  'NEEDS_HINT_FIX',
  'NEEDS_COPY_FIX',
]);

export function verifyChoicePresentationReview(packet, intake) {
  if (packet?.schemaVersion !== 2 || !Array.isArray(packet.cases)) {
    throw new Error('PACKET_MALFORMED');
  }
  if (
    intake?.schemaVersion !== 1 ||
    intake.verdictAxis !== 'PRESENTATION_ONLY' ||
    intake.groundingLedgerStatus !== 'UNREVIEWED' ||
    intake.status !== 'COMPLETE_PRESENTATION_REVIEW' ||
    !Array.isArray(intake.judgments)
  ) {
    throw new Error('PRESENTATION_REVIEW_MALFORMED');
  }
  if (packet.cases.length !== intake.judgments.length) {
    throw new Error('REVIEW_COVERAGE_MISMATCH');
  }

  const numbers = new Set();
  const verdicts = Object.fromEntries([...VERDICTS].map((verdict) => [verdict, 0]));
  const issues = {};
  for (const judgment of intake.judgments) {
    const number = judgment.number;
    const choiceCase = packet.cases[number - 1];
    if (
      !Number.isInteger(number) ||
      numbers.has(number) ||
      !choiceCase ||
      choiceCase.evidenceId !== judgment.evidenceId ||
      typeof choiceCase.narrative !== 'string' ||
      !choiceCase.narrative.trim() ||
      typeof choiceCase.finalChoice?.label !== 'string' ||
      typeof choiceCase.finalChoice?.hint !== 'string'
    ) {
      throw new Error('REVIEW_EVIDENCE_MISMATCH');
    }
    if (!VERDICTS.has(judgment.verdict)) {
      throw new Error('REVIEW_VERDICT_MALFORMED');
    }
    if (
      judgment.verdict !== 'ALLOW' &&
      (!judgment.reason?.trim() || !judgment.issueType?.trim() || judgment.groundingCounted !== false)
    ) {
      throw new Error('REVIEW_ISSUE_MALFORMED');
    }
    numbers.add(number);
    verdicts[judgment.verdict]++;
    if (judgment.issueType) {
      issues[judgment.issueType] = (issues[judgment.issueType] ?? 0) + 1;
    }
  }
  return { axis: 'PRESENTATION_ONLY', cases: numbers.size, verdicts, issues };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [packetPath, intakePath] = process.argv.slice(2);
  if (!packetPath || !intakePath) {
    throw new Error('usage: node scripts/choice-presentation-review.mjs <packet.json> <presentation-intake.json>');
  }
  const packet = JSON.parse(readFileSync(resolve(packetPath), 'utf8'));
  const intake = JSON.parse(readFileSync(resolve(intakePath), 'utf8'));
  process.stdout.write(`${JSON.stringify(verifyChoicePresentationReview(packet, intake), null, 2)}\n`);
}
