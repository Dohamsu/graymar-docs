# Playtest Report — Fixplan3 v2 검증 (2026-03-17, 서버 재시작 후)

## 기본 정보
- **RunID**: 3ce1a9a7-934b-4d9d-8b47-dba7ec115232
- **프리셋**: DESERTER / male
- **턴 수**: 15턴 기록 (실 게임 턴 T1~T20, HUB/이동 턴 포함)
- **최종 상태**: RUN_ACTIVE (정상 진행 중)
- **방문 장소**: LOC_MARKET → LOC_GUARD → LOC_HARBOR (3곳 이동!)
- **Heat**: 1/100 | **Day**: 1 | **Incidents**: 1개 활성 (INC_MARKET_THEFT)

---

## A. 서사 흐름 (Narrative Flow)

### 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 결과 |
|----|------|------|--------|------|
| T1 | HUB | accept_quest | — | 의뢰 수락 |
| T2 | HUB | go_market | — | 시장 거리 진입 |
| T4 | MARKET | 주변 살펴보기 | ATM_3 (사과 소동) | PARTIAL |
| T5 | MARKET | 말 걸기 | ATM_1 (향신료 가게) | — |
| T6 | MARKET | 조사 | ENC_PEDDLER (이국 행상) | SUCCESS |
| T7 | MARKET | 뒷골목 탐색 | CFT_1 (건달 갈취) | FAIL |
| **T8** | **MARKET** | **"다른 장소로 이동한다"** | **sys: HUB 복귀** | **NODE_ENDED** ✅ |
| T10 | HUB | go_guard | — | 경비대 진입 |
| T12 | GUARD | 관찰 대기 | OPP_REWARD (현상금) | PARTIAL |
| T13 | GUARD | 살펴보기 | ATM_3 (훈련장) | SUCCESS |
| T14 | GUARD | 말 걸기 | INT_1 (BREN 대위) | — |
| T15 | GUARD | 조사 | DSC_1 (소각 문서) | SUCCESS |
| **T16** | **GUARD** | **"다른 장소로 이동한다"** | **sys: HUB 복귀** | **NODE_ENDED** ✅ |
| T18 | HUB | go_harbor | — | 항만 진입 |
| T20 | HARBOR | 뒷골목 탐색 | OPP_WRECK (난파 보트) | SUCCESS |

### 평가
- **P4 MOVE_LOCATION 완전 작동**: T8, T16에서 "다른 장소로 이동한다" → NODE_ENDED → HUB 복귀 → 새 장소 선택 정상 동작
- **3개 장소 순회**: MARKET(4턴) → GUARD(4턴) → HARBOR(1턴+) — 다양한 환경 체험
- **이벤트 연속성**: 시장에서 관찰→대화→조사→잠입→이동, 경비대에서 관찰→관찰→대화→조사→이동 자연스러운 흐름
- **storySummary 생성**: `"[시장 거리 방문] 관찰(부분성공), 대화(성공), 조사(성공)\n[경비대 지구 방문] 관찰(부분성공), 관찰(성공), 대화(성공). 브렌 대위 만남"` — P1 finalizeVisit 호출 확인
- **점수**: 8/10

---

## B. NPC 일관성 (NPC Coherence)

### NPC 상태

| NPC | encounterCount | introduced | 비고 |
|-----|---------------|------------|------|
| NPC_CAPTAIN_BREN | 1 | false | T14에서 primaryNpcId로 매칭 |
| 나머지 10명 | 0 | false | 전부 미조우 |

### 장소별 NPC Posture

| 장소 | NPC Postures |
|------|-------------|
| LOC_MARKET | SEO_DOYUN=CAUTIOUS, KANG_CHAERIN=CALCULATING, MOON_SEA=CAUTIOUS |
| LOC_GUARD | KANG_CHAERIN=CALCULATING, MOON_SEA=CAUTIOUS, GUARD_CAPTAIN=CAUTIOUS |
| LOC_HARBOR | YOON_HAMIN=FRIENDLY, BAEK_SEUNGHO=CAUTIOUS, INFO_BROKER=CALCULATING |

### 평가
- **NPC posture 장소별 변화**: 장소 이동에 따라 적절한 NPC posture가 표시됨 — 시스템 정상
- **encounterCount 여전히 부족**: 11명 중 NPC_CAPTAIN_BREN만 1회. TAG_TO_NPC에 LOC_GUARD/LOC_MARKET/LOC_HARBOR 태그 미등록이 주 원인
- **점수**: 5/10 (posture 전환 정상, encounter 축적 부족 지속)

---

## C. 맥락 유지 (Context Retention)

### 관찰
- **장소 전환 정상**: MARKET → HUB → GUARD → HUB → HARBOR 3회 이동 성공
- **MOVE_LOCATION 정상 작동**: T8, T16 모두 `NODE_ENDED` + `transition.nextNodeType: "HUB"` ✅
  - 이벤트 텍스트: `"다른 장소를 찾아 거점으로 돌아간다."` — 적절한 시스템 메시지
- **storySummary 축적**: 시장/경비대 방문 기록이 storySummary에 정상 저장 ✅
- **structuredMemory**: null — `run_memories` 레코드가 LLM Worker에 의해 아직 생성되지 않았을 가능성 (storySummary는 legacy fallback으로 정상 작동)
- **actionHistory 리셋**: 장소 이동 시 actionHistory가 초기화됨 (len=1, 마지막 HARBOR 턴만 남음) — 정상 동작
- **점수**: 8/10

---

## D. 시스템 점검

### P1. structuredMemory — ⚠️ 부분 작동
- **storySummary 정상**: `finalizeVisit()` 호출되어 시장/경비대 방문 기록 축적 확인 ✅
- **structuredMemory=null**: `run_memories` DB 레코드가 없거나 LLM Worker 미생성
  - `storySummary`는 `runState` 내부 필드로 정상 저장 (legacy fallback)
  - `structuredMemory`는 `run_memories` 테이블의 별도 컬럼 → LLM Worker가 첫 내러티브 생성 시 INSERT
- **결론**: P1 코드 수정(RUN_ENDED 전 finalizeVisit)은 검증 불가하나, 장소 이동 시 finalizeVisit은 정상 작동

### P2. NPC encounterCount — ⚠️ 개선 필요
- NPC_CAPTAIN_BREN만 encounter=1 (T14 INT_1 이벤트의 primaryNpcId)
- TAG_TO_NPC 보충 로직 자체는 코드에 추가됨, 하지만:
  - LOC_MARKET 이벤트 태그: ACCIDENT, DAILY_LIFE, SPICE, PEDDLER, EXTORTION, THUGS — TAG_TO_NPC에 없음
  - LOC_GUARD 이벤트 태그: BOUNTY, TRAINING, NPC_CAPTAIN_BREN, DISCOVERY — `NPC_CAPTAIN_BREN` 태그는 있지만 T14 기준 이미 eventPrimaryNpc로 처리됨
  - LOC_HARBOR 이벤트 태그: WRECK, SALVAGE — TAG_TO_NPC에 없음
- **필요 조치**: TAG_TO_NPC 매핑 확장 또는 이벤트 `primaryNpcId` 직접 추가

### P4. MOVE_LOCATION — ✅ 완전 작동!
- T8: "다른 장소로 이동한다" → `NODE_ENDED` + `transition: {nextNodeType: "HUB"}` ✅
- T16: "다른 장소로 이동한다" → `NODE_ENDED` + `transition: {nextNodeType: "HUB"}` ✅
- `llm-intent-parser.service.ts` 수정 (KW MOVE_LOCATION 무조건 우선) + `turns.service.ts` HUB fallback 모두 정상 작동
- 시스템 메시지: `"다른 장소를 찾아 거점으로 돌아간다."` — 자연스러운 표현

### P5. 이벤트 반복 — ✅ 개선 확인
- **9종 고유 이벤트** / 실질 10 LOCATION 턴:
  - MARKET: ATM_3, ATM_1, ENC_PEDDLER, CFT_1 (4종)
  - GUARD: OPP_REWARD, ATM_3, INT_1, DSC_1 (4종)
  - HARBOR: OPP_WRECK (1종)
- 연속 2턴 같은 이벤트: 없음 ✅
- 장소 간 이벤트 중복: ATM_3가 MARKET과 GUARD 모두에 있으나 다른 장소이므로 정상

### P7. 조기 RUN_ENDED — ✅ 작동 확인
- 20턴까지 RUN_ACTIVE 유지
- Incidents: INC_MARKET_THEFT 1개, control=22, pressure=18 — 미해결

### P10. 한국어 조사 — 미검증 (엔딩 미발생)

---

## E. 점수 (10점 만점)

| 항목 | 이전 | 금번 | 비고 |
|------|------|------|------|
| 서사 흐름 | 7 | **8/10** | 3장소 순회, 자연스러운 이동 |
| NPC 일관성 | 5 | **5/10** | posture 장소별 전환 OK, encounter 부족 지속 |
| 맥락 유지 | 6 | **8/10** | MOVE_LOCATION 작동, storySummary 축적 |
| 이벤트 다양성 | 8 | **9/10** | 9종/10 LOCATION턴, 연속 반복 없음 |
| 메모리 시스템 | 4 | **6/10** | storySummary 정상, structuredMemory=null |
| **종합** | **6.0** | **7.2/10** | P4 완전 해결, 전반적 개선 |

---

## F. 개선 권장사항

### High
1. **TAG_TO_NPC 매핑 확장**
   - 현재 매핑에 LOC_GUARD/MARKET/HARBOR 이벤트 태그 추가 필요
   - 또는 이벤트 JSON에 `primaryNpcId` 직접 추가 (더 확실한 방법)
   - 없으면 NPC 이름 공개 시스템이 사실상 작동하지 않음

2. **structuredMemory null 원인 조사**
   - `run_memories` 테이블에 해당 run의 레코드 존재 여부 확인
   - LLM Worker가 `run_memories` INSERT 타이밍 확인
   - `storySummary`(runState 내부)는 정상 → structuredMemory(run_memories 컬럼)만 연결 문제

### Medium
3. **actionContext.actionType 누락**
   - 전 턴에서 `actionContext.actionType = null`
   - IntentParser 결과가 serverResult.ui로 전달되지 않는 것으로 보임

### Low
4. **HUB 이동 시 한국어 조사 개선**
   - `"경비대 지구(으)로 향한다"`, `"항만 부두(으)로 향한다"` — `(으)` 하드코딩
   - `korParticle()` 활용하여 `"경비대 지구로"`, `"항만 부두로"` 자연스럽게 처리

---

## G. Fixplan3 최종 검증 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| P1. RUN_ENDED 시 finalizeVisit | ⚠️ 간접 확인 | storySummary 축적 OK, structuredMemory null |
| P2. NPC encounterCount 보충 | ⚠️ 코드 OK, 데이터 부족 | TAG_TO_NPC에 매핑 없음 |
| P4. MOVE_LOCATION | ✅ **완전 해결** | T8, T16 모두 정상 |
| P5. 씬 연속성 1턴 제한 | ✅ **작동** | 연속 반복 없음 |
| P7. 조기 엔딩 방지 | ✅ **작동** | 20턴 RUN_ACTIVE |
| P10. 한국어 조사 | ⚠️ 미검증 | 엔딩 미발생 |
