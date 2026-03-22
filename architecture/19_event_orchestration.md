# 19 — Event Orchestration System v1.2

> 마지막 갱신: 2026-03-22 (SituationGenerator 3계층 추가)

## 목적

현재 LOCATION과 상태에 맞는 이벤트를 선택한다. SituationGenerator가 우선 시도되며, 실패 시 EventMatcher가 fallback으로 동작한다.

---

## SituationGenerator (Living World v2)

월드 상태 기반 맥락적 상황 생성 시스템. EventMatcher보다 **우선** 실행된다.

### 3계층 구조

| Layer | 이름 | 입력 | 설명 |
|-------|------|------|------|
| **Layer 1** | Landmark | LocationDynamicState | 장소 고유 상태(security, crime, unrest) 기반 랜드마크 이벤트. 장소의 현재 분위기 반영 |
| **Layer 2** | Incident-Driven | ActiveIncidents + WorldFact | 활성 사건과 누적 사실에서 파생되는 상황. 사건의 여파가 장소에 미치는 영향 |
| **Layer 3** | World-State | NpcAgenda + NpcSchedule + WorldFact | NPC 자율 행동과 월드 사실 조합으로 창발적 상황 생성. 가장 동적인 계층 |

### 실행 흐름

```
SituationGenerator.generate(context)
  1. Layer 1 (Landmark) 시도
  2. Layer 2 (Incident-Driven) 시도
  3. Layer 3 (World-State) 시도
  → 유효한 상황 생성됨? → SituationEvent 반환
  → 모든 Layer 실패?   → null 반환 → EventMatcher fallback
```

### EventMatcher와의 관계

- SituationGenerator가 null을 반환하면 EventMatcher의 기존 6단계 매칭이 동작
- SituationGenerator가 생성한 이벤트는 EventMatcher의 반복 페널티 추적에 포함됨
- Procedural Plot Protection 불변식 유지: SituationGenerator도 arcRouteTag/commitmentDelta 생성 금지

---

## Event Director

이벤트 선택 정책 계층. SituationGenerator 실패 시 동작하는 fallback 경로.

### 선택 알고리즘

1.  Stage Filter
2.  Condition Filter
3.  Cooldown Filter
4.  Priority Sort
5.  Weighted Random

### Priority Weight

| priority | weight |
|----------|--------|
| critical | 10 |
| high | 6 |
| medium | 3 |
| low | 1 |

---

## Event Library

LOCATION별 이벤트 관리

### Event Schema

```json
{ "event_id": "inspect_door", "type": "discovery", "priority": "medium",
  "stage": ["investigation"], "cooldown": 2, "effects": { "progress": 0.05 } }
```

### Event Types

- interaction
- discovery
- conflict
- atmosphere
- story

### 권장 수량

LOCATION당 20~30 events
