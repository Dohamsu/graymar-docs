# 19. Context Coherence Reinforcement

> 맥락 유지 강화 설계서
> 선행 문서: [[architecture/05_llm_narrative|llm narrative]], `18_narrative_runtime_patch.md`, [[guides/04_llm_memory_guide|llm memory guide]]
> 대상: 서사 맥락 유지, NPC 기억, 장면 연속성, 장기 기억 품질
> 원칙: 기존 시스템을 깨지 않고, 계층별로 강화한다. 새 LLM 호출을 추가하지 않는다.

---

# 0. 문제 요약

현재 맥락 유지 시스템은 2026-03-16 장면 연속성 패치로 대폭 개선되었으나, 아래 5개 구간에서 여전히 기억이 끊어진다.

| 구간 | 증상 | 근본 원인 |
|------|------|-----------|
| LOCATION 6턴+ | NPC가 알려준 구체적 정보를 LLM이 잊음 | Mid Summary 200자에 NPC 대사 디테일이 담기지 않음 |
| EventMatcher ↔ LLM | 서버가 다른 NPC 이벤트를 골라서 장면이 점프 | EventMatcher가 NPC 연속성을 고려하지 않음 |
| LOCATION 재방문 | "저번에 여기서 뭘 했는지" LLM이 모호하게 기억 | visitLog가 장소별로 필터링되지 않음 |
| NPC 재등장 | NPC가 이전에 알려준 정보를 모르는 것처럼 행동 | NPC별 "전달된 정보" 명시적 추적 없음 |
| 게임 중후반 | 장기 기억 블록이 토큰 예산을 초과해 중요 정보가 잘림 | 동적 예산 트리밍 미완성 |

---

# 1. 의존성 그래프 & 구현 순서

```
Phase 1: EventMatcher NPC 연속성
    ↓ (이벤트 매칭이 안정되어야 NPC 기억이 의미 있음)
Phase 2: NPC Knowledge Ledger
    ↓ (NPC가 아는 것을 추적해야 Mid Summary에 반영 가능)
Phase 3: Mid Summary 강화
    ↓ (단기 기억 품질이 올라야 장기 기억 입력도 좋아짐)
Phase 4: 장소별 재방문 기억
    ↓ (장기 기억 렌더링 개선)
Phase 5: 토큰 예산 동적 트리밍
    (모든 블록이 안정된 후 예산 관리)
```

이 순서를 바꾸지 않는 것이 좋다. 각 Phase는 이전 Phase 없이도 독립 배포 가능하지만, 효과가 누적되는 구조다.

---

# 2. Phase 1 — EventMatcher NPC 연속성 가중치

## 2.1 문제

플레이어가 "경비대장에게 더 물어본다"고 입력해도, EventMatcher가 affordance(INVESTIGATE)만 보고 전혀 다른 NPC의 이벤트를 매칭할 수 있다. 이때 `actionContext.primaryNpcId`가 바뀌면서 `[현재 장면 상태]`의 대화 상대가 교체되고, LLM이 연속성 규칙으로 이전 NPC를 유지하려 하면 서버 맥락과 충돌한다.

## 2.2 목표

같은 LOCATION 방문 내에서 이전 턴의 NPC가 존재하면, 해당 NPC를 포함하는 이벤트에 가중치 보너스를 부여한다. NPC가 없는 이벤트도 여전히 선택 가능하되, NPC 연속 이벤트가 우선한다.

## 2.3 수정 대상

- `server/src/engine/hub/event-matcher.service.ts`

## 2.4 설계

### 새 입력 파라미터

```typescript
// EventMatcherService.match() 시그니처 확장
match(
  events: EventDefV2[],
  locationId: string,
  intent: ParsedIntentV2,
  ws: WorldState,
  arcState: ArcState,
  agenda: PlayerAgenda,
  cooldowns: Map<string, number>,
  currentTurnNo: number,
  rng: RNG,
  recentEventIds: string[],
  // ── 신규 ──
  sessionNpcContext?: {
    lastPrimaryNpcId: string | null;    // 직전 턴 primaryNpcId
    sessionTurnCount: number;           // 이번 방문 턴 수
    interactedNpcIds: string[];         // 이번 방문에서 상호작용한 NPC 전체
  },
)
```

### 가중치 계산 (6단계 이후 추가)

기존 6단계 매칭으로 후보 이벤트 목록이 나온 후, 최종 가중치 선택 직전에 NPC 보너스를 적용한다.

```typescript
// 기존: finalWeight = priority*10 + weight + agendaBoost - penalty
// 추가: finalWeight += npcContinuityBonus

function calcNpcContinuityBonus(
  event: EventDefV2,
  ctx: SessionNpcContext,
): number {
  if (!ctx.lastPrimaryNpcId) return 0;
  if (ctx.sessionTurnCount < 2) return 0;

  const eventNpcId = event.payload?.primaryNpcId;
  if (!eventNpcId) return 0;

  // 직전 턴과 같은 NPC → 강한 보너스
  if (eventNpcId === ctx.lastPrimaryNpcId) return 25;

  // 이번 방문에서 이미 상호작용한 NPC → 약한 보너스
  if (ctx.interactedNpcIds.includes(eventNpcId)) return 10;

  return 0;
}
```

### sessionNpcContext 구축 위치

`turns.service.ts`의 LOCATION 턴 처리에서 EventMatcher 호출 직전에 구축한다.

```typescript
// turns.service.ts — handleLocationTurn 내부
const sessionNpcContext = {
  lastPrimaryNpcId: this.getLastPrimaryNpcId(runId, nodeInstanceId),
  sessionTurnCount: locationSessionTurns.length,
  interactedNpcIds: this.getSessionInteractedNpcIds(runId, nodeInstanceId),
};
```

**데이터 출처**:
- `lastPrimaryNpcId`: 직전 턴의 `serverResult.ui.actionContext.primaryNpcId` (turns 테이블에서 조회)
- `interactedNpcIds`: 이번 nodeInstanceId의 모든 턴에서 primaryNpcId가 null이 아닌 것들의 고유 집합

### 예외

- `sessionTurnCount < 2`: 첫 턴에서는 NPC 보너스를 적용하지 않는다 (아직 연속성이 없으므로).
- `lastPrimaryNpcId === null`: 직전 턴이 NPC 없는 행동(SEARCH, OBSERVE 등)이었다면 보너스 없음.
- BLOCK matchPolicy 이벤트: Heat 간섭으로 강제 선택된 BLOCK 이벤트에는 NPC 보너스를 적용하지 않는다. 위험 상황은 NPC 연속성보다 우선.

## 2.5 완료 조건

- 기존 EventMatcher 테스트가 통과한다.
- 같은 NPC와 대화 중일 때 연관 이벤트가 우선 선택되는 것을 로그로 확인 가능하다.
- NPC 없는 행동(조사, 관찰)에서는 기존과 동일하게 동작한다.

## 2.6 효과

서버가 선택한 이벤트의 NPC와 LLM의 장면 연속성 규칙이 일치하게 된다. 현재는 LLM이 "이전 NPC를 유지하라"는 규칙을 따르면서 서버가 준 다른 NPC 이벤트 맥락을 무시하는 모순이 있었는데, 이 모순이 해소된다.

---

# 3. Phase 2 — NPC Knowledge Ledger

## 3.1 문제

NPC의 **감정 상태**는 5축(trust/fear/respect/suspicion/attachment)으로 정밀 추적되지만, NPC가 **알고 있는 정보**는 추적되지 않는다.

예시: 경비대장에게 "항만 밀수 증거"를 보여줬는데, 다음 방문 시 LLM이 경비대장을 "밀수에 대해 아무것도 모르는 상태"로 서술한다.

## 3.2 목표

NPC별로 "플레이어가 전달하거나, 대화 중 공유된 핵심 정보"를 최대 5개까지 추적한다. 이 정보는 해당 NPC 등장 시 LLM 프롬프트에 함께 전달된다.

## 3.3 새 타입

```typescript
// server/src/db/types/npc-knowledge.ts

export interface NpcKnowledgeEntry {
  factId: string;               // 고유 ID (예: "knows_smuggling_evidence")
  text: string;                 // 50자 이내 요약
  source: 'PLAYER_TOLD' | 'WITNESSED' | 'INFERRED';
  turnNo: number;               // 획득 시점
  locationId: string;           // 획득 장소
  importance: number;           // 0.0~1.0
}

export interface NpcKnowledgeLedger {
  [npcId: string]: NpcKnowledgeEntry[];  // NPC당 최대 5개
}
```

## 3.4 저장 위치

`run_memories.structuredMemory`에 `npcKnowledge` 필드 추가.

```typescript
// 기존 structuredMemory 확장
structuredMemory: {
  visitLog: VisitLogEntry[];
  npcJournal: NpcJournalEntry[];
  incidentChronicle: IncidentChronicleEntry[];
  milestones: MilestoneEntry[];
  llmExtracted: LlmExtractedFact[];
  // ── 신규 ──
  npcKnowledge: NpcKnowledgeLedger;
};
```

## 3.5 수집 시점 (2가지)

### (A) 서버 측 자동 수집 — `MemoryCollectorService.collect()` 확장

매 LOCATION 턴에서 아래 조건을 체크:

| 조건 | 생성할 knowledge |
|------|-----------------|
| actionType이 TALK/PERSUADE/BRIBE이고 resolveOutcome이 SUCCESS/PARTIAL | `source: 'PLAYER_TOLD'` |
| resolve 시 아이템 전달/증거 제시 이벤트 발생 | `source: 'PLAYER_TOLD'` |
| NPC injection 시 incident 관련 정보 노출 | `source: 'WITNESSED'` |

**text 생성 규칙** (LLM 호출 없이 서버가 생성):
- `${actionType} → ${resolveOutcome}: ${summary.short의 핵심 부분 50자}`
- 예: `"밀수 증거 제시 → 성공: 장부 사본을 경비대장에게 보여줌"`

### (B) LLM 태그 기반 수집 — `[MEMORY:NPC_KNOWLEDGE]` 신규 태그

기존 `[MEMORY]` 태그 카테고리에 `NPC_KNOWLEDGE`를 추가한다.

```
[MEMORY:NPC_KNOWLEDGE:NPC_GUARD_CAPTAIN]경비대장이 밀수 장부의 존재를 알게 됨[/MEMORY]
```

LLM Worker 파싱 시:
- 카테고리가 `NPC_KNOWLEDGE`이면 `:` 뒤의 npcId를 추출
- `npcKnowledge[npcId]`에 추가
- NPC당 5개 초과 시 importance 낮은 것부터 제거

### System Prompt 추가 지시

```
[MEMORY:NPC_KNOWLEDGE:NPC_ID] 태그로 "NPC가 새로 알게 된 핵심 정보"를 기록하세요.
- NPC에게 직접 전달한 정보, NPC가 목격한 사건, NPC가 추론할 수 있는 사실
- 50자 이내, NPC당 최대 5개
```

## 3.5-B [MEMORY] 태그 예산 확대

NPC Knowledge와 별개로, 기존 `[MEMORY]` 태그 자체의 추출 품질도 강화한다.

### 현재 제한

- 턴당 최대 **2개**, 항목당 **50자**
- 카테고리: `NPC_DETAIL`, `PLACE_DETAIL`, `PLOT_HINT`, `ATMOSPHERE`

### 변경

- 턴당 최대 **4개**, 항목당 **80자**
- 카테고리 추가: `NPC_DIALOGUE` (NPC가 직접 말한 구체적 정보)

### System Prompt 변경

```
[MEMORY] 태그로 향후 중요할 사실을 기록하세요.
- 턴당 최대 4개, 각 80자 이내
- 카테고리: NPC_DETAIL, PLACE_DETAIL, PLOT_HINT, ATMOSPHERE, NPC_DIALOGUE
- NPC_DIALOGUE: NPC가 구체적으로 알려준 정보 (이름, 장소, 시간, 숫자 등). 반드시 추출하세요.
  예: [MEMORY:NPC_DIALOGUE]경비대장 曰: 관리인은 매주 화요일 밤 뒷문으로 나감[/MEMORY]
```

### 토큰 영향

출력 토큰 증가: 기존 ~100자 → ~320자 (+220자 ≈ +73 출력 토큰). `LLM_MAX_TOKENS`(1024) 예산 내에서 충분히 수용 가능.

### llm-worker 파싱 변경

```typescript
// 기존: 최대 2개 파싱
const MAX_MEMORY_TAGS = 2;
// 변경: 최대 4개 파싱
const MAX_MEMORY_TAGS = 4;
const MAX_MEMORY_LENGTH = 80; // 50 → 80
```

### llmExtracted 상한 조정

항목당 크기 증가에 따라 전체 상한도 조정한다.
- 기존: 15개 × 50자 = 750자
- 변경: **20개** × 80자 = 1600자

토큰 환산: ~533 토큰. STRUCTURED_MEMORY 예산(500 토큰) 내에서 `renderActiveClues()`가 상위 5개만 렌더링하므로 실제 프롬프트 토큰은 5 × 80자 ≈ 133 토큰으로 수용 가능.

### 수정 대상

- `server/src/llm/llm-worker.service.ts`: 파싱 상한 변경
- `server/src/llm/prompts/system-prompts.ts`: 태그 지시 변경
- `server/src/llm/memory-renderer.service.ts`: llmExtracted 상한 20개로 변경

## 3.6 프롬프트 전달

`prompt-builder.service.ts`의 NPC 로스터 섹션에서, 해당 NPC의 knowledge를 함께 표시한다.

### 현재

```
[등장 가능 NPC 목록]
- 카를로스 (경비대장) [이미 소개됨] — CAUTIOUS
```

### 변경 후

```
[등장 가능 NPC 목록]
- 카를로스 (경비대장) [이미 소개됨] — CAUTIOUS
  이 인물이 알고 있는 것: "항만 밀수 장부 사본의 존재", "창고 관리인의 야간 순찰 경로"
  ⚠️ 이 인물은 위 정보를 이미 알고 있으므로, 처음 듣는 것처럼 반응하면 안 됩니다.
```

### 구현 위치

- `context-builder.service.ts`: `npcKnowledge`를 LlmContext에 추가
- `prompt-builder.service.ts`: NPC 로스터 렌더링 시 knowledge 병합

```typescript
// LlmContext 확장
interface LlmContext {
  // ... 기존 필드 ...
  npcKnowledge: NpcKnowledgeLedger;  // 신규
}
```

## 3.7 토큰 비용

NPC당 최대 5개 × 50자 = 250자 ≈ 83 토큰. 활성 NPC가 3명이면 약 250 토큰. BUFFER 예산(300 토큰) 내에서 수용 가능.

## 3.8 완료 조건

- TALK/PERSUADE 성공 시 해당 NPC의 knowledge가 자동 생성된다.
- LLM이 `[MEMORY:NPC_KNOWLEDGE:ID]` 태그를 출력하면 파싱되어 저장된다.
- NPC 재등장 시 프롬프트에 knowledge가 표시된다.
- NPC당 5개 초과 시 자동 정리된다.

---

# 4. Phase 3 — Mid Summary 강화 + 경량 LLM 요약

## 4.1 문제

LOCATION에서 6턴 이상 머물면 초기 턴들이 200자 Mid Summary로 압축된다. 현재 이 요약은 서버가 LLM 호출 없이 계산하므로, NPC 대사의 구체적 내용(이름, 장소, 숫자 등)이 누락된다.

핵심 한계: LLM이 생성한 서술 안에만 존재하는 정보 — 예를 들어 NPC가 "관리인은 매주 화요일 밤에 뒷문으로 나간다"고 말한 대사 — 는 서버의 `summary.short`에 담기지 않는다. Phase 2의 `[MEMORY]` 태그 확대(턴당 4개/80자)와 `NPC_DIALOGUE` 카테고리가 매 턴 추출 품질을 올려주지만, 추출을 빠뜨리는 경우가 남는다. 6턴 초과 압축 시점에서 **한 번의 경량 LLM 호출**로 누락된 정보까지 회수한다.

## 4.2 목표

Mid Summary를 2단계 합성(Two-pass Synthesis)으로 변경한다.

1. **Pass 1 — 서버 기반 뼈대 요약** (기존, LLM 호출 없음)
2. **Pass 2 — 경량 LLM 압축** (신규, Haiku급 모델 1회 호출)

두 결과를 병합하여 최종 400자 Mid Summary를 생성한다.

## 4.3 수정 대상

- `server/src/llm/mid-summary.service.ts` — 핵심 로직
- `server/src/llm/llm-caller.service.ts` — 경량 모델 호출 경로 추가
- `server/src/llm/llm-config.service.ts` — 요약 전용 모델 설정

## 4.4 설계

### 전체 흐름

```
locationSessionTurns > 6턴 감지
  ↓
Pass 1: buildServerSkeleton()     — 기존 서버 로직 (즉시, ~150자)
  ↓
Pass 2: compressWithLightLlm()    — 경량 LLM 호출 (~250자)
  ↓
mergeMidSummary()                 — 합산 + 중복 제거 → 최종 400자
  ↓
[중간 요약] 블록으로 프롬프트 삽입
```

### Pass 1 — 서버 기반 뼈대 요약 (기존 확장)

```typescript
buildServerSkeleton(
  compressedTurns: TurnRecord[],
  llmExtracted: LlmExtractedFact[],
  npcKnowledge: NpcKnowledgeLedger,
): string {
  const parts: string[] = [];

  // 기존 4항목
  parts.push(this.buildCoreSummary(compressedTurns));  // ~100자

  // Phase 2에서 수집된 llmExtracted (PLOT_HINT/NPC_DETAIL/NPC_DIALOGUE)
  const turnRange = {
    min: compressedTurns[0].turnNo,
    max: compressedTurns[compressedTurns.length - 1].turnNo,
  };
  const relevantFacts = llmExtracted
    .filter(f =>
      ['PLOT_HINT', 'NPC_DETAIL', 'NPC_DIALOGUE'].includes(f.category) &&
      f.turnNo >= turnRange.min && f.turnNo <= turnRange.max
    )
    .slice(0, 4);

  if (relevantFacts.length > 0) {
    parts.push('핵심 정보: ' + relevantFacts.map(f => f.text).join(', '));
  }

  // NPC knowledge
  const knowledgeInRange = this.getKnowledgeInTurnRange(npcKnowledge, turnRange);
  if (knowledgeInRange.length > 0) {
    parts.push('NPC 인지: ' + knowledgeInRange.map(k => k.text).join(', '));
  }

  return this.trimToLength(parts.join(' | '), 150);
}
```

### Pass 2 — 경량 LLM 압축

```typescript
async compressWithLightLlm(
  compressedTurns: TurnRecord[],
  serverSkeleton: string,
): Promise<string> {
  // 압축 대상 턴들의 서술 텍스트 수집
  const narratives = compressedTurns
    .filter(t => t.llmOutput && t.llmStatus === 'DONE')
    .map(t => `[턴${t.turnNo}] ${this.trimToLength(t.llmOutput, 200)}`)
    .join('\n');

  // 서술이 없으면 Pass 1만 사용
  if (!narratives) return '';

  const prompt = `아래는 RPG 게임에서 한 장소 방문 중 초기 턴들의 서술이다.
이 서술들에서 **향후 장면에 필요한 핵심 사실만** 추출하여 250자 이내로 요약하라.

추출 우선순위:
1. NPC가 구체적으로 말한 정보 (이름, 장소, 시간, 조건 등)
2. 플레이어가 획득한 물건/단서의 구체적 내용
3. NPC의 감정 변화나 태도 전환
4. 장소의 구체적 상태 변화

이미 서버가 파악한 정보:
${serverSkeleton}

위 정보와 중복되는 내용은 제외하고, **서술에만 있는 구체적 디테일**을 추출하라.

서술:
${narratives}

250자 이내 요약:`;

  try {
    const result = await this.llmCaller.callLight({
      messages: [{ role: 'user', content: prompt }],
      maxTokens: 200,
      temperature: 0.2,  // 창의성 최소화, 사실 추출에 집중
    });
    return this.trimToLength(result, 250);
  } catch {
    // LLM 실패 시 Pass 1만 사용 (graceful degradation)
    return '';
  }
}
```

### 합산

```typescript
async buildMidSummary(
  compressedTurns: TurnRecord[],
  llmExtracted: LlmExtractedFact[],
  npcKnowledge: NpcKnowledgeLedger,
): Promise<string> {
  const skeleton = this.buildServerSkeleton(compressedTurns, llmExtracted, npcKnowledge);
  const llmCompressed = await this.compressWithLightLlm(compressedTurns, skeleton);

  if (!llmCompressed) return skeleton; // fallback

  return this.trimToLength(`${skeleton}\n${llmCompressed}`, 400);
}
```

## 4.5 경량 모델 설정

### LlmCallerService 확장 — `callLight()` 메서드

```typescript
// llm-caller.service.ts

async callLight(params: {
  messages: LlmMessage[];
  maxTokens: number;
  temperature: number;
}): Promise<string> {
  const config = this.configService.getLightModelConfig();
  return this.callWithProvider(config.provider, {
    ...params,
    model: config.model,
  });
}
```

### LlmConfigService 확장

```typescript
// llm-config.service.ts

getLightModelConfig(): { provider: string; model: string } {
  return {
    provider: process.env.LLM_LIGHT_PROVIDER || 'anthropic',
    model: process.env.LLM_LIGHT_MODEL || 'claude-haiku-4-5-20251001',
  };
}
```

### .env 추가 변수

```env
# 경량 LLM (요약/추출 전용)
LLM_LIGHT_PROVIDER=anthropic
LLM_LIGHT_MODEL=claude-haiku-4-5-20251001
LLM_LIGHT_TIMEOUT_MS=5000
LLM_LIGHT_MAX_RETRIES=1
```

## 4.6 호출 빈도 & 비용

| 항목 | 값 |
|------|-----|
| 호출 시점 | LOCATION 방문 중 6턴 초과 시 **1회** |
| 추가 호출 | 이후 6턴마다 재압축 시 **1회** (12턴 → 2회, 18턴 → 3회) |
| 입력 토큰 | ~300(프롬프트) + ~200×압축턴수 ≈ **~1000~1500** |
| 출력 토큰 | **~150~200** |
| 모델 | Haiku급 ($0.25/M input, $1.25/M output 기준) |
| 1회 비용 | ~$0.0005 (입력 1000tok + 출력 200tok) |
| 일반 LOCATION 방문당 | 0~2회 ≈ **$0.001 이하** |

서사 LLM 본호출(Sonnet/Opus) 대비 약 **1/20~1/50 비용**이므로 무시 가능한 수준이다.

## 4.7 실패 정책 (Graceful Degradation)

경량 LLM 호출 실패 시:
1. `compressWithLightLlm()`이 빈 문자열을 반환
2. `buildMidSummary()`는 Pass 1(서버 뼈대) 만으로 Mid Summary 생성
3. 게임 진행에 영향 없음 (기존 동작과 동일)
4. 실패 로그만 `ai_turn_logs`에 기록 (type: `MID_SUMMARY_LIGHT`)

즉, 경량 LLM은 **있으면 좋고 없어도 동작하는 보너스 레이어**다.

## 4.8 수정 파일

| 파일 | 변경 |
|------|------|
| `llm/mid-summary.service.ts` | `buildMidSummary` async 전환, `compressWithLightLlm` 추가 |
| `llm/llm-caller.service.ts` | `callLight()` 메서드 추가 |
| `llm/llm-config.service.ts` | `getLightModelConfig()` 추가 |
| `llm/ai-turn-log.service.ts` | `MID_SUMMARY_LIGHT` 로그 타입 추가 |

## 4.9 완료 조건

- 6턴 초과 방문 시 경량 LLM이 호출되어 서술 기반 요약이 생성된다.
- 경량 LLM 실패 시 서버 뼈대 요약만으로 fallback 동작한다.
- Mid Summary가 400자 이내로 생성된다.
- NPC 대사의 구체적 정보(이름, 시간, 장소 등)가 Mid Summary에 보존된다.
- `ai_turn_logs`에 경량 LLM 호출 기록이 남는다.
- 기존 서사 LLM 파이프라인에 영향이 없다.

---

# 5. Phase 4 — 장소별 재방문 기억

## 5.1 문제

시장을 방문한 후 HUB로 돌아갔다가 다시 시장에 오면, `[이야기 요약]` 블록에 모든 LOCATION 방문이 시간순으로 뒤섞여 있다. LLM이 "시장에서 전에 뭘 했는지"를 추출하려면 전체 요약을 스캔해야 한다.

## 5.2 목표

현재 LOCATION 재방문 시 `[이 장소의 이전 방문]` 블록을 추가하여, 해당 장소에서의 이전 행동과 결과를 별도로 전달한다.

## 5.3 수정 대상

- `server/src/llm/memory-renderer.service.ts`
- `server/src/llm/context-builder.service.ts`
- `server/src/llm/prompts/prompt-builder.service.ts`

## 5.4 설계

### LlmContext 확장

```typescript
interface LlmContext {
  // ... 기존 필드 ...
  locationRevisitContext: string | null;  // 신규
}
```

### 데이터 생성 — `memory-renderer.service.ts`

```typescript
renderLocationRevisitContext(
  locationId: string,
  visitLog: VisitLogEntry[],
  npcJournal: NpcJournalEntry[],
  npcKnowledge: NpcKnowledgeLedger,
): string | null {
  // 이 locationId와 관련된 이전 방문만 필터
  const previousVisits = visitLog.filter(
    v => v.locationId === locationId
  );
  if (previousVisits.length === 0) return null;

  const parts: string[] = [];
  parts.push(`[이 장소의 이전 방문 (${previousVisits.length}회)]`);

  // 최근 2회 방문만 상세, 나머지는 1줄 요약
  const recent = previousVisits.slice(-2);
  const older = previousVisits.slice(0, -2);

  if (older.length > 0) {
    parts.push(`이전 ${older.length}회 방문: ${older.map(v => v.summary).join('; ')}`);
  }

  for (const visit of recent) {
    parts.push(`- ${visit.summary}`);
  }

  // 이 장소에서 만났던 NPC의 현재 knowledge
  const locationNpcs = npcJournal.filter(
    j => j.locationIds?.includes(locationId)
  );
  if (locationNpcs.length > 0) {
    const npcSummaries = locationNpcs.map(npc => {
      const knowledge = npcKnowledge[npc.npcId] || [];
      const knowText = knowledge.length > 0
        ? ` (알고 있는 것: ${knowledge.map(k => k.text).join(', ')})`
        : '';
      return `${npc.displayName}${knowText}`;
    });
    parts.push(`이 장소의 주요 인물: ${npcSummaries.join(' / ')}`);
  }

  return parts.join('\n');
}
```

### 프롬프트 삽입 위치

Memory Block 순서에서 `[현재 장소]`(7번) 바로 뒤, `[현재 장면 상태]`(8번) 앞에 삽입한다.

```
7.  [현재 장소]
7.5 [이 장소의 이전 방문]   ← 신규
8.  [현재 장면 상태]
```

### 첫 방문 시

`previousVisits`가 비어있으면 블록 자체를 생략한다. 토큰 낭비 없음.

### 예시 출력

```
[이 장소의 이전 방문 (2회)]
이전 1회 방문: 상인에게서 장부 조작 소문을 들음
- 에드릭에게 장부 사본을 요청해 성공. 뒷거래 증거를 확보함.
이 장소의 주요 인물: 에드릭 (알고 있는 것: "장부 사본 전달함", "밀수 조직 의심 중")
```

## 5.5 토큰 비용

재방문 시만 생성. 최근 2회 방문 상세 + NPC knowledge ≈ 100~200자 ≈ 33~67 토큰.
STRUCTURED_MEMORY 예산(500 토큰)에서 분할하여 사용.

분할 기준:
- `[이야기 요약]`: 350 토큰 (기존 500에서 축소)
- `[이 장소의 이전 방문]`: 최대 100 토큰
- `[NPC 관계]` + `[사건 일지]` + `[서사 이정표]` + `[기억된 사실]`: 나머지

재방문이 아니면 `[이야기 요약]`이 전체 500 토큰을 사용한다.

## 5.6 `[이야기 요약]` 에서 현재 장소 중복 제거

`[이 장소의 이전 방문]` 블록이 존재하면, `[이야기 요약]` 렌더링 시 현재 locationId의 visitLog 엔트리를 **제외**한다. 동일 정보가 두 블록에 중복되는 것을 방지하고 토큰을 절약한다.

## 5.7 완료 조건

- 재방문 시 `[이 장소의 이전 방문]` 블록이 프롬프트에 포함된다.
- 첫 방문 시 블록이 생략된다.
- `[이야기 요약]`에서 현재 장소 관련 엔트리가 제거된다.

---

# 6. Phase 5 — 토큰 예산 동적 트리밍

## 6.1 문제

게임이 진행될수록 STRUCTURED_MEMORY(visitLog + npcJournal + incidentChronicle + milestones + llmExtracted)가 500 토큰을 초과한다. 현재 "부분 구현" 상태인 동적 축소가 완성되지 않아, 어떤 블록이 잘리는지 예측할 수 없다.

## 6.2 목표

블록별 우선순위를 명확히 정의하고, 예산 초과 시 낮은 우선순위부터 트리밍하는 결정적 알고리즘을 완성한다.

## 6.3 수정 대상

- `server/src/llm/token-budget.service.ts`

## 6.4 블록 우선순위 (높을수록 마지막에 잘림)

```typescript
enum BlockPriority {
  // === 절대 삭제 금지 ===
  THEME = 100,              // L0: 세계관 기억

  // === 현재 장면 핵심 (높음) ===
  SCENE_CONTEXT = 90,       // [현재 장면 상태]
  RECENT_STORY = 85,        // [이번 방문 대화]
  CURRENT_FACTS = 80,       // Facts Block (이번 턴 사건)

  // === 맥락 보존 (중간) ===
  NARRATIVE_THREAD = 70,    // [장면 흐름]
  ACTIVE_CLUES = 65,        // [활성 단서]
  NPC_KNOWLEDGE = 63,       // [NPC knowledge] — Phase 2
  LOCATION_REVISIT = 60,    // [이 장소의 이전 방문] — Phase 4
  NPC_ROSTER = 58,          // [등장 가능 NPC 목록]

  // === 장기 기억 (낮음-중간) ===
  STORY_SUMMARY = 55,       // [이야기 요약]
  NPC_JOURNAL = 50,         // [NPC 관계]
  INCIDENT_CHRONICLE = 45,  // [사건 일지]
  MILESTONES = 40,          // [서사 이정표]
  LLM_FACTS = 35,           // [기억된 사실]

  // === 부가 정보 (낮음) ===
  INTENT_MEMORY = 25,       // [플레이어 행동 패턴]
  SIGNAL_CONTEXT = 20,      // [도시 시그널]
  WORLD_SNAPSHOT = 15,      // [세계 상태]
  AGENDA_ARC = 12,          // [성향/아크]
  PLAYER_PROFILE = 10,      // [플레이어 프로필]
  EQUIPMENT_TAGS = 5,       // [장비 인상]
}
```

## 6.5 트리밍 알고리즘

```typescript
// token-budget.service.ts

interface RenderedBlock {
  key: string;
  priority: BlockPriority;
  content: string;
  tokens: number;
  minTokens: number;    // 이 이하로 줄이면 의미 없음 (0이면 완전 삭제 가능)
}

function trimToTotalBudget(
  blocks: RenderedBlock[],
  totalBudget: number,
): RenderedBlock[] {
  let totalTokens = blocks.reduce((sum, b) => sum + b.tokens, 0);
  if (totalTokens <= totalBudget) return blocks;

  // 우선순위 오름차순 정렬 (낮은 것부터 자르기)
  const sorted = [...blocks].sort((a, b) => a.priority - b.priority);

  for (const block of sorted) {
    if (totalTokens <= totalBudget) break;
    if (block.priority >= BlockPriority.THEME) continue; // 절대 삭제 금지

    const excess = totalTokens - totalBudget;

    if (block.tokens <= block.minTokens) continue; // 이미 최소

    const canTrim = block.tokens - block.minTokens;
    const trimAmount = Math.min(canTrim, excess);

    // 문장 경계에서 자르기
    block.content = this.trimAtSentenceBoundary(
      block.content,
      block.tokens - trimAmount,
    );
    block.tokens -= trimAmount;
    totalTokens -= trimAmount;

    // minTokens가 0이고 여전히 초과하면 블록 완전 제거
    if (block.minTokens === 0 && totalTokens > totalBudget) {
      totalTokens -= block.tokens;
      block.content = '';
      block.tokens = 0;
    }
  }

  return blocks;
}
```

### minTokens 기본값

| 블록 | minTokens | 이유 |
|------|-----------|------|
| THEME | ∞ | 삭제 불가 |
| SCENE_CONTEXT | 80 | 대화 상대 + 위치는 반드시 유지 |
| RECENT_STORY | 200 | 최소 직전 2턴은 유지 |
| ACTIVE_CLUES | 50 | 최소 1개 단서 |
| NPC_KNOWLEDGE | 30 | 최소 1명 knowledge |
| STORY_SUMMARY | 100 | 최소 2문장 |
| NPC_JOURNAL | 0 | 완전 삭제 가능 (npcKnowledge가 대체) |
| EQUIPMENT_TAGS | 0 | 완전 삭제 가능 |
| SIGNAL_CONTEXT | 0 | 완전 삭제 가능 |

## 6.6 예산 분배 변경

현재 블록별 고정 예산을 **총 예산 공유 방식**으로 변경한다.

```
현재: 각 블록이 독립 예산 (SCENE 150, INTENT 200, CLUES 150, RECENT 700, ...)
변경: 전체 2500 토큰 풀에서 렌더링 → 초과 시 우선순위 트리밍
```

이렇게 하면 재방문이 아닌 경우 LOCATION_REVISIT의 예산이 자동으로 다른 블록에 흡수된다.

## 6.7 llmExtracted 교체 정책

llmExtracted가 20개 상한(Phase 2에서 확대)에 도달했을 때, 현재는 오래된 것부터 제거한다. 이를 importance 기반으로 변경한다.

```typescript
function evictLlmExtracted(
  facts: LlmExtractedFact[],
  newFact: LlmExtractedFact,
): LlmExtractedFact[] {
  if (facts.length < 20) return [...facts, newFact];

  // PLOT_HINT, NPC_DIALOGUE는 보호 (importance 보너스)
  const scored = facts.map(f => ({
    fact: f,
    score: f.importance
      + (f.category === 'PLOT_HINT' ? 0.3 : 0)
      + (f.category === 'NPC_DIALOGUE' ? 0.2 : 0)
      - (Date.now() - f.createdAt) / (1000 * 60 * 60 * 24 * 7) * 0.1,
      // 7일당 0.1 감쇠
  }));

  scored.sort((a, b) => a.score - b.score);
  scored[0] = { fact: newFact, score: 999 }; // 새 것으로 교체

  return scored.map(s => s.fact);
}
```

## 6.8 완료 조건

- 총 토큰이 2500을 초과하면 낮은 우선순위 블록부터 트리밍된다.
- THEME은 절대 삭제되지 않는다.
- SCENE_CONTEXT, RECENT_STORY는 minTokens 이하로 줄어들지 않는다.
- 각 블록의 트리밍 결과가 ai_turn_logs에 기록된다 (디버그용).

---

# 7. 전체 수정 파일 목록

| Phase | 파일 | 변경 유형 |
|-------|------|-----------|
| 1 | `engine/hub/event-matcher.service.ts` | 수정: NPC 가중치 추가 |
| 1 | `turns/turns.service.ts` | 수정: sessionNpcContext 구축 후 전달 |
| 2 | `db/types/npc-knowledge.ts` | 신규 |
| 2 | `engine/hub/memory-collector.service.ts` | 수정: NPC knowledge 자동 수집 |
| 2 | `llm/llm-worker.service.ts` | 수정: NPC_KNOWLEDGE 태그 파싱 + MEMORY 상한 4개/80자 |
| 2 | `llm/prompts/system-prompts.ts` | 수정: NPC_KNOWLEDGE + NPC_DIALOGUE 태그 지시, MEMORY 예산 확대 |
| 2 | `llm/context-builder.service.ts` | 수정: npcKnowledge 컨텍스트 추가 |
| 2 | `llm/prompts/prompt-builder.service.ts` | 수정: NPC 로스터에 knowledge 병합 |
| 2 | `engine/hub/memory-integration.service.ts` | 수정: npcKnowledge 저장/통합 |
| 2 | `llm/memory-renderer.service.ts` | 수정: llmExtracted 상한 20개, NPC_DIALOGUE 카테고리 |
| 3 | `llm/mid-summary.service.ts` | 수정: async 전환, 2-pass 합성, 400자 확장 |
| 3 | `llm/llm-caller.service.ts` | 수정: callLight() 메서드 추가 |
| 3 | `llm/llm-config.service.ts` | 수정: getLightModelConfig() 추가 |
| 3 | `llm/ai-turn-log.service.ts` | 수정: MID_SUMMARY_LIGHT 로그 타입 |
| 4 | `llm/memory-renderer.service.ts` | 수정: renderLocationRevisitContext 추가 |
| 4 | `llm/context-builder.service.ts` | 수정: locationRevisitContext 필드 추가 |
| 4 | `llm/prompts/prompt-builder.service.ts` | 수정: Memory Block 순서 7.5 삽입 |
| 5 | `llm/token-budget.service.ts` | 수정: 우선순위 트리밍 알고리즘 완성 |

---

# 8. PR 단위 권장 분리

## PR 1 — EventMatcher NPC 연속성 (Phase 1)

- `event-matcher.service.ts` NPC 가중치
- `turns.service.ts` sessionNpcContext 구축
- 테스트: 같은 NPC 이벤트 우선 선택 확인

## PR 2 — NPC Knowledge Ledger + MEMORY 태그 확대 (Phase 2)

- 타입 추가 (`npc-knowledge.ts`)
- memory-collector NPC knowledge 수집
- llm-worker 파싱: NPC_KNOWLEDGE 태그 + MEMORY 상한 4개/80자
- system-prompts: NPC_DIALOGUE 카테고리 + MEMORY 예산 확대 지시
- memory-renderer: llmExtracted 상한 20개
- prompt-builder NPC 로스터 렌더링
- 테스트: TALK SUCCESS 시 knowledge 생성, NPC_DIALOGUE 태그 파싱 확인

## PR 3 — Mid Summary 2-pass 합성 + 경량 LLM (Phase 3)

- mid-summary.service async 전환 + 2-pass(서버 뼈대 + 경량 LLM)
- llm-caller.service `callLight()` 추가
- llm-config.service 경량 모델 설정
- ai-turn-log.service `MID_SUMMARY_LIGHT` 타입
- 테스트: 6턴+ 방문 시 경량 LLM 호출 확인, 실패 시 fallback 동작 확인

## PR 4 — 장소별 재방문 기억 (Phase 4)

- memory-renderer 필터링
- context-builder + prompt-builder 블록 삽입
- 테스트: 재방문 시 블록 생성, 첫 방문 시 생략

## PR 5 — 토큰 예산 동적 트리밍 (Phase 5)

- token-budget.service 알고리즘 완성
- llmExtracted 교체 정책
- 테스트: 인위적으로 토큰 초과 상황 만들어 트리밍 순서 확인

---

# 9. 테스트 체크리스트

## Phase 1
- [ ] 같은 NPC와 3턴 연속 대화 시, EventMatcher가 해당 NPC 이벤트를 우선 선택하는가
- [ ] NPC 없는 행동(SEARCH)에서는 보너스가 0인가
- [ ] BLOCK matchPolicy 이벤트는 NPC 보너스를 무시하는가
- [ ] 기존 EventMatcher 매칭 결과가 NPC 보너스 없을 때 동일한가

## Phase 2
- [ ] TALK + SUCCESS 시 npcKnowledge에 엔트리가 생성되는가
- [ ] LLM이 `[MEMORY:NPC_KNOWLEDGE:ID]` 태그를 출력하면 파싱되는가
- [ ] NPC 재등장 시 프롬프트에 knowledge가 표시되는가
- [ ] NPC당 5개 초과 시 importance 낮은 것이 제거되는가
- [ ] `[MEMORY]` 태그가 턴당 4개까지 파싱되는가
- [ ] `NPC_DIALOGUE` 카테고리가 정상 저장되는가
- [ ] llmExtracted가 20개 상한으로 동작하는가
- [ ] 항목당 80자 초과 시 절삭되는가

## Phase 3
- [ ] 6턴 초과 방문에서 경량 LLM 호출이 발생하는가
- [ ] 경량 LLM 실패 시 서버 뼈대 요약으로 fallback되는가
- [ ] Mid Summary가 400자를 초과하지 않는가
- [ ] NPC 대사의 구체적 정보(이름, 시간 등)가 Mid Summary에 보존되는가
- [ ] `ai_turn_logs`에 `MID_SUMMARY_LIGHT` 타입으로 기록되는가
- [ ] 경량 LLM 호출이 서사 LLM 파이프라인(Worker)에 영향을 주지 않는가
- [ ] 12턴 방문 시 재압축이 정상 동작하는가 (2회 호출)

## Phase 4
- [ ] 재방문 시 `[이 장소의 이전 방문]` 블록이 생성되는가
- [ ] 첫 방문 시 블록이 생략되는가
- [ ] `[이야기 요약]`에서 현재 장소 엔트리가 중복 제거되는가
- [ ] 이전 방문의 NPC knowledge가 블록에 포함되는가

## Phase 5
- [ ] 총 토큰 2500 초과 시 EQUIPMENT_TAGS → SIGNAL_CONTEXT 순으로 먼저 잘리는가
- [ ] THEME은 절대 잘리지 않는가
- [ ] SCENE_CONTEXT가 80 토큰 이하로 줄어들지 않는가
- [ ] llmExtracted 15개 초과 시 importance 기반 교체가 동작하는가

---

# 10. 예상 효과

| 문제 | 해결 Phase | 기대 결과 |
|------|-----------|-----------|
| NPC와 대화 중 다른 이벤트로 점프 | Phase 1 | 서버-LLM 간 NPC 불일치 80%+ 감소 |
| NPC가 이전에 전달한 정보를 모름 | Phase 2 | NPC 재등장 시 정보 일관성 확보 |
| LLM 서술 디테일이 매 턴 추출 누락 | Phase 2 (MEMORY 확대) | NPC_DIALOGUE 카테고리로 대사 정보 추출률 향상 |
| 6턴+ 방문 시 초반 대사 기억 상실 | Phase 3 | 경량 LLM이 서술 기반 요약 생성, 구체적 정보 보존 |
| 재방문 시 "여기서 전에 뭘 했는지" 모호 | Phase 4 | 장소별 이전 행동/NPC 맥락 명시적 전달 |
| 게임 후반 토큰 초과로 정보 무작위 손실 | Phase 5 | 결정적 우선순위 기반 트리밍 |

---

# 부록 A. 현재 프롬프트 블록 순서 (변경 후)

```
[system]   NARRATIVE_SYSTEM_PROMPT + 성별 + L0 theme (캐시)
[assistant] Memory Block:
  1.  [세계 상태]
  2.  [서사 이정표]
  3.  [이야기 요약]           ← Phase 4: 현재 장소 엔트리 제외
  4.  [NPC 관계]
  5.  [사건 일지]
  6.  [기억된 사실]
  7.  [현재 장소]
  7.5 [이 장소의 이전 방문]    ← Phase 4: 신규 (재방문 시만)
  8.  [현재 장면 상태]
  9.  [현재 노드 사실]
  10. [장면 흐름]
  11. [이번 방문 대화]         ← Phase 3: Mid Summary 350자로 강화
  12. [등장 가능 NPC 목록]     ← Phase 2: knowledge 병합
  13. [활성 사건 현황]
  14. [도시 시그널]
  15. [성향/아크]
  16. [플레이어 프로필]
  17. [장비 인상]
[user]     Facts Block (기존과 동일)
```

---

# 부록 B. NPC Knowledge 태그 예시

```
(LLM 서술 본문 끝)

[CHOICES]
1. "에드릭에게 장부 사본의 출처를 추궁한다" | INVESTIGATE | 에드릭
2. "뒷골목 정보상에게 밀수 조직 수장을 묻는다" | TALK | 정보상
3. "항만 창고를 직접 탐색한다" | SNEAK | 없음
[/CHOICES]
[MEMORY:PLOT_HINT]경비대 내부에 밀수 조직 협력자가 있을 가능성[/MEMORY]
[MEMORY:NPC_KNOWLEDGE:NPC_EDRIK]장부 사본의 존재를 알게 됨, 경계 중[/MEMORY]
[THREAD]시장 후미진 창고. 에드릭에게 장부 사본 요청 성공. 에드릭은 불안해하며 조건부 협력 의사를 밝힘. 뒷거래 관련 추가 정보를 암시.[/THREAD]
```