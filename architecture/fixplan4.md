# Fixplan4 — Playtest 2026-03-18 수정 계획

## Context

플레이테스트 20턴 분석에서 발견된 6개 문제. 코드 조사 완료 후 근본 원인 특정.

---

## F1. Incident 미발생 (activeIncidents = 0) — Critical

### 근본 원인

`initIncidents()`는 `runs.service.ts:117`에서 런 시작 시 호출됨.
그러나 incidents.json의 spawnConditions를 보면:

| incidentId | minDay | minHeat | eligible at start? |
|------------|--------|---------|-------------------|
| INC_SMUGGLING_RING | 1 | **10** | ❌ (heat=0) |
| INC_GUARD_CORRUPTION | 2 | **20** | ❌ |
| INC_LABOR_STRIKE | 3 | **15** | ❌ |
| INC_MERCHANT_WAR | 2 | **5** | ❌ (day=1) |
| INC_SLUM_PLAGUE | 4 | **25** | ❌ |
| INC_ASSASSINATION_PLOT | 5 | **40** | ❌ |
| **INC_MARKET_THEFT** | 1 | **null** | ✅ |
| INC_GUARD_SLUM_RAID | 4 | **35** | ❌ |

**day=1, heat=0에서 eligible한 사건은 INC_MARKET_THEFT 1개뿐.**
이것이 initIncidents에서 선택되었어야 하는데, 플레이테스트에서 activeIncidents=0.

**추가 원인**: `trySpawnIncident()`는 매 LOCATION 턴 preStepTick에서 호출되지만, **20% 확률**로만 spawn. heat가 0에서 거의 증가하지 않으면 대부분의 사건이 영원히 자격 미달.

### 수정

#### A. initIncidents 디버깅
`runs.service.ts:117` — initIncidents 호출 후 결과를 로깅하여 INC_MARKET_THEFT가 선택되는지 확인.
만약 선택됨에도 API에서 빈 배열로 반환된다면, worldState 직렬화/역직렬화 문제.

#### B. 초기 heat 부스트
`world-state.service.ts:21` — 초기 hubHeat를 0→**15**로 변경.
Day 1에서 INC_SMUGGLING_RING(minHeat:10)과 INC_MARKET_THEFT(minHeat:null) 2개가 즉시 eligible.

```typescript
// 변경 전
hubHeat: 0,

// 변경 후
hubHeat: 15,
```

#### C. trySpawnIncident 확률 상향
`incident-management.service.ts:100` — spawn 확률 20%→**40%**로 증가.
20턴 중 LOCATION 턴 약 12턴 × 20% = 2.4회 기대 → 12턴 × 40% = 4.8회로 개선.

```typescript
// 변경 전
if (!rng.chance(20)) return null;

// 변경 후
if (!rng.chance(40)) return null;
```

**파일**: `server/src/engine/hub/world-state.service.ts`, `server/src/engine/hub/incident-management.service.ts`

---

## F2. NPC encounterCount 미증가 — Critical

### 근본 원인

encounterCount 증가는 3개 경로:
1. **eventPrimaryNpc** (turns.service.ts ~L765): `matchedEvent.payload.primaryNpcId` 존재 시
2. **TAG_TO_NPC** (turns.service.ts ~L800): eventPrimaryNpc=null일 때 태그 기반 보충 (Fixplan3-P2)
3. **orchestration injection** (turns.service.ts ~L959): NPC 주입 시

**문제**: 이벤트 콘텐츠 데이터에서 `primaryNpcId`가 설정된 이벤트가 소수. TAG_TO_NPC 매핑도 일부 태그만 커버.
→ 대부분의 이벤트에서 encounterCount가 증가하지 않음.

### 수정

#### A. 이벤트 콘텐츠에 primaryNpcId 보강
`content/graymar_v1/events_*.json` — NPC가 등장하는 이벤트에 primaryNpcId 필드 추가.

조사 필요 이벤트:
- EVT_MARKET_INT_2 (술꾼 → NPC 매핑 필요)
- EVT_MARKET_ENC_BUSKER (악사 → NPC 매핑 필요)
- EVT_GUARD_CHECKPOINT (경비병 → NPC_GUARD_CAPTAIN?)
- EVT_GUARD_OPP_REWARD (보상 → NPC 매핑 필요)
- EVT_HARBOR_ATM_3, EVT_HARBOR_INT_1, EVT_HARBOR_INT_3, EVT_HARBOR_ENC_FISHERMEN

#### B. TAG_TO_NPC 매핑 확장
`memory-collector.service.ts`의 TAG_TO_NPC 맵에 추가 태그→NPC 매핑:
- ELDERLY → NPC_ROSA (시장 노부인)
- GUARD/PATROL → NPC_GUARD_CAPTAIN
- HARBOR/DOCK → NPC_CAPTAIN_BREN
- BUSKER/STREET → NPC_RENNICK(?)

#### C. NPC_LOCATION_AFFINITY 보강 (신규 발견)
`turn-orchestration.service.ts` L40-48의 NPC_LOCATION_AFFINITY 맵에 **4개 NPC 누락**:
- NPC_MIRELA → market (시장에서 활동하는 NPC)
- NPC_RENNICK → market (거리 악사)
- NPC_ROSA → market (시장 노부인)
- NPC_CAPTAIN_BREN → harbor (항구 선장)

이 NPC들은 orchestration injection 경로(경로 3)로 encounterCount가 증가할 수 없음.

**파일**: `content/graymar_v1/events_*.json`, `server/src/engine/hub/memory-collector.service.ts`, `server/src/engine/hub/turn-orchestration.service.ts`

---

## F3. NPC posture = None (API 응답) — High

### 근본 원인

`initNPCState()`(npc-state.ts:58~87)에서 `posture: basePosture ?? 'CAUTIOUS'`로 초기화됨.
코드상 posture가 None일 수 없음. → **API 직렬화 문제** 가능성.

`GET /runs/:id` 응답에서 `runState.npcStates`가 어떤 경로로 반환되는지 확인 필요.
플레이테스트 스크립트에서 `state.runState.npcStates[npc].posture`가 None이었다면:
- DB에서 읽을 때 JSONB에서 posture 키가 누락되었거나
- syncLegacyFields()에서 computeEffectivePosture()가 호출되지 않아 posture 갱신 안 됨

### 수정

#### A. computeEffectivePosture 반환 경로 확인
`npc-state.ts:110` — emotional이 모두 0이면 `return state.posture`로 basePosture 반환해야 함.
그런데 `currentPosture`로 읽고 있을 가능성. API 응답 필드명과 내부 필드명 불일치 확인.

#### B. NPC 상태 직렬화 시 posture 필드 포함 확인
`runs.service.ts`의 GET /runs/:id 응답 빌더에서 npcStates 직렬화 확인.

**파일**: `server/src/db/types/npc-state.ts`, `server/src/runs/runs.service.ts`

---

## F4. NPC 감정축 비활성 (trust/fear = None) — Medium

### 근본 원인

`applyActionImpact()`(npc-emotional.service.ts:56~80)는 encounterCount가 증가하는 경로에서만 호출됨 (turns.service.ts L794~797).

**F2에서 encounterCount가 미증가 → applyActionImpact 미호출 → 감정축 변화 없음.**

### 수정

F2 수정(encounterCount 보강)이 해결되면 자동으로 감정축도 활성화됨.
추가로 encounterCount 증가 없이도 NPC가 등장하면 감정 영향을 주는 경로 검토.

**의존**: F2 수정 후 자동 해결 기대.

---

## F5. structuredMemory 비어있음 — Critical

### 근본 원인

조사 결과:
- `collectFromTurn()` → `nodeMemories.visitContext`에 저장 ✅ (호출됨)
- `finalizeVisit()` → `nodeMemories.visitContext` 읽기 → `runMemories.structuredMemory` 업데이트 ✅ (호출됨)

**확인된 근본 원인** (에이전트 코드 조사 완료):

1. **[PRIMARY] API 응답에서 structuredMemory 미반환**: `runs.service.ts` L490-495에서 `memory` 객체에 `theme`과 `storySummary`만 포함. `structuredMemory`는 DB에 저장되지만 **API 응답에 포함되지 않음**.
2. collectFromTurn()이 try-catch로 감싸져 오류 발생 시 무시됨 → 실패 로그 미확인
3. finalizeVisit()이 정상 호출되고 DB에도 저장되지만, 클라이언트/플레이테스트에서 확인 불가

### 수정

#### A. API 응답에 structuredMemory 추가 (핵심 수정)
`runs.service.ts` ~L490-495 — memory 응답 객체에 structuredMemory 포함:

```typescript
// 변경 전
memory: {
  theme: runMemories?.theme ?? null,
  storySummary: runMemories?.storySummary ?? null,
}

// 변경 후
memory: {
  theme: runMemories?.theme ?? null,
  storySummary: runMemories?.storySummary ?? null,
  structuredMemory: runMemories?.structuredMemory ?? null,
}
```

#### B. collectFromTurn 에러 로깅 강화
`turns.service.ts ~L1196` — catch 블록에 `this.logger.warn()` 추가.

```typescript
} catch (err) {
  this.logger.warn(`[MemoryCollector] collectFromTurn failed: ${err.message}`);
}
```

#### C. finalizeVisit 결과 로깅
`turns.service.ts` — finalizeVisit 호출 후 결과 로깅.

**파일**: `server/src/runs/runs.service.ts`, `server/src/turns/turns.service.ts`

---

## F6. resolveOutcome API 필드 위치 — Low

### 근본 원인

resolveOutcome은 `serverResult.ui.resolveOutcome`에 포함됨 (최상위가 아닌 ui 객체 내).
플레이테스트 스크립트가 `serverResult.resolveOutcome`으로 접근하여 빈 값으로 판단.

비도전 행위(TALK, REST 등)에서는 `hideResolve=true`로 의도적으로 숨김.
도전 행위(INVESTIGATE, FIGHT 등)에서는 정상 포함.

### 수정

**코드 수정 불필요** — 플레이테스트 스크립트의 접근 경로를 `serverResult.ui.resolveOutcome`으로 수정.
리포트의 "resolveOutcome API 미노출" 판정은 **오진**. 실제로는 정상 동작.

---

## 수정 파일 목록

| # | 파일 | 수정 내용 | 우선순위 |
|---|------|----------|---------|
| 1 | `server/src/engine/hub/world-state.service.ts` | F1: 초기 hubHeat 0→15 | Critical |
| 2 | `server/src/engine/hub/incident-management.service.ts` | F1: spawn 확률 20%→40% | Critical |
| 3 | `server/src/runs/runs.service.ts` | F5: API 응답에 structuredMemory 추가 | Critical |
| 4 | `server/src/turns/turns.service.ts` | F5: 메모리 에러 로깅 강화 | Critical |
| 5 | `content/graymar_v1/events_*.json` | F2: primaryNpcId 보강 | Critical |
| 6 | `server/src/engine/hub/memory-collector.service.ts` | F2: TAG_TO_NPC 매핑 확장 | Critical |
| 7 | `server/src/engine/hub/turn-orchestration.service.ts` | F2: NPC_LOCATION_AFFINITY 보강 | Critical |
| 8 | `server/src/db/types/npc-state.ts` | F3: posture 필드명 확인 | High |

## 작업 순서

1. **F5** (structuredMemory API 노출) → 근본 원인 해결, 1줄 추가
2. **F1** (Incident spawn) → Narrative Engine v1 핵심 기능 활성화
3. **F2** (NPC encounterCount + LOCATION_AFFINITY) → NPC 시스템 정상화
4. **F3** (posture 직렬화) → NPC 이름 공개 시스템
5. **F4** (감정축) → F2 의존, 자동 해결 기대
6. **F6** (resolveOutcome) → 스크립트만 수정, 코드 변경 불필요

## 검증

수정 후 `/playtest`로 20턴 재테스트:
- [ ] activeIncidents > 0 (Incident 정상 spawn)
- [ ] NPC encounterCount 증가 확인 (3명 이상 count > 0)
- [ ] NPC posture가 None이 아닌 값 확인
- [ ] structuredMemory에 visitLog, npcJournal 존재
- [ ] 감정축(trust/fear) 변화 확인
