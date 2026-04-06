# 24. 멀티플레이어 파티 채팅 + 협동 플레이 시스템

> Phase 1: 파티 채팅 시스템 (우선 구현)
> Phase 2: 협동 던전 (Phase 1 이후, 아키텍처만 고려)

## 1. 아키텍처 개요

### 1.1 현재 (싱글플레이어)

```
Client (Next.js 16)  --->  REST API  --->  Server (NestJS 11)  --->  PostgreSQL
                                                  |
                                            LLM Worker (async)
```

- 완전 싱글플레이어: 1 user = 1 run
- 실시간 통신 없음: REST + LLM 폴링

### 1.2 변경 (멀티플레이어)

```
Client (Next.js 16)
  ├── REST API (기존 유지)
  └── WebSocket (/party) ────>  Server (NestJS 11)
       ↑                            ├── REST Controllers (기존)
       │                            ├── PartyGateway (WebSocket)
       └── 실시간 이벤트             ├── PartyModule
                                    └── PostgreSQL (기존 + 파티/채팅 테이블)
```

핵심 변경:
- NestJS WebSocket Gateway 추가 (`@nestjs/websockets` + `socket.io`)
- 새 모듈: `party/` (PartyGateway, PartyService, ChatService)
- 새 DB 테이블: `parties`, `party_members`, `chat_messages`
- 클라이언트: `party-store.ts` + WebSocket + 채팅 UI
- Redis: Phase 1 불필요 (단일 서버). Phase 2 스케일링 시 도입

---

## 2. 기술 스택

### WebSocket: `@nestjs/websockets` + `socket.io`

| 옵션 | 장점 | 단점 | 판정 |
|------|------|------|------|
| socket.io | NestJS 공식, room/namespace, 자동 재연결 | 번들 ~45KB | **채택** |
| ws (raw) | 경량 ~3KB | room/reconnect 직접 구현 필요 | 제외 |
| SSE | 단방향 충분할 수 있음 | 양방향 채팅 부적합 | 제외 |

### 추가 의존성

서버: `@nestjs/websockets`, `@nestjs/platform-socket.io`, `socket.io`
클라이언트: `socket.io-client`

---

## 3. DB 스키마

### 3.1 parties

```sql
CREATE TABLE parties (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  leader_id UUID NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN | FULL | IN_DUNGEON | DISBANDED
  max_members INTEGER NOT NULL DEFAULT 4,
  invite_code TEXT NOT NULL UNIQUE,      -- 6자리 영숫자
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 party_members

```sql
CREATE TABLE party_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  party_id UUID NOT NULL REFERENCES parties(id),
  user_id UUID NOT NULL REFERENCES users(id),
  role TEXT NOT NULL DEFAULT 'MEMBER',   -- LEADER | MEMBER
  joined_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(party_id, user_id)
);
```

### 3.3 chat_messages

```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  party_id UUID NOT NULL REFERENCES parties(id),
  sender_id UUID REFERENCES users(id),  -- null = SYSTEM
  type TEXT NOT NULL DEFAULT 'TEXT',     -- TEXT | SYSTEM | GAME_EVENT
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX chat_messages_party_created_idx ON chat_messages(party_id, created_at);
```

---

## 4. API 설계

### 4.1 REST API

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/parties` | 파티 생성 `{ name }` |
| GET | `/v1/parties/my` | 내 파티 조회 |
| POST | `/v1/parties/join` | 초대코드로 가입 `{ inviteCode }` |
| POST | `/v1/parties/:partyId/leave` | 파티 탈퇴 |
| POST | `/v1/parties/:partyId/kick` | 멤버 추방 (리더) `{ userId }` |
| DELETE | `/v1/parties/:partyId` | 파티 해산 (리더) |
| GET | `/v1/parties/:partyId/messages` | 채팅 히스토리 `?cursor=&limit=50` |

### 4.2 WebSocket (namespace: `/party`)

인증: handshake `auth.token` → JWT 검증 → `socket.data.userId`

#### Client → Server

| Event | Payload | Description |
|-------|---------|-------------|
| `party:join_room` | `{ partyId }` | 소켓을 파티 room에 참가 |
| `party:leave_room` | `{ partyId }` | 소켓을 room에서 퇴장 |
| `chat:send` | `{ partyId, content }` | 채팅 메시지 전송 |
| `party:request_status` | `{ partyId }` | 파티원 상태 요청 |

#### Server → Client

| Event | Payload | Description |
|-------|---------|-------------|
| `chat:new_message` | `ChatMessageDTO` | 새 메시지 |
| `party:member_joined` | `{ userId, nickname }` | 멤버 가입 |
| `party:member_left` | `{ userId, nickname }` | 멤버 탈퇴 |
| `party:member_status` | `{ members[] }` | 파티원 상태 (온/오프라인, 위치) |
| `party:disbanded` | `{ partyId }` | 파티 해산 |
| `party:error` | `{ code, message }` | 에러 |

---

## 5. 서버 모듈 구조

```
server/src/party/
  ├── party.module.ts
  ├── party.controller.ts      # REST 엔드포인트
  ├── party.service.ts         # 파티 CRUD
  ├── chat.service.ts          # 채팅 메시지 저장/조회
  ├── party.gateway.ts         # WebSocket Gateway
  └── dto/
      ├── create-party.dto.ts
      └── join-party.dto.ts
```

---

## 6. 클라이언트 구조

### 6.1 파일 구조

```
client/src/
  ├── lib/socket-client.ts          # socket.io 싱글턴
  ├── store/party-store.ts          # Zustand 파티 스토어
  └── components/party/
      ├── PartyPanel.tsx            # 메인 패널
      ├── PartyCreateModal.tsx
      ├── PartyJoinModal.tsx
      ├── PartyMemberList.tsx       # 온/오프라인 표시
      ├── ChatWindow.tsx            # 메시지 영역
      ├── ChatInput.tsx
      └── ChatMessage.tsx
```

### 6.2 배치

SidePanel에 "파티" 탭 추가 (기존: 캐릭터, 인벤토리, 퀘스트)

### 6.3 파티 스토어 주요 상태

```typescript
interface PartyState {
  party: PartyInfo | null;
  members: MemberStatus[];
  messages: ChatMessage[];     // 최근 200개
  isConnected: boolean;
  unreadCount: number;
  // 액션: createParty, joinParty, leaveParty, sendMessage, ...
}
```

---

## 7. Phase 1 구현 계획

| Step | 내용 | 예상 |
|------|------|------|
| 1 | 서버 인프라 (의존성, 스키마, WsAuthGuard) | 2일 |
| 2 | 파티 모듈 REST API | 2일 |
| 3 | WebSocket Gateway | 2일 |
| 4 | 클라이언트 연결 계층 (socket, store) | 1일 |
| 5 | 클라이언트 UI 컴포넌트 | 3일 |
| 6 | 통합 테스트 + 엣지 케이스 | 1일 |
| **합계** | | **~11일** |

---

## 8. Phase 2 확장 고려사항 (협동 던전)

### 8.1 DB 확장

```sql
-- 파티 턴 액션 (개별 행동)
CREATE TABLE party_turn_actions (
  id UUID PRIMARY KEY,
  run_id UUID, turn_no INTEGER, user_id UUID,
  action JSONB,
  submitted_at TIMESTAMP
);

-- 파티 턴 상태 (제출 현황)
CREATE TABLE party_turn_states (
  id UUID PRIMARY KEY,
  run_id UUID, turn_no INTEGER,
  required_users TEXT[],
  submitted_users TEXT[],
  deadline TIMESTAMP,
  resolved BOOLEAN DEFAULT FALSE
);
```

### 8.2 run_sessions 확장

```sql
ALTER TABLE run_sessions ADD COLUMN party_id UUID REFERENCES parties(id);
ALTER TABLE run_sessions ADD COLUMN run_mode TEXT DEFAULT 'SOLO';  -- SOLO | PARTY
```

### 8.3 협동 턴 처리 모델

```
파티 던전 진입 → 공유 run_session (runMode: PARTY)
  → 각 파티원 행동 선택 → party_turn_actions에 저장
  → 전원 제출 (or 30초 타임아웃) → 통합 처리
  → 결과 WebSocket 브로드캐스트
```

### 8.4 추가 WebSocket 이벤트

| Event | Direction | Description |
|-------|-----------|-------------|
| `dungeon:enter` | C→S | 파티 던전 진입 (리더) |
| `dungeon:action_submit` | C→S | 개별 행동 제출 |
| `dungeon:waiting` | S→C | "X명 대기 중" |
| `dungeon:turn_resolved` | S→C | 통합 결과 |
| `dungeon:timeout_warning` | S→C | 제출 시한 임박 |

### 8.5 고려사항

- **타임아웃**: 미제출 시 30초 후 자동 "방어" 행동
- **이탈 처리**: 연결 끊김 시 AI 대행 또는 NPC 전환
- **밸런스**: 적 HP/데미지를 인원 수에 비례 스케일링
- **LLM**: 4인분 합산 서술 → 토큰 예산 증가 필요
- **Redis**: 수평 스케일링 시 `@socket.io/redis-adapter` 도입

---

## 핵심 설계 원칙

1. **기존 불변**: Server SoT, LLM narrative-only, 멱등성 유지
2. **점진적 도입**: Phase 1은 기존 게임 로직에 영향 없음 (독립 모듈)
3. **WebSocket은 채팅+상태 전용**: 턴 처리는 REST 유지
4. **단일 서버 최적화**: Redis 없이 시작, 어댑터 교체로 스케일링
