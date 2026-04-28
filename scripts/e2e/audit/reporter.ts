/**
 * NPA Reporter — 마크다운 + JSON 출력.
 * 설계: architecture/47_dialogue_quality_audit.md §7.
 */

import * as fs from "node:fs";
import * as path from "node:path";

import type { AuditFinding, AuditReport, DialoguePair } from "./types.js";

function stars(score: number): string {
  // 0~5 → 채운 별 1~5
  const n = Math.max(1, Math.min(5, Math.round(score)));
  return "★".repeat(n) + "☆".repeat(5 - n);
}

function formatPair(p: DialoguePair): string {
  const speaker = p.speakerDisplayName
    ? `${p.speakerDisplayName}${p.speakerNpcId ? ` (${p.speakerNpcId})` : ""}`
    : "(없음)";
  const utterance = p.npcUtterances.length
    ? p.npcUtterances.map((u) => `"${u.text}"`).join(" ")
    : "(대사 없음)";
  return `T${p.turn} [${p.detectedMode}] ${speaker}\n  사용자: ${p.userInput}\n  NPC   : ${utterance}`;
}

export function renderMarkdown(report: AuditReport): string {
  const q = report.dialogueQuality;
  const lines: string[] = [];
  lines.push(`# Dialogue Quality Audit — ${report.scenario.name}`);
  lines.push("");
  lines.push(
    `**서버**: ${report.serverVersion} | **시나리오**: \`${report.scenario.id}\` | **소요**: ${(report.totalElapsedMs / 1000).toFixed(1)}s | **턴**: ${report.pairs.filter((p) => !p.isSetup).length}평가 + ${report.pairs.filter((p) => p.isSetup).length}setup`,
  );
  lines.push("");
  lines.push(`> ${report.scenario.intent}`);
  lines.push("");

  // ── 종합 점수 ─────────────────────────────────
  lines.push("## ⭐ 종합 점수");
  lines.push("");
  lines.push(`- **연결성**:   ${stars(q.continuity.score)} (${q.continuity.score.toFixed(2)} / 5)`);
  lines.push(`- **자유도**:   ${stars(q.topicFreedom.score)} (${q.topicFreedom.score.toFixed(2)} / 5)`);
  lines.push(`- **사람다움**: ${stars(q.humanity.score)} (${q.humanity.score.toFixed(2)} / 5)`);
  lines.push(`- **NPC 차별화**: ${stars(q.npcDistinctness.score)} (${q.npcDistinctness.score.toFixed(2)} / 5)`);
  lines.push(`- **톤 일치도**: ${stars(q.toneMatch.score)} (${q.toneMatch.score.toFixed(2)} / 5)`);
  lines.push(`- **종합**:     ${stars(q.overall)} (${q.overall.toFixed(2)} / 5)`);
  lines.push("");

  // ── 자동 검출 ─────────────────────────────────
  const { errors, warnings, infos } = report.findings;
  lines.push("## 자동 검출");
  lines.push(
    `- ❌ ERROR: ${errors.length}건  ⚠️ WARNING: ${warnings.length}건  ℹ️ INFO: ${infos.length}건`,
  );
  lines.push("");
  if (errors.length > 0) {
    lines.push("### Errors");
    for (const f of errors) lines.push(formatFinding(f));
    lines.push("");
  }
  if (warnings.length > 0) {
    lines.push("### Warnings");
    for (const f of warnings) lines.push(formatFinding(f));
    lines.push("");
  }
  lines.push("### Info");
  for (const f of infos) lines.push(formatFinding(f));
  lines.push("");

  // ── 대화 흐름 ─────────────────────────────────
  lines.push("## 대화 흐름");
  lines.push("");
  lines.push("| T | 입력 | 모드 | NPC | 평가 |");
  lines.push("|---|------|------|------|------|");
  for (const p of report.pairs) {
    const speaker = p.speakerDisplayName ?? "-";
    const tag = p.isSetup ? "(setup)" : p.detectedMode;
    const note: string[] = [];
    const ut = p.npcUtterances.map((u) => u.text).join(" ").slice(0, 40);
    if (ut) note.push(`"${ut}${ut.length >= 40 ? "…" : ""}"`);
    lines.push(
      `| ${p.turn} | ${escMd(p.userInput.slice(0, 30))} | ${tag} | ${speaker} | ${escMd(note.join(" · "))} |`,
    );
  }
  lines.push("");

  // ── Quality 모듈 상세 ─────────────────────────
  lines.push("## Quality 모듈 상세");
  lines.push("");
  lines.push(`### 연결성 (${q.continuity.score.toFixed(2)} / 5)`);
  lines.push(`- 키워드 carry-over: ${(q.continuity.keywordCarryOverRate * 100).toFixed(0)}%`);
  lines.push(`- 호칭 일관: ${(q.continuity.pronounConsistency * 100).toFixed(0)}%`);
  lines.push(`- 어미 일치: ${(q.continuity.toneConsistency * 100).toFixed(0)}%`);
  lines.push(`- 사용자 응답률: ${(q.continuity.userResponseRate * 100).toFixed(0)}%`);
  if (q.continuity.notes.length) lines.push(`- 메모: ${q.continuity.notes.join(" · ")}`);
  lines.push("");

  lines.push(`### 자유도 (${q.topicFreedom.score.toFixed(2)} / 5)`);
  const md = q.topicFreedom.modeDistribution;
  lines.push(
    `- 모드 분포: A=${md.A_FACT.toFixed(0)}% / B=${md.B_HANDOFF.toFixed(0)}% / C=${md.C_DEFAULT.toFixed(0)}% / D=${md.D_CHAT.toFixed(0)}%`,
  );
  lines.push(`- 모드 균형: ${(q.topicFreedom.modeBalance * 100).toFixed(0)}%`);
  lines.push(`- 화제 다양성: ${(q.topicFreedom.topicVariety * 100).toFixed(0)}%`);
  lines.push(`- fact 비반복: ${(q.topicFreedom.noFactRepeat * 100).toFixed(0)}%`);
  if (q.topicFreedom.notes.length) lines.push(`- 메모: ${q.topicFreedom.notes.join(" · ")}`);
  lines.push("");

  lines.push(`### 사람다움 (${q.humanity.score.toFixed(2)} / 5)`);
  lines.push(`- 회피 어휘: ${(q.humanity.avoidWordRate * 100).toFixed(0)}%`);
  lines.push(`- 명령조: ${(q.humanity.imperativeRate * 100).toFixed(0)}%`);
  lines.push(`- NPC 고유 어휘: ${(q.humanity.npcSignatureRate * 100).toFixed(0)}%`);
  lines.push(`- 비유 사용: ${(q.humanity.metaphorUsageRate * 100).toFixed(0)}%`);
  lines.push(`- 반복 표현: ${(q.humanity.repetitionRate * 100).toFixed(0)}%`);
  if (q.humanity.notes.length) lines.push(`- 메모: ${q.humanity.notes.join(" · ")}`);
  lines.push("");

  // architecture/51 — NPC 차별화
  lines.push(`### NPC 차별화 (${q.npcDistinctness.score.toFixed(2)} / 5)`);
  for (const [npcId, rate] of Object.entries(q.npcDistinctness.perNpcDistinctness)) {
    const pool = q.npcDistinctness.perNpcSignaturePoolSize[npcId] ?? 0;
    lines.push(`- ${npcId}: ${(rate * 100).toFixed(0)}% (시그니처 풀 ${pool})`);
  }
  if (q.npcDistinctness.notes.length) lines.push(`- 메모: ${q.npcDistinctness.notes.join(" · ")}`);
  lines.push("");

  // architecture/51 — 톤 일치도
  lines.push(`### 톤 일치도 (${q.toneMatch.score.toFixed(2)} / 5)`);
  lines.push(`- 매칭률: ${(q.toneMatch.matchRate * 100).toFixed(0)}%`);
  lines.push(`- 사용자 톤 분포: casual=${q.toneMatch.userToneDistribution.casual}, serious=${q.toneMatch.userToneDistribution.serious}, unknown=${q.toneMatch.userToneDistribution.unknown}`);
  lines.push(`- NPC 톤 분포: casual=${q.toneMatch.npcToneDistribution.casual}, serious=${q.toneMatch.npcToneDistribution.serious}, unknown=${q.toneMatch.npcToneDistribution.unknown}`);
  if (q.toneMatch.notes.length) lines.push(`- 메모: ${q.toneMatch.notes.join(" · ")}`);
  lines.push("");

  // ── Pipeline Trace (펼치기) ────────────────────
  lines.push("## Pipeline Trace (보조)");
  lines.push("");
  for (const p of report.pairs.filter((p) => !p.isSetup)) {
    lines.push(`<details>`);
    lines.push(`<summary>T${p.turn} [${p.detectedMode}] ${p.userInput}</summary>`);
    lines.push("");
    lines.push(`**프롬프트** (${p.prompt.totalTokens} 토큰, 블록 ${p.prompt.blocks.length}개)`);
    lines.push("");
    lines.push("```");
    for (const b of p.prompt.blocks) {
      lines.push(`[${b.tokens}t] ${b.name}`);
      const preview = b.preview.split("\n").slice(0, 3).join(" ↩ ");
      lines.push(`  → ${preview.slice(0, 200)}`);
    }
    lines.push("```");
    lines.push("");
    lines.push("**LLM 원본 출력**");
    lines.push("");
    lines.push("```");
    lines.push(p.rawOutput.slice(0, 800));
    lines.push("```");
    lines.push("");
    lines.push(
      `**후처리/렌더**: speakerNpcId=\`${p.speakerNpcId ?? "null"}\` displayName=${p.speakerDisplayName ?? "null"} resolveOutcome=${p.resolveOutcome ?? "-"} eventId=${p.eventId ?? "-"} latency=${p.llmLatencyMs}ms`,
    );
    lines.push("");
    lines.push(`</details>`);
    lines.push("");
  }

  // ── 사용자 ↔ NPC 흐름 (수동 review용) ────────────
  lines.push("## 사용자 ↔ NPC 흐름");
  lines.push("");
  lines.push("```");
  for (const p of report.pairs) {
    lines.push(formatPair(p));
    lines.push("");
  }
  lines.push("```");

  return lines.join("\n");
}

function escMd(s: string): string {
  return s.replace(/\|/g, "\\|").replace(/\n/g, " ");
}

function formatFinding(f: AuditFinding): string {
  const head = f.turn !== undefined ? `[T${f.turn} / ${f.rule}]` : `[${f.rule}]`;
  return `- ${head} ${f.message}`;
}

export function writeReport(
  report: AuditReport,
  outputPath: string,
): { mdPath: string; jsonPath: string } {
  const dir = path.dirname(outputPath);
  fs.mkdirSync(dir, { recursive: true });

  const mdPath = outputPath.endsWith(".md")
    ? outputPath
    : `${outputPath}.md`;
  const jsonPath = mdPath.replace(/\.md$/, ".json");

  fs.writeFileSync(mdPath, renderMarkdown(report), "utf-8");
  fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2), "utf-8");

  return { mdPath, jsonPath };
}

export function printConsoleSummary(report: AuditReport): void {
  const q = report.dialogueQuality;
  const { errors, warnings, infos } = report.findings;
  console.log("");
  console.log("═".repeat(60));
  console.log(`Dialogue Quality Audit — ${report.scenario.name}`);
  console.log("═".repeat(60));
  console.log(`  연결성   ${stars(q.continuity.score)} ${q.continuity.score.toFixed(2)}`);
  console.log(`  자유도   ${stars(q.topicFreedom.score)} ${q.topicFreedom.score.toFixed(2)}`);
  console.log(`  사람다움 ${stars(q.humanity.score)} ${q.humanity.score.toFixed(2)}`);
  console.log(`  NPC차별화 ${stars(q.npcDistinctness.score)} ${q.npcDistinctness.score.toFixed(2)}`);
  console.log(`  톤일치   ${stars(q.toneMatch.score)} ${q.toneMatch.score.toFixed(2)}`);
  console.log(`  ──────────────`);
  console.log(`  종합    ${stars(q.overall)} ${q.overall.toFixed(2)} / 5`);
  console.log("");
  console.log(
    `  ❌ ${errors.length} ERROR · ⚠️ ${warnings.length} WARN · ℹ️ ${infos.length} INFO`,
  );
  if (errors.length > 0) {
    console.log("");
    for (const f of errors)
      console.log(`  ❌ ${f.turn ? `T${f.turn} ` : ""}${f.rule}: ${f.message}`);
  }
  if (warnings.length > 0) {
    console.log("");
    for (const f of warnings)
      console.log(`  ⚠️  ${f.turn ? `T${f.turn} ` : ""}${f.rule}: ${f.message}`);
  }
}
