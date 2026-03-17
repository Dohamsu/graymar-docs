# 19 — Event Orchestration System v1.1

## 목적

현재 LOCATION과 상태에 맞는 이벤트를 선택한다.

## Event Director

이벤트 선택 정책 계층

### 선택 알고리즘

1.  Stage Filter
2.  Condition Filter
3.  Cooldown Filter
4.  Priority Sort
5.  Weighted Random

### Priority Weight

  priority   weight
  ---------- --------
  critical   10
  high       6
  medium     3
  low        1

## Event Library

LOCATION별 이벤트 관리

### Event Schema

{ "event_id": "inspect_door", "type": "discovery", "priority": "medium",
"stage": \["investigation"\], "cooldown": 2, "effects": { "progress":
0.05 } }

### Event Types

-   interaction
-   discovery
-   conflict
-   atmosphere
-   story

### 권장 수량

LOCATION당 20\~30 events
