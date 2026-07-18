# 77. God Method 리팩토링 계획 — 대형 파일 구조 개선

> 상태: ✅ Phase 1 완료 (2026-07-16) — P1.0 하네스 + P1.0b COMBAT 보강 + P1.1~P1.17 추출 + P1.final (God method **2,838→1,087줄, -62%**). 잔여는 조율 로직 — 의도적 잔존. 다음: Phase 2(context-builder) 또는 P3.X(중복 단일화). 진행 로그는 §9.
> 관련: [[guides/01_server_module_map|server module map]], [[guides/02_client_component_map|client component map]]
> 원칙: 동작 보존 리팩토링(behavior-preserving) — 기능 변경 0, 순수 구조 개선. 각 단계는 독립 커밋 + 회귀 검증 통과가 조건.

## 1. 문제 한 줄 요약

상위 대형 파일들이 큰 이유는 **메서드가 많아서가 아니라, 거대 단일 메서드(God method) 1~2개가 파일 대부분을 차지**하기 때문이다. 한 메서드가 3,000~4,400줄에 달해 가독성·테스트 가능성·변경 안전성이 모두 붕괴한다.

## 2. 실측 대상 (2026-07-16 스캔)

### 2.1 서버 — God method 패턴

| 파일 | 전체 줄 | 문제 메서드 | 메서드 크기 | 파일 내 비중 | 성격 |
|---|---|---|---|---|---|
| `turns/turns.service.ts` | 7,629 | `handleLocationTurnInner` (L1084~) | ~4,440줄 | **58%** | 핵심 턴 로직 (고위험) |
| `llm/llm-worker.service.ts` | 4,762 | `processTurnInner` (L578~) | ~3,503줄 | **74%** | 핵심 서술 파이프라인 (고위험) |
| `llm/prompts/prompt-builder.service.ts` | 3,308 | 프롬프트 빌드 (L61~) | ~2,838줄 | **86%** | 순수 문자열 조립 (저위험) |
| `llm/context-builder.service.ts` | 2,664 | (미상세 — 유사 추정) | — | — | 컨텍스트 조립 (중위험) |

> 참고 건강 파일(분산형, 대상 아님): `runs.service.ts`(1,617), `combat.service.ts`(1,404), `intent-parser-v2.service.ts`(1,250), `content-loader.service.ts`(1,235) — 메서드가 고르게 분산돼 God method 없음.

### 2.2 클라이언트 — God component/store

| 파일 | 전체 줄 | 문제 | 리팩토링 방향 |
|---|---|---|---|
| `components/screens/StartScreen.tsx` | 2,481 | 캐릭터 생성 6단계 위저드 + 54 훅 단일 파일 | 단계별 하위 컴포넌트 분리 (StepPreset/StepPortrait/StepName/StepStats/StepTrait/StepConfirm) |
| `store/game-store.ts` | 2,134 | 단일 Zustand 스토어 103 액션 | slice 패턴 분리 (turn/hud/inventory/npc/party 등) |
| `components/narrative/StoryBlock.tsx` | 1,291 | 서술 렌더 + 마커 파싱 + 타이핑 로직 혼재 | 렌더/로직 분리, 훅 추출 |

## 3. 리팩토링 원칙 (안전 우선)

1. **동작 보존이 최우선** — 기능·출력·부작용 변경 0. 순수 추출(Extract Method/Component)만.
2. **안전망 먼저, 리팩토링 나중** — 대상별 특성 검증 하네스를 먼저 구축한 뒤 손댄다.
3. **작은 단계 + 독립 커밋** — 한 커밋에 한 추출. `pnpm build` + 회귀 검증 통과가 커밋 조건.
4. **추출 방향은 응집도 기준** — 라인 수 균등 분할 금지. 의미 단위(단계·블록·관심사)로 자른다.
5. **서버 코드 = 재시작 세트** — 커밋 시 build + kickstart + `/v1/version` 확인 (CLAUDE.md 규칙).

## 4. 단계 계획 (우선순위)

### Phase 1 — `prompt-builder.service.ts` (시작점, 저위험 고효율)
**왜 먼저**: 출력이 순수 문자열(프롬프트)이라 **골든 스냅샷 테스트**로 리팩토링 전후 바이트 동일성을 보장 가능. 게임 로직 회귀 위험 없음. 여기서 만든 스냅샷 하네스가 이후 단계의 발판.

- **안전망**: 대표 입력 N종(LOCATION/COMBAT/HUB, NPC 유무, 이벤트 유무)에 대해 빌드된 프롬프트 문자열을 골든 파일로 고정하는 스냅샷 테스트 작성.
- **fixture 조립이 진짜 작업 (검토 반영)**: `buildNarrativePrompt` 입력(TurnContext+ServerResult)은 수십 필드 거대 객체 — 손으로 만들지 말고 **실런에서 캡처**한다. 기존 경로 재사용: 턴 상세 `?includeDebug=true`의 `debug.llmPrompt`(2026-07-16 앵커링 진단에 실사용) + playtest `--dry-run` 프롬프트 추출을 확장해 빌더 입력 (ctx, sr)을 직렬화 저장 → 골든 fixture.
- **byte-equality 전제 점검 (검토 반영)**: 착수 시 조립부의 **비결정 소스 사전 스캔** 필수 — 턴 의존 로테이션([이번 턴 감각 초점]·[최근 사용 표현])과 TokenBudget 트리밍은 입력 고정 시 결정론이나, Date.now/비고정 랜덤이 하나라도 섞여 있으면 스냅샷 flaky.
- **추출**: 2,838줄 단일 메서드를 블록별 private 빌더로 분해 (L0 테마 / 세계관 / NPC 감정 / 장소 / 메모리 / 규칙 / 톤 가이드 등). 이미 `injected-block-headers.ts` 블록 헤더 구조가 존재 → 블록 경계 기준으로 자연 분할. `factsParts` push **순서 = 프롬프트 순서**이므로 추출 순서 보존은 스냅샷이 감시.
- **검증**: 스냅샷 전후 동일 → 동작 보존 확정.

### Phase 2 — `context-builder.service.ts` (중위험)
prompt-builder와 짝. 컨텍스트 조립 → 프롬프트 입력. Phase 1 스냅샷 하네스 재사용. 블록별 selector/assembler 추출.

### Phase 3 — `turns.service.ts::handleLocationTurnInner` (고위험, 최대 가치)
**전제**: E2E/스냅샷 안전망 확보 후 착수. 이 메서드는 LOCATION 턴의 intent→event→resolve→commit 전 과정.
- **안전망 기준 (검토 반영 — "충분"의 실용 답)**: 신규 E2E 하네스를 새로 짓지 않는다. 이 레포는 순수 로직을 export 정본+유닛으로 빼는 관례가 확립돼 있고(beat-gravity·npc-agitation.core·EventChoiceGate 등, 전체 1,318 유닛) playtest V1~V10+directionMetrics가 E2E 게이트 역할 — **1차 목표를 "조율 로직의 단계 함수화"로 잡고, 회귀 검증은 기존 유닛 스위트 + playtest 다회(10~15턴 × 2~3런)로 갈음**한다. ServerResultV1 스냅샷은 그 위에 선택적 보강.
- **추출 방향(관심사 단위)**: intent 결정 / 이벤트 매칭 / NPC 결정 / resolve 판정 / fact 공개 / 메모리 기록 / 결과 조립 등 이미 존재하는 서브시스템 경계로 분해. (다수는 이미 별도 서비스 호출 — 인라인된 조율 로직만 추출 대상)
- **스코프 주의 (검토 반영)**: God method는 1개가 아니다 — `handleCombatTurn`·`handleDagNodeTurn`도 수백~천 줄대. 특히 **`nodeResolver.resolve` 호출과 "RunState 반영" 블록이 파일 안에 거의 동일한 형태로 2벌 존재** → 2026-07-16 combatAppraisalNote를 DAG 분기에 오배치했다 옮긴 실사고의 원인. Phase 3 범위에 "동일 파일 잔여 대형 메서드 + 중복 블록 단일화 검토"를 포함한다.

### Phase 4 — `llm-worker.service.ts::processTurnInner` (고위험)
서술 생성 파이프라인(3-Stage + 후처리 다수). Phase 3와 동일 접근 — 단계별(디렉터→메인 LLM→후처리 sanitize 체인) 추출. 후처리 `violations[]` 체인이 유력한 첫 추출 후보 (순수 후처리 — 참조 11곳 실측).
- **추출 금지선 (검토 반영)**: 이 메서드는 순수 조립이 아니라 **부작용 덩어리** — SSE 스트림 브로커 emit 순서, fire-and-forget CAS 패치(`applyRunStatePatch`), **DB UPDATE 순서가 곧 Single Source of Truth인 구간**(nano 선택지 DB/stream desync 봉합 이력 — CLAUDE.md 구현 표), 워커 이중 처리 락(`.returning` 선점). 추출로 await 순서·락 경계가 바뀌면 과거 봉합 버그가 재발한다. **스트림 emit·DB 커밋·락 구간은 1차 추출에서 제외**하고 경계에 주석 명시 후, 순수 후처리(sanitize 체인)부터 뺀다.

### Phase 5 — 클라이언트 (독립 진행 가능)
- `StartScreen.tsx`: 6단계 위저드를 스텝 컴포넌트로 분리. 상태는 상위 유지 or 스텝 스토어.
- `game-store.ts`: Zustand slice 패턴으로 도메인별 분할. **persist 미사용 확인(검토 반영)** — 스토리지 마이그레이션 부담 없음. 단 `game-selectors.ts`가 스토어 형태에 결합 → **공개 훅 시그니처 유지**를 커밋 조건에 포함.
- `StoryBlock.tsx`: 타이핑/마커 로직을 훅으로 추출. StreamTyper once-guard·onComplete 멱등성(스트리밍 렌더 안정화 이력) 보존 주의.

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 턴 파이프라인 회귀(핵심 로직) | Phase 1~2로 안전망·근육 먼저. Phase 3~4는 E2E + 스냅샷 필수 선행 |
| 숨은 부작용(클로저 캡처·순서 의존) | 작은 단계 추출 + 매 단계 build/회귀. 순서 의존 발견 시 문서화 |
| **유사 코드 2벌로 인한 추출 오배치** (검토 반영) | turns.service에 resolve 호출·RunState 반영 블록이 2벌 — 2026-07-16 실사고. 편집 전 `grep -n`으로 대상 분기 유일성 확인, 장기적으로 중복 블록 단일화 |
| **스냅샷 flaky** (검토 반영) | 비결정 소스(Date.now/랜덤/로테이션) 사전 스캔 — 입력 fixture에 turnNo·상태 완전 고정 |
| 대형 diff 리뷰 부담 | 파일당 다중 커밋, 커밋 1개 = 추출 1건 |
| 진행 중 사용자 병행 작업 충돌 | 리팩토링은 대상 파일 단위로 격리, 착수 전 해당 파일 dirty 여부 확인 |
| **리팩토링 후 재비대화** (검토 반영) | ESLint `max-lines-per-function` warn 래칫(신규 코드만) 또는 "새 조율 로직은 단계 함수로" 관례 등재 검토 |

## 6. 미착수 / 열린 질문

- ~~Phase 3/4 착수 전 안전망 수준 결정~~ → **답 확정 (검토 반영)**: 신규 E2E 하네스 없이 기존 유닛 스위트(1,318) + playtest 다회(10~15턴 × 2~3런) + Phase 1 스냅샷을 기준선으로. ServerResultV1 스냅샷은 선택 보강.
- `context-builder`의 God method 실측 미완료 — Phase 2 착수 시 상세 스캔.
- 클라이언트(Phase 5)와 서버(Phase 1~4)의 진행 순서: 독립적이라 병행 가능.
- 착수 시점: arch/75 P7/P8(자율 서사 잔여)·arch/73(시나리오 차별화)과의 우선순위 — 소유자 결정. 근거 참고: God method 구조로 인한 실사고 1건 발생(2026-07-16 combatAppraisalNote 오배치 — §5).

## 7. 착수 순서 요약

```
Phase 1 (prompt-builder, 스냅샷 하네스 구축)  ← 시작점 추천
  → Phase 2 (context-builder, 하네스 재사용)
    → Phase 3 (turns.service God method, E2E 선행)
      → Phase 4 (llm-worker God method)
Phase 5 (클라이언트) — 언제든 병행 가능
```

## 8. 실행 착수 페이즈 & 테스트 범위 (2026-07-16 확정)

각 전략 Phase를 **커밋 단위 실행 스텝**으로 분해한다. 각 스텝은 독립 커밋 + 명시된 테스트 게이트 통과가 조건. `S.0`은 항상 **안전망 선행**(리팩토링 없음, 테스트/하네스만).

### Phase 1 — prompt-builder (스냅샷 하네스 시작점)

| 스텝 | 작업 | 테스트 범위 (게이트) |
|---|---|---|
| **P1.0** | 안전망 구축(리팩토링 0): ① `--dry-run` 확장으로 대표 4~6 fixture 캡처(LOCATION+NPC / LOCATION+event / COMBAT / HUB / 소개턴 / fact공개턴)의 빌더 입력(ctx, sr) 직렬화 저장 ② 비결정 소스 스캔(`Date.now`/`Math.random`/턴 로테이션) — 입력 고정 시 결정론 확인 ③ 스냅샷 스위트 작성: fixture→`buildNarrativePrompt`→golden 문자열 비교 | **신규 스냅샷 스위트**(vitest/jest). 이 스위트 green = P1 전 구간의 유일 게이트. flaky 0 확인이 P1.0 완료 조건 |
| **P1.1~N** | 블록별 private 빌더 추출(커밋당 1블록): L0 테마 / 세계관 / NPC 감정 / 장소 / 메모리 / 규칙 / 톤 가이드. `factsParts` push 순서 보존 | 매 커밋: **스냅샷 스위트 byte-equal** + `pnpm build` |
| **P1.final** | 잔여 정리 + 파일 분할 여부 판단 | 스냅샷 green + 서버 전체 유닛 회귀 + playtest 1런 sanity(서술 정상 생성) |

### Phase 2 — context-builder

| 스텝 | 작업 | 테스트 범위 |
|---|---|---|
| **P2.0** | God method 상세 스캔(§6 미완) + context 출력 직렬화 스냅샷 하네스 | **context 출력 스냅샷** + P1 프롬프트 스냅샷(context→prompt 연쇄라 이중 게이트) |
| **P2.1~N** | 블록별 selector/assembler 추출 | 매 커밋: context 스냅샷 + 프롬프트 스냅샷 byte-equal + build |

### Phase 3 — turns.service::handleLocationTurnInner (고위험)

| 스텝 | 작업 | 테스트 범위 |
|---|---|---|
| **P3.0** | 기준선 확정(리팩토링 0): 기존 유닛 스위트(1,318) green 기록 + playtest 3런(10~15턴) baseline(V1~V10·directionMetrics) 저장. (선택) ServerResultV1 스냅샷 하네스 | 기존 유닛 + playtest 기준선 = 회귀 판정 근거 |
| **P3.1~N** | 관심사 단위 단계 함수 추출: intent 결정 / 이벤트 매칭 / NPC 결정 / resolve 판정 / fact 공개 / 메모리 기록 / 결과 조립. **순수 로직은 export 정본 + 유닛 추가**(레포 관례) | 커밋당: **추출 순수 함수 신규 유닛** + 기존 유닛 green + `grep -n`으로 대상 분기 유일성 확인(오배치 방지) |
| **P3.X** | 중복 블록 단일화 검토: `resolve` 호출 + RunState 반영이 Location/DAG/Combat에 유사 2~3벌(2143·5537·5944) → 공통 헬퍼로 수렴 (별도 신중 커밋) | 단일화 전후 playtest 다회(전 노드 유형 커버) + 유닛 |
| **P3.final** | — | playtest 2~3런 회귀(baseline 대비 지표 불변) |

### Phase 4 — llm-worker::processTurnInner (고위험, 부작용 덩어리)

| 스텝 | 작업 | 테스트 범위 |
|---|---|---|
| **P4.0** | 금지선 마킹(리팩토링 0): 스트림 emit 순서 / DB UPDATE(SSoT) 구간 / fire-and-forget CAS 패치 / 이중처리 락에 경계 주석. 1차 추출 제외 구간 확정 | — (주석·경계만) |
| **P4.1** | `violations[]` sanitize 체인(순수 후처리, 참조 11곳) export 정본 + 유닛 추출 | **sanitize 순수 함수 유닛** + `audit_quality.py`(서술 품질 회귀) |
| **P4.2~N** | 디렉터→메인 LLM 단계 함수화(**부작용 구간 제외**). await 순서·락 경계 불변 | 매 커밋: build + playtest 다회 **V7~V10**(프롬프트 누출·NPC 정합·화자·어체) + 마커/desync 회귀 감시 |

### Phase 5 — 클라이언트 (병행 가능)

| 스텝 | 작업 | 테스트 범위 |
|---|---|---|
| **P5a** | `StartScreen.tsx` 6단계 위저드를 스텝 컴포넌트 분리(StepPreset/Portrait/Name/Stats/Trait/Confirm) | **E2E Playwright**(회원가입→캐릭생성 6단계→게임 진입) + 타입체크 + `/browse` 수동 6단계 확인 |
| **P5b** | `game-store.ts` Zustand slice 분리(persist 없음 — 마이그레이션 무). **공개 훅 시그니처 유지**(game-selectors 결합) | 타입체크 + E2E 게임플레이 1런 + game-selectors 소비처 컴파일 green |
| **P5c** | `StoryBlock.tsx` 타이핑/마커 로직 훅 추출. StreamTyper once-guard·onComplete 멱등성 보존 | `/browse` 스트리밍 렌더 시각 확인(타이핑/마커 회귀) + 타입체크 |

### 테스트 범위 총괄 (계층)

| 계층 | 커버 Phase | 도구 |
|---|---|---|
| **스냅샷**(byte-equal) | P1·P2 | 신규 vitest/jest 스냅샷 스위트 |
| **유닛**(export 정본) | P3·P4 순수 추출분 | 기존 스위트(1,318) + 추출별 신규 |
| **E2E/시나리오** | P3·P4 통합, P5a·P5b | `scripts/playtest.py` 다회 + Playwright |
| **품질 회귀** | P4 | `audit_quality.py` + playtest V7~V10 |
| **시각 회귀** | P5a·P5c | `/browse` 헤드리스 |

## 9. 검토·진행 로그

- **2026-07-16 검토 v1 반영**: 실측 수치 전수 재검증 일치(메서드 경계 4곳·violations 참조 11곳·game-store persist 미사용). 보강 5건 — ① Phase 1 fixture 실런 캡처 경로 ② byte-equality 비결정 소스 스캔 ③ Phase 3 스코프(잔여 대형 메서드·중복 2벌 오배치 리스크) + 안전망 실용 기준 확정 ④ Phase 4 추출 금지선(스트림/DB 커밋/락) ⑤ Phase 5 공개 훅 유지 조건 + 재비대화 래칫.
- **2026-07-16 P1.0** (server 2b97c0a): 스냅샷 하네스 — 실런 캡처 훅(env `PROMPT_FIXTURE_CAPTURE`) + fixture 14개 + golden 587KB. 결정론 2·3회차 검증.
- **2026-07-16 P1.1** (9c22569): 획득 아이템 블록 추출 (buildAcquiredItemsBlock).
- **2026-07-16 P1.0b** (698ae46): **COMBAT fixture 3종 보강** — P1.0이 HUB/LOCATION만 캡처해 전투 분기([전투 장면] 디렉티브·isCombat 게이트·기만 전술) 무방비였던 갭 보완. 진입 SYSTEM / DISTRACTION+도주 / FEINT 지속. 캡처는 launchd bootout → env 기동 → 전투 시나리오 → 복구 절차.
- **2026-07-16 P1.2~P1.10** (e29920a..839077c, 커밋당 1블록): 대화 행위 톤 가이드 / 창의 행동 재해석 4종 / Nano 이벤트 컨셉 / NpcReaction P0 / 직전 NPC 발화(105줄) / 대화 단계 카운터 / 행동-반응 매핑(70줄) / 대화 연속 상태 / NPC 등장 주입(156줄). 매 커밋 스냅샷 17개 byte-equal + build. **God method 2,838 → 2,250줄 (-21%)**. 전체 1,336 passed·린트 0·재시작 확인(839077c).
- **2026-07-16 P1.11~P1.17** (커밋당 1블록, ..be84b1b): NPC 로스터(244줄, **탈출 상태 targetNpcIds는 반환값으로 공유**) / Narrative Engine(98줄) / 플레이어 행동(178줄) / 문체·초점(106줄) / L0~L1 메모리 묶음(316줄) / 턴 결과(140줄) / NPC 대화 자세(118줄). 숨은 외부 의존(sr·useJsonMode·isQuestionTurn)은 tsc가 검출 → 파라미터로 명시화. **God method 2,838 → 1,087줄 (-62%)**.
- **2026-07-16 P1.final**: 전체 1,336 passed·린트 0·재시작(be84b1b) + playtest 8턴 sanity 9/10 (V2는 단축런 특성, 서술 품질 V7~V10 전부 green). **파일 분할 판단: 보류** — 추출 빌더들이 content/tokenBudget 의존을 서비스와 공유해 응집. 파일(3,583줄)이 부담되면 `prompts/blocks/` 이관은 후속 선택지.
- **잔여 (의도적 잔존)**: 시스템 프롬프트 병합/파티 모드/JSON 스키마/Token Budget 트리밍/witness·agitation·전투 디렉티브 등 조율 로직 ~1,087줄 — 코디네이터 메서드의 본래 몫. 2단계 다듬기(서명 축소·순수 함수화·블록별 유닛)는 필요 시 별도 사이클.
- **2026-07-17 P3.X** (server 7d73520): 중복 단일화 — **조사 결과 정정: "resolve+RunState 반영 2벌"은 통째 중복이 아니라 시맨틱이 다른 유사 코드**였다 (DAG gold `+=` 무바닥 vs COMBAT `max(0,…)` 0-바닥 / hp가 delta+clamp vs battleState 절대값 / 아이템 출처 상이). 통일 시 동작 변경이라 보류하고: ① 실제 동일 중복인 **인벤토리 수량 병합 5곳**(LOCATION 보상·스크립트 보상·상점 구매·DAG 구매·전투 획득)을 `run-state-apply.core.ts::mergeInventoryItem`으로 수렴(유닛 3종) ② resolve 호출 2곳에 **경로 식별 주석**(오배치 실사고 재발 방지) ③ **잠재 결함 기록**: DAG 경로 gold 무바닥(음수 가능) — 동작 보존 원칙상 미수정, 별도 판단 필요. 검증: 1,339 passed·실런 8턴(상점 구매 gold 20→10 실증)·재시작 7d73520.
- **2026-07-17 P2.1~P2.3** (server 543d4f0): **Phase 2 착수** — context-builder `build()` 블록 추출 3건: Fact Pool 4-mode 분기(buildFactPoolContext, 145줄) / 장면 연속성(buildSceneContinuityContext, 194줄) / NPC 개인 기록 선별(buildRelevantNpcMemoryText, 68줄). **build() 1,528 → 1,065줄 (-30%)**. 하네스 판단: build()가 DB 다중 조회 + 7서비스 의존이라 P2.0 캡처-리플레이 스냅샷은 비용 초과 — Phase 3에 확정된 실용 기준(기존 유닛 스위트 + playtest 게이트)을 Phase 2에 적용. 각 스텝 후 전체 1,373 유닛 그린, 암묵 클로저 의존(focusedNpcId)은 tsc 검출 → 파라미터 명시화. 잔여 P2.4~N 후보: HUB/WorldState(~120줄)·Narrative Engine(~105줄)·L0~L3 메모리 로드(~120줄)·보조 NPC 억제(~45줄).
- **2026-07-17 P2.4~P2.7** (server fc8e4d0): Phase 2 트랜치 2 — buildWorldContext(122줄) / buildNarrativeEngineContext(105줄) / buildAuxSuppressionContext(43줄, arch/57) / loadMemoryLayers(121줄, L0~L3 DB 조회 묶음). **build() 1,528 → 707줄 (-54%)**. 암묵 의존 3건 컴파일러·린터 검출 → 명시화(focusedNpcId·turnNoForNames 파라미터, 미사용 serverResult 2건 제거). 전체 1,373 유닛·린트 0/0. 트랜치 1(P2.1~P2.3, 543d4f0)의 playtest 게이트에서 **V10 1건은 센서 FP로 확정** — EventChoiceGate가 캐시 오염 수정(21424bc) 후 깨끗한 콘텐츠 NPC로 첫 실발동한 정상 폐기 턴을 과탐 → V10에 "이벤트 선택지 실노출" 조건 추가(docs ba38215). 잔여 소블록(resolveOutcome·Deadline·소개 상태·PR2~4·프리셋 배경 ~118줄)은 코디네이터 잔존 기준으로 1차 마감 — 추가 추출은 필요 시.
- **2026-07-18 P2.8~P2.10 + Phase 2 마감** (server 3f38086): buildProtagonistBackground(115줄) / buildPreviousVisitContext(22줄, structured를 StructuredMemory 실타입으로 정밀화) / collectIntroductionState(23줄, 2턴 분리 가드). **build() 1,528 → 553줄 (-64%) — Phase 1(-62%)과 동급, 잔여(resolveOutcome·Deadline·PR2~4 위임·최종 조립)는 코디네이터 잔존 기준으로 마감**. 전체 1,374 유닛·린트 0. 게이트: 에이전트 2런 15턴 (결과는 아래 갱신).
- **2026-07-18 P3.0 + P3.1~P3.12 (Phase 3 트랜치 1)** (server 003c180..26ff407, 커밋당 1스텝): **P3.0 기준선** — 유닛 1,374 green + playtest 3런 12턴(coercer/chatty/weirdo) 전부 V1~V10 10/10 PASS, JSON은 `playtest-reports/arch77-p3-baseline/` 저장. **추출 12스텝**: HP≤0 패배 엔딩(93줄, handleDefeatByHpZero) / **HUB 복귀 2벌 단일화**(go_hub·MOVE fallback 각 85줄이 문구만 다른 실제 동일 중복 → returnToHubFlow) / Narrative 틱·사건·전설 보상 묶음(195줄, applyNarrativeTicksAndRewards — 하류 소비 3건은 반환값) / nanoCtx 빌드(180줄, buildNanoEventContext) / Layer 3 목격 반응(86줄, collectWitnessReactions) / 돌발행동 감정(53줄, applySuddenActionEmotions) / **Quest Progression(528줄 — 최대 단일 블록**, processQuestProgression, 출력 5종 반환) / 보상 지급 묶음(130줄, applyLocationRewards) / SHOP(163줄, processShopAction) / primary NPC 감정·행동화·기록(287줄, updatePrimaryNpcEmotionAndRecords — D3-b′/c′ 포함) / 결과 UI 조립(198줄, assembleResultUi) / 주입 NPC 보충(73줄, applyInjectedNpcRecords). **handleLocationTurnInner 4,440 → 2,513줄 (-43%)**. 암묵 의존은 tsc·lint 검출로 명시화(NON_TOPIC_FALLBACK_REVEAL_CHANCE 재구조분해, finalWs 불변 단언 등). 중간 게이트(P3.7 시점) coercer/weirdo 12턴 각 10/10, **P3.final 게이트(26ff407 재시작 후) chatty/brawler 12턴 각 10/10 — baseline 대비 지표 불변, 트랜치 1 마감**. **잔여 트랜치 2 후보**: Step 1~3 턴 모드+비트 채택+이벤트 매칭(~470줄 — 불변식 47·48 심장부라 별도 신중 커밋), Marks~history 전이 조율(~110줄)·Structured Memory 수집(~58줄)은 코디네이터 잔존 판단 여지. handleCombatTurn/handleDagNodeTurn은 미착수.
- **2026-07-18 P4.0~P4.2 (Phase 4 트랜치 1)** (server 9dcd096..e52898e): **P4.0 금지선 마킹** — 이중처리 락(조건부 UPDATE 원자성)/스트림 emit 순서(타이핑·R7 결합)/DONE+finalChoices SSoT 커밋(desync 봉합 이력)/CAS 패치(lost-update 방벽) 4곳 경계 주석, 코드 무변경. **P4.1** — violations[] 서술 품질 체인(플레이어 대사 방어→P1 접근→P1b 메타→R1 회피 어휘→P4 미소개 실명→P5 경어체→P6 opening→중복 제거, 266줄)을 `narrative-filter.core.ts::applyNarrativeQualityFilters` export 정본으로 이동 + 유닛 11케이스. **발견: P5 서술 경어체→해라체 규칙은 JS `\b`가 한글 뒤 불성립(ASCII `\w` 기준)이라 원본 시절부터 한 번도 발화한 적 없는 죽은 규칙** — 동작 보존 원칙으로 코드 유지·유닛으로 현재 동작 고정, 수정 여부 별도 판단. **P4.2** — 5.10.5~5.10.10 마커·표기 정리 시리즈(120줄)를 `cleanupNarrativeArtifacts`로 이동 + 유닛 5케이스, insertSpaceAfterSentenceCore 정본 core 이사(워커 re-export). 전체 1,390 유닛·린트 0. **게이트 + V9 조사**: chatty 10/10·weirdo 1런 V9 FAIL → 원인 규명 — "약초"(기행 장면 중심 사물)·"책임자는"(별칭 서술) 명사 반복으로, 치환 규칙 목록에 없어 추출 필터의 처리 대상 자체가 아님 + baseline 3런 동일 검사 0건 + [NarrativeFilter] 실발화 로그 확인 + **P4.2 반영 weirdo 재런 10/10 PASS** → flaky 콘텐츠성 반복 확정, 회귀 아님. 잔여 P4.3~N 후보: 5.5 마커 삽입 대단위·5.11 소개 롤백·5.13 speakingNpc 재결정(부작용 섞임 — 신중 커밋), 금지선 4곳은 항구 제외.
- **2026-07-18 P4.3~P4.5 (Phase 4 트랜치 2)** (server 7c7b111..608fc81): 부작용 섞인 3블록을 **CAS/DB 호출 구조를 그대로 품은 통째 이동**(패치 단위·시맨틱 불변 — 금지선 준수 방식)으로 추출 — **P4.3** 5.11 소개 롤백·확정(258줄, rollbackOrConfirmIntroductions — 성사 판정→자기소개 삽입/별칭 교정→IntroFallback→롤백 + appearanceCount·제스처, narrative 변조는 반환값 회수) / **P4.4** 5.13 speakingNpc·카드 재결정(189줄, reconcileSpeakingNpcAndPortrait — 완전형 마커 역해석·LockSeed CAS·카드 교체/제거) / **P4.5** narrativeThemes 기록(80줄, recordNarrativeThemes). **processTurnInner 3,503 → 2,647줄 (-24%)**. 게이트: chatty/coercer 12턴 각 10/10 + 추출 경로 실발화 로그(LockSeed·ThemeRecord) 교차 확인. **잔여**: 5.5 nano 마커 삽입 대단위(~900줄)는 스트리밍 sanitize와 결합된 최대 위험 구간 — 별도 트랜치 필수, 금지선 4곳 항구 제외.
- **2026-07-18 P4.6 + Phase 4 마감** (server cbf2e74): **5.5 nano 마커 삽입 대단위(920줄) 추출 — insertDialogueMarkers**. Step A(nano 발화자 판단+regex fallback) → B(표시명 변환) → C(실명 세이프가드) → D(도입 트리밍) → E(프리픽스 제거) → F/F-0(불일치 교정) → F-aux(focused 억제) → 마커 합쳐짐 복구. 스트리밍/JSON 모드 게이트(hasDialogue) 원 시맨틱 유지, narrative + 수집물 4종(appearedNpcIds/portraits/npcStatesRef/getNpcDisplayNameFn — 5.11 롤백·5.13 카드가 소비)을 반환으로 회수. 외부 의존은 기계 스캔으로 7종 확정(messages·lightConfig·runState는 오탐 — 객체 키/내부 선언). **processTurnInner 3,503 → 1,746줄 (-50%)**, 파일 4,537줄. 게이트: chatty/coercer/weirdo 12턴 **3런 전부 10/10 PASS·위화감 0** + 추출 경로 실발화 로그(DialogueMarker·FocusedAuxStrip·LockSeed·NarrativeFilter) 교차 확인. **Phase 4 1차 마감** — 잔여(5.12 작별·5.12.5 재탕 센서·4-b/c/d 메모리 저장·Track 2·금지선 4곳 ~1,746줄)는 코디네이터 본연 몫. 유닛 1,390·린트 0.
- **2026-07-18 전투/DAG 트랜치 (C1~C5)** (server 0a75653..16c53e3): **C1 — DAG 골드 무바닥 결함 수정**(P3.X 기록분 해소: LOCATION/COMBAT과 동일한 Math.max(0,…) 0-바닥으로 통일, SHOP 리졸버 잔액 검증은 있으나 타 노드 goldDelta 방어선 부재였음 — 유일한 의도적 동작 변경) / **C2** 전투 입력 파이프라인(105줄, buildCombatActionPlan — RuleParser→Policy DENY 조기 커밋→ActionPlan→PropMatch Tier→기만 전술 nano, usedTactics 제자리 변조) / **C3** 적 스탯 로드(21줄, loadEnemyStatsForBattle 순수) / **C4** 승리 장비 드랍(54줄, applyCombatVictoryDrops — 시드 결정론 유지) / **C5** 패배 엔딩(90줄, handleCombatDefeatEnding). **handleCombatTurn 544 → 319줄 (-41%)**, handleDagNodeTurn은 255줄로 코디네이터 잔존 판정(전이 조율 본연 몫). 게이트: coercer 10/10 / brawler 9/10 — **V9 1건은 COMBAT 0경유 런(HUB 3+LOCATION 9)의 날씨 수식어('젖은') 편중 = 변경 코드 미실행이라 인과 불가, flaky 확정**. 전투 라이브 조우는 트리거 조건(FAIL+BLOCK/CRITICAL) 특성상 미발생 — 유닛(전투 코어 스펙 포함 1,390)·동작 보존 컷-페이스트·tsc로 커버 (COWARDLY 스펙 대체 전례와 동일).
- **2026-07-18 P3.13 (트랜치 2)** (server 773561c): **Step 1~3 추출 — determineTurnEventAndRouting(473줄)**. 씬 연속성(CHOICE sourceEventId) → IncidentRouter → 턴 모드 3분류(불변식 33·47 가드 일체: 사교/REST 억제·강제창·연속 상호작용 비트 게이트) → 모드별 매칭(비트 채택+동적 NPC 등록/SitGen/EventDirector/Procedural) → FREE 셸 보장. **추출 전 하류 전수 스캔으로 블록 밖 소비가 matchedEvent·routingResult 2종뿐임을 확인** — 나머지 로컬 16종(turnMode·beatAvailable·contextNpcId 등)은 전부 블록 내부 전용이라 경계가 예상보다 깨끗했다. 딥카피 초크포인트(불변식 48)는 의도적으로 호출부(Inner)에 잔존 — "캐시 참조 반환 → 소비 전 클론" 규약이 호출부에서 보이도록. **Inner 4,440 → 2,061줄 (-54%)**. 게이트: 유닛 1,374 green + 재시작(773561c) 후 baseline 동일 3페르소나(coercer/chatty/weirdo) 12턴 — **3런 전부 V1~V10 10/10 PASS·위화감 노트 0, D4-3/3b baseline 범위 내. 손실 없음 판정, revert 불필요**. 잔여: Marks~history(~110줄)·Structured Memory 수집(~58줄)은 코디네이터 잔존 기준으로 보류, 전이·엔딩·커밋 조율 ~2,061줄이 코디네이터 본연 몫.
