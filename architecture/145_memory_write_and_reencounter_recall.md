# 145. 기억 저장 정정 + 재회 회상

> 상태: 구현 완료·미커밋 (2026-10-16). 설계 리뷰·구현 리뷰 모두 fable APPROVE_WITH_CHANGES → 반영(§8·§9). 선행: arch/139(원문 회상 블록 R1·R2), arch/144 §16(지시문 기억 오염).
> 범위: 서버 `turns/location-turn`·`engine/hub/memory-*`·`llm/context-builder`·`llm/recall-block.core`·`llm/mid-summary`·`llm/memory-renderer`.

## 0. 결론

중간·오래된 기억이 약한 이유는 **저장이 내용을 버리고, 꺼내기가 질문과 무관하기 때문**이다. 원문(`turns.raw_input`·`llm_output`)은 불변으로 남아 있지만, 구조화 기억 칸 상당수가 "이벤트 도입 문장(`sceneFrame`)"으로 채워지고, 원문을 꺼내는 길은 회상 신호어가 있는 턴의 회상 블록 하나뿐이다.

이 설계는 새 LLM 호출 없이 두 가지를 한다.

1. **M1 저장 정정** — 칸 이름과 다른 값이 들어가는 4곳을 서버 확정 값(플레이어 입력·공개 단서)으로 바꾸고, 공개 단서가 잡담 기록에 밀려 사라지는 정리 규칙을 고친다.
2. **M2 재회 회상** — 이전 방문에서 대화한 NPC와 이번 방문에 처음 말을 섞는 턴에, 그 NPC가 마지막으로 한 말 원문 1묶음을 넣는다. 신호어 없이도 "아는 사이"의 근거가 생긴다.

부수로 **M3**(만난 적 없는 NPC에 "알아보라" 지시가 붙는 문제)와 **M4**(요약에 내부 ID·지시문이 섞이는 문제)를 정리한다.

## 1. 실측 근거 (2026-10-16, 최근 14일 프롬프트 보존 582턴)

| 관찰 | 수치 |
|---|---|
| `[관련 NPC 기록]` 항목 중 만난 적 없는 NPC | 1,353개 중 1,018개(75%). 102턴은 전원 미조우인데 "이전에 만난 NPC는 알아보는 반응" 지시 동반 |
| `[장소 기억]` 중 "처음 방문하는 장소" 한 줄 | 498턴 중 473턴 |
| 장소 기억 "발견한 비밀" 30일 저장값 | 84건 전부 이벤트 도입 문장("날카로운 회계사이(가) 상단 사무소에 일찍 출근해…", 절차 시드 조각 "말다툼이 벌어지고 있다 여인이(가) 쓰러져 있다…") |
| `[이야기 요약]` | `NPC_EDRIC_VEIL 만남`, `MERCHANT_CONSORTIUM+6` — 내부 ID 노출, 행동 분류명만 |
| `[중간 요약]` 서버 뼈대 | `의도: - 외교적 접근: 설득과 대화로 문제 해결 — 우호적 톤으로 서술` (서술 지시문), `사건: INC_SMUGGLING_RING` |
| 회상 블록 발동 | 18턴, 전부 10/12 검증 프로브. 이후 실플레이 0 |
| `entity_facts` 30일 | 2,411건 중 `PLOT_CLUE` 93건(4%), 나머지 외형·행동 묘사 |

### 1.1 코드에서 확인한 오배선

| 칸 | 기대 | 실제 값 | 위치 |
|---|---|---|---|
| `NpcPersonalMemory.encounters[].briefNote` | 그때 한 일 | 이벤트 `sceneFrame ?? rawInput` | `location-turn.service.ts` ~1864 |
| `NpcPersonalMemory.knownFacts` ("알려진 사실") | 이 NPC에게 들은 정보 | SUCCESS 판정 턴의 `sceneFrame` | 같은 곳 ~1872 |
| `LocationPersonalMemory.discoveredSecrets` ("발견한 비밀") | 이 장소에서 알아낸 것 | SUCCESS + 조사 행동 턴의 `brief`(=`sceneFrame`) | `memory-integration.service.ts` ~940 |
| `NpcLlmSummary.lastDialogueTopic` / `lastDialogueSnippet` | 직전 대화 주제 / 마지막 대사 | 주제=`sceneFrame`, 대사=항상 `''`("다음 턴에서 반영" 주석만 있고 미구현 — 사문) | `location-turn` ~1890, `npc-state.ts buildNpcLlmSummary` |
| `npcKnowledge` 정리 규칙 | 공개 단서 보존 | 공개 단서(PARTIAL=0.5)가 이후 SUCCESS 잡담 기록("\"…\" 주제로 대화를 나눴다", 0.8) 5건에 밀려 삭제 가능 | `memory-collector.collectNpcKnowledge` |

이미 고쳐진 것(범위 밖): 회상 질문 턴의 오답 재사용(arch/139 §6.1-2, `recall-block.core` 289행), `[직전 장소 정보]` 지시문 오염(arch/144 §16).

## 2. M1 저장 정정

원칙: **칸 이름이 약속하는 값만 넣는다. 없으면 비운다.** 비어 있는 칸은 블록에서 생략되므로 거짓 기억보다 낫다.

- **M1-a briefNote** — `clipAtWordCore(rawInput, 30)`. 선택지 턴은 선택지 라벨(이미 rawInput에 들어옴). 렌더(`renderRelevantNpcMemory`)의 20자 절단도 어절 경계로.
- **M1-b knownFacts** — `sceneFrame` 쓰기를 제거한다. 그 턴에 이 NPC가 공개한 단서가 있을 때만(`questRevealThisTurn.npcId` 일치) 그 텍스트(`versions[npcId] ?? description`, npcKnowledge와 같은 정본)를 넣는다. 공개 주체가 없는 소문·자동 발견은 NPC 기억에 남기지 않는다(그 NPC가 말한 것이 아니다). 커밋 객체는 offscreenTick 이후의 `postTickRunState`.
- **M1-c discoveredSecrets** — 조사 행동 brief 규칙을 제거한다. `VisitContextCache`에 선택 필드 `revealedFacts?: string[]`를 두고 `collectFromTurn`이 `revealedFactText`를 쌓는다. `finalizeVisit`가 이를 discoveredSecrets로 병합한다(상한 유지). 렌더 라벨은 "알아낸 단서"로 바꾼다.
- **M1-d npcKnowledge 정리** — 공개 단서 항목 importance 1.0(판정 무관), 주제 기록 SUCCESS 0.4 / PARTIAL 0.3, AUTO_COLLECT 0.3. 삭제 판정만 importance 로 하고, **저장 순서는 turnNo 오름차순으로 되돌린다** — `[등장 가능 NPC 목록]` 의 `.slice(-3)`(최근 3개)와 `[이미 나눈 대화]` 의 `slice(0,-4)`(이전 공개)가 배열 순서를 시간순으로 읽는다(리뷰 F1).
- **M1-e lastDialogueTopic** — `clipAtWordCore(rawInput, 40)`. `lastDialogueSnippet` 은 채우지 않는다(M2가 원문으로 대신한다). 빈 값이면 렌더 생략이 이미 되어 있다.

기존 런의 저장값은 이관하지 않는다(진행 중 런이 사실상 없음, 다음 방문부터 새 값). 단 M1-c 렌더는 구 값(=도입 문장)을 계속 보여 주므로, 이 필드를 렌더에서 읽지 않고 새 필드만 읽도록 필드명을 분리한다(`discoveredClues`).

## 3. M2 재회 회상 `[지난 만남 원문]`

### 3.1 언제

다음을 모두 만족하는 턴 1회 (1~5는 메모리 판정, DB 조회 없음 — 리뷰 F2):

1. 회상 신호가 없다(있으면 arch/139 경로가 맡는다 — 코드 게이트로 배타, 레지스트리 `exclusiveWith` 는 기록용).
2. 대화 상대(`playerTargetNpcId ?? primaryNpcId`)가 있고, 동행 NPC(`worldState.companionNpcId`)가 아니다(리뷰 F5 — 동행자는 장소마다 새 노드라 매 이동 발동).
3. 그 NPC의 `encounterCount >= 2`(방문 단위 1회 증가 — 이전 방문 만남 존재).
4. `lastEncounterTurn === 이번 턴`(= 이번 방문의 첫 조우 턴, arch/91 재회 호명 게이트와 같은 값).
5. 킬스위치 `REENCOUNTER_RECALL_DISABLED` 가 꺼져 있다.
6. (DB 1회) **이전 노드**(`node_instance_id` ≠ 현재)의 DONE 턴 중 이 NPC가 말한 턴이 있다.

방문 단위를 `node_instance_id`로 자르는 근거: `transitionToLocation`·`transitionToHub` 가 항상 새 노드를 만들고 전투 복귀는 부모 노드를 재활성한다(리뷰 확인). `[이번 방문 대화]`·`[최근 대화 이력]`이 같은 방문 안의 맥락을 싣고, 이전 방문의 말만 비어 있다.

**알려진 한계**: 이전 방문에서 대화 상대(primary)가 된 적 없이 곁에서만 말한 NPC는 `encounterCount` 가 오르지 않아 발동하지 않는다(arch/139 §7.2-3과 같은 부류).

### 3.2 무엇을

- 6의 후보 중 가장 최근 턴 1개. 회상 질문 턴(입력에 회상 신호)은 제외(arch/139와 같은 규칙).
- 화자 판정: 마커 `npcId` 일치. ID 없는 마커(`@[별칭] "…"`)는 그 턴 primaryNpcId 가 이 NPC이고 화자 라벨이 이 NPC의 이름·별칭 중 하나일 때만 인정(리뷰 F4).
- 묶음 = 그 턴의 플레이어 입력 + **그 NPC의 마지막 대사 1~2개**. 서술·다른 NPC 대사는 넣지 않는다(오염 표면 최소화, 불변식 50).
- 대사는 자르지 않는다. 합계 300자 이내에서 뒤(최근)부터 대사 단위로 담는다(최소 1대사).
- 실명 은닉은 `sanitizeNpcNames`(정본 `maskHiddenNpcNames`, 불변식 51).

### 3.3 지시문 (예시 문장 없음 — arch/105 P0-3)

```
[지난 만남 원문]
이 인물과 지난 방문에서 실제로 오간 말이다. 당신을 아는 사이로 대하고, 이와 어긋나는 과거를 말하지 않는다. 이 말을 그대로 되풀이하거나 먼저 들추지 말고, 지금 장면과 이어질 때만 받아 쓴다.
(턴 N, 장소명)
플레이어: "…"
화자: "…"
```

### 3.4 배치·계측

- 순수 함수 `selectReencounterBundle()`을 `recall-block.core.ts`에 추가(스펙 동반). `context-builder.buildRecallContext` 에서 신호 없는 분기로 호출한다. 회상 블록과 같은 memoryParts HIGH 등급.
- 블록 레지스트리(arch/114 T2)에 `REENCOUNTER_SOURCE` 등록, `RECALL_SOURCE`와 배타.
- 로그 `[Reencounter] t{N} npc=… from=t{M} chars=…`. 킬스위치 `REENCOUNTER_RECALL_DISABLED`(런타임 플래그 — 기존 플래그 서비스 패턴).
- 기존 `※ 이 인물은 당신을 알아본다…` 지시(`renderRelevantNpcMemory`)와 내용이 겹치므로, 재회 블록이 실린 턴엔 그 줄을 생략한다. NPC 기록 렌더(동기)가 회상 조회(비동기)보다 먼저 돌기 때문에 회상 결과가 나온 뒤 그 줄을 제거한다(리뷰 F6).

### 3.5 위험

| 위험 | 대응 |
|---|---|
| 원문 낭독·어휘 복제(불변식 50) | NPC 대사만·마지막 1~2대사·방문당 1회. **사전 등록 롤백 기준(리뷰 F8)**: 주입 묶음과 그 턴 출력 사이 12자 이상 공통 부분 문자열이 있는 턴 비율이 **20% 이상이면 킬스위치를 켠다**. 판정은 묶음 **10건 이상** 누적 후. 측정은 정본 스크립트 `scripts/recall_block_monitor.py` 로 회상 블록(arch/139)과 함께 본다. 기준선: arch/139 §6.2 정답 10회 중 원문 낭독 0 |
| 매 방문 "지난번…" 상투 반복 | 지시문의 "먼저 들추지 말고" + 방문당 1회 |
| 이전 대사가 그 자체로 지어낸 내용 | 원문은 플레이어가 본 텍스트라 "말한 적 있음"은 사실이다. 정합 기준이 원문이므로 의도된 동작 |
| 쿼리 비용 | 조건 3에서 대부분 걸러짐. 걸린 턴만 런당 1회 인덱스 조회(arch/139와 동일 형태) |

## 4. M3 초면 분리 (`renderRelevantNpcMemory`)

- 만남 기록(`encounters.length > 0`)이 있는 NPC만 지금 형식으로 렌더한다.
- 없는 NPC는 한 줄로 묶는다: `아직 말을 나눈 적 없는 인물: 별칭(태도), …` + "초면으로 대한다". 태도 정보는 유지된다.
- "과거 상호작용을 반드시 반영 / 알아보는 반응" 지시는 `prompt-builder` 가 붙이므로(리뷰 F6), ctx 플래그 `relevantNpcHasMet` 로 만남 기록 NPC가 1명 이상일 때만 붙인다.

## 5. M4 요약 정리

- `[이야기 요약]`(`memory-renderer`): `npcsEncountered` → 표시명. 렌더러가 runState 없이 돌므로 npcStates 를 넘겨 `getNpcDisplayName` 으로 미소개 NPC는 별칭을 보장한다(리뷰 F7, 불변식 15·51). `reputationChanges` → `getFactionDisplayName`.
- `[중간 요약]` 서버 뼈대(`mid-summary.buildServerSkeleton`): `의도:` 제거(intentMemory는 서술 지시문이라 요약이 아니다), `사건:` → 사건 표시명(없으면 생략).

## 6. 범위 밖 (의도적으로 하지 않음)

- THREAD 요약 부활, `entity_facts` 재설계(arch/139 R3) — 결정 대기 항목. 이번 정정 후 실측으로 판단한다.
- V15 플레이테스트 게이트 정식화.
- `NpcTopicEntry.topic`(`buildTopicEntry`)도 `sceneFrame` 을 쓰지만, 이 값은 기억이 아니라 화제 중복 방지·관계 언급 쿨다운의 비교 키다. 바꾸면 dedup 동작이 달라지므로 이번엔 제외한다(리뷰 지적, 의도적 제외).
- 진입 턴(SYSTEM 입력) `[장소 기억: LOC_SS_INN]` 내부 ID 노출 — 별빛모래 진입 턴에서만 보인다. 워커가 시나리오 스코프를 설정하는데도 생기므로 원인이 다르다. 별도 조사.

## 7. 검증

1. 단위 스펙: `selectReencounterBundle`(첫 접촉/같은 방문 재접촉/이전 방문 없음/회상 턴 제외/600자 경계/다른 NPC 대사 제외), M3 렌더 분리, M1-d 정리 순서, M1-c 병합, M4 표시명.
2. 골든 스냅샷: 바뀐 블록만 diff가 나는지 확인 후 갱신(예상: `[관련 NPC 기록]`, `[중간 요약]`, `[이야기 요약]`).
3. 서버 빌드·전체 jest.
4. 실런 1회(graymar, 18~22턴, 스크립트 입력): 시장에서 회계사와 3~4턴 → 선술집 3~4턴 → 시장 복귀 후 회계사에게 신호어 없이 말 걸기. 확인: 재회 블록 주입, 출력이 이전 대화와 어긋나지 않음, 12자 이상 복제 0, 장소 기억에 "알아낸 단서"가 실제 공개 단서로 표시.
5. 일반 플레이테스트 10턴 1회로 게이트 회귀 확인.

완료 조건: 1~3 통과, 4에서 재회 블록이 발동하고 복제·모순이 없을 것. 실런은 1회라 "효과 확인"이 아니라 "동작·무해 확인"으로 보고한다.

## 8. fable 리뷰 반영 (2026-10-16)

판정 APPROVE_WITH_CHANGES. §1.1·§2 사실 확인은 전부 일치. 필수 변경 8건을 위 본문에 반영했다.

| # | 지적 | 반영 |
|---|---|---|
| F1 | npcKnowledge 를 importance 로 정렬하면 시간순 소비자(`.slice(-3)`·이전 공개)가 깨짐 | 삭제 후 turnNo 순 복원 (§2 M1-d) |
| F2 | `encounters.length` 는 턴 수라 긴 대화마다 DB 조회 | `encounterCount`·`lastEncounterTurn` 메모리 판정, DB는 이전 노드 조회 1회 (§3.1) |
| F3 | 조건 판정에 DONE 필터를 쓰면 FAILED 턴을 놓침 | 같은 방문 판정은 `lastEncounterTurn`(커밋 상태)이 맡아 llmStatus 무관 |
| F4 | ID 없는 마커는 화자 필터에서 빠짐 | primaryNpcId + 이름·별칭 대조 폴백 (§3.2). 동적 NPC ID 는 `NPC_DYN_1` 대문자라 기존 정규식 통과(DB 확인) |
| F5 | 동행 NPC는 매 이동 발동 | `companionNpcId` 제외 (§3.1) |
| F6 | "알아보는 반응" 지시는 prompt-builder 가 붙이고, 렌더 순서가 회상보다 앞 | ctx 플래그 + 회상 결과 후 줄 제거 (§3.4, §4) |
| F7 | 이야기 요약 렌더러에 runState 없음 → 실명 노출 위험 | npcStates 전달 (§5) |
| F8 | 불변식 50 롤백 기준 부재·600자 과대 | 20%/10건 기준 사전 등록, 300자·1~2대사 (§3.2·§3.5) |

선택 반영: `clipAtWordCore` 를 `common/text-clip.core.ts` 로 이동(F10), 레지스트리 배타가 기록용임을 명시(F9), `buildTopicEntry` 는 의도적 제외(§6).

## 9. 구현 결과 (2026-10-16)

### 9.1 변경 파일

| 범위 | 파일 |
|---|---|
| M1-a·b·e (NPC 기록) | `turns/location-turn.service.ts`, `db/types/npc-state.ts`(`addNpcKnownFact` 80자 어절 절단) |
| M1-c (장소 단서) | `db/types/structured-memory.ts`(`revealedFacts`), `db/types/permanent-stats.ts`(`discoveredClues`, 구 필드 deprecated), `engine/hub/memory-collector.service.ts`, `engine/hub/memory-integration.service.ts`, `llm/context-builder.service.ts`(렌더 "알아낸 단서") |
| M1-d (지식 장부) | `engine/hub/memory-collector.service.ts` `pruneNpcKnowledgeCore` |
| M2 (재회) | `llm/recall-block.core.ts` `selectReencounterBundle`·`renderReencounterBlock`, `llm/context-builder.service.ts` `buildReencounterContext`, `llm/prompts/prompt-builder.service.ts`(memoryParts HIGH), 레지스트리·주입 헤더, `common/runtime-flags.ts` `REENCOUNTER_RECALL_DISABLED` |
| M3 (초면) | `llm/context-builder.service.ts` `renderRelevantNpcMemory`(반환 `{text, hasMet}`), `prompt-builder` 지시 조건화(플래그 없으면 `만남` 줄 판정 — 구 픽스처 출력 불변) |
| M4 (요약) | `llm/memory-renderer.service.ts` `renderVisitLog(…, npcStates, turnNo)`, `llm/mid-summary.service.ts`(`의도:` 제거), 사건 표시명 |
| 공용 | `common/text-clip.core.ts`(`clipAtWordCore` 이동, 구 경로 재노출) |
| 계측 | `scripts/recall_block_monitor.py` — 회상·재회 블록 주입·12자 복제율, 재회 20%/10턴 롤백 판정 |

구현 리뷰 추가 반영: 주입 NPC 경로(`location-turn` Step 5)에도 `lastEncounterTurn` 기록 — 빠지면 주입으로 첫 접촉한 방문은 재회·arch/91 호명 게이트가 열리지 않았다.

### 9.2 검증

- 신규 스펙 3파일 22건(재회 선택 7·컨텍스트 빌더·프롬프트 지시 조건 9·수집/정리/장소 단서 6), 서버 전체 jest 통과, 골든 스냅샷 17건 불변(구 픽스처는 `만남` 줄이 있어 지시 유지).
- 실런 1회(run `fcc476ec`, graymar, 고정 입력 17턴, 게이트 15/15): T12 선술집에서 회계사 재접촉 → `[Reencounter] t12 npc=NPC_EDRIC_VEIL reason=SELECTED from=6 visitStart=t8 chars=88`. 출력은 T6 대사를 복제하지 않았고(12자 공통 0) 그때 대화("대가")와 어긋나지 않게 이었다. 같은 턴 `[관련 NPC 기록]`에서 "알아본다" 줄이 빠졌다. NPC "알려진 사실"에 T4 공개 단서가 실렸고, 이야기·중간 요약에서 내부 ID·지시문이 사라졌다.
- 한계: 실런 1회·재회 1건이라 "동작·무해 확인"이다. 복제율 판정은 `recall_block_monitor.py` 로 10턴 누적 후.

### 9.3 실런에서 본 범위 밖 결함

- T11 "시장 거리로 간다"(선술집 주인과 대화 잠금 중)가 `INVESTIGATE+TALK` 로 분류돼 이동이 조용히 무시됐다. 같은 런 T7(잠금 없음) 이동은 정상. 별도 조사 대상.
