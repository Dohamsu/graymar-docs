/**
 * NPA 시나리오 — chat-rat-king: 쥐왕(빈민가)와 잡담 10턴.
 *
 * CORE NPC 잡담 모드(D_CHAT) 집중 평가 — fact 캐기 X, 인격 발현/연결성/사람다움.
 * 쥐왕 personality: 빈민가 지하 조직 두목, 몰락한 옛 상인, 쉰 목소리 압도적 ~하오 체.
 *
 * 설계: architecture/47_dialogue_quality_audit.md §8.
 */
import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "chat-rat-king",
  name: "쥐왕 잡담 10턴",
  intent:
    "빈민가에서 CORE NPC 쥐왕과의 10턴 잡담 — daily_topics 카테고리 다양성, 몰락한 상인 출신 personality 발현, 압도적이고 느린 ~하오 체 유지를 평가",
  preset: "DESERTER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest", note: "프롤로그 의뢰 수락" },
    { type: "CHOICE", choiceId: "go_slums", note: "HUB → 빈민가 진입" },
    {
      type: "ACTION",
      text: "지하 조직의 두목에게 다가간다",
      note: "쥐왕 첫 만남",
    },
  ],
  turns: [
    {
      input: "안녕하시오. 처음 뵙소.",
      expectMode: "D_CHAT",
      note: "도입 인사",
    },
    {
      input: "이곳 빈민가 분위기는 어떻소?",
      expectMode: "D_CHAT",
      note: "WORK — 영역 화제",
    },
    {
      input: "예전엔 상인이셨다는 이야기 들었소.",
      expectMode: "D_CHAT",
      note: "PERSONAL — 몰락 이야기",
    },
    {
      input: "도시 소식은 어떻게 들으시오?",
      expectMode: "D_CHAT",
      note: "WORK — 정보망",
    },
    {
      input: "윗동네 권력자들을 어찌 보시오?",
      expectMode: "D_CHAT",
      note: "OPINION — 정치적 견해",
    },
    {
      input: "여기 사람들 살아가는 게 걱정되지 않소?",
      expectMode: "D_CHAT",
      note: "WORRY — 인민 공감",
    },
    {
      input: "옛 상인 시절이 그립지 않으시오?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 회고",
    },
    {
      input: "두목 자리는 외롭지 않소?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 고독 공감",
    },
    {
      input: "혹시 가족이나 의지하는 이가 있소?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 사적",
    },
    {
      input: "오늘 좋은 이야기 들었소. 또 뵙겠소.",
      expectMode: "D_CHAT",
      note: "마무리 인사",
    },
  ],
  expectSameNpc: true,
};

export default scenario;
