# Combat Engine Resolve v1

> 전투 턴 처리의 구현 사양서.
> `resolveCombatTurn` 단일 진입점을 중심으로, 입력(ActionPlan) → 판정(Resolve) → 출력(ServerResultV1) 전 과정을 정의한다.
>
> 관련 정본: `combat_system.md` (스탯/공식), `input_processing_pipeline_v1.md` (입력→DSL), `schema/server_result_v1.json` (출력 스키마)

---

## §0. 단일 진입점

서버에서 전투 턴 처리의 심장은 함수 1개다.

```typescript
resolveCombatTurn(params): {
  nextBattleState: BattleState
  serverResult: ServerResultV1
  internal: { rngConsumed: number; aiLog?: any }
}
```

- **입력**: ActionPlan(DSL) + 현재 BattleState + player/enemy 스탯 + rng_state + enemyNames
- **출력**: next BattleState + server_result_v1 (events/diff/ui/flags 포함) + combatOutcome

```typescript
type CombatOutcome = "ONGOING" | "VICTORY" | "DEFEAT" | "FLEE_SUCCESS";
```

이 출력만 있으면 클라이언트 HUD 복원, 리플레이, LLM 서술까지 모두 연결된다.

> 참조: `core_game_architecture_v1.md` §1 (역할 분리), `llm_context_system_v1.md` (LLM 컨텍스트)

---

## §1. 도메인 타입 (TypeScript 기준)

### §1.1 ActionPlan — 서버 실행 DSL

입력 파이프라인(`input_processing_pipeline_v1.md`)에서 최종 생성되는 DSL 정의.

전투 Action만 포함한다. 비전투 Action(TALK, SEARCH, OBSERVE)은 `combat_system.md` §12 참조.

```typescript
type ActionType =
  | "ATTACK_MELEE" | "ATTACK_RANGED"
  | "DEFEND" | "EVADE"
  | "MOVE" | "USE_ITEM"
  | "FLEE" | "INTERACT";

type ActionUnit = {
  type: ActionType;
  targetId?: string;       // enemy_01 등
  direction?: "LEFT" | "RIGHT" | "FORWARD" | "BACK";
  meta?: Record<string, any>;
};

type ActionPlan = {
  units: ActionUnit[];      // 순서대로 resolve
  consumedSlots: {
    base: number;
    used: number;
    bonusUsed: boolean;
  };
  staminaCost: number;
  policyResult: "ALLOW" | "TRANSFORM" | "PARTIAL" | "DENY";
  parsedBy: "RULE" | "LLM" | "MERGED";
};
```

### §1.2 BattleState — 전투 상태 (정본)

distance/angle은 적 per-enemy가 정본이다.

> 참조: `schema/07_database_schema.md` (DB 필드), `schema/OpenAPI 3.1.yaml` (API 스키마)

```typescript
type Distance = "ENGAGED" | "CLOSE" | "MID" | "FAR" | "OUT";
type Angle = "FRONT" | "SIDE" | "BACK";
type Personality = "AGGRESSIVE" | "TACTICAL" | "COWARDLY" | "BERSERK" | "SNIPER";

type BattleState = {
  phase: "START" | "TURN" | "END";
  playerState: {
    hp: number;
    stamina: number;
    status: string[];
  };
  enemiesState: Array<{
    id: string;
    hp: number;
    status: string[];
    personality: Personality;
    distance: Distance;
    angle: Angle;
  }>;
  rng: {
    seed: string;             // 생성 시 고정
    cursor: number;           // 난수 소비 카운터 (조건부 소비 대응)
  };
  lastResolvedTurnNo: number;
};
```

### §1.3 StatsSnapshot — 매 턴 계산

- Resolve 직전에 StatsBuilder가 Modifier Stack 기반으로 생성한다.
- **battle_state에는 스탯을 저장하지 않는다** — 매 턴 계산이 원칙.
- 기어/버프/디버프/환경 등의 modifier를 priority 순서대로 적용하여 최종 스탯을 산출한다.

> 참조: `combat_resolve_engine_v1.md` §2 (스탯 적용 파이프라인 Priority 구조)

### §1.4 ServerResultV1 — 출력 스키마

events, diff, ui, flags는 정본 스키마(`schema/server_result_v1.json`) 그대로 채운다.

---

## §2. RNG/결정성 규칙

전투의 결정성 보장은 리플레이/멱등성/부정행위 방지의 기반이다.

> 참조: `server_api_system.md` (멱등성), `combat_system.md` Part 0 (RNG 소비 순서)

### §2.1 RNG 소비 고정 순서

단일 적이든 다수 적이든 항상 같은 순서로 난수를 소비한다.

1. 플레이어 ActionUnit 1 resolve (필요 난수 소비)
2. 플레이어 ActionUnit 2 resolve
3. (보너스 사용 시) ActionUnit 3 resolve
4. 적 행동 순서 결정 (SPEED/seed)
5. 적1 resolve
6. 적2 resolve ...

**핵심 제약**: 각 ActionUnit마다 난수 소비 순서는 고정이다.

```
ActionUnit당 고정 호출 순서: hitRoll → (hit일 때만) varianceRoll → critRoll
```

- `hitRoll`은 항상 소비한다.
- `varianceRoll`, `critRoll`은 hit일 때만 소비한다 (조건부 소비).
- 조건부 소비이므로 실행 경로에 따라 소비량이 달라진다.
- 따라서 RNG 상태는 반드시 **seed + cursor** 방식으로 저장한다 (`battlestate_storage_recovery_v1.md` §4 참조).
- RNG 상태는 turn 단위로 저장한다.

---

## §3. Resolve 알고리즘 (턴 처리)

### §3.1 프리체크 — 슬롯/스태미나/상태

| 항목 | 규칙 | 정본 |
|------|------|------|
| 슬롯 | 기본 2 + 보너스 1, **최대 3** | `combat_system.md` Part 1 |
| 스태미나 비용 | 기본 Action = 1, 보너스 Action = 2 | `combat_system.md` Part 1 |
| 스태미나 부족 강행 | stamina=0 강행 시 ACC -5, damage -20% | `combat_system.md` Part 0 |
| 정책 확정 | TRANSFORM/PARTIAL은 resolve 이전에 확정 | `input_processing_pipeline_v1.md` §6 |

### §3.2 플레이어 ActionUnit resolve (순차)

각 유닛은 `applyActionUnit()`로 처리한다.

#### A) MOVE / EVADE — 포지셔닝

- 결과: enemy의 distance/angle 변경 가능
- events에 `MOVE` kind로 기록
- `diff.meta.position`에는 편의용 복사본만 (단일 적 기준), 정본은 `enemies[].distance/angle`

> **v1 구현 현황**: MOVE는 distance/angle 변경이 구현됨. EVADE는 이벤트 생성만 수행하며 실제 회피 기계적 효과(적 명중률 감소 등)는 미구현. EVADE의 기계적 효과는 v2에서 추가 예정.

> 참조: `schema/server_result_v1.json` (Event kind), `schema/07_database_schema.md` (distance/angle 정본)

#### B) ATTACK — 명중/치명/피해

**명중 규칙** (정본: `combat_resolve_engine_v1.md` §3):
- d20 판정, 1 자동 실패 / 20 자동 성공
- `roll + floor(ACC * HIT_MULT) >= 10 + targetEVA`

**피해 규칙** (정본: `combat_resolve_engine_v1.md` §5):
- `baseDamage = ATK * (100 / (100 + effectiveDEF))`
- 랜덤 ±10%, DAMAGE_MULT/TAKEN_DMG_MULT 적용, floor, 최소 1

**치명타 규칙** (정본: `combat_system.md` Part 0):
- CRIT% (0~50 clamp)
- 치명타 시 DEF 30% 무시

결과는 events에 `DAMAGE`로 기록, `diff.enemies[].hp` 갱신.

> **v1 구현 현황**: 명중/피해/치명타 판정은 완전 구현됨. ATTACK 시 상태이상 부여 시도(§1회)는 미구현 — v2에서 추가 예정.

#### C) DEFEND

- 행동 포기 대가로 stamina +1
- events에 kind: `BATTLE`, tags: `['DEFEND']` 기록

> **v1 구현 현황**: stamina +1 + 서술용 event만 생성. 피해 -30% 감소 효과(`combat_resolve_engine_v1.md` §9)는 미구현 — v2에서 추가 예정.

#### D) USE_ITEM

> **v1 구현 현황**: USE_ITEM은 **placeholder 구현**. 이벤트(kind: `BATTLE`)만 생성하며 실제 기계적 효과(아이템 소모 등)는 없음. v2에서 인벤토리 시스템과 연동 예정.

#### E) INTERACT (환경 활용)

> **v1 구현 현황**: `meta.envAction === true` 일 때 환경 활용 시스템으로 동작한다.

- **판정**: `d20 + ACC >= 12`
- **성공 시**: 모든 생존 적에게 maxHP의 40-60% 광역 피해 (AoE)
- **실패 시**: 모든 생존 적에게 maxHP의 10% 피해 (최소 피해 보장)
- events에 kind: `DAMAGE`, tags: `['ENV_ACTION', 'SUCCESS']` 또는 `['ENV_ACTION', 'PARTIAL']`로 기록
- envTags 기반 한국어 레이블 매핑: `COVER_CRATE` → "화물 상자를 적에게 던진다", `COVER_WALL` → "벽의 잔해를 무너뜨린다", `NARROW` → "좁은 통로를 이용해 가둔다"

`meta.envAction`이 아닌 일반 INTERACT는 기존 placeholder 동작 유지.

#### F) FLEE / 전투 회피

**기본 FLEE 판정** (정본: `combat_system.md` Part 2):
- `d20 + SPEED >= 12 + engaged_enemy_count * 2`
- 성공 시 전투 종료 + 전리품 없음
- 실패 시 기회공격 등
- `flags.battleEnded` 및 node 상태 전이 연계

**전투 회피** (`meta.isAvoid === true`):
- `d20 + SPEED + EVA >= 10 + 생존_적_수`
- 성공 시 `FLEE_SUCCESS`로 전투 종료 (기본 FLEE와 동일 결과)
- 실패 시 턴 소모만 (기회공격 없음)
- events tags: `['AVOID']` 또는 `['AVOID_FAIL']`

### §3.3 보너스 슬롯 판단 & UI

보너스 슬롯 조건은 서버가 판정하고 UI에만 노출한다.

- 조건 예: 크리티컬, 완벽 회피, 적 기절, 약점 노출 등
- `flags.bonusSlot = true`
- `ui.actionSlots.bonusAvailable = true`
- 이벤트는 kind `UI`로 "빈틈을 드러냈다"처럼 기록 가능

> 참조: `combat_system.md` Part 1 (보너스 조건), `schema/server_result_v1.json` (flags/ui 스키마)

> **v1 구현 현황**: 보너스 슬롯 트리거 조건 중 **HP ≤ 30% 진입**만 구현됨. 크리티컬, 완벽 회피, 적 기절, 약점 노출 등 나머지 조건은 미구현.

### §3.4 적 AI resolve (v1 최소 구현)

정본 방향은 "점수 기반 + roulette pick"이고, personality를 입력으로 사용한다.

> 참조: `combat_system.md` Part 3 (Enemy AI)

> **v1 구현 현황**: 점수 기반 + roulette pick이 아닌 **결정적 personality 기반 분기**로 구현됨. distance에 따른 고정 행동 패턴을 사용하며, RNG는 명중/피해 판정에만 사용한다.

**v1 최소 구현**:

| Personality | 행동 패턴 |
|-------------|-----------|
| TACTICAL | COVER/FLANK 우선, 아니면 ATTACK |
| AGGRESSIVE | 접근(ENGAGED 유도) 후 근접 |
| SNIPER | FAR 유지 후 원거리 |
| COWARDLY | HP 낮으면 후퇴, 아니면 소극적 공격 |
| BERSERK | 무조건 접근 + 최대 피해 |

결과는 플레이어 hp/stamina/status, enemies distance/angle 변화로 diff에 반영.

### §3.5 DOWNED 처리

HP 0이면 즉시 사망이 아니다. DOWNED로 전환한다.

> 참조: `core_game_architecture_v1.md` §8 (Downed & Recovery), `combat_system.md` Part 0

- DOWNED 저항 판정: `d20 + RESIST >= 15` → 성공 시 HP 1로 복구
- 실패 시 `flags.downed = true`, battle 종료/구조 이벤트 트리거는 노드/런 정책으로 처리

### §3.6 전투 종료 처리

| Outcome | 조건 | 처리 |
|---------|------|------|
| VICTORY | 모든 적 HP ≤ 0 | 보상 계산 (`rewards_and_progression_v1.md` 참조), `battle_state.phase = END` |
| DEFEAT | 플레이어 HP ≤ 0 + DOWNED 실패 | RUN 종료 정책에 따름 |
| FLEE_SUCCESS | 도주 판정 성공 | 보상 없음, 즉시 종료 |

---

## §4. server_result_v1 생성 규칙

스키마 필수 필드: summary, events, diff, ui, choices, flags

> 정본 스키마: `schema/server_result_v1.json`

### §4.1 summary.short

- 180자 이내
- "이번 턴의 핵심" 한 문장
- 예: `"오른쪽으로 굴러 회피한 뒤, 화살이 적중했다."`

### §4.2 events[]

- kind: `BATTLE` / `DAMAGE` / `STATUS` / `LOOT` / `GOLD` / `QUEST` / `NPC` / `MOVE` / `SYSTEM` / `UI`
- 전투 턴은 보통 `MOVE` + `DAMAGE` + (선택) `UI` 조합으로 충분
- `BATTLE`은 전투 시작/종료 등 전투 흐름 이벤트에 사용
- USE_ITEM, INTERACT 이벤트는 kind: `BATTLE`로 기록 (클라이언트 필터링 대상)

> **v1 구현 현황 — 클라이언트 이벤트 필터링**: 기본적으로 클라이언트(`result-mapper.ts`)는 `SYSTEM`, `LOOT`, `GOLD` kind만 유저에게 표시한다. 단, **전투 LLM 스킵 시**(llm.status === 'SKIPPED') `BATTLE`, `DAMAGE`, `MOVE`, `STATUS` 이벤트도 SYSTEM 메시지로 유저에게 표시한다. 이는 LLM 내러티브가 없을 때 전투 결과를 직접 보여주기 위함이다.
- `STATUS`: STATUS_APPLIED / STATUS_TICKED / STATUS_REMOVED (`status_effect_system_v1.md` §8 참조)
- `BONUS_GRANTED`: 보너스 슬롯 트리거 시
- `COMBAT_END`: 전투 종료 시 (VICTORY/DEFEAT/FLEE_SUCCESS)

### §4.3 diff

| 필드 | 내용 |
|------|------|
| `player` | hp, stamina, status |
| `enemies` | hp, status + (선택) distance, angle |
| `inventory` | 변화 시 |
| `meta.battle.phase` | START/TURN/END |
| `meta.battle.rngConsumed` | 소비된 난수 개수 |
| `meta.position.env` | 환경 태그 |

### §4.4 ui

| 필드 | 내용 |
|------|------|
| `availableActions` | 노드 타입/상태/스태미나 등에 따라 |
| `targetLabels` | 적 이름 (enemyNames 맵에서 조회) |
| `actionSlots` | `{ base: 2, max: 3, bonusAvailable: boolean }` |
| `toneHint` | tense / calm 등 |

### §4.5 flags

| 플래그 | 용도 |
|--------|------|
| `bonusSlot` | 보너스 슬롯 발동 |
| `downed` | 플레이어 DOWNED |
| `battleEnded` | 전투 종료 |
| `nodeTransition` | 노드 상태 전이 |

---

## §5. 구현 모듈 분리 (권장 파일 구조)

```
engine/
├── combat/
│   ├── resolveCombatTurn.ts      ← 단일 진입점 (§0)
│   ├── actions/
│   │   └── applyActionUnit.ts    ← ActionUnit별 분기 (§3.2)
│   ├── rules/
│   │   ├── hit.ts                ← 명중 판정 (§3.2.B)
│   │   ├── damage.ts             ← 피해 계산 (§3.2.B)
│   │   └── crit.ts               ← 치명타 판정 (§3.2.B)
│   ├── position/
│   │   └── applyMove.ts          ← 포지셔닝 (§3.2.A)
│   ├── ai/
│   │   └── selectEnemyActions.ts ← 적 AI (§3.4)
│   └── result/
│       ├── buildServerResult.ts  ← ServerResultV1 조립 (§4)
│       └── buildDiff.ts          ← diff 생성 (§4.3)
└── rng/
    └── prng.ts                   ← seed 기반 PRNG (§2)
```

---

## §6. 구현 의사코드

```typescript
function resolveCombatTurn(input: {
  turnNo: number;
  node: {
    id: string;
    type: "COMBAT";
    index: number;
    state: "NODE_ACTIVE" | "NODE_ENDED";
  };
  envTags: string[];          // OPEN/COVER 등
  actionPlan: ActionPlan;
  battleState: BattleState;
  enemyNames?: Record<string, string>;  // enemy ID → 한국어 이름 (LLM/이벤트 텍스트용)
  stats: {
    player: {
      ATK: number; DEF: number; ACC: number; EVA: number;
      CRIT: number; CRIT_DMG: number; RESIST: number; SPEED: number;
      MaxHP: number; MaxStamina: number;
    };
    enemies: Record<string, {
      ATK: number; DEF: number; ACC: number; EVA: number;
      CRIT: number; CRIT_DMG: number; RESIST: number; SPEED: number;
    }>;
  };
}): {
  nextBattleState: BattleState;
  serverResult: ServerResultV1;
  internal: { rngConsumed: number };
} {

  const rng = createRng(input.battleState.rng.seed, input.battleState.rng.cursor);

  // ── 1) 슬롯/스태미나 적용 ──
  const staminaBefore = input.battleState.playerState.stamina;
  const staminaAfter = Math.max(0, staminaBefore - input.actionPlan.staminaCost);
  const forced = staminaBefore === 0 && input.actionPlan.staminaCost > 0;

  // ── 2) nextState 초안 ──
  const next = deepClone(input.battleState);
  next.phase = "TURN";
  next.playerState.stamina = staminaAfter;

  const events: Event[] = [];
  const diff = initDiffFrom(input.battleState, next, input.envTags);

  // ── 3) 플레이어 유닛 resolve ──
  for (const unit of input.actionPlan.units.slice(0, maxAllowedUnits(next))) {
    const r = applyActionUnit({
      unit, next, stats: input.stats,
      rng, forced, env: input.envTags,
    });
    merge(next, r.nextBattlePatch);
    events.push(...r.events);
    applyDiffPatch(diff, r.diffPatch);
  }

  // ── 4) 보너스 슬롯 판단 ──
  const bonusAvailable = computeBonusAvailable({ events, next, rng });

  // ── 5) 적 AI resolve (battleEnded이면 스킵) ──
  if (!isBattleEnded(next)) {
    const enemyOrder = decideEnemyOrder(next, input.stats, rng);
    for (const enemyId of enemyOrder) {
      const aiUnits = selectEnemyActions({
        enemyId, next, stats: input.stats,
        rng, env: input.envTags,
      });
      for (const unit of aiUnits) {
        const r = applyEnemyActionUnit({
          enemyId, unit, next, stats: input.stats,
          rng, env: input.envTags,
        });
        events.push(...r.events);
        applyDiffPatch(diff, r.diffPatch);
      }
    }
  }

  // ── 6) DOWNED 체크 ──
  if (next.playerState.hp === 0) {
    const saved = rollDownedResist(next, input.stats.player, rng);
    if (saved) {
      next.playerState.hp = 1;
      // diff에 hp=1 반영
    } else {
      // flags.downed = true
    }
  }

  // ── 7) server_result 생성 ──
  const serverResult = buildServerResultV1({
    turnNo: input.turnNo,
    node: input.node,
    events,
    diff,
    ui: buildUI(next, bonusAvailable),
    flags: buildFlags(next, bonusAvailable),
    choices: [],              // COMBAT 기본 빈 배열
  });

  // ── 8) rng 갱신 ──
  next.rng = { seed: input.battleState.rng.seed, cursor: rng.cursor() };
  next.lastResolvedTurnNo = input.turnNo;

  return {
    nextBattleState: next,
    serverResult,
    internal: { rngConsumed: rng.consumed() },
  };
}
```

---

## 문서 간 참조 맵

| 이 문서 섹션 | 참조 정본 |
|-------------|-----------|
| §0 단일 진입점 | `core_game_architecture_v1.md` §1 역할 분리 |
| §1.1 ActionPlan | `input_processing_pipeline_v1.md` §5 Action DSL |
| §1.2 BattleState | `schema/07_database_schema.md`, `schema/OpenAPI 3.1.yaml` |
| §1.3 StatsSnapshot | `combat_resolve_engine_v1.md` §2 (스탯 파이프라인) |
| §1.4 ServerResultV1 | `schema/server_result_v1.json` |
| §2 RNG 결정성 | `server_api_system.md` 멱등성, `combat_system.md` Part 0 §7 |
| §3.1 슬롯/스태미나 | `combat_system.md` Part 1 |
| §3.2 명중/피해/치명 | `combat_system.md` Part 0 §3-5 |
| §3.3 보너스 슬롯 | `combat_system.md` Part 1, `schema/server_result_v1.json` |
| §3.4 적 AI | `combat_system.md` Part 3 |
| §3.5 DOWNED | `core_game_architecture_v1.md` §8, `combat_system.md` Part 0 |
| §3.6 전투 종료 | `rewards_and_progression_v1.md`, `node_resolve_rules_v1.md` §4 |
| §4 결과 생성 | `schema/server_result_v1.json` (전체) |
| §7 구현 계약 | `combat_resolve_engine_v1.md`, `status_effect_system_v1.md`, `battlestate_storage_recovery_v1.md` |

---

## §7. 구현 계약 보충

### §7.1 상태 반환 규약

- Resolve 결과는 **전체 상태 스냅샷**을 반환한다.
- 클라이언트는 **교체 방식**으로 적용한다 (patch/diff 방식 미사용).

### §7.2 LLM 의존 정책

- `server_result`는 서술 텍스트를 포함한다 (LLM 필수).
- LLM 실패 시: 다른 모델로 재시도 → 전부 실패 시 `SYSTEM` 폴백 서술로 대체.
- LLM 장애는 HTTP 500으로 처리하지 않는다.

### §7.3 에러 정책

| 코드 | 상황 |
|------|------|
| 409 | turn 충돌 / 동시 요청 |
| 422 | 정책상 거부 (DENY) |
| 500 | 내부 오류 (LLM 장애 제외) |

### §7.4 추천 행동 UI 정책

- `recommendedActions`는 기본 비활성.
- 옵션 플래그로 활성화 가능.

### §7.5 적 이름 체인 (enemyNames)

이벤트 텍스트와 UI 라벨에서 적 ID(`ENEMY_DOCK_THUG_0`) 대신 한국어 이름을 사용한다.

```
turns.service.ts → encounter 기반 enemyNames 맵 구축
  → NodeResolveInput.enemyNames
  → CombatNodeInput.enemyNames
  → CombatTurnInput.enemyNames
  → combat.service.ts에서 eName(id) 헬퍼로 이벤트 텍스트에 적용
```

- `enemyNames`는 `turns.service.ts`에서 `battleState.enemies`의 각 ID로부터 content(`enemies.json`)를 조회하여 구축
- ID 패턴: `ENEMY_DOCK_THUG_0` → `_숫자` 접미사 제거 → content key `ENEMY_DOCK_THUG`로 조회
- 이름이 없으면 원본 ID를 그대로 사용 (fallback)

### §7.6 최소 검증 기준

- 동일 seed + 동일 ActionPlan → 동일 결과
- EVADE 후 1회만 방어 적용
- STUN 면역 2턴 적용 확인
- HP 30% 진입 트리거는 직접 피해일 때만

---

## §8. 전투 확장 시스템 (v1 구현)

### §8.1 콤보 선택지

스태미나 ≥ 2이고 ENGAGED/CLOSE 거리의 적이 있을 때, 2개의 ActionUnit을 1턴에 실행하는 콤보 선택지가 제공된다.

| 콤보 ID | 구성 | 스태미나 | 설명 |
|---------|------|---------|------|
| `combo_double_attack_{enemyId}` | ATTACK_MELEE × 2 | 2 | 동일 대상 연속 공격 |
| `combo_attack_defend_{enemyId}` | ATTACK_MELEE + DEFEND | 2 | 공격 후 방어 태세 |

- `turns.service.ts`의 `parseComboChoiceToActionPlan()`에서 ActionPlan으로 변환
- 2개의 ActionUnit이 순차 resolve되며 각각 독립적으로 명중/피해 판정

### §8.2 환경 활용 (env_action)

전투 중 `envTags` 기반으로 확률적 광역 대미지를 가하는 시스템.

- **선택지 ID**: `env_action`
- **ActionPlan 매핑**: `{ type: 'INTERACT', meta: { envAction: true } }`
- **판정 공식**: `d20 + ACC >= 12`
- **성공 효과**: 모든 생존 적에게 maxHP의 40-60% 피해 (약한 적 즉사 가능)
- **실패 효과**: 모든 생존 적에게 maxHP의 10% 피해
- **envTags → 레이블 매핑**:
  - `COVER_CRATE` → "화물 상자를 적에게 던진다"
  - `COVER_WALL` → "벽의 잔해를 무너뜨린다"
  - `NARROW` → "좁은 통로를 이용해 가둔다"
  - `INDOOR` → "실내 구조물을 활용한다"
  - (기본) → "주변 환경을 활용한다"

### §8.3 전투 회피 (combat_avoid)

전투를 확률적으로 완전히 스킵하는 시스템.

- **선택지 ID**: `combat_avoid`
- **ActionPlan 매핑**: `{ type: 'FLEE', meta: { isAvoid: true } }`
- **판정 공식**: `d20 + SPEED + EVA >= 10 + 생존_적_수`
- **성공**: `FLEE_SUCCESS`로 전투 종료 (보상 없음)
- **실패**: 턴 소모, 전투 계속

기본 FLEE(도주)와의 차이:
- 도주: `d20 + SPEED >= 12 + engaged_count * 2` (교전 중인 적 수 기준)
- 회피: `d20 + SPEED + EVA >= 10 + 생존_적_수` (모든 생존 적 수 기준)

### §8.4 전투 LLM 스킵

전투 중 턴은 LLM 내러티브를 생략하여 속도를 높인다.

| 턴 유형 | LLM 상태 | 이유 |
|---------|----------|------|
| 전투 진입 (enter) | PENDING | 분위기 전달 |
| 전투 중 (action/choice) | **SKIPPED** | 속도감 (1-2초/턴) |
| 전투 종료 → 다음 노드 | PENDING | enter 턴 자동 생성 |

- 클라이언트: `submitAction`/`submitChoice`에서 `currentNodeType === 'COMBAT'`이면 `options: { skipLlm: true }` 전송
- 서버: `llmStatus = 'SKIPPED'`로 저장, LLM Worker가 처리하지 않음
- 클라이언트: `llm.status === 'SKIPPED'`이면 전투 이벤트(BATTLE/DAMAGE/MOVE/STATUS)를 SYSTEM 메시지로 직접 표시, NARRATOR 메시지 생략

### §8.5 전투 선택지 빌드 순서

COMBAT 노드 진입 시 및 매 턴 종료 후, 다음 순서로 선택지를 생성한다:

1. **기본 단일 액션**: 공격(근접/원거리), 방어, 회피, 이동, 아이템 사용
2. **콤보 선택지**: 스태미나 ≥ 2 && ENGAGED/CLOSE 적 존재 시
3. **환경 활용**: envTags 기반 레이블
4. **전투 회피**: 항상 제공
5. **도주**: 기존 FLEE

구현 위치: `combat.service.ts#buildCombatChoices()`, `node-transition.service.ts#buildEnterResult()`
