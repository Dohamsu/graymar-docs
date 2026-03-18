# Playtest Analysis Report — 2026-03-18

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | aeaea888-4590-4cba-a127-0af171f75372 |
| 프리셋 | DESERTER (male) |
| 총 턴 수 | 20 |
| 최종 상태 | RUN_ACTIVE (계속 진행 가능) |
| HP | 100 / 100 |
| Gold | 59 |
| Heat | N/A (API 미노출) |
| Day | N/A (API 미노출) |
| 방문 장소 | market → guard → harbor → slums |
| Incidents | 0개 |
| NPC 등록 | 11명 (introduced: 1명 — NPC_MIRELA) |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 판정 | 비고 |
|----|------|------|--------|------|------|
| 1 | HUB | CHOICE:accept_quest | - | - | 의뢰 수락 |
| 2 | HUB | CHOICE:go_market | - | - | 시장 이동 |
| 3 | LOC | ACTION:주변을 살핀다 | EVT_MARKET_INT_2 | 부분성공 | 술꾼 NPC 등장 |
| 4 | LOC | ACTION:말을 건다 | EVT_MARKET_ENC_BUSKER | 성공(대화) | 거리 악사 이벤트 |
| 5 | LOC | ACTION:조사한다 | EVT_MARKET_OPP_LOST_CARGO | 부분성공 | 분실 화물 기회 |
| 6 | LOC | ACTION:설득한다 | EVT_MARKET_ENC_DISPUTE | 실패 | 분쟁 조우 |
| 7 | LOC | CHOICE:go_hub | - | - | HUB 복귀 |
| 8 | HUB | CHOICE:go_guard | - | - | 경비대 이동 |
| 9 | LOC | ACTION:몰래 접근 | EVT_GUARD_CHECKPOINT | 부분성공 | 검문소 → 전투 진입 |
| 10 | COM | CHOICE:attack_melee | - | - | 부패 경비병 공격 |
| 11 | COM | CHOICE:attack_melee | - | - | 부패 경비병 처치 |
| 12 | COM | CHOICE:attack_melee | - | - | 항만 감시병 공격 |
| 13 | COM | CHOICE:attack_melee | - | - | 항만 감시병 공격 |
| 14 | COM | CHOICE:attack_melee | - | - | 전투 종료 (승리) |
| 15 | LOC | ACTION:도움을 준다 | EVT_GUARD_ATM_3 | 성공 | 노동자 돕기 |
| 16 | LOC | ACTION:관찰한다 | EVT_GUARD_OPP_REWARD | 성공 | 보상 기회 |
| 17 | LOC | ACTION:거래 제안 | EVT_GUARD_ENC_PATROL | 부분성공 | 순찰 조우 |
| 18 | LOC | CHOICE:go_hub | - | - | HUB 복귀 |
| 19 | HUB | CHOICE:go_harbor | - | - | 항만 이동 |
| 20 | LOC | CHOICE:harbor_talk | EVT_HARBOR_INT_1 | 성공 | 미렐라 NPC 소개 |

## C. 종합 점수 (10점 만점)

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 7.5 | 일관된 퀘스트 동선, 장소별 분위기 전환 양호 |
| NPC 일관성 | 5.0 | 11명 등록 중 1명만 소개됨, NPC 이름 비공개 시스템 검증 부족 |
| 맥락 유지 | 6.5 | storySummary 축적됨, 하지만 structuredMemory 비어있음 |
| 이벤트 다양성 | 8.5 | 11개 고유 이벤트, 반복 없음, 장소별 4-3-4 분포 |
| 메모리 시스템 | 4.0 | storySummary만 동작, structuredMemory 완전 미작동 |
| **종합** | **6.3** | |

## D. 개선 권장사항

### Critical
1. **structuredMemory 미작동** — 20턴 동안 visitLog, npcJournal, npcKnowledge 모두 비어있음. finalizeVisit() 호출 여부 또는 MemoryCollector 동작 확인 필요.

### High
2. **NPC encounterCount 미증가** — 11명 NPC 중 encounterCount > 0인 NPC가 2명뿐 (MIRELA: 1, RENNICK: 1). 대부분의 NPC와 실제로 상호작용했음에도 카운트 미증가.
3. **resolveOutcome API 미노출** — summary에는 "성공/부분성공/실패"가 기록되지만, serverResult.resolveOutcome 필드가 비어있음. 클라이언트 HUD에 판정 결과 표시 불가능.

### Medium
4. **NPC 감정축 초기값 유지** — trust, fear, respect, suspicion, attachment 모두 None/0. NPC와 상호작용(도움, 위협, 거래)했음에도 감정 변화 없음.
5. **Incident 미발생** — 20턴 동안 activeIncidents가 0. 시그널이나 사건 시스템이 작동하지 않는 것으로 보임.

### Low
6. **Heat/Day API 미노출** — GET /runs/:id 응답에서 heat, day 필드가 null로 반환됨.

---

## E. 심층 분석 1: 이벤트 서술 품질

### 문장 품질 (8/10)

전반적으로 문장 완성도가 높음. 문법 오류나 어색한 번역체 표현은 거의 없음.

**양호한 점:**
- 감각 묘사(시각/청각/후각)가 풍부함: "짠내 섞인 바닷바람" (T14), "기름 얼룩진 자락" (T5), "삐걱거리는 나무 판자길" (T14)
- 한국어 고어체(~하오/~이오) 일관 유지
- 장면 전환 시 환경 묘사로 자연스러운 도입

**개선 필요:**
- T12: "입은 골드 주머니를 손에 쥐고" → "얻은" 오타 의심
- T16: "낮은 햇살" vs 전체 문맥이 "밤" — 시간대 모순 (T9부터 밤 설정이었으나 T16에서 갑자기 낮 묘사)

### 톤 일관성 (7.5/10)

| 장소 | 기대 톤 | 실제 톤 | 평가 |
|------|---------|---------|------|
| 시장 (T3-6) | 활기+경계 | 경계+긴장 | ⚠️ 활기 부족, 지나치게 어두움 |
| 경비대 (T9-13) | 긴장+권위 | 긴장+권위 | ✅ 적절 |
| 항만 (T15-18) | 바다+비밀 | 바다+비밀 | ✅ 적절 |
| 빈민가 (T20) | 궁핍+음산 | 궁핍+음산 | ✅ 적절 |

시장이 시장다운 "북적임"보다 "어두운 골목" 분위기에 치우침.

### 반복 표현 (6.5/10)

3회 이상 반복된 표현 패턴:
- **"경계심"/"경계를 늦추지 않는"** — 9회 (T3,5,8,9,10,12,15,16,18)
- **"조심스럽게/조심스레"** — 11회 (거의 매 턴)
- **"긴장감이 감돌/긴장감을 더했다"** — 8회
- **"낮은 목소리로"** — 7회
- **"골목 끝/골목 어귀"** — 6회
- **"숨을 고르며"** — 4회

→ "경계심", "조심스럽게", "긴장감" 3종 세트가 거의 모든 턴에 등장하여 단조로움 유발.

### 장면 묘사력 (8/10)

- **시각**: ✅ 풍부 (빛, 그림자, 색상 묘사 다수)
- **청각**: ✅ 양호 (발소리, 쇠사슬, 파도, 바람 등)
- **후각**: ⚠️ 반복적 ("짠내", "먼지 냄새" 위주)
- **촉각**: ⚠️ 제한적 ("차가운 금속" 정도)
- **미각**: ❌ 부재 (식사/음주 장면 없음)

### 선택지 서술 (N/A)

LLM 생성 선택지(llmChoices)는 이번 테스트에서 캡처되지 않음. 서버가 제공하는 고정 선택지 위주로 진행.

### 서술 길이 분포

| 통계 | 값 |
|------|-----|
| 평균 | 735자 |
| 최소 | 321자 (T1 HUB) |
| 최대 | 1,136자 (T18 정보 수집) |
| LOCATION 평균 | ~780자 |
| HUB 평균 | ~650자 |

적절한 분포. ACTION 유형(조사, 정보 수집)이 더 긴 서술을 생성하는 경향.

### 서술 품질 종합: 7.5/10

**개선 필요 턴**: T12(오타), T16(시간대 모순)
**핵심 개선점**: "경계심/조심스럽게/긴장감" 반복 억제를 위한 LLM 프롬프트 다양성 지시 추가

---

## F. 심층 분석 2: 맥락 유지 & NPC 성향

### 정보 참조 체인 (7/10)

| 연결 | 내용 | 평가 |
|------|------|------|
| T1→T2 | 로넨의 의뢰(장부 찾기) → 시장 탐색 동기 | ✅ 유지 |
| T3→T4 | 술꾼의 "동쪽 창고" 정보 → 후속 탐색 | ✅ 유지 |
| T9→T10 | 경비대 검문 → 위협 시도 | ✅ 자연스러움 |
| T14→T15-18 | "창고 관리인" "뒷문 열쇠" → 항만 탐색 | ✅ 좋은 연속성 |
| T3→T17 | 시장의 술꾼 정보 → 항만에서 미렐라 참조 | ⚠️ 간접적 (직접 언급 없음) |

**단절 지점:**
- T6(설득 실패) 후 T7에서 바로 go_hub — 실패 결과에 대한 서술적 후속이 없음
- T14에서 "투박한 노동자"가 창고 정보를 주지만, 이 NPC가 시장/경비대에서 만난 인물과의 연결이 모호

### NPC 이름 공개 타이밍 (4/10)

| NPC | encounterCount | posture | threshold | introduced | 평가 |
|-----|---------------|---------|-----------|------------|------|
| NPC_MIRELA | 1 | None | ? | ✅ True | 소개됨 (이벤트 자체에서 이름 제공) |
| NPC_RENNICK | 1 | None | ? | ❌ False | 1회 만남에도 미소개 |
| 나머지 9명 | 0 | None | - | ❌ False | 만남 자체 없음 |

**문제점:**
1. **encounterCount가 거의 증가하지 않음** — 20턴 동안 NPC와 직접 상호작용(T3 술꾼, T4 악사, T10 장교, T15 노동자, T17 미렐라)이 5회 이상 있었으나, encounterCount는 MIRELA(1), RENNICK(1)뿐
2. **posture가 모두 None** — 초기 posture가 설정되지 않아 shouldIntroduce() 판정 불가
3. **NPC alias 사용** — 서술에서 "권위적인 야간 경비 책임자", "투박한 노동자", "수상한 창고 관리인" 등 alias가 일관되게 사용됨. 이는 시스템이 의도한 대로 동작하는 것으로 보이나, encounterCount 미증가로 이름 공개 전환이 발생하지 않음

### NPC 감정축 변화 (3/10)

모든 NPC의 감정축이 None/초기값:
- trust: None (기대: T4 대화, T15 도움 → trust 증가)
- fear: None (기대: T10 위협 → fear 증가)
- respect: None
- suspicion: None
- attachment: None

**판정**: NPC 감정축 시스템이 실질적으로 비활성 상태. ResolveService의 판정 결과가 NPC 감정에 반영되는 파이프라인이 연결되지 않았거나, 이벤트-NPC 매핑이 누락된 것으로 추정.

### NPC 태도 일관성 (6/10)

서술 내에서 NPC들의 태도는 비교적 일관적:
- "권위적인 야간 경비 책임자" — 경계/권위 유지 (T9~T18까지 동일 톤)
- "미렐라" — 호기심+조심성 유지 (T17, T20)
- "투박한 노동자" — 경계+정보 제공 (T14~T16)

**문제**: 동일 NPC가 장소를 넘어서 등장 (경비 책임자가 경비대→항만에서도 나타남). 이는 서버가 NPC를 장소에 바인딩하지 않고 전역으로 관리하기 때문이나, 서술적으로 부자연스러움.

### alias→name 전환 (2/10)

**전환 사례**: 0건 (미렐라 제외 — 미렐라는 이벤트 자체에서 이름 제공)

- 20턴 동안 단 한 번도 alias→실명 전환이 발생하지 않음
- encounterCount 미증가 + posture None → shouldIntroduce() 조건 미충족
- 시스템 의도대로라면 FRIENDLY 1회, CAUTIOUS 2회, HOSTILE 3회에 소개되어야 하나, posture 자체가 None이므로 판정 불가

### [MEMORY]/[THREAD] 태그 (5/10)

서술 내에서 [MEMORY] 태그가 생성된 턴:
- T11: `[MEMORY:NPC_KNOWLEDGE:권위적인 야간 경비 책임자]` — 탈영병 제압 정보
- T12: `[MEMORY:NPC_KNOWLEDGE:단정한 제복의 장교]` + `[MEMORY:NPC_KNOWLEDGE:권위적인 야간 경비 책임자]`

**문제**:
- [MEMORY] 태그가 서술 텍스트에 그대로 노출됨 (사용자에게 보이면 안 됨)
- 태그 생성 후 후속 턴에서 소비(참조)되는지 불명확
- [THREAD] 태그는 전혀 생성되지 않음

### 맥락 유지 & NPC 성향 종합: 4.5/10

**핵심 문제:**
1. NPC encounterCount가 이벤트-NPC 매핑 누락으로 증가하지 않음
2. NPC posture가 초기화되지 않아 shouldIntroduce() 판정 불가
3. NPC 감정축이 완전히 비활성 상태
4. structuredMemory 비어있어 장기 기억 축적 실패
5. [MEMORY] 태그가 서술에 그대로 노출

---

## G. 종합 요약

### 강점
- **이벤트 다양성**: 11개 고유 이벤트, 장소별 균형 있는 분포, 반복 없음 (Fixplan3 P5 수정 효과)
- **서술 품질**: 감각 묘사 풍부, 고어체 일관 유지, 적절한 길이
- **장소 전환**: market→guard→harbor→slums 4개 장소 정상 순회

### 약점
- **NPC 시스템**: encounterCount, posture, 감정축 모두 미작동 수준
- **메모리 시스템**: structuredMemory 완전 공백, storySummary만 동작
- **Incident 부재**: 20턴 동안 사건이 0개 — Narrative Engine v1의 핵심 기능 미동작
- **서술 반복**: "경계심/조심스럽게/긴장감" 과다 반복
