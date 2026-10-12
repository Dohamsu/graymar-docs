import assert from "node:assert/strict";
import test from "node:test";
import { auditFixedCaseEvidence } from "./choice-grounding-fixed-case-audit.mjs";

const fixedCases = `| ID | 팩 | 조건 | 정본 | 기대 | 클릭 근거 | 출처 |
|---|---|---|---|---|---|---|
| G01 | graymar | 잘못된 가방 | 미공개 | 거부 | 실제 클릭 | 실런 |
| S11 | star_sand | 열린 질문 | 공개 | 허용 | 미관찰 | 회귀 |
`;

const sample = {
  caseId: "G01",
  sourceReport: "/report.json",
  expected: {
    runId: "run-1",
    turnNo: 7,
    choiceId: "nano_7_0",
    label: "잘못된 가방을 살핀다",
    payload: { affordance: "OBSERVE", sourceNpcId: "NPC_E" },
  },
  reportExcerpt: {
    runId: "run-1",
    turns: [
      {
        turnNo: 7,
        llmStatus: "DONE",
        llmChoices: [
          {
            id: "nano_7_0",
            label: "잘못된 가방을 살핀다",
            action: {
              type: "CHOICE",
              payload: { affordance: "OBSERVE", sourceNpcId: "NPC_E" },
            },
          },
        ],
      },
      { turnNo: 8, input: "AGENT:nano_7_0" },
    ],
  },
};

const matchingRecord = {
  choiceId: sample.expected.choiceId,
  finalLabel: sample.expected.label,
  payload: sample.expected.payload,
};

const matchingTurn = {
  runId: sample.expected.runId,
  turnNo: sample.expected.turnNo,
  records: [matchingRecord],
};

test("고정 사례는 정확히 같은 최종 Nano와 다음 턴 클릭만 실측 증거로 센다", () => {
  assert.deepEqual(auditFixedCaseEvidence(fixedCases, [sample]), {
    fixedCases: 2,
    expectedReject: 1,
    expectedAllow: 1,
    exactFinalNano: 1,
    linkedReject: 1,
    linkedAllow: 0,
    clicked: 1,
    clickedReject: 1,
    clickedAllow: 0,
    exposedNotClicked: 0,
    clickUnobserved: 0,
    unlinked: 1,
    linked: [{ caseId: "G01", clickStatus: "CLICKED" }],
    unlinkedCaseIds: ["S11"],
  });
});

test("라벨 또는 payload가 달라진 표본을 같은 사례로 승인하지 않는다", () => {
  assert.throws(
    () =>
      auditFixedCaseEvidence(fixedCases, [
        {
          ...sample,
          expected: {
            ...sample.expected,
            payload: { affordance: "TALK", sourceNpcId: "NPC_E" },
          },
        },
      ]),
    /final surface mismatch: G01/,
  );
});

test("다른 런의 shadow 판정은 고정 사례의 미검출·오경보 점수로 연결하지 않는다", () => {
  const shadow = {
    schemaVersion: 2,
    turns: [
      {
        runId: "different-run",
        turnNo: 7,
        records: [
          {
            choiceId: "nano_7_0",
            finalLabel: "잘못된 가방을 살핀다",
            payload: { affordance: "OBSERVE", sourceNpcId: "NPC_E" },
            status: "CONTRADICTED",
          },
        ],
      },
    ],
  };
  const result = auditFixedCaseEvidence(fixedCases, [sample], { shadowAudit: shadow });
  assert.equal(result.sharedRunIds, 0);
  assert.equal(result.sameRunTurnSamples, 0);
  assert.equal(result.sameSurfaceShadow, 0);
});

test("같은 런, 같은 서버 턴, 최종 표면 일치를 각각 다른 수치로 센다", () => {
  const cases = [
    {
      turn: { ...matchingTurn, turnNo: matchingTurn.turnNo + 1 },
      counts: [1, 0, 0],
    },
    {
      turn: {
        ...matchingTurn,
        records: [{ ...matchingRecord, finalLabel: "다른 최종 문구" }],
      },
      counts: [1, 1, 0],
    },
    {
      turn: {
        ...matchingTurn,
        records: [{ ...matchingRecord, payload: { affordance: "TALK" } }],
      },
      counts: [1, 1, 0],
    },
    { turn: matchingTurn, counts: [1, 1, 1] },
  ];
  for (const { turn, counts } of cases) {
    const result = auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: { schemaVersion: 2, turns: [turn] },
    });
    assert.deepEqual(
      [result.sharedRunIds, result.sameRunTurnSamples, result.sameSurfaceShadow],
      counts,
    );
  }
});

test("버전 1·2 shadow는 같은 최종 선택지만 중첩으로 센다", () => {
  for (const schemaVersion of [1, 2]) {
    const result = auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: { schemaVersion, turns: [matchingTurn] },
    });
    assert.equal(result.sameSurfaceShadow, 1);
  }
});

test("shadow 원본이 없으면 보류하고 원본 최종 Nano가 같을 때만 검증한다", () => {
  const shadow = { schemaVersion: 2, turns: [matchingTurn] };
  assert.deepEqual(
    auditFixedCaseEvidence(fixedCases, [sample], { shadowAudit: shadow })
      .shadowFinalSurfaceVerification,
    { status: "UNVERIFIED", total: 1, verified: 0 },
  );
  assert.deepEqual(
    auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: shadow,
      shadowSourceReports: [sample.reportExcerpt],
    }).shadowFinalSurfaceVerification,
    { status: "VERIFIED", total: 1, verified: 1 },
  );
  assert.throws(
    () => auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: shadow,
      shadowSourceReports: [],
    }),
    /shadow source report/,
  );
  const changedReport = {
    ...sample.reportExcerpt,
    turns: [{
      ...sample.reportExcerpt.turns[0],
      llmChoices: [{
        ...sample.reportExcerpt.turns[0].llmChoices[0],
        label: "원본에서 다른 최종 문구",
      }],
    }],
  };
  assert.throws(
    () => auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: shadow,
      shadowSourceReports: [changedReport],
    }),
    /shadow final surface mismatch/,
  );
  const changedPayloadReport = {
    ...sample.reportExcerpt,
    turns: [{
      ...sample.reportExcerpt.turns[0],
      llmChoices: [{
        ...sample.reportExcerpt.turns[0].llmChoices[0],
        action: { type: "CHOICE", payload: { affordance: "TALK" } },
      }],
    }],
  };
  assert.throws(
    () => auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: shadow,
      shadowSourceReports: [changedPayloadReport],
    }),
    /shadow final surface mismatch/,
  );
  assert.throws(
    () => auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: shadow,
      shadowSourceReports: [{ ...sample.reportExcerpt, runId: "different-run" }],
    }),
    /shadow source report run mismatch/,
  );
});

test("후속 실런 형식은 명시한 선택자와 최종 choice 대조가 있어야 연결된다", () => {
  const followup = {
    turns: [{
      runId: sample.expected.runId,
      serverTurnNo: sample.expected.turnNo,
      records: [{
        ...matchingRecord,
        finalChoice: {
          id: sample.expected.choiceId,
          label: sample.expected.label,
          action: { type: "CHOICE", payload: sample.expected.payload },
        },
      }],
    }],
  };
  assert.throws(
    () => auditFixedCaseEvidence(fixedCases, [sample], { shadowAudit: followup }),
    /shadow format/,
  );
  assert.equal(
    auditFixedCaseEvidence(fixedCases, [sample], {
      shadowAudit: followup,
      shadowFormat: "followup-v1",
    })
      .sameSurfaceShadow,
    1,
  );
  for (const finalChoice of [
    { id: "other" },
    { label: "다른 문구" },
    { action: { type: "CHOICE", payload: { affordance: "TALK" } } },
  ]) {
    const changed = {
      turns: [{
        ...followup.turns[0],
        records: [{
          ...followup.turns[0].records[0],
          finalChoice: {
            ...followup.turns[0].records[0].finalChoice,
            ...finalChoice,
          },
        }],
      }],
    };
    assert.throws(
      () => auditFixedCaseEvidence(fixedCases, [sample], {
        shadowAudit: changed,
        shadowFormat: "followup-v1",
      }),
      /final choice mismatch/,
    );
  }
});

test("shadow 스키마 오류를 중첩 0건으로 바꾸지 않는다", () => {
  const valid = { schemaVersion: 2, turns: [matchingTurn] };
  const badAudits = [
    { ...valid, schemaVersion: 3 },
    { ...valid, turns: undefined },
    { ...valid, turns: [] },
    { ...valid, turns: [{ ...matchingTurn, runId: "" }] },
    { ...valid, turns: [{ ...matchingTurn, turnNo: undefined }] },
    { ...valid, turns: [{ ...matchingTurn, serverTurnNo: matchingTurn.turnNo }] },
    { ...valid, turns: [{ ...matchingTurn, records: undefined }] },
    { ...valid, turns: [{ ...matchingTurn, records: [] }] },
    { ...valid, turns: [{ ...matchingTurn, records: [{ ...matchingRecord, finalLabel: "" }] }] },
    { ...valid, turns: [{ ...matchingTurn, records: [{ ...matchingRecord, payload: null }] }] },
    { ...valid, turns: [matchingTurn, matchingTurn] },
    { ...valid, turns: [{ ...matchingTurn, records: [matchingRecord, matchingRecord] }] },
  ];
  for (const badAudit of badAudits) {
    assert.throws(
      () => auditFixedCaseEvidence(fixedCases, [sample], { shadowAudit: badAudit }),
      /shadow/,
    );
  }
  assert.throws(
    () => auditFixedCaseEvidence(
      fixedCases,
      [sample],
      {
        shadowAudit: { turns: [{ ...matchingTurn, serverTurnNo: matchingTurn.turnNo }] },
        shadowFormat: "followup-v1",
      },
    ),
    /shadow/,
  );
});

test("원본 보고서가 있으면 발췌본의 최종 선택지와 다음 클릭을 다시 대조한다", () => {
  const changedSource = {
    ...sample.reportExcerpt,
    turns: [
      {
        ...sample.reportExcerpt.turns[0],
        llmChoices: [
          {
            ...sample.reportExcerpt.turns[0].llmChoices[0],
            label: "원본에서 달라진 선택지",
          },
        ],
      },
      sample.reportExcerpt.turns[1],
    ],
  };
  assert.throws(
    () =>
      auditFixedCaseEvidence(
        fixedCases,
        [sample],
        { sourceReports: new Map([[sample.sourceReport, changedSource]]) },
      ),
    /source report mismatch: G01/,
  );
});
