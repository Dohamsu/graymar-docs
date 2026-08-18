# 103 — 아크 종반부 3막: 스테이지 배선 + 피날레 선택지 + 엔딩 안전망 HUB 확장 (2026-08-18)

버그 리포트 `3c501bf7`(08-16, graymar 턴 35) 분석에서 출발. 유저가 S5에서
`arc_commit_ally_guard`를 클릭한 88초 뒤 "결론이 어떻게 난건지, 이후 어떻게
게임이 끝나는건지 모르겠다"며 이탈했다. 소유자 문답 설계(7결정)로 확정한 종반부 재설계.

관련: [[architecture/88_endgame_arc_commit_encounter_fix|arc 커밋 동선]] ·
[[architecture/39_ending_journey_archive|엔딩 연출]] ·
[[architecture/68_uiux_audit_v1|arc 커밋 부록 F]] · [[architecture/101_selfcheck_loop|자기점검]]

## 1. 근본 원인 3층 (분석 확정)

1. **S5+5 안전망 타이머가 HUB에서 정지** — Part B(S5 체류 5턴 → incident 강제
   CONTAINED → ALL_RESOLVED 엔딩)와 `checkEndingConditions` 호출이 모두
   `handleLocationTurnInner` 전용. 커밋 선택지는 HUB에만 뜨므로 **커밋 직후의
   유저는 반드시 타이머가 멈춘 공간에 서 있다**. 해당 런: S5 진입 턴 30, 커밋 턴
   35 — 정확히 타이머 발화 시점이었으나 HUB 턴이라 미실행.
2. **커밋 후 안내 공백** — 커밋 전 유도 힌트(arch/88)는 있으나 커밋 후에는
   `nextObjectives=[]`, 힌트 없음, 분위기 서술만. "최종 선택" 문구로 유도해 놓고
   선택 후 침묵.
3. **아크 스테이지 이벤트 사문** — `getArcEvents()` 소비처 0곳 (2026-02-18 도입
   이래). graymar `arc_events.json`의 3루트×3스테이지 9종("대위의 부탁"→"내부의
   적"→"정의의 칼날" 등)이 저작만 되고 영구 발화 불능. arch/101이 추적하는
   "조용히 꺼진 배선" 부류.

## 2. 확정 설계 (소유자 문답 7결정, 2026-08-18)

| # | 결정 | 확정안 |
|---|------|--------|
| 1 | 발화 시점 | **커밋 후 전용** — 커밋 → 루트 전용 3막 → 엔딩. 커밋 전 퀘스트 흐름(NPC fact 공개)과 분리 |
| 2 | 진행 방식 | **판정형** — 스테이지 장소에서 비사교 행동 판정 SUCCESS/PARTIAL이면 완료, FAIL 재시도 |
| 3 | FAIL 구제 | 같은 스테이지 FAIL 2회 누적 → 3회차 시도는 **자동 PARTIAL 보정** (판정 최저 보장) |
| 4 | 요구조건 | **순차 완료만 강제** — requiredFacts·minReputation 게이트 폐기 (커밋=자격, 미보유 fact는 보상으로 자연 획득) |
| 5 | 엔딩 진입 | stage 3 완료 → **"결말을 맞이한다" 명시 선택지** → 클릭 시 엔딩 (즉시 종료 금지 — 예고 없는 상태 변화가 이번 리포트의 혼란 원인) |
| 6 | 결말 선택지 | **상시 유지** — finaleReady 후 매 턴(HUB·LOCATION 공통) 노출. 유예 허용, 종결권은 항상 손에 |
| 7 | 안전망 | S5+5 타이머 **유지 + HUB 배선** — 스테이지를 안 따라가도 엔딩 보장. 스테이지 없는 팩(star_sand 등)은 이 경로가 유일하므로 필수 |

## 3. 구현 설계

### 3.1 상태 모델 — `ArcState.stageProgress` (신규 optional)

```ts
export type ArcStageProgress = {
  completedStages: number[];            // 완료 스테이지 번호 (오름차순)
  failCounts: Record<string, number>;   // stage 번호 → FAIL 누적 (jsonb 키는 string)
  finaleReady: boolean;                 // 최종 스테이지 완료 → 결말 선택지 상시 노출
};
```

`arc_commit_*` 처리 시 `stageProgress` 초기화. 스테이지가 없는 팩(빈
`getArcEvents(route)`)은 커밋 즉시 `finaleReady=false` 유지 + 타이머 경로.

### 3.2 스테이지 발화·완료 (LOCATION 전용 오버레이)

이벤트 파이프라인(EventDefV2 변환·EventDirector 주입)이 **아니라** 전용
오버레이로 처리한다 — EventChoiceGate·NpcResolver·대화 잠금과의 상호작용 부작용을
원천 회피 (매칭 파이프라인 무변경).

- **활성 판정**: `arcState.currentRoute` 존재 && 다음 스테이지(미완료 최소
  stage)의 `locationId == 현재 장소` && 이번 행동이 비사교(사교 발화·REST 제외).
- **판정 강제**: 스테이지 활성 턴은 ChallengeClassifier FREE 스킵을 무시하고
  **항상 CHECK** — 잡담 자동 SUCCESS로 스테이지가 공짜 완료되는 구멍 차단.
- **완료**: 그 턴 resolve outcome이 SUCCESS/PARTIAL(또는 FAIL 2회 후 자동
  PARTIAL 보정)이면 완료 처리:
  - rewards 지급 — gold→goldDelta, items→인벤토리(기존 지급 경로),
    facts→`discoveredQuestFacts`(+questReveal 주입, 중복 무시),
    reputationChanges→`ws.reputation`.
  - events에 `[아크] <title> — 완료` (kind QUEST, tags [ARC_STAGE, route]).
  - `pendingQuestHint` = `nextStageCondition` (다음 무대 안내).
- **발화 서술**: 활성 스테이지의 title·description을 LLM 프롬프트 디렉티브
  `[아크 스테이지]`로 주입 (커밋 후 한정이라 토큰 예산 영향 미미).

### 3.3 피날레 — "결말을 맞이한다"

- stage 3(루트 최종) 완료 → `finaleReady=true`.
- 선택지 노출: HUB는 `buildHubChoices` 선두, LOCATION은 finalChoices 확정 지점
  (`buildNanoChoiceItemsCore` 이후 단일 지점)에 고정 삽입. `choiceId: arc_finale`.
- 클릭 처리(HUB·LOCATION 공통): 미해결 incident 전부 `CONTAINED` 마킹(기존
  Part B 수법 재사용) → 그 턴 `checkEndingConditions`가 ALL_RESOLVED로 발화 →
  `finalizeRunEnding` (arcRouteEndings 12분기·[마지막 장면] 디렉티브 기존 재사용).
  신규 엔딩 reason 없음 — 엔진 표면 무증가.

### 3.4 안전망 HUB 배선

- Part B 타이머(S5+5 → incident 마킹)를 순수 코어 `applyS5EndgameTimerCore`
  (turns/arc-stage.core.ts)로 추출 — LOCATION(processQuestProgression)과 HUB
  (submitTurn pre-dispatch, AUTONOMOUS 팩 제외)가 동일 로직 공유.
- **구현 조정**: HUB에서는 자동 엔딩을 실행하지 않는다 — 타이머 성숙 시
  incident 마킹 + (커밋 런이면) `finaleReady=true`로 **결말 선택지를 노출**하고,
  종결은 클릭으로만 일어난다. 결정 5(예고 없는 종료 금지)·6(종결권 상시 노출)과
  정합 — 유저가 클릭한 다른 HUB 선택을 엔딩이 가로채지 않는다. LOCATION의
  기존 자동 ALL_RESOLVED 경로(무커밋 런 포함)는 그대로 유지 (회귀 0).
- 결말 선택지(`arc_finale`) 클릭은 노드 타입 무관 단일 분기
  (`handleArcFinaleTurn`, submitTurn pre-dispatch)에서 처리: incident 일괄
  CONTAINED → 기존 `finalizeRunEnding`(reason=ALL_RESOLVED) 직행.
- **불변식 19 예외 (개정)**: "ALL_RESOLVED ≥ 15턴" 가드는 **자동 발동**(타이머·
  incident 자연 해소)에만 적용한다. 명시 결말 선택(arc_finale)은 커밋+스테이지
  완주라는 능동 조건을 거친 종결이므로 최소 턴 가드 대상이 아니다 (조기 엔딩
  방지라는 원 취지와 충돌하지 않음). selfcheck #19 디텍터 판정 시 ARC_FINALE
  이벤트 보유 런은 분모에서 제외할 것.

### 3.5 안내(UX) 봉합

- **커밋 턴**: `pendingQuestHint` = "<stage1.title>이(가) <장소명>에서 기다린다"
  (스테이지 팩) / "거리에서 시간을 보내면 결말이 찾아온다" (무스테이지 팩).
- **questStatus.nextObjectives**: 커밋 후 = 다음 스테이지 `{title, 장소}`,
  finaleReady 후 = "결말을 맞이할 수 있다". 빈 배열 금지.
- 커밋 턴 LLM 프롬프트에 결말 방향 암시 디렉티브 1줄.

## 4. 팩 계약 (arch/88 계약 확장)

- `arc_events.json` 루트 배열(스테이지)은 **선택** 자산. 있으면 3막 경로가 정본,
  없으면(star_sand·silverdeen·karnholt) 커밋 후 안내 문구 + S5+5 타이머 경로.
- 스테이지 배열 저작 시: `stage`(1부터 연속)·`locationId`(실존)·`title`·
  `description`·`rewards`·`nextStageCondition` 필수. requirements는 참고용
  (커밋 후 경로에서 게이트로 쓰지 않음).

## 5. 검증 (2026-08-18 구현 완료)

- 단위: `arc-stage.core.spec.ts` 18케이스 (순차·FAIL 구제·finaleReady·타이머
  성숙/미성숙/무커밋) — 전체 스위트 1,988 통과, 스냅샷 변화 0.
- E2E (skipLlm, DB 시드로 S5 단축): **전 항목 PASS** —
  - 커밋 턴: ARC_COMMIT 이벤트 + directionHint "대위의 부탁 — 경비대에서…" +
    nextObjectives 비공백 + stageProgress 초기화.
  - 스테이지: 도달 턴 ARC_STAGE_INTRO 1회 발화, FREE 스킵 0(항상 판정),
    실제 FAIL 재시도 후 완수(failCounts {"1":1,"2":1}), 3막 완주 → finaleReady.
  - 보상: 골드·ITEM_GUARD_PERMIT·CLUE 지급, CITY_GUARD 평판 +50 반영.
  - 피날레: arc_finale 선택지 선두 노출 → 클릭 → RUN_ENDED +
    `finale.arcRoute=ALLY_GUARD`(arcTitle "질서의 수호자", STABLE) 엔딩 요약 저장.
  - HUB 타이머: S5+5 성숙 HUB 턴에서 incident 전부 마킹 + arc_finale 노출 +
    HUB에서의 피날레 클릭 → RUN_ENDED.
- 일반 플로우 스모크(LLM 3턴) PASS — 기존 경로 회귀 없음.
- 구현 중 잡은 결함: 스테이지 진행을 `updatedRunState.arcState`에 쓰면
  이후 "RunState 반영"의 `arcState = newArcState` 대입이 덮어써 **매 턴 진행이
  유실**된다 (E2E 실측). 갱신은 반드시 `newArcState` 경유 — 코드 주석에 명시.
- 잔여: 실LLM 플레이테스트에서 스테이지 이벤트 서술 품질([이번 턴 사건] 경유)
  확인 1런 — 후속.
