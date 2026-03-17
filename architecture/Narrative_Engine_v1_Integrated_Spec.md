# Narrative Engine v1

## Integrated Design & Implementation Specification

------------------------------------------------------------------------

# 1. Project Philosophy

## Game Identity

-   Memory-driven political narrative RPG
-   The player is a passing figure who eventually leaves the city
-   The world moves autonomously
-   Certain choices create permanent narrative marks

## Core Axes

1.  World Simulation
2.  Incident System (Dual-axis Model)
3.  Emotional Relationship + Narrative Mark
4.  Time & Deadline Transition

------------------------------------------------------------------------

# 2. Core Gameplay Loop

HUB (Strategic Brief) → LOCATION Entry → Operation Session (2--3 Steps)
→ Time Consumption → WorldTick → Signal Generation → Return to HUB

------------------------------------------------------------------------

# 3. World Simulation

``` ts
WorldSimulationState {
  globalClock: number;
  day: number;
  phase: "DAWN" | "DAY" | "DUSK" | "NIGHT";
  heat: number;
  tension: number;
  activeIncidents: IncidentRuntime[];
  npcGoals: Record<string, NpcGoalState>;
}
```

WorldTick runs before and after each operation step.

------------------------------------------------------------------------

# 4. Incident System (Dual-Axis Model)

## Runtime Structure

``` ts
IncidentRuntime {
  id: string;
  kind: string;
  stage: number;
  control: number;   // 0–100
  pressure: number;  // 0–100
  deadlineClock: number;
  resolved: boolean;
  outcome?: "CONTAINED" | "ESCALATED" | "EXPIRED";
}
```

## Resolution Conditions

-   control ≥ 80 → CONTAINED
-   pressure ≥ 95 → ESCALATED
-   deadline exceeded → EXPIRED

------------------------------------------------------------------------

# 5. Operation Session (Player Action Structure)

``` ts
OperationTurn {
  sessionId: string;
  locationId: string;
  steps: Step[1..3];
  totalTimeCost: number;
  incidentPatches: IncidentImpactPatch[];
}
```

-   Each step consumes time.
-   Each step triggers WorldTick.
-   Player may exit early ("Return").

------------------------------------------------------------------------

# 6. Emotional Engine

## Mutable Emotional State

``` ts
NpcEmotionalState {
  trust: number;
  fear: number;
  respect: number;
  suspicion: number;
  attachment: number;
}
```

## Permanent Narrative Marks

``` ts
NarrativeMark {
  type: string;
  npcId?: string;
  factionId?: string;
  permanent: true;
  createdAt: number;
}
```

Total planned marks: 12 (7 main arc + 5 sub incidents).

Marks are irreversible and influence dialogue tone and behavior
triggers.

------------------------------------------------------------------------

# 7. Signal Feed System

``` ts
SignalFeedItem {
  channel: "RUMOR" | "SECURITY" | "NPC_BEHAVIOR" | "ECONOMY" | "VISUAL";
  severity: 1|2|3|4|5;
  locationId?: string;
  text: string;
  expiresAt?: number;
}
```

-   Local signals during operation
-   Global summary signals upon return
-   Severity 5 signals pinned in HUB

------------------------------------------------------------------------

# 8. Main Deadline Transition

``` ts
MainArcClock {
  startDay: number;
  softDeadlineDay: number;
  triggered: boolean;
}
```

Soft deadline exceeded: - Political state shifts - Key NPC consequences
occur - Story continues under altered conditions - No hard fail state

------------------------------------------------------------------------

# 9. Ending Generation System

Inputs: - Incident outcomes - NPC emotional states - Narrative marks -
Global heat & tension - Days spent

Output: - NPC-specific epilogues - City status summary - Closing line:
"The city was still breathing."

------------------------------------------------------------------------

# 10. LLM Role Contract

LLM Responsibilities: - Narrative expansion - Tone adjustment based on
emotional state - Mark-aware dialogue generation

LLM Restrictions: - No numeric calculation - No state mutation - No
authoritative rule decisions

Server remains Source of Truth.

------------------------------------------------------------------------

# 11. Structured Memory v2 (구현됨)

> 정본: `server/src/engine/hub/memory-collector.service.ts`, `memory-integration.service.ts`

## Memory Collection (매 LOCATION 턴)

`MemoryCollectorService.collect()` — visitContext 실시간 수집:
- 방문 장소, NPC 상호작용, 행동 결과, 사건 상태 변화

## Memory Integration (방문 종료 시)

`MemoryIntegrationService.finalizeVisit()` — 구조화 메모리 통합:
- `visitLog`: 방문 기록 누적
- `npcJournal`: NPC별 상호작용 이력
- `incidentChronicle`: 사건 타임라인
- `milestones`: 서사 이정표 (NarrativeMark 연동)
- `llmExtracted`: LLM [MEMORY] 태그 누적 (max 15개)

## LLM Context Integration

`MemoryRendererService` → 프롬프트 블록 렌더링:
- `[이야기 요약]`, `[NPC 관계]`, `[사건 일지]`, `[서사 이정표]`, `[기억된 사실]`
- 기존 storySummary/incidentContext/npcEmotionalContext 대체 (우선 사용)

------------------------------------------------------------------------

# 12. Scene Continuity System (2026-03-16 구현)

> 정본: `server/src/llm/context-builder.service.ts`, `prompt-builder.service.ts`

## Problem

EventMatcher가 매 턴 다른 이벤트를 선택 → sceneFrame 변경 → LLM 장면 점프

## Solution (3 메커니즘)

1. **`[현재 장면 상태]` 블록**: 대화 상대/세부 위치/직전 행동을 명시적 전달
2. **sceneFrame 3단계 억제**: 첫턴=전달, 1턴=참고, 2턴+=완전억제
3. **`[이번 방문 대화]` 규칙 강화**: 7개 연속성 규칙 (정보 기억, NPC 대화 맥락 유지)

## Narrative Thread

LLM `[THREAD]` 태그 → `node_memories.narrativeThread` 누적 (max 200자/항목, 총 1200자)
→ 장면 흐름 블록으로 LLM에 재전달

------------------------------------------------------------------------

# 13. Implementation Status (2026-03-16)

| 모듈 | 상태 |
|------|------|
| WorldTick + 4상 시간 | ✅ 구현 |
| Incident Dual-Axis | ✅ 구현 |
| Operation Session | ✅ 구현 |
| NPC Emotional + Mark | ✅ 구현 |
| Signal Feed | ✅ 구현 |
| Ending System | ✅ 구현 |
| Structured Memory v2 | ✅ 구현 |
| Scene Continuity | ✅ 구현 |
| NPC Introduction | ✅ 구현 |
| Turn Orchestration | ✅ 구현 |

------------------------------------------------------------------------

# Final Identity

This is not a power fantasy. This is not a full sandbox. This is not a
fixed visual novel.

This is a memory-driven political narrative engine where the player
leaves, but the city remembers.
