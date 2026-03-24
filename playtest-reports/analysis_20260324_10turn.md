# 플레이테스트 분석 리포트 (2026-03-24, 10턴)

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | e2d6ace3-d3d8-4691-89a0-ad89c9547b3c |
| 프리셋 | DESERTER |
| 턴 수 | 10 |
| HP | 100 (변동 없음) |
| Heat | 14 |
| Day | 1 |
| Incidents | 2개 활성 (INC_SMUGGLING_RING, INC_MARKET_THEFT) |
| 검증 | 6/6 PASS |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 판정 | 서술(자) |
|----|------|------|--------|------|---------|
| T01 | HUB | CHOICE:accept_quest | - | - | 265 |
| T02 | HUB | CHOICE:go_market | - | - | 409 |
| T03 | LOCATION(시장) | 거래를 시도한다 | PROC_4 | PARTIAL | 566 |
| T04 | LOCATION(시장) | 물건을 훔친다 | PROC_5 | SUCCESS | 631 |
| T05 | LOCATION(시장) | 골목길 벽에 기대어 관찰 | SIT_CONSEQUENCE | SUCCESS | 839 |
| T06 | LOCATION(시장) | 주변을 살펴본다 | SIT_CONSEQUENCE | SUCCESS | 541 |
| T07 | LOCATION(시장) | move_location | - | - | 505 |
| T08 | HUB | CHOICE:go_guard | - | - | 479 |
| T09 | LOCATION(경비대) | 설득한다 | PROC_12 | PARTIAL | 468 |
| T10 | LOCATION(경비대) | CHOICE:encounter_observe | SIT_CONSEQUENCE | SUCCESS | 715 |

## C. 종합 점수

| 항목 | 점수 | 비고 |
|------|------|------|
| 1. 이벤트 서술 품질 | 8/10 | 문장 자연스러움, 반복 표현 0건 |
| 2. 맥락 유지 & NPC | 6/10 | NPC 3명 만남, intro 1명만 |
| 3. 이벤트 다양성 | 7/10 | 고유 5종/6건, SIT_CONSEQUENCE 반복 |
| 4. 메모리 시스템 | 6/10 | visitLog 1건, storySummary 미생성 |
| 5. 판정 & 밸런스 | 5/10 | FAIL 0건 (편향), SUCCESS 67% |
| 6. 장소 전환 & HUB | 8/10 | 시장→경비대 정상 전환 |
| 7. Incident & 시그널 | 7/10 | 2개 활성, 정상 작동 |
| **종합** | **6.7/10** | |

---

## [1] 이벤트 서술 품질 심층 (8/10)

### 긍정적
- 서술 평균 541자 (적절한 길이)
- 반복 표현 0건 (3어절 이상 3회 반복 없음)
- 시장 분위기 묘사 우수 ("노점상들의 분주함", "생선 상인의 큰소리")
- 감각 묘사 존재 (시각+청각)

### 개선 필요
- 최소 265자(T01)와 최대 839자(T05) 편차 큼 → 길이 일관성
- HUB 서술이 상대적으로 짧음

---

## [2] 맥락 유지 & NPC 성향 심층 (6/10)

### NPC 만남 현황
| NPC | 만남 수 | 소개됨 | 태도 |
|-----|---------|--------|------|
| NPC_SEO_DOYUN | 3 | ✅ | CAUTIOUS |
| NPC_KANG_CHAERIN | 2 | ❌ | CALCULATING |
| NPC_MOON_SEA | 1 | ❌ | CAUTIOUS |

### 문제점
- **NPC_KANG_CHAERIN**: 2회 만남 + CALCULATING인데 소개 안 됨
  → CAUTIOUS 2회에서 소개되는 규칙. CALCULATING은 별도 규칙 필요?
- **NPC_SEO_DOYUN**: 3회 만남에서 소개됨 (CAUTIOUS 2회 규칙 충족)
- 전체 42명 NPC 중 3명만 만남 (7%) — 10턴 내에서는 정상

### 감정축
- 대부분 초기값 유지 (trust ±10 수준)
- 급격한 감정 변화 없음 (안정적)

---

## [3] 이벤트 다양성 심층 (7/10)

### 이벤트 분포
| 이벤트 ID | 횟수 | 타입 |
|-----------|------|------|
| PROC_4 | 1 | Procedural |
| PROC_5 | 1 | Procedural |
| PROC_12 | 1 | Procedural |
| SIT_CONSEQUENCE_fact_player_action_t5 | 2 | Situation |
| SIT_CONSEQUENCE_fact_player_action_t12 | 1 | Situation |

- 고유 5종 / 6건 = 83% 다양성 (양호)
- SIT_CONSEQUENCE 계열이 50% (3/6) — Situation 이벤트 편중
- Procedural 이벤트 3건 = 50%

### 문제점
- 고정 이벤트(events_v2.json)에서 매칭된 것이 0건 → EventDirector가 고정 이벤트를 매칭하지 못함
- SIT_CONSEQUENCE 반복 → SituationGenerator가 같은 worldFact에서 반복 생성

---

## [4] 메모리 시스템 심층 (6/10)

| 항목 | 상태 | 비고 |
|------|------|------|
| visitLog | 1건 | 시장 방문 기록 |
| npcJournal | 11건 | 정상 |
| storySummary | 없음 ❌ | finalizeVisit 미호출? |
| structuredMemory | 존재 | |

### 문제점
- **storySummary 미생성**: 시장에서 경비대로 이동했는데 storySummary가 없음
  → finalizeVisit()이 호출되지 않았거나, storySummary 생성이 비동기로 실패
- visitLog가 1건뿐 (시장 1회 방문 기록은 있음)
- 10턴 내에 Mid Summary 생성 조건(6턴 초과) 충족 → 확인 필요

---

## [5] 판정 & 밸런스 심층 (5/10)

### 판정 분포
| 결과 | 횟수 | 비율 | 기대 |
|------|------|------|------|
| SUCCESS | 4 | 67% | ~30% |
| PARTIAL | 2 | 33% | ~40% |
| FAIL | 0 | 0% | ~30% |

### 문제점
- **FAIL 0건**: 10턴 내 6번 판정에서 한 번도 실패 없음 → 난이도 너무 낮음
- SUCCESS 67%는 기대값(30%)의 2배 이상
- HP 100 유지 (전투 없음) → 전투 노드 미진입

### 원인 추정
- DESERTER 프리셋의 스탯이 전체적으로 높음 (str11, dex10, wit9, con9, per10, cha8)
- baseMod가 0이거나 양수일 가능성
- 1d6 + floor(stat/3) + baseMod ≥ 6이면 SUCCESS인데, floor(10/3)=3 → 1d6에서 3 이상이면 SUCCESS

---

## [6] 장소 전환 & HUB 심층 (8/10)

### 방문 패턴
| 장소 | 체류 턴 | 전환 방식 |
|------|---------|----------|
| HUB | 2턴 | quest 수락 → 시장 이동 |
| 시장 (market) | 4턴 | move_location → HUB 복귀 |
| HUB | 1턴 | 경비대 이동 |
| 경비대 (guard) | 2턴 | (진행 중) |

- HUB→LOCATION 전환 정상 ✅
- LOCATION→HUB 복귀 정상 ✅ (T07 move_location)
- 장소당 체류: 시장 4턴, 경비대 2턴+ (적절)

---

## [7] Incident & 시그널 심층 (7/10)

### 활성 Incident
| ID | Stage | Control | Pressure |
|----|-------|---------|----------|
| INC_SMUGGLING_RING | 0 | 0 | 18 |
| INC_MARKET_THEFT | 0 | 35 | 12 |

- 2개 사건 정상 spawn ✅
- control/pressure 변화 관찰됨
- INC_MARKET_THEFT: control 35 → 플레이어 행동(시장에서 거래/절도)이 반영된 것으로 추정

### 시그널
- hubHeat: 14 (기본 0에서 증가) → 활동에 따른 변화 정상

---

## D. 개선 권장사항

### Critical
1. **판정 난이도 조정** — SUCCESS 67%는 너무 높음. baseMod 하향 또는 판정 기준선 상향 검토

### High
2. **storySummary 미생성** — finalizeVisit() 호출 여부 및 LLM 요약 생성 확인
3. **고정 이벤트 매칭 실패** — EventDirector가 events_v2.json의 112개 이벤트를 활용하지 못함

### Medium
4. **SIT_CONSEQUENCE 반복** — SituationGenerator 다양성 개선
5. **NPC CALCULATING 소개 규칙** — CALCULATING 태도에서의 이름 공개 기준 확인

### Low
6. **서술 길이 편차** — HUB 서술이 짧음 (265자 vs LOCATION 평균 627자)
7. **전투 노드 미진입** — 10턴 내 전투가 한 번도 발생하지 않음
