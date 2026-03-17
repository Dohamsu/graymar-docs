# HUB 엔진 구현 지침

> 정본 위치: `server/src/engine/hub/`
> 설계 문서: `architecture/03_hub_engine.md`, `14~17`, `18~20`
> 최종 갱신: 2026-03-17

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

---

## Reputation System (세력 평판)

| 세력 | 키 | 관련 이벤트 태그 |
|------|-----|---------------|
| 경비대 | CITY_GUARD | GUARD_ALLIANCE, GUARD_PATROL, CHECKPOINT, ARMED_GUARD |
| 상인 길드 | MERCHANT_CONSORTIUM | MERCHANT_GUILD, LEDGER, MERCHANT_CONSORTIUM |
| 노동 길드 | LABOR_GUILD | LABOR_GUILD, WORKER_RIGHTS, DOCK_THUGS |

판정 결과: SUCCESS +3, FAIL -2, PARTIAL 0

---

## Character Presets (캐릭터 프리셋)

`content/graymar_v1/presets.json`

| 프리셋 | 이름 | 컨셉 | 핵심 스탯 | 강점 actionType |
|-------|------|------|----------|---------------|
| DOCKWORKER | 부두 노동자 | 근접 탱커 | ATK16 DEF14 | FIGHT/THREATEN/HELP |
| DESERTER | 탈영병 | 균형 전투가 | ATK17 ACC7 | FIGHT/INVESTIGATE |
| SMUGGLER | 밀수업자 | 은밀 특화 | EVA7 SPEED7 CRIT8 | SNEAK/PERSUADE/BRIBE |
| HERBALIST | 약초상 | 아이템 활용 | RESIST9 Stamina7 ACC6 | INVESTIGATE/HELP |
