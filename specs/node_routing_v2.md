# Node Routing v2 — 조건부 분기 DAG 설계서

> ✅ **구현됨** — DAG 24노드 그래프 + 3루트 조건부 분기 구현 완료.
> **정본**: 노드 라우팅 시스템 재설계 (선형 고정 → 조건부 분기)
> **대상**: Graymar Vertical Slice (항만 실종 사건)
> **의존 문서**: `run_node_system.md`, `node_resolve_rules_v1.md`, `vertical_slice_v1.md`, `07_database_schema.md`
> **버전**: v2.0

---

# 0. 목적

## 0.1 문제

현재 시스템은 12노드가 하드코딩된 선형 시퀀스다.

- `RunPlannerService.planGraymarVerticalSlice()` → 고정 `PlannedNode[]` 반환
- `NodeTransitionService` → `nextIndex = currentNodeIndex + 1`로만 전환
- `RunsService.createRun()` → 런 시작 시 12행 일괄 INSERT

**결과**: 모든 플레이어가 동일 경험. `vertical_slice_v1.md` §7에서 암시한 "길드/경비대/독자 조사" 분기가 내러티브에만 반영되고, 실제 경로에는 영향을 미치지 않는다.

## 0.2 목표

S2(핵심 분기점)에서의 선택에 따라 **3개 루트로 완전 분기**되는 조건부 라우팅 시스템.

- 노드 시퀀스를 **유향 비순환 그래프(DAG)** 로 재정의
- 각 노드에 **엣지(Edge)** 배열 부여, 엣지마다 **조건(Condition)** 보유
- 노드 종료 시 조건을 평가하여 다음 노드 자동 결정
- 런당 방문 노드 수는 항상 **12노드** 유지 (4 공통 + 6 루트 + 2 합류)

## 0.3 비변경 범위

이 설계는 **라우팅 구조만** 변경한다. 아래 시스템은 재활용하며 변경하지 않는다:

- CombatService, DamageService, HitService, EnemyAiService
- RestNodeService, ShopNodeService, ExitNodeService
- RngService, RuleParser, PolicyService
- `server_result_v1.json` 스키마 (클라이언트 계약 불변)
- 멱등성 보장 (`run_id, turn_no` + `idempotency_key`)
- RNG 결정성 (`seed + cursor` 체계)

---

# 1. AS-IS 구조

```
0:EVENT(S0) → 1:EVENT(S1) → 2:COMBAT(부두) → 3:EVENT(S2) →
4:REST → 5:SHOP → 6:EVENT(S3) → 7:COMBAT(창고) →
8:EVENT(S4) → 9:COMBAT(보스) → 10:EVENT(S5) → 11:EXIT
```

| 구성 요소 | 현재 방식 |
|-----------|----------|
| PlannedNode | `nodeIndex` 기반 순차 배열 |
| 노드 전환 | `currentNodeIndex + 1` |
| 노드 생성 | 런 시작 시 12행 일괄 INSERT |
| 분기 | 없음 |
| DB 제약 | `UNIQUE(run_id, node_index)` |

---

# 2. TO-BE 구조: 조건부 분기 DAG

## 2.1 핵심 아이디어

`nodeIndex` 선형 배열 대신 **노드 ID 기반 유향 비순환 그래프(DAG)**.
각 노드에 **엣지(Edge)** 배열이 있고, 엣지마다 **조건(Condition)**이 있다.
노드 종료 시 조건을 priority 순서로 평가하여 첫 번째 만족 조건의 targetNodeId로 전환한다.

## 2.2 전체 그래프 구조

```
                        ┌──── 공통 구간 (4노드) ────┐
                        │ common_s0 → common_s1     │
                        │ → common_combat_dock      │
                        │ → common_s2 (분기점)       │
                        └─────────┬─────────────────┘
                  ┌───────────────┼───────────────────┐
                  ▼               ▼                   ▼
          ┌── 길드 루트 ──┐ ┌── 경비대 루트 ──┐ ┌── 독자 루트 ──┐
          │ guild_rest    │ │ guard_event_s3 │ │ solo_event_s3 │
          │ guild_shop    │ │ guard_shop     │ │ solo_combat   │
          │ guild_event   │ │ guard_combat   │ │ solo_rest     │
          │ guild_combat  │ │ guard_event_s4 │ │ solo_shop     │
          │ guild_event_s4│ │ guard_rest     │ │ solo_event_s4 │
          │ guild_boss    │ │ guard_boss     │ │ solo_boss     │
          └───────┬───────┘ └───────┬────────┘ └───────┬───────┘
                  └─────────────────┼──────────────────┘
                                    ▼
                        ┌──── 합류 구간 (2노드) ────┐
                        │ merge_s5 → merge_exit     │
                        └───────────────────────────┘
```

- **공통 구간** (4노드): 모든 플레이어 공유
- **루트별 고유** (6노드 × 3루트): 18노드 정의, 런당 6개만 방문
- **합류 구간** (2노드): 모든 플레이어 공유 (루트별 내러티브 분화)
- **런당 총 방문**: 항상 12노드 (4 + 6 + 2)

## 2.3 데이터 구조

### PlannedNodeV2

```typescript
interface PlannedNodeV2 {
  nodeId: string;            // 그래프 내 고유 ID (e.g. "common_s0", "guild_rest")
  nodeType: NodeType;        // COMBAT | EVENT | REST | SHOP | EXIT
  nodeMeta: Record<string, unknown>;  // 기존 nodeMeta 구조 유지
  environmentTags: string[];
  edges: EdgeDefinition[];   // 이 노드에서 나가는 간선 목록
}
```

### EdgeDefinition

```typescript
interface EdgeDefinition {
  targetNodeId: string;      // 목표 노드의 graphNodeId
  condition: EdgeCondition;  // 전환 조건
  priority: number;          // 낮을수록 먼저 평가 (1이 최우선)
}
```

### EdgeCondition

```typescript
interface EdgeCondition {
  type: 'DEFAULT' | 'CHOICE' | 'COMBAT_OUTCOME';
  choiceId?: string;         // CHOICE: S2에서 플레이어가 선택한 선택지 ID
  combatOutcome?: string;    // COMBAT_OUTCOME: VICTORY | DEFEAT | FLEE_SUCCESS
}
```

**조건 타입 설명:**

| type | 의미 | 사용처 |
|------|------|--------|
| `DEFAULT` | 무조건 통과 (fallback) | 단일 경로 노드 (공통 구간, 루트 내부) |
| `CHOICE` | 플레이어 선택지 ID 일치 시 통과 | S2 분기점 (3갈래) |
| `COMBAT_OUTCOME` | 전투 결과 일치 시 통과 | 향후 확장용 (v2에서는 미사용) |

### RouteContext

노드 전환 시 조건 평가에 사용되는 컨텍스트:

```typescript
interface RouteContext {
  lastChoiceId?: string;     // 직전 EVENT 노드에서의 선택 ID
  combatOutcome?: string;    // 직전 COMBAT 노드의 결과
  routeTag?: string;         // 현재 루트 (GUILD | GUARD | SOLO | null)
}
```

---

# 3. DB 스키마 변경

## 3.1 `node_instances` 추가 컬럼

```sql
ALTER TABLE node_instances
  ADD COLUMN graph_node_id TEXT,      -- 그래프 정의 내 노드 ID
  ADD COLUMN edges         JSONB;     -- EdgeDefinition[] (출력 간선)

-- 기존 UNIQUE 유지
-- UNIQUE(run_id, node_index)

-- 새 UNIQUE 추가
CREATE UNIQUE INDEX uq_node_instances_graph
  ON node_instances(run_id, graph_node_id);
```

**`nodeIndex`의 역할 변경:**

- AS-IS: 노드 시퀀스의 고정 위치 (0=S0, 1=S1, ..., 11=EXIT)
- TO-BE: **방문 순서 카운터** (0, 1, 2, ... 순차 증가). 어떤 루트를 타든 0~11.
- `UNIQUE(run_id, node_index)` 제약 유지. 의미만 "시퀀스 위치" → "방문 순서"로 변경.

## 3.2 `run_sessions` 추가 컬럼

```sql
ALTER TABLE run_sessions
  ADD COLUMN current_graph_node_id TEXT,  -- 현재 노드의 그래프 ID
  ADD COLUMN route_tag             TEXT;  -- 현재 루트 (GUILD / GUARD / SOLO / null)
```

- `current_node_index`는 유지. 기존 API 호환.
- `current_graph_node_id`로 그래프 위치 추적.
- `route_tag`는 분기 결정 후 설정. 합류 구간에서도 유지 (내러티브 분화용).

## 3.3 `run_state` JSONB 확장

```typescript
interface RunState {
  // 기존 필드 (변경 없음)
  hp: number;
  maxHp: number;
  stamina: number;
  maxStamina: number;
  gold: number;
  inventory: InventoryItem[];

  // 추가 필드
  routeTag?: string;          // 분기 루트 (GUILD | GUARD | SOLO)
  branchChoiceId?: string;    // S2에서의 선택 ID (감사 추적용)
}
```

---

# 4. 노드 그래프 상세 정의

## 4.1 공통 구간 (4노드, 모든 플레이어)

| 방문순 | nodeId | Type | eventId / encId | 설명 | 엣지 |
|--------|--------|------|-----------------|------|------|
| 0 | `common_s0` | EVENT | `S0_ARRIVE` | 항만 도착, 의뢰 수락. `nodeMeta.isIntro: true` | → `common_s1` (DEFAULT) |
| 1 | `common_s1` | EVENT | `S1_GET_ANGLE` | 에드릭 만남, 장부 조작 단서 | → `common_combat_dock` (DEFAULT) |
| 2 | `common_combat_dock` | COMBAT | `ENC_DOCK_AMBUSH` | 부두 깡패 × 2. 기존 encounter 재사용 | → `common_s2` (DEFAULT) |
| 3 | `common_s2` | EVENT | `S2_PROVE_TAMPER` | **핵심 분기점**: 3갈래 선택지 제시 | 아래 참조 |

### common_s2 엣지 (분기점)

```json
[
  { "targetNodeId": "guild_rest",      "condition": { "type": "CHOICE", "choiceId": "guild_ally"  }, "priority": 1 },
  { "targetNodeId": "guard_event_s3",  "condition": { "type": "CHOICE", "choiceId": "guard_ally"  }, "priority": 2 },
  { "targetNodeId": "solo_event_s3",   "condition": { "type": "CHOICE", "choiceId": "solo_path"   }, "priority": 3 }
]
```

**S2 선택지 정의:**

| choiceId | 선택지 텍스트 (LLM 서술용 힌트) | 설명 |
|----------|-------------------------------|------|
| `guild_ally` | "하를런과 손잡겠다" | 노동 길드와 동맹. 부두 중심 루트 |
| `guard_ally` | "경비대에 보고하겠다" | 도시 수비대와 협력. 공식 수사 루트 |
| `solo_path` | "혼자 해결하겠다" | 독자 행동. 위험하지만 높은 보상 |

> **DEFAULT 엣지 없음**: S2는 반드시 3개 선택지 중 하나를 선택해야 한다.
> PolicyService에서 "공백 입력" 등 비선택을 DENY 처리.

## 4.2 길드 루트 (6노드)

**톤**: 거칠지만 의리있는 동맹. 부두 중심 액션. 하를런이 핵심 동맹.
**routeTag**: `GUILD`
**세력 평판 변화**: LABOR_GUILD ↑↑, MERCHANT_CONSORTIUM ↓

| 방문순 | nodeId | Type | 상세 | 엣지 |
|--------|--------|------|------|------|
| 4 | `guild_rest` | REST | 길드 은신처 휴식. 하를런이 경계. envTags: `[INDOOR, SAFE]` | → `guild_shop` (DEFAULT) |
| 5 | `guild_shop` | SHOP | 길드 비밀 무기상. 전투 소모품 풍부 (독침, 연막탄, 치료제). shopId: `SHOP_GUILD_ARMS` | → `guild_event_s3` (DEFAULT) |
| 6 | `guild_event_s3` | EVENT | S3_GUILD: 길드 정보원이 밀수 경로 폭로. 하를런과 창고 급습 계획 수립. Fact: `FACT_SMUGGLE_ROUTE_GUILD` | → `guild_combat` (DEFAULT) |
| 7 | `guild_combat` | COMBAT | ENC_WHARF_RAID: 밀수업자 × 2 + 고용 무력배 × 1. envTags: `[OPEN, COVER_CRATE, NIGHT]` | → `guild_event_s4` (DEFAULT) |
| 8 | `guild_event_s4` | EVENT | S4_GUILD: 토브렌 심문. 마이렐 경의 장부 은폐 개입 폭로. Fact: `FACT_MAIREL_GUILD_EVIDENCE` | → `guild_boss` (DEFAULT) |
| 9 | `guild_boss` | COMBAT | ENC_GUILD_BOSS: 마이렐 경(보스) + 매수된 수비대원 × 1. `nodeMeta.isBoss: true`. envTags: `[OPEN, COVER_WALL, NIGHT]` | → `merge_s5` (DEFAULT) |

## 4.3 경비대 루트 (6노드)

**톤**: 공식적, 절차적. 내부 부패 발각. 라이라가 핵심 협력자.
**routeTag**: `GUARD`
**세력 평판 변화**: CITY_GUARD ↑↑, LABOR_GUILD ↓

| 방문순 | nodeId | Type | 상세 | 엣지 |
|--------|--------|------|------|------|
| 4 | `guard_event_s3` | EVENT | S3_GUARD: 수사권으로 공식 조사. 라이라가 문서실 접근 지원. Fact: `FACT_OFFICIAL_INQUIRY` | → `guard_shop` (DEFAULT) |
| 5 | `guard_shop` | SHOP | 경비대 보급소. 방어구/치료제 중심. shopId: `SHOP_GUARD_SUPPLY` | → `guard_combat` (DEFAULT) |
| 6 | `guard_combat` | COMBAT | ENC_BARRACKS: 매수된 수비대원 × 1 + 항만 경비병 × 1. envTags: `[INDOOR, NARROW]` | → `guard_event_s4` (DEFAULT) |
| 7 | `guard_event_s4` | EVENT | S4_GUARD: 결정적 증거 발견. 벨론 대위 접촉, 내부 진압 지원 약속. Fact: `FACT_MAIREL_GUARD_EVIDENCE` | → `guard_rest` (DEFAULT) |
| 8 | `guard_rest` | REST | 경비대 숙소 안전 휴식 (보스전 대비). envTags: `[INDOOR, SAFE]` | → `guard_boss` (DEFAULT) |
| 9 | `guard_boss` | COMBAT | ENC_GUARD_BOSS: 마이렐 경(보스, 체포 저항) + 충성 부하 × 1. `nodeMeta.isBoss: true`. envTags: `[OPEN, COVER_WALL, AFTERNOON]` | → `merge_s5` (DEFAULT) |

## 4.4 독자 루트 (6노드)

**톤**: 고독, 위험, 잠행. 누구도 믿지 않는다. 최고 난이도, 최고 보상.
**routeTag**: `SOLO`
**세력 평판 변화**: 최소 변화 (양쪽 모두 중립 유지)

| 방문순 | nodeId | Type | 상세 | 엣지 |
|--------|--------|------|------|------|
| 4 | `solo_event_s3` | EVENT | S3_SOLO: 뒷골목 정보상(쉐도우)에게 정보 구매. 골드 25~40 소모. Fact: `FACT_SHADOW_INTEL` | → `solo_combat` (DEFAULT) |
| 5 | `solo_combat` | COMBAT | ENC_ALLEY: 길드 정예 깡패 × 1 + 매수된 수비대원 × 1. 양쪽 세력에서 온 적. envTags: `[NARROW, COVER_WALL, NIGHT]` | → `solo_rest` (DEFAULT) |
| 6 | `solo_rest` | REST | 폐건물에서 은신 휴식. envTags: `[INDOOR]` | → `solo_shop` (DEFAULT) |
| 7 | `solo_shop` | SHOP | 암시장. 독침/연막탄/상급 치료제 등 특수 아이템. 가격 1.5배. shopId: `SHOP_BLACK_MARKET` | → `solo_event_s4` (DEFAULT) |
| 8 | `solo_event_s4` | EVENT | S4_SOLO: 단독 창고 잠입. 양쪽 비밀문서 탈취. Fact: `FACT_BOTH_SIDES_EVIDENCE` | → `solo_boss` (DEFAULT) |
| 9 | `solo_boss` | COMBAT | ENC_SOLO_BOSS: 토브렌(전투형) + 마이렐 경(보스). `nodeMeta.isBoss: true`. 최고 난이도. envTags: `[INDOOR, NARROW, NIGHT]` | → `merge_s5` (DEFAULT) |

## 4.5 합류 구간 (2노드)

| 방문순 | nodeId | Type | 상세 | 엣지 |
|--------|--------|------|------|------|
| 10 | `merge_s5` | EVENT | S5 엔딩 이벤트. 루트별 내러티브/선택지 분화 (§4.6 참조) | → `merge_exit` (DEFAULT) |
| 11 | `merge_exit` | EXIT | 런 종료. 결산 처리 | (없음) |

## 4.6 merge_s5 내러티브 분화

`merge_s5`는 모든 루트에서 공유하는 단일 노드이나, `routeTag`에 따라 **eventId를 동적 설정**하여 다른 내러티브와 선택지를 제공한다.

```typescript
// NodeTransitionService에서 merge_s5 진입 시
const eventId = `S5_RESOLVE_${routeTag}`;  // S5_RESOLVE_GUILD | S5_RESOLVE_GUARD | S5_RESOLVE_SOLO
nodeMeta.eventId = eventId;
```

| routeTag | eventId | 엔딩 선택지 (3종) |
|----------|---------|-----------------|
| `GUILD` | `S5_RESOLVE_GUILD` | 1) 진실 폭로 / 2) 길드와 타협 / 3) 은폐하고 빚 |
| `GUARD` | `S5_RESOLVE_GUARD` | 1) 공식 보고 / 2) 상부 타협 / 3) 증거 파기 |
| `SOLO` | `S5_RESOLVE_SOLO` | 1) 양쪽에 공개 / 2) 증거 매각 / 3) 침묵 |

> 엔딩 선택지는 **서사 분기**이며 런 종료 후 `hub_states` 업데이트에 반영.
> 이 선택은 노드 라우팅에는 영향 없음 (merge_s5 → merge_exit는 DEFAULT).

---

# 5. 콘텐츠 확장 목록

## 5.1 새 적 (`enemies.json` 추가)

기존 적 형식(`enemyId`, `name`, `description`, `faction`, `hp`, `stats`, `personality`, `defaultDistance`, `defaultAngle`, `statusImmunities`, `loot`)을 따른다.

| enemyId | 이름 | 루트 | HP | ATK | DEF | ACC | EVA | CRIT | SPEED | 성격 | 설명 |
|---------|------|------|----|-----|-----|-----|-----|------|-------|------|------|
| `ENEMY_HIRED_MUSCLE` | 고용 무력배 | 길드 | 70 | 13 | 8 | 4 | 2 | 4% | 4 | AGGRESSIVE | 길드가 밀수 경호에 고용한 거구. 주먹과 곤봉 사용 |
| `ENEMY_CORRUPT_GUARD_LOYAL` | 마이렐 충성 부하 | 경비대 | 70 | 12 | 12 | 5 | 3 | 4% | 5 | TACTICAL | 마이렐에게 충성하는 수비대 정예. 방패술 숙련 |
| `ENEMY_GUILD_THUG_ELITE` | 길드 정예 깡패 | 독자 | 80 | 16 | 7 | 5 | 4 | 7% | 5 | AGGRESSIVE | 항만 길드의 숙련된 전투원. 단검과 주먹 병용 |
| `ENEMY_TOBREN_COMBAT` | 토브렌 하위크 (전투형) | 독자 보스 | 65 | 11 | 6 | 4 | 5 | 3% | 6 | COWARDLY | 궁지에 몰린 토브렌. 단검 난동, FLEE 경향 높음 |

**밸런스 기준:**
- 기존 적 범위: HP 45~90, ATK 10~16 (ACT 1 기준, `combat_system.md` Part 0 참조)
- 독자 보스전 토브렌 + 마이렐 연합은 최고 난이도 → 합산 HP 175, 독자 루트만의 도전

## 5.2 새 전투 (`encounters.json` 추가)

기존 encounter 형식(`encounterId`, `name`, `description`, `questState`, `nodeType`, `nodeMeta`, `enemies`, `initialPositioning`, `envTags`, `toneHint`, `timePhase`, `rewards`)을 따른다.

### ENC_WHARF_RAID (길드 루트)

```json
{
  "encounterId": "ENC_WHARF_RAID",
  "name": "부두 창고 급습",
  "description": "하를런과 함께 밀수 경로를 급습한다. 밀수업자와 고용 무력배가 대기 중.",
  "questState": "S3_GUILD",
  "nodeType": "COMBAT",
  "nodeMeta": { "isBoss": false },
  "enemies": [
    { "ref": "ENEMY_SMUGGLER", "count": 2 },
    { "ref": "ENEMY_HIRED_MUSCLE", "count": 1 }
  ],
  "initialPositioning": [
    { "enemyRef": "ENEMY_SMUGGLER", "instance": 0, "distance": "FAR", "angle": "FRONT" },
    { "enemyRef": "ENEMY_SMUGGLER", "instance": 1, "distance": "MID", "angle": "SIDE" },
    { "enemyRef": "ENEMY_HIRED_MUSCLE", "instance": 0, "distance": "CLOSE", "angle": "FRONT" }
  ],
  "envTags": ["OPEN", "COVER_CRATE"],
  "toneHint": "tense",
  "timePhase": "NIGHT",
  "rewards": { "gold": "20-45", "xp": 0 }
}
```

### ENC_GUILD_BOSS (길드 루트 보스)

```json
{
  "encounterId": "ENC_GUILD_BOSS",
  "name": "마이렐 경 대치 (길드)",
  "description": "증거를 들이밀자 마이렐 경이 무력으로 저항한다.",
  "questState": "S4_GUILD",
  "nodeType": "COMBAT",
  "nodeMeta": { "isBoss": true },
  "enemies": [
    { "ref": "ENEMY_CORRUPT_GUARD", "count": 1, "overrides": {
      "name": "마이렐 단 경 (야간 책임자)", "hp": 110,
      "stats": { "ATK": 18, "DEF": 16, "ACC": 7, "EVA": 4, "CRIT": 6, "CRIT_DMG": 1.6, "RESIST": 10, "SPEED": 5 },
      "personality": "TACTICAL"
    }},
    { "ref": "ENEMY_CORRUPT_GUARD", "count": 1 }
  ],
  "initialPositioning": [
    { "enemyRef": "ENEMY_CORRUPT_GUARD", "instance": 0, "distance": "CLOSE", "angle": "FRONT" },
    { "enemyRef": "ENEMY_CORRUPT_GUARD", "instance": 1, "distance": "MID", "angle": "SIDE" }
  ],
  "envTags": ["OPEN", "COVER_WALL"],
  "toneHint": "climax",
  "timePhase": "NIGHT",
  "rewards": { "gold": "30-60", "xp": 0, "clueChance": { "itemId": "CLUE_SMEARED_INK_LOG", "probability": 1.0 } }
}
```

### ENC_BARRACKS (경비대 루트)

```json
{
  "encounterId": "ENC_BARRACKS",
  "name": "병영 내부 전투",
  "description": "마이렐의 매수된 수비대원들이 증거 인멸을 위해 공격한다.",
  "questState": "S3_GUARD",
  "nodeType": "COMBAT",
  "nodeMeta": { "isBoss": false },
  "enemies": [
    { "ref": "ENEMY_CORRUPT_GUARD", "count": 1 },
    { "ref": "ENEMY_HARBOR_WATCHMAN", "count": 1 }
  ],
  "initialPositioning": [
    { "enemyRef": "ENEMY_CORRUPT_GUARD", "instance": 0, "distance": "CLOSE", "angle": "FRONT" },
    { "enemyRef": "ENEMY_HARBOR_WATCHMAN", "instance": 0, "distance": "MID", "angle": "SIDE" }
  ],
  "envTags": ["INDOOR", "NARROW"],
  "toneHint": "tense",
  "timePhase": "AFTERNOON",
  "rewards": { "gold": "15-35", "xp": 0 }
}
```

### ENC_GUARD_BOSS (경비대 루트 보스)

```json
{
  "encounterId": "ENC_GUARD_BOSS",
  "name": "마이렐 경 체포 저항",
  "description": "체포 영장을 집행하자 마이렐 경이 충성 부하와 함께 저항한다.",
  "questState": "S4_GUARD",
  "nodeType": "COMBAT",
  "nodeMeta": { "isBoss": true },
  "enemies": [
    { "ref": "ENEMY_CORRUPT_GUARD", "count": 1, "overrides": {
      "name": "마이렐 단 경 (야간 책임자)", "hp": 110,
      "stats": { "ATK": 18, "DEF": 16, "ACC": 7, "EVA": 4, "CRIT": 6, "CRIT_DMG": 1.6, "RESIST": 10, "SPEED": 5 },
      "personality": "TACTICAL"
    }},
    { "ref": "ENEMY_CORRUPT_GUARD_LOYAL", "count": 1 }
  ],
  "initialPositioning": [
    { "enemyRef": "ENEMY_CORRUPT_GUARD", "instance": 0, "distance": "CLOSE", "angle": "FRONT" },
    { "enemyRef": "ENEMY_CORRUPT_GUARD_LOYAL", "instance": 0, "distance": "MID", "angle": "SIDE" }
  ],
  "envTags": ["OPEN", "COVER_WALL"],
  "toneHint": "climax",
  "timePhase": "AFTERNOON",
  "rewards": { "gold": "30-60", "xp": 0, "clueChance": { "itemId": "CLUE_SMEARED_INK_LOG", "probability": 1.0 } }
}
```

### ENC_ALLEY (독자 루트)

```json
{
  "encounterId": "ENC_ALLEY",
  "name": "뒷골목 기습",
  "description": "양쪽 세력 모두에게 추적당한다. 길드 정예와 매수된 수비대원이 협공.",
  "questState": "S3_SOLO",
  "nodeType": "COMBAT",
  "nodeMeta": { "isBoss": false },
  "enemies": [
    { "ref": "ENEMY_GUILD_THUG_ELITE", "count": 1 },
    { "ref": "ENEMY_CORRUPT_GUARD", "count": 1 }
  ],
  "initialPositioning": [
    { "enemyRef": "ENEMY_GUILD_THUG_ELITE", "instance": 0, "distance": "CLOSE", "angle": "FRONT" },
    { "enemyRef": "ENEMY_CORRUPT_GUARD", "instance": 0, "distance": "MID", "angle": "SIDE" }
  ],
  "envTags": ["NARROW", "COVER_WALL"],
  "toneHint": "tense",
  "timePhase": "NIGHT",
  "rewards": { "gold": "25-50", "xp": 0 }
}
```

### ENC_SOLO_BOSS (독자 루트 보스)

```json
{
  "encounterId": "ENC_SOLO_BOSS",
  "name": "토브렌-마이렐 연합 대치",
  "description": "증거를 양쪽에 모두 쥐고 있으므로, 양쪽 모두 적이 된다. 최고 난이도.",
  "questState": "S4_SOLO",
  "nodeType": "COMBAT",
  "nodeMeta": { "isBoss": true },
  "enemies": [
    { "ref": "ENEMY_TOBREN_COMBAT", "count": 1 },
    { "ref": "ENEMY_CORRUPT_GUARD", "count": 1, "overrides": {
      "name": "마이렐 단 경 (야간 책임자)", "hp": 110,
      "stats": { "ATK": 18, "DEF": 16, "ACC": 7, "EVA": 4, "CRIT": 6, "CRIT_DMG": 1.6, "RESIST": 10, "SPEED": 5 },
      "personality": "TACTICAL"
    }}
  ],
  "initialPositioning": [
    { "enemyRef": "ENEMY_TOBREN_COMBAT", "instance": 0, "distance": "MID", "angle": "SIDE" },
    { "enemyRef": "ENEMY_CORRUPT_GUARD", "instance": 0, "distance": "CLOSE", "angle": "FRONT" }
  ],
  "envTags": ["INDOOR", "NARROW"],
  "toneHint": "climax",
  "timePhase": "NIGHT",
  "rewards": { "gold": "40-80", "xp": 0, "clueChance": { "itemId": "CLUE_SMEARED_INK_LOG", "probability": 1.0 } }
}
```

## 5.3 새 이벤트 (EventContentProvider 추가)

| eventId | 루트 | 내러티브 요약 | questState |
|---------|------|-------------|------------|
| `S3_GUILD` | 길드 | 하를런과 밀수 경로 추적, 창고 급습 계획 | `S3_TRACE_ROUTE` |
| `S4_GUILD` | 길드 | 토브렌 심문, 마이렐 경의 개입 발각 | `S4_CONFRONT` |
| `S3_GUARD` | 경비대 | 라이라와 문서실 조사, 공식 수사 | `S3_TRACE_ROUTE` |
| `S4_GUARD` | 경비대 | 결정적 증거 발견, 벨론 대위 접촉 | `S4_CONFRONT` |
| `S3_SOLO` | 독자 | 뒷골목 정보상 거래, 잠행 루트 확보 | `S3_TRACE_ROUTE` |
| `S4_SOLO` | 독자 | 단독 창고 잠입, 양쪽 비밀문서 탈취 | `S4_CONFRONT` |
| `S5_RESOLVE_GUILD` | 합류 | 길드 루트 엔딩 3종 (§4.6) | `S5_RESOLVE` |
| `S5_RESOLVE_GUARD` | 합류 | 경비대 루트 엔딩 3종 (§4.6) | `S5_RESOLVE` |
| `S5_RESOLVE_SOLO` | 합류 | 독자 루트 엔딩 3종 (§4.6) | `S5_RESOLVE` |

> 기존 `S3_TRACE_ROUTE`, `S4_CONFRONT`, `S5_RESOLVE`는 루트별 분화 eventId로 대체된다.

## 5.4 새 NPC (`npcs.json` 추가)

기존 NPC 형식(`npcId`, `name`, `role`, `faction`, `hostile`, `combatProfile`, `title`, `aliases`, `nameStyle`)을 따른다.

```json
[
  {
    "npcId": "NPC_INFO_BROKER",
    "name": "쉐도우",
    "role": "뒷골목 정보 브로커. 양쪽 세력 모두에게 정보를 판다.",
    "faction": null,
    "hostile": false,
    "combatProfile": null,
    "title": null,
    "aliases": ["쉐도우", "정보상"],
    "nameStyle": "WESTERN_MEDIEVAL_KR"
  },
  {
    "npcId": "NPC_GUARD_CAPTAIN",
    "name": "벨론 대위",
    "role": "그레이마르 수비대 대위. 마이렐의 상관으로 내부 부패 진압 의지가 있다.",
    "faction": "CITY_GUARD",
    "hostile": false,
    "combatProfile": null,
    "title": "대위",
    "aliases": ["벨론", "대위"],
    "nameStyle": "WESTERN_MEDIEVAL_KR"
  }
]
```

## 5.5 루트별 상점 차별화

| 루트 | shopId | 상점 특징 | 가격 배율 | 전용 아이템 |
|------|--------|----------|----------|------------|
| 길드 | `SHOP_GUILD_ARMS` | 전투용 (독침, 연막탄, 치료제) | 1.0× | `ITEM_GUILD_BADGE` (길드 인장) |
| 경비대 | `SHOP_GUARD_SUPPLY` | 방어/치료 (체력 강장제, 치료제) | 0.8× | `ITEM_GUARD_PERMIT` (경비대 허가증) |
| 독자 | `SHOP_BLACK_MARKET` | 고가 특수 (독침, 연막탄, 상급 치료제) | 1.5× | `ITEM_SMUGGLE_MAP` (밀수 지도) |

### 전용 아이템 정의 (`items.json` 추가)

```json
[
  {
    "itemId": "ITEM_GUILD_BADGE",
    "type": "KEY_ITEM",
    "name": "노동 길드 인장",
    "description": "하를런이 신뢰의 증표로 건넨 인장. 길드원들이 경계를 풀어준다.",
    "buyPrice": 0,
    "maxStack": 1
  },
  {
    "itemId": "ITEM_GUARD_PERMIT",
    "type": "KEY_ITEM",
    "name": "경비대 임시 허가증",
    "description": "벨론 대위가 발급한 임시 수사 허가증. 관할 시설 출입 가능.",
    "buyPrice": 0,
    "maxStack": 1
  },
  {
    "itemId": "ITEM_SMUGGLE_MAP",
    "type": "KEY_ITEM",
    "name": "밀수 경로 지도",
    "description": "쉐도우에게서 구입한 비밀 항로 지도. 밀수 네트워크의 전체 윤곽이 담겨있다.",
    "buyPrice": 35,
    "maxStack": 1
  },
  {
    "itemId": "ITEM_SUPERIOR_HEALING",
    "type": "CONSUMABLE",
    "name": "상급 치료제",
    "description": "암시장에서 거래되는 고급 약재. 회복량이 크지만 비싸다.",
    "combat": {
      "actionType": "USE_ITEM",
      "effect": "HEAL_HP",
      "value": 50,
      "targetSelf": true
    },
    "buyPrice": 45,
    "maxStack": 2
  }
]
```

## 5.6 새 Fact 키 (`quest.json` 확장)

```json
{
  "questId": "MAIN_Q1_LEDGER",
  "states": [
    "S0_ARRIVE", "S1_GET_ANGLE", "S2_PROVE_TAMPER",
    "S3_TRACE_ROUTE", "S4_CONFRONT", "S5_RESOLVE"
  ],
  "facts": [
    "FACT_LEDGER_EXISTS",
    "FACT_WAGE_FRAUD_PATTERN",
    "FACT_TAMPERED_LOGS",
    "FACT_ROUTE_TO_EAST_DOCK",
    "FACT_INSIDE_JOB",
    "FACT_SMUGGLE_ROUTE_GUILD",
    "FACT_MAIREL_GUILD_EVIDENCE",
    "FACT_OFFICIAL_INQUIRY",
    "FACT_MAIREL_GUARD_EVIDENCE",
    "FACT_SHADOW_INTEL",
    "FACT_BOTH_SIDES_EVIDENCE"
  ]
}
```

---

# 6. 서비스 변경 방향

## 6.1 RunPlannerService (재작성)

### AS-IS

```typescript
planGraymarVerticalSlice(): PlannedNode[] {
  return [/* 12개 하드코딩 PlannedNode */];
}
```

### TO-BE

```typescript
class RunPlannerService {
  /**
   * Graymar 그래프 정의 전체를 반환한다.
   * 24개 노드 (4 공통 + 18 루트별 + 2 합류) 정의.
   * 런당 12개만 방문.
   */
  getGraymarGraph(): PlannedNodeV2[] { ... }

  /**
   * 그래프에서 시작 노드 ID를 반환한다.
   */
  getStartNodeId(): string { return 'common_s0'; }

  /**
   * 현재 노드의 엣지를 순회하여 다음 노드 ID를 결정한다.
   * @param currentGraphNodeId 현재 노드의 graphNodeId
   * @param context 전환 컨텍스트 (choiceId, combatOutcome, routeTag)
   * @returns 다음 노드의 graphNodeId, 또는 null (EXIT)
   */
  resolveNextNodeId(
    currentGraphNodeId: string,
    context: RouteContext
  ): string | null {
    const node = this.findNode(currentGraphNodeId);
    if (!node || node.edges.length === 0) return null;

    // priority 순으로 정렬하여 순회
    const sortedEdges = [...node.edges].sort((a, b) => a.priority - b.priority);

    for (const edge of sortedEdges) {
      if (this.evaluateCondition(edge.condition, context)) {
        return edge.targetNodeId;
      }
    }

    // 만족하는 조건 없음 — 에러 (S2에서 choiceId 누락 등)
    throw new Error(`No matching edge for node ${currentGraphNodeId}`);
  }

  private evaluateCondition(condition: EdgeCondition, context: RouteContext): boolean {
    switch (condition.type) {
      case 'DEFAULT': return true;
      case 'CHOICE':  return context.lastChoiceId === condition.choiceId;
      case 'COMBAT_OUTCOME': return context.combatOutcome === condition.combatOutcome;
    }
  }
}
```

## 6.2 NodeTransitionService (핵심 변경)

### AS-IS

```typescript
async advanceToNextNode(runId, currentNodeIndex) {
  const nextIndex = currentNodeIndex + 1;
  const nextNode = await this.findByIndex(runId, nextIndex);
  // ...
}
```

### TO-BE

```typescript
async advanceToNextNode(
  runId: string,
  currentGraphNodeId: string,
  context: RouteContext,
  tx: Transaction
): Promise<NodeTransitionResult | null> {

  // 1. 다음 노드 ID 결정
  const nextGraphNodeId = this.planner.resolveNextNodeId(currentGraphNodeId, context);
  if (!nextGraphNodeId) return null;  // EXIT 이후 (런 종료)

  // 2. 그래프에서 노드 정의 조회
  const nodeDef = this.planner.findNode(nextGraphNodeId);

  // 3. 현재 방문 카운트 조회 (nodeIndex로 사용)
  const visitedCount = await this.countVisitedNodes(runId, tx);

  // 4. routeTag 결정 (분기점에서만 설정)
  let routeTag = context.routeTag;
  if (currentGraphNodeId === 'common_s2') {
    routeTag = this.resolveRouteTag(context.lastChoiceId);
    // guild_ally → GUILD, guard_ally → GUARD, solo_path → SOLO
  }

  // 5. node_instances에 INSERT (lazy 생성)
  await tx.insert(nodeInstances).values({
    runId,
    nodeIndex: visitedCount,        // 방문 순서 카운터
    graphNodeId: nextGraphNodeId,   // 그래프 내 ID
    nodeType: nodeDef.nodeType,
    nodeMeta: this.resolveNodeMeta(nodeDef, routeTag),
    environmentTags: nodeDef.environmentTags,
    edges: nodeDef.edges,
    status: 'NODE_ACTIVE',
  });

  // 6. run_sessions 업데이트
  await tx.update(runSessions)
    .set({
      currentNodeIndex: visitedCount,
      currentGraphNodeId: nextGraphNodeId,
      routeTag: routeTag,
    })
    .where(eq(runSessions.id, runId));

  // 7. COMBAT 노드면 BattleState 초기화
  // (기존 로직 재활용)

  return { nextNodeIndex: visitedCount, nextNodeType: nodeDef.nodeType, ... };
}
```

## 6.3 RunsService.createRun (수정)

### AS-IS

```typescript
// 12개 노드 일괄 INSERT
const plan = this.planner.planGraymarVerticalSlice();
for (const node of plan) {
  await tx.insert(nodeInstances).values({ ... });
}
```

### TO-BE

```typescript
// 첫 노드만 INSERT (나머지는 lazy 생성)
const startNodeId = this.planner.getStartNodeId();
const startNode = this.planner.findNode(startNodeId);

await tx.insert(nodeInstances).values({
  runId: run.id,
  nodeIndex: 0,
  graphNodeId: startNodeId,
  nodeType: startNode.nodeType,
  nodeMeta: startNode.nodeMeta,
  environmentTags: startNode.environmentTags,
  edges: startNode.edges,
  status: 'NODE_ACTIVE',
});

await tx.update(runSessions).set({
  currentNodeIndex: 0,
  currentGraphNodeId: startNodeId,
  routeTag: null,
});
```

## 6.4 TurnsService.submitTurn (수정)

NODE_ENDED 반환 시 RouteContext를 구성하여 전환에 전달:

```typescript
if (outcome === 'NODE_ENDED') {
  const context: RouteContext = {
    lastChoiceId: turnResult.selectedChoiceId,   // EVENT 선택지 ID
    combatOutcome: turnResult.combatOutcome,     // VICTORY 등
    routeTag: run.routeTag,                      // 현재 루트
  };

  const transition = await this.nodeTransition.advanceToNextNode(
    runId,
    run.currentGraphNodeId,   // nodeIndex 대신 graphNodeId 사용
    context,
    tx
  );
}
```

## 6.5 변경 불필요 (재활용) 목록

| 서비스 | 이유 |
|--------|------|
| CombatService | encounter 데이터만 다름, 전투 로직 동일 |
| DamageService | 스탯 파이프라인 불변 |
| HitService | hitRoll/critRoll 로직 불변 |
| EnemyAiService | personality 기반, 기존 AI 패턴 재활용 |
| RestNodeService | REST 노드 처리 불변 |
| ShopNodeService | shopId로 아이템 목록 조회, 기존 로직 |
| ExitNodeService | EXIT 노드 처리 불변 |
| RngService | seed + cursor 체계 불변 |
| RuleParser | 의도 파싱 불변 |
| PolicyService | 정책 검증 불변 (S2 선택 강제만 추가) |
| LLM Worker | 비동기 서술 생성 불변 |

---

# 7. 노드 전환 흐름 상세

## 7.1 전환 흐름 (변경 후)

```
NODE_ENDED 발생
  ↓
RouteContext 구성 { lastChoiceId, combatOutcome, routeTag }
  ↓
RunPlannerService.resolveNextNodeId(currentGraphNodeId, context)
  ├─ 현재 노드의 edges 순회 (priority 순)
  ├─ 조건 평가:
  │    CHOICE  → context.lastChoiceId === edge.condition.choiceId ?
  │    DEFAULT → 항상 true
  └─ 첫 번째 만족 조건의 targetNodeId 반환
  ↓
NodeTransitionService.advanceToNextNode()
  ├─ 그래프에서 다음 노드 정의 조회
  ├─ node_instances에 INSERT (visitedCount를 nodeIndex로)
  ├─ run_sessions 업데이트 (currentGraphNodeId, routeTag)
  ├─ merge_s5 진입 시 → eventId를 S5_RESOLVE_{routeTag}로 동적 설정
  └─ COMBAT 노드면 BattleState 초기화, enterResult 생성
```

## 7.2 런 생성 흐름 (변경 후)

```
POST /v1/runs
  ↓
RunPlannerService.getStartNodeId() → "common_s0"
  ↓
node_instances에 첫 노드만 INSERT (nodeIndex=0, graphNodeId="common_s0")
  ↓
이후 노드는 전환 시 lazy 생성 (§6.2)
```

## 7.3 분기 결정 흐름 (S2)

```
S2 EVENT 노드 진행 중
  ↓
플레이어 입력: "하를런과 손잡겠다"
  ↓
RuleParser: choiceId = "guild_ally" 추출
  ↓
PolicyService: CHOICE 필수 검증 (비선택 → DENY)
  ↓
서버 처리: NODE_ENDED + selectedChoiceId = "guild_ally"
  ↓
RouteContext = { lastChoiceId: "guild_ally", routeTag: null }
  ↓
resolveNextNodeId("common_s2", context)
  ├─ edge[0]: CHOICE, choiceId="guild_ally", priority=1 → ✅ 매칭
  └─ return "guild_rest"
  ↓
routeTag = "GUILD" 설정 (분기점에서만)
  ↓
node_instances INSERT (nodeIndex=4, graphNodeId="guild_rest", type=REST)
```

---

# 8. 호환성 보장

## 8.1 nodeIndex

- **역할 변경**: "시퀀스 위치" → "방문 순서 카운터"
- 어떤 루트를 타든 0, 1, 2, ..., 11 순차 증가
- `UNIQUE(run_id, node_index)` 제약 유지
- 기존 API에서 `current_node_index`를 사용하는 부분 — 호환 유지 (값의 의미만 변경)

## 8.2 ServerResultV1

- **변경 없음**. 분기 정보(`routeTag`, `graphNodeId`)는 서버 내부에서만 사용
- 클라이언트에는 기존대로 `nodeIndex`, `nodeType`, `events[]` 전달
- `nextNodeHint`에 다음 노드 타입 제공 (기존과 동일)

## 8.3 멱등성

- `(run_id, turn_no)` + `(run_id, idempotency_key)` 제약 유지
- 분기 결정도 트랜잭션 내에서 원자적으로 처리
- 동일 idempotency_key 재요청 시 → 기존 결과 반환 (분기 결정 포함)

## 8.4 RNG 결정성

- 분기는 `choiceId` 기반 (플레이어 명시적 선택)이므로 RNG 소비에 영향 없음
- `seed + cursor` 체계 불변
- RNG 소비 순서: hitRoll → varianceRoll → critRoll (기존과 동일)

## 8.5 LLM 컨텍스트

- `llm_ctx_v1`에 `routeTag` 추가 전달 가능 (LLM이 루트별 톤 조절)
- L0 theme memory에 루트 정보 기록 (절대 삭제되지 않음)
- 기존 Fact Extraction 체계 유지, 새 Fact 키만 추가

---

# 9. 루트별 체험 비교

| 항목 | 길드 루트 | 경비대 루트 | 독자 루트 |
|------|----------|-----------|----------|
| **톤** | 거칠고 의리있는 | 공식적, 절차적 | 고독, 위험, 잠행 |
| **핵심 NPC** | 하를런 (NPC_YOON_HAMIN) | 라이라 (NPC_MOON_SEA) + 벨론 대위 (NPC_GUARD_CAPTAIN) | 쉐도우 (NPC_INFO_BROKER) |
| **보스** | 마이렐 경 + 수비대원 (HP 200) | 마이렐 경 + 충성 부하 (HP 180) | 토브렌 + 마이렐 연합 (HP 175) |
| **난이도** | 중간 (3적 일반전 + 2적 보스전) | 낮음~중간 (2적 일반전 + 2적 보스전) | 높음 (2적 고스탯 일반전 + 2적 보스전) |
| **보상** | 보통 골드, 길드 인장 | 저렴한 보급소, 허가증 | 높은 골드, 밀수 지도, 고가 상점 |
| **전투 횟수** | 2 (+ 공통 1 = 총 3) | 2 (+ 공통 1 = 총 3) | 2 (+ 공통 1 = 총 3) |
| **세력 평판** | LABOR_GUILD ↑↑, MERCHANT_CONSORTIUM ↓ | CITY_GUARD ↑↑, LABOR_GUILD ↓ | 변화 최소 |
| **노드 순서** | REST→SHOP→EVENT→COMBAT→EVENT→BOSS | EVENT→SHOP→COMBAT→EVENT→REST→BOSS | EVENT→COMBAT→REST→SHOP→EVENT→BOSS |

---

# 10. 확장 고려사항

## 10.1 향후 분기점 추가

이 DAG 구조는 S2 이외에도 추가 분기점을 쉽게 지원한다:

- 루트 내부에서 소규모 분기 (예: 전투 패배 시 대체 경로)
- `COMBAT_OUTCOME` 조건 활용 (DEFEAT → 구출 이벤트, FLEE_SUCCESS → 도주 이벤트)
- 새 `EdgeCondition.type` 추가 가능 (예: `FLAG`, `STAT_CHECK`)

## 10.2 다른 시나리오 적용

Graymar 이외 시나리오도 동일 DAG 구조로 정의:

```typescript
// 시나리오별 그래프 정의
getGraph(scenarioId: string): PlannedNodeV2[] {
  switch (scenarioId) {
    case 'GRAYMAR_HARBOR': return this.getGraymarGraph();
    case 'CAPITAL_INTRIGUE': return this.getCapitalGraph();
    // ...
  }
}
```

## 10.3 제약: 순환 금지

DAG이므로 순환(cycle)은 허용하지 않는다. 구현 시 그래프 정의에 대해 위상 정렬(topological sort) 검증을 런 생성 시점에 1회 수행한다.

---

# 11. 검증 방법

설계 완료 후 구현 시 다음을 검증:

1. **3개 루트 각각 12노드 완주**
   - curl로 S2에서 `guild_ally` / `guard_ally` / `solo_path` 각각 선택 후 끝까지 진행
   - 모든 루트에서 방문 노드 수 = 12 확인

2. **분기 정확성**
   - S2 선택 → 올바른 루트 첫 노드로 전환 확인
   - `run_sessions.route_tag` 정확히 설정 확인
   - 미선택 루트 노드가 `node_instances`에 존재하지 않음 확인

3. **합류 정확성**
   - 3개 루트 모두 `merge_s5` → `merge_exit` 합류 확인
   - `merge_s5`에서 `routeTag`별 다른 `eventId` 적용 확인

4. **엔딩 분화**
   - `S5_RESOLVE_GUILD` / `S5_RESOLVE_GUARD` / `S5_RESOLVE_SOLO` 각각 다른 선택지 표시 확인

5. **멱등성**
   - 동일 `idempotency_key` 재요청 시 동일 분기 결과 반환 확인
   - 분기 결정이 트랜잭션 내 원자적으로 처리되는지 확인

6. **DB 정합성**
   - 방문 노드만 `node_instances`에 존재 (미방문 루트 노드 없음)
   - `UNIQUE(run_id, graph_node_id)` 제약 위반 없음
   - `nodeIndex` 0~11 순차 유지

7. **기존 호환**
   - `ServerResultV1` 스키마 변경 없음 확인
   - `GET /v1/runs/{runId}` 응답에 `nodeIndex` 정상 포함 확인
   - RNG `seed + cursor` 결정성 유지 확인

---

# 부록 A. 전체 그래프 엣지 맵

| # | 출발 노드 | 조건 | 도착 노드 | priority |
|---|-----------|------|-----------|----------|
| 1 | `common_s0` | DEFAULT | `common_s1` | 1 |
| 2 | `common_s1` | DEFAULT | `common_combat_dock` | 1 |
| 3 | `common_combat_dock` | DEFAULT | `common_s2` | 1 |
| 4 | `common_s2` | CHOICE: guild_ally | `guild_rest` | 1 |
| 5 | `common_s2` | CHOICE: guard_ally | `guard_event_s3` | 2 |
| 6 | `common_s2` | CHOICE: solo_path | `solo_event_s3` | 3 |
| 7 | `guild_rest` | DEFAULT | `guild_shop` | 1 |
| 8 | `guild_shop` | DEFAULT | `guild_event_s3` | 1 |
| 9 | `guild_event_s3` | DEFAULT | `guild_combat` | 1 |
| 10 | `guild_combat` | DEFAULT | `guild_event_s4` | 1 |
| 11 | `guild_event_s4` | DEFAULT | `guild_boss` | 1 |
| 12 | `guild_boss` | DEFAULT | `merge_s5` | 1 |
| 13 | `guard_event_s3` | DEFAULT | `guard_shop` | 1 |
| 14 | `guard_shop` | DEFAULT | `guard_combat` | 1 |
| 15 | `guard_combat` | DEFAULT | `guard_event_s4` | 1 |
| 16 | `guard_event_s4` | DEFAULT | `guard_rest` | 1 |
| 17 | `guard_rest` | DEFAULT | `guard_boss` | 1 |
| 18 | `guard_boss` | DEFAULT | `merge_s5` | 1 |
| 19 | `solo_event_s3` | DEFAULT | `solo_combat` | 1 |
| 20 | `solo_combat` | DEFAULT | `solo_rest` | 1 |
| 21 | `solo_rest` | DEFAULT | `solo_shop` | 1 |
| 22 | `solo_shop` | DEFAULT | `solo_event_s4` | 1 |
| 23 | `solo_event_s4` | DEFAULT | `solo_boss` | 1 |
| 24 | `solo_boss` | DEFAULT | `merge_s5` | 1 |
| 25 | `merge_s5` | DEFAULT | `merge_exit` | 1 |
| 26 | `merge_exit` | (없음 — EXIT) | — | — |

**총 노드 수**: 24 (4 공통 + 6×3 루트 + 2 합류)
**총 엣지 수**: 26 (DEFAULT 23 + CHOICE 3)
**런당 방문**: 항상 12노드, 12엣지 순회

---

# 부록 B. vertical_slice_v1.md 와의 대응

| vertical_slice_v1 노드 | node_routing_v2 대응 |
|------------------------|---------------------|
| 0: EVENT (S0_ARRIVE, isIntro) | `common_s0` (동일) |
| 1: EVENT (S1_GET_ANGLE) | `common_s1` (동일) |
| 2: COMBAT (ENC_DOCK_AMBUSH) | `common_combat_dock` (동일) |
| 3: EVENT (S2_PROVE_TAMPER) | `common_s2` (동일, 분기점으로 확장) |
| 4: REST | 루트별: `guild_rest` / `guard_rest`(8번째) / `solo_rest`(6번째) |
| 5: SHOP (HARBOR_SHOP) | 루트별: `guild_shop` / `guard_shop` / `solo_shop` |
| 6: EVENT (S3_TRACE_ROUTE) | 루트별: `guild_event_s3` / `guard_event_s3` / `solo_event_s3` |
| 7: COMBAT (ENC_WAREHOUSE_INFILTRATION) | 루트별: `guild_combat` / `guard_combat` / `solo_combat` |
| 8: EVENT (S4_CONFRONT) | 루트별: `guild_event_s4` / `guard_event_s4` / `solo_event_s4` |
| 9: COMBAT (ENC_GUARD_CONFRONTATION, isBoss) | 루트별: `guild_boss` / `guard_boss` / `solo_boss` |
| 10: EVENT (S5_RESOLVE) | `merge_s5` (합류, routeTag별 eventId 분화) |
| 11: EXIT | `merge_exit` (동일) |

> `vertical_slice_v1.md`는 이 문서에 의해 **대체(supersede)** 되지 않는다.
> 서사 검증 목적의 원본 시퀀스로 유지하되, 실제 구현은 본 문서의 DAG 구조를 따른다.
