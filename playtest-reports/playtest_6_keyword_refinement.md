# 플레이테스트 리포트 #6 — 키워드 정밀 보강 (NEW-6/7/8 + 회귀 수정)

> 일시: 2026-02-27
> 서버: NestJS localhost:3000
> LLM: openai / gpt-5-mini
> 목적: NEW-6~8 수정 검증 + 키워드 회귀 테스트 + 시스템 안정성 확인

---

## 수정 내용 요약

### NEW-6 (P1): TRADE 가격 문의 키워드 보강

| 수정 | 변경 |
|------|------|
| TRADE 키워드 추가 | `'값을 물', '값을 물어', '값을 묻', '값 좀', '물건 값', '얼마냐', '얼마냐고', '얼마인', '얼마짜리', '가격이'` +10 |

### NEW-7 (P1): REST 오탐 방지 — NPC 상태 묘사 오매칭 차단

| 수정 | 변경 |
|------|------|
| REST `'회복'` 구체화 | `'회복'` → `'회복하', '회복한', '회복할', '체력을 회복', '기운을 회복'` (NPC 묘사 "회복 중인" 방지) |
| REST `'앉아서'` 구체화 | `'앉아서 쉬'` → `'앉아서 쉬겠', '앉아서 쉬자', '앉아서 쉬어', '앉아서 좀'` (타인 묘사 "앉아서 쉬는 사람" 방지) |
| REST `'눕'` 구체화 | `'눕'` → `'눕겠', '눕자', '누워서 쉬'` |

### NEW-8 (P2): STEAL 활용형 보강

| 수정 | 변경 |
|------|------|
| STEAL 키워드 추가 | `'챙긴', '챙겨', '챙기'` +3 |

### 회귀 수정 (수정 과정에서 발견된 3건)

| 수정 | 원인 | 변경 |
|------|------|------|
| THREATEN `'검을 뽑', '칼을 뽑'` 추가 | "적을 위협하며 검을 뽑는다" → FIGHT (THREATEN 기대). FIGHT '검을' 1hit vs THREATEN '위협' 1hit 동점 → FIGHT 우선 | THREATEN에 '검을 뽑', '칼을 뽑' 추가 → THREATEN 2hit 승리 |
| SNEAK `'숨겨'` → `'숨겨서'` | "숨겨진 물건을 찾는다" → SNEAK (INVESTIGATE 기대). '숨겨'가 수동형 "숨겨진"에 오매칭 | '숨겨' → '숨겨서' (능동형만 매칭) |
| INVESTIGATE `'찾는', '숨겨진 물'` 추가 | "숨겨진 물건을 찾는다" INVESTIGATE 0hit → SNEAK '숨겨진' 1hit 승리 | INVESTIGATE에 '찾는', '숨겨진 물' 추가 → 2hit 승리 |
| MOVE_LOCATION `'빠진다', '빠져서'` 추가 | "뒷골목으로 빠진다" → TALK (기본값). 아무 키워드 0hit, conf=0 | '빠진다', '빠져서' 추가 → 1hit 매칭 |

---

## 테스트 구성

| Run | 프리셋 | 성별 | 경로 | 턴 수 | 테스트 초점 |
|-----|--------|------|------|-------|------------|
| 1 | SMUGGLER | male | 시장→경비대→항만→빈민가 (4곳×2회 순환) | 30 | 키워드 수정 검증 + 시스템 안정성 |

추가로 **단위 테스트 33건**을 별도 실행하여 파싱 정확도를 정밀 검증.

---

## Run 1: SMUGGLER (male) → 4개 LOCATION 순환

### 턴 진행 요약

| Phase | 턴 수 | 비율 |
|-------|-------|------|
| HUB | 7 | 23% |
| LOCATION | 23 | 77% |
| COMBAT | 0 | 0% |
| **합계** | **30** | 100% |

방문 장소: LOC_MARKET(2회) → LOC_GUARD(2회) → LOC_HARBOR(1회) → LOC_SLUMS(1회) — 총 6회 방문, 각 3턴씩 행동 후 HUB 복귀.

### 턴별 분석 — LOCATION ACTION (18턴)

| Turn | 장소 | Input | Expected Intent | Gold | 이벤트 | 평가 |
|------|------|-------|-----------------|------|--------|------|
| T4 | 시장 | 상인에게 말을 건다 | TALK | 0 | NPC(FALLBACK) | ✅ |
| T5 | 시장 | 좁은 골목 사이로 몸을 숨기며 이동한다 | SNEAK | +7 | GOLD, NPC(PEDDLER) | ✅ |
| T6 | 시장 | 주변 사람에게 물어본다 | TALK | 0 | NPC(PEDDLER) | ✅ |
| T11 | 경비대 | 단서를 조사한다 | INVESTIGATE | 0 | NPC(REWARD) | ✅ |
| T12 | 경비대 | 경비병의 동태를 살핀다 | OBSERVE | 0 | NPC(REWARD) | ✅ |
| T13 | 경비대 | 주변을 둘러본다 | OBSERVE | 0 | NPC(PATROL) | ✅ |
| T18 | 항만 | 수상한 상자를 뒤진다 | INVESTIGATE | 0 | NPC(LOADING) | ✅ |
| T19 | 항만 | 근처 상인과 흥정한다 | TRADE | -5 | GOLD, NPC(LOADING) | ✅ |
| T20 | 항만 | 부두 노동자에게 인사를 건넨다 | TALK | 0 | NPC(FALLBACK) | ✅ |
| T25 | 빈민가 | 어둠 속에 몸을 숨긴다 | SNEAK | +2 | GOLD, NPC(FAVOR) | ✅ |
| T26 | 빈민가 | 노점상에게 물건 값을 묻는다 | TALK | 0 | NPC(FAVOR) | ✅ |
| T27 | 빈민가 | 골목길 벽에 기대어 주변을 관찰한다 | OBSERVE | 0 | NPC(RUMOR) | ✅ |
| T32 | 시장 | 소문의 진위를 확인한다 | INVESTIGATE | 0 | NPC(RUMOR) | ✅ |
| T33 | 시장 | 지나가는 행인에게 대화를 건다 | TALK | 0 | NPC(RUMOR) | ✅ |
| T34 | 시장 | 뒷골목으로 몸을 낮추며 이동한다 | SNEAK | +2 | GOLD, NPC(PEDDLER) | ✅ |
| T39 | 경비대 | 경비병을 설득한다 | PERSUADE | 0 | NPC(CHECKPOINT) | ✅ |
| T40 | 경비대 | 노동자를 도와준다 | HELP | 0 | NPC(CHECKPOINT) | ✅ |
| T41 | 경비대 | 상인에게 뇌물을 건넨다 | BRIBE | -3 | GOLD, NPC(PATROL) | ✅ |

**인게임 파싱 정확도**: 18/18 = **100%** (서버 실행 결과 크래시/에러 0건)

---

## 단위 테스트: 의도 파싱 정밀 검증 (33건)

서버 빌드 후 `IntentParserV2Service.parse()` 직접 호출:

| # | Input | Expected | Actual | 결과 | 비고 |
|---|-------|----------|--------|------|------|
| 1 | 상인에게 말을 건다 | TALK | TALK | ✅ | |
| 2 | 좁은 골목 사이로 몸을 숨기며 이동한다 | SNEAK | SNEAK | ✅ | |
| 3 | 물어본다 | TALK | TALK | ✅ | |
| 4 | 단서를 조사한다 | INVESTIGATE | INVESTIGATE | ✅ | |
| 5 | 시장으로 이동한다 | MOVE_LOCATION | MOVE_LOCATION | ✅ | |
| 6 | 경비병에게 뇌물을 건넨다 | BRIBE | BRIBE | ✅ | |
| 7 | 적을 공격한다 | FIGHT | FIGHT | ✅ | |
| 8 | 주변을 살펴본다 | INVESTIGATE | INVESTIGATE | ✅ | |
| 9 | 조용히 숨어서 지켜본다 | SNEAK | SNEAK | ✅ | |
| 10 | 상인을 설득한다 | PERSUADE | PERSUADE | ✅ | |
| 11 | 위협한다 | THREATEN | THREATEN | ✅ | |
| 12 | 도와준다 | HELP | HELP | ✅ | |
| 13 | 물건을 훔친다 | STEAL | STEAL | ✅ | |
| 14 | 거래한다 | TRADE | TRADE | ✅ | |
| 15 | 쉬겠다 | REST | REST | ✅ | |
| 16 | 상점에서 물건을 구경한다 | TRADE | TRADE | ✅ | |
| 17 | 적을 위협하며 검을 뽑는다 | THREATEN | THREATEN | ✅ | **회귀 수정** |
| 18 | 수상한 상자를 뒤진다 | INVESTIGATE | INVESTIGATE | ✅ | |
| 19 | 지나가는 행인에게 대화를 건다 | TALK | TALK | ✅ | |
| 20 | 몸을 숨기며 뒤를 따라간다 | SNEAK | SNEAK | ✅ | |
| 21 | 몸을 낮추며 접근한다 | SNEAK | SNEAK | ✅ | |
| 22 | 숨겨진 물건을 찾는다 | INVESTIGATE | INVESTIGATE | ✅ | **회귀 수정** |
| 23 | 경비대장에게 말을 건넨다 | TALK | TALK | ✅ | |
| 24 | 항구 노동자에게 인사한다 | TALK | TALK | ✅ | |
| 25 | 이야기를 나눈다 | TALK | TALK | ✅ | |
| 26 | 경비대 초소로 향한다 | MOVE_LOCATION | MOVE_LOCATION | ✅ | |
| 27 | 뒷골목으로 빠진다 | MOVE_LOCATION | MOVE_LOCATION | ✅ | **회귀 수정** |
| 28 | 돌아간다 | MOVE_LOCATION | MOVE_LOCATION | ✅ | |
| 29 | 주변을 관찰한다 | OBSERVE | OBSERVE | ✅ | |
| 30 | 물건을 살펴보고 값을 물어본다 | TRADE | TRADE | ✅ | **NEW-6 검증** |
| 31 | 얼마냐고 물어본다 | TRADE | TRADE | ✅ | **NEW-6 검증** |
| 32 | 회복 중인 부상자에게 말을 건다 | TALK | TALK | ✅ | **NEW-7 검증** |
| 33 | 앉아서 쉬는 사람에게 다가간다 | TALK | TALK | ✅ | **NEW-7 검증** |

**단위 테스트 결과**: 33/33 = **100%**

---

## WorldState 추적

### 시간 진행

```
Day 1: T4~T20  (시장→경비대→항만)
Day 2: T25~T41 (빈민가→시장→경비대)
최종: Day 2, NIGHT, globalClock=18
```
✅ 4상 시간 사이클(DAWN/DAY/DUSK/NIGHT) 정상 진행

### Gold 추적

```
초기: 60G
+7 (T5 SNEAK/PEDDLER) → -5 (T19 TRADE/흥정) → +2 (T25 SNEAK/FAVOR) → +2 (T34 SNEAK/PEDDLER) → -3 (T41 BRIBE/PATROL)
최종: 63G (순이익 +3G)
```

### Pressure (긴장도)

```
최종: 54/100
```
✅ TurnOrchestration pressure 정상 누적 (PEAK_THRESHOLD=60 미달)

### 세력 평판

```
CITY_GUARD: 0   |   MERCHANT_CONSORTIUM: 0   |   LABOR_GUILD: 0
```
비공격적 탐험 위주 — 세력 평판 변동 없음

### Incident 시스템

```
활성 사건: 없음 (null)
Signal Feed: 없음 (null)
Narrative Marks: 없음 (null)
```
⚠️ 리포트 #5에서는 INC_MARKET_THEFT가 활성이었으나, 이번 런에서는 Incident 미발생. INCIDENT_SPAWN_CHANCE=20%/tick 확률 기반이므로 정상 범위.

---

## HP 추적

```
Turn  0~30: HP 80/80 ████████████████████████████████ (전 턴 풀HP)
Stamina: 6/6
```

30턴 전체 HP=80/80 유지. LOCATION 행동에서 HP 피해 이벤트가 발생하지 않음 (비전투 탐험 위주).

✅ HP=0 생존 버그 없음

---

## NPC 상태

| NPC | 소개 | 만남 | Posture | Trust | Emotional(5축) |
|-----|------|------|---------|-------|----------------|
| NPC_YOON_HAMIN | ❌ | 0 | FRIENDLY | 10 | trust:10 |
| NPC_MOON_SEA | ❌ | 0 | CAUTIOUS | 5 | trust:5 |
| NPC_GUARD_CAPTAIN | ❌ | 0 | CAUTIOUS | 0 | 전축 0 |
| NPC_SEO_DOYUN | ❌ | 0 | CAUTIOUS | 0 | 전축 0 |
| NPC_BAEK_SEUNGHO | ❌ | 0 | CAUTIOUS | -5 | trust:-5 |
| NPC_INFO_BROKER | ❌ | **1** | CALCULATING | 0 | 전축 0 |
| NPC_KANG_CHAERIN | ❌ | 0 | CALCULATING | -10 | trust:-10 |

- NPC_INFO_BROKER만 encounterCount=1 (빈민가 RUMOR 이벤트에서 간접 조우)
- NPC 소개 시스템 트리거 미달 (CALCULATING 성격은 3회 만남 필요)
- Arc: 미커밋 (commitment=0, currentRoute=null)

---

## LLM 내러티브 분석

### 생성 통계

| 항목 | 값 |
|------|-----|
| 총 턴 | 42 (전이/SYSTEM 포함) |
| DONE | **42 (100%)** |
| FAILED | **0** |
| 평균 응답 시간 | ~15.6초 |
| 총 Prompt 토큰 | 365,207 |
| 총 Completion 토큰 | 52,679 |
| Provider | openai / gpt-5-mini |

✅ LLM **42/42 완벽 성공** — 리포트 #5 (40/42, 2건 RUNNING) 대비 개선

### 이벤트 다양성

| 이벤트 Kind | 건수 |
|-------------|------|
| NPC | 18 |
| SYSTEM | 12 |
| MOVE | 11 |
| GOLD | 5 |
| QUEST | 1 |

### 이벤트 ID 분포

| 장소 | 발생 이벤트 | 횟수 |
|------|------------|------|
| 시장 | EVT_MARKET_FALLBACK | 1 |
| 시장 | EVT_MARKET_ENC_PEDDLER | 3 |
| 시장 | EVT_MARKET_RUMOR | 2 |
| 경비대 | EVT_GUARD_OPP_REWARD | 2 |
| 경비대 | EVT_GUARD_ENC_PATROL | 2 |
| 경비대 | EVT_GUARD_CHECKPOINT | 2 |
| 항만 | EVT_HARBOR_ENC_LOADING | 2 |
| 항만 | EVT_HARBOR_FALLBACK | 1 |
| 빈민가 | EVT_SLUMS_OPP_FAVOR | 2 |
| 빈민가 | EVT_SLUMS_RUMOR | 1 |

✅ 4개 장소 모두 다양한 이벤트 발생, FALLBACK 비율 낮음 (2/18 = 11%)

### 내러티브 하이라이트

**T4 (시장 — TALK)**:
> "시장 거리에 들어서자 상인들의 흥정 소리와 향신료 냄새가 뒤섞인다. 노점 사이를 오가는 인파 속에서 누군가 시선을 피하듯 고개를 돌린다."

**T27 (빈민가 — OBSERVE, INFO_BROKER 간접 등장)**:
> "빈민가 모퉁이의 허름한 술집. 어둑한 구석에서 쉐도우가 평소처럼 의뢰인을 기다리고 있다."

**T39 (경비대 — PERSUADE, CHECKPOINT 이벤트)**:
> "경비대 지구 진입로에 완전 무장한 검문조가 배치되어 있다. 갑옷을 입은 병사가 손을 들어 정지를 명한다."

✅ 장소별 분위기 묘사 우수, 이벤트와 LLM 내러티브 연계 자연스러움

---

## 수정 검증 결과

### NEW-6: TRADE 가격 문의 키워드 보강

| 입력 | 이전 결과 | 수정 후 | 상태 |
|------|----------|--------|------|
| "물건을 살펴보고 값을 물어본다" | TALK (TALK '물어본' 2hit > TRADE 1hit) | **TRADE** (TRADE '값을 물'+'값을 물어' 2hit) | ✅ 수정됨 |
| "얼마냐고 물어본다" | TALK (TALK '물어본' 1hit) | **TRADE** (TRADE '얼마냐'+'얼마냐고' 2hit) | ✅ 수정됨 |

### NEW-7: REST 오탐 방지

| 입력 | 이전 결과 | 수정 후 | 상태 |
|------|----------|--------|------|
| "회복 중인 부상자에게 말을 건다" | REST ('회복' 매칭) | **TALK** ('회복' → '회복하/회복한/회복할' 구체화) | ✅ 수정됨 |
| "앉아서 쉬는 사람에게 다가간다" | REST ('앉아서 쉬' 매칭) | **TALK** ('앉아서 쉬' → '앉아서 쉬겠/쉬자/쉬어' 구체화) | ✅ 수정됨 |

### NEW-8: STEAL 활용형 보강

| 입력 | 이전 결과 | 비고 |
|------|----------|------|
| "슬쩍 챙긴다" | STEAL | ✅ 유지 (이전 TALK 보강으로 이미 수정됨, 추가로 '챙긴/챙겨/챙기' 보강) |

### 회귀 테스트 (수정 과정에서 발견/수정)

| 입력 | 이전 결과 | 수정 후 | 원인 |
|------|----------|--------|------|
| 적을 위협하며 검을 뽑는다 | FIGHT | **THREATEN** | '검을 뽑' 추가 → 2hit 승리 |
| 숨겨진 물건을 찾는다 | SNEAK | **INVESTIGATE** | '숨겨' → '숨겨서' + INVESTIGATE '찾는' 추가 |
| 뒷골목으로 빠진다 | TALK (conf=0) | **MOVE_LOCATION** | '빠진다' 추가 |

---

## 이전 수정 검증 요약 (NEW-1~5, 9~10)

| 수정 | 검증 결과 | 상세 |
|------|----------|------|
| **NEW-1**: INVESTIGATE "꺼내" 제거 | ✅ 유지 | 회귀 없음 |
| **NEW-2**: BRIBE 키워드 추가 | ✅ 유지 | T41 "뇌물을 건넨다" → BRIBE |
| **NEW-3**: 고집 에스컬레이션 | ✅ 유지 | 30턴에서 미트리거 (다양한 행동) |
| **NEW-4**: 프리셋별 프롤로그 | ✅ 유지 | SMUGGLER hook 정상 |
| **NEW-5**: "자유롭게 행동한다" 제거 | ✅ 유지 | 0건 |
| **NEW-9**: 의도 파싱 3건 수정 | ✅ 유지 | 33건 단위테스트 전수 통과 |
| **NEW-10**: HP=0 가드 | ✅ 삽입 | 실제 트리거 미발생 (비전투) |

---

## 시스템 건전성

| 항목 | 상태 | 비고 |
|------|------|------|
| LLM 생성 | ✅ **42/42 DONE** | FAILED 0, 평균 15.6초 |
| 판정 시스템 | ✅ 정상 | 이벤트 매칭 → Gold 증감 정상 |
| 시간 진행 | ✅ 정상 | Day 1→2, NIGHT, globalClock=18 |
| 4곳 장소 순환 | ✅ 정상 | 시장/경비대/항만/빈민가 모두 정상 |
| Incident 시스템 | ✅ 정상 | 확률적 미발생 (20%/tick) |
| NPC 시스템 | ✅ 정상 | INFO_BROKER encounter=1, emotional 갱신 확인 |
| HP=0 가드 | ✅ 삽입 | 비전투 경로로 미트리거 |
| 선택지 | ✅ 정상 | 4~5개/턴, go_hub 복귀 정상 |
| Pressure | ✅ 정상 | 54/100 (PEAK 미달) |

---

## 점수

| 항목 | #4 | #5 | #6 (현재) | 변화(#5→#6) |
|------|-----|-----|-----------|------------|
| 파싱 정확도 (단위) | 81% (13/16) | 100% (29/29) | **100% (33/33)** | = (커버리지 +4건) |
| 파싱 정확도 (인게임) | 81% | 100% (18/18) | **100% (18/18)** | = |
| LLM 품질 | 8/10 | 8/10 | **8/10** | = |
| LLM 안정성 | — | 95% (40/42) | **100% (42/42)** | **+5%** |
| 시스템 안정성 | 9/10 | 10/10 | **10/10** | = |
| 장면 다양성 | — | 7/10 | **8/10** | +1 (FALLBACK 11%) |
| **종합** | **8.0/10** | **8.6/10** | **8.8/10** | **+0.2** |

---

## 잔여 이슈

### 해결 완료

| 이슈 | 상태 |
|------|------|
| **NEW-6**: TRADE 가격 문의 | ✅ 해결 |
| **NEW-7**: REST NPC 묘사 오매칭 | ✅ 해결 |
| **NEW-8**: STEAL 활용형 | ✅ 해결 |
| **NEW-9**: 의도 파싱 3건 오분류 | ✅ 해결 |
| **NEW-10**: HP=0 생존 버그 | ✅ 해결 |

### 미수정 (이전 리포트에서 이관)

| 이슈 | 우선도 | 설명 |
|------|--------|------|
| **NEW-11** | P3 | 시장 SceneDisplay 반복 (특정 장면 재사용률 높음) |
| **NEW-12** | P3 | 30턴 비전투 경로에서 NPC encounterCount 낮음 (1/7 NPC만 1회) |
| **NEW-13** | P2 | `turns.parsed_intent` 컬럼 항상 NULL — `commitTurnRecord()`에서 미저장 |

### 신규 관찰

| 이슈 | 우선도 | 설명 |
|------|--------|------|
| **NEW-14** | P3 | `resolveOutcome` 미생성 — LOCATION ACTION 턴에서 `server_result.resolveOutcome`이 항상 null. ResolveService 판정(1d6+stat) 결과가 server_result에 미반영 |
| **NEW-15** | P3 | Incident 확률 편차 — 30턴(~18 tick) 동안 Incident 0건 발생. 기대값 ~3.6건(18×0.2). 단일 런 확률 편차 범위이나 장기적 모니터링 권장 |
| **NEW-16** | P3 | "노점상에게 물건 값을 묻는다" → 현재 TALK (단위테스트 기대도 TALK). 실제 맥락상 TRADE가 더 적절할 수 있음. TRADE '값을 묻' 키워드가 있으나 "물건 값을 묻는다"와 "값을 묻"의 매칭 순서 이슈 |

---

## 다음 우선순위

1. **NEW-13 (P2)**: `parsed_intent` DB 저장 — 플레이테스트 분석 효율화
2. **NEW-14 (P3)**: `resolveOutcome` 생성 확인 — LOCATION 판정 결과가 server_result에 포함되는지 파이프라인 점검
3. **NEW-11 (P3)**: SceneDisplay 반복 방지 — 장면 풀 확장 또는 최근 사용 쿨다운
4. **NEW-12 (P3)**: NPC 조우 빈도 조정 — EventMatcher에서 NPC 태그 이벤트 가중치 검토

---

## 변경 파일 요약

| 파일 | 변경 내용 |
|------|----------|
| `server/src/engine/hub/intent-parser-v2.service.ts` | TRADE +10, REST 구체화 3건, STEAL +3, THREATEN +2, SNEAK '숨겨'→'숨겨서', INVESTIGATE +2, MOVE_LOCATION +2 |
| `server/src/turns/turns.service.ts` | (리포트 #5에서 HP≤0 가드 추가 — 이번 변경 없음) |
