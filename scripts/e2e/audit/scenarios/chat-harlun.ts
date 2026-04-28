/**
 * NPA 시나리오 — chat-harlun: 하를런 보스(항만)와 잡담 10턴.
 *
 * CORE NPC 잡담 모드(D_CHAT) 집중 평가 — fact 캐기 X, 인격 발현/연결성/사람다움.
 * 하를런 personality: 거친 부두 형제단 두목, 복서 출신, 짧은 ~하오 체.
 *
 * 설계: architecture/47_dialogue_quality_audit.md §8.
 */
import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "chat-harlun",
  name: "하를런 보스 잡담 10턴",
  intent:
    "항만에서 CORE NPC 하를런과의 10턴 잡담 — daily_topics 카테고리(WORK/PERSONAL/GOSSIP/OPINION/WORRY) 다양성, 복서 출신 personality 발현, 거친 ~하오 체 유지를 평가",
  preset: "DOCKWORKER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest", note: "프롤로그 의뢰 수락" },
    { type: "CHOICE", choiceId: "go_harbor", note: "HUB → 항만 부두 진입" },
    {
      type: "ACTION",
      text: "부두 형제단의 두목에게 다가간다",
      note: "하를런 첫 만남",
    },
  ],
  turns: [
    {
      input: "안녕하시오. 부두에 처음 와봤소.",
      expectMode: "D_CHAT",
      note: "도입 인사",
    },
    {
      input: "요즘 부두 일은 어떻소?",
      expectMode: "D_CHAT",
      note: "WORK — 일상 화제",
    },
    {
      input: "예전에 복서로 활동하셨다고 들었소.",
      expectMode: "D_CHAT",
      note: "PERSONAL — 과거 이야기",
    },
    {
      input: "북쪽 세금 소식은 들으셨소?",
      expectMode: "D_CHAT",
      note: "GOSSIP — 일반 소문",
    },
    {
      input: "형제단의 앞날을 어떻게 보시오?",
      expectMode: "D_CHAT",
      note: "OPINION — 견해",
    },
    {
      input: "젊은 일꾼이 줄어든다던데 걱정되시오?",
      expectMode: "D_CHAT",
      note: "WORRY — 걱정",
    },
    {
      input: "가장 기억에 남는 싸움이 있소?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 인생 회고",
    },
    {
      input: "주먹 굳은 손은 지금도 가끔 답답하지 않소?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 신체적 고통 공감",
    },
    {
      input: "동료들과 술 한잔 자주 하시오?",
      expectMode: "D_CHAT",
      note: "PERSONAL — 일상 사적",
    },
    {
      input: "오늘 좋은 이야기 들었소. 또 들르겠소.",
      expectMode: "D_CHAT",
      note: "마무리 인사",
    },
  ],
  expectSameNpc: true,
};

export default scenario;
