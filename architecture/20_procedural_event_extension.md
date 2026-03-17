# 20 — Procedural Event Extension v1.1

## 목적

고정 이벤트가 부족한 구간에서 동적 이벤트 생성

## Procedural Event 구조

Trigger + Subject + Action + Outcome

예시:

npc_nervous_reaction + dock_guard + denies + suspicion_up

## Seed Types

-   Trigger
-   Subject
-   Action
-   Outcome

## Context Filter

입력 요소: - location - stage - time - npc - active clues - player
intent

## Anti-Repetition Rules

  rule                      value
  ------------------------- ---------
  trigger cooldown          3 turns
  subject-action cooldown   5 turns
  same outcome repeat       max 2
  same npc focus            max 3

## Fallback

1.  atmosphere event
2.  low priority fixed event
3.  narrative reaction only
