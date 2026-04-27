/**
 * NPA 시나리오 — npc-continuity: 잡담↔fact↔이동↔복귀 흐름.
 *
 * 미렐라와 첫 만남 → 잡담 → fact 질문 → 잡담 → "다른 곳 다녀오겠소" 후 HUB 복귀 →
 * 다시 시장 → 미렐라 재방문. 떠났다가 돌아온 NPC가 이전 대화 맥락을 잇는지,
 * 재회 인식("또 오셨군") 같은 자연 연결성이 나오는지 평가.
 *
 * 설계: architecture/47_dialogue_quality_audit.md §8.
 */
import type { AuditScenario } from "../types.js";

export const scenario: AuditScenario = {
  id: "npc-continuity",
  name: "미렐라 떠남↔복귀 연속성",
  intent:
    "같은 NPC와 잡담→fact→이탈→복귀 시 이전 대화 맥락 인식 / 재회 자연성 / 호칭·어조 유지를 평가",
  preset: "DESERTER",
  gender: "male",
  setup: [
    { type: "CHOICE", choiceId: "accept_quest" },
    { type: "CHOICE", choiceId: "go_market" },
    { type: "ACTION", text: "약초 노점에 다가간다", note: "미렐라 첫 만남" },
  ],
  turns: [
    { input: "안녕하시오. 시장 분위기 좀 보러 왔소.", expectMode: "D_CHAT", note: "도입" },
    { input: "약초 시세는 어떻소?", expectMode: "D_CHAT", note: "잡담 — 미렐라 전문 영역" },
    {
      input: "사라진 장부에 대해 들은 게 있소?",
      expectMode: "A_FACT",
      expectNpcId: "NPC_MIRELA",
      note: "fact 질문",
    },
    {
      input: "다른 곳을 좀 더 둘러봐야겠소. 또 오겠소.",
      expectMode: "D_CHAT",
      note: "이탈 인사 — NPC가 자연스럽게 작별 응답하는지",
    },
    {
      input: "다른 장소로 이동한다",
      note: "MOVE_LOCATION — HUB 자동 복귀",
    },
    {
      input: "(go_market)",
      type: "CHOICE",
      choiceId: "go_market",
      note: "HUB → 시장 재진입",
    },
    {
      input: "약초 노점으로 다시 간다",
      expectMode: "D_CHAT",
      note: "미렐라 재방문 — '또 오셨군' 류 인식 기대",
    },
    {
      input: "아까 장부 이야기, 더 생각해 보셨소?",
      expectMode: "A_FACT",
      note: "이전 대화 명시적 참조 — Continuity 핵심 측정",
    },
    {
      input: "그래도 시장에서 약초만 팔며 지내시는 게 안전하시오?",
      expectMode: "D_CHAT",
      note: "걱정·잡담 — 인격 발현",
    },
    {
      input: "오늘 정말 도움이 되었소. 또 들르겠소.",
      expectMode: "D_CHAT",
      note: "마무리 (다음 만남 예고)",
    },
  ],
  expectSameNpc: false,
};

export default scenario;
