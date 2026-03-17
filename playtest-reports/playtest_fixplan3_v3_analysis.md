# Playtest Report — Fixplan3 v3 검증 (2026-03-17)

## 기본 정보
- **RunID**: 5d4152bd-7f75-4b00-ba6b-c42957fec83a
- **프리셋**: DESERTER / male
- **턴 수**: 18턴 기록 (실 게임 턴 T1~T23)
- **최종 상태**: RUN_ACTIVE (정상 진행 중)
- **방문 장소**: LOC_MARKET (3회 방문 — 스크립트가 항상 go_market 선택)
- **Heat**: 0/100 | **Day**: 2 | **Incidents**: 1개 활성

---

## A. 서사 흐름 (Narrative Flow)

| 턴 | 장소 | 입력 | 이벤트 | 결과 | 비고 |
|----|------|------|--------|------|------|
| T1 | HUB | accept_quest | — | ONGOING | |
| T2 | HUB | go_market | — | NODE_ENDED | →LOCATION |
| T4 | MARKET | 살펴보기 | PROC_4 (동적) | PARTIAL | ProceduralEvent |
| T5 | MARKET | 말 걸기 | ENC_DISPUTE | — | |
| T6 | MARKET | 조사 | PROC_6 (동적) | PARTIAL | ProceduralEvent |
| T7 | MARKET | CHOICE llm_6_0 | OPP_ERRAND (미렐라) | PARTIAL | **NPC_MIRELA INTRO** |
| **T8** | **MARKET** | **"다른 장소로 이동"** | — | **NODE_ENDED** | **P4 ✅** |
| T10 | HUB | go_market | — | NODE_ENDED | →LOCATION |
| T12 | MARKET | 뒷골목 탐색 | CFT_1 | PARTIAL | |
| T13 | MARKET | 거래 | OPP_ERRAND (미렐라) | PARTIAL | npc=NPC_MIRELA |
| T14 | MARKET | 위협 | ENC_BUSKER | SUCCESS | |
| T15 | MARKET | CHOICE llm_14_0 | OPP_LOST_CARGO | FAIL | |
| **T16** | **MARKET** | **"다른 장소로 이동"** | — | **NODE_ENDED** | **P4 ✅** |
| T18 | HUB | go_market | — | NODE_ENDED | →LOCATION |
| T20 | MARKET | 관찰 | ENC_DISPUTE | SUCCESS | |
| T21 | MARKET | 돕기 | ATM_1 | PARTIAL | |
| T22 | MARKET | 설득 | ENC_PEDDLER | PARTIAL | |
| T23 | MARKET | CHOICE llm_22_0 | OPP_LOST_CARGO | PARTIAL | |

### 평가
- **P4 MOVE_LOCATION**: T8, T16 모두 정상 작동 ✅
- **ProceduralEvent**: T4 PROC_4, T6 PROC_6 동적 이벤트 2개 생성 ✅
- **NPC 소개 시스템**: T7에서 NPC_MIRELA 정식 소개 ✅ (encounterCount 충족)
- **LLM 선택지 활용**: T7, T15, T23에서 LLM 생성 선택지 사용
- **이벤트 다양성**: 9종 고유 이벤트 / 12 LOCATION턴 (ProceduralEvent 2개 포함)
- **점수**: 8/10

---

## B. NPC 일관성 (NPC Coherence)

- **NPC_MIRELA**: T7에서 `newlyIntroducedNpcIds: ['NPC_MIRELA']`로 정식 소개 ✅
  - T13에서 재등장 (primaryNpcId=NPC_MIRELA) → 일관성 있는 NPC 연결
- **npcStates 최종 상태**: API 응답에서 npcStates가 빈 객체로 반환됨 ⚠️
  - 게임 중에는 NPC 추적 정상, 하지만 최종 조회 시 비어있음
- **점수**: 7/10 (소개 시스템 작동 확인, 최종 상태 조회 이슈)

---

## C. 맥락 유지 (Context Retention)

- **장소 전환**: T8, T16 MOVE_LOCATION → HUB 복귀 정상 ✅
- **storySummary**: **None** ❌ — finalizeVisit 호출되었으나 storySummary 미저장
- **structuredMemory**: **null** ❌
- **점수**: 6/10

---

## D. Fixplan3 항목별 최종 검증

| # | 항목 | 상태 | 비고 |
|---|------|------|------|
| P4 | MOVE_LOCATION | ✅ 완전 작동 | T8, T16 NODE_ENDED |
| P5 | 이벤트 다양성 | ✅ 작동 | 9종/12턴, 연속 반복 없음 |
| P7 | 조기 엔딩 방지 | ✅ 작동 | 23턴 RUN_ACTIVE |
| P2 | NPC 소개 | ✅ 작동 | NPC_MIRELA T7 소개 |
| P1 | structuredMemory | ❌ 미작동 | storySummary=None |
| P10 | 한국어 조사 | ⚠️ 미검증 | 엔딩 미발생 |

---

## E. 점수 (10점 만점)

| 항목 | v2 → v3 | 비고 |
|------|---------|------|
| 서사 흐름 | 8 → **8/10** | ProceduralEvent + LLM 선택지 |
| NPC 일관성 | 5 → **7/10** | NPC_MIRELA 소개 성공! |
| 맥락 유지 | 8 → **6/10** | storySummary 미저장 ❌ |
| 이벤트 다양성 | 9 → **9/10** | 9종, ProceduralEvent 2개 |
| 메모리 시스템 | 6 → **4/10** | storySummary/structuredMemory 모두 null |
| **종합** | **7.2** → **6.8/10** | NPC 개선, 메모리 퇴보 |

---

## F. 문제점 리스트

### 1. [Critical] storySummary 미저장 — finalizeVisit 호출되나 결과 미반영
- **현상**: T8, T16에서 MOVE_LOCATION → NODE_ENDED 후 HUB 복귀 시 finalizeVisit 호출
- **그러나**: 최종 상태의 storySummary = None
- **가설**: MOVE_LOCATION HUB fallback 경로에서 finalizeVisit 결과가 runState에 반영되지 않거나, 후속 턴이 runState를 덮어씀
- **조사 필요**: `turns.service.ts`의 MOVE_LOCATION HUB fallback 경로에서 finalizeVisit 결과가 실제로 DB에 저장되는지

### 2. [High] structuredMemory null — run_memories 연결 문제
- **현상**: 3회 방문/이동 후에도 structuredMemory가 null
- **가설**: run_memories 테이블 레코드 미생성, 또는 finalizeVisit 결과가 해당 컬럼에 저장되지 않음

### 3. [Medium] HUB 위치 선택지 순서 고정
- **현상**: go_market이 항상 첫 번째 → 스크립트가 항상 같은 장소 선택 (스크립트 이슈)
- **영향**: 다른 장소 이벤트 검증 불가

### 4. [Low] npcStates 최종 조회 시 빈 객체
- **현상**: 게임 중 NPC 추적 정상이나, GET /runs/:id 응답의 worldState.npcStates가 비어있음
- **가설**: HUB 복귀 시 worldState가 리셋되거나, npcStates가 다른 경로에 저장됨
