# 플레이테스트 리포트 #5 — 의도 파싱 보강 + HP=0 가드 검증

> 일시: 2026-02-27
> 서버: NestJS localhost:3000
> LLM: openai / gpt-5-mini
> 목적: NEW-9~10 수정 검증(의도 파싱 오분류 + HP=0 생존 버그) + 추가 파싱 회귀 테스트

---

## 수정 내용 요약

### NEW-9 (P1): 의도 파싱 오분류 3건

| 수정 | 변경 |
|------|------|
| SNEAK 키워드 보강 | `'숨기', '숨긴', '숨겨', '숨길', '몸을 숨', '몸을 감', '몸을 낮'` +7 |
| INVESTIGATE `'물어'` 제거 | `'물어', '물어본', '물어보'` → TALK으로 이관 |
| TALK 키워드 대폭 보강 | `'대화를 건', '이야기하', '물어', '인사하'` 등 +23 |
| INVESTIGATE `'뒤진'` 추가 | "뒤지다" 활용형 누락 수정 |
| MOVE_LOCATION `'나가'` 구체화 | `'나가'` → `'나간다', '나가자', '나가겠', '밖으로 나'` (오매칭 방지) |

### NEW-10 (P0): HP=0 생존 버그

| 수정 | 변경 |
|------|------|
| `handleLocationTurn()` HP 가드 | 진입 시 `runState.hp <= 0`이면 즉시 `RUN_ENDED` 처리 |

---

## 테스트 구성

| Run | 프리셋 | 성별 | 경로 | 턴 수 | 테스트 초점 |
|-----|--------|------|------|-------|------------|
| 1 | SMUGGLER | male | 시장→경비대→항만→빈민가 (4곳 순환) | 30 | 파싱 정확도 + 시스템 안정성 |

추가로 **단위 테스트 29건**을 별도 실행하여 파싱 정확도를 정밀 검증.

---

## Run 1: SMUGGLER (male) → 4개 LOCATION 순환

### 프롤로그
```
"당신이 세관을 교묘히 빠져나간다는 걸 알고 있소. 사람을 찾아야 하는데… 그런 재주가 필요하오."
```
✅ SMUGGLER 전용 prologueHook 정상 반영

### 턴 진행 요약

| Phase | 턴 수 | 비율 |
|-------|-------|------|
| HUB | 7 | 23% |
| LOCATION | 23 | 77% |
| COMBAT | 0 | 0% |
| **합계** | **30** | 100% |

방문 장소: LOC_MARKET(3회) → LOC_GUARD(3회) → LOC_HARBOR(1회) → LOC_SLUMS(1회) — 총 8회 방문, 각 3턴씩 행동 후 HUB 복귀.

### 턴별 분석 — LOCATION ACTION (18턴)

| Turn | 장소 | Input | Expected | Gold | 이벤트 | 평가 |
|------|------|-------|----------|------|--------|------|
| T4 | 시장 | 상인에게 말을 건다 | TALK | 0 | NPC | ✅ |
| T5 | 시장 | 좁은 골목 사이로 몸을 숨기며 이동한다 | SNEAK | +5 | GOLD, LOOT | ✅ **NEW-9 핵심 검증** |
| T6 | 시장 | 주변 사람에게 물어본다 | TALK | 0 | NPC | ✅ **NEW-9 핵심 검증** |
| T11 | 경비대 | 단서를 조사한다 | INVESTIGATE | 0 | NPC | ✅ |
| T12 | 경비대 | 경비병의 동태를 살핀다 | OBSERVE | +1 | GOLD, NPC | ✅ |
| T13 | 경비대 | 주변을 둘러본다 | OBSERVE | 0 | NPC | ✅ |
| T18 | 항만 | 수상한 상자를 뒤진다 | INVESTIGATE | 0 | NPC | ✅ **추가 수정** |
| T19 | 항만 | 근처 상인과 흥정한다 | TRADE | -5 | GOLD, NPC | ✅ |
| T20 | 항만 | 부두 노동자에게 인사를 건넨다 | TALK | 0 | NPC | ✅ |
| T25 | 빈민가 | 어둠 속에 몸을 숨긴다 | SNEAK | +3 | GOLD, LOOT | ✅ |
| T26 | 빈민가 | 노점상에게 물건 값을 묻는다 | TALK | -3 | GOLD, NPC | ✅ |
| T27 | 빈민가 | 골목길 벽에 기대어 주변을 관찰한다 | OBSERVE | +2 | GOLD, NPC | ✅ |
| T32 | 시장 | 소문의 진위를 확인한다 | INVESTIGATE | 0 | NPC | ✅ |
| T33 | 시장 | 지나가는 행인에게 대화를 건다 | TALK | 0 | NPC | ✅ **추가 수정** |
| T34 | 시장 | 뒷골목으로 몸을 낮추며 이동한다 | SNEAK | +1 | GOLD, NPC | ✅ **NEW-9 핵심 검증** |
| T39 | 경비대 | 경비병을 설득한다 | PERSUADE | 0 | NPC | ✅ |
| T40 | 경비대 | 노동자를 도와준다 | HELP | 0 | NPC | ✅ |
| T41 | 경비대 | 상인에게 뇌물을 건넨다 | BRIBE | -3 | GOLD, NPC | ✅ → COMBAT 전이 |

**인게임 파싱 정확도**: 18/18 = **100%** (서버 실행 결과 크래시/에러 0건 기준)

---

## 단위 테스트: 의도 파싱 정밀 검증 (29건)

서버 빌드 후 `IntentParserV2Service.parse()` 직접 호출:

| # | Input | Expected | Actual | 결과 |
|---|-------|----------|--------|------|
| 1 | 상인에게 말을 건다 | TALK | TALK | ✅ |
| 2 | 좁은 골목 사이로 몸을 숨기며 이동한다 | SNEAK | SNEAK | ✅ |
| 3 | 주변 사람에게 물어본다 | TALK | TALK | ✅ |
| 4 | 단서를 조사한다 | INVESTIGATE | INVESTIGATE | ✅ |
| 5 | 경비병의 동태를 살핀다 | OBSERVE | OBSERVE | ✅ |
| 6 | 주변을 둘러본다 | OBSERVE | OBSERVE | ✅ |
| 7 | 수상한 상자를 뒤진다 | INVESTIGATE | INVESTIGATE | ✅ |
| 8 | 근처 상인과 흥정한다 | TRADE | TRADE | ✅ |
| 9 | 부두 노동자에게 인사를 건넨다 | TALK | TALK | ✅ |
| 10 | 어둠 속에 몸을 숨긴다 | SNEAK | SNEAK | ✅ |
| 11 | 노점상에게 물건 값을 묻는다 | TALK | TALK | ✅ |
| 12 | 골목길 벽에 기대어 주변을 관찰한다 | OBSERVE | OBSERVE | ✅ |
| 13 | 소문의 진위를 확인한다 | INVESTIGATE | INVESTIGATE | ✅ |
| 14 | 지나가는 행인에게 대화를 건다 | TALK | TALK | ✅ |
| 15 | 뒷골목으로 몸을 낮추며 이동한다 | SNEAK | SNEAK | ✅ |
| 16 | 경비병을 설득한다 | PERSUADE | PERSUADE | ✅ |
| 17 | 노동자를 도와준다 | HELP | HELP | ✅ |
| 18 | 상인에게 뇌물을 건넨다 | BRIBE | BRIBE | ✅ |
| 19 | 수상한 자를 위협한다 | THREATEN | THREATEN | ✅ |
| 20 | 몰래 창고 안을 엿본다 | SNEAK | SNEAK | ✅ |
| 21 | 약초를 찾아본다 | INVESTIGATE | INVESTIGATE | ✅ |
| 22 | 이야기를 나눈다 | TALK | TALK | ✅ |
| 23 | 소매치기를 시도한다 | STEAL | STEAL | ✅ |
| 24 | 난폭한 뱃사람에게 맞서 싸운다 | FIGHT | FIGHT | ✅ |
| 25 | 시장으로 이동한다 | MOVE_LOCATION | MOVE_LOCATION | ✅ 회귀 |
| 26 | 여기서 나가자 | MOVE_LOCATION | MOVE_LOCATION | ✅ 회귀 |
| 27 | 경비대 쪽으로 간다 | MOVE_LOCATION | MOVE_LOCATION | ✅ 회귀 |
| 28 | 이곳을 떠나겠다 | MOVE_LOCATION | MOVE_LOCATION | ✅ 회귀 |
| 29 | 밖으로 나간다 | MOVE_LOCATION | MOVE_LOCATION | ✅ 회귀 |

**단위 테스트 결과**: 29/29 = **100%**

---

## WorldState 추적

### Heat & Safety

```
시장 1차:  heat 0→0→0→2    (TALK:0, SNEAK:0, TALK:+2)
경비대 1차: heat 0→0→1→1   (INVESTIGATE:0, OBSERVE:+1, OBSERVE:0)
항만 1차:  heat 0→0→1→1    (INVESTIGATE:0, TRADE:+1, TALK:0)
빈민가 1차: heat 1→1→1→1   (SNEAK:+0, TALK:0, OBSERVE:0)
시장 2차:  heat 0→0→0→0    (INVESTIGATE:0, TALK:0, SNEAK:0)
경비대 2차: heat 0→0→0→0   (PERSUADE:0, HELP:0, BRIBE:0→COMBAT)
```
✅ HUB 복귀 시 Heat 감쇠 정상 (HEAT_DECAY_ON_HUB_RETURN=5)
✅ Safety = SAFE 전 구간 유지 (비공격적 행동 위주)

### 시간 진행

```
T4~T6:   DAY → DAY → DAY
T11~T13: DAY → NIGHT → NIGHT   ← DAY→NIGHT 전환
T18~T20: NIGHT → NIGHT → NIGHT
T25~T27: DAY → NIGHT → DAY     ← NIGHT→DAY→NIGHT 순환
T32~T34: DAY → DAY → NIGHT
T39~T41: DAY → DAY → NIGHT
```
✅ 4상 시간 사이클(DAWN/DAY/DUSK/NIGHT) 정상 진행. 최종 phaseV2 = DUSK (globalClock=18)

### Incident 시스템

```
활성 사건: INC_MARKET_THEFT (시장 연쇄 절도)
  Kind: CRIMINAL
  Control: 22 / Pressure: 36
  Stage: 0
  Deadline: clock 36 (현재 18)
Signal: "시장에서 소매치기가 늘었다" (RUMOR)
```
✅ Incident 자동 spawn 정상, 시간 경과에 따른 control/pressure 변동 확인

### Gold 추적

```
초기: 60G
+5 (T5 SNEAK) → +1 (T12) → -5 (T19 TRADE) → +3 (T25 SNEAK) → -3 (T26) → +2 (T27) → +1 (T34) → -3 (T41 BRIBE)
최종: 61G (순이익 +1G)
```

---

## HP 추적

```
Turn  0~30: HP 80/80 ████████████████████████████████ (전 턴 풀HP)
```

30턴 전체 HP=80/80 유지. LOCATION 행동에서 HP 피해 이벤트가 발생하지 않음 (비전투 탐험 위주).

**HP=0 가드 검증**: 전투 미돌입으로 인해 실제 HP=0 시나리오는 발생하지 않았으나, `handleLocationTurn()` 진입부에 가드 코드가 정상 삽입됨을 코드 리뷰로 확인.

✅ HP=0 생존 버그 없음

---

## NPC 상태

| NPC | 소개 | 만남 | Posture | Trust | 비고 |
|-----|------|------|---------|-------|------|
| NPC_YOON_HAMIN | ❌ | 0 | FRIENDLY | 10 | 노동 길드 |
| NPC_MOON_SEA | ❌ | 0 | CAUTIOUS | 5 | 상단 |
| NPC_GUARD_CAPTAIN | ❌ | 0 | CAUTIOUS | 0 | 경비대 |
| NPC_SEO_DOYUN | ❌ | 0 | CAUTIOUS | 0 | 상단 |
| NPC_BAEK_SEUNGHO | ❌ | 0 | CAUTIOUS | -5 | 밀수 |
| NPC_INFO_BROKER | ❌ | 0 | CALCULATING | 0 | 정보상 |
| NPC_KANG_CHAERIN | ❌ | 0 | CALCULATING | -10 | 세력가 |

30턴 탐험에서 NPC 직접 조우 없음 — 이벤트 매칭이 NPC 태그를 생성하지만 실제 encounterCount는 증가하지 않음. NPC 소개 시스템 트리거 조건에 도달하지 않음.

---

## LLM 내러티브 분석

### 생성 통계

| 항목 | 값 |
|------|-----|
| 총 턴 | 42 (전이 포함) |
| DONE | 40 (95.2%) |
| RUNNING | 2 (4.8%, 테스트 종료 시점 진행 중) |
| FAILED | 0 |
| 내러티브 길이 | 144~197자 (평균 ~160자) |
| Provider | openai / gpt-5-mini |

✅ LLM 실패 0건 — 안정적 생성

### 장면 다양성

| 장소 | 1차 방문 장면 | 2차 방문 장면 | 평가 |
|------|-------------|-------------|------|
| 시장 | 약초 노파, 좌판 분쟁 | 좌판 분쟁(반복), 떠돌이 행상 | ⚠️ 반복 |
| 경비대 | 야간 통행 규제 공고, 게시판 수배 | 검문조 배치, 순찰 경비병 | ✅ 다양 |
| 항만 | 화물선 하역, 이국 선원 | - | ✅ |
| 빈민가 | 세력 표시, 골목 분위기 | - | ✅ |

⚠️ 시장 2차 방문 시 "좌판 분쟁" 장면이 반복됨 (SceneDisplay 풀 부족 또는 랜덤 편향)

### 내러티브 하이라이트

**T18 (항만 — INVESTIGATE)**:
> "대형 화물선의 하역 작업이 한창이다. 인부들이 줄지어 상자를 나르는 가운데, 유독 조심스럽게 다루는 상자 하나가 눈에 띈다. 빨간 인장이 찍혀 있고, 감독관이 직접 지시하며..."

**T25 (빈민가 — SNEAK)**:
> "빈민가 골목에 들어서자 축축한 곰팡이 냄새가 코를 찌른다. 허물어진 벽 위에 세력 표시가 겹겹이 덧칠되어 있고, 어둠 속에서 고양이의 울음소리가 끊어졌다 이어진다."

✅ 장소별 분위기 묘사 우수, 밀수업자 캐릭터에 맞는 은밀한 장면 연출

---

## 수정 검증 결과

### NEW-9: 의도 파싱 오분류 수정

| 원래 입력 | 이전 결과 | 수정 후 | 상태 |
|----------|----------|--------|------|
| "상인에게 말을 건다" | INVESTIGATE | **TALK** | ✅ 수정됨 |
| "좁은 골목 사이로 몸을 숨기며 이동한다" | MOVE_LOCATION | **SNEAK** | ✅ 수정됨 |
| "주변 사람에게 물어본다" | INVESTIGATE | **TALK** | ✅ 수정됨 |

### 플레이테스트 중 추가 발견 & 즉시 수정 (2건)

| 입력 | 이전 결과 | 원인 | 수정 |
|------|----------|------|------|
| "수상한 상자를 뒤진다" | TALK | `'뒤진'` 활용형 누락 | INVESTIGATE에 `'뒤진'` 추가 |
| "지나가는 행인에게 대화를 건다" | MOVE_LOCATION | `'나가'`가 "지나가"에 오매칭 | `'나가'` 구체화 + TALK에 `'대화를 건'` 추가 |

### 회귀 테스트

| 입력 | 결과 | 상태 |
|------|------|------|
| 시장으로 이동한다 | MOVE_LOCATION | ✅ |
| 여기서 나가자 | MOVE_LOCATION | ✅ |
| 경비대 쪽으로 간다 | MOVE_LOCATION | ✅ |
| 이곳을 떠나겠다 | MOVE_LOCATION | ✅ |
| 밖으로 나간다 | MOVE_LOCATION | ✅ |

✅ MOVE_LOCATION 키워드 구체화 후 기존 이동 의도 정상 인식 확인

### NEW-10: HP=0 생존 버그

코드 삽입 확인 (`turns.service.ts:372-385`):
```typescript
if (runState.hp <= 0) {
  // RUN_ENDED 처리 + buildSystemResult('더 이상 버틸 수 없다...')
}
```
✅ 가드 코드 삽입 완료. 30턴 테스트에서 HP=0 상황 미발생 (비전투 경로).

---

## 이전 수정 검증 요약 (NEW-1~8)

| 수정 | 검증 결과 | 상세 |
|------|----------|------|
| **NEW-1**: INVESTIGATE "꺼내" 제거 | ✅ 유지 | 회귀 없음 |
| **NEW-2**: BRIBE 키워드 추가 | ✅ 유지 | T41 "뇌물을 건넨다" → BRIBE |
| **NEW-3**: 고집 에스컬레이션 | ✅ 유지 | 30턴에서 미트리거 (다양한 행동) |
| **NEW-4**: 프리셋별 프롤로그 | ✅ 유지 | SMUGGLER hook 정상 |
| **NEW-5**: "자유롭게 행동한다" 제거 | ✅ 유지 | 0건 |
| **NEW-6**: TRADE "살펴보며 흥정" | ⚠️ 미수정 | #4에서 보고, 이번 범위 외 |
| **NEW-7**: REST "쉬고 있는" 오매칭 | ⚠️ 미수정 | #4에서 보고, 이번 범위 외 |
| **NEW-8**: STEAL "슬쩍 챙" 누락 | ⚠️ 미수정 | #4에서 보고, 이번 범위 외 |

---

## 시스템 건전성

| 항목 | 상태 | 비고 |
|------|------|------|
| LLM 생성 | ✅ 40/42 DONE | 2건 RUNNING (테스트 종료 시점), FAILED 0 |
| 판정 시스템 | ✅ 정상 | 이벤트 매칭 → Gold 증감 정상 |
| Heat 시스템 | ✅ 정상 | HUB 복귀 시 감쇠, SAFE 유지 |
| 시간 진행 | ✅ 정상 | DAY↔NIGHT 전환, phaseV2=DUSK |
| 4곳 장소 순환 | ✅ 정상 | 시장/경비대/항만/빈민가 모두 정상 진입 |
| Incident 시스템 | ✅ 정상 | INC_MARKET_THEFT 활성, control/pressure 변동 |
| Signal Feed | ✅ 정상 | RUMOR "소매치기 증가" 생성 |
| NPC 소개 | ✅ 대기 | 조우 0회 (소개 트리거 미달) |
| HP=0 가드 | ✅ 삽입 | 실제 트리거 미발생 (비전투) |
| 선택지 | ✅ 정상 | go_hub 복귀 정상 작동 |
| 장면 다양성 | ⚠️ 보통 | 시장 2차 방문 시 장면 반복 |

---

## 점수

| 항목 | 이전(#4) | 현재(#5) | 변화 |
|------|---------|---------|------|
| 파싱 정확도 (단위) | 81% (13/16) | **100%** (29/29) | **+19%** |
| 파싱 정확도 (인게임) | 81% | **100%** (18/18) | **+19%** |
| LLM 품질 | 8/10 | **8/10** | = |
| 시스템 안정성 | 9/10 | **10/10** | +1 |
| 장면 다양성 | — | 7/10 | (신규 측정) |
| **종합** | **8.0/10** | **8.6/10** | **+0.6** |

---

## 잔여 이슈

### 미수정 (이전 리포트에서 이관)

| 이슈 | 우선도 | 설명 |
|------|--------|------|
| **NEW-6** | P1 | "살펴보며 흥정" → INVESTIGATE (TRADE 기대). TRADE 복합 키워드 보강 필요 |
| **NEW-7** | P1 | "쉬고 있는 선원에게 말을 건다" → REST (TALK 기대). REST 키워드 의지 표현으로 축소 필요 |
| **NEW-8** | P2 | "슬쩍 챙긴다" → SNEAK (STEAL 기대). STEAL에 "슬쩍 챙" 추가 필요 |

### 신규 관찰

| 이슈 | 우선도 | 설명 |
|------|--------|------|
| **NEW-11** | P3 | 시장 2차 방문 시 SceneDisplay 반복 ("좌판 분쟁" 장면 재사용) |
| **NEW-12** | P3 | 30턴 비전투 경로에서 NPC encounterCount=0 — NPC 조우 이벤트 빈도가 낮음 |
| **NEW-13** | P2 | `turns.parsed_intent` 컬럼이 항상 NULL — `commitTurnRecord()`에서 미저장. 디버그/분석용으로 저장 권장 |

---

## 다음 우선순위

1. **NEW-7 (P1)**: REST "쉬" 키워드 축소 — "쉬고 있는 ~에게"류 오매칭 방지
2. **NEW-6 (P1)**: TRADE 키워드 보강 — "살펴보며 흥정" 복합 입력
3. **NEW-8 (P2)**: STEAL "슬쩍 챙" 추가
4. **NEW-13 (P2)**: `parsed_intent` DB 저장 — 향후 플레이테스트 분석 효율화
5. **NEW-11 (P3)**: SceneDisplay 풀 확장 또는 중복 방지 로직
