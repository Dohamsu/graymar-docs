# 81 — 밤낮 시스템 재설계 (2026-07-20)

> 상태: ✅ 구현·배포. server `3f219f0`+`644af71`, client `4406aaa`.
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
