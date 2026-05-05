# 08 — 노드 라우팅 아키텍처 (DAG 분기)

> 원본 참조: [[specs/node_routing_v2|node routing v2]] (41KB 전문)
> 상태: **✅ 구현됨** — DAG 기반 아키텍처(PlannedNodeV2, Edge, resolveNextNodeId) + 24노드 그래프 정의 + 3루트 조건부 분기 완료.
> 의존: `run_node_system.md`, `node_resolve_rules_v1.md`, `vertical_slice_v1.md`

---

## 1. 문제 & 목표

### AS-IS

현재 시스템은 12노드 하드코딩 선형 시퀀스.
- `RunPlannerService.planGraymarVerticalSlice()` → 고정 `PlannedNode[]`
- `NodeTransitionService` → `nextIndex = currentNodeIndex + 1`
- 모든 플레이어가 동일 경험, 분기가 내러티브에만 반영

### TO-BE

**조건부 분기 DAG(유향 비순환 그래프)** 기반 라우팅.
- 핵심 분기점(S2)에서 3개 루트로 완전 분기
- 노드에 **Edge** 배열 부여, Edge마다 **Condition** 보유
- 노드 종료 시 조건 평가 → 첫 번째 만족 조건의 `targetNodeId`로 전환
- 런당 방문 노드 수 항상 **12노드** (4 공통 + 6 루트 + 2 합류)

### 비변경 범위

전투 엔진(Combat/Damage/Hit/EnemyAI), RNG, 상태이상, `server_result_v1.json` 스키마, 멱등성 보장 — 모두 재활용, 변경 없음.

---

## 2. 그래프 구조

```
┌──── 공통 구간 (4노드) ────┐
│ common_s0 → common_s1     │
│ → common_combat_dock      │
│ → common_s2 (분기점)       │
└─────────┬─────────────────┘
          ┌───────┼───────────────┐
          ▼       ▼               ▼
   ┌─ 길드 루트 ─┐ ┌─ 경비대 루트 ─┐ ┌─ 독자 루트 ─┐
   │ 6노드       │ │ 6노드        │ │ 6노드       │
   └──────┬──────┘ └──────┬───────┘ └──────┬──────┘
          └───────────────┼────────────────┘
                          ▼
              ┌── 합류 구간 (2노드) ──┐
              │ merge_s5 → merge_exit │
              └───────────────────────┘
```

- **공통 구간** (4노드): 모든 플레이어 공유
- **루트별 고유** (6노드 × 3루트): 18노드 정의, 런당 6개만 방문
- **합류 구간** (2노드): 모든 플레이어 공유 (routeTag별 내러티브 분화)

---

## 3. 핵심 데이터 구조

### PlannedNodeV2

```typescript
interface PlannedNodeV2 {
  nodeId: string;            // 그래프 내 고유 ID ("common_s0", "guild_rest" 등)
  nodeType: NodeType;        // COMBAT | EVENT | REST | SHOP | EXIT
  nodeMeta: Record<string, unknown>;
  environmentTags: string[];
  edges: EdgeDefinition[];   // 출력 간선 목록
}
```

### EdgeDefinition

```typescript
interface EdgeDefinition {
  targetNodeId: string;      // 목표 노드 graphNodeId
  condition: EdgeCondition;
  priority: number;          // 낮을수록 먼저 평가 (1 최우선)
}
```

### EdgeCondition

| type | 의미 | 사용처 |
|------|------|--------|
| `DEFAULT` | 무조건 통과 (fallback) | 단일 경로 노드 |
| `CHOICE` | 플레이어 선택지 ID 일치 시 통과 | S2 분기점 |
| `COMBAT_OUTCOME` | 전투 결과 일치 시 통과 | 향후 확장용 |

### RouteContext

```typescript
interface RouteContext {
  lastChoiceId?: string;     // 직전 EVENT 선택 ID
  combatOutcome?: string;    // 직전 COMBAT 결과
  routeTag?: string;         // 현재 루트 (GUILD | GUARD | SOLO)
}
```

---

## 4. DB 스키마 변경 (예정)

### node_instances 추가 컬럼

- `graph_node_id TEXT` — 그래프 정의 내 노드 ID
- `edges JSONB` — EdgeDefinition[]
- `UNIQUE(run_id, graph_node_id)` 인덱스 추가
- `nodeIndex`는 "시퀀스 위치" → "방문 순서 카운터"로 의미 변경

### run_sessions 추가 컬럼

- `current_graph_node_id TEXT` — 현재 그래프 위치
- `route_tag TEXT` — 현재 루트 (GUILD / GUARD / SOLO / null)

---

## 5. 서비스 변경 방향

### RunPlannerService (재작성)

- `getGraymarGraph(): PlannedNodeV2[]` — 24노드 그래프 전체 정의 반환
- `getStartNodeId(): string` — `'common_s0'`
- `resolveNextNodeId(currentGraphNodeId, context): string | null` — 엣지 순회 → 조건 평가 → 다음 노드 결정

### NodeTransitionService (핵심 변경)

- nodeIndex 대신 `graphNodeId` 기반 전환
- 노드 lazy 생성: 전환 시점에 `node_instances` INSERT
- 분기점(common_s2)에서 routeTag 결정
- merge_s5 진입 시 `eventId = S5_RESOLVE_{routeTag}` 동적 설정

### RunsService.createRun (수정)

- 12개 일괄 INSERT → **첫 노드만 INSERT** (나머지 lazy)

### TurnsService.submitTurn (수정)

- NODE_ENDED 시 RouteContext 구성 → 전환에 전달

---

## 6. 분기점 상세: S2 (common_s2)

### S2 선택지

| choiceId | 텍스트 | 설명 |
|----------|------|------|
| `guild_ally` | "하를런과 손잡겠다" | 노동 길드 동맹, 부두 중심 |
| `guard_ally` | "경비대에 보고하겠다" | 도시 수비대 협력, 공식 수사 |
| `solo_path` | "혼자 해결하겠다" | 독자 행동, 최고 난이도/보상 |

### S2 엣지

```json
[
  { "targetNodeId": "guild_rest",     "condition": { "type": "CHOICE", "choiceId": "guild_ally" },  "priority": 1 },
  { "targetNodeId": "guard_event_s3", "condition": { "type": "CHOICE", "choiceId": "guard_ally" },  "priority": 2 },
  { "targetNodeId": "solo_event_s3",  "condition": { "type": "CHOICE", "choiceId": "solo_path" },   "priority": 3 }
]
```

DEFAULT 엣지 없음 — S2는 반드시 3개 중 택1 필수.

---

## 7. 루트별 요약

### 길드 루트 (routeTag: GUILD)

- 톤: 거칠지만 의리있는 동맹, 부두 중심 액션
- 핵심 NPC: 하를런 (노동 길드)
- 세력 변화: LABOR_GUILD ↑↑, MERCHANT_CONSORTIUM ↓
- 노드: REST → SHOP(길드 무기상) → EVENT(밀수 경로) → COMBAT(창고 급습) → EVENT(심문) → BOSS(마이렐 경)

### 경비대 루트 (routeTag: GUARD)

- 톤: 공식적, 절차적, 내부 부패 발각
- 핵심 NPC: 라이라, 벨론 대위
- 세력 변화: CITY_GUARD ↑↑, LABOR_GUILD ↓
- 노드: EVENT(공식 수사) → SHOP(경비대 보급) → COMBAT(병영) → EVENT(증거 발견) → REST(보스 대비) → BOSS(마이렐 체포)

### 독자 루트 (routeTag: SOLO)

- 톤: 고독, 잠행, 최고 위험
- 핵심 NPC: 쉐도우 (정보상)
- 세력 변화: 최소 (양쪽 중립)
- 노드: EVENT(정보 구매) → COMBAT(뒷골목 기습) → REST(은신) → SHOP(암시장 1.5×) → EVENT(잠입) → BOSS(토브렌+마이렐)

### 합류 구간

- merge_s5: routeTag별 eventId 동적 설정 → 3종 엔딩 선택지
- merge_exit: 런 종료 + 결산

---

## 8. 콘텐츠 확장 (미적용)

### 새 적 4종

| enemyId | 이름 | 루트 | 특성 |
|---------|------|------|------|
| ENEMY_HIRED_MUSCLE | 고용 무력배 | 길드 | HP 70, AGGRESSIVE |
| ENEMY_CORRUPT_GUARD_LOYAL | 마이렐 충성 부하 | 경비대 | HP 70, TACTICAL |
| ENEMY_GUILD_THUG_ELITE | 길드 정예 깡패 | 독자 | HP 80, AGGRESSIVE |
| ENEMY_TOBREN_COMBAT | 토브렌 (전투형) | 독자 보스 | HP 65, COWARDLY |

### 루트별 상점 차별화

| 루트 | shopId | 특징 | 가격 배율 |
|------|--------|------|----------|
| 길드 | SHOP_GUILD_ARMS | 전투용 (독침, 연막탄) | 1.0× |
| 경비대 | SHOP_GUARD_SUPPLY | 방어/치료 | 0.8× |
| 독자 | SHOP_BLACK_MARKET | 고가 특수 아이템 | 1.5× |

---

## 9. 호환성 & 구현 주의사항

- `nodeIndex`는 유지 (방문 순서 카운터로 의미 변경), 기존 API 호환
- `server_result_v1.json` 스키마 불변 — 클라이언트 계약 유지
- RNG 결정성 보장 — 루트가 달라도 seed+cursor 결정적
- LLM 컨텍스트: `routeTag`를 L0에 추가하여 루트별 내러티브 톤 유도
- 런 복구(GET /runs/:runId): `currentGraphNodeId`로 위치 추적

> 전체 상세(24개 노드 정의, encounter/event/NPC/item JSON, 서비스 의사코드)는 원본 [[specs/node_routing_v2|node routing v2]] 참조.
