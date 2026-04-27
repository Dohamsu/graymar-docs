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
  signatureKeywords: Set<string>;
  speechRegister: "HAOCHE" | "HAEYO" | "BANMAL" | "HAPSYO" | "HAECHE";
}

let _npcCache: Map<string, NpcContentSnapshot> | null = null;

function loadNpcs(): Map<string, NpcContentSnapshot> {
  if (_npcCache) return _npcCache;
  const npcsPath = path.join(CONTENT_ROOT, "npcs.json");
  const raw = JSON.parse(fs.readFileSync(npcsPath, "utf-8")) as Array<{
    npcId: string;
    name: string;
    personality?: {
      signature?: string[];
      traits?: string[];
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
    map.set(n.npcId, {
      npcId: n.npcId,
      name: n.name,
      signatureKeywords: keywords,
      speechRegister: n.personality?.speechRegister ?? "HAOCHE",
    });
  }
  _npcCache = map;
  return map;
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

  // 2) 호칭 일관성 — NPC 발화에서 가장 많이 쓴 호칭 외 다른 호칭 등장 비율
  const pronounCounts = new Map<string, number>();
  for (const p of evalPairs) {
    const txt = utterancesText(p);
    for (const m of txt.match(PRONOUN_RE) ?? []) {
      pronounCounts.set(m, (pronounCounts.get(m) ?? 0) + 1);
    }
  }
  const totalPronouns = [...pronounCounts.values()].reduce((a, b) => a + b, 0);
  const dominant = Math.max(0, ...pronounCounts.values());
  const pronounConsistency =
    totalPronouns === 0 ? 1 : dominant / totalPronouns;

  // 3) 어조 일관성 — 화자 NPC speechRegister 패턴 적중률
  let toneHit = 0;
  let toneDen = 0;
  for (const p of evalPairs) {
    const txt = utterancesText(p);
    if (!txt) continue;
    const npc = p.speakerNpcId ? npcs.get(p.speakerNpcId) : null;
    const patterns =
      REGISTER_PATTERNS[npc?.speechRegister ?? "HAOCHE"] ??
      REGISTER_PATTERNS.HAOCHE;
    const sentences = txt
      .split(/[.!?…]\s*/)
      .map((s) => s.trim())
      .filter(Boolean);
    for (const s of sentences) {
      toneDen++;
      if (patterns.some((re) => re.test(s))) toneHit++;
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
// 통합
// ──────────────────────────────────────────────────────────────

export function computeDialogueQuality(pairs: DialoguePair[]): DialogueQuality {
  const c = continuityScore(pairs);
  const t = topicFreedomScore(pairs);
  const h = humanityScore(pairs);
  return {
    continuity: c,
    topicFreedom: t,
    humanity: h,
    overall: (c.score + t.score + h.score) / 3,
  };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}
