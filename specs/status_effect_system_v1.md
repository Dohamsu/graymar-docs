# Status Effect System v1 (Canonical)

## 상태이상 시스템 정본 설계 (저장 스키마 + 엔진 통합 + 가드레일)

> 이 문서는 Combat Resolve Engine v1에 **직접 연결 가능한 정본**입니다.\
> battle_state 저장 구조, 적용/중첩/틱 처리, server_result 이벤트 기록,
> 악용 방지(가드레일)까지 포함합니다.

------------------------------------------------------------------------

# 0. 이번 세션에서 확정된 결정사항(요약)

-   **Q1**: battle_state에 상태이상을 **객체 배열로 직접 저장**
    -   `playerState.status: StatusInstance[]`\
    -   `enemiesState[i].status: StatusInstance[]`
-   **Q2**: StatusInstance 최소 필드 = 실행에 필요한 값 포함
    -   `{ id, sourceId, applierId, duration, stacks, power }`
-   **Q3**: 상태 정의는 **DB 테이블**(`status_definitions`)에서 관리
-   **Q4**: 적용 판정(저항) = `d20 + attacker.ACC >= 10 + target.RESIST`
-   **Q5**: stackable=true면 **stacks cap(예: 5) + duration 갱신**
-   **Q6**: duration 감소/틱 = **턴 종료 단계**에서 처리
-   **Q7**: DOT 피해 = **방어 무시**, `TAKEN_DMG_MULT`는 적용
-   **Q8**: DOT 피해 기준 = **target.maxHP 기반 %**
-   **Q9**: status tick은 **RNG 사용 안 함(결정적)**
-   **Q10**: events에 `APPLIED/REMOVED/TICKED` **모두 기록**
-   **Q11**: 상태 부여 시도 = **ATTACK 1회당 1개만**
-   **Q12**: STUN 제한 = **면역 쿨다운(2턴) + duration 1턴 고정**
-   **Q13**: 보너스 슬롯 가드레일
    -   STUN/CC가 걸린 턴에는 **보너스 슬롯 트리거 비활성**
    -   status tick으로 HP30% 진입한 경우 **보너스 슬롯 트리거 비활성**

------------------------------------------------------------------------

# 1. 저장 스키마 (BattleState 정본 확장)

## 1.1 BattleState 내 저장 위치

-   `battle_state.player_state.status[]`
-   `battle_state.enemies_state[].status[]`

> battle_state는 **복구/리플레이용 SoT**이므로, 상태이상 인스턴스를 직접
> 포함한다.

## 1.2 StatusInstance (저장/실행 최소 필드)

``` ts
type StatusInstance = {
  id: string;                 // status definition id (ex: "BLEED", "STUN")
  sourceId: "PLAYER" | "ENEMY";
  applierId: string;          // 부여자 엔티티 id (ex: "player", "enemy_01")
  duration: number;           // 남은 턴 수
  stacks: number;             // 현재 스택 수 (stackable=true일 때 의미)
  power: number;              // 상태 강도(레벨/계수). v1은 1로 시작 권장
  meta?: Record<string, any>; // 선택(디버깅/특성 연동)
};
```

## 1.3 Status Definitions (DB)

DB 테이블 `status_definitions`를 정본으로 둔다.

필수 컬럼 예시:

-   `id` (PK)
-   `kind` (BUFF/DEBUFF/DOT/CC 등)
-   `stackable` (bool)
-   `max_stacks` (int) --- v1 권장: 5
-   `base_duration` (int)
-   `tick_type` (NONE/DOT 등)
-   `dot_percent_of_maxhp` (float) --- DOT일 때 사용
-   `modifiers_json` (json) --- 적용 시 부여되는 modifier 정의
-   `notes` (text)

> 실행 시점에는 **definition을 읽고**, 인스턴스의
> `power/stacks/duration`을 반영해 계산한다.

------------------------------------------------------------------------

# 2. 적용(저항) 규칙

## 2.1 상태 부여 시도 횟수 제한 (가드레일)

-   **ATTACK 1회당 상태 부여 시도는 1개만** 허용한다.
-   MOVE/EVADE/DEFEND/FLEE는 기본적으로 상태 부여 시도 없음(v1).

## 2.2 적용 판정

``` text
d20 + attacker.ACC >= 10 + target.RESIST
```

-   성공 시: 상태 적용
-   실패 시: 아무 일도 없음(단, 이벤트는 남길 수 있음: 선택)

## 2.3 적용 대상 선택

-   기본: 공격의 `targetId`
-   광역/다중 타겟은 v2로 미룸(필요 시 `targets[]` 확장)

------------------------------------------------------------------------

# 3. 중첩(Stacks) & Duration 정책

## 3.1 stackable=true (스택 가능)

-   `stacks = min(stacks + 1, maxStacks)`
-   `duration = max(duration, newDuration)` (duration 갱신)

권장 기본값:

-   `maxStacks = 5`
-   `newDuration = definition.base_duration`

## 3.2 stackable=false (스택 불가)

-   `stacks = 1`
-   `duration = max(duration, newDuration)` (또는 덮어쓰기)
    -   v1 권장: `max()`

------------------------------------------------------------------------

# 4. Tick 처리(턴 종료) 및 RNG

## 4.1 Tick 타이밍

Combat 턴 종료 처리 순서의 **5번 단계**에서 수행:

1)  tickEffect 실행\
2)  `duration -= 1`\
3)  `duration <= 0`이면 제거

## 4.2 Tick은 RNG를 사용하지 않는다

-   DOT 피해는 **결정적**(항상 동일 결과)

------------------------------------------------------------------------

# 5. DOT(지속 피해) 규칙

## 5.1 DOT 피해 계산(방어 무시)

DOT는 DEF를 무시한다. 단, **TAKEN_DMG_MULT는 적용**한다.

``` text
rawDot = floor(target.maxHP * dotPercent * stacks * power)

dot = floor(rawDot * target.TAKEN_DMG_MULT)

if dot < 1 then dot = 1
```

-   `dotPercent`는 definition에서 가져온다.
-   `stacks`는 인스턴스 스택.
-   `power`는 상태 강도(기본 1).

## 5.2 DOT 최소 피해

-   tick이 발생하면 최소 1 피해 보장(전투 템포 정체 방지)

------------------------------------------------------------------------

# 6. CC(하드 컨트롤) 가드레일: STUN

STUN은 악용 루프의 핵심이므로 v1부터 강하게 제한한다.

## 6.1 STUN duration 고정

-   STUN은 **duration 1턴 고정**
-   재적용 시 duration 갱신 불가(항상 1)

## 6.2 STUN 면역 쿨다운(2턴)

-   STUN이 제거되거나 만료되면, 대상에게 `STUN_IMMUNE`를 **2턴** 부여
-   `STUN_IMMUNE`가 있는 동안 STUN 적용 시도는 **자동 실패**

> `STUN_IMMUNE`는 내부 상태로만 두고, 플레이어 노출 여부는 UI 정책으로
> 결정.

------------------------------------------------------------------------

# 7. Modifier 적용 규칙 (스탯 파이프라인 연결)

상태 정의에 포함된 modifiers를 Modifier Stack에 삽입:

-   BUFF 계열: priority 300
-   DEBUFF 계열: priority 400

예시(WEAKEN):

-   ATK PERCENT -0.15 @400

예시(FORTIFY):

-   DEF PERCENT +0.20 @300
-   TAKEN_DMG_MULT PERCENT -0.10 @300

> 실제 적용은 Combat Resolve Engine의 스탯 계산기에 위임한다.

------------------------------------------------------------------------

# 8. server_result.events 기록 정책(정본)

상태 관련 이벤트는 **모두 기록**한다.

## 8.1 이벤트 종류

-   `STATUS_APPLIED`
-   `STATUS_TICKED`
-   `STATUS_REMOVED`

> 스키마 상 kind는 `STATUS`로 두고, `tags` 또는 `data.subkind`로
> 구분한다.

## 8.2 data 필드 권장 구조

``` json
{
  "subkind": "APPLIED | TICKED | REMOVED",
  "statusId": "BLEED",
  "targetId": "enemy_01",
  "applierId": "player",
  "duration": 3,
  "stacks": 2,
  "power": 1,
  "tickDamage": 6
}
```

-   APPLIED/REMOVED에는 `tickDamage` 없음
-   TICKED에는 `tickDamage` 포함

------------------------------------------------------------------------

# 9. 보너스 슬롯(1턴 1회)과의 상호작용 가드레일

## 9.1 STUN/CC가 걸린 턴: 보너스 슬롯 트리거 비활성

-   대상 또는 공격자가 **하드 CC 영향**(예: STUN) 하에 있는 턴에는
    -   보너스 슬롯 트리거를 **발생시키지 않는다**

> 목적: STUN 기반 "무한 보너스" 루프 차단

## 9.2 status tick으로 HP30% 진입: 트리거 비활성

-   "HP 30% 이하 진입" 보너스는 **직접 공격 피해로 인한 진입**에만 허용
-   DOT tick으로 30% 이하 진입한 경우는 트리거하지 않는다

> **v1 구현 현황**: HP ≤ 30% 보너스 슬롯 트리거는 구현됨. 단, DOT source 추적을 통한 "직접 공격 피해에 의한 진입만 허용" 구분은 미구현 — 현재는 DOT tick으로 진입해도 보너스 슬롯이 트리거될 수 있음. v2에서 source 추적 추가 예정.

------------------------------------------------------------------------

# 10. v1 기본 상태 세트(권장)

> 실제 수치는 `status_definitions`에서 조정 가능. 아래는 추천 시작점.

## BLEED (DOT)

-   kind: DEBUFF/DOT
-   stackable: true, maxStacks: 5
-   base_duration: 3
-   dotPercentOfMaxHP: 0.03

## POISON (DOT + 경미한 취약)

-   kind: DEBUFF/DOT
-   stackable: true, maxStacks: 5
-   base_duration: 3
-   dotPercentOfMaxHP: 0.02
-   modifiers: TAKEN_DMG_MULT PERCENT +0.05 @400 (선택)

## STUN (CC)

-   kind: DEBUFF/CC
-   stackable: false
-   base_duration: 1 (고정)
-   onApply: 대상에게 "행동 제한" 플래그 부여 (예: actionSlots.base를
    0으로 제한하거나, availableActions를 DEFEND만 허용 등)
-   onRemove: STUN_IMMUNE 2턴 부여

> **v1 구현 현황**: STUN duration 1턴 고정 + 면역 쿨다운 2턴은 구현됨. 단, `actionSlots.base` 제한이나 `availableActions` DEFEND 제한 등 **행동 제한 기계적 효과는 미구현**. 현재 STUN은 상태 플래그로만 존재하며, 실제 행동 차단은 v2에서 추가 예정.

## WEAKEN (약화)

-   kind: DEBUFF
-   stackable: false
-   base_duration: 2
-   modifiers: ATK PERCENT -0.15 @400

## FORTIFY (강화)

-   kind: BUFF
-   stackable: false
-   base_duration: 2
-   modifiers:
    -   DEF PERCENT +0.20 @300
    -   TAKEN_DMG_MULT PERCENT -0.10 @300

------------------------------------------------------------------------

# 11. 엔진 통합 체크리스트

resolveCombatTurn 구현 시 아래를 보장한다:

-   [ ] ~~ATTACK resolve 중 "상태 부여 시도"는 1회만 수행(Q11)~~ — ❌ 미구현 (v2)
-   [ ] ~~적용 판정 수식은 ACC vs RESIST(Q4)~~ — ❌ 미구현 (상태 부여 자체가 미구현)
-   [x] status tick은 턴 종료 단계에서 수행(Q6) — ✅ 구현됨
-   [x] tick은 RNG 사용 없음(Q9) — ✅ 구현됨
-   [x] DOT는 DEF 무시, TAKEN_DMG_MULT 적용(Q7) — ✅ 구현됨
-   [x] 모든 status 이벤트 APPLIED/TICKED/REMOVED 기록(Q10) — ✅ 구현됨
-   [x] STUN은 1턴 고정 + 2턴 면역(Q12) — ✅ 구현됨
-   [ ] ~~CC 턴에는 보너스 슬롯 트리거 비활성(Q13-B)~~ — ⚠️ 부분 구현 (STUN 플래그는 존재하나 행동 제한 미구현)
-   [ ] ~~DOT tick으로 HP30% 진입 시 보너스 슬롯 트리거 비활성(Q13-C)~~ — ❌ 미구현 (source 추적 없음)

------------------------------------------------------------------------

# 부록: battle_state 예시 스니펫

``` json
{
  "playerState": {
    "hp": 82,
    "stamina": 1,
    "status": [
      { "id": "FORTIFY", "sourceId": "PLAYER", "applierId": "player", "duration": 2, "stacks": 1, "power": 1 }
    ]
  },
  "enemiesState": [
    {
      "id": "enemy_01",
      "hp": 37,
      "status": [
        { "id": "BLEED", "sourceId": "PLAYER", "applierId": "player", "duration": 3, "stacks": 2, "power": 1 }
      ],
      "personality": "TACTICAL",
      "distance": "MID",
      "angle": "SIDE"
    }
  ]
}
```

------------------------------------------------------------------------

# 결론

이 문서는 v1 상태이상 시스템의 **정본 설계**이며, 전투 수치 엔진(Combat
Resolve Engine)과 결합해 결정성/복구/악용 방지를 동시에 만족하도록
구성되었다.
