# 05 --- LLM 내러티브 & 컨텍스트 시스템

> LLM은 **서술 전용**이다. 게임 규칙, 수치, 판정은 서버(SoT)가 확정하며, LLM은 서버 결과를 바탕으로 생생한 내러티브 텍스트만 생성한다. LLM 호출이 실패해도 게임은 진행된다(graceful degradation).
>
> 마지막 갱신: 2026-03-16 (장면 연속성 시스템, Structured Memory v2, THREAD/MEMORY/CHOICES 태그 반영)

---

## 1. LLM 시스템 개요

### 1.1 역할 분리

| 구분 | 담당 |
|------|------|
| 서버 (SoT) | 판정, 수치, 상태 변경, 이벤트 매칭, 보상 계산 |
| LLM | 확정된 사실(events + summary)을 2인칭 산문으로 서술 + [THREAD]/[MEMORY]/[CHOICES] 태그 생성 |

LLM 출력은 게임 결과에 영향을 주지 않는다. `turns.llmOutput`에 저장되며, 클라이언트 표시 전용이다.

### 1.2 비동기 파이프라인

```
턴 제출 → 서버 판정(ServerResultV1 확정)
  → turns.llmStatus = 'PENDING'
  → [비동기] LLM Worker 폴링 (2s 간격)
    → ContextBuilder.build() → L0-L4 + 확장 컨텍스트 구축
    → PromptBuilder.buildNarrativePrompt() → 메시지 배열 조립
    → LlmCaller.call() → provider 호출 (재시도/fallback 포함)
    → 성공:
      → [MEMORY] 태그 파싱 → structuredMemory.llmExtracted에 저장
      → [THREAD] 태그 파싱 → node_memories.narrativeThread에 누적
      → [CHOICES] 태그 파싱 → turns.llmChoices에 저장
      → 태그 제거 후 narrative → turns.llmOutput = 'DONE'
    → 실패: llmStatus = 'FAILED', 에러 JSON 저장
  → 클라이언트 폴링 (2s, max 15회) → narrator 메시지 교체
```

### 1.3 LLM Worker 동작

| 항목 | 값 |
|------|-----|
| 폴링 간격 | `POLL_INTERVAL_MS = 2000` |
| 락 타임아웃 | `LOCK_TIMEOUT_S = 60` |
| 락 방식 | `llmLockedAt` + `llmLockOwner` (워커 ID) |
| 타임아웃 복구 | RUNNING + locked_at 60s 초과 → PENDING 리셋 |
| 실패 처리 | `llmStatus = 'FAILED'`, 에러 JSON 저장 |
| 요약 저장 | DONE 후 `recent_summaries`에 narrative 삽입 |

### 1.4 LLM Worker 태그 파싱 (3종)

> 정본: `server/src/llm/llm-worker.service.ts`

LLM 출력에서 3종 태그를 파싱 후 서술 본문에서 제거:

| 태그 | 파싱 | 저장 위치 | 예산 |
|------|------|----------|------|
| `[MEMORY:카테고리]...[/MEMORY]` | 최대 2개, 50자 절삭 | `run_memories.structuredMemory.llmExtracted[]` (최대 15개) | 카테고리: NPC_DETAIL, PLACE_DETAIL, PLOT_HINT, ATMOSPHERE, NPC_KNOWLEDGE |
| `[THREAD]...[/THREAD]` | 최대 200자 절삭 | `node_memories.narrativeThread` (JSON, 누적) | 총 1200자 초과 시 오래된 엔트리 삭제 |
| `[CHOICES]...[/CHOICES]` | LOCATION 턴만, 3개 선택지 파싱 | `turns.llmChoices[]` | go_hub 선택지 자동 추가 |

**Narrative Thread 누적**:
```typescript
{ entries: [
  { turnNo: 5, summary: "경비대 본부. 야간 책임자에게서 창고 관리인 순찰 경로가 적힌 종이뭉치를 받음." },
  { turnNo: 6, summary: "창고 뒷문 근처. 종이뭉치 단서를 따라 관리인 추적 중. 발자국과 금속 조각 발견." }
]}
```

### 1.5 LLM Status Enum

`SKIPPED | PENDING | RUNNING | DONE | FAILED`

### 1.6 LLM 재시도 (Retry) 시스템

> 정본: `server/src/turns/turns.controller.ts` (POST retry-llm), `client/src/components/ui/LlmFailureModal.tsx`

```
FAILED 감지 (클라이언트 폴링)
  → LlmFailureModal 표시 (재시도 / 건너뛰기 / 닫기)
  → [재시도] POST /v1/runs/:runId/turns/:turnNo/retry-llm
    → 서버: FAILED → PENDING 리셋 (llmError, llmLockedAt, llmLockOwner null)
    → Worker가 다음 폴링(2s)에서 자동 감지 → 재처리
    → 클라이언트: 재폴링 시작
  → [건너뛰기] narrator를 "..." fallback 텍스트로 교체 → pending flush
  → [닫기] 모달만 닫기 (fallback 텍스트로 진행)
```

---

## 2. 컨텍스트 5계층 (L0 -- L4) + 확장

`ContextBuilderService.build()`가 DB에서 조회하여 `LlmContext` 객체를 구성한다. 상위 레이어일수록 우선순위가 높다.

### 2.0 LlmContext 인터페이스 (현행)

> 정본: `server/src/llm/context-builder.service.ts`

```typescript
interface LlmContext {
  // L0: 세계관 기억
  theme: unknown[];                    // 절대 삭제 금지
  worldSnapshot: string | null;        // WorldState 요약 (시간/경계도/긴장도)
  // L1: 이야기 요약
  storySummary: string | null;         // run_memories.storySummary
  locationContext: string | null;      // 현재 LOCATION ID
  // L2: 노드 사실
  nodeFacts: unknown[];                // node_memories.nodeFacts
  // L3: 최근 맥락 (우선순위 체인)
  recentSummaries: string[];           // recent_summaries (fallback)
  recentTurns: RecentTurnEntry[];      // 글로벌 최근 5턴 (차선)
  locationSessionTurns: RecentTurnEntry[];  // 현재 방문 전체 대화 (최우선, max 20)
  // L4: 이번 턴
  currentEvents: unknown[];            // serverResult.events
  summary: string;                     // summary.short + resolveOutcome
  agendaArc: string | null;            // Agenda/Arc 진행도

  // === 확장 필드 (Phase 2~3, Narrative v1) ===

  // NPC 관계/프로필
  npcRelationFacts: string[];          // NPC 관계 서술 요약 (displayName 사용)
  playerProfile: string | null;        // PBP 성향 요약

  // Turn Orchestration (Phase 3)
  npcInjection: { npcId?: string; npcName: string; introduced?: boolean;
    posture: string; dialogueSeed: string; reason: string } | null;
  peakMode: boolean;                   // 감정 절정 모드
  npcPostures: Record<string, string>; // npcId → effective posture

  // Equipment (Phase 4)
  equipmentTags: string[];             // 장비 서술 태그 (최대 6개)
  activeSetNames: string[];            // 활성 세트 이름

  // 캐릭터
  gender: 'male' | 'female';

  // Narrative Thread Cache
  narrativeThread: string | null;      // node_memories.narrativeThread (JSON)

  // Narrative Engine v1
  incidentContext: string | null;      // 활성 Incident 요약
  npcEmotionalContext: string | null;  // NPC 5축 감정 상태 요약
  narrativeMarkContext: string | null; // Narrative Mark 요약
  signalContext: string | null;        // Signal Feed (severity ≥ 3)

  // NPC 소개 시스템
  introducedNpcIds: string[];          // 이미 소개된 NPC
  newlyIntroducedNpcIds: string[];     // 이번 턴 이름 공개
  newlyEncounteredNpcIds: string[];    // 이번 턴 첫 만남

  // Structured Memory v2
  structuredSummary: string | null;    // visitLog 기반 이야기 요약
  npcJournalText: string | null;      // NPC 관계 일지
  incidentChronicleText: string | null; // 사건 연대기
  milestonesText: string | null;      // 서사 이정표
  llmFactsText: string | null;        // LLM 추출 사실 ([MEMORY] 태그 누적)

  // 장면 연속성 (2026-03-16 추가)
  currentSceneContext: string | null;  // 대화 상대, 세부 위치, 진행 중인 상황

  // 장소 전환 맥락 (Fixplanv1 PR3 추가)
  previousVisitContext: string | null; // 직전 장소 VisitExitSummary 텍스트
}
```

### 2.1 L0 -- Theme (절대 삭제 금지)

| 항목 | 설명 |
|------|------|
| 소스 | `run_memories.theme` |
| 내용 | 메인 아크, 퀘스트, 핵심 NPC, KEY_ITEM 등 |
| 제한 | max 12개, 항목당 max 220자 |
| 정책 | **토큰 예산 압박에도 삭제 금지**. 필요 시 문장을 짧게 정제할 수는 있으나 항목 자체를 삭제하지 않는다 |

**L0 확장 -- WorldState 스냅샷**:
- 소스: `runState.worldState`
- 형식: `"시간: 낮/밤, 경계도: {hubHeat}/100 ({hubSafety}), 긴장도: {tension}/10"`

### 2.2 L1 -- Story Summary

| 항목 | 설명 |
|------|------|
| 소스 | `run_memories.storySummary` 또는 `structuredMemory.visitLog` |
| 내용 | Structured Memory v2 우선, fallback으로 기존 storySummary |
| 제한 | max 2000자 |

**L1 확장 -- LOCATION 컨텍스트**:
- 형식: `"현재 위치: {locationId}"`

### 2.3 L2 -- Node Facts

| 항목 | 설명 |
|------|------|
| 소스 | `node_memories.nodeFacts` (현재 nodeInstanceId) |
| 내용 | 현재 노드에서 축적된 사실 |
| 제한 | max 20개, 항목당 max 220자 |

### 2.4 L3 -- Recent Context

3가지 소스가 **우선순위 체인**으로 상호 배타적 선택된다:

```
locationSessionTurns > recentTurns > recentSummaries
```

#### (a) locationSessionTurns (최우선)

| 항목 | 설명 |
|------|------|
| 소스 | `turns` 테이블 (runId + nodeInstanceId, SYSTEM 제외) |
| 범위 | 현재 LOCATION 방문의 전체 대화 (COMBAT 시 부모 LOCATION 포함) |
| 제한 | max 20턴 |
| 서술 포함 | 직전 턴 300자, 2~3턴 전 150~250자, **4턴 이전도 100자** (2026-03-16 변경) |

#### (b) recentTurns / (c) recentSummaries

locationSession 없을 때 fallback. 동일 구조.

### 2.5 L4 -- Current Turn + Extensions

| 항목 | 설명 |
|------|------|
| currentEvents | `serverResult.events` (UI kind 필터링) |
| summary | `serverResult.summary.short` + resolveOutcome |
| agendaArc | Agenda dominant + Arc route/commitment |
| npcRelationFacts | NPC 관계 서술 요약 (displayName 사용) |
| playerProfile | PBP dominant/secondary + scores |
| equipmentTags | 장비 인상 태그 (서술 톤 영향) |

---

## 3. 장면 연속성 시스템 (2026-03-16 구현)

> 정본: `context-builder.service.ts` (currentSceneContext), `prompt-builder.service.ts` (3-tier sceneFrame)

### 3.1 문제와 해결

**문제**: EventMatcher가 매 턴 다른 이벤트를 선택하면 sceneFrame(이벤트 배경 묘사)이 바뀌어 LLM이 장면을 점프함.

**해결**: 3가지 메커니즘으로 장면 연속성 보장.

### 3.2 `[현재 장면 상태]` 컨텍스트 블록

`context-builder.service.ts`에서 자동 구축, Memory Block에 삽입:

```
[현재 장면 상태]
아래는 지금 진행 중인 장면의 핵심 맥락입니다. 서술은 반드시 이 장면에서 이어져야 합니다.

대화/상호작용 상대: 권위적인 야간 경비 책임자 (CAUTIOUS)
직전 장면(이어쓸 지점): ...종이뭉치를 손에 쥐고 살펴보는 순간, 주변 공기마저 긴장감으로 무거워졌다.
현재 위치: 경비대 지구
이번 방문 4턴째
직전 행동: "획득한 종이뭉치를 단서 삼아 창고 관리인을 추적한다" → 부분 성공
```

**데이터 출처**:
- `actionContext.primaryNpcId` + `getNpcDisplayName()` → 대화 상대
- 2턴 이상 진행: 직전 내러티브 마지막 150자 (sceneFrame 무시)
- 첫/두번째 턴: `actionContext.eventSceneFrame` → 장면 배경
- `worldState.currentLocationId` → 현재 위치
- `locationSessionTurns.length` → 방문 턴 수

### 3.3 sceneFrame 3단계 억제 (Facts Block)

| 조건 | sceneFrame 처리 | 지시 |
|------|----------------|------|
| 첫 턴 (narrative 0개) | 그대로 전달 | "플레이어 행동 먼저, 상황이 자연스럽게 펼쳐지도록" |
| 1턴 진행 (narrative 1개) | `[참고 배경]`으로 격하 | "분위기 참고만, 인물/장소 전환 금지" |
| 2턴 이상 진행 | **완전 억제** | "장면 연속성 절대 우선: 직전 서술의 인물/장소/대화를 이어가세요" |

### 3.4 `[이번 방문 대화]` 연속성 규칙 (7개)

1. 직전 서술 반복/복사 금지
2. 직전 서술 마지막 장면에서 자연스럽게 이어가기
3. 같은 NPC와 상호작용 이어가기 (갑작스러운 인물 전환 금지)
4. 같은 장소에서 계속하기
5. [상황 요약]은 장면 전환 지시가 아님
6. **NPC가 알려준 정보/획득 물건을 기억하고 반복 금지** (2026-03-16)
7. **이미 대화한 NPC는 이전 대화 내용을 알고 있어야 함** (2026-03-16)

### 3.5 Narrative Thread (`[장면 흐름]` 블록)

`node_memories.narrativeThread`에 누적된 장면 요약이 Memory Block에 삽입:

```
[장면 흐름]
이 장소 방문 중 누적된 장면 맥락입니다. 이 흐름에서 자연스럽게 이어가세요.
⚠️ 이미 알게 된 정보를 NPC가 다시 처음 알려주는 것처럼 반복하지 마세요.

[턴 5] 경비대 본부. 야간 책임자에게 창고 관리인에 대해 물음. 관리인이 서류를 은밀히 반출한다는 정보 획득.
[턴 6] 책임자에게서 순찰 경로와 뒷문 위치가 적힌 종이뭉치를 받음.
[턴 7] 종이뭉치 단서를 따라 창고 뒷문 근처 추적. 발자국과 금속 조각 발견.
```

---

## 4. LOCATION 메모리 시스템

### 4.1 단기 기억 (locationSessionTurns)

- **범위**: 현재 `nodeInstanceId`에 속한 전체 턴 (SYSTEM 제외) + COMBAT 시 부모 LOCATION 턴 포함
- **생애주기**: LOCATION 진입 ~ go_hub(HUB 복귀)
- **서술 포함 정책** (2026-03-16 변경):

| 턴 위치 | 서술 포함량 | 용도 |
|---------|-----------|------|
| 직전 턴 (distFromEnd=0) | 마지막 300자 | "여기서 이어쓰세요" 지점 명확화 |
| 2~3턴 전 (distFromEnd 1~2) | 마지막 150~250자 | 맥락 참고 |
| **4턴 이전 (distFromEnd 3+)** | **마지막 100자** | **핵심 정보 유지 (NPC 대사, 단서)** |

> 이전에는 4턴 이전 서술이 완전 누락되어 LLM이 NPC 대화 기억을 잃는 문제가 있었음.

### 4.2 장기 기억 (Structured Memory v2)

go_hub 선택 시 `MemoryIntegration.finalizeVisit()` 호출:
- `run_memories.structuredMemory` (visitLog, npcJournal, incidentChronicle, milestones, llmExtracted, npcKnowledge, lastExitSummary) 통합 저장
- 호환용 `storySummary` 동시 저장

### 4.3 메모리 흐름 요약

```
LOCATION 진입
  ├── 매 턴: turns 테이블에 기록 + MemoryCollector.collect() (visitContext 실시간 수집)
  ├── LLM 호출 시:
  │   ├── locationSessionTurns → [이번 방문 대화] (단기 기억)
  │   ├── narrativeThread → [장면 흐름] (장면 맥락 캐시)
  │   └── currentSceneContext → [현재 장면 상태] (장면 연속성)
  ├── LLM 완료 시:
  │   ├── [THREAD] → node_memories.narrativeThread 누적 (max 1200자)
  │   ├── [MEMORY] → structuredMemory.llmExtracted 추가 (max 15개)
  │   └── [CHOICES] → turns.llmChoices 저장
  └── go_hub 선택 시:
      ├── MemoryIntegration.finalizeVisit() → 구조화 메모리 통합
      └── actionHistory 초기화 (고집 이력 리셋)
```

---

## 5. 프롬프트 빌더

> 정본: `server/src/llm/prompts/prompt-builder.service.ts`

`PromptBuilderService.buildNarrativePrompt()`가 LlmContext + ServerResultV1을 받아 LLM API 호출용 메시지 배열을 조립한다.

### 5.1 메시지 구조 (3블록)

```
[system]  NARRATIVE_SYSTEM_PROMPT + 성별 힌트 + 세계관 기억 (cacheControl: 'ephemeral')
[assistant]  Memory Block (L0-L4 + 확장 컨텍스트, cacheControl: 'ephemeral')
[user]  Facts Block (이번 턴 정보)
```

### 5.2 Memory Block (assistant role) — 조립 순서 (현행)

| 순서 | 태그 | 소스 | 조건 |
|------|------|------|------|
| 1 | `[세계 상태]` | ctx.worldSnapshot | L0 확장 |
| 2 | `[서사 이정표]` | ctx.milestonesText | Structured Memory v2 |
| 3 | `[이야기 요약]` | ctx.structuredSummary (우선) / ctx.storySummary (fallback) | L1 |
| 3.5 | `[직전 장소 정보]` | ctx.previousVisitContext | Fixplanv1 PR3: 장소 전환 맥락 (PREVIOUS_VISIT 150토큰) |
| 4 | `[NPC 관계]` | ctx.npcJournalText | Structured Memory v2 |
| 5 | `[사건 일지]` | ctx.incidentChronicleText | Structured Memory v2 |
| 6 | `[기억된 사실]` | ctx.llmFactsText | Structured Memory v2 (LLM [MEMORY] 누적) |
| 7 | `[현재 장소]` | ctx.locationContext | L1 확장 |
| 8 | `[현재 장면 상태]` | ctx.currentSceneContext | 장면 연속성 (2026-03-16) |
| 9 | `[현재 노드 사실]` | ctx.nodeFacts | L2 |
| 10 | `[장면 흐름]` | ctx.narrativeThread (JSON 파싱) | Narrative Thread Cache |
| 11a | `[이번 방문 대화]` | ctx.locationSessionTurns | L3 (최우선) |
| 11b | `[최근 대화 이력]` | ctx.recentTurns | L3 (차선) |
| 11c | `[최근 서술]` | ctx.recentSummaries | L3 (fallback) |
| 12 | `[등장 가능 NPC 목록]` | allNpcs + 소개 상태 5-way 분기 | NPC 소개 시스템 |
| 13 | `[활성 사건 현황]` / `[도시 사건]` | ctx.incidentContext | Narrative v1 (구조화 메모리 유무에 따라 분기) |
| 14 | `[도시 시그널]` | ctx.signalContext | severity ≥ 3 |
| 15 | `[성향/아크]` | ctx.agendaArc | L4 확장 |
| 16 | `[플레이어 프로필]` | ctx.playerProfile | PBP |
| 17 | `[장비 인상]` | ctx.equipmentTags + activeSetNames | Phase 4 |

### 5.3 Facts Block (user role) — 조립 순서 (현행)

| 순서 | 내용 | 조건 |
|------|------|------|
| 1 | `[이번 턴 플레이어 행동]` / `[플레이어 선택]` | inputType !== 'SYSTEM' |
| 1a | sceneFrame 3단계 처리 (§3.3) | ACTION + eventSceneFrame 존재 시 |
| 1b | 고집 에스컬레이션 지시 | escalated === true |
| 2 | `[상황 요약]` (summary.short) | 항상 |
| 3 | `[이번 턴 사건]` (events, UI kind 필터링) | events 존재 시 |
| 4 | `[분위기]` (toneHint) | 항상 |
| 5 | `[NPC 등장]` (npcInjection + 소개 지시) | Phase 3 Orchestration |
| 6 | `[감정 절정]` (peakMode) | peakMode === true |
| 7 | `[NPC 대화 자세]` (npcPostures) | postures 존재 시 |
| 8 | `[서술 지시]` (프롤로그 3막 구조) | turnNo === 0 |
| 9 | `[보너스 행동 슬롯 활성]` | flags.bonusSlot |
| 10 | `[참고 선택지]` + `[CHOICES]` 생성 지시 | choices 존재 시 |

### 5.4 ActionContext (현행)

`serverResult.ui.actionContext`에서 추출:

| 필드 | 설명 |
|------|------|
| `parsedType` | IntentParserV2가 해석한 ActionType |
| `originalInput` | 플레이어 원문 입력 |
| `tone` | 행동 톤 (NEUTRAL 제외 시 표시) |
| `escalated` | 고집 에스컬레이션 여부 |
| `insistenceCount` | 고집 반복 횟수 |
| `eventSceneFrame` | 매칭된 이벤트의 배경 묘사 (3단계 억제 대상) |
| `eventMatchPolicy` | 이벤트 matchPolicy (SUPPORT/BLOCK/NEUTRAL) |
| `eventId` | 매칭된 이벤트 ID |
| `primaryNpcId` | 이벤트의 주 NPC ID (null 가능) |

---

## 6. 서사 규칙

### 6.1 System Prompt 핵심 규칙

> 정본: `server/src/llm/prompts/system-prompts.ts`

| 규칙 | 내용 |
|------|------|
| 시점 | 2인칭 ("당신"), 관찰자 시점 |
| 서술체 | **해라체(~다, ~했다)** 문어체 통일. 합쇼체(~합니다) 금지 |
| NPC 대사 | 큰따옴표(""), 별도 줄, 중세 경어체(~소/~오/~하오) |
| NPC 호칭 | "그대" 또는 "당신" 사용. **"너" 금지** |
| 강조 | 작은따옴표('') (대사가 아닌 경우) |
| 플레이어 대사 | **절대 금지** — 행동/시선/손짓으로만 반응 |
| 내면 묘사 | 감정/판단/결심 직접 서술 금지 → 외면적 단서로만 |
| 분량 | **일반 500~800자, 프롤로그 600~1000자** (500자 미만 금지) |
| 사건 중심 | 서술 60% 이상 구체적 사건, 분위기 묘사 30% 이하 |
| 장면 범위 | 한 턴 = 하나의 행동 결과. 선택지 행동 미리 수행 금지 |
| 세계관 | 서양 중세 판타지 (동양 요소 금지) |
| 태그 출력 금지 | [THREAD], [MEMORY], [CHOICES] 외 대괄호 태그 출력 금지 |
| NPC 소스 제한 | 서버 제공 NPC만 사용. 이름 있는 새 NPC 창작 금지 |

### 6.2 장면/NPC 연속성 규칙

| 규칙 | 내용 |
|------|------|
| 장면 연속성 | [이번 방문 대화]에서 확립된 장소/상황을 반드시 이어감 |
| NPC 연속성 | 이전 턴 NPC와 같은 인물로 상호작용 이어감 |
| sceneFrame | 참고용 분위기 소재. 이전 장면과 충돌 시 이전 장면 우선 |
| 정보 기억 | NPC가 알려준 정보/획득 물건을 기억. 반복 금지 |
| 기억 활용 | 재방문 시 이전 방문 흔적 반영, NPC는 이전 대화 기억 |

### 6.3 프롤로그 (turnNo === 0)

3막 구조:
1. **1막 (40%)**: 장소/분위기 감각 묘사. NPC 미등장.
2. **2막 (35%)**: NPC 등장, 경계/망설임. 대사 1~2마디로 호기심 유발.
3. **3막 (25%)**: 핵심 의뢰 제시. 수락/거절 결정 장면은 쓰지 않음.

### 6.4 LLM 출력 태그 3종 (필수)

| 태그 | 위치 | 용도 |
|------|------|------|
| `[CHOICES]...[/CHOICES]` | 서술 본문 뒤 | 맥락 선택지 3개 (구체적 고유명사 포함, AFFORDANCE 2종 이상) |
| `[MEMORY:카테고리]...[/MEMORY]` | [CHOICES] 뒤 | 향후 활용 사실 추출 (최대 2개, 50자 이내) |
| `[THREAD]...[/THREAD]` | 맨 마지막 줄 | 장면 요약 (80~180자, 장소+인물+상황+핵심정보) |

---

## 7. Structured Memory v2 프롬프트 블록

> 정본: `server/src/llm/memory-renderer.service.ts`, `server/src/llm/context-builder.service.ts`

기존 storySummary를 대체하는 구조화 메모리. 존재 시 우선 사용.

| 블록 | 소스 | 용도 |
|------|------|------|
| `[이야기 요약]` | visitLog (방문 기록) | 재방문 시 이전 행동 결과 흔적 반영 |
| `[직전 장소 정보]` | lastExitSummary (PR3) | 장소 전환 시 직전 장소 맥락 보존 (keyActions, keyDialogues, unresolvedLeads) |
| `[NPC 관계]` | npcJournal + npcKnowledge | NPC 태도/과거 상호작용 → 대사 톤 반영. NPC가 알고 있는 정보도 포함 (PR4) |
| `[사건 일지]` | incidentChronicle | 진행 중 사건 여파 → 배경 묘사 반영 |
| `[기억된 사실]` | llmExtracted | LLM [MEMORY] 태그 누적 → 감각적 디테일 재활용 (타 장소 importance≥0.7도 포함, max 3) |
| `[서사 이정표]` | milestones | 중요 사건 콜백 (NPC 대사/배경 간접 언급) |

### NPC Knowledge 파이프라인 (Fixplanv1 PR4)

NPC가 플레이어와의 대화에서 알게 된 정보를 기록하고 프롬프트에 반영:

```
트리거 조건: 7종 대화형 actionType (TALK, PERSUADE, BRIBE, INVESTIGATE, OBSERVE, HELP, THREATEN)
  + SUCCESS/PARTIAL 판정
  + targetNpcId 존재 (primaryNpcId 우선, 없으면 eventTags에서 TAG_TO_NPC 매핑)
  → MemoryCollector.collectNpcKnowledge() 호출
  → structuredMemory.npcKnowledge[npcId] 저장 (NPC당 max 5, importance 기반 정리)
  → 다음 턴 [등장 가능 NPC 목록]에 "이 인물이 알고 있는 것" 렌더링
```

---

## 8. NPC 소개 시스템 프롬프트 연동

> 정본: `prompt-builder.service.ts` NPC 로스터 섹션

`[등장 가능 NPC 목록]`에서 소개 상태에 따라 5-way 분기:

| 상태 | 표시 | LLM 지시 |
|------|------|---------|
| 첫 만남 + 소개 | `npc.name` | "자기소개(이름 포함) 서술" |
| 재만남 + 소개 | `npc.name` | "타인 언급/상황 단서로 이름 드러남" |
| 첫 만남 + 미소개 | `"unknownAlias"` | "이름 미공개, 별칭으로만 지칭" |
| 이미 소개 | `npc.name` | (지시 없음) |
| 미등장/미소개 | `"unknownAlias"` | "이름 미공개" |

---

## 9. 예산 정책

### 9.1 항목별 한도

| 항목 | 최대 | 비고 |
|------|------|------|
| theme (L0) | 12개, 항목당 220자 | 절대 삭제 금지 |
| storySummary (L1) | 2000자 | |
| nodeFacts (L2) | 20개, 항목당 220자 | |
| recentTurns (L3b) | 5턴, 서술 200자 | |
| locationSessionTurns (L3a) | 20턴 | 직전 300자, 2~3턴전 150~250자, 4턴전+ 100자 |
| narrativeThread | 총 1200자 | 항목당 max 200자 |
| llmExtracted | 15개, 항목당 50자 | |

### 9.2 LLM 호출 설정 (.env)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_MAX_RETRIES` | 2 | 재시도 횟수 |
| `LLM_TIMEOUT_MS` | 8000 | 호출 타임아웃 |
| `LLM_MAX_TOKENS` | 1024 | 최대 출력 토큰 |
| `LLM_TEMPERATURE` | 0.8 | 창의성 |
| `LLM_FALLBACK_PROVIDER` | mock | 실패 시 fallback |

---

## 10. 구현 상태 요약

### 10.1 구현 완료

| 파일 | 역할 |
|------|------|
| `server/src/llm/context-builder.service.ts` | L0-L4 + 확장 컨텍스트 구축, NPC 소개/시그널/Structured Memory/장면 연속성 포함 |
| `server/src/llm/prompts/prompt-builder.service.ts` | 3블록 메시지 조립, NPC 소개 5-way, sceneFrame 3단계 억제, NPC 정보 기억 규칙 |
| `server/src/llm/prompts/system-prompts.ts` | NARRATIVE_SYSTEM_PROMPT (해라체, NPC 호칭, 장면/NPC 연속성, THREAD/MEMORY/CHOICES 태그) |
| `server/src/llm/llm-worker.service.ts` | 비동기 폴링, 락/복구, [THREAD]/[MEMORY]/[CHOICES] 파싱, narrativeThread 누적 |
| `server/src/llm/llm-caller.service.ts` | 멀티 provider 호출 (OpenAI/Claude/Gemini/Mock), 재시도/fallback |
| `server/src/llm/llm-config.service.ts` | .env 기반 + PATCH /v1/settings/llm 런타임 변경 |
| `server/src/llm/ai-turn-log.service.ts` | AI 호출 로그 기록 (ai_turn_logs) |
| `server/src/llm/memory-renderer.service.ts` | Structured Memory → 프롬프트 블록 렌더링 |

### 10.2 설계 대비 현황

| 설계 항목 | 상태 | 비고 |
|-----------|------|------|
| L0-L4 5계층 컨텍스트 | ✅ 구현 | + 확장 15개 필드 |
| LOCATION 단기 기억 | ✅ 구현 | 모든 턴 서술 snippet 포함 (2026-03-16) |
| Structured Memory v2 장기 기억 | ✅ 구현 | visitLog/npcJournal/incidentChronicle/milestones/llmFacts |
| 장면 연속성 (currentSceneContext) | ✅ 구현 | 대화 상대, 세부 위치, 직전 행동 (2026-03-16) |
| sceneFrame 3단계 억제 | ✅ 구현 | 첫턴=전달, 1턴=참고, 2턴+=완전억제 (2026-03-16) |
| Narrative Thread ([THREAD] 누적) | ✅ 구현 | max 200자/항목, 총 1200자 (2026-03-16 확대) |
| [MEMORY] 태그 추출 | ✅ 구현 | NPC_DETAIL/PLACE_DETAIL/PLOT_HINT/ATMOSPHERE |
| [CHOICES] 맥락 선택지 | ✅ 구현 | LLM이 구체적 선택지 3개 생성, go_hub 자동 추가 |
| NPC 소개 시스템 | ✅ 구현 | 5-way 분기 (소개 시점 × 만남 여부) |
| NPC 감정/posture 서술 | ✅ 구현 | 5축 감정 → effective posture → LLM 전달 |
| Turn Orchestration | ✅ 구현 | NPC 주입 + pressure/peakMode |
| LLM 재시도 | ✅ 구현 | retry-llm API + LlmFailureModal |
| 예산 축소 (trimToBudget) | ⚠️ 부분 | 기본 제한 적용, 동적 축소는 향후 |
| 캐시 전략 | ❌ 미구현 | 매 호출마다 DB 조회 |

---

> **정본 파일**: `server/src/llm/context-builder.service.ts`, `server/src/llm/prompts/prompt-builder.service.ts`, `server/src/llm/prompts/system-prompts.ts`, `server/src/llm/llm-worker.service.ts`
