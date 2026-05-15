# 14. User-Driven System Implementation Bridge

## 문서 목적

이 문서는 아래 두 축을 연결한다.

1. **이미 작성된 유저 주도형 설계 초안**
   - ParsedIntent v3
   - Incident 재정의
   - IncidentRouter
   - World Delta / Off-screen Tick
   - PlayerThread
   - Ending Input 재설계
2. **현재 graymar-server / graymar-client 실제 코드 구조**

이 문서는 구현 정답 코드가 아니라 **Claude Code가 그대로 따라가며 작업할 수 있는 구현 브리지 문서**다.

핵심 원칙은 단순하다.

- 기존 시스템을 한 번에 갈아엎지 않는다.
- `V2 → V3` 병행 레이어를 둔다.
- `EventMatcher`를 즉시 삭제하지 않고 `IncidentRouter`를 먼저 얹는다.
- 클라이언트 응답 계약을 깨지 않는다.
- 현재 Narrative Engine v1을 유지한 채, 유저 주도형 시스템을 **점진 확장**한다.

---

# 1. 현재 코드 기준 실제 구조 요약

## 1.1 서버의 실제 LOCATION 턴 파이프라인

현재 LOCATION 턴은 사실상 아래 흐름으로 고정되어 있다.

```text
turns.service.ts / handleLocationTurn
→ llmIntentParser.parseWithInsistence()
→ eventMatcher.match()
→ resolveService.resolve()
→ world state / relation / reputation / flags 반영
→ worldTick.preStepTick()
→ incidentManagement.findRelevantIncident() / applyImpact()
→ worldTick.postStepTick()
→ npc emotional 업데이트
→ orchestration.orchestrate()
→ result.ui 조립
→ orchestration.offscreenTick()
→ endingGenerator.checkEndingConditions()
→ commitTurnRecord()
→ 필요 시 endingGenerator.generateEnding()
```

즉 현재 엔진은 이미 단일 진입점이 분명하다.

### 실제 핵심 파일

- `graymar-server-main/src/turns/turns.service.ts`
- `graymar-server-main/src/engine/hub/llm-intent-parser.service.ts`
- `graymar-server-main/src/engine/hub/intent-parser-v2.service.ts`
- `graymar-server-main/src/engine/hub/event-matcher.service.ts`
- `graymar-server-main/src/engine/hub/resolve.service.ts`
- `graymar-server-main/src/engine/hub/world-tick.service.ts`
- `graymar-server-main/src/engine/hub/incident-management.service.ts`
- `graymar-server-main/src/engine/hub/turn-orchestration.service.ts`
- `graymar-server-main/src/engine/hub/ending-generator.service.ts`

## 1.2 현재 서버 타입 구조

현재 서버 타입은 이미 Narrative Engine v1 기준으로 정리되어 있다.

### 이미 존재하는 타입 축

- `ParsedIntentV2`
- `IncidentRuntime`
- `WorldState.activeIncidents`
- `WorldState.signalFeed`
- `WorldState.operationSession`
- `EndingInput`, `EndingResult`
- `ServerResultV1.ui.activeIncidents`
- `ServerResultV1.ui.signalFeed`
- `ServerResultV1.ui.npcEmotional`

즉 완전히 빈 상태가 아니라, **새 설계가 꽂힐 뼈대는 이미 존재**한다.

## 1.3 클라이언트의 실제 의존 구조

클라이언트는 아래 계약을 기대한다.

### 상태 저장소

- `graymar-client-main/src/store/game-store.ts`

### 공용 타입

- `graymar-client-main/src/types/game.ts`

### 실제 화면 소비 지점

- `components/hub/HubScreen.tsx`
- `components/hub/IncidentTracker.tsx`
- `components/hub/SignalFeedPanel.tsx`
- `components/hub/ResolveOutcomeBanner.tsx`
- `components/input/InputSection.tsx`
- `components/screens/EndingScreen.tsx`

현재 클라이언트는 서버 결과를 그대로 읽고 있으며, 특히 아래 UI 필드를 사용한다.

- `ui.worldState`
- `ui.resolveOutcome`
- `ui.resolveBreakdown`
- `ui.signalFeed`
- `ui.activeIncidents`
- `ui.npcEmotional`
- `ui.operationProgress`
- `events[].data.endingResult`

따라서 서버 변경 시 **기존 UI 계약을 유지하거나, 확장만 해야 한다.**

---

# 2. 설계 초안과 현재 코드의 차이

## 2.1 ParsedIntent

### 현재
- `ParsedIntentV2`
- 핵심 축: `actionType`, `secondaryActionType`, `tone`, `target`, `riskLevel`, `source`, `confidence`
- 실제 파서 진입점은 `LlmIntentParserService.parseWithInsistence()`

### 목표
- `ParsedIntentV3`
- 핵심 축: `primaryActionType`, `secondaryActionType`, `goalCategory`, `goalText`, `approachVector`, `secondaryApproachVector`, `riskLevel`, `source`, `intentTags`

### 갭
현재 파이프라인은 **행동 유형 중심**이다. 유저 주도형 확장에서는 **목표와 접근 방식 중심**이어야 한다.

## 2.2 Incident

### 현재
- `IncidentRuntime` = `stage:number`, `control:number`, `pressure:number`, `deadlineClock:number`, `resolved:boolean`, `outcome`
- `IncidentDef`의 `stages[]`와 `affordances[]`를 통해 단계별 처리

### 목표
- incident를 “이벤트 결과를 먹는 객체”에서 “여러 벡터로 흔들 수 있는 문제 공간”으로 확장
- `vector state`, `suspicion`, `security`, `playerProgress`, `rivalProgress`, `mutationFlags` 추가 필요

### 갭
현재 incident는 **진행형 사건**이지만, 아직 **approachVector 중심 구조가 없음**.

## 2.3 EventMatcher / IncidentRouter

### 현재
- `EventMatcherService.match()`가 이벤트를 고른다.
- 필터 순서: location → conditions → gates → affordances → heat 간섭 → agenda weight

### 목표
- `IncidentRouter`가 “입력이 어느 incident에 어떤 방식으로 먹히는지”를 평가
- 그 뒤 event/scene을 고르거나 fallback scene을 생성

### 갭
현재는 **event 중심**, 목표 구조는 **incident 중심**이다.

## 2.4 WorldTick / WorldDelta

### 현재
- `WorldTickService.preStepTick()` / `postStepTick()` 존재
- `TurnOrchestrationService.offscreenTick()`도 존재
- 그러나 플레이어에게 보여주는 delta summary는 없다.

### 목표
- 내부 tick 결과를 `WorldDelta`로 명시 저장
- 필요 시 `WorldDeltaSummary`로 UI/LLM에 전달

### 갭
현재도 tick은 돌지만, **가시화된 세계 변화 구조**가 없다.

## 2.5 Ending

### 현재
- `EndingGeneratorService.gatherEndingInputs()` / `generateEnding()` 존재
- 입력 축은 incident outcome, npc epilogue, heat, tension, reputation, narrative marks 중심

### 목표
- dominant vector, player thread, city state signature, relation footprint, consequence footprint까지 읽는 구조

### 갭
현재 엔딩은 Narrative Engine v1 수준으로 충분하지만, **플레이 방식의 누적 흔적**을 읽기엔 부족하다.

---

# 3. 구현 전략 원칙

## 3.1 절대 하지 말아야 할 것

1. `ParsedIntentV2`를 바로 삭제하지 말 것
2. `EventMatcherService`를 바로 삭제하지 말 것
3. `IncidentRuntime`를 한 번에 전면 교체하지 말 것
4. 클라이언트 `ServerResultV1` 계약을 깨지 말 것
5. `turns.service.ts`의 LOCATION 전체 흐름을 한 번에 리라이트하지 말 것

## 3.2 반드시 지켜야 할 것

1. **어댑터 레이어 추가** 방식으로 진행
2. 신규 타입은 `V3`, `V2_5`, `Extended` 같은 병행 버전으로 추가
3. 기존 UI는 그대로 동작해야 함
4. 신규 필드는 서버에서 `ui` 확장 필드로 먼저 공급
5. 완전 교체 전에 최소 1단계 병행 운영 구간을 둘 것

---

# 4. 구현 우선순위

구현은 아래 5단계로 끊어서 진행한다.

## Phase 1. Intent 확장 레이어
## Phase 2. Incident 확장 레이어
## Phase 3. IncidentRouter 도입
## Phase 4. WorldDelta / PlayerThread 도입
## Phase 5. Ending 확장

이 순서를 바꾸지 않는 것이 좋다.

---

# 5. Phase 1 — ParsedIntent v3 도입

## 5.1 목표

현재 `ParsedIntentV2`를 유지하면서, LOCATION 턴에서만 사용할 수 있는 `ParsedIntentV3`를 병행 도입한다.

## 5.2 새 파일 추가

### 서버 타입
- `src/db/types/parsed-intent-v3.ts`

### 서버 서비스
- `src/engine/hub/intent-v3-builder.service.ts`

## 5.3 권장 타입 정의

```ts
export type ApproachVector =
  | 'SOCIAL'
  | 'STEALTH'
  | 'PRESSURE'
  | 'ECONOMIC'
  | 'OBSERVATIONAL'
  | 'POLITICAL'
  | 'LOGISTICAL'
  | 'VIOLENT';

export type IntentGoalCategory =
  | 'GET_INFO'
  | 'GAIN_ACCESS'
  | 'SHIFT_RELATION'
  | 'ACQUIRE_RESOURCE'
  | 'BLOCK_RIVAL'
  | 'CREATE_DISTRACTION'
  | 'HIDE_TRACE'
  | 'ESCALATE_CONFLICT'
  | 'DEESCALATE_CONFLICT'
  | 'TEST_REACTION';

export type ParsedIntentV3 = {
  version: 3;
  rawInput: string;
  primaryActionType: string;
  secondaryActionType?: string | null;
  tone: string;
  targetText?: string | null;
  goalCategory: IntentGoalCategory;
  goalText: string;
  approachVector: ApproachVector;
  secondaryApproachVector?: ApproachVector | null;
  riskLevel: 1 | 2 | 3;
  confidence: 0 | 1 | 2 | 3;
  source: 'LLM' | 'RULE' | 'CHOICE' | 'HYBRID';
  intentTags: string[];
  suppressedActionType?: string | null;
  escalated?: boolean;
};
```

## 5.4 구현 방식

`IntentV3BuilderService`는 **기존 `ParsedIntentV2` 결과를 받아 확장**한다.

### 금지
- LLM을 새로 하나 더 추가해서 비용을 늘리는 방식

### 권장
- 현재 `LlmIntentParserService` 결과를 이용
- 우선은 rule-based enrichment로 V3 생성
- 나중에 intent LLM JSON 응답에 `goalCategory`, `goalText`, `approachVector`를 추가

## 5.5 초기 구현 규칙

초기에는 아래처럼 단순 매핑으로 시작한다.

```text
BRIBE      -> ECONOMIC / GET_INFO or GAIN_ACCESS
PERSUADE   -> SOCIAL   / SHIFT_RELATION or GAIN_ACCESS
TALK       -> SOCIAL   / GET_INFO
OBSERVE    -> OBSERVATIONAL / GET_INFO
INVESTIGATE-> OBSERVATIONAL / GET_INFO
SNEAK      -> STEALTH  / GAIN_ACCESS or HIDE_TRACE
THREATEN   -> PRESSURE / SHIFT_RELATION or ESCALATE_CONFLICT
FIGHT      -> VIOLENT  / ESCALATE_CONFLICT
TRADE      -> ECONOMIC / ACQUIRE_RESOURCE
```

`goalText`는 초기에 짧은 rule 기반 문장으로 생성해도 충분하다.

예:
- target이 있으면: `"${target} 관련 정보 확보"`
- target이 없으면: `"현재 상황에 대한 정보 확보"`

## 5.6 turns.service.ts 반영 지점

LOCATION 턴에서 기존 코드:

```ts
const intent = await this.llmIntentParser.parseWithInsistence(...)
```

이후 바로 아래에 추가한다.

```ts
const intentV3 = this.intentV3Builder.build(intent, rawInput, locationId, choicePayload)
```

### 이 단계에서 하지 않는 것
- resolve/이벤트 선택 로직 교체 금지

### 이 단계에서 하는 것
- `result.ui.actionContext` 또는 `turn.transformedIntent` 쪽에 v3를 추가 저장
- 디버그 로그로 v2/v3를 같이 남김

## 5.7 완료 조건

- 기존 게임 진행이 그대로 된다.
- LOCATION ACTION/CHOICE에서 `ParsedIntentV3`가 생성된다.
- DB turn record 또는 로그에서 v3 확인 가능하다.

---

# 6. Phase 2 — Incident 확장 레이어

## 6.1 목표

기존 `IncidentRuntime`를 깨지 않고, incident별 vector / suspicion / security / progress 정보를 확장한다.

## 6.2 새 타입 추가

### 권장 파일
- `src/db/types/incident-extended.ts`

```ts
export type IncidentVectorState = {
  vector: string;
  enabled: boolean;
  preferred: boolean;
  friction: number;
  effectivenessBase: number;
  failForwardMode:
    | 'HEAT'
    | 'SUSPICION'
    | 'RIVAL_PROGRESS'
    | 'LOCKOUT'
    | 'ESCALATION'
    | 'MIXED';
};

export type IncidentRuntimeExtended = IncidentRuntime & {
  suspicion?: number;
  security?: number;
  playerProgress?: number;
  rivalProgress?: number;
  vectors?: IncidentVectorState[];
  mutationFlags?: string[];
  lockReasons?: string[];
};
```

## 6.3 현재 코드와의 연결 방식

현재 `WorldState.activeIncidents`는 `IncidentRuntime[]`다.

초기 단계에서는 타입을 즉시 바꾸지 말고, **런타임 데이터만 확장 필드 허용** 방식으로 처리한다.

즉 실제 저장은 이렇게 해도 된다.

```ts
activeIncidents: Array<IncidentRuntime & {
  suspicion?: number;
  security?: number;
  playerProgress?: number;
  rivalProgress?: number;
  vectors?: IncidentVectorState[];
}>
```

## 6.4 수정 대상

- `src/db/types/incident.ts`
- `src/db/types/world-state.ts`
- `src/engine/hub/incident-management.service.ts`
- `src/engine/hub/world-tick.service.ts`

## 6.5 초기값 규칙

Incident spawn 시 아래 기본값을 넣는다.

- `suspicion = 0`
- `security = location security 기반 기본값`
- `playerProgress = control과 동일값 또는 0`
- `rivalProgress = pressure 기반 보정값 또는 0`
- `vectors = incident kind/location/tag 기반 기본 벡터 셋`

## 6.6 주의

현재 `IncidentSummaryUI`는 숫자형 `stage`, `control`, `pressure`, `deadlineClock`, `resolved`만 사용한다.

따라서 초기 단계에서는 **UI 요약형은 그대로 유지**하고, 확장 incident 필드는 서버 내부에서만 먼저 사용한다.

## 6.7 완료 조건

- 기존 incident UI는 깨지지 않는다.
- 신규 incident는 내부적으로 vector 상태를 가진다.
- spawn / tick / impact 이후 확장 필드가 유지된다.

---

# 7. Phase 3 — EventMatcher 옆에 IncidentRouter 추가

## 7.1 목표

기존 `EventMatcherService.match()`를 바로 없애지 않고, 그 앞단에 `IncidentRouterService`를 둔다.

## 7.2 새 파일 추가

- `src/engine/hub/incident-router.service.ts`

## 7.3 역할

`IncidentRouterService`는 아래만 책임진다.

1. 현재 location의 active incident 후보 수집
2. `ParsedIntentV3`와 incident의 연관도 계산
3. 가장 적절한 incident 선택
4. 해당 incident에 맞는 `routeMode`, `matchedVector`, `friction`, `effectivenessBase` 계산

즉 **scene/event를 직접 고르는 서비스가 아니다.**

## 7.4 권장 반환 타입

```ts
export type IncidentRoutingResult = {
  incidentId: string | null;
  matchedVector: string | null;
  routeMode: 'DIRECT' | 'REROUTED' | 'FALLBACK_SCENE';
  effectivenessBase: number;
  friction: number;
  failForwardMode:
    | 'HEAT'
    | 'SUSPICION'
    | 'RIVAL_PROGRESS'
    | 'LOCKOUT'
    | 'ESCALATION'
    | 'MIXED';
  notes: string[];
};
```

## 7.5 turns.service.ts 반영 위치

현재 위치:

```ts
const intent = ...
...
matchedEvent = this.eventMatcher.match(...)
```

새 흐름:

```ts
const intent = ...
const intentV3 = ...
const routing = this.incidentRouter.route(ws, locationId, intentV3)
matchedEvent = this.eventMatcher.matchWithIncidentContext(...)
```

## 7.6 구현 방식

### 1단계
`IncidentRouter`는 결과만 만들고, `EventMatcher`는 기존대로 둔다.

### 2단계
`EventMatcher`에 아래 시그니처를 추가한다.

```ts
matchWithIncidentContext(
  events,
  locationId,
  intent,
  ws,
  arcState,
  agenda,
  cooldowns,
  currentTurnNo,
  rng,
  recentEventIds,
  routingResult,
)
```

### 3단계
라우팅 결과가 있으면 아래 우선순위를 적용한다.

- 라우팅된 incident와 관련된 tags / npc / location affinity 높은 event 우선
- matchedVector와 affordance가 맞는 event 우선
- 없으면 기존 `match()` fallback

## 7.7 중요한 점

`EventMatcherService`를 `IncidentRouter`로 대체하는 것이 아니라,

- `IncidentRouter` = 사건 연결 판단
- `EventMatcher` = 구체 장면/이벤트 선택

으로 역할을 분리한다.

## 7.8 완료 조건

- 기존 이벤트 선택 실패율이 높아지지 않는다.
- 자유 입력이 incident와 연결되는 비율이 올라간다.
- 로그에서 `routingResult` 확인 가능하다.

---

# 8. Phase 4 — Resolve 후처리 + WorldDelta + PlayerThread

## 8.1 목표

기존 `ResolveService.resolve()` 결과를 incident/world/thread에 반영하는 후처리 계층을 만든다.

## 8.2 새 파일 추가

- `src/db/types/world-delta.ts`
- `src/db/types/player-thread.ts`
- `src/engine/hub/world-delta.service.ts`
- `src/engine/hub/player-thread.service.ts`
- 선택: `src/engine/hub/incident-resolution-bridge.service.ts`

## 8.3 권장 구조

### WorldDelta

```ts
export type WorldDelta = {
  tickNo: number;
  cause: 'PLAYER_ACTION' | 'TIME_PASSAGE' | 'HUB_RETURN' | 'RIVAL_MOVE' | 'THREAD_TRIGGER';
  incidentDeltas: Array<{
    incidentId: string;
    oldStage: number;
    newStage: number;
    playerProgressDelta: number;
    rivalProgressDelta: number;
    pressureDelta: number;
    suspicionDelta: number;
    securityDelta: number;
    publicSignals: string[];
  }>;
  startedThreads: string[];
  spawnedSignals: string[];
  endingMarksAdded: string[];
};
```

### PlayerThread

```ts
export type PlayerThread = {
  id: string;
  title: string;
  seedType: 'RUMOR' | 'RELATION' | 'BLACKMAIL' | 'ALLIANCE' | 'SUSPICION' | 'LEVERAGE' | 'DEBT' | 'HOSTILITY';
  status: 'SEED' | 'GROWING' | 'ACTIVE' | 'EXPLOITED' | 'COLLAPSED' | 'ARCHIVED';
  originTurnNo: number;
  locationId?: string | null;
  relatedNpcIds: string[];
  relatedFactionIds: string[];
  relatedIncidentIds: string[];
  progress: number;
  heat: number;
  leverage: number;
  fragility: number;
  sourceSummary: string;
  triggerTags: string[];
  payoffModes: string[];
};
```

## 8.4 현재 코드에 꽂는 위치

현재 LOCATION 턴 중 아래 사이에 넣는다.

```text
resolveService.resolve()
→ incidentManagement.applyImpact()
→ worldTick.postStepTick()
```

권장 변경:

```text
resolveService.resolve()
→ incidentResolutionBridge.apply(...)
→ worldDeltaService.build(...)
→ playerThreadService.update(...)
→ worldTick.postStepTick()
```

## 8.5 incidentResolutionBridge의 책임

- `resolveResult.outcome`
- `routingResult`
- `intentV3`
- `matchedEvent`
- `relevantIncident`

이 다섯 개를 받아서,

- incident의 `playerProgress`, `rivalProgress`, `suspicion`, `security`, `vectors` 수정
- failForwardMode 처리
- delta 계산

을 담당한다.

즉 지금 `IncidentManagementService.applyImpact()`가 하는 일을 대체하지 말고, **확장 후처리**로 둔다.

## 8.6 실제 저장 위치

초기에는 `RunState`에 아래 필드를 추가하면 충분하다.

```ts
worldDeltas?: WorldDelta[];
playerThreads?: PlayerThread[];
```

### 주의
- 처음부터 별도 테이블로 빼지 않아도 된다.
- runState JSON 누적만으로도 1차 구현 가능하다.
- 이후 용량 이슈가 생기면 분리한다.

## 8.7 UI 반영 방식

초기에는 클라이언트 전체 개편을 하지 않는다.

대신 `result.ui`에 선택적 확장 필드만 추가한다.

```ts
ui.worldDeltaSummary?: {
  headline: string;
  visibleChanges: string[];
  urgency: 'LOW' | 'MID' | 'HIGH';
}
ui.playerThreads?: Array<{
  threadId: string;
  title: string;
  status: string;
  leverage: number;
}>
```

클라이언트는 이 단계에서 **표시하지 않아도 된다.** 우선 서버와 스토어까지만 반영해도 충분하다.

## 8.8 완료 조건

- 실패가 incident/world state에 누적된다.
- 동일 incident에 대한 반복 개입이 player thread로 승격될 수 있다.
- world delta가 runState에 저장된다.

---

# 9. Phase 5 — Ending 확장

## 9.1 목표

현재 `EndingGeneratorService`를 유지하면서 입력을 확장한다.

## 9.2 수정 대상

- `src/db/types/ending.ts`
- `src/engine/hub/ending-generator.service.ts`

## 9.3 확장 입력

현재 `gatherEndingInputs()`는 아래 축을 모은다.

- incident outcomes
- npc epilogues
- narrative marks
- global heat / tension / reputation / days / arc state

여기에 추가한다.

```ts
dominantVectors
playerThreads
cityStateSignature
relationFootprint
consequenceFootprint
```

## 9.4 구현 방식

처음부터 엔딩 문장 전체를 바꾸지 말고,

1. 입력 수집 확장
2. statistics / metadata 확장
3. closingLine / epilogue 규칙 보정

순으로 간다.

## 9.5 예시 규칙

- `dominantVectors`가 `VIOLENT` / `PRESSURE` 편중이면 closingLine을 더 거칠게 조정
- `playerThreads` 성공이 많으면 “공식 경로 밖 흔적” 계열 narrative mark 추가
- `consequenceFootprint.rivalWins`가 높으면 city stability 불이익

## 9.6 클라이언트 영향

`EndingScreen.tsx`는 현재도 `endingResult` 기반이다.

따라서 기존 필드는 유지하고, 아래 추가 필드만 optional로 넣는다.

- `playstyleSummary?: string`
- `dominantVectors?: Array<{ vector: string; weight: number }>`
- `threadSummary?: string[]`

기존 화면은 optional 필드를 무시해도 동작한다.

---

# 10. 서버 파일별 작업 지시서

## 10.1 `src/turns/turns.service.ts`

### 해야 할 일
- LOCATION 턴에서 `intentV3` 생성 추가
- `IncidentRouter` 호출 추가
- `incidentResolutionBridge` 호출 추가
- `worldDeltaService` / `playerThreadService` 호출 추가
- `result.ui`에 선택적 확장 필드 추가

### 하지 말 것
- HUB / COMBAT 흐름 건드리지 말 것
- `handleHubTurn()` / `handleCombatTurn()` 대규모 수정 금지

## 10.2 `src/engine/hub/llm-intent-parser.service.ts`

### 해야 할 일
- 초기엔 그대로 사용
- 2차에서 intent JSON 응답에 `goalCategory`, `goalText`, `approachVector` 추가 가능

### 하지 말 것
- 메인 narrative LLM과 intent LLM을 합치지 말 것

## 10.3 `src/engine/hub/event-matcher.service.ts`

### 해야 할 일
- 기존 `match()` 유지
- `matchWithIncidentContext()` 또는 내부 optional arg 추가
- routingResult 기반 가중치 보정 추가

### 하지 말 것
- 기존 6단계 필터 제거 금지

## 10.4 `src/engine/hub/resolve.service.ts`

### 해야 할 일
- 기존 시그니처 최대한 유지
- 필요하면 `resolveExtended()` 추가
- routing friction / effectivenessBase를 보정값으로 넣을 수 있게 준비

### 하지 말 것
- 판정 기준을 한 번에 전면 교체하지 말 것

## 10.5 `src/engine/hub/incident-management.service.ts`

### 해야 할 일
- incident 확장 필드 초기화 로직 추가
- vector state seed 생성
- stage 변화와 extended field 동기화

## 10.6 `src/engine/hub/world-tick.service.ts`

### 해야 할 일
- `WorldDelta` 재료 생성
- off-screen rival progress / vector lock / signal spawn 보강

### 하지 말 것
- 기존 pre/post tick 분리 구조를 없애지 말 것

## 10.7 `src/engine/hub/ending-generator.service.ts`

### 해야 할 일
- `gatherEndingInputs()` 확장
- `generateEnding()`에 dominant vector / thread / consequence 반영

---

# 11. 클라이언트 파일별 작업 지시서

## 11.1 `src/types/game.ts`

### 해야 할 일
아래 optional 타입만 추가한다.

```ts
export interface WorldDeltaSummaryUI {
  headline: string;
  visibleChanges: string[];
  urgency: 'LOW' | 'MID' | 'HIGH';
}

export interface PlayerThreadSummaryUI {
  threadId: string;
  title: string;
  status: string;
  leverage: number;
}
```

그리고 `ServerResultV1.ui` 확장 필드로 optional 추가.

## 11.2 `src/store/game-store.ts`

### 해야 할 일
- `result.ui.worldDeltaSummary`
- `result.ui.playerThreads`

를 optional로 store에 반영

### 주의
- 기존 화면에 바로 꽂지 않아도 된다.
- 우선 상태만 저장해도 충분하다.

## 11.3 `components/hub/*`

### 1차 단계
UI 변경 없이 유지

### 2차 단계
다음 패널 추가 가능
- `WorldDeltaPanel`
- `PlayerThreadPanel`

하지만 이건 서버 안정화 후에 한다.

---

# 12. Claude Code용 실제 작업 순서

아래 순서를 그대로 따르는 것이 좋다.

## Step 1
`ParsedIntentV3` 타입과 `IntentV3BuilderService` 추가

## Step 2
`turns.service.ts` LOCATION 파이프라인에 `intentV3` 생성 연결

## Step 3
`IncidentRuntimeExtended` 확장 필드 도입

## Step 4
incident spawn / tick 시 extended field 유지되도록 수정

## Step 5
`IncidentRouterService` 추가

## Step 6
`EventMatcherService`에 incident context optional 인자 추가

## Step 7
`turns.service.ts`에서 `routingResult` 생성 후 이벤트 선택에 전달

## Step 8
`WorldDelta` / `PlayerThread` 타입과 서비스 추가

## Step 9
`incidentResolutionBridge` 추가 후 resolve 이후 적용

## Step 10
`EndingInput` 확장 및 `EndingGeneratorService` 반영

## Step 11
클라이언트 타입/store optional 필드 확장

## Step 12
필요 시 허브 UI 패널 추가

---

# 13. PR 단위 권장 분리

## PR 1
Intent V3 추가

- 타입 추가
- builder 추가
- turns.service 연결
- 로그/저장 반영

## PR 2
Incident 확장 + Router 추가

- incident extended 필드
- router 추가
- event matcher 가중치 보정

## PR 3
WorldDelta + PlayerThread

- 타입/서비스 추가
- runState 저장
- result.ui optional 확장

## PR 4
Ending 확장

- ending input 확장
- ending result optional 확장

## PR 5
Client optional UI 반영

- types/store 확장
- 패널 추가는 선택

---

# 14. 테스트 체크리스트

## Intent
- ACTION 입력 시 V2와 V3가 둘 다 생성되는가
- CHOICE 입력에서도 V3가 생성되는가
- 기존 전투/허브 흐름이 깨지지 않는가

## Incident Router
- 같은 목표를 SOCIAL/STEALTH/ECONOMIC으로 넣었을 때 routing 결과가 달라지는가
- incident 없는 입력이 fallback scene으로 안전하게 처리되는가

## WorldDelta
- 실패 시 rivalProgress / suspicion / security가 누적되는가
- 허브 복귀 시 visibleChanges가 생성되는가

## PlayerThread
- 동일 npc/incident 주변 반복 행동 시 thread가 생성되는가
- heat 높을 때 thread가 collapse 가능한가

## Ending
- dominant vector에 따라 결과 summary가 달라지는가
- thread / consequence footprint가 ending input에 반영되는가

---

# 15. 최종 구현 판단 기준

이 문서 기준 구현이 성공한 상태는 아래다.

1. 현재 게임은 그대로 플레이 가능하다.
2. LOCATION 입력에 대해 `ParsedIntentV3`가 생성된다.
3. 입력이 단순 event가 아니라 incident에 연결된다.
4. 실패가 world delta로 남는다.
5. 플레이어가 만든 반복 흔적이 thread로 축적된다.
6. 엔딩이 플레이 방식의 흔적을 더 많이 읽는다.
7. 클라이언트 기존 허브/전투/엔딩 화면은 깨지지 않는다.

---

# 16. Claude Code에 전달할 한 줄 요약

> 현재 graymar 코드베이스는 `turns.service.ts`의 LOCATION 턴 파이프라인을 중심으로 `ParsedIntentV3 → IncidentRouter → Incident extended state → WorldDelta → PlayerThread → EndingInput extended`를 **점진 병행 방식**으로 도입해야 한다. 기존 `ParsedIntentV2`, `EventMatcher`, `IncidentRuntime`, `ServerResultV1` 계약은 유지하고, 신규 로직은 어댑터/확장 레이어로 추가하라.

