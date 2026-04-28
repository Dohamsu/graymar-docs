/**
 * NPA 시나리오 — chat-ronen: 로넨(항만)과 잡담 10턴.
 *
 * CORE NPC 잡담 모드(D_CHAT) 평가.
 * 로넨 personality: 초조한 서기관, 의뢰인, 공손한 HAPSYO 어체, 절박할 때 더듬음.
 * accept_quest의 의뢰인이라 신뢰 관계가 이미 형성된 상태에서의 잡담 평가.
 *
 * 설계: architecture/47.
 */
import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "chat-ronen",
  name: "로넨 잡담 10턴",
  intent:
    "항만에서 의뢰인 CORE NPC 로넨과의 10턴 잡담 — 초조한 서기관 personality 발현, HAPSYO(~소이다/~습니다) 어체 유지, 노모·고향 그리움 등 인간미 평가",
  preset: "DESERTER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest", note: "프롤로그 의뢰 수락" },
    { type: "CHOICE", choiceId: "go_harbor", note: "HUB → 항만 부두 진입" },
    {
      type: "ACTION",
      text: "초조한 서기관에게 다가간다",
      note: "로넨 만남 (role 키워드 매칭)",
    },
  ],
  turns: [
    {
      input: "안녕하시오, 로넨. 또 만났구려.",
      expectMode: "D_CHAT",
      note: "도입 인사 (재회)",
    },
    {
      input: "요즘 잘 지내시오?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 안부",
    },
    {
      input: "고향에 노모가 계시다 들었소.",
      expectMode: "D_CHAT",
      note: "PERSONAL — softSpot",
    },
    {
      input: "서기관 일은 얼마나 하셨소?",
      expectMode: "D_CHAT",
      note: "WORK",
    },
    {
      input: "이 도시에서 오래 지내셨소?",
      expectMode: "D_CHAT",
      note: "PERSONAL",
    },
    {
      input: "도시 사람들에 대해 어떻게 보시오?",
      expectMode: "D_CHAT",
      note: "OPINION",
    },
    {
      input: "잠은 잘 주무시오?",
      expectMode: "D_CHAT",
      note: "WORRY — softSpot",
    },
    {
      input: "이 일이 끝나면 무엇을 하시고 싶소?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 미래 희망",
    },
    {
      input: "고향 노모께 편지는 보내시오?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 가족",
    },
    {
      input: "오늘 잠시 같이 이야기해 좋았소. 또 들르겠소.",
      expectMode: "D_CHAT",
      note: "마무리",
    },
  ],
  expectSameNpc: true,
};

export default scenario;
