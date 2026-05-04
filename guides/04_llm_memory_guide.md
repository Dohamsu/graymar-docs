# LLM & 메모리 시스템 구현 지침

> 정본 위치: `server/src/llm/`
> 설계 문서: `architecture/05_llm_narrative.md`, `18_narrative_runtime_patch.md`
> 최종 갱신: 2026-04-03 (NPC 대사 품질/후처리 필터/퀘스트 힌트 추가)

## LLM Narrative Pipeline

```
1. Server marks turn llmStatus: PENDING
2. LLM Worker polls (2s), builds L0-L4 context, calls provider
3. Worker parses [THREAD], [MEMORY], [CHOICES] tags from output
4. Client polls GET /turns/:turnNo (2s, max 15 attempts)
5. Narrator message shows loading animation → replaced with LLM text
6. Pending messages/choices flush after narrator completes
7. 실패 시: LlmFailureModal → 재시도(retry-llm API) / 서술 건너뛰기 / 닫기
```

### Message Display Order
1. SYSTEM messages (즉시 표시)
2. RESOLVE (주사위 애니메이션 1.2s → 판정 결과 공개, 즉시 표시)
3. NARRATOR (LLM 로딩 → 완료 시 교체)
4. 나머지 messages + CHOICE (narrator 완료 후 flush)

HUB↔LOCATION 전환 시: 전환 화면 없이 즉시 전환, enter narrator만 표시

---

## 강화된 LLM 파이프라인 (A56, 2026-05-04)

> 설계: `architecture/56_npc_reaction_director.md`

ResolveService 호출 직전 + 메인 LLM 호출 직전에 nano LLM 사전 결정 단계 추가:

1. **ChallengeClassifier** (`server/src/llm/challenge-classifier.service.ts`)
   - 룰 1차 게이트: NON_CHALLENGE(MOVE/REST/SHOP/EQUIP) 즉시 FREE, ALWAYS_CHALLENGE(FIGHT/STEAL/SNEAK/THREATEN/BRIBE/PERSUADE) 즉시 CHECK
   - 회색지대(TALK/OBSERVE/INVESTIGATE 등) → nano LLM 분류 → FREE/CHECK
   - FREE → ResolveService.forceAutoSuccess() (주사위 스킵)

2. **NpcReactionDirector** (`server/src/llm/npc-reaction-director.service.ts`)
   - LOCATION + primaryNpcId 있을 때만 호출
   - 출력: reactionType(7종) + refusalLevel + immediateGoal + openingStance + emotionalShiftHint + 추상 톤 3축
   - 추상 톤 3축: voiceQuality(15~25자) / emotionalUndertone(15~25자) / bodyLanguageMood(10~20자)
   - **예시 어구 절대 금지** — 추상 묘사만, LLM 자유 어휘 선택 보장

3. **메인 LLM 호출** (PromptBuilder가 톤 가이드 블록을 추가 주입)
   - `personality.signature` 노출 완전 제거 (무의식적 anchor 방지)
   - `personality.speechStyle` 어구 예시 추상화 (콘텐츠 측 작업, `content/graymar_v1/npcs.json`)

4. **5.5 마커 후처리 끝**: 마커 substring 합쳐짐 자동 복구
   - `@[X|...]` 별칭에 동일 substring(8자+) 2회 등장 → 알려진 unknownAlias로 복원
   - `[MarkerCollision]` 경고 로그

**환경변수 토글**:
```
NPC_REACTION_DIRECTOR_ENABLED=true|false  # 기본 true
CHALLENGE_CLASSIFIER_ENABLED=true|false   # 기본 true
```

**검증 효과** (5회 A/B 평균):
- 시그니처 어구율: 39.7% → 6.2% (-84%)
- TTR: 0.752 → 0.809 (+0.057)
- 마커 합쳐짐: V8 정합성 100% PASS

---

## 메모리 계층 (L0~L4+)

`server/src/llm/context-builder.service.ts`

| 계층 | 데이터 | DB 테이블 | 설명 |
|------|--------|----------|------|
| L0 | theme | run_memories | 세계관 기억 (**절대 삭제 금지**) |
| L0+ | worldSnapshot | (runState) | WorldState 요약 (시간/경계도/긴장도) |
| L1 | storySummary | run_memories | 이야기 요약 (LOCATION 방문 요약 누적) |
| L1+ | locationContext | (runState) | 현재 장소 ID |
| L1+ | midSummary | (생성) | 4턴 초과 시 초기 턴 200자 요약 |
| L2 | nodeFacts | node_memories | 현재 노드 사실 |
| L3 | locationSessionTurns | turns | 현재 방문 대화 (최대 4턴, MidSummary 적용) |
| L3 | recentTurns | turns (최근 5개) | 글로벌 최근 행동+결과 (fallback) |
| L3+ | intentMemory | (생성) | 행동 패턴 감지 결과 (6종) |
| L3+ | activeClues | (생성) | 활성 단서 (PLOT_HINT importance≥0.6, 최대 5개) |
| L4 | currentEvents | (serverResult) | 이번 턴 events |
| L4+ | agendaArc | (runState) | Agenda/Arc 진행도 |
| L4+ | npcEmotional | (runState) | NPC 감정/관계 요약 (displayName 사용) |
| L4+ | introducedNpcIds | (runState) | NPC 소개 상태 |

### Structured Memory v2 프롬프트 블록 순서
`[World State]` → `[Narrative Milestones]` → `[Story Summary]` → `[직전 장소 정보]` → `[NPC Relationships]` → `[Incident Chronicle]` → `[Extracted Facts]`

### LOCATION 떠날 때 기억 저장
go_hub/MOVE_LOCATION/RUN_ENDED → `MemoryIntegration.finalizeVisit()` → `run_memories.structuredMemory` + 호환 `storySummary` 동시 저장
- Fixplanv1 PR3: `lastExitSummary` (VisitExitSummary) 동시 생성 → 다음 장소에서 `[직전 장소 정보]` 블록으로 활용
- Fixplanv2 PR-B: `updateNpcJournal()`에서 NPC별 관련 행동만 필터 (`relatedNpcId` 매칭). 관련 행동 없는 NPC는 interaction 미기록 → npcJournal 오염 방지
- **Fixplan3 P1**: RUN_ENDED 경로에서도 `finalizeVisit()` 호출 추가 — go_hub/MOVE_LOCATION 없이 런이 끝나도 structuredMemory 보존

### VisitAction 구조 (Fixplanv2 PR-B)
`server/src/db/types/structured-memory.ts`
```
{ rawInput, actionType, outcome, eventId?, brief, summaryShort?, relatedNpcId? }
```
- `summaryShort`: 행동+결과 요약 (최대 60자). turns.service.ts에서 `summaryText` 전달. sceneFrame이 아닌 실제 행동 기반.
- `relatedNpcId`: 이 행동에 관련된 NPC ID. updateNpcJournal에서 NPC별 필터링에 사용.
- snippet 생성 우선순위: summaryShort > rawInput > brief (sceneFrame은 최후 fallback)

### NPC Knowledge 자동 수집 (Fixplanv2 PR-E)
`server/src/engine/hub/memory-collector.service.ts`
- 기존: 대화형 actionType(TALK, PERSUADE 등) + SUCCESS/PARTIAL → source=`PLAYER_TOLD`
- 추가: 이벤트 태그(EVIDENCE, SECRET, RUMOR 등) 감지 → source=`AUTO_COLLECT`
- source 타입: `PLAYER_TOLD | WITNESSED | INFERRED | AUTO_COLLECT`
- 중복 방지: 같은 턴+NPC+source 조합이면 스킵
- 렌더링 시 중복 제거: `MemoryRendererService.deduplicateNpcKnowledge()` — AUTO_COLLECT와 nonAuto가 같은 턴이면 AUTO_COLLECT 제거

---

## Token Budget (2500 토큰)

`server/src/llm/token-budget.service.ts` — 설계문서 18

### 블록별 예산
| 블록 | 토큰 | 내용 |
|------|------|------|
| SCENE_CONTEXT | 150 | [현재 장면 상태] |
| INTENT_MEMORY | 200 | [플레이어 행동 패턴] |
| ACTIVE_CLUES | 150 | [활성 단서] |
| RECENT_STORY | 700 | [이번 방문 대화] |
| PREVIOUS_VISIT | 150 | [직전 장소 정보] (PR3 추가, priority=57, minTokens=0) |
| STRUCTURED_MEMORY | 450 | [이야기 요약]+[NPC 관계]+[사건 일지]+[서사 이정표]+[기억된 사실] |
| BUFFER | 250 | 기타 블록 (장비, 성향, NPC 목록 등) |
| **TOTAL** | **2500** | |

### 토큰 추정
```typescript
estimateTokens(text: string): number → Math.ceil(text.length / 3)  // 한국어 ~3자/token
```

### 트리밍
문장 경계(. 。 !) 기준으로 자르기. 예산 초과 시 저우선 블록부터 트리밍.

---

## Mid Summary (4턴 제한 + 중간 요약)

`server/src/llm/mid-summary.service.ts` — 설계문서 18

```
locationSessionTurns > 4턴
  → 초기 턴들을 200자 요약으로 압축 (midSummary)
  → 최근 4턴만 locationSessionTurns에 유지
  → [중간 요약] 블록을 [이번 방문 대화] 앞에 삽입
```

LLM 호출 없이 서버 계산 (SoT 원칙):
- resolved incidents, NPC 상태 변화, 획득 아이템, 주요 판정 결과 포함

---

## Active Clues (활성 단서)

`server/src/llm/memory-renderer.service.ts` → `renderActiveClues()`

```
1. llmExtracted에서 category='PLOT_HINT' && importance≥0.6 추출
2. 미해결 incident 관련 단서 추출
3. 중요도 내림차순 정렬, 최대 5개
4. [기억된 사실] 블록에서 PLOT_HINT 중복 제거
```

---

## Scene Continuity System (장면 연속성)

> 정본: `context-builder.service.ts`, `prompt-builder.service.ts`

### 문제
EventMatcher가 매 턴 다른 이벤트를 선택 → sceneFrame 변경 → LLM 장면 점프

### 3가지 메커니즘

1. **`[현재 장면 상태]` 블록**: 대화 상대/세부 위치/직전 행동을 명시적 전달
2. **sceneFrame 3단계 억제**: 첫턴=전달, 1턴=참고, 2턴+=완전억제
3. **씬 이벤트 유지**: ACTION 입력 시 직전 이벤트 1턴만 자동 유지 (Fixplan3 P5: 2턴→1턴 축소)
4. **`[이번 방문 대화]` 7개 연속성 규칙**:
   - 규칙 1-5: 기본 연속성 (이전 대화 이어가기, 인물 유지 등)
   - 규칙 6: ⚠️ NPC가 알려준 정보/획득 물건/단서를 반드시 기억
   - 규칙 7: ⚠️ 이미 대화한 NPC 재등장 시 이전 대화 내용 인지

### Narrative Thread
- LLM `[THREAD]` 태그 → `node_memories.narrativeThread` 누적
- 엔트리당 max 200자, 총 예산 1200자
- 장면 흐름 블록으로 LLM에 재전달

### locationSessionTurns 서술 포함량 (거리 기반)
| 거리 | 서술 포함 | 라벨 |
|------|----------|------|
| 0 (직전) | 300자 (끝부분) | "여기서 이어쓰세요" |
| 1~2 | 250~150자 | "맥락 참고 — 복사 금지" |
| 3+ | 100자 | "요약 참고" |

---

## LLM Worker Tag Parsing

`server/src/llm/llm-worker.service.ts`

| 태그 | 저장 위치 | 용도 |
|------|----------|------|
| `[THREAD]...[/THREAD]` | `node_memories.narrativeThread` | 장면 흐름 추적 (max 200자/항목, 총 1200자) |
| `[MEMORY]...[/MEMORY]` | `run_memories.structuredMemory.llmExtracted` | LLM 추출 사실 (max 15개) |
| `[MEMORY:NPC_KNOWLEDGE:NPC_ID]` | `run_memories.structuredMemory.npcKnowledge` | NPC가 알게 된 정보 (source=WITNESSED, NPC당 max 5개) |
| `[CHOICES]...[/CHOICES]` | `turns.suggestedChoices` | LLM 제안 선택지 (JSON 파싱) |

NPC 소개 5-way 분기 (`prompt-builder.service.ts`):
- 첫만남+소개 / 재만남+소개 / 첫만남+미소개 / 이미 소개 / 미등장
- **NPC 별칭 대명사 허용** (Fixplan5): `[이름 미공개]` NPC는 첫 등장 시 별칭(unknownAlias) 사용 후, 같은 장면 내에서 "그", "그녀", "그 인물" 등 짧은 대명사로 대체 가능. 매 문장 전체 별칭 반복 방지.

`[MEMORY:NPC_KNOWLEDGE:NPC_ID]` 태그 regex (Fixplan5): `[\w:]` → `[^\]]` 변경으로 한국어 NPC 이름 포함 매칭 지원. 기존 regex는 `\w`가 한국어를 포함하지 않아 태그가 서술에 노출되는 버그 존재.

---

## 선별 주입 시스템 (Selective Injection)

> 핵심 원칙: LLM 컨텍스트에 전체 메모리를 주입하지 않고, **현재 턴에 관련된 것만 선별**하여 토큰을 절약하고 일관성을 높인다.

### 4가지 선별 메모리

| 메모리 종류 | 선별 기준 | 주입 조건 |
|------------|----------|----------|
| **NpcPersonalMemory** | 현재 턴에 등장/관련된 NPC | 해당 NPC의 personalMemory만 주입 |
| **LocationMemory** | 현재 플레이어가 위치한 장소 | 현재 장소의 locationMemory만 주입 |
| **IncidentMemory** | 현재 활성 사건 또는 관련 사건 | 관련 incidentMemory만 주입 |
| **ItemMemory** | 장착 중이거나 이번 턴에 획득한 아이템 | RARE 이상 등급 아이템의 itemMemory만 주입 |

### NPC Personal Memory

`NpcState.personalMemory: NpcPersonalMemoryEntry[]`

```
NpcPersonalMemoryEntry {
  turnNo: number          // 기록된 턴
  locationId: string      // 만남 장소
  action: string          // 플레이어 행동 요약
  outcome: string         // 결과 요약
  emotionalImpact?: string // 감정 변화
}
```

- 축적: `MemoryCollectorService.recordNpcEncounter()` — NPC 관련 행동 발생 시 자동 기록
- 선별: `ContextBuilderService` — 현재 턴에 등장하는 NPC의 personalMemory만 프롬프트에 포함
- 렌더: `MemoryRendererService` — `[NPC 개인 기록]` 블록으로 렌더링

### Location Memory

`RunState.locationMemories: Record<string, LocationMemoryEntry[]>`

```
LocationMemoryEntry {
  turnNo: number
  summary: string         // 행동+결과 요약
  significantEvent?: string  // 주요 이벤트 ID
}
```

- 축적: LOCATION 방문 중 매 턴 기록
- 선별: 현재 장소 ID로 필터 → 해당 장소의 기록만 주입
- 용도: "이 장소에서 이전에 무엇을 했는지" LLM에 전달

### Incident Memory

`RunState.incidentMemories: Record<string, IncidentMemoryEntry[]>`

```
IncidentMemoryEntry {
  turnNo: number
  action: string          // 사건 관련 행동
  impact: string          // 사건에 미친 영향
  controlDelta?: number   // control 변동
  pressureDelta?: number  // pressure 변동
}
```

- 축적: 사건 관련 행동 발생 시 자동 기록
- 선별: 현재 활성 사건 ID로 필터 → 관련 사건의 기록만 주입

### Item Memory

`RunState.itemMemories: Record<string, ItemMemoryEntry[]>`

```
ItemMemoryEntry {
  turnNo: number
  action: string          // 획득/사용/장착 등
  context: string         // 상황 설명
}
```

- 축적: RARE 이상 등급 아이템의 획득/사용/장착 시 기록
- 선별: 현재 장착 중 + 이번 턴에 획득한 아이템만 주입
- 용도: "이 아이템의 내력" LLM에 전달하여 서사적 일관성 유지

---

## NPC 대사 품질 개선 시스템

### 2-Stage NPC Reaction (NPC 반응 2단계 판정)

`server/src/turns/turns.service.ts` — Quest FACT 발견 경로 2

NPC knownFacts 공개 시 서버에서 2단계 판정을 수행한다.

**1단계: willReveal (공개 여부)**
- posture, emotional(5축), trust 값에 따라 NPC가 정보를 공개할지 결정
- trust 기준:
  - trust > 20: 공개 (직접 전달)
  - trust 0~20: SUCCESS만 공개 (간접 전달)
  - trust -20~0: SUCCESS만 공개 (관찰 힌트)
  - trust < -20: 거부 (fact 미발견 -- 다른 NPC나 이벤트로 우회 필요)

**2단계: revealMode (전달 방식)**

| revealMode | 조건 | LLM 프롬프트 효과 |
|-----------|------|-----------------|
| direct | FRIENDLY / trust > 20 | NPC가 직접 대사로 정보 전달 |
| indirect | CAUTIOUS / trust 0~20 | NPC가 돌려 말하기, 힌트로 전달 |
| observe | 비대화 행동 (OBSERVE, INVESTIGATE 등) | NPC 대사 없이 관찰로 정보 획득 |
| refuse | HOSTILE / trust < -20 | 서버에서 fact 미발견 처리 (프롬프트 미전달) |

- 비대화 행동(OBSERVE, INVESTIGATE, SEARCH, SNEAK, STEAL)은 revealMode를 강제로 `observe`로 설정
- revealMode는 `ctx.npcRevealableFact`에 저장되어 prompt-builder에서 전달 방식 분기에 활용

### NpcLlmSummary (NPC별 요약)

`server/src/db/types/npc-state.ts` — `buildNpcLlmSummary()`

NPC 재등장 시 간소 프롬프트 블록을 위한 규칙 기반 요약이다. LLM 호출 없이 서버에서 생성한다.

```
NpcLlmSummary {
  moodLine: string           // "경계를 풀기 시작했지만 여전히 신중" (~30자)
  behaviorGuide: string      // "투박한 ~하오 체, 짧은 문장" (~40자)
  lastDialogueTopic: string  // "장부 조작 흔적에 대해 이야기함" (~30자)
  lastDialogueSnippet: string// "숫자가 맞지 않는 대목이 있소..." (~40자)
  currentConcern: string     // "상단 비리 고발 여부 고민 중" (~20자)
  updatedAtTurn: number
}
```

- **첫 만남**: full emotional block (5축 감정, speechStyle, personality) 전달
- **재만남**: condensed llmSummary만 전달 (토큰 ~70% 절감)
- `moodLine`: trust + fear + posture에서 규칙 기반 생성
- `behaviorGuide`: speechStyle을 압축 + signature 첫 번째 항목
- `recentTopics`: `addRecentTopic()`으로 별도 관리 (buildNpcLlmSummary에서 생성하지 않음)

### 대화 잠금 (Conversation Lock)

`server/src/turns/turns.service.ts`

대화 계열 행동(TALK, PERSUADE, BRIBE, THREATEN, HELP, INVESTIGATE, OBSERVE, TRADE) 시 이전 턴의 대화 NPC를 자동 유지한다.

- CHOICE 선택지로 같은 이벤트가 연속되면 **최대 4턴**까지 허용
- 비대화 행동(SNEAK, STEAL, FIGHT 등) 수행 시 잠금 해제
- NPC 결정 우선순위: (1) 텍스트 매칭 NPC > (2) IntentParser targetNpcId > (3) conversationLockedNpcId > (4) event.payload.primaryNpcId

---

## LLM 후처리 필터 (P1-P5)

`server/src/llm/llm-worker.service.ts`

LLM 서술 출력에 대해 5단계 자동 후처리 필터를 적용한다.

### P1: NPC 다가오기 패턴 치환
- "조심스레 다가왔다" -> "멀찍이 서서 당신을 지켜보고 있었다" 등
- NPC가 비현실적으로 플레이어에게 다가오는 서술 패턴을 자연스러운 관찰형으로 교체

### P2: 말투 위반 감지 (Speech Violation Detection)
- 미소개 NPC가 실명으로 불리는 케이스 감지
- 금지 패턴: `자네`, `이보게`, `~일세`, `해요/세요/합니다` (경어), `~야/~해/~잖아` (반말)
- 위반 횟수를 로깅하여 프롬프트 개선에 활용

### P3: 빈번 위반 직접 치환
- "자네" -> "그대"
- "이보게" -> "듣고 계시오"
- 가장 자주 발생하는 말투 위반을 즉시 교정

### P4: NPC 이름 sanitize
- **서술**: 미소개 NPC의 실명을 `unknownAlias`("수상한 남자", "누군가" 등)로 치환
- **선택지 label**: 선택지 텍스트에서도 동일하게 미소개 NPC 실명을 별칭으로 치환
- ContentLoaderService에서 NPC 정의(이름, unknownAlias)를 참조

### P5: 서술 경어체 -> 해라체 변환
- 큰따옴표 바깥(서술부)에서만 적용, 큰따옴표 안(NPC 대사)은 유지
- 서술과 대사를 분리한 뒤 서술부의 경어체 어미를 해라체로 자동 치환
- 예: "~했습니다" -> "~했다", "~보였습니다" -> "~보였다"

---

## LLM 출력 후처리 추가 단계 (2026-04-15)

기존 Step A~D(P1~P5 필터)에 추가:
- **Step E**: 대사 내부 "NPC이름:" 프리픽스 제거 — LLM이 대사 텍스트에 화자 이름을 넣는 경우 제거
- **Step F**: NPC 불일치 교정 — primaryNpcId와 LLM 출력의 첫 @마커 NPC가 다르면 마커+본문을 강제 교체

---

## 퀘스트 방향 힌트 (pendingQuestHint)

`server/src/turns/turns.service.ts` — FACT 발견 후 힌트 생성
`server/src/llm/prompts/prompt-builder.service.ts` — HINT_DIRECTIVES 프롬프트 삽입

### 동작 흐름

```
FACT 발견 (이번 턴)
  → quest.json에서 해당 fact의 nextHint 조회
  → RNG로 5가지 hintMode 중 하나 선택
  → pendingQuestHint = { hint, setAtTurn, mode } 저장 (RunState)
  → 다음 턴 LLM 프롬프트에서 HINT_DIRECTIVES로 전달
  → setAtTurn < turnNo-1 이면 만료 삭제 (1턴 소비)
```

### 5가지 hintMode

| hintMode | 전달 방식 |
|----------|----------|
| OVERHEARD | 지나가는 사람들의 대화 일부가 귀에 스쳐 들어오는 장면 |
| DOCUMENT | 바닥에 떨어진 낡은 쪽지/찢긴 영수증/반쯤 지워진 메모 발견 |
| SCENE_CLUE | 환경에서 이상한 점(발자국, 긁힌 자국, 열린 문) 포착 |
| NPC_BEHAVIOR | 근처 인물이 수상한 행동(서류 급히 숨기기, 골목으로 사라지기) 목격 |
| RUMOR_ECHO | 이전에 들었던 소문/정보가 현재 상황과 연결되는 순간 |

- 서버 RNG(`rng.range`)로 모드를 무작위 선택하여 매번 다른 전달 방식 사용
- LLM 프롬프트에서 `[단서 방향]` 블록으로 삽입 (HINT_DIRECTIVES 매핑)
- 힌트 내용(hint) 자체는 quest.json의 `nextHint` 필드에서 가져옴
