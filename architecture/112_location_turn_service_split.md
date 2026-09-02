# 112. turns.service 3차 재비대 대응 — LOCATION 턴 서비스 분리 설계·계획

- 작성: 2026-09-02 (30턴 롱런 분석 직후, arch/77 §18·§19 의 후속)
- 상태: ✅ Phase 0~2 구현 완료 · Phase 3 진행 중 — P3-A 완료(§10.1), 다음 P3-C 정적층 → P3-B ctx
- 대상: `server/src/turns/turns.service.ts` (7,975줄 · `handleLocationTurnInner` 2,047줄)

## 0. 결정 요약

1. **래칫 상한은 올리지 않는다** (파일 7,900 · 함수 2,000 — arch/77 §18 원칙 유지).
2. LOCATION 턴 파이프라인을 **`location-turn.service.ts` 로 통째 이관**한다. HUB·DAG·전투·상점·관계가
   이미 서브서비스로 나갔는데 LOCATION 만 본체에 남은 비대칭을 없앤다. `TurnsService` 는 라우터
   (submitTurn·조회·재시도·결말) 로 남는다.
3. 이관한 서비스도 상한에 가깝기(≈7,000) 때문에 **같은 세션에서 2차 절단**한다 — 퀘스트 진행
   (`location-quest.service.ts`)·결과 조립(`location-result.service.ts`) 두 도메인을 떼어 파일 ≈5,000 ·
   함수 ≈1,600 으로 내린다.
4. **동작 보존 컷-페이스트만** 한다. 시그니처·순서·변조 방식 불변. 프롬프트 순증 0 · DB 무변경 · SSoT
   (`applyRunStatePatch` CAS·DONE 커밋) 무접촉.
5. 장수 변수 34개를 컨텍스트 객체로 묶는 **Phase 3 은 별도 후속** — 헬퍼 시그니처 전부를 건드리는
   변경이라 이번 절단과 같은 커밋에 섞지 않는다.

## 1. 발단 — 세 번째 재비대

| 시점 | 파일 | 함수 | 조치 |
|---|---|---|---|
| 2026-08-07 (§18) | 9,194 → 6,864 | 2,075 → 1,860 | 도메인 분할 6단계, 상한 9,000→7,900 조임 |
| 2026-08-31 (§19) | 8,306 → 7,837 | 2,416 → <2,000 | relation-turn 신설 + turn-shared 이동 (마진 63) |
| 2026-09-02 (이 문서) | **7,975 / 7,900** | **2,047 / 2,000** | 이틀 만에 재발화 |

§19 가 남긴 교훈 그대로다 — "새 도메인이 생기면 수렴점에 집을 지어줘야 한다". 마진 63줄은
이틀치(빈손 가드·nano 다양화·arc 게이트·questReveal 배선)로 소진됐다. 상한을 올리면 3주 뒤
같은 자리다(§18 실측). **집을 짓는다.**

## 2. 진단 (2026-09-02 계측)

### 2.1 무엇이 크고, 어디에 붙어 있나

| 계측 | 값 |
|---|---|
| 메서드 | 47개. 상위 5개(`handleLocationTurnInner` 2,053 · `processQuestProgression` 637 · `determineTurnEventAndRouting` 605 · `updatePrimaryNpcEmotionAndRecords` 402 · `applyLocationRewards` 337)가 파일의 51% |
| 호출 그래프 | `handleLocationTurnInner` 가 부르는 사설 메서드 29개 중 **28개가 1회 호출** — arch/77 방식 추출은 이미 끝까지 간 상태. 남은 본체는 오케스트레이터 |
| **LOCATION 클러스터** | `handleLocationTurnInner` 에서 도달 가능한 메서드 **36개 · 6,998줄 (파일의 88%)** |
| 비-LOCATION 잔류 | 11개 · 682줄 (`submitTurn`·`handleLocationTurn` 래퍼·`handleArcFinaleTurn`·`getTurnDetail`·`retryLlm`·`getLlmUsage`·`assertRunOwnership` 등) |
| 클러스터 ↔ 잔류 공유 | `finalizeRunEnding`(192) 하나 — `handleArcFinaleTurn` 도 호출 |
| 장수 변수 | 본체 최상위 변수 121개 중 **34개가 1,000줄 넘게 생존** (rawInput·updatedRunState·locationId·arcState·intent·ws·event·rng·resolveResult·challengeDecision…). 추출 단위마다 10~15 필드 인자 객체가 생기는 원인 |
| 주입 의존성 59 | LOCATION 전용 **40** · 양쪽 4(db·turnShared·content·rngService) · 비-LOCATION 전용 5(dagTurn·hubTurn·combatTurn·llmCallLog·points) · **미사용 10**(ruleParser·policyService·actionPlanService·propMatcher·nodeResolver·eventMatcher·campaignsService·consequenceProcessor·playerGoalService·llmWorker) |
| 사문 | `saveLocationVisitSummary`(93줄) — 호출자 0 (L715 주석이 "역할 포함"으로 흡수됐음을 기록) |
| `as any` 57 | 그중 **25건이 결과 UI 부착**(`(result.ui as any).nanoEventCtx = …`) — `UIBundle` 에 타입이 있는 필드도 any. "조용히 꺼진 배선"(arch/100 §14, 이날 결함 B 의 `factRevealed` 사문 계약)의 온상 |
| 테스트 | TurnsService 를 다루는 스펙 8개는 전부 코어 함수 단위. 본체 흐름은 스모크·E2E 만. 이날 결함 A(활성 판정 게이트)·B(nano 값 무대조 승격)는 둘 다 "코어는 맞고 배선이 틀린" 부류 |

### 2.2 본체 절단 후보 블록 (원문 대조 완료 — §19.3 함정 회피)

| 블록 | 위치 | 크기 | 외부 읽기 | 외부 쓰기 | 내부 선언→이후 사용 |
|---|---|---|---|---|---|
| quest_forward 전진 선택지 + 빈손 가드 결정 | L5499~5636 | 138 | 9 | `emptyHandedHint` | 없음 |
| 이벤트·UI 조립(사례금 연출·골드/장비 이벤트·아크 스테이지 이벤트·행동화 디렉티브·nano ctx 부착) | L5893~6172 | 280 | 32 | 없음 (`result` 제자리 변조) | 없음 |
| pendingQuestHint 소비 | L5408~5472 | 65 | 2 | 없음 | `questDirectionHintForUi` |
| 선택지 조립(결말·전진·modifier) | L5748~5800 | 53 | 11 | `choices` | `summaryText`·`result` (본체 유지) |

앞 셋은 반환값 0~1개의 순수 sink 라 메서드로 떼기 쉽다. 넷째는 `result` 를 만드는 자리라 본체에 둔다.

## 3. 목표 구조

```
turns/
├─ turns.service.ts            ≈ 800   라우터: submitTurn · getTurnDetail · retryLlm · getLlmUsage ·
│                                       assertRunOwnership · handleArcFinaleTurn · (LOCATION → locationTurn)
├─ location-turn.service.ts    ≈ 5,000 LOCATION 오케스트레이터 + 라우팅·판정·NPC·보상·전이 헬퍼
│     handleLocationTurn(Inner) ≈ 1,600 (quest_forward·이벤트조립·pendingQuestHint 3블록 추출)
├─ location-quest.service.ts   ≈ 1,100 processQuestProgression · applyArcStageProgress · quest_forward 결정 ·
│                                       pendingQuestHint 소비 · accrue/applyAccrual · pushRumorDiscoveryEvent
├─ location-result.service.ts  ≈ 900   assembleResultUi · buildLocationResult · attachNewsArticle ·
│                                       attachChoiceModifierBadges · 이벤트·UI 조립 · collectTurnMemory
├─ turn-shared.service.ts      ≈ 610   (+ extractTargetNpcFromInput 공용 — finalizeRunEnding 은 §8.1 대로 location-turn public)
├─ hub-turn / dag-turn / combat-turn / equip-shop-turn / relation-turn   (불변)
└─ turns.core.ts · arc-stage.core.ts · … (순수 코어, 불변)
```

의존 방향: `TurnsService → LocationTurnService → {LocationQuestService, LocationResultService, TurnSharedService, 기존 서브서비스}`.
순환 없음 — 새 서비스는 `TurnsService` 를 주입하지 않는다(`turn-shared` 가 이미 그 규약).

## 4. 단계별 계획

### Phase 0 — 사문 제거 (동작 무영향, 별도 커밋)
- 미사용 주입 10개 제거 + `saveLocationVisitSummary` 삭제 (−≈130줄).
- 게이트: `pnpm build` · 전체 스펙 · 부팅 스모크(주입 그래프 변화 확인).

### Phase 1 — LOCATION 클러스터 이관 (컷-페이스트)
1. `LocationTurnService` 신설. 생성자는 LOCATION 전용 40 + 양쪽 4 만 받는다.
2. `handleLocationTurnInner` + 도달 가능 34개 메서드를 **원문 그대로** 이동(`git show HEAD:… ` 로 재대조 —
   §19.3 함정). 이동 전 상단 import 도 필요분만 옮긴다.
3. `finalizeRunEnding` 은 `TurnSharedService` 로 (arc finale 공유). 의존 endingGenerator·summaryBuilder·
   memoryIntegration 을 turn-shared 생성자에 추가.
4. `TurnsService.handleLocationTurn` 래퍼(`runInTurnContext` + llmCallLog flush)는 본체에 남기고 안에서
   `this.locationTurn.handleLocationTurnInner(...)` 호출. **wrapper 의 AsyncLocalStorage 경계는 불변**
   (nano/llm 호출 계측이 여기 묶여 있다).
5. `turns.module.ts` providers 등록. 외부 공개 API(submitTurn·getTurnDetail·retryLlm·getLlmUsage·
   assertRunOwnership — party·admin 이 사용)는 시그니처 불변.
- 게이트: build · 전체 스펙(2,524) · 골든 스냅샷 diff 0 · 스모크 · **eslint 파일 경고: turns.service 소멸,
  location-turn 은 7,000/7,900 통과, 함수 경고는 Phase 2 까지 잔존 허용**.

### Phase 2 — 2차 절단 (같은 세션)
| 이동분 | 목적지 | 근거 |
|---|---|---|
| `processQuestProgression`(637) · `applyArcStageProgress`(138) · `accruePendingQuestReward` · `applyAccrualToResult` · `pushRumorDiscoveryEvent` · **quest_forward 블록**(138, 본체에서 추출) · **pendingQuestHint 소비**(65, 추출) | `location-quest.service.ts` | 퀘스트 fact·단계·아크 스테이지·전진 선택지는 한 도메인(arch/58·60·65·103). 이날 결함 A·B 의 배선이 모두 여기 |
| `assembleResultUi`(275) · `buildLocationResult`(104) · `attachNewsArticle`(129) · `attachChoiceModifierBadges` · **이벤트·UI 조립 블록**(280, 추출) · `collectTurnMemory`(104) | `location-result.service.ts` | 결과 번들 조립. `as any` 25건이 전부 여기로 모여 후속 타입화의 표적이 된다 |

- 추출 블록 3개는 반환값이 0~1개(§2.2)라 `{ emptyHandedHint }`·`{ questDirectionHintForUi }`·void 로 닫힌다.
- 게이트: Phase 1 과 동일 + **함수 경고 소멸**(≈1,600/2,000) + 레포 lint 경고 0.

### Phase 3 — 후속 (이 문서의 범위 밖, 트리거 명시)
- `LocationTurnContext` 도입: 장수 변수 34개를 한 객체로, phase 메서드는 ctx 하나만 받는다. 인자 객체
  비대(현 최대 11필드)와 제자리 변조/반환 혼재(arch/103 "arcState 대입이 진행 유실" 실측)를 여기서 정리.
- UI 부착 타입화: `attachUi(result.ui, {...})` 헬퍼 + `UIBundle` 필드 보강으로 `as any` 25건 제거.
- **배선 정합 통합 스펙** 1개: mock 콘텐츠 + runState 로 LOCATION 턴 1회를 돌려 `ui.questReveal ↔
  프롬프트 [정보 전달] ↔ arc 이벤트` 정합을 본다 — 이날 결함 A·B 부류 전용.
- 트리거: Phase 2 배포 후 첫 기능 추가 시점, 또는 location-turn 이 6,500줄을 넘을 때.

## 5. 검증 (각 Phase 공통)

1. `pnpm build` (nest) · `npx jest` 전체 — **2,524 passed 기준선, 스냅샷 변경 0** (분할은 프롬프트를
   만지지 않는다. 스냅샷이 바뀌면 컷-페이스트가 틀린 것).
2. `npx eslint src/turns` — 래칫 경고 수 기록(Phase 1: 함수 1건 허용 → Phase 2: 0).
3. 재기동 + `SMOKE_NO_BROWSER=1 scripts/e2e/smoke.ts` (부팅·주입 그래프·3턴).
4. 15턴 플레이테스트 1런(chatty·graymar) — 게이트 15종 + 이날 프로브 3종 재실행
   (무커밋 route-only 닫힘 / 무공개 턴 `[정보 전달]` 0 / 에드릭 "삼할" 0).
5. 커밋 단위: Phase 0 · Phase 1 · Phase 2 각각 (되돌리기 단위 = Phase).

## 6. 위험과 대응

| 위험 | 대응 |
|---|---|
| 이동 중 인자 축약·재작성으로 동작 변경 (§19.3 실측) | 블록은 `git show HEAD:파일` 원문에서 복사. diff 는 "삭제 N줄 = 추가 N줄" 형태여야 하며 내용 차이는 `this.` 접두 치환뿐 |
| 클로저 캡처 변수(`questRevealThisTurn`·`emptyHandedHint` 등 `let`)가 추출 경계를 넘음 | §2.2 표의 "외부 쓰기" 열이 반환값. `let` 19개 중 블록 경계에 걸린 것만 반환 객체로 |
| NestJS 순환 주입 | 새 서비스는 `TurnsService` 미주입. `TurnSharedService` 가 이미 같은 규약으로 5개 서브서비스를 지탱 |
| `runInTurnContext` 경계 이동으로 LLM 호출 로그 누락 | 래퍼는 `TurnsService` 에 그대로, 내부 호출만 위임 |
| party-turn 이 `submitTurn` 경유 — 파티 런 회귀 | 파티 스펙 유지 + 스모크(솔로) 후 파티 E2E 1회 (`scripts/e2e/` 파티 시나리오) |

## 7. 비목표

- 프롬프트·nano·워커 동작 변경 없음. 콘텐츠 무변경. DB·스키마 무변경.
- `processQuestProgression`(637)·`determineTurnEventAndRouting`(605) 자체의 내부 분해는 하지 않는다 —
  파일 이동으로 상한 문제가 풀리면 내부 분해는 Phase 3 컨텍스트 객체와 함께.

## 8. 진행 결과 (2026-09-02)

| Phase | 커밋 | 결과 |
|---|---|---|
| 0 사문 제거 | eec845f | 미사용 주입 10 + `saveLocationVisitSummary` 93줄 제거. 7,975 → 7,861 |
| 1 이관 | 77a5883 | `location-turn.service.ts` 7,308 / `turns.service.ts` 587. 메서드 45개 원문 기계 대조(치환은 위임 접두·정적 상수 클래스명·public 화뿐). 미사용 import 177 정리 |
| 2 절단 | 7ece1de | `location-turn` 5,171 · `location-quest` 1,108 · `location-result` 1,289 · `turn-shared` 613. **`handleLocationTurnInner` 2,047 → 1,620** — 레포 lint 경고 0 |

각 Phase 게이트: build · 2,524 passed · 골든 스냅샷 17 불변 · 재기동 스모크 PASS.

Phase 2 배포 후 검증(§5-4): 15턴 런(chatty·graymar·SMUGGLER, run_20260902_p2verify) 게이트 14/15 —
V14 FAIL 은 3런 풀링에 남은 직전 star_sand 런의 BACKGROUND 고착 1건(이 런 bgOver 0). fact 공개 3건
(이벤트 경로 observe·NPC direct·rumor) · questState S2 도달 · 레이턴시 p90 8.2s · 어체 위반 1/17.
프로브 3종 재실행 PASS — A: route-only 아크 이벤트 0 / 커밋 후 안내만 / 둘째 턴 FAIL 은 failCounts 누적(완수 없음) ·
B: `[정보 전달]` 지시가 questReveal 있는 턴에만(t·t·f = 공개·공개·무공개) · C: 에드릭 3턴 "삼할" 0.

### 8.1 설계와 달라진 점
- **`finalizeRunEnding` 은 turn-shared 가 아니라 `LocationTurnService` public** — 정산 헬퍼 2개(`settlePendingQuestReward`·`buildSettlementEvents`)와 memoryIntegration·summaryBuilder 의존이 딸려 turn-shared 를 키우는 것보다 위임이 싸다. arc finale(TurnsService)이 `this.locationTurn.finalizeRunEnding` 호출.
- **`extractTargetNpcFromInput` 은 turn-shared 공용으로** — location-turn(3곳)과 location-quest(processQuestProgression)가 같이 쓰고, 새 서비스가 location-turn 을 역참조하면 순환이라서.
- 추출 3블록의 params 는 `finalizeRunEnding` 선례대로 대부분 `any`(sink). `updatedRunState`·`discoveredFactIdsThisTurn` 등 추론이 끊기는 것만 실제 타입. 그 결과 `assembleTurnEvents` 안의 `(result.ui as any).X` 11줄은 eslint `no-unnecessary-type-assertion` 자동수정으로 단언이 사라졌다 — **타입이 좋아진 게 아니라 `result` 가 any 가 된 것**. Phase 3 의 UI 부착 타입화가 이걸 되돌려야 한다.

### 8.2 함정 기록
- BSD `sed` 는 `\+` 를 모른다 — 정적 상수 치환이 3곳 조용히 안 됐다. 치환은 python `re` 로.
- 청크 경계는 `  }` 단독 줄로 잡되, 이동 후 prettier 가 시그니처를 줄바꿈하면 대조 파서가 "MISSING" 을 낸다 — 다중집합 줄 대조(공백 제거)가 더 견고했다.
- 생성자 파라미터는 `@Optional()` 이 별줄일 수 있어 삭제 시 고아 데코레이터가 남는다 — 삭제 후 연속 `@Optional()` 검사.
- 새 서비스 생성자에 필수 파라미터를 optional 뒤에 붙이면 TS1016 — `turnShared` 바로 뒤에 삽입.

## 9. Phase 3 상세 설계·수정 계획 (2026-09-02 계측 기준 — 착수 전)

### 9.0 목표·비목표

목표는 셋이다. ① 오케스트레이터의 장수 변수 34개를 **한 컨텍스트 객체**로 묶어 인자 객체 비대(현 최대 34필드)와
제자리 변조/반환 혼재를 없앤다. ② 결과 UI 부착을 **타입 있는 단일 경로**로 모아 "조용히 꺼진 배선" 부류를
컴파일 시점에 잡는다. ③ 코어 함수 사이의 **배선**을 검증하는 층을 만든다 — 이날 결함 A·B 는 코어 스펙이
전부 통과한 채 배선에서 났다.

비목표: 프롬프트·nano·워커 동작 변경 없음, DB·콘텐츠 무변경, `processQuestProgression`(637)·
`determineTurnEventAndRouting`(605) 내부 분해는 9.4 이후.

### 9.1 계측 (location-turn.service.ts @ 7ece1de)

| 항목 | 값 |
|---|---|
| 오케스트레이터 | 1,620줄 · 최상위 변수 125 · **800줄 이상 생존 34** |
| 재대입되는 `let` | `ws` 15회 · `challengeDecision` 6 · `intent` 3 · `rawInput` 1 · `agenda` 1 · `goldShortfall` 1 (나머지 28개는 const 참조 — 객체 내부 변조만) |
| 객체 인자 호출 | 25곳. 필드 수 상위: `assembleTurnEvents` 34 · `npcResolver.resolve` 45(외부) · `finalizeRunEnding` 21 · `collectTurnMemory` 19 · `assembleResultUi` 18 · `applyTurnStateTransitions`/`applyInjectedNpcRecords`/`determineTurnEventAndRouting` 15 |
| UI 부착 | `result.ui.X =` 34종. `UIBundle` 에 있는 것 22 / **없는 것 22** (speakingNpc·shops·questStatus·primaryNpcWitnessedTags·priceIndex·portraitMap·peakMode·npcReactions·npcPostures·npcPortrait·npcInjection·npcAgitation·newlyIntroducedNpcIds·newlyEncounteredNpcIds·narrativeMarks·nanoEventHint·nanoEventCtx·mainArcClock·equipmentTags·day·arcState·activeSetNames) |
| 주입 41 | 순수 엔진 30 · I/O 경계 ≈11(db·turnShared·equipShopTurn·nodeTransition·memoryIntegration = DB / llmIntentParser·nanoEventDirector·challengeClassifier·locationResult(호외 nano) = LLM / resolveService·rewardsService 미분류) |
| 테스트 | `createTestingModule` 사용 0건 — 레포 스펙 전부가 순수 코어 단위. 서비스 조립 테스트 인프라가 없다 |

### 9.2 작업 항목

#### P3-A. UI 부착 타입화 (반나절, 동작 무변경)
1. `db/types/server-result.ts UIBundle` 에 누락 22필드를 **실제 값 타입**으로 추가 (부착 지점의 우변 타입을 그대로 옮긴다 — `any` 금지, 미확정은 `unknown` 대신 값 타입을 좁힌다).
2. `location-result` `assembleTurnEvents`·`assembleResultUi` 와 `location-turn` 의 `(result.ui as any).X =` / `result.ui.X =` 를 `result.ui.X = …` 로 통일하고 params 의 `result: any` → `ServerResultV1`.
3. 소비 측(`llm-worker`·`context-builder`)의 `(serverResult.ui as Record<string, unknown>)?.nanoEventHint` 류는 `serverResult.ui.nanoEventHint` 로 (읽기 8곳 내외 — grep 으로 확정).
4. 게이트: tsc/빌드 · 2,524 스펙 · 스냅샷 0 · `as any` 는 location-result 에서 0 이어야 한다. **부작용 감시**: 타입을 붙이면서 "실제로 안 쓰이는 부착"이 드러나면 삭제하지 말고 기록만 (P3-C 의 검출 대상).

#### P3-B. `LocationTurnContext` (1~2일, 헬퍼 단위 커밋)
컨텍스트는 **역할별 4묶음**으로 나눈다 — 한 덩어리 `any` 백이 되면 인자 객체와 다를 게 없다.

```ts
type LocationTurnCtx = {
  in:   { run; currentNode; turnNo; body; runState; playerStats };          // 불변 입력
  state:{ updatedRunState; ws; arcState; agenda; npcStates; actionHistory;
          cooldowns; heatAtTurnStart; priorWsSnapshot; prevHeat; prevSafety; prevIncidents }; // 세계 상태(변조·재대입 허용은 ws·agenda 만)
  turn: { locationId; source; rawInput; choicePayload; intent; intentV3; dialogueAct;
          worldBoundary; rng; event; routingResult; challengeDecision; resolveResult;
          goldShortfall; presetActionBonuses };                             // 이번 턴 결정(재대입: rawInput·intent·challengeDecision·goldShortfall)
  out:  { result; newlyIntroducedNpcIds; newlyEncounteredNpcIds; nanoEventCtx; nanoEventResult;
          npcReactions; primaryNpcWitnessedTags; relevantIncident; legendaryResult; … }; // 결과·부산물
};
```

절차 (각 단계가 커밋이며 스냅샷 0 이 게이트):
1. 오케스트레이터 상단에서 `ctx` 를 만들되 **기존 지역 변수는 그대로 둔다** (`const ctx = { … }` 로 참조만 모음). 동작 0 변경.
2. 헬퍼를 **sink 부터** 전환 — 반환 없는 것(`applyNarrativeTicksAndRewards`·`applyLocationRewards`·`applyInjectedNpcRecords`·`applyTurnStateTransitions`·`assembleTurnEvents`·`collectTurnMemory`·`assembleResultUi`) 순으로 `params` → `ctx`. 호출부는 `this.x(ctx)`. 헬퍼 본문 첫 줄에서 종전 이름으로 구조분해(`const { a, b } = ctx.turn`)해 본문은 손대지 않는다 → 본문 diff 0.
3. 값을 돌려주는 헬퍼(`determineTurnEventAndRouting`·`buildNanoEventContext`·`applyCombatTransition`·`finalizeRunEnding`·quest 2종)는 **반환 유지**. 반환값을 `ctx` 에 쓰는 건 호출부 한 줄. 헬퍼가 `ctx` 를 직접 쓰게 바꾸는 것은 하지 않는다 — arch/103 "arcState 대입이 진행 유실" 함정은 "누가 쓰는가"가 둘이 될 때 난다.
4. 재대입 변수 6개는 마지막에 `ctx.state.ws = …`/`ctx.turn.intent = …` 로 옮긴다. 이때 이후 문장이 지역 변수를 읽고 있으면 안 되므로 **지역 변수 선언을 삭제하고 컴파일러가 남은 참조를 전부 잡게** 한다(수동 검색 금지).
5. 완료 기준: 오케스트레이터에 800줄 이상 생존 변수 0 (ctx 하나만 남음), 인자 객체 필드 수 최대 ≤ 5(ctx + 국소 인자), 함수 ≈ 1,400.

위험: `assembleTurnEvents` 처럼 params 가 `any` 였던 곳은 P3-A 를 먼저 끝내 타입이 실재해야 ctx 전환에서 오타·누락이 컴파일에 걸린다. **순서 A → B 고정**.

#### P3-C. 배선 검증 2층 (반나절 + 스파이크 1일)
정적층(반나절, 확정): `scripts/selfcheck/` 에 디텍터 1족 추가 — **`wiring.py`**
- W1 `ui 부착 ↔ UIBundle`: 서버 코드의 `result.ui.X =` 전수 ↔ 타입 필드. 누락은 ERROR (P3-A 완료 후 0 이 baseline).
- W2 `nano 출력 필드 ↔ 소비`: NanoEventResult/NpcReaction JSON 필드마다 프롬프트 빌더 소비처와 서버 정규화(`normalize*Core`) 유무를 표로 — "nano 가 답하고 서버가 대조 없이 쓰는 필드"가 신규로 생기면 WARN (결함 B 부류).
- W3 `ARC/QUEST 게이트 정본 단일성`: `currentRoute` 로 커밋을 판정하는 코드가 다시 생기면 ERROR (`isArcCommitted` 이외의 `arcState.currentRoute &&` 조건식 grep).
- 기존 ledger.jsonl·baseline 규약 그대로(arch/101).

동적층(스파이크, 채택 조건부): **LocationTurn 테스트베드** — 순수 엔진 30개는 실제 인스턴스, I/O 경계 ≈11개만 스텁.
- 스텁 규약: `db`(no-op 커밋·조회 빈 배열), `llmIntentParser`(입력 → 고정 intent 테이블), `challengeClassifier`(FREE/CHECK 고정), `nanoEventDirector`(null), `turnShared.commitTurnRecord`(메모리), `memoryIntegration`(no-op).
- 콘텐츠는 실제 `content/graymar_v1` 로드(`ContentLoaderService` 는 파일 기반) — 팩 계약 위에서 배선을 본다.
- 첫 케이스 3개 = 이날 결함 재현: (a) ARC_HINT 이벤트 매칭 턴 → `arcState.currentRoute` 세팅 + ARC_STAGE_INTRO 0 (b) 이벤트 경로 FREE 턴 fact 발견 → `ui.questReveal` 존재 (c) 커밋 후 안내 턴 → announced 만, 완수 0.
- **채택 조건**: 테스트베드 구축 1일 안에 세 케이스가 돌고, 순수 엔진 인스턴스화가 DB 없이 되는 것이 확인되면 정본 스펙으로 승격. 안 되면(엔진이 숨은 DB 의존을 갖거나 스텁이 10개를 넘으면) 폐기하고 정적층 + E2E 스모크 확장(smoke.ts 에 arc 시드 케이스)으로 대체한다. 스파이크는 `spike/location-turn-testbed` 브랜치, 결과는 이 문서 §10 에 기록 후 브랜치 삭제(브랜치 정책).

#### P3-D. 잔여 대형 메서드 (선택, ctx 이후)
`processQuestProgression`(637)은 경로 1·2·3 + 전환 + 힌트 5단으로 자연 절단면이 있고, `determineTurnEventAndRouting`(605)은 턴 모드·매칭·셸 보장 3단이다. ctx 가 있으면 각 단이 `(ctx) → 부분 결과` 로 떨어진다. 파일 상한과 무관하므로 **필요할 때만**.

### 9.3 순서·크기·게이트

| 순서 | 항목 | 크기 | 커밋 단위 | 게이트 |
|---|---|---|---|---|
| 1 | P3-A UI 타입화 | 0.5일 | 1 | tsc · 2,524 · 스냅샷 0 · location-result `as any` 0 |
| 2 | P3-C 정적층 (wiring.py) | 0.5일 | 1 | W1 baseline 0 · W2 표 산출 · W3 0 · ledger 기록 |
| 3 | P3-B ctx | 1~2일 | 헬퍼당 1 (≈12) | 매 커밋 스냅샷 0 · 완료 시 생존 변수 0·함수 ≈1,400 · 15턴 런 1회 |
| 4 | P3-C 동적층 스파이크 | 1일 상한 | 브랜치 | 케이스 3개 통과 시 채택, 아니면 §10 기록 후 폐기 |
| 5 | P3-D | 필요 시 | — | — |

트리거는 §4 그대로(다음 기능 추가 시점 또는 location-turn 6,500줄 초과)이되, **P3-A 와 P3-C 정적층은 트리거와 무관하게 먼저 해도 되는 저위험 항목**이다 — 각각 반나절이고 동작을 바꾸지 않는다.

### 9.4 위험

| 위험 | 대응 |
|---|---|
| ctx 전환 중 헬퍼가 지역 복사본 대신 ctx 원본을 변조해 동작이 바뀜 | 9.2-B-3: 반환 유지, ctx 쓰기는 호출부 한 줄. 본문 diff 0 규약 |
| UIBundle 타입을 붙이자 기존 부착 값이 타입과 안 맞음(실제 버그 노출) | 고치지 말고 기록 → 별도 결함 항목. P3-A 커밋은 타입 전용 |
| 테스트베드가 엔진의 숨은 I/O 의존을 만나 눈덩이 | 1일 상한 + 스텁 10개 상한, 초과 시 폐기 (채택 조건 명시) |
| Phase 3 도중 기능 커밋이 location-turn 에 계속 쌓임 | ctx 전환은 헬퍼 단위 커밋이라 rebase 충돌이 국소적. 기능 작업과 같은 날 겹치지 않게 일정 배치 |

## 10. Phase 3 진행 기록

### 10.1 P3-A UI 부착 타입화 — 완료 (2026-09-02, server a4e124a)

- `UIBundle` +24 필드(계획의 22 + 호외 `newsArticle`·`newsHeadlines` — 부착 인벤토리에 안 잡혔던 `ui.X =` 형태).
  정본 타입이 엔진·LLM 모듈에 있는 4종(`ShopDisplayItem`·`NpcInjection`·`NanoEventContext/Result`·`EmptyHandedHint`)은
  **type-only import** 로 참조했다 — db/types → engine/llm 방향의 런타임 의존은 없다(중복 정의보다 낫다고 판단).
- 생산 측 캐스트 대입 0 (turn-shared·hub-turn·location-result·location-turn). `assembleTurnEvents`·`finalizeRunEnding`·
  `attachNewsArticle` 의 `result: any`/`ui: Record` → `ServerResultV1`/`UIBundle`. 소비 측 10곳 타입 읽기 전환.
- 게이트: tsc 0 · build · 2,524 passed · 스냅샷 17 불변 · `eslint src/turns` 0 · 스모크 PASS. 동작 변경 0.
  (레포 전체 `eslint src` 는 변경 전과 동일한 28건 — 스펙 파일 `any` 경고·auth/npc-resolver prettier 드리프트. 이번 범위 밖, 별건.)
- **타입을 붙여서 드러난 것(수정하지 않고 기록 — §9.4 규약)**:
  1. MOVE 출발 턴 스탬프 `actionContext = { parsedType: 'MOVE_LOCATION' }` 2곳(location-turn)은 `ActionContext.originalInput`(필수)이 없다.
     소비자가 `originalInput` 을 읽으면 undefined — 캐스트를 남기고 기록. 실제 읽는 곳이 있는지는 W1 디텍터 후속에서 확인.
  2. `questStatus` 는 생산자가 `null` 을 넣는다(`buildQuestStatus` 반환) — 타입을 `| null` 로 맞췄다. 클라 표시 계약과 일치하는지 확인 대상.
  3. 기존 타입 필드(`actionContext`·`resolveOutcome`·`speakingNpc`)의 레거시 캐스트 읽기가 llm-worker 26·context-builder 21·prompt-builder 8 남아 있다.
     동작엔 무관하나 "타입이 있는데 우회"라 W1 디텍터가 잡을 대상.
  4. `location-result` 의 비-UI `as any` 4곳(`event.payload`·`resolveOutcome as any`·`npcEmotionalDelta`·`kind: 'NPC' as any`)은 이번 범위 밖.
- 다음: P3-C 정적층(`scripts/selfcheck/wiring.py`) → P3-B ctx.
