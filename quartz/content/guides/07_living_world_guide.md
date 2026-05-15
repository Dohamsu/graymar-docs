# Living World v2 구현 지침

> 정본 위치: `server/src/engine/hub/` (living-world 서브폴더 없음, hub/ 평면 배치)
> 설계 배경: [[architecture/21_living_world_redesign|living world redesign]] (배경/대안 분석)
> 타입 정본: `server/src/db/types/{world-state,location-state,world-fact,player-goal,npc-schedule}.ts`

Living World v2를 구성하는 7개 서비스의 API, 호출 흐름, runState 스키마, 상수만 정리. 설계 배경/대안 비교는 21 원본 참조.

---

## 1. 서비스 맵

| 서비스 | 파일 | 역할 |
|--------|------|------|
| LocationStateService | `location-state.service.ts` | 장소 동적 상태(security/prosperity/unrest/conditions/presentNpcs) |
| WorldFactService | `world-fact.service.ts` | WorldFact CRUD + 태그/NPC/장소/카테고리 검색 + 만료 |
| NpcScheduleService | `npc-schedule.service.ts` | NPC 시간대별 위치 계산 + 장소별 NPC 갱신 |
| NpcAgendaService | `npc-agenda.service.ts` | NPC 장기 목표 stage 진행 + Fact/Condition/Signal 자동 발생 |
| ConsequenceProcessorService | `consequence-processor.service.ts` | 판정 결과 → Fact + LocationState 변경 + NPC 목격 + 임계값 트리거 |
| SituationGeneratorService | `situation-generator.service.ts` | 3계층 상황 생성(Landmark/Incident-Driven/World-State) |
| PlayerGoalService | `player-goal.service.ts` | 명시적/암시적 목표 + milestone 자동 체크 |

tick 오케스트레이터: `WorldTickService`(`world-tick.service.ts`)가 Living World 서비스들을 Optional 주입받아 호출.

---

## 2. runState JSONB 스키마 (Living World 확장)

`server/src/db/types/world-state.ts` — `WorldState` 타입에 추가된 필드:

```ts
type WorldState = {
  // ... 기존 v1 필드 (hubHeat, reputation, flags, globalClock, day, phaseV2, activeIncidents, npcGoals, ...)
  worldFacts?: WorldFact[];                                  // max 50
  npcLocations?: Record<string, string>;                     // npcId → locationId
  locationDynamicStates?: Record<string, LocationDynamicState>;
  playerGoals?: PlayerGoal[];                                // max 5
};
```

### LocationDynamicState / LocationCondition

```ts
interface LocationDynamicState {
  locationId: string;
  controllingFaction: string | null;
  controlStrength: number;               // 0~100 (기본 70)
  contestedBy?: string;
  security: number; prosperity: number; unrest: number;  // 0~100
  activeConditions: LocationCondition[]; // max 3
  presentNpcs: string[];
  recentEventIds: string[];              // 최근 5개
  playerVisitCount: number; lastVisitTurn: number;
}

interface LocationCondition {
  id: string;        // CURFEW | FESTIVAL | LOCKDOWN | RIOT | INCREASED_PATROLS | UNREST_RUMORS | BLACK_MARKET | RAID_AFTERMATH
  source: string;    // 'threshold:security<15' | incidentId | npcAction 등
  startTurn: number;
  duration: number;  // -1 = 영구
  effects: {
    securityMod: number; prosperityMod: number; unrestMod: number;
    blockedActions?: string[]; boostedActions?: string[];
  };
}
```

### WorldFact

```ts
interface WorldFact {
  id: string;                  // 'fact_player_action_t15_1234'
  category: 'PLAYER_ACTION' | 'NPC_ACTION' | 'WORLD_CHANGE' | 'DISCOVERY' | 'RELATIONSHIP';
  text: string;
  locationId: string;
  involvedNpcs: string[];
  turnCreated: number; dayCreated: number;
  tags: string[];              // 소문자: actionType, outcome, locationId, npcId, event tags
  impact?: {
    reputationChanges?: Record<string, number>;
    npcKnowledge?: Record<string, 'WITNESSED' | 'HEARD_FROM_NPC' | 'HEARD_RUMOR'>;
  };
  permanent: boolean;
  expiresAtTurn?: number;      // !permanent ? turnCreated + 30 : undefined
}
```

### PlayerGoal

```ts
interface PlayerGoal {
  id: string;                  // 'goal_explicit_{turn}_{rand}' | 'goal_implicit_{pattern}_{turn}'
  type: 'EXPLICIT' | 'IMPLICIT';
  description: string;
  relatedNpcs: string[]; relatedLocations: string[]; relatedFactTags: string[];
  progress: number;            // 0~100
  milestones: { description: string; completed: boolean; factRequired: string }[];
  createdTurn: number; createdDay: number; completed: boolean;
  rewards?: { reputationChanges?; goldRange?: [number, number]; unlocks?: string[] };
}
```

### NpcSchedule / NpcAgenda (콘텐츠 데이터)

`content/graymar_v1/npcs.json`에 NPC별 정의. 런타임 상태는 `ws.npcLocations`(현재 위치) + `ws.npcGoals`(stage 진행)로 분리.

```ts
interface NpcSchedule {
  default: Record<TimePhaseV2, NpcScheduleEntry>;  // DAWN/DAY/DUSK/NIGHT
  overrides?: { condition: string; schedule: Partial<Record<TimePhaseV2, NpcScheduleEntry>> }[];
}
interface NpcScheduleEntry { locationId: string; activity: string; interactable: boolean }

interface NpcAgenda {
  currentGoal: string;
  stages: NpcAgendaStage[];
  currentStage: number; completed: boolean;
}
interface NpcAgendaStage {
  stage: number; description: string;
  triggerCondition: string;     // 'day >= 5 AND security.LOC_HARBOR < 50'
  onTrigger: {
    factText: string; factTags: string[];
    conditionApply?: { locationId: string; condition: Omit<LocationCondition, 'startTurn'> };
    signalText?: string; signalChannel?: string;  // RUMOR | SECURITY | NPC_BEHAVIOR | ECONOMY | VISUAL
  };
  blockedBy?: string;           // 'INC_XXX.resolved' 형식 지원
}
```

### 초기화 (runs.service.ts `createRun`)

불변식 22: 새 런 생성 시 반드시 `locationDynamicStates`(콘텐츠 7개 장소의 baseState 기반) + `worldFacts=[]` + `npcLocations={}` + `playerGoals=[]` 초기화.

---

## 3. 서비스 API

### LocationStateService

```ts
initializeLocationStates(defs): Record<string, LocationDynamicState>
getState(ws, locationId): LocationDynamicState | undefined
addCondition(ws, locId, Omit<LocationCondition,'startTurn'>, currentTurn): boolean
  // 동일 id 있으면 갱신. max 3개 초과 시 false.
removeCondition(ws, locId, conditionId): boolean
tickConditions(ws, currentTurn): string[]
  // duration 만료 조건 제거. duration=-1은 영구. 반환: ['LOC_HARBOR:CURFEW', ...]
updatePresentNpcs(ws, locId, npcIds): void
recordVisit(ws, locId, turnNo): void          // playerVisitCount++, lastVisitTurn 기록
addRecentEvent(ws, locId, eventId): void       // 최대 5개
naturalDecay(ws, baseStates): void             // base로 10% 회귀 후 0~100 클램프
```

### WorldFactService

```ts
addFact(ws, Omit<WorldFact,'id'|'expiresAtTurn'> & { id? }): WorldFact
  // id 자동: 'fact_{category}_t{turn}_{Date%10000}'
  // expiresAtTurn = permanent ? undefined : turnCreated + 30
  // max 50 초과 시 비permanent 중 오래된 것부터 제거
findByTags / findByNpc / findByLocation / findByCategory / getRecent / hasFact
pruneExpired(ws, currentTurn): number         // 반환: 제거 개수
createFromResolve(params): Omit<WorldFact,'id'|'expiresAtTurn'>
```

### NpcScheduleService

```ts
getNpcLocation(npcId, timePhase, ws): NpcScheduleEntry | null
  // overrides 순차 평가 → 첫 매칭 우선, 없으면 default[timePhase]
getPresentNpcs(locationId, timePhase, ws): string[]
updateAllNpcLocations(ws): void
  // WorldTick.postStepTick에서 호출. ws.npcLocations 전체 + locationDynamicStates[*].presentNpcs 갱신.
  // phaseV2 없으면 timePhase('DAY'|'NIGHT')로 fallback.
```

**조건 평가** 문법: `day >= N` | `incident.INC_XXX.stage >= N` | `hubHeat >= N` | `flag.FLAG_NAME`. NpcAgendaService는 추가로 `security.LOC_XXX < N`과 `A AND B` 지원.

### NpcAgendaService

```ts
tickAgendas(ws, currentTurn): AgendaTickResult[]
  // 모든 NPC agenda 순회. stage.triggerCondition 만족 + blockedBy 해제 시 진행.
  // 진행 시: WorldFact 생성 + LocationCondition 추가(conditionApply) + Signal 발생(signalText).
  // ws.npcGoals[npcId].progress 0~100 → stage 0~4 (25씩 매핑).
getAgendaState(ws, npcId): { currentGoal; progress } | null

interface AgendaTickResult {
  npcId: string; stageAdvanced: number;
  factCreated?: string; conditionApplied?: string; signalEmitted?: string;
}
```

### ConsequenceProcessorService

```ts
process(ws, input: ConsequenceInput): ConsequenceOutput

interface ConsequenceInput {
  resolveResult: ResolveResult; intent: ParsedIntentV2; event: EventDefV2;
  locationId: string; turnNo: number; day: number; primaryNpcId?: string;
}
interface ConsequenceOutput {
  factsCreated: WorldFact[]; locationEffects: string[];
  npcWitnesses: string[]; triggeredConditions: string[];
}
```

**처리 순서**:
1. **Fact 생성** — `category: PLAYER_ACTION`, text는 `ACTION_DESCRIPTIONS + OUTCOME_DESCRIPTIONS` 조합. permanent는 FIGHT/STEAL/THREATEN+SUCCESS 또는 NPC 관련 SUCCESS.
2. **LocationState delta** — FIGHT: security −5/−3, unrest +3/+5 | STEAL FAIL: security −2, unrest +2 | THREATEN: −2/+2 | HELP+SUCCESS: +1/−1. │delta│≥10이면 SECURITY 채널 Signal 자동 발생.
3. **임계값 트리거** (`checkThresholdTriggers`):
   - `security < 15` → **LOCKDOWN** (duration 8, block: STEAL/SNEAK, boost: OBSERVE/TALK)
   - `security < 30` → **INCREASED_PATROLS** (6턴)
   - `unrest > 80` → **RIOT** (5턴, block: TRADE/SHOP, boost: FIGHT/STEAL)
   - `unrest > 60` → **UNREST_RUMORS** (8턴)
   - 회복 임계: security≥35 PATROLS 해제, security≥20 LOCKDOWN 해제, unrest≤55 RUMORS 해제, unrest≤70 RIOT 해제.
4. **NPC 목격** — `presentNpcs` + `primaryNpcId` 전원에 `fact.impact.npcKnowledge[npcId]='WITNESSED'`.

gold/heat/reputation/relation 업데이트는 `turns.service.ts`가 계속 담당. ConsequenceProcessor는 "세계 사실" 레이어만.

### SituationGeneratorService

```ts
generate(
  ws, locationId, intent,
  allEvents, incidentDefs,
  recentPrimaryNpcIds?, discoveredFacts?: Set<string>
): Situation | null

interface Situation {
  trigger: 'LANDMARK' | 'INCIDENT_DRIVEN'
         | 'NPC_ACTIVITY' | 'NPC_CONFLICT' | 'ENVIRONMENTAL'
         | 'CONSEQUENCE' | 'DISCOVERY' | 'OPPORTUNITY' | 'ROUTINE';
  eventDef: EventDefV2;        // 기존 파이프라인 호환
  primaryNpcId?: string; secondaryNpcId?: string;
  relatedFacts: string[]; dynamicSceneFrame?: string;
}
```

**3계층 순차 시도**:
- **Layer 1 — tryLandmark**: ARC_HINT 이벤트 중 locationId/mainArc.stage/activeArcId 일치한 첫 이벤트.
- **Layer 2 — tryIncidentDriven**: 현재 장소의 미해결 incident → payload.tags가 incidentId를 포함한 이벤트 중 최고 priority → `relatedNpcIds ∩ presentNpcs`로 primaryNpc.
- **Layer 3 — tryWorldState** (우선순위):
  1. **NPC_CONFLICT** — presentNpcs 중 서로 다른 faction 2명 쌍.
  2. `globalClock % 3 === 0`이면 CONSEQUENCE 우선.
  3. **ENVIRONMENTAL** — activeConditions 첫 번째 (CURFEW/LOCKDOWN/FESTIVAL/BLACK_MARKET/RAID_AFTERMATH 서술 맵).
  4. **NPC_ACTIVITY** — CORE > SUB NPC의 schedule.activity. BG NPC는 배경 묘사.
  5. CONSEQUENCE fallback (turnMod≠0).
  6. NPC_ACTIVITY fallback.
  7. 전부 실패 → `null` → EventDirector/EventMatcher로 fallback.

보조 규칙:
- **NPC 연속 방지** — `recentPrimaryNpcIds` 최근 2명을 정렬 뒤로 밀기(연속 3턴 방지).
- **Fact 우선 템플릿** (`findTemplatePreferFact`) — `discoverableFact`가 있고 `discoveredFacts`에 없는 이벤트 우선.
- **tier 분류** (`classifyNpcsByTier`) — CORE/SUB만 상호작용 대상, BACKGROUND는 배경.

### PlayerGoalService

```ts
addExplicitGoal(ws, goal, turnNo, day): PlayerGoal | null
  // 활성 5개 초과 시 null. type='EXPLICIT', progress=0.
detectImplicitGoals(ws, patterns, turnNo, day): PlayerGoal[]
  // count >= 3인 pattern만. 동일 pattern IMPLICIT 있으면 스킵. progress=min(count*15,60).
  // pattern: aggressive | diplomatic | stealth | commercial | investigative | helpful
checkMilestones(ws): { goalId; milestoneIdx; completed }[]
  // factRequired를 fact id 또는 tag로 검색. 일치 시 ms.completed=true.
  // progress = (완료/전체)*100. 전원 완료 → goal.completed=true.
getActiveGoals(ws): PlayerGoal[]
completeGoal(ws, goalId): boolean
```

IntentMemoryService가 감지한 행동 패턴을 `detectImplicitGoals()`에 주입.

---

## 4. WorldTick 통합

`world-tick.service.ts`. Living World 서비스를 `@Optional()` 주입 — 미주입 시 해당 단계 스킵.

### preStepTick (입력 처리 전)
1. `globalClock++`, `phaseV2` 전환 (DAWN 2 + DAY 4 + DUSK 2 + NIGHT 4 = 12tick/일)
2. `incidentMgmt.tickAllIncidents` — pressure 자동 증가
3. Incident deadline 체크 → EXPIRED
4. `incidentMgmt.trySpawnIncident` — 새 incident
5. `signalFeed.generateFromIncidents`

### postStepTick (판정 결과 반영 후)
1. resolvedPatches 적용 (heat/tension/reputation/flags)
2. `hubSafety` 재계산 (`<40=SAFE`, `<70=ALERT`, `≥70=DANGER`)
3. `timePhase` ↔ `phaseV2` 동기화
4. `signalFeed.expireSignals`
5. **`npcSchedule.updateAllNpcLocations(ws)`**
6. **`locationState.tickConditions(ws, globalClock)`**
7. **`worldFact.pruneExpired(ws, globalClock)`**
8. **`npcAgenda.tickAgendas(ws, globalClock)`** → `(ws as any).recentAgendaEvents` 저장 (LLM 힌트)

---

## 5. 턴 파이프라인 (turns.service.ts LOCATION)

```
1. ACTION/CHOICE → IntentParserV2 → IntentV3Builder
2. [이벤트 매칭]
   a. questFactTrigger=true → EventDirector 직행 (SitGen 바이패스, 불변식 29)
   b. 직전 턴이 SIT_*/PROC_* 아니고 rng < SITGEN_CHANCE
      → situationGenerator.generate() → Situation.eventDef
   c. 실패 시 EventDirector/EventMatcher fallback
3. IncidentRouter → ResolveService (1d6 + floor(stat/3) + baseMod)
4. IncidentResolutionBridge
5. [async] nanoCtx 빌드 (NanoEventDirector는 LLM Worker에서 호출)
6. consequenceProcessor.process(ws, {...}) ← Fact + LocationState + 임계값 + NPC 목격
7. WorldDelta → PlayerThread → NotificationAssembler
8. worldTick.preStepTick(ws, incidentDefs, rng, 1)
9. Incident impact 적용 + IncidentMemory 축적
10. worldTick.postStepTick(ws, resolvedPatches)
    ← NPC 위치 → Condition 만료 → Fact 만료 → Agenda tick
11. Rewards/Equipment
12. playerGoal.checkMilestones(ws)
13. ServerResultV1 DB commit → [async] LLM Worker
```

**중요**: ConsequenceProcessor는 `preStepTick` **이전** (판정 직후). Agenda tick은 `postStepTick` 끝부분.

---

## 6. 핵심 상수 & 임계치

| 상수 | 값 | 정의 위치 |
|------|---|---------|
| MAX_CONDITIONS_PER_LOCATION | 3 | `db/types/location-state.ts` |
| MAX_WORLD_FACTS | 50 | `db/types/world-fact.ts` |
| DEFAULT_FACT_TTL | 30 턴 | `db/types/world-fact.ts` |
| MAX_ACTIVE_GOALS | 5 | `db/types/player-goal.ts` |
| SITGEN_CHANCE | `quest-balance.config.ts` | SitGen 발동 확률 |
| TICKS_PER_DAY | 12 (DAWN 2 + DAY 4 + DUSK 2 + NIGHT 4) | `world-tick.service.ts` |
| 자연 회귀율 | 0.1 | `LocationStateService.naturalDecay` |
| HUB Heat ±8 clamp | 한 턴 | 불변식 9 |
| HUB Safety | SAFE<40, ALERT<70, DANGER≥70 | `WorldTickService.computeSafety` |
| LOCKDOWN 임계 / duration | security<15 / 8턴 | ConsequenceProcessor |
| INCREASED_PATROLS | security<30 / 6턴 | ConsequenceProcessor |
| RIOT | unrest>80 / 5턴 | ConsequenceProcessor |
| UNREST_RUMORS | unrest>60 / 8턴 | ConsequenceProcessor |
| Signal 자동 발생 | │securityDelta│≥10 또는 │unrestDelta│≥10 | ConsequenceProcessor |
| Implicit goal 최소 반복 | 3회 | PlayerGoalService |
| controlStrength 기본값 | 70 | runs.service.ts |

---

## 7. 불변식 & 검증 지점

**관련 불변식**:
- **9**: HUB Heat 한 턴 변동 ±8 clamp.
- **22**: `createRun` 시 `locationDynamicStates`(7개) + `worldFacts=[]` + `npcLocations={}` + `playerGoals=[]` 초기화 필수.
- **29**: `questFactTrigger` true 시 SitGen 바이패스, EventDirector 직행.
- **30**: SITGEN_CHANCE/PARTIAL 발견률/weight 부스트는 `quest-balance.config.ts`에서 관리, 하드코딩 금지.
- Fact/Condition 제거는 `postStepTick`에서만 (`pruneExpired`/`tickConditions`). 다른 지점 직접 삭제 금지.

**플레이테스트 검증 체크**:
1. `ws.worldFacts.length ≤ 50`
2. `Object.keys(ws.locationDynamicStates).length === 7`
3. 장소별 `activeConditions.length ≤ 3`
4. 활성 `playerGoals.length ≤ 5`
5. `postStepTick` 후 `ws.npcLocations`가 현 phaseV2 schedule과 일치
6. ConsequenceProcessor 호출 후 primaryNpc가 `fact.impact.npcKnowledge`에 'WITNESSED'
7. 낮은 security 장소에서 FIGHT 연속 시 LOCKDOWN 자동 발동

---

## 8. DI 메모

- 7개 서비스 모두 `engine/hub` 모듈 provider.
- `WorldTickService`가 `NpcSchedule/LocationState/WorldFact/NpcAgenda`를 `@Optional()` 주입.
- `NpcAgendaService`가 `SignalFeedService`를 `@Optional()` 주입.
- `turns.service.ts`가 `SituationGeneratorService/ConsequenceProcessorService`를 `@Optional()` 주입 — 미주입 시 기존 EventMatcher 경로.
