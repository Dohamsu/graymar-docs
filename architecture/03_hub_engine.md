# 03. HUB 탐험 엔진 설계

> 통합 정본. 원본: `HUB_Exploration_RPG_Architecture_v1.md`, `Action_First_Architecture_v2.md`, `HUB_RPG_Engine_Spec_v2.md`
> 구현 코드: `server/src/engine/hub/*.service.ts`
> 마지막 갱신: 2026-03-17 (서비스 목록 29개, 5 서브시스템 반영)

---

## 1. 설계 철학 & 게임 루프

**정체성** --- 허브를 중심으로 탐험하다가, 조건이 모이면 메인 줄기가 열리는 인터랙티브 스토리 RPG.

- 스토리 70~80%, 전투 20~30%
- 서버가 수치/결과를 확정, LLM은 서술 전용
- 선형 로그라이크가 아닌 **HUB 중심 순환 구조**

```
RUN 시작 → HUB → LOCATION 선택 → Scene Shell
  → 플레이어 행동 선언(텍스트/선택지)
  → Intent Parse → EventMatcher → Resolve
  → 후폭풍/Deferred 처리 → HUB 복귀(Heat 감쇠)
  → (조건 충족 시 Arc 선택지 노출) → 반복
```

**핵심 원칙**:
- **Action-First**: 이벤트가 먼저가 아니라, 플레이어가 먼저 행동 → 세계가 반응
- 이벤트 = 플레이어 행동에 대한 지원/방해 레이어
- 선택지는 가이드일 뿐, 자유 텍스트가 상위

---

## 2. WorldState

```typescript
type WorldState = {
  currentLocationId: string | null;   // null = HUB
  timePhase: 'DAY' | 'NIGHT';        // legacy (2상)
  timePhaseV2: 'DAWN' | 'DAY' | 'DUSK' | 'NIGHT';  // 4상 시간 사이클
  timeCounter: number;                // legacy 5턴 전환용
  globalClock: number;                // 4상 tick 카운터
  day: number;                        // 현재 날짜
  hubHeat: number;                    // 0~100
  hubSafety: 'SAFE' | 'ALERT' | 'DANGER';
  hubHeatReasons: string[];
  tension: number;                    // 0~10
  mainArc: MainArcProgress;
  mainArcClock: MainArcClock;         // 데드라인 (Narrative v1)
  reputation: Record<string, number>; // factionId → 평판 (±)
  flags: Record<string, boolean>;
  deferredEffects: DeferredEffect[];
  combatWindowCount: number;
  combatWindowStart: number;
  activeIncidents: IncidentRuntime[]; // Narrative v1: 활성 사건 (max 3)
  signalFeed: SignalFeedItem[];       // Narrative v1: 시그널 피드 (max 20)
  narrativeMarks: NarrativeMark[];    // Narrative v1: 불가역 표식 (12종)
};
```

### 2-1. Heat 시스템

| Heat 구간 | Safety    |
|-----------|-----------|
| 0~39      | SAFE      |
| 40~69     | ALERT     |
| 70~100    | DANGER    |

**Heat 증가 요인**: NIGHT 활동(+3), 전투 트리거(+5), Arc 급진전(+3~5), FIGHT/THREATEN(+2), FAIL+BLOCK(+5)
**Heat 감쇠**: HUB 복귀 시 -5 자동 감쇠
**불변**: 턴당 Heat 변동 ±8 클램프

**Heat 해결**:

| 방식 | 메커니즘 |
|------|---------|
| CONTACT_ALLY | NPC 관계 tier 기반 감소. Tier 0~4 = -5/-8/-10/-13/-16 |
| PAY_COST | cost = 50 + heat*2 + usageCount*25. 고정 -15 감소 |

관계 tier: 0~19=T0, 20~39=T1, 40~59=T2, 60~79=T3, 80~100=T4

### 2-2. 시간 시스템

**4상 시간 사이클** (Narrative Engine v1, `WorldTickService`):
- DAWN(2 tick) → DAY(4 tick) → DUSK(2 tick) → NIGHT(4 tick) = 12 tick/day
- `preStepTick()` / `postStepTick()`으로 LOCATION 턴 전후 tick 진행
- 이벤트 분기 및 Heat 계산에 활용 (NIGHT → Heat +3 보너스)
- Legacy: `timePhase` (DAY/NIGHT) 5턴 전환은 하위 호환용으로 유지

### 2-3. Reputation 시스템

```typescript
reputation: Record<string, number>  // CITY_GUARD, MERCHANT_CONSORTIUM, LABOR_GUILD
```

이벤트 태그 기반 자동 변동:
- `GUARD_ALLIANCE`, `CHECKPOINT` 등 → CITY_GUARD: SUCCESS +3, FAIL -2
- `MERCHANT_GUILD`, `LEDGER` 등 → MERCHANT_CONSORTIUM: SUCCESS +3, FAIL -2
- `LABOR_GUILD`, `DOCK_THUGS` 등 → LABOR_GUILD: SUCCESS +3, FAIL -2

---

## 3. Action-First 파이프라인

```
LOCATION 진입 → Scene Shell(분위기) → 플레이어 입력
  → IntentParserV2 → ParsedIntentV2
  → EventMatcherService → EventDefV2 선택
  → ResolveService → ResolveResult
  → WorldState/Agenda/Arc 업데이트 → LLM 서술
```

### 3-1. IntentParserV2 --- 자연어 → ActionType

**ParsedIntentV2**:
```typescript
{
  inputText, actionType, tone, target,
  riskLevel: 1|2|3, intentTags, confidence: 0|1|2,
  source: 'RULE'|'LLM'|'CHOICE',
  suppressedActionType?, escalated?
}
```

**IntentActionType** (15종):
`INVESTIGATE`, `PERSUADE`, `SNEAK`, `BRIBE`, `THREATEN`, `HELP`, `STEAL`, `FIGHT`, `OBSERVE`, `TRADE`, `TALK`, `SEARCH`, `MOVE_LOCATION`, `REST`, `SHOP`

**IntentTone**: `CAUTIOUS`, `AGGRESSIVE`, `DIPLOMATIC`, `DECEPTIVE`, `NEUTRAL`

**파싱 방식**: 한국어 키워드 매칭 (예: `조사/살펴/탐색` → INVESTIGATE, `몰래/잠입` → SNEAK)
- 입력에서 모든 매칭 actionType 수집, 첫 번째가 primary
- CHOICE 입력 시 payload.affordance에서 직접 매핑

### 3-2. 고집(Insistence) 에스컬레이션

**에스컬레이션 맵**:
| 약한 actionType | 강한 actionType |
|-----------------|-----------------|
| TALK            | PERSUADE        |
| OBSERVE         | INVESTIGATE     |
| PERSUADE        | THREATEN        |
| THREATEN        | FIGHT           |

- suppressedActionType: 키워드 매칭되었으나 우선순위에 밀린 강한 actionType
- 같은 LOCATION에서 **3회 연속** 반복 → 강한 actionType으로 승격 (`escalated: true`)
- LOCATION 이동 또는 HUB 복귀 시 actionHistory 초기화
- LLM에 escalated 플래그 전달 → "행동 그대로 실행" 강한 서술 지시

### 3-3. MOVE_LOCATION 처리 (Fixplan3 P4)

ACTION 입력에서 MOVE_LOCATION 파싱 성공 시:
1. `extractTargetLocation()`으로 목표 장소 특정 시도
2. 목표 특정 성공 → `performLocationTransition()` (직접 장소 이동)
3. **목표 불명확 → go_hub와 동일한 HUB 복귀 처리** (`finalizeVisit` + `returnToHub` + `transitionToHub`)

---

## 4. Resolve 판정 시스템

### 4-1. 공식 (현행)

```
score = 1d6 + floor(stat / 3) + baseMod
```

| 항목 | 설명 |
|------|------|
| 1d6 | rng.range(1, 6) --- 결정적 RNG |
| stat | ACTION_STAT_MAP에 따른 PermanentStats 값 |
| baseMod | matchPolicy(SUPPORT +1, BLOCK -1) - friction(0~3) - (riskLevel==3 ? 1 : 0) |

### 4-2. ActionType → Stat 매핑

| ActionType | Stat | 비고 |
|------------|------|------|
| FIGHT, THREATEN | ATK | 전투/위협 |
| SNEAK, OBSERVE, STEAL | EVA | 은밀 행동 |
| INVESTIGATE | ACC | 정밀 탐색 |
| PERSUADE, BRIBE, TRADE | SPEED | 사교/거래 |
| HELP | DEF | 보호/지원 |

### 4-3. 판정 결과

| score | Outcome | 의미 |
|-------|---------|------|
| >= 6  | SUCCESS | 완전 성공 |
| 3~5   | PARTIAL | 부분 성공 |
| < 3   | FAIL    | 실패 |

> **OBSOLETE**: 이전 공식 (score >= 1 → SUCCESS, 0 → PARTIAL, <= -1 → FAIL)은 폐기됨.

### 4-4. 판정 후 효과

| 항목 | SUCCESS | PARTIAL | FAIL |
|------|---------|---------|------|
| heatDelta (SUPPORT) | +1 | 0 | +2 |
| heatDelta (BLOCK) | +3 | 0 | +5 |
| FIGHT/THREATEN 추가 | +2 | +2 | +2 |
| tensionDelta | 0 | 0 | +1 |
| influenceDelta | +1 | 0 | 0 |
| NPC relationChange | +5 | +2 | -3 |
| agendaBucketDelta | +2 | +1 | 0 |
| reputationChange | +3 | 0 | -2 |

**전투 트리거**: FAIL + BLOCK matchPolicy + combatWindowCount < 3 → 전투 진입
**Deferred**: THREATEN/DECEPTIVE tone + SUCCESS → 3턴 후 REPUTATION_BACKLASH

---

## 5. 이벤트 매칭 알고리즘 (6단계)

### 5-1. EventDefV2 스키마

```typescript
{
  eventId, locationId,
  eventType: 'RUMOR'|'FACTION'|'ARC_HINT'|'SHOP'|'CHECKPOINT'|'AMBUSH'|'FALLBACK',
  priority: number,          // 높을수록 우선
  weight: number,            // 가중치 선택용
  conditions: ConditionCmp | null,
  gates: Gate[],             // COOLDOWN_TURNS, REQUIRE_FLAG, REQUIRE_ARC
  affordances: Affordance[], // INVESTIGATE, PERSUADE, SNEAK, ... ANY
  friction: 0|1|2|3,        // 0=기회, 3=강한 방해
  matchPolicy: 'SUPPORT'|'BLOCK'|'NEUTRAL',
  arcRouteTag?, commitmentDeltaOnSuccess?,
  payload: { sceneFrame, primaryNpcId?, choices, effectsOnEnter, tags }
}
```

### 5-2. 매칭 단계

| 단계 | 처리 | 설명 |
|------|------|------|
| 1 | locationId 필터 | 현재 위치와 일치하는 이벤트만 |
| 2 | conditions 평가 | CMP(eq/ne/gt/gte/lt/lte) --- dot-notation으로 WorldState/ArcState 접근 |
| 3 | gates 평가 | COOLDOWN_TURNS, REQUIRE_FLAG, REQUIRE_ARC |
| 4 | affordances 매칭 | actionType이 affordances에 포함 (ANY는 모든 행동 허용) |
| 5 | Heat 간섭 | ALERT → 40% / DANGER → 25% 확률로 BLOCK 이벤트만 남김 |
| 6 | 가중치 선택 | `priority*10 + weight + agendaBoost - penalty` → RNG 가중치 선택 |

### 5-3. 페널티 (Fixplanv1 PR2 누진 페널티 적용)

| 페널티 | 값 | 조건 |
|--------|-----|------|
| FALLBACK 연속 | -30 * consecutiveCount | 최근 이벤트가 연속 FALLBACK |
| 최근 사용 1회 | -40 | recentEventIds에 1회 포함 |
| 최근 사용 2연속 | -70 | recentEventIds에서 직전 2회 연속 동일 |
| 최근 사용 3연속+ | -100 | 사실상 차단 |
| NPC 보너스 캡 | repeatPenalty * 0.5 | NPC 보너스가 반복 페널티의 50% 이상 상쇄 불가 |
| 방문 내 하드캡 | 후보 제외 | 동일 이벤트 2회 이상 사용 → 후보에서 제거 (전체 제거 시 필터 스킵) |

### 5-4. Agenda 부스트

이벤트 payload.tags와 PlayerAgenda.implicit 버킷 매칭:
- `destabilize` → destabilizeGuard * 2
- `merchant` → allyMerchant * 2
- `underworld` → empowerUnderworld * 2
- `corruption` → exposeCorruption * 2
- `chaos` → profitFromChaos * 2

---

## 6. Agenda & Arc 시스템

### 6-1. PlayerAgenda

```typescript
{
  explicit: { type: string | null, intensity: 1|2|3 },
  implicit: {
    destabilizeGuard, allyMerchant, empowerUnderworld,
    exposeCorruption, profitFromChaos   // 각 number
  },
  dominant: string | null  // implicit 최대값 버킷
}
```

- implicit 버킷은 Resolve 결과와 이벤트 태그 기반으로 누적
- dominant는 최대값 버킷 자동 계산
- 이벤트 가중치 재계산, Resolve modifier, 분기에 영향

### 6-2. Arc 시스템

**Routes**: `EXPOSE_CORRUPTION`, `PROFIT_FROM_CHAOS`, `ALLY_GUARD`

```typescript
ArcState = {
  currentRoute: ArcRoute | null,
  commitment: 0~3,    // 3 = 루트 잠금
  betrayalCount: number
}
```

| 규칙 | 조건 |
|------|------|
| 루트 전환 가능 | commitment <= 2 AND betrayalCount < 2 |
| 루트 잠금 | commitment == 3 → 변경 불가 |
| 배신 카운트 | 루트 전환 시 +1 |

**Arc 해금 조건** (HUB 진입 시 평가):
- Heat >= 40 → EXPOSE_CORRUPTION
- tension >= 5 → PROFIT_FROM_CHAOS
- flags.guard_trust → ALLY_GUARD

---

## 7. Scene Shell & 선택지 시스템

### 7-1. Scene Shell

LOCATION 진입 시 분위기 텍스트 생성: `getSceneShell(locationId, timePhase, hubSafety)`
- `content/graymar_v1/scene_shells.json`에서 LOCATION x TimePhase x Safety 조합 조회

### 7-2. 선택지 우선순위

| 순위 | 소스 | 설명 |
|------|------|------|
| 1 | event.payload.choices | 이벤트 고유 선택지 |
| 2 | suggested_choices.json | eventType별 템플릿 (RUMOR, FACTION, ARC_HINT 등) |
| 3 | LOCATION별 기본 선택지 | LOC_MARKET/GUARD/HARBOR/SLUMS 각 3개 |
| fallback | 범용 탐색 선택지 | OBSERVE, PERSUADE, INVESTIGATE |

- **go_hub** (거점 복귀) 선택지는 항상 포함
- HUB에서는 4개 LOCATION 이동 + Heat 해결 옵션(Heat > 0일 때 CONTACT_ALLY, PAY_COST)

### 7-3. LOCATION 구성 (Graymar Harbor)

| ID | 이름 | 특성 |
|----|------|------|
| LOC_MARKET | 시장 거리 | 상인, 소문, 거래 |
| LOC_GUARD | 경비대 지구 | 질서, 감시, 정보 |
| LOC_HARBOR | 항만 부두 | 선원, 밀수, 화물 |
| LOC_SLUMS | 빈민가 | 암흑가, 위험, 단서 |

---

## 8. 캐릭터 프리셋

| Preset | HP | ATK | DEF | ACC | EVA | SPEED | RESIST | 특성 |
|--------|-----|-----|-----|-----|-----|-------|--------|------|
| DOCKWORKER (부두 노동자) | 120 | 16 | 14 | 3 | 2 | 4 | 7 | 근접 탱커, 높은 체력/방어 |
| DESERTER (탈영병) | 100 | 17 | 11 | 7 | 3 | 5 | 5 | 밸런스 근접, 정석 전투 |
| SMUGGLER (밀수업자) | 80 | 14 | 7 | 5 | 7 | 7 | 3 | 스텔스, 높은 회피/치명타 |
| HERBALIST (약초상) | 90 | 11 | 9 | 6 | 4 | 4 | 9 | 유틸, 아이템 활용 |

**Resolve 적용 예시** (score = 1d6 + floor(stat/3) + baseMod):
- DOCKWORKER가 FIGHT(ATK 16) → statBonus = floor(16/3) = 5
- SMUGGLER가 SNEAK(EVA 7) → statBonus = floor(7/3) = 2
- HERBALIST가 HELP(DEF 9) → statBonus = floor(9/3) = 3

---

## 9. 구현 상태 요약

### 9.1 기본 HUB 서비스 (Phase 1)

| 서비스 | 파일 | 상태 |
|--------|------|------|
| WorldStateService | `world-state.service.ts` | ✅ init, moveToLocation, returnToHub, advanceTime, deferred, migrateWorldState |
| HeatService | `heat.service.ts` | ✅ delta clamp ±8, decay, CONTACT_ALLY, PAY_COST |
| IntentParserV2Service | `intent-parser-v2.service.ts` | ✅ 키워드 파싱, 고집 에스컬레이션, CHOICE 매핑, 복귀 의도 |
| LlmIntentParserService | `llm-intent-parser.service.ts` | ✅ LLM 기반 의도 파싱 (폴백) |
| EventMatcherService | `event-matcher.service.ts` | ✅ 6단계 필터링, 누진 반복 페널티(-40/-70/-100), NPC보너스 캡, 방문 내 하드캡 |
| ResolveService | `resolve.service.ts` | ✅ 1d6 + stat/3 + baseMod, reputation 변동 |
| AgendaService | `agenda.service.ts` | ✅ implicit bucket 누적, dominant 계산 |
| ArcService | `arc.service.ts` | ✅ route switch, commitment lock, unlock 조건 |
| SceneShellService | `scene-shell.service.ts` | ✅ Scene Shell, 선택지 3단 우선순위, go_hub |
| ShopService | `shop.service.ts` | ✅ 상점 거래 처리 |

### 9.2 Narrative Engine v1 서비스 (8개)

| 서비스 | 파일 | 역할 |
|--------|------|------|
| IncidentManagementService | `incident-management.service.ts` | Incident 생명주기 (spawn/tick/resolve) |
| WorldTickService | `world-tick.service.ts` | preStepTick/postStepTick, 4상 시간 사이클 |
| SignalFeedService | `signal-feed.service.ts` | 5채널 시그널 생성/만료 |
| OperationSessionService | `operation-session.service.ts` | 멀티스텝 LOCATION 세션 (1-3스텝) |
| NpcEmotionalService | `npc-emotional.service.ts` | 5축 감정 모델 + posture 자동 계산 |
| NarrativeMarkService | `narrative-mark.service.ts` | 12개 불가역 표식 시스템 |
| EndingGeneratorService | `ending-generator.service.ts` | 엔딩 조건 체크/결과 생성 |
| ShopService | `shop.service.ts` | 상점 거래 처리 |

### 9.3 Turn Orchestration (1개)

| 서비스 | 파일 | 역할 |
|--------|------|------|
| TurnOrchestrationService | `turn-orchestration.service.ts` | NPC 주입 (displayName) + pressure/peakMode 긴장도 관리 |

### 9.4 Structured Memory v2 서비스 (2개)

| 서비스 | 파일 | 역할 |
|--------|------|------|
| MemoryCollectorService | `memory-collector.service.ts` | 매 LOCATION 턴 visitContext 실시간 수집 |
| MemoryIntegrationService | `memory-integration.service.ts` | 방문 종료 시 StructuredMemory 통합+압축 |

### 9.5 User-Driven Bridge (6개) — 설계문서 14~17

| 서비스 | 파일 | 역할 |
|--------|------|------|
| IntentV3BuilderService | `intent-v3-builder.service.ts` | ParsedIntentV2 → ParsedIntentV3 확장 변환 |
| IncidentRouterService | `incident-router.service.ts` | IntentV3 기반 Incident 라우팅/매칭 |
| IncidentResolutionBridgeService | `incident-resolution-bridge.service.ts` | ResolveResult → Incident control/pressure 반영 |
| WorldDeltaService | `world-delta.service.ts` | 턴 전후 WorldState 차이 추적 |
| PlayerThreadService | `player-thread.service.ts` | 행동 성향 패턴 추적 (playstyleSummary, dominantVectors) |
| NotificationAssemblerService | `notification-assembler.service.ts` | Notification 조립 (scope×presentation) |

### 9.6 Narrative v2 & Event v2 (4개) — 설계문서 18~20

| 서비스 | 파일 | 역할 |
|--------|------|------|
| IntentMemoryService | `intent-memory.service.ts` | actionHistory 분석 → 행동 패턴 감지 (6종) |
| EventDirectorService | `event-director.service.ts` | 5단계 정책 파이프라인 (EventMatcher 래핑) |
| ProceduralEventService | `procedural-event.service.ts` | 동적 이벤트 생성 (Trigger+Subject+Action+Outcome) |
| LlmIntentParserService | `llm-intent-parser.service.ts` | LLM 기반 의도 파싱 (폴백) |

> **총 29개 서비스** — `server/src/engine/hub/` 디렉토리
> Base 9 + Narrative v1 8 + Orchestration 1 + Memory v2 2 + Bridge 6 + Narrative/Event v2 3

### 9.7 콘텐츠 데이터 (`content/graymar_v1/`)

- `events_v2.json` --- 88개 이벤트 (LOCATION당 22개, eventCategory 포함)
- `scene_shells.json` / `scene_shells_v2.json` --- LOCATION x TimePhase x Safety 분위기 텍스트
- `suggested_choices.json` --- eventType별 선택지 템플릿
- `arc_events.json` --- Arc route별 이벤트
- `incidents.json` --- Incident 정의
- `endings.json` --- 엔딩 조건/결과
- `narrative_marks.json` --- 12개 불가역 표식 정의
- `presets.json` --- 4개 캐릭터 프리셋
