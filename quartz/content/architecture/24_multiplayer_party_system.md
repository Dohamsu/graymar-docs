# 24. 멀티플레이어 파티 시스템 — 설계 배경 + Phase 계획

> 구현 API 는 guides/08_party_guide.md 참조. 이 문서는 설계 배경·단계 계획만 유지.
> 마지막 갱신: 2026-04-17

---

## 1. 개요 및 목표

### 1.1 목적

기존 싱글플레이어 RPG에 최대 4인 파티 시스템을 도입한다. 파티원은 같은 장소에서 함께 이동하고, 각자 독립적으로 행동한 뒤 서버가 통합 처리하며, LLM이 4인분 행동을 하나의 서사로 생성한다.

### 1.2 핵심 원칙

1. **기존 불변식 유지** — Server SoT, LLM narrative-only, 멱등성, RNG 결정성
2. **솔로/파티 완전 분리** — 솔로 런은 그대로, 파티 런은 별도 메뉴로 진입
3. **단일 서버 최적화** — Phase 1에서 Redis 불필요 (동시 접속 10명 이하)
4. **점진적 도입** — Phase별로 독립 배포 가능
5. **SSE+REST 구조** — 다운스트림은 SSE, 업스트림은 REST POST (WebSocket 미사용)

### 1.3 Phase 로드맵

| Phase | 범위 | 선행 조건 | 상태 |
|-------|------|-----------|------|
| **Phase 1** | 파티 CRUD + 초대코드 + 파티 목록 + 실시간 채팅 + 로비 UI | 없음 | 구현 완료 |
| **Phase 2** | 파티 전용 런 + 동시 턴 처리 + 이동 투표 + 보상 분배 + 던전 UI | Phase 1 완료 | 구현 완료 |
| **Phase 3** | 런 통합 (파티장 세계 합류) + 스케일링 (Redis adapter) | Phase 2 안정화 | 부분 구현 (통합 완료, 스케일링 미완) |

---

## 2. 아키텍처 배경

### 2.1 기존 싱글플레이어

```
Client (Next.js 16) ──REST──> Server (NestJS 11) ──> PostgreSQL
                                   │
                             LLM Worker (async, DB Polling)
```

완전 싱글플레이어: 1 user = 1 run, 실시간 통신 없음 (REST + LLM 폴링).

### 2.2 멀티플레이어 확장

```
Client ── REST API (기존 + 파티 REST POST)
      └── SSE  (GET /v1/parties/:partyId/stream)
                                   │
                              Server (NestJS)
                                   │
                              + PartyModule (7 services, 1 controller)
                                   │
                              PostgreSQL (+ 6 파티 테이블, run_sessions 확장)
```

**통신 모델**: Client→Server는 전부 REST POST, Server→Client는 SSE 스트림. NestJS 내장 SSE 지원(`@Sse()` 데코레이터, `Observable<MessageEvent>` 반환)을 사용하며 외부 의존성 없음.

---

## 3. 실시간 통신 방식 선택 근거

| 옵션 | 장점 | 단점 | 판정 |
|------|------|------|------|
| **SSE + REST** | 의존성 0, NestJS 내장, 브라우저 내장 EventSource, 자동 재연결, HTTP/2 멀티플렉싱, 프록시 친화적 | 서버→클라이언트 단방향 (업스트림은 REST) | **채택** |
| socket.io | room/namespace, 양방향 | 서버+클라이언트 의존성 ~45KB, CORS 이슈, 프록시 설정 필요 | 제외 |
| ws (raw) | 경량 | room/reconnect 직접 구현, 프로토콜 업그레이드 필요 | 제외 |

**SSE 채택 근거**: 이 프로젝트의 실시간 통신 패턴은 "서버가 클라이언트에 이벤트 푸시 + 클라이언트가 REST로 액션 제출"이다. 기존 싱글플레이어에서도 REST + LLM 폴링으로 동작하므로, SSE는 이 패턴의 자연스러운 확장이다. 채팅 전송도 REST POST로 충분하며 (Slack, Discord 초기 등 동일 패턴), 양방향 WebSocket의 복잡성이 불필요하다.

### 3.1 SSE 제약사항 및 대응

| 제약 | 대응 |
|------|------|
| EventSource는 커스텀 헤더 미지원 | 쿼리 파라미터 `?token=<JWT>` 폴백 (HTTPS 필수) |
| 프록시 유휴 타임아웃 (60초 등) | 30초 간격 heartbeat 이벤트 전송 |
| 브라우저 탭당 동시 SSE 6개 제한 (HTTP/1.1) | 파티당 SSE 1개 + HTTP/2 환경에서 무제한 |
| 놓친 이벤트 복구 | `Last-Event-ID` 헤더 + 서버 이벤트 ID 순번 관리 (선택적) |

---

## 4. 핵심 설계 결정

### 4.1 파티 상태 모델

```
OPEN ─(join)→ FULL
OPEN/FULL ─(start|invite-run)→ IN_DUNGEON
IN_DUNGEON ─(RUN_ENDED)→ OPEN/FULL
* ─(disband|last leave)→ DISBANDED
```

**IN_DUNGEON 중 가입 허용**: 진행 중 파티에 합류 가능. 파티장의 런 소속 시 `run_participants`에 자동 등록. 중간 합류자는 현재 턴 이후부터 행동 가능.

### 4.2 동시 턴 처리 모델

네 멤버가 30초 내에 독립적으로 행동을 제출하고, 서버가 통합 판정한다.

**결정**: 리더 계정으로 기존 `TurnsService.submitTurn`을 1회만 호출하고, 각 멤버의 rawInput을 `/` 로 결합. 네 명의 개별 행동 데이터는 `turns.actionPlan.partyActions`에 병합 저장되어 LLM Worker가 서사에 활용.

**근거**:
- 기존 엔진 (IntentParserV2, Resolve, EventDirector) 재사용
- 런 상태(runState)의 단일 소유권 유지 → 경쟁 조건 방지
- LLM Worker는 `partyActions`를 보고 4인 서사 조합

**타임아웃**: 30초. 미제출자는 자동 행동(LOCATION=OBSERVE, COMBAT=DEFEND) 삽입 후 판정.

### 4.3 이동 투표 (Phase 2)

HUB 노드에서 `go_*` CHOICE는 개별 실행 대신 자동으로 투표 제안을 생성한다. 과반수 yes 도달 시 리더 계정으로 이동 실행. 30초 만료.

**근거**: 4인이 각각 다른 장소를 찍을 경우 충돌 방지. 파티당 PENDING 투표는 1개로 제한.

### 4.4 보상 분배

- **아이템**: 멤버별 1d6 주사위, 최고점 승자 획득. `sha256(seed:cursor)` 기반 결정론.
- **골드**: 균등 분배, 나머지는 리더.
- **솔로 동기화**: 파티 런 종료 시 각 멤버의 최근 SOLO 런 runState에 gold/inventory 합산.

### 4.5 이탈 처리

| 상황 | 처리 |
|------|------|
| SSE 연결 끊김 (잠시) | 30초 유예 |
| 30초 후 재연결 없음 | AI 제어 전환 — 매 턴 자동행동 삽입 |
| 재접속 | AI 제어 전 런에서 자동 해제 |
| 리더 이탈 | 가장 오래된 멤버에게 자동 위임, 혼자면 DISBANDED |
| Phase 3 명시적 이탈 (`leave`) | participantState의 gold/items를 솔로 런에 정산 후 `leftAt` 설정 |

---

## 5. Phase 1 범위 (채팅 + 파티 관리)

### 5.1 목표

- 파티 CRUD + 초대코드 + 파티 검색
- 실시간 채팅(SSE) + 시스템 메시지
- 로비 UI (게임 외부)

### 5.2 주요 작업

| Step | 내용 | 산출물 |
|------|------|--------|
| 1 | DB 스키마 (`parties`, `party_members`, `chat_messages`) + drizzle push | schema 3 파일 |
| 2 | PartyService/ChatService + 7 REST 엔드포인트 | party CRUD 동작 |
| 3 | PartyStreamService + SSE 엔드포인트 + 채팅 브로드캐스트 | 실시간 채팅 |
| 4 | 클라이언트 SSE 래퍼 + Zustand 스토어 | `sse-client.ts`, `party-store.ts` |
| 5 | UI 컴포넌트 (파티 패널, 채팅, 멤버리스트) | `/play/party` 라우트 |
| 6 | 통합 테스트 (멀티 탭, 리더 이탈, 만석, 재연결) | |

**엣지 케이스**:
- 만석 → OPEN으로 자동 복귀 (추방/탈퇴 시)
- 리더 이탈 → 가장 오래된 멤버 자동 위임 or 해산
- 재연결 → EventSource 내장 재연결 + Last-Event-ID 복구

---

## 6. Phase 2 범위 (협동 던전)

### 6.1 목표

- 파티 전용 런 생성 (`runMode: PARTY`, `partyId` FK)
- 4인 동시 턴 처리 + 타임아웃
- 이동 투표
- 보상 분배 + 솔로 런 동기화
- 던전 UI (PartyHud, TurnStatus, VoteModal, LootDistribution)

### 6.2 주요 작업

| Step | 내용 |
|------|------|
| 1 | DB 확장 (`party_turn_actions`, `party_votes`, `run_sessions.partyId/partyRunMode`) |
| 2 | PartyTurnService + TurnsService 연동 + 통합 판정 |
| 3 | VoteService + HUB CHOICE 자동 투표 훅 |
| 4 | LobbyService + `lobby:dungeon_starting` 카운트다운 |
| 5 | 던전 UI (기존 게임 레이아웃 재사용 + 파티 오버레이) |
| 6 | PartyRewardService + 솔로 동기화 |
| 7 | 통합 테스트 (4인 동시 턴, 타임아웃, 투표 3케이스, 중간 이탈/합류) |

### 6.3 LLM 통합 서술

네 명분 행동을 하나의 프롬프트로 결합한다:
- Token Budget 확장 (SOLO 2500 → PARTY 4000)
- `partyActions` 배열을 컨텍스트 블록에 포함
- LLM은 3인칭 관찰자 시점으로 4인 행동 서술

---

## 7. Phase 3 범위 (런 통합 + 스케일링)

### 7.1 "내 세계에 초대" 모델

Phase 2까지는 "파티 전용 런"으로 솔로와 완전 분리된다. Phase 3에서는 파티장의 기존 솔로 런 세계에 다른 멤버들이 합류한다.

```
파티장 (기존 솔로 런 보유)
  → "내 세계에 초대" (POST /lobby/invite-run)
  → 파티원이 파티장의 run_session에 합류
  → 파티장의 WorldState, Heat, Incident, NPC 관계 등 공유
  → 각 파티원은 자신의 스탯/장비로 행동
  → 파티 해산/이탈 시 파티원의 경험/보상만 솔로로 반영
```

### 7.2 필요 변경

| 영역 | 변경 |
|------|------|
| `run_sessions` | `partyId`, `partyRunMode` 컬럼 추가 (완료) |
| `run_participants` | 멀티 유저 참조 테이블 신설 (완료) |
| WorldState | 파티장 기준 단일 유지 (멤버는 읽기 참여) |
| NPC 관계 | 파티장의 NPC posture 기준, 멤버 행동은 개별 영향 |
| 메모리 | 파티장 runMemories에 멤버 행동도 기록 |
| LLM 컨텍스트 | 4인 배경 + 파티장 세계 상태 조합 |

### 7.3 기술 스케일링

| 영역 | Phase 2 | Phase 3 목표 |
|------|---------|-------------|
| 동시접속 | 10명 이하 | 50명+ |
| SSE | 단일 서버 메모리 (`Map<partyId, Map<userId, Subject>>`) | Redis Pub/Sub 기반 크로스-인스턴스 브로드캐스트 |
| 타이머 | setTimeout | BullMQ delayed job |
| 세션 | PostgreSQL | PostgreSQL + Redis 캐시 |
| 배포 | 단일 인스턴스 | 수평 확장 (PM2 cluster or K8s) |

### 7.4 런 통합 시 불변식 추가

1. **파티장 WorldState 단일성** — WorldState는 파티장의 것만 존재. 멤버는 읽기만.
2. **행동 독립 + 결과 합산** — 각 멤버의 Resolve는 독립, 후폭풍/Heat/NPC 영향은 합산.
3. **이탈 무해성** — 멤버 이탈 시 파티장 월드에 부작용 없음 (보상만 정산).
4. **메모리 귀속** — 합류 기간 메모리는 파티장 런에 귀속, 멤버에게는 요약만 복사.

---

## 8. Redis 도입 시점 판단

- **Phase 1~2**: 불필요. 단일 서버 + 동시접속 10명 이하 + 메모리 Map으로 충분.
- **Phase 3 (스케일링)**: Redis Pub/Sub 도입 — 수평 확장 시 크로스-인스턴스 SSE 브로드캐스트.
- **BullMQ**: Phase 3에서 타이머/큐 관리용으로 검토.

---

## 9. 에러 코드

| 코드 | 의미 | 발생 상황 |
|------|------|-----------|
| `PARTY_NOT_FOUND` | 파티 없음 | 잘못된 partyId |
| `PARTY_FULL` | 만석 | 4명 초과 가입 시도 |
| `PARTY_DISBANDED` | 해산됨 | 해산된 파티 접근 |
| `ALREADY_IN_PARTY` | 이미 소속 | 1인 1파티 제한 |
| `NOT_PARTY_MEMBER` | 비멤버 | 비소속 파티 접근 |
| `NOT_PARTY_LEADER` | 비리더 | 리더 전용 기능 (추방/시작/해산) |
| `INVALID_INVITE_CODE` | 코드 오류 | 존재하지 않는 초대코드 |
| `DUNGEON_IN_PROGRESS` | 던전 진행 중 | (Phase 2에서 중간 합류 허용) |
| `NOT_ALL_READY` | 준비 미완 | 전원 미준비 상태에서 시작 |
| `TURN_ALREADY_SUBMITTED` | 중복 제출 | 같은 턴 2번 행동 (멱등 응답으로 처리) |
| `VOTE_EXPIRED` | 투표 만료 | 만료된 투표에 참여 |
| `VOTE_ALREADY_CAST` | 중복 투표 | 이미 투표한 안건 |

---

## 10. 관련 문서

- **구현 API**: [[guides/08_party_guide|party guide]] — 서비스/메서드/API/SSE 이벤트/DB 스키마
- **서버 전체 맵**: [[guides/01_server_module_map|server module map]]
- **클라이언트 맵**: [[guides/02_client_component_map|client component map]]
- **LLM 파이프라인**: [[guides/04_llm_memory_guide|llm memory guide]]
