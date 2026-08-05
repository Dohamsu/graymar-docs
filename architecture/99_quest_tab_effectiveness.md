# 99. 퀘스트탭 실효성 개선

> 2026-08-05 · 상태: ✅ 구현됨 (빌드·유닛 검증 통과, 미커밋)
> 선행 조사: 퀘스트탭 전수 점검 (본 문서 §1) · 관련: arch/58(단서 단일화), arch/68 부록(현황판 신설 2026-07-23), arch/75(AUTONOMOUS 종결 축), arch/88(arc 커밋 동선)

## 1. 조사 결론 (2026-08-05)

퀘스트탭 데이터 연결 전수 점검 결과:

**건강한 부분** — 의뢰 현황판(`buildQuestStatus`)은 questState·discoveredQuestFacts에서
단계/단서/이정표/방향 힌트를 조립하고, fact 발견(`processQuestProgression`)이 UI 조립
(`assembleResultUi`)보다 먼저 실행되어 같은 턴 반영이 보장된다. 복원 경로(createRun·getRun)도
재조립로직 완비. 3개 퀘스트 팩 facts 콘텐츠(description·discoveryLocations·nextHint) 전량 충실.

**결함 5건**:

| # | 결함 | 근거 |
|---|------|------|
| D1 | **"활성 목표" 섹션 = 죽은 기능.** `addExplicitGoal`/`completeGoal` 호출처 0건 — EXPLICIT 목표·마일스톤 UI는 도달 불능 데드코드. 실생성되는 IMPLICIT 목표는 progress 동결(`min(count×15,60)`)·완료 경로 없음·영구 활성. "행동 패턴"(playerThreads)과 정보 중복 | player-goal.service.ts 전수 grep |
| D2 | **HUB 턴에 quest UI 번들 미부착.** arcState·mainArcClock·day·questStatus는 LOCATION 턴 `assembleResultUi`에서만 실림. 정작 노선 확정(`arc_commit_*`)은 HUB에서 일어나 커밋 직후 ~다음 LOCATION 행동까지 탭이 스테일 | turns.service handleHubTurn |
| D3 | **"현재 상황" 요약 = 하위 섹션 완전 중복** (노선·시한·사건 수·목표) | QuestTab.tsx |
| D4 | **팩 격차.** karnholt(AUTONOMOUS): quest.json·arcRoutes 부재 → 노선 "미정" 영구 표시 + 엔진 디폴트 시한 D-14 노출(AUTONOMOUS는 종결 축이 규명율로 대체되어 시한 무의미 — turns.service:6388 `shouldEnd` 오버라이드 확인). silverdeen: routeCommitChoices 부재(팩 계약) → 노선 채워질 경로 없음 | content 팩 대조 |
| D5 | **발견성.** 단서 발견·단계 전환 시 퀘스트 탭 유도 배지 없음 (배지는 소지품 탭 전용) | SidePanel.tsx |

## 2. 개선 설계

### P1 — 서버: HUB 턴 quest UI 부착 + hasArcCommit (D2·D4)

- `attachQuestUiBundle(result, runState, ws)` 헬퍼 신설: playerThreads·arcState·
  narrativeMarks·mainArcClock·day·questStatus 부착 (기존 assembleResultUi 내 블록 추출).
- 호출 지점: `assembleResultUi`(기존 유지) + HUB 턴 4경로 — `arc_commit_*`(핵심),
  `accept_quest`, `contact_ally`/`pay_cost`(buildHubActionResult 내부), 장소 이동
  (day 변동 반영).
- `QuestStatusUI.hasArcCommit: boolean` 신설 — `getArcRouteCommitChoices().length > 0`.
  클라 노선 섹션 게이팅 신호 (silverdeen처럼 커밋 동선 없는 팩에서 "미정" 영구 노출 방지).

### P2 — 클라: 죽은 섹션 제거 + 팩 게이팅 (D1·D3·D4)

- **"활성 목표" 섹션 제거** (엔진 playerGoals는 LLM 컨텍스트 등 다른 소비처가 있어 유지 —
  UI만 정리). **"현재 상황" 요약 섹션 제거** (중복).
- **노선 섹션 게이팅**: `currentRoute` 있으면 표시 / 없으면 `hasArcCommit`일 때만
  "미정" 카드 / 그 외 섹션 숨김.
- **시한 섹션 게이팅**: `questStatus` 있는 팩(AUTHORED)만 표시. AUTONOMOUS는 시한
  엔딩이 규명율로 대체되므로 D-14 표시는 오정보.
- 남는 구성: 의뢰 → 노선 → 세력 관계 → 시한 → 진행 중 사건 → 정체성 → 행동 패턴 (7→9섹션에서 축소).

### P3 — 클라: 퀘스트 탭 배지 (D5)

- `game-store.questTabBadge` — `applyServerResultUi`에서 discoveredFacts 증가 또는
  stateIndex 전진 감지 시 true. 탭 열람 시 해제.
- 데스크톱 SidePanel "퀘스트" 탭 + 모바일 햄버거 버튼·메뉴 항목에 점 배지.

### 범위 외 (기록)

- silverdeen arc_events.json 저작: 콘텐츠 저작 작업 — 팩 계약(커밋 선택지 없음)이
  현행 정본. 노선 섹션은 hasArcCommit 게이팅으로 숨겨 오정보만 제거.
- fact→EXPLICIT 목표 배선: 의뢰 현황판과 중복이라 채택 안 함. playerGoal 엔진 코드
  정리는 LLM 컨텍스트 소비처 검토가 선행되어야 해 별도 트랙.

## 3. 구현 기록 (2026-08-05)

### 서버 (P1)

| 파일 | 변경 |
|------|------|
| `db/types/server-result.ts` | `QuestStatusUI.hasArcCommit: boolean` 신설 |
| `engine/hub/quest-progression.service.ts` | `buildQuestStatus`가 `getArcRouteCommitChoices().length > 0`로 hasArcCommit 채움 |
| `turns/turns.service.ts` | `attachQuestUiBundle(result, runState, ws)` 헬퍼 추출 (기존 assembleResultUi 내 블록). 호출 지점 6곳: assembleResultUi(기존) + `buildHubActionResult` 내부(runState 전달 시 — arc_commit·contact_ally·pay_cost 3경로) + `accept_quest` + HUB 장소 이동(post-travel ws) |

주의: `buildHubActionResult`의 `runState` 파라미터는 optional — 넘기지 않는 미래 호출자는
기존 동작(번들 없음) 유지. 현 호출자 3곳은 전부 `updatedRunState` 전달.

### 클라이언트 (P2·P3)

| 파일 | 변경 |
|------|------|
| `types/game.ts` | `QuestStatusUI.hasArcCommit?` (구서버 호환 optional) |
| `components/side-panel/QuestTab.tsx` | "현재 상황" 요약·"활성 목표" 섹션 제거 (D1·D3). 노선 섹션: `currentRoute \|\| hasArcCommit` 게이팅. 시한 섹션: `questStatus && mainArcClock` 게이팅 (AUTONOMOUS 숨김). 레거시 goal 번역기(`localizeGoalDescription` 등) 제거, 스레드 번역기는 유지 |
| `store/game-store.ts` | `questTabBadge` 상태 + `clearQuestTabBadge` 액션 + reset 포함 |
| `store/game-store.helpers.ts` | `applyServerResultUi`에서 discoveredFacts 증가·stateIndex 전진 감지 시 배지 점등 (prevQs 존재 시에만 — 복원 직후 오점등 방지) |
| `components/side-panel/SidePanel.tsx` | "퀘스트" 탭 점 배지 (소지품 배지와 동일 룩), 탭 클릭 시 해제 |
| `components/layout/Header.tsx` | MobileHeader 햄버거 버튼 + 드롭다운 "퀘스트" 항목 점 배지 |
| `app/GameClient.tsx` | 모바일 quests 탭 진입 시 배지 해제 effect |

### 검증

- 서버 `pnpm build` ✅ / `jest --testPathPatterns="quest-progression"` 13 passed ✅ / `"turns"` 162 passed ✅
- 클라 `tsc --noEmit` ✅ / `pnpm build` ✅ / 변경 6파일 eslint 0건 ✅

### 잔여 확인 항목 (실런)

- arc_commit HUB 턴 응답에서 노선 섹션 즉시 갱신 (D2 핵심 시나리오) — 실플레이 확인 권장
- karnholt 런에서 노선·시한 섹션 미표시 + silverdeen 노선 섹션 미표시
- 단서 발견 턴 배지 점등 → 탭 열람 해제 (데스크톱·모바일)
