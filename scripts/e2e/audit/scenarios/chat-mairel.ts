/**
 * NPA 시나리오 — chat-mairel: 마이렐 단 경(경비대)과 잡담 10턴.
 *
 * CORE NPC 잡담 모드(D_CHAT) 평가.
 * 마이렐 personality: 권위적 군인, 야간 책임자, 부하 복지 집착, '그대' 호칭, ~하오/~시오 체.
 *
 * 설계: architecture/47.
 */
import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "chat-mairel",
  name: "마이렐 단 경 잡담 10턴",
  intent:
    "경비대에서 CORE NPC 마이렐과의 10턴 잡담 — 군인 + 부하 복지 집착 personality, 권위적 ~하오/~시오 체 유지, '그대' 호칭 일관성 평가",
  preset: "DESERTER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest", note: "프롤로그 의뢰 수락" },
    { type: "CHOICE", choiceId: "go_guard", note: "HUB → 경비대 지구 진입" },
    {
      type: "ACTION",
      text: "야간 경비 책임자에게 다가간다",
      note: "마이렐 첫 만남 (role 키워드 매칭)",
    },
  ],
  turns: [
    {
      input: "안녕하시오, 단 경. 처음 뵙소.",
      expectMode: "D_CHAT",
      note: "도입 인사 (호칭)",
    },
    {
      input: "야간 경비는 어떻소?",
      expectMode: "D_CHAT",
      note: "WORK — 핵심 화제",
    },
    {
      input: "북부 전선 참전하셨다 들었소.",
      expectMode: "D_CHAT",
      note: "PERSONAL — 회고",
    },
    {
      input: "단 가문의 명예에 대해 어떻게 생각하시오?",
      expectMode: "D_CHAT",
      note: "OPINION — innerConflict",
    },
    {
      input: "외지인이 늘어 골치라 들었소.",
      expectMode: "D_CHAT",
      note: "GOSSIP — 도시 화제",
    },
    {
      input: "병영 식사 사정은 좀 나아지셨소?",
      expectMode: "D_CHAT",
      note: "WORRY — softSpot 트리거",
    },
    {
      input: "부하들 봉급은 무사히 나오시오?",
      expectMode: "D_CHAT",
      note: "WORRY — 부하 복지",
    },
    {
      input: "전쟁 뒤 도시 생활에 익숙해지셨소?",
      expectMode: "D_CHAT",
      note: "PERSONAL",
    },
    {
      input: "야근이 길어질 때는 어떻게 견디시오?",
      expectMode: "D_CHAT",
      note: "PERSONAL",
    },
    {
      input: "오늘 좋은 이야기 들었소. 단 경, 또 들르겠소.",
      expectMode: "D_CHAT",
      note: "마무리",
    },
  ],
  expectSameNpc: true,
};

export default scenario;
