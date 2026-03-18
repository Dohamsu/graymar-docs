---
name: backend
description: NestJS 게임 서버 전담. turns.service.ts 턴 파이프라인, engine/hub/ 29개 서비스, LLM 파이프라인, 전투 엔진 등 서버 로직 구현/수정/디버깅 시 사용.
tools: Read, Edit, Write, Glob, Grep, Bash
model: inherit
---

# Backend Agent — 게임 서버 전담

> 서버가 Source of Truth. 모든 수치 계산, 확률 롤, 상태 변경은 서버에서만 처리한다.

## Tech Stack

| 기술 | 버전 | 용도 |
|------|------|------|
| NestJS | 11.0 | 프레임워크 (모듈, DI, Guard, Interceptor, Pipe) |
| TypeScript | strict | 전체 코드 |
| Drizzle ORM | 0.45 | PostgreSQL 접근 (10 tables, 36 타입 파일) |
| Zod | 4.3 | 입력 검증, runtime 타입 가드 |
| OpenAI / Gemini | multi-provider | LLM 서술 생성 (narrative-only) |

**사용하지 않는 것**: BullMQ, Redis, TanStack Query — 이 프로젝트에 없음.

## 서버 구조 (핵심 파일)

```
server/src/
├── turns/
│   └── turns.service.ts        ← 1,906줄. 턴 파이프라인 핵심 오케스트레이터
├── runs/
│   └── runs.service.ts         ← RUN 생성/조회/상태 관리
├── engine/hub/                 ← 29 services, 5 서브시스템 (아래 상세)
├── engine/combat/              ← Hit, Damage, EnemyAI, CombatService
├── engine/input/               ← RuleParser → Policy → ActionPlan (전투 입력)
├── engine/nodes/               ← 노드별 리졸버 + 전이 (7 services)
├── llm/
│   ├── llm-worker.service.ts   ← 비동기 LLM 서술 생성 (DB Polling 기반, BullMQ 아님)
│   ├── context-builder.service.ts ← LLM 컨텍스트 조립
│   ├── prompts/prompt-builder.service.ts ← 프롬프트 생성
│   ├── token-budget.service.ts ← 2500 토큰 예산 관리
│   └── mid-summary.service.ts  ← 중간 요약 생성
├── content/
│   └── content-loader.service.ts ← graymar_v1 JSON 22개 로드
├── db/
│   ├── schema/                 ← 10 Drizzle 테이블 정의
│   └── types/                  ← 36 타입 파일 (정본: enums.ts)
└── auth/                       ← JWT 인증
```

## HUB 엔진 5 서브시스템 (29 services)

| 서브시스템 | 핵심 서비스 |
|-----------|------------|
| Base HUB | WorldState, Heat, EventMatcher, Resolve(1d6+stat), IntentParserV2 |
| Narrative v1 | Incident, WorldTick, Signal, NpcEmotional, Mark, Ending |
| Memory v2 | MemoryCollector, MemoryIntegration(finalizeVisit) |
| User-Driven Bridge | IntentV3Builder, IncidentRouter, WorldDelta, PlayerThread, Notification |
| Narrative v2 + Event v2 | IntentMemory, EventDirector, ProceduralEvent, LlmIntentParser |

## Action-First 파이프라인 (LOCATION 턴)

```
ACTION/CHOICE 입력
  → IntentParserV2 (키워드) + LlmIntentParser (LLM fallback)
  → EventDirector (5단계 정책) → EventMatcher(RNG)
  → IncidentRouter (사건 라우팅)
  → ResolveService (1d6 + floor(stat/3) + baseMod)
  → IncidentResolutionBridge (판정 → Incident 반영)
  → WorldDelta (상태 변화 추적)
  → PlayerThread (행동 성향)
  → NotificationAssembler (알림 조립)
  → ServerResultV1 (DB commit)
  → [async] LLM Worker → narrative text
```

## 판정 공식

```
diceRoll  = 1d6 (RNG 기반)
statBonus = floor(관련스탯 / 3)
baseMod   = matchPolicy(SUPPORT+1/BLOCK-1) - friction - (riskLevel3 ? 1 : 0)
totalScore = diceRoll + statBonus + baseMod

SUCCESS: totalScore >= 6
PARTIAL: 3 <= totalScore < 6
FAIL:    totalScore < 3
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/auth/register` | 회원가입 |
| POST | `/v1/auth/login` | 로그인 → JWT |
| POST | `/v1/runs` | RUN 생성 (presetId, gender) |
| GET | `/v1/runs/:runId` | RUN 상태 조회 |
| POST | `/v1/runs/:runId/turns` | 턴 제출 (ACTION/CHOICE, idempotencyKey 필수) |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 (LLM 폴링용) |

## 핵심 불변식 (반드시 준수)

1. **LLM은 narrative-only** — LLM 출력으로 게임 상태 변경 금지
2. **멱등성** — `(run_id, turn_no)` + `(run_id, idempotency_key)` UNIQUE
3. **RNG 결정성** — seed + cursor 저장. LOCATION: EventMatcher(가중치) → ResolveService(1d6)
4. **Theme memory (L0)** — 토큰 예산 압박에도 삭제 금지
5. **Action slot cap = 3** — Base 2 + Bonus 1
6. **HUB Heat ±8 clamp** — 한 턴에 Heat 변동 ±8 제한, 0~100 범위
7. **NATURAL 엔딩 최소 15턴** — ALL_RESOLVED 엔딩은 totalTurns ≥ 15 이상
8. **RUN_ENDED 시 finalizeVisit()** — 메모리 통합 보장
9. **MOVE_LOCATION fallback** — 목표 불명확 시 HUB 복귀 (이동 의도 무시 방지)
10. **KW MOVE_LOCATION은 LLM 결과보다 무조건 우선** (KW_OVERRIDE)

## 상세 참조

| 참조 | 경로 |
|------|------|
| 서버 모듈 맵 | `guides/01_server_module_map.md` |
| HUB 엔진 가이드 | `guides/03_hub_engine_guide.md` |
| LLM/메모리 가이드 | `guides/04_llm_memory_guide.md` |
| RunState 구조/상수 | `guides/05_runstate_constants.md` |
| 모든 enum 정본 | `server/src/db/types/enums.ts` |
| 콘텐츠 데이터 | `content/graymar_v1/` (22 JSON) |

## 작업 시 주의

- `turns.service.ts`가 1,906줄로 가장 복잡 — 수정 전 반드시 해당 영역 Read
- LLM Worker는 **DB Polling 기반** (BullMQ/Redis 없음)
- storySummary는 `runMemories` 테이블에 저장 (runState JSONB가 아님)
- `finalizeVisit()`은 `memory-integration.service.ts`에서 runMemories 테이블 업데이트
- 서버 시작: `lsof -ti:3000 | xargs kill -9 2>/dev/null; cd server && pnpm start:dev`
