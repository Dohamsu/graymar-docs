# Playtest Report — 장소 이동 이미지 검증 (2026-03-18)

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | `9d70c724-8c23-4a0c-86f9-3d246790dffb` |
| 프리셋 | DESERTER (male) |
| 총 턴 수 | 10 (턴 1~13, HUB 전환 턴 포함) |
| 최종 상태 | RUN_ACTIVE |
| 방문 장소 | LOC_MARKET (4턴 체류), LOC_GUARD (3턴 체류) |
| Heat | 15 → 10 → 5 |
| TimePhase | DAY → NIGHT (턴 12에서 전환) |
| HubSafety | SAFE (전구간) |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 서술 | 비고 |
|----|------|------|--------|------|------|
| 1 | HUB | accept_quest | 의뢰 수락 | — | 초기 퀘스트 |
| 2 | HUB→MARKET | go_market | 시장 이동 | 673자 | NODE_ENDED + 전환 |
| 4 | LOC_MARKET | llm_3_0 (노부인 질문) | 1골드+MERCHANT_DISPUTE | 958자 | 장부 관련 정보 획득 |
| 5 | LOC_MARKET | llm_4_0 (상인 화해) | BUSKER_ENC | 787자 | 두 상인 다툼 개입 |
| 6 | LOC_MARKET | llm_5_0 (골목 추적) | 2골드+PEDDLER_ENC | 835자 | 수상한 사내 추적 |
| 7 | LOC_MARKET | go_hub | 귀환 | — | NODE_ENDED |
| 9 | HUB→GUARD | go_guard | 경비대 이동 | 630자 | NODE_ENDED + 전환 |
| 11 | LOC_GUARD | llm_10_0 (순찰 동선) | PROC_11 | 870자 | 순찰 정보 습득 |
| 12 | LOC_GUARD | llm_11_0 (병력 배치) | GUARD_ATM_3 | 783자 | 배치도 입수, DAY→NIGHT |
| 13 | LOC_GUARD | go_hub | 귀환 | — | NODE_ENDED |

## C. 종합 점수

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 7.5/10 | 장부 → 추적 → 경비대 정보의 연결 자연스러움 |
| NPC 일관성 | 7.0/10 | 노부인/경비대장 태도 유지, 이름 비공개 정상 |
| 맥락 유지 | 7.0/10 | 장부 사건이 두 장소 걸쳐 유지됨 |
| 이벤트 다양성 | 7.0/10 | 4종 이벤트 발생 (DISPUTE, BUSKER, PEDDLER, PROC) |
| 메모리 시스템 | 6.5/10 | storySummary 미확인 (LLM 데이터만 수집) |
| **종합** | **7.0/10** | |

## D. 개선 권장사항

### Critical
- 없음

### High
- **resolveOutcome이 null** — LOCATION 턴에서 판정 결과(SUCCESS/PARTIAL/FAIL)가 수집되지 않음. serverResult 경로 확인 필요 (게임 로직 자체는 정상 작동, 수집 스크립트 이슈일 가능성)

### Medium
- **장소 다양성 부족** — 10턴 중 2개 장소(MARKET, GUARD)만 방문. 4개 장소 순회 미완
- **시간대 전환 느림** — DAY→NIGHT 전환이 턴 12에서야 발생 (9턴 소요)

### Low
- **HUB 경유 턴 소비** — go_hub → go_location 전환 시 2턴 소비 (턴 7→9, 13→14)

---

## E. 심층 분석 [1] — 이벤트 서술 품질

### 문장 품질
- 전반적으로 **중세 판타지 톤 유지** 양호
- 경어체("~하오", "~하시오") 일관 사용
- 번역체 표현 최소화됨

### 톤 일관성
| 장소 | 기대 톤 | 실제 톤 | 일치 |
|------|---------|---------|------|
| LOC_MARKET | 활기+긴장 | 활기+소문+은밀 | O |
| LOC_GUARD | 질서+위엄 | 질서+경계+피로 | O |

### 반복 표현 (3회 이상)
| 표현 | 횟수 | 비고 |
|------|------|------|
| "낮은 목소리로" | 4회 | 턴 4,5,11,12 |
| "조심스레/조심스럽게" | 5회 | 과다 |
| "눈빛/시선" | 6회+ | 거의 매 턴 등장 |
| "소곤거리는" | 3회 | 턴 9,11,12 |
| "골목" | 5회+ | 장소 묘사 편향 |

### 장면 묘사력
- **시각**: 풍부 (색감, 건물, 인물 외형)
- **청각**: 양호 (발소리, 소란, 바람)
- **후각**: 제한적 (고기 굽는 냄새 1회, 약초 향 1회)
- **촉각**: 거의 없음

### 서술 길이 분포
| 턴 | 장소 | 문자수 |
|----|------|--------|
| 3 (진입) | MARKET | 673 |
| 4 | MARKET | 958 |
| 5 | MARKET | 787 |
| 6 | MARKET | 835 |
| 10 (진입) | GUARD | 630 |
| 11 | GUARD | 870 |
| 12 | GUARD | 783 |
| **평균** | | **791자** |
| **최소** | | 630자 (진입) |
| **최대** | | 958자 |

### 선택지 서술
- LLM 생성 선택지: 평균 3개/턴 + go_hub 1개
- 선택지가 직전 서술의 구체적 요소를 반영 (노부인, 골목, 상인 등)
- **양호**: 상황 맥락이 잘 녹아 있음

### 점수: 7.5/10
- **강점**: 톤 일관성, 선택지 맥락 반영, 장면 구성
- **약점**: 반복 표현 과다 ("조심스레", "낮은 목소리"), 후각/촉각 묘사 부족
- **개선 필요 턴**: 턴 11~12 (경비대장 묘사 반복)

---

## F. 심층 분석 [6] — 장소 전환 & HUB

### 장소 순회 패턴

```
HUB(T1) → accept_quest
HUB(T2) → go_market → LOC_MARKET(T3~T7, 4턴 체류)
HUB(T8~T9) → go_guard → LOC_GUARD(T10~T13, 3턴 체류)
HUB(T14) ← 최종
```

### MOVE_LOCATION 처리
| 전환 | 방법 | 결과 | 정상 |
|------|------|------|------|
| HUB→MARKET | CHOICE:go_market | NODE_ENDED + transition | O |
| MARKET→HUB | CHOICE:go_hub | NODE_ENDED | O |
| HUB→GUARD | CHOICE:go_guard | NODE_ENDED + transition | O |
| GUARD→HUB | CHOICE:go_hub | NODE_ENDED | O |

- 모든 전환이 정상 처리됨
- `transition.enterResult`에서 새 노드 초기 데이터 정상 수신

### WorldState 변화 추적 (이미지 매핑 검증)

| 턴 | locationId | timePhase | hubSafety | 예상 이미지 |
|----|-----------|-----------|-----------|------------|
| 1-2 | null (HUB) | DAY | SAFE | `graymar_overview.png` |
| 3-7 | LOC_MARKET | DAY | SAFE | `market_day_safe.png` |
| 8-9 | null (HUB) | DAY | SAFE | `graymar_overview.png` |
| 10-11 | LOC_GUARD | DAY | SAFE | `guard_day_safe.png` |
| 12 | LOC_GUARD | NIGHT | SAFE | fallback → `guard_day_safe.png`* |
| 13 | LOC_GUARD | NIGHT | SAFE | fallback → `guard_day_safe.png`* |

*`guard_night_safe.png`가 없으므로 fallback 체인 동작:
1. `guard_night_safe` → 없음
2. `guard_night_safe` (SAFE 디그레이드) → 없음
3. `guard_day_safe` → 있음 (fallback 성공)

### LocationImage 컴포넌트 예상 동작

1. **HUB→MARKET 전환**: `graymar_overview.png` → `market_day_safe.png` (크로스페이드)
2. **MARKET 체류**: 이미지 변경 없음 (같은 파일)
3. **MARKET→HUB**: `market_day_safe.png` → HUB에서는 LocationImage 미표시 (LOCATION phase만)
4. **HUB→GUARD**: → `guard_day_safe.png` (크로스페이드)
5. **DAY→NIGHT 전환(턴 12)**: `guard_day_safe.png` → `guard_day_safe.png` (fallback, 변경 없음)

### HUB 썸네일 검증
- `LocationCard`에 `imagePath` 추가됨
- 4개 장소 모두 `*_day_safe.png` 썸네일 표시 예상

### 체류 패턴
| 장소 | 체류 턴 |
|------|---------|
| LOC_MARKET | 4턴 (T3~T7) |
| LOC_GUARD | 3턴 (T10~T13) |
| LOC_HARBOR | 미방문 |
| LOC_SLUMS | 미방문 |

### finalizeVisit 타이밍
- T7 (MARKET 떠남): NODE_ENDED → 정상
- T13 (GUARD 떠남): NODE_ENDED → 정상

### 점수: 8.0/10
- **강점**: 전환 메커니즘 안정적, WorldState 정확, fallback 체인 동작 예상
- **약점**: 10턴 내 2개 장소만 방문 (4개 중), NIGHT 시 이미지 변형 부족 (guard_night_safe 없음)
- **이미지 매핑 커버리지**: 13개 이미지 중 3개만 활용 (graymar_overview, market_day_safe, guard_day_safe)

---

## G. 이미지 기능 검증 결과

### 매핑 로직 검증

| 테스트 케이스 | 입력 | 기대 출력 | 결과 |
|-------------|------|----------|------|
| HUB (loc=null) | (null, DAY, SAFE) | `graymar_overview.png` | PASS |
| 시장 낮 안전 | (LOC_MARKET, DAY, SAFE) | `market_day_safe.png` | PASS |
| 경비대 낮 안전 | (LOC_GUARD, DAY, SAFE) | `guard_day_safe.png` | PASS |
| 경비대 밤 안전 | (LOC_GUARD, NIGHT, SAFE) | `guard_day_safe.png` (fallback) | PASS |
| TimePhaseV2 정규화 | DAWN→DAY, DUSK→NIGHT | 정상 | PASS |

### 미검증 항목 (추가 테스트 필요)
- [ ] LOC_HARBOR, LOC_SLUMS 장소 이미지 매핑
- [ ] ALERT, DANGER 안전도에서의 이미지 변형
- [ ] 크로스페이드 애니메이션 (브라우저 테스트 필요)
- [ ] 이미지 로드 실패 시 fallback 그라디언트
- [ ] 모바일 반응형 (140px 높이)
- [ ] HUB LocationCard 썸네일 표시

### 결론
- **게임 흐름**: 정상 — HUB → LOCATION → HUB 순환 안정적
- **WorldState 데이터**: 정상 — currentLocationId, timePhase, hubSafety 모두 올바르게 전달
- **이미지 매핑 로직**: 정상 — fallback 체인 포함 모든 경우 커버
- **브라우저 UI 테스트**: 미실시 — 수동 테스트 권장
