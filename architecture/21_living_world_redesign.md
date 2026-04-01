# 21. Living World Redesign — 살아있는 세계 재설계

> **목표**: "사용자가 자유롭게 탐색하며 세계를 탐험하고 만들어나가는 게임"
> **범위**: 이벤트 시스템, 장소 시스템, NPC 시스템, 시간 시스템, 결과 지속성, 플레이어 목표 전면 재설계
> **원칙**: 기존 자산(29개 HUB 서비스, 전투 시스템, RNG, 메모리 v2) 최대 활용. 교체가 아닌 진화.

---

## Part 1. 비전과 원칙

### 1.1 핵심 비전

플레이어가 그레이마르 항구도시를 **자유롭게 돌아다니며**, 자신의 **의지로 목표를 정하고**, 행동의 **결과가 세계에 남아** 다음 상황을 만들어내는 게임.

"주크박스에서 곡을 뽑는 게임"이 아니라, "도시에서 살아가는 게임".

### 1.2 현재 시스템과의 차이

| 측면 | 현재 (v1) | 재설계 (v2) |
|------|-----------|-------------|
| 이벤트 | 112개 정적 이벤트 로테이션 | 세계 상태가 상황을 생성 |
| 장소 | 4개 고정, 독립적 | 6~8개, 상호 연결, 동적 상태 |
| NPC | 이벤트에 붙은 속성 | 장소에 존재하는 개체, 일정/목표 보유 |
| 시간 | DAY/NIGHT 표시용 | 세계가 시간에 따라 변화 |
| 결과 | 수치 변동 (gold, heat) | 사실(fact)로 누적, 세계 상태 변경 |
| 목표 | 시스템이 이벤트를 밀어넣음 | 플레이어가 목표를 세우고 추적 |
| 이동 | HUB→LOCATION→HUB 허브스포크 | 장소↔장소 직접 이동 가능 |

### 1.3 절대 보존 원칙 (기존 불변식 유지)

1. **Server is SoT** — 모든 판정/상태 변경은 서버에서만
2. **LLM은 서술만** — 게임 결과에 영향 없음, 실패해도 진행
3. **턴제 구조** — 입력→판정→서술 사이클 유지
4. **RNG 결정성** — seed+cursor 완전 재현
5. **멱등성** — (runId, turnNo) + idempotencyKey 이중 유니크
6. **Action Slot Cap = 3** — 전투 규칙 불변
7. **LOCATION 판정 = 1d6 + floor(stat/3) + baseMod** — 판정 공식 불변
8. **Theme Memory (L0) 불변** — 토큰 압박에도 삭제 금지

---

## Part 2. 기존 자산 분류

### 2.1 그대로 유지 (변경 없음)

| 자산 | 이유 |
|------|------|
| RNG (splitmix64) | 완전 결정적, 안정적 |
| 전투 시스템 (d20, distance/angle) | 잘 설계됨, 전투는 그대로 |
| DB 스키마 (10 tables, Drizzle ORM) | JSONB 유연성으로 확장 가능 |
| LLM 파이프라인 (8 services) | Context Builder, Token Budget 안정적 |
| Structured Memory v2 | visitLog, npcJournal, incidentChronicle 완성도 높음 |
| Narrative Mark (12개) | 불가역 표식, 변경 불필요 |
| Signal Feed (5채널) | 채널 구조 유지, 생성 로직만 확장 |

### 2.2 확장 (기존 구조에 필드/로직 추가)

| 자산 | 확장 내용 |
|------|----------|
| WorldState | locationStates 동적화, npcLocations 추가, worldFacts 추가 |
| NPC Emotional (5축) | schedule, longTermAgenda, currentLocation 추가 |
| Incident System | 사건 간 인과관계, NPC 연루, 자동 체인 |
| IntentParserV2 | 골드 명시 파싱 (이미 완료), 장소/NPC 타겟 정밀화 |
| ResolveService | computeGoldCost에 specifiedGold 반영 (이미 완료) |
| RewardsService | 행동 기반 골드 (이미 완료) |

### 2.3 재설계 (구조 변경)

| 자산 | 변경 내용 |
|------|----------|
| EventMatcher 6단계 | → SituationGenerator로 교체 (세계 상태 → 상황 생성) |
| HUB→LOCATION 허브스포크 | → 장소↔장소 자유 이동 |
| Node 시스템 (COMBAT/EVENT/...) | → LOCATION이 기본, COMBAT은 서브노드로 유지 |
| 112개 정적 이벤트 | → 시드 이벤트(랜드마크) + 동적 상황 생성 |
| SceneShell 선택지 생성 | → 장소 상태 기반 동적 선택지 |

---

## Part 3. 7대 핵심 시스템 재설계

### System 1: Living Location (살아있는 장소)

#### 1.1 개념

장소는 고정된 이벤트 풀이 아니라, **자체 상태를 가진 동적 공간**.
플레이어가 방문하든 안 하든 장소의 상태는 변한다.

#### 1.2 LocationState (장소별 동적 상태)

```typescript
interface LocationState {
  locationId: string;

  // 세력 통제
  controllingFaction: FactionId | null;  // 현재 통제 세력
  controlStrength: number;               // 0~100 (낮으면 분쟁 중)
  contestedBy?: FactionId;               // 통제권 도전 세력

  // 환경
  security: number;      // 0~100 (치안 수준)
  prosperity: number;    // 0~100 (경제 활성도)
  unrest: number;        // 0~100 (민심 불안)

  // 현재 상황
  activeConditions: LocationCondition[];  // 예: 'CURFEW', 'MARKET_DAY', 'RAID_AFTERMATH'
  presentNpcs: string[];                  // 현재 이 장소에 있는 NPC 목록

  // 이력
  recentEvents: string[];   // 최근 5개 발생 사건 (중복 방지용)
  playerVisitCount: number; // 플레이어 방문 횟수
  lastVisitTurn: number;    // 마지막 방문 턴
}
```

#### 1.3 LocationCondition (장소 조건)

```typescript
interface LocationCondition {
  id: string;           // 'CURFEW', 'FESTIVAL', 'LOCKDOWN', 'BLACK_MARKET' 등
  source: string;       // 발생 원인 (incidentId, npcAction, playerAction)
  startTurn: number;
  duration: number;     // -1 = 영구 (해제 조건 별도)
  effects: {
    securityMod: number;     // security에 가산
    prosperityMod: number;
    unrestMod: number;
    blockedActions?: string[];  // 이 장소에서 불가능한 행동
    boostedActions?: string[]; // 이 장소에서 유리한 행동
  };
}
```

#### 1.4 장소 확장 (4개 → 7개)

| ID | 이름 | 특성 | 기본 통제 |
|----|------|------|----------|
| LOC_MARKET | 중앙 시장 | 상업, 정보, 만남 | MERCHANT_CONSORTIUM |
| LOC_GUARD | 경비대 초소 | 질서, 감시, 권력 | CITY_GUARD |
| LOC_HARBOR | 항만 부두 | 밀수, 노동, 외부 | LABOR_GUILD |
| LOC_SLUMS | 빈민가 | 범죄, 은신, 저항 | (무통제) |
| LOC_NOBLE | 상류 거리 | 귀족, 정치, 음모 | ARCANE_SOCIETY |
| LOC_TAVERN | 잠긴 닻 선술집 | 거점, 휴식, 정보 교환 | (중립) |
| LOC_DOCKS_WAREHOUSE | 항만 창고구 | 밀수, 은닉, 거래 | (분쟁) |

#### 1.5 장소 간 직접 이동

```
기존: HUB ←→ LOCATION (허브스포크)
변경: LOCATION ←→ LOCATION (자유 이동)

LOC_TAVERN (거점/휴식)
  ↕
LOC_MARKET ←→ LOC_NOBLE
  ↕              ↕
LOC_HARBOR ←→ LOC_GUARD
  ↕
LOC_DOCKS_WAREHOUSE ←→ LOC_SLUMS
```

**이동 규칙:**
- 인접 장소로 1턴 이동 (MOVE_LOCATION)
- 비인접 장소는 2턴 (경유)
- 특정 조건에서 지름길 발견 가능 (fact 기반)
- CURFEW 등 조건에 의해 이동 제한 가능
- LOC_TAVERN은 모든 장소와 인접 (거점 역할, 기존 HUB 대체)

**기존 HUB의 역할 변화:**
- HUB 노드 → LOC_TAVERN으로 통합
- Heat 해결 (CONTACT_ALLY, PAY_COST) → LOC_TAVERN에서 가능
- 퀘스트 수락 → LOC_TAVERN에서 NPC 대화로 자연스럽게

---

### System 2: NPC Presence (NPC 존재감)

#### 2.1 개념

NPC는 이벤트의 속성이 아니라, **세계에 존재하는 개체**.
자기 일정이 있고, 자기 목표가 있고, 플레이어와 독립적으로 움직인다.

#### 2.2 NPC Schedule (일정)

```typescript
interface NpcSchedule {
  // 기본 일정 (시간대별 위치)
  default: Record<TimePhaseV2, {
    locationId: string;
    activity: string;        // "상점 운영", "순찰", "밀회"
    interactable: boolean;   // 플레이어와 상호작용 가능 여부
  }>;

  // 조건부 일정 변경
  overrides: Array<{
    condition: string;       // "incident.INC_SMUGGLING.stage >= 2"
    schedule: Partial<Record<TimePhaseV2, { locationId: string; activity: string }>>;
  }>;
}
```

**예시 — 강채린 (항만 관리인):**
```json
{
  "default": {
    "DAWN": { "locationId": "LOC_HARBOR", "activity": "입항 기록 검토", "interactable": true },
    "DAY": { "locationId": "LOC_HARBOR", "activity": "하역 감독", "interactable": true },
    "DUSK": { "locationId": "LOC_TAVERN", "activity": "선술집에서 식사", "interactable": true },
    "NIGHT": { "locationId": "LOC_DOCKS_WAREHOUSE", "activity": "밀수품 확인", "interactable": false }
  },
  "overrides": [
    {
      "condition": "incident.INC_SMUGGLING.stage >= 2",
      "schedule": {
        "NIGHT": { "locationId": "LOC_HARBOR", "activity": "야간 감시 강화" }
      }
    }
  ]
}
```

#### 2.3 NPC Long-Term Agenda (장기 목표)

```typescript
interface NpcAgenda {
  npcId: string;
  currentGoal: string;           // "밀수 조직 확장", "경비대 내부 부패 조사"
  stages: Array<{
    stage: number;
    description: string;
    triggerCondition: string;     // "day >= 5 AND controlStrength.LOC_HARBOR < 50"
    onTrigger: {
      worldEffect: WorldEffect;  // 세계에 미치는 영향
      signalEmit?: SignalFeedItem;  // 시그널 발생
      conditionApply?: LocationCondition; // 장소 조건 적용
    };
    blockedBy?: string;          // 다른 NPC/사건이 막고 있는 조건
  }>;
  currentStage: number;
  completed: boolean;
}
```

**예시 — 마르코 (밀수업자):**
```
Stage 0: 소규모 밀수 유지 (기본)
Stage 1: day >= 3 → 창고구에 비밀 거래소 개설 (LOC_DOCKS_WAREHOUSE에 BLACK_MARKET 조건 추가)
Stage 2: day >= 7 AND security.LOC_HARBOR < 40 → 대규모 밀수 시도 (Incident 자동 spawn)
Stage 3: INC_SMUGGLING resolved → 결과에 따라 도주/체포/확장
```

#### 2.4 NPC 위치 추적

매 턴(WorldTick) 시:
1. 현재 timePhaseV2에 따라 각 NPC의 위치 계산
2. override 조건 체크 → 일정 변경 반영
3. `locationState.presentNpcs` 업데이트
4. 플레이어와 같은 장소에 있는 NPC → 상호작용 가능

**"어제 만난 대장장이를 다시 찾아가기"가 가능해짐.**

#### 2.5 NPC 간 자동 상호작용

```typescript
interface NpcInteraction {
  npcA: string;
  npcB: string;
  condition: string;          // "같은 장소 + 같은 시간대"
  frequency: 'ALWAYS' | 'SOMETIMES' | 'RARE';
  effect: {
    emotionalDelta: Partial<Record<string, number>>;  // 감정 변화
    signalChance?: number;     // 시그널 발생 확률
    factGenerate?: string;     // 사실 생성 (예: "마르코와 강채린이 논쟁했다")
  };
}
```

NPC끼리 같은 장소에 있으면 자동으로 상호작용이 발생하고, 그 결과가 Signal로 플레이어에게 전달될 수 있음.

---

### System 3: World Facts (세계 사실 시스템)

#### 3.1 개념

플레이어의 행동과 세계의 변화가 **사실(fact)**로 누적된다.
fact는 수치가 아니라 **서술적 진실**이며, 이후 상황 생성의 재료가 된다.

#### 3.2 WorldFact 구조

```typescript
interface WorldFact {
  id: string;                    // "fact_helped_marco_day3"
  category: FactCategory;        // PLAYER_ACTION | NPC_ACTION | WORLD_CHANGE | DISCOVERY
  text: string;                  // "플레이어가 마르코의 밀수를 도왔다"
  locationId: string;            // 발생 장소
  involvedNpcs: string[];        // 관련 NPC
  turnCreated: number;           // 생성 턴
  dayCreated: number;            // 생성 일자
  tags: string[];                // ['smuggling', 'marco', 'harbor', 'helped']

  // 영향도
  impact: {
    reputationChanges?: Record<string, number>;
    locationEffects?: Partial<LocationState>;
    npcKnowledge?: Record<string, string>;  // NPC가 이 사실을 알고 있는지
  };

  // 수명
  expiry?: number;               // 특정 턴 후 "잊혀짐" (선택적)
  permanent: boolean;            // true면 영구 보존
}

type FactCategory =
  | 'PLAYER_ACTION'    // 플레이어가 한 행동
  | 'NPC_ACTION'       // NPC가 한 행동 (off-screen 포함)
  | 'WORLD_CHANGE'     // 세계 상태 변화 (세력 교체, 조건 변경)
  | 'DISCOVERY'        // 플레이어가 발견한 정보
  | 'RELATIONSHIP';    // 관계 변화 사건
```

#### 3.3 Fact 생성 시점

| 시점 | 생성되는 Fact 예시 |
|------|-------------------|
| 판정 SUCCESS/PARTIAL/FAIL | "시장에서 경비병을 협박하여 정보를 얻었다" |
| NPC agenda stage 진행 | "마르코가 창고구에 비밀 거래소를 열었다" |
| Incident 상태 변화 | "밀수 조직 사건이 2단계로 확대되었다" |
| 장소 조건 변경 | "경비대 초소에 야간통행금지가 선포되었다" |
| NPC 간 상호작용 | "강채린과 마르코가 항만에서 대립했다" |
| 플레이어 이동 | "플레이어가 처음으로 상류 거리를 방문했다" (DISCOVERY) |

#### 3.4 Fact의 활용

1. **상황 생성의 재료** — SituationGenerator가 관련 fact를 참조하여 상황 구성
2. **NPC 대화 반영** — NPC가 아는 fact를 대화에 반영 (LLM 컨텍스트)
3. **선택지 생성** — fact에 따라 새로운 선택지 해금 ("마르코를 도왔으므로 밀수 정보 접근 가능")
4. **조건 평가** — 이벤트/Incident 조건에 fact 존재 여부 사용
5. **엔딩 반영** — 누적된 fact가 엔딩 서술의 재료

#### 3.5 Fact와 기존 시스템 연결

| 기존 시스템 | Fact 연결 |
|------------|----------|
| StructuredMemory.visitLog | → Fact 자동 생성 (방문 요약에서 추출) |
| StructuredMemory.npcJournal | → NPC 관련 Fact 교차 참조 |
| SignalFeed | → Fact에서 시그널 자동 파생 |
| NarrativeMark | → Mark 부여 시 영구 Fact 생성 |
| Incident | → 사건 진행마다 Fact 생성 |

---

### System 4: Situation Generator (상황 생성기)

#### 4.1 개념

기존 EventMatcher(112개 정적 이벤트에서 선택)를 대체.
**세계의 현재 상태에서 상황을 생성**한다.

#### 4.2 상황 생성 파이프라인

```
[세계 상태 수집]
  → LocationState (현재 장소의 security/prosperity/unrest/conditions/presentNpcs)
  → WorldFacts (최근 + 관련 facts)
  → NPC states (현재 장소에 있는 NPC의 감정/agenda)
  → Incident context (활성 사건의 stage/pressure)
  → Player history (최근 행동 패턴)
  → Time context (시간대, 날짜)

[상황 결정 (3계층)]
  Layer 1: Landmark Event (정적, 스토리 체크포인트)
    → 조건 충족 시 무조건 발동 (arc_events, quest progression)
    → 기존 ARC_HINT, CHECKPOINT 이벤트 유지

  Layer 2: Incident-Driven Situation (반동적)
    → 활성 Incident가 있고, 현재 장소/NPC가 관련되면
    → Incident 맥락에서 상황 생성
    → 기존 IncidentRouter 확장

  Layer 3: World-State Situation (완전 동적)
    → Layer 1, 2에 해당 없으면
    → LocationState + presentNpcs + WorldFacts + timePhase 조합
    → 상황 동적 생성

[선택지 구성]
  → 장소에 있는 NPC 기반
  → LocationCondition 기반 (CURFEW면 SNEAK 선택지 등)
  → 플레이어 이전 행동 기반 (fact 참조)
```

#### 4.3 Layer 3 상세: World-State Situation 생성

```typescript
interface SituationSeed {
  // 무엇이 일어나고 있는가
  trigger: SituationTrigger;    // NPC_ACTIVITY | ENVIRONMENTAL | CONSEQUENCE | DISCOVERY

  // 누가 관련되는가
  primaryNpc?: string;          // 현재 장소에 있는 NPC
  secondaryNpc?: string;

  // 왜 일어나는가
  cause: string;                // WorldFact id 또는 LocationCondition id

  // 플레이어가 할 수 있는 것
  affordances: IntentActionType[];

  // 장면 설명 (LLM에 전달)
  sceneFrame: string;
}

type SituationTrigger =
  | 'NPC_ACTIVITY'      // NPC가 뭔가 하고 있음 (schedule 기반)
  | 'NPC_CONFLICT'      // NPC 간 대립 (같은 장소에 적대 NPC)
  | 'ENVIRONMENTAL'     // 장소 조건에서 파생 (CURFEW, FESTIVAL 등)
  | 'CONSEQUENCE'       // 이전 fact의 결과 (복수, 보답, 소문 확산)
  | 'DISCOVERY'         // 새로운 정보/장소/비밀 발견
  | 'OPPORTUNITY'       // 일시적 기회 (시간대/조건 한정)
  | 'ROUTINE'           // 일상적 장면 (NPC 활동 관찰);
```

#### 4.4 예시: 상황 생성 시나리오

**상태:**
- 장소: LOC_HARBOR, 시간: DUSK
- presentNpcs: ['NPC_MARCO', 'NPC_MAIREL']
- fact 존재: "플레이어가 마르코의 밀수를 도왔다" (3턴 전)
- LocationCondition: 없음
- Incident: INC_SMUGGLING stage 1

**Layer 2 (Incident-Driven) 발동:**
```
trigger: NPC_CONFLICT
primaryNpc: NPC_MAIREL (항만 관리인 - 밀수 단속 중)
secondaryNpc: NPC_MARCO (밀수업자 - 플레이어가 도운 적 있음)
cause: INC_SMUGGLING stage 1 + fact "플레이어가 마르코를 도왔다"
sceneFrame: "강채린이 해질녘 부두에서 마르코를 추궁하고 있다.
             마르코가 플레이어 쪽을 힐끗 본다 — 도움을 기대하는 눈빛."
affordances: [PERSUADE, THREATEN, SNEAK, OBSERVE, HELP, FIGHT]
```

**플레이어 선택에 따른 분기:**
- HELP (마르코 편) → fact "강채린 앞에서 마르코를 감쌌다" → 강채린 suspicion↑, 마르코 trust↑
- PERSUADE (중재) → fact "밀수 건을 중재하려 했다" → 양쪽 respect↑
- OBSERVE (관망) → fact "마르코와 강채린의 대립을 지켜봤다" → 정보 획득
- THREATEN (강채린 편) → fact "마르코를 위협했다" → 마르코 fear↑, 강채린 trust↑

**각 결과가 fact로 남고, 다음 방문 시 상황에 영향.**

#### 4.5 기존 이벤트(112개)의 역할 변경

| 기존 역할 | 변경 후 역할 |
|----------|-------------|
| ENCOUNTER (45개) | → SituationSeed의 **템플릿** (sceneFrame, affordances 참조용) |
| OPPORTUNITY (16개) | → Layer 3의 OPPORTUNITY trigger 시 참조 |
| RUMOR (6개) | → Signal 시스템으로 통합 (fact 기반 자동 생성) |
| AMBUSH (6개) | → Incident-Driven 또는 CONSEQUENCE trigger |
| FALLBACK (4개) | → ROUTINE trigger (일상 장면) |
| ARC_HINT (4개) | → Layer 1 Landmark Event (그대로 유지) |
| FACTION (3개) | → Incident-Driven |
| CHECKPOINT (2개) | → LocationCondition 기반 |
| SHOP (2개) | → LOC_MARKET/LOC_TAVERN의 ROUTINE |

**112개 이벤트를 버리지 않고, 상황 생성의 재료/템플릿으로 재활용.**

---

### System 5: Time & World Tick (시간과 세계 진행)

#### 5.1 개념

시간이 흐르면 세계가 변한다. 플레이어가 행동하지 않아도 NPC는 움직이고, 사건은 진행되고, 장소 상태는 변한다.

#### 5.2 WorldTick 확장

**현재 WorldTick (world-tick.service.ts):**
- globalClock 증가, timePhaseV2 전환
- Incident deadline 체크
- DeferredEffect 발동

**확장:**

```typescript
// 매 턴 실행되는 WorldTick 파이프라인
worldTick(ws: WorldState, turnNo: number): WorldTickResult {
  // 1. 시간 진행 (기존)
  advanceGlobalClock(ws);

  // 2. NPC 위치 업데이트 (신규)
  updateNpcLocations(ws);

  // 3. NPC Agenda 진행 (신규)
  const agendaResults = tickNpcAgendas(ws);
  // → stage 조건 체크 → 충족 시 WorldEffect 적용 + Fact 생성

  // 4. NPC 간 상호작용 (신규)
  const interactionResults = tickNpcInteractions(ws);
  // → 같은 장소에 있는 NPC 쌍 → 감정 변화 + Fact 생성

  // 5. LocationState 업데이트 (신규)
  updateLocationStates(ws);
  // → activeConditions 만료 체크
  // → security/prosperity/unrest 자연 회귀
  // → NPC agenda 결과 반영

  // 6. Incident 진행 (기존 + 확장)
  tickIncidents(ws);
  // → pressure 자동 증가
  // → NPC agenda와 연동 (NPC가 사건에 기여)

  // 7. Signal 생성 (기존 + 확장)
  generateSignals(ws, agendaResults, interactionResults);
  // → NPC 행동에서 시그널 파생
  // → 장소 변화에서 시그널 파생

  // 8. Fact 정리 (신규)
  pruneExpiredFacts(ws);
}
```

#### 5.3 시간 체감

| 시간 단위 | 게임 내 효과 |
|----------|-------------|
| 1턴 | 행동 1회, NPC 위치 고정 |
| 1 phase (3턴) | DAWN→DAY→DUSK→NIGHT, NPC 위치 변경 |
| 1일 (12턴) | NPC agenda 체크, LocationCondition 만료 체크 |
| 3일 | Incident stage 자동 진행 가능, 상점 재고 갱신 |
| 7일 | 세력 통제도 변동, 주요 NPC 행동 완료 |

#### 5.4 부재 효과 (Away Effect)

플레이어가 특정 장소를 오래 방문하지 않으면:

```typescript
// 장소 미방문 시 자연 변화
if (turnsSinceLastVisit > 12) {  // 1일 이상
  // security는 통제 세력 기본값으로 회귀
  locationState.security += (baseSecurity - locationState.security) * 0.1;

  // NPC agenda는 계속 진행
  // → "안 간 사이에 마르코가 거래소를 열었다" (fact 생성)

  // Incident는 deadlineClock 기반 진행
}
```

---

### System 6: Player-Driven Goals (플레이어 주도 목표)

#### 6.1 개념

시스템이 이벤트를 밀어넣는 것이 아니라, 플레이어가 자기 목표를 세우고 추적한다.
목표는 명시적(NPC 대화에서 수락)이거나 암시적(행동 패턴에서 추론).

#### 6.2 PlayerGoal 구조

```typescript
interface PlayerGoal {
  id: string;
  type: 'EXPLICIT' | 'IMPLICIT';

  // EXPLICIT: NPC 의뢰, 발견한 단서 추적 등
  // IMPLICIT: 행동 패턴에서 추론 (기존 IntentMemory 확장)

  description: string;         // "밀수 조직의 배후를 밝혀라"
  relatedNpcs: string[];
  relatedLocations: string[];
  relatedFacts: string[];      // 관련 WorldFact ids

  // 진행도
  progress: number;            // 0~100
  milestones: Array<{
    description: string;
    completed: boolean;
    factRequired: string;      // 이 fact가 생기면 달성
  }>;

  // 보상
  rewards?: {
    reputationChanges: Record<string, number>;
    goldRange: [number, number];
    unlocks?: string[];        // 새로운 장소/NPC/능력 해금
  };
}
```

#### 6.3 목표 생성 경로

**명시적 목표 (EXPLICIT):**
- NPC 대화에서 의뢰 수락 → "강채린이 밀수 증거를 찾아달라고 했다"
- 이벤트 선택지에서 파생 → "비밀 문서를 발견했다, 추적하겠다"
- 플레이어 직접 선언 → "나는 경비대를 돕겠다" (IntentParser가 감지)

**암시적 목표 (IMPLICIT):**
- 기존 IntentMemory의 패턴 감지 확장
  - STEALTH 행동 반복 → "은밀 활동 성향" 목표 생성
  - 특정 NPC 반복 방문 → "NPC_X 관계 심화" 목표 생성
  - 특정 장소 집중 탐색 → "LOC_X 장악" 목표 생성

#### 6.4 목표와 상황 생성의 연결

SituationGenerator가 플레이어의 활성 목표를 참조:
- 관련 NPC가 있는 장소 방문 시 → 목표 관련 상황 우선 생성
- 목표 milestone 달성 조건에 가까우면 → 기회/도전 상황 생성
- 목표 무시하고 다른 행동 시 → 목표 관련 사건이 알아서 진행 (NPC agenda)

**"시스템이 끌고 가는 것이 아니라, 플레이어가 하고 싶은 것을 세계가 반응하는 것."**

---

### System 7: Consequence Chain (결과의 연쇄)

#### 7.1 개념

모든 판정 결과는 즉각적 효과(수치 변동) + 지연된 결과(fact → 후속 상황)를 가진다.
결과가 결과를 낳고, 세계가 플레이어의 발자취로 변해간다.

#### 7.2 결과 전파 경로

```
플레이어 행동
  → 즉각 효과 (기존: gold/heat/reputation/relation 변동)
  → WorldFact 생성 (신규)
  → LocationState 변경 (신규: 장소 조건 추가/제거)
  → NPC 반응 (신규: agenda 조정, 다른 NPC에게 정보 전달)
  → Signal 발생 (기존 + 확장)
  → 후속 상황의 재료가 됨 (다음 턴 SituationGenerator)
```

#### 7.3 NPC 기억과 반응

```typescript
// NPC가 아는 fact
interface NpcKnowledge {
  npcId: string;
  knownFacts: Array<{
    factId: string;
    learnedTurn: number;
    source: 'WITNESSED' | 'HEARD_FROM_NPC' | 'HEARD_RUMOR';
  }>;
}
```

**전파 규칙:**
- NPC가 직접 목격 → 즉시 인지 (WITNESSED)
- 같은 세력 NPC → 1일 후 전파 (HEARD_FROM_NPC)
- Signal RUMOR 채널 → 확률적 전파 (HEARD_RUMOR)

**결과:**
- "시장에서 경비병을 협박했다" → 경비대 NPC가 모두 인지 (1일 후)
- 다음에 경비대 초소 방문 시 → 적대적 상황 생성

#### 7.4 예시: 결과 연쇄 시나리오

```
Turn 5: 플레이어가 항만에서 마르코의 밀수를 도움 (HELP, SUCCESS)
  → fact: "player_helped_marco_smuggling" (permanent)
  → 마르코 trust +15, 강채린 suspicion +10
  → Signal: RUMOR "항만에서 수상한 움직임이 있었다"

Turn 8: 강채린이 fact를 인지 (같은 항만, WITNESSED)
  → 강채린 agenda 조정: "밀수 조사 가속"
  → 강채린 schedule 변경: NIGHT에 창고구 감시

Turn 12: 플레이어가 항만 방문 (DAY)
  → SituationGenerator:
    - presentNpcs: [강채린, 마르코]
    - 관련 facts: ["player_helped_marco", "채린이 밀수 조사 가속"]
    - → NPC_CONFLICT 상황: "강채린이 플레이어에게 마르코와의 관계를 추궁한다"

Turn 15: 강채린 agenda stage 2 달성 (day >= 7)
  → 경비대 초소에 LOCKDOWN 조건 적용
  → fact: "강채린이 항만 전면 수색을 명령했다"
  → LOC_HARBOR: security +30, prosperity -20
  → Signal: SECURITY "경비대가 항만을 봉쇄했다"

  → 다음에 항만 방문 시: 완전히 다른 상황 (봉쇄된 항만)
```

---

## Part 4. 데이터 흐름 (신규 턴 파이프라인)

### 4.1 LOCATION 턴 처리 (v2)

```
1. 입력 수신 (ACTION/CHOICE)
   ↓
2. IntentParserV2 (기존) → ParsedIntentV2 + specifiedGold
   ↓
3. IntentV3Builder (기존) → goalCategory + approachVector
   ↓
4. ── 신규 ── SituationGenerator
   │  입력: LocationState, presentNpcs, WorldFacts, Incidents, PlayerGoals
   │  Layer 1: Landmark Event 체크
   │  Layer 2: Incident-Driven 체크
   │  Layer 3: World-State Situation 생성
   │  출력: Situation (sceneFrame, affordances, primaryNpc)
   ↓
5. ResolveService (기존, 변경 없음)
   │  1d6 + floor(stat/3) + baseMod → SUCCESS/PARTIAL/FAIL
   ↓
6. ── 신규 ── ConsequenceProcessor
   │  즉각 효과: gold/heat/reputation/relation (기존)
   │  WorldFact 생성 (신규)
   │  LocationState 업데이트 (신규)
   │  NPC 반응 처리 (신규)
   │  PlayerGoal 진행도 체크 (신규)
   ↓
7. WorldTick 확장 (기존 + NPC 위치/agenda/상호작용)
   ↓
8. MemoryCollector (기존) + Fact 저장 (신규)
   ↓
9. LLM 비동기 호출 (기존, 변경 없음)
   │  Context에 WorldFacts, NPC knowledge 추가
   ↓
10. Turn Commit (기존)
```

### 4.2 장소 이동 처리 (v2)

```
MOVE_LOCATION 감지
  ↓
이동 가능성 체크
  → 인접 장소? (1턴)
  → 비인접? (2턴, 경유)
  → 이동 제한 조건? (CURFEW, LOCKDOWN → SNEAK 판정 필요)
  ↓
현재 장소 이탈
  → memoryIntegration.finalizeVisit() (기존)
  → LocationState.lastVisitTurn 기록
  ↓
이동 턴 생성 (기존 SYSTEM 턴)
  → 이동 중 이벤트 가능 (조건: Heat ≥ 60, DANGER 구간)
  ↓
목적지 장소 진입
  → LocationState.presentNpcs 확인
  → SceneShell 생성 (시간대 + 안전도 + LocationConditions)
  → SituationGenerator 호출 (도착 즉시 상황 생성)
```

---

## Part 5. 콘텐츠 확장 요구사항

### 5.1 locations.json 확장

```json
{
  "LOC_NOBLE": {
    "name": "상류 거리",
    "description": "귀족들의 저택과 정원이 늘어선 조용한 거리",
    "adjacentLocations": ["LOC_MARKET", "LOC_GUARD"],
    "baseState": {
      "controllingFaction": "ARCANE_SOCIETY",
      "security": 80, "prosperity": 90, "unrest": 10
    },
    "affordanceBias": ["PERSUADE", "OBSERVE", "SNEAK", "BRIBE"],
    "discoveryThreshold": 3
  }
}
```

### 5.2 npcs.json 확장 (11명 → 15~18명)

기존 11명 유지 + 추가:
- LOC_NOBLE 관련 NPC 2~3명 (귀족, 하인, 정보원)
- LOC_TAVERN 관련 NPC 1~2명 (주인장, 단골)
- LOC_DOCKS_WAREHOUSE 관련 NPC 1~2명 (창고지기, 밀수꾼)
- 떠돌이 NPC 1명 (여러 장소 순회)

각 NPC에 schedule + longTermAgenda 필수 추가.

### 5.3 incidents.json 확장 (2개 → 8~10개)

| Incident | 장소 | 연결 |
|----------|------|------|
| INC_SMUGGLING_RING | LOC_HARBOR | 기존 |
| INC_GUARD_CORRUPTION | LOC_GUARD | 기존 |
| INC_MERCHANT_MONOPOLY | LOC_MARKET | 신규: 상인 독점 |
| INC_NOBLE_CONSPIRACY | LOC_NOBLE | 신규: 귀족 음모 |
| INC_LABOR_STRIKE | LOC_HARBOR | 신규: 노동자 파업 |
| INC_SLUM_UPRISING | LOC_SLUMS | 신규: 빈민가 봉기 |
| INC_ARCANE_EXPERIMENT | LOC_NOBLE | 신규: 비밀 실험 |
| INC_TAVERN_INTRIGUE | LOC_TAVERN | 신규: 정보전 |

**사건 간 인과관계 예시:**
```
INC_SMUGGLING_RING ESCALATED → INC_GUARD_CORRUPTION pressure +20
INC_LABOR_STRIKE CONTAINED → INC_MERCHANT_MONOPOLY pressure -10
INC_NOBLE_CONSPIRACY stage 2 → INC_GUARD_CORRUPTION spawn (경비대에 압력)
```

### 5.4 events_v2.json 역할 변경

112개 기존 이벤트를 삭제하지 않고 **SituationTemplate**으로 재분류:

```json
{
  "templateId": "TPL_MARKET_MERCHANT_DISPUTE",
  "basedOn": "EVT_MARKET_ENC_STALL",
  "trigger": "NPC_CONFLICT",
  "requiredNpcRoles": ["merchant", "customer_or_rival"],
  "sceneFrameTemplate": "{{primaryNpc.name}}이(가) {{secondaryNpc.name}}과(와) {{location.name}}에서 {{cause}}로 인해 대립하고 있다.",
  "affordances": ["PERSUADE", "THREATEN", "OBSERVE", "HELP", "TRADE"],
  "outcomeEffects": {
    "SUCCESS": { "factTemplate": "{{player}}가 분쟁을 해결했다" },
    "PARTIAL": { "factTemplate": "{{player}}가 분쟁에 개입했으나 미해결" },
    "FAIL": { "factTemplate": "{{player}}의 개입이 상황을 악화시켰다" }
  }
}
```

---

## Part 6. 구현 전략 (Phase 계획)

### Phase A: Foundation (기반, 2~3주)

**목표:** 핵심 데이터 구조 추가, 기존 기능 유지

1. **WorldState 타입 확장**
   - `worldFacts: WorldFact[]` 필드 추가
   - `locationStates` 구조 확장 (controllingFaction, conditions 등)
   - `npcLocations: Record<npcId, string>` 추가

2. **LocationState 서비스** (신규)
   - `LocationStateService` — 장소 상태 관리, 조건 추가/제거/만료

3. **WorldFact 서비스** (신규)
   - `WorldFactService` — fact CRUD, 태그 검색, 만료 관리

4. **NPC Schedule 적용**
   - npcs.json에 schedule 필드 추가
   - WorldTick에서 NPC 위치 업데이트 로직 추가

5. **콘텐츠 확장**
   - locations.json: 3개 장소 추가 + adjacency 정의
   - npcs.json: 5~7명 NPC 추가 + schedule

**검증:** 기존 플레이테스트 통과 (기존 기능 불변)

### Phase B: Living World (살아있는 세계, 3~4주)

**목표:** NPC가 움직이고, 장소가 변하고, 결과가 남는다

1. **NPC Agenda 시스템**
   - `NpcAgendaService` — agenda stage 진행, WorldEffect 적용
   - npcs.json에 longTermAgenda 추가

2. **ConsequenceProcessor** (신규)
   - 판정 결과 → WorldFact 생성 + LocationState 변경
   - 기존 WorldState 업데이트 로직 래핑

3. **WorldTick 확장**
   - NPC agenda tick
   - NPC 간 상호작용 tick
   - LocationState 자연 회귀
   - Fact 기반 Signal 생성

4. **장소 간 직접 이동**
   - MOVE_LOCATION에서 목표 장소 감지 → 직접 이동
   - LOC_TAVERN ↔ 각 장소 인접 관계

5. **콘텐츠 확장**
   - incidents.json: 6~8개 추가 + 인과관계
   - NPC agenda 데이터

**검증:** "3일간 플레이하면 세계가 변했다" 체감 테스트

### Phase C: Dynamic Situations (동적 상황, 3~4주)

**목표:** 정적 이벤트 로테이션 → 동적 상황 생성

1. **SituationGenerator** (EventMatcher 대체)
   - Layer 1: Landmark (기존 arc_events 유지)
   - Layer 2: Incident-Driven (기존 IncidentRouter 확장)
   - Layer 3: World-State (신규)

2. **SituationTemplate** 시스템
   - 기존 112개 이벤트를 템플릿으로 변환
   - NPC 슬롯, 조건부 분기 추가

3. **PlayerGoal** 시스템
   - 명시적/암시적 목표 관리
   - 목표와 상황 생성 연결

4. **LLM Context 확장**
   - WorldFacts를 L2 nodeFacts에 추가
   - NPC knowledge를 대화 컨텍스트에 반영

**검증:** "같은 장소를 방문해도 매번 다른 상황" 플레이테스트

### Phase D: Polish & Balance (조율, 2~3주)

1. 상황 생성 밸런스 조정
2. NPC agenda 속도 조율
3. Fact 생성/만료 주기 최적화
4. 엔딩 시스템에 WorldFacts/PlayerGoals 반영
5. 종합 플레이테스트 10+ 세션

---

## Part 7. 기존 서비스 매핑 (변경/유지/신규)

### 유지 (변경 없음)

| 서비스 | 이유 |
|--------|------|
| RngService | 완전 결정적 |
| ResolveService | 판정 공식 불변 |
| CombatService (4개) | 전투 시스템 불변 |
| RewardsService | 행동 기반 골드 (이미 수정 완료) |
| NpcEmotionalService | 5축 모델 유지 |
| NarrativeMarkService | 12개 표식 유지 |
| MemoryCollectorService | 수집 로직 유지 |
| MemoryIntegrationService | 통합 로직 유지 |
| EndingGeneratorService | 입력만 확장 |
| LLM Pipeline (8개) | Context에 fact만 추가 |

### 확장 (기존 + 필드/로직 추가)

| 서비스 | 확장 내용 |
|--------|----------|
| WorldStateService | locationStates 관리, npcLocations 관리 |
| WorldTickService | NPC 위치/agenda/상호작용 tick 추가 |
| IncidentManagementService | 사건 간 인과관계, NPC 연루 |
| SignalFeedService | Fact 기반 시그널 자동 생성 |
| IntentMemoryService | PlayerGoal implicit 감지 |
| SceneShellService | LocationCondition 반영 |
| TurnsService | SituationGenerator 호출, ConsequenceProcessor 호출 |

### 신규

| 서비스 | 역할 |
|--------|------|
| LocationStateService | 장소 동적 상태 관리 |
| WorldFactService | 사실 CRUD, 검색, 만료 |
| NpcScheduleService | NPC 일정 관리, 위치 계산 |
| NpcAgendaService | NPC 장기 목표 진행 |
| NpcInteractionService | NPC 간 자동 상호작용 |
| SituationGeneratorService | 3계층 상황 생성 (EventMatcher 대체) |
| ConsequenceProcessorService | 판정 결과 → fact + 상태 변경 |
| PlayerGoalService | 목표 관리, 진행도 추적 |

### 폐기/교체

| 서비스 | 대체 |
|--------|------|
| EventMatcherService | → SituationGeneratorService (Layer 2, 3) |
| EventDirectorService | → SituationGeneratorService (Layer 1 통합) |

---

## Part 8. 핵심 상수 & 밸런스

| 항목 | 값 | 근거 |
|------|-----|------|
| 장소 수 | 7개 | 4→7 (탐험 다양성, 관리 가능) |
| NPC 수 | 15~18명 | 11→18 (장소당 2~3명 보장) |
| Incident 수 | 8~10개 | 2→10 (장소별 1~2개 + 교차) |
| WorldFact 최대 보유 | 50개 | permanent 20 + temporary 30 |
| Fact 기본 수명 | 30턴 | ~2.5일 (permanent 제외) |
| NPC agenda 최대 stage | 4개 | 1주일 이내 완결 |
| LocationCondition 최대 | 3개/장소 | 과도한 복잡도 방지 |
| 인접 장소 이동 | 1턴 | 빠른 탐험감 |
| 비인접 장소 이동 | 2턴 | 경유 비용 |
| NPC 정보 전파 | 1일 (12턴) | 같은 세력 내 |
| RUMOR 전파 | 2일 (24턴) | 비세력 NPC |

---

## Part 9. 위험 요소 & 완화 전략

| 위험 | 영향 | 완화 |
|------|------|------|
| WorldFact 폭발적 증가 | 메모리/성능 | max 50개 제한 + 자동 만료 + 중요도 기반 정리 |
| NPC agenda 충돌 | 논리 모순 | agenda에 blockedBy 필드로 상호 배제 |
| 상황 생성 품질 불균일 | 게임 경험 저하 | SituationTemplate으로 최소 품질 보장 |
| LLM 컨텍스트 토큰 증가 | 비용/속도 | Token Budget 기존 2500 유지, fact는 요약 전달 |
| turns.service.ts 더 비대해짐 | 유지보수 | ConsequenceProcessor/SituationGenerator로 분리 |
| 기존 플레이테스트 호환성 | 회귀 버그 | Phase A에서 기존 기능 불변 검증 |

---

## Part 10. 성공 기준

### "살아있는 세계"를 체감하는 5가지 테스트

1. **같은 장소, 다른 상황** — 시장을 3번 방문했을 때 매번 다른 상황이 펼쳐진다.
2. **내 행동의 결과** — "어제 마르코를 도왔더니, 오늘 강채린이 나를 추궁한다."
3. **NPC를 찾아가기** — "밤에 창고구에 가면 마르코를 만날 수 있다."
4. **부재 중 세계 변화** — "3일 만에 항만에 갔더니 경비대가 봉쇄하고 있다."
5. **내 목표 추적** — "밀수 조직을 추적하겠다고 결심하고, 관련 정보를 모아간다."

### 수치 목표

- 20턴 플레이 시 동일 상황 0회 (현재: 3~5회 반복)
- NPC 재회율 80% (같은 장소 같은 시간대 방문 시)
- WorldFact 평균 30개 유지 (20턴 기준)
- 플레이어 행동 → 후속 상황 연결률 60% 이상
