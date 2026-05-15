# 02 — 전투 시스템 통합

> 원본: `03_combat_rules.md` + `04_combat_engine.md` 통합. 중복 제거, 공식/테이블 보존.

---

## 1. 전투 기본 규칙

D20 명중 판정, 비율형 방어, 최대 3 Action (기본 2 + 보너스 1, **3 초과 절대 불가**). 플레이어와 AI 동일 규칙.

### 스탯 정의

| 스탯 | 설명 | 비고 |
|------|------|------|
| HP / MaxHP | 현재/최대 체력 | |
| Stamina / MaxStamina | 현재/최대 스태미나 | Action 비용 |
| ATK | 공격력 | 피해 공식 |
| DEF | 방어력 | 피해 감소 |
| ACC | 명중 보정 | |
| EVA | 회피 보정 | 방어측 |
| CRIT | 치명타 확률 | 0~50% clamp |
| CRIT_DMG | 치명타 배율 | 기본 1.5, 최대 2.5 |
| RESIST | 상태이상/DOWNED 저항 | |
| SPEED | 행동 순서 보정 | 단일 적: 플레이어 우선 |
| DAMAGE_MULT | 피해 배율 | 기본 1.0 |
| HIT_MULT | 명중 배율 | 기본 1.0, ACC 곱연산 |
| TAKEN_DMG_MULT | 받는 피해 배율 | 기본 1.0 |

### Modifier Stack (스탯 적용 순서)

| Priority | Layer | Priority | Layer |
|----------|-------|----------|-------|
| 100 | BASE | 400 | DEBUFF |
| 200 | GEAR | 900 | FORCED |
| 300 | BUFF | 950 | ENV |

StatsBuilder가 매 턴 계산 (StatsSnapshot). **battle_state에 스탯 저장 안 함.**

### Stamina

- 소모: Action = 1, Bonus Action = 2. stamina 0 강행 시 ACC -5, damage -20%
- 회복: 전투 중 없음. DEFEND +1. REST 전량. 비전투 노드 종료 +2

### Action Economy

- 기본 2개 실행, 초과분은 TRANSFORM. 비용: 1번째=1, 2번째=1, 보너스=2

### ActionType (enum 정본)

전투: `ATTACK_MELEE | ATTACK_RANGED | DEFEND | EVADE | MOVE | USE_ITEM | FLEE | INTERACT`

비전투 (EVENT/REST/SHOP): `TALK | SEARCH | OBSERVE`

---

## 2. 판정 공식

### 명중 (정본)

```
roll = d20
hit if: roll + floor(ACC * HIT_MULT) >= 10 + targetEVA
```
- roll 1: 자동 실패 / roll 20: 자동 성공. 치명타는 hit일 때만 판정.

### 치명타

```
critChance = clamp(CRIT, 0, 50%)
effectiveDEF = isCrit ? DEF * 0.7 : DEF   // 치명타 시 DEF 30% 무시
```

### 피해 (정본)

```
baseDamage = ATK * (100 / (100 + effectiveDEF))
dmg = baseDamage
dmg *= random(0.9 ~ 1.1)         // varianceRoll
if (isCrit) dmg *= CRIT_DMG
dmg *= DAMAGE_MULT
dmg *= TAKEN_DMG_MULT
dmg = Math.floor(dmg)            // 최종 단계에서만 floor
if (hit && dmg < 1) dmg = 1     // 적중 시 최소 1
```

### DOWNED

```
HP 0 시: d20 + RESIST >= 15 → 성공: HP 1, 실패: DOWNED
```
SPEED는 DOWNED 판정에 영향 없음. 실패 시 `flags.downed = true`.

### FLEE (도주)

```
d20 + SPEED >= 12 + (engaged_enemy_count * 2)
```
성공: NODE_ENDED(보상 없음). 실패: 턴 소모. FLEE만 단독 사용. ENGAGED 적 없으면 자동 성공.

### 전투 회피 (combat_avoid)

```
d20 + SPEED + EVA >= 10 + 생존_적_수
```
성공: FLEE_SUCCESS(보상 없음). 실패: 턴 소모(기회공격 없음). ActionPlan: `{ type: 'FLEE', meta: { isAvoid: true } }`. 도주는 engaged_count, 회피는 생존_적_수 기준.

---

## 3. 상태이상 시스템

### 상태이상 5종

| Status | 종류 | 중첩 | 최대 | 지속 | 효과 |
|--------|------|------|------|------|------|
| BLEED | DOT | O | 5 | 3턴 | maxHP 3%/스택 |
| POISON | DOT | O | 5 | 3턴 | maxHP 2%/스택 + TAKEN_DMG_MULT +5% |
| STUN | CC | X | - | 1턴(고정) | 행동 불가, 해제 시 STUN_IMMUNE 2턴 |
| WEAKEN | DEBUFF | X | - | 2턴 | ATK -15% |
| FORTIFY | BUFF | X | - | 2턴 | DEF +20%, TAKEN_DMG_MULT -10% |

### StatusInstance 스키마

```ts
type StatusInstance = {
  id: string;                 // "BLEED", "STUN" 등
  sourceId: "PLAYER" | "ENEMY";
  applierId: string;          // "player", "enemy_01"
  duration: number;
  stacks: number;
  power: number;              // v1: 1
  meta?: Record<string, any>;
};
```

### 적용 판정

```
d20 + attacker.ACC >= 10 + target.RESIST
```
ATTACK 1회당 부여 시도 **1개만**. v1: 부여 시도 자체 미구현, tick/만료만 구현.

### 중첩 & Duration

- stackable=true: `stacks = min(stacks+1, maxStacks)`, `duration = max(duration, newDuration)`
- stackable=false: `stacks = 1`, `duration = max(duration, newDuration)`

### Tick (턴 종료 5번 단계)

1. tickEffect 실행 → 2. `duration -= 1` → 3. `duration <= 0`이면 제거. **RNG 미사용(결정적).**

### DOT 피해 공식 (방어 무시)

```
rawDot = floor(target.maxHP * dotPercent * stacks * power)
dot = floor(rawDot * target.TAKEN_DMG_MULT)
if dot < 1 then dot = 1
```
BLEED dotPercent=0.03, POISON dotPercent=0.02. DEF 무시, TAKEN_DMG_MULT 적용, 최소 1.

### STUN 가드레일

- duration **1턴 고정**, 재적용 갱신 불가
- 해제 시 `STUN_IMMUNE` **2턴** 자동 부여 (STUN 시도 자동 실패)
- CC 턴에는 보너스 슬롯 트리거 비활성

### Modifier 연결

BUFF=priority 300, DEBUFF=priority 400. WEAKEN: ATK -15% @400. FORTIFY: DEF +20% @300, TAKEN_DMG_MULT -10% @300. 소모형 효과(EVADE_GUARD 등)도 status로 저장.

### 상태이상 이벤트

kind: `STATUS`, subkind: `APPLIED | TICKED | REMOVED`. TICKED에만 `tickDamage` 포함.

---

## 4. 위치 시스템

### Distance (per-enemy 개별 관리)

| 값 | 의미 | 값 | 의미 |
|----|------|----|------|
| ENGAGED | 근접 교전 | FAR | 원거리 |
| CLOSE | 근접 직전 | OUT | 교전 이탈 |
| MID | 중거리 | | |

그리드 없는 관계 기반 시스템. 다수 적: `distance(player, enemy_n)` 각각 관리.

### Angle

FRONT (기본) / SIDE (측면) / BACK (후방)

### 거리별 판정 영향

| Distance | 근접 공격 | 원거리 공격 |
|----------|-----------|-------------|
| ENGAGED | 보너스 | 불리 |
| FAR | 접근 필요 | 보너스 |

### SIDE/BACK 보정 (정본)

| | 공격 시 | 방어 시 |
|------|--------|---------|
| SIDE | target.DEF -10% | target.TAKEN_DMG_MULT +10% |
| BACK | target.DEF -20%, attacker.CRIT +10% | target.TAKEN_DMG_MULT +25% |

BACK은 공격 **1회만** 적용, 턴 종료 시 FRONT 복귀.

### BACK 방지 로직

FRONT->SIDE->BACK 단계 필수 (한 턴 FRONT->BACK 불가). 거리 CLOSE/ENGAGED, 1턴 1회 시도. 실패: stamina -1, FRONT 고정. AI BACK 시도 시 **-3 보정**.

### 환경 태그 (6종)

| Tag | 효과 | 하위 예시 |
|-----|------|-----------|
| COVER | 원거리 회피 보너스 | COVER_CRATE, COVER_WALL, COVER_PILLAR |
| HIGH_GROUND | 명중/관통 보너스 | |
| LOW_GROUND | 회피 페널티 | |
| OBSTACLE | 장애물 | OBSTACLE_BARREL, OBSTACLE_RUBBLE |
| NARROW | 다중 행동 페널티 | |
| OPEN | 광역 공격 보너스 | |

`기본태그_세부` 형식. 엔진은 언더스코어 앞 접두사로 기본 태그 인식. v1: 한 턴 최대 1단계 거리 변화, 환경 태그는 Node 시작 시 결정.

---

## 5. 적 AI

### Personality (5종)

| Personality | 특성 |
|-------------|------|
| AGGRESSIVE | 접근 우선, 방어 적음 |
| TACTICAL | 위치 계산, 엄폐/측면 활용 |
| COWARDLY | HP 낮으면 도주/후퇴 |
| BERSERK | 체력 낮을수록 공격성 증가 |
| SNIPER | 거리 유지 최우선 |

### AI 행동 카테고리

APPROACH, RETREAT, FLANK, SEEK_COVER, ATTACK_MELEE, ATTACK_RANGED, SPECIAL, INTERRUPT, DEFENSIVE_STANCE

### 의사결정 알고리즘

```
score = personality_weight + tactical_bonus + environment_bonus + random_noise
```
최종: `roulettePick(score)`. 10~20% 비최적 선택.

### v1 구현 (결정적 personality 분기)

| Personality | 패턴 |
|-------------|------|
| TACTICAL | COVER/FLANK 우선, 아니면 ATTACK |
| AGGRESSIVE | 접근(ENGAGED) 후 근접 |
| SNIPER | FAR 유지 + 원거리 |
| COWARDLY | HP 낮으면 후퇴, 아니면 소극적 |
| BERSERK | 무조건 접근 + 최대 피해 |

v1은 점수 roulette 아닌 결정적 분기. RNG는 명중/피해에만 사용.

### 협동 AI (다수 적)

FLANK(다른 각도), PRESSURE(ENGAGED 유지), DISTRACT(엄폐 파괴), PIN(거리 이동 제한)

---

## 6. 전투 흐름

### resolveCombatTurn 진입점

```typescript
resolveCombatTurn(params): {
  nextBattleState: BattleState;
  serverResult: ServerResultV1;
  internal: { rngConsumed: number; aiLog?: any };
}
```
입력: ActionPlan + BattleState + stats + rng_state + enemyNames. 출력: CombatOutcome(`ONGOING | VICTORY | DEFEAT | FLEE_SUCCESS`).

### ActionPlan (서버 DSL)

```typescript
type ActionUnit = {
  type: ActionType;
  targetId?: string;
  direction?: "LEFT" | "RIGHT" | "FORWARD" | "BACK";
  meta?: Record<string, any>;
};
type ActionPlan = {
  units: ActionUnit[];
  consumedSlots: { base: number; used: number; bonusUsed: boolean };
  staminaCost: number;
  policyResult: "ALLOW" | "TRANSFORM" | "PARTIAL" | "DENY";
  parsedBy: "RULE" | "LLM" | "MERGED";
};
```

### RNG 소비 순서 (불변 규칙)

1. 플레이어 ActionUnit 1~3 순차 resolve
2. 적 행동 순서 결정 (SPEED/seed)
3. 적1, 적2, 적3 순차 resolve

**ActionUnit당 고정 순서: `hitRoll` → (hit시만) `varianceRoll` → `critRoll`**

- hitRoll: **항상** 소비
- varianceRoll, critRoll: **hit일 때만** 소비 (조건부)
- seed + cursor 저장 (경로별 소비량 상이)

### 턴 처리 순서

1. 프리체크 (슬롯/스태미나/상태)
2. 플레이어 ActionUnit resolve (순차)
3. 보너스 슬롯 판단
4. 적 AI resolve (battleEnded면 스킵)
5. DOWNED 체크
6. 보너스 슬롯 확정
7. 상태이상 tick
8. 임시 버프 제거
9. BACK -> FRONT 복귀

### ActionUnit별 resolve

| Action | 처리 | v1 현황 |
|--------|------|---------|
| MOVE | distance/angle 변경 | 구현 |
| EVADE | 이벤트 생성 | 기계적 효과 미구현 |
| ATTACK | 명중/치명/피해 판정 | 구현 (상태부여 미구현) |
| DEFEND | stamina +1 | 피해 -30% 미구현 |
| USE_ITEM | placeholder | 기계적 효과 없음 |
| INTERACT | envAction시 `d20+ACC>=12`, 성공: maxHP 40-60% AoE, 실패: maxHP 10% | 구현 |
| FLEE | SS2 공식 적용 | 구현 |

### 보너스 슬롯

조건 하나 만족 시 +1 (턴당 1회, 이월 불가):
- 전투: 크리티컬, 적 기절, 완벽 회피, 약점 노출, **적 HP 30% 이하 진입**
- 사회: 설득 대성공, 감정 붕괴, 중요 단서, NPC 신뢰도 임계치
- 탐험: 함정 해체, 비밀 통로, 환경 이점

가드레일: CC 턴 비활성, DOT tick HP 30% 진입 비활성. v1: **HP<=30%만** 구현.

### 전투 종료

| Outcome | 조건 | 처리 |
|---------|------|------|
| VICTORY | 모든 적 HP<=0 | 보상, phase=END |
| DEFEAT | 플레이어 DOWNED | RUN 종료 정책 |
| FLEE_SUCCESS | 도주/회피 성공 | 보상 없음, 즉시 종료 |

---

## 7. BattleState 스키마

### BattleStateV1 (DB jsonb 정본)

```ts
type BattleStateV1 = {
  version: "battle_state_v1";
  phase: "START" | "TURN" | "END";
  lastResolvedTurnNo: number;
  rng: { seed: string; cursor: number };
  env: string[];
  player: { hp: number; stamina: number; status: StatusInstance[] };
  enemies: Array<{
    id: string;
    name?: string;
    hp: number;
    maxHp?: number;
    status: StatusInstance[];
    personality: "AGGRESSIVE" | "TACTICAL" | "COWARDLY" | "BERSERK" | "SNIPER";
    distance: "ENGAGED" | "CLOSE" | "MID" | "FAR" | "OUT";
    angle: "FRONT" | "SIDE" | "BACK";
  }>;
};
```

**distance/angle은 enemies에만 존재 (per-enemy 정본).**

### RNG 저장

seed + cursor. 동일 입력 = 동일 결과. splitmix/xorshift + index 기반.

### 원자 커밋

turn + battle_state + server_result + run 메타를 단일 트랜잭션으로 커밋. 멱등성: `(runId, turnNo)` 유니크 키.

### 복구

GET /runs/{runId}로 최신 battle_state + 마지막 server_result 복원. LLM 없이 전투 HUD 표시 가능. 중간 장애: 미커밋 -> 이전 상태 유지, 재시도 가능.

---

## 8. 콤보 / 환경 / LLM 스킵

### 콤보 선택지 (스태미나>=2, ENGAGED/CLOSE 적 존재 시)

| 콤보 ID | 구성 | 설명 |
|---------|------|------|
| `combo_double_attack_{enemyId}` | ATTACK_MELEE x 2 | 연속 공격 |
| `combo_attack_defend_{enemyId}` | ATTACK_MELEE + DEFEND | 공격 후 방어 |

### 환경 활용 (env_action)

선택지 `env_action` -> `{ type: 'INTERACT', meta: { envAction: true } }`. 판정: `d20+ACC>=12`.
- 성공: 모든 생존 적 maxHP 40-60% 피해 / 실패: maxHP 10%
- 레이블: COVER_CRATE->"화물 상자를 던진다", COVER_WALL->"벽 잔해를 무너뜨린다", NARROW->"좁은 통로로 가둔다", 기본->"주변 환경을 활용한다"

### 전투 선택지 빌드 순서

1. 기본 단일 액션 (공격/방어/회피/이동/아이템)
2. 콤보 (스태미나>=2 && ENGAGED/CLOSE)
3. 환경 활용 (envTags 기반)
4. 전투 회피 (항상)
5. 도주 (FLEE)

### 전투 LLM 스킵

| 턴 유형 | LLM 상태 | 이유 |
|---------|----------|------|
| 전투 진입 | PENDING | 분위기 전달 |
| 전투 중 | **SKIPPED** | 속도감 |
| 전투 종료 후 | PENDING | enter 턴 자동 생성 |

클라이언트: `currentNodeType==='COMBAT'` -> `skipLlm:true`. 서버: `llmStatus='SKIPPED'`. 클라이언트: 전투 이벤트를 SYSTEM 메시지로 직접 표시.

---

## 9. ServerResultV1 (전투 출력)

### events[]

kind: `BATTLE | DAMAGE | STATUS | LOOT | GOLD | QUEST | NPC | MOVE | SYSTEM | UI`

전투 턴: MOVE + DAMAGE + UI 조합. STATUS: APPLIED/TICKED/REMOVED. COMBAT_END: VICTORY/DEFEAT/FLEE_SUCCESS.

클라이언트 필터: 기본 SYSTEM/LOOT/GOLD만 표시. LLM 스킵 시 BATTLE/DAMAGE/MOVE/STATUS도 표시.

### diff

| 필드 | 내용 |
|------|------|
| `player` | hp, stamina, status |
| `enemies` | hp, status, distance, angle |
| `inventory` | 변화 시 |
| `meta.battle.phase` | START/TURN/END |
| `meta.battle.rngConsumed` | 소비 난수 수 |

### ui / flags

ui: `availableActions`, `targetLabels`, `actionSlots { base:2, max:3, bonusAvailable }`, `toneHint`

flags: `bonusSlot`, `downed`, `battleEnded`, `nodeTransition`

### enemyNames 체인

`turns.service.ts` -> encounter 기반 맵 구축 -> `combat.service.ts#eName(id)`. ID 패턴: `ENEMY_DOCK_THUG_0` -> `_숫자` 제거 -> content key 조회.

---

## 10. 구현 상태

### 완료

- [x] 명중/피해/치명타 판정 + RNG seed+cursor 결정성
- [x] 상태이상 tick/만료 + STUN 1턴+2턴면역 + DOT(DEF무시)
- [x] HP<=30% 보너스 슬롯 + MOVE distance/angle + FLEE/회피
- [x] 콤보(DOUBLE_ATTACK, ATTACK_DEFEND) + 환경활용(INTERACT)
- [x] 전투 LLM 스킵 + 원자 커밋 + 멱등성 + 선택지 빌드

### 미구현 (v2)

- [ ] 상태이상 부여 시도 (ACC vs RESIST)
- [ ] EVADE 기계적 효과 (자동 miss, ACC -5, SIDE)
- [ ] DEFEND 피해 -30% / USE_ITEM 실제 효과
- [ ] STUN 행동 제한 / 점수 기반 AI / DOT source 추적
- [ ] CC 턴 보너스 비활성 (완전) / 크리티컬 보너스 트리거

---

## 부록

### 모듈 구조

```
engine/combat/   combat.service(진입), hit.service, damage.service, enemy-ai.service
engine/rng/      rng.service (seed PRNG)
engine/stats/    stats.service (Modifier Stack -> Snapshot)
engine/status/   status.service (tick/적용/해제)
engine/input/    rule-parser -> policy -> ActionPlan
engine/nodes/    node-resolver, node-transition.service
engine/rewards/  rewards.service
```

### 에러 정책

409: turn 충돌 / 422: DENY / 500: 내부 오류 (LLM 장애 제외)

### 검증 기준

- 동일 seed + 동일 ActionPlan -> 동일 결과
- STUN 면역 2턴 확인
- HP 30% 트리거는 직접 피해만
- 상태 events (APPLIED/TICKED/REMOVED) 모두 기록

---

## 부록 B: COMBAT 키워드→ActionType 매핑 (정본)

> 원본 참조: [[specs/input_processing_pipeline_v1|input processing pipeline v1]] §4.1

Rule Parser가 자유 텍스트를 전투 ActionType으로 변환할 때 사용하는 전체 키워드 테이블.

| ActionType | 키워드 |
|------------|--------|
| ATTACK_MELEE | 베다, 베어, 벤다, 벤, 벨, 휘두르, 휘둘, 내려치, 내리치, 찌르, 찌른, 찔러, 공격, 때리, 때린, 친다, 쳐, 칼, 검, 도끼, 창, 주먹, 발차기 |
| ATTACK_RANGED | 쏜다, 쏘, 발사, 활, 석궁, 화살, 던지, 던진 |
| EVADE | 구르, 피한, 피하, 회피, 몸을 낮, 닷지, 굴러, 빠져 |
| DEFEND | 막는, 막아, 방패, 받아친, 방어, 지킨, 버틴 |
| MOVE | 오른쪽, 왼쪽, 뒤로, 앞으로, 이동, 다가, 물러, 기둥, 숨 |
| FLEE | 도망, 도주, 달아나, 뛰어, 탈출, 빠져나 |
| USE_ITEM | 포션, 아이템, 사용, 먹, 치료제, 강장제, 연막, 독침 |
| INTERACT | 환경, 문, 닫, 열, 밟 |
| TALK | 묻, 설득, 협박, 대화, 이야기, 말 |
| SEARCH | 조사, 살핀, 둘러, 탐색, 찾 |
| OBSERVE | 관찰, 지켜, 주시, 감시 |

### 파싱 규칙

- `confidence >= 0.7`이면 LLM 호출 없이 확정
- 매칭 실패 시 DEFEND로 축소 (COMBAT) / OBSERVE로 축소 (비전투)
- 복합 문장: 최대 2개 ActionType 추출 (콤보)
- v1: 100% 룰 기반 처리, LLM 보조 파싱 미구현

### Action DSL 카테고리 (전체)

| 카테고리 | ActionType | 설명 |
|----------|------------|------|
| COMBAT | ATTACK_MELEE, ATTACK_RANGED, DEFEND, EVADE, USE_ITEM, MOVE, FLEE, INTERACT | 전투 행동 8종 |
| SOCIAL | TALK, OFFER, OBSERVE, SIGNAL | 사회적 행동 |
| EXPLORATION | MOVE_AREA, SEARCH, STEALTH, PICKLOCK, USE_TOOL, REST | 탐험 행동 |
| SYSTEM | CHECK_STATUS, INVENTORY, NOTE, SAVE_POINT_ACTION | 시스템 행동 |

> v2 예정 확장 타입: COUNTER, POSITIONING, INTERRUPT
