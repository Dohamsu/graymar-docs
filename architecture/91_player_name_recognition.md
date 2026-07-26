# 91. 플레이어 이름 인지 — 프롤로그 통성명 + 재회 호명

> 상태: ✅ 구현됨 (2026-07-26)
> 관련: arch/66(NPC 자기소개) · arch/64(이름 공개 무결성) · arch/82 #7(첫 조우 개방 깊이) · arch/88 C(encounterCount)
> 불변식: 41/42/50(구체 어휘 anchor) · 2(소프트 상태 CAS) · 15(이름 공개 규율)

---

## 1. 문제

캐릭터 생성에서 받은 이름(`characterName`, 1~8자)이 **게임 플레이 안에서 전혀 쓰이지 않는다.**

### 1.1 현재 흐름 (전수 조사)

| 단계 | 위치 | 내용 |
|---|---|---|
| 입력 | `StartScreen.tsx:156,1342` Step 3 | 선택 입력. **실측 148/252 런(59%)이 지정** |
| 저장 | `runState.characterName` | JSONB |
| 소비 ① | `runs.service.ts:673` | L0 테마 `{CHARACTER_NAME}` 치환 → 시스템 프롬프트 `## 세계관 기억` JSON |
| 소비 ② | `summary-builder.service.ts:234,353` | 엔딩 여정 요약 도입 문장 |
| UI | CharacterTab / StartScreen 이어하기 / EndingsList / JourneySummary | 표기만 |

**LLM 레이어(`context-builder` / `prompt-builder` / `dialogue-generator` / nano 전체)는 `characterName`을 한 번도 참조하지 않는다.** 이름은 L0 문자열에 박혀 들어갈 뿐 호명 지침·게이트·상태가 없다.

오히려 억제 방향이다 — `system-prompts.ts:54` 규칙 E("주인공 3인칭 금지, 주인공은 '당신'뿐"), 규칙 C(어체별 `그대/당신/너/자네` 한정).

### 1.2 실측

이름 지정 런의 `llm_output` 800+턴 중 이름 등장 = **1건**. 그마저 정상 사용이 아니다:

```
[김리 런 T4] 처음 만난 구두닦이 소년(첫 등장, 미소개)
@[재빠른 구두닦이 소년] "이보시오, 김리 영감! 영감이라면 내게 좋은 정보를…"
```

플레이어가 이름을 밝힌 적이 없는데 L0 세계관 기억에서 읽고 호명했다. **이름을 알 서사적 경로가 0인 상태로 L0에만 노출된 구조적 누수**다.

NPC의 실제 플레이어 호칭 분포(30일): 당신 341 / 그대 84 / 손님 57 / 젊은이 1 — 전부 2인칭·일반 호칭.

### 1.3 이미 있는데 비어 있는 자리

`prompt-builder.service.ts:3715-3730`의 관계 깊이 4단계 가이드가 매 턴 주입된다:

```
관계 깊이: 재회 — 얼굴을 기억함. 이전 대화를 언급하며, 조금 더 편하게 대화
```

**"얼굴을 기억함"까지만 말하고, 재회를 알리는 가장 강한 신호인 이름 호명이 비어 있다.** 이 문서의 본체는 저 자리를 조건부로 채우는 것이다.

---

## 2. 설계 원칙

1. **전역 허용 금지** — 불변식 50. 이름은 강한 anchor다. 상시 주입하면 저모델이 매 대사마다 붙이고, 서술 본문 3인칭 사용은 규칙 E(2인칭 몰입)를 파괴한다.
2. **arch/66과 대칭** — NPC 이름이 근거를 갖고 공개되듯, 플레이어 이름도 "알게 된 NPC만" 부른다.
3. **호명은 대사 안에서만, 재회 첫 턴 1회** — 서술 본문 3인칭 금지는 그대로 유지.
4. **주입은 데이터로, 어구 예시는 금지** — 불변식 42. "○○ 님", "○○ 씨" 같은 예시를 넣으면 그 형태로 고착한다. 어체 규칙만 참조시킨다.
5. **사후 삭제는 최후 수단** — 누수 제거보다 계측 로그 우선(§5.3).
6. **이름 미지정 런(41%)은 완전 무동작** — 플래그가 안 켜진다.

---

## 3. Part A — 프롤로그 통성명

### A1. 콘텐츠: `prologue.lines`에 이름 교환 왕복 추가 (4팩)

`content/{graymar_v1,silverdeen_v1,star_sand_v1,karnholt_v1}/scenario.json`

현재 graymar 프롤로그는 로넨이 자기 이름만 밝히고 끝난다. 의뢰 본론 진입 **전**에 3줄을 넣는다:

```json
"@[로넨|/npc-portraits/ronen.webp] \"실례합니다. 항만 노동 길드 서기관 로넨이라고 합니다.\"",
"",
"@[로넨|/npc-portraits/ronen.webp] \"뭐라고 불러 드리면 되겠습니까?\"",
"",
"당신은 이름을 밝혔다.",
"",
"@[로넨|/npc-portraits/ronen.webp] \"{CHARACTER_NAME}. 기억하겠습니다.\"",
"",
"당신은 잔을 내려놓고 사내를 살폈다. …"
```

- **프롤로그는 LLM이 아니라 하드코딩 스크립트다** — 남발 위험 0, 어체 훼손 0.
- 어체는 팩별 프롤로그 NPC의 `speechRegister`에 맞춘다. graymar 로넨 = 합쇼체(arch/69에서 전환 완료). 나머지 3팩은 각 `prologue.npcId`의 register를 확인해 문장을 맞춘다.
- `{CHARACTER_NAME}` 대사는 **호격 1회만** — 뒤 라인에 반복하지 않는다.

### A2. 코드: 치환 + 미지정 시 라인 제거

`server/src/runs/runs.service.ts:779-782` — 기존 `{HOOK}` 패턴을 그대로 확장한다.

```ts
const hook = preset?.prologueHook ?? '';
const pName = characterName?.trim() ?? '';
const lines = (pMeta.lines ?? [])
  .filter((l) => hook !== '' || !l.includes('{HOOK}'))
  .filter((l) => pName !== '' || !l.includes('{CHARACTER_NAME}'))
  .map((l) => l.replace('{HOOK}', hook).replace('{CHARACTER_NAME}', pName));
```

- 이름 미지정 런은 `{CHARACTER_NAME}` 라인이 통째로 빠진다. 다만 "뭐라고 불러 드리면…" / "당신은 이름을 밝혔다" 2줄이 남으면 대화가 붕 뜬다 → **이름 교환 3줄을 한 덩어리로 묶는 마커가 필요**하다.
- 처리: 3줄 모두에 `{CHARACTER_NAME}` 토큰을 심는 대신, **콘텐츠에서 이름 교환 라인에 `{NAME_ASK}` 접두 토큰을 붙이고** 미지정 시 `{NAME_ASK}` 포함 라인 전체를 필터, 지정 시 토큰만 제거하는 방식이 명확하다.

```ts
.filter((l) => pName !== '' || !l.includes('{NAME_ASK}'))
.map((l) => l.replace('{NAME_ASK}', '').replace('{CHARACTER_NAME}', pName))
```

빈 줄 정리는 기존 `[atmo, '', ...lines].join('\n')` 뒤에 `\n{3,}` → `\n\n` 압축 1줄로 마감한다.

### A3. 상태: 프롤로그 의뢰인은 처음부터 이름을 안다

`runs.service.ts:363-366`에 이미 프롤로그 NPC를 `introduced = true`로 세팅하는 자리가 있다. 바로 옆에 붙인다.

```ts
if (npcDef.npcId === this.content.getPrologueMeta().npcId) {
  npcStates[npcDef.npcId].introduced = true;
  npcStates[npcDef.npcId].introducedAtTurn = -1;
  if (characterName?.trim()) {
    npcStates[npcDef.npcId].knowsPlayerName = true;
    npcStates[npcDef.npcId].playerNameLearnedTurn = -1;
  }
}
```

---

## 4. Part B — 통성명 기반 재회 호명

### B1. 상태 필드 (`db/types/npc-state.ts`)

`NPCState`에 3개 추가. 전부 옵셔널(기존 런 호환).

```ts
/** arch/91 — 이 NPC가 플레이어의 이름을 안다 (통성명 성립). */
knowsPlayerName?: boolean;
/** 이름을 알게 된 턴. 소개 턴 당일 호명 방지용(arch/66 2턴 분리 대칭). */
playerNameLearnedTurn?: number;
/** encounterCount를 마지막으로 증가시킨 턴 번호 — "재회 첫 턴" 판정.
 *  lastEncounterNodeId(방문 단위 dedup)와 짝. */
lastEncounterTurn?: number;
```

`knowsPlayerName`은 `introduced`에서 파생시키지 않고 **실필드로 둔다** — 트리거 (c)(플레이어 자발 발화)를 나중에 붙일 때 파생식이 깨지고, 이월 런(`carry-over.ts:24,96`)에서 소개 상태만 넘어오는 경로와도 분리해야 한다.

### B2. 세팅 트리거 (3곳, 이것만)

| # | 지점 | 조건 |
|---|---|---|
| **(a)** | `runs.service.ts:363` 런 생성 | 프롤로그 의뢰인 — §A3 |
| **(b)** | `llm-worker.service.ts` 5.11 소개 확정부(≈779-900) | 자기소개 성사 턴에 `introduced=true`와 **동시** 세팅. `playerNameLearnedTurn = pending.turnNo` |
| **(c)** | (후속) `turns.service` 인텐트 처리 | `rawInput`에 `characterName` 포함 → 그 턴 primary NPC에 세팅. **본 계획에서는 구현하지 않고 필드만 열어둔다** |

**(b) 주의 — 불변식 2.** 워커에서 `runState`를 쓰는 경로는 반드시 `applyRunStatePatch` CAS를 경유한다. `introduced` 세팅과 같은 패치에 묶어 원자적으로 처리한다(별도 패치로 나누면 lost update — arch/60 P0와 동일 함정).

`tier === 'BACKGROUND'` NPC는 제외한다(통성명하지 않는다).

### B3. 재회 첫 턴 판정 (`turns.service.ts:3088-3095`)

encounterCount 증가 블록에 턴 번호를 같이 남긴다.

```ts
if (npcStates[npcId].lastEncounterNodeId !== currentNodeId) {
  npcStates[npcId].encounterCount = (npcStates[npcId].encounterCount ?? 0) + 1;
  npcStates[npcId].lastEncounterNodeId = currentNodeId;
  npcStates[npcId].lastEncounterTurn = turnNo;   // ← 추가
}
```

증가가 **방문(LOCATION 노드 instance) 단위 1회**이므로(arch/88 C), `lastEncounterTurn === 현재 턴`이 곧 "이번 방문에서 처음 마주친 턴"이 된다. 같은 장소에 머무는 동안은 다시 켜지지 않는다.

### B4. 판정 코어 (신규 export 함수)

`db/types/npc-state.ts`에 `shouldIntroduce`와 나란히 둔다 — 유닛 테스트 대상이자 정본.

```ts
export function shouldCallPlayerName(
  npcState: NPCState | undefined,
  playerName: string | null | undefined,
  currentTurn: number,
  tier: string | undefined,
): boolean {
  if (!playerName?.trim()) return false;          // 이름 미지정 런
  if (!npcState?.knowsPlayerName) return false;   // 통성명 안 함
  if (tier === 'BACKGROUND') return false;
  if ((npcState.encounterCount ?? 0) < 2) return false;            // 재회부터
  if (npcState.lastEncounterTurn !== currentTurn) return false;    // 재회 첫 턴만
  if ((npcState.playerNameLearnedTurn ?? -1) >= currentTurn) return false; // 소개 턴 당일 제외
  return true;
}
```

### B5. 프롬프트 주입 (`prompt-builder.service.ts:3715-3730`)

`depthGuide`에 조건부 1줄을 덧붙인다. 구체 어구·호칭 예시는 넣지 않는다(불변식 42).

```ts
const nameCall = shouldCallPlayerName(npc, ctx.playerName, sr.turnNo, npcDef?.tier)
  ? `\n    ⚠️ 이 인물은 당신의 이름 "${ctx.playerName}"을 안다 — 이번 재회의 첫 인사 대사에서 **한 번만** 이름을 부른다. 호칭 형태는 이 인물의 어체를 따른다. 이후 문장·서술 본문에서는 이름을 쓰지 않는다(주인공 지칭은 "당신").`
  : '';
```

`ContextBuilder`에 필드 하나를 추가한다 — `playerName: string | null` (`runState.characterName`에서 읽음, `context-builder.service.ts:1039` 인근 반환 객체).

### B6. 자기소개 상호 교환 (`dialogue-generator.service.ts:454`)

`generateIntroDialogue` input에 `playerName?: string`을 추가하고, 있을 때만 user 메시지에 1줄을 더한다.

```
상대는 방금 자기 이름을 "○○"라고 밝혔습니다. 그 이름을 한 번 되받아 부르며 자기 이름을 밝히세요.
```

- `validate()`는 **건드리지 않는다** — 현재 NPC 실명 포함 + 어체 검증만 한다. 플레이어 이름 포함은 강제하지 않는다(2회 재시도 실패 시 템플릿 fallback으로 떨어지는데, 조건을 늘리면 fallback률만 올라간다).
- **템플릿 fallback 5종은 그대로 둔다.** 이름 변형을 넣으면 매 소개마다 같은 문장이 반복되어 anchor가 된다.
- 재등장 통성명 프레이밍(`llm-worker.service.ts:2980-2990`의 `isReencounter` 분기)은 그대로 유효 — `situationContext`만 기존대로 넘긴다.

### B7. 마커 안전망 (**B5보다 먼저 들어가야 한다**)

호명이 생기기 전에 방어가 서 있어야 한다.

1. **`PLAYER_ALIASES` 동적화** — `stream-classifier.service.ts:44`(모듈 const), `npc-dialogue-marker.service.ts:753`(static readonly). 둘 다 런별 `characterName`을 알 수 없는 static 구조다. 호출부에서 런 캐릭터명을 파라미터로 받아 `has()` 검사 시 합쳐 보도록 바꾼다(Set 복사 또는 `alias === playerName` 단축 검사).
2. **`resolveNpcId` 퍼지매칭 가드** — 레벤슈타인 거리 2 매칭 앞에 플레이어 이름 배제. 실제 DB에 "김리"와 "김진원"이 동시에 존재해 오매칭 사거리 안이다.
3. **콜론 라벨 3-Tier 매칭**(arch/65 부록 C) — `"김리: ..."` 형태가 무명 NPC 라벨로 잡히지 않도록 플레이어 이름을 후보에서 제외.

### B8. 누수 계측 (제거는 하지 않는다)

L0에는 이름이 계속 노출되므로 미허용 턴 호명이 남을 수 있다(현재 1/800). **후처리 삭제는 문장 파괴 위험이 있어 최후 수단**이므로, 먼저 로그만 남긴다.

`llm-worker` 후처리 5.x 구간에서 — 이번 턴 등장 NPC 중 `shouldCallPlayerName` 통과자가 없는데 대사 안에 `playerName`이 있으면:

```
[PlayerNameLeak] turn=N npc=NPC_X — 미허용 호명 감지: "…"
```

2주 실측 후 빈도가 유의미하면 arch/64 R7과 같은 새니타이즈 패턴으로 승격한다.

---

## 5. 작업 순서

| # | 범위 | 파일 | 커밋 단위 |
|---|---|---|---|
| 1 | Part A 전체 | `scenario.json` ×4, `runs.service.ts` | 독립 — 새 런 1회로 즉시 검증 |
| 2 | B7 마커 안전망 | `stream-classifier`, `npc-dialogue-marker` | 방어 선행 |
| 3 | B1·B2·B3 상태 | `npc-state.ts`, `runs.service.ts`, `llm-worker.ts`, `turns.service.ts` | CAS 검토 필수 |
| 4 | B4·B5 판정+주입 | `npc-state.ts`, `context-builder.ts`, `prompt-builder.ts` | 유닛 동반 |
| 5 | B6 자기소개 교환 | `dialogue-generator.ts`, `llm-worker.ts` | |
| 6 | B8 계측 | `llm-worker.ts` | |

서버 8파일 + 콘텐츠 4파일. 신규 DB 컬럼 없음(전부 `runState` JSONB).

---

## 6. 검증

**유닛** — `shouldCallPlayerName` 6케이스: 이름 미지정 / `knowsPlayerName=false` / BACKGROUND / 소개 턴 당일 / 재회 첫 턴(통과) / 같은 방문 2번째 턴(차단). 프롤로그 라인 필터 2케이스(지정·미지정).

**실런** — `playtest.py --agent devotee --turns 15`(단일 NPC 전담 우호 = 재회 다발, 이 경로를 정확히 밟는다) + `--agent chatty --turns 12`(다수 NPC 재회). **테스터 포인트 잔액 확인 필수**(0이면 0턴 false-PASS — 충전 코드 `Z48S-FB46`).

**지표**

| 항목 | 기준 |
|---|---|
| 허용 턴 호명 성사 | devotee 런에서 재회 턴 ≥1회 실제 호명 |
| 호명 남발 | 한 턴 서술 내 이름 등장 ≤1회, 서술 본문(대사 밖) 0회 |
| 누수 | `[PlayerNameLeak]` 로그 건수 계측(기준선 없음, 관찰) |
| 회귀 | 자기소개 성사율(arch/66) 유지 · V8 마커 정합 · V9 어체 · audit 9/9 |

**사후 DB 실측** — §1.2와 동일 쿼리로 "이름 등장 턴 / 전체 턴" 재측정, 등장 턴이 전부 재회 첫 턴인지 대조.

---

## 7. 구현 결과 (2026-07-26)

서버 9파일 + 콘텐츠 4팩 + `scripts/playtest.py`(`--character-name` 옵션 신설). 신규 DB 컬럼 0.
린트 0/0 · 빌드 통과 · 유닛 1,584 passed(신규 8) · playtest 12/12 PASS ×3런.

### 실측

**프롤로그 통성명(A)** — graymar 실런 렌더:

```
@[로넨] "실례합니다. 항만 노동 길드 서기관 로넨이라고 합니다."
당신은 잔을 내려놓고 사내를 살폈다. …
@[로넨] "실례가 아니라면, 뭐라고 불러 드리면 되겠습니까?"
당신은 짧게 이름을 밝혔다.
@[로넨] "에반. 기억하겠습니다."
```

이름 미지정 런은 `{NAME_ASK}` 3줄이 통째로 빠져 기존 흐름과 동일(4팩 지정/미지정 8케이스 렌더 확인).

**상호 통성명(B6)** — 어체를 지키며 되받기 성립. 3NPC 실측:

| 턴 | NPC | 어체 | 대사 |
|---|---|---|---|
| T14 | 레닉 | BANMAL | `"에반, 이름 참 듣기 좋네. 난 레닉이라고 해."` |
| T20 | 하를런 | HAOCHE | `"에반이라 하였소? 내 이름은 하를런 보스라고 하오."` |
| T7 | 에드릭 | HAOCHE | `"세인이라 하였소? 나는 에드릭 베일이라고 하오. …"` |

**재회 호명(B5)** — 선술집 재방문(`encounterCount` 1→2, `lastEncounterTurn=35`):

```
@[오웬] "에반, 다시 오셨구려. 마침 잔을 닦던 참이었소. …"
… (같은 턴 두 번째 대사) "그나저나 이른 새벽부터 발걸음을 하신 걸 보니…"
```

인사 대사에서 1회 호명 후 같은 턴 후속 대사에서는 반복 없음 — 설계 의도대로.

### 게이트 도달 빈도 → A안으로 재설계 (§9)

초기 구현(재회 단독 트리거)은 실전에서 거의 열리지 않았다. 원인 규명과 재설계는 §9.

### 계측 센서 수정 1건

`auditPlayerNameLeak`이 소개 턴의 상호 통성명 대사를 누수로 오경보했다(3회 실측). `shouldCallPlayerName`은 재회 게이트라 소개 당일을 제외하므로 통과하지 못한다. 1차 수정(`playerNameLearnedTurn === turnNo` 인정)도 실패 — `llmContext.npcStates`는 **턴 시작 스냅샷**이라 5.11 CAS가 방금 쓴 값이 보이지 않는다. 같은 스냅샷의 `newlyIntroducedNpcIds`로 판정해 해소(수정 후 오경보 0, Exchange 로그만 발생).

### 부수 발견

`matchNpcFromContext`의 이름 매칭에 실제 오귀속 사거리가 있었다 — 플레이어 이름이 NPC 이름을 부분 포함하면(플레이어 "브렌" vs NPC "브렌 대위"의 alias "브렌") 플레이어를 호명한 문맥이 그 NPC 발화로 귀속된다. 매칭 구간이 플레이어 이름 출현 구간과 겹치면 버리도록 방어 추가(1차·fuzzy·after 3경로).

---

## 8. 명시적 비목표

- 서술 본문 3인칭 호명(규칙 E 유지 — 2인칭 몰입 유지)
- 매 턴 호명 / 관계 깊이 3·4단계에서의 상시 호명
- 소문·시그널 피드로의 이름 확산(별건 — Mark/Heat 트랙과 함께 검토)
- 파티 `nickname` ↔ 솔로 `characterName` 정체성 통합(모순은 실재하나 범위 밖)
- 엔딩 피날레 호명(1줄이면 되지만 엔딩 톤 검증이 따로 필요)
- 트리거 (c) 플레이어 자발 발화 — 필드만 열어두고 미구현

---

## 9. A안 — 친밀도 파생 지표 (2026-07-26 후속)

### 9.1 진단: 게이트가 아니라 `encounterCount`가 문제였다

재회 트리거가 실플레이에서 열리지 않아 원인을 추적한 결과, **arch/91 범위를 넘는 구조 문제**가 드러났다.

**(a) `encounterCount`는 "서로 다른 방문 수"다.** arch/88 C가 방문(노드 instance) 단위 1회로 정확히 고친 뒤, 이 값은 재방문 없이는 절대 오르지 않는다. 그런데 실플레이는 한 장소에 오래 머물며 한 NPC와 깊이 대화하는 패턴이다.

arch/88 이후 실유저 런 5개(평균 22.4턴) 전수:

| NPC | encounterCount | appearanceCount |
|---|---|---|
| 이렌 | **1** | **15** |
| 유르마 | 1 | 11 |
| 루오르 | 1 | 9 |

**재회 0건.** 서술에 15번 등장하며 대화한 상대의 조우 횟수가 1이다.

> 구 로직(arch/88 이전) 런에서는 같은 방문 안에서도 증가해 값이 부풀려졌다(하를런 12, `lastEncounterNodeId` 없음). 신·구를 섞으면 "실유저 절반이 재회"라는 잘못된 결론이 나온다 — 반드시 `lastEncounterNodeId` 존재 여부로 분리해서 봐야 한다.

**(b) 같은 병을 앓던 소비처가 더 있었다.** 관계 깊이 4단계(`prompt-builder`)가 같은 값을 쓰고 있어 **전 NPC가 영구히 "첫 만남"** 이었다. 실유저 런 프롬프트 9턴 연속 실측:

```
관계 깊이: 첫 만남 — 경계하며 최소한의 반응. 정보를 쉽게 주지 않음
감정: 마음을 열기 시작했…
```

"첫 만남이라 경계한다"와 "마음을 열기 시작했다"가 한 프롬프트에 공존한다. 안면(4~6)·깊은 관계(7+) 단계는 도달 불가였다. 재등장 말투 간소화(`isReEncounter`)도 같은 이유로 영구 미발동이었다(항상 풀 speechStyle 주입 = 토큰 낭비 + 반복 anchor).

**(c) NPC 장소 귀속은 원인이 아니다.** graymar NPC 43명 **전원** 스케줄 보유, **40명이 시간대별로 장소를 옮긴다**(하를런 DAWN/DAY 항구 → DUSK/NIGHT 선술집). 장소를 옮겨도 같은 NPC를 만나는 경로는 열려 있고 실측도 됐다(마이렐을 NIGHT 항구에서 조우). 다만 arch/81 2차로 대화가 0-cost가 되어 25턴 런의 `globalClock`이 13tick(하루 남짓)에 머물러, 스케줄 이동 자체가 드물다. 여기에 대화 잠금 4턴이 겹쳐 **한 방문(6턴) = NPC 1~2명**이 된다.

### 9.2 처방

`encounterCount`(방문 수)는 **건드리지 않는다** — arch/88이 고친 정확성을 보존한다. 소비 측이 실제로 원하는 "얼마나 겪었나"를 파생값으로 분리한다.

```ts
// npc-state.ts
computeFamiliarity(st) = encounterCount + floor(appearanceCount / 2)
                         → knowsPlayerName이면 최소 2 보장
```

- 서술 등장은 같은 방문 안의 반복도 세므로 2회를 1로 환산.
- **통성명 보정**: 이름을 주고받은 상대를 "첫 만남"으로 서술하면 자기모순이라 최소 '재회' 단계를 보장한다(하를런 T21 실측 — 같은 프롬프트의 "이름을 안다" + "첫 만남이라 경계"가 충돌해 LLM이 호명을 버렸다).
- 임계는 기존 그대로: ≤1 첫 만남 / 2~3 재회 / 4~6 안면 / 7+ 깊은 관계.

**전환한 소비처 3곳** — 관계 깊이 4단계 · `isReEncounter`(말투 간소화) · `isFirstEncounter`.
**전환하지 않은 곳** — `shouldIntroduce`의 encounterCount 임계(CAUTIOUS 2·CALCULATING/HOSTILE 3)는 그대로 뒀다. `appearanceCount` 강제 소개 경로(3~5회)가 이미 그 역할을 대신하고 있어 실질 무해하고, 소개 타이밍 변경은 arch/66 검증 자산에 영향을 준다. `npc-reaction-director`의 `만난 횟수` nano 입력도 라벨 의미가 "방문 수"라 유지.

### 9.3 호명 게이트 재설계

재회 단독 → **대화가 새로 시작되는 순간 1회**, 두 타이밍:

| # | 조건 | 의미 |
|---|---|---|
| ① | `playerNameLearnedTurn === currentTurn - 1` | 통성명 직후 턴 — 막 이름을 주고받았으니 한 번 불러본다 |
| ② | `lastEncounterTurn === currentTurn` | 새 방문 첫 조우 턴 — 재회 인사 |

친밀도 하한은 두지 않는다. `knowsPlayerName` 자체가 "소개 성사 + BACKGROUND 아님"을 통과한 신호이고, 하한을 걸면 FRIENDLY NPC(첫 조우에 소개, familiarity 1)가 통성명하고도 영영 못 부르는 모순이 생긴다(하를런 T20 실측).

### 9.4 R4 권장 호칭과의 충돌 (핵심 함정)

게이트를 고쳐 지시가 정상 주입된 뒤에도 LLM이 이름을 안 불렀다. 원인은 같은 블록의 **R4 권장 호칭**(arch/51 §B)이었다:

```
⚠️ 권장 호칭: "형제" — 이 NPC는 사용자를 항상 "형제"(으)로 부른다.
⚠️ 이 인물은 당신의 이름 "하윤"을 안다 — … 한 번만 이름을 부른다.
```

**"항상 X로 부른다"가 뒤에 와서 호명 지시를 덮어썼다.** 저모델에 상충 지시 둘을 경쟁시키면 나중 것·강한 것이 이긴다. 두 지시를 하나로 합쳐 해결했다 — 호명이 열린 턴에는 R4 문구 자체가 예외를 품는다:

```
⚠️ 권장 호칭: "자네" — … 단 이번 턴 첫 대사에서만 이름("지운")으로 부르고, 이후는 "자네".
```

이를 위해 `canCallPlayerName`을 R4 블록 **앞에서** 선계산한다(순서 의존).

### 9.5 검증

**① 통성명 직후 호명** — T14 통성명 → T15 발동:

```
T14 @[입이 가벼운 술꾼] "지운, 이름 참 근사하네. 나는 레닉이라고 해."
T15 @[레닉] "지운, 자네는 참 집요하네. 내 입에서 뭘 더 빼내고 싶은 건지…"
```

이름으로 부른 뒤 권장 호칭 "자네"로 이어간다 — 통합 지시대로.

**② 재회 호명** — 선술집 재방문(`encounterCount` 1→2): `@[오웬] "에반, 다시 오셨구려…"`

**관계 깊이 정상화** — 같은 런에서 첫 만남 5턴 / 재회 4턴으로 분화(A안 이전 100% 첫 만남).

**남발 없음** — 20턴 중 이름 등장 3턴(소개·통성명·① 호명), 서술 본문 3인칭 0.

유닛 33(친밀도 7 + 게이트 10) · 전체 1,592 passed · 린트 0/0 · playtest 12/12 PASS.

> V8 1건 실패는 무관 — 배경 인물의 홑따옴표 소문 서술("약초 채집인이 …나지막이 속삭인다")을 센서가 화자로 오인한 것으로, 플레이어 이름 경로와 접점이 없다.

### 9.6 남은 관찰

- **`shouldIntroduce`의 encounterCount 임계는 여전히 사문화** 상태다(appearanceCount 경로가 대신 수행). 무해하지만 코드가 의도를 오해하게 만든다 — 정리 시점은 arch/66 재검증과 묶는 편이 안전.
- **시간이 거의 흐르지 않는다**(25턴에 13tick). arch/81 2차의 의도된 결과지만, NPC 스케줄 이동·시간대별 이벤트가 사실상 잠들어 있다는 부작용은 별도 검토 대상.
