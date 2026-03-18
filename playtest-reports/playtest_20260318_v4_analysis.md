# Playtest Report — 2026-03-18 v4

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | b87975a3-8dc5-420a-b952-51248468b5d1 |
| 프리셋 | DESERTER / male |
| 총 턴 | 20 |
| 최종 상태 | RUN_ACTIVE |
| 방문 장소 | market (18턴 체류) |
| Heat | 23 |
| Safety | SAFE |
| TimePhase | NIGHT |
| Incidents | 없음 |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 결과 | 비고 |
|----|------|------|--------|------|------|
| 1 | HUB | CHOICE(accept_quest) | sys_1 | - | 의뢰 수락 |
| 2 | HUB | CHOICE(go_market) | sys_2 | - | 시장 이동 |
| 3 | LOC | CHOICE(상인 소문) | OPP_ERRAND | PARTIAL | - |
| 4 | LOC | CHOICE(짐 도움) | OPP_ERRAND | PARTIAL | **연속 반복** |
| 5 | LOC | CHOICE(어디까지 가느냐) | OPP_ERRAND | PARTIAL | **3연속** |
| 6 | LOC | CHOICE(약초 구매 제안) | PROC_7 | PARTIAL | ProceduralEvent |
| 7 | LOC | CHOICE(말 건넴) | ENC_BUSKER | PARTIAL | - |
| 8 | LOC | CHOICE(노래 의미) | ENC_BUSKER | PARTIAL | **연속 반복** |
| 9 | LOC | CHOICE(악사에게 말) | ENC_BUSKER | PARTIAL | **3연속** |
| 10 | LOC | CHOICE(동전 던져 곡 요청) | PROC_11 | SUCCESS | ProceduralEvent |
| 11 | LOC | CHOICE(조용히 지켜봄) | DSC_1 | FAIL | - |
| 12 | LOC | CHOICE(양피지 읽기) | DSC_1 | FAIL | **연속 반복** |
| 13 | LOC | CHOICE(다른 문서 찾기) | DSC_1 | - | **3연속** |
| 14 | LOC | CHOICE(주변 살핌) | OPP_LOST_CARGO | PARTIAL | - |
| 15 | LOC | CHOICE(상자 내용물) | OPP_LOST_CARGO | SUCCESS | **연속 반복** |
| 16 | LOC | CHOICE(몰래 상자 챙김) | OPP_LOST_CARGO | FAIL | **3연속** |
| 17 | LOC | CHOICE(지켜봄) | ATM_1 | SUCCESS | - |
| 18 | LOC | CHOICE(향신료 가게) | ATM_1 | SUCCESS | **연속 반복** |
| 19 | LOC | CHOICE(장사 어떤지 묻기) | ATM_1 | - | **3연속** |
| 20 | LOC | CHOICE(다른 상인 접근) | INT_3 | SUCCESS | - |

## C. 종합 점수 (10점 만점)

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 6.5 | 개별 턴 서술 양호, 전체 진행감 부족 |
| NPC 일관성 | 4.0 | 미렐라 고정 출연, nameRevealed 미작동 |
| 맥락 유지 | 5.0 | 정보 참조 일부 존재, 메모리 시스템 미작동 |
| 이벤트 다양성 | 3.0 | 모든 이벤트 3연속 반복, hard block 미작동 |
| 메모리 시스템 | 1.0 | storySummary=null, structuredMemory=null |
| **종합** | **3.9** | |

## D. 개선 권장사항

### Critical
1. **이벤트 연속 반복 차단 실패** — 같은 이벤트가 3턴 연속 매칭됨. EventDirector의 "직전 이벤트 hard block" 규칙 미작동
2. **메모리 시스템 완전 미작동** — storySummary=null, structuredMemory=null. finalizeVisit 미호출 또는 저장 로직 고장

### High
3. **NPC nameRevealed 미작동** — MIRELA(FRIENDLY, 5회), SEO_DOYUN(CAUTIOUS, 6회) 모두 nameRevealed=false
4. **내러티브 반복 표현** — "미렐라가" 23회, "어둠 속에서" 17회, "약초 꾸러미" 12회

### Medium
5. **판정 PARTIAL 편중** — PARTIAL 50%, SUCCESS 31%, FAIL 19%

---

## E. 심층 분석

### [1] 이벤트 서술 품질 심층

- **문장 품질**: 7/10 — 중세 어투 적절, 문법 오류 없음
- **톤 일관성**: 6/10 — 시장 분위기 유지하나 "어둠 속에서" 표현이 시간대 무관 사용
- **반복 표현**: 3/10
  - "미렐라가/미렐라는" 39회 — 동일 NPC만 등장
  - "어둠 속에서" 17회 — 시간대 무관
  - "약초 꾸러미" 12회, "조심스레" 16회, "낮은 목소리로 말했다" 11회
- **장면 묘사력**: 7/10 — 시각·후각·청각 감각 묘사 존재
- **선택지 서술**: 7/10 — 이벤트 고유 선택지 적절
- **서술 길이**: 평균 736자, 최소 278자, 최대 1000자
- **점수**: 5.0/10 (반복 표현이 전체 점수 하락)
- **개선 턴**: T3-T5, T7-T9, T17-T19 (동일 이벤트 3연속 구간)

### [2] 맥락 유지 & NPC 성향 심층

- **정보 참조**: T6→T10 약초 상인 정보, T14→T15 상자 정보 연속 참조
- **단절 지점**: T11 — 이전 10턴 맥락 거의 미반영
- **NPC 이름 공개**:
  - MIRELA: FRIENDLY, 5회 만남 → threshold 1회 → **nameRevealed=false** ❌
  - SEO_DOYUN: CAUTIOUS, 6회 만남 → threshold 2회 → **nameRevealed=false** ❌
  - **이름 공개 로직 완전 미작동**
- **NPC 감정축**: trust/fear/respect 변화 기록 없음
- **NPC 태도**: MIRELA "친절한 약초 상인" 역할 일관 유지
- **점수**: 4.0/10

### [4] 메모리 시스템 심층

- **storySummary**: **null** — 방문 요약 0건
- **structuredMemory**: **null** — visitLog, npcJournal, npcKnowledge 모두 미생성
- **[MEMORY]/[THREAD] 태그**: 확인 불가
- **토큰 예산**: LLM DONE 100% → 기본 작동
- **Mid Summary**: 확인 불가 (T9에서 6턴 초과했으나 중간 요약 생성 미확인)
- **RUN_ENDED 메모리 통합**: 해당 없음 (런 미종료)
- **점수**: 1.0/10 — **메모리 시스템 완전 미작동**

---

## F. 수정 전후 비교 (-fix 모드)

### 수정 내용
1. `turns.service.ts` line 557: CHOICE 연속 한도 3→2 (이벤트 체인 축소)
2. `turns.service.ts` line 580: ACTION 씬 유지 dead code 수정 (`consecutiveCount < 1` → `<= 1`)
3. `system-prompts.ts`: 표현 다양성 지시 추가 (같은 부사/동사구/감각묘사 2회 이상 사용 금지)

### 점수 비교

| 항목 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 서사 흐름 | 6.5 | 7.0 | +0.5 |
| NPC 일관성 | 4.0 | 4.5 | +0.5 |
| 맥락 유지 | 5.0 | 5.5 | +0.5 |
| 이벤트 다양성 | 3.0 | 5.5 | +2.5 |
| 메모리 시스템 | 1.0 | 1.0 | 0.0 |
| **종합** | **3.9** | **4.7** | **+0.8** |

### 정량 비교

| 지표 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 고유 이벤트 | 8 | 9 | +1 |
| 최대 연속 동일 이벤트 | 3턴 | 2턴 | -1 |
| 연속 반복 횟수 | 10 | 8 | -2 |
| 최다 반복 구문 (NPC명) | 23회 | 8회 | -15 |
| 최다 반복 구문 (기타) | 17회 | 19회 | +2 |

### 수정 항목별 검증
- ✅ CHOICE 연속 한도 3→2: 최대 연속 3→2턴, 이벤트 다양성 향상
- ✅ LLM 표현 다양성: NPC명 반복 23→8회로 대폭 감소
- ⬜ ACTION 씬 유지 수정: ACTION 미사용으로 직접 검증 불가 (코드 논리상 확인)

### 분석 정정
- NPC `introduced` 필드는 실제 `true` (API 응답 필드명 차이로 오판)
- 메모리 null은 장소 이동 없어 `finalizeVisit()` 미호출 (설계 정상 동작)
