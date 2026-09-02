# 112. turns.service 3차 재비대 대응 — LOCATION 턴 서비스 분리 설계·계획

- 작성: 2026-09-02 (30턴 롱런 분석 직후, arch/77 §18·§19 의 후속)
- 상태: ✅ Phase 0~2 구현 완료 (2026-09-02 같은 날) · Phase 3 후속 (§4 트리거)
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
