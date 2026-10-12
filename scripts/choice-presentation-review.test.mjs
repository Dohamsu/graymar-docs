import test from 'node:test';
import assert from 'node:assert/strict';
import { verifyChoicePresentationReview } from './choice-presentation-review.mjs';

const packet = {
  schemaVersion: 2,
  cases: [
    { evidenceId: 'a', narrative: '이렌이 기다려 달라고 말한다.', finalChoice: { label: '기다린다', hint: '좋은 인상을 남긴다' } },
    { evidenceId: 'b', narrative: '경비가 말을 건다.', finalChoice: { label: '숨는다', hint: '주변을 살핀다' } },
  ],
};
const intake = {
  schemaVersion: 1,
  verdictAxis: 'PRESENTATION_ONLY',
  groundingLedgerStatus: 'UNREVIEWED',
  status: 'COMPLETE_PRESENTATION_REVIEW',
  judgments: [
    { number: 1, evidenceId: 'a', verdict: 'ALLOW', reason: null },
    { number: 2, evidenceId: 'b', verdict: 'NEEDS_COPY_FIX', reason: '직전 발언과 연결되지 않음', issueType: 'SCENE_CONTINUITY', groundingCounted: false },
  ],
};

test('presentation review covers the packet without becoming a grounding score', () => {
  assert.deepEqual(verifyChoicePresentationReview(packet, intake), {
    axis: 'PRESENTATION_ONLY',
    cases: 2,
    verdicts: { ALLOW: 1, REJECT: 0, UNCLEAR: 0, NEEDS_HINT_FIX: 0, NEEDS_COPY_FIX: 1 },
    issues: { SCENE_CONTINUITY: 1 },
  });
});

test('a mismatched evidence ID or duplicate number fails closed', () => {
  assert.throws(
    () => verifyChoicePresentationReview(packet, { ...intake, judgments: [{ ...intake.judgments[0], evidenceId: 'wrong' }, intake.judgments[1]] }),
    /REVIEW_EVIDENCE_MISMATCH/,
  );
  assert.throws(
    () => verifyChoicePresentationReview(packet, { ...intake, judgments: [intake.judgments[0], { ...intake.judgments[1], number: 1 }] }),
    /REVIEW_EVIDENCE_MISMATCH/,
  );
});

test('issues cannot be counted as grounding failures or lack a reason', () => {
  assert.throws(
    () => verifyChoicePresentationReview(packet, { ...intake, judgments: [intake.judgments[0], { ...intake.judgments[1], groundingCounted: true }] }),
    /REVIEW_ISSUE_MALFORMED/,
  );
  assert.throws(
    () => verifyChoicePresentationReview(packet, { ...intake, judgments: [intake.judgments[0], { ...intake.judgments[1], reason: '' }] }),
    /REVIEW_ISSUE_MALFORMED/,
  );
});

test('formal grounding labels cannot masquerade as presentation review', () => {
  assert.throws(
    () => verifyChoicePresentationReview(packet, { ...intake, verdictAxis: 'GROUNDING' }),
    /PRESENTATION_REVIEW_MALFORMED/,
  );
});
