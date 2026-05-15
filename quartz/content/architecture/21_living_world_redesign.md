# 21. Living World Redesign — 살아있는 세계 재설계

> **구현 API는 [[guides/07_living_world_guide|living world guide]] 참조. 이 문서는 설계 배경·대안 분석만 유지.**
> **목표**: "사용자가 자유롭게 탐색하며 세계를 탐험하고 만들어나가는 게임"
> **범위**: 이벤트/장소/NPC/시간/결과/목표 재설계 모티베이션
> **원칙**: 기존 자산(29개 HUB 서비스, 전투, RNG, 메모리 v2) 최대 활용. 교체가 아닌 진화.

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
| IntentParserV2 | 골드 명시 파싱, 장소/NPC 타겟 정밀화 |
| ResolveService | computeGoldCost에 specifiedGold 반영 |
| RewardsService | 행동 기반 골드 |

### 2.3 재설계 (구조 변경)

| 자산 | 변경 내용 |
|------|----------|
| EventMatcher 6단계 | → SituationGenerator로 교체 (세계 상태 → 상황 생성) |
| HUB→LOCATION 허브스포크 | → 장소↔장소 자유 이동 |
| Node 시스템 (COMBAT/EVENT/...) | → LOCATION이 기본, COMBAT은 서브노드로 유지 |
| 112개 정적 이벤트 | → 시드 이벤트(랜드마크) + 동적 상황 생성 |
| SceneShell 선택지 생성 | → 장소 상태 기반 동적 선택지 |

---

## Part 3. 7대 핵심 시스템 — 설계 배경

각 시스템의 구체 API/스키마/메서드는 [[guides/07_living_world_guide|living world guide]]에 정리되어 있다. 아래는 각 시스템이 **왜 필요한가**와 **어떤 문제를 푸는가**에 초점을 맞춘다.

### System 1: Living Location (살아있는 장소)

**문제**: 기존에는 장소가 "이벤트 풀의 태그"에 가까웠다. 플레이어가 방문할 때만 의미를 가지고, 방문 간 변화가 없었다.

**핵심 아이디어**: 장소는 **자체 상태(security/prosperity/unrest/conditions/presentNpcs)를 가진 동적 공간**. 플레이어가 방문하든 안 하든 상태가 변한다.

**확장**: 4개 장소 → 7개 (LOC_MARKET / LOC_GUARD / LOC_HARBOR / LOC_SLUMS / LOC_NOBLE / LOC_TAVERN / LOC_DOCKS_WAREHOUSE). LOC_TAVERN이 기존 HUB의 거점 역할을 흡수(Heat 해결, 퀘스트 수락).

**이동**: 인접 1턴 / 비인접 2턴(경유) / CURFEW 등 조건에 의한 이동 제한. LOC_TAVERN은 모든 장소와 인접.

### System 2: NPC Presence (NPC 존재감)

**문제**: NPC가 이벤트에 소환되는 "속성"이었다. 플레이어 턴 밖에서는 존재하지 않았다.

**핵심 아이디어**: NPC는 **세계에 존재하는 개체**. schedule(시간대별 위치)과 longTermAgenda(장기 목표)를 가진다.

**효과**:
- "밤에 창고구에 가면 마르코를 만날 수 있다" — 플레이어가 NPC를 **찾아갈 수 있다**
- NPC가 자기 agenda를 WorldTick에서 자율적으로 진행
- NPC끼리 같은 장소에 있으면 자동 상호작용 → Signal/Fact 발생

### System 3: World Facts (세계 사실 시스템)

**문제**: 행동의 결과가 수치(gold±/heat±)로만 남았다. "무슨 일이 있었는가"를 LLM/NPC/후속 이벤트가 알기 어려웠다.

**핵심 아이디어**: 행동과 세계 변화를 **WorldFact(서술적 진실)**로 누적. 이후 상황 생성의 재료가 된다.

**활용**:
1. 상황 생성의 재료 (SituationGenerator 참조)
2. NPC 대화 반영 (LLM 컨텍스트)
3. 선택지 해금 ("마르코를 도왔으므로 밀수 정보 접근 가능")
4. 조건 평가 (이벤트/Incident의 선행 조건)
5. 엔딩 서술의 재료

**기존 시스템과 연결**: visitLog/npcJournal/SignalFeed/NarrativeMark/Incident에서 Fact 파생/교차참조.

### System 4: Situation Generator (상황 생성기)

**문제**: EventMatcher 6단계가 112개 고정 이벤트 풀에서 골라내는 구조여서, 세계 상태 변화가 상황에 반영되지 않았다.

**핵심 아이디어**: **3계층 상황 생성** — 정적 체크포인트 유지 + 반동적 맥락 + 완전 동적 조합.

- **Layer 1 Landmark**: ARC_HINT, arc_events → 조건 충족 시 무조건 (스토리 체크포인트)
- **Layer 2 Incident-Driven**: 활성 Incident 맥락에서 상황 생성 (기존 IncidentRouter 확장)
- **Layer 3 World-State**: LocationState + presentNpcs + WorldFacts + timePhase 조합 (완전 동적)

**기존 112개 이벤트의 역할 변경**: 삭제하지 않고 **SituationTemplate**(sceneFrame/affordances 참조용)으로 재활용.

**예시 (Incident-Driven, LOC_HARBOR DUSK)**:
- 상태: presentNpcs=[MARCO, MAIREL], fact="player_helped_marco", Incident INC_SMUGGLING stage 1
- 생성: NPC_CONFLICT — 강채린이 마르코를 추궁, 플레이어 반응에 따라 분기(HELP/PERSUADE/OBSERVE/THREATEN)

### System 5: Time & World Tick (시간과 세계 진행)

**문제**: 시간이 표시용 태그에 머물렀다. 플레이어 행동이 없어도 세계는 계속 움직여야 "살아있다"는 감각이 생긴다.

**핵심 아이디어**: 매 턴 실행되는 WorldTick 파이프라인에 **NPC 위치 업데이트 / agenda 진행 / NPC 간 상호작용 / LocationState 자연 회귀**를 추가.

**시간 체감**:
| 단위 | 효과 |
|------|------|
| 1턴 | 행동 1회, NPC 위치 고정 |
| 1 phase (DAWN=2, DAY=4, DUSK=2, NIGHT=4 tick) | NPC 위치 변경 |
| 1일 (12턴) | NPC agenda 체크, Condition 만료 체크 |
| 3일 | Incident stage 자동 진행, 상점 재고 갱신 |
| 7일 | 세력 통제도 변동, 주요 NPC 행동 완료 |

**부재 효과 (Away Effect)**: 방문 오래 안 한 장소는 자연 회귀 + NPC agenda는 계속 진행 → "3일 만에 갔더니 봉쇄되어 있다".

### System 6: Player-Driven Goals (플레이어 주도 목표)

**문제**: 시스템이 이벤트를 밀어넣는 방식이어서, 플레이어의 **의지**가 드러나지 않았다.

**핵심 아이디어**: 플레이어가 목표를 세우고(EXPLICIT) 또는 행동 패턴에서 추론되는(IMPLICIT) 목표가 자동 생성되어 상황 생성에 영향.

**경로**:
- **EXPLICIT**: NPC 의뢰 / 이벤트 선택지 / IntentParser가 감지한 선언
- **IMPLICIT**: IntentMemory 패턴 감지 확장 — STEALTH 반복 / 특정 NPC 반복 방문 / 특정 장소 집중 탐색

**연결**: SituationGenerator가 활성 목표를 참조 — 관련 NPC/장소/milestone 근접 시 관련 상황 우선 생성. 무시하면 NPC agenda가 대신 진행.

### System 7: Consequence Chain (결과의 연쇄)

**문제**: 판정 결과가 즉각 수치 변동으로 끝났다. 행동 → 결과 → 후속 상황의 **연쇄**가 약했다.

**핵심 아이디어**: 모든 판정이 **즉각 효과 + 지연된 결과(fact → 후속 상황)**를 가진다. 결과가 결과를 낳는다.

**전파 경로**:
```
플레이어 행동
  → 즉각 효과 (gold/heat/reputation)
  → WorldFact 생성
  → LocationState 변경 (조건 추가/제거)
  → NPC 반응 (agenda 조정, 정보 전달)
  → Signal 발생
  → 다음 턴 SituationGenerator의 재료
```

**NPC 기억 전파**:
- 직접 목격 → 즉시 (WITNESSED)
- 같은 세력 NPC → 1일 후 (HEARD_FROM_NPC)
- Signal RUMOR → 확률 전파 (HEARD_RUMOR)

**예시 연쇄** (Turn 5 → 8 → 12 → 15):
1. T5: 플레이어가 마르코 밀수를 도움 → fact + 관계 변동 + 소문 Signal
2. T8: 강채린이 fact 인지 → agenda 조정 (밤 창고구 감시)
3. T12: 플레이어가 항만 재방문 → NPC_CONFLICT 상황 (강채린이 마르코와의 관계 추궁)
4. T15: 강채린 agenda stage 2 → LOC_GUARD에 LOCKDOWN, security +30, Signal "경비대가 봉쇄"

---

## Part 4. 데이터 흐름 — 핵심 변경점

구체 파이프라인과 서비스 호출 순서는 `guides/07_living_world_guide.md §5` 참조. 여기서는 v1→v2 핵심 차이만 정리.

**LOCATION 턴 처리의 신규 단계**:
1. 기존 EventMatcher 앞에 **SituationGenerator** 삽입 (3계층 시도 → 실패 시 EventMatcher fallback)
2. ResolveService 뒤에 **ConsequenceProcessor** 삽입 (기존 즉각 효과 + Fact/LocationState 레이어)
3. WorldTick 확장 (NPC 위치/agenda/상호작용 tick)
4. LLM Context에 WorldFacts 추가 (L2 nodeFacts)

**장소 이동의 신규 단계**:
1. MOVE_LOCATION → 인접/비인접 판정, 이동 제한 조건 체크
2. 이탈 시 finalizeVisit + lastVisitTurn 기록
3. 도착 시 LocationState.presentNpcs 확인 → SituationGenerator 즉시 호출

---

## Part 5. 콘텐츠 확장 요구사항

### 5.1 locations.json 확장

- 기존 4개 → 7개
- 필수 필드: `adjacentLocations`, `baseState(controllingFaction, security, prosperity, unrest)`, `affordanceBias`

### 5.2 npcs.json 확장 (11명 → 15~18명)

- LOC_NOBLE 2~3명(귀족/하인/정보원)
- LOC_TAVERN 1~2명(주인장/단골)
- LOC_DOCKS_WAREHOUSE 1~2명(창고지기/밀수꾼)
- 떠돌이 NPC 1명 (여러 장소 순회)
- 각 NPC에 `schedule` + `longTermAgenda` 필수

### 5.3 incidents.json 확장 (2개 → 8~10개)

장소당 1~2개 + 교차 사건. 인과관계 예:
- `INC_SMUGGLING_RING ESCALATED` → `INC_GUARD_CORRUPTION pressure +20`
- `INC_LABOR_STRIKE CONTAINED` → `INC_MERCHANT_MONOPOLY pressure -10`
- `INC_NOBLE_CONSPIRACY stage 2` → `INC_GUARD_CORRUPTION spawn`

### 5.4 events_v2.json 역할 변경

기존 112개 이벤트를 삭제하지 않고 **SituationTemplate**(sceneFrameTemplate, affordances, outcomeEffects의 factTemplate)으로 재분류.

---

## Part 6. 구현 전략 (Phase 계획, 완료)

| Phase | 범위 | 기간 | 상태 |
|-------|------|-----|------|
| A: Foundation | WorldState 확장, LocationState/WorldFact 서비스, NPC schedule, 콘텐츠 3개 장소 추가 | 2~3주 | 완료 |
| B: Living World | NpcAgenda, ConsequenceProcessor, WorldTick 확장, 장소 간 직접 이동, incidents 확장 | 3~4주 | 완료 |
| C: Dynamic Situations | SituationGenerator 3계층, SituationTemplate, PlayerGoal, LLM 컨텍스트 확장 | 3~4주 | 완료 |
| D: Polish & Balance | 상황 생성 밸런스, NPC agenda 속도, Fact 수명 주기, 엔딩 연결 | 2~3주 | 완료 |

---

## Part 7. 기존 서비스 매핑 결정

### 유지
RngService / ResolveService / CombatService(4) / RewardsService / NpcEmotionalService / NarrativeMarkService / MemoryCollector / MemoryIntegration / EndingGenerator / LLM Pipeline(8).

### 확장
WorldStateService(locationStates/npcLocations) / WorldTickService(v2 tick 추가) / IncidentManagementService(인과관계) / SignalFeedService(Fact 기반 생성) / IntentMemoryService(IMPLICIT 감지) / SceneShellService(LocationCondition 반영) / TurnsService(SitGen+ConsequenceProc 호출).

### 신규 (7개 — 구현 API는 guides/07 참조)
LocationStateService / WorldFactService / NpcScheduleService / NpcAgendaService / NpcInteractionService / SituationGeneratorService / ConsequenceProcessorService / PlayerGoalService.

### 폐기/교체 의사결정
EventMatcherService → SituationGenerator Layer 2/3에 흡수. EventDirectorService → SituationGenerator Layer 1로 통합 (**단, 현 구현에서는 SitGen 실패 시 EventDirector로 fallback하는 하이브리드로 운영**).

**대안으로 검토했다가 폐기한 것**:
- **EventMatcher 완전 제거**: 초기 검증 위험 → 112개 자산을 버리지 않고 Template로 재활용하는 점진적 전환 채택.
- **NPC Interaction을 이벤트로 스폰**: 턴 성능 부담 → WorldTick 내부 자동 집계로 간소화.
- **장소 이동을 별도 턴 노드로 분리**: 허브스포크와 혼재되는 복잡도 → 현재 구조에서는 MOVE_LOCATION 의도로 처리 + 목적지 불명 시 HUB fallback(불변식 21).

---

## Part 8. 핵심 상수 의사결정 근거

구현 상수 값은 `guides/07_living_world_guide.md §6`에 있다. 아래는 **왜 그 값인가**에 대한 근거.

| 항목 | 값 | 근거 |
|------|-----|------|
| 장소 수 | 7 | 탐험 다양성 확보 + 콘텐츠 관리 가능 상한 |
| NPC 수 | 15~18 | 장소당 2~3명 보장 (CORE/SUB/BACKGROUND 3 tier) |
| Incident 수 | 8~10 | 장소별 1~2개 + 교차 2~3개 |
| WorldFact max 50 | permanent 20 + temporary 30 상정 | 메모리/LLM 토큰 관리 |
| Fact TTL 30턴 | ~2.5일 | 단기 영향과 장기 영향의 경계 |
| NPC agenda 최대 stage 4 | 1주일 이내 완결 | 플레이어 체감 주기 |
| Condition 장소당 max 3 | 과도한 복잡도 방지 | UI/LLM 서술 포화 방지 |
| 정보 전파 1일 (같은 세력) | 세력 내 빠른 전달 | NPC 기억의 자연스러움 |
| RUMOR 전파 2일 | 확산의 느린 속도 | "소문이 퍼지는 시간" |

---

## Part 9. 위험 요소 & 완화 전략

| 위험 | 영향 | 완화 |
|------|------|------|
| WorldFact 폭발적 증가 | 메모리/성능 | max 50 + 자동 만료 + permanent 보호 |
| NPC agenda 충돌 | 논리 모순 | `blockedBy` 필드로 상호 배제 |
| 상황 생성 품질 불균일 | 경험 저하 | SituationTemplate로 최소 품질 보장 |
| LLM 토큰 증가 | 비용/속도 | Token Budget 2500 유지, fact는 요약 전달 |
| turns.service 비대화 | 유지보수 | ConsequenceProcessor/SituationGenerator 분리 |
| 기존 호환성 | 회귀 버그 | Phase A에서 기존 기능 불변 검증 |

---

## Part 10. 성공 기준

### "살아있는 세계" 5가지 체감 테스트

1. **같은 장소, 다른 상황** — 시장을 3번 방문했을 때 매번 다른 상황
2. **내 행동의 결과** — "어제 마르코를 도왔더니, 오늘 강채린이 나를 추궁한다"
3. **NPC를 찾아가기** — "밤에 창고구에 가면 마르코를 만날 수 있다"
4. **부재 중 세계 변화** — "3일 만에 항만에 갔더니 경비대가 봉쇄하고 있다"
5. **내 목표 추적** — "밀수 조직을 추적하겠다고 결심하고, 관련 정보를 모아간다"

### 수치 목표

- 20턴 플레이 시 동일 상황 0회 (이전: 3~5회 반복)
- NPC 재회율 80% (같은 장소 같은 시간대)
- WorldFact 평균 30개 유지 (20턴 기준)
- 행동 → 후속 상황 연결률 60% 이상
