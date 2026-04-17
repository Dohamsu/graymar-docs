# 파티 시스템 구현 가이드

> 정본 위치: `server/src/party/`
> 설계 배경·Phase 계획: `architecture/24_multiplayer_party_system.md`
> 최종 갱신: 2026-04-17

최대 4인 파티 시스템 구현 가이드. 파티 CRUD, 실시간 채팅(SSE), 협동 던전(동시 턴/이동 투표/보상 분배), 런 통합(파티장 솔로 런 합류)을 포괄한다.

---

## 1. 모듈 구조

```
server/src/party/
├── party.module.ts                ← PartyModule (forwardRef: RunsModule, TurnsModule)
├── party.controller.ts            ← REST + SSE 엔드포인트 (26 endpoints)
├── party.service.ts               ← 파티 CRUD + 리더 위임
├── chat.service.ts                ← 채팅 메시지 저장/조회
├── party-stream.service.ts        ← SSE 연결 관리 + 브로드캐스트
├── lobby.service.ts               ← 로비 준비 상태 + 던전 시작
├── vote.service.ts                ← 이동 투표 생성/집계/만료
├── party-turn.service.ts          ← 동시 턴 수집 + 통합 판정 + 타임아웃
├── party-reward.service.ts        ← 주사위 아이템 분배 + 골드 균등 분배
├── run-participants.service.ts    ← 런 통합 (파티장 세계 합류)
└── dto/
    ├── create-party.dto.ts
    ├── send-message.dto.ts
    ├── lobby.dto.ts
    ├── submit-action.dto.ts
    └── cast-vote.dto.ts
```

의존성: 없음 (NestJS 내장 `@Sse()` + 브라우저 `EventSource` 사용).

---

## 2. 서비스별 핵심 메서드

### 2.1 PartyService (파티 CRUD)

`server/src/party/party.service.ts`

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `createParty` | `(userId, name) → PartyResponse` | 파티 생성 + 초대코드 발급 + 리더 자동 가입 |
| `getMyParty` | `(userId) → PartyResponse \| null` | 활성 파티 조회 (1인 1파티) |
| `searchParties` | `(query, cursor?, limit=20) → { items, nextCursor }` | 파티 검색 (OPEN/FULL/IN_DUNGEON) |
| `joinParty` | `(userId, inviteCode) → PartyResponse + isDungeonActive` | 초대코드 가입. IN_DUNGEON 시 중간 합류 |
| `leaveParty` | `(userId, partyId) → { success }` | 탈퇴. 리더 탈퇴 시 `joinedAt` 오래된 멤버에게 자동 위임, 1인 잔류 시 해산 |
| `kickMember` | `(leaderId, partyId, targetUserId)` | 리더 전용. 추방 대상에 `party:kicked` 전송 후 연결 해제 |
| `disbandParty` | `(leaderId, partyId)` | 리더 전용. 파티 DISBANDED + 전원 연결 해제 |
| `getPartyMembers` | `(partyId)` | 멤버 목록 (role, isOnline, nickname) |
| `assertMembership` | `(userId, partyId)` | 외부(controller/chat)에서 멤버십 검증 |

**초대코드 생성**: 6자리 영숫자 대문자, 혼동 문자(`0/O/1/I/L`) 제외. `crypto.randomBytes` 기반.

**1인 1파티 제한**: `ensureNotInParty()` — 이미 소속 시 `BadRequestError`. DISBANDED 잔여 멤버십은 정리.

### 2.2 ChatService (채팅)

`server/src/party/chat.service.ts`

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `saveMessage` | `(partyId, senderId, content, type='TEXT') → ChatMessageRow` | 메시지 저장 + 닉네임 조회 |
| `saveSystemMessage` | `(partyId, content) → ChatMessageRow` | `senderId=null, type=SYSTEM` |
| `getMessages` | `(partyId, cursor?, limit=50) → { messages, nextCursor }` | 커서 기반 역순 조회 (최대 100) |

**MessageType**: `TEXT` / `SYSTEM` / `GAME_EVENT`.

### 2.3 PartyStreamService (SSE)

`server/src/party/party-stream.service.ts`

구조: `Map<partyId, Map<userId, Subject<MessageEvent>>>`.

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `register` | `(partyId, userId) → Subject<MessageEvent>` | 기존 연결 있으면 complete 후 교체 |
| `unregister` | `(partyId, userId)` | 연결 해제. 파티 Map 비면 삭제 |
| `broadcast` | `(partyId, eventType, data)` | 파티 전체 브로드캐스트. closed subject 자동 정리 |
| `sendToUser` | `(partyId, userId, eventType, data)` | 특정 유저에만 전송 |
| `disconnectAll` | `(partyId)` | 파티 해산 시 전원 complete |
| `broadcastError` | `(partyId, code, message)` | `party:error` 이벤트 브로드캐스트 |
| `isUserConnected` | `(partyId, userId) → boolean` | 재접속 유예 판정용 |
| `getConnectionCount` | `(partyId) → number` | 진단용 |

### 2.4 LobbyService (로비)

`server/src/party/lobby.service.ts`

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `toggleReady` | `(userId, partyId, ready) → LobbyStateDTO` | 준비 토글 + `lobby:state_updated` 브로드캐스트 |
| `getLobbyState` | `(partyId) → LobbyStateDTO` | 멤버 목록 + 최근 런 프리셋/성별 + `allReady`/`canStart` |
| `initiateDungeonStart` | `(leaderId, partyId) → { runId, memberUserIds, memberProfiles }` | 리더 검증 → `canStart` 확인 → 파티 IN_DUNGEON 전환 → ready 초기화 |
| `endDungeon` | `(partyId)` | 멤버 수에 따라 FULL/OPEN 복귀 |

**canStart 조건**: 멤버 2명 이상 + 전원 ready. `LobbyMemberState`는 `userId`, `nickname`, `presetId`, `gender`, `isReady`, `isOnline`.

### 2.5 VoteService (이동 투표)

`server/src/party/vote.service.ts`

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `createVote` | `(partyId, runId, proposerId, targetLocationId) → VoteDTO` | 30초 타이머 + 제안자 자동 찬성 + `vote:proposed` |
| `castVote` | `(voteId, userId, partyId, choice)` | 집계 → 과반수 도달 시 resolveVote, 아니면 `vote:updated` |
| `resolveVote` *(private)* | `(voteId, partyId, status, extra?)` | 상태 확정 → APPROVED 시 `executeMove` 실행 + `vote:resolved` |
| `expireVote` *(private)* | `(voteId, partyId)` | 30초 경과 자동 EXPIRED |
| `executeMove` *(private)* | `(partyId, targetLocationId)` | HUB 턴 자동 제출 (리더 계정, `vote-move-{partyId}-{ts}` idempotency) |

**만료 타이머**: `expiryTimers = Map<voteId, setTimeout>`. 정상 resolve 시 clearTimeout.
**동시 투표 차단**: 파티당 PENDING 투표 1개만.
**과반수**: `Math.floor(totalMembers / 2) + 1`.

### 2.6 PartyTurnService (동시 턴)

`server/src/party/party-turn.service.ts`

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `startTurn` | `(runId, turnNo, partyId, memberUserIds)` | 30초 타임아웃 + 10/5초 경고 타이머 + `dungeon:waiting` |
| `submitAction` | `(runId, turnNo, userId, partyId, inputType, rawInput, idempotencyKey) → { accepted, allSubmitted, actions? }` | AI 자동제출 → 멱등성 체크 → 저장 → `dungeon:action_received` → 전원 제출 시 resolveTurn |
| `handleTimeout` | `(runId, turnNo, partyId)` | 미제출자에 자동 행동 삽입 + resolveTurn |
| `resolveTurn` | `(runId, turnNo, partyId)` | 4인분 행동 결합 → 리더 계정으로 `TurnsService.submitTurn` → partyActions를 turns.actionPlan에 저장 → SSE 브로드캐스트 → 보상 분배 → 런 종료 정산 |
| `getSubmittedActions` | `(runId, turnNo)` | 제출된 행동 조회 |
| `getAutoAction` | `(runState) → string` | COMBAT → "방어 자세를 취한다", LOCATION → "주변을 관찰한다" |
| `setAiControlled` | `(runId, userId)` | 이탈 멤버 AI 제어 (30초 유예 후 호출) |
| `removeAiControlled` | `(runId, userId)` | 런별 해제 |
| `removeAiControlledByUser` | `(userId)` | 재접속 시 전 런에서 해제 |
| `isAiControlled` | `(runId, userId) → boolean` | 상태 조회 |

**내부 상태**:
- `timers: Map<runId, TurnTimer>` — 턴별 타임아웃/경고 핸들
- `aiControlled: Map<runId, Set<userId>>` — 이탈 AI 제어 목록

**통합 판정 원리**: 각 멤버 행동을 `/` 로 결합하여 리더 계정으로 `TurnsService.submitTurn` 1회 호출. `partyActions` 배열(userId/nickname/presetId/rawInput/isAutoAction)은 `turns.actionPlan`에 병합 저장 → LLM Worker가 4인 서사 생성에 참조.

**전투 승리 시 보상 분배**: `serverResult.events`에서 `SYSTEM:승리`, `LOOT`, `GOLD` 탐색 → `PartyRewardService.distributeLoot/distributeGold` 호출.

**RUN_ENDED 시**: 멤버별 골드 균등 분배 + 인벤토리 리더에게 + `PartyRewardService.syncToSoloRuns` + `LobbyService.endDungeon`.

### 2.7 PartyRewardService (보상 분배)

`server/src/party/party-reward.service.ts`

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `distributeLoot` | `(partyId, memberUserIds, lootItems, seed, cursor) → LootResult[]` | 아이템별 1d6 최고점 승자. `dungeon:loot_distributed` + 시스템 메시지 |
| `distributeGold` | `(partyId, memberUserIds, totalGold) → GoldResult[]` | 균등 분배, 나머지는 리더. `dungeon:gold_distributed` |
| `syncToSoloRuns` | `(partyId, partyRunId, memberGold, memberItems)` | 각 멤버의 최근 SOLO 런 runState에 gold/inventory 합산 |

**주사위**: `seededRoll1d6(seed, cursor)` — `sha256(seed:cursor)` 기반 결정론. 동점 시 첫 번째 승자 선택(단순화).

### 2.8 RunParticipantsService (런 통합 - Phase 3)

`server/src/party/run-participants.service.ts`

| 메서드 | 시그니처 | 역할 |
|--------|---------|------|
| `inviteToExistingRun` | `(leaderId, partyId) → { runId, memberUserIds }` | 파티장 활성 SOLO 런을 PARTY로 전환 + 전원 run_participants INSERT + runState.partyMembers/partyMemberHp 갱신 |
| `addMidJoinMember` | `(runId, userId, partyId)` | 던전 중 새 멤버 run_participants INSERT + runState 갱신 |
| `getParticipants` | `(runId) → Participant[]` | `leftAt IS NULL` 필터링 |
| `leaveDungeon` | `(runId, userId, partyId)` | participantState.gold/items를 솔로 런에 동기화 → `leftAt` 설정 → runState에서 제거 → `party:member_left_dungeon` |

**참가자 초기 상태**: `hp`/`maxHp`는 런 runState 값, `inventory=[]`, `gold=0`, `equipped={}`.

---

## 3. API 엔드포인트

모든 엔드포인트는 `AuthGuard`(JWT) 적용. 정본 경로: `server/src/party/party.controller.ts`. CLAUDE.md "API Endpoints" 섹션의 파티 표와 일치.

### 3.1 파티 관리

| Method | Path | Body | 반환 |
|--------|------|------|------|
| POST | `/v1/parties` | `{ name }` | PartyResponse (201) |
| GET | `/v1/parties/my` | — | PartyResponse 또는 `{ id: null }` |
| GET | `/v1/parties/search` | `?q=&cursor=&limit=20` | `{ items, nextCursor }` |
| POST | `/v1/parties/join` | `{ inviteCode }` | PartyResponse + `isDungeonActive` |
| POST | `/v1/parties/:partyId/leave` | — | `{ success }` |
| POST | `/v1/parties/:partyId/kick` | `{ userId }` | `{ success }` |
| DELETE | `/v1/parties/:partyId` | — | `{ success }` |

### 3.2 채팅 + SSE

| Method | Path | 설명 |
|--------|------|------|
| POST | `/v1/parties/:partyId/messages` | `{ content }` — DB 저장 + `chat:new_message` 브로드캐스트 |
| GET | `/v1/parties/:partyId/messages` | `?cursor=&limit=50` 커서 기반 히스토리 |
| GET | `/v1/parties/:partyId/stream` | SSE 스트림. `?token=JWT` 쿼리 인증. 30초 heartbeat. 재접속 시 AI 제어 자동 해제 |

### 3.3 로비 / 던전

| Method | Path | 설명 |
|--------|------|------|
| GET | `/v1/parties/:partyId/lobby` | LobbyStateDTO |
| POST | `/v1/parties/:partyId/lobby/ready` | `{ ready }` — 준비 토글 |
| POST | `/v1/parties/:partyId/lobby/start` | 리더 전용. 런 생성 + runState.partyMembers/partyMemberHp 초기화 + `lobby:dungeon_starting` |
| POST | `/v1/parties/:partyId/lobby/invite-run` | Phase 3: 리더 솔로 런에 합류. `isRunIntegration: true` |
| POST | `/v1/parties/:partyId/runs/:runId/turns` | `{ inputType, rawInput, idempotencyKey }`. HUB CHOICE(`go_*`)는 자동 투표 생성 |
| GET | `/v1/parties/:partyId/runs/:runId/turns/:turnNo` | partyActions + serverResult + llm 병합 |
| POST | `/v1/parties/:partyId/runs/:runId/leave` | 던전 이탈 (보상 정산 + AI 전환) |

### 3.4 이동 투표

| Method | Path | 설명 |
|--------|------|------|
| POST | `/v1/parties/:partyId/votes` | `{ targetLocationId }` — 30초 투표 제안 |
| POST | `/v1/parties/:partyId/votes/:voteId/cast` | `{ choice: 'yes'\|'no' }` — 과반수 도달 시 이동 실행 |

**HUB 이동 자동 투표**: 파티 던전에서 HUB CHOICE `go_market` 등 제출 시 `submitPartyAction`이 VoteService.createVote 자동 호출 → `{ accepted: true, voteCreated: true, vote }` 반환.

**locationId ↔ choiceId 매핑** (VoteService/Controller 공용):
```
LOC_MARKET ↔ go_market, LOC_HARBOR ↔ go_harbor, LOC_GUARD ↔ go_guard,
LOC_SLUMS ↔ go_slums, LOC_NOBLE ↔ go_noble, LOC_TEMPLE ↔ go_temple, LOC_TAVERN ↔ go_tavern
```

---

## 4. DB 테이블 구조

정본: `server/src/db/schema/`. Drizzle ORM.

### 4.1 parties

```
id uuid PK, name text, leader_id uuid→users, status text enum,
max_members int default 4, invite_code text unique,
created_at timestamp, updated_at timestamp
```

**PartyStatus**: `OPEN` / `FULL` / `IN_DUNGEON` / `DISBANDED`.
인덱스: `leader_idx`, `status_idx`, `invite_code_idx`.

### 4.2 party_members

```
id uuid PK, party_id uuid→parties, user_id uuid→users,
role text enum('LEADER','MEMBER') default 'MEMBER',
is_online text default 'false',        -- 'true'|'false' (text 플래그)
is_ready text default 'false',          -- Phase 2 로비 준비 상태
joined_at timestamp
```

Unique: `(party_id, user_id)`.

### 4.3 chat_messages

```
id uuid PK, party_id uuid→parties, sender_id uuid?→users,  -- null = SYSTEM
type text enum('TEXT','SYSTEM','GAME_EVENT') default 'TEXT',
content text, created_at timestamp
```

인덱스: `(party_id, created_at)`.

### 4.4 party_turn_actions

```
id uuid PK, run_id uuid→run_sessions, turn_no int, user_id uuid→users,
input_type text, raw_input text, is_auto_action bool default false,
action_data jsonb, submitted_at timestamp
```

Unique: `(run_id, turn_no, user_id)` (멱등성).
인덱스: `(run_id, turn_no)`.

### 4.5 party_votes

```
id uuid PK, party_id uuid→parties, run_id uuid?,
proposer_id uuid→users, vote_type text default 'MOVE_LOCATION',
target_location_id text?, status text enum('PENDING','APPROVED','REJECTED','EXPIRED'),
yes_votes int default 1, no_votes int default 0, total_members int,
voted_user_ids text[], expires_at timestamp, resolved_at timestamp?,
created_at timestamp
```

인덱스: `(party_id, status)`.

### 4.6 run_participants (Phase 3)

```
id uuid PK, run_id uuid→run_sessions, user_id uuid→users,
role text enum('OWNER','GUEST') default 'GUEST',
preset_id text?, gender text enum('male','female') default 'male',
nickname text?,
participant_state jsonb {hp, maxHp, inventory, gold, equipped},
joined_at timestamp, left_at timestamp?    -- null = 참여 중
```

Unique: `(run_id, user_id)`. 인덱스: `run_idx`, `user_idx`.

### 4.7 run_sessions 확장 컬럼

```
party_id uuid? → parties                    -- null = 솔로 런
party_run_mode text enum('SOLO','PARTY') default 'SOLO'
```

---

## 5. 파티 런 상태 머신

```
OPEN ─(join +1)→ FULL ─(leave/kick)→ OPEN
OPEN/FULL ─(lobby/start | lobby/invite-run)→ IN_DUNGEON
IN_DUNGEON ─(join: 중간 합류, addMidJoinMember)→ IN_DUNGEON
IN_DUNGEON ─(RUN_ENDED: endDungeon)→ OPEN/FULL
* ─(leader disband | 1인 잔류 리더 탈퇴)→ DISBANDED
```

**턴 수명 주기** (`PartyTurnService`): `startTurn` (30s 타이머, 10s/5s 경고) → `submitAction × N` → [전원 제출 또는 `handleTimeout` 자동행동 삽입] → `resolveTurn` (리더 계정으로 `TurnsService.submitTurn`, `turns.actionPlan`에 partyActions 병합) → `dungeon:turn_resolved` → 보상 분배 → RUN_ENDED 시 솔로 동기화.

---

## 6. SSE 이벤트

`PartyStreamService.broadcast(partyId, eventType, data)` 로 전파. 클라이언트는 `EventSource.addEventListener(eventType, handler)` 바인딩.

### 6.1 파티 이벤트

| 이벤트 | 페이로드 | 발생 시점 |
|--------|----------|-----------|
| `chat:new_message` | `{ id, senderId, senderNickname, type, content, createdAt }` | 채팅 저장 후 |
| `party:member_joined` | `{ userId, nickname, midJoin? }` | 가입 시 (IN_DUNGEON 중이면 `midJoin: true`) |
| `party:member_left` | `{ userId, nickname, kicked? }` | 탈퇴/추방 |
| `party:member_status` | `{ userId, isOnline }` | SSE 연결/해제 |
| `party:member_ai_controlled` | `{ userId }` | 연결 해제 30초 후 AI 전환 |
| `party:member_left_dungeon` | `{ userId, nickname }` | Phase 3 던전 이탈 |
| `party:member_hp_update` | `{ members: [{userId, nickname, hp, maxHp}] }` | 턴 해결 후 |
| `party:leader_changed` | `{ newLeaderId, nickname }` | 리더 자동 위임 |
| `party:disbanded` | `{ disbandedBy }` | 파티 해산 |
| `party:kicked` | `{ reason }` | 추방 대상 개인에게만 |
| `party:error` | `{ code, message }` | 에러 브로드캐스트 |
| `heartbeat` | `{ ts }` | 30초 간격 프록시 타임아웃 방지 |

### 6.2 로비 이벤트

| 이벤트 | 페이로드 | 발생 시점 |
|--------|----------|-----------|
| `lobby:state_updated` | `LobbyStateDTO` | `toggleReady` 후 |
| `lobby:dungeon_starting` | `{ partyId, runId, memberUserIds, memberProfiles, countdown: 3, isRunIntegration? }` | 던전 시작 직전 |

### 6.3 던전 이벤트

| 이벤트 | 페이로드 | 발생 시점 |
|--------|----------|-----------|
| `dungeon:waiting` | `{ turnNo, submitted, pending, deadline }` | 턴 시작/행동 제출 시 |
| `dungeon:action_received` | `{ userId, nickname, turnNo }` | 각 멤버 제출 |
| `dungeon:timeout_warning` | `{ secondsLeft, turnNo }` | 10초/5초 남음 |
| `dungeon:turn_resolved` | `{ runId, turnNo, actions, serverResult, llmStatus }` | resolveTurn 완료 |
| `dungeon:location_changed` | `{ targetLocationId, targetLocationName }` | 투표 통과 후 이동 |
| `dungeon:loot_distributed` | `{ results: [{itemId, itemName, winnerId, winnerNickname, rolls}] }` | 아이템 분배 |
| `dungeon:gold_distributed` | `{ totalGold, results }` | 골드 분배 |

### 6.4 투표 이벤트

| 이벤트 | 페이로드 | 발생 시점 |
|--------|----------|-----------|
| `vote:proposed` | VoteDTO (expiresAt 포함) | 투표 생성 |
| `vote:updated` | `{ id, yesVotes, noVotes, totalMembers, status }` | 미결 상태 진행 |
| `vote:resolved` | `{ voteId, status, targetLocationId }` | APPROVED/REJECTED/EXPIRED |

---

## 7. 핵심 불변식

1. **SSE 인증**: EventSource 커스텀 헤더 미지원 → 쿼리 파라미터 `?token=<JWT>` 사용 (HTTPS 필수).
2. **1인 1파티**: `ensureNotInParty`로 중복 가입 차단. DISBANDED 잔여 멤버십은 자동 정리.
3. **턴 멱등성**: `(runId, turnNo, userId)` unique + `idempotencyKey` 전달. 중복 제출 시 `{ accepted: true, allSubmitted: false }` 즉시 반환.
4. **AI 제어 유예**: SSE 연결 해제 후 30초 유예 → 재연결 없으면 `setAiControlled`. 재연결 시 `removeAiControlledByUser` 자동 해제.
5. **리더 자동 위임**: 리더 탈퇴 시 `joinedAt` 오래된 순서로 MEMBER → LEADER 승격. 혼자면 DISBANDED.
6. **보상 결정론**: `distributeLoot`의 1d6 주사위는 `sha256(seed:cursor)` 기반 — 재현 가능.
7. **Phase 2 투표 단일**: 파티당 PENDING 투표 1개 제한.
8. **LLM 4인 서사**: `partyActions`는 `turns.actionPlan`에 병합 저장되며 LLM Worker가 4인 행동을 하나의 서사로 조합.
9. **중간 합류**: `party.status === 'IN_DUNGEON'` 가입은 `runParticipantsService.addMidJoinMember` 자동 호출.
10. **이탈 보상 정산**: `leaveDungeon` 시 `participantState.gold/inventory`를 멤버의 최근 SOLO 런에 합산한 후 `leftAt` 설정.

---

## 8. 관련 파일 레퍼런스

- 컨트롤러: `server/src/party/party.controller.ts`
- DB 스키마: `server/src/db/schema/parties.ts`, `party-members.ts`, `chat-messages.ts`, `party-turn-actions.ts`, `party-votes.ts`, `run-participants.ts`
- Run 확장: `server/src/db/schema/run-sessions.ts` (`partyId`, `partyRunMode`)
- 통합 대상: `server/src/turns/turns.service.ts` (`submitTurn`), `server/src/runs/runs.service.ts` (`createRun`, `getActiveRun`)
- 에러: `server/src/common/errors/game-errors.ts` — `BadRequestError`, `NotFoundError`, `ForbiddenError`
- 클라이언트 스토어: `client/src/store/party-store.ts`
- 클라이언트 SSE: `client/src/lib/sse-client.ts`
- 설계 문서: `architecture/24_multiplayer_party_system.md`
