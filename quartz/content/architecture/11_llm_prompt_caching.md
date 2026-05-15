# 11. LLM Prompt Caching 설계

정본: 이 문서
관련: [[architecture/05_llm_narrative|llm narrative]], [[specs/llm_context_system_v1|llm context system v1]]

---

## §1 현재 구조 분석

### 1.1 호출 흐름

```
LlmWorkerService.poll() (2초 폴링)
  → ContextBuilderService.build()        // DB에서 L0~L4 컨텍스트 조회
  → PromptBuilderService.buildNarrativePrompt()  // LlmMessage[] 조립
  → LlmCallerService.call()              // 재시도 + fallback
    → OpenAIProvider.generate()           // chat.completions.create()
```

### 1.2 현재 프롬프트 구조 (3 메시지)

| # | role | 내용 | 토큰 (추정) | 안정성 |
|---|------|------|------------|--------|
| 1 | `system` | NARRATIVE_SYSTEM_PROMPT (서술 원칙, 금지 사항 등) | ~1,000 | **고정** (코드 변경 시에만 변경) |
| 2 | `assistant` | Memory block (L0 theme + L0+ world + L1 story + L3 대화이력 + L4+ 메타) | ~500–2,000 | **준안정** (턴마다 L3 증가) |
| 3 | `user` | Facts block (행동 + 요약 + 사건 + 분위기 + 선택지) | ~200–800 | **휘발성** (매 턴 변경) |

**총 입력 토큰: 턴당 ~1,700–3,800 토큰**

### 1.3 문제점

1. ~~**캐싱 없음**~~ ✅ 해결됨 — System prompt에 L0 theme 병합으로 prefix 1,024+ 토큰 보장
2. **L0 theme 분리** — 런 내 고정인 세계관 기억이 assistant 메시지 안에 있어 prefix 캐싱 불가
3. **OpenAI 자동 캐싱 미달** — System prompt만으로는 ~1,000 토큰 ≈ 1,024 토큰 경계선 (불안정)
4. ~~**캐시 히트 추적 없음**~~ ⚠️ 부분 해결 — `ai_turn_logs` 테이블에 LLM 호출 로그 기록됨, cached_tokens 상세 추적은 미완
5. **Claude/Gemini 미구현** — 스켈레톤 상태, 각 프로바이더 고유 캐싱 전략 없음

---

## §2 프로바이더별 캐싱 메커니즘

### 2.1 OpenAI — Automatic Prefix Caching

| 항목 | 값 |
|------|-----|
| 활성 조건 | 동일 prefix ≥ 1,024 토큰 |
| 캐시 단위 | 128 토큰 청크 |
| 할인 | 캐시 히트 시 **입력 토큰 50% 할인** |
| TTL | 마지막 사용 후 5~10분 (비공개, 트래픽에 따라 변동) |
| 설정 | 별도 설정 불필요, 자동 적용 |
| 응답 필드 | `usage.prompt_tokens_details.cached_tokens` |

**핵심 전략**: System 메시지에 L0 theme을 병합 → 고정 prefix를 1,024+ 토큰으로 보장.

```
현재:  [system: ~1000 tok] [assistant: theme+...] [user: ...]
       ↑ 경계선 미달, 캐시 불안정

변경후: [system: prompt+theme ~1200+ tok] [assistant: ...] [user: ...]
        ↑ 확실히 1024 초과, 자동 캐시
```

### 2.2 Claude — Explicit Cache Control (향후)

| 항목 | 값 |
|------|-----|
| 활성 조건 | `cache_control: { type: "ephemeral" }` 마커 |
| 최소 토큰 | 1,024 (Sonnet), 2,048 (Haiku) |
| 할인 | 캐시 Read **90% 할인**, Write 25% 추가 |
| TTL | 5분 (사용 시 갱신) |
| 브레이크포인트 | 최대 4개 |

**핵심 전략**: 2개 캐시 브레이크포인트.
```
[system: prompt + L0 theme]  ← cache_control ① (모든 턴 캐시)
[assistant: L1 story + L2 facts + metadata]  ← cache_control ② (LOCATION 내 캐시)
[user: 이번 턴 사건]  ← 캐시 없음
```

### 2.3 Gemini — Context Caching API (향후)

| 항목 | 값 |
|------|-----|
| 활성 조건 | `caches.create()` API로 명시적 캐시 생성 |
| 최소 토큰 | 32,768 |
| 할인 | 캐시 토큰 **75% 할인** |
| TTL | 기본 1시간, 설정 가능 |
| 스토리지 비용 | $1.00/M 토큰/시간 |

**핵심 전략**: 최소 32K 토큰 요구 → 현재 프롬프트 규모(~3K)에서는 **비실용적**.
Gemini는 당분간 일반 호출, 프롬프트가 대폭 확장될 때 재검토.

---

## §3 프롬프트 재구조화 설계

### 3.1 3-Tier 안정성 분류

```
┌──────────────────────────────────────────────┐
│  Tier 1: STATIC PREFIX (런 전체 고정)         │ → 캐싱 대상
│  - NARRATIVE_SYSTEM_PROMPT                    │
│  - L0: theme (세계관 기억)                    │
│  예상: ~1,200 토큰                            │
├──────────────────────────────────────────────┤
│  Tier 2: SESSION CONTEXT (LOCATION 내 준안정) │ → 부분 캐싱 (Claude만)
│  - L0+: worldSnapshot                        │
│  - L1: storySummary                          │
│  - L1+: locationContext                      │
│  - L2: nodeFacts                             │
│  - L2+: npcRelationFacts                     │
│  - L4+: agendaArc, playerProfile             │
│  - Phase 4: equipmentTags, activeSetNames    │
│  예상: ~300–800 토큰                          │
├──────────────────────────────────────────────┤
│  Tier 3: VOLATILE (매 턴 변경)                │ → 캐싱 불가
│  - L3: locationSessionTurns (매 턴 증가)      │
│  - L4: 이번 턴 사건/행동/분위기               │
│  - NPC 주입/피크모드/자세                     │
│  - 프롤로그 힌트/선택지                       │
│  예상: ~200–2,000 토큰                        │
└──────────────────────────────────────────────┘
```

### 3.2 메시지 재배치

**변경 전 (현재)**:
```
[system]     NARRATIVE_SYSTEM_PROMPT
[assistant]  L0 theme + L0+ world + L1 story + L1+ loc + L2 + L3 session + L4+ meta + equipment
[user]       action + summary + events + tone + prologue + choices
```

**변경 후**:
```
[system]     NARRATIVE_SYSTEM_PROMPT + "\n\n" + L0 theme (Tier 1, 고정)
[assistant]  Tier 2: L0+ world + L1 story + L1+ loc + L2 + L4+ meta + equipment
             ---구분---
             Tier 3-memory: L3 locationSessionTurns OR recentTurns
[user]       Tier 3-facts: action + summary + events + tone + prologue + choices
```

**효과**:
- OpenAI: Tier 1 (~1,200 tok)이 매 턴 자동 캐시 → **입력 토큰의 ~30–50% 캐시 할인**
- Claude: Tier 1 + Tier 2 (~2,000 tok)까지 캐시 → **입력 토큰의 ~50–70% 캐시 할인**

### 3.3 L0 Theme 병합 포맷

```typescript
// PromptBuilderService.buildNarrativePrompt() 변경

// 현재: system prompt만 단독
messages.push({ role: 'system', content: NARRATIVE_SYSTEM_PROMPT });

// 변경: system prompt + L0 theme 병합
const systemContent = ctx.theme.length > 0
  ? `${NARRATIVE_SYSTEM_PROMPT}\n\n## 세계관 기억\n${JSON.stringify(ctx.theme)}`
  : NARRATIVE_SYSTEM_PROMPT;
messages.push({ role: 'system', content: systemContent });

// assistant memory block에서 L0 theme 제거
// (기존 memoryParts에서 theme 블록 삭제)
```

---

## §4 캐시 히트 추적 설계

### 4.1 OpenAI 응답에서 cached_tokens 수집

```typescript
// OpenAIProvider.generate() 변경

return {
  text,
  model: completion.model,
  promptTokens: completion.usage?.prompt_tokens ?? 0,
  completionTokens: completion.usage?.completion_tokens ?? 0,
  cachedTokens: completion.usage?.prompt_tokens_details?.cached_tokens ?? 0,  // 신규
  latencyMs: Date.now() - start,
};
```

### 4.2 LlmProviderResponse 타입 확장

```typescript
export interface LlmProviderResponse {
  text: string;
  model: string;
  promptTokens: number;
  completionTokens: number;
  cachedTokens: number;      // 신규: 캐시 히트 토큰 수
  latencyMs: number;
}
```

### 4.3 Worker 로깅 강화

```
LLM DONE: turn 5 (run abc123, model=gpt-4o-mini)
  tokens: prompt=2450 cached=1200 (49%) completion=380 latency=1.2s
```

캐시 히트율이 0%면 prefix 불일치 → 디버깅 필요.
캐시 히트율이 30%+ 이면 정상 작동.

---

## §5 LlmMessage 타입 확장 (Claude 캐싱 대비)

### 5.1 캐시 힌트 필드 추가

```typescript
export interface LlmMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
  cacheControl?: 'ephemeral';  // 신규: Claude 캐시 브레이크포인트
}
```

### 5.2 프로바이더별 처리

| 프로바이더 | cacheControl 처리 |
|-----------|------------------|
| OpenAI | **무시** (자동 prefix 캐싱, 별도 마커 불필요) |
| Claude | `cache_control: { type: "ephemeral" }` 로 변환 |
| Gemini | **무시** (Context Caching API는 별도 경로) |
| Mock | **무시** |

### 5.3 PromptBuilder에서 캐시 힌트 배치

```typescript
// Tier 1: System message (모든 턴 캐시)
messages.push({
  role: 'system',
  content: systemContent,
  cacheControl: 'ephemeral',  // Claude용
});

// Tier 2: Semi-stable memory (LOCATION 내 캐시)
messages.push({
  role: 'assistant',
  content: tier2Parts.join('\n\n'),
  cacheControl: 'ephemeral',  // Claude용
});

// Tier 3: Volatile (캐시 안 함)
if (tier3MemoryParts.length > 0) {
  messages.push({
    role: 'assistant',
    content: tier3MemoryParts.join('\n\n'),
    // cacheControl 없음
  });
}

// Facts (캐시 안 함)
messages.push({ role: 'user', content: factsParts.join('\n\n') });
```

---

## §6 비용 영향 분석

### 6.1 GPT-4o-mini 기준 (현재 사용 중)

| 항목 | 캐싱 전 | 캐싱 후 (예상) |
|------|---------|--------------|
| 턴당 입력 토큰 | ~2,500 | ~2,500 (동일) |
| 캐시 히트 | 0 tok | ~1,200 tok (Tier 1) |
| 입력 비용 (1턴) | 2,500 × $0.15/M = $0.000375 | 1,300 × $0.15/M + 1,200 × $0.075/M = $0.000285 |
| **절감율** | — | **~24%** |
| 100턴 런 비용 | $0.0375 | $0.0285 |

### 6.2 GPT-4o 기준 (권장)

| 항목 | 캐싱 전 | 캐싱 후 (예상) |
|------|---------|--------------|
| 턴당 입력 토큰 | ~2,500 | ~2,500 (동일) |
| 캐시 히트 | 0 tok | ~1,200 tok (Tier 1) |
| 입력 비용 (1턴) | 2,500 × $2.50/M = $0.00625 | 1,300 × $2.50/M + 1,200 × $1.25/M = $0.00475 |
| **절감율** | — | **~24%** |
| 100턴 런 비용 | $0.625 | $0.475 |

### 6.3 Claude Sonnet 기준 (향후)

| 항목 | 캐싱 전 | 캐싱 후 (예상) |
|------|---------|--------------|
| 턴당 입력 토큰 | ~2,500 | ~2,500 (동일) |
| 캐시 히트 | 0 tok | ~2,000 tok (Tier 1 + 2) |
| 입력 비용 (1턴) | 2,500 × $3.00/M = $0.0075 | 500 × $3.00/M + 2,000 × $0.30/M = $0.0021 |
| **절감율** | — | **~72%** |
| 100턴 런 비용 | $0.75 | $0.21 |

> Claude의 캐시 Read 90% 할인이 가장 큰 절감 효과.
> GPT-4o-mini는 단가 자체가 낮아 절대 금액 차이는 작지만, 비율은 동일.

---

## §7 구현 단계

### Phase A: 프롬프트 재구조화 + 캐시 추적 (즉시)

| 파일 | 변경 |
|------|------|
| `server/src/llm/prompts/prompt-builder.service.ts` | L0 theme → system 메시지 병합, Tier 2/3 분리 |
| `server/src/llm/types/llm-provider.types.ts` | `LlmProviderResponse.cachedTokens` 추가, `LlmMessage.cacheControl` 추가 |
| `server/src/llm/providers/openai.provider.ts` | `cached_tokens` 수집, 로깅 |
| `server/src/llm/llm-worker.service.ts` | 캐시 히트율 로깅 추가 |

**효과**: OpenAI 자동 캐싱 활성화 + 모니터링 가능.

### Phase B: Claude Provider 구현 (다음)

| 파일 | 변경 |
|------|------|
| `server/src/llm/providers/claude.provider.ts` | @anthropic-ai/sdk 기반 구현, cache_control 변환 |
| `package.json` | `@anthropic-ai/sdk` 의존성 추가 |

**효과**: Claude 사용 시 Tier 1+2 캐시 → 72% 입력 비용 절감.

### Phase C: Gemini Provider 구현 (보류)

현재 프롬프트 규모(~3K tok)에서는 Gemini Context Caching의 최소 요구(32K tok)를 충족하지 못함.
프롬프트가 대폭 확장되거나 배치 처리가 도입될 때 재검토.

---

## §8 주의사항

1. **TTL 의존성**: OpenAI 캐시 TTL이 5~10분 → 플레이어가 10분 이상 멈추면 캐시 만료. 게임 특성상 턴 간격이 짧아(2~30초) 대부분 히트 예상.

2. **L0 theme 불변 원칙 유지**: system 메시지로 이동해도 L0 theme은 런 생성 시 고정, 이후 절대 변경 없음 (기존 [[CLAUDE]] 불변 규칙 준수).

3. **assistant 메시지 연속 금지**: OpenAI API는 동일 role 연속 메시지를 허용하지만, Claude API는 user/assistant 교대가 필수. Tier 2와 Tier 3를 하나의 assistant 메시지로 합치되 내부 구분선으로 분리.

4. **캐시 prefix 바이트 동일성**: OpenAI 자동 캐싱은 바이트 레벨 prefix 비교. JSON.stringify(theme)의 키 순서가 일정해야 함 → 정렬 보장 필요.

5. **프로바이더 전환 투명성**: `cacheControl` 필드는 OpenAI/Gemini/Mock에서 무시. 프로바이더 전환 시 프롬프트 구조 변경 불필요.
