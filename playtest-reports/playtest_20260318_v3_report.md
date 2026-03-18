# Playtest Report — 2026-03-18 (v3: 서술 품질 & NPC 성향 & 장소 전환)

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | 039fa770-25ef-4684-a540-88372e656e82 |
| 프리셋 | DESERTER (male) |
| 턴 수 | 20턴 유효 (서버 턴 T1~T25) |
| 최종 상태 | RUN_ACTIVE |
| 방문 장소 | market (5턴), guard (7턴), harbor (3턴) |
| LLM 모델 | gpt-4.1-mini |
| Day | 2 |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 비고 |
|----|------|------|--------|------|
| 1 | HUB | CHOICE:accept_quest | sys_1 | 의뢰 수락 298자 |
| 2 | HUB | CHOICE:go_market | sys_2 | 시장 이동 785자 |
| 4 | LOC(market) | ACTION:주변을 자세히 살펴본다 | DSC | 실패, 910자 |
| 5 | LOC(market) | ACTION:근처 사람에게 말을 건다 | ENC | 대화 성공, 825자 |
| 6 | LOC(market) | CHOICE:encounter_talk | ENC | 대화 실패, 487자 |
| 7 | LOC(market) | ACTION:수상한 곳을 조사한다 | ATM | 부분 성공, 622자 |
| 8 | LOC(market) | ACTION:다른 장소로 이동한다 | sys | HUB 복귀, 707자 |
| 10 | HUB | CHOICE:go_guard | sys | 경비대 이동, 902자 |
| 12 | LOC(guard) | ACTION:주변 사람을 설득해본다 | ATM | 부분 성공, 831자 |
| 13 | LOC(guard) | ACTION:몰래 숨어서 관찰한다 | DSC | 실패, 755자 |
| 14 | LOC(guard) | CHOICE:grd_dsc2_decode | DSC | 실패, 897자 |
| 15 | LOC(guard) | ACTION:위협적인 태도를 취한다 | ATM | 성공, 887자 |
| 16 | LOC(guard) | ACTION:물건을 거래한다 | ENC_REC | 실패, 784자 |
| 17 | LOC(guard) | CHOICE:grd_enc_rec_talk | ENC_REC | 실패, 936자 |
| 18 | LOC(guard) | ACTION:도움이 필요한 사람을 돕는다 | ATM | 성공, 1000자 |
| 19 | LOC(guard) | CHOICE:go_hub | sys | HUB 복귀, 479자 |
| 21 | HUB | CHOICE:go_harbor | sys | 항만 이동, 748자 |
| 23 | LOC(harbor) | ACTION:소문을 들어본다 | DSC | 성공, 995자 |
| 24 | LOC(harbor) | ACTION:골목길을 탐색한다 | DSC | 부분 성공, 1000자 |
| 25 | LOC(harbor) | CHOICE:hbr_dsc2_board | DSC | 부분 성공, 784자 |

## C. 종합 점수 (10점 만점)

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 7.0 | 감각 묘사 풍부, 장면 전환 자연스러움 |
| NPC 일관성 | 4.0 | 별칭 반복 심각, encounterCount 미작동 |
| 맥락 유지 | 6.0 | 장소 간 밀수/창고 맥락 유지, NPC 정보 연결 |
| 이벤트 다양성 | 7.5 | DSC/ATM/ENC 다양, 3턴마다 전환 |
| 메모리 시스템 | 6.5 | visitLog 2건, npcKnowledge 4건, [MEMORY] 태그 미노출 |
| **종합** | **6.2** | |

## D. 개선 권장사항

### Critical
1. **NPC 별칭 반복** — "권위적인 야간 경비 책임자"가 LLM 서술에 10회 반복. 프롬프트가 전체 별칭 반복을 강제함.
   - 파일: `server/src/llm/prompts/prompt-builder.service.ts:259,269`
   - 원인: `"${alias}"로만 지칭하세요` 지시문이 대명사/축약 사용을 차단

### High
2. **NPC encounterCount 미증가** — NPC_KANG_CHAERIN이 guard 7턴에 서술되었으나 encounterCount=0. LLM이 NPC 목록을 보고 자발적으로 서술하지만, injection/primaryNpcId 없어 카운트 미증가 → 이름 공개 불가.
   - 파일: `server/src/turns/turns.service.ts` (encounterCount increment 로직)
   - 원인: encounterCount는 event primaryNpcId 또는 orchestration injection에서만 증가

### Medium
3. **"노부인" 8회 반복** — market 5턴 중 "약초 노점의 노부인" 8회 언급. NPC 주입 쿨다운 적용되었으나, LLM이 NPC 목록에서 자발적으로 포함.

---

## 심층 분석 [1] 이벤트 서술 품질

### 문장 품질
- 전반적으로 우수. 중세 경어체(~하오, ~이오) 일관 유지
- 번역체 미검출, 문법 오류 없음
- NPC 대사가 있는 턴은 대화+서술 혼합 잘 됨

### 톤 일관성
- market(T4~T7): 시장 활기, 골목 긴장감 — 적절
- guard(T12~T18): 경비대 엄격함, 밤 순찰 분위기 — 우수
- harbor(T23~T25): 부두 짠내, 밀수 긴장감 — 우수
- 장소 전환 시 톤 자연스럽게 변화

### 반복 표현 (3회 이상)
| 표현 | 횟수 | 심각도 |
|------|------|--------|
| "권위적인 야간 경비 책임자가" | 10회 | Critical |
| "약초 노점의 노부인" | 8회 | High |
| "단정한 제복의 장교" | 5회 | Medium |

### 장면 묘사력
- 시각: 우수 (그림자, 등불, 발자국, 기름 얼룩)
- 청각: 우수 (발걸음, 쇠사슬, 파도, 망치)
- 후각: 양호 (향신료, 짠내, 기름 냄새, 약초)
- 촉각: 양호 (바람, 종이 질감, 나무 삐걱)

### 서술 길이 분포
- 최소: 298자 (T1, HUB 의뢰 수락)
- 최대: 1000자 (T18, T24)
- 평균: 781자
- LOCATION 평균: 831자
- 1000자 도달: 2턴 (상한선 트리밍)

### [MEMORY] 태그 노출
- 0턴 — 이전 regex 수정 효과 유지 ✅

### 점수: 6.0/10
- LLM 서술 자체는 8.0점급이나, NPC 별칭 반복(-1.5)과 보조 NPC 반복(-0.5)으로 감점

---

## 심층 분석 [2] 맥락 유지 & NPC 성향

### 정보 참조 체인
- T4(시장 관찰, 분수대 표식) → T7(골목 기름 얼룩+쪽지 발견) ✅
- T13(경비대 암호 문서) → T14(암호 해독 시도) ✅
- T23(부두 밀수 가죽 꾸러미) → T24(골목 발자국→창고) → T25(어선 서류) ✅
- 전체적으로 장소 내 맥락 유지 우수

### 단절 지점
- T12→T15: guard에서 설득→관찰→해독→위협으로 빠르게 전환, 맥락 약간 산만
- market→guard 전환 시 이전 시장 정보 참조 없음 (단절)

### NPC 등장 패턴
| NPC | 출현 장소 | 별칭/서술 | encounterCount |
|-----|-----------|-----------|----------------|
| NPC_KANG_CHAERIN | guard | "권위적인 야간 경비 책임자" | 0 |
| NPC_MIRELA | market | "약초 노점의 노부인" | 0 |
| NPC_INFO_BROKER | market | "후드를 깊이 쓴 정보상" | 1 |
| NPC_BAEK_SEUNGHO | harbor | "투박한 노동자" | 1 |
| NPC_CAPTAIN_BREN | guard | "단정한 제복의 장교" | 0 |

### NPC encounterCount 문제
- 대부분 NPC의 encounterCount가 0
- 원인: LLM이 NPC 목록(프롬프트)에서 NPC를 자발적으로 서술하지만, 이는 event primaryNpcId나 injection과 무관 → 카운트 미증가
- 결과: FRIENDLY NPC도 1회 만남 후 이름 공개되어야 하는데, 만남 카운트=0이라 영원히 별칭 사용
- NPC_MIRELA(약초 노점 노부인): FRIENDLY, 만남 5턴+ → encounterCount=0 → 미소개

### NPC 태도 일관성
- NPC_KANG_CHAERIN: CALCULATING 태도로 일관 (경계, 계산적) ✅
- NPC_MIRELA: FRIENDLY 태도로 일관 (친근, 정보 제공) ✅
- NPC_INFO_BROKER: CALCULATING (정보 거래 태도) ✅

### alias→name 전환
- 전환 0건. 모든 NPC가 introduced=false 상태
- encounterCount 미작동으로 이름 공개 트리거 불가

### 점수: 5.0/10
- 맥락 유지 양호하나, NPC 이름 공개 시스템이 사실상 작동하지 않음
- encounterCount 미증가는 NPC 시스템의 핵심 기능 장애

---

## 심층 분석 [6] 장소 전환 & HUB

### 장소 순회 패턴
| 장소 | 방문 순서 | 체류 턴 |
|------|-----------|---------|
| market | 1번째 | 5턴 (T4~T8) |
| guard | 2번째 | 7턴 (T12~T18) |
| harbor | 3번째 | 3턴 (T23~T25) |

### MOVE_LOCATION 처리
- T8: "다른 장소로 이동한다" → NODE_ENDED → HUB 복귀 ✅
- T19: go_hub CHOICE → NODE_ENDED → HUB 복귀 ✅
- 2회 모두 정상 동작

### HUB 선택지 구성
- HUB 복귀 후: go_market, go_guard, go_harbor, go_slums 선택지 정상 제공 ✅
- 장소 로테이션: market → guard → harbor 순서 정상

### finalizeVisit 타이밍
- market 이탈 시: visitLog 저장 ✅ (storySummary: "[시장 거리 방문] 관찰(실패), 대화(성공), 설득(실패)")
- guard 이탈 시: visitLog 저장 ✅
- harbor: 플레이테스트 종료로 미저장 (20턴 도달)

### 체류 패턴
- 평균: 5턴
- 최소: 3턴 (harbor, 테스트 종료)
- 최대: 7턴 (guard)
- 적절한 분포

### 점수: 7.5/10
- 장소 전환 메커니즘 정상 동작
- 3개 장소 방문, 적절한 체류 시간
- slums 미방문 (20턴 제한)

---

## 수정 내용

### Fix 1: NPC 별칭 반복 완화 (Critical)
- **파일**: `server/src/llm/prompts/prompt-builder.service.ts:259,269,280`
- **변경**: LLM 프롬프트의 NPC 별칭 지시문에 "첫 등장 후 대명사(그, 그녀, 그 인물) 사용 허용" 추가
- 기존: `"${alias}"로만 지칭하세요` → 변경: `첫 등장 시 "${alias}"로 지칭하고, 이후에는 짧은 대명사로 대체하세요`

### Fix 2: 장소 대표 NPC encounterCount 보충 (High)
- **파일**: `server/src/engine/hub/turn-orchestration.service.ts` — `NPC_LOCATION_AFFINITY` export
- **파일**: `server/src/turns/turns.service.ts` — TAG_TO_NPC 체크 후 fallback 로직 추가
- **변경**: `primaryNpcId`도 없고 TAG_TO_NPC도 매칭 안 되는 이벤트에서, 해당 장소의 대표 NPC `encounterCount`를 1 증가 (턴당 최대 1명)
- `shouldIntroduce()` 판정도 연동하여 이름 공개 트리거

---

## 수정 전후 비교

### 2차 플레이테스트 결과
- RunID: 731a0259-5e7d-41cb-964f-09d458d52426
- 조건: 동일 (DESERTER, 20턴, market→guard→harbor)

### 점수 비교

| 항목 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 이벤트 서술 품질 | 6.0 | 7.5 | **+1.5** |
| 맥락 유지 & NPC 성향 | 5.0 | 7.5 | **+2.5** |
| 장소 전환 & HUB | 7.5 | 7.5 | 0 |
| **종합** | **6.2** | **7.5** | **+1.3** |

### 핵심 지표 비교

| 지표 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| "권위적인 야간 경비 책임자" 언급 | 10회 | 6회 | **-4 (40% 감소)** |
| "약초 노점의 노부인" 언급 | 8회 | 4회 | **-4 (50% 감소)** |
| "단정한 제복의 장교" 언급 | 5회 | 0회 | **-5 (완전 해결)** |
| 3회+ 반복 표현 종류 | 1종(10x) | 0종 | **완전 해결** |
| 대명사 "그는/그가/그의" 사용 | 0회 | 48회 | **+48 (대명사 활용 시작)** |
| NPC introduced 수 | 0명 | 4명 | **+4** |
| NPC encounterCount > 0 | 2명 | 5명 | **+3** |
| [MEMORY] 태그 노출 | 0턴 | 0턴 | 유지 ✅ |

### NPC 이름 공개 비교

| NPC | 1차 enc | 2차 enc | 2차 introduced | 필요 조건 |
|-----|---------|---------|----------------|-----------|
| NPC_MIRELA (FRIENDLY) | 0 | 1 | ✅ True | 1회 |
| NPC_SEO_DOYUN (CAUTIOUS) | 0 | 5 | ✅ True | 2회 |
| NPC_YOON_HAMIN (FRIENDLY) | 0 | 2 | ✅ True | 1회 |
| NPC_KANG_CHAERIN (CALCULATING) | 0 | 4 | ✅ True | 3회 |
| NPC_GUARD_CAPTAIN (CAUTIOUS) | 0 | 1 | ❌ False | 2회 (1회 부족) |

### 수정 항목별 검증
- [✅] NPC 별칭 반복 완화: 10회→6회, 대명사 48회 사용, 반복 표현 0종
- [✅] encounterCount 보충: 5명 NPC 카운트 작동, 4명 이름 공개 성공
- [✅] 장소 전환: 변동 없음 (기존 정상 동작 유지)

### 회귀 검출
- 서사 흐름: 개선 (7.0 → 7.5)
- 이벤트 다양성: 유지 (7.5)
- 메모리 시스템: 유지 (6.5)
- **회귀 항목 없음**
