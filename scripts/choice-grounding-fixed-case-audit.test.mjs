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
  const result = auditFixedCaseEvidence(fixedCases, [sample], shadow);
  assert.equal(result.sameSurfaceShadow, 0);
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
        undefined,
        new Map([[sample.sourceReport, changedSource]]),
      ),
    /source report mismatch: G01/,
  );
});
