# 114. 거대 파일 4개 조각내기 — T1 llm-worker 단계 파이프라인 · T2 프롬프트 블록 레지스트리 · T3 RunState 소프트 슬라이스 (2026-09-08)

> 상태: ✅ **T1 Phase 1·2 · T2 Phase A · T3 완료** (동작 보존 기계 대조, jest 2,614 passed, 스냅샷 17 불변, 스모크 PASS, 서버 라이브). §6 은 착수 설계 원문, 결과는 §7·§8
> 관련: arch/77(1차 God method), arch/112(turns.service 3차 분할), TODOS.md 최우선 3과제

## 0. 결정 요약

재작성 대신 유지보수를 택했다. 근거는 코드가 아니라 **코드에 박힌 실측 지식**이다 — "실측" 주석 540곳, 인용 런 id 41, 버그 id 17, 불변식 58. 재작성하면 이 규칙들이 사라지고 같은 플레이테스트를 다시 해야 한다. 대신 재작성 충동의 실제 원인인 거대 파일 4개(`llm-worker` 6,764 · `location-turn` 5,189 · `prompt-builder` 4,634 · `context-builder` 3,275)를 순서대로 조각낸다. 오늘 품질 사이클 수정 9건 중 7건이 이 네 파일 안이었다.

| 과제 | 대상 | 방식 |
|---|---|---|
| **T1** | `llm-worker.service.ts` | `processTurnInner` 1,955줄 → 단계 메서드 10개 (Phase 1) + 후처리 헬퍼 군·CAS·core 함수 블록을 `llm/worker/` 로 이관 (Phase 2) |
| T2 | `prompt-builder.service.ts` | 블록 레지스트리 — 115개 push 지점에 id·헤더·배타 규칙을 붙여 블록 간 모순을 표에서 검출 |
| T3 | `RunState` jsonb | 타입 슬라이스 — 워커 CAS 가 소프트 상태만 건드린다는 불변식 2 를 타입으로 강제 |

## 1. 계측 (2026-09-08, server `96e9d5a`)

- 파일 6,765줄 · 메서드 48 · 생성자 주입 20.
- `processTurnInner` 3010-4964 = **1,955줄**, 내부 `this.*` 호출 42(32종), 장수 지역변수(선언→마지막 사용 400줄+) **35개** — `serverResult` 1,862줄, `workerRunState` 1,812, `npcDef` 1,658, `nanoEventCtx` 1,507 …
- 그 뒤: `insertDialogueMarkers` 1,105 · `rollbackOrConfirmIntroductions` 296 · `assembleJsonModeNarrative` 283 · `reconcileSpeakingNpcAndPortrait` 240.
- 클래스 앞 순수 core 함수 블록 185-929 (**745줄**, export 20) — 다른 파일 6곳이 import.
- try 본문 안 `return` 9곳 중 메서드 레벨 조기 종료는 **1곳**(4085, 실패 통지·환불 후 종료), 나머지는 콜백 내부.
- 금지선(arch/77 P4.0): 이중처리 락(조건부 UPDATE+returning) · 스트림 emit 순서 · DONE 커밋+finalChoices SSoT · fire-and-forget CAS. 전부 위치 불변.

## 2. Phase 1 — 단계 파이프라인 (같은 파일, 컷-페이스트)

원문 try 본문(3043-4948)을 섹션 주석 경계 10곳에서 잘라 각각 `private async stageX(pending, ctx)` 로 옮겼다. 절단 기준은 **데이터플로 분석기**(`blockflow.py`, 스크래치) — 블록별 입력(앞에서 선언·안에서 읽힘)·변이 입력·출력(안에서 선언/대입·뒤에서 읽힘)을 계산하고, 단계는 `const { … } = ctx` 로 받고 `return { … }` 로 넘긴다. **수동 타이핑 0** — `type WorkerCtxN = WorkerCtxN-1 & Awaited<ReturnType<LlmWorkerService['stageX']>>` 로 누적 추론(private 메서드의 인덱스 접근은 모듈 레벨에서 허용됨을 실험으로 확인).

| # | 단계 | 원문 | 입력 | 출력 |
|---|---|---|---|---|
| 1 | `stageAcquireAndLoad` | 3043-3118 | — | runSession·prevTurn·recentRows·workerRunState |
| 2 | `stageBuildContext` | 3119-3196 | 3 | llmContext·previousChoiceLabels·actionCtxForTarget |
| 3 | `stagePreDirect` | 3197-3516 | 6 | directorHint·nanoEventHint·npcReaction·reactionNpcIdUsed·isEndingTurn |
| 4 | `stageAssemblePrompt` | 3517-3633 | 7 | messages·config·lightConfig·promptProfile·alternateModel·introDialogue·isCombat·useJsonMode |
| 5 | `stageGenerate` | 3634-3857 | 10 | callResult |
| 6 | `stageDecideNarrative` | 3858-4100 | 10 | narrative·llmChoices·modelUsed·extractedFacts·threadEntry·isStreamingMode·jsonModeParsed·dialogueSlotNpcIds (+`halted`) |
| 7 | `stagePostProcessMarkers` | 4101-4353 | 13 | narrative·speechAudit·npcFarewellDetectedThisTurn·_appearedNpcIds·_npcStatesRef·_portraits |
| 8 | `stageCommitDone` | 4354-4427 | 14 | sceneCutPromise |
| 9 | `stageFinalizeChoices` | 4428-4757 | 10 | — |
| 10 | `stageFollowUp` | 4758-4948 | 11 | — |

- 조기 종료 1곳은 `return { halted: true as const }` → 파이프라인이 `if (out6.halted) return;` — `Extract<…, { halted: false }>` 로 정상 분기만 누적.
- 분석기 오탐(콜백·중첩 스코프 이름 `id`·`gh`·`b`·`rs`·`npcId`·`npcState`·`profile`)은 **tsc 가 전부 잡았다** — TS18004 "shorthand property not in scope" 15건 → overrides 로 제거, 잔여 0.
- 클로저 함정 점검: 이후 단계에서 재대입되는 `narrative`·`threadEntry` 를 이전 단계 콜백이 지연 참조하는 곳 0.
- **기계 대조**: 단계 본문을 재조립해 원문 3043-4948 과 byte 비교 → 1,906/1,906 동일(prettier 전).
- 결과: `processTurnInner` 1,955 → **60줄**, 파일 6,765 → 6,955(+시그니처·타입), eslint 0, jest 2,592, 스모크 PASS.

## 3. Phase 2 — `llm/worker/` 이관

| 새 파일 | 내용 | 줄수 |
|---|---|---|
| `worker/worker-narrative.core.ts` | 클래스 앞 순수 함수 20 (`sanitizeNanoChoiceNpcsCore`·`fixNpcMismatchCore`·`resolveColonLabelNpcCore`…) + 재수출 1 | 758 |
| `worker/run-state-patch.service.ts` | `RunStatePatchService.apply` = 구 `applyRunStatePatch` (CAS 3회 재시도) — **워커 역류의 단일 쓰기 지점** | 64 |
| `worker/narrative-postprocess.service.ts` | 후처리 15 메서드: 마커 삽입(1,105)·소개 롤백/확정·화자 정합·별칭 정리·작별 감지·어체 조회·스트림 세그먼트·재탕/실명 센서 | 2,291 |

- 워커는 기존 import 경로 호환을 위해 core 심볼 전부를 재수출(`export { … } from './worker/worker-narrative.core.js'`, 타입은 `export type`). 다른 파일 6곳의 import 무변경.
- 호출 치환: `this.applyRunStatePatch(` → `this.runStatePatch.apply(` (워커 7·후처리 4), `this.<moved>(` → `this.postprocess.<moved>(`. 생성자 주입 2 추가(`@Optional` 앞).
- 함정 2건: ① 시그니처 안 타입 중괄호(`params: { … }`)에서 브레이스 균형이 끊겨 메서드가 반토막 — 괄호 깊이 0 이후 본문 `{` 부터 세도록 수정 ② 메서드 본문 안 `import('../x')` 타입 임포트와 재수출 문(`export { x } from './y'`)은 import 파서 밖이라 경로 보정을 따로 걸었다.
- **의미 대조**: 이동 메서드 15 + `apply` + 워커 잔여 31 + 단계 10 을 원문과 공백 정규화 비교 → 불일치 2건은 prettier trailing comma 뿐.
- 결과: `llm-worker.service.ts` 6,955 → **3,983줄**(-43%), 최대 함수 `insertDialogueMarkers` 는 후처리 서비스로. jest 2,592 · 스냅샷 17 · 스모크 PASS · 서버 라이브.

## 4. 검증 (공통)

tsc 0 → eslint 0 → 기계/의미 대조 → 전체 jest → `pnpm build` + kickstart → `/v1/version` → 스모크 3턴. 골든 스냅샷은 프롬프트 빌더 소관이라 T1 에서 변경 없음.

## 5. 잔여 (T1)

- `assembleJsonModeNarrative`(283, JSON 모드 사문 경로)·`buildSceneCutPromise`(142)·`retryShortAlternateResponse`(84) 는 워커에 남김 — 다음 후보는 `worker/json-mode.service.ts`.
- 단계 ctx 는 누적 교집합이라 단계 9·10 이 14개 입력을 받는다. 필요 이상 넓지만 동작 보존 우선. 좁히기는 T3(RunState 슬라이스)와 함께.
- 로그 컨텍스트 이름이 `NarrativePostprocessService`·`RunStatePatchService` 로 바뀜 — 태그(`[LockSeed]` 등) 기반 grep 은 영향 없음.

## 6. T2·T3 착수 설계 (원문 보존 — 결과는 §7·§8)

**T2 블록 레지스트리** — `buildNarrativePrompt` 1,534줄에 push 지점 115. 전면 재구성 대신 ① `prompt-block.registry.ts` 에 블록 id·헤더·목적·`exclusiveWith` 를 데이터로 등록 ② push 를 `emit(id, text)` 로 치환(동작 보존 — 문자열 동일) ③ 빌드 끝에 공존 금지 쌍 검사 → `[PromptBlockConflict]` 경고 + 골든 픽스처 스펙. 첫 규칙 2쌍은 오늘 실측: `REF_CHOICES × HUB_RETURN_SHELL`, `INFO_REVEAL × SMALL_TALK`.

**T3 RunState 슬라이스** — `RunState` 를 `HardState`(hp·gold·inventory·questState·discoveredQuestFacts…)와 `SoftState`(npcStates.emotional·sceneCutState·nextBeatCandidates·recentTopics…) 로 나누고 `RunStatePatchService.apply` 의 patch 콜백 타입을 `(rs: SoftStateView) => boolean` 으로 좁힌다. 하드 필드 접근이 컴파일 오류가 되는 것이 목표.

## 7. T2 — 프롬프트 블록 레지스트리 Phase A (2026-09-08)

§6 의 ② "push 를 `emit(id, text)` 로 치환" 은 **하지 않았다**. `buildNarrativePrompt` 의 push 지점 115 를 전부 손대면 스냅샷 17 이 그대로여도 diff 가 1,000줄이 넘어 리뷰가 불가능하고, 블록은 이미 첫 줄 `[헤더]` 로 자기 식별이 된다. 대신 **조립이 끝난 `factsParts` 를 사후 분류**한다 — 동작 보존이 문자열 동일이 아니라 "빌더 코드 무변경 + 로그 한 줄" 이라 대조가 필요 없다.

| 파일 | 내용 | 줄수 |
|---|---|---|
| `prompts/prompt-block.registry.ts` | `PROMPT_BLOCKS` **90 항목** — `{ header: string \| RegExp, purpose, when, exclusiveWith? }`. 헤더는 문자열 접두(대부분 `[헤더]`) 또는 RegExp(`/^⚠️ NPC 반응 가이드:/` 처럼 대괄호 없는 블록 4종). `classifyPromptBlocks(parts) → { ids, unregistered, conflicts }` | 562 |
| `prompts/prompt-block.registry.spec.ts` | 무결성(id 유일·exclusiveWith 참조 해소·대칭) + **골든 픽스처 17 전부 unregistered=0·conflicts=0** | 107 |
| `prompt-builder.service.ts` | `messages.push(user)` 직전 분류 → `[PromptBlockConflict]` warn · `[PromptBlockUnregistered]` debug · 선택 `sink.blocks` 로 리포트 반환 (마지막 optional 파라미터, 호출부 무변경) | +22 |

- **배타 규칙 첫 등재**(오늘 품질 사이클 실측 2쌍 + 정책 1쌍): `HUB_RETURN_SHELL ↔ REF_CHOICES`(셸 턴에 참고 선택지 — QC 3-B), `NPC_DAILY ↔ INFO_REVEAL_NPC / INFO_REVEAL_RUMOR`(잡담과 단서 동시 주입 — 불변식 44). 픽스처 17 에서 충돌 0 이므로 경고는 **새 블록·새 게이트가 규칙을 깰 때만** 뜬다.
- 등록 누락은 debug 로 두었다 — 새 블록을 추가하고 레지스트리에 안 넣으면 스펙(`unregistered` 빈 배열 기대)이 먼저 잡는다. 픽스처가 못 덮는 게이트(파티·전투·엔딩 턴)는 실런 debug 로그로 관측.
- 후속(Phase B, 트리거 시): 헤더 상수를 빌더와 레지스트리가 **공유**(지금은 문자열 이중 기재 — 헤더 오타는 스펙이 잡는다) · `when` 을 서술이 아니라 술어로 바꿔 "켜져야 하는데 안 켜진" 방향도 검출.

## 8. T3 — RunState 소프트 슬라이스 (2026-09-08)

§6 의 "HardState / SoftState 로 나눈다" 는 **RunState 자체를 쪼개지 않았다**. 소비처가 수백 곳이라 분리는 재작성이고, 목표는 워커 역류 경계 하나다. 대신 `SoftStateView = Pick<RunState, 소프트 5필드> & { worldState?: Pick<WorldState, 2>; readonly characterName? }` 를 만들고 CAS 단일 쓰기 지점 `RunStatePatchService.apply` 의 콜백 타입만 좁혔다(`patch: (rs: SoftStateView) => boolean`, 내부는 `working as unknown as SoftStateView`). 하드 상태는 뷰에 없으므로 접근이 프로퍼티 부재 오류다.

- **결과**: 기존 CAS 호출 11곳(워커 7·후처리 4)이 **수정 0 으로 통과** — 즉 현재 코드베이스에서 워커 역류가 하드 상태를 건드리는 곳은 없다는 것이 컴파일로 확인됐다. 뷰에 넣은 필드가 곧 불변식 2 의 "등재 목록"이다(npcStates·actionHistory·sceneCutState·nextBeatCandidates·relationships·worldState.companionNpcId/locationDynamicStates·characterName 읽기 전용).
- **스펙** `worker/run-state-patch.soft-state.spec.ts`: `@ts-expect-error` 9줄(hp·gold·inventory·questState·discoveredQuestFacts·equipped·worldState.heat·characterName 쓰기)로 벽을 고정 + apply 의 noop/CAS 경로 mock 2케이스. `@ts-expect-error` 는 jest 가 아니라 tsc 가 검증하므로 `pnpm typecheck:soft-state`(레포 tsc 에는 T3 이전부터 스펙 전용 오류 19건이 있어 이 파일만 필터) 를 둔다.
- **한계 1건(정직하게)**: 이 레포는 `noImplicitAny: false` 라 `rs['gold']` 같은 **대괄호 문자열 접근은 암묵 any 로 통과**한다. 처음 넣은 `@ts-expect-error` 가 "unused" 로 실패해 발견. 점 접근만 막히므로 리뷰에서 대괄호 접근을 금지한다.

## 9. 종합 (2026-09-08)

| | 전 | 후 |
|---|---|---|
| `llm-worker.service.ts` | 6,765 | 3,965 |
| `processTurnInner` | 1,955 | 60 |
| `llm/worker/` 신설 | — | core 758 · patch 64 · postprocess 2,291 · 스펙 73 |
| 프롬프트 블록 정본 | 없음(115 push 산재) | 레지스트리 90 + 배타 3쌍 + 픽스처 스펙 |
| 불변식 2 강제 | 문서·리뷰 | 컴파일(`SoftStateView`) |
| jest | 2,592 | 2,614 (+22) |

검증 사다리는 §4 그대로 3회(T1·T2·T3 각각 build+kickstart+스모크). `prompt-builder`(4,656)·`context-builder`(3,275)·`location-turn`(5,189) 본체 분할은 이번 범위 밖 — 래칫(arch/77 §18) 발화 시 T1 방식(계측→컷-페이스트→tsc 교정→기계 대조)으로.
