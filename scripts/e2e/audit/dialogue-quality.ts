/**
 * NPA ⭐ 1순위 — Dialogue Quality 측정.
 *
 * 3 score (각 0~5점):
 *   1. Continuity   — 직전 발화/사용자 입력을 참조/기억하는가
 *   2. TopicFreedom — fact/quest 강제 없이 다양한 화제 가능한가
 *   3. Humanity     — 기계가 아닌 인격체로 말하는가
 *
 * 설계: architecture/47_dialogue_quality_audit.md §4.
 */

import * as fs from "node:fs";
import * as path from "node:path";

import type {
  AuditMode,
  ContinuityScore,
  DialoguePair,
  DialogueQuality,
  HumanityScore,
  NpcDistinctnessScore,
  ToneCategory,
  ToneMatchScore,
  TopicFreedomScore,
} from "./types.js";

// ──────────────────────────────────────────────────────────────
// 콘텐츠 — NPC personality 키워드 추출 (signature + traits)
// ──────────────────────────────────────────────────────────────
const CONTENT_ROOT = path.resolve(
  __dirname,
  "..",
  "..",
  "..",
  "content",
  "graymar_v1",
);

interface NpcContentSnapshot {
  npcId: string;
  name: string;
  /** architecture/55 — utterance.npcName으로 NPC 찾기 위한 매칭 정보 */
  unknownAlias: string | null;
  aliases: string[];
  signatureKeywords: Set<string>;
  /** architecture/51 — distinct 시그니처 풀 (signature + traits + roleKeywords + alias) */
  distinctPool: Set<string>;
  speechRegister: "HAOCHE" | "HAEYO" | "BANMAL" | "HAPSYO" | "HAECHE";
  /** architecture/51 §A — NPC baseline tone (personality에서 추론). 사용자 casual 입력에
   *  NPC가 baseline보다 *더* 무겁게 응답하면 mismatch로 판정. dark NPC가 dark로 답하는
   *  건 자연스러우니 mismatch 아님. */
  baselineTone: "dark" | "warm" | "cold" | "neutral";
}

let _npcCache: Map<string, NpcContentSnapshot> | null = null;

function loadNpcs(): Map<string, NpcContentSnapshot> {
  if (_npcCache) return _npcCache;
  const npcsPath = path.join(CONTENT_ROOT, "npcs.json");
  const raw = JSON.parse(fs.readFileSync(npcsPath, "utf-8")) as Array<{
    npcId: string;
    name: string;
    unknownAlias?: string;
    aliases?: string[];
    roleKeywords?: string[];
    personality?: {
      signature?: string[];
      traits?: string[];
      speechStyle?: string;
      speechRegister?: NpcContentSnapshot["speechRegister"];
    };
  }>;
  const map = new Map<string, NpcContentSnapshot>();
  for (const n of raw) {
    const sigParts = [
      ...(n.personality?.signature ?? []),
      ...(n.personality?.traits ?? []),
    ];
    const keywords = new Set<string>();
    for (const s of sigParts) {
      for (const kw of extractKoreanNouns(s)) keywords.add(kw);
    }
    // architecture/51 — distinct pool: signature + traits + roleKeywords + alias 단어들
    const distinctPool = new Set<string>(keywords);
    for (const k of n.roleKeywords ?? []) {
      if (k.length >= 2) distinctPool.add(k);
    }
    if (n.unknownAlias) {
      for (const word of n.unknownAlias.split(/\s+/)) {
        if (word.length >= 2) distinctPool.add(word);
      }
    }
    map.set(n.npcId, {
      npcId: n.npcId,
      name: n.name,
      unknownAlias: n.unknownAlias ?? null,
      aliases: n.aliases ?? [],
      signatureKeywords: keywords,
      distinctPool,
      speechRegister: n.personality?.speechRegister ?? "HAOCHE",
      baselineTone: inferBaselineTone(n.personality?.speechStyle, sigParts),
    });
  }
  _npcCache = map;
  return map;
}

/**
 * architecture/55 — utterance.npcName으로 NPC 찾기.
 * NpcDialogueMarkerService가 마커에 넣어주는 이름은 NPC의 name / unknownAlias /
 * aliases 중 하나. 정확 매칭 우선, fallback 없음 (가짜 NPC면 null).
 */
function findNpcByDisplayName(
  displayName: string,
  npcs: Map<string, NpcContentSnapshot>,
): NpcContentSnapshot | null {
  if (!displayName) return null;
  const trimmed = displayName.trim();
  // 1. name 정확 매칭
  for (const npc of npcs.values()) {
    if (npc.name === trimmed) return npc;
  }
  // 2. unknownAlias 정확 매칭
  for (const npc of npcs.values()) {
    if (npc.unknownAlias === trimmed) return npc;
  }
  // 3. aliases 매칭
  for (const npc of npcs.values()) {
    if (npc.aliases.includes(trimmed)) return npc;
  }
  return null;
}

/** speechStyle + signature/traits에서 NPC baseline tone 추론. */
function inferBaselineTone(
  speechStyle: string | undefined,
  sigParts: string[],
): "dark" | "warm" | "cold" | "neutral" {
  const text = ((speechStyle ?? "") + " " + sigParts.join(" ")).toLowerCase();
  // dark: 거친/위협/쉰/차가운/어둠
  if (/험한|거친|위협|쉰\s?목소리|압도적|어둠|편집증|위태|독|골목|빈민가|두려|차갑/.test(text)) {
    return "dark";
  }
  // warm: 친근/할미/공손/따뜻
  if (/친근|할미|공손|조심스러운|따뜻|다정|온화|상냥|어머니|약초/.test(text)) {
    return "warm";
  }
  // cold: 신경질/계산/정밀/우아/빈틈없는
  if (/신경질|정밀|우아|빈틈없|냉정|계산|차분|딱딱|단호|권위적|군인/.test(text)) {
    return "cold";
  }
  return "neutral";
}

// ──────────────────────────────────────────────────────────────
// 텍스트 유틸
// ──────────────────────────────────────────────────────────────
function extractKoreanNouns(text: string): string[] {
  if (!text) return [];
  const tokens = text.match(/[가-힣]{2,}/g) ?? [];
  const STOP = new Set([
    "이번",
    "그것",
    "이것",
    "저것",
    "지금",
    "오늘",
    "어제",
    "내일",
    "그대",
    "자네",
    "그는",
    "그녀",
    "당신",
    "이야기",
    "말이야",
    "말씀",
  ]);
  return tokens.filter((t) => t.length >= 2 && !STOP.has(t));
}

function utterancesText(p: DialoguePair): string {
  return p.npcUtterances.map((u) => u.text).join(" ");
}

function pairText(p: DialoguePair): string {
  return `${p.narration} ${utterancesText(p)}`.trim();
}

// ──────────────────────────────────────────────────────────────
// 1. Continuity
// ──────────────────────────────────────────────────────────────

/** speechRegister별 어미 정규식 (히트율 측정).
 *  주의: JS의 `\b`는 ASCII word-boundary 기준이라 한글에 안전하지 않음 →
 *  문장 종결부 (구두점/공백/줄끝/끝따옴표) 직전 형태로 매칭. */
const SENT_END = `(?=[\\s.!?…"”'’]|$)`;
const REGISTER_PATTERNS: Record<string, RegExp[]> = {
  HAOCHE: [
    new RegExp(`(?:하오|이오|시오|이외다|소이다|구려|구먼|구만|라네|다네|이네|군그래|일세|이로세)${SENT_END}`),
    new RegExp(`(?:[가-힣]오|[가-힣]네)${SENT_END}`),
  ],
  HAEYO: [new RegExp(`(?:해요|이에요|예요|네요|거든요|군요)${SENT_END}`)],
  BANMAL: [new RegExp(`(?:[가-힣]야|[가-힣]지|[가-힣]거든|[가-힣]어|[가-힣]아)${SENT_END}`)],
  HAPSYO: [new RegExp(`(?:습니다|입니다|십시오|니까)${SENT_END}`)],
  HAECHE: [new RegExp(`(?:했다|하다|[가-힣]는다|[가-힣]ㄴ다|[가-힣]다)${SENT_END}`)],
};

const PRONOUN_RE = /(그대|자네|당신|너|그쪽|손님|친구)/g;

function continuityScore(pairs: DialoguePair[]): ContinuityScore {
  const evalPairs = pairs.filter((p) => !p.isSetup);
  const npcs = loadNpcs();
  if (evalPairs.length < 2) {
    return {
      score: 5,
      keywordCarryOverRate: 1,
      pronounConsistency: 1,
      toneConsistency: 1,
      userResponseRate: 1,
      notes: ["평가 턴 < 2 — 기본값"],
    };
  }

  // 1) 키워드 carry-over (per-turn binary): 직전 NPC 발화 또는 직전 사용자 입력의
  //    명사 1개 이상이 현재 NPC 발화에 등장하면 +1. 비율 = 등장 턴 / 평가 턴-1.
  let carryOverHits = 0;
  let carryOverDen = 0;
  for (let i = 1; i < evalPairs.length; i++) {
    const prevUtter = utterancesText(evalPairs[i - 1]);
    const prevInput = evalPairs[i - 1].userInput;
    const cur = utterancesText(evalPairs[i]);
    if (!cur) continue;
    carryOverDen++;
    const prevNouns = new Set([
      ...extractKoreanNouns(prevUtter),
      ...extractKoreanNouns(prevInput),
    ]);
    if (prevNouns.size === 0) {
      carryOverHits++; // prev에 noun이 없으면 패널티 없음
      continue;
    }
    for (const k of prevNouns) {
      if (cur.includes(k)) {
        carryOverHits++;
        break;
      }
    }
  }
  const keywordCarryOverRate =
    carryOverDen > 0 ? carryOverHits / carryOverDen : 0.5;

  // 2) 호칭 일관성 — NPC별로 자기 utterance 안 호칭 일관성 측정
  // architecture/55 — 한 응답에 여러 NPC 등장 시 NPC별로 분리 측정.
  // 이전: 모든 utterance 합쳐서 dominant 호칭 카운트 → 다른 NPC 호칭 섞이면 mismatch.
  // 변경: NPC별 dominant/total 비율을 평균.
  const perNpcPronounCounts = new Map<string, Map<string, number>>();
  for (const p of evalPairs) {
    for (const u of p.npcUtterances) {
      const key = u.npcName?.trim() || "unknown";
      let counts = perNpcPronounCounts.get(key);
      if (!counts) {
        counts = new Map<string, number>();
        perNpcPronounCounts.set(key, counts);
      }
      for (const m of u.text.match(PRONOUN_RE) ?? []) {
        counts.set(m, (counts.get(m) ?? 0) + 1);
      }
    }
  }
  const npcPronounRatios: number[] = [];
  // 합산 카운트 — notes 출력용
  const pronounCounts = new Map<string, number>();
  for (const counts of perNpcPronounCounts.values()) {
    const total = [...counts.values()].reduce((a, b) => a + b, 0);
    if (total === 0) continue;
    const dominant = Math.max(...counts.values());
    npcPronounRatios.push(dominant / total);
    for (const [k, v] of counts) {
      pronounCounts.set(k, (pronounCounts.get(k) ?? 0) + v);
    }
  }
  const pronounConsistency =
    npcPronounRatios.length === 0
      ? 1
      : npcPronounRatios.reduce((a, b) => a + b, 0) / npcPronounRatios.length;

  // 3) 어조 일관성 — utterance 단위로 자기 NPC speechRegister 패턴 적중률
  // architecture/55 — 한 응답에 여러 NPC 등장 시 각자 자기 register로 평가.
  // primary NPC의 register로 모든 utterance를 측정하던 버그 수정.
  let toneHit = 0;
  let toneDen = 0;
  for (const p of evalPairs) {
    for (const u of p.npcUtterances) {
      if (!u.text) continue;
      // u.npcName으로 NPC 찾기 (name → unknownAlias → aliases). 매칭 안 되면
      // primary NPC로 fallback (가짜 NPC인 경우).
      const npc =
        findNpcByDisplayName(u.npcName, npcs) ??
        (p.speakerNpcId ? npcs.get(p.speakerNpcId) : null);
      const patterns =
        REGISTER_PATTERNS[npc?.speechRegister ?? "HAOCHE"] ??
        REGISTER_PATTERNS.HAOCHE;
      const sentences = u.text
        .split(/[.!?…]\s*/)
        .map((s) => s.trim())
        .filter(Boolean);
      for (const s of sentences) {
        toneDen++;
        if (patterns.some((re) => re.test(s))) toneHit++;
      }
    }
  }
  const toneConsistency = toneDen > 0 ? toneHit / toneDen : 1;

  // 4) 사용자 응답률 (per-turn binary) — 입력 명사 1개 이상 NPC 응답에 등장 시 +1
  let respHits = 0;
  let respDen = 0;
  for (const p of evalPairs) {
    const inputNouns = extractKoreanNouns(p.userInput);
    if (inputNouns.length === 0) continue;
    const txt = utterancesText(p);
    if (!txt) continue;
    respDen++;
    for (const k of inputNouns) {
      if (txt.includes(k)) {
        respHits++;
        break;
      }
    }
  }
  const userResponseRate = respDen > 0 ? respHits / respDen : 0.5;

  const score =
    keywordCarryOverRate * 2.0 +
    pronounConsistency * 1.0 +
    toneConsistency * 1.0 +
    userResponseRate * 1.0;

  const notes: string[] = [];
  if (keywordCarryOverRate < 0.2)
    notes.push(`carry-over ${(keywordCarryOverRate * 100).toFixed(0)}% — NPC가 이전 대화 잊음`);
  if (pronounConsistency < 0.7)
    notes.push(`호칭 변동: ${[...pronounCounts.keys()].join("/")}`);
  if (toneConsistency < 0.6)
    notes.push(`어미 일치율 ${(toneConsistency * 100).toFixed(0)}%`);
  if (userResponseRate < 0.3)
    notes.push(`사용자 질문 무시 비율 ${((1 - userResponseRate) * 100).toFixed(0)}%`);

  return {
    score: clamp(score, 0, 5),
    keywordCarryOverRate,
    pronounConsistency,
    toneConsistency,
    userResponseRate,
    notes,
  };
}

// ──────────────────────────────────────────────────────────────
// 2. Topic Freedom
// ──────────────────────────────────────────────────────────────

/** 모드 분포 이상치 (D 50, A 30, B 10, C 10). 합 100. */
const IDEAL_MODE_DIST: Record<Exclude<AuditMode, "NONE">, number> = {
  D_CHAT: 50,
  A_FACT: 30,
  B_HANDOFF: 10,
  C_DEFAULT: 10,
};

function topicFreedomScore(pairs: DialoguePair[]): TopicFreedomScore {
  const evalPairs = pairs.filter((p) => !p.isSetup);
  if (evalPairs.length === 0) {
    return {
      score: 5,
      modeBalance: 1,
      topicVariety: 1,
      noFactRepeat: 1,
      modeDistribution: { A_FACT: 0, B_HANDOFF: 0, C_DEFAULT: 0, D_CHAT: 0 },
      factOccurrences: {},
      notes: ["평가 턴 = 0"],
    };
  }
  // 1) 모드 분포
  const counts: Record<Exclude<AuditMode, "NONE">, number> = {
    A_FACT: 0,
    B_HANDOFF: 0,
    C_DEFAULT: 0,
    D_CHAT: 0,
  };
  let detectedTotal = 0;
  for (const p of evalPairs) {
    if (p.detectedMode === "NONE") continue;
    counts[p.detectedMode]++;
    detectedTotal++;
  }
  const modeDistribution: typeof counts = { ...counts };
  if (detectedTotal > 0) {
    for (const k of Object.keys(modeDistribution) as Array<keyof typeof counts>) {
      modeDistribution[k] = (counts[k] / detectedTotal) * 100;
    }
  }
  // 거리 = sum(|actual - ideal|), 0~200 → 1 - dist/200
  const dist =
    detectedTotal === 0
      ? 100
      : Object.keys(IDEAL_MODE_DIST)
          .map((k) =>
            Math.abs(
              modeDistribution[k as keyof typeof counts] -
                IDEAL_MODE_DIST[k as keyof typeof IDEAL_MODE_DIST],
            ),
          )
          .reduce((a, b) => a + b, 0);
  const modeBalance = clamp(1 - dist / 200, 0, 1);

  // 2) 화제 다양성 — fact 공개 블록 안의 factId 추출 (preview에서 factId 패턴 검색)
  const factOccurrences: Record<string, number[]> = {};
  for (const p of evalPairs) {
    const factBlock = p.prompt.blocks.find((b) => b.name === "fact 공개 (A)");
    if (!factBlock) continue;
    // factId는 보통 prompt에 직접 노출되지 않음 — 토픽 라벨 사용. preview 첫 줄 다음 fact "topic" 추출
    const topicMatch = factBlock.preview.match(/"([^"]{2,40})"/);
    const key = topicMatch ? topicMatch[1] : `T${p.turn}_unknown_fact`;
    factOccurrences[key] = factOccurrences[key] ?? [];
    factOccurrences[key].push(p.turn);
  }
  // 다양성: 모드 별 등장 종류 / 평가 턴 수 (간이 엔트로피 대용)
  const distinctModes = new Set(
    evalPairs.map((p) => p.detectedMode).filter((m) => m !== "NONE"),
  );
  const topicVariety = clamp(distinctModes.size / 4, 0, 1);

  // 3) fact 반복 — 같은 토픽 2회+ 출현
  const repeatedFacts = Object.entries(factOccurrences).filter(
    ([, ts]) => ts.length >= 2,
  );
  const noFactRepeat = clamp(1 - repeatedFacts.length * 0.5, 0, 1);

  const score = modeBalance * 2.0 + topicVariety * 1.5 + noFactRepeat * 1.5;

  const notes: string[] = [];
  if (modeDistribution.A_FACT >= 70)
    notes.push(`fact 모드 ${modeDistribution.A_FACT.toFixed(0)}% — 강제 주입 의심`);
  if (modeDistribution.D_CHAT < 20 && detectedTotal >= 3)
    notes.push(`잡담 ${modeDistribution.D_CHAT.toFixed(0)}% — 자연 대화 부족`);
  for (const [topic, ts] of repeatedFacts) {
    notes.push(`fact 반복: "${topic}" T${ts.join(",")}`);
  }

  return {
    score: clamp(score, 0, 5),
    modeBalance,
    topicVariety,
    noFactRepeat,
    modeDistribution,
    factOccurrences,
    notes,
  };
}

// ──────────────────────────────────────────────────────────────
// 3. Humanity
// ──────────────────────────────────────────────────────────────

const AVOID_WORDS = [
  "위험",
  "곤란",
  "조심하",
  "입을 닫",
  "함부로",
  "위태",
  "말할 수 없",
  "비밀이",
];

const IMPERATIVE_TAILS = [
  /[가-힣]하라\b/,
  /[가-힣]하지\s?마\b/,
  /[가-힣]해야\s?한\b/,
  /[가-힣]해야만\b/,
];

const METAPHOR_HINTS = [
  /[가-힣]+처럼/,
  /[가-힣]+같이\s/,
  /[가-힣]+같은/,
  /마치\s/,
  /비유하자면/,
];

function humanityScore(pairs: DialoguePair[]): HumanityScore {
  const evalPairs = pairs.filter((p) => !p.isSetup);
  if (evalPairs.length === 0) {
    return {
      score: 5,
      avoidWordRate: 0,
      imperativeRate: 0,
      npcSignatureRate: 1,
      metaphorUsageRate: 1,
      repetitionRate: 0,
      notes: ["평가 턴 = 0"],
    };
  }
  const npcs = loadNpcs();

  // 1) 회피 어휘
  let avoidHit = 0;
  for (const p of evalPairs) {
    const txt = utterancesText(p);
    if (AVOID_WORDS.some((w) => txt.includes(w))) avoidHit++;
  }
  const avoidWordRate = avoidHit / evalPairs.length;

  // 2) 명령조
  let impHit = 0;
  for (const p of evalPairs) {
    const txt = utterancesText(p);
    if (IMPERATIVE_TAILS.some((re) => re.test(txt))) impHit++;
  }
  const imperativeRate = impHit / evalPairs.length;

  // 3) NPC signature — speakerNpc의 signature/traits 키워드 등장 비율
  let sigHit = 0;
  let sigDen = 0;
  for (const p of evalPairs) {
    if (!p.speakerNpcId) continue;
    const npc = npcs.get(p.speakerNpcId);
    if (!npc || npc.signatureKeywords.size === 0) continue;
    sigDen++;
    const txt = pairText(p);
    let any = false;
    for (const k of npc.signatureKeywords) {
      if (txt.includes(k)) {
        any = true;
        break;
      }
    }
    if (any) sigHit++;
  }
  const npcSignatureRate = sigDen > 0 ? sigHit / sigDen : 0.5;

  // 4) 비유 사용 — METAPHOR 패턴 1+ 등장
  let metHit = 0;
  for (const p of evalPairs) {
    const txt = pairText(p);
    if (METAPHOR_HINTS.some((re) => re.test(txt))) metHit++;
  }
  const metaphorUsageRate = metHit / evalPairs.length;

  // 5) 반복 표현 — 4글자 substring 2회+ 등장 (NPC 발화만)
  let repHit = 0;
  for (let i = 1; i < evalPairs.length; i++) {
    const cur = utterancesText(evalPairs[i]);
    if (cur.length < 8) continue;
    const window = evalPairs
      .slice(Math.max(0, i - 2), i)
      .map((p) => utterancesText(p))
      .join(" ");
    // 4글자 substring 후보
    let found = false;
    for (let j = 0; j + 4 <= cur.length; j++) {
      const frag = cur.slice(j, j + 4);
      if (!/^[가-힣]{4}$/.test(frag)) continue;
      if (window.includes(frag)) {
        found = true;
        break;
      }
    }
    if (found) repHit++;
  }
  const repetitionRate = evalPairs.length >= 2 ? repHit / (evalPairs.length - 1) : 0;

  const score =
    (1 - avoidWordRate) * 1.0 +
    (1 - imperativeRate) * 1.0 +
    npcSignatureRate * 1.5 +
    metaphorUsageRate * 1.0 +
    (1 - repetitionRate) * 0.5;

  const notes: string[] = [];
  if (avoidWordRate >= 0.3)
    notes.push(`회피 어휘 ${(avoidWordRate * 100).toFixed(0)}%`);
  if (imperativeRate >= 0.3)
    notes.push(`명령조 ${(imperativeRate * 100).toFixed(0)}%`);
  if (npcSignatureRate < 0.3 && sigDen > 0)
    notes.push(
      `NPC 고유 어휘 등장 ${(npcSignatureRate * 100).toFixed(0)}% — personality 발현 부족`,
    );
  if (metaphorUsageRate < 0.2)
    notes.push(`비유 사용 ${(metaphorUsageRate * 100).toFixed(0)}%`);
  if (repetitionRate >= 0.4)
    notes.push(`반복 표현 ${(repetitionRate * 100).toFixed(0)}%`);

  return {
    score: clamp(score, 0, 5),
    avoidWordRate,
    imperativeRate,
    npcSignatureRate,
    metaphorUsageRate,
    repetitionRate,
    notes,
  };
}

// ──────────────────────────────────────────────────────────────
// architecture/51 — NpcDistinctness 점수
// ──────────────────────────────────────────────────────────────

/**
 * 화자 NPC별 distinct 시그니처(signature/traits/roleKeywords/alias 단어) 등장률.
 * 높을수록 NPC가 자기다운 톤으로 말함.
 */
function npcDistinctnessScore(pairs: DialoguePair[]): NpcDistinctnessScore {
  const evalPairs = pairs.filter((p) => !p.isSetup);
  const npcs = loadNpcs();
  const perNpcHits: Record<string, number> = {};
  const perNpcTurns: Record<string, number> = {};
  const perNpcSignaturePoolSize: Record<string, number> = {};

  for (const p of evalPairs) {
    if (!p.speakerNpcId) continue;
    const npc = npcs.get(p.speakerNpcId);
    if (!npc || npc.distinctPool.size === 0) continue;
    perNpcSignaturePoolSize[p.speakerNpcId] = npc.distinctPool.size;
    const txt = pairText(p);
    if (!txt) continue;
    perNpcTurns[p.speakerNpcId] = (perNpcTurns[p.speakerNpcId] ?? 0) + 1;
    const hit = [...npc.distinctPool].some((kw) => txt.includes(kw));
    if (hit) perNpcHits[p.speakerNpcId] = (perNpcHits[p.speakerNpcId] ?? 0) + 1;
  }

  const perNpcDistinctness: Record<string, number> = {};
  for (const npcId of Object.keys(perNpcTurns)) {
    const turns = perNpcTurns[npcId] || 0;
    const hits = perNpcHits[npcId] ?? 0;
    perNpcDistinctness[npcId] = turns > 0 ? hits / turns : 0;
  }
  const rates = Object.values(perNpcDistinctness).filter(
    (n) => Number.isFinite(n),
  );
  const avg =
    rates.length > 0 ? rates.reduce((a, b) => a + b, 0) / rates.length : 0.5;
  const score = clamp(avg * 5, 0, 5);

  const notes: string[] = [];
  for (const [npcId, rate] of Object.entries(perNpcDistinctness)) {
    if (rate < 0.4) {
      notes.push(`${npcId} distinctness ${(rate * 100).toFixed(0)}%`);
    }
  }

  return {
    score,
    perNpcDistinctness,
    perNpcSignaturePoolSize,
    notes,
  };
}

// ──────────────────────────────────────────────────────────────
// architecture/51 — ToneMatch 점수
// ──────────────────────────────────────────────────────────────

/** 사용자 입력 톤 분류. */
function classifyUserTone(input: string): ToneCategory {
  if (!input) return "unknown";
  const text = input.trim();
  // 가벼운 신호: 짧음 + 의문문 + 가벼운 명사
  const hasQuestion = /[?？]/.test(text);
  const isShort = text.length <= 25;
  const CASUAL_WORDS = [
    "안녕",
    "오늘",
    "어떻소",
    "어떻",
    "잘",
    "고맙",
    "기억",
    "들었소",
    "나왔",
    "보러",
    "스튜",
    "빵",
    "약초",
    "가족",
    "자식",
    "잠은",
    "주무",
    "재밌",
  ];
  const SERIOUS_WORDS = [
    "장부",
    "사라진",
    "도난",
    "임금",
    "횡령",
    "밀수",
    "음모",
    "위협",
    "비밀",
    "조직",
    "권력",
    "처형",
    "처벌",
    "위태",
    "위험",
  ];
  const hasCasual = CASUAL_WORDS.some((w) => text.includes(w));
  const hasSerious = SERIOUS_WORDS.some((w) => text.includes(w));
  if (hasSerious && !hasCasual) return "serious";
  if (hasCasual || (isShort && hasQuestion)) return "casual";
  if (text.length > 40) return "serious";
  return "unknown";
}

/** NPC 응답 톤 분류 (회피 어휘 + 길이). */
function classifyNpcTone(text: string): ToneCategory {
  if (!text) return "unknown";
  const HEAVY_WORDS = [
    "위험",
    "조심",
    "곤란",
    "위태",
    "독",
    "썩은",
    "음모",
    "잘못",
    "비밀",
    "함부로",
    "멀쩡",
    "독초",
  ];
  const heavyCount = HEAVY_WORDS.filter((w) => text.includes(w)).length;
  if (heavyCount >= 2) return "serious";
  if (text.length > 200 && heavyCount >= 1) return "serious";
  if (text.length <= 80 && heavyCount === 0) return "casual";
  return "unknown";
}

function toneMatchScore(pairs: DialoguePair[]): ToneMatchScore {
  const evalPairs = pairs.filter((p) => !p.isSetup);
  const npcs = loadNpcs();
  const userToneDist: Record<ToneCategory, number> = {
    casual: 0,
    serious: 0,
    unknown: 0,
  };
  const npcToneDist: Record<ToneCategory, number> = {
    casual: 0,
    serious: 0,
    unknown: 0,
  };
  const perTurn: ToneMatchScore["perTurn"] = [];
  let matched = 0;
  let total = 0;

  for (const p of evalPairs) {
    const userTone = classifyUserTone(p.userInput);
    const npcText = utterancesText(p);
    if (!npcText) continue;
    const npcTone = classifyNpcTone(npcText);
    userToneDist[userTone]++;
    npcToneDist[npcTone]++;
    if (userTone === "unknown" || npcTone === "unknown") continue;
    total++;
    // architecture/51 §A — NPC baseline 고려 mismatch 판정.
    // 사용자 casual인데 NPC가 baseline보다 *더* 무거우면 mismatch.
    // 동일 톤은 항상 match. 사용자 serious는 baseline 무관 match (어떤 NPC도 serious 응답 자연스럽).
    const npc = p.speakerNpcId ? npcs.get(p.speakerNpcId) : null;
    const baseline = npc?.baselineTone ?? "neutral";
    let match: boolean;
    if (userTone === npcTone) {
      // 동일 톤
      match = true;
    } else if (userTone === "serious") {
      // serious 입력엔 NPC가 무엇이든 자연스럽게 응답
      match = true;
    } else {
      // userTone=casual, npcTone=serious — baseline 차이로 보정
      // dark NPC는 어두운 응답이 자연 — match (단, "회피 어휘 2회+"면 여전히 mismatch)
      if (baseline === "dark" || baseline === "cold") {
        // baseline이 dark/cold라도 회피 어휘가 과다하면 mismatch
        const HEAVY_WORDS = [
          "위험",
          "조심",
          "곤란",
          "위태",
          "독",
          "썩은",
          "음모",
          "잘못",
          "비밀",
          "함부로",
          "독초",
        ];
        const heavyCount = HEAVY_WORDS.filter((w) => npcText.includes(w)).length;
        match = heavyCount <= 1;
      } else {
        // warm/neutral baseline이 serious 응답 → mismatch
        match = false;
      }
    }
    if (match) matched++;
    perTurn.push({ turn: p.turn, userTone, npcTone, matched: match });
  }

  const matchRate = total > 0 ? matched / total : 0.5;
  const score = clamp(matchRate * 5, 0, 5);
  const notes: string[] = [];
  const casualToSerious = perTurn.filter(
    (t) => t.userTone === "casual" && t.npcTone === "serious" && !t.matched,
  );
  if (casualToSerious.length > 0) {
    notes.push(
      `casual→serious mismatch ${casualToSerious.length}회 (T${casualToSerious.map((t) => t.turn).join(",")})`,
    );
  }
  if (matchRate < 0.5) {
    notes.push(`톤 일치 ${(matchRate * 100).toFixed(0)}%`);
  }

  return {
    score,
    matchRate,
    userToneDistribution: userToneDist,
    npcToneDistribution: npcToneDist,
    perTurn,
    notes,
  };
}

// ──────────────────────────────────────────────────────────────
// 통합
// ──────────────────────────────────────────────────────────────

export function computeDialogueQuality(pairs: DialoguePair[]): DialogueQuality {
  const c = continuityScore(pairs);
  const t = topicFreedomScore(pairs);
  const h = humanityScore(pairs);
  const d = npcDistinctnessScore(pairs);
  const tm = toneMatchScore(pairs);
  return {
    continuity: c,
    topicFreedom: t,
    humanity: h,
    npcDistinctness: d,
    toneMatch: tm,
    // architecture/51 — 5 score 평균
    overall: (c.score + t.score + h.score + d.score + tm.score) / 5,
  };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}
