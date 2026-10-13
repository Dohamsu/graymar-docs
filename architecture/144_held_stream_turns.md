# 144. 보류 스트림 턴 — 분석과 수정 계획

> 상태: 분석 완료·계획 (2026-10-13). 선행: arch/141(지연 계측)·143(사전 결정·첫 조각). 계측 코드(`[StreamHold]`)는 미커밋.

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
