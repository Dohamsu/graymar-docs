# Combat System v1

> 통합 설계서: 전투 스탯/공식 (정본) + Action Economy + Positioning + Enemy AI + Multi-Target
> 목적: 자유 입력 기반 전투에 전략적 깊이와 밸런스 안정성 부여

---

# Part 0: Combat Stats & Formulas (정본)

---

## 1. 전투 철학

- D20 기반 명중 판정
- 비율형 방어 계산
- 보너스 슬롯 시스템
- 최대 3 Action (기본 2 + 보너스 1)

---

## 2. 스탯 정의 (정본)

| 스탯 | 설명 | 사용처 |
|------|------|--------|
| HP | 현재 체력 | 피해 적용 |
| MaxHP | 최대 체력 | HP 상한 |
| Stamina | 현재 스태미나 | Action 비용 |
| MaxStamina | 최대 스태미나 | Stamina 상한 |
| ATK | 공격력 | 피해 공식 |
| DEF | 방어력 | 피해 감소 공식 |
| ACC | 명중 보정 | 명중 공식 |
| EVA | 회피 보정 | 명중 공식 (방어측) |
| CRIT | 치명타 확률 | 치명타 판정 |
| CRIT_DMG | 치명타 배율 | 기본 1.5, 성장/장비로 최대 2.5 |
| RESIST | 상태이상 저항 | DOWNED 저항, 상태이상 저항 |
| SPEED | 행동 순서 보정 | 다수 적 전투 시 턴 내 resolve 순서 결정 |
| DAMAGE_MULT | 피해 배율 | 기본 1.0, 버프/디버프로 변동 |
| HIT_MULT | 명중 배율 | 기본 1.0, ACC에 곱연산 적용 |
| TAKEN_DMG_MULT | 받는 피해 배율 | 기본 1.0, 방어/취약 상태로 변동 |

> SPEED: 다수 적 전투에서 동일 턴 내 행동 resolve 순서를 결정한다. 단일 적 전투에서는 항상 플레이어 우선.
> CRIT_DMG: 기본값 1.5. GP 투자(Tactical 트리) 또는 RUN 내 장비로 상승 가능.

---

## 3. 명중 공식

roll = d20

hit if:
roll + floor(ACC * HIT_MULT) >= 10 + targetEVA

자동 실패: roll == 1
자동 성공: roll == 20

> HIT_MULT는 기본값 1.0. 버프/디버프로 변동 가능. 정본: `combat_resolve_engine_v1.md` §3.

---

## 4. 피해 공식

baseDamage = ATK * (100 / (100 + effectiveDEF))
dmg = baseDamage * random(0.9~1.1)
if (isCrit) dmg *= CRIT_DMG
dmg *= DAMAGE_MULT
dmg *= TAKEN_DMG_MULT
dmg = floor(dmg), 적중 시 최소 1

> 전체 계산 순서 정본: `combat_resolve_engine_v1.md` §5

---

## 5. 치명타

critChance = clamp(CRIT, 0, 50%)

critMultiplier = CRIT_DMG (기본 1.5, 최대 2.5)

치명타 시 DEF 30% 무시

---

## 6. 상태이상

> 정본: `status_effect_system_v1.md` §10

| Status | 종류 | 중첩 | 최대 | 지속 | 효과 |
|--------|------|------|------|------|------|
| BLEED | DEBUFF/DOT | 가능 | 5 | 3턴 | maxHP 3%/스택 |
| POISON | DEBUFF/DOT | 가능 | 5 | 3턴 | maxHP 2%/스택 + TAKEN_DMG_MULT +5% |
| STUN | DEBUFF/CC | 불가 | - | 1턴(고정) | 행동 불가, 해제 시 STUN_IMMUNE 2턴 |
| WEAKEN | DEBUFF | 불가 | - | 2턴 | ATK -15% |
| FORTIFY | BUFF | 불가 | - | 2턴 | DEF +20%, TAKEN_DMG_MULT -10% |

> **v1 구현 현황**: ATTACK 시 상태이상 부여 시도(d20 + ACC >= 10 + RESIST)는 미구현. 상태이상 tick/만료 처리는 구현됨.

---

## 7. 보너스 슬롯 트리거

> 정본: `combat_resolve_engine_v1.md` §10

발동 조건 (결정적, 1턴 1회 제한):

- 치명타 발생
- 완벽 회피 (EVADE 성공 + SIDE 확보)
- 적 HP가 30% 이하로 진입

> **v1 구현 현황**: **HP ≤ 30% 진입**만 구현됨 (직접 공격 피해로 진입 시에만 트리거). 크리티컬, 완벽 회피 조건은 미구현. CC 상태에서는 보너스 슬롯 비활성. TacticalScore 기반 확률 공식은 v2 확장 후보.

---

## 8. Stamina 규칙

### 소모
- Action 1개 = 1 stamina
- Bonus Action = 2 stamina (Tactical 특성으로 1 가능)
- stamina 0 시 강행 가능 (ACC -5, damage -20%)

### 회복
- 전투 중: 턴당 자연 회복 없음
- DEFEND 선택 시: +1 stamina (행동 포기 대가)
- REST 노드: MaxStamina까지 전량 회복
- EVENT/SHOP 노드 종료 시: +2 stamina (비전투 노드 보너스)

---

## 9. FLEE (도주)

roll = d20

flee_success if:
  roll + SPEED >= 12 + (engaged_enemy_count * 2)

성공 → 전투 즉시 종료, NODE_ENDED 처리
실패 → 턴 소모

- FLEE 성공 시 전리품 없음
- 1턴에 FLEE만 가능 (다른 Action과 결합 불가)
- ENGAGED 적이 없으면 자동 성공

> **v1 구현 현황**: FLEE 스태미나 비용은 **1** (일반 Action과 동일). 기회공격은 미구현. 설계안의 2 스태미나 소모는 v2 밸런싱 시 재검토.

---

## 10. DOWNED

HP 0 시 마지막 저항 (SPEED는 DOWNED 판정에 영향 없음):

d20 + RESIST >= 15
성공 → HP 1
실패 → DOWNED

---

# Part 1: Action Economy

---

## 11. Action Economy 기본 원칙

- 한 Step(=Turn)당 기본 Action Slot = **2**
- 조건 만족 시 Bonus Slot **+1**
- 최대 Action Slot = **3**
- 3개 초과는 절대 불가 (불변 규칙)
- 이 규칙은 플레이어와 AI 모두에 동일하게 적용

---

## 12. Action Unit 정의

Action Unit = 서버 DSL 기준 판정 단위 1회

### 전투 Action (resolveCombatTurn 처리 범위)

- ATTACK_MELEE
- ATTACK_RANGED
- EVADE
- DEFEND
- MOVE
- USE_ITEM
- FLEE (§9 참조)
- INTERACT (전투 중 환경 상호작용)

### 비전투 Action (EVENT/REST/SHOP 노드 전용)

- TALK
- SEARCH
- OBSERVE

복합 문장은 Action Unit 여러 개로 분해됨.

---

## 13. 입력 → 슬롯 소모 규칙

### 예시 1: 정상 처리

입력:
"굴러 피하며 화살을 쏜다"

DSL:
1) EVADE
2) ATTACK_RANGED

→ 슬롯 2 소모 (정상 처리)

### 예시 2: 초과 입력 처리

입력:
"굴러 피하고 화살을 쏜 뒤 달려가 베어버린다"

DSL:
1) EVADE
2) ATTACK_RANGED
3) ATTACK_MELEE

→ 기본 슬롯 초과

처리:

- 기본 2개 실행
- 나머지는 TRANSFORM
  - 연출로만 반영
  - 또는 다음 턴 의도 힌트 제공

### 예시 3: 다수 대상 행동

입력:
"왼쪽 적을 밀어내고, 오른쪽 적에게 화살을 쏜다"

DSL:
1) PUSH (enemy_left)
2) ATTACK_RANGED (enemy_right)

→ 슬롯 2 소모 (정상 처리)

---

## 14. Bonus Slot 조건

아래 조건 중 하나 만족 시 +1 슬롯 부여

### 14.1 전투 조건

- 크리티컬 성공
- 적이 기절/넘어짐 상태
- 적이 상태이상으로 행동 불가
- 완벽 회피 성공
- 약점 노출 상태

### 14.2 사회/이벤트 조건

- 설득 대성공
- 상대 감정 붕괴
- 중요한 단서 발견
- NPC 신뢰도 임계치 돌파

### 14.3 탐험 조건

- 함정 완벽 해체
- 비밀 통로 발견
- 환경 이점 확보

---

## 15. Bonus Slot 처리 방식

보너스 슬롯은:

- 같은 턴 내 즉시 사용 가능
- 자동 부여가 아니라 "사용 가능 상태"
- UI에서 시각적으로 표시
- Bonus 연쇄 발생 금지 (1턴 1회 제한)
- 다음 턴으로 이월 불가

---

## 16. 스태미나 비용 모델

> 정본 공식: Part 0 §8 참조

복합 행동 비용 예시:
1번째 = 1, 2번째 = 1, 보너스 = 2 (리스크 증가)

---

# Part 2: Tactical Positioning System

---

## 17. 위치 시스템 설계 철학

- 위치는 단순 연출이 아니라 실제 판정 요소
- 그러나 그리드 기반 SRPG처럼 복잡하게 만들지 않음
- "관계 기반 위치 시스템"으로 설계
- 절대 좌표가 아닌 상대적 상태로 관리

---

## 18. 위치 모델 (Grid 없음)

### 18.1 거리 상태 (Distance State)

- **ENGAGED** (근접 교전)
- **CLOSE** (근접 직전)
- **MID** (중거리)
- **FAR** (원거리)
- **OUT** (교전 이탈)

다수 적 전투 시 거리 상태는 "쌍(pair)" 기준으로 각 적과 개별 관리:

```
distance(player, enemy_1)
distance(player, enemy_2)
distance(player, enemy_3)
```

### 18.2 방향 상태 (Facing / Angle)

- **FRONT** — 기본 상태
- **SIDE** — 측면
- **BACK** — 후방

### 18.3 환경 상태 (Environment Tags)

기본 태그 6종. 콘텐츠는 `기본태그_세부` 형식으로 하위타입을 사용할 수 있다.
엔진은 언더스코어 앞 접두사를 기본 태그로 인식한다 (예: `COVER_CRATE` → `COVER` 효과 적용).

- **COVER** (엄폐) — 하위: COVER_CRATE, COVER_WALL, COVER_PILLAR 등
- **HIGH_GROUND** (고지)
- **LOW_GROUND** (저지)
- **OBSTACLE** (장애물) — 하위: OBSTACLE_BARREL, OBSTACLE_RUBBLE 등
- **NARROW** (좁은 공간)
- **OPEN** (개활지)

---

## 19. 위치 변경 Action

MOVE는 단순 연출이 아니라 실제 상태 전이

예:

MOVE + EVADE →
- ENGAGED → MID
- 또는 SIDE 확보 시 BACK 전환 가능

다수 적 전투 시:
- 특정 대상과 거리 변화
- 다른 대상은 유지
- 특정 방향 이동 시 일부 적에게 BACK 노출 가능

### 복잡도 관리 (v1)

- 실제 좌표 없음
- 한 턴에 최대 1단계 거리 변화
- 방향은 조건 충족 시에만 변경
- 환경 태그는 Node 시작 시 결정

---

## 20. 위치 기반 판정 영향

### 20.1 거리 영향

| Distance State | 근접 공격 | 원거리 공격 |
|---|---|---|
| ENGAGED | 보너스 | 불리 |
| FAR | 접근 필요 | 보너스 |

### 20.2 방향 영향

| Angle State | 효과 |
|---|---|
| BACK | 치명타 확률 증가, 방어 무시 일부 적용 |
| SIDE | 방어 감소 |
| FRONT | 기본 상태 |

### 20.3 환경 영향

| Environment Tag | 효과 |
|---|---|
| COVER | 원거리 회피 보너스 |
| HIGH_GROUND | 명중/관통 보너스 |
| LOW_GROUND | 회피 페널티 |
| NARROW | 다중 행동 페널티 |
| OPEN | 광역 공격 보너스 (다수 전투 시) |

---

## 21. Action Slot과 위치 시스템 연동

예:

"기둥 뒤로 구르며 화살을 쏜다"

1) MOVE → COVER 상태 획득
2) ATTACK_RANGED → COVER 보너스 적용

→ 슬롯 2 소모

---

# Part 3: Tactical Enemy AI

---

## 22. AI 설계 철학

- AI는 단순 랜덤이 아니다
- AI는 목표를 가진다
- AI는 현재 상태를 평가한다
- AI는 확률 기반 선택을 한다
- 모든 결정은 서버 RNG 기반으로 재현 가능해야 한다

---

## 23. AI 의사결정 입력 상태

- player_distance_state
- enemy_distance_state
- angle_state
- environment_tags
- enemy_hp_ratio
- player_hp_ratio
- enemy_personality
- status_effects

---

## 24. AI 행동 카테고리

- **APPROACH** (거리 좁히기)
- **RETREAT** (거리 벌리기)
- **FLANK** (측면 확보)
- **SEEK_COVER** (엄폐 확보)
- **ATTACK_MELEE**
- **ATTACK_RANGED**
- **SPECIAL** (특수기)
- **INTERRUPT**
- **DEFENSIVE_STANCE**

---

## 25. AI Personality 모델

각 적은 personality를 가진다.

| Personality | 특성 |
|---|---|
| **AGGRESSIVE** | 접근 우선, 방어 적음 |
| **TACTICAL** | 위치 계산, 엄폐/측면 활용 |
| **COWARDLY** | HP 낮으면 도주/후퇴 |
| **BERSERK** | 체력 낮을수록 공격성 증가 |
| **SNIPER** | 거리 유지 최우선 |

---

## 26. AI 의사결정 알고리즘

### 26.1 점수 기반 선택

각 행동에 score 계산:

```
score =
  personality_weight
+ tactical_bonus
+ environment_bonus
+ random_noise
```

최종: `roulettePick(score 기반)`

### 26.2 확률 균형

AI는 항상 최적 선택만 하지 않는다.

- 10~20% 확률로 비최적 선택
- 예측 가능성 완화
- 인간적인 실수 표현 가능

---

## 27. AI 전술 예시

### 예시 1: 플레이어가 COVER 상태

- FLANK 가중치 상승
- APPROACH + SIDE 시도

### 예시 2: 플레이어가 FAR 거리

- AGGRESSIVE → APPROACH 우선
- SNIPER → ATTACK_RANGED 유지

### 예시 3: 플레이어가 BACK 확보

- TURN(각도 회복) 우선
- DEFENSIVE_STANCE

---

# Part 4: Multi-Target Combat

---

## 28. 다수 전투 기본 구조

- 플레이어: 1명
- 적: 1~N명
- 각 적은 독립 AI + 독립 위치 상태 보유

---

## 29. 다수 전투 상태 모델

> battle_state 구조 정본: `schema/07_database_schema.md`, `schema/OpenAPI 3.1.yaml` BattleState
> 핵심: distance/angle은 enemies에만 존재 (per-enemy 정본)

---

## 30. 다수 전투 위치 전술

### 예시

- enemy_1: ENGAGED
- enemy_2: MID
- enemy_3: FAR

플레이어가 MOVE하면:

- 특정 대상과 거리 변화
- 다른 대상은 유지
- 또는 특정 방향 이동 시 일부에게 BACK 노출 가능

---

## 31. AoE(범위 공격) 정책

v1 기본:

- 광역 스킬은 특수 행동으로만 허용
- 기본 공격은 단일 타겟

환경 연동:

- NARROW 공간에서 범위 페널티
- OPEN 공간에서 광역 보너스

---

## 32. 협동 AI (전술형 핵심)

AI는 다음 전략 수행 가능:

- **FLANK**: 서로 다른 각도 확보
- **PRESSURE**: 한 명 ENGAGED 유지
- **DISTRACT**: 한 명이 엄폐 파괴
- **PIN**: 플레이어 거리 이동 제한

---

## 33. AI 턴 처리 순서 및 RNG 소비

### 턴 순서

1) 플레이어 행동 resolve
2) 적1 resolve
3) 적2 resolve
4) 적3 resolve

순서는 seed 기반 고정

### RNG 소비 순서 (결정성 보장)

각 턴 RNG 소비 순서 고정:

1) 플레이어 행동 판정
2) 적 순서 정렬
3) 적1 판정
4) 적2 판정
5) 적3 판정

추가 난수 소비는 절대 순서 변경 금지

> ActionUnit당 상세 소비 순서(hitRoll → varianceRoll → critRoll, 조건부 소비)와 seed+cursor 저장 방식은 `combat_engine_resolve_v1.md` §2.1 및 `battlestate_storage_recovery_v1.md` §4 참조.

---

## 34. 난이도 균형 장치

다수 적 전투 시:

- 플레이어 Bonus 조건 완화
- 완벽 회피 성공 시 인접 적에게도 거리 변화
- 적 수가 많을수록 AI 개별 정확도 약간 감소

---

# Part 5: 공통 시스템

---

## 35. 저장 모델

> 저장 구조 정본: `schema/07_database_schema.md`
> AI 턴별 저장: ai_selected_actions[], ai_score_map, rng_state (재현 가능성 확보)

---

## 36. UX 설계 (통합)

### Action Slot 표시

```
[●][●] 기본
[★] 보너스 (조건 충족 시 점등)
```

### 위치/전투 묘사 원칙

LLM은 정성적으로 표현하되 수치 직접 노출 금지

- "기둥 뒤로 몸을 숨겼다" (COVER)
- "측면을 잡았다" (SIDE)
- "등을 보이고 있다" (BACK)

### 다수 전투 묘사

플레이어가 상황을 공간적으로 인지 가능해야 함

- "왼쪽 리자드맨이 파고든다"
- "뒤쪽 궁수가 활을 당긴다"
- "측면이 비어 있다"

---

## 37. 확장 참고

- Action Economy: 보너스 조건 완화, 슬롯 0.5 소모 (고급 단계)
- Positioning: 지형 파괴, 이동 제약 상태이상
- Enemy AI: 둘러싸기, 함정 유도, 환경 파괴
