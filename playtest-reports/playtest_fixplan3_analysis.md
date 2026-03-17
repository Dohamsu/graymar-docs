# Playtest Report — Fixplan3 검증 (2026-03-17)

## 기본 정보
- **RunID**: b8093bab-5589-4708-b863-8dd365125b2d
- **프리셋**: DESERTER / male
- **턴 수**: 15턴 (목표 15)
- **최종 상태**: RUN_ACTIVE (정상 진행 중)
- **장소**: LOC_GUARD (경비대 지구) — 전 턴 체류
- **Heat**: 13/100 | **Day**: 2 | **Incidents**: 3개 활성

---

## A. 서사 흐름 (Narrative Flow)

### 턴 흐름 요약

| 턴 | 입력 | 이벤트 | 결과 |
|----|------|--------|------|
| T1 | accept_quest | — | 의뢰 수락 |
| T2 | go_guard | — | 경비대 지구 진입 |
| T4 | 주변 살펴보기 | DSC_1 | PARTIAL |
| T5 | 말 걸기 | ATM_2 | — |
| T6 | 조사 | ENC_PATROL | SUCCESS |
| T7 | 이동 시도 | ATM_2 | SUCCESS (이동 실패) |
| T8 | 선택지 사용 | INT_1 (NPC_CAPTAIN_BREN) | SUCCESS |
| T9 | 은밀 탐색 | CFT_1 | PARTIAL |
| T10 | 위협 (선택지) | CFT_1 | SUCCESS |
| T11 | 거래 | ATM_3 | PARTIAL |
| T12 | 위협 정보 요구 | ENC_RECRUIT | SUCCESS |
| T13 | 관찰 대기 | DSC_2 | FAIL |
| T14 | 단서 추적 (선택지) | DSC_2 | — |
| T15 | 탐색 심화 (선택지) | PROC_15 | SUCCESS |
| T16 | 돕기 | ATM_2 | SUCCESS |

### 평가
- **인과관계**: 턴 간 점진적 발견 흐름 존재 (순찰 관찰 → 공고문 발견 → 내부 갈등 탐지 → 모집 이벤트)
- **에스컬레이션**: T9~T10 은밀→위협 전환, T12 정보 강요 등 행동 강도 상승
- **ProceduralEvent 작동**: T15에서 PROC_15 동적 이벤트 생성 확인 ✅
- **점수**: 7/10

---

## B. NPC 일관성 (NPC Coherence)

### NPC 상태

| NPC | encounterCount | introduced | 비고 |
|-----|---------------|------------|------|
| NPC_CAPTAIN_BREN | 1 | false | T8에서 primaryNpcId로 매칭 |
| 나머지 10명 | 0 | false | 전부 미조우 |

### 평가
- **NPC 소개 시스템**: NPC_CAPTAIN_BREN만 encounter=1. CAUTIOUS 포스처라 2회 필요 → 아직 미소개 (정상)
- **TAG_TO_NPC 보충**: LOC_GUARD 이벤트 태그("PATROL", "CURFEW", "BLACKSMITH" 등)가 TAG_TO_NPC 매핑에 없음 → 태그 기반 보충이 실질적으로 작동하지 않음
- **npcPostures 일관성**: T4~T16까지 NPC_KANG_CHAERIN=CALCULATING, NPC_MOON_SEA=CAUTIOUS, NPC_GUARD_CAPTAIN=CAUTIOUS 일관 유지 ✅
- **문제**: LOC_GUARD의 11개 이벤트 중 primaryNpcId가 있는 건 INT_1(NPC_CAPTAIN_BREN) 1개뿐. 나머지 이벤트는 NPC 연결 없음
- **점수**: 5/10 (encounter 시스템 자체는 정상이나 이벤트-NPC 연결 부족)

---

## C. 맥락 유지 (Context Retention)

### 관찰
- **장소 일관성**: 15턴 전부 LOC_GUARD 체류 ✅
- **MOVE_LOCATION 미작동**: T7 "다른 장소로 이동한다" → ONGOING [SUCCESS]. MOVE_LOCATION으로 파싱되지 않고 일반 ACTION으로 처리됨 ❌
  - **원인 추정**: LlmIntentParserService가 키워드 기반 IntentParserV2 대신 LLM으로 파싱 → MOVE_LOCATION 대신 SNEAK/OBSERVE 등으로 분류
- **structuredMemory**: None (장소 이탈 없었으므로 finalizeVisit 미호출 — 검증 불가)
- **점수**: 6/10

---

## D. 시스템 점검

### P1. structuredMemory — ⚠️ 검증 불가
- 15턴 동안 한 번도 장소를 이탈하지 않아 `finalizeVisit()` 호출 시점 없음
- `memoryCollector.collectFromTurn()`은 매 턴 호출 (nodeMemories에 축적 중)
- **다음 테스트에서 장소 이동 포함 필요**

### P2. NPC encounterCount — ⚠️ 부분 작동
- eventPrimaryNpcId 경로: NPC_CAPTAIN_BREN encounter=1 ✅
- TAG_TO_NPC 경로: LOC_GUARD 이벤트 태그가 TAG_TO_NPC에 없어 실질 작동 안 됨
- **대안**: LOC_GUARD 이벤트에 NPC 태그 추가 또는 TAG_TO_NPC 확장 필요

### P4. MOVE_LOCATION — ❌ 미작동
- "다른 장소로 이동한다" 가 MOVE_LOCATION으로 파싱 실패
- **근본 원인**: `llmIntentParser.parseWithInsistence()`가 LLM 기반으로 파싱 → 키워드 매칭(IntentParserV2)의 MOVE_LOCATION 키워드를 무시
- `turns.service.ts`의 MOVE_LOCATION 분기 자체에 도달하지 못함
- **수정 필요**: LlmIntentParserService에서 MOVE_LOCATION 키워드 우선 감지 로직 추가

### P5. 이벤트 반복 — ✅ 개선 확인
- **10종 고유 이벤트** / 15턴 (이전: 5종 / 15턴)
- 연속 2턴 같은 이벤트 반복: 없음 (CHOICE sourceEventId 제외)
- ATM_2가 3회 사용되었으나 T5→T7→T16으로 분산 (연속 아님)
- ProceduralEvent(PROC_15) 생성 확인 ✅

### P7. 조기 RUN_ENDED — ✅ 작동 확인
- 15턴 완료 후 RUN_ACTIVE 유지
- Incidents 3개 모두 미해결 → ALL_RESOLVED 조건 미달
- 최소 15턴 가드가 직접 발동된 케이스는 아니나, 엔딩 미발생 확인

### P10. 한국어 조사 — ✅ (엔딩 미발생으로 직접 검증 불가, 코드 확인 완료)

---

## E. 점수 (10점 만점)

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 7/10 | 점진적 발견, ProceduralEvent 작동 |
| NPC 일관성 | 5/10 | posture 일관성 OK, encounter 축적 부족 |
| 맥락 유지 | 6/10 | 장소 일관, 이동 실패, 메모리 미검증 |
| 이벤트 다양성 | 8/10 | 10종/15턴, 연속 반복 없음 ✅ |
| 메모리 시스템 | 4/10 | structuredMemory=None, 검증 불가 |
| **종합** | **6.0/10** | Fixplan3 P5/P7 확인, P4 미작동 |

---

## F. 개선 권장사항

### Critical
1. **P4 재수정: MOVE_LOCATION 파싱 경로 보강**
   - `LlmIntentParserService.parseWithInsistence()`에서 MOVE_LOCATION 키워드("이동", "다른 장소", "떠나") 감지 시 LLM 결과보다 우선 적용
   - 또는 `turns.service.ts`에서 LLM 파싱 결과와 별도로 IntentParserV2 키워드 매칭 병행 → MOVE_LOCATION 키워드 감지 시 강제 적용

### High
2. **LOC_GUARD 이벤트 NPC 연결 보강**
   - `events.json`의 LOC_GUARD 이벤트에 `primaryNpcId` 추가 (최소 3~4개 이벤트)
   - 또는 TAG_TO_NPC에 LOC_GUARD 태그 추가: `GUARD_CAPTAIN → NPC_GUARD_CAPTAIN`, `CAPTAIN_BREN → NPC_CAPTAIN_BREN`

3. **장소 이동 포함 테스트 설계**
   - 플레이테스트 스크립트에서 5~6턴마다 go_hub CHOICE 강제 선택 → 장소 이동 → structuredMemory 검증

### Medium
4. **actionContext.actionType 누락 조사**
   - 모든 턴에서 `actionContext.actionType = null` — serverResult.ui에 actionType이 전달되지 않음
   - LLM 컨텍스트의 `[현재 장면 상태]` 블록에서 행동 타입 정보 부재 가능성

### Low
5. **TALK actionType 비판정 처리**
   - T5 "근처 사람에게 말을 건다" → resolveOutcome=null (비판정). 이는 TALK이 비도전 행위로 분류되어 정상 동작이나, LLM 서술의 깊이가 얕아질 수 있음
