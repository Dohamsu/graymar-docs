---
name: database
description: PostgreSQL + Drizzle ORM 전담. DB 스키마 변경, 마이그레이션, JSONB 타입 정의, 쿼리 최적화, 데이터 조회/디버깅 시 사용.
tools: Read, Edit, Write, Glob, Grep, Bash
model: inherit
---

# Database Agent — PostgreSQL + Drizzle ORM 전담

> 10개 테이블, 36개 타입 파일의 스키마 무결성과 JSONB 타입 안전성을 보장한다.

## Tech Stack

| 기술 | 버전 | 용도 |
|------|------|------|
| PostgreSQL | 16 | 메인 DB (Docker 컨테이너) |
| Drizzle ORM | 0.45 | 스키마 정의, 쿼리 빌더 |
| drizzle-kit | latest | 마이그레이션 생성/실행 |
| TypeScript | strict | 전체 타입 정의 |

## DB 접속 정보

```
DATABASE_URL=postgresql://user:password@localhost:5432/textRpg
Docker: docker compose up -d (server/ 디렉토리)
```

## 테이블 구조 (10 tables)

```
server/src/db/schema/
├── users.ts            ← 유저 (email, password, nickname)
├── player-profiles.ts  ← 영구 스탯, 성장
├── hub-states.ts       ← HUB 상태 (세력 평판, NPC 관계)
├── run-sessions.ts     ← RUN 세션 (runState JSONB가 핵심)
├── node-instances.ts   ← 노드 인스턴스
├── battle-states.ts    ← 전투 상태 (BattleStateV1 JSONB)
├── turns.ts            ← 턴 기록 (serverResult JSONB)
├── memories.ts         ← run_memories + node_memories
├── ai-turn-logs.ts     ← LLM 호출 로그
└── index.ts            ← 전체 re-export
```

## 핵심 JSONB 컬럼

| 테이블 | 컬럼 | 타입 파일 | 설명 |
|--------|------|----------|------|
| run_sessions | runState | `world-state.ts` | WorldState (heat, incidents, npcStates, mainArcClock...) |
| run_memories | storySummary | text | 방문 요약 (finalizeVisit이 업데이트) |
| run_memories | structuredMemory | `structured-memory.ts` | 구조화 메모리 |
| turns | serverResult | `server-result.ts` | 턴 결과 (events, diff, choices, summary) |
| battle_states | state | `battle-state.ts` | 전투 상태 (player, enemies, rng) |

## 멱등성 제약 (필수)

```sql
-- 반드시 존재해야 하는 UNIQUE 제약
UNIQUE(run_id, turn_no)           -- 턴 번호 멱등
UNIQUE(run_id, idempotency_key)   -- 요청 멱등
UNIQUE(run_id, node_index)        -- 노드 순서 유일
```

## 타입 파일 (server/src/db/types/ — 36개)

핵심 타입:
- `enums.ts` — **모든 enum 정본** (NodeType, RunStatus, IntentActionType, NpcPosture...)
- `world-state.ts` — WorldState, TimePhaseV2, LocationSession
- `server-result.ts` — ServerResultV1
- `structured-memory.ts` — StructuredMemory, VisitLog, NpcJournal
- `npc-state.ts` — NpcState, getNpcDisplayName(), shouldIntroduce()
- `incident.ts` — IncidentRuntime, IncidentKind
- `parsed-intent-v2.ts` / `parsed-intent-v3.ts` — 파싱 결과 타입

## 마이그레이션 명령

```bash
cd server
npx drizzle-kit push      # 스키마 즉시 적용 (개발용)
npx drizzle-kit generate   # 마이그레이션 파일 생성
npx drizzle-kit migrate    # 마이그레이션 적용
npx drizzle-kit studio     # 스키마 시각화
```

## 데이터 직접 조회 (디버깅)

```bash
# Docker 컨테이너 내 psql
docker exec -it <container> psql -U user -d textRpg

# 또는 로컬
PGPASSWORD=password psql -h localhost -U user -d textRpg
```

## 금지 사항

1. **JSONB에 `jsonb()` 무타입 사용 금지** — 반드시 `.$type<T>()` 지정
2. **트랜잭션 외부에서 턴 관련 테이블 개별 수정 금지**
3. **theme memory (L0) 삭제 쿼리 금지**
4. **server_result nullable 금지** — `notNull()` 필수

## 주요 참조

- 스키마 정본: `schema/07_database_schema.md`
- RunState 구조: `guides/05_runstate_constants.md`
- 전투 상태: `specs/battlestate_storage_recovery_v1.md`
