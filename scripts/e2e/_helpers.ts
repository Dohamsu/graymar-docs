/**
 * 그레이마르 E2E 공통 라이브러리
 *
 * - API 호출 (auth / run 생성 / 턴 제출 / 폴링)
 * - Playwright 공통 유틸 (로그인 플로우 · 캐릭터 생성 · 클릭 헬퍼)
 * - V1~V9 자동 검증 (playtest.py 포팅)
 * - 성능 메트릭 수집 (LLM latency · DOM paint)
 *
 * 모든 정본 e2e 스크립트(smoke/full/perf/regression)가 이 모듈을 참조한다.
 */

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";

// ──────────────────────────────────────────────────────────────
// 환경 상수
// ──────────────────────────────────────────────────────────────
export const CLIENT_BASE = process.env.CLIENT_BASE || "http://localhost:3001";
export const SERVER_BASE = process.env.SERVER_BASE || "http://localhost:3000/v1";
export const HEADLESS = process.env.HEADLESS !== "false";
export const VIEWPORT = { width: 1440, height: 900 };
export const DEFAULT_PASSWORD = "Test1234!!";
export const DEFAULT_NICKNAME = "E2ETester";

// ──────────────────────────────────────────────────────────────
// 타입
// ──────────────────────────────────────────────────────────────
export type Resolve = "SUCCESS" | "PARTIAL" | "FAIL";
export type NodeType = "HUB" | "LOCATION" | "COMBAT";

export interface TurnLog {
  turn: number;
  nodeType: string;
  input: string;
  eventId: string;
  resolveOutcome: Resolve | null;
  nodeOutcome: string;
  events: string[];
  narrative: string;
  npcPortrait: { npcId?: string; npcName?: string; imageUrl?: string } | null;
  rawInput: string;
  /** LLM 응답 latency (서버 로그 파싱 or 폴링 간격 추정) */
  latencyMs?: number;
}

export interface RunState {
  hp: number;
  gold: number;
  npcStates: Record<string, any>;
  worldState: {
    hubHeat?: number;
    activeIncidents: any[];
    day?: number;
  };
  memory: {
    structuredMemory?: {
      visitLog: any[];
      npcJournal: Record<string, any>;
    };
    storySummary?: string;
  };
  discoveredQuestFacts: string[];
}

export interface VerifyResult {
  name: string;
  passed: boolean;
  detail: string;
}

// ──────────────────────────────────────────────────────────────
// API 클라이언트 (fetch 기반)
// ──────────────────────────────────────────────────────────────
export class ApiClient {
  private token: string | null = null;
  constructor(private base: string = SERVER_BASE) {}

  async register(email: string, password = DEFAULT_PASSWORD, nickname = DEFAULT_NICKNAME) {
    const r = await this.request("POST", "/auth/register", { email, password, nickname });
    if (r.status === 201 || r.status === 200) {
      this.token = r.body.token;
    } else {
      // 이미 존재하면 로그인
      return this.login(email, password);
    }
    return this.token!;
  }

  async login(email: string, password = DEFAULT_PASSWORD) {
    const r = await this.request("POST", "/auth/login", { email, password });
    if (r.status !== 200 && r.status !== 201) {
      throw new Error(`로그인 실패: ${r.status} ${JSON.stringify(r.body)}`);
    }
    this.token = r.body.token;
    return this.token!;
  }

  async createRun(presetId: string, gender: "male" | "female") {
    const r = await this.request("POST", "/runs", { presetId, gender });
    if (r.status !== 200 && r.status !== 201) {
      throw new Error(`런 생성 실패: ${r.status} ${JSON.stringify(r.body)}`);
    }
    return r.body;
  }

  async getRun(runId: string) {
    const r = await this.request("GET", `/runs/${runId}`);
    return r.body;
  }

  async submitTurn(runId: string, body: any) {
    return this.request("POST", `/runs/${runId}/turns`, body);
  }

  async getTurn(runId: string, turnNo: number, opts: { includeDebug?: boolean } = {}) {
    const qs = opts.includeDebug ? "?includeDebug=true" : "";
    const r = await this.request("GET", `/runs/${runId}/turns/${turnNo}${qs}`);
    return r.body;
  }

  async pollLlm(runId: string, turnNo: number, maxWaitMs = 90_000): Promise<{ output: string; status: string; elapsedMs: number; uiData?: any }> {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      const data = await this.getTurn(runId, turnNo);
      const llm = data?.llm ?? {};
      if (llm.status === "DONE") {
        return {
          output: llm.output || "",
          status: "DONE",
          elapsedMs: Date.now() - start,
          uiData: data.serverResult?.ui,
        };
      }
      if (llm.status === "FAILED" || llm.status === "SKIPPED") {
        return { output: `[LLM_${llm.status}]`, status: llm.status, elapsedMs: Date.now() - start };
      }
      await sleep(2000);
    }
    return { output: "[LLM_TIMEOUT]", status: "TIMEOUT", elapsedMs: Date.now() - start };
  }

  private async request(method: string, path: string, body?: any): Promise<{ status: number; body: any }> {
    const url = `${this.base}${path}`;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    try {
      const res = await fetch(url, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
      const text = await res.text();
      return { status: res.status, body: text ? JSON.parse(text) : {} };
    } catch (e) {
      return { status: 0, body: { error: String(e) } };
    }
  }

  get jwtToken() {
    return this.token;
  }
}

// ──────────────────────────────────────────────────────────────
// Playwright 공통 유틸
// ──────────────────────────────────────────────────────────────
export async function launchBrowser(): Promise<{ browser: Browser; context: BrowserContext; page: Page }> {
  const browser = await chromium.launch({ headless: HEADLESS });
  const context = await browser.newContext({ viewport: VIEWPORT, locale: "ko-KR" });
  const page = await context.newPage();
  return { browser, context, page };
}

/** 타이틀에서 "로그인하기"→AUTH로 이동 후 이메일/패스워드 입력. 실패 시 예외. */
export async function uiLogin(page: Page, email: string, password: string = DEFAULT_PASSWORD) {
  await page.goto(`${CLIENT_BASE}/play`);
  await page.waitForTimeout(3500); // 로고 드로잉 대기
  // "시작하기" 또는 "로그인" 버튼 클릭 (비로그인 상태)
  const startBtn = page.locator('button:has-text("시작하기")').first();
  if (await startBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await startBtn.click();
    await page.waitForTimeout(1500);
  }
  // 이메일 입력
  const emailInput = page.locator('input[name="email"], input[type="email"], input[placeholder*="email" i]').first();
  await emailInput.waitFor({ state: "visible", timeout: 10_000 });
  await emailInput.fill(email);
  const pwInput = page.locator('input[type="password"]').first();
  await pwInput.fill(password);
  // 로그인 버튼
  await clickText(page, "로그인");
  // TITLE 복귀 대기
  await page.waitForTimeout(3000);
}

/** 신규 회원가입 플로우 (로그인 화면의 "가입" 탭) */
export async function uiRegister(page: Page, email: string, password: string = DEFAULT_PASSWORD, nickname: string = DEFAULT_NICKNAME) {
  await page.goto(`${CLIENT_BASE}/play`);
  await page.waitForTimeout(3500);
  const startBtn = page.locator('button:has-text("시작하기")').first();
  if (await startBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await startBtn.click();
    await page.waitForTimeout(1500);
  }
  // "회원가입" 탭
  await clickText(page, "회원가입");
  await page.waitForTimeout(500);
  await page.locator('input[name="email"], input[type="email"], input[placeholder*="email" i]').first().fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  const nickInput = page.locator('input[placeholder*="닉네임" i], input[name="nickname"]').first();
  if (await nickInput.isVisible({ timeout: 1500 }).catch(() => false)) {
    await nickInput.fill(nickname);
  }
  await clickText(page, "가입하기");
  await page.waitForTimeout(3000);
}

/** 텍스트로 버튼 클릭 (여러 스크립트 중복 헬퍼 통합) */
export async function clickText(
  page: Page,
  text: string,
  opts: { force?: boolean; timeout?: number; nth?: number } = {},
): Promise<boolean> {
  const locator = page.locator(`button:has-text("${text}"), a:has-text("${text}")`).nth(opts.nth ?? 0);
  try {
    await locator.waitFor({ state: "visible", timeout: opts.timeout ?? 5000 });
    await locator.click({ force: opts.force, timeout: 5000 });
    return true;
  } catch {
    return false;
  }
}

export async function waitForNarrativeText(page: Page, minLength = 50, timeoutMs = 30_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const txt = await page.locator("main, [role='main'], body").innerText().catch(() => "");
    if (txt.length >= minLength) return true;
    await sleep(500);
  }
  return false;
}

export function sleep(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms));
}

// ──────────────────────────────────────────────────────────────
// 플레이 유틸 — API로 플레이테스트 시나리오 실행
// ──────────────────────────────────────────────────────────────
export const ACTIONS = [
  "주변을 살펴본다",
  "사람들에게 말을 건다",
  "수상한 곳을 조사한다",
  "조심스럽게 잠입한다",
  "거래를 시도한다",
  "소문의 진위를 확인한다",
  "경비병의 동태를 살핀다",
];

export const HUB_LOCATIONS = ["market", "guard", "harbor", "slums"];

export function randomUuid() {
  return ((globalThis as any).crypto?.randomUUID?.() as string) ?? `${Date.now()}-${Math.random()}`;
}

/** LOCATION/HUB 구분해서 턴 입력 자동 생성. choice 확률 0.3 기본. */
export function pickTurnInput(
  state: any,
  lastResult: any,
  opts: { locIdx: number; locTurns: number; locLimit: number; choiceRate: number },
): { body: any; description: string } {
  const idem = randomUuid();
  const currentTurn = state?.run?.currentTurnNo ?? 1;
  const nodeType = state?.currentNode?.nodeType ?? "";
  const choices = lastResult?.choices ?? [];

  if (nodeType === "HUB") {
    const locName = HUB_LOCATIONS[opts.locIdx % HUB_LOCATIONS.length];
    let target = choices.find((c: any) => (c.id ?? "").toLowerCase().includes(locName))
      ?? choices.find((c: any) => /accept|quest/i.test(c.id ?? ""))
      ?? choices.find((c: any) => /go_|loc_/i.test(c.id ?? ""))
      ?? choices[0];
    if (target) {
      return {
        body: { input: { type: "CHOICE", choiceId: target.id }, expectedNextTurnNo: currentTurn + 1, idempotencyKey: idem },
        description: `CHOICE:${target.id}`,
      };
    }
  }
  if (nodeType === "COMBAT") {
    return {
      body: { input: { type: "ACTION", text: "정면에서 검을 휘두른다" }, expectedNextTurnNo: currentTurn + 1, idempotencyKey: idem },
      description: "ACTION:combat_attack",
    };
  }
  // LOCATION
  if (opts.locTurns >= opts.locLimit) {
    return {
      body: { input: { type: "ACTION", text: "다른 장소로 이동한다" }, expectedNextTurnNo: currentTurn + 1, idempotencyKey: idem },
      description: "ACTION:move_location",
    };
  }
  const hasLocChoice = choices.filter((c: any) => c.id !== "go_hub");
  if (hasLocChoice.length && Math.random() < opts.choiceRate) {
    const c = hasLocChoice[Math.floor(Math.random() * hasLocChoice.length)];
    return {
      body: { input: { type: "CHOICE", choiceId: c.id }, expectedNextTurnNo: currentTurn + 1, idempotencyKey: idem },
      description: `CHOICE:${c.id}`,
    };
  }
  const action = ACTIONS[Math.floor(Math.random() * ACTIONS.length)];
  return {
    body: { input: { type: "ACTION", text: action }, expectedNextTurnNo: currentTurn + 1, idempotencyKey: idem },
    description: `ACTION:${action.slice(0, 20)}`,
  };
}

// ──────────────────────────────────────────────────────────────
// 검증 V1~V9 (playtest.py 포팅)
// ──────────────────────────────────────────────────────────────
const LEAK_PATTERNS: [RegExp, string][] = [
  [/시도하여\s?(?:성공|실패)/g, "행동 결과 복붙"],
  [/활성 단서:/g, "활성 단서 태그 노출"],
  [/턴\s?\d+에서/g, "턴 번호 노출"],
  [/플레이어가\s/g, "플레이어 3인칭"],
  [/\[이번 턴/g, "프롬프트 블록 노출"],
  [/\[판정:/g, "판정 블록 노출"],
  [/\[상황 요약\]/g, "상황 요약 태그 노출"],
  [/\[서술 규칙\]/g, "서술 규칙 태그 노출"],
  [/엔진 해석:/g, "엔진 해석 노출"],
];

const COMMON_WORDS = new Set([
  "당신", "당신은", "당신의", "당신이", "당신을", "그는", "그의", "있다", "없다", "있었",
  "하고", "에서", "으로", "이다", "했다", "하는", "것이", "있는", "위에", "앞에", "속에",
  "조용한", "낡은", "어두운", "시장", "경비", "경비대", "항만", "부두", "선술집", "골목", "창고",
]);

export function verifyRun(state: any, turnLogs: TurnLog[]): VerifyResult[] {
  const results: VerifyResult[] = [];
  const runState = state?.runState ?? {};
  const npcStates: Record<string, any> = runState.npcStates ?? {};
  const worldState = runState.worldState ?? {};
  const memory = state?.memory ?? {};
  const structured = memory.structuredMemory ?? null;

  // V1: Incidents
  const incidents: any[] = worldState.activeIncidents ?? [];
  results.push({ name: "V1_incidents", passed: incidents.length > 0, detail: `${incidents.length}건 활성` });

  // V2: NPC encounter
  const encCount = Object.values(npcStates).filter((n: any) => (n.encounterCount ?? 0) > 0).length;
  results.push({ name: "V2_encounter", passed: encCount >= 2, detail: `${encCount}명 encounter` });

  // V3: posture 누락
  const postureNone = Object.values(npcStates).filter((n: any) => n.posture == null).length;
  results.push({ name: "V3_posture", passed: postureNone === 0, detail: `누락 ${postureNone}명` });

  // V4: 감정축 활성
  const emoActive = Object.values(npcStates).filter((n: any) => {
    const e = n.emotional ?? {};
    return (e.trust ?? 0) !== 0 || (e.fear ?? 0) !== 0;
  }).length;
  results.push({ name: "V4_emotion", passed: emoActive > 0, detail: `${emoActive}명 활성` });

  // V5: structuredMemory
  const visitLogLen = structured?.visitLog?.length ?? 0;
  results.push({ name: "V5_memory", passed: visitLogLen > 0, detail: `visitLog ${visitLogLen}건` });

  // V6: resolveOutcome 포함 턴
  const resolveCount = turnLogs.filter((t) => t.resolveOutcome).length;
  results.push({ name: "V6_resolve", passed: resolveCount > 0, detail: `${resolveCount}/${turnLogs.length}턴` });

  // V7: 프롬프트 누출
  const leaks: string[] = [];
  for (const t of turnLogs) {
    for (const [pat, label] of LEAK_PATTERNS) {
      if (pat.test(t.narrative)) {
        leaks.push(`T${t.turn}: ${label}`);
        pat.lastIndex = 0;
      }
    }
  }
  results.push({ name: "V7_no_leak", passed: leaks.length === 0, detail: leaks.length ? leaks.slice(0, 5).join(" · ") : "누출 없음" });

  // V8: NPC 정합성 — npcPortrait.npcId가 서술 @마커와 일치
  const mismatches: string[] = [];
  for (const t of turnLogs) {
    const portrait = t.npcPortrait;
    if (!portrait?.npcId) continue;
    const markers = Array.from(t.narrative.matchAll(/@([A-Z][A-Z_0-9]+)\s/g), (m) => m[1]);
    const brackets = Array.from(t.narrative.matchAll(/@\[([^\]|]+)/g), (m) => m[1]);
    const hit = markers.includes(portrait.npcId)
      || brackets.some((b) => portrait.npcName && b.includes(portrait.npcName))
      || (portrait.npcName ? t.narrative.includes(portrait.npcName) : false);
    if (!hit && t.narrative && !t.narrative.startsWith("[LLM_")) {
      mismatches.push(`T${t.turn}: ${portrait.npcName}(${portrait.npcId}) 서술에 없음`);
    }
  }
  results.push({ name: "V8_npc_match", passed: mismatches.length === 0, detail: mismatches.length ? mismatches.slice(0, 3).join(" · ") : "정합성 양호" });

  // V9: 서술 품질 — 단어 반복 (3턴 윈도우 5회+)
  const repeats: string[] = [];
  for (let i = 2; i < turnLogs.length; i++) {
    const window = turnLogs.slice(Math.max(0, i - 2), i + 1).map((t) => t.narrative).join(" ").replace(/@\[[^\]]+\]/g, "");
    const words = window.match(/[가-힣]{2,4}/g) ?? [];
    const counts = new Map<string, number>();
    for (const w of words) counts.set(w, (counts.get(w) ?? 0) + 1);
    for (const [w, c] of counts) {
      if (c >= 5 && !COMMON_WORDS.has(w) && w.length >= 2) {
        repeats.push(`T${turnLogs[i].turn}: '${w}' ${c}회`);
        break;
      }
    }
  }
  results.push({ name: "V9_quality", passed: repeats.length <= 2, detail: repeats.length ? repeats.slice(0, 3).join(" · ") : "양호" });

  return results;
}

export function printVerifyReport(results: VerifyResult[]): number {
  const passed = results.filter((r) => r.passed).length;
  console.log("\n" + "═".repeat(60));
  console.log(`검증 ${passed}/${results.length} PASS`);
  console.log("═".repeat(60));
  for (const r of results) {
    const icon = r.passed ? "✅" : "❌";
    console.log(`  ${icon} ${r.name.padEnd(18)} ${r.detail}`);
  }
  return passed;
}

// ──────────────────────────────────────────────────────────────
// 메트릭 수집
// ──────────────────────────────────────────────────────────────
export interface PerfMetrics {
  latencies: number[];
  avgLatency: number;
  minLatency: number;
  maxLatency: number;
  totalTurns: number;
  totalElapsedMs: number;
  avgCharsPerTurn: number;
}

export function summarize(turnLogs: TurnLog[], totalElapsedMs: number): PerfMetrics {
  const latencies = turnLogs.map((t) => t.latencyMs ?? 0).filter((x) => x > 0);
  const chars = turnLogs.map((t) => t.narrative.length).filter((x) => x > 0);
  const sum = (arr: number[]) => arr.reduce((a, b) => a + b, 0);
  return {
    latencies,
    avgLatency: latencies.length ? Math.round(sum(latencies) / latencies.length) : 0,
    minLatency: latencies.length ? Math.min(...latencies) : 0,
    maxLatency: latencies.length ? Math.max(...latencies) : 0,
    totalTurns: turnLogs.length,
    totalElapsedMs,
    avgCharsPerTurn: chars.length ? Math.round(sum(chars) / chars.length) : 0,
  };
}

export function printPerfReport(m: PerfMetrics) {
  console.log("\n── 성능 메트릭 ──");
  console.log(`  턴 수:      ${m.totalTurns}`);
  console.log(`  총 시간:    ${(m.totalElapsedMs / 1000).toFixed(1)}s`);
  console.log(`  턴당 평균:  ${(m.totalElapsedMs / m.totalTurns / 1000).toFixed(1)}s`);
  console.log(`  LLM avg:    ${m.avgLatency}ms  (min ${m.minLatency}, max ${m.maxLatency})`);
  console.log(`  서술 평균:  ${m.avgCharsPerTurn}자/턴`);
}
