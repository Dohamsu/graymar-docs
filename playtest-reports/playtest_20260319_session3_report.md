# 플레이테스트 리포트 — 2026-03-19 Session 3

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | c0cfa4ea-d9ad-4e46-9ead-2bc92369485c |
| 프리셋 | DESERTER |
| 총 턴 수 | 20 |
| 최종 상태 | RUN_ACTIVE (20턴 완료) |
| HP / Gold | 100 / 63 |
| Day | 2 |
| Heat | 12 |
| Incidents | 3개 (SMUGGLING_RING, MARKET_THEFT, MERCHANT_WAR) |
| 방문 장소 | market(5턴) → harbor(5턴) → market(5턴) |
| 검증 결과 | 6/6 PASS |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 결과 | 비고 |
|----|------|------|--------|------|------|
| T01 | HUB | CHOICE:accept_quest | SYSTEM | - | 퀘스트 수락 |
| T02 | HUB | CHOICE:go_market | SYSTEM | - | 시장 이동 |
| T03 | LOCATION | ACTION:물건을 훔친다 | GOLD,LOOT,NPC | SUCCESS | 절도 성공, 금화+아이템 |
| T04 | LOCATION | ACTION:수상한 곳을 조사한다 | NPC | SUCCESS | 조사 성공 |
| T05 | LOCATION | CHOICE:mkt_atm3_watch | NPC | FAIL | 관찰 실패 |
| T06 | LOCATION | ACTION:조심스럽게 잠입한다 | NPC | FAIL | 잠입 실패, 발각 |
| T07 | LOCATION | ACTION:move_location | SYSTEM | - | 장소 이탈 |
| T08 | HUB | CHOICE:go_harbor | SYSTEM | - | 항만 이동 |
| T09 | LOCATION | CHOICE:harbor_talk | NPC | SUCCESS | 대화 성공 |
| T10 | LOCATION | ACTION:골목길 벽에 기대어 주변을 관찰 | GOLD,NPC | SUCCESS | 관찰 성공 |
| T11 | LOCATION | CHOICE:hbr_int1_greet | NPC | - | NPC 인사 |
| T12 | LOCATION | ACTION:골목길 벽에 기대어 주변을 관찰 | NPC | PARTIAL | 부분 성공 |
| T13 | LOCATION | ACTION:move_location | SYSTEM | - | 장소 이탈 |
| T14 | HUB | CHOICE:go_market | SYSTEM | - | 시장 재방문 |
| T15 | LOCATION | CHOICE:market_observe | NPC | SUCCESS | 관찰 성공 |
| T16 | LOCATION | ACTION:조심스럽게 잠입한다 | GOLD,NPC | SUCCESS | 잠입 성공 |
| T17 | LOCATION | ACTION:조심스럽게 잠입한다 | GOLD,NPC | SUCCESS | 잠입 성공 (반복) |
| T18 | LOCATION | ACTION:경비병의 동태를 살핀다 | NPC | SUCCESS | 관찰 성공 |
| T19 | LOCATION | ACTION:move_location | SYSTEM | - | 장소 이탈 |
| T20 | HUB | CHOICE:go_harbor | SYSTEM | - | 항만 이동 (마지막 턴) |

## C. 종합 점수

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 6.5 | 장면 묘사 우수, 반복 표현 존재, 300ch 잘림 |
| NPC 일관성 | 4.0 | encounterCount 대부분 0, 이름 미공개 NPC 다수 |
| 맥락 유지 | 6.0 | storySummary 축적 정상, 턴 간 참조 부분적 |
| 이벤트 다양성 | 5.5 | eventId 기록 없음, NPC 이벤트 편중 |
| 메모리 시스템 | 7.0 | visitLog 3건, storySummary 정상 |
| **종합** | **5.8** | |

## D. 개선 권장사항

| 우선순위 | 이슈 | 설명 |
|---------|------|------|
| **Critical** | 플레이테스트 서술 300ch 잘림 | `scripts/playtest.py`에서 narrative[:300] 제한 → 서술 품질 분석 불가 |
| **High** | NPC encounterCount 미증가 | primaryNpcId=null 이벤트에서 NPC 카운트 증가 안됨 |
| **High** | eventId 미기록 | 플레이테스트 로그에 eventId 누락 → 이벤트 다양성 분석 불가 |
| **Medium** | 반복 입력 패턴 | T16-T17 "조심스럽게 잠입한다" 연속, T10/T12 동일 관찰 입력 |
| **Medium** | NPC 이름 비공개 지연 | FRIENDLY NPC도 enc=0으로 이름 미공개 |
| **Low** | 마지막 턴 HUB 도착만 | T20에서 HUB 선택만 하고 종료 |

---

## [1] 이벤트 서술 품질 심층

### 서술 길이 분포
- **평균**: 298자 / **최소**: 265자 / **최대**: 300자
- **원인**: `scripts/playtest.py` 라인 228에서 `narrative[:300]` 하드코딩 잘림
- 서버 DB에는 전체 서술이 저장되나, 플레이테스트 JSON에는 300자만 기록됨

### 문장 품질 (300자 범위 내 분석)
- **장점**: 감각 묘사가 풍부 (시각/청각/후각 고루 활용)
  - T09: "짠내를 실어 나른다", "삐걱거리는 오래된 선박"
  - T04: "기름 얼룩", "차가운 공기가 새어 나왔다"
- **단점**: 300자 잘림으로 문장이 중간에 끊김 (T01, T04, T06 등)

### 톤 일관성
- 시장: 활기+긴장 → **적절** (T03~T06)
- 항만: 바다 내음+경계 → **적절** (T09~T14)
- HUB 복귀: 평온 전환 → **적절** (T07, T15)

### 반복 표현 (3회 이상)
| 표현 | 횟수 | 비고 |
|------|------|------|
| "약초 노점의 노부인이" | 3회 | T05, T17, T23에서 동일 묘사 반복 |
| "골목길 벽에 기대어" | 2회 | 입력 자체가 반복 (스크립트 패턴) |
| "조심스럽게" | 4회+ | 잠입 행동 반복 시 동일 수식어 |

### 장면 묘사력
- **시각**: 가로등 불빛, 천막, 깃발 펄럭임 — 매턴 존재 ✅
- **청각**: 파도 소리, 상인 목소리, 쇠사슬 소리 — 빈번 ✅
- **후각**: 짠내, 염분, 구운 고기 — 간헐적 ⚠️
- **촉각**: 차가운 금화, 벽면 온도 — 드묾 ⚠️

### 점수: 6.5/10
- 300자 잘림으로 정밀 분석 불가 (-2.0)
- 감각 묘사 다양성 우수 (+1.0)
- "약초 노점의 노부인" 3회 반복 (-0.5)

---

## [2] 맥락 유지 & NPC 성향 심층

### NPC encounterCount 현황

| NPC | enc | intro | posture | trust | 비고 |
|-----|-----|-------|---------|-------|------|
| NPC_YOON_HAMIN | 1 | ✅ | FRIENDLY | 22 | 유일한 소개 완료 NPC |
| NPC_SEO_DOYUN | 1 | ❌ | CAUTIOUS | -2 | enc=1이나 CAUTIOUS→2회 필요 |
| NPC_ROSA | 0 | ❌ | FRIENDLY | 5 | FRIENDLY인데 enc=0 |
| NPC_MIRELA | 0 | ❌ | FRIENDLY | 10 | FRIENDLY인데 enc=0 |
| NPC_MOON_SEA | 0 | ❌ | CAUTIOUS | 5 | - |
| 기타 6명 | 0 | ❌ | 다양 | - | 전혀 만나지 않음 |

### 근본 원인 분석

**encounterCount 미증가 3중 원인:**

1. **이벤트 `primaryNpcId: null` 다수** — events_v2.json에서 약 44%의 이벤트가 primaryNpcId를 지정하지 않음
2. **태그 기반 NPC 초기화는 카운트 미증가** — Fixplan3-P2 설계: 태그 매칭은 "직접 대면"이 아니므로 encounterCount 증가 안함
3. **FALLBACK 시 NPC 주입 미실행** — `turns.service.ts`에서 이벤트 미매칭(FALLBACK) 시 조기 리턴하여 orchestration 호출 안됨

### NPC 이름 공개 타이밍 검증

| NPC | posture | 필요 enc | 실제 enc | 이름 공개 | 판정 |
|-----|---------|---------|---------|---------|------|
| NPC_YOON_HAMIN | FRIENDLY | 1 | 1 | ✅ | 정상 |
| NPC_SEO_DOYUN | CAUTIOUS | 2 | 1 | ❌ | 정상 (미달) |
| NPC_ROSA | FRIENDLY | 1 | 0 | ❌ | ⚠️ 만남 자체가 없음 |
| NPC_MIRELA | FRIENDLY | 1 | 0 | ❌ | ⚠️ 만남 자체가 없음 |

### 정보 참조 체인
- T03(절도) → T04(조사): 시장 골목 맥락 연속 ✅
- T09(대화) → T10(관찰): 하를런 보스 맥락 유지 ✅
- T11(인사) → T12(관찰): 하를런 동행 유지 ✅
- **단절**: T15~T18(시장 재방문) — 1차 방문(T03~T06) 경험 참조 없음 ⚠️

### NPC 감정축 변화
- **NPC_YOON_HAMIN**: trust 22, respect 8 — 항만에서 대화/관찰 통해 신뢰 축적 ✅
- **NPC_KANG_CHAERIN**: trust -10 — 만남 없이 음수 (초기값 추정) ⚠️

### 점수: 4.5/10
- encounterCount 미증가로 NPC 소개 시스템 사실상 작동 안함 (-3.0)
- 하를런/에드릭 등 서술 내 NPC는 등장하나 시스템 추적 안됨 (-1.5)
- 턴 간 단기 맥락 유지는 양호 (+1.0)
- 장소 재방문 시 이전 방문 정보 참조 부재 (-1.0)

---

## [6] 장소 전환 & HUB 심층

### 장소 순회 패턴

| 방문 | 장소 | 체류 턴 | 이동 방식 |
|------|------|--------|----------|
| 1 | market | 5턴 (T03~T07) | move_location |
| 2 | harbor | 5턴 (T09~T13) | move_location |
| 3 | market | 5턴 (T15~T19) | move_location |

- **장소당 평균 체류**: 5.0턴 (스크립트 기본 4턴 + move_location 1턴)
- **장소 다양성**: 2종/4종 (market, harbor만 방문) — guard, slums 미방문
- **원인**: 스크립트가 `loc-turns=4` 설정으로 4턴 후 이동, 장소 순환은 market→harbor만 반복

### MOVE_LOCATION 처리 검증

| 턴 | 처리 | NODE_ENDED | HUB 복귀 | 비고 |
|----|------|-----------|---------|------|
| T07 | ✅ | ✅ | ✅ T08에서 go_harbor | 정상 |
| T13 | ✅ | ✅ | ✅ T14에서 go_market | 정상 |
| T19 | ✅ | ✅ | ✅ T20에서 go_harbor | 정상 |

- move_location 3회 모두 정상 처리 ✅

### finalizeVisit 타이밍

| 방문 | 장소 | finalizeVisit | storySummary | 비고 |
|------|------|--------------|-------------|------|
| 1 | market | ✅ | "절도(성공), 조사(성공), 관찰(실패). 에드릭 베일 만남" | 정상 |
| 2 | harbor | ✅ | "설득(성공), 관찰(성공), 대화(성공). 하를런 보스 만남" | 정상 |
| 3 | market | ✅ | "관찰(성공), 잠입(성공), 잠입(성공)" | 정상 |

- visitLog 3건 정상 기록 ✅

### HUB 선택지 구성
- T02: go_market → 정상
- T08: go_harbor → 정상
- T14: go_market → 정상
- T20: go_harbor → 정상
- HUB에서 항상 올바른 장소 선택지 제공 ✅

### 점수: 7.5/10
- MOVE_LOCATION 처리 완벽 (+2.0)
- finalizeVisit + storySummary 정상 (+2.0)
- 장소 다양성 부족 (2종/4종) — 스크립트 제한 (-1.5)
- 스크립트가 guard/slums 순환하지 않음 (-1.0)

---

## 수정 대상 이슈 요약

| # | 우선순위 | 이슈 | FOCUS | 대상 파일 |
|---|---------|------|-------|----------|
| 1 | Critical | narrative 300ch 잘림 | [1] | scripts/playtest.py |
| 2 | High | eventId 미기록 | [1] | scripts/playtest.py |
| 3 | High | NPC encounterCount 미증가 (primaryNpcId null 이벤트) | [2] | turns.service.ts |
| 4 | Medium | 장소 순환 2종만 반복 | [6] | scripts/playtest.py |
| 5 | Medium | "약초 노점의 노부인" 반복 | [1] | LLM 컨텍스트 (관찰 필요) |

---

## 수정 전후 비교

### 수정 내용
1. `scripts/playtest.py`: narrative[:300] → 전체 저장, poll_llm [:500] 제거
2. `scripts/playtest.py`: eventId를 ui.actionContext.eventId에서 추출하도록 변경
3. `server/src/turns/turns.service.ts`: 태그 기반 NPC에 대해서도 encounterCount 증가
4. `scripts/playtest.py`: HUB go_X 선택 시 NODE_ENDED에서 loc_idx 미증가 → 4종 순환 보장

### 2차 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | 67772fb4-13a4-4219-a2a3-370ea7d15114 |
| 프리셋 | DESERTER |
| 총 턴 수 | 20 |
| HP / Gold | 100 / ? |
| Day | 2 |
| Heat | 7 |
| Incidents | 3개 |
| 방문 장소 | market(5턴) → guard(5턴) → harbor(5턴) → slums(0턴, 마지막) |

### 점수 비교

| 항목 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 서사 흐름 | 6.5 | 7.5 | **+1.0** |
| NPC 일관성 | 4.0 | 5.5 | **+1.5** |
| 맥락 유지 | 6.0 | 6.5 | **+0.5** |
| 이벤트 다양성 | 5.5 | 7.0 | **+1.5** |
| 메모리 시스템 | 7.0 | 7.0 | 0 |
| **종합** | **5.8** | **6.7** | **+0.9** |

### [1] 이벤트 서술 품질 (2차)

- **서술 길이**: 평균 713ch (1차 298ch → **+415ch**), 최대 1201ch
- **문장 완결**: 300ch 잘림 해소 → 모든 서술이 완결된 문장으로 끝남 ✅
- **반복 표현**: "권위적인 야간 경비" 8회 반복 (새로운 반복 패턴) ⚠️
- **장면 묘사**: 감각 묘사가 풍부해짐 (전체 길이 증가로 더 많은 디테일)
- **점수**: 7.5/10 (+1.0)

### [2] 맥락 유지 & NPC 성향 (2차)

| NPC | enc (1차) | enc (2차) | intro (2차) |
|-----|----------|----------|------------|
| NPC_MIRELA | 0 | 1 | ✅ True |
| NPC_BAEK_SEUNGHO | 0 | 1 | ❌ (CAUTIOUS→2회 필요) |
| NPC_SEO_DOYUN | 1 | 0 | ❌ |
| NPC_YOON_HAMIN | 1 | 0 | ❌ |

- 태그 기반 NPC encounterCount 증가 작동 확인 (NPC_MIRELA: FRIENDLY→enc=1→intro=True) ✅
- 서술에서 "미렐라" NPC 이름이 실제 등장 (T05, T06, T07) ✅
- 이전보다 NPC 추적 범위 확대
- **점수**: 5.5/10 (+1.5)

### [6] 장소 전환 & HUB (2차)

| 방문 | 장소 | 체류 턴 |
|------|------|--------|
| 1 | market | 5턴 |
| 2 | guard | 5턴 |
| 3 | harbor | 5턴 |
| 4 | slums | 0턴 (마지막 턴) |

- **장소 다양성**: 4종/4종 (1차 2종 → 4종) ✅
- guard, slums 방문 성공 ✅
- MOVE_LOCATION 처리 정상 ✅
- **점수**: 8.5/10 (+1.0)

### 수정 항목별 검증

- [✅] narrative 300ch 잘림: 평균 713ch, 최대 1201ch → 완전 해소
- [✅] eventId 미기록: 12개 LOCATION 턴 중 12개 eventId 기록 (100%)
- [✅] NPC encounterCount: 태그 NPC도 카운트 증가 (NPC_MIRELA enc=1→intro=True)
- [✅] 장소 4종 순환: market→guard→harbor→slums 확인
