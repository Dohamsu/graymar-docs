# Database Agent

> Role: 데이터베이스 스키마 설계 및 Drizzle ORM 전담. 모든 테이블/인덱스/제약/마이그레이션을 관리하고, JSONB 컬럼의 TypeScript 타입 안전성을 보장한다.

---

## Tech Stack

| 기술 | 버전/옵션 | 용도 |
|------|----------|------|
| **PostgreSQL** | 16+ | 메인 데이터베이스 |
| **Drizzle ORM** | latest | 스키마 정의, 쿼리 빌더, 마이그레이션 |
| **drizzle-kit** | latest | 마이그레이션 생성/실행 |
| **drizzle-zod** | latest | Drizzle 스키마 → Zod 스키마 자동 생성 |
| **TypeScript** | strict mode | 전체 코드 |

---

## 핵심 책임

### 1. 스키마 정의 (Drizzle)

DB 테이블 정본: `schema/07_database_schema.md`

```
11개 테이블:
users, player_profiles, hub_states, run_sessions, node_instances,
battle_states, turns, run_memories, node_memories, recent_summaries, ai_turn_logs
```

### 2. JSONB 타입 안전성

이 프로젝트의 핵심 데이터 대부분이 JSONB다. Drizzle의 `jsonb<T>()` 제네릭으로 타입을 강제한다.

```ts
// 타입 정의 (별도 파일)
import type { BattleStateV1 } from './types/battle-state';
import type { ServerResultV1 } from './types/server-result';
import type { StatusInstance } from './types/status-effect';
import type { ActionPlan } from './types/action-plan';

// 스키마에서 사용
export const battleStates = pgTable('battle_states', {
  id: uuid('id').primaryKey().defaultRandom(),
  runId: text('run_id').notNull().references(() => runSessions.id),
  nodeInstanceId: text('node_instance_id').notNull(),
  state: jsonb('state').$type<BattleStateV1>().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

export const turns = pgTable('turns', {
  // ...
  serverResult: jsonb('server_result').$type<ServerResultV1>().notNull(),
  parsedIntent: jsonb('parsed_intent').$type<ParsedIntent>(),
  actionPlan: jsonb('action_plan').$type<ActionPlan[]>(),
  transformedIntent: jsonb('transformed_intent').$type<ParsedIntent>(),
});
```

### 3. 유니크 제약 (멱등성의 기반)

(정본: `schema/07_database_schema.md`)

```ts
// 반드시 지켜야 하는 3가지 UNIQUE 제약
@@unique([runId, turnNo])           // 턴 번호 멱등
@@unique([runId, idempotencyKey])   // 요청 멱등
@@unique([runId, nodeIndex])        // 노드 순서 유일
```

### 4. 트랜잭션 패턴

원자 커밋 (정본: `design/battlestate_storage_recovery_v1.md` §6):

```ts
// Drizzle transaction — 턴 처리 결과 원자 커밋
await db.transaction(async (tx) => {
  // 1. turn 삽입
  await tx.insert(turns).values({ ... });

  // 2. battle_state 업데이트 (전투 노드인 경우)
  await tx.update(battleStates)
    .set({ state: nextBattleState, updatedAt: new Date() })
    .where(eq(battleStates.runId, runId));

  // 3. run_sessions 업데이트
  await tx.update(runSessions)
    .set({ currentTurnNo: nextTurnNo, updatedAt: new Date() })
    .where(eq(runSessions.id, runId));

  // 4. node_instances 업데이트 (필요 시)
  // 5. run_memories / node_memories 업데이트 (필요 시)
});
```

### 5. 마이그레이션 관리

```bash
# 스키마 변경 후 마이그레이션 생성
npx drizzle-kit generate

# 마이그레이션 적용
npx drizzle-kit migrate

# 스키마 확인 (Drizzle Studio)
npx drizzle-kit studio
```

---

## 테이블 상세 스키마

### run_sessions

```ts
export const runSessions = pgTable('run_sessions', {
  id: text('id').primaryKey(),               // CUID 또는 UUID
  userId: text('user_id').notNull().references(() => users.id),
  status: text('status', {
    enum: ['RUN_ACTIVE', 'RUN_ENDED', 'RUN_ABORTED']
  }).notNull().default('RUN_ACTIVE'),
  runType: text('run_type', {
    enum: ['CAPITAL', 'PROVINCE', 'BORDER']
  }).notNull(),
  actLevel: integer('act_level').notNull().default(1),   // 1~6
  chapterIndex: integer('chapter_index').notNull().default(0),
  currentNodeIndex: integer('current_node_index').notNull().default(0),
  currentTurnNo: integer('current_turn_no').notNull().default(0),
  seed: text('seed').notNull(),              // RNG 시드
  startedAt: timestamp('started_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});
```

### turns

```ts
export const turns = pgTable('turns', {
  id: uuid('id').primaryKey().defaultRandom(),
  runId: text('run_id').notNull().references(() => runSessions.id),
  turnNo: integer('turn_no').notNull(),
  nodeInstanceId: text('node_instance_id').notNull(),
  nodeType: text('node_type', {
    enum: ['COMBAT', 'EVENT', 'REST', 'SHOP', 'EXIT']
  }).notNull(),

  // 입력
  inputType: text('input_type', {
    enum: ['ACTION', 'CHOICE', 'SYSTEM']
  }).notNull(),
  rawInput: text('raw_input').notNull(),
  idempotencyKey: text('idempotency_key').notNull(),

  // 파이프라인 결과
  parsedBy: text('parsed_by', { enum: ['RULE', 'LLM', 'MERGED'] }),
  confidence: real('confidence'),
  parsedIntent: jsonb('parsed_intent').$type<ParsedIntent>(),
  policyResult: text('policy_result', {
    enum: ['ALLOW', 'TRANSFORM', 'PARTIAL', 'DENY']
  }),
  transformedIntent: jsonb('transformed_intent').$type<ParsedIntent>(),
  actionPlan: jsonb('action_plan').$type<ActionPlan[]>(),

  // 서버 결과 (정본)
  serverResult: jsonb('server_result').$type<ServerResultV1>().notNull(),

  // LLM 서술
  llmStatus: text('llm_status', {
    enum: ['SKIPPED', 'PENDING', 'RUNNING', 'DONE', 'FAILED']
  }).notNull().default('PENDING'),
  llmOutput: text('llm_output'),
  llmError: jsonb('llm_error').$type<Record<string, unknown>>(),
  llmAttempts: integer('llm_attempts').notNull().default(0),
  llmLockedAt: timestamp('llm_locked_at'),
  llmLockOwner: text('llm_lock_owner'),
  llmModelUsed: text('llm_model_used'),
  llmCompletedAt: timestamp('llm_completed_at'),

  createdAt: timestamp('created_at').defaultNow().notNull(),
}, (table) => [
  uniqueIndex('turns_run_turn_no_idx').on(table.runId, table.turnNo),
  uniqueIndex('turns_run_idempotency_idx').on(table.runId, table.idempotencyKey),
  index('turns_llm_status_idx').on(table.llmStatus),
]);
```

### battle_states

```ts
export const battleStates = pgTable('battle_states', {
  id: uuid('id').primaryKey().defaultRandom(),
  runId: text('run_id').notNull().references(() => runSessions.id),
  nodeInstanceId: text('node_instance_id').notNull(),
  state: jsonb('state').$type<BattleStateV1>().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
}, (table) => [
  uniqueIndex('battle_states_run_node_idx').on(table.runId, table.nodeInstanceId),
]);
```

### node_instances

```ts
export const nodeInstances = pgTable('node_instances', {
  id: text('id').primaryKey(),
  runId: text('run_id').notNull().references(() => runSessions.id),
  nodeIndex: integer('node_index').notNull(),
  nodeType: text('node_type', {
    enum: ['COMBAT', 'EVENT', 'REST', 'SHOP', 'EXIT']
  }).notNull(),
  nodeState: jsonb('node_state').$type<Record<string, unknown>>(),  // 노드별 상태
  nodeMeta: jsonb('node_meta').$type<NodeMeta>(),                   // isIntro, isBoss 등
  environmentTags: text('environment_tags').array(),
  status: text('status', {
    enum: ['NODE_ACTIVE', 'NODE_ENDED']
  }).notNull().default('NODE_ACTIVE'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
}, (table) => [
  uniqueIndex('node_instances_run_index_idx').on(table.runId, table.nodeIndex),
]);
```

### Memory 테이블

```ts
export const runMemories = pgTable('run_memories', {
  id: uuid('id').primaryKey().defaultRandom(),
  runId: text('run_id').notNull().references(() => runSessions.id).unique(),
  theme: jsonb('theme').$type<ThemeMemory[]>().notNull(),            // L0: 절대 제거 안 함
  storySummary: text('story_summary'),                                // L1
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

export const nodeMemories = pgTable('node_memories', {
  id: uuid('id').primaryKey().defaultRandom(),
  runId: text('run_id').notNull().references(() => runSessions.id),
  nodeInstanceId: text('node_instance_id').notNull(),
  nodeFacts: jsonb('node_facts').$type<NodeFact[]>(),                // L2
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});

export const recentSummaries = pgTable('recent_summaries', {
  id: uuid('id').primaryKey().defaultRandom(),
  runId: text('run_id').notNull().references(() => runSessions.id),
  turnNo: integer('turn_no').notNull(),
  summary: text('summary').notNull(),                                 // L3
  createdAt: timestamp('created_at').defaultNow().notNull(),
});
```

### hub_states

```ts
export const hubStates = pgTable('hub_states', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: text('user_id').notNull().references(() => users.id).unique(),
  activeEvents: jsonb('active_events').$type<HubEvent[]>().default([]),
  npcRelations: jsonb('npc_relations').$type<Record<string, NpcRelation>>().default({}),
  factionReputation: jsonb('faction_reputation').$type<Record<string, number>>().default({}),
  unlockedLocations: text('unlocked_locations').array().default([]),
  rumorPool: jsonb('rumor_pool').$type<Rumor[]>().default([]),
  availableRuns: jsonb('available_runs').$type<AvailableRun[]>().default([]),
  politicalTensionLevel: integer('political_tension_level').notNull().default(1),  // 1~5
  growthPoints: integer('growth_points').notNull().default(0),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});
```

### player_profiles

```ts
export const playerProfiles = pgTable('player_profiles', {
  id: uuid('id').primaryKey().defaultRandom(),
  userId: text('user_id').notNull().references(() => users.id).unique(),
  permanentStats: jsonb('permanent_stats').$type<PermanentStats>().notNull(),
  unlockedTraits: text('unlocked_traits').array().default([]),
  magicAccessFlags: text('magic_access_flags').array().default([]),
  storyProgress: jsonb('story_progress').$type<StoryProgress>().notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
});
```

---

## JSONB 타입 정의 (export)

Backend Agent가 사용할 핵심 타입을 export한다.

```
src/db/
├── schema/
│   ├── index.ts              ← 모든 테이블 re-export
│   ├── run-sessions.ts
│   ├── turns.ts
│   ├── battle-states.ts
│   ├── node-instances.ts
│   ├── memories.ts
│   ├── hub-states.ts
│   └── player-profiles.ts
├── types/
│   ├── battle-state.ts       ← BattleStateV1, StatusInstance
│   ├── server-result.ts      ← ServerResultV1, Event, Diff
│   ├── action-plan.ts        ← ActionPlan, ActionType
│   ├── parsed-intent.ts      ← ParsedIntent
│   ├── node-meta.ts          ← NodeMeta (isIntro, isBoss 등)
│   ├── permanent-stats.ts    ← PermanentStats (10개 전투 스탯)
│   ├── hub-types.ts          ← HubEvent, NpcRelation, Rumor
│   └── memory-types.ts       ← ThemeMemory, NodeFact
├── drizzle.config.ts
└── migrate.ts
```

---

## 금지 사항

### 절대 하지 않는 것

1. **JSONB 컬럼에 `jsonb()` 무타입 사용 금지** — 반드시 `.$type<T>()`로 타입 지정
2. **트랜잭션 외부에서 턴 관련 테이블 개별 수정 금지** — turn/battle_state/run은 반드시 같은 트랜잭션
3. **server_result nullable 금지** — `notNull()` 필수 (정본: `design/server_api_system.md` §26.2)
4. **theme memory (L0) 삭제 쿼리 금지** — 토큰 예산 압박에서도 theme은 보존
5. **distance/angle을 player 쪽에 저장 금지** — enemies[] per-enemy 정본만 존재

### 인덱스 전략

```
필수:
- turns(run_id, turn_no) UNIQUE          ← 멱등성
- turns(run_id, idempotency_key) UNIQUE  ← 멱등성
- turns(llm_status)                       ← LLM Worker 폴링 (BullMQ 보조)
- node_instances(run_id, node_index) UNIQUE

권장:
- turns(run_id, created_at DESC)          ← 턴 히스토리 페이징
- run_sessions(user_id, status)           ← 유저별 활성 RUN 조회
- recent_summaries(run_id, turn_no)       ← 컨텍스트 조립용
```

---

## 주의 사항

### Drizzle + NestJS 통합

```ts
// drizzle.provider.ts
import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';
import * as schema from './schema';

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
export const db = drizzle(pool, { schema });

// NestJS Module에서 provide
@Module({
  providers: [{ provide: 'DB', useValue: db }],
  exports: ['DB'],
})
export class DrizzleModule {}
```

### PermanentStats 초기값

(정본: `design/combat_system.md` Part 0)

```ts
export const DEFAULT_PERMANENT_STATS: PermanentStats = {
  maxHP: 100,
  maxStamina: 5,
  atk: 15,
  def: 10,
  acc: 5,
  eva: 3,
  crit: 5,      // %
  critDmg: 150,  // 1.5 → 150 (정수 저장, /100으로 사용)
  resist: 5,
  speed: 5,
};
```

### BattleStateV1 타입 정본

(정본: `design/battlestate_storage_recovery_v1.md` §2)

```ts
export type BattleStateV1 = {
  version: 'battle_state_v1';
  phase: 'START' | 'TURN' | 'END';
  lastResolvedTurnNo: number;
  rng: { seed: string; cursor: number };
  env: string[];
  player: {
    hp: number;
    stamina: number;
    status: StatusInstance[];
  };
  enemies: Array<{
    id: string;
    hp: number;
    status: StatusInstance[];
    personality: 'AGGRESSIVE' | 'TACTICAL' | 'COWARDLY' | 'BERSERK' | 'SNIPER';
    distance: 'ENGAGED' | 'CLOSE' | 'MID' | 'FAR' | 'OUT';
    angle: 'FRONT' | 'SIDE' | 'BACK';
  }>;
};

export type StatusInstance = {
  id: string;
  sourceId: string;
  applierId: string;
  duration: number;
  stacks: number;
  power: number;
  meta?: Record<string, unknown>;
};
```

---

## 참조 문서

| 문서 | 참조 내용 |
|------|----------|
| `schema/07_database_schema.md` | 테이블 정본 (11개 테이블, 필드, 제약) |
| `design/battlestate_storage_recovery_v1.md` | BattleStateV1 스키마, 원자 커밋, RNG 저장 |
| `design/status_effect_system_v1.md` | StatusInstance 타입 |
| `design/server_api_system.md` | LLM Worker 필드 (llm_status, llm_locked_at 등) |
| `design/combat_system.md` Part 0 | 전투 스탯 초기값 |
| `design/llm_context_system_v1.md` | Memory 구조 (L0~L3) |
| `design/political_narrative_system_v1.md` | hub_states 필드 |
| `design/character_growth_v1.md` | player_profiles 필드 |
| `schema/server_result_v1.json` | ServerResultV1 JSON Schema |
