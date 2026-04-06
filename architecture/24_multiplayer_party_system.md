# 24. 멀티플레이어 파티 시스템 — 설계 정본

> 확정 설계. 파티 채팅 + 협동 던전 + 보상 분배 + 런 통합 고도화
> 마지막 갱신: 2026-04-04

---

## 1. 개요 및 Phase 로드맵

### 1.1 목표

기존 싱글플레이어 RPG에 최대 4인 파티 시스템을 도입한다. 파티원은 같은 장소에서 함께 이동하고, 각자 독립적으로 행동한 뒤 서버가 통합 처리하며, LLM이 4인분 행동을 하나의 서사로 생성한다.

### 1.2 핵심 원칙

1. **기존 불변식 유지** --- Server SoT, LLM narrative-only, 멱등성, RNG 결정성
2. **솔로/파티 완전 분리** --- 솔로 런은 그대로, 파티 런은 별도 메뉴로 진입
3. **단일 서버 최적화** --- Phase 1에서 Redis 불필요 (동시 접속 10명 이하)
4. **점진적 도입** --- Phase별로 독립 배포 가능

### 1.3 Phase 로드맵

| Phase | 범위 | 선행 조건 | 예상 기간 |
|-------|------|-----------|-----------|
| **Phase 1** | 파티 CRUD + 초대코드 + 파티 목록 + 실시간 채팅 + 로비 UI | 없음 | 3주 |
| **Phase 2** | 파티 전용 런 + 동시 턴 처리 + 이동 투표 + 보상 분배 + 던전 UI | Phase 1 완료 | 5주 |
| **Phase 3** | 런 통합 (파티장 세계 합류) + 스케일링 (Redis adapter) | Phase 2 안정화 | 미정 |

---

## 2. 아키텍처

### 2.1 현재 (싱글플레이어)

```
Client (Next.js 16)  ──REST──>  Server (NestJS 11)  ──>  PostgreSQL
                                       |
                                 LLM Worker (async, DB Polling)
```

- 완전 싱글플레이어: 1 user = 1 run
- 실시간 통신 없음: REST + LLM 폴링

### 2.2 변경 (멀티플레이어)

```
Client (Next.js 16)
  ├── REST API (기존 유지 + 파티 엔드포인트)
  └── WebSocket (/party) ─────>  Server (NestJS 11)
       |                              ├── 기존 모듈 (auth, runs, turns, engine, llm, ...)
       |                              ├── PartyModule (NEW)
       |                              │   ├── PartyGateway (WebSocket)
       |                              │   ├── PartyService (파티 CRUD)
       |                              │   ├── ChatService (채팅)
       |                              │   ├── LobbyService (로비/준비)
       |                              │   ├── VoteService (이동 투표)
       |                              │   └── PartyTurnService (통합 턴 처리)
       |                              └── PostgreSQL (기존 + 파티/채팅 테이블)
       |
       └── 실시간 이벤트 (채팅, 턴 상태, 투표, 로비)
```

### 2.3 핵심 변경 요약

| 영역 | 변경 |
|------|------|
| 의존성 (서버) | `@nestjs/websockets`, `@nestjs/platform-socket.io`, `socket.io` |
| 의존성 (클라이언트) | `socket.io-client` |
| 새 모듈 | `server/src/party/` (6 services, 1 gateway, 1 controller) |
| 새 DB 테이블 | `parties`, `party_members`, `chat_messages`, `party_turn_actions`, `party_votes` |
| 기존 테이블 변경 | `run_sessions`에 `partyId`, `runMode` 컬럼 추가 |
| 클라이언트 | `party-store.ts`, `socket-client.ts`, 파티/로비/채팅 컴포넌트 |

---

## 3. DB 스키마

### 3.1 새 테이블 (Drizzle ORM)

```typescript
// server/src/db/schema/parties.ts

import {
  index,
  integer,
  pgTable,
  text,
  timestamp,
  uuid,
} from 'drizzle-orm/pg-core';
import { users } from './users.js';

/**
 * 파티 상태:
 * - OPEN: 가입 가능
 * - FULL: 4명 만석 (가입 불가, 추방/탈퇴 시 OPEN으로 복귀)
 * - IN_DUNGEON: 파티 런 진행 중
 * - DISBANDED: 해산됨
 */
export const PARTY_STATUS = ['OPEN', 'FULL', 'IN_DUNGEON', 'DISBANDED'] as const;
export type PartyStatus = (typeof PARTY_STATUS)[number];

export const parties = pgTable(
  'parties',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    name: text('name').notNull(),
    leaderId: uuid('leader_id')
      .notNull()
      .references(() => users.id),
    status: text('status', { enum: PARTY_STATUS })
      .notNull()
      .default('OPEN'),
    maxMembers: integer('max_members').notNull().default(4),
    inviteCode: text('invite_code').notNull().unique(), // 6자리 영숫자
    createdAt: timestamp('created_at').defaultNow().notNull(),
    updatedAt: timestamp('updated_at').defaultNow().notNull(),
  },
  (table) => [
    index('parties_leader_idx').on(table.leaderId),
    index('parties_status_idx').on(table.status),
    index('parties_invite_code_idx').on(table.inviteCode),
  ],
);
```

```typescript
// server/src/db/schema/party-members.ts

import {
  pgTable,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from 'drizzle-orm/pg-core';
import { users } from './users.js';
import { parties } from './parties.js';

export const PARTY_ROLE = ['LEADER', 'MEMBER'] as const;
export type PartyRole = (typeof PARTY_ROLE)[number];

export const partyMembers = pgTable(
  'party_members',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    partyId: uuid('party_id')
      .notNull()
      .references(() => parties.id),
    userId: uuid('user_id')
      .notNull()
      .references(() => users.id),
    role: text('role', { enum: PARTY_ROLE })
      .notNull()
      .default('MEMBER'),
    isOnline: text('is_online').notNull().default('false'), // WebSocket 연결 상태
    joinedAt: timestamp('joined_at').defaultNow().notNull(),
  },
  (table) => [
    uniqueIndex('party_members_party_user_idx').on(table.partyId, table.userId),
  ],
);
```

```typescript
// server/src/db/schema/chat-messages.ts

import {
  index,
  pgTable,
  text,
  timestamp,
  uuid,
} from 'drizzle-orm/pg-core';
import { users } from './users.js';
import { parties } from './parties.js';

/**
 * 메시지 타입:
 * - TEXT: 일반 채팅
 * - SYSTEM: 시스템 알림 (가입/탈퇴/추방 등)
 * - GAME_EVENT: 게임 이벤트 서술 (턴 결과, 이동 등)
 */
export const MESSAGE_TYPE = ['TEXT', 'SYSTEM', 'GAME_EVENT'] as const;
export type MessageType = (typeof MESSAGE_TYPE)[number];

export const chatMessages = pgTable(
  'chat_messages',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    partyId: uuid('party_id')
      .notNull()
      .references(() => parties.id),
    senderId: uuid('sender_id').references(() => users.id), // null = SYSTEM
    type: text('type', { enum: MESSAGE_TYPE })
      .notNull()
      .default('TEXT'),
    content: text('content').notNull(),
    createdAt: timestamp('created_at').defaultNow().notNull(),
  },
  (table) => [
    index('chat_messages_party_created_idx').on(table.partyId, table.createdAt),
  ],
);
```

```typescript
// server/src/db/schema/party-turn-actions.ts

import {
  boolean,
  index,
  integer,
  jsonb,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from 'drizzle-orm/pg-core';
import { users } from './users.js';
import { runSessions } from './run-sessions.js';

/**
 * 파티 턴에서 각 멤버의 개별 행동 기록.
 * 전원 제출 or 타임아웃 후 PartyTurnService가 통합 처리.
 */
export const partyTurnActions = pgTable(
  'party_turn_actions',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    runId: uuid('run_id')
      .notNull()
      .references(() => runSessions.id),
    turnNo: integer('turn_no').notNull(),
    userId: uuid('user_id')
      .notNull()
      .references(() => users.id),
    inputType: text('input_type').notNull(), // ACTION | CHOICE
    rawInput: text('raw_input').notNull(),
    isAutoAction: boolean('is_auto_action').notNull().default(false), // 타임아웃 자동 행동
    actionData: jsonb('action_data').$type<Record<string, unknown>>(),
    submittedAt: timestamp('submitted_at').defaultNow().notNull(),
  },
  (table) => [
    uniqueIndex('party_turn_actions_run_turn_user_idx').on(
      table.runId,
      table.turnNo,
      table.userId,
    ),
    index('party_turn_actions_run_turn_idx').on(table.runId, table.turnNo),
  ],
);
```

```typescript
// server/src/db/schema/party-votes.ts

import {
  boolean,
  index,
  integer,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from 'drizzle-orm/pg-core';
import { users } from './users.js';
import { parties } from './parties.js';

/**
 * 이동 투표. 누구든 제안 가능, 과반수 동의 시 이동 실행.
 */
export const VOTE_STATUS = ['PENDING', 'APPROVED', 'REJECTED', 'EXPIRED'] as const;
export type VoteStatus = (typeof VOTE_STATUS)[number];

export const partyVotes = pgTable(
  'party_votes',
  {
    id: uuid('id').primaryKey().defaultRandom(),
    partyId: uuid('party_id')
      .notNull()
      .references(() => parties.id),
    runId: uuid('run_id'), // 파티 런 진행 중일 때만
    proposerId: uuid('proposer_id')
      .notNull()
      .references(() => users.id),
    voteType: text('vote_type').notNull().default('MOVE_LOCATION'), // 확장 가능
    targetLocationId: text('target_location_id'), // MOVE_LOCATION 시
    status: text('status', { enum: VOTE_STATUS })
      .notNull()
      .default('PENDING'),
    yesVotes: integer('yes_votes').notNull().default(1), // 제안자 자동 찬성
    noVotes: integer('no_votes').notNull().default(0),
    totalMembers: integer('total_members').notNull(),
    votedUserIds: text('voted_user_ids').array(), // 투표 완료한 유저 ID 목록
    expiresAt: timestamp('expires_at').notNull(), // 30초 제한
    resolvedAt: timestamp('resolved_at'),
    createdAt: timestamp('created_at').defaultNow().notNull(),
  },
  (table) => [
    index('party_votes_party_status_idx').on(table.partyId, table.status),
  ],
);
```

### 3.2 기존 테이블 변경

```typescript
// run_sessions 테이블에 추가할 컬럼 (server/src/db/schema/run-sessions.ts)

// 기존 컬럼 뒤에 추가:
partyId: uuid('party_id').references(() => parties.id),  // null = 솔로 런
runMode: text('run_mode', { enum: ['SOLO', 'PARTY'] as const })
  .notNull()
  .default('SOLO'),
```

### 3.3 전체 테이블 관계도

```
users ──< party_members >── parties
  |                            |
  |                            ├──< chat_messages
  |                            ├──< party_votes
  |                            └──< run_sessions (partyId FK)
  |                                    |
  └──< party_turn_actions ─────────────┘ (runId FK)
```

### 3.4 마이그레이션

```bash
# 스키마 파일 추가 후
cd server && npx drizzle-kit push
```

---

## 4. API 설계

### 4.1 REST API

모든 엔드포인트는 `AuthGuard` 적용 (JWT 필수).

#### 파티 관리

| Method | Path | Purpose | Request Body | Response |
|--------|------|---------|-------------|----------|
| POST | `/v1/parties` | 파티 생성 | `{ name: string }` | `PartyDTO` |
| GET | `/v1/parties` | 파티 목록 검색 | `?status=OPEN&q=검색어&cursor=&limit=20` | `{ items: PartyDTO[], nextCursor }` |
| GET | `/v1/parties/my` | 내 파티 조회 | - | `PartyDTO \| null` |
| GET | `/v1/parties/:partyId` | 파티 상세 | - | `PartyDetailDTO` (멤버 목록 포함) |
| POST | `/v1/parties/join` | 초대코드로 가입 | `{ inviteCode: string }` | `PartyDTO` |
| POST | `/v1/parties/:partyId/leave` | 파티 탈퇴 | - | `{ ok: true }` |
| POST | `/v1/parties/:partyId/kick` | 멤버 추방 (리더) | `{ userId: string }` | `{ ok: true }` |
| DELETE | `/v1/parties/:partyId` | 파티 해산 (리더) | - | `{ ok: true }` |
| POST | `/v1/parties/:partyId/refresh-code` | 초대코드 재생성 (리더) | - | `{ inviteCode: string }` |

#### 채팅

| Method | Path | Purpose | Query | Response |
|--------|------|---------|-------|----------|
| GET | `/v1/parties/:partyId/messages` | 채팅 히스토리 | `?cursor=&limit=50` | `{ items: ChatMessageDTO[], nextCursor }` |

#### 파티 런 (Phase 2)

| Method | Path | Purpose | Request Body | Response |
|--------|------|---------|-------------|----------|
| POST | `/v1/parties/:partyId/runs` | 파티 런 생성 (리더) | `{ presetId?, gender? }` | `PartyRunDTO` |
| GET | `/v1/parties/:partyId/runs/:runId` | 파티 런 상태 | - | `PartyRunDTO` |
| POST | `/v1/parties/:partyId/runs/:runId/turns` | 개별 행동 제출 | `{ inputType, rawInput, idempotencyKey }` | `PartyTurnActionDTO` |
| GET | `/v1/parties/:partyId/runs/:runId/turns/:turnNo` | 통합 턴 결과 | - | `PartyTurnResultDTO` |

#### 로비 (Phase 2)

| Method | Path | Purpose | Request Body | Response |
|--------|------|---------|-------------|----------|
| POST | `/v1/parties/:partyId/lobby/ready` | 준비 완료 토글 | `{ ready: boolean }` | `LobbyStateDTO` |
| GET | `/v1/parties/:partyId/lobby` | 로비 상태 | - | `LobbyStateDTO` |

### 4.2 WebSocket (namespace: `/party`)

인증: handshake `auth: { token }` -> JWT 검증 -> `socket.data.userId`, `socket.data.nickname`

#### Client -> Server 이벤트

| Event | Payload | Phase | Description |
|-------|---------|-------|-------------|
| `party:join_room` | `{ partyId }` | 1 | 소켓을 파티 room에 참가 |
| `party:leave_room` | `{ partyId }` | 1 | 소켓을 room에서 퇴장 |
| `chat:send` | `{ partyId, content }` | 1 | 채팅 메시지 전송 (최대 500자) |
| `lobby:ready` | `{ partyId, ready }` | 2 | 준비 상태 토글 |
| `lobby:start` | `{ partyId }` | 2 | 던전 시작 (리더, 전원 준비 필요) |
| `dungeon:submit_action` | `{ partyId, runId, turnNo, inputType, rawInput }` | 2 | 개별 행동 제출 |
| `vote:propose` | `{ partyId, voteType, targetLocationId }` | 2 | 이동 투표 제안 |
| `vote:cast` | `{ partyId, voteId, choice: 'yes' \| 'no' }` | 2 | 투표 참여 |

#### Server -> Client 이벤트

| Event | Payload | Phase | Description |
|-------|---------|-------|-------------|
| `chat:new_message` | `ChatMessageDTO` | 1 | 새 메시지 (TEXT/SYSTEM/GAME_EVENT) |
| `party:member_joined` | `{ userId, nickname, memberCount }` | 1 | 멤버 가입 |
| `party:member_left` | `{ userId, nickname, memberCount, newLeaderId? }` | 1 | 멤버 탈퇴/추방 |
| `party:member_online` | `{ userId, isOnline }` | 1 | 접속 상태 변경 |
| `party:disbanded` | `{ partyId }` | 1 | 파티 해산 |
| `party:leader_changed` | `{ newLeaderId, nickname }` | 1 | 리더 위임 |
| `party:error` | `{ code, message }` | 1 | 에러 |
| `lobby:state_updated` | `LobbyStateDTO` | 2 | 로비 상태 (준비 현황) |
| `lobby:dungeon_starting` | `{ runId, countdown }` | 2 | 던전 시작 카운트다운 |
| `dungeon:action_received` | `{ userId, nickname }` | 2 | "X가 행동을 제출했습니다" |
| `dungeon:waiting` | `{ submitted: string[], pending: string[], deadline }` | 2 | 제출 대기 현황 |
| `dungeon:timeout_warning` | `{ secondsLeft }` | 2 | 제출 시한 임박 (10초, 5초) |
| `dungeon:turn_resolved` | `PartyTurnResultDTO` | 2 | 통합 턴 결과 |
| `dungeon:turn_narrative` | `{ turnNo, narrative }` | 2 | LLM 서술 완성 |
| `vote:proposed` | `PartyVoteDTO` | 2 | 새 투표 |
| `vote:updated` | `PartyVoteDTO` | 2 | 투표 현황 갱신 |
| `vote:resolved` | `{ voteId, status, targetLocationId? }` | 2 | 투표 결과 |

### 4.3 DTO 정의

```typescript
// PartyDTO
interface PartyDTO {
  id: string;
  name: string;
  leaderId: string;
  status: PartyStatus;
  memberCount: number;
  maxMembers: number;
  inviteCode: string;  // 본인이 멤버일 때만 노출
  createdAt: string;
}

// PartyDetailDTO
interface PartyDetailDTO extends PartyDTO {
  members: {
    userId: string;
    nickname: string;
    role: PartyRole;
    isOnline: boolean;
    presetId?: string;    // 캐릭터 프리셋 (표시용)
    joinedAt: string;
  }[];
}

// ChatMessageDTO
interface ChatMessageDTO {
  id: string;
  partyId: string;
  senderId: string | null;
  senderNickname: string | null;
  type: MessageType;
  content: string;
  createdAt: string;
}

// LobbyStateDTO (Phase 2)
interface LobbyStateDTO {
  partyId: string;
  members: {
    userId: string;
    nickname: string;
    presetId: string;
    gender: string;
    isReady: boolean;
    isOnline: boolean;
  }[];
  allReady: boolean;
  canStart: boolean;  // 리더 + 전원 준비 + 2명 이상
}

// PartyTurnResultDTO (Phase 2)
interface PartyTurnResultDTO {
  runId: string;
  turnNo: number;
  actions: {
    userId: string;
    nickname: string;
    rawInput: string;
    isAutoAction: boolean;
    resolveOutcome?: string;  // SUCCESS | PARTIAL | FAIL
  }[];
  serverResult: ServerResultV1;  // 통합 결과
  llmStatus: string;
  narrative?: string;
}

// PartyVoteDTO (Phase 2)
interface PartyVoteDTO {
  id: string;
  partyId: string;
  proposerId: string;
  proposerNickname: string;
  voteType: string;
  targetLocationId?: string;
  targetLocationName?: string;
  status: VoteStatus;
  yesVotes: number;
  noVotes: number;
  totalMembers: number;
  expiresAt: string;
}
```

---

## 5. 서버 모듈 구조

```
server/src/party/
  ├── party.module.ts              # PartyModule (imports: AuthModule)
  ├── party.controller.ts          # REST 엔드포인트 (파티 CRUD, 채팅 조회)
  ├── party.service.ts             # 파티 생성/가입/탈퇴/해산/검색
  ├── chat.service.ts              # 채팅 메시지 저장/조회, 시스템 메시지 생성
  ├── party.gateway.ts             # WebSocket Gateway (/party namespace)
  ├── ws-auth.guard.ts             # WebSocket JWT 인증 가드
  ├── lobby.service.ts             # [Phase 2] 로비 상태 관리, 준비 체크
  ├── vote.service.ts              # [Phase 2] 이동 투표 생성/참여/집계
  ├── party-turn.service.ts        # [Phase 2] 개별 행동 수집 → 통합 처리 → 브로드캐스트
  ├── party-reward.service.ts      # [Phase 2] 보상 분배 (주사위 굴림)
  └── dto/
      ├── create-party.dto.ts      # Zod: { name: z.string().min(1).max(30) }
      ├── join-party.dto.ts        # Zod: { inviteCode: z.string().length(6) }
      ├── kick-member.dto.ts       # Zod: { userId: z.string().uuid() }
      ├── submit-action.dto.ts     # [Phase 2] Zod: { inputType, rawInput, idempotencyKey }
      └── cast-vote.dto.ts         # [Phase 2] Zod: { voteId, choice }
```

### 5.1 파일별 역할 상세

#### `party.module.ts`

```typescript
@Module({
  imports: [],  // AuthModule은 @Global이므로 별도 import 불필요
  controllers: [PartyController],
  providers: [
    PartyService,
    ChatService,
    PartyGateway,
    // Phase 2:
    // LobbyService,
    // VoteService,
    // PartyTurnService,
    // PartyRewardService,
  ],
  exports: [PartyService],
})
export class PartyModule {}
```

#### `party.gateway.ts`

```typescript
@WebSocketGateway({
  namespace: '/party',
  cors: { origin: '*' },  // 프로덕션에서 도메인 제한
})
export class PartyGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer() server: Server;

  // 연결 시: JWT 검증 → socket.data에 userId/nickname 저장
  async handleConnection(socket: Socket): Promise<void> { ... }

  // 연결 해제 시: 온라인 상태 업데이트 → 파티원에게 브로드캐스트
  // 리더 이탈 시 자동 위임 (joinedAt 기준 다음 멤버)
  async handleDisconnect(socket: Socket): Promise<void> { ... }

  @SubscribeMessage('party:join_room')
  async handleJoinRoom(socket, payload): Promise<void> {
    // 멤버십 확인 → socket.join(partyId) → 온라인 상태 업데이트
  }

  @SubscribeMessage('chat:send')
  async handleChatSend(socket, payload): Promise<void> {
    // 검증 → chatService.save() → room에 브로드캐스트
  }

  // Phase 2: lobby:ready, lobby:start, dungeon:submit_action, vote:*
}
```

#### `party.service.ts`

| 메서드 | 역할 |
|--------|------|
| `createParty(userId, name)` | 파티 생성, 초대코드 발급, 리더로 자동 가입 |
| `joinByInviteCode(userId, code)` | 코드 검증 → 인원 체크 → 가입 (중복 방지) |
| `searchParties(query, status, cursor, limit)` | OPEN 파티 검색 (이름 부분 일치) |
| `getMyParty(userId)` | 현재 소속 파티 조회 (1인 1파티 제한) |
| `leaveParty(userId, partyId)` | 탈퇴. 리더 탈퇴 시 자동 위임 or 해산 |
| `kickMember(leaderId, partyId, targetId)` | 리더만 가능. 대상에게 kicked 이벤트 전송 |
| `disbandParty(leaderId, partyId)` | 해산. 전원에게 disbanded 이벤트 |
| `refreshInviteCode(leaderId, partyId)` | 초대코드 재생성 |
| `transferLeadership(partyId, newLeaderId)` | 리더 위임 (이탈/접속 종료 시 내부 호출) |
| `generateInviteCode()` | 6자리 영숫자 랜덤 (충돌 시 재시도) |

#### `chat.service.ts`

| 메서드 | 역할 |
|--------|------|
| `saveMessage(partyId, senderId, type, content)` | DB 저장 + DTO 반환 |
| `getHistory(partyId, cursor, limit)` | 커서 기반 역순 조회 |
| `sendSystemMessage(partyId, content)` | senderId=null, type=SYSTEM |
| `sendGameEvent(partyId, content)` | type=GAME_EVENT (턴 결과 요약 등) |

#### `party-turn.service.ts` (Phase 2)

| 메서드 | 역할 |
|--------|------|
| `submitAction(runId, turnNo, userId, input)` | 개별 행동 저장 → 전원 제출 체크 |
| `checkAllSubmitted(runId, turnNo)` | 제출 현황 확인 → 전원 시 resolveTurn 호출 |
| `resolveTurn(runId, turnNo)` | 4인분 행동 통합 → 기존 engine 파이프라인 호출 → 결과 브로드캐스트 |
| `handleTimeout(runId, turnNo)` | 30초 경과 시 미제출자 자동 행동 삽입 → resolveTurn |
| `getAutoAction(nodeType)` | 미제출 시 자동 행동: LOCATION=OBSERVE, COMBAT=DEFEND |

#### `party-reward.service.ts` (Phase 2)

| 메서드 | 역할 |
|--------|------|
| `distributeLoot(runId, turnNo, lootItems)` | 아이템별 주사위 굴림 → 당첨자 결정 |
| `distributeGold(runId, turnNo, totalGold, memberIds)` | 균등 분배 (나머지는 리더) |
| `syncToSoloRuns(partyId)` | 파티 런 종료 시 솔로 런에 보상 반영 |

---

## 6. 클라이언트 구조

### 6.1 파일 구조

```
client/src/
  ├── lib/
  │   └── socket-client.ts              # socket.io-client 싱글턴 관리
  ├── store/
  │   └── party-store.ts                # Zustand 파티+채팅+로비 스토어
  └── components/
      └── party/
          ├── PartyButton.tsx            # 타이틀 화면 "파티" 진입 버튼
          ├── PartyPanel.tsx             # 파티 메인 패널 (생성/가입/현재 파티)
          ├── PartyCreateModal.tsx        # 파티 생성 모달
          ├── PartyJoinModal.tsx          # 초대코드 입력 모달
          ├── PartySearchModal.tsx        # 파티 목록 검색 모달
          ├── PartyMemberList.tsx         # 멤버 목록 (온/오프라인, 역할 표시)
          ├── PartyInviteCode.tsx         # 초대코드 표시 + 복사 버튼
          ├── ChatWindow.tsx             # 채팅 메시지 영역 (스크롤, 자동 하단 고정)
          ├── ChatInput.tsx              # 메시지 입력 (Enter 전송, 500자 제한)
          ├── ChatMessage.tsx            # 개별 메시지 (TEXT=흰색, SYSTEM=노랑, GAME_EVENT=회색)
          ├── LobbyScreen.tsx            # [Phase 2] 전체 화면 로비 (캐릭터 표시, 준비 버튼)
          ├── LobbyMemberCard.tsx         # [Phase 2] 로비 내 멤버 카드
          ├── PartyHud.tsx               # [Phase 2] 던전 진행 시 상단 파티원 HUD
          ├── PartyTurnStatus.tsx         # [Phase 2] "X/4 제출 완료" 표시
          ├── VoteModal.tsx              # [Phase 2] 이동 투표 제안/참여 모달
          └── LootDistribution.tsx       # [Phase 2] 주사위 굴림 보상 분배 UI
```

### 6.2 소켓 클라이언트 싱글턴

```typescript
// client/src/lib/socket-client.ts

import { io, Socket } from 'socket.io-client';

let socket: Socket | null = null;

export function getPartySocket(token: string): Socket {
  if (socket?.connected) return socket;

  const baseUrl = getBaseUrl(); // auth-store.ts와 동일 패턴
  socket = io(`${baseUrl}/party`, {
    auth: { token },
    transports: ['websocket'],
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
  });

  return socket;
}

export function disconnectPartySocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}
```

### 6.3 파티 스토어

```typescript
// client/src/store/party-store.ts

import { create } from 'zustand';

interface PartyMember {
  userId: string;
  nickname: string;
  role: 'LEADER' | 'MEMBER';
  isOnline: boolean;
  presetId?: string;
  isReady?: boolean;  // Phase 2: 로비
}

interface ChatMessage {
  id: string;
  senderId: string | null;
  senderNickname: string | null;
  type: 'TEXT' | 'SYSTEM' | 'GAME_EVENT';
  content: string;
  createdAt: string;
}

interface PartyInfo {
  id: string;
  name: string;
  leaderId: string;
  status: string;
  inviteCode: string;
  memberCount: number;
}

interface PartyState {
  // -- 상태 --
  party: PartyInfo | null;
  members: PartyMember[];
  messages: ChatMessage[];       // 최근 200개 (클라이언트 캡)
  isConnected: boolean;
  unreadCount: number;
  lobbyState: LobbyStateDTO | null;  // Phase 2
  currentVote: PartyVoteDTO | null;  // Phase 2
  turnStatus: {                      // Phase 2
    turnNo: number;
    submitted: string[];
    pending: string[];
    deadline: string;
  } | null;

  // -- 액션 --
  createParty(name: string): Promise<void>;
  joinParty(inviteCode: string): Promise<void>;
  leaveParty(): Promise<void>;
  fetchMyParty(): Promise<void>;
  sendMessage(content: string): void;      // WebSocket
  connectSocket(token: string): void;
  disconnectSocket(): void;

  // Phase 2 액션
  toggleReady(): void;
  startDungeon(): void;
  submitAction(input: string): void;
  proposeMove(locationId: string): void;
  castVote(voteId: string, choice: 'yes' | 'no'): void;
}
```

### 6.4 UI 배치

#### Phase 1: 채팅

- **타이틀 화면**: "솔로 플레이" 옆에 "파티" 버튼 추가
- **파티 화면**: 전용 라우트 `/play/party` (파티 관리 + 채팅)
- **게임 중**: SidePanel에 "파티" 탭 추가 (기존: 캐릭터, 인벤토리, 퀘스트)
  - 채팅 + 게임 서술이 같은 화면에 혼합
  - 채팅 메시지는 회색 배경으로 구분
  - GAME_EVENT 메시지는 기울임체 + 아이콘

#### Phase 2: 던전

- **로비**: 전체 화면 전환 (`/play/party/lobby`)
  - 캐릭터 카드 (프리셋 아이콘, 닉네임, 스탯 요약)
  - "준비 완료" 토글 버튼
  - 리더: "던전 시작" 버튼 (전원 준비 시 활성)
- **던전 진행**: 기존 게임 레이아웃 재사용
  - **상단**: 파티원 HUD (HP 바, 상태 아이콘, 제출 여부)
  - **서술 영역**: 통합 서사 + 채팅 혼합
  - **입력 영역**: 기존 ActionInput 재사용 (타이머 표시 추가)
- **모바일**: 완전 지원 (기존 MobileBottomNav에 파티 탭 추가)

---

## 7. 핵심 플로우 시퀀스 다이어그램

### 7.1 파티 생성 -> 가입 -> 채팅 (Phase 1)

```
[유저 A: 파티 생성]
  A.Client                    Server                        DB
  ──────                    ──────                        ──
  POST /v1/parties          →  PartyService.create()
  { name: "용병단" }            generateInviteCode()
                                insert parties (leaderId=A) →  parties
                                insert party_members (LEADER) →  party_members
                            ←  { id, name, inviteCode: "X3K9M2" }
  
  WebSocket connect         →  PartyGateway.handleConnection()
  auth: { token }              JWT 검증 → socket.data.userId = A
  
  emit party:join_room      →  멤버십 확인 → socket.join(partyId)
  { partyId }                   isOnline = true

[유저 B: 초대코드 가입]
  B.Client                    Server                        DB
  ──────                    ──────                        ──
  POST /v1/parties/join     →  PartyService.joinByInviteCode()
  { inviteCode: "X3K9M2" }     파티 조회 → 인원 체크 (< 4)
                                insert party_members (MEMBER) →  party_members
                                ChatService.sendSystemMessage("B 가입")
                                gateway.to(partyId).emit('party:member_joined')
                            ←  PartyDTO

  B: WebSocket connect + join_room → (위와 동일)

[채팅]
  A.Client                    Server                        DB
  ──────                    ──────                        ──
  emit chat:send            →  ChatService.saveMessage()    →  chat_messages
  { partyId, content }         gateway.to(partyId).emit('chat:new_message')
                            →  B.Client: chat:new_message { senderNickname: "A", ... }
```

### 7.2 던전 로비 -> 진입 -> 턴 처리 -> 보상 (Phase 2)

```
[로비]
  A(Leader).Client            Server                        DB
  ──────────                ──────                        ──
  /play/party/lobby 진입
  
  B: emit lobby:ready       →  LobbyService.toggleReady(B, true)
  C: emit lobby:ready       →  LobbyService.toggleReady(C, true)
  A: emit lobby:ready       →  LobbyService.toggleReady(A, true)
                                allReady = true
                                → all: lobby:state_updated { allReady: true }

  A: emit lobby:start       →  LobbyService.canStart() 확인
                                PartyService.setStatus('IN_DUNGEON')
                                RunsService.createPartyRun(partyId, members)
                                  → run_sessions (runMode=PARTY, partyId)
                                → all: lobby:dungeon_starting { runId, countdown: 3 }

[턴 처리]
  Server                        각 Client
  ──────                        ──────────
  턴 시작 → 30초 타이머 시작
  
  A: emit dungeon:submit_action →  PartyTurnService.submitAction(A)
  { rawInput: "도적을 공격" }       → party_turn_actions INSERT
                                    → all: dungeon:action_received { userId: A }
                                    → all: dungeon:waiting { submitted: [A], pending: [B,C] }
  
  B: emit dungeon:submit_action →  PartyTurnService.submitAction(B)
  { rawInput: "방어 자세" }         checkAllSubmitted() → 아직 C 미제출
  
  ... 30초 경과, C 미제출 ...
  
  Server: handleTimeout()       →  C에 자동 행동 삽입 (OBSERVE/DEFEND)
                                   → party_turn_actions INSERT (isAutoAction=true)

  PartyTurnService.resolveTurn():
    1. party_turn_actions에서 3명분 조회
    2. 각 행동을 IntentParserV2로 파싱
    3. 통합 ResolveService 호출 (각자 독립 판정)
    4. ServerResultV1 생성 (events에 각자 결과 포함)
    5. turns INSERT (통합 결과)
    6. → all: dungeon:turn_resolved { actions[], serverResult }
    7. [async] LLM Worker: 4인분 행동 → 통합 서사 생성
    8. → all: dungeon:turn_narrative { narrative }

[보상 분배]
  전투 종료 시:
    PartyRewardService.distributeLoot():
      아이템별 1d6 → 가장 높은 유저에게
      동점 시 재굴림
    PartyRewardService.distributeGold():
      totalGold / memberCount (나머지 → 리더)
    → all: dungeon:loot_distributed { results[] }
```

### 7.3 이동 투표 (Phase 2)

```
  A.Client                    Server                        DB
  ──────                    ──────                        ──
  emit vote:propose          →  VoteService.createVote()
  { targetLocationId:            insert party_votes          →  party_votes
    "market_district" }          (proposerId=A, yesVotes=1, expiresAt=now+30s)
                                → all: vote:proposed { ... }

  B: emit vote:cast          →  VoteService.castVote(B, 'yes')
  { voteId, choice: 'yes' }     yesVotes++ → 2/3 = 과반수!
                                VoteService.resolveVote('APPROVED')
                                PartyTurnService.executeMove(targetLocationId)
                                ChatService.sendGameEvent("시장 구역으로 이동합니다")
                                → all: vote:resolved { status: 'APPROVED' }
                                → all: dungeon:location_changed { locationId }

  [과반수 미달 + 30초 경과]
  Server: VoteService.expireVote()
                                → all: vote:resolved { status: 'EXPIRED' }
```

### 7.4 멤버 이탈/합류 (Phase 1 + Phase 2)

```
[접속 종료 → 리더 자동 위임]
  A(Leader) 연결 끊김       →  PartyGateway.handleDisconnect()
                                isOnline = false
                                30초 대기 (재연결 유예)
                                ... 재연결 없음 ...
                                PartyService.transferLeadership(partyId, B)
                                  B.role = LEADER
                                → all: party:leader_changed { newLeaderId: B }
                                → all: party:member_online { userId: A, isOnline: false }

[던전 중 멤버 이탈 (Phase 2)]
  C 연결 끊김               →  PartyGateway.handleDisconnect()
                                30초 대기 → 재연결 없음
                                PartyTurnService.setAiControlled(runId, C)
                                  이후 C의 행동 = 자동 (getAutoAction)
                                ChatService.sendSystemMessage("C가 이탈. AI가 대신 행동합니다")
                                → all: party:member_ai_controlled { userId: C }

[중간 합류 (Phase 2)]
  D: POST /v1/parties/join   →  PartyService.joinByInviteCode()
                                 상태 IN_DUNGEON → 즉시 파티 런에 참가
                                 PartyTurnService.addMidJoinMember(runId, D)
                                   현재 턴 이후부터 행동 가능
                                 ChatService.sendSystemMessage("D가 합류했습니다")
                                 → all: party:member_joined { userId: D, midJoin: true }
```

---

## 8. Phase 1 구현 계획 (채팅 + 파티 관리)

### Step 1: 서버 인프라 (2일)

| 작업 | 상세 |
|------|------|
| 의존성 설치 | `pnpm add @nestjs/websockets @nestjs/platform-socket.io socket.io` |
| DB 스키마 | `parties.ts`, `party-members.ts`, `chat-messages.ts` 생성 |
| schema/index.ts | 3개 테이블 export 추가 |
| WsAuthGuard | `ws-auth.guard.ts` — JWT 검증, socket.data 할당 |
| Drizzle push | `npx drizzle-kit push` |

### Step 2: 파티 모듈 REST API (2일)

| 작업 | 상세 |
|------|------|
| PartyService | create, join, leave, kick, disband, search, getMyParty |
| ChatService | saveMessage, getHistory, sendSystemMessage |
| PartyController | 7개 REST 엔드포인트 |
| DTO + Zod 검증 | create-party.dto.ts, join-party.dto.ts, kick-member.dto.ts |
| 초대코드 생성 | 6자리 영숫자, unique 충돌 시 재시도 (최대 5회) |
| 1인 1파티 제한 | 이미 파티 소속 시 가입 거부 (409 Conflict) |

### Step 3: WebSocket Gateway (2일)

| 작업 | 상세 |
|------|------|
| PartyGateway | handleConnection, handleDisconnect |
| Room 관리 | join_room, leave_room (socket.io room = partyId) |
| 채팅 핸들러 | chat:send → DB 저장 → room 브로드캐스트 |
| 온라인 상태 | 연결/해제 시 isOnline 갱신 + 브로드캐스트 |
| 리더 위임 | disconnect 30초 후 자동 위임 (setTimeout, 재연결 시 취소) |
| 에러 처리 | 비멤버 접근 차단, 메시지 길이 검증 (500자) |

### Step 4: 클라이언트 연결 계층 (1일)

| 작업 | 상세 |
|------|------|
| socket.io-client 설치 | `pnpm add socket.io-client` |
| socket-client.ts | 싱글턴 관리, 자동 재연결, 토큰 갱신 |
| party-store.ts | Zustand 스토어 (파티 상태, 메시지, 소켓 액션) |
| 이벤트 바인딩 | connectSocket() 내에서 모든 서버 이벤트 리스너 등록 |

### Step 5: 클라이언트 UI 컴포넌트 (3일)

| 작업 | 상세 |
|------|------|
| PartyButton | 타이틀 화면 "파티" 버튼 |
| PartyPanel | 파티 관리 메인 화면 (미가입: 생성/검색/코드입력, 가입: 채팅+멤버) |
| PartyCreateModal | 이름 입력 → 생성 → 코드 표시 |
| PartyJoinModal | 코드 입력 → 가입 |
| PartySearchModal | OPEN 파티 목록 (무한 스크롤) → 가입 버튼 |
| ChatWindow | 메시지 렌더링 (스크롤 고정, 새 메시지 자동 스크롤) |
| ChatInput | 입력 + Enter 전송 |
| ChatMessage | 타입별 스타일링 (TEXT/SYSTEM/GAME_EVENT) |
| PartyMemberList | 멤버 (역할 배지, 온/오프라인 점) |
| PartyInviteCode | 코드 + 복사 버튼 |
| SidePanel 탭 추가 | 기존 side-panel에 "파티" 탭 |
| 모바일 대응 | MobileBottomNav에 파티 아이콘 |

### Step 6: 통합 테스트 + 엣지 케이스 (1일)

| 작업 | 상세 |
|------|------|
| 멀티 탭 테스트 | 같은 유저 2탭 접속 시 동작 확인 |
| 리더 이탈 | 위임 + 해산 (1인 잔류 시) |
| 만석 처리 | 4명 가입 → FULL → 추가 가입 거부 |
| 재연결 | 네트워크 끊김 → 자동 재연결 → 메시지 정합성 |
| 빌드 검증 | `cd server && pnpm build` + `cd client && pnpm build` |

**Phase 1 합계: 약 11일 (3주, 여유 포함)**

---

## 9. Phase 2 구현 계획 (협동 던전)

### Step 1: DB 확장 + 서비스 (3일)

| 작업 | 상세 |
|------|------|
| party-turn-actions.ts | 스키마 생성 + push |
| party-votes.ts | 스키마 생성 + push |
| run-sessions.ts 수정 | partyId, runMode 컬럼 추가 |
| PartyTurnService | 행동 수집, 통합 처리, 타임아웃 |
| VoteService | 투표 생성, 참여, 집계, 만료 |
| PartyRewardService | 주사위 분배, 솔로 런 동기화 |

### Step 2: 턴 파이프라인 확장 (5일)

| 작업 | 상세 |
|------|------|
| turns.service.ts 분기 | runMode=PARTY 시 PartyTurnService 위임 |
| 통합 판정 | 각 멤버별 독립 IntentParser + Resolve → 결과 병합 |
| LLM 통합 서술 | context-builder: 4인분 행동/결과 → 하나의 프롬프트 |
| 토큰 예산 증가 | PARTY 모드: 2500 → 4000 토큰 |
| 타임아웃 관리 | 30초 타이머 (setTimeout). 10초/5초 경고 이벤트 |
| 자동 행동 | LOCATION=OBSERVE, COMBAT=DEFEND |

### Step 3: 이동 투표 (2일)

| 작업 | 상세 |
|------|------|
| vote:propose 핸들러 | VoteService.createVote → 브로드캐스트 |
| vote:cast 핸들러 | 집계 → 과반수 도달 시 이동 실행 |
| 만료 처리 | 30초 타이머 → EXPIRED |
| UI 투표 모달 | 팝업 + 찬성/반대 버튼 + 타이머 |

### Step 4: 로비 화면 (3일)

| 작업 | 상세 |
|------|------|
| LobbyService | 준비 상태 관리, 시작 조건 체크 |
| LobbyScreen | 전체 화면 (캐릭터 카드 4장, 준비 버튼) |
| LobbyMemberCard | 프리셋 아이콘, 닉네임, 스탯 요약, 준비 체크 |
| 던전 시작 플로우 | 리더 시작 → 카운트다운 3초 → 게임 화면 전환 |
| 파티 런 생성 | RunsService 확장: createPartyRun(partyId, memberIds) |

### Step 5: 던전 UI (4일)

| 작업 | 상세 |
|------|------|
| PartyHud | 상단 고정: 파티원 HP 바, 상태 아이콘, 제출 여부 |
| PartyTurnStatus | "2/4 제출 완료" + 타이머 바 |
| 채팅+서술 혼합 | ChatMessage 회색 vs 게임 서술 기존 스타일 |
| LootDistribution | 주사위 애니메이션 + 당첨자 표시 |
| VoteModal | 이동 제안 팝업 |
| 모바일 대응 | PartyHud 축소 모드 (아이콘만) |

### Step 6: 보상 동기화 + 이탈 처리 (2일)

| 작업 | 상세 |
|------|------|
| 파티 런 종료 | 아이템+골드+경험치 → 각 멤버의 솔로 캐릭터에 반영 |
| AI 자동 행동 | 이탈 멤버 턴마다 getAutoAction 호출 |
| 중간 합류 | 새 멤버 즉시 참가, 현재 턴 이후부터 행동 가능 |
| 리더 이탈 | 자동 위임 → 파티 런 계속 진행 |

### Step 7: 통합 테스트 (2일)

| 작업 | 상세 |
|------|------|
| 4인 동시 턴 | 전원 제출 → 통합 결과 확인 |
| 타임아웃 | 미제출 30초 → 자동 행동 → 정상 처리 |
| 이동 투표 | 과반수/미달/만료 3가지 시나리오 |
| 중간 이탈/합류 | AI 전환, 재합류 |
| 보상 분배 | 주사위 공정성, 솔로 동기화 |
| LLM 통합 서술 | 4인분 서사 품질 확인 |
| 빌드 검증 | `cd server && pnpm build` + `cd client && pnpm build` |

**Phase 2 합계: 약 21일 (5주, 여유 포함)**

---

## 10. Phase 3 고도화 (런 통합) 방향

### 10.1 개요

Phase 2까지는 "파티 전용 런"으로 솔로와 완전 분리된다. Phase 3에서는 파티장의 기존 솔로 런 세계에 다른 멤버들이 합류하는 "런 통합" 모델을 도입한다.

### 10.2 런 통합 모델

```
파티장 (기존 솔로 런 보유)
  → "내 세계에 초대" 기능
  → 파티원이 파티장의 run_session에 합류
  → 파티장의 WorldState, Heat, Incident, NPC 관계 등 공유
  → 각 파티원은 자신의 스탯/장비로 행동
  → 파티 해산 시 파티원의 경험/보상만 솔로로 반영
```

### 10.3 필요 변경

| 영역 | 변경 |
|------|------|
| run_sessions | 멀티 유저 참조 (run_participants 테이블 신설) |
| WorldState | 파티장 기준 단일 유지 (멤버는 읽기 참여) |
| NPC 관계 | 파티장의 NPC posture 기준, 멤버 행동은 개별 영향 |
| 메모리 | 파티장 runMemories에 멤버 행동도 기록 |
| LLM 컨텍스트 | 4인 배경 + 파티장 세계 상태 조합 |

### 10.4 기술 스케일링

| 영역 | Phase 2 | Phase 3 |
|------|---------|---------|
| 동시접속 | 10명 이하 | 50명+ |
| WebSocket | 단일 서버 메모리 | `@socket.io/redis-adapter` |
| 타이머 | setTimeout | BullMQ delayed job |
| 세션 | PostgreSQL | PostgreSQL + Redis 캐시 |
| 배포 | 단일 인스턴스 | 수평 확장 (PM2 cluster or K8s) |

### 10.5 런 통합 시 불변식 추가

1. **파티장 WorldState 단일성** --- WorldState는 파티장의 것만 존재. 멤버는 읽기만.
2. **행동 독립 + 결과 합산** --- 각 멤버의 Resolve는 독립, 후폭풍/Heat/NPC 영향은 합산.
3. **이탈 무해성** --- 멤버 이탈 시 파티장 월드에 부작용 없음 (보상만 정산).
4. **메모리 귀속** --- 합류 기간 메모리는 파티장 런에 귀속, 멤버에게는 요약만 복사.

---

## 부록 A: 기술 선택 근거

### WebSocket 라이브러리

| 옵션 | 장점 | 단점 | 판정 |
|------|------|------|------|
| socket.io | NestJS 공식 지원, room/namespace, 자동 재연결, 폴백 | 번들 ~45KB | **채택** |
| ws (raw) | 경량 ~3KB | room/reconnect 직접 구현 필요 | 제외 |
| SSE | 단방향 충분할 수 있음 | 양방향 채팅 부적합 | 제외 |

### 서버 의존성 추가

```bash
# 서버
cd server && pnpm add @nestjs/websockets @nestjs/platform-socket.io socket.io

# 클라이언트
cd client && pnpm add socket.io-client
```

### Redis 도입 시점

- Phase 1~2: **불필요** (단일 서버, 동시접속 10명 이하)
- Phase 3: `@socket.io/redis-adapter` 도입 (수평 확장 필요 시)
- BullMQ: Phase 3에서 타이머/큐 관리용으로 검토

---

## 부록 B: 에러 코드

| 코드 | 의미 | 발생 상황 |
|------|------|-----------|
| `PARTY_NOT_FOUND` | 파티 없음 | 잘못된 partyId |
| `PARTY_FULL` | 만석 | 4명 초과 가입 시도 |
| `PARTY_DISBANDED` | 해산됨 | 해산된 파티 접근 |
| `ALREADY_IN_PARTY` | 이미 소속 | 1인 1파티 제한 |
| `NOT_PARTY_MEMBER` | 비멤버 | 비소속 파티 접근 |
| `NOT_PARTY_LEADER` | 비리더 | 리더 전용 기능 (추방, 시작, 해산) |
| `INVALID_INVITE_CODE` | 코드 오류 | 존재하지 않는 초대코드 |
| `DUNGEON_IN_PROGRESS` | 던전 진행 중 | 진행 중 가입 (Phase 2에서 허용) |
| `NOT_ALL_READY` | 준비 미완 | 전원 미준비 상태에서 시작 |
| `TURN_ALREADY_SUBMITTED` | 중복 제출 | 같은 턴에 2번 행동 |
| `VOTE_EXPIRED` | 투표 만료 | 만료된 투표에 참여 |
| `VOTE_ALREADY_CAST` | 중복 투표 | 이미 투표한 안건 |
