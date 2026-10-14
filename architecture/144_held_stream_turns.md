# 144. 보류 스트림 턴 — 분석과 수정 계획

> 상태: P1~P4 구현 (2026-10-13), P5 구현 (2026-10-14 §14). 선행: arch/141(지연 계측)·143(사전 결정·첫 조각). 계측 `[StreamHold]` 는 운영에 남긴다.

## 1. 문제

서술 스트림은 몇몇 조건에서 **보류**된다. 보류된 턴은 모델이 서술을 다 쓴 뒤 완료(`done`) 시점에 한 번에 보인다. 완료 시점에 서술을 고쳐 쓰는 후처리가 예정된 턴에서, 고치기 전 원문(오답·지울 문단)이 화면에 먼저 흐르지 않게 하려는 장치다. 대부분 9월 말 근거 정합 작업(arch/123 N-13)에서 들어왔고, 당시 모델은 단서를 뒤집어 말하는 일이 있었다.

비용은 크다. 측정 런의 장소 대화 턴 기준으로 보면 다음과 같다.

| 턴 | 클라이언트 첫 글자 |
|---|---|
| 스트리밍 턴 | 약 3.5초 |
| 보류 턴 | 완료 시점 9~12초 (한 번은 20초) |

워커 기준으로는 보류 턴의 첫 표시가 서술 생성 + 후처리(중앙값 3.7초, 2.5~5.4초)이고, 스트리밍 턴의 첫 조각은 중앙값 1.6초다. 장소 대화 턴은 서술이 길어서 차이가 더 벌어진다.

## 2. 보류 조건 11가지 (워커 `stageGenerate`)

| 사유 | 짝이 되는 완료 시점 교정 | 교정 위치 |
|---|---|---|
| `withheldNextStep` | `ensureWithheldNextStepCore` — NPC 가 다음 확인 행동을 말하지 않았으면 대사 한 줄 덧붙임 | **끝에 추가** |
| `reconfirm` | `reconfirmKnownFactAnswerCore` — 재질문에 대상 NPC 첫 대사를 정본으로 교체 | 대상 NPC 첫 대사 (안 했으면 맨 앞 삽입) |
| `revealDirect` | 같은 함수 — 최초 공개 정본 교정 | 같음 |
| `playerKnownFact` | `groundCountedRecordNarrativeCore` — 근거 없는 인원 수 등이면 전체 폐기·대체 | 전체 |
| `spokenFactMedium` | `groundUnrevealedSpokenFactQuoteCore` — 미공개 구술 단서 원문 인용 시 전체 대체 | 전체 |
| `evidenceBoundary` | `renderUnconfirmedEvidenceResponseCore` — **항상** 템플릿으로 전체 교체 | 전체 |
| `hubDestination` | `applyFirstHubReturnNarrativeCore`(2턴째 거점 귀환 → 저작본 전체 교체) · `condenseHubTravelNarrativeCore`(지난 장소 문단 제거) | 전체 / 앞 문단 |
| `moveLocation` | `condenseSimpleMoveDepartureCore` — 출발 동작 중심 재구성 | 전체 |
| `compoundFight` | `ensureCompoundFightAttemptsCore` | — |
| `arcStage` | 아크 스테이지 결말 서술 | — |
| `eventSubsceneLead` | `ensureSubsceneBridgeCore` | — |

## 3. 실측 — 보류가 실제로 막은 것

계측: 보류 사유를 이름으로 돌려주는 `narrativeStreamHoldReasonsCore`(판정은 기존과 동일)와 `[StreamHold]` 로그(사유·모델 원문 대비 최종본 유사도)를 넣었다. 그레이마르 선택지 2런 + 대화 에이전트 1런 + 별빛모래 2런, 65턴을 돌렸다.

| 사유 | 보류 턴 | 글이 실제로 바뀐 턴 | 바뀐 내용 |
|---|---|---|---|
| (보류 없음) | 47 | 1 (유사도 0.966, 일반 후처리) | — |
| `hubDestination` | 8 | **2** | 둘 다 별빛모래 T2 첫 귀환 — 모델 원문을 버리고 저작본(83자)으로 교체 |
| `spokenFactMedium` | 5 | 0 | — |
| `moveLocation` | 3 | **1** | 출발 동작 중심 축약 (337→134자) |
| `withheldNextStep` | 2 | 0 | — |

10월 5일 이후 서버 로그 전체(스트리밍 턴 277개)에서도 교정 태그는 5번뿐이었다.

| 교정 | 적용 횟수 |
|---|---|
| `[RevealedFactAnswer]` | 2 |
| `[KnownFactAnswer]` | 1 |
| `[HubTravel]` | 1 |
| `[FirstHubReturn]` | 1 |
| `[EvidenceGrounding]`·`[WithheldNextStep]`·`[MoveDeparture]`·`[SubsceneBridge]` | 0 |

앞선 선택지 측정(arch/143)의 보류 턴 30개는 이렇게 나뉘었다.

| 보류 턴 | 수 | 짐작되는 사유 |
|---|---|---|
| 거점 이동 T2 | 19 | `hubDestination` |
| 장소 단서 대화 | 11 | `revealDirect`·`reconfirm`·`withheldNextStep`·`spokenFactMedium` (사유 로그 도입 전) |

실유저 60일 107턴 중 DB 에서 계산 가능한 사유는 거점 이동 8, 장소 이동 2, 단서 직접 공개 1이다(표본이 작아 참고만).

**결론**
- **단서 대화 쪽:** 보류의 대부분이 고칠 것이 없는 턴을 붙잡고 있다. 고칠 일이 생겨도 고치는 곳은 **대상 NPC 의 대사 한 줄**이다(`withheldNextStep` 은 끝에 덧붙일 뿐).
- **이동 쪽:** 실제 교정이 일어난다. 그중 첫 귀환은 **생성 전에 이미 결과가 정해져 있다**(저작본 전체 교체). 그런데도 모델을 불러 4초를 기다린 뒤 그 결과를 버린다.
- **클라이언트:** 완료 시점에 버퍼를 최종본으로 교체한다(`game-store.helpers` `onDone`). 따라서 앞부분만 흘려보낸 경우, 그 앞부분이 최종본과 같으면 교체가 자연스럽다.

## 4. 수정 계획

### P1. `withheldNextStep` 보류 해제 (낮은 위험)

교정이 끝에 한 줄을 덧붙이는 것뿐이라, 스트리밍한 글이 최종본의 앞부분과 같다. 해당 턴은 보류 사유에서 뺀다.

### P2. 화자 게이트 부분 스트리밍 (중간 위험, 가장 큰 효과)

대상: `reconfirm`·`revealDirect`·`playerKnownFact`·`spokenFactMedium`.

- 이 사유들로만 보류되는 턴은 전체를 붙잡지 않는다. **대상 NPC 의 첫 대사 조각이 나오기 직전까지는 흘려보내고**, 그 조각부터 끝까지만 완료 시점에 보인다.
- 대상 NPC 는 단서 공개 NPC(`questReveal.npcId`)·재질문 NPC(`npcAskedKnownFact.npcId`)·주 화자(`primaryNpcId`) 순으로 정한다.
- 판정은 구조화 스트림 이벤트의 화자 ID(`StructuredNarrativeStream` 이 이미 해석)로 한다.
- 화자가 해석되지 않은 대사(무명 라벨)가 먼저 나와도 거기서 멈춘다. 대상 NPC 일 가능성이 있기 때문이다.

기대: 장소 단서 대화 보류 턴의 첫 글자가 9~12초에서 일반 턴 수준(약 3.5초)으로 내려간다. 대부분의 응답이 서술 → NPC 대사 순이기 때문이다.

남는 위험과 처리:
- **전체 폐기형 교정**(`playerKnownFact`·`spokenFactMedium` 이 막힐 때): 흘려보낸 서술까지 대체문으로 바뀐다. 관측 0건이다. 발생하면 `[StreamHold] gatedReplaced` 로 센다.
- **"대상 NPC 가 말하지 않음 → 맨 앞에 답변 삽입"**: 흘려보낸 서술 위에 대사가 끼어든다. 교정 함수에 "첫 서술 문단 뒤에 삽입" 옵션을 두어, 흘려보낸 앞부분은 유지되게 한다.

### P3. 첫 귀환은 모델 호출 없이 바로 표시 (중간 위험)

- `applyFirstHubReturnNarrativeCore` 조건(2턴째·선택지·목적지 = 거점 장소·저작본 있음)은 생성 전에 판정된다.
- 이 턴은 서술 모델을 부르지 않고 저작본을 서술 이벤트로 바로 보낸다. 서술 호출 1회(약 4초·턴 비용 대부분)를 아낀다.
- 서술 결과를 쓰는 후속 단계(선택지 Track 2·단서 추출·장면 컷)가 저작본으로도 정상 동작하는지 확인이 필요하다. 지금도 최종 서술은 저작본이므로, 바뀌는 것은 "모델 원문이 없다"는 점뿐이다.

### P4. 이동 서술은 보류 유지 + 근본 원인 조사 (후속)

- `hubDestination`(첫 귀환 외)·`moveLocation` 은 실제로 교정이 일어나고(앞 문단 제거·출발 중심 재구성), 교정이 앞부분을 바꾸므로 부분 스트리밍이 맞지 않는다.
- 이동 서술은 짧아 보류 비용이 약 2초다.
- 근본 해결은 프롬프트에서 이동 서술 구조(목적 → 출발 → 도착)를 정하게 해 축약 적용률을 0에 가깝게 만드는 것이다. 적용률을 `[StreamHold]` 로 확인한 뒤 보류 해제를 판단한다.

### P5. 그대로 둠

- `evidenceBoundary`: 항상 전체 교체 — 관측 0건. 서술 호출 생략은 P3 이후 같은 방식으로 검토한다.
- `arcStage`·`compoundFight`·`eventSubsceneLead`: 관측 0건, 희귀.

### 공통

- `[StreamHold]` 계측을 운영에 남긴다. 부분 스트리밍 턴은 `gated=true firstEmit=…` 를 추가로 찍는다.
- 기존 `shouldHoldNarrativeQualityStreamCore` 는 사유 함수로 대체되어 사문이 된다. 스펙을 사유 함수 기준으로 옮기고 삭제한다.

## 5. 검증

- **단위:** 사유 함수 동등성(기존 판정과 같음), 화자 게이트(서술만 흘리고 대상 대사부터 보류 / 무명 대사에서 멈춤 / 대상 NPC 가 말하지 않음), 첫 귀환 모델 호출 생략.
- **실측:** 선택지 런 3회 + 별빛모래 1회.
  - 장소 단서 대화 턴의 첫 글자.
  - 보류 사유 분포.
  - 부분 스트리밍 턴에서 흘려보낸 부분이 최종본에서 바뀐 경우 = 0 확인 (모델 원문 대비 최종본의 앞부분 일치).
- **완료 화면 회귀:** 클라이언트에서 완료 시점 교체가 자연스러운지 `/qa` 로 실제 브라우저 확인.

## 6. 구현 결과 (2026-10-13)

T1~T4 구현. 변경: `narrative-quality-stream-hold.core`(사유에서 `withheldNextStep` 제거, `narrativeStreamModeCore`·`GATEABLE_HOLD_REASONS`, 구 `shouldHoldNarrativeQualityStreamCore` 삭제), `speaker-candidates.core`(`SegmentEvent.speakerNpcId` 내부 필드), `structured-narrative-stream.core`(대사 이벤트에 화자 ID), `llm-worker.service`(모드별 송출·게이트·SSE 전 ID 제거·첫 귀환 단락·`[StreamHold] mode=… prefixKept=`), `known-fact-answer.core`(`insertAfterFirstNarration`), 런타임 플래그 `NARRATIVE_STREAM_GATE_DISABLED`. 스펙 신설 `llm-worker.stream-gate.spec.ts` 8건 + 기존 스펙 확장, 전체 3,311 passed. 수정을 하나씩 되돌리면 해당 스펙이 실패함을 확인(게이트 미차단·무명 대사 통과·ID 누출·첫 귀환 미단락·킬스위치 'true' 무시).

**실측** — 그레이마르 선택지 3런(장소 턴 30) + 별빛모래 1런(8턴):

| | 변경 전 | 변경 후 |
|---|---|---|
| 그레이마르 장소 턴 중 보류(첫 글자 = 완료) | 선택지 런마다 1~3턴, 첫 글자 9~12초 | **0턴** (첫 조각 2.8~4.7초) |
| 부분 스트리밍 턴 | — | 4턴 (`revealDirect` 1·`spokenFactMedium` 3), 흘린 서술 3~5조각, **4턴 모두 `prefixKept=true`** |
| 그레이마르 T8 단서 직접 공개 턴 첫 글자 | (같은 유형 보류 시 10초대) | 3.43초 |
| 별빛모래 T2 첫 귀환 | 모델 4초 생성 후 원문 폐기·저작본 일괄 | **워커 23ms**, 서술 호출 0 |
| 보류 유지 | — | 거점 이동·장소 이동만 (계획대로 P4 대상) |

이번 런에서는 완료 시점 단서 정본 교정이 발동하지 않았다(교정이 실제로 흘린 글과 충돌하는 경우의 화면은 미관측). 실제 브라우저 확인은 로그인이 필요해 미수행 — 소유자 로그인 후 `/qa` 또는 수동 확인이 남았다.

### 6.1 커밋 전 `/review` 후속 (2026-10-13, server `c456253`)

- **[CRITICAL] 서술로 새는 미공개 단서** — 근거 검사는 대사뿐 아니라 서술도 훑는데, 첫 게이트는 대사만 막았다. 부분 스트리밍 턴은 서술 조각을 보내기 전에 지금까지 흘린 서술 + 이번 조각에 완료 시점과 같은 검사(미공개 구술 인용·인원·기록 주장·기록 주장)를 **같은 조건으로** 돌리고, 걸리면 그 자리에서 게이트를 닫는다.
- **[CRITICAL] 조각 안 줄바꿈을 공백으로 잇던 문제** — 앞줄 부정어가 다음 줄 주장을 가렸다. 서술 조각에 내부 필드 `endsLine` 을 붙여 원문 줄바꿈 그대로 잇는다(SSE 전 제거, 페이로드 어서션은 줄바꿈 조각에서 mutation 확인).
- 부분 스트리밍 턴의 재확인 답은 서술 **끝**에 붙인다(`insertAt: 'end'`) — 이미 흘린 앞부분과 어긋나지 않게.
- 킬스위치 판정 `flagIsOn`(`'1'`·`'true'`, 공백·대소문자 무시)으로 통일 — `NPC_REACTION_SPECULATIVE_DISABLED` 도 같은 헬퍼.
- 건너뜀: 2턴째 저작본 귀환 턴의 기록 정리.
- 최종 빌드 별빛모래 실런: T2 저작본 즉시 송출, T5~T7 `gated`(`spokenFactMedium`) 3턴 모두 `prefixKept=true`·sim 1.000, 이동·거점 이동은 `hold`. 전체 3,328 passed·스모크 PASS. 레드팀·브라우저 QA·Codex 외부 검토는 미수행.


## 7. P4 이동 턴 스트리밍 (2026-10-13)

**교정 빈도 실측** — 이동 축약 두 가지는 모두 3문단 이상일 때만 걸린다.

| 구간 | 거점 이동(go_*) | 장소 이동(MOVE_LOCATION) |
|---|---|---|
| 10/5 이후 턴 | 93 | 10 |
| 실제 축약 (`[HubTravel]`·`[MoveDeparture]` 로그) | 1 | 1 |
| GPT-6 Luna 이후(10/12~) 최종본 3문단 이상 | 0 / 37 | 2 / 6 (축약 조건 불충족으로 원문 유지) |

축약된 장소 이동 1건은 직접 입력("다른 장소로 이동한다")이었고, 이 경로의 프롬프트에는 분량 지시가 없었다(거점 이동·선택지 이동에는 "1문단 2~3문장"이 이미 있다).

**변경**
- `hubDestination`·`moveLocation` 을 흘려도 되는 사유(`STREAMABLE_HOLD_REASONS`)로 둔다. 이 사유뿐이면 `stream`, 단서 사유와 섞이면 `gated`, 그 밖의 사유와 섞이면 `hold`. 킬스위치 `NARRATIVE_STREAM_GATE_DISABLED` 를 켜면 예전처럼 보류한다.
- 완료 시점 이동 축약(`condenseMoveNarrative` 로 묶음)은 이미 흘린 글이 있으면 건너뛰고 `[MoveDeparture]`/`[HubTravel] … 송출분 보존 — 축약 생략` 경고로 센다. 축약은 앞 문단을 지우거나 문장을 재조합해서, 흘린 글과 어긋나기 때문이다.
- 첫 귀환 저작본(P3) 송출도 송출분으로 기록한다. 기록하지 않으면 완료 시점에 저작본이 축약될 수 있다.
- 직접 입력 이동 턴 프롬프트에 "1문단 2~3문장"을 추가했다. 구성 요소만 지시하고 예시 문장은 넣지 않았다(불변식 50).
- `[StreamHold]` 의 `prefixKept` 를 이동 사유로 흘린 턴에도 찍는다.

**실측** — 그레이마르 선택지·대화 에이전트·별빛모래 각 1런(8턴):

| | 변경 전 | 변경 후 |
|---|---|---|
| 이동 턴 첫 조각(워커) | 완료 시점 3.3~4.9초 | **1.4~1.9초** (공급자 첫 토큰이 늦은 1턴 5.8초) |
| 이동 턴 6개 | 보류 | 전부 `stream`, `prefixKept=true`, sim 1.000 |
| 축약 생략 경고 | — | 0건 |
| 직접 입력 이동 턴 문단 수 | 3문단 이상 → 축약(337→134자) | 1~2문단 |

스펙: 모드 코어(이동만 → stream·섞이면 gated/hold·킬스위치), 워커(이동 턴 전량 송출·거점 목적지 송출·킬스위치 보류·저작본 송출 기록·흘린 턴 축약 생략), 기존 "이동이 섞이면 hold" 테스트는 진짜 보류 사유(복합 공격)로 바꾸고 "이동+단서 공개 → gated"를 추가했다. 세 변경을 각각 되돌리면 스펙이 실패함을 확인. 전체 3,336 passed.

**남는 것**
- 흘린 턴에서 축약이 생략되면 3문단 이상 이동 서술이 그대로 남는다. 경고 로그로 빈도를 보고, 늘어나면 프롬프트를 다시 본다.
- 별개 관측: 공급자 빈 스트림(0토큰)으로 비스트림 재호출된 턴이 451회 중 3회(0.7%)다. 그 턴은 첫 글자가 14~16초다(이번 대화 에이전트 런 T1·T3).
- 아직 보류되는 사유: `evidenceBoundary`(P5)·`arcStage`·`compoundFight`·`eventSubsceneLead` — 모두 관측 0건.


## 8. 빈 스트림 재시도 (2026-10-14)

10/12~13 구조화 스트림 451회 중 3회(0.7%)가 콘텐츠 0토큰으로 정상 종료했다(`빈 스트림 응답`). 이때 곧바로 non-stream JSON 재호출로 넘어가 그 턴의 첫 글자가 14~16초였다. 구조화 스트림 실패는 이 3건이 전부다(첫 토큰·정체 타임아웃 0건). 3건 중 2건은 같은 런의 거점 이동 턴과 도착 턴이 거의 동시에 스트림을 연 경우였지만, 1건은 단독이라 원인은 확정하지 못했다.

**변경**
- 공급자: 빈 스트림을 `EmptyStreamError` 로 던지고, 청크 수·`finish_reason`·`refusal`·스트림 내 `error` 필드·헤더 도착 시간·총 시간을 메시지와 `diag` 에 싣는다.
- 워커: 토큰을 하나도 받지 않은 빈 스트림이면 스트림을 한 번 더 연다(받은 글이 없어 화면 정합성 문제 없음). 두 번째도 실패하거나 다른 종류의 실패면 종전대로 non-stream 재호출.

**검증** — 스펙(진단 필드·청크 0개·1회 재시도 후 송출·2회 연속 시 non-stream·타임아웃은 재시도 안 함), 재시도 조건을 끄거나 무제한으로 바꾸면 실패. 전체 3,341 passed. 병렬 2런(14턴)에서 빈 스트림 0건·정상 경로 이상 없음.

**재현은 하지 않는다**(소유자 결정 2026-10-14) — 운영에서 다시 나오면 `[StructuredStream] 빈 스트림 → 스트림 1회 재시도` 로그의 진단 필드로 원인을 본다.


## 9. 장면 전환 턴의 서술이 라이브에 안 보이던 문제 (2026-10-14)

**발견** — 브라우저 확인(arch/144 P4 이후) 중, 거점 이동 턴의 서술("…발길을 돌린다")이 라이브 화면에 한 번도 나오지 않고 이어하기 복원 때만 보였다. 서버는 이동 요청 1회에 두 턴을 만든다 — 출발 턴(이동 서술)과 도착 턴(SYSTEM, 도착 서술). 응답에 전환(`transition`)이 실리면 클라(`game-store.helpers` `processTurnResponse`)는 출발 턴 서술을 요청하지 않고 곧바로 다음 노드로 넘어가 도착 턴 서술만 요청했다. 2026-02-15 클라 첫 구현(`18f36ba`)부터의 동작이다. 같은 경로: 거점→장소, 장소→거점 복귀, 장소 간 이동, 전투 돌입.

결과: 출발 턴 서술(Luna 호출 1회)이 라이브에선 버려졌고, 이동 서술 규칙(QC 2026-09-01)·별빛모래 첫 귀환 저작본·P3/P4 이동 턴 지연 개선이 라이브에 반영되지 않았으며, 이후 프롬프트의 "최근 서술"(`selectRecentTurnEntries`)엔 플레이어가 못 본 장면이 들어갔다. `playtest.py` 는 DB 서술을 읽어 이 차이를 못 잡는다.

**결정(소유자)** — A: 라이브에서도 이동 장면을 보여 준다. 확인 중 장소→거점 복귀는 출발 서술과 거점 진입 서술이 같은 이동 장면을 두 번 그려(거점은 갈림길이라 진입 서술도 이동 장면) → 복귀는 B: 출발 턴 서술을 만들지 않는다. 전투 돌입은 전투 토픽 보류 지시(2026-10-14)에 따라 종전 동작 유지, TODOS.md 전투 토픽 스택에 기록.

**변경**
- 클라: 전환 응답의 출발 턴 서술이 PENDING 이고 다음 노드가 COMBAT 이 아니면 전환을 미룬다(`pendingTransition`). 출발 서술을 먼저 타이핑하고, 완료(`flushPending`) 때 `applyTransition`(즉시 전환 경로와 공유)으로 다음 노드로 넘어가 도착 서술을 요청한다. 출발 서술이 실패·시간 초과면 실패 창 대신 요약 문구로 대신하고 전환을 잇는다(종전엔 보이지 않던 서술이라 진행을 멈출 이유가 없다).
- 서버: `returnToHubFlow`(거점 복귀 — 선택지 `go_hub`·직접 입력 이동의 거점 폴백) 출발 턴을 `skipLlm`(SKIPPED)으로 기록·응답. 클라는 SKIPPED 라 종전처럼 즉시 전환한다. 서술 호출 1회 절약.

**검증** — 클라 스펙 6(전환 보류·완료 시 전환·전투 제외·SKIPPED 즉시 전환·실패 시 요약 대체·보류 아닌 턴은 실패 창), 서버 스펙 2(복귀 출발 SKIPPED·진입 PENDING). 각 조건을 되돌리면 실패. 브라우저: 거점→경비대 지구·거점→항만 부두는 거점 화면에서 이동 서술이 2초부터 타이핑되고 끝나면 장소로 넘어가 도착 장면이 이어진다. 장소→거점 복귀는 출발 턴 SKIPPED·진입 서술 하나만.

**남는 것**
- 거점 진입·복귀 출발 서술이 **직전 장소를 틀리게 그린다** — 경비대 지구·항만 부두에서 돌아왔는데 "시장 거리의 좌판", "시장을 지나온 뒤"(2회 관측). 종전부터 라이브(진입 서술)에 보이던 결함으로 별도 추적.
- 직접 입력 이동이 거점으로 떨어지는 경우는 이제 SKIPPED 라 §7 P4 의 스트리밍 효과는 장소 간 직접 이동에만 남는다.


## 10. 거점 서술이 직전 장소를 틀리게 그리던 문제 (2026-10-14, `/investigate`)

**증상** — 경비대 지구·항만 부두에서 거점으로 돌아왔는데 거점 진입 서술이 "시장 거리의 좌판", "시장을 지나온 뒤"를 그렸다(run 5630d89e T11·T15, 거점→항만 출발 T12 도 "시장 거리의 장사치들이").

**원인 (DB 저장 프롬프트로 확인)**
1. **거점 턴엔 출발지가 없다.** `[직전 장소 정보]`(`context-builder` `buildPreviousVisitContext`)는 `currentLocationId` 가 있고 직전 장소와 다를 때만 붙는데, `returnToHub` 가 거점에서 `currentLocationId` 를 `null` 로 만든다 → 거점 턴엔 한 번도 안 붙었다. 출발지는 `[최근 대화 이력]` 의 "[턴 9] (이동) 경비대 지구로 이동했다." 한 줄뿐이고, 기억 블록(최근 방문·기억된 사실·최근 사실·이정표)엔 "시장"이 9회 — 모델이 이를 출발지로 그렸다.
2. **도착만 한 방문은 기록되지 않는다.** 행동 턴이 없으면 `node_memories.visitContext` 가 없어 `finalizeVisit` 가 조기 반환 → `lastExitSummary`·`visitLog` 미갱신. 이 런은 경비대·항만을 다녀온 뒤에도 `lastExitSummary` = 시장 거리, `visitLog` 1건이었고, 항만 도착 턴(T13) 프롬프트에 "직전 장소: 시장 거리 (2턴 체류)"가 들어갔다. 30일 장소 도착 턴 123건 중 틀린 직전 장소 2건 — 보통은 방문지에서 행동해 드물지만, 장소를 빠르게 오가면 드러난다.

**수정**
- `memory-integration` `saveMinimalVisitSummary`(조기 반환 경로): 구조화 메모리가 있으면 `lastExitSummary` 를 이번 장소(행동 0)로 갱신.
- `context-builder` `buildPreviousVisitContext`: 거점 진입 턴(MOVE 이벤트 `HUB_RETURN` 태그)이면 현재 장소 ID 가 없어도 붙이고 "방금 떠나온 곳"이라고 적는다. 거점에서 떠나는 턴은 출발지가 거점이라 붙이지 않는다. 행동 0 방문은 "N턴 체류" 대신 "잠시 들렀다 떠남".

**검증** — 스펙 6(거점 진입 블록·거점 출발 미부착·장소 턴 종전·행동 0 문구·조기 반환 경로 갱신·메모리 없으면 미생성), 두 수정을 각각 되돌리면 실패. 전체 3,349 passed·프롬프트 스냅샷 17 불변. 실재현(같은 런): 거점→경비대 지구(도착만)→거점 복귀 → `lastExitSummary` = 경비대 지구(0), 진입 프롬프트 "직전 장소: 경비대 지구 (방금 떠나온 곳, 잠시 들렀다 떠남)", 서술 "시장 거리에서 붙잡은 단서와 경비대 지구에서 살핀 흔적은…"(시장은 단서 출처로만).


## 11. 후처리가 문장을 깨뜨리던 문제 — 한자 단어 제거 (2026-10-14)

**증상** — run 5630d89e T6 최종본 "시선을 거둔 뒤,**의** 마지막 말을"(원문 242→240자, `prefixKept=false`). 90일 DB 에서 같은 모양(이름 없이 조사만 남음) 3건: 이 건 + "시장 곳곳에서 **은** 장부 쪽을"(e5e0e7fb T3, Solar) + "손끝에 걸린다. **의** 발소리 사이로"(61137ca0 T4, Luna 5.6).

**추적** — 모델 원문은 저장되지 않는다. 마커 삽입(`insertDialogueMarkers`)·별칭 정리·텍스트 치환표·조사 교정을 6턴 실데이터와 후보 원문(그·그녀·회계사·에드릭 등 9종)으로 재생해도 재현되지 않았고, 세 사례가 모두 "사람을 가리키는 말"이 통째로 빠진 점에서 **모델이 한자로 쓴 단어**를 의심했다. `stripModelJunkCore` 에 "뒤, 他의"를 넣으면 "뒤, 의", "人们은"은 "은"만 남는다 — 재현.

**원인** — `stripModelJunkCore` (a)는 한글·라틴 밖 문자를 지우는 화이트리스트(아르메니아·인도계 잔해 대응)인데, 모델이 대명사·명사를 한자로 쓰면 한자만 지우고 붙은 조사를 남긴다. 또 이 정리는 완료 시점(`cleanupNarrativeArtifacts`)에만 돌아, 스트림 화면엔 한자 원문이 흐르다 완료 때 깨진 문장으로 바뀌었다.

**수정**
- `stripModelJunkCore` (a0): 한자 대명사(닫힌 집합 — 他·她·他们·人们·我们 등)는 한국어로 바꾸고, 그 밖의 비허용 문자 단어에 조사가 붙어 있으면 조사째 지운다. 그다음 기존 (a).
- `sanitizeStreamSegment`: 스트림 조각에도 같은 정리를 적용(조각 앞뒤 공백 유지) — 흘린 글과 최종본이 같아진다.

**검증** — 스펙 5(대명사 치환 3종·조사째 삭제 2종·조사 없는 한자 회귀·스트림 조각), 각 수정을 되돌리면 실패. 전체 3,354 passed·스냅샷 17 불변. 한자 출력 빈도 자체는 원문이 저장되지 않아 모른다(보이는 깨짐 90일 3건).


## 12. LLM 요청 정리 — 생성 기록·JSON 모드 제거·response_format (2026-10-14)

arch/140 리뷰에서 소유자가 미뤄 둔 세 가지(실제 요청·원본 JSON·폴백 경로 기록, `LLM_JSON_MODE` 사문 경로, `response_format` 중복)를 정리했다.

**발견** — 모델 원문은 이미 `ai_turn_logs.raw_completion` 에 남고 있었다(마커 변환 뒤 텍스트). §11 원인 추적 때 이 테이블을 확인하지 않아 재현에 시간이 들었다 — 6턴 원문은 "뒤,相手의"(일본어 '상대')였다. 30일 원문 2,803건 중 한자·가나 혼입 5건(Luna, 10/12 이후)이고, 관측 단어(相手·余白·どこ·灯)는 §11 표에 추가했다. 없던 것은 모델 **원본 JSON**·실제 요청 파라미터·폴백 경로다.

**1. 생성 기록** — `ai_turn_logs.pipeline_log.generation`(jsonb, 스키마 변경 없음):
- `path` stream·stream-retry·nonstream-json·text·authored·legacy-call, `events`(빈 스트림·스트림 실패·JSON 변환 실패·형태 구제·짧은 응답 재시도 등 발생 순서), `rawJson`(모델 원본, 20,000자 상한), `modelUsed`·`provider`·`attempts`.
- `request`(워커가 요청한 값) 와 `sent`(공급자가 **실제로 보낸** 값 — `LlmProviderResponse.sentParams`)를 따로 둔다. 실측(run 5630d89e T25): 워커는 `reasoningEffort: low`·`temperature 0.8` 을 요청하지만 실제 전송은 `reasoning: {effort: none}`(env 맵)·샘플링 키 0개(Luna 미지원). 이 차이가 기록이 필요한 이유였다.
- 플레이어 노출 없음 — `ai_turn_logs` 는 API 로 나가지 않는다(원본엔 미소개 실명이 있을 수 있다).

**2. `LLM_JSON_MODE` 제거** — json_object 서술 모드(arch/32 2-Stage 대사 분리 포함)는 `LLM_JSON_MODE=false` 로 사문이었다. 워커 `useJsonMode`·`assembleJsonModeNarrative`(287줄)·JSON 파싱 헬퍼·`jsonModeParsed`·`dialogueSlotNpcIds`·부팅 경고, 프롬프트 빌더 JSON 분기·`NARRATIVE_JSON_FORMAT_INSTRUCTION(_SPLIT)`, 후처리·품질 필터의 `jsonModeParsed`, 런타임 영수증 키(`LLM_JSON_MODE`·`LLM_DIALOGUE_SPLIT`), 픽스처 필드를 지웠다. `buildNarrativePrompt` 위치 인자 하나가 빠졌다(호출 스펙 4개 수정). `DialogueGeneratorService` 는 대사 누락 보강·자기소개에 계속 쓴다. 텍스트 폴백이 JSON 봉투를 돌려준 경우의 감지(`"segments":`)는 유지.

**3. `response_format`** — 스트림·비스트림에 복제돼 있던 규칙을 `responseFormatParam` 하나로.

**검증** — 프롬프트 스냅샷 17 불변(JSON 모드가 꺼져 있었으므로 실제 프롬프트 동일), 전체 3,358 passed, 타입 오류 프로파일 기준선과 동일, 변경 파일 신규 린트 오류 0. 실런 2턴에서 생성 기록 확인.

## 13. 추론 강도 요청값 정리 (2026-10-14)

§12 생성 기록이 드러낸 불일치("요청 low → 전송 none")의 원인은 경로별 판정이 달랐던 것이다.

- **OpenRouter 경로**(운영): `buildOpenRouterParams` 가 `resolveReasoningEffort(model)` 을 **요청값 없이** 불렀다. 워커의 `determineReasoningEffort`(평소 low·긴장 정점 medium)는 한 번도 전송되지 않았고, 실제 값은 env 맵 → 추론 계열 기본 `none` 이었다.
- **OpenAI 직결 Responses 경로**(미사용): 요청값을 그대로 쓰고, 없으면 `medium` — "서술은 추론 none" 정책과 반대였다.

**조치 (운영 동작 불변)**
- 워커 `determineReasoningEffort` 와 짧은 응답 재시도의 전달 인자를 지웠다. 서술 요청은 추론 강도를 정하지 않는다(생성 기록 `request.reasoningEffort` = null, 실제 값은 `sent.reasoning`).
- 두 경로가 같은 판정 `resolveReasoningEffort(model, 요청값)` 을 쓴다 — env 맵 → 요청값 → 추론 계열 `none`. Responses API 는 `max` 가 없어 `high` 로 내린다.
- 운영 영향 0: 서술·선택지 모델(Luna)은 맵에 `none` 으로 등재돼 맵이 이기고, 요청값을 싣는 다른 호출(인텐트 파서 `low`)은 비추론 모델(gpt-4.1-nano)이라 필드가 붙지 않는다.
- 요청한 `temperature 0.8` 이 전송되지 않는 것은 정상이다 — 모델 지원 판정(`supportsTemperature`)이 Luna 에서 뺀다. 모델을 바꾸면 다시 실린다.

## 14. P5 증거 경계 턴 서술 모델 생략 (2026-10-14)

`evidenceBoundary`(질문한 증거의 정본이 없음) 턴은 후처리가 모델 원고를 `renderUnconfirmedEvidenceResponseCore` 문안으로 **통째 교체**한다. 판정(`evidenceQuestionBoundary`)이 생성 전에 끝나므로 P3 과 같이 서술 모델을 부르지 않고 문안을 확정한다(`[EvidenceGrounding] … 서술 모델 생략`, 생성 기록 `path=authored`·`events=[evidence-boundary: <사유>]`, 모델명 `authored-evidence-boundary`).

- 제외: 확정 아크 사건(`ARC_STAGE`) 턴 — 원고를 재구성 입력으로 쓴다. 전투 턴.
- 송출하지 않는다 — 이 턴은 종전에도 보류(완료 때 일괄 표시)였고, 문안이 `이름: "대사"` 형식이라 서술 조각으로 흘릴 수 없다. 달라지는 것은 모델 대기(약 4초)와 서술 호출 1회가 사라진다는 점이다.
- 후처리의 교체는 그대로 두어 같은 문안을 다시 만든다(멱등). 짧은 응답 재시도는 저작 턴에서 건너뛴다.
- 관측 0건인 경로라 효과 측정은 `scripts/stream_metrics_monitor.py` 의 생성 경로 집계로 본다.

**운영 지표 정본** — `scripts/stream_metrics_monitor.py`(신설): 생성 기록 경로·이벤트·실제 전송 추론, `[StreamHold]` 모드·사유·prefixKept=false, 이동 축약 생략, 빈 스트림 재시도·강등, `[TurnTiming]` 분위, 한자·가나 혼입 턴을 한 번에 집계한다. 기준선(10/12~14, 3일): 송출 stream 183·hold 29·gated 17, prefixKept=false 1/35(§11 한자 턴 — 수정 전), 첫 토큰 p50 1.2초·p90 1.8초, 첫 송출 p50 1.6초, 한자·가나 혼입 0/504.

## 15. 관찰 런 후속 — 출발지 오기·단서 중복·첫 조각 불일치 (2026-10-14)

관찰 런 2회(그레이마르 이동 위주 `38cb4372` 12턴, 별빛모래 chatty `b26366ca` 12턴, 게이트 15/15)를 정독해 4건을 고쳤다. 한자·가나 혼입은 0건, 출발 서술 표시·직전 장소(거점 진입)는 정상이었다.

| 증상 | 근본 원인 | 조치 |
|---|---|---|
| 거점 출발 서술이 출발지를 "광장 좌판을 등진"으로 씀 (38cb4372 T12) | ① 워커는 전환 커밋 **뒤**의 runState 를 읽어, 출발 턴에도 `currentLocationId` 가 이미 목적지다. §10 의 "거점 출발 턴엔 붙이지 않는다" 가드는 장소 ID 가 null 인 상태를 가정해 **한 번도 작동하지 않았고**, 직전 방문지(시장)가 [직전 장소 정보]로 붙었다. ② 출발지가 거점이라는 정보가 프롬프트 어디에도 없었다. ③ 상점 구매 턴 장면 지시문이 "광장 좌판에서"를 하드코딩했고, 이 지시문이 기억 요약(주요 행동·알고 있는 단서)에 섞였다 | ① `buildPreviousVisitContext` 에 노드 종류(`serverResult.node.type`)를 넘겨 거점 비진입 턴은 생략 ② 거점 이동 선택 지시에 `출발지: <거점명>` 한 줄(스냅샷 002_HUB_t2 이 한 줄만 변경) ③ 구매 지시문 장소명 제거. 실런 재검증(4fd08f24 T9): 블록 생략·출발지 줄 확인, 서술 "그레이마르 거점의 갈림길에서 …" |
| 첫 공개 단서 문장이 대사에 두 번 나옴 + 흘린 앞부분 불일치 (b26366ca T6) | `reconfirmKnownFactAnswerCore` 가 **첫 문장**에만 핵심어가 있는지 봐, "물으셨으니 들은 그대로 말씀드릴게요. 사라진 손님들은 … '눈이 아직 바다를 보고 있다'라고 했어요." 를 미답변으로 판정해 정본 문장을 또 넣었다 | 첫 문장이 유보가 아니고 핵심어가 든 문장이 단정이면 답한 것으로 본다. 기존 9케이스 판정 불변 + 2케이스 추가 |
| 흘린 첫 조각 "당신은 …"이 완료 때 "…"로 바뀜 (b26366ca T10, 3일 448턴 중 9회) | 완료 필터 P6(첫머리 "당신은/당신이" 제거)가 스트림 조각에는 없었다 | 같은 규칙(`stripPlayerOpeningCore`)을 첫 서술 조각에 적용. 지시 개시문 교체(director opening)는 조각 단위 재현이 안 돼 종전대로(3일 0건) |

**판정 보류 — 하네스 경합 (수정 안 함)**: 별빛모래 T9 거점 진입 서술이 여관에서 왔는데 "부두를 등진 걸음"으로 시작했다. 플레이테스트가 진입 턴 커밋 약 60ms 뒤 다음 선택(go_ss_dock)을 제출해, 진입 턴 워커가 이미 부두로 옮긴 runState 를 읽었다. 실클라이언트는 진입 서술 타이핑이 끝나야 선택지를 보이므로 이 순서가 생기지 않는다. 출발 턴(위 ①)은 같은 POST 에서 목적지가 커밋되므로 실유저에게도 해당돼 고쳤다.

**후속 후보**: 장면 지시문(sceneFrame)이 기억 요약의 "주요 행동"·"알고 있는 것"(사건 단서)에 그대로 실린다 — 지시문은 서술용이지 사건 기록이 아니다. 플레이테스트 하네스가 앞 턴 서술 완료 전에 다음 턴을 제출하는 경합(실클라와 다른 순서).

## 16. 기억 오염·하네스 경합·로그 회전 (2026-10-14, §15 후속)

**1. 장면 지시문이 기억에 섞이던 문제** — 기억 수집기(`memory-collector`)는 행동마다 이벤트 `sceneFrame` 을 40자로 잘라 `brief` 로 남기고, 직전 장소 요약의 "주요 행동"·"주요 대화", 사건 관여 기록(→ [당신이 알고 있는 것]), 장소 디테일·발견 비밀이 그 값을 썼다. 상점 구매 턴의 `sceneFrame` 은 장면이 아니라 **서술 지시문**("방금까지의 대화를 잠시 멈추고, … 상인에게 물건을 산다")이라 지시문이 기억 사실로 굳었고, 40자 절단이 어절을 잘랐다("… 갈등이 생길 수 있"). 장면이 없는 턴은 "관찰(성공): " 빈 값이었다.
- 이벤트 페이로드 `sceneFrameIsDirective` 신설 — 상점 구매 합성 이벤트에 표시, 수집 단계에서 기억에 넣지 않는다.
- "주요 행동"·"주요 대화"·사건 관여 기록은 플레이어 입력(`rawInput`)을 쓴다(없을 때만 brief).
- `clipAtWordCore` — 상한에서 자르되 어절 경계에서.
- 실런 c335d876: 상점 턴 brief 공란, `keyActions` = "거래(성공): 체력 강장제를 구매한다" 형식, 사건 관여 snippet = 입력.

**2. 플레이테스트 하네스 경합** — `playtest.py` 가 노드 전환 응답의 진입 턴(`transition.enterTurnNo`)을 기다리지 않고 다음 선택을 제출했다(실클라와 다른 순서 — §15 판정 보류 건). 진입 턴 서술 완료까지 폴링하고 로그에 `entryTurnNo`·`entryLlmStatus` 만 남긴다(게이트 통계 불변을 위해 진입 서술은 넣지 않는다). 실런: 진입 턴 3·12 DONE 확인 후 진행.

**3. 서버 로그 회전** — `/tmp/graymar-server.log` 가 회전 없이 1.21GB(디스크 사용률 97%). `scripts/rotate-server-log.sh`(200MB 초과 시 gzip 사본 `.1.gz`~`.4.gz` + 원본 비우기) + launchd `com.graymar.server-logrotate`(매시 정각, 사본 `scripts/launchd/`). launchd 가 append 모드로 열어 비운 뒤에도 서버가 파일 처음부터 이어 쓴다(실측 확인, 재시작 불필요). 첫 회전 1,211MB → gzip 13.9MB. `stream_metrics_monitor.py` 는 `.1.gz` 도 함께 읽는다(rg `-z`).

## 17. 완료 순간의 화면 점프 — 서술 렌더러 단일화 (2026-10-14, 버그 a28d52e3)

**리포트** — 실유저(별빛모래 T12): "내레이션이 완료되고 npc대사가 갑자기 나타나요". 부분 스트리밍(P2) 턴에서 흘린 서술 128자 뒤, 보류된 이렌 대사 2개와 서술 한 문단(393자)이 완료 7ms 만에 타이핑 없이 붙었다(첨부 클라 로그). §5 의 "완료 화면 회귀 브라우저 확인"이 미수행으로 남아 있던 빈틈이다. 3일 부분 스트리밍 23턴 중 22턴 해당.

**원인 조사에서 드러난 것** — 완료 순간 화면이 바뀌는 원인이 넷 겹쳐 있었다. 실측(모바일 430px, 소개+장면 컷 턴): 내레이터 카드 819 → **1,238px** 한순간 증가.
1. 서술 렌더러가 셋(실시간 `StreamingBlock`·보류/폴링 `StreamTyper`/`TypewriterText`·완료 `NarratorContent`)이고 문단 간격·화자 판정이 달랐다 — 완료 때 컴포넌트가 바뀌며 같은 글을 다시 그렸다(~49px).
2. 완료 후에만 그리는 요소 — 상단 초상화 카드(+118px, 서술 턴 15%)·단서 말풍선 강조(20%)·장면 컷(+252px, ~37%).
3. 조각으로 오지 않은 뒷부분(보류 대사·완료 시점 보강)은 "받은 조각 다 침 → 최종본 교체 + typed" 경로로 통째 붙었다(리포트 원인).
4. 흘린 글의 완료 시점 보정(앞서 집계 ~15% 턴) — 이번 범위 밖(송출 단계 이전은 후속).

**조치 (클라이언트)**
- `narrative-text`: 서술 → 줄 모델(`buildNarrativeLines` — 서술·대사·구형 인용 항목, 화자 compact·단서 강조·대표 화자 폴백 판정 포함)과 "몇 글자까지" 렌더(`renderNarrativeLines(lines, {reveal, cursor})`)로 분리. `NarratorContent` 도 이 둘로 그린다 — 다 친 결과와 완료 화면이 같은 DOM(스펙 고정).
- `NarrativeReveal`(신설, 타이핑 단일 정본): 실시간 조각은 완료 서술과 같은 형식으로 묶고(`segmentsToNarrative` — 문단 안 공백, 문단·대사 빈 줄), 원문이 바뀌면 보여 준 위치를 새 원문에 맞춰 옮긴다(`alignReveal` — 연장이면 그대로, 앞부분 교정이면 보여 준 끝 16자를 찾아 그 뒤, 무관하면 같은 분량). 완료 신호 뒤 남은 글은 **이어서 타이핑**한다. 리듬은 구 TypewriterText 규칙(대사 0.7배속·대사 진입/이탈 pause·문단 pause) 그대로.
- `StoryBlock`: 스트리밍 중·타이핑·완료가 같은 위치의 같은 컴포넌트라 완료 때 다시 마운트되지 않는다. 초상화 카드는 스트리밍 시작부터, 장면 컷·단서 노티는 타이핑이 끝난 뒤 서서히(fadeIn). 완료 처리의 상태 갱신을 한 번에 묶어 로딩 화면이 한 프레임 끼어들던 틈도 막았다.
- 삭제: `StreamingBlock.tsx`·`StreamTyper`·`TypewriterText`. 구 `StreamingBlock.test` 계약(마커만 있는 조각·빈 조각·늦은 완료·완료 후 선택지·버린 초안)은 `NarrativeReveal.test` 로 옮기고, 보류 뒷부분 이어 타이핑·완료 DOM 동일·스트리밍 중 초상화 카드를 추가.

**검증** — 클라 테스트 93 passed(`NarrativeReveal.test` 14 — 구 StreamingBlock 6건 이관 포함), 린트·타입·빌드 통과. 브라우저(로컬 클라 + 실서버, 430px) 2턴: 완료 순간 카드 높이 577→577·696→696px(종전 +419px), 문단·대사·인용 렌더 동일. 장면 컷 턴과 부분 스트리밍 턴은 실런에서 조건이 안 걸려 스펙으로만 확인.

**잔여** — 4번(흘린 글의 완료 시점 보정)은 서버 송출 단계로 옮기는 후속. 증거 경계 고정 문안의 어체 선택(`renderUnconfirmedEvidenceResponseCore` 가 speechStyle 의 "반말" 단어로만 판정 — 해체 NPC 토브렌이 해요체로 답함) 수정 필요.

---

# Eng Review — arch/144 보류 스트림 턴 (2026-10-13, `/plan-eng-review`)

대상: 이 문서 §4 수정 계획 P1~P3 (P4·P5 는 계획상 보류). 검토 기준선 = 위 계획 원문 + 2026-10-13 소유자 승인("좋아 진행해줘").

## Scope Challenge

**A. 평가**
- 기존 해결책: 보류 판정은 `narrativeStreamHoldReasonsCore`(미커밋 계측, `server/src/llm/worker/narrative-quality-stream-hold.core.ts`)로 이미 사유별로 분리돼 있다. 화자 해석은 `resolveStructuredSpeaker`(structured-narrative-stream.core.ts) 가 한다. 첫 귀환 판정은 `applyFirstHubReturnNarrativeCore`(hub-move-narrative.core.ts:2) 의 순수 조건이다.
- 최소 변경: P1 은 사유 하나 제거, P2 는 스트림 이벤트에 화자 ID 를 싣고 워커 emit 게이트를 추가, P3 은 생성 단계 단락. 모두 기존 파일 안에서 끝난다.
- 복잡도: 변경 파일(예상) 워커·스트림 core·speaker-candidates core·hold core·known-fact-answer core + 스펙 4~5개 = 프로덕션 5개, 새 서비스 0 → B(복잡도 선택) 생략.
- 검색: 새 인프라·동시성 패턴 없음(스트림 emit 게이트는 기존 패턴의 조건 추가) → 외부 검색 불필요.
- TODOS.md: 소유자 운영 작업 3건뿐, 이 계획과 무관.

**사실 정정 (동작 변경 없음)**
- §4 P2 "판정은 구조화 스트림 이벤트의 화자 ID(`StructuredNarrativeStream` 이 이미 해석)" — 해석은 하지만 이벤트에 ID 가 없다. `SegmentEvent` 는 `type·text·npcName·npcImage·paragraphStart` 뿐(speaker-candidates.core.ts:21-28). 구현 시 내부 필드 `speakerNpcId` 를 이벤트에 싣고, SSE 로 내보내기 전에 제거한다.
- §4 P3 의 짧은 응답 재시도(`retryShortAlternateResponse`, llm-worker.service.ts:4975)는 `alternateModel` 이 메인과 다를 때만 돈다. 현 운영은 Luna 단일이라 무관하지만, 단락 경로는 재시도를 명시적으로 건너뛴다.

**전제 검증표** (`unverified=0`)

| 전제 | 주장 | 근거 | 판정 |
|---|---|---|---|
| 보류 조건 11가지 | 워커 OR 체인과 사유 함수가 같다 | llm-worker.service.ts `holdReasons` 블록 (구 `holdNarrativeStream` OR 체인 치환) | 참 [measured: 계측 런 65턴 held 18 = 사유 비어있지 않은 턴] |
| 단서 정본 교정 위치 | 대상 NPC 첫 대사, 없으면 맨 앞 삽입 | known-fact-answer.core.ts:10-30 (`ownLineIndex < 0` → 앞에 붙임) | 참 |
| 다음 확인 행동 보강 위치 | 끝에 한 줄 | withheld-next-step.core.ts `${narrative.trimEnd()}\n\n${line}` | 참 |
| 첫 귀환 | 2턴째·거점 장소·저작본 → 전체 교체 | hub-move-narrative.core.ts:2-22 | 참 |
| 클라 완료 교체 | done 시 최종본으로 버퍼 교체 | client game-store.helpers.ts:641-660 | 참 |
| 교정 적용 빈도 | 277 스트리밍 턴 중 5회 | 서버 로그 태그 집계 [measured: /tmp/graymar-server.log 10/05~] | 참 |
| 보류 대가 | 장소 대화 보류 턴 첫 글자 9~12초 | choice_probe 로그 [measured] | 참 |

REALITY: premise-table pass 7 claims, unverified=0 server/src/llm/known-fact-answer.core.ts:10
REALITY: already-done pass origin/main since 2026-10-12 touches only 35d5814 (JSON 스키마 스트림, 별개 작업) server/src/llm/speaker-candidates.core.ts:21
REALITY: surface-check pass 새 CLI·플래그·라우트 없음, 로그 태그만 추가 server/src/llm/llm-worker.service.ts:2931
REALITY: binding-decisions pass 브랜치 결정 1건(arch/142)은 다른 경로, 충돌 없음 architecture/142_intent_challenge_decision_call.md:1
REALITY: numbers pass 수치 전부 측정값 태그, 기대 효과(3.5초)는 [estimated] — 구현 후 재측정 architecture/144_held_stream_turns.md:15
REALITY: deferred-asks pass 요청(분석+수정 계획) 전부 수행, P4·P5 는 계획 내 보류로 명시 architecture/144_held_stream_turns.md:1
REALITY: pr-count pass 레포당 커밋 1(서버·문서), ship-policy 없음 → 기본 1 architecture/144_held_stream_turns.md:1

**B.** 생략 (프로덕션 파일 5개 < 8, 새 서비스 0).

**C. 결과:** Scope Challenge 지적 0건(사실 정정 2건은 위에 기록). scope accepted as-is.

## 1. Architecture review

```
stageGenerate (스트리밍 경로)
  holdReasons = narrativeStreamHoldReasonsCore(...)          ← 사유 11종
  mode = reasons 비어있음            → STREAM (전량 송출)
       = reasons ⊆ GATEABLE          → GATED  (P2)
         GATEABLE = {reconfirm, revealDirect, playerKnownFact, spokenFactMedium}
       = 그 외 사유 하나라도          → HOLD   (현행, done 에서 일괄)
  P1: withheldNextStep 은 사유 목록에서 제거 → STREAM
  P3: 첫 귀환 조건 성립 → 생성 단락: 저작본을 서술 이벤트로 즉시 송출, LLM 호출 없음

  for token in callStream:
    events = structuredStream.feed(token)          ← 이벤트에 speakerNpcId(내부) 포함
    for ev in events:
      GATED && !gateClosed && ev.type==dialogue && (ev.speakerNpcId==guardNpc || ev.speakerNpcId==null)
            → gateClosed = true                   ← 대상·무명 대사부터 끝까지 보류
      emit if STREAM || (GATED && !gateClosed)    ← speakerNpcId 제거 후 SSE
  done → 최종본(교정 적용) 송출 → 클라 버퍼 교체
```

[P2] (confidence: 8/10) architecture/144_held_stream_turns.md §4 P2 — 사유 혼재 시 우선순위. "이 사유들로만 보류되는 턴" 문구대로 GATEABLE 밖 사유가 하나라도 있으면 HOLD 가 우선한다. 위 도식으로 명시함(동작 변경 아님, 질문 불필요).
[P2] (confidence: 7/10) server/src/llm/llm-worker.service.ts holdReasons 블록 — 부분 스트리밍을 끄는 런타임 스위치가 계획에 없다. 직전 arch/143 은 같은 성격의 변경에 킬스위치(`NPC_REACTION_SPECULATIVE_DISABLED`)를 뒀다. → R1.
[P3] (confidence: 6/10) server/src/llm/worker/spoken-evidence-medium.core.ts:42 · counted-record-grounding.core.ts — 전체 대체형 교정이 걸리면 흘려보낸 서술까지 바뀐다(관측 0건). 계획대로 `[StreamHold] gatedReplaced` 로 센다. Medium confidence, 실제 발생 빈도는 계측으로 확인.

Dispositions: 사유 혼재 우선순위 — accepted(계획 문구 명시, 질문 불필요) · 킬스위치 — accepted D1(A) · 전체 대체형 교정 — accepted(계획대로 계측)

## 2. Code quality review

[P2] (confidence: 9/10) server/src/llm/worker/narrative-postprocess.service.ts:2096 — `sanitizeStreamSegment` 가 `ev = { ...ev, npcName }` 로 이벤트를 펼쳐 SSE 로 넘긴다. 이벤트에 `speakerNpcId` 를 실으면 그대로 클라이언트로 나간다. 워커 emit 직전에 내부 필드를 떼어낸다(계획 사실 정정의 구현 조건). 질문 불필요 — 승인된 P2 의 필수 구현.
[P3] (confidence: 9/10) server/src/llm/worker/narrative-quality-stream-hold.core.ts:2 — `shouldHoldNarrativeQualityStreamCore` 는 사유 함수 도입 후 호출처 0. 계획 §4 공통대로 스펙을 사유 함수 기준으로 옮기고 삭제.
[P3] (confidence: 7/10) server/src/llm/known-fact-answer.core.ts:22-26 — 대상 NPC 무발화 시 맨 앞 삽입. P2 와 함께 쓰면 흘려보낸 서술 위에 대사가 끼어든다. 계획 §4 P2 대로 "첫 서술 문단 뒤 삽입" 옵션을 두되, 비보류(STREAM) 경로의 기존 동작도 바뀌므로 두 호출처(llm-worker.service.ts:2647·2669)에 같은 옵션을 넘기고 스펙으로 위치를 고정한다.
공유 코드: 새 헬퍼 추출 없음(기존 사유 함수·교정 함수 재사용). 해당 없음.

Dispositions: 전부 accepted (승인된 P1~P3 의 필수 구현·정리, 새 정책 아님)

## 3. Test review

프레임워크: jest (server). 프롬프트·LLM 출력 변경 없음 → 평가(eval) 대상 아님.

```
CODE PATHS                                                  USER FLOWS
[+] narrativeStreamHoldReasonsCore                          [+] 단서 대화 턴 (P2)
  ├── [GAP] 사유 11종 각각 → 이름 (기존 판정과 동등)          ├── [GAP] [→E2E] 서술 먼저 보이고 대사는 완료 때 — /qa
  └── [GAP] withheldNextStep 은 사유 아님 (P1)               └── [GAP]        교정 적용 턴: 흘린 앞부분이 최종본과 같음
[+] 스트림 모드 결정 (워커)                                  [+] 별빛모래 첫 귀환 (P3)
  ├── [GAP] 사유 없음 → STREAM                               └── [GAP] [→E2E] 저작본 즉시 표시 — /qa
  ├── [GAP] GATEABLE 만 → GATED                             [+] 거점·장소 이동
  ├── [GAP] 혼재(GATEABLE + 이동 등) → HOLD                   └── [GAP]        종전대로 완료 때 일괄 (회귀)
  └── [GAP] 킬스위치 켜짐 → GATED 대신 HOLD (D1)
[+] 게이트 emit
  ├── [GAP] 서술 송출 → 대상 NPC 대사에서 닫힘, 이후 전부 보류
  ├── [GAP] 무명(ID 없음) 대사에서 닫힘
  ├── [GAP] 다른 NPC 대사는 통과
  └── [GAP] speakerNpcId 는 SSE 페이로드에 없음
[+] reconfirmKnownFactAnswerCore 삽입 위치
  ├── [★★★ TESTED] 정본 교체·모순 판정 — known-fact-answer.core.spec.ts
  └── [GAP] 무발화 시 첫 서술 문단 뒤 삽입
[+] 첫 귀환 단락 (P3)
  ├── [GAP] 조건 성립 → LLM 호출 0, 저작본 이벤트 송출, 최종본 = 저작본
  └── [GAP] 조건 불성립(3턴째·다른 목적지) → 종전 호출

COVERAGE: 1/17 paths tested | GAPS: 16 (2 E2E)
```

회귀 계약 (기존 동작, 계획 §5 "사유 함수 동등성" 으로 승인됨): GATEABLE 밖 사유가 있는 턴은 종전대로 완료 때 일괄 표시한다. 단언 — 이동·증거 경계·아크·복합 공격·하위 장면 사유는 각각 HOLD.

추가 테스트 (전부 승인 범위, 새 정책 없음):
- `narrative-quality-stream-hold.core.spec.ts` 확장 — 사유 11종 표 + withheld 제외 + 모드 결정 함수(STREAM/GATED/HOLD, 혼재, 킬스위치).
  Value: protects=보류 판정 동등성과 P1·P2 경계; fails_when=사유 누락·혼재 시 GATED 오판; why_new=기존 스펙은 구 함수 5개 조건만; seam=none; no_claim=실제 스트림 타이밍(단위)
- `structured-narrative-stream.core.spec.ts` 확장 — 대사 이벤트에 speakerNpcId(해석 ID / 무명 null).
  Value: protects=게이트 판정 입력; fails_when=화자 ID 누락; why_new=이벤트에 ID 필드 신설; seam=none; no_claim=none beyond protects
- `llm-worker.stream-gate.spec.ts` 신설 — 워커 게이트 emit(서술 통과 → 대상·무명 대사에서 닫힘 → 이후 보류, 다른 NPC 통과, SSE 페이로드에 speakerNpcId 없음) + 첫 귀환 단락(호출 0·이벤트 송출) + 킬스위치.
  Value: protects=부분 스트리밍 계약과 첫 귀환 단락; fails_when=게이트 위치 오류·ID 누출·불필요 LLM 호출; why_new=stageGenerate 스트리밍 경로 스펙 없음; seam=none; no_claim=클라 교체 연출(→/qa)
- `known-fact-answer.core.spec.ts` 확장 — 무발화 시 첫 서술 문단 뒤 삽입.
  Value: protects=흘린 앞부분 보존; fails_when=맨 앞 삽입 회귀; why_new=위치 옵션 신설; seam=none; no_claim=none beyond protects
- E2E: `/qa` 로 단서 대화 턴·별빛모래 T2 실제 브라우저 확인.

폐기 대상 테스트: `shouldHoldNarrativeQualityStreamCore` 직접 스펙 → 사유 함수 스펙으로 이관 후 삭제.

Dispositions: 회귀 계약 — carried forward(계획 §5) · 테스트 4종 + /qa — accepted(승인 범위)

## 4. Performance review

- P3 은 별빛모래 첫 귀환 턴의 서술 호출 1회를 없앤다(턴 비용 대부분 + 약 4초) [measured: 계측 런 T2 생성 2.5~4초].
- P2 게이트는 이벤트당 비교 1회, 추가 호출·메모리 없음.
- `[StreamHold]` 로그의 바이그램 유사도는 턴당 1회, 서술 ~600자 → 무시할 수준 [estimated].
No issues found.

Dispositions: 해당 없음

## Decision ledger

### R1: 부분 스트리밍(P2) 런타임 킬스위치
Finding: [P2] (7/10) server/src/llm/llm-worker.service.ts holdReasons 블록, Architecture review
Plan baseline: 원문 계획에 스위치 없음 (2026-10-13 승인 "좋아 진행해줘")
Runtime evidence: 런타임 플래그 체계 `RUNTIME_FLAG_KEYS` (server/src/common/runtime-flags.ts), 선례 `NPC_REACTION_SPECULATIVE_DISABLED` (llm-worker.service.ts, d1262cb)
Comparison grid:
| 선택 | 현재 | A | B |
|---|---|---|---|
| R1 킬스위치 | 없음(제안) | `NARRATIVE_STREAM_GATE_DISABLED` 런타임 플래그 — '1'/'true' 면 GATED 대신 HOLD | 없음 |
| P1·P2·P3 동작 | 승인됨 | 그대로 | 그대로 |
Question D1:
D1 — 부분 스트리밍(P2)에 런타임 킬스위치를 둘까요?
Project/branch/task: graymar-server main, arch/144 보류 스트림 턴 계획 검토.
ELI10: P2 는 단서 대화 턴에서 대상 NPC 대사 직전까지 서술을 먼저 흘려보냅니다. 드물게 완료 시점 교정이 서술 전체를 바꾸면, 먼저 보인 글이 다른 글로 바뀌는 장면이 생길 수 있습니다. 그때 어드민에서 즉시 예전 방식(완료 때 한 번에 보여 주기)으로 되돌릴 스위치가 있으면 빌드·재시작 없이 대응할 수 있습니다.
Stakes if we pick wrong: 스위치가 없으면 문제가 생겼을 때 코드 수정·빌드·재시작으로만 되돌릴 수 있습니다.
Recommendation: A because 플래그 한 개와 조건 한 줄로 직전 작업(arch/143)과 같은 롤백 수단을 갖춥니다.
Completeness: A=9/10, B=7/10
Pros / cons:
A) 추가 (recommended)
  ✅ PATCH /v1/admin/llm/flags 로 재시작 없이 부분 스트리밍만 끄고 예전 보류로 되돌립니다
  ✅ 킬스위치 경로도 스펙 한 건으로 고정해 회귀를 막습니다
  ❌ 런타임 플래그 목록이 하나 늘고 어드민 설명 맵에도 추가가 필요합니다 (human: ~30분 / CC: ~5분)
B) 없음
  ✅ 코드가 가장 작고, 관측상 전체 대체형 교정은 0건이라 쓸 일이 드뭅니다
  ❌ 문제 시 되돌리려면 코드 수정·빌드·재시작이 필요합니다
Net: 플래그 하나 대 즉시 롤백 수단.
Header: D1 킬스위치
Options:
A) 추가 (recommended)
`NARRATIVE_STREAM_GATE_DISABLED` 런타임 플래그 신설, 켜면 P2 대상 턴을 예전처럼 완료 때 일괄 표시. 스펙 1건 포함.
B) 없음
코드·인덱스 변경 없음. P2 는 항상 켜짐.

State: approved
Actual answer: A) 추가 (recommended) — 2026-10-13 D1
Accepted scope: 런타임 플래그 `NARRATIVE_STREAM_GATE_DISABLED`('1'/'true', trim·소문자) 신설, 켜면 GATED 대상 턴을 HOLD 로 처리. 킬스위치 경로 스펙 1건. CLAUDE.md 킬스위치 목록 1줄. (어드민 설명 맵은 별도 레포 — 후속)
History: —

Approval readiness: PASS — R1 (D1 A, 2026-10-13). P1·P2·P3 본체는 계획 승인(2026-10-13 "좋아 진행해줘"), 리뷰 지적은 전부 승인 범위의 필수 구현·정정.

## Outside Voice

Codex(`gpt-6-astra`)는 ChatGPT 계정 미지원 모델로 400 — 외부 의견 미수행(`outside_status: unavailable`). 해결: `gstack-config set plan_review_tier smart`. 네이티브 대체(Plan 서브에이전트)는 이 세션에 TaskOutput 도구가 없어 사용 불가. 외부 커버리지 없음.

## NOT in scope
- P4 이동 서술 근본 수정(프롬프트로 축약 적용률 0) — 교정이 실제로 일어나는 경로라 측정 후 별도 판단.
- P5 `evidenceBoundary` 서술 호출 생략 — 관측 0건, P3 와 같은 단락 패턴으로 후속 가능.
- 어드민 콘솔(graymar-admin) 플래그 설명 맵 — 별도 레포. `NPC_REACTION_SPECULATIVE_DISABLED` 와 함께 후속.
- TODOS.md — 이 프로젝트에서 TODOS.md 는 소유자 수동 작업 전용(CLAUDE.md "잔여 TASK"). 개발 후속은 이 문서 §4 에 남긴다. 제안 0건.

## What already exists
- 사유 분리: `narrativeStreamHoldReasonsCore`·`bigramDiceCore`·`[StreamHold]` 로그 (미커밋 계측, 이번 구현과 함께 커밋).
- 화자 해석: `resolveStructuredSpeaker` — 게이트는 이 결과를 이벤트에 싣기만 한다(재해석 없음).
- 교정 함수: `reconfirmKnownFactAnswerCore`·`ensureWithheldNextStepCore`·`applyFirstHubReturnNarrativeCore` 재사용, 위치 옵션 1개만 추가.
- 킬스위치: `flagValue` + `RUNTIME_FLAG_KEYS` 기존 체계 재사용.

## Failure modes
| 경로 | 현실적 실패 | 대응 | 사용자 체감 |
|---|---|---|---|
| GATED 송출 | 대상 NPC ID 오해석으로 정답 대사가 흘러나감 | 무명(ID 없음) 대사에서도 닫힘 + 스펙 | 교정 전 대사가 보였다가 바뀜(드묾) |
| GATED 송출 | 전체 대체형 교정이 흘린 서술까지 교체 | `gatedReplaced` 계측 + 킬스위치(D1) | 글 교체가 보임 — 조용한 실패 아님 |
| 첫 귀환 단락 | 조건 오판으로 일반 이동까지 저작본 | 순수 조건 재사용 + 3턴째·다른 목적지 스펙 | 잘못된 이동 서술 |
| SSE 페이로드 | `speakerNpcId` 누출 | emit 직전 제거 + 스펙 | 없음(ID 는 비밀 아님, 포맷 오염만) |
치명적 공백(테스트·처리 없음 + 조용함): 0.

## Worktree parallelization strategy
Sequential implementation, no parallelization opportunity. (서버 워커 단일 모듈)

## Implementation Tasks
- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — hold core — 사유 함수에서 withheldNextStep 제거 + 모드 결정(STREAM/GATED/HOLD·혼재·킬스위치), 구 함수 삭제·스펙 이관
  - Surfaced by: §4 P1, Section 1 혼재 우선순위, Section 2 사문 함수
  - Files: server/src/llm/worker/narrative-quality-stream-hold.core.ts(+spec), server/src/common/runtime-flags.ts
  - Verify: `pnpm jest narrative-quality-stream-hold`
- [ ] **T2 (P1, human: ~2h / CC: ~20min)** — stream core·worker — 대사 이벤트에 speakerNpcId, 워커 게이트 emit + SSE 전 제거
  - Surfaced by: §4 P2, Scope 사실 정정, Section 2 페이로드 누출
  - Files: server/src/llm/speaker-candidates.core.ts, structured-narrative-stream.core.ts(+spec), llm-worker.service.ts, llm-worker.stream-gate.spec.ts(신설)
  - Verify: `pnpm jest structured-narrative-stream llm-worker.stream-gate`
- [ ] **T3 (P2, human: ~1h / CC: ~10min)** — known-fact-answer — 무발화 시 첫 서술 문단 뒤 삽입
  - Surfaced by: Section 2 삽입 위치
  - Files: server/src/llm/known-fact-answer.core.ts(+spec), llm-worker.service.ts(호출 2곳)
  - Verify: `pnpm jest known-fact-answer`
- [ ] **T4 (P1, human: ~2h / CC: ~20min)** — worker — 첫 귀환 생성 단락(LLM 호출 0, 저작본 이벤트 송출)
  - Surfaced by: §4 P3
  - Files: server/src/llm/llm-worker.service.ts, llm-worker.stream-gate.spec.ts
  - Verify: 스펙 + 별빛모래 실측 T2 첫 글자
- [ ] **T5 (P2, human: ~1h / CC: ~15min)** — 실측·QA — 선택지 런 3회 + 별빛모래 1회 `[StreamHold]`·첫 글자, `/qa` 브라우저 확인
  - Surfaced by: §5 검증, Test review E2E
  - Files: (측정)
  - Verify: 단서 대화 턴 첫 글자, 흘린 앞부분 = 최종본 앞부분

## Unresolved decisions
없음.

## Completion summary
- Step 0: Scope Challenge — scope accepted as-is
- Reality rows: 7/7 applicable rows emitted (`PLAN_REALITY: phase=eng rows=7/7 missing=none unverified=0 verdict=complete`), 0 unverified premises
- Architecture Review: 3 issues found
- Code Quality Review: 3 issues found
- Test Review: diagram produced, 16 gaps identified
- Performance Review: 0 issues found
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 0 items proposed to user
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: codex, unavailable (모델 미지원 400; 네이티브 대체 도구 없음)
- Parallelization: 1 lane, 0 parallel / 1 sequential
- Lake Score: 1/1 (D1 에서 최고 완성도 선택지 A 선택)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | codex (plan-review) | Independent 2nd opinion | 3 | unavailable | 모델 미지원(gpt-6-astra) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | issues_open | 22 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** codex plan-review — unavailable (400, ChatGPT 계정 미지원 모델). 네이티브 대체 미수행(TaskOutput 없음). 외부 커버리지 없음.
- **VERDICT:** ENG 검토 완료 — 지적 22건 전부 승인 범위로 매핑(T1~T5), 미해결 결정 0. CEO·Design 은 해당 없음(백엔드 스트리밍 경로).

NO UNRESOLVED DECISIONS
