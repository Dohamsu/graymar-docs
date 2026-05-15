# 47. Narrative Pipeline Audit (NPA) — Dialogue Quality 1순위

> **목표**: 사용자와 NPC 간 대화 품질을 정밀 감사. 단순 기능 PASS/FAIL이 아니라 "이전 발화와 연결되는가, 주제에 갇히지 않는가, 사람답게 말하는가"를 측정.
> **위치**: `scripts/e2e/audit/` — 정본 5번째 e2e (smoke / full-run / perf / regression / **audit**).
> **선행**: architecture/45 (자유 대화) + 46 (Fact 일급화 + Continuity).
> **작성**: 2026-04-27

---

## 1. 동기

### 1.1 기존 e2e의 한계

- `smoke.ts` — 3턴 기본 동작 (대화 품질 측정 X)
- `full-run.ts` — 35턴 V1~V9 (이벤트/상태 검증, 발화 자체는 unique 카운트만)
- `regression.ts` — UI 회귀 (텍스트 내용 미평가)

→ **"대화가 자연스러운가" 자체를 측정하는 도구 부재**

### 1.2 측정 대상 (사용자 정의 1순위)

같은 NPC와의 연속 대화에서:
1. **연결성 (Continuity)** — 이전 NPC 발화/사용자 발화를 참조/기억하는가
2. **주제 자유도 (Topic Freedom)** — fact/quest 강제 주입 없이 다양한 화제 가능한가
3. **사람다움 (Humanity)** — 기계적/명령적 톤이 아닌 인격체로 말하는가

### 1.3 보조 자료 — Pipeline Trace

각 턴마다 3 레이어 데이터 수집해 수동 review에 활용:
1. LLM 입력 프롬프트 (블록별 분리 + 토큰 수)
2. LLM 원본 출력 (마커/대사/서술 분리)
3. 후처리 + 렌더 결과 (speakingNpc / actionContext / DialogueBubble 텍스트)

---

## 2. 명명 / 위치

- 약어: **NPA** (Narrative Pipeline Audit)
- 파일 구조:

```
scripts/e2e/audit/
├── audit.ts                  # 실행 엔진 (CLI)
├── dialogue-quality.ts       # ⭐ 1순위 평가 모듈
├── pipeline-trace.ts         # 보조: 3-레이어 캡처
├── auto-verifier.ts          # 자동 ERROR/WARNING 검출
├── reporter.ts               # 마크다운 + JSON 출력
├── types.ts                  # 공유 타입 (DialoguePair / AuditReport)
└── scenarios/
    ├── dialog-handoff.ts     # 시나리오 1: 미렐라 인계 흐름
    ├── fact-progression.ts   # 시나리오 2: 같은 NPC 다양한 fact
    ├── npc-continuity.ts     # 시나리오 3: 잡담→fact→잡담 전환
    └── README.md             # 시나리오 작성 가이드
```

- CLI:
```bash
pnpm exec tsx scripts/e2e/audit/audit.ts \
  --scenario dialog-handoff \
  --output playtest-reports/audit-2026-04-27.md
```

---

## 3. 데이터 모델

### 3.1 AuditScenario (시나리오 정의)

```ts
export interface AuditScenario {
  /** 시나리오 식별자 (CLI --scenario 인자) */
  id: string;
  /** 사람용 이름 */
  name: string;
  /** 시나리오 의도 설명 (리포트 헤더에 표시) */
  intent: string;
  /** 게임 설정 */
  preset: 'DESERTER' | 'SMUGGLER' | 'HERBALIST' | 'FALLEN_NOBLE' | 'GLADIATOR' | 'DOCKWORKER';
  gender: 'male' | 'female';
  /** 초기 setup 입력 (HUB → location 진입 등, 평가 제외) */
  setup: Array<
    | { type: 'CHOICE'; choiceId: string }
    | { type: 'ACTION'; text: string }
  >;
  /** 평가 대상 턴 시퀀스 */
  turns: AuditTurn[];
  /** 같은 NPC와의 연속 대화 기대 (점프 0 목표) */
  expectSameNpc?: boolean;
}

export interface AuditTurn {
  input: string;
  /** 의도된 모드 (자동 검증 비교용, optional) */
  expectMode?: 'A_FACT' | 'B_HANDOFF' | 'C_DEFAULT' | 'D_CHAT';
  /** 의도된 NPC 호명 (자동 검증) */
  expectNpcId?: string;
  /** 사람용 메모 (리포트 표시) */
  note?: string;
}
```

### 3.2 DialoguePair (수집 단위)

각 평가 턴 = 1 pair:

```ts
export interface DialoguePair {
  turn: number;
  /** 사용자 입력 */
  userInput: string;
  parsedActionType: string | null;

  /** 서버 결정된 화자 */
  speakerNpcId: string | null;
  speakerDisplayName: string | null;

  /** NPC 발화 (대사만 추출, 서술 제외) */
  npcUtterances: Array<{
    text: string;          // 따옴표 안 대사
    npcName: string;       // @[이름|...]의 이름
    npcImage?: string;
  }>;
  /** 서술 부분 (대사 제외 본문) */
  narration: string;
  /** 원본 LLM 출력 (마커 포함) */
  rawOutput: string;

  /** 프롬프트 메타 (Pipeline Trace) */
  prompt: {
    totalTokens: number;
    blocks: Array<{ name: string; preview: string; tokens: number }>;
  };

  /** 모드 검출 (factHandoffHint / npcRevealableFact / chat 등) */
  detectedMode: 'A_FACT' | 'B_HANDOFF' | 'C_DEFAULT' | 'D_CHAT' | 'NONE';

  /** 메타데이터 */
  resolveOutcome: 'SUCCESS' | 'PARTIAL' | 'FAIL' | null;
  eventId: string | null;
  llmLatencyMs: number;
}
```

### 3.3 AuditReport

```ts
export interface AuditReport {
  scenario: AuditScenario;
  startedAt: string;
  totalElapsedMs: number;
  serverVersion: string;

  pairs: DialoguePair[];

  /** ⭐ 1순위 평가 */
  dialogueQuality: {
    continuity: ContinuityScore;
    topicFreedom: TopicFreedomScore;
    humanity: HumanityScore;
    /** 종합 5점 만점 */
    overall: number;
  };

  /** 자동 검출 결과 */
  errors: AuditFinding[];
  warnings: AuditFinding[];
  infos: AuditFinding[];

  /** 사용자 입장에서 본 흐름 (수동 review용) */
  flow: Array<{ turn: number; speaker: string; text: string }>;
}

export interface AuditFinding {
  turn?: number;
  rule: string;        // 예: "MARKER_NPCID_NULL"
  message: string;
  severity: 'ERROR' | 'WARNING' | 'INFO';
}
```

---

## 4. ⭐ 1순위 모듈 — Dialogue Quality

### 4.1 Continuity (연결성)

이전 발화를 NPC가 기억/참조하는가.

**측정**:
- **이전 키워드 등장률** — 직전 N턴 NPC 발화의 한글 명사 2자+ 추출 → 현재 발화에 등장 비율
- **호칭 일관성** — NPC가 사용자를 부르는 호칭 ("그대"/"자네" 등) 변동 없음
- **어조 일관성** — speechStyle 어미 패턴(~네/~하오/~소) 유지율
- **사용자 질문 응답률** — 사용자 입력의 핵심 명사가 NPC 응답에 등장 (회피 패턴 검출)

**점수 계산** (0~5):
```
keywordCarryOverRate * 2.0    # 0~2
+ pronounConsistency * 1.0    # 0~1
+ toneConsistency * 1.0       # 0~1
+ userResponseRate * 1.0      # 0~1
```

### 4.2 Topic Freedom (주제 자유도)

fact/quest에 묶이지 않고 다양한 화제 가능한가.

**측정**:
- **모드 분포** — A(fact) / B(인계) / C(default) / D(잡담) 비율
  - 이상적: 잡담 40~60%, fact 20~40%, 나머지 보조
  - 우려: fact 70%+ (강제 주입 의심)
- **화제 카테고리** — daily_topics 카테고리(WORK/PERSONAL/GOSSIP/OPINION/WORRY) 분포
  - 균등할수록 좋음
- **동일 fact 반복** — 같은 factId 2회+ 노출 ⚠️
- **fact 강제도** — 키워드 매칭 안 됐는데 fact 공개됐는지

**점수**:
```
modeBalance * 2.0           # 0~2 (잡담:fact:기타 = 4:3:3 근사)
+ topicVariety * 1.5        # 0~1.5 (카테고리 다양성, 엔트로피)
+ noFactRepeat * 1.5        # 0~1.5 (같은 fact 0회 = 1.5)
```

### 4.3 Humanity (사람다움)

기계적 톤이 아닌 인격체로 말하는가.

**측정**:
- **회피 어휘 빈도** — "위험"/"곤란"/"조심하"/"입을 닫"/"함부로" 등장 비율
- **명령조 비율** — "~하라/~하지 마라" vs "~한다네/~하더이다" 등 자연 어미
- **NPC 고유 어휘** — speechStyle.signature 또는 personality.traits 키워드 등장
  - 예: 미렐라 → "약초/뿌리/할미", 하를런 → "부두/형제단/주먹"
- **비유/예시 사용** — daily_topics식 비유 ("독초 같은", "썩은 뿌리처럼") 등장
- **반복 표현** — 같은 표현 N턴 동안 2회+ 등장 (기계적 신호)

**점수**:
```
(1 - avoidWordRate) * 1.0   # 0~1
+ (1 - imperativeRate) * 1.0 # 0~1
+ npcSignatureRate * 1.5     # 0~1.5
+ metaphorUsageRate * 1.0    # 0~1
+ (1 - repetitionRate) * 0.5 # 0~0.5
```

### 4.4 종합 점수 (5점 만점)

```
overall = (continuity + topicFreedom + humanity) / 3
```

- ★★★★★ (4.5+): 우수 — 사람과 거의 구분 안 됨
- ★★★★☆ (3.5~4.5): 양호
- ★★★☆☆ (2.5~3.5): 보통 — 개선 여지
- ★★☆☆☆ (1.5~2.5): 부자연스러움
- ★☆☆☆☆ (~1.5): 기계적

---

## 5. 보조 모듈 — Pipeline Trace

각 페어에 부가 데이터 첨부 (수동 review용):

### 5.1 입력 프롬프트 분석

`includeDebug=true` API 호출 → user 메시지 추출 → 정규식 기반 블록 분리:
```ts
const BLOCK_PATTERNS = [
  { name: '상황 요약',          re: /\[상황 요약\][\s\S]*?(?=\[|$)/ },
  { name: 'NPC 정보',           re: /\[NPC 정보\][\s\S]*?(?=\[|$)/ },
  { name: 'fact 공개',          re: /\[이번 턴 NPC가 공개할 정보\][\s\S]*?(?=\[|$)/ },
  { name: '인계 가이드',         re: /\[NPC 모름 — 인계 가이드\][\s\S]*?(?=\[|$)/ },
  { name: 'default 텍스트',     re: /\[일반 정보 — 도시 분위기\][\s\S]*?(?=\[|$)/ },
  { name: 'NPC 일상 화제',      re: /\[NPC 일상 화제[\s\S]*?(?=\[|$)/ },
  { name: '활성 단서',           re: /\[활성 단서\][\s\S]*?(?=\[|$)/ },
  { name: '시간 / 장소',        re: /\[현재 시간\][\s\S]*?(?=\[|$)/ },
  { name: 'recentTopics',       re: /\[최근 대화 주제\][\s\S]*?(?=\[|$)/ },
  // ...
];
```

### 5.2 LLM 출력 파싱

- `@[NPC|URL] "대사"` 마커 → DialoguePair.npcUtterances
- 마커 외 본문 → narration
- 마커 형식 깨짐 검출 → ERROR

### 5.3 후처리 + 렌더

- DB의 server_result.ui.speakingNpc / npcPortrait / actionContext
- 클라이언트 렌더는 시뮬레이션 (StoryBlock의 renderStyledText 로직 참고)

---

## 6. 자동 검증 — 3-tier (ERROR / WARNING / INFO)

### 6.1 ERROR (명백 결함)

| Rule | 검출 |
|---|---|
| `MARKER_NPCID_NULL` | speakingNpc.npcId === null이고 displayName 있음 (architecture/46 회귀) |
| `MARKER_FORMAT_BROKEN` | `@[...]` 마커 정규식 매칭 실패 |
| `NPC_JUMP_NO_HONORIFIC` | 사용자 입력에 NPC 호명 없는데 NPC 변경 |
| `TOKEN_EXPLOSION` | 프롬프트 토큰 ≥ 13,000 (Gemini Flash 입력 제한 근접) |
| `FACT_BLOCK_NO_KEYWORD_MATCH` | `[이번 턴 NPC가 공개할 정보]` 블록 있는데 입력에 키워드 0개 |
| `LLM_FAILED` | LLM 응답 FAILED/TIMEOUT |

### 6.2 WARNING (의심)

| Rule | 검출 |
|---|---|
| `AVOID_WORD_HEAVY` | 회피 어휘 비율 ≥ 30% |
| `SAME_FACT_REPEATED` | 같은 factId 2회+ 노출 |
| `PRONOUN_INCONSISTENT` | NPC가 사용자 호칭 변경 ("그대" → "자네" 등) |
| `TONE_DRIFT` | speechStyle 어미 60% 미만 일치 |
| `LOW_USER_RESPONSE` | 사용자 핵심 명사 NPC 응답에 등장 비율 < 30% |
| `MODE_IMBALANCE` | fact 모드 비율 ≥ 70% (강제 주입 의심) |

### 6.3 INFO (데이터)

| Rule | 데이터 |
|---|---|
| `TOKEN_USAGE` | 평균 프롬프트 토큰 / 출력 토큰 |
| `MODE_DISTRIBUTION` | A/B/C/D 비율 |
| `NPC_DISTRIBUTION` | 등장 NPC별 발화 수 |
| `LATENCY` | 평균 / max / p95 LLM latency |
| `WORD_COUNT` | 평균 발화 자수 |

---

## 7. 리포트 — 마크다운 + JSON

### 7.1 마크다운 구조 (Dialogue Quality 첫 페이지)

```markdown
# Dialogue Quality Audit — 미렐라 장부 인계 흐름
**서버**: 6f523c3 (2026-04-27 14:00) | **시나리오**: dialog-handoff | **소요**: 2분 14초

## ⭐ 종합 점수
- **연결성**: ★★★★☆ (4.0 / 5)
- **자유도**: ★★★★★ (4.6 / 5)
- **사람다움**: ★★★★☆ (4.2 / 5)
- **종합**: ★★★★☆ (4.3 / 5)

## 자동 검출 요약
- ❌ ERROR: 0건
- ⚠️ WARNING: 2건 (T6 회피 어휘 / T8 같은 fact 재공개)
- ℹ️ INFO: 8건

## 대화 흐름
| T | 사용자 | NPC | 모드 | 평가 |
|---|---|---|---|---|
| 4 | 약초 노점에 다가간다 | 미렐라 | (setup) | ✅ 첫 만남 |
| 5 | 오늘 시장 분위기 어떻소? | 미렐라 | D 잡담 | ✅ 약초 비유 ("뿌리가 상한") |
| 6 | 사라진 장부에 대해 들었소? | 미렐라 | A fact | ⚠️ 회피 어휘 ("위험") |
| 7 | 동쪽 부두 일은? | 미렐라 | B 인계 | ✅ "독초 같은 곳..." |
| 8 | 임금 문제는? | 미렐라 | A fact | ⚠️ 같은 fact 재공개 |

## 자동 검증 상세
### Warnings
- ⚠️ [T6 / AVOID_WORD_HEAVY] 회피 어휘 "위험" 등장. NPC 답변 30%가 회피 톤.
- ⚠️ [T8 / SAME_FACT_REPEATED] FACT_LEDGER_EXISTS T6에 이미 공개됐음.

## 분석 모듈

### 연결성 (4.0)
- 키워드 carry-over: 65% (★★★)
- 호칭 일관: "그대" 8/8 (★★★★★)
- 어조: ~네/~다네/~소 90% 유지 (★★★★)
- 사용자 응답률: 75% (★★★★)

### 자유도 (4.6)
- 모드: D 50% / A 25% / B 25% (이상적 분포 4:3:3 근사)
- 카테고리: WORK 1, PERSONAL 2, GOSSIP 2, OPINION 1, WORRY 0
- fact 반복: 1건 (T6→T8)

### 사람다움 (4.2)
- 회피 어휘: 12% (T6 한 건만)
- 명령조: 5%
- NPC 고유 어휘 ("약초/뿌리/할미"): 6/8 턴
- 비유 사용: 4건

## Pipeline Trace (보조)
[각 턴 펼치기]

### T5 ↘
**프롬프트** (8,234 token)
- [상황 요약] (300t) ...
- [NPC 일상 화제] (180t) ⭐ "이 시장에 자리 잡은 게 마흔 해 전이야..."

**LLM 원본**
@[미렐라|/npc-portraits/mirela.webp] "겉보기엔 평온해 보일지 모르나..."

**후처리/렌더**
speakingNpc: NPC_MIRELA / DialogueBubble: "겉보기엔..."

## 사용자 발화 vs NPC 발화 흐름 (수동 review용)
[T4] 사용자: "약초 노점에 다가간다"
       NPC : "그대, 안색이 창백하구먼..."
[T5] 사용자: "오늘 시장 분위기 어떻소?"
       NPC : "겉보기엔 평온해 보일지 모르나..."
...
```

### 7.2 JSON 구조

`AuditReport` 인터페이스 그대로 직렬화. 회귀 비교 / 메트릭 추출용.

저장 경로: `playtest-reports/audit_<scenario>_<YYYYMMDD_HHmmss>.{md,json}`

---

## 8. 시나리오 작성 가이드

### 8.1 기본 형식

```ts
// scripts/e2e/audit/scenarios/dialog-handoff.ts
import type { AuditScenario } from '../types';

export const scenario: AuditScenario = {
  id: 'dialog-handoff',
  name: '미렐라 장부 인계 흐름',
  intent: '같은 NPC(미렐라)와 잡담↔fact↔인계 모드 전환 시 자연스러움 평가',
  preset: 'DESERTER',
  gender: 'male',
  setup: [
    { type: 'CHOICE', choiceId: 'accept_quest' },
    { type: 'CHOICE', choiceId: 'go_market' },
    { type: 'ACTION', text: '약초 노점에 다가간다' },
  ],
  turns: [
    { input: '오늘 시장 분위기 어떻소?',     expectMode: 'D_CHAT' },
    { input: '사라진 장부에 대해 들었소?',  expectMode: 'A_FACT', expectNpcId: 'NPC_MIRELA' },
    { input: '동쪽 부두 일은?',              expectMode: 'B_HANDOFF' },
    { input: '임금 문제는?',                 expectMode: 'A_FACT' },
    { input: '당신 가족이 있소?',            expectMode: 'D_CHAT' },
    { input: '약초는 어떻게 키우시오?',      expectMode: 'D_CHAT' },
    { input: '밀수에 대해 들은 게 있소?',   expectMode: 'B_HANDOFF' },
    { input: '오늘 정말 고맙소.',            expectMode: 'D_CHAT' },
  ],
  expectSameNpc: true,
};
```

### 8.2 표준 시나리오 3종 (P0)

| 시나리오 | 목적 |
|---|---|
| `dialog-handoff` | 모드 A/B/D 전환 + NPC 일관성 |
| `fact-progression` | 한 NPC와 여러 fact 자연 진행 |
| `npc-continuity` | 잡담→fact→잡담→이동→복귀 흐름 |

### 8.3 NPC별 시나리오 추가 (P1)

CORE 6 NPC 각각 시나리오 1개 추가 가능 — 각 NPC personality 발현 평가용.

---

## 9. 구현 단계

### Phase 1 — MVP (3시간)
- [ ] `types.ts` (AuditScenario / DialoguePair / AuditReport)
- [ ] `audit.ts` 실행 엔진 (시나리오 로드, 턴 실행, 데이터 수집)
- [ ] `pipeline-trace.ts` (3-레이어 캡처)
- [ ] `dialogue-quality.ts` Continuity / TopicFreedom / Humanity 산출
- [ ] `auto-verifier.ts` 6 ERROR + 6 WARNING 룰
- [ ] `reporter.ts` 마크다운 + JSON 출력
- [ ] `scenarios/dialog-handoff.ts` 1개 작성
- [ ] CLI: `pnpm exec tsx scripts/e2e/audit/audit.ts --scenario dialog-handoff`

### Phase 2 — 시나리오 확장 (1시간)
- [ ] `fact-progression.ts`
- [ ] `npc-continuity.ts`

### Phase 3 — 정밀화 (반나절)
- [ ] HTML 리포트 (선택, P2)
- [ ] 회귀 비교 (`audit-diff.ts` — 두 JSON 비교)
- [ ] CORE 6 NPC 시나리오 6개 (P1)

---

## 10. 위험 및 완화

| 위험 | 완화 |
|---|---|
| LLM 변동성으로 점수 들쭉날쭉 | 같은 시나리오 3회 평균 / median 옵션 |
| 자동 검증 false positive | 3-tier로 나누고 ERROR만 strict |
| 수동 review 부담 | 마크다운 첫 페이지에 Quality 점수만 (상세는 펼치기) |
| 토큰 비용 (NPA 자체가 LLM 호출 다수) | 시나리오당 10턴 이내 / 자주 안 돌림 |
| 회피 어휘 화이트리스트 부족 | 우선 6개 (위험/곤란/조심/입을 닫/함부로/위태) — 점진 확장 |

---

## 11. 측정 메트릭 — 도입 후 목표

| 지표 | 베이스라인 | 목표 |
|---|---|---|
| 종합 점수 | ? (측정 시작) | 4.0+ (★★★★) |
| ERROR | 0건 (회귀 없음) | 0 유지 |
| WARNING | 시나리오당 평균 | 줄이기 |
| 잡담 모드 비율 | 30~40% | 40~60% |
| fact 반복 | 측정 시작 | 0~1회/시나리오 |
| 회피 어휘 | 측정 시작 | 시나리오당 ≤ 1건 |

---

## 12. Open Questions

### Q1. NPC 고유 어휘 사전을 어떻게 채울 것인가?
- A. NPC 콘텐츠(personality.signature, traits)에서 자동 추출
- B. 시나리오에 명시 (NPC_MIRELA → ["약초", "뿌리", "할미"])
- 추천 A — 콘텐츠 일관성

### Q2. 자동 검증 룰 추가 시점?
- 사용자 피드백 받으면서 점진 추가
- ERROR는 보수적, WARNING은 공격적

### Q3. Quality 점수 가중치 조정?
- 사용자 피드백에 따라 (Continuity 1.5x 등)

### Q4. CI 통합?
- Phase 3 이후 검토 (수동 실행만으로 시작)

---

## 13. 관련 문서

- [[architecture/45_npc_free_dialogue|npc free dialogue]] — daily_topics 기반 잡담 (Topic Freedom 토대)
- [[architecture/46_fact_pool_continuity|fact pool continuity]] — Fact 분리 + Continuity (Continuity 토대)
- [[architecture/26_narrative_pipeline_v2|narrative pipeline v2]] — 3-Stage Pipeline (Pipeline Trace 토대)
- `scripts/e2e/README.md` — 정본 e2e 4종 (audit 추가 위치)
- `scripts/playtest.py` — V1~V9 검증 (자동 검증 룰 일부 재사용 가능)
