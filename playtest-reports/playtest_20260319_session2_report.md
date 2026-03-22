# Playtest Report — Session 2 (2026-03-19)

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | f2546c42-43b2-47bb-acc9-9a693b532cd7 |
| 프리셋 | DESERTER (male) |
| 턴 수 | 10턴 (HUB 2 + LOCATION 8) |
| 최종 상태 | RUN_ACTIVE (T11) |
| 방문 장소 | market (전체 체류) |
| Heat | None (미설정) |
| Day | 1 |
| GlobalClock | 8 |
| HubSafety | SAFE |
| Active Incidents | 1 (CRIMINAL, control=52, pressure=42) |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 결과 | 서술 길이 | 비고 |
|---|------|------|--------|------|----------|------|
| 1 | HUB | CHOICE: 의뢰 수락 | sys_1 | - | 297c | 로넨 의뢰 수락 |
| 2 | HUB | CHOICE: 시장 이동 | sys_2 | - | 663c | 시장 진입 서술 |
| 4 | LOC | ACTION: 주변 살펴봄 | EVT_MARKET_ATM_2 | PARTIAL | 544c | 비 오는 시장, NPC 등장 |
| 5 | LOC | ACTION: 말 건다 | EVT_MARKET_ATM_2 | SUCCESS | 707c | 경계하는 사내와 대화 |
| 6 | LOC | ACTION: 흔적 조사 | EVT_MARKET_OPP_LOST_CARGO | SUCCESS | 665c | 기름 얼룩, 창고 관리인 |
| 7 | LOC | ACTION: 뒷골목 이동 | EVT_MARKET_OPP_LOST_CARGO | PARTIAL | 847c | 골목 잠입, 아이템 획득 |
| 8 | LOC | ACTION: 흥정 | EVT_MARKET_ENC_PEDDLER | FAIL | 837c | 상인 거절 |
| 9 | LOC | ACTION: 위협 정보 | EVT_MARKET_ENC_PEDDLER | SUCCESS | 737c | 창고 관리인 위협 성공 |
| 10 | LOC | ACTION: 돕기 | PROC_10 (동적) | PARTIAL | 753c | 보육원 여인 등장 |
| 11 | LOC | CHOICE: 말 건넴 | EVT_MARKET_OPP_ERRAND | SUCCESS | 688c | 미렐라 등장, 약초 |

## C. 종합 점수

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 7.0/10 | 장면 전환 자연스러움. 다만 시장 한 곳 체류로 변화 제한 |
| NPC 일관성 | 5.5/10 | NPC 감정 축은 작동하나 이름 시스템에 이슈 (아래 상세) |
| 맥락 유지 | 6.0/10 | "창고" 맥락은 유지되나 structuredMemory 비축적 우려 |
| 이벤트 다양성 | 7.0/10 | 5종 이벤트(ATM_2, LOST_CARGO, PEDDLER, PROC_10, ERRAND) + 동적 1건 |
| 메모리 시스템 | 3.0/10 | **structuredMemory 완전 비어있음** — visitLog, npcJournal, llmExtracted 모두 0 |
| **종합** | **5.7/10** | 메모리 미축적이 가장 큰 문제 |

## D. 개선 권장사항

### Critical
1. **structuredMemory 미축적** — 10턴 동안 npcJournal, llmExtracted, npcKnowledge가 전혀 쌓이지 않음. memory-collector가 제대로 호출되지 않는 것으로 추정

### High
2. **NPC 소개 시스템 불일치** — NPC_SEO_DOYUN은 enc=5, intro=True지만 서술에서 "수상한 창고 관리인"으로만 등장. 이름 "서도윤"이 서술에 사용되지 않음
3. **NPC_MIRELA intro=True(enc=1)인데 FRIENDLY → 소개 조건 1회 만족** — 정상이나 서술에서 "약초 노점의 노부인"으로만 등장 (T4). T11에서야 "미렐라" 언급
4. **Heat 값이 None** — WorldState의 heat가 설정되지 않아 heat 기반 이벤트 시스템이 정상 작동하지 않을 수 있음

### Medium
5. **T5 resolve가 None(SUCCESS여야)** — ACTION "근처 사람에게 말을 건다"가 TALK으로 파싱 → NON_CHALLENGE → resolve 없음
6. **동일 이벤트 연속** — EVT_MARKET_ATM_2 (T4~5), EVT_MARKET_OPP_LOST_CARGO (T6~7), EVT_MARKET_ENC_PEDDLER (T8~9) 각각 2턴 연속
7. **storySummary 미축적** — 장소를 아직 떠나지 않았으므로 정상이나, 10턴+ 체류에도 중간 요약 없음

---

## [1] 이벤트 서술 품질 심층

### 문장 품질
전반적으로 우수함. 문법 오류 없음. 번역체 느낌 극히 적음.

**어색한 표현:**
- T5: "낡은 장부 조각에 적힌 표식을 보여주며" — 플레이어가 장부 조각을 갖고 있지 않은 상태에서 LLM 선택지가 이를 전제
- T10: "다정한 보육원 여인" — ProceduralEvent에서 생성된 NPC의 수식어가 기계적

### 톤 일관성: 8/10
- 시장 거리의 긴장감 있는 분위기가 전체적으로 일관됨
- "비" "어둠" "바람" 등 감각 묘사가 꾸준히 등장
- 다만 T2(시장 진입)에서 "활기찬" 묘사 → T4에서 갑자기 "비를 피해" 등장 — 날씨 전환이 설명 없이 발생

### 반복 표현 (3회+ 사용)
| 표현 | 횟수 | 턴 |
|------|------|-----|
| "낮은 목소리로" | 5회 | T1,5,6,9,11 |
| "주변을 살피(다/며)" | 4회 | T4,5,7,9 |
| "골목 (어귀/구석/끝)" | 5회 | T4,5,7,8,9 |
| "경계(심/하는)" | 4회 | T5,6,8,9 |
| "당신의 시선이" | 3회 | T1,7,11 |

### 장면 묘사력: 7.5/10
- **시각**: 우수 (기름 얼룩, 분필 번호, 그림자, 빗방울)
- **청각**: 양호 (발소리, 웅성거림, 종소리)
- **후각**: 부족 (T2 "향신료 냄새"만, 이후 미등장)
- **촉각**: 최소 (T8 "손가락 끝으로" 정도)

### 선택지 서술: 7/10
- 서버 선택지: 구체적이고 행동 지향적 ✅
- LLM 선택지: 맥락 반영 양호하나, T5의 "장부 조각" 같은 비소유 아이템 전제가 문제

### 서술 길이 분포
- 평균: 674자 (HUB 480, LOCATION 722)
- 최소: 297자 (T1, HUB)
- 최대: 847자 (T7, 잠입)
- 편차 적절, 액션 밀도에 비례

### 서술 품질 점수: 7.0/10
- 개선 필요: 반복 표현 감소 ("낮은 목소리로"), 날씨 연속성, 후각/촉각 묘사 보강

---

## [2] 맥락 유지 & NPC 성향 심층

### 정보 참조 체인
| 발견 턴 | 정보 | 참조 턴 | 상태 |
|---------|------|---------|------|
| T4 | 약초 노점 노부인 | T11 | ✅ 미렐라로 연결 |
| T5 | "동부 창고 이상한 움직임" | T6,7,9 | ✅ 창고 관련 서술 지속 |
| T6 | 기름 얼룩, 발자국 | T7 | ✅ "상자" 맥락 이어짐 |
| T6 | "창고 관리인" | T9 | ✅ 같은 인물 위협 |
| T10 | "보육원 여인" | T11 | ✅ 대화 이어짐 |

**단절 지점:**
- T8 상인 흥정 → T9 위협: 상인과 창고 관리인이 별도 인물인데 연결이 모호
- T2 "투박한 노동자가 무언가를 건네는 모습" — 이후 전혀 참조 안 됨

### NPC 이름 공개 분석

| NPC | posture | enc | intro | 기준 | 실제 서술 | 판정 |
|-----|---------|-----|-------|------|----------|------|
| NPC_MIRELA | FRIENDLY | 1 | True | 1회 ✅ | T4: "약초 노점의 노부인", T11: "미렐라" | ⚠️ T4에서 이미 intro=True인데 alias 사용 |
| NPC_SEO_DOYUN | CAUTIOUS | 5 | True | 2회 ✅ | "수상한 창고 관리인"으로만 서술 | ❌ 이름 미사용 |
| NPC_BAEK_SEUNGHO | CAUTIOUS | 1 | False | 2회 필요 | 서술에 미등장 | - |

**핵심 이슈:**
- **NPC_SEO_DOYUN**: introduced=True(enc=5)인데 서술에서 이름 사용 안 됨. 이는 H1 수정(unknownAlias 사용)이 작동하지만, 이미 intro된 NPC도 alias로 나가는 건 아닌지 확인 필요
- **NPC_MIRELA**: T4에서는 alias, T11에서 이름 — 서술 내에서 전환점이 불명확

### NPC 감정축 변화 추적

| NPC | 시작 trust | 최종 trust | 변화 | 이유 |
|-----|-----------|-----------|------|------|
| NPC_MIRELA | 0 | 22 | +22 | TALK(+), HELP(+) |
| NPC_SEO_DOYUN | 0 | 0 | 0 | OBSERVE/INVESTIGATE/SNEAK: 직접 대상 아님 |
| NPC_BAEK_SEUNGHO | 0 | -9 | -9 | THREATEN(-) — H2 수정 후 올바른 방향 ✅ |

**감정 변화 검증:**
- NPC_BAEK_SEUNGHO: T9에서 THREATEN 성공 → trust=-9, suspicion=15 — **H2 수정 정상 작동** (이전이었으면 FAIL 시 trust 양수로 역전됐을 것)
- NPC_MIRELA: trust=22, respect=8 → FRIENDLY 유지 — 자연스러움 ✅

### 맥락 유지 점수: 6.5/10
- 강점: 창고 맥락 일관성, NPC 감정 방향 정상
- 약점: 소개된 NPC 이름 미사용, 일부 정보 단절

---

## [4] 메모리 시스템 심층

### structuredMemory 상태: ❌ 심각

| 항목 | 기대 | 실제 | 판정 |
|------|------|------|------|
| visitLog | 0 (미이동) | 0 | ✅ 정상 |
| npcJournal | 3+ entries | **0** | ❌ 미축적 |
| npcKnowledge | 2+ entries | **0** | ❌ 미축적 |
| llmExtracted | 3+ facts | **0** | ❌ 미축적 |
| incidentChronicle | 1 | **0** | ❌ 미축적 |
| milestones | 1+ | **0** | ❌ 미축적 |

**진단:** 10턴 동안 NPC 5명과 상호작용했음에도 npcJournal이 비어있고, LLM이 [MEMORY] 태그를 생성해도 llmExtracted가 비어있음. **memory-collector 또는 memory-integration 파이프라인에 심각한 문제가 있음**.

### storySummary: 비어있음
- 장소 미이동이므로 finalizeVisit 미호출 → 정상
- 다만 10턴+ 체류에서 storySummary 축적이 없다면 장기 플레이에서 맥락 손실 우려

### [MEMORY]/[THREAD] 태그 분석
서술을 확인했으나, LLM 출력에 [MEMORY]/[THREAD] 태그가 관찰되지 않음. 이는:
1. 프롬프트에 태그 생성 지시가 포함되었으나 LLM이 생략했거나
2. 태그가 파싱되어 서술에서 제거되었지만 llmExtracted에 저장 안 됨

### 토큰 예산
- 디버그에 tokenBudget 정보 미노출 (API 응답에 포함 안 됨)
- L0(theme)은 정상 존재 ✅

### Mid Summary
- locationSessionTurns 8턴 > 임계값 4턴이므로 midSummary가 생성되어야 하나 확인 불가

### Scene Continuity
- 이벤트 연속성: 같은 이벤트 2턴 연속 사용이 3회 발생 (ATM_2, LOST_CARGO, PEDDLER)
- sceneFrame 3단계 억제가 적용된 것으로 보이나, 더 다양한 이벤트가 나와야 함

### 메모리 시스템 점수: 3.0/10
- **Critical**: npcJournal/llmExtracted/npcKnowledge 미축적은 장기 플레이에서 완전한 맥락 손실을 초래
- 원인 조사 필요: memory-collector.service.ts의 collectFromTurn() 호출 여부 확인

---

## 핵심 발견 요약

1. **[Critical] structuredMemory 미축적** — 모든 하위 항목(npcJournal, llmExtracted, npcKnowledge, incidentChronicle, milestones)이 비어있음. 10턴의 NPC 상호작용과 정보 발견이 전혀 저장되지 않음
2. **[High] NPC 이름 시스템** — introduced=True인 NPC도 서술에서 alias로만 등장 (NPC_SEO_DOYUN)
3. **[Medium] Heat 미설정** — WorldState.heat가 None으로 남아있어 heat 기반 시스템 비활성
4. **[Medium] 반복 표현** — "낮은 목소리로" 5회, "골목" 5회 등
5. **[Low] 날씨 불연속** — T2 맑음 → T4 비, 전환 설명 없음
