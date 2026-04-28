/**
 * NPA 시나리오 — chat-edric: 에드릭 베일(시장)과 잡담 10턴.
 *
 * CORE NPC 잡담 모드(D_CHAT) 평가.
 * 에드릭 personality: 신경질적인 회계사, 도박 빚, 숫자 강박, ~이오/~하오 체.
 *
 * 설계: architecture/47.
 */
import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "chat-edric",
  name: "에드릭 베일 잡담 10턴",
  intent:
    "시장에서 CORE NPC 에드릭과의 10턴 잡담 — 회계사·도박꾼 personality 발현, 신경질적 ~이오/~하오 체 유지, 도박 빚의 인간미 evaluation",
  preset: "DESERTER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest", note: "프롤로그 의뢰 수락" },
    { type: "CHOICE", choiceId: "go_market", note: "HUB → 시장 거리 진입" },
    {
      type: "ACTION",
      text: "은장부 상단의 회계사에게 다가간다",
      note: "에드릭 첫 만남 (role 키워드 매칭)",
    },
  ],
  turns: [
    {
      input: "안녕하시오. 시장에 처음 와봤소.",
      expectMode: "D_CHAT",
      note: "도입 인사",
    },
    {
      input: "장부 정리는 보통 얼마나 걸리시오?",
      expectMode: "D_CHAT",
      note: "WORK — 회계 화제",
    },
    {
      input: "어젯밤은 잘 주무셨소?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 잠 안부",
    },
    {
      input: "도박을 즐기신다 들었소.",
      expectMode: "D_CHAT",
      note: "PERSONAL — 도박 (softSpot 트리거)",
    },
    {
      input: "오늘 시장 분위기는 어떻소?",
      expectMode: "D_CHAT",
      note: "GOSSIP",
    },
    {
      input: "회계 일이 외롭다 하셨는데, 어떤 의미요?",
      expectMode: "D_CHAT",
      note: "OPINION — 회상 질문",
    },
    {
      input: "스튜 한 그릇 어떠시오?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 식사 권유",
    },
    {
      input: "빵 굽는 냄새가 나는데, 좋은 빵집이 있소?",
      expectMode: "D_CHAT",
      note: "GOSSIP — 시장 정보",
    },
    {
      input: "숫자 다루는 일이 두려워질 때는 없으시오?",
      expectMode: "D_CHAT",
      note: "WORRY — innerConflict",
    },
    {
      input: "오늘 좋은 이야기 들었소. 또 들르겠소.",
      expectMode: "D_CHAT",
      note: "마무리",
    },
  ],
  expectSameNpc: true,
};

export default scenario;
