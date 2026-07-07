# 58. Fact Reveal Unification — 단서 기록·서술 단일화

> **목표**: NPC 경로 단서 발견에서 "서버가 기록하는 fact"와 "LLM이 서술하는 fact"를 반드시 같은 fact로 만든다.
> **계기**: 사용자 피드백 — "NPC가 다음 단서를 알려주는 프로세스가 어색하다." 분석 결과 취향 문제가 아니라 구조적 데스싱크.
> **선행**: architecture/46 (Fact Pool + NPC Continuity) · architecture/34 (Player-First)
> **작성**: 2026-07-03
> **Status**: ✅ 구현됨

---

## 1. 문제 — 한 번의 발견에 세 시스템이 따로 동작

턴 N에서 NPC 경로로 fact가 발견될 때:

| 시스템 | 위치 | fact 선택 기준 |
|--------|------|----------------|
| ① 발견 기록 | turns.service 경로 2 | `getRevealableQuestFact()` — **npcs.json knownFacts 배열 순서** (질문 주제 무시) |
| ② 서술 주입 | context-builder (arch/46) | **입력 키워드 ↔ facts.json 매칭**, `discoveredQuestFacts` 제외 |
| ③ 다음 힌트 | pendingQuestHint | ①이 기록한 fact의 nextHint (다음 턴 1회 연출) |

### 1.1 구조적 데스싱크

①이 fact Y를 `discoveredQuestFacts`에 넣고 **커밋한 뒤** LLM 워커가 컨텍스트를 빌드한다.
그 시점에 Y는 이미 발견됨 목록에 있어 ②의 후보에서 **제외**된다.
→ **서버가 방금 발견 처리한 fact는 절대 서술 블록으로 주입될 수 없다.**

증상:
- 플레이어가 정확히 Y 주제를 물으면 → ② 후보 0개 → 잡담 모드, 또는 다른 미발견 fact X의 detail을 서술 (X는 미기록)
- UI에는 "단서 발견(Y)"이 뜨는데 NPC 대사는 Y와 무관하거나 딴 단서
- 다음 턴 [단서 방향] 힌트는 Y 기준 → 직전 대화 흐름과 단절

### 1.2 순서 기반 공개

`getRevealableQuestFact`는 질문 주제와 무관하게 knownFacts 순서대로 "다음" fact를 반환.
예: 하를룬에게 밀수 루트를 물어도 첫 미발견인 "장부 소문"이 기록됨.

### 1.3 미기록 detail 누출 (②의 mode A)

②가 키워드로 고른 fact X의 detail을 서술에 공개하지만 X는 발견 기록에 남지 않음
→ 플레이어는 들었는데 퀘스트 로그에는 없는 정보.

## 2. 설계

### 2.1 선택 단일화 — 주제 우선 + 순서 fallback

`QuestProgressionService.selectRevealableFact(npcId, rawInput, runState)`:

1. rawInput의 한글 2자+ 토큰 → `content.getFactsByKeywords()` (미발견분만)
2. 현재 NPC가 `knownBy`로 보유한 매칭 fact 있으면 → 그 fact (`matchedByTopic: true`)
3. 없으면 기존 `getRevealableQuestFact()` 순서 fallback (`matchedByTopic: false`)

→ "물어본 것에 답하는 NPC". 주제 없는 잡담 성공 시에는 기존처럼 순서 공개(퀘스트 페이스 유지).

### 2.2 전달 단일화 — ui.questReveal

turns.service 경로 2에서 발견 확정 시:

```ts
result.ui.questReveal = { factId, npcId, revealMode, matchedByTopic };
```

- runState `_npcRevealMode` 해크 제거 (stale 누수 함께 해소)
- context-builder는 `ui.questReveal`이 있으면 **그 fact를 그대로** `npcRevealableFact`로 구성
  (`versions[npcId] ?? description`, revealMode는 서버 판정값)
- 제외 목록 문제 원천 차단: 키워드 재매칭 없이 factId 직접 조회

### 2.3 미기록 누출 차단 — 보류 가이드 (factWithheldHint)

questReveal이 없는 턴에 키워드 매칭 fact를 현재 NPC가 보유한 경우(구 mode A):
detail을 공개하지 않고 `[NPC 정보 보류]` 블록으로 "아는 눈치지만 입을 열지 않는" 반응만 유도.
mode B(인계)/C(default)/D(잡담)는 기존 유지.

### 2.4 부수 효과

- ③ nextHint는 이제 실제 대화 주제와 일치하는 fact 기준 → [단서 방향] 연출이 자연 연결
- `matchedByTopic` 플래그로 주제 매칭율 측정 가능 (플레이테스트 지표)

## 3. 변경 파일 (server)

| 파일 | 변경 |
|------|------|
| `engine/hub/quest-progression.service.ts` | `selectRevealableFact()` 신설 |
| `turns/turns.service.ts` | 경로 2 선택 로직 교체 + `ui.questReveal` 전달 + `_npcRevealMode` 제거 |
| `db/types/server-result.ts` | `QuestRevealUI` 타입 + `UIBundle.questReveal` |
| `llm/context-builder.service.ts` | questReveal 최우선 주입 + mode A → factWithheldHint 전환 |
| `llm/prompts/prompt-builder.service.ts` | `[NPC 정보 보류]` 블록 + 잡담 모드 조건에 withheld 추가 |

## 4. 테스트

- `quest-progression.select-fact.spec.ts` (7) — 주제 우선/fallback/발견 제외/타 NPC 누출 방지/빈 입력
- `prompt-builder.fact-reveal.spec.ts` (3) — 공개 블록 detail 포함 / 보류 블록 detail 미포함 / 우선순위

## 5. 비변경 (스코프 밖)

- 경로 1/3 (이벤트 discoverableFact SUCCESS/PARTIAL) — 이벤트 자체가 주제 컨텍스트라 데스싱크 없음
- INFO_ACTIONS 축소 (원인 3) — 플레이 데이터 실측 후 별도 판단
- nextHint 연출 빈도 완화 (원인 3) — 후속 개선 후보
