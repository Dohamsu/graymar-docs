/**
 * NPA Pipeline Trace — 3 레이어 캡처:
 *   1. 입력 프롬프트 블록 분리 (includeDebug API)
 *   2. LLM 출력 파싱 (@마커 / 대사 / 서술)
 *   3. 후처리 (serverResult.ui.speakingNpc / actionContext)
 *
 * 설계: architecture/47_dialogue_quality_audit.md §5.
 */

import type {
  AuditMode,
  DialoguePair,
  NpcUtterance,
  PromptBlock,
} from "./types.js";

// ──────────────────────────────────────────────────────────────
// 1. 프롬프트 블록 분리
// ──────────────────────────────────────────────────────────────
/** 프롬프트 안에서 분리해 내고 싶은 블록 헤더 패턴.
 *  실제 prompt-builder.service.ts의 헤더 문자열과 일치. */
const BLOCK_PATTERNS: Array<{ name: string; re: RegExp }> = [
  { name: "상황 요약", re: /\[상황 요약\][\s\S]*?(?=\n\[|$)/ },
  { name: "이번 턴 사건", re: /\[이번 턴 사건\][\s\S]*?(?=\n\[|$)/ },
  { name: "이번 턴 판정", re: /\[이번 턴 판정[^\]]*\][\s\S]*?(?=\n\[|$)/ },
  { name: "이번 턴 행동", re: /(?:⚠️\s*)?\[이번 턴 행동\][\s\S]*?(?=\n\[|$)/ },
  { name: "이번 턴 획득 아이템", re: /\[이번 턴 획득 아이템\][\s\S]*?(?=\n\[|$)/ },
  { name: "현재 시간대", re: /\[현재 시간대\][\s\S]*?(?=\n\[|$)/ },
  { name: "이번 턴 감각 초점", re: /\[이번 턴 감각 초점\][\s\S]*?(?=\n\[|$)/ },
  { name: "이번 턴 플레이어 지목 대상", re: /\[이번 턴 플레이어 지목 대상\][\s\S]*?(?=\n\[|$)/ },
  // ⭐ 모드 4종 (architecture/46)
  { name: "fact 공개 (A)", re: /\[이번 턴 NPC가 공개할 정보\][\s\S]*?(?=\n\[|$)/ },
  { name: "인계 가이드 (B)", re: /\[NPC 모름 — 인계 가이드\][\s\S]*?(?=\n\[|$)/ },
  { name: "default 텍스트 (C)", re: /\[일반 정보 — 도시 분위기\][\s\S]*?(?=\n\[|$)/ },
  { name: "NPC 일상 화제 (D)", re: /\[NPC 일상 화제[\s\S]*?(?=\n\[|$)/ },
  { name: "NPC 정보", re: /\[NPC 정보\][\s\S]*?(?=\n\[|$)/ },
  { name: "NPC 등장", re: /\[NPC 등장\][\s\S]*?(?=\n\[|$)/ },
  { name: "NPC 관계", re: /\[NPC 관계\][\s\S]*?(?=\n\[|$)/ },
  { name: "활성 단서", re: /\[활성 단서\][\s\S]*?(?=\n\[|$)/ },
  { name: "장소 분위기 힌트", re: /\[장소 분위기 힌트\][\s\S]*?(?=\n\[|$)/ },
  { name: "단서 방향", re: /\[단서 방향\][\s\S]*?(?=\n\[|$)/ },
  { name: "이번 턴 NPC 말투", re: /\[이번 턴 NPC 말투\][\s\S]*?(?=\n\[|$)/ },
  { name: "최근 대화 주제", re: /\[최근 대화 주제\][\s\S]*?(?=\n\[|$)/ },
];

/** 한국어/영문 혼합 텍스트의 토큰 수를 어림 계산 (Gemini ≈ 1 token / 4 chars 기준). */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / 4);
}

/** llmPrompt(jsonb): [{role, content}] 배열에서 user content를 합쳐 반환. */
export function extractPromptText(
  llmPrompt: unknown,
): { userText: string; systemText: string; totalText: string } {
  if (!Array.isArray(llmPrompt)) {
    return { userText: "", systemText: "", totalText: "" };
  }
  const messages = llmPrompt as Array<{ role?: string; content?: unknown }>;
  const userParts: string[] = [];
  const systemParts: string[] = [];
  for (const m of messages) {
    const content = typeof m?.content === "string" ? m.content : "";
    if (m?.role === "user") userParts.push(content);
    else if (m?.role === "system") systemParts.push(content);
  }
  const userText = userParts.join("\n");
  const systemText = systemParts.join("\n");
  return { userText, systemText, totalText: `${systemText}\n${userText}` };
}

export function extractPromptBlocks(userText: string): PromptBlock[] {
  if (!userText) return [];
  const blocks: PromptBlock[] = [];
  for (const { name, re } of BLOCK_PATTERNS) {
    const m = userText.match(re);
    if (m && m[0]) {
      const body = m[0].trim();
      blocks.push({
        name,
        preview: body.slice(0, 220),
        tokens: estimateTokens(body),
      });
    }
  }
  return blocks;
}

/** 프롬프트 블록 헤더 → 모드 검출.
 *  우선순위: A > B > C > D (실제 prompt-builder의 if-else와 같음). */
export function detectMode(blocks: PromptBlock[]): AuditMode {
  const has = (name: string) => blocks.some((b) => b.name === name);
  if (has("fact 공개 (A)")) return "A_FACT";
  if (has("인계 가이드 (B)")) return "B_HANDOFF";
  if (has("default 텍스트 (C)")) return "C_DEFAULT";
  if (has("NPC 일상 화제 (D)")) return "D_CHAT";
  return "NONE";
}

// ──────────────────────────────────────────────────────────────
// 2. LLM 출력 파싱 — @[NPC|URL] "대사"
// ──────────────────────────────────────────────────────────────

/** @[이름|URL] "대사" 또는 @[이름] "대사" 두 형태 지원.
 *  대사는 한쌍의 큰따옴표 또는 한국어 곱은따옴표("…"). */
const MARKER_RE =
  /@\[([^\]|]+)(?:\|([^\]]+))?\]\s*[“"]([^“”"]+)[”"]/g;

export function parseDialogueMarkers(rawOutput: string): {
  utterances: NpcUtterance[];
  narration: string;
} {
  const utterances: NpcUtterance[] = [];
  let narration = rawOutput;
  if (!rawOutput) return { utterances, narration: "" };

  // 1) 마커 추출
  const matches = Array.from(rawOutput.matchAll(MARKER_RE));
  for (const m of matches) {
    const npcName = (m[1] ?? "").trim();
    const npcImage = m[2] ? m[2].trim() : undefined;
    const text = (m[3] ?? "").trim();
    if (npcName && text) {
      utterances.push({ npcName, npcImage, text });
    }
  }

  // 2) 마커 부분을 narration에서 제거 → 서술만 남김
  narration = rawOutput.replace(MARKER_RE, "").replace(/\n{3,}/g, "\n\n").trim();

  return { utterances, narration };
}

// ──────────────────────────────────────────────────────────────
// 3. 후처리 — serverResult.ui
// ──────────────────────────────────────────────────────────────

export interface ServerUiSnapshot {
  speakerNpcId: string | null;
  speakerDisplayName: string | null;
  parsedActionType: string | null;
  eventId: string | null;
  resolveOutcome: "SUCCESS" | "PARTIAL" | "FAIL" | null;
  actionContextDebug: Record<string, unknown> | null;
}

export function extractUi(serverResult: unknown): ServerUiSnapshot {
  const ui = (serverResult as Record<string, any> | null)?.ui ?? {};
  const speakingNpc = ui.speakingNpc ?? null;
  const ac = ui.actionContext ?? {};
  return {
    speakerNpcId: speakingNpc?.npcId ?? null,
    speakerDisplayName: speakingNpc?.displayName ?? null,
    parsedActionType: ac?.parsedType ?? null,
    eventId: ac?.eventId ?? null,
    resolveOutcome: ui?.resolveOutcome ?? null,
    actionContextDebug: ac && Object.keys(ac).length > 0 ? ac : null,
  };
}

// ──────────────────────────────────────────────────────────────
// 통합: 1턴 trace → DialoguePair 부분 채우기
// ──────────────────────────────────────────────────────────────

export interface RawTurnSources {
  turn: number;
  userInput: string;
  inputKind: "ACTION" | "CHOICE" | "SETUP";
  serverResult: unknown;
  llmOutput: string;
  llmLatencyMs: number;
  /** debug.llmPrompt (jsonb 배열) */
  llmPrompt: unknown;
  isSetup?: boolean;
}

export function buildDialoguePair(src: RawTurnSources): DialoguePair {
  const { userText } = extractPromptText(src.llmPrompt);
  const blocks = extractPromptBlocks(userText);
  const totalTokens = estimateTokens(userText);
  const mode = detectMode(blocks);
  const { utterances, narration } = parseDialogueMarkers(src.llmOutput);
  const ui = extractUi(src.serverResult);

  return {
    turn: src.turn,
    userInput: src.userInput,
    inputKind: src.inputKind,
    parsedActionType: ui.parsedActionType,
    speakerNpcId: ui.speakerNpcId,
    speakerDisplayName: ui.speakerDisplayName,
    npcUtterances: utterances,
    narration,
    rawOutput: src.llmOutput,
    prompt: { totalTokens, blocks },
    detectedMode: mode,
    resolveOutcome: ui.resolveOutcome,
    eventId: ui.eventId,
    llmLatencyMs: src.llmLatencyMs,
    isSetup: src.isSetup,
    actionContextDebug: ui.actionContextDebug,
  };
}
