# 70. 캠페인 순차 진행 (한 캐릭터 · 이어달리기 · 되돌아가기 불가)

> 상태: ⚠️ 게이팅 정책 대체됨 — 순차 게이팅(§3.1~3.2, LOCKED/원점 정책)은 [[71_campaign_free_scenario_selection]] 자유 선택 모델로 교체 (2026-07-14). 캐리오버 엔진·완주/실패 시맨틱(§3.3)·활성 런 가드·폴백 제거는 유효.
> 이전 상태: ✅ 구현됨 (2026-07-14) — P1~P3 완료·API 실증 검증 · 검토 반영 v2(폴백 7곳 확장, 캐릭터 정체성 이월, 실패 시맨틱, 순번 산출식 통일)
> 관련: [[63_multi_scenario_content_decoupling]] (멀티 시나리오 디커플링), 캠페인 carry-over 골격

## 1. 목표 (사용자 의도)

**하나의 캐릭터로 여러 시나리오를 순차적으로 플레이한다.**

- 한 번에 **하나의 시나리오만** 진행 (동시 플레이 없음 — 단일 활성 시나리오 정책 유지)
- 시나리오를 완주하면 **다음 순번**으로 캐릭터가 이월된다
  - 수치: 스탯·골드·아이템·평판·NPC 관계
  - **정체성: characterName · gender · traitId · 초상화** — 캐릭터가 "같은 사람"이려면 수치만이 아니라 정체성 필드도 이월되어야 한다 (검토 반영: 기존 계획에 누락)
- **되돌아갈 수 없다** — 완주한 시나리오는 재진입 불가, 순번을 건너뛸 수도 없다

순서: graymar_v1(order 1) → silverdeen_v1(order 2) → star_sand_v1(order 3)

## 2. 현재 구현 상태 (실측)

캐리오버 엔진은 **약 75% 구현**되어 있으나, 진입 흐름에 하드코딩·게이팅 공백이 있다.

### 이미 되어 있는 것 ✅
| 영역 | 구현 |
|------|------|
| 캠페인 CRUD | `CampaignsService.createCampaign/getActiveCampaign/getCampaign`, `GET /v1/campaigns` |
| 캐리오버 상태 | `CarryOverState`(completedScenarios/gold/items/finalStats/statBonuses/reputation/npcCarryOver) |
| 런 종료 머지 | `turns.service.saveCampaignResultIfNeeded` → `campaigns.service.saveScenarioResult` → `mergeCarryOver` (RUN_ENDED 시 자동) |
| 이후 시나리오 스탯 | `runs.service.createRun`: `!isFirstScenario && carryOver` 이면 **프리셋 대신 이월 스탯** 사용 (프리셋 불필요) |
| 시나리오 순번 | scenario.json `order`(1/2/3) + `carryOverRules`(goldRate/itemsCarry/reputationDecay/statBonusPerScenario) |
| 클라 캠페인 UI | `StartScreen`: createCampaign / getActiveCampaign / getAvailableScenarios / CAMPAIGN_SCENARIO 화면 |

### 근본 문제 — `?? 'DOCKWORKER'` 폴백 리터럴 7곳 (진입 경로 3 + 표시·파티 경로 4)

진입을 깨는 3곳(P1)과, 이월 런(presetId null)에서 같은 오류 클래스를 재발시키는 4곳(P1'):

| 구분 | 위치 | 코드 | 영향 |
|------|------|------|------|
| 진입 | 서버 `runs.controller.ts:54` | `presetId ?? 'DOCKWORKER'` | 프리셋 누락 시 graymar 프리셋으로 폴백 → 비-graymar 팩에서 400 |
| 진입 | 클라 `StartScreen.tsx:1092` | `startCampaignRun(..., "DOCKWORKER", "male")` | order>1 시나리오에 DOCKWORKER **+ gender "male"** 강제 전송 |
| 진입 | 클라 `GameClient.tsx:376` | `presetId ?? "DOCKWORKER"` | 표시/전송 기본값 |
| 표시·파티 | 서버 `party/lobby.service.ts:212` | `m.presetId ?? 'DOCKWORKER'` | 이월 런 파티 로비에서 프리셋 오인 |
| 표시·파티 | 서버 `party/run-participants.service.ts:126,236` | `?? 'DOCKWORKER'` | 파티 합류/정산 경로 동일 |
| 표시·파티 | 서버 `engine/hub/summary-builder.service.ts:243` | `run.presetId ?? 'DOCKWORKER'` | 여정 아카이브 요약이 "항구 노동자"로 오인 |
| 표시·파티 | 클라 `PartyMainScreen.tsx:58` | `m.presetId ?? "DOCKWORKER"` | 파티 화면 표시 오인 |

**실패 경로 (사용자 실측)**: 캠페인에서 star_sand(order 3) 선택 → 아직 완주 시나리오 없음 → `carryOver` 비어 `isFirstScenario=true` → 클라가 보낸 `DOCKWORKER`를 **star_sand 팩**에서 검증 → star_sand 프리셋은 `SS_DOCKHAND`·`SS_PILGRIM`… 뿐 → `Unknown presetId: DOCKWORKER` (400, `runs.service.ts:124`).

> **왜 지금까지 안 드러났나**: silverdeen은 graymar와 **동일 프리셋 ID**(DOCKWORKER 등)를 써서 폴백이 우연히 통과했다. `SS_` 고유 프리셋을 쓰는 star_sand가 최초로 노출시켰다. (불변식 45 — 엔진/클라 콘텐츠 ID 리터럴 금지 위반)

> **스코프 분리**: `context-builder.service.ts:1524`(PRESET_MANNERISMS) / `prompt-builder.service.ts:191` / `portrait.service.ts:38` / `summary-builder.service.ts:40` 등 프리셋별 **데이터 테이블**의 DOCKWORKER 키는 폴백이 아니라 콘텐츠 매핑(기존 불변식 45 그레이존)이므로 본 작업 범위 외. §7.4 검증 기준은 "**폴백 리터럴**(`?? 'DOCKWORKER'`) 0건"이다.

### 공백 3가지
1. **순차 게이팅 없음** — `listAvailableScenarios()`가 전체 목록만 반환(캠페인별 완료/잠금 상태 없음). `handleSelectScenario`가 order>1도 즉시 시작 허용 → 1번 완주 없이 3번 진입 가능. (클라 `isAvailable = prerequisites.length === 0`는 전 팩 `[]`라 **항상 true** — 잠금 UI가 영원히 발동하지 않는 죽은 분기)
2. **되돌아가기 금지 미배선** — `completedScenarios` 재진입 차단 로직 없음.
3. **프리셋 게이팅 혼선** — order 1만 프리셋 선택 화면(CAMPAIGN_PRESET), 이후는 프리셋 강제 전송. 이월 캐릭터엔 프리셋 자체가 불필요한데 더미 값(+gender "male")을 보냄.

## 3. 목표 설계

### 3.1 모델
```
Campaign (userId 1:1 활성)
  └─ carryOverState.completedScenarios: [graymar, silverdeen, ...]  (순서대로 누적)
  └─ carryOverState.identity: { characterName, gender, traitId, portraitUrl }  (첫 시나리오 확정 후 불변)
  └─ 다음 진행 가능 시나리오 = order 오름차순 중 첫 미완료
```

- **첫 시나리오(다음 순번 = order 1)**: 프리셋 선택 → 캐릭터 생성 (기존 캐릭터 생성 6단계 재사용). 완주 시 identity를 carryOver에 확정 저장.
- **이후 시나리오**: 프리셋·gender·이름 **미전송** → `carryOver` 스탯/골드/아이템/평판 + identity 이월.
- **게이팅**: 다음 순번 시나리오 **하나만** 진입 가능. 완료된 것·건너뛴 것은 잠금.

### 3.2 "다음 순번" 결정 규칙 (집합 기반 — 단일 정본)
```
completed = set(carryOver.completedScenarios[].scenarioId)
allByOrder = scenarios sorted by order asc
next = allByOrder.first(s => s.scenarioId ∉ completed)
가능 진입 = { next }        (그 외는 잠금 또는 완료)
```

- 기존 `runs.service.ts:113`의 `scenarioOrder = completedScenarios.length + 1`(위치 기반)은 **집합 기반으로 교체**한다. 위치 기반은 중복 저장·순서 꼬임에 취약 (같은 결과가 2회 저장되면 순번을 건너뜀).
- `mergeCarryOver`(campaigns.service.ts:216)는 현재 `[...prev.completedScenarios, result]`로 **중복 방지 없이 append** — 같은 scenarioId가 이미 있으면 **교체(최신 결과로 갱신)**하는 중복 가드를 추가한다.

### 3.3 완주·실패 시맨틱 (검토 반영 — 신규)
| 종료 상태 | 캠페인 처리 |
|------|------|
| `RUN_ENDED` (엔딩 도달 — 성패 무관) | **완주**. `saveScenarioResult` 머지 → completedScenarios 기록 → 다음 순번 개방. 나쁜 엔딩도 "그 시나리오의 결말"로 이월 (현행 코드 동작과 일치, 의도로 확정) |
| `RUN_ABORTED` (포기·이탈) | **미완주**. 머지하지 않음 → 다음 순번 미개방 → **같은 시나리오 재도전**. 이월 상태는 직전 완주 시점 스냅샷 유지 (시나리오 중간 획득분은 소실 — 재도전은 깨끗한 재시작) |
| 첫 시나리오(order 1) RUN_ABORTED | 재도전 시 **캐릭터 재생성 허용** (identity 미확정 상태이므로 프리셋 선택 화면 재진입) |

`saveCampaignResultIfNeeded`는 현재 campaignId만 확인하므로, 호출 지점이 전부 RUN_ENDED 경로인지 확인하고 RUN_ABORTED 경로에서 호출되지 않음을 보장(또는 함수 내 status 가드 추가)한다.

## 4. 변경 명세

### 4.1 서버
| 파일 | 변경 |
|------|------|
| `runs.controller.ts` | `presetId ?? 'DOCKWORKER'` **제거**. presetId를 그대로 전달(optional). 기본값 주입 금지. |
| `runs.service.ts` | 프리셋 결정 로직: **다음 순번이 첫 시나리오면** 프리셋 필수(없으면 400), **이후면** 프리셋 무시하고 carryOver 사용. `getPreset` 폴백이 필요하면 활성 팩의 **첫 프리셋**으로(리터럴 금지). |
| `runs.service.ts` | **순번 산출 집합 기반 교체** (§3.2) + 이후 시나리오에서 gender/characterName/traitId를 **요청값이 아닌 carryOver.identity에서** 취득. |
| `runs.service.ts` (신규) | 캠페인 모드 진입 시 **순차 검증**: 요청 scenarioId가 "다음 순번"과 일치하는지 확인. 불일치(건너뜀/되돌아감) 시 `BadRequestError('시나리오 순서 위반')`. |
| `campaigns.service.ts` | `mergeCarryOver`: completedScenarios **중복 가드**(§3.2) + 첫 완주 시 identity 확정 저장(§3.3). |
| `campaigns.service.ts` (신규) | `getScenarioProgress(campaignId)` → 각 시나리오에 `status: COMPLETED \| CURRENT \| LOCKED` 부여해 반환. |
| `campaigns.controller.ts` | `GET :id/scenarios` → `listAvailableScenarios()` 대신 `getScenarioProgress()` 사용(캠페인 컨텍스트 반영). |
| `party/lobby.service.ts:212` `party/run-participants.service.ts:126,236` `engine/hub/summary-builder.service.ts:243` | `?? 'DOCKWORKER'` 폴백 제거 — presetId null 허용 경로로 정리 (표시명은 preset 조회 실패 시 캐릭터 이름/제네릭 라벨로 폴백, 콘텐츠 ID 리터럴 금지). |

### 4.2 클라이언트
| 파일 | 변경 |
|------|------|
| `StartScreen.tsx` `handleSelectScenario` | 하드코딩 `"DOCKWORKER"` **및 `"male"`** 제거. status=CURRENT 인 시나리오만 선택 가능. 다음 순번이 order 1(첫 캐릭터 생성)이면 프리셋 화면, 이후면 프리셋·gender 미전송으로 `startCampaignRun`. |
| `StartScreen.tsx` 시나리오 목록 UI | `status`(완료/현재/잠금) 배지 표시. 잠금·완료는 비활성. 기존 `prerequisites.length === 0` 죽은 분기 **제거**(status로 대체). |
| `GameClient.tsx:376` | `presetId ?? "DOCKWORKER"` → 이월 캐릭터는 presetId null 허용, 표시용 폴백은 시나리오/캐릭터 기반. |
| `PartyMainScreen.tsx:58` | `?? "DOCKWORKER"` 폴백 제거 (4.1 파티 경로와 동일 정책). |
| `startCampaignRun` 시그니처 | presetId·gender를 optional로(이후 시나리오는 미전달). |

### 4.3 콘텐츠
- 변경 없음. `order`/`carryOverRules`는 이미 정의됨. `prerequisites`는 order 기반 게이팅으로 대체하므로 빈 배열 유지 (클라 죽은 분기도 4.2에서 함께 제거).

## 5. API 계약 변경
| 엔드포인트 | 변경 |
|------|------|
| `POST /v1/runs` | `presetId`·`gender` optional 유지. 캠페인 모드+이후 시나리오면 무시(carryOver.identity 우선). 순서 위반 시 400. |
| `GET /v1/campaigns/:id/scenarios` | 응답에 `status: COMPLETED\|CURRENT\|LOCKED` 필드 추가(비파괴적 확장). |
| `POST /v1/runs/:runId/abort` (신규) | 진행 중 런 포기 → RUN_ABORTED. 캠페인 머지 없음 → 재도전 가능. RUN_ACTIVE 아니면 400. **§3.3 재도전 트리거 배선** — 클라 시작화면 "그만두기" 버튼 + 새 게임 활성 런 경고에서 호출. |

## 6. 불변식 · 엣지 케이스
1. **단일 활성 시나리오 정책 유지** — 캐리오버는 순차이므로 동시 활성 없음. `enterScenario` 전역 교체와 충돌 없음.
2. **되돌아가기 불가** — 서버가 순서 검증으로 강제(클라 UI 잠금은 편의, 서버가 진짜 게이트).
3. **진행 중 런 존재 시** — 활성 RUN이 있으면 새 시나리오 진입 차단(기존 이어하기 우선). 완주(RUN_ENDED) 후에만 다음 순번 개방. 실패(RUN_ABORTED)는 §3.3 재도전 규칙.
4. **프리셋 하드코딩 전면 금지** — 폴백 7곳 제거가 핵심 (§2 표). 이후 팩이 고유 프리셋을 써도 안전. 프리셋별 데이터 테이블은 스코프 외(§2 스코프 분리).
5. **carryOver 없는 첫 진입** — 반드시 order 1만 허용(2·3을 첫 시나리오로 시작 불가).
6. **캐릭터 정체성 불변** — gender/characterName/traitId는 첫 시나리오 완주 시 확정, 이후 요청값으로 덮어쓸 수 없음 (여성 캐릭터가 2번부터 남성이 되는 클래스 차단).
7. **기존 단독 플레이 경로**(campaignId 없이 scenarioId 직접) — 개발/검증용으로 유지하되, 이 경로도 하드코딩 제거 후엔 프리셋을 명시해야 함(누락 시 팩 첫 프리셋 또는 400). 단독 런은 campaignId가 없어 캠페인 머지를 타지 않음(실측 확인).

## 7. 검증 계획
1. **단위**: 순서 검증(다음 순번만 통과), getScenarioProgress status 산출, 프리셋 결정(첫=필수/이후=무시), mergeCarryOver 중복 가드, identity 이월(gender 요청값 무시).
2. **E2E**: 캠페인 생성 → graymar 프리셋(여성 캐릭터) 선택·플레이 → 완주 → silverdeen 자동 개방(프리셋 없이 이월 + **gender 유지** 확인) → star_sand 개방. 되돌아가기/건너뛰기 시도 400 확인.
3. **회귀**: star_sand를 캠페인 첫 시나리오로 고를 수 없음(order 3) 확인. 단독 경로에서 `SS_PILGRIM` 명시 시 정상, 프리셋 누락 시 팩 첫 프리셋 폴백. RUN_ABORTED 후 같은 시나리오 재도전 가능·다음 순번 미개방 확인.
4. **불변식 45 스캔**: 코드 전역 `?? 'DOCKWORKER'` **폴백 리터럴 0건** (데이터 테이블 키는 제외 — §2 스코프 분리).

## 8. 작업 순서 (Phase)
- **P1 (언블록)**: 진입 경로 하드코딩 3곳 제거 + 서버 프리셋 결정 로직 정리. → star_sand 첫 진입 에러 해소.
- **P1' (동일 클래스 소탕)**: 표시·파티 경로 폴백 4곳 제거 + gender/identity 이월 배선.
- **P2 (게이팅)**: `getScenarioProgress` + 서버 순서 검증(집합 기반 순번) + 클라 status 배지/잠금.
- **P3 (되돌아가기 금지·엣지)**: 활성 런 가드, 재진입 차단, RUN_ABORTED 재도전 시맨틱, mergeCarryOver 중복 가드, E2E 완주 배선.

각 Phase 끝에 `pnpm build`(server/client) + 해당 테스트 + `/v1/version` 확인.
