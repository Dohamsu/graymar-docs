# Core Game Architecture v1

> 범위: LLM 기반 턴제 게임의 핵심 아키텍처, 서버/클라이언트 역할 분리, API 계약,
> 캐싱 전략, UI 상태 머신, Downed State & Recovery 메커니즘, 에러 처리, 확장 가능성

---

## 1. 핵심 아키텍처 원칙

### 1.1 게임 방식

- 턴제(turn-based) 기반
- 매 턴 LLM 호출
- 서버가 모든 수치/결과를 확정한 뒤 LLM이 서술을 생성

### 1.2 설계 철학

- **서버는 숫자, LLM은 분위기** — 게임 로직과 내러티브를 완전히 분리
- 서버 결과가 먼저 확정되므로, LLM 지연이나 실패가 게임 진행에 영향을 주지 않음
- 클라이언트는 서버 결과를 즉시 반영하고, LLM 서술은 비동기로 덧씌움

---

## 2. 서버 / LLM / 클라이언트 역할 분리

| 영역 | 담당 |
|------|------|
| **서버** | 수치 계산, 확률 판정, 드랍, 상태 변화, DB 트랜잭션 |
| **LLM** | 서술(내러티브)만 생성 — 수치 변경 권한 없음 |
| **클라이언트** | HUD 렌더링, UI 상태 머신 관리, 사용자 입력 전송 |

핵심 규칙:

- LLM 출력은 게임 결과에 **절대 영향 없음** (순수 연출용)
- 클라이언트는 `serverResult`를 기준으로 게임 상태를 반영하며, LLM 서술은 같은 turnNo의 narration만 덧씌움 (수치 변경 금지)

---

## 3. 턴 처리 데이터 흐름

### 3.1 전체 흐름

1. 사용자 입력 수신 (`POST /turns`)
2. 서버 게임 엔진 계산 (DB 트랜잭션)
   - 입력 검증
   - 전투/드랍/이벤트 계산
   - `turns` insert (`llm_status=PENDING`)
   - `player_states` 업데이트
3. 트랜잭션 커밋 (게임 결과 확정)
4. LLM 호출
   - 컨텍스트 조립
   - 서술 생성
5. `turns.llm_output` 저장 (`DONE`)
6. 클라이언트 응답 반환

### 3.2 LLM 응답 상태에 따른 분기

- **DONE**: `serverResult` + `llm.output` 즉시 전달
- **PENDING**: `serverResult`만 즉시 전달 → 클라이언트가 폴링 또는 SSE/WS로 LLM 결과 수신

---

## 4. API 계약

> 상세: `server_api_system.md` Part 1 (Request/Response 예시, 멱등성, 폴링)

---

## 5. 캐싱 & LLM 컨텍스트

> 캐싱 4 Layer 상세: `server_api_system.md` Part 2
> LLM 컨텍스트 3 Layer 정본: `llm_context_system_v1.md`

---

## 7. UI 상태 머신 (Client State Machine)

> 서버 결과 확정 → LLM 서술 비동기 흐름을 UI가 안정적으로 표현하기 위한 상태 전이 정의

### 7.1 상태 목록

> **v1 구현 현황**: 설계 문서의 7 States는 실제 구현에서 **6 States로 단순화**되었다. 아래는 실제 구현된 상태 목록이다.

**실제 구현 (6 States)**:

| 상태 | 설명 |
|------|------|
| `TITLE` | 타이틀 화면, 게임 시작 전 |
| `LOADING` | 새 게임 생성 중 |
| `PLAYING` | 게임 진행 중 (입력 대기 + 턴 처리 + LLM 폴링 포함) |
| `NODE_TRANSITION` | 노드 종료 후 다음 노드로 전환 중 |
| `RUN_ENDED` | 런 종료 (게임 오버/클리어) |
| `ERROR` | 오류 발생 |

> `PLAYING` 상태 내에서 `isSubmitting` 플래그로 턴 제출 중 여부를 구분하고, `messages[].loading` 플래그로 LLM 대기 상태를 표현한다. 설계 문서의 IDLE, TURN_SUBMITTING, TURN_CONFIRMED, LLM_PENDING, TURN_DISPLAYED가 `PLAYING` 하나로 통합되었다.

<details>
<summary>원본 설계 (7 States, 참조용)</summary>

| 상태 | 설명 |
|------|------|
| `IDLE` | 사용자 입력 대기 |
| `TURN_SUBMITTING` | 턴 요청 전송 중 |
| `TURN_CONFIRMED` | 서버 결과 수신 완료, HUD 즉시 반영 |
| `LLM_PENDING` | LLM 서술 대기 중 (로딩 표시) |
| `TURN_DISPLAYED` | 서술 포함 전체 턴 표시 완료 |
| `NODE_TRANSITION` | 노드 종료 후 다음 노드로 전환 중 |
| `ERROR` | 오류 발생 |

</details>

### 7.2 상태 전이 다이어그램

**실제 구현**:

```txt
TITLE
  -> LOADING (startNewGame)
      -> PLAYING (게임 시작 성공)
          -> PLAYING (턴 제출/결과 수신, isSubmitting으로 구분)
          -> NODE_TRANSITION (노드 종료)
              -> PLAYING (다음 노드 진입)
          -> RUN_ENDED (런 종료)
      -> ERROR (시작 실패)
          -> PLAYING (clearError, runId 존재 시)
          -> TITLE (reset)
```

### 7.3 렌더 규칙

- **`PLAYING`**: `serverResult` 즉시 반영 — HUD, 로그, 선택지 업데이트
- **LLM 대기**: narrator 메시지에 `loading: true` 표시 → 2초 간격 폴링 → LLM 완료 시 텍스트 교체 + pending 메시지/선택지 flush
- **전투 UI**: narrator 로딩 중에는 BattlePanel 숨김 → narrator 완료 후 표시
- **`LLM DONE`**: 같은 `turnNo`의 narration만 덧씌움 — 수치 변경 금지

---

## 8. Downed State & Recovery 시스템

> 목표: 플레이어 사망을 최소화하고, 쓰러짐을 스토리/시스템 이벤트로 전환하여
> 과도한 리셋을 방지하면서 긴장감을 유지

### 8.1 기본 원칙

- HP 0 = **즉시 사망이 아님**
- 플레이어는 `DOWNED` 상태로 전환
- RUN은 즉시 종료되지 않음
- 시스템적/스토리적 개입이 발생

### 8.2 상태 전이

```
HP > 0  → 정상 (NORMAL)
HP == 0 → DOWNED
DOWNED  → RECOVERED 또는 RUN_ABORTED
```

### 8.3 DOWNED 발생 시 처리 흐름

1. 현재 전투 즉시 종료
2. 적은 철수 또는 상황 종료 처리
3. 구조 이벤트 발생
4. 페널티 적용
5. 안전 지점으로 이동

### 8.4 구조 개입 방식

구조는 Node/Run 설정에 따라 달라지며, 다양한 스토리 연출이 가능:

- 동료가 개입하여 구출
- 길드 구조대 파견
- 적이 포로로 잡았다가 탈출 이벤트
- 의식을 잃고 마을에서 깨어남

### 8.5 페널티 시스템

DOWNED 시 반드시 발생하는 페널티:

- RUN 보상 감소
- 임시 장비 일부 파손
- 스태미나 감소 상태로 복귀
- 스토리 신뢰도 감소 (특정 NPC)
- 특정 노드 재도전 불가

### 8.6 영구 성장과의 관계

- 영구 스탯 감소 **없음** — 실패 학습 구조 유지
- GP 보상은 감소 가능
- 플레이어의 영구 성장은 보호됨

### 8.7 긴장감 유지 장치

연속 DOWNED 발생 시 점진적 불이익:

- RUN 강제 종료 가능
- 구조 비용 증가
- 특정 세력 신뢰도 하락

### 8.8 UI/LLM 연출

LLM은 DOWNED 상태를 내러티브로 묘사:

- "시야가 어두워진다"
- "누군가 당신을 끌어낸다"
- "다시 눈을 떴을 때…"

> 수치 노출 금지 — 서버 결과는 HUD로만 전달

### 8.9 예외: 스토리 사망

- 특정 보스/엔딩 분기에서만 실제 사망 가능
- 이는 시스템 페널티가 아닌 **스토리 이벤트**로 취급

---

## 9. 에러 처리

### 9.1 네트워크/서버 에러

- UI 상태 머신의 `ERROR` 상태로 전환
- 사용자에게 **retry** 또는 **cancel** 선택지 제공
- retry 시 `TURN_SUBMITTING`으로 재진입
- cancel 시 `IDLE`로 복귀

### 9.2 LLM 실패 처리

- 서버 결과는 이미 확정(커밋)되었으므로 게임 진행에 영향 없음
- LLM 타임아웃 시 `llm_status`가 `PENDING`으로 유지
- 클라이언트는 서술 없이 게임 진행 가능 (서버 결과만으로 HUD 반영)
- LLM 재시도는 서버 측에서 비동기로 처리

### 9.3 중복 요청 방어

- `idempotencyKey`로 동일 턴 중복 생성 방지
- `expectedNextTurnNo`로 클라이언트-서버 턴 번호 동기화 검증
- Redis 분산 락으로 LLM 중복 호출 방지

---

## 10. 관련 문서

- 전투 규칙 정본: `combat_system.md`
- DB 스키마 정본: `schema/07_database_schema.md`
