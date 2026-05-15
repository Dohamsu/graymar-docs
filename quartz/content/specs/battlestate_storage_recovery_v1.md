# BattleState Storage & Recovery v1 (Canonical)

## battle_state 저장·복구 정본 설계

------------------------------------------------------------------------

# 0. 이번 세션 확정 사항(요약)

-   **Q1**: battle_state에 버전 필드 포함
    -   `battle_state.version = "battle_state_v1"`
-   **Q2**: EVADE 같은 "소모형(다음 공격 1회)" 효과도 **status로 저장**
    (정본)\
-   **Q3**: RNG 저장은 **seed + cursor(소모 카운터)** 방식\
-   **Q4**: server_result.events에는 **플레이어 가시 이벤트만** 기록
    (AI/난수 추적 없음)\
-   **Q5**: 턴 처리 결과는 **단일 트랜잭션으로 원자 커밋**
    -   `run + battle_state + server_result + turn`

------------------------------------------------------------------------

# 1. battle_state의 역할(SoT)

battle_state는 전투 노드(COMBAT)에서의 **단일 진실 소스(Source of
Truth)**다.

-   재접속/새로고침 시 UI 복구
-   멱등성(같은 turnNo 재요청) 처리 기준
-   리플레이/디버깅의 근거 데이터

------------------------------------------------------------------------

# 2. battle_state 스키마(권장)

> JSON 저장(예: DB jsonb) 기준. 필드는 필요 최소를 포함한다.

``` ts
type BattleStateV1 = {
  version: "battle_state_v1";

  // 전투 페이즈/턴 정합성
  phase: "START" | "TURN" | "END";
  lastResolvedTurnNo: number;

  // RNG 결정성
  rng: {
    seed: string;     // 생성 시 고정
    cursor: number;   // 난수 소비 카운터 (조건부 소비를 허용하므로 필수)
  };

  // 환경 태그(노드 전역)
  env: string[]; // 예: ["OPEN", "COVER"]

  // 플레이어 상태
  player: {
    hp: number;
    stamina: number;
    status: StatusInstance[];
  };

  // 적 상태(다수 적)
  enemies: Array<{
    id: string;
    name?: string;      // 한국어 표시명 (v1 추가)
    hp: number;
    maxHp?: number;     // 최대 HP (환경 활용 피해 계산용, v1 추가)
    status: StatusInstance[];
    personality: "AGGRESSIVE" | "TACTICAL" | "COWARDLY" | "BERSERK" | "SNIPER";
    distance: "ENGAGED" | "CLOSE" | "MID" | "FAR" | "OUT";
    angle: "FRONT" | "SIDE" | "BACK";
  }>;
};
```

------------------------------------------------------------------------

# 3. StatusInstance를 "정본"으로 저장하는 이유(Q2)

EVADE/DEFEND/면역/CC 같은 "임시 효과"는 전투 흐름에서 **정확히
소모/만료**되어야 한다. 따라서 별도 transients 없이 **status 배열이
정본**이 된다.

## 3.1 소모형 효과의 모델링

### 예: EVADE_GUARD (다음 공격 1회 방어 토큰)

-   id: `EVADE_GUARD`
-   duration: 1 (턴 종료 시 제거될 수 있음)
-   stacks: 1
-   power: 1
-   meta:
    -   `meleeAutoMiss: true`
    -   `rangedAccPenalty: -5`
    -   `consumable: true`

> "다음 적 공격 1회 적용 후 즉시 REMOVED" 형태로 처리.

------------------------------------------------------------------------

# 4. RNG 저장 방식: seed + cursor (Q3)

## 4.1 원칙

-   동일 seed + 동일 cursor + 동일 입력(ActionPlan)이면 결과가
    재현되어야 한다.
-   난수는 `cursor` 기반으로 결정적으로 생성한다(예: splitmix/xorshift +
    index 기반).

## 4.2 왜 cursor가 필요한가

조건부 난수 소비(적중 시에만 crit/variance 소비)를 선택했기 때문에, 실행
경로가 달라질 때 소비량이 달라질 수 있다. 따라서 다음 턴의 시작 RNG
위치를 명확히 하는 `cursor`가 필수다.

------------------------------------------------------------------------

# 5. server_result.events 기록 범위(Q4)

`server_result.events`에는 **플레이어 가시 이벤트만** 기록한다.

-   DAMAGE / STATUS / MOVE / QUEST / NPC / SYSTEM / UI 등
-   AI 의사결정, RNG 상세값, 내부 판정 로그는 events에 포함하지 않는다.

장점: - 클라/LLM 서술에 필요한 "서사 이벤트"만 남아 payload가 깔끔해짐 -
운영 중 내부 로직 노출 최소화

> 내부 디버그가 필요하면 별도 `turn_debug_log` 테이블/스토리지로
> 분리(선택).

------------------------------------------------------------------------

# 6. 원자 커밋(단일 트랜잭션) 정책(Q5)

턴 처리 결과는 반드시 **원자적으로 커밋**한다.

## 6.1 커밋 대상

-   `turn` 레코드(입력/ActionPlan/요약/상태)
-   `battle_state` 업데이트
-   `server_result` 저장 (server_result_v1)
-   `run` 메타 업데이트(현재 노드/turnNo 등)

## 6.2 커밋 시점

-   resolve(플레이어 행동 → 적 행동 → downed → bonus → status tick →
    임시 제거 → angle 복귀) 완료
-   `server_result` 생성 완료
-   그 후 단일 트랜잭션으로 커밋

## 6.3 멱등성 처리

-   `(runId, turnNo)`를 유니크 키로 둔다.
-   같은 turnNo 재요청 시:
    -   이미 커밋된 `server_result`를 그대로 반환
    -   `battle_state`도 동일 (재실행 금지)

------------------------------------------------------------------------

# 7. 복구(Recovery) 규칙

## 7.1 GET /runs/{runId}

-   최신 커밋된 `battle_state` + 마지막 `server_result`로 UI 복원
    가능해야 한다.
-   LLM 호출 없이도 "전투 HUD/상태/타겟/행동 슬롯" 표시는 가능해야 한다.

## 7.2 중간 장애/실패 처리

턴 처리 중 장애가 발생하면:

-   트랜잭션이 커밋되지 않았으므로 `battle_state`는 이전 상태 유지
-   클라는 재시도 가능(같은 turnNo로)

------------------------------------------------------------------------

# 8. 체크리스트

-   [ ] battle_state에 version 포함
-   [ ] status가 정본(소모형 효과 포함)
-   [ ] rng: seed + cursor 저장
-   [ ] events는 플레이어 가시 이벤트만
-   [ ] 단일 트랜잭션 원자 커밋
-   [ ] (runId, turnNo) 멱등성 보장

------------------------------------------------------------------------

# 부록: battle_state 예시

``` json
{
  "version": "battle_state_v1",
  "phase": "TURN",
  "lastResolvedTurnNo": 12,
  "rng": { "seed": "run_abc_seed_001", "cursor": 57 },
  "env": ["OPEN"],
  "player": {
    "hp": 82,
    "stamina": 1,
    "status": [
      { "id": "EVADE_GUARD", "sourceId": "PLAYER", "applierId": "player", "duration": 1, "stacks": 1, "power": 1, "meta": { "meleeAutoMiss": true, "rangedAccPenalty": -5, "consumable": true } }
    ]
  },
  "enemies": [
    { "id": "enemy_01", "hp": 37, "status": [], "personality": "TACTICAL", "distance": "MID", "angle": "SIDE" }
  ]
}
```

------------------------------------------------------------------------

# 결론

본 문서는 battle_state 저장/복구의 정본이며, Combat Resolve Engine +
Status System과 결합되어 재접속 복구, 결정성, 멱등성, 운영 안정성을
보장한다.
