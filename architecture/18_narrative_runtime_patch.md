# 18 — Narrative Runtime Patch v1.1

## 목적

기존 Narrative Engine v1의 맥락 유지 성능을 강화하고 LLM 토큰 효율을
개선한다.

## 핵심 구성

### Context Layers

-   Scene Context
-   Player Intent Memory
-   Active Clues
-   Recent Story
-   Structured Memory

### Token Budget (≈2500 tokens)

  Layer               Tokens
  ------------------- --------
  System              300
  Scene Context       150
  Intent Memory       200
  Active Clues        150
  Recent Story        700
  Previous Visit      150
  Structured Memory   450
  User Input          200
  Buffer              250

### Recent Story 정책

-   최대 4턴 유지
-   이후 Mid Summary 생성

### Mid Summary

요약 대상: - resolved incidents - new clues - npc state change -
location state change

### Previous Visit Context (Fixplanv1 PR3 추가)

장소 전환 시 직전 장소 맥락을 보존하는 블록.

- `VisitExitSummary`: locationId, locationName, turnCount, keyActions(max 3), keyDialogues(max 3), unresolvedLeads(max 2)
- `StructuredMemory.lastExitSummary`에 저장
- LlmContext에 `previousVisitContext: string | null` 추가
- `[이야기 요약]` 뒤, `[NPC 관계]` 앞에 `[직전 장소 정보]` 블록 삽입
- 토큰 예산: PREVIOUS_VISIT 150 (priority=57, minTokens=0)

### Cross-Location Facts (Fixplanv1 PR3 추가)

- `renderLlmFacts()`: 타 장소 사실도 importance≥0.7이면 포함 (max 3개)
- 타 장소 사실에 `[장소명]` 접두사 추가

### Intent Memory

플레이어 행동 패턴 기록

예시: - aggressive interrogation - stealth exploration - evidence
focused investigation
