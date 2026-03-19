# 플레이테스트 리포트 — 2026-03-19 Session 4

## A. 기본 정보

| 항목 | 1차 | 2차 (수정 후) |
|------|-----|-------------|
| RunID | 00838813 | cfe0e2ca |
| 프리셋 | DESERTER | DESERTER |
| 턴 수 | 20 | 20 |
| HP / Gold | 100 / 63 | 100 / ? |
| Heat | 10 | 11 |
| Incidents | 3개 | 2개 |
| 방문 장소 | market→guard→harbor→slums | market→guard→harbor→slums |

## B. 턴 흐름 요약 (1차)

| 턴 | 장소 | 입력 | 이벤트 | 결과 | 비고 |
|----|------|------|--------|------|------|
| T01 | HUB | accept_quest | - | - | 퀘스트 수락 |
| T02 | HUB | go_market | - | - | 시장 이동 |
| T03 | LOC | 주변을 살펴본다 | EVT_MARKET_INT_2 | PARTIAL | |
| T04 | LOC | 경비병의 동태를 살핀다 | EVT_MARKET_INT_2 | PARTIAL | |
| T05 | LOC | 조심스럽게 잠입한다 | EVT_MARKET_ATM_3 | SUCCESS | |
| T06 | LOC | 도움을 준다 | EVT_MARKET_ATM_3 | SUCCESS | |
| T07 | LOC | move_location | - | - | |
| T08 | HUB | go_guard | - | - | 경비대 이동 |
| T09 | LOC | guard_observe | PROC_12 | FAIL | ProceduralEvent |
| T10 | LOC | 물건을 훔친다 | EVT_GUARD_ENC_PATROL | PARTIAL | |
| T11 | LOC | grd_enc_pat_chat | EVT_GUARD_ENC_PATROL | PARTIAL | |
| T12 | LOC | 싸움을 건다 | EVT_GUARD_ATM_1 | SUCCESS | |
| T13 | LOC | move_location | - | - | |
| T14 | HUB | go_harbor | - | - | 항만 이동 |
| T15 | LOC | 소문의 진위를 확인 | EVT_HARBOR_DSC_3 | SUCCESS | |
| T16 | LOC | hbr_dsc3_mark | EVT_HARBOR_DSC_3 | - | 선택지 |
| T17 | LOC | 주변을 살펴본다 | EVT_HARBOR_ATM_3 | SUCCESS | |
| T18 | LOC | 조심스럽게 잠입한다 | EVT_HARBOR_ATM_3 | SUCCESS | |
| T19 | LOC | move_location | - | - | |
| T20 | HUB | go_slums | - | - | 빈민가 이동 |

## C. 종합 점수

| 항목 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 서사 흐름 | 6.5 | 7.5 | **+1.0** |
| NPC 일관성 | 4.5 | 7.5 | **+3.0** |
| 맥락 유지 | 6.5 | 7.0 | **+0.5** |
| 이벤트 다양성 | 6.5 | 7.0 | +0.5 |
| 메모리 시스템 | 7.0 | 7.0 | 0 |
| **종합** | **6.2** | **7.2** | **+1.0** |

## D. 수정 내용

1. **TAG_TO_NPC 확장** (`memory-collector.service.ts`): GUARD_MORALE, PATROL, SHIFT_CHANGE → NPC_GUARD_CAPTAIN 등 장소별 태그-NPC 매핑 추가
2. **NPC 별칭 반복 억제** (`prompt-builder.service.ts`): 미소개 NPC 별칭 지시를 간략화 + 연속 턴 반복 금지 지시 추가
3. **NPC injection 임계치 완화** (`turn-orchestration.service.ts`): agenda만 있어도 injection 발동 (score 2 → 임계치 2)

---

## [1] 이벤트 서술 품질 심층

### 서술 길이
- 1차: 평균 773ch, 최소 308, 최대 963
- 2차: 평균 711ch, 최소 311, 최대 1065

### 반복 표현 비교

| 표현 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| "권위적인 야간 경비" | 11회 | 7회 | **-4** |
| "약초 노점의 노부인" | 3회 | 2회 | **-1** |

- 프롬프트 지시 개선으로 별칭 반복 30% 감소
- 여전히 7회 반복은 개선 여지 있음 (LLM 행동 한계)

### NPC 실명 등장 (2차)
- "에드릭" (NPC_SEO_DOYUN): T04, T06, T12~T15 — introduced=True 후 실명 사용 ✅
- "하를런" (NPC_YOON_HAMIN): T19~T23 — introduced=True 후 실명 사용 ✅
- 1차에서는 NPC 실명이 한 번도 등장하지 않았음 → 대폭 개선

### 점수: 1차 6.5 → 2차 7.5 (+1.0)

---

## [2] 맥락 유지 & NPC 성향 심층

### NPC encounterCount 비교

| NPC | 1차 enc | 2차 enc | 1차 intro | 2차 intro |
|-----|---------|---------|-----------|-----------|
| NPC_SEO_DOYUN | 0 | **4** | ❌ | **✅** |
| NPC_YOON_HAMIN | 0 | **4** | ❌ | **✅** |
| NPC_KANG_CHAERIN | 0 | **2** | ❌ | ❌ (CALCULATING→3회) |
| NPC_RENNICK | 1 | 0 | ❌ | ❌ |
| NPC_BAEK_SEUNGHO | 1 | 0 | ❌ | ❌ |

- **2명 NPC 소개 성공** (1차 0명 → 2차 2명): 에드릭, 하를런
- NPC injection 활성화로 만남 횟수 대폭 증가
- NPC_KANG_CHAERIN enc=2: CALCULATING posture로 3회 필요 → 다음 방문에서 소개 가능

### NPC 감정축 변화 (2차)
- NPC_SEO_DOYUN: trust=-3, fear=25.5 — 위협 행동으로 공포 축적 ✅ (자연스러움)
- NPC_YOON_HAMIN: trust=10 — 도움 행동으로 신뢰 유지 ✅

### 점수: 1차 4.5 → 2차 7.5 (+3.0)

---

## [6] 장소 전환 & HUB 심층

### 장소 순회 (동일)
- 1차/2차 모두: market → guard → harbor → slums (4종 순환) ✅
- 각 5턴 체류 (loc-turns=4 + move_location 1턴)
- MOVE_LOCATION 3회 모두 정상 처리 ✅
- finalizeVisit: visitLog 3건 정상 ✅

### 점수: 1차 8.5 → 2차 8.5 (동일)

---

## 수정 전후 비교

| 항목 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 서사 흐름 | 6.5 | 7.5 | **+1.0** |
| NPC 일관성 | 4.5 | 7.5 | **+3.0** |
| 맥락 유지 | 6.5 | 7.0 | +0.5 |
| 이벤트 다양성 | 6.5 | 7.0 | +0.5 |
| 메모리 시스템 | 7.0 | 7.0 | 0 |
| **종합** | **6.2** | **7.2** | **+1.0** |

### 수정 항목별 검증
- [✅] TAG_TO_NPC 확장: NPC_KANG_CHAERIN enc 0→2, NPC injection 활성화
- [✅] NPC 별칭 반복 억제: "권위적인 야간 경비" 11→7회 감소
- [✅] NPC injection 임계치 완화: NPC_SEO_DOYUN enc=4 intro=True, NPC_YOON_HAMIN enc=4 intro=True
- [✅] NPC 실명 등장: 에드릭/하를런 실명이 서술에 사용됨
