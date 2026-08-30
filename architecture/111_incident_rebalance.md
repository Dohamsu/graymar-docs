# 111. Incident 재기준화 — 만성 저활성 해소 (2026-08-30)

## 0. 발견 경위

arch/110 6차 데이터 런에서 D4-3b "떡밥 과적" 경고가 4런 연속 발화 → 30일 전수
조사로 실체 규명: 과적이 아니라 **배수구가 막힌 것**이었다.

## 1. 실측 (30일, 554개 사건)

| 지표 | 값 |
|------|-----|
| 해소 outcome | **CONTAINED 24 / ESCALATED 0 / EXPIRED 0** (해소율 4.3%) |
| 사건당 생존 중 tick | 평균 1.7 (pressure 3/tick → 평균 pressure ~5, 임계 95) |
| 플레이어 개입 0회 사건 | 59% (미해소 사건 평균 control 16.8 — 시작값 ~20) |

## 2. 근본 원인

**시간 상수가 구세계 기준.** 저작값(pressure 95 도달 = 32 tick, deadline 48
tick)은 시간이 상시 흐르는 구설계 기준. arch/81 밤낮 재설계로 대화 timeCost=0
(불변식 49)이 되며 시계 실효가 **0.4 tick/턴**으로 떨어졌는데 incident 상수는
재기준화를 안 거쳤다 — ESCALATED ~80턴, EXPIRED ~120턴 = 평균 런(15턴)에서
수학적으로 도달 불가. **arch/21 Part 11 "아젠다 스테이지 전부 day≥2 vs 91%
런이 day 1 종료"와 정확히 같은 부류** (그때 아젠다는 고쳤으나 incident 누락).

부차: 시그널 템플릿 트리거(triggerPressure 60~85)도 같은 이유로 도달 불능
(arch/21 잔여 "14/55 도달 불능"의 원인 동일). CONTAINED 경로는 살아 있으나
3중 마찰(사건 장소 × affordance 매칭 × SUCCESS 4~6회) — 이번 범위 밖, 관측 후 판단.

## 3. 처방 (A안 — 임계 재기준화 + 해소 시그널)

### 3-1. 콘텐츠 재기준화 (graymar 13 + star_sand 10, 스테이지 80건)

- `pressurePerTick` = clamp(round(구값 × 2.2), 6, 13)
- `deadlineTicks` = clamp(round(구값 × 0.4), 16, 24)
- 임계(95/80)와 0~100 스케일은 불변 — 상승 속도만 시계 실효에 맞춤

검산 (방치 시나리오, stage0 고정 — 방치 사건은 control 50 미달로 stage 가
오르지 않으므로 stage0 값이 지배):

| 도달 | 재기준화 전 | 후 |
|------|------------|-----|
| ESCALATED (pressure 95) | 24~48 tick = 60~120턴 | **9~16 tick = 22~40턴** |
| EXPIRED (deadline) | 24~60 tick = 60~150턴 | **16~24 tick = 40~60턴** |
| 시그널 트리거 60~85 | 도달 불능 | pressure 60 ≈ 9 tick ≈ 20~25턴 |

의도: 평균 런(15턴)에서는 안 터지고(소음 방지), 긴 런·방치 사건에서 터진다.
온건한 첫 기준 — 관측 런으로 조정(콘텐츠 값이라 재조정 비용 낮음).

### 3-2. 해소 순간 시그널 (world-tick)

ESCALATED/EXPIRED 는 30일간 0건이라 **한 번도 실행된 적 없는 경로** — 발동해도
유저 인지 수단이 Heat 수치 급등뿐이었다. preStepTick 에서 이번 tick 에 resolved
로 전환된 사건마다 소문 시그널 적재 (문구는 세계관 중립 + `def.title` 참조 —
불변식 45):

- ESCALATED: severity 5, "'{title}' 사태가 걷잡을 수 없이 번졌다는 소식이 돈다"
- EXPIRED: severity 2, "'{title}' 소동이 흐지부지 잊혀 간다는 말이 돈다"
- CONTAINED: severity 3, "'{title}' 소동이 가라앉았다는 말이 돈다"

스펙 4 (`world-tick.incident-resolution.spec.ts`) — ESCALATED/EXPIRED 발동·
멱등·미해소 무시그널.

### 3-3. 재발 방지 — audit_content INCIDENT_PACING (L2)

stage0 `pressurePerTick < 6` / `deadlineTicks > 30` 을 WARN — 새 incident 저작이
같은 함정(시간 상수 재기준화 누락)에 빠지는 것을 모양 검사로 차단.

## 4. 기각·보류

- **B안 (턴 기반 압력 보조 소스)**: 대화 위주 플레이어는 tick 자체가 안 돌아
  A의 한계가 남는다. "사건 장소 미방문 N턴마다 pressure 부스트"가 후보이나
  불변식 49("대화 중 세계 시간 정지") 철학과의 경계 논의가 필요 — **소유자
  결정 대기**. A 관측 후 효과 부족 시 재론.
- **CONTAINED 마찰 완화** (controlThreshold 80→70 등): 개입이 물리면 진행은
  된다(STAGE_ADVANCE 106건) — A 효과 관측 후 판단.

## 5. 검증 계획

- 배포 후 20턴+ 런: pressure 진행 곡선(턴당 ~2.8 상승 기대), 시그널 템플릿
  발화 여부, (긴 런에서) ESCALATED 발동 + 해소 시그널 서술 반영
- 30일 후 재조사: 해소율 4.3% → 목표 20%+ (CONTAINED 포함), ESCALATED > 0
