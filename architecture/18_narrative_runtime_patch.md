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
  Structured Memory   500
  User Input          200
  Buffer              300

### Recent Story 정책

-   최대 6턴 유지
-   이후 Mid Summary 생성

### Mid Summary

요약 대상: - resolved incidents - new clues - npc state change -
location state change

### Intent Memory

플레이어 행동 패턴 기록

예시: - aggressive interrogation - stealth exploration - evidence
focused investigation
