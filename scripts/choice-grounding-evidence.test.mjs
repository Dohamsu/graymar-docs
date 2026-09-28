import assert from "node:assert/strict";
import test from "node:test";
import { extractFinalNanoChoiceEvidence } from "./choice-grounding-evidence.mjs";

test("최종 Nano 목록을 기준으로 다음 턴의 실제 선택 ID만 클릭 증거로 인정한다", () => {
  const evidence = extractFinalNanoChoiceEvidence({
    runId: "run-1",
    turns: [
      {
        turn: 5,
        llmStatus: "DONE",
        choiceIds: ["fallback_talk"],
        llmChoices: [
          {
            id: "nano_6_0",
            label: "없는 쪽지를 살핀다",
            action: { type: "CHOICE", payload: { affordance: "INVESTIGATE" } },
          },
          {
            id: "nano_6_1",
            label: "이렌에게 묻는다",
            action: {
              type: "CHOICE",
              payload: { affordance: "TALK", sourceNpcId: "NPC_SS_IREN" },
            },
          },
          {
            id: "go_hub",
            label: "거점으로",
            action: { type: "CHOICE", payload: {} },
          },
        ],
      },
      { turn: 6, input: "AGENT:nano_6_1", llmStatus: "DONE" },
    ],
  });

  assert.deepEqual(evidence, [
    {
      runId: "run-1",
      playtestTurn: 5,
      turnNo: 5,
      choiceId: "nano_6_0",
      label: "없는 쪽지를 살핀다",
      payload: { affordance: "INVESTIGATE" },
      clickStatus: "NOT_CLICKED",
      nextTurnNo: null,
    },
    {
      runId: "run-1",
      playtestTurn: 5,
      turnNo: 5,
      choiceId: "nano_6_1",
      label: "이렌에게 묻는다",
      payload: { affordance: "TALK", sourceNpcId: "NPC_SS_IREN" },
      clickStatus: "CLICKED",
      nextTurnNo: 6,
    },
  ]);
});

test("다음 턴이 없거나 턴 번호가 건너뛰면 클릭을 추정하지 않는다", () => {
  const choice = {
    id: "nano_8_0",
    label: "묻는다",
    action: { type: "CHOICE", payload: { affordance: "TALK" } },
  };
  const evidence = extractFinalNanoChoiceEvidence({
    runId: "run-2",
    turns: [
      { turn: 7, turnNo: 8, llmStatus: "DONE", llmChoices: [choice] },
      { turn: 9, turnNo: 10, input: "AGENT:nano_8_0" },
      { turn: 10, turnNo: 11, llmStatus: "DONE", llmChoices: [choice] },
    ],
  });
  assert.deepEqual(
    evidence.map(({ clickStatus, nextTurnNo }) => ({
      clickStatus,
      nextTurnNo,
    })),
    [
      { clickStatus: "UNOBSERVED", nextTurnNo: null },
      { clickStatus: "UNOBSERVED", nextTurnNo: null },
    ],
  );
});

test("테스터의 preferred·sequence 주석 뒤에도 실제 선택 ID를 복원한다", () => {
  const choice = {
    id: "nano_9_1",
    label: "이렌에게 묻는다",
    action: { type: "CHOICE", payload: { affordance: "TALK" } },
  };
  for (const input of [
    "CHOICE:nano_9_1 (preferred)",
    "CHOICE:nano_9_1 (sequence 1/2)",
  ]) {
    const evidence = extractFinalNanoChoiceEvidence({
      runId: "run-3",
      turns: [
        { turnNo: 9, llmStatus: "DONE", llmChoices: [choice] },
        { turnNo: 10, input },
      ],
    });
    assert.equal(evidence[0].clickStatus, "CLICKED");
    assert.equal(evidence[0].nextTurnNo, 10);
  }
});
