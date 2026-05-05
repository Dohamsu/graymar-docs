# 04 — 서버 아키텍처 · API · 입력 파이프라인 · 노드 처리

> 통합 문서: 서버 아키텍처 원칙, API 엔드포인트, HUB/LOCATION/COMBAT 턴 분기, 입력 파이프라인(COMBAT Rule Parser + LOCATION IntentParserV2), Policy & Transform, 노드 처리 규약, LLM Worker, 클라이언트 상태
>
> 원칙: 서버 SoT, 멱등성, LLM 실패 무해성, 재시도 안전
>
> 관련 정본: `03_combat_rules.md` (전투 엔진), `09_llm_context.md` (LLM 컨텍스트/캐싱)

---

## 1. 서버 아키텍처 개요

### 1.1 설계 철학 & 역할 분리

**서버는 숫자, LLM은 분위기** — 게임 로직과 내러티브를 완전히 분리한다.

| 영역 | 담당 |
|------|------|
| **서버** | 수치 계산, 확률 판정, 드랍, 상태 변화, DB 트랜잭션 |
| **LLM** | 서술(내러티브)만 생성 — 수치 변경 권한 없음 |
| **클라이언트** | HUD 렌더링, Phase 상태 머신, 사용자 입력 전송 |

- LLM 출력은 게임 결과에 **절대 영향 없음** (순수 연출용)
- 서버 결과가 먼저 확정되므로 LLM 지연/실패가 게임 진행을 막지 않음
- 클라이언트는 `serverResult` 기준으로 게임 상태를 반영, LLM 서술은 같은 turnNo의 narration만 덧씌움

### 1.2 턴 기반 데이터 흐름

```
1. 사용자 입력 수신 (POST /v1/runs/:runId/turns)
2. 서버 게임 엔진 계산 (DB 트랜잭션)
   - 노드 타입별 분기 (HUB / LOCATION / COMBAT)
   - 입력 파싱 → 판정 → server_result_v1 생성
   - turns insert (llm_status=PENDING) + run_sessions 업데이트
3. 트랜잭션 커밋 (게임 결과 확정)
4. LLM Worker (비동기): 컨텍스트 조립 → 서술 생성 → llm_output 저장
5. 클라이언트 폴링 → narrator 교체
```

### 1.3 멱등성 & 안정성

- `(runId, idempotencyKey)` + `(runId, turnNo)` 이중 유니크
- 동일 key 재요청 → 기존 결과 반환, 입력 불일치 → 409/422
- 모든 turn은 DB 트랜잭션 안에서 생성 (turn + run + node_state + battle_state)
- RNG 결정성: `seed + cursor` 저장, 소비 순서 고정 (hitRoll → varianceRoll → critRoll)

### 1.4 server_result_v1

"이 턴에 서버가 확정한 모든 결과"의 정본. LLM은 이 결과를 바꾸지 못한다.

| 구성 요소 | 설명 |
|-----------|------|
| `summary.short` | 짧은 로그 (LLM fallback 텍스트) |
| `events[]` | UI/로그/팩트 추출용 이벤트 |
| `diff` | HUD 상태 변경 (클라이언트 전용, LLM 비전달) |
| `ui` | 다음 턴 입력 가이드 + WorldState + resolveOutcome |
| `choices[]` | 서버가 허용한 선택지 |
| `flags` | 특수 상태 (bonusSlot, downed, battleEnded) |

---

## 2. API 엔드포인트

### 2.1 엔드포인트 목록

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/auth/register` | 회원가입 (email, password, nickname) |
| POST | `/v1/auth/login` | 로그인 (email, password) → JWT |
| POST | `/v1/runs` | 새 RUN 생성 |
| GET | `/v1/runs` | 활성 RUN 조회 (userId 기반) |
| GET | `/v1/runs/:runId` | RUN 상태 조회 (재접속/복구) |
| POST | `/v1/runs/:runId/turns` | 턴 제출 (ACTION/CHOICE) |
| GET | `/v1/runs/:runId/turns/llm-usage` | LLM 사용량 조회 |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 (LLM 폴링용) |
| POST | `/v1/runs/:runId/turns/:turnNo/retry-llm` | LLM 재시도 (FAILED → PENDING) |
| POST | `/v1/campaigns` | 캠페인 생성 |
| GET | `/v1/campaigns` | 활성 캠페인 조회 |
| GET | `/v1/campaigns/:id` | 캠페인 상세 조회 |
| GET | `/v1/campaigns/:id/scenarios` | 시나리오 목록 조회 |
| GET | `/v1/settings/llm` | LLM 설정 조회 |
| PATCH | `/v1/settings/llm` | LLM 설정 변경 |

### 2.2 POST /v1/runs — RUN 생성

- **Request**: difficulty(옵션), runConfig(옵션), `clientRunRequestId`(멱등 생성용)
- **Response**: run(ACTIVE) + initial server_result + HUB 초기 선택지
- 런 시작 시 `WorldState`, `ArcState`, `Agenda` 초기화

### 2.3 POST /v1/runs/:runId/turns — 턴 제출

1. idempotencyKey 확인 — 동일 키 존재 시 기존 결과 반환
2. RUN 조회 + 소유권 검증 + 상태 확인 (RUN_ACTIVE)
3. expectedNextTurnNo 검증 — 불일치 시 409 CONFLICT
4. 현재 노드 조회 (NODE_ACTIVE 확인)
5. **nodeType에 따라 분기** (HUB / LOCATION / COMBAT) → 3장 참조
6. 결과 커밋 + 응답 반환

| 입력 타입 | 설명 | 사용 노드 |
|-----------|------|-----------|
| ACTION | 자유 텍스트 입력 | LOCATION, COMBAT |
| CHOICE | 서버 제공 선택지 중 택1 | HUB, LOCATION, COMBAT |
| SYSTEM | 진입/전환 자동 생성 | 모든 노드 (서버 내부) |

### 2.4 GET /v1/runs/:runId — RUN 상태 조회

재접속/복구용. 한 번의 호출로 현재 화면 복원. 포함: run 메타, currentNode, last server_result, battleState(전투 중만), WorldState. LLM 재호출 없음.

### 2.5 GET /v1/runs/:runId/turns/:turnNo — 턴 상세

LLM 폴링용. 항상 반환: run 메타, turn 메타, serverResult, llm(status + output). `includeDebug=true` 시 parsedIntent, policyResult, actionPlan 포함.

### 2.6 에러 처리

| 코드 | 상황 | 에러 코드 |
|------|------|-----------|
| 404 | run/turn 없음 | NOT_FOUND |
| 409 | turn 번호 불일치 / 동시 충돌 | TURN_NO_MISMATCH / TURN_CONFLICT |
| 422 | 정책 거부 / 입력 검증 실패 | POLICY_DENY / INVALID_INPUT |
| 500 | 내부 오류 (LLM 장애 제외) | INTERNAL_ERROR |

에러 바디: `{ code, message, details }`

---

## 3. 턴 처리 분기 — HUB / LOCATION / COMBAT

턴 제출 시 현재 노드의 `nodeType`에 따라 다른 파이프라인으로 분기한다.

### 3.1 Node 타입

| Enum | 상태 | 설명 |
|------|------|------|
| **HUB** | 활성 | 거점 — LOCATION 선택, Heat 해결 |
| **LOCATION** | 활성 | 탐험 — Action-First 이벤트 매칭 |
| **COMBAT** | 활성 | 전투 — 전술 액션 판정 |
| EVENT/REST/SHOP/EXIT | 비활성 | HUB 엔진 이전 설계, 현재 미사용 |

---

## 부록 A: 구 노드 타입 처리 규칙 (레거시 참조)

> 원본 참조: [[specs/node_resolve_rules_v1|node resolve rules v1]]

현재 HUB 엔진에서는 HUB/LOCATION/COMBAT만 사용하지만, 향후 구조화된 미션(Structured Mission) 모드에서 EVENT/REST/SHOP/EXIT 노드를 재활용할 수 있다. 아래는 각 노드의 서버 처리 규약이다.

### EVENT 노드 규약

- **서버 처리 범위**: 이벤트 ID 선택, 선택지 생성, 선택 결과에 따른 상태 변화, 단계 진행/종료
- **LLM**: 장면 묘사, 선택지 문구 표현, 결과 서술 (상태 변화는 server_result 기반)
- **NodeState**: `{ eventId, stage, availableChoices[], flags }`
- **처리 패턴**: INTRO(상황 제시) → CHOICE(선택 수신) → RESOLVE(상태 변경 + 다음/종료)
- **FREEFORM 입력**: 가장 가까운 choice로 TRANSFORM하거나, 매칭 실패 시 재선택 요청
- **종료**: stage가 END에 도달하면 `nodeOutcome = NODE_ENDED`

### REST 노드 규약

- **처리**: 회복량 계산, 상태이상 정리, 다음 노드 전이
- **입력**: CHOICE 기반 — "짧은 휴식" / "깊은 휴식" / "정찰/대화"
- **효과**: Short Rest: stamina +1, HP +10% maxHP / Long Rest: stamina +2, HP +25% maxHP, DOT 1개 제거
- **종료**: 1~2턴 내 종료 원칙, 선택 후 `nodeOutcome = NODE_ENDED`

### SHOP 노드 규약

- **처리**: 상품 리스트 확정(진입 시), 가격/재고 확정, 구매/판매 처리
- **NodeState**: `{ shopId, catalog[], playerGoldSnapshot, ui }`
- **입력**: CHOICE 또는 COMMAND형 FREEFORM ("포션 2개 구매")
- **검증**: 가능 → PURCHASE 이벤트 + 상태 변경 / 불가 → SYSTEM(사유) + 변화 없음
- **종료**: "나간다" 선택 시 `NODE_ENDED`, catalog는 노드 유지 중 고정

### EXIT 노드 규약

- **처리**: RUN 정산 트리거, 영구/임시 보상 반영, RUN 상태 ENDED 전환
- **입력**: CHOICE — "귀환한다(종료)" / "더 진행한다(취소)"
- **종료**: 귀환 선택 시 `nodeOutcome = RUN_ENDED`, `run.status = ENDED`

### 노드 공통 규칙

- **NodeInput**: `{ turnNo, input.type ∈ {FREEFORM, CHOICE}, input.text | input.choiceId }`
- **NodeOutput**: `{ nextNodeState, server_result_v1, nodeOutcome ∈ {ONGOING, NODE_ENDED, RUN_ENDED} }`
- **전이 시 컨텍스트**: 전투 결과, 획득 아이템/골드, 퀘스트 플래그, 이벤트 로그 요약
- **진입 시스템 메시지**: COMBAT → "전투가 시작된다!", EVENT → "새로운 상황이 펼쳐진다.", REST → "휴식을 취할 수 있는 장소에 도착했다.", SHOP → "상점에 도착했다.", EXIT → "여정의 끝이 보인다."

---

## 부록 B: 턴 파이프라인 10단계 확장

> 원본 참조: `Game_Turn_Orchestration_Spec_v1.md`

현재 LOCATION 턴 처리는 3.3절의 6단계이다. 향후 NPC/감정/정치 시스템 도입 시 아래 10단계로 확장한다.

### 확장 턴 파이프라인 (Authoritative Order)

| Step | 단계 | 설명 | 구현 상태 |
|------|------|------|-----------|
| 1 | Player Input Receive | 입력 수신 + 멱등성 확인 | ✅ 구현 |
| 2 | Intent Parsing | IntentParserV2 → ActionType 확정 | ✅ 구현 |
| 3 | Event Matching | EventMatcher 6단계 필터링 | ✅ 구현 |
| 4 | Server Resolve | 판정, 수치 계산, 결과 확정 | ✅ 구현 |
| 5 | NPC Injection Check | TurnOrchestrationService: pressure 기반 NPC 주입 판단 | ✅ 구현 |
| 6 | Emotional Peak Check | pressure ≥ 60 AND cooldown → peakMode 활성 | ✅ 구현 |
| 7 | Dialogue Posture Calc | NpcEmotionalService: 5축 감정 → effectivePosture 계산 | ✅ 구현 |
| 8 | LLM Prompt Build & Call | ContextBuilder + PromptBuilder + LlmCaller | ✅ 구현 |
| 9 | Turn Commit | RunState/NPCState/WorldState 저장 | ✅ 구현 |
| 10 | Off-screen Tick | 조건 충족 시 NPC 위치/agenda 진행 | ❌ 미구현 |

### 멱등성 규칙

- `(runId, turnNo)` + `(runId, idempotencyKey)` 이중 유니크
- 동일 turnId 중복 요청 → 이전 결과 반환
- LLM 호출 실패 → Server Resolve 결과만으로 fallback 가능

### 동시성 처리

- RunState 단위 트랜잭션
- NPC/World 업데이트는 Turn Commit 이후 단일 트랜잭션
- Off-screen Tick은 별도 큐 처리 가능

### Emotional Peak 통합

- RunState에 `pressure` 필드 추가 (0~100)
- `pressure >= 60 AND cooldown 충족` → peakMode 활성
- peakMode는 LLM prompt length, dialogue intensity에만 영향 (게임 규칙 변경 없음)
- LLM 실패 시 peakMode 자동 비활성화 (Safe Degradation)

### 3.2 HUB 턴 — CHOICE only

ACTION(자유 텍스트) 불가. CHOICE만 허용.

```
go_market / go_guard / go_harbor / go_slums
  → moveToLocation → LOCATION 노드 생성 → actionHistory 초기화
contact_ally  → Heat 감소 (최고 관계 NPC 자동 선택)
pay_cost      → 골드로 Heat 해소
```

**LOCATION 이동 시**: HUB 노드 NODE_ENDED → 새 LOCATION 노드 생성 → enter 턴 자동 생성(SYSTEM, PENDING) → WorldState.currentLocationId 업데이트 → Arc unlock 체크

### 3.3 LOCATION 턴 — Action-First 파이프라인

```
ACTION(자유 텍스트) 또는 CHOICE 입력
  ↓
go_hub CHOICE? → HUB 복귀 (장기기억 저장 + actionHistory 초기화)
  ↓
IntentParserV2 파싱 → 고집 카운트 계산
  ↓
EventMatcher.match (location × conditions × gates × affordance × heat간섭 × 가중치)
  ↓
ResolveService.resolve → SUCCESS / PARTIAL / FAIL
  ↓
전투 트리거? → COMBAT 서브노드 삽입 (LOCATION 유지, 전투 종료 후 복귀)
  ↓
WorldState 업데이트 (Heat, Tension, Time, Safety, Relations, Flags, Deferred)
  ↓
Agenda + Arc commitment 진행 → SceneShell 선택지 생성 → 커밋
```

### 3.4 COMBAT 턴 — 전투 엔진

```
ACTION 또는 CHOICE → Rule Parser → Policy Check
  ↓
DENY? → denyResult + 대체안 제시
  ↓
Action Plan 생성 → NodeResolver.resolve → BattleState 업데이트
  ↓
CombatOutcome: ONGOING / VICTORY / DEFEAT / FLEE_SUCCESS
  ├── DEFEAT → RUN_ENDED
  └── VICTORY/FLEE → 부모 LOCATION 복귀 (Heat +3)
```

전투 중 턴: `options: { skipLlm: true }` → SKIPPED → **1-2초** 응답. 전투 이벤트(BATTLE/DAMAGE/MOVE/STATUS)는 SYSTEM 메시지로 직접 표시. 전투 진입/종료 시에만 LLM 내러티브 생성.

### 3.5 노드 전이

```
HUB ──[go_location]──→ LOCATION ──[triggerCombat]──→ COMBAT
 ↑                         ↑                            │
 └──[go_hub]───────────────┘←──[VICTORY/FLEE]───────────┘
```

- 전환 시 enter 턴 자동 생성 (inputType: SYSTEM, llmStatus: PENDING)
- HUB↔LOCATION 전환: 전환 화면 없이 즉시 전환
- 전이 시 전달: WorldState, 전투 결과, 아이템/골드 변화, 이벤트 요약

---

## 4. 입력 파이프라인

노드 타입에 따라 서로 다른 파서를 사용한다.

### 4.1 COMBAT — Rule Parser

> 정본: `server/src/engine/input/rule-parser.service.ts`

자유 텍스트를 전투 ActionType(8종)으로 변환.

| ActionType | 키워드 예시 |
|------------|------------|
| ATTACK_MELEE | 베다, 휘두르, 찌르, 공격, 칼, 검 |
| ATTACK_RANGED | 쏜다, 발사, 활, 화살, 던지 |
| EVADE | 구르, 피하, 회피, 굴러 |
| DEFEND | 막아, 방패, 방어 |
| MOVE | 오른쪽, 왼쪽, 이동, 물러 |
| FLEE | 도망, 도주, 탈출 |
| USE_ITEM | 포션, 아이템, 사용 |
| INTERACT | 환경, 문, 열 |

- `confidence >= 0.7`이면 확정 (LLM 호출 없음)
- 매칭 실패 시 DEFEND로 축소
- v1: 100% 룰 기반, LLM 보조 파싱 미구현

### 4.2 LOCATION — IntentParserV2

> 정본: `server/src/engine/hub/intent-parser-v2.service.ts`

자유 텍스트를 탐험 ActionType(15종)으로 변환.

**IntentActionType**: INVESTIGATE, PERSUADE, SNEAK, BRIBE, THREATEN, HELP, STEAL, FIGHT, OBSERVE, TRADE, TALK, SEARCH, MOVE_LOCATION, REST, SHOP

**ParsedIntentV2 출력**:

```typescript
{
  inputText: string,
  actionType: IntentActionType,
  tone: 'CAUTIOUS' | 'AGGRESSIVE' | 'DIPLOMATIC' | 'DECEPTIVE' | 'NEUTRAL',
  target: string | null,
  riskLevel: 1 | 2 | 3,
  intentTags: string[],
  confidence: 0 | 1 | 2,
  source: 'RULE' | 'LLM' | 'CHOICE',
  suppressedActionType?: IntentActionType,  // 고집 시스템용
  escalated?: boolean,
}
```

### 4.3 고집(Insistence) 에스컬레이션

같은 LOCATION에서 동일 패턴의 강한 행동이 반복 억제될 때 자동 승격.

- `suppressedActionType`: 키워드 매칭되었으나 우선순위에 밀린 actionType
- **3회 연속** 억제 시 에스컬레이션 (예: THREATEN → FIGHT)
- `escalated: true` → LLM에 "행동 그대로 실행" 강한 서술 지시
- LOCATION 이동 또는 HUB 복귀 시 초기화, actionHistory 최대 10개

### 4.4 CHOICE 입력 처리

CHOICE 시 이전 턴의 `serverResult.choices[]`에서 `choiceId` 매칭 → `label`을 rawInput으로, `action.payload`를 파서에 전달, source를 `'CHOICE'`로 설정.

---

## 5. Policy & Transform

### 5.1 정책 결과 타입

기본 전략: **COOPERATIVE_TRANSFORM** — DENY는 최후의 수단.

| 타입 | 설명 |
|------|------|
| ALLOW | 그대로 실행 |
| TRANSFORM | 유사 행동으로 변환하여 실행 (기본) |
| PARTIAL | 일부만 실행 (불가능한 조각 제거) |
| DENY | 실행 불가 (극소화) — 대체안 제시 필수 |

### 5.2 불변 규칙

- **서버 SoT**: 수치는 서버만 결정, 확정 결과 변경 불가, RNG 재현성 유지
- **세계관**: 존재하지 않는 능력/아이템/장소 확정 생성 불가
- **시스템**: Action slot cap = 3 초과 불가, stamina 무시 불가, 상태머신 역행 불가

### 5.3 TRANSFORM 규칙

| 패턴 | 변환 예시 |
|------|-----------|
| 불가능 → 가능한 근접 행동 | "순간이동해서 뒤를 잡는다" → EVADE + MOVE |
| 과도한 다중 행동 → 콤보 2단 축약 | "구르고, 쏘고, 달려들어 베고..." → EVADE + ATTACK |
| 확정 결과 요구 → 시도 | "무기를 빼앗아 던진다" → DISARM_TRY |
| 리소스 무시 → 비용 증가 | "무한 연속 사격" → stamina 비용 증가 + 페널티 |

### 5.4 판정 구조 — 리스크-보상

서버는 "의도"가 아니라 "행동"을 판정. ActionPlan은 고정 순서로 resolve.

복합 행동일수록: stamina 소모 증가 / 실패 확률 증가 / 성공 시 보상 증가

---

## 6. 노드 처리 규약

### 6.1 공통 인터페이스

- **NodeInput**: turnNo, input.type (ACTION | CHOICE), input.text 또는 input.choiceId
- **NodeOutput**: nextNodeState, server_result_v1, nodeOutcome (ONGOING | NODE_ENDED | RUN_ENDED)

### 6.2 COMBAT 노드 종료 조건

| CombatOutcome | nodeOutcome | 후속 처리 |
|---------------|-------------|-----------|
| ONGOING | ONGOING | 전투 계속 |
| VICTORY | NODE_ENDED | 보상 정산 → 부모 LOCATION 복귀 (Heat +3) |
| DEFEAT | RUN_ENDED | 런 종료 |
| FLEE_SUCCESS | NODE_ENDED | 부모 LOCATION 복귀 (Heat +3) |

BattleState 관리: distance/angle은 per-enemy 정본 (playerState에 없음)

### 6.3 LOCATION 노드

- ACTION: IntentParserV2 → EventMatcher → ResolveService
- CHOICE: go_hub(HUB 복귀) 또는 이벤트 선택지
- 전투 트리거 시 COMBAT 서브노드 삽입, 전투 종료 후 복귀
- 종료: go_hub CHOICE 시 NODE_ENDED

### 6.4 HUB 노드

- CHOICE only — LOCATION 이동 시 NODE_ENDED, Heat 해결은 ONGOING 유지

---

## 7. LLM Worker — 비동기 내러티브 파이프라인

### 7.1 상태 머신 (turns.llm_status)

```
SKIPPED (전투 중 턴 — skipLlm: true)
PENDING → RUNNING → DONE (정상)
PENDING → RUNNING → FAILED (실패)
RUNNING → PENDING (워커 크래시 복구, lock_timeout 30~60초)
```

### 7.2 Worker 동작

- **큐**: DB 폴링 (v1) — `llm_status=PENDING` 선택 + 락 획득
- **처리**: 컨텍스트(L0-L4) 생성 → 모델 호출(타임아웃 3~8초) → 결과 저장
- **재시도**: primary 2회 → fallback 1회 → FAILED

### 7.3 LLM 컨텍스트 (L0-L4)

| Layer | 내용 | 비고 |
|-------|------|------|
| L0 | theme memory | 불변 — 삭제 금지 |
| L1 | storySummary | 런 전체 스토리 요약 |
| L2 | nodeFacts | 현재/직전 노드 merge |
| L3 | recent summaries | 최근 턴 요약 |
| L4 | events + summary.short | 이번 턴 확정 사실 |

diff(수치)는 LLM에 전달하지 않는다. LOCATION 턴에는 ActionContext(parsedType, originalInput, tone, escalated, insistenceCount)를 추가 전달.

### 7.4 서술 가드레일

- **금지**: 판정/드랍 결과 변경, 서버에 없는 선택지 생성, 수치 과다 노출
- **권장**: toneHint 반영, bonusSlot 힌트, ACTION 서술 3단계(원문 시도 → 방향 전환 이유 → 결과)

---

## 8. 클라이언트 상태 — Phase 체계 · 메시지 표시

### 8.1 Phase 상태 머신

```
TITLE → LOADING → HUB → LOCATION ⇄ COMBAT → HUB (순환)
                   ↕         ↕
                 ERROR    RUN_ENDED
```

`derivePhase(nodeType)`: HUB | LOCATION | COMBAT → 해당 Phase

| Phase | 주요 UI | 입력 |
|-------|---------|------|
| HUB | HubScreen (LOCATION 카드 + HeatGauge + TimePhase) | CHOICE |
| LOCATION | NarrativePanel + InputSection + LocationHeader | ACTION + CHOICE |
| COMBAT | BattlePanel + NarrativePanel | ACTION + CHOICE |

### 8.2 메시지 표시 순서

```
1. SYSTEM 메시지 → 즉시 표시
2. RESOLVE 인라인 → 주사위 결과 (LOCATION)
3. NARRATOR → LLM 로딩 애니메이션 → 완료 시 텍스트 교체
4. pending flush → 나머지 messages + CHOICE (narrator 완료 후)
```

### 8.3 LLM 폴링

- 2초 간격, 최대 15회 (30초)
- DONE → `llm.output` narrator 반영 + pending flush
- FAILED / 횟수 초과 → `summary.short` fallback
- 전투 LLM 스킵 시: BATTLE/DAMAGE/MOVE/STATUS를 SYSTEM 메시지로 직접 표시, NARRATOR 생략

### 8.4 이벤트 필터링

- 기본: `SYSTEM`, `LOOT`, `GOLD` kind만 유저 표시
- 전투 LLM 스킵 시: `BATTLE`, `DAMAGE`, `MOVE`, `STATUS`도 표시

---

## 9. 구현 상태 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| HUB 턴 처리 | ✅ 구현 | LOCATION 선택 + Heat 해결 |
| LOCATION Action-First | ✅ 구현 | IntentParserV2 → EventMatcher → Resolve |
| COMBAT 전투 엔진 | ✅ 구현 | Rule Parser → Policy → NodeResolver |
| 고집 에스컬레이션 | ✅ 구현 | 3회 연속 억제 → 자동 승격 |
| LLM Worker | ✅ 구현 | DB 폴링, 2초 간격 |
| LLM 재시도 | ✅ 구현 | POST retry-llm → FAILED→PENDING 리셋, Worker 자동 재처리 |
| 전투 LLM 스킵 | ✅ 구현 | skipLlm → 1-2초 응답 |
| Auth 시스템 | ✅ 구현 | `server/src/auth/` — 회원가입/로그인 + JWT |
| NPC Injection + peakMode | ✅ 구현 | TurnOrchestrationService (pressure 기반) |
| NPC Emotional + Posture | ✅ 구현 | NpcEmotionalService (5축 감정 모델) |
| NPC Introduction | ✅ 구현 | shouldIntroduce + getNpcDisplayName |
| Narrative Engine v1 | ✅ 구현 | Incident/Signal/Operation/NarrativeMark/Ending (6 서비스) |
| Structured Memory v2 | ✅ 구현 | MemoryCollector + MemoryIntegration |
| LLM 보조 파싱 | ⚠️ 제한적 | LlmIntentParser 존재, IntentParserV2 우선 |
| Downed 시스템 | ❌ 미구현 | 현재 DEFEAT → 즉시 RUN_ENDED |
| SSE/WebSocket | ❌ 미구현 | 폴링으로 대체 |
| EVENT/REST/SHOP/EXIT | 비활성 | HUB 엔진으로 대체 |
