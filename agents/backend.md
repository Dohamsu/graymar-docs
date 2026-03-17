# Backend Agent

> Role: 게임 서버 전담. 모든 게임 로직을 결정적으로 처리하고, LLM 서술을 비동기로 생성한다. 서버가 Source of Truth다.

---

## Tech Stack

| 기술 | 버전/옵션 | 용도 |
|------|----------|------|
| **NestJS** | v11+ | 프레임워크 (모듈, DI, Guard, Interceptor, Pipe) |
| **Fastify** | NestJS adapter | HTTP 서버 (Express 대비 2~3배 throughput) |
| **TypeScript** | strict mode | 전체 코드 |
| **BullMQ** | v5+ | LLM 서술 생성 Worker 큐 |
| **Redis** | v7+ | BullMQ 백엔드, 멱등성 캐시, 분산 락 |
| **Drizzle ORM** | — | DB 접근 (Database Agent가 스키마 정의) |
| **Zod** | — | 입력 검증, runtime 타입 가드 |

---

## 핵심 책임

### 1. 턴 처리 파이프라인

`POST /v1/runs/{runId}/turns` — 12단계 순차 처리 (정본: `design/server_api_system.md` §2.1)

```
1. idempotencyKey 확인 (Redis SET NX 또는 DB)
2. expectedNextTurnNo 검증
3. 입력 타입 분기 (ACTION / CHOICE / SYSTEM)
4. Rule Parser 실행 (70~85% 처리)
5. (confidence < 0.7) LLM Intent Parser (fallback)
6. Intent Merge (RULE / LLM / MERGED)
7. Policy Check (ALLOW / TRANSFORM / PARTIAL / DENY)
8. Action DSL 생성
9. 수치 판정 수행 (Combat Resolve / Node Resolve)
10. server_result_v1 생성
11. DB 원자 커밋 (turn + battle_state + run)
12. BullMQ에 LLM 서술 작업 enqueue
13. 즉시 응답 반환
```

### 2. 전투 엔진 (Combat Resolve)

단일 진입점: `resolve(battleState, actionPlan) → { nextBattleState, serverResult }` (정본: `design/combat_engine_resolve_v1.md` §0)

처리 순서 (정본: `design/combat_engine_resolve_v1.md` §3):
```
1. StatsSnapshot 계산 (Modifier Stack: BASE→GEAR→BUFF→DEBUFF→FORCED→ENV)
2. 플레이어 행동 resolve (Hit→Damage→Crit→Position 순)
3. 적 행동 resolve (SPEED 순, AI personality 기반)
4. Downed 판정
5. Bonus Slot 판정
6. Status tick (DOT/duration 감소)
7. 임시 효과 제거
8. Angle 복귀 (BACK→FRONT)
9. Combat 종료 판정 (VICTORY/DEFEAT/FLEE_SUCCESS)
```

### 3. 노드별 처리 (Node Resolve)

(정본: `design/node_resolve_rules_v1.md`)

| Node Type | 서버 책임 |
|-----------|----------|
| COMBAT | 전투 엔진 위임, 종료 시 보상 정산 |
| EVENT | eventId 선택, 선택지 생성, 상태 변화 적용, stage 진행 |
| REST | 회복량 계산 (Short: +1 stamina/+10% HP, Long: +2/+25%), 상태이상 정리 |
| SHOP | 상품 목록 확정, 가격/재고 SoT, 구매 검증 처리 |
| EXIT | RUN 정산 트리거, RUN 상태 ENDED 전환 |

### 4. LLM Worker (BullMQ)

(정본: `design/server_api_system.md` Part 2)

```
Queue: "llm-narrative"
Job data: { runId, turnNo }
Worker 처리:
  1. llm_ctx_v1 컨텍스트 조립 (L0 theme → L1 story → L2 nodeFacts → L3 recent → events)
  2. Primary 모델 호출 (timeout 3~8초)
  3. 실패 시 같은 모델 1회 재시도
  4. 재실패 시 fallback 모델 1회
  5. 성공: llm_status=DONE, llm_output 저장
  6. 전실패: llm_status=FAILED, llm_error 저장
  7. SSE 이벤트 push (DONE/FAILED)
```

BullMQ 설정:
```ts
{
  attempts: 3,
  backoff: { type: 'exponential', delay: 1000 },
  removeOnComplete: { count: 1000 },
  removeOnFail: { count: 5000 }
}
```

### 5. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| POST | `/v1/runs` | RUN 생성 |
| POST | `/v1/runs/:runId/turns` | 턴 제출 |
| POST | `/v1/runs/:runId/choices/:choiceId` | 선택지 전용 (옵션) |
| GET | `/v1/runs/:runId` | RUN 상태 + 복구 |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 |
| GET | `/v1/runs/:runId/turns` | 턴 히스토리 (cursor 페이징) |
| GET | `/v1/runs/:runId/events` | SSE (LLM 상태 push) |

### 6. RNG 결정성

(정본: `design/combat_engine_resolve_v1.md` §2, `design/battlestate_storage_recovery_v1.md` §4)

```ts
// seed + cursor 기반 결정적 난수
const rng = createRng(battleState.rng.seed, battleState.rng.cursor);

// 소비 순서 (조건부)
const hitRoll = rng.next();       // 항상 소비
if (hit) {
  const varianceRoll = rng.next(); // 적중 시에만
  const critRoll = rng.next();     // 적중 시에만
}

// 턴 종료 시 cursor 저장
nextBattleState.rng = { seed: battleState.rng.seed, cursor: rng.cursor() };
```

---

## 모듈 구조 (권장)

```
src/
├── app.module.ts
├── common/
│   ├── guards/           ← IdempotencyGuard, AuthGuard
│   ├── interceptors/     ← ResponseTransformInterceptor
│   ├── pipes/            ← ZodValidationPipe
│   └── rng/              ← 결정적 난수 엔진 (splitmix64)
├── run/
│   ├── run.module.ts
│   ├── run.controller.ts     ← POST /runs, GET /runs/:runId
│   └── run.service.ts
├── turn/
│   ├── turn.module.ts
│   ├── turn.controller.ts    ← POST /turns, GET /turns
│   ├── turn.service.ts       ← 12단계 파이프라인 오케스트레이션
│   └── turn-pipeline/
│       ├── rule-parser.ts
│       ├── llm-intent-parser.ts
│       ├── intent-merger.ts
│       ├── policy-checker.ts
│       └── action-dsl-builder.ts
├── combat/
│   ├── combat.module.ts
│   ├── combat-resolve.service.ts   ← resolve(battleState, actionPlan)
│   ├── stat-snapshot.ts            ← Modifier Stack 계산
│   ├── hit-calculator.ts
│   ├── damage-calculator.ts
│   └── status-effect.service.ts
├── node/
│   ├── node.module.ts
│   ├── event-resolve.service.ts
│   ├── rest-resolve.service.ts
│   ├── shop-resolve.service.ts
│   └── exit-resolve.service.ts
├── llm/
│   ├── llm.module.ts
│   ├── llm-worker.processor.ts    ← BullMQ Worker
│   ├── llm-context-builder.ts     ← llm_ctx_v1 조립
│   └── llm-sse.gateway.ts         ← SSE endpoint
└── db/
    └── drizzle/                    ← Database Agent 관할
```

---

## 금지 사항

### 절대 하지 않는 것

1. **LLM 결과로 게임 상태 변경 금지** — LLM은 서술만 생성. 수치/상태 변경 권한 없음
2. **트랜잭션 분리 금지** — turn/battle_state/run/server_result는 반드시 단일 트랜잭션
3. **RNG 순서 변경 금지** — hitRoll → varianceRoll → critRoll 순서 고정
4. **diff를 LLM에 전달 금지** — events/summary만 전달
5. **LLM 실패로 500 반환 금지** — 게임 결과는 이미 확정됨, summary.short로 대체
6. **클라이언트 입력을 확정 결과로 신뢰 금지** — 모든 입력은 intent로만 해석

### server_result 생성 규칙

- `events[]`에는 **플레이어 가시 이벤트만** 포함 (AI 판단/난수/디버그 제외)
- `diff`는 클라이언트 HUD용 (LLM에 전달하지 않음)
- `summary.short`는 항상 존재해야 함 (LLM 실패 시 폴백)
- `choices[]`는 서버가 확정한 선택지만 포함

---

## 주의 사항

### 멱등성 구현

```
1. idempotencyKey → Redis SET NX (TTL 5분)
2. 이미 존재 → DB에서 기존 결과 조회 후 반환
3. (runId, turnNo) UNIQUE 제약으로 이중 보장
4. 입력 내용이 다르면 409 또는 422
```

### 동시성 방어

```
1. expectedNextTurnNo != run.current_turn_no → 409 CONFLICT
2. 성공 시 run.current_turn_no++ (같은 트랜잭션 내)
```

### LLM 컨텍스트 조립 순서

(정본: `design/llm_context_system_v1.md`, `design/server_api_system.md` §16)

```
1. run_memories.theme (L0) — 절대 제거하지 않음
2. run_memories.storySummary (L1)
3. node_memories.nodeFacts (L2) — 현재/직전 노드 merge
4. recent_summaries (L3)
5. server_result.events + summary.short — 이번 턴 확정 사실
6. ui/choices (필요 시)
```

### 전투 공식 참조

| 공식 | 정본 |
|------|------|
| Hit: `d20 + ACC >= 10 + targetEVA` | `design/combat_resolve_engine_v1.md` §1 |
| Damage: `ATK * (100 / (100 + DEF)) * variance(0.9~1.1)` | `design/combat_resolve_engine_v1.md` §1 |
| Crit: `DEF 30% 무시, CRIT_DMG 배율 (max 2.5)` | `design/combat_resolve_engine_v1.md` §1 |
| SIDE: `DEF -10%, TAKEN_DMG_MULT +10%` | `design/combat_resolve_engine_v1.md` §2 |
| BACK: `DEF -20%, CRIT +10%, TAKEN_DMG_MULT +25%` | `design/combat_resolve_engine_v1.md` §2 |
| Downed: `d20 + RESIST >= 15` | `design/combat_system.md` §10 |
| Flee: `d20 + SPEED >= 12 + engaged*2` | `design/combat_system.md` §9 |

### Status Effect 규칙

(정본: `design/status_effect_system_v1.md`)

- StatusInstance: `{ id, sourceId, applierId, duration, stacks, power, meta? }`
- 적용 판정: ACC vs RESIST
- STUN: duration 1 고정 + 2턴 면역
- DOT: DEF 무시, TAKEN_DMG_MULT 적용
- Bonus Slot과 상태이상은 상호 간섭하지 않음

### 에러 응답 표준

```json
{
  "code": "TURN_CONFLICT",
  "message": "사용자 표시 가능한 메시지",
  "details": { "개발용 추가 정보" }
}
```

---

## 참조 문서

| 문서 | 참조 내용 |
|------|----------|
| `design/server_api_system.md` | API 전체, LLM Worker, 에러 처리 |
| `design/combat_engine_resolve_v1.md` | 전투 Resolve 엔진, 의사코드, RNG |
| `design/combat_resolve_engine_v1.md` | 수치 공식 정본 (Hit/Dmg/Crit/Position) |
| `design/combat_system.md` | 전투 통합 (Action Economy, AI, Multi-Target) |
| `design/status_effect_system_v1.md` | 상태이상 시스템 |
| `design/battlestate_storage_recovery_v1.md` | BattleState 저장/복구, 원자 커밋 |
| `design/node_resolve_rules_v1.md` | 노드별 서버 처리 규약 |
| `design/input_processing_pipeline_v1.md` | 입력 파이프라인 (Rule→LLM→Policy→Action) |
| `design/rewards_and_progression_v1.md` | 보상/정산 |
| `design/llm_context_system_v1.md` | LLM 컨텍스트 스키마 |
| `design/run_planner_v1_1.md` | RUN 생성기 |
| `schema/server_result_v1.json` | server_result JSON Schema |
| `schema/OpenAPI 3.1.yaml` | OpenAPI 스키마 |
