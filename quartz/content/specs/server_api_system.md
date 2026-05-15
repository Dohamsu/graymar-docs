# Server API & Runtime System v1

> 통합 설계서: API Contract + LLM Worker Async Architecture + Turn Detail Endpoint
> 원칙: 서버 SoT, 멱등성, LLM 실패 무해성, 재시도 안전
>
> 관련 정본: `combat_engine_resolve_v1.md` (전투 Resolve), `node_resolve_rules_v1.md` (노드별 처리), `battlestate_storage_recovery_v1.md` (저장/복구)

---

# Part 1: API Contract & Runtime Rules

---

## 1. 설계 철학

1. 서버가 Source of Truth
2. 모든 수치 판정은 서버에서만 수행
3. LLM은 결과를 바꾸지 못한다
4. API는 멱등적이며 재시도에 안전해야 한다
5. 복구 시 LLM 재호출 없이 화면을 재구성할 수 있어야 한다

---

## 1.5 POST /v1/runs (RUN 생성)

새 RUN을 시작한다.

- **Request**: difficulty(옵션), runConfig(옵션), `clientRunRequestId`(권장; 멱등 생성용)
- **Response**: run(ACTIVE) + initial server_result(선택; 첫 화면 필요 시)
- **Error**: 401 Unauthorized, 422 Invalid config

---

## 2. POST /v1/runs/{runId}/turns

### 2.1 처리 흐름

1. idempotencyKey 확인
2. expectedNextTurnNo 검증
3. 입력 타입 분기
4. Rule Parser 실행
5. (필요 시) LLM Intent Parser
6. Policy Check
7. Action DSL 생성
8. 수치 판정 수행
9. server_result_v1 생성
10. DB 저장 (turn + run 상태 갱신)
11. LLM 서술 요청 (옵션)
12. 응답 반환

### 2.2 멱등성 규칙

- (runId, idempotencyKey) 유니크 — 기본 멱등성 키
- (runId, turnNo) 유니크 — 추가 멱등성 보장
- `clientTurnId`(옵션) — 네트워크 재시도 식별 보조키
- 동일 key 재요청 시 기존 결과 그대로 반환
- 입력 내용이 다르면 409 또는 422

### 2.3 동시성 규칙

- expectedNextTurnNo != run.current_turn_no → 409 CONFLICT
- 성공 시 run.current_turn_no++

### 2.4 입력 타입 처리

#### ACTION
- 자유 텍스트
- Rule Parser 우선
- ~~실패 시 LLM 보조 파싱~~ (v1 미구현: 100% Rule Parser로 처리)

#### CHOICE
- 서버가 제공한 choices[] 중 하나만 허용
- 존재하지 않는 choiceId는 거부

#### SYSTEM
- CHECK_STATUS
- INVENTORY
- NOTE
- HELP

### 2.5 POST /v1/runs/{runId}/choices/{choiceId} (선택지 전용, 옵션)

UI choice를 별도 엔드포인트로 제출하고 싶을 때 사용한다.

- 내부적으로 `/turns`와 동일 파이프라인 사용
- request는 `{ type: "CHOICE", choiceId }`로 정규화
- Response/Error: `/turns`와 동일

---

## 3. server_result_v1 역할

server_result는
"이 턴에 서버가 확정한 모든 결과"의 정본이다.

구성:

- summary.short → 짧은 로그
- events[] → UI/로그/팩트 추출용
- diff → HUD 상태 변경
- ui → 다음 턴 입력 가이드
- choices → 서버가 허용한 선택지
- flags → 특수 상태

LLM은 이 결과를 바꾸지 못한다.

---

## 4. LLM 처리 규칙

### 4.1 서술 생성 기본 정책

**기본(동기)**: POST /turns 응답에 서술(narrative)을 포함한다. LLM 실패 시 다른 모델로 재시도 후 폴백 서술로 대체. LLM 장애는 HTTP 500으로 처리하지 않는다.

**비동기(옵션, 운영 확장)**: 동기 서술이 부담되면 비동기 전환을 허용한다.

비동기 모드 시:
- llm.status = PENDING
- 이후 워커가 생성
- 클라이언트는 폴링 또는 SSE로 수신

### 4.2 LLM 실패

- FAILED 상태 저장
- 게임 진행에는 영향 없음
- summary.short는 항상 존재

### 4.3 LLM 입력 구성

LLM은 다음을 받는다 (L0-L4 레이어):

- L0: theme memory (불변, 토큰 예산 압박에도 삭제 금지)
- L1: storySummary
- L2: nodeFacts (현재/직전 노드 merge)
- L3: recent summaries
- L4: server_result.events + summary.short (이번 턴 확정 사실)

diff(수치)는 전달하지 않는다. events 내 전투 이벤트 텍스트에는 적 이름이 한국어로 표시된다 (enemyNames 체인).

---

## 5. GET /v1/runs/{runId}

### 5.1 목적

- 앱 재접속
- 브라우저 새로고침
- 복구

한 번의 호출로 현재 화면을 복원한다.

### 5.2 포함되어야 하는 정보

> OpenAPI 정본: `schema/OpenAPI 3.1.yaml` → `GetRunResponse` 스키마

- run 메타 정보 (RunDetail: id, status, runType, actLevel, chapterIndex 등)
- currentNode (NodeDetail: type, state, environmentTags, nodeMeta)
- last server_result (ServerResultV1)
- memory snapshot (MemorySnapshot: theme, storySummary, nodeFacts, recent)
- battleState (BattleState: 전투 중인 경우만. distance/angle은 per-enemy 정본)
- 최근 N개 턴 요약 (TurnSummary[])
- 페이지네이션 (PageInfo)

### 5.3 복구 원칙

1. lastResult.summary.short 표시
2. llm_output이 존재하면 표시
3. HUD는 diff 또는 battle_state 기반 복원
4. LLM 재호출 없음

---

## 6. 전투 재개 규칙

battle_state가 존재하면:

- phase 기반으로 전투 재개
- lastResolvedTurnNo와 run.current_turn_no가 일치해야 함
- 불일치 시 서버가 우선

---

## 7. 페이지네이션 규칙

GET /turns

- limit 기본 20
- before 기반 커서 페이징
- 최신 → 과거 순 정렬

---

## 8. 에러 처리 원칙

### 8.1 HTTP 상태 코드

| 코드 | 상황 | 에러 코드 |
|------|------|-----------|
| 401 | 인증 실패 | UNAUTHORIZED |
| 404 | run/turn 없음 | NOT_FOUND |
| 409 | turn 번호 불일치 | TURN_NO_MISMATCH |
| 409 | 동시 요청 충돌 | TURN_CONFLICT |
| 422 | 정책상 거부 (DENY) | POLICY_DENY |
| 422 | 입력 검증 실패 | INVALID_INPUT |
| 500 | 내부 오류 (LLM 장애 제외) | INTERNAL_ERROR |

### 8.2 표준 에러 바디

```json
{
  "code": "TURN_CONFLICT",
  "message": "사용자 표시 가능한 메시지",
  "details": { "개발용 추가 정보" }
}
```

---

## 9. 안정성 보장 요소

- 모든 turn은 DB 트랜잭션 안에서 생성
- run.current_turn_no 갱신과 turn 생성은 같은 트랜잭션
- battle_state 갱신도 동일 트랜잭션
- rng_state 저장

### 9.1 노드별 UI 힌트 (권장)

`server_result.ui`에 다음을 포함한다:

- `availableActions`: 현재 노드에서 가능한 입력 타입
- `choices[]`: { id, label, hint? }
- `primaryCTA`: "계속" | "구매" | "휴식" | "종료" 등
- `recommendedActions`: 옵션 플래그가 켜졌을 때만 제공

### 9.2 성능/안정성 권장

- `/turns`는 서버 단에서 timeout을 둔다 (예: 10~20초)
- LLM 재시도는 모델별 우선순위 리스트로 수행
- 응답이 길어질 경우 narrative를 요약하거나 UI를 우선 반환

---

## 10. 보안/무결성

- 클라이언트는 절대 수치를 계산하지 않는다
- diff는 서버가 계산
- choice는 서버가 생성
- LLM은 권한이 없다

---

# Part 2: LLM Worker & Async Narrative Architecture

---

## 11. 전체 처리 개요

### 11.1 턴 처리 (동기, 반드시 빠름)

POST /turns 요청 시 서버는:
1) 입력 파싱(RULE 우선, 필요 시 LLM 파싱)
2) Policy Check
3) Action Plan 생성
4) 수치 판정 수행
5) server_result_v1 생성/저장
6) (옵션) 서술 생성 작업 enqueue
7) 즉시 응답 반환

서술이 늦거나 실패해도 서버 결과는 즉시 확정된다.

### 11.2 서술 생성 (비동기, 느려도 됨)

별도 워커가:
- LLM 컨텍스트(llm_ctx_v1) 생성
- 모델 호출
- llm_out_v1 저장
- 클라이언트가 폴링/SSE로 수신

---

## 12. LLM 상태 머신

### 12.1 turns.llm_status

- SKIPPED: 서술 생성 비활성(설정/off)
- PENDING: 작업 대기/진행 전
- RUNNING: 워커가 잡았음(락 소유)
- DONE: llm_output 저장 완료
- FAILED: 모든 재시도/폴백 실패

권장 전이:
SKIPPED (처음부터)
PENDING -> RUNNING -> DONE
PENDING -> RUNNING -> FAILED
RUNNING -> PENDING (워커 타임아웃/크래시 복구)

### API 노출 규칙

| API | 노출 enum | 설명 |
|-----|-----------|------|
| POST /turns 응답 | PENDING, DONE, FAILED, SKIPPED | POST 시점에 RUNNING 상태는 불가능 (워커가 아직 미수신) |
| GET /turns/{turnNo} 응답 | PENDING, RUNNING, DONE, FAILED, SKIPPED | 조회 시점에 워커가 처리 중일 수 있음 |

> POST 응답에 RUNNING이 없는 것은 의도적 설계이다.

---

## 13. 데이터 모델

### 13.1 turns에 최소 필요 필드

- llm_status: PENDING/DONE/FAILED/SKIPPED
- llm_output: text (DONE 시)
- llm_error: jsonb (FAILED 시)
- (권장 추가)
  - llm_attempts: int default 0
  - llm_locked_at: timestamptz null
  - llm_lock_owner: text null (worker_id)
  - llm_model_used: text null
  - llm_completed_at: timestamptz null

> v1은 turns에 붙이는 방식이 단순하고 운영이 쉽다.

---

## 14. 워커 큐 설계

### 14.1 Queue 선택지

- DB 폴링(가장 단순, v1 권장)
- Redis Queue/BullMQ (규모 커지면)
- SQS/PubSub (클라우드 운영)

v1 추천: **DB 폴링**
- turns에서 `llm_status=PENDING`을 가져와 처리
- 락으로 중복 처리 방지

### 14.2 작업 선택 (워커 fetch)

조건:
- llm_status = PENDING
- (선택) created_at 오래된 순
- (선택) run_id 단위로 과도한 동시 처리 제한

---

## 15. 락 (동시 워커 안전)

### 15.1 DB 락 방식 (권장)

1) 후보 rows select
2) 원자적 update로 락 획득

락 획득 조건:
- llm_status = PENDING
- (추가) llm_locked_at is null OR now-locked_at > lock_timeout

락 타임아웃:
- 30~60초 권장

### 15.2 크래시 복구

- RUNNING 상태인데 `now - llm_locked_at > lock_timeout`이면
  - PENDING으로 되돌리고 재시도 가능

---

## 16. LLM 컨텍스트 생성 규칙

워커는 아래 순서로 `llm_ctx_v1`을 만든다(정본).
1) run_memories.theme (L0)
2) run_memories.storySummary (L1)
3) node_memories.nodeFacts (L2) (현재/직전 노드 merge)
4) recent_summaries (L3)
5) server_result.events + summary.short (이번 턴 확정 사실)
6) ui/choices(필요 시, 선택)

주의:
- diff(수치)는 LLM에 전달하지 않는 것을 기본으로 한다
- events.text는 과장 연출을 막기 위해 "사실 중심"이어야 한다

---

## 17. 모델 호출 정책

### 17.1 타임아웃

- 3~8초 권장(운영 상황에 맞춰)
- 타임아웃이면 재시도

### 17.2 재시도/폴백

권장:
- 같은 모델 1회 재시도(총 2회)
- 실패 시 폴백 모델로 1회
- 그래도 실패하면 FAILED

예:
- attempt 1: primary model
- attempt 2: primary model (retry)
- attempt 3: fallback model

### 17.3 결과 저장 규칙

- DONE:
  - llm_output 저장
  - llm_model_used 기록
  - llm_completed_at 기록
- FAILED:
  - llm_error에 마지막 에러 + attempt history 저장
  - llm_status=FAILED
  - 클라에는 summary.short를 계속 사용

---

## 18. 서술 품질/안정 가드레일

### 18.1 금지

- 피해/판정/드랍 결과를 변경하거나 추가로 "만들기"
- 서버에 없는 선택지 생성
- 수치 과다 노출(피해량/확률을 장문으로 설명)

### 18.2 권장

- bonusSlot=true면 "틈/기회/리듬" 같은 서술 힌트
- toneHint에 맞춘 문체(tense/calm 등)
- server_result.summary.short 내용을 본문에 자연스럽게 반영

---

## 19. 클라이언트 전달 방식

### 19.1 폴링 (단순, v1 권장)

- GET /v1/runs/{runId}/turns/{turnNo} (턴별 LLM 상태 조회)

폴링 주기:
- 500ms~1500ms (초기)
- 3~5초 (백그라운드)

> **v1 구현 현황**: 클라이언트는 `GET /v1/runs/{runId}/turns/{turnNo}` 엔드포인트로 **2초 간격, 최대 15회(30초)** 폴링한다. `llm.status === 'DONE'`이면 `llm.output`을 narrator 메시지에 반영하고 pending 메시지/선택지를 flush한다. `FAILED`이거나 최대 횟수 초과 시 `summary.short`를 fallback 텍스트로 사용한다.

### 19.2 SSE (선택)

- /v1/runs/{runId}/events (turnNo별 llm_status 업데이트 push)
- DONE/FAILED 시 클라가 텍스트 영역 갱신

v1은 폴링으로 충분하며, SSE는 추후 추가한다.

---

## 20. API 확장 (권장)

### 20.1 POST /v1/runs/{runId}/turns/{turnNo}/narrative:retry (운영용)

- FAILED된 서술만 재시도(관리자/개발자 플래그 필요)

---

## 21. 운영/관측 지표

필수 지표:
- LLM DONE 비율
- 평균 생성 시간(ms)
- 타임아웃 비율
- 재시도 횟수 분포
- 폴백 모델 사용률
- 노드 타입별 실패율(COMBAT/EVENT 등)

로그:
- turnNo, runId, model, prompt_tokens/response_tokens(가능하면), latency, error_code

---

## 22. 장애 시 UX 규칙

- PENDING: narrator 메시지에 `loading: true` 표시 (바운스 애니메이션) + 2초 간격 폴링
- FAILED/TIMEOUT: `summary.short` 또는 `summary.display`를 fallback 텍스트로 사용 + pending 메시지/선택지 즉시 flush
- DONE: `llm.output` 텍스트로 narrator 교체 + pending flush

게임 진행은 항상 가능해야 한다.

> **v1 구현 현황 (업데이트)**: BattlePanel은 COMBAT 노드에서 적 데이터가 있으면 **항상 표시**된다 (narrator 로딩 대기 없음). 전투 중 턴은 `options: { skipLlm: true }`로 제출되어 LLM 상태가 `SKIPPED`가 되며, 클라이언트는 전투 이벤트(BATTLE/DAMAGE/MOVE/STATUS)를 SYSTEM 메시지로 직접 표시한다. NARRATOR 메시지는 LLM 스킵 시 생략된다. 이를 통해 전투 턴당 대기 시간이 15-20초에서 1-2초로 단축되었다.

---

## 23. 구현 우선순위 (v1)

1) turns.llm_status + 락 필드 추가
2) 워커: DB 폴링 + 락 획득 + LLM 호출 + 저장
3) GET /runs 에 turns llm_status 포함
4) 클라: PENDING/DONE 표시 로직
5) (추후) SSE/푸시

---

# Part 3: Turn Detail Endpoint

`GET /v1/runs/{runId}/turns/{turnNo}`

---

## 24. 목적

- 특정 턴의 "서버 확정 결과 + LLM 상태/서술"을 단일 호출로 조회한다.
- 재접속/복구뿐 아니라 디버깅, 운영, 리플레이에 사용한다.

원칙:
- server_result_v1이 정본이다.
- llm_output은 부가 정보이며, 실패/지연이 게임 진행을 막지 않는다.

---

## 25. Endpoint

- Path: `/v1/runs/{runId}/turns/{turnNo}`
- Auth: 사용자 인증 필수
- 권한: 해당 runId의 소유자만 조회 가능

---

## 26. 조회 규칙

### 26.1 항상 반환해야 하는 것

- run 메타(최소)
- turn 메타
- server_result_v1 (존재하면)
- llm 상태 + (DONE면) llm_output

### 26.2 server_result가 없는 경우

- turnNo가 존재하지 않음: 404
- turn row는 존재하나 server_result가 null(비정상/마이그레이션): 500 또는 409

v1에서는 `turns.server_result`를 not null로 두는 것을 권장한다.

---

## 27. OpenAPI 3.1 (핵심)

```yaml
openapi: 3.1.0
info:
  title: Text RPG API
  version: 0.1.0

paths:
  /v1/runs/{runId}/turns/{turnNo}:
    get:
      summary: Get a specific turn detail
      operationId: getTurnDetail
      parameters:
        - name: runId
          in: path
          required: true
          schema: { type: string, minLength: 1, maxLength: 80 }
        - name: turnNo
          in: path
          required: true
          schema: { type: integer, minimum: 0 }
        - name: includeDebug
          in: query
          required: false
          schema: { type: boolean, default: false }
          description: "개발/운영 환경에서만 허용(파싱/정책/액션플랜 등 디버그 필드 포함)"

      responses:
        "200":
          description: Turn detail
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/TurnDetailResponse"
        "404":
          description: Not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"
        "403":
          description: Forbidden
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

components:
  schemas:
    TurnDetailResponse:
      type: object
      additionalProperties: false
      required: [run, turn, serverResult, llm]
      properties:
        run:
          $ref: "#/components/schemas/RunMeta"
        turn:
          $ref: "#/components/schemas/TurnMeta"
        serverResult:
          $ref: "#/components/schemas/ServerResultV1"
        llm:
          $ref: "#/components/schemas/LLMDetail"
        debug:
          oneOf:
            - { $ref: "#/components/schemas/TurnDebugBundle" }
            - { type: "null" }

    RunMeta:
      type: object
      additionalProperties: false
      required: [id, status, actLevel, currentTurnNo]
      properties:
        id: { type: string, minLength: 1, maxLength: 80 }
        status: { type: string, enum: [RUN_ACTIVE, RUN_ENDED, RUN_ABORTED] }
        actLevel: { type: integer, minimum: 1, maximum: 6 }
        currentTurnNo: { type: integer, minimum: 0 }

    TurnMeta:
      type: object
      additionalProperties: false
      required: [turnNo, inputType, rawInput, createdAt]
      properties:
        turnNo: { type: integer, minimum: 0 }
        nodeInstanceId: { type: string, minLength: 1, maxLength: 80 }
        nodeType: { type: string, enum: [COMBAT, EVENT, REST, SHOP, EXIT] }
        inputType: { type: string, enum: [ACTION, CHOICE, SYSTEM] }
        rawInput: { type: string, maxLength: 400 }
        createdAt: { type: string, format: date-time }

    LLMDetail:
      type: object
      additionalProperties: false
      required: [status]
      properties:
        status: { type: string, enum: [PENDING, RUNNING, DONE, FAILED, SKIPPED] }
        output:
          oneOf:
            - { type: string, maxLength: 4000 }
            - { type: "null" }
        modelUsed:
          oneOf:
            - { type: string, maxLength: 80 }
            - { type: "null" }
        completedAt:
          oneOf:
            - { type: string, format: date-time }
            - { type: "null" }
        error:
          oneOf:
            - { type: object, additionalProperties: true }
            - { type: "null" }

    TurnDebugBundle:
      type: object
      additionalProperties: false
      required: [parsedBy, parseConfidence, parsedIntent, policyResult, actionPlan]
      properties:
        parsedBy: { type: string, enum: [RULE, LLM, MERGED] }
        parseConfidence: { type: number, minimum: 0, maximum: 1 }
        parsedIntent: { type: object, additionalProperties: true }
        policyResult: { type: string, enum: [ALLOW, TRANSFORM, PARTIAL, DENY] }
        actionPlan: { type: array, maxItems: 12, items: { type: object, additionalProperties: true } }
        idempotencyKey:
          oneOf:
            - { type: string, maxLength: 80 }
            - { type: "null" }
        expectedNextTurnNo:
          oneOf:
            - { type: integer, minimum: 0 }
            - { type: "null" }

    ServerResultV1:
      type: object
      description: "Canonical: server_result_v1.schema.json"
      additionalProperties: true

    ErrorResponse:
      type: object
      additionalProperties: false
      required: [code, message]
      properties:
        code: { type: string, maxLength: 64 }
        message: { type: string, maxLength: 300 }
        details:
          type: object
          additionalProperties: true
```
