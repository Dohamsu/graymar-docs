import assert from "node:assert/strict";
import test from "node:test";
import {
  auditShadowSurfaces,
  verifyShadowSources,
} from "./choice-grounding-shadow-surface.mjs";

const payload = { affordance: "TALK", sourceNpcId: "NPC_A", riskLevel: 1 };
const report = {
  runId: "run-1",
  turns: [
    {
      turn: 1,
      turnNo: 4,
      input: "AGENT:explore_talk",
      llmStatus: "DONE",
      narrative: "A가 장부 앞에 서 있다.",
      llmChoices: [
        {
          id: "nano_4_0",
          label: "A에게 묻는다",
          action: { type: "CHOICE", payload },
        },
      ],
    },
    { turn: 2, turnNo: 5, input: "AGENT:nano_4_0", llmStatus: "DONE" },
  ],
};
const shadow = {
  turns: [
    {
      runId: "run-1",
      packId: "star_sand_v1",
      turnNo: 4,
      catalogTurnNo: 4,
      publicRefIds: ["NPC_PRESENT:4:0"],
      finalNanoCount: 1,
      records: [
        {
          choiceId: "nano_4_0",
          candidateLabel: "A에게 묻는다",
          candidateAffordance: "TALK",
          finalLabel: "A에게 묻는다",
          payload,
          proposal: { intent: "TALK", targetRef: "NPC_A" },
          status: "CONTRADICTED",
          reasons: ["UNKNOWN_REF"],
        },
      ],
    },
  ],
};

test("shadow를 동일 런·턴·최종 라벨·payload·클릭에 연결한다", () => {
  const audit = auditShadowSurfaces(shadow, [report]);
  assert.deepEqual(audit.summary, {
    turns: 1,
    finalNano: 1,
    clicked: 1,
    exposedNotClicked: 0,
    clickUnobserved: 0,
    contradicted: 1,
    structureMatch: 0,
    unresolved: 0,
    missing: 0,
    malformed: 0,
    proposalCandidateAffordanceChanged: 0,
    candidatePayloadAffordanceChanged: 0,
  });
  assert.deepEqual(audit.rows[0], {
    runId: "run-1",
    packId: "star_sand_v1",
    turnNo: 4,
    choiceId: "nano_4_0",
    label: "A에게 묻는다",
    payload,
    candidateAffordance: "TALK",
    proposalIntent: "TALK",
    status: "CONTRADICTED",
    reasons: ["UNKNOWN_REF"],
    publicRefIds: ["NPC_PRESENT:4:0"],
    clickStatus: "CLICKED",
    nextTurnNo: 5,
  });
});

test("구조 제안↔원 후보와 원 후보↔최종 payload 변경을 별도로 센다", () => {
  const changed = {
    ...shadow,
    turns: [{
      ...shadow.turns[0],
      records: [{
        ...shadow.turns[0].records[0],
        candidateAffordance: "PERSUADE",
        proposal: { intent: "INVESTIGATE" },
      }],
    }],
  };
  const summary = auditShadowSurfaces(changed, [report]).summary;
  assert.equal(summary.proposalCandidateAffordanceChanged, 1);
  assert.equal(summary.candidatePayloadAffordanceChanged, 1);
});

test("ID가 같아도 최종 라벨이나 payload가 다른 shadow는 거부한다", () => {
  for (const record of [
    { finalLabel: "달라진 라벨" },
    { payload: { ...payload, affordance: "PERSUADE" } },
  ]) {
    assert.throws(
      () =>
        auditShadowSurfaces(
          {
            turns: [
              {
                ...shadow.turns[0],
                records: [{ ...shadow.turns[0].records[0], ...record }],
              },
            ],
          },
          [report],
        ),
      /final surface mismatch/,
    );
  }
});

test("중복 관찰과 공개 참조 누락은 같은 표면 근거로 승인하지 않는다", () => {
  assert.throws(
    () => auditShadowSurfaces({ turns: [...shadow.turns, shadow.turns[0]] }, [report]),
    /duplicate shadow turn/,
  );
  assert.throws(
    () =>
      auditShadowSurfaces(
        { turns: [{ ...shadow.turns[0], publicRefIds: undefined }] },
        [report],
      ),
    /missing public refs/,
  );
});

test("후보 affordance 또는 제안 intent가 없으면 변경 지표의 분모에서 조용히 빼지 않는다", () => {
  for (const record of [
    { candidateAffordance: undefined },
    { proposal: { targetRef: "NPC_A" } },
  ]) {
    assert.throws(
      () =>
        auditShadowSurfaces(
          {
            turns: [{
              ...shadow.turns[0],
              records: [{ ...shadow.turns[0].records[0], ...record }],
            }],
          },
          [report],
        ),
      /missing candidate affordance or proposal intent/,
    );
  }
});

test("원시 서버 로그와 원본 플레이테스트를 별도 출처로 대조한다", () => {
  const archived = {
    ...shadow,
    reportExcerpts: [{
      runId: report.runId,
      turns: report.turns.map((turn, index) => index === 0
        ? turn
        : { turn: turn.turn, turnNo: turn.turnNo, input: turn.input, llmStatus: turn.llmStatus }),
    }],
  };
  const raw = `[ChoiceGroundingShadow] run=run-1 pack=star_sand_v1 turn=4 ${JSON.stringify(
    Object.fromEntries(
      Object.entries(shadow.turns[0]).filter(
        ([key]) => !["runId", "packId", "turnNo"].includes(key),
      ),
    ),
  )}\n`;
  assert.equal(verifyShadowSources(archived, [report], raw).summary.finalNano, 1);
  assert.throws(
    () => verifyShadowSources({ ...archived, turns: [{ ...shadow.turns[0], publicRefIds: [] }] }, [report], raw),
    /server stdout mismatch/,
  );
  assert.throws(
    () => verifyShadowSources({ ...archived, reportExcerpts: [{ ...archived.reportExcerpts[0], turns: [{ ...archived.reportExcerpts[0].turns[0], narrative: "고쳐 쓴 문장" }, archived.reportExcerpts[0].turns[1]] }] }, [report], raw),
    /source report excerpt mismatch/,
  );
  assert.throws(
    () => verifyShadowSources({ ...archived, reportExcerpts: [{ ...archived.reportExcerpts[0], turns: [archived.reportExcerpts[0].turns[0]] }] }, [report], raw),
    /source report excerpt mismatch/,
  );
  const secondReport = { ...report, runId: "run-2" };
  const secondShadow = { ...shadow.turns[0], runId: "run-2" };
  assert.throws(
    () => verifyShadowSources(
      {
        ...archived,
        turns: [shadow.turns[0], secondShadow],
        reportExcerpts: [archived.reportExcerpts[0], archived.reportExcerpts[0]],
      },
      [report, secondReport],
      `${raw}${raw.replace("run=run-1", "run=run-2")}`,
    ),
    /source report excerpt mismatch/,
  );
});
