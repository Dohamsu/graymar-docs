# 81 — 밤낮 시스템 재설계 (2026-07-20) + 2차 재설계 (2026-07-25)

> 상태: ✅ 구현·배포. server `3f219f0`+`644af71`, client `4406aaa`. **2차: §2차 재설계 참조.**
> 배경: "컨셉은 좋은데 맥락이 끊기고, 강제로 밤낮 전환되고, 특이사항이 안 느껴진다"는 사용자 체감.

## 진단 — 이중 시간계가 절반만 배선

밤낮이 **두 병렬 시스템**으로 돌아가고 있었다.

| 시스템 | 값 | 구동 대상 |
|--------|-----|----------|
| **v2 (4상, 정밀)** `phaseV2` | 새벽/낮/황혼/밤 (12tick=1일) | LLM 프롬프트 조명 힌트, NPC 위치 스케줄, NIGHT_CHILD 특성 |
| **v1 (2상, 조잡)** `timePhase` | DAY/NIGHT | **플레이어가 보는 모든 UI** |

세 증상 → 근본 원인:
1. **강제 전환**: `preStepTick` timeCost 하드코딩 `1` — 행동 무관 2~4턴마다 기계식 전환.
2. **맥락 단절**: [현재 시간대] 블록이 매 턴 '지금'만 주입, 전환 발생 사실은 LLM에 미전달 → 장면 중간 조명 급전환.
3. **특이사항 미체감**: 클라 `TimePhaseTransition`이 2상만 반응 → 4개 전환 중 2개만, 그것도 황혼→"밤" 오표기.

**심층 결함 — `advanceTime` v1 토글**: `world-state.service.advanceTime`가 `timeCounter` 5턴마다 timePhase를 DAY↔NIGHT 독립 토글. LOCATION 턴은 postStepTick 재동기화로 가려지나 **전투 트리거 경로(postStepTick 스킵)에서 토글 잔존** → `timePhase=NIGHT` vs `phaseV2=DAY` 불일치 실측. 구 클라가 timePhase를 소비했으므로 "5턴마다 강제 밤낮 + 서술 불일치"의 진짜 근원.

## 구현 (4건, 전부 phaseV2 기반)

### ① 행동 가중 시간 (`computeTurnTimeCost`)
- 인사·안부·감사·작별(dialogueAct) = **0**(시간 정지) / 이동·휴식 = **2** / 그 외 = **1**.
- packMeter 틱도 동일 가중. 실측: chatty 15턴 globalClock 4(구 코드 ~15, 전환 5회→1회).

### ② 전환 서술 주입 (`recentPhaseTransition`)
- `WorldState.recentPhaseTransition{from,to,atClock}` 신설. 전환이 **실제 일어난 턴에만** prompt에 `[시간대 전환]` 디렉티브(도입부 전환 문구 강제).
- prevPhaseV2 캡처 → `context.phaseTransition` → prompt-builder 조건부 블록. `injected-block-headers` 등록.
- 실측: T5 서술이 DAY 전환 문구 "해가 완전히 떠올라" 실반영.

### ③ 4상 UI 승격
- WorldStateUI 빌더 4곳(turns 3 + runs 1)에 `phaseV2`·`day` 추가. `server-result.ts` 타입 확장.
- 클라 `TimePhaseTransition` 2상→4상 재작성(새벽/낮/황혼/밤 고유 아이콘·문구, 황혼 오표기 해소). Header 표시기·GameClient 배선.

### ④ 이중 시간계 통합 (핵심)
- **`deriveTimePhaseFromV2(phaseV2)` 헬퍼 신설** — timePhase는 phaseV2의 파생 미러로 통일.
- `advanceTime`: v1 독립 토글 폐지 → phaseV2 파생 동기화만. `timeCounter`(미사용) 증가 제거, `TIME_CYCLE_TURNS` 삭제.
- `world-tick.postStepTick` 동기화도 동일 헬퍼로 통일(단일 공식).
- turns.service LOCATION 경로 redundant `advanceTime` 제거(postStepTick 소유), 전투 트리거 경로는 미러 동기화 유지.
- 실측: brawler 12턴 globalClock 8 → phaseV2 NIGHT = timePhase NIGHT 정합, 전환 {DUSK→NIGHT} 캡처.

## 불변 (신규)
- **timePhase = phaseV2 파생 미러** — 독립 시간계 아님. 단일 정본 = phaseV2(globalClock). timePhase를 독립 토글하는 코드 추가 금지.

## 잔여 (백로그)
- 시간대별 **특이 이벤트/시그널** ("밤에만 벌어지는 일") — 콘텐츠 작업. 원 진단 ③의 미해결 축.

---

## 2차 재설계 (2026-07-25) — "시간은 이동과 시간이 걸리는 행동에서만 흐른다"

> 배경: "대화 중에 시간대가 급격히 바뀌는 게 이상하다. 장소 이동이나 시간이 걸리는
> 행동을 했을 때 시간이 흐르게 하라"는 소유자 지시.

### 실측 진단 (배포 후 실유저 런 6개, phase 턴 129·전환 38회)

1. **전환 과빈** — 평균 **3.4턴마다** 시간대 전환. 1차 실측(chatty 봇, 15턴 4tick)은
   잡담 위주라 실유저(조사·이동 위주, 1tick/턴)와 괴리. 대화·조사 턴이 시계를 밀어
   "대화 중 일몰"이 상시 발생.
2. **이동은 시간이 0** — `MOVE_LOCATION: 2` 비용은 **죽은 코드**였다. 실제 이동 3경로
   (HUB `go_*` / `performLocationTransition` / `returnToHubFlow`)는 전부
   `applyNarrativeTicksAndRewards`(preStepTick) **이전에 조기 return** → 설계 의도와
   정반대로 "대화하면 시간이 가고 이동하면 안 가는" 배선.
3. **전환 상투구 anchor** — `transPhrase` 예문("해가 기울며 그림자가 길어지고" 등)을
   LLM이 그대로 복제, 전환 38회 중 41히트. 불변식 50 위반 실측.

### 구현 (server ca44b01 시점)

| # | 변경 | 위치 |
|---|------|------|
| ① | **행동 시간표 재설계** — 대화 계열(TALK/PERSUADE/BRIBE/THREATEN/HELP/TRADE/OBSERVE) + 사교 발화 = **0(시간 정지)** / 시간이 걸리는 행동(INVESTIGATE/SEARCH/SNEAK/STEAL/FIGHT/SHOP) = 1 / REST = 2. 정본을 `turns/time-cost.ts`로 추출(유닛 4케이스) | `time-cost.ts` `computeTurnTimeCost` |
| ② | **이동 시계 배선 복구** — `WorldTickService.advanceClockForTravel(ws, ticks)` 신설(경량: clock/phaseV2/day 전진 + timePhase 미러 + `recentPhaseTransition` 기록 + NPC 스케줄 재배치. **Incident tick·spawn·signal·packMeter는 의도적 제외** — 이동 SYSTEM 턴에 사건 스폰 부작용 방지). 직행 이동(LOC→LOC) `MOVE_TIME_COST=2`, HUB 경유 편도 `TRAVEL_LEG_TIME_COST=1`(왕복 합 = 직행과 등가, 2배 벌어짐 방지). 유닛 6케이스 | `world-tick.service.ts` + turns.service 이동 3경로 |
| ③ | **전환 상투구 anchor 제거** — `transPhrase` 예문 삭제, "이 장소·상황의 구체 사물로 표현(상투구 반복 금지)" 추상 지시로 교체 | `prompt-builder.service.ts` [시간대 전환] |

이동 턴 전환 시 `recentPhaseTransition`이 도착 턴 LLM 컨텍스트로 소비되어
"도착하니 해가 저물어 있었다"류 서술이 자연 발생한다.

### 검증 (chatty 12턴 + 10턴 실런, 게이트 PASS)

- 대화 턴(TALK/PERSUADE/사교) 동안 phase 불변 — **대화 중 전환 0회** (T4~T7 DAY 고정 등).
- 전환은 전부 이동·조사 턴에서만 발생. 시계 산수 기대값=실측 완전 일치(clock 10, clock 4).
- HUB 왕복(장소→HUB→장소) = 총 2tick = 직행과 등가 확인.
- 전체 유닛 1,583 green(신규 10 포함), 스냅샷 17 통과.

### 불변 (갱신)
- 시간 진행 소유자 = **WorldTickService** (`preStepTick` — 행동 턴 + `advanceClockForTravel` — 이동 턴). 그 외 경로에서 globalClock/phaseV2 변경 금지.
- **대화로는 시간이 흐르지 않는다** — 대화 계열·사교 발화 timeCost 0. 시간대 전환은 이동·시간 소요 행동에서만.

---

## 3차 조정 (2026-08-13) — 대화 지연 틱 비율·발효 상한

> 계기는 밤낮이 아니라 "세계가 고요하다"는 피드백이었다. 시계에 매달린 세계 시스템
> (Incident 압력·NPC agenda 문턱)이 2차 재설계 이후의 느린 시계를 전제로 재조정된 적이
> 없다는 것이 실측으로 드러났다. 세계 쪽 정본은 [[21_living_world_redesign|living world]] Part 11.

### 실측 (30일 · 런 159 / 10턴 이상)

- 실효 시계 **0.39 tick/턴** — 17턴 런이 6.9 tick (12 tick = 1일)
- **day 평균 1.10** · 158런 중 144런(91%)이 day 1 에서 종료 · 최대 3
- 적립분(`dialogueTickAccrual`)이 **평균 3.90 잠긴 채** 런 종료, 최대 8
  → 임계 6 이 런 길이 대비 너무 커서 한 런에 1회 남짓만 발효됐다
- Incident 압력 333건 평균 12.6 · 63%가 ≤10 정체 (`pressurePerTick` 2~3 은
  2차 재설계 이전 ≈1 tick/턴 기준으로 저작된 값)

### 변경

- `DIALOGUE_TICK_ACCRUAL_TURNS` **6 → 2**
- `DIALOGUE_TICK_DISCHARGE_CAP` **2 신설** — 비율만 낮추면 적립이 한꺼번에 터져
  (실측 최대 적립 8 → 4tick) 3tick = 1시간대인 구조상 해가 두 단계 건너뛴다.
  2차 재설계가 없앤 급전환이 비대화 턴으로 자리만 옮기는 꼴이라 상한을 함께 둔다.
  기본 비용 + 상한 ≤ 3tick = 1시간대 이내로 묶인다.
- 행동 턴(`preStepTick` 경로)과 이동 턴(`advanceClockForTravel`)에 **복제돼 있던 규칙을
  `settleDialogueAccrual` 하나로 통합**. 이동 경로가 `accrual % N` 으로 상한 초과분을
  **버리던 것**도 함께 해소(이월).

불변식 49 무손상 — 발효 시점은 여전히 비대화·이동 턴뿐이다.

### 검증 (15턴 chatty 실런 — 대화 비중 최대가 최악 조건)

- 시간대 전환은 조사 턴·이동 구간에서만. **대화 턴 8회(TALK/PERSUADE) 중 전환 0건.**
- 실효 시계 0.39 → **0.43 tick/턴**. 예상(≈0.64)에 못 미쳤다 — 단일 런이라 비율을
  주장할 표본이 아니고, 세계 쪽 결과 지표는 문턱 재기준화로 달성됐다.
  **시계 자체의 개선폭은 며칠 누적 후 재측정이 필요하다.**
- 유닛 1,909 passed (time-cost 신규 8케이스 — 상한·이월·1시간대 상한 계약 고정).
