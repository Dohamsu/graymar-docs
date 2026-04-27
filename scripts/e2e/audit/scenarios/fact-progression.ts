/**
 * NPA 시나리오 — fact-progression: 같은 NPC와 여러 fact 점진 공개.
 *
 * 미렐라(NPC_MIRELA)의 knownFacts(LEDGER_EXISTS, WAGE_FRAUD_PATTERN)를 두 개 이상 탐색해
 * fact가 자연스럽게 누적·발전하는지 평가. 시나리오는 fact 모드 A 다수를 노리되,
 * setup 단계에서 첫 fact가 자동 reveal될 수 있음을 인지하고 후반은 잡담↔fact 전환 측정.
 *
 * 설계: architecture/47_dialogue_quality_audit.md §8.
 */
import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "fact-progression",
  name: "미렐라 fact 점진 공개 흐름",
  intent:
    "미렐라와의 10턴 연속 대화에서 LEDGER → WAGE_FRAUD 등 여러 fact를 점진 공개하며 동일 fact 반복 / 자연 흐름 / 톤 유지를 평가",
  preset: "DESERTER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest", note: "프롤로그 의뢰 수락" },
    { type: "CHOICE", choiceId: "go_market", note: "HUB → 시장 거리 진입" },
    { type: "ACTION", text: "약초 노점에 다가간다", note: "미렐라 첫 만남 (첫 fact 자동 reveal 가능)" },
  ],
  turns: [
    { input: "안녕하시오, 약초나 좀 보러 왔소.", expectMode: "D_CHAT", note: "도입 잡담" },
    { input: "요즘 시장에 흉흉한 소문 있소?", expectMode: "D_CHAT", note: "넓은 잡담 — 자연 도입" },
    {
      input: "장부에 무슨 일이 있는 모양이오?",
      expectMode: "A_FACT",
      expectNpcId: "NPC_MIRELA",
      note: "LEDGER 첫 명시 — 자동 reveal됐다면 재언급 가능",
    },
    {
      input: "임금 쪽으로 이상한 일은 없소?",
      expectMode: "A_FACT",
      expectNpcId: "NPC_MIRELA",
      note: "WAGE_FRAUD — 미렐라 두 번째 fact",
    },
    {
      input: "약초 사업은 그래도 잘 되시오?",
      expectMode: "D_CHAT",
      note: "잡담 복귀 — 톤 전환 측정",
    },
    {
      input: "그 장부, 누가 가져갔는지 짐작 가는 사람이 있소?",
      expectMode: "A_FACT",
      note: "LEDGER 후속 — 같은 fact 재언급 시 자연스러움 평가",
    },
    {
      input: "당신 자식들은 잘 지내오?",
      expectMode: "D_CHAT",
      note: "사적 잡담 (인격 발현)",
    },
    {
      input: "장부 사건, 부두 쪽 사람들 의심하시오?",
      expectMode: "B_HANDOFF",
      note: "부두 쪽은 미렐라 모름 → 인계",
    },
    {
      input: "임금 횡령에 길드가 관련됐을 수 있소?",
      expectMode: "A_FACT",
      note: "WAGE_FRAUD 심화 — 같은 fact 재언급",
    },
    {
      input: "오늘 정말 도움이 되었소.",
      expectMode: "D_CHAT",
      note: "마무리",
    },
  ],
  expectSameNpc: true,
};

export default scenario;
