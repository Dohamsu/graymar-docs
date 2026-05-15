# HUB 엔진 구현 지침

> 정본 위치: `server/src/engine/hub/`
> 설계 문서: [[architecture/03_hub_engine|hub engine]], `14~17`, `18~20`
> 최종 갱신: 2026-04-03 (퀘스트/프리셋6종/특성/KW_OVERRIDE 추가)

## Action-First 파이프라인

```
LOCATION: ACTION/CHOICE
  → IntentParserV2 (자연어 → ActionType)
  → IntentV3Builder (V2 → V3 확장)
  → EventDirector (5단계 정책) → EventMatcher(RNG) 내부 위임
  → IncidentRouter (사건 라우팅)
  → ResolveService (1d6 + stat)
  → IncidentResolutionBridge (판정 → Incident 반영)
  → WorldDelta (상태 변화 추적)
  → PlayerThread (행동 성향 추적)
  → NotificationAssembler (알림 조립)
  → ServerResultV1 (DB commit)
  → [async] LLM Worker → narrative text
```

---

## MOVE_LOCATION 처리 (Fixplan3 P4)

`server/src/turns/turns.service.ts`

### 파싱
- IntentParserV2 키워드: "이동", "향한다", "떠나", "다른 곳", "다른 장소" 등
- LlmIntentParserService: KW와 LLM 결과 병합 시 아래 KW_OVERRIDE 규칙 적용

### 처리 흐름
```
MOVE_LOCATION 감지
  → extractTargetLocation(rawInput, currentLocationId)
  → 목표 장소 특정됨? → performLocationTransition() (LOCATION→LOCATION 직접 이동)
  → 목표 불명확?     → HUB 복귀 fallback (finalizeVisit + transitionToHub)
```

### HUB 복귀 fallback
목표 장소가 불명확한 이동 의도("다른 장소로 이동한다")는 go_hub CHOICE와 동일하게 처리:
1. `finalizeVisit()` 호출 → storySummary 축적
2. `worldStateService.returnToHub()` → worldState 초기화
3. `NODE_ENDED` + `transitionToHub()` → HUB 노드 생성
4. 플레이어가 HUB에서 새 장소 선택

---

## IntentParser KW_OVERRIDE 규칙

`server/src/engine/hub/llm-intent-parser.service.ts` — `mergeResults()`
`server/src/engine/hub/intent-parser-v2.service.ts` — `extractAllActionTypes()`

LlmIntentParserService는 KW(키워드)와 LLM 결과를 병합할 때 3단계 규칙을 적용한다.

### mergeResults 병합 규칙

```
1. KW=MOVE_LOCATION + LLM=MOVE_LOCATION → AGREE (양쪽 일치)
2. KW=MOVE_LOCATION + detectLocationBasedMove=true → KW_OVERRIDE (장소명+이동접미사 복합감지)
3. KW=MOVE_LOCATION + detectLocationBasedMove=false → LLM 신뢰 (단순 1-hit은 오탐 가능)
4. KW와 LLM 일치 → AGREE
5. KW와 LLM 불일치 → LLM 우선 (맥락 이해 우수), KW 결과는 secondary로 보존
```

- `detectLocationBasedMove()`: 장소명("부두", "시장", "빈민가" 등)과 이동 접미사("가자", "이동", "향한다" 등)가 **동시에** 매칭되는 경우에만 true
- MOVE_LOCATION에서 단순 키워드 1-hit("그만", "끝내" 등 서브스트링 오탐)은 LLM을 신뢰

### extractAllActionTypes 안전망 (IntentParserV2)

```
MOVE_LOCATION이 1위 AND 키워드 hit=1 AND detectLocationBasedMove=false
  → MOVE_LOCATION을 후보에서 제거
```

"동작그만"처럼 "이동"이 서브스트링으로 매칭되는 오탐을 방지한다. `detectLocationBasedMove`가 true이면 장소명 복합감지이므로 제거하지 않는다.

---

## Player-First 턴 모드 (2026-04-15)

이벤트 매칭 전 `determineTurnMode()`로 턴 모드를 결정:
- **PLAYER_DIRECTED**: 플레이어가 NPC를 명시적으로 지목 → 이벤트 매칭 스킵
- **CONVERSATION_CONT**: 대화 연속 (SOCIAL_ACTION + lastNpcId/contextNpcId) → 이벤트 매칭 스킵
- **WORLD_EVENT**: 첫 진입 / pressure>=70 / questFactTrigger → 기존 매칭 파이프라인

기본값은 PLAYER_DIRECTED (이벤트 강제 없음).

---

## LOCATION 판정 시스템

`server/src/engine/hub/resolve.service.ts`

### 공식
```
diceRoll  = 1d6 (RNG 기반, 결정적)
statBonus = floor(관련스탯 / 3)
baseMod   = matchPolicy(SUPPORT+1/BLOCK-1) - friction - (riskLevel3 ? 1 : 0)
totalScore = diceRoll + statBonus + baseMod

SUCCESS: totalScore >= 6
PARTIAL: 3 <= totalScore < 6
FAIL:    totalScore < 3
```

### ActionType → 스탯 매핑
| actionType | 스탯 |
|-----------|------|
| FIGHT, THREATEN | ATK |
| SNEAK, OBSERVE, STEAL | EVA |
| INVESTIGATE | ACC |
| PERSUADE, BRIBE, TRADE | SPEED |
| HELP | DEF |

---

## Event Director (5단계 정책)

`server/src/engine/hub/event-director.service.ts` — 설계문서 19

EventMatcherService를 래핑하여 정책 레이어 추가:

```
1. Stage Filter    → mainArcClock.stage와 event.stage[] 매칭
2. Condition Filter → evaluateCondition() 위임
3. Cooldown Filter  → evaluateGates() + cooldownTurns
4. Priority Sort    → priority → weight 리매핑
5. Weighted Random  → weightedSelect() 위임
```

Priority → Weight 매핑:
- priority ≥ 8 → critical(10)
- priority ≥ 6 → high(6)
- priority ≥ 4 → medium(3)
- else → low(1)

Fallback 체인: 고정 이벤트 → 절차적 이벤트 → atmosphere fallback

### 이벤트 반복 방지 (Fixplanv1 PR2 + Fixplanv2 PR-D)

EventMatcherService의 3중 방지 체계:
1. **직전 이벤트 hard block** (Fixplanv2 PR-D): 가중치 선택 이전에 `recentEventIds[last]`와 동일한 이벤트를 후보에서 제거 (안전장치: 전체 제거 시 원래 후보 유지). match() + matchWithIncidentContext() 양쪽 적용.
2. **누진 반복 페널티**: 1회 반복 -60 (Fixplanv2: 40→60), 2연속 -70, 3연속+ -100 (사실상 차단)
3. **방문 내 하드캡**: 동일 이벤트 2회 이상 → 후보에서 제거

- NPC 보너스 캡: repeatPenalty의 50% 초과 상쇄 불가

---

## Procedural Event (동적 이벤트 생성)

`server/src/engine/hub/procedural-event.service.ts` — 설계문서 20

고정 이벤트 부족 시 Trigger+Subject+Action+Outcome 조합으로 자동 생성.

### Anti-Repetition 규칙
| 규칙 | 값 | 추적 |
|------|-----|------|
| trigger 쿨다운 | 3턴 | proceduralHistory.triggerId |
| subject-action 쿨다운 | 5턴 | proceduralHistory.subjectActionKey |
| same outcome 연속 | max 2 | proceduralHistory.outcomeId |
| same NPC 연속 | max 3 | proceduralHistory.npcId |

**불변식**: arcRouteTag=undefined, commitmentDeltaOnSuccess=undefined (메인 플롯 보호)

---

## Intent Memory (행동 패턴 감지)

`server/src/engine/hub/intent-memory.service.ts` — 설계문서 18

actionHistory 최근 10턴 분석 → 6종 패턴 감지:

| 패턴 | 조건 | 서술 톤 |
|------|------|------|
| 공격적 심문 | THREATEN+INVESTIGATE ≥2 | 위협적 어조 |
| 은밀 탐색 | SNEAK+OBSERVE ≥2 | 조심스러운 분위기 |
| 외교적 접근 | PERSUADE+TALK ≥2 | 우호적 톤 |
| 증거 수집 | INVESTIGATE+OBSERVE+SEARCH ≥3 | 분석적 관점 |
| 대결적 | FIGHT+THREATEN ≥2 | 긴장감 강조 |
| 상업적 | TRADE+BRIBE ≥2 | 거래 중심 |

최소 4회 actionHistory 필요. 최대 2개 패턴 반환.

---

## User-Driven Bridge 파이프라인 (설계문서 14~17)

```
IntentV3Builder     → ParsedIntentV2에 incidentContext 추가
  ↓
IncidentRouter      → IntentV3 기반 관련 Incident 매칭
  ↓
ResolveService      → 판정 (기존)
  ↓
IncidentResolution  → 판정 결과 → Incident control/pressure 반영
  ↓
WorldDelta          → 턴 전후 WorldState 차이 추적
  ↓
PlayerThread        → 행동 성향 패턴 추적 (playstyleSummary, dominantVectors)
  ↓
NotificationAssembler → scope × presentation 기반 알림 조립
```

---

## Narrative Engine v1 시스템

### Incident System (사건 시스템)
- **Dual-axis**: control (0-100, 높을수록 억제) / pressure (0-100, 높을수록 폭발)
- **생명주기**: ACTIVE → CONTAINED(control≥80) / ESCALATED(pressure≥95) / EXPIRED(deadline)
- **Spawn**: 20%/tick 확률, 최대 3개 동시 활성
- **8 Incidents**: 밀수단, 부패, 시장 절도, 노동 파업, 암살 등

### Signal Feed (시그널 피드)
- **5 channels**: RUMOR, SECURITY, NPC_BEHAVIOR, ECONOMY, VISUAL
- **severity** 1-5 (높을수록 긴급)
- Incident tick 시 시그널 자동 생성, MAX_SIGNALS=20

### NPC Emotional Model (NPC 감정 모델)
- **5축**: trust / fear / respect / suspicion / attachment (-100~100)
- `computeEffectivePosture()`: 5축 → NpcPosture 자동 계산
- 매 LOCATION 턴 자동 업데이트 (이벤트 태그/판정 결과 기반)

### Narrative Marks (서사 표식)
- **12종** (불가역): BETRAYER, SAVIOR, KINGMAKER, SHADOW_HAND, MARTYR, PROFITEER, PEACEMAKER, WITNESS, ACCOMPLICE, AVENGER, COWARD, MERCIFUL
- 조건 충족 시 자동 부여, LLM 프롬프트에 반영

### Ending System (엔딩 시스템)
- **트리거**: ALL_RESOLVED / DEADLINE / PLAYER_CHOICE
- **최소 턴 가드** (Fixplan3 P7): ALL_RESOLVED 엔딩은 `totalTurns ≥ 15` 이상이어야 발동. 미달 시 엔딩 지연 → 탐색 시간 확보.
- **결과**: NPC epilogues (high_trust/neutral/hostile, `korParticle` 조사 적용) + city status (STABLE/UNSTABLE/COLLAPSED) + 통계

### 4-Phase Time Cycle
- DAWN(2 tick) → DAY(4) → DUSK(2) → NIGHT(4) = 12 tick/day

### NPC Introduction System
| Posture | 소개 시점 | 방식 |
|---------|----------|------|
| FRIENDLY / FEARFUL | 1회째 만남 | 자기소개 |
| CAUTIOUS | 2회째 만남 | 상황 단서 |
| CALCULATING / HOSTILE | 3회째 만남 | 문서/타인 |

- 소개 전: `unknownAlias`, 소개 후: `npcDef.name`
- 핵심 함수: `getNpcDisplayName()`, `shouldIntroduce()` (`server/src/db/types/npc-state.ts`)
- **encounterCount 방문 단위 제한** (Fixplanv2 PR-A): actionHistory에서 이미 만난 NPC면 스킵. 같은 방문 내 5턴 연속 만나도 encounterCount는 1만 증가.
- **effectiveNpcId 통합** (Fixplanv2 PR-A): `matchedEvent.payload.primaryNpcId` 우선, 없으면 `orchestrationResult.npcInjection.npcId` fallback.
- **TAG_TO_NPC 보충** (Fixplan3 P2): 위 두 소스 모두 null이면 이벤트 `tags`에서 `TAG_TO_NPC` 매핑으로 NPC를 추론 → encounterCount 증가 + shouldIntroduce 판정. `memory-collector.service.ts`의 `TAG_TO_NPC` 재활용.
- **장소 대표 NPC encounterCount fallback** (Fixplan5): primaryNpcId, npcInjection, TAG_TO_NPC 모두 null일 때, `NPC_LOCATION_AFFINITY`에서 해당 장소 친화도가 있는 미만남 NPC의 encounterCount를 1 증가 (턴당 최대 1명). LLM이 NPC 목록에서 자발적으로 서술하는 NPC의 만남을 추적.
- **NPC 주입 연속 등장 방지** (Fixplan5): `orchestrate()` 호출 시 `actionHistory` 직전 2턴의 `primaryNpcId`를 수집, `checkNpcInjection()` 후보에서 제외. 모든 후보가 제외되면 원래 후보 풀로 fallback.

---

## Reputation System (세력 평판)

| 세력 | 키 | 관련 이벤트 태그 |
|------|-----|---------------|
| 경비대 | CITY_GUARD | GUARD_ALLIANCE, GUARD_PATROL, CHECKPOINT, ARMED_GUARD |
| 상인 길드 | MERCHANT_CONSORTIUM | MERCHANT_GUILD, LEDGER, MERCHANT_CONSORTIUM |
| 노동 길드 | LABOR_GUILD | LABOR_GUILD, WORKER_RIGHTS, DOCK_THUGS |

판정 결과: SUCCESS +3, FAIL -2, PARTIAL 0

---

## Living World v2 시스템

Living World v2는 7개 서비스로 구성되며, 세계가 플레이어 행동과 독립적으로 살아 움직이는 느낌을 제공한다.

### WorldFact 시스템

`server/src/engine/hub/world-fact.service.ts`

플레이어 행동과 이벤트 결과에서 발생하는 **사실(Fact)**을 누적 관리한다.

- **Fact 생성**: 판정 결과, Incident 진행, NPC 상호작용에서 자동 생성
- **Fact 조회**: SituationGenerator, EventMatcher conditions에서 참조
- **Fact 만료**: 시간 경과 또는 조건 충족 시 자동 정리 (WorldTick 연동)
- 예: `{ factId: "MARKET_FIGHT_WITNESSED", locationId: "LOC_MARKET", ttl: 5 }`

### LocationDynamicState (장소 동적 상태)

`server/src/engine/hub/location-state.service.ts`

장소별 동적 상태(security, crime, unrest)를 관리한다.

- **초기값**: `locations.json`에 정의
- **변동**: ConsequenceProcessor가 판정 결과에 따라 업데이트
- **감쇠**: WorldTick에서 시간 경과 시 중립값으로 자동 감쇠
- **SituationGenerator Layer 1 입력**: 장소 상태가 임계치를 넘으면 랜드마크 이벤트 트리거

### NpcSchedule (시간대별 NPC 위치)

`server/src/engine/hub/npc-schedule.service.ts`

- NPC별 DAWN/DAY/DUSK/NIGHT 위치를 `npcs.json`의 `schedule` 필드에서 로드
- WorldTick 시간대 변경 시 NPC 위치 자동 업데이트
- 이벤트 매칭 시 현재 장소에 있는 NPC만 상호작용 대상으로 필터링
- Incident에 의한 임시 스케줄 오버라이드 지원

### NpcAgenda (NPC 장기 목표)

`server/src/engine/hub/npc-agenda.service.ts`

CORE/SUB NPC의 장기 목표를 자율적으로 진행한다.

- **Tick 진행**: 매 WorldTick에서 progress 자동 증가
- **플레이어 영향**: 판정 결과가 NPC agenda를 가속/차단 가능
- **Incident 트리거**: agenda 진행도가 임계치 도달 시 새 Incident spawn
- **SituationGenerator Layer 3 입력**: NPC agenda 상태가 상황 생성에 반영

### ConsequenceProcessor (판정 결과 → 세계 변화)

`server/src/engine/hub/consequence-processor.service.ts`

ResolveService 판정 결과를 WorldFact + LocationDynamicState에 반영한다.

- **판정 → Fact**: SUCCESS/PARTIAL/FAIL에 따라 서로 다른 Fact 생성
- **판정 → LocationState**: 전투/위협 행동은 security 감소, 도움 행동은 unrest 감소 등
- **파이프라인 위치**: ResolveService 직후, WorldDelta 이전에 실행

### SituationGenerator (3계층 상황 생성)

`server/src/engine/hub/situation-generator.service.ts`

EventMatcher보다 **우선 실행**되는 맥락적 상황 생성기.

| Layer | 이름 | 입력 | 예시 |
|-------|------|------|------|
| 1 | Landmark | LocationDynamicState | crime > 70이면 "밀수품 거래 현장 목격" |
| 2 | Incident-Driven | ActiveIncidents + WorldFact | 파업 사건 + 부두 위치 → "노동자 시위 조우" |
| 3 | World-State | NpcAgenda + Schedule + Fact | 마이렐 야간 순찰 + 부두 창고 → "경비대 수색 목격" |

- 3 Layer 순차 시도 → 유효한 상황 생성 시 반환, 모두 실패 시 null → EventMatcher fallback
- **Procedural Plot Protection**: arcRouteTag/commitmentDelta 생성 절대 금지

### PlayerGoal (플레이어 목표)

`server/src/engine/hub/player-goal.service.ts`

플레이어의 현재 추구 목표를 추적하고 진행도를 관리한다.

- **목표 등록**: 퀘스트 진행, Fact 발견, NPC 대화에서 자동/수동 등록
- **진행도 추적**: 관련 행동 수행 시 자동 업데이트
- **알림 연동**: NotificationAssembler에 목표 진행/완료 알림 전달
- **LLM 컨텍스트**: 현재 활성 목표를 LLM 프롬프트에 전달하여 서술 방향 유도

---

## Character Presets (캐릭터 프리셋 6종)

`content/graymar_v1/presets.json`

| 프리셋 | 이름 | 컨셉 | 핵심 스탯 | actionBonuses |
|-------|------|------|----------|---------------|
| DOCKWORKER | 부두 노동자 | 근접 탱커 | str14 con14 | FIGHT+1, THREATEN+1 |
| DESERTER | 탈영병 | 균형 전투가 | str11 dex10 wit9 | FIGHT+1, OBSERVE+1 |
| SMUGGLER | 밀수업자 | 은밀 특화 | dex14 cha12 | SNEAK+1, BRIBE+1 |
| HERBALIST | 약초상 | 아이템 활용 | wit15 per12 con10 | INVESTIGATE+1, HELP+1 |
| FALLEN_NOBLE | 몰락 귀족 | 사교/설득 | cha16 wit10 | PERSUADE+1, TRADE+1 |
| GLADIATOR | 떠돌이 검투사 | 최강 전투 | str14 dex12 con10 | FIGHT+1, OBSERVE+1 |

### 프리셋별 부가 데이터
각 프리셋은 다음 데이터를 포함한다:
- **npcPostureOverrides**: NPC 초기 태도 오버라이드 (특정 NPC와의 관계 사전 설정)
  - 예: DOCKWORKER → NPC_OWEN_KEEPER=FRIENDLY(+10 trust), DESERTER → NPC_GUARD_FELIX=HOSTILE(-15 trust)
- **actionBonuses**: 프리셋 고유 행동 보너스 (ResolveService baseMod에 반영)
- **protagonistTheme**: LLM 프롬프트에 전달되는 캐릭터 배경 텍스트
- **prologueHook**: 프롤로그에서 의뢰인이 건네는 대사 (프리셋별 차별화)

---

## Character Traits (캐릭터 특성 6종)

`content/graymar_v1/traits.json`

캐릭터 생성 시 1개 특성을 선택한다. 특성 효과는 `traitEffects`로 RunState에 저장되어 resolve/combat에서 참조된다.

| 특성 | 이름 | 핵심 효과 |
|------|------|----------|
| BATTLE_MEMORY | 전장의 기억 | FIGHT+1, THREATEN+1, MaxHP+10 |
| STREET_SENSE | 거리의 촉 | SNEAK+1, STEAL+1, OBSERVE+1, 초기골드+20 |
| SILVER_TONGUE | 타고난 언변 | PERSUADE+1, BRIBE+1, 전체 NPC trust+5 |
| GAMBLER_LUCK | 도박꾼의 운 | FAIL 판정 50% 확률로 PARTIAL 전환, 크리티컬 비활성화, 골드+30 |
| BLOOD_OATH | 피의 맹세 | HP 50% 이하 시 판정+2, 25% 이하 시 추가+1, MaxHP-20, 치유 50% 감소 |
| NIGHT_CHILD | 밤의 아이 | NIGHT 시간대 판정+2, DAY 시간대 판정-1, SNEAK+1 |

### 특성 런타임 처리
- **GAMBLER_LUCK**: ResolveService에서 FAIL 판정 시 50% 확률로 PARTIAL로 전환. 대신 크리티컬(대성공) 비활성화
- **BLOOD_OATH**: 현재 HP 비율에 따라 baseMod에 보너스 추가. 치유 아이템/효과 50% 감소
- **NIGHT_CHILD**: WorldState의 현재 시간대(TimePhaseV2)에 따라 baseMod 가감
- **actionBonuses 계열** (BATTLE_MEMORY, STREET_SENSE, SILVER_TONGUE): 프리셋의 actionBonuses와 합산되어 ResolveService baseMod에 반영

---

## Quest System (퀘스트 시스템)

`server/src/engine/hub/quest-progression.service.ts`
`server/src/engine/hub/quest-balance.config.ts`
`content/graymar_v1/quest.json`

### 6단계 퀘스트 전환

```
S0_ARRIVE → S1_GET_ANGLE → S2_FIND_EVIDENCE → S3_CHOOSE_SIDE → S4_CLIMAX → S5_RESOLUTION
```

`QuestProgressionService.checkTransition()`이 매 턴 호출되어 discoveredQuestFacts와 quest.json의 stateTransitions 조건을 비교한다. 한 번 호출에 **최대 1단계만 전환** (연쇄 전환 방지).

### FACT 발견 3경로

| 경로 | 조건 | 발견 확률 |
|------|------|----------|
| 이벤트 discoverableFact | SUCCESS/PARTIAL + 매칭 이벤트에 discoverableFact | SUCCESS=100%, PARTIAL=50% |
| NPC knownFacts | SUCCESS/PARTIAL + 정보성 행동 + 2단계 NPC 반응 판정 | trust에 따른 revealMode |
| WorldFact 태그 | FACT_ 프리픽스 태그가 worldFacts에 존재 | 자동 |

### discoveredQuestFacts 수집

`collectDiscoveredFacts()`가 3개 소스에서 FACT ID를 수집:
1. `runState.discoveredQuestFacts` (명시적 추적 필드)
2. `worldFacts` 태그에서 `FACT_` 프리픽스
3. NPC personalMemory에서 `FACT_` 매칭 (텍스트 기반 heuristic)

### questFactTrigger: SitGen 바이패스

미발견 `discoverableFact`가 있는 이벤트가 현재 장소에 존재하면, SituationGenerator를 건너뛰고 EventDirector로 직행하여 fact 이벤트 매칭을 보장한다. 미발견 fact 이벤트에는 weight +35 부스트가 적용된다.

### 밸런스 상수 외부화

`quest-balance.config.ts`의 `QUEST_BALANCE` 객체에서 핵심 상수를 관리한다.

| 상수 | 기본값 | 용도 |
|------|--------|------|
| SITGEN_CHANCE | 50 | SituationGenerator 실행 확률 (%) |
| PARTIAL_FACT_DISCOVERY_CHANCE | 50 | PARTIAL 판정 시 fact 발견 확률 (%) |
| UNDISCOVERED_FACT_WEIGHT_BOOST | 35 | 미발견 fact 이벤트 weight 부스트 |
| INCIDENT_PRESSURE_THRESHOLD | 50 | shouldMatchEvent: incident pressure 임계값 |
| ROUTING_SCORE_THRESHOLD | 40 | shouldMatchEvent: routing score 임계값 |
| DANGER_BLOCK_CHANCE | 40 | DANGER 상태 BLOCK 이벤트 삽입 확률 (%) |
| CRACKDOWN_BLOCK_CHANCE | 25 | ALERT 상태 BLOCK 이벤트 삽입 확률 (%) |
