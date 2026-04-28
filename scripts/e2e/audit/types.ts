/**
 * NPA (Narrative Pipeline Audit) — 공유 타입.
 * 설계: architecture/47_dialogue_quality_audit.md §3.
 */

export type AuditMode = 'A_FACT' | 'B_HANDOFF' | 'C_DEFAULT' | 'D_CHAT' | 'NONE';
export type AuditPreset =
  | 'DESERTER'
  | 'SMUGGLER'
  | 'HERBALIST'
  | 'FALLEN_NOBLE'
  | 'GLADIATOR'
  | 'DOCKWORKER';

export type SetupStep =
  | { type: 'CHOICE'; choiceId: string; note?: string }
  | { type: 'ACTION'; text: string; note?: string };

export interface AuditTurn {
  /** 사용자 입력 (ACTION 텍스트). type==='CHOICE'면 무시되고 choiceId 사용 */
  input: string;
  /** 입력 종류 (기본 ACTION). HUB 진입 시점 등에서 'CHOICE' 사용 */
  type?: 'ACTION' | 'CHOICE';
  /** type==='CHOICE'일 때 choice id (예: 'go_market', 'go_hub') */
  choiceId?: string;
  /** 의도된 모드 (자동 검증 비교용) */
  expectMode?: Exclude<AuditMode, 'NONE'>;
  /** 의도된 NPC (자동 검증) */
  expectNpcId?: string;
  /** 사람용 메모 */
  note?: string;
}

export interface AuditScenario {
  id: string;
  name: string;
  intent: string;
  preset: AuditPreset;
  gender: 'male' | 'female';
  /** 평가 외 초기 진입 입력 */
  setup: SetupStep[];
  /** 평가 대상 턴 시퀀스 */
  turns: AuditTurn[];
  /** 같은 NPC 연속성 기대 */
  expectSameNpc?: boolean;
  /** 시나리오별 화이트리스트 (회피 어휘 false positive 회피 등, optional) */
  customWhitelist?: string[];
}

export interface PromptBlock {
  name: string;
  preview: string;
  tokens: number;
}

export interface NpcUtterance {
  /** 따옴표 안 대사 본문 */
  text: string;
  /** @[이름|...] 마커의 이름 부분 */
  npcName: string;
  /** 마커의 이미지 URL (optional) */
  npcImage?: string;
}

export interface DialoguePair {
  turn: number;
  /** 사용자 입력 원문 */
  userInput: string;
  /** 입력 분류 (ACTION / CHOICE / SETUP) */
  inputKind: 'ACTION' | 'CHOICE' | 'SETUP';
  parsedActionType: string | null;

  /** 서버가 결정한 화자 */
  speakerNpcId: string | null;
  speakerDisplayName: string | null;

  /** 마커 추출 NPC 발화 */
  npcUtterances: NpcUtterance[];
  /** 대사 제외 본문 */
  narration: string;
  /** 원본 LLM 출력 (마커 포함) */
  rawOutput: string;

  /** Pipeline Trace — 입력 프롬프트 */
  prompt: {
    totalTokens: number;
    blocks: PromptBlock[];
  };

  /** 모드 검출 (프롬프트 블록 헤더 기반) */
  detectedMode: AuditMode;

  resolveOutcome: 'SUCCESS' | 'PARTIAL' | 'FAIL' | null;
  eventId: string | null;
  llmLatencyMs: number;
  /** 평가 대상 외 (setup) */
  isSetup?: boolean;
  /** 디버그용 — actionContext 일부 (primaryNpcId / parsedType / turnMode 등) */
  actionContextDebug?: Record<string, unknown> | null;
}

// ──────────────────────────────────────────────────────────────
// Score 모듈 — Dialogue Quality
// ──────────────────────────────────────────────────────────────
export interface ContinuityScore {
  /** 최종 점수 0~5 */
  score: number;
  keywordCarryOverRate: number;
  pronounConsistency: number;
  toneConsistency: number;
  userResponseRate: number;
  notes: string[];
}

export interface TopicFreedomScore {
  score: number;
  modeBalance: number;
  topicVariety: number;
  noFactRepeat: number;
  /** A/B/C/D 비율 (%) */
  modeDistribution: Record<Exclude<AuditMode, 'NONE'>, number>;
  /** topicId/factId → 등장 턴 */
  factOccurrences: Record<string, number[]>;
  notes: string[];
}

export interface HumanityScore {
  score: number;
  avoidWordRate: number;
  imperativeRate: number;
  npcSignatureRate: number;
  metaphorUsageRate: number;
  repetitionRate: number;
  notes: string[];
}

// architecture/51 — NPC Distinctness 점수
export interface NpcDistinctnessScore {
  /** 0~5 */
  score: number;
  /** 화자 NPC별 distinct 시그니처 등장률 */
  perNpcDistinctness: Record<string, number>;
  /** 화자 NPC별 시그니처 풀 (signature + traits + roleKeywords) 단어 수 */
  perNpcSignaturePoolSize: Record<string, number>;
  notes: string[];
}

// architecture/51 — 톤 일치도 점수
export type ToneCategory = 'casual' | 'serious' | 'unknown';

export interface ToneMatchScore {
  /** 0~5 */
  score: number;
  /** 일치 턴 수 / 총 턴 수 */
  matchRate: number;
  /** 사용자 톤 분포 */
  userToneDistribution: Record<ToneCategory, number>;
  /** NPC 응답 톤 분포 */
  npcToneDistribution: Record<ToneCategory, number>;
  /** 턴별 비교 — 디버깅 */
  perTurn: Array<{
    turn: number;
    userTone: ToneCategory;
    npcTone: ToneCategory;
    matched: boolean;
  }>;
  notes: string[];
}

export interface DialogueQuality {
  continuity: ContinuityScore;
  topicFreedom: TopicFreedomScore;
  humanity: HumanityScore;
  /** architecture/51 — 신규 메트릭 */
  npcDistinctness: NpcDistinctnessScore;
  toneMatch: ToneMatchScore;
  /** 종합 5점 만점 = (5 score 평균) */
  overall: number;
}

// ──────────────────────────────────────────────────────────────
// 자동 검증
// ──────────────────────────────────────────────────────────────
export type FindingSeverity = 'ERROR' | 'WARNING' | 'INFO';

export interface AuditFinding {
  turn?: number;
  rule: string;
  message: string;
  severity: FindingSeverity;
  /** 룰별 부가 데이터 */
  data?: Record<string, unknown>;
}

// ──────────────────────────────────────────────────────────────
// 리포트
// ──────────────────────────────────────────────────────────────
export interface AuditReport {
  scenario: AuditScenario;
  startedAt: string;
  totalElapsedMs: number;
  serverVersion: string;
  runId: string;

  pairs: DialoguePair[];

  dialogueQuality: DialogueQuality;

  findings: {
    errors: AuditFinding[];
    warnings: AuditFinding[];
    infos: AuditFinding[];
  };

  /** 사람용 발화 흐름 */
  flow: Array<{ turn: number; speaker: string; text: string }>;
}
