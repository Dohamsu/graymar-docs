# 93. 장소 배경 지속화 (Location Backdrop)

**상태**: ✅ 구현됨 (2026-07-27) — 클라이언트 단독
**관련**: [[80_pack_asset_pool]] (팩 에셋 풀) · [[63_multi_scenario_content_decoupling]] ⑥ (팩별 이미지 커버리지) · [[86_pack_parity_mobile_ux]] (모바일 스크롤 `min-h-0`)

---

## 1. 문제 — 대화 흐름 중 장면 시각의 공백

이미지 채널은 5개인데, 대화가 이어지는 동안 살아 있는 것은 인물 초상화뿐이다.

| 채널 | 앵커 | 발생률 (2,117턴 실측) | 상태 |
|---|---|---|---|
| DialogueBubble 초상화 | `@[이름\|URL]` 마커 | 대사마다 | 가동 |
| NpcPortraitCard | `ui.npcPortrait` (첫 만남·이름 공개) | 158턴 / 7.5% | 가동 |
| locationImage | `LOCATION_ENTER` 이벤트 | 260턴 / 12.3% | 가동 (1회 소비 후 소멸) |
| SceneImageButton (Gemini) | 유저 클릭 | 0 | 봉인 (`scene-image.service.ts` `IMAGE_GENERATION_DISABLED`) |
| 팩 에셋 풀 (arch/80) | 자동 매칭 | — | 인프라 |

장면 이미지(장소 진입 + NPC 카드)가 한 번도 뜨지 않는 연속 턴 구간을 측정하면:

```
중앙값 3턴 · p90 6턴 · 최장 23턴   (532개 구간)
```

장소에 들어가 대화를 시작하면 평균 3턴, 나쁘면 6턴 이상 화면에 장면이 없다.
**부족한 것은 인물이 아니라 장면**이다.

### 앵커 후보 빈도 (같은 표본)

| 앵커 | 발생률 | 12~15턴 런 환산 |
|---|---|---|
| QUEST 이벤트 | 15.7% | 2회 |
| 크리티컬(주사위 6) | 5.1% | 0.7회 |
| 장비 획득 | 2.2% | 0.3회 |
| fact 발견 (`questReveal`) | 1.7% | 0.2회 |
| posture 전환 | 1.5% | 0.2회 |
| 전투 진입 | 1.2% | 0.2회 |
| INCIDENT_RESOLVED | 0% | 0 |

전환점 삽화(§6 후속)는 희소성이 곧 임팩트지만, 위 공백을 메우지는 못한다.
공백은 **지속**으로만 메워진다.

---

## 2. 채택안 — 배경 레이어

서술 패널 뒤에 현재 장소 이미지를 옅게 깔고, 장소·시간대가 바뀔 때만 교체한다.

| 항목 | 배경 레이어 (채택) | 헤더 밴드 (기각) |
|---|---|---|
| 세로 공간 | 0 | 180~300px |
| 대화 중 지속 | 유지 | 유지 |
| 가독성 리스크 | 있음 → 알파·스크림으로 통제 | 없음 |
| 신규 에셋 | 0 | 0 |

밴드 기각 이유: 모바일 뷰포트의 약 25%를 서술에서 빼앗아 arch/86에서 확보한
서술 영역을 되돌린다. orphan이던 `components/location/LocationImage.tsx`(90줄,
어디서도 import되지 않음)가 밴드 형태였고, **크로스페이드 로직만 이식한 뒤 삭제**했다.

---

## 3. 부작용 격리 — 이 기능이 서술을 건드리지 않는 이유

1. **서버 0줄 · LLM 0줄 · 프롬프트 0줄.** 앵커는 `ui.worldState`의
   `currentLocationId` / `phaseV2` / `timePhase` / `hubSafety`뿐이다.
2. **하드 상태 앵커.** 서술 내용에 의존하지 않으므로
   `llm-worker.service.ts`의 `reconcileSpeakingNpcAndPortrait`(약 200줄, 실측 결함으로
   3차례 위치 이동)처럼 "서술 최종본과 대조해 교체/제거"하는 정합 로직이 필요 없다.
   이미지 앵커를 소프트 상태에 걸면 그 복잡도를 그대로 물려받는다.
3. **텍스트 옆, 텍스트 안이 아님.** URL이 서술 문자열에 들어가지 않는다
   (`narrative-text.tsx`의 `/npc-portraits/` 누출 제거 필터가 그 전례).
4. **네트워크 추가 없음.** 진입 턴 인라인 이미지와 같은 URL·같은 `sizes`를 써서
   최적화 변형 캐시에 적중한다.

검증도 그만큼 가볍다 — 서버 파이프라인 무변경이므로 playtest 게이트가 필요 없고,
클라 빌드 + 헤드리스 시각 확인으로 충분하다.

---

## 4. 구현

### 4.1 신규 — `client/src/components/location/LocationBackdrop.tsx`

- `useGameStore` 셀렉터 **안에서** `getLocationImagePath()`까지 파생한다.
  `worldState` 객체는 매 턴 새로 갱신되지만 경로 문자열이 같으면 리렌더가 없다.
- 크로스페이드: 현재/다음 2레이어. 경로 변경은 **렌더 중에 반영**하고
  (effect 경유 시 한 프레임 늦다), 페이드 완료 승격만 effect + `clearTimeout`.
- 이미지가 없으면 `null` 반환 — 타 팩 이미지 fallback 금지(세계관 오염, arch/63 ⑥).
- 상수 3개: `BACKDROP_OPACITY = 0.3` · `CROSSFADE_MS = 600` · `SIZES`.

### 4.2 stacking context — `isolation: isolate` 필수

배경은 `absolute inset-0 -z-10`이다. 음수 z-index는 **가장 가까운 stacking context**
기준으로 해석되므로, 부모가 stacking context를 만들지 않으면 부모의
`bg-[var(--bg-primary)]` **뒤로** 밀려 완전히 가려진다 (실측 확인: DOM·이미지·opacity가
모두 정상인데 화면에 아무것도 안 보임).

`position: relative` + `z-index: auto`는 stacking context를 만들지 않는다.
따라서 두 삽입 지점의 컨테이너에 `isolation: isolate`를 준다.

> **Tailwind `isolate` 클래스는 쓰지 않는다.** 이 프로젝트의 Tailwind v4 빌드에서
> `.isolate` 규칙이 생성되지 않아 `isolation`이 `auto`로 남는 것을 실측했다
> (클래스는 DOM에 붙지만 computed style은 `auto`). 인라인
> `style={{ isolation: "isolate" }}`로 고정한다.

### 4.3 서술 카드 반투명화

`StoryBlock`의 모든 메시지 카드가 불투명(`--bg-card` / `--bg-secondary`)이라
배경이 카드 사이 여백에만 보였다. 반투명 토큰을 신설해 카드 너머로 비치게 한다.

```css
--bg-card-translucent: rgba(20, 20, 20, 0.75);
--bg-secondary-translucent: rgba(10, 10, 10, 0.78);
```

`StoryBlock` 전용이다. 원본 토큰은 사이드패널·버튼 등 다른 소비처가 그대로 쓴다.
배경이 없는 팩·화면에서는 `--bg-primary` 위에 얹혀 불투명 원본과 육안 차이가 없다.

**농도 계산**: 카드 알파 0.75 → 본문 뒤 실효 배경 농도는 `BACKDROP_OPACITY`의 약 1/4
(≈0.075). 카드 사이 여백에서는 0.3 그대로 보인다. 최악(이미지 흰 영역) 대비:
`--text-primary` 약 14.6:1(문제없음), `--text-muted`는 3.29:1 → 2.67:1로 하락.
muted는 라벨·힌트 등 장식 텍스트에만 쓰여 수용 가능하나, 농도 조정 시 이 값이 기준선이다.

### 4.4 삽입 지점 (2곳)

| 위치 | 컨테이너 |
|---|---|
| 데스크톱 | `GameClient.tsx` 좌측 서술 컬럼 |
| 모바일 | `GameClient.tsx` `mobileTab === "story"` 래퍼 (신규 div) |

⚠️ 모바일 래퍼는 `flex min-h-0 flex-1 flex-col`을 반드시 유지한다.
빠뜨리면 arch/86에서 고친 "서술 스크롤 overflow 무력화"가 재발한다.

적용 범위: `phase === "LOCATION" || phase === "HUB"`.
COMBAT은 BattlePanel이 시각을 점유하므로 제외.

---

## 5. 검증 (2026-07-27, 헤드리스 + 실런 e0804e83)

| 항목 | 결과 |
|---|---|
| 데스크톱(1440×900) 배경 렌더 | ✅ `guard_day_safe.webp`, opacity 0.3 |
| 앵커 정합 | ✅ 서버 `currentLocationId=LOC_GUARD`/DAY/SAFE ↔ 배경 이미지 일치 |
| 카드 반투명 | ✅ computed `rgba(20, 20, 20, 0.75)` |
| stacking context | ✅ computed `isolation: isolate` |
| 모바일(390×844) 스크롤 | ✅ `scrollHeight 5343 > clientHeight 677`, `overflow-y: auto`, scrollTop 이동 정상 |
| 이미지 없는 팩 | ✅ `getLocationImagePath` null → 컴포넌트 `null` 반환 (DOM 미생성) |
| lint / build | ✅ 0 / 성공 |

---

## 6. 잔여 · 후속

- **스크롤 시 과거 장소**: 배경은 "지금 여기" 고정이라, 위로 스크롤해 이전 장소의
  대화를 읽어도 배경은 현재 장소다. 수용된 트레이드오프.
- **팩 커버리지 격차**: graymar 13장 · star_sand 8장 · karnholt 28장(풀) · **silverdeen 0장**.
  실버딘은 배경이 뜨지 않는 것이 정상 동작이며, 개선하려면 에셋 확보가 선행 조건이다.
- **농도 토글**: `settings-store`에 on/off를 추가하는 안은 실물 확인 후로 보류.
  현재는 `BACKDROP_OPACITY` 상수 1곳으로 조정한다.
- **전환점 삽화 (§1 앵커표)**: fact 발견·posture 전환·questState 전환·아크 커밋·엔딩 등
  하드 앵커에 `ui.sceneMoment`를 신설하는 후속. 본 문서 §3 원칙을 그대로 따른다.

---

## 7. 후속 — 장소 라벨 정본화 (2026-07-27, 같은 작업분)

§6 별건으로 발견한 헤더 라벨 오류를 이어서 해소했다. 원인은 하나가 아니라 둘이었다.

### 7.1 결함 A — 복원 시 기본 라벨로 떨어짐

`game-store`의 `locationName`은 **노드 전이 시점에만** 세팅되어, 이어하기 후에는 `null` →
`scenarioLabels.fallbackLocation`으로 표시됐다. 실측: `currentLocationId = LOC_GUARD`
(경비대 지구)인데 헤더는 "그레이마르 항만"(graymar 기본 라벨).

**수정**: `GET /v1/runs/:runId` 응답에 `currentLocationName`을 추가한다
(`runs.service.ts` — `runState.worldState.currentLocationId` → `content.getLocation().name`).
`enterScenario`는 같은 메서드 상단에서 이미 호출되므로 팩 스코프가 보장된다.
`npcEmotional`·`questStatus`와 동일한 "복원 갭 메우기" 패턴이다.

### 7.2 결함 B — 플레이 중에는 서술 문장이 라벨

전이 경로는 `enterResult.summary.display`를 라벨로 썼는데, 그 값은
`` `${locationName}에 도착했다.` `` — 메시지 피드용 문장이지 라벨이 아니다.
복원만 고치면 복원("경비대 지구")과 플레이("경비대 지구에 도착했다.")가 어긋난다.

**수정**: `WorldStateUI.currentLocationName`(선택 필드) 신설.
LOCATION 진입 2곳(`transitionToLocation`, `returnFromCombat`)에서 채우고,
클라 전이 핸들러가 이 값을 우선 사용한다 (`summary.display`는 구 런 fallback으로만 유지).
HUB 진입은 `currentLocationId`가 null이므로 이름도 null이 정상.

### 7.3 함정 — 복원 경로가 3벌이다

`game-store.ts`에 `locationName: null`을 세팅하는 블록이 2곳 더 있지만,
**이어하기가 실제로 타는 경로는 `game-store.helpers.ts`의 `applyRunSnapshot`**이다
(`resumeRun` → `applyRunSnapshot`). 앞의 두 곳만 고치면 화면은 그대로다 — 실측으로 한 번
헛짚었다. 복원 계열 상태를 만질 때는 `applyRunSnapshot`을 먼저 확인할 것.

또한 **Next dev HMR이 store 모듈 변경을 반영하지 않는 경우가 있다.** 코드·API 응답이
모두 정상인데 화면만 옛 값이면 dev 서버를 재시작한다
(`lsof -ti:3001 | xargs kill -9` → `pnpm dev --port 3001`. `pnpm dev -- --port`는
`--`가 next에 그대로 전달되어 "Invalid project directory" 로 실패한다).

### 7.4 검증 (실런 e0804e83)

| 경로 | 결과 |
|---|---|
| 복원(이어하기) — LOCATION 체류 | ✅ 헤더 "경비대 지구" (기존: "그레이마르 항만") |
| 복원 — API 필드 | ✅ `currentLocationName: "경비대 지구"` |
| 플레이 — 거점 복귀 | ✅ 헤더 "그레이마르 거점" (hubName) |
| 플레이 — 장소 이동(항만 부두) | ✅ 헤더 "항만 부두" (기존: "…에 도착했다.") |
| 배경 동시 전환 | ✅ `guard_day_safe` → `harbor_day_safe` 크로스페이드 |
| server build/lint · client build/lint | ✅ |

### 7.5 잔여

파티 복원 경로(`resumePartyRun` → `getPartyRunState`, arch/84)는 별도 엔드포인트라
같은 갭이 남아 있을 수 있다. 미확인.
