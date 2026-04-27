/**
 * NPA 시나리오 — 미렐라 장부 인계 흐름.
 * 같은 NPC(미렐라)와 잡담↔fact↔인계 모드 전환 평가.
 * 설계: architecture/47_dialogue_quality_audit.md §8.1.
 */

import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "dialog-handoff",
  name: "미렐라 장부 인계 흐름",
  intent:
    "같은 NPC(미렐라)와의 8턴 연속 대화에서 잡담→fact→인계→fact 모드 전환 시 자연스러움 / 사람다움 / 연결성 평가",
  preset: "DESERTER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest", note: "프롤로그 의뢰 수락" },
    { type: "CHOICE", choiceId: "go_market", note: "HUB → 시장 거리 진입" },
    { type: "ACTION", text: "약초 노점에 다가간다", note: "미렐라 첫 만남" },
  ],
  turns: [
    { input: "오늘 시장 분위기 어떻소?", expectMode: "D_CHAT", note: "잡담 시작" },
    {
      input: "사라진 장부에 대해 들었소?",
      expectMode: "A_FACT",
      expectNpcId: "NPC_MIRELA",
      note: "장부 키워드 → fact 매칭",
    },
    {
      input: "동쪽 부두 일은?",
      expectMode: "B_HANDOFF",
      note: "미렐라가 모르는 fact → 인계 가이드",
    },
    { input: "임금 문제는?", expectMode: "A_FACT", note: "다른 fact" },
    { input: "당신 가족이 있소?", expectMode: "D_CHAT", note: "인격 질문 — 잡담" },
    { input: "약초는 어떻게 키우시오?", expectMode: "D_CHAT", note: "전문 잡담" },
    {
      input: "밀수에 대해 들은 게 있소?",
      expectMode: "B_HANDOFF",
      note: "다른 NPC 영역 → 인계",
    },
    { input: "오늘 정말 고맙소.", expectMode: "D_CHAT", note: "마무리 인사" },
  ],
  expectSameNpc: true,
};

export default scenario;
