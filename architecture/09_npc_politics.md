# 09 — NPC 정치 · 관계 · 행동 상태 시스템

> 원본 참조: `State_Storage_Spec_v1.md`, `specs/political_narrative_system_v1.md`, `specs/llm_context_memory_v1_1.md`
> 상태: **구현 완료** — NPC 감정 모델, 소개 시스템, TurnOrchestration NPC 주입, posture 계산, PBP, Off-screen Tick, Schedule/Agenda, knownFacts 점진 공개, 퀘스트 Fact 연동 구현됨. Leverage(타입만 정의) 미사용. LocationRuntimeState는 Living World v2(21번)로 대체.
> 의존: WorldState (구현됨), Reputation (구현됨), TurnOrchestration (구현됨), QuestProgression (구현됨)
> 마지막 갱신: 2026-04-01 (NPC ID 정규화, knownFacts-Quest 연동, P0~P5 밸런싱)

---

## 1. NPCState

각 NPC의 런타임 상태. RunState에 `npcStates: Record<string, NPCState>`로 저장.

> 정본: `server/src/db/types/npc-state.ts`

### 1.1 NPCState 스키마

```typescript
interface NPCState {
  npcId: string;               // NPC 식별자 (npcs.json 참조)
  introduced: boolean;         // ✅ 이름 공개 여부 (소개 시스템)
  encounterCount: number;      // ✅ 만남 횟수
  agenda: string;              // NPC의 현재 목표/동기 서술
  currentGoal: string;         // 구체적 현재 행동 목표
  currentStage: string;        // 목표 진행 단계
  emotional: NpcEmotionalState; // ✅ 5축 감정 모델
  posture: NpcPosture;         // 현재 대화 자세 (동적 계산)
  trustToPlayer: number;       // 플레이어에 대한 신뢰 (-100~100)
  suspicion: number;           // 플레이어에 대한 의심 (0~100)
  influence: number;           // 정치적 영향력 (0~100)
  funds: number;               // 자금 상태 (0~100)
  network: number;             // 인맥 상태 (0~100)
  exposure: number;            // 비밀 노출 위험도 (0~100)
}

// 5축 감정 모델 (NpcEmotionalService에서 관리)
interface NpcEmotionalState {
  trust: number;      // 신뢰 (-100~100)
  fear: number;       // 공포 (0~100)
  respect: number;    // 존경 (-100~100)
  suspicion: number;  // 의심 (0~100)
  attachment: number; // 애착 (0~100)
}

type NpcPosture = 'FRIENDLY' | 'CAUTIOUS' | 'HOSTILE' | 'FEARFUL' | 'CALCULATING';
```

### 1.2 NPC 3계층 (42명)

NPC는 **CORE / SUB / BACKGROUND** 3계층으로 구분된다.

| 계층 | 수 | 설명 | 감정 모델 | Agenda |
|------|---|------|----------|--------|
| **CORE** | 5명 | 메인 아크 핵심 인물 | 5축 감정 완비 | 고유 장기 목표 |
| **SUB** | 12명 | 세력/장소 중간 인물 | 5축 감정 완비 | 세력 연동 목표 |
| **BACKGROUND** | 25명 | 도시 배경 NPC | 간소화 (posture만) | 없음 (스케줄만) |

CORE NPC: 하를런 보스, 마이렐 단 경, 에드릭 베일, 쉐도우, 벨론 대위

### 1.3 Base Posture

`content/graymar_v1/npcs.json`에 각 NPC의 `basePosture` 필드로 정의 (CORE/SUB 대표):

| NPC | 계층 | basePosture | unknownAlias (소개 전 별칭) |
|-----|------|------------|---------------------------|
| 하를런 보스 | CORE | FRIENDLY | 투박한 노동자 |
| 에드릭 베일 | CORE | CAUTIOUS | 날카로운 눈매의 회계사 |
| 마이렐 단 경 | CORE | CALCULATING | 권위적인 야간 경비 책임자 |
| 쉐도우 | CORE | CALCULATING | 후드를 깊이 쓴 정보상 |
| 벨론 대위 | CORE | CAUTIOUS | 위풍당당한 수비대 장교 |
| 토브렌 하위크 | SUB | CAUTIOUS | 수상한 창고 관리인 |
| 라이라 케스텔 | SUB | FEARFUL | 조용한 문서 실무자 |
| 미렐라 | SUB | FRIENDLY | 약초 향이 나는 노점상 |

### 1.4 Posture 계산 (구현됨)

> 정본: `server/src/engine/hub/npc-emotional.service.ts`

`computeEffectivePosture(npcState)` — 5축 감정 상태 기반 동적 posture 계산:

```
effectivePosture = f(basePosture, emotional.trust, emotional.fear, emotional.suspicion)
```

- trust > 30 → FRIENDLY 경향
- suspicion > 60 → HOSTILE 경향
- fear > 50 → FEARFUL 경향
- LLM 실패 시 기본값 CAUTIOUS (Safe Degradation)

### 1.5 NPC 소개(Introduction) 시스템 (구현됨)

NPC 성격에 따라 이름 공개 시점이 다르다. 소개 전에는 `unknownAlias`(묘사적 별칭)로 표시.

**소개 시점 판정** — `shouldIntroduce(npcState, posture)`:

| posture | 필요 만남 횟수 | 소개 방식 |
|---------|--------------|----------|
| FRIENDLY / FEARFUL | 1회 (첫 만남) | 자기소개 (이름 포함) |
| CAUTIOUS | 2회 | 서서히 이름 공개 (타인 언급/상황 단서) |
| CALCULATING / HOSTILE | 3회 | 다른 경로로 알게 됨 (문서, 대화, 간판) |

**표시 이름 결정** — `getNpcDisplayName(npcState, npcDef)`:
- `introduced === true` → 실명 (`npcDef.name`)
- `introduced === false` → 별칭 (`npcDef.unknownAlias` 또는 '낯선 인물')

**LLM 프롬프트 연동**:
- 새로 소개되는 NPC → "[첫 만남 — 자기소개하세요]" 또는 "[이름이 드러남 — 상황/타인 통해]"
- 아직 미소개 NPC → "[이름 미공개 — 별칭으로만 지칭하세요]"
- context-builder가 `introducedNpcIds`, `newlyIntroducedNpcIds`, `newlyEncounteredNpcIds`를 LlmContext에 전달

### 1.6 NPC Schedule 시스템 (Living World v2)

> 정본: `server/src/engine/hub/npc-schedule.service.ts`

각 NPC는 시간대(DAWN/DAY/DUSK/NIGHT)별 위치가 정의된 스케줄을 가진다.

```typescript
interface NpcScheduleEntry {
  npcId: string;
  schedule: Record<TimePhaseV2, string | null>;  // locationId or null (부재)
}
```

- **WorldTick 연동**: `WorldTickService`의 시간대 변경 시 `NpcScheduleService`가 NPC 위치 자동 업데이트
- **이벤트 매칭 영향**: 현재 장소에 스케줄상 존재하는 NPC만 이벤트/상호작용 대상
- **CORE/SUB**: 고유 스케줄 보유. BACKGROUND: 장소 고정 또는 단순 DAY/NIGHT 패턴
- Incident/WorldFact에 의해 임시 스케줄 오버라이드 가능

### 1.7 NPC Agenda 시스템 (Living World v2)

> 정본: `server/src/engine/hub/npc-agenda.service.ts`

CORE/SUB NPC는 장기 목표(Agenda)를 가지며, 플레이어 행동과 독립적으로 자율 진행한다.

```typescript
interface NpcAgenda {
  npcId: string;
  goalId: string;           // 현재 추구 중인 목표
  progress: number;         // 0~100 진행도
  priority: number;         // 목표 우선순위
  blockedBy: string | null; // 차단 조건 (Fact/Flag)
}
```

- **Tick 기반 자율 진행**: `NpcAgendaService`가 매 WorldTick에서 NPC 목표 진행도 업데이트
- **플레이어 행동 영향**: 플레이어의 판정 결과가 NPC agenda 진행을 가속/차단
- **Incident 연동**: agenda 진행이 임계치 도달 시 Incident spawn 트리거 가능
- **SituationGenerator 입력**: NPC agenda 상태가 상황 생성의 주요 입력

### 1.8 NPC 자동 상호작용 (Living World v2)

같은 장소에 있는 NPC 간 자동 상호작용이 발생한다.

- **조건**: 동일 장소 + 동일 시간대에 2명 이상 NPC 존재
- **상호작용 유형**: 협력(같은 세력), 갈등(대립 세력), 정보 교환
- **결과**: WorldFact 생성, NPC 감정 상태 변동, Signal Feed 시그널 발생
- **플레이어 관찰 가능**: 해당 장소에 플레이어가 있으면 상호작용이 이벤트/서술에 반영

---

## 2. RelationshipGraph

Player↔NPC 관계를 구조화. 기존 flat score → 다차원 관계 모델.

### 2.1 관계 구조

```typescript
interface Relationship {
  relation: 'ALLY' | 'NEUTRAL' | 'TENSE' | 'HOSTILE';
  trust: number;        // 신뢰 (-100~100)
  fear: number;         // 공포 (0~100)
  dependence: number;   // 의존도 (0~100)
}
```

### 2.2 서술적 관계 요약 (LLM 전달)

> 원본: `specs/llm_context_memory_v1_1.md` §1.2

관계는 수치가 아닌 **서술 요약**으로 LLM에 전달:
- "상인 라비는 당신을 신뢰하기 시작했다."
- "경비대장은 여전히 당신을 의심하고 있다."
- "하를런은 당신에게 빚진 감정이 있다."

### 2.3 관계 변동 트리거

| 트리거 | 신뢰 변화 | 공포 변화 |
|--------|----------|----------|
| HELP NPC 성공 | +5~10 | - |
| THREATEN NPC | -5 | +10~15 |
| FIGHT (NPC 연관) | -10~20 | +5~10 |
| PERSUADE 성공 | +3~5 | - |
| BRIBE 성공 | +2~3 | - |
| STEAL 발각 | -15 | - |

---

## 3. Leverage (약점/정보)

NPC 간 또는 Player→NPC 약점 정보.

```typescript
interface Leverage {
  ownerId: string;        // 약점을 알고 있는 주체
  targetId: string;       // 약점의 대상
  type: string;           // 약점 유형 (CORRUPTION, SECRET, DEBT 등)
  severity: number;       // 심각도 (1~5)
  exposureRisk: number;   // 노출 시 파급도 (1~5)
}
```

- Leverage는 이벤트 진행 중 발견 → RunState에 저장
- THREATEN/BRIBE 판정에 severity 보너스 적용 (향후)
- LLM 컨텍스트에 관련 Leverage 요약 전달

---

## 4. WorldState 확장: Per-location 상태

기존 WorldState에 Location별 런타임 상태 추가.

```typescript
interface LocationRuntimeState {
  security: number;     // 치안 수준 (0~100)
  crime: number;        // 범죄 활동 (0~100)
  unrest: number;       // 불안 수준 (0~100)
  spotlight: boolean;   // 주목 상태 (세력이 주시 중)
}

// WorldState 확장
interface WorldState {
  // 기존 필드...
  hubHeat: number;
  hubSafety: HubSafety;
  timePhase: TimePhase;
  tension: number;
  reputation: Record<string, number>;
  flags: Record<string, boolean>;
  // 추가
  locationStates: Record<string, LocationRuntimeState>;
  incidentFlags: Record<string, boolean>;
}
```

### LocationRuntimeState 초기값

| locationId | security | crime | unrest | spotlight |
|------------|----------|-------|--------|-----------|
| LOC_MARKET | 60 | 30 | 20 | false |
| LOC_GUARD | 80 | 10 | 10 | false |
| LOC_HARBOR | 40 | 50 | 40 | false |
| LOC_SLUMS | 20 | 70 | 60 | false |

---

## 5. PlayerBehaviorProfile (PBP)

플레이어 행동 패턴 집계. 행동 통계로부터 자동 계산.

```typescript
interface PlayerBehaviorProfile {
  dominant: PBPCategory;     // 가장 높은 점수 카테고리
  secondary: PBPCategory;    // 두 번째 높은
  scores: {
    violence: number;         // FIGHT, THREATEN 기반
    stealth: number;          // SNEAK, STEAL 기반
    negotiation: number;      // PERSUADE, BRIBE, TRADE 기반
    investigation: number;    // INVESTIGATE, OBSERVE, SEARCH 기반
    greed: number;            // STEAL, BRIBE, 골드 우선 선택
    lawfulness: number;       // HELP, 법적 행동 선택
    insistence: number;       // 고집 에스컬레이션 빈도
    riskTaking: number;       // riskLevel 3 행동 빈도
  };
}

type PBPCategory = 'VIOLENCE' | 'STEALTH' | 'NEGOTIATION' | 'INVESTIGATION' |
                   'GREED' | 'LAWFULNESS' | 'INSISTENCE' | 'RISK_TAKING';
```

### PBP 집계 규칙

- ActionHistory에서 최근 N턴(예: 20) 기준 집계
- 각 ActionType → score 매핑:
  - FIGHT/THREATEN → violence +1
  - SNEAK/STEAL → stealth +1
  - PERSUADE/BRIBE/TRADE → negotiation +1
  - INVESTIGATE/OBSERVE/SEARCH → investigation +1
- dominant/secondary는 scores 중 상위 2개
- PBP는 LLM 컨텍스트(L4 확장)에 전달하여 서술 톤 유도
- **서버 규칙 판정에 PBP는 사용하지 않음** (서술 전용)

---

## 6. RunState 확장

```typescript
interface RunState {
  // 기존 필드...
  worldState: WorldState;
  arcState: ArcState;
  agenda: Agenda;
  actionHistory: ActionHistoryEntry[];

  // Phase 2 추가
  npcStates: Record<string, NPCState>;     // NPC 런타임 상태
  relationships: Record<string, Relationship>;  // player↔NPC 관계
  leverages: Leverage[];                    // 발견된 약점 정보
  pbp: PlayerBehaviorProfile;              // 행동 프로필

  // Phase 3 (구현됨)
  pressure: number;        // 감정 압력 (0~100) — TurnOrchestrationService
  lastPeakTurn: number;    // 마지막 peakMode 발동 턴

  // Narrative Engine v1 (구현됨)
  activeIncidents: IncidentRuntime[];    // 활성 사건
  signalFeed: SignalFeedItem[];          // 시그널 피드
  narrativeMarks: NarrativeMark[];       // 불가역 표식
  mainArcClock: MainArcClock;            // 데드라인
  operationSession: OperationSession | null;  // 멀티스텝 세션

  // Equipment (Phase 4, 부분 구현)
  equipped: EquippedGear;
  equipmentBag: ItemInstance[];
}
```

---

## 7. LLM 컨텍스트 확장

NPCState, PBP, Relationship을 L2/L4에 주입.

### L2 확장: NPC 관계 Facts

현재 LOCATION에 관련된 NPC의 관계 서술 요약을 nodeFacts에 추가:
```
{ key: "npc.라비.relation", value: "당신을 신뢰하기 시작했다", importance: 0.7, tags: ["NPC", "RELATION"] }
```

### L4 확장: 행동 프로필

```
"플레이어 성향: 폭력적/은밀 (violence=7, stealth=5)"
```

---

## 8. 정치 내러티브 시스템 참조

> 원본: `specs/political_narrative_system_v1.md`

### 세력 관계 모델

| 세력 | 키 | 관련 NPC | 관계 |
|------|-----|---------|------|
| 경비대 | CITY_GUARD | 마이렐 경, 라이라, 벨론 대위 | 법 집행 |
| 상인 길드 | MERCHANT_CONSORTIUM | 토브렌, 상인들 | 경제 이권 |
| 노동 길드 | LABOR_GUILD | 하를런, 부두 노동자들 | 노동 권익 |

세력 간 긴장은 WorldState.tension으로 추적되며, NPC의 agenda는 소속 세력의 이해관계에 영향받는다.

### 정치적 선택의 영향

- 세력 평판(reputation)은 이벤트 conditions에서 참조
- reputation이 특정 임계치 이상/이하 → 조건부 이벤트 활성화
- NPC posture는 해당 세력 reputation에 연동

---

## 9. 구현 상태 요약

| 항목 | 상태 | 구현 파일 |
|------|------|----------|
| NPCState 타입 (introduced, encounterCount, emotional) | ✅ 구현 | `db/types/npc-state.ts` |
| NpcEmotionalState (5축 감정 모델) | ✅ 구현 | `db/types/npc-state.ts` |
| NpcEmotionalService (감정 계산/posture) | ✅ 구현 | `engine/hub/npc-emotional.service.ts` |
| NPC Introduction (소개 시스템) | ✅ 구현 | `npc-state.ts`, `turns.service.ts`, `prompt-builder.service.ts` |
| getNpcDisplayName / shouldIntroduce | ✅ 구현 | `db/types/npc-state.ts` |
| TurnOrchestration (NPC 주입 + pressure) | ✅ 구현 | `engine/hub/turn-orchestration.service.ts` |
| NPC unknownAlias (콘텐츠) | ✅ 구현 | `content/graymar_v1/npcs.json` |
| Reputation 시스템 | ✅ 구현 | `engine/hub/resolve.service.ts` |
| PBP (행동 프로필) | ✅ 구현 | `db/types/player-behavior.ts`, `turns.service.ts`에서 업데이트 |
| Relationship (다차원 관계) | ✅ 구현 | `db/types/npc-state.ts`, Resolve 결과에 따라 자동 변동 |
| LLM 컨텍스트 전달 | ✅ 구현 | `context-builder.service.ts` — npcRelationFacts, playerProfile, npcEmotionalContext |
| NPC 정보 기억 | ✅ 구현 | `[이번 방문 대화]` 규칙 6~7: NPC 대화 기억 유지 (2026-03-16) |
| Leverage (약점/정보) | ⚠️ 타입만 정의 | `db/types/npc-state.ts` — 런타임 로직 미구현 (퀘스트 Fact 시스템으로 대체) |
| LocationRuntimeState | ✅ Living World v2로 대체 | `21_living_world_redesign.md` — locationDynamicStates로 구현됨 |
| NPC knownFacts → Quest | ✅ 구현 | `quest-progression.service.ts` — NPC 대화로 퀘스트 Fact 점진 공개 |
| 밸런스 상수 외부화 | ✅ 구현 | `quest-balance.config.ts` — SitGen 확률, PARTIAL 발견률 등 |
| Off-screen Tick | ✅ 구현 | `world-tick.service.ts` — preStepTick/postStepTick |
| NPC 3계층 (42명) | ✅ 구현 | CORE 5 + SUB 12 + BACKGROUND 25 |
| NPC Schedule | ✅ 구현 | `npc-schedule.service.ts` — 시간대별 위치, WorldTick 연동 |
| NPC Agenda | ✅ 구현 | `npc-agenda.service.ts` — 장기 목표 자율 진행 |
| NPC 자동 상호작용 | ✅ 구현 | 동일 장소 NPC 간 상호작용 → WorldFact/Signal 생성 |
