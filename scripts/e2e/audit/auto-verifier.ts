/**
 * NPA 자동 검증 — 3-tier (ERROR / WARNING / INFO).
 * 설계: architecture/47_dialogue_quality_audit.md §6.
 */

import type {
  AuditFinding,
  AuditScenario,
  DialoguePair,
  DialogueQuality,
} from "./types.js";

const TOKEN_LIMIT_WARN = 13_000;
const AVOID_WORDS = [
  "위험",
  "곤란",
  "조심하",
  "입을 닫",
  "함부로",
  "위태",
  "말할 수 없",
];
const HONORIFIC_HINTS = [
  /미렐라/,
  /로넨/,
  /에드릭/,
  /하를런/,
  /[가-힣]{2,4}\s?[씨님]\b/,
  /노파|노점\s?주인|상인|문지기|경비/,
];

const MARKER_RE = /@\[[^\]]+\]/g;
const MARKER_OPEN_RE = /@\[/g;

export function verify(
  scenario: AuditScenario,
  pairs: DialoguePair[],
  quality: DialogueQuality,
): { errors: AuditFinding[]; warnings: AuditFinding[]; infos: AuditFinding[] } {
  const errors: AuditFinding[] = [];
  const warnings: AuditFinding[] = [];
  const infos: AuditFinding[] = [];
  const evalPairs = pairs.filter((p) => !p.isSetup);

  // ── ERROR ────────────────────────────────────────────────
  for (const p of pairs) {
    // E1. MARKER_NPCID_NULL — speakingNpc.npcId null인데 displayName이 무명 외
    if (
      p.speakerNpcId === null &&
      p.speakerDisplayName &&
      p.speakerDisplayName !== "무명 인물"
    ) {
      errors.push({
        turn: p.turn,
        rule: "MARKER_NPCID_NULL",
        message: `speakingNpc.npcId=null인데 displayName="${p.speakerDisplayName}" — architecture/46 회귀`,
        severity: "ERROR",
      });
    }

    // E2. MARKER_FORMAT_BROKEN — '@[' 토큰은 있는데 정상 마커가 0건
    const opens = (p.rawOutput.match(MARKER_OPEN_RE) ?? []).length;
    const fullMatches = (p.rawOutput.match(MARKER_RE) ?? []).length;
    if (opens > 0 && fullMatches < opens) {
      errors.push({
        turn: p.turn,
        rule: "MARKER_FORMAT_BROKEN",
        message: `@[ ${opens}개 vs 정상 마커 ${fullMatches}개 — 마커 깨짐`,
        severity: "ERROR",
      });
    }

    // E5. FACT_BLOCK_NO_KEYWORD_MATCH — fact 블록 있는데 입력에 한글 명사 0
    const factBlock = p.prompt.blocks.find((b) => b.name === "fact 공개 (A)");
    if (factBlock && (p.userInput.match(/[가-힣]{2,}/g) ?? []).length === 0) {
      errors.push({
        turn: p.turn,
        rule: "FACT_BLOCK_NO_KEYWORD_MATCH",
        message: `fact 공개 블록 노출됐는데 사용자 입력에 한글 키워드 0건`,
        severity: "ERROR",
      });
    }

    // E6. LLM_FAILED — output 없거나 sentinel
    if (!p.rawOutput || p.rawOutput.startsWith("[LLM_")) {
      errors.push({
        turn: p.turn,
        rule: "LLM_FAILED",
        message: `LLM 응답 비정상: "${p.rawOutput.slice(0, 40)}"`,
        severity: "ERROR",
      });
    }
  }

  // E3. NPC_JUMP_NO_HONORIFIC — 호명 없는데 NPC 변경 (expectSameNpc=true)
  if (scenario.expectSameNpc) {
    const speakers = evalPairs.map((p) => p.speakerNpcId).filter(Boolean) as string[];
    if (speakers.length >= 2) {
      const first = speakers[0];
      for (let i = 1; i < evalPairs.length; i++) {
        const p = evalPairs[i];
        const prevSpeaker = speakers[i - 1];
        if (!p.speakerNpcId || p.speakerNpcId === prevSpeaker) continue;
        // 사용자 입력에 NPC 호명 힌트 있나
        const hasHonorific = HONORIFIC_HINTS.some((re) => re.test(p.userInput));
        if (!hasHonorific) {
          errors.push({
            turn: p.turn,
            rule: "NPC_JUMP_NO_HONORIFIC",
            message: `T${p.turn} NPC 변경 (${prevSpeaker} → ${p.speakerNpcId}) — 사용자 입력에 호명 없음 ("${p.userInput}")`,
            severity: "ERROR",
          });
        }
      }
      void first;
    }
  }

  // E4. TOKEN_EXPLOSION
  for (const p of evalPairs) {
    if (p.prompt.totalTokens >= TOKEN_LIMIT_WARN) {
      errors.push({
        turn: p.turn,
        rule: "TOKEN_EXPLOSION",
        message: `프롬프트 ${p.prompt.totalTokens} 토큰 (≥${TOKEN_LIMIT_WARN})`,
        severity: "ERROR",
      });
    }
  }

  // ── WARNING ──────────────────────────────────────────────

  // W1. AVOID_WORD_HEAVY
  let avoidHit = 0;
  const avoidTurns: number[] = [];
  for (const p of evalPairs) {
    const txt = p.npcUtterances.map((u) => u.text).join(" ");
    if (AVOID_WORDS.some((w) => txt.includes(w))) {
      avoidHit++;
      avoidTurns.push(p.turn);
    }
  }
  if (evalPairs.length > 0 && avoidHit / evalPairs.length >= 0.3) {
    warnings.push({
      rule: "AVOID_WORD_HEAVY",
      message: `회피 어휘 ${avoidHit}/${evalPairs.length}턴 (T${avoidTurns.join(",")})`,
      severity: "WARNING",
    });
  }

  // W2. SAME_FACT_REPEATED
  for (const [topic, ts] of Object.entries(quality.topicFreedom.factOccurrences)) {
    if (ts.length >= 2) {
      warnings.push({
        rule: "SAME_FACT_REPEATED",
        message: `같은 fact "${topic}" T${ts.join(",")}에 중복 노출`,
        severity: "WARNING",
      });
    }
  }

  // W3. PRONOUN_INCONSISTENT
  if (quality.continuity.pronounConsistency < 0.7) {
    warnings.push({
      rule: "PRONOUN_INCONSISTENT",
      message: `호칭 일관성 ${(quality.continuity.pronounConsistency * 100).toFixed(0)}%`,
      severity: "WARNING",
    });
  }

  // W4. TONE_DRIFT
  if (quality.continuity.toneConsistency < 0.6) {
    warnings.push({
      rule: "TONE_DRIFT",
      message: `어미 일치율 ${(quality.continuity.toneConsistency * 100).toFixed(0)}% — speechRegister 이탈`,
      severity: "WARNING",
    });
  }

  // W5. LOW_USER_RESPONSE
  if (quality.continuity.userResponseRate < 0.3) {
    warnings.push({
      rule: "LOW_USER_RESPONSE",
      message: `사용자 핵심어 응답률 ${(quality.continuity.userResponseRate * 100).toFixed(0)}%`,
      severity: "WARNING",
    });
  }

  // W6. MODE_IMBALANCE
  const factPct = quality.topicFreedom.modeDistribution.A_FACT;
  if (factPct >= 70) {
    warnings.push({
      rule: "MODE_IMBALANCE",
      message: `fact 모드 ${factPct.toFixed(0)}% — 강제 주입 의심`,
      severity: "WARNING",
    });
  }

  // ── INFO (데이터) ─────────────────────────────────────────
  const tokens = evalPairs.map((p) => p.prompt.totalTokens).filter((x) => x > 0);
  const lats = evalPairs.map((p) => p.llmLatencyMs).filter((x) => x > 0);
  const wordCounts = evalPairs.map((p) =>
    p.npcUtterances.map((u) => u.text.length).reduce((a, b) => a + b, 0),
  );

  infos.push({
    rule: "TOKEN_USAGE",
    message: `프롬프트 평균 ${avg(tokens).toFixed(0)} (max ${Math.max(...tokens, 0)})`,
    severity: "INFO",
    data: { avg: avg(tokens), max: Math.max(...tokens, 0) },
  });
  infos.push({
    rule: "MODE_DISTRIBUTION",
    message: `A=${quality.topicFreedom.modeDistribution.A_FACT.toFixed(0)}% B=${quality.topicFreedom.modeDistribution.B_HANDOFF.toFixed(0)}% C=${quality.topicFreedom.modeDistribution.C_DEFAULT.toFixed(0)}% D=${quality.topicFreedom.modeDistribution.D_CHAT.toFixed(0)}%`,
    severity: "INFO",
    data: quality.topicFreedom.modeDistribution,
  });

  const npcCounts = new Map<string, number>();
  for (const p of evalPairs) {
    if (!p.speakerNpcId) continue;
    npcCounts.set(p.speakerNpcId, (npcCounts.get(p.speakerNpcId) ?? 0) + 1);
  }
  infos.push({
    rule: "NPC_DISTRIBUTION",
    message:
      [...npcCounts.entries()].map(([k, v]) => `${k}:${v}`).join(", ") ||
      "(없음)",
    severity: "INFO",
    data: Object.fromEntries(npcCounts),
  });

  if (lats.length > 0) {
    const sorted = [...lats].sort((a, b) => a - b);
    const p95 = sorted[Math.floor(sorted.length * 0.95)] ?? sorted[sorted.length - 1];
    infos.push({
      rule: "LATENCY",
      message: `avg=${avg(lats).toFixed(0)}ms · max=${Math.max(...lats)}ms · p95=${p95}ms`,
      severity: "INFO",
      data: { avg: avg(lats), max: Math.max(...lats), p95 },
    });
  }

  if (wordCounts.length > 0) {
    infos.push({
      rule: "WORD_COUNT",
      message: `NPC 발화 평균 ${avg(wordCounts).toFixed(0)}자/턴`,
      severity: "INFO",
      data: { avg: avg(wordCounts) },
    });
  }

  return { errors, warnings, infos };
}

function avg(arr: number[]): number {
  if (arr.length === 0) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}
