# Input Processing Pipeline v1

> 플레이어의 자유 텍스트 입력을 게임 전반에서 허용하되,
> 서버(SoT)가 결정적으로 판정할 수 있도록 "의도(Intent) → 규칙(Action)"으로 환원한다.
> 비용 안정성, 결정성, 자유도의 균형을 유지하면서 COOPERATIVE_TRANSFORM(유연/협조적) 정책을 기본으로 운용한다.

---

## 1. 기본 원칙

- 플레이어 입력은 **항상 자유 텍스트**를 허용한다.
- 서버는 입력을 그대로 실행하지 않는다.
- 서버는 입력을 **제한된 "행동 DSL"**로 환원한 뒤 판정한다.
- LLM은 "해석/요약"을 돕지만, **결정은 서버**가 한다.
- 자유도와 규칙의 균형이 핵심이다:
  - 플레이어는 자유롭게 입력
  - 서버는 제한된 행동 타입으로 환원
  - LLM은 해석 보조
  - 최종 판정은 서버

### 1.1 기대 효과

- 몰입감 증가
- "내가 대응했다"는 느낌 강화
- 스토리 중심 RPG와 궁합이 좋음
- 빌드 없이도 전략성 확보 가능

### 1.2 리스크 인식

- 입력 해석 오류 가능성
- 악의적 입력 시도
- 과도한 자유도 요구
- → 해결: Intent 제한 레이어(Policy Check)로 통제

---

## 2. 처리 파이프라인

### 2.1 전체 흐름

```
Raw Input (자유 텍스트)
   ↓
Rule Parser (1차 룰 기반 파싱)
   ↓
[성공] → Intent 확정
[불명확] → LLM 보조 파싱
   ↓
Intent Merge (RULE / LLM / MERGED 판단)
   ↓
Policy Check (허용/변환/부분/거부)
   ↓
Action Plan 생성 (서버 규칙 형태 DSL)
   ↓
Resolve (판정) + server_result 생성 (트랜잭션)
   ↓
LLM 내러티브 생성 (서술만)
```

### 2.2 단계별 역할 요약

| 단계 | 역할 | 담당 |
|------|------|------|
| RawInput 수신 | 자유 텍스트 수집 | 클라이언트 |
| Intent Parse | 입력 구조화 (룰 → LLM fallback) | 서버 + LLM |
| Policy Check | 허용/금지/변환 판정 | 서버 |
| Action Plan 생성 | 서버 규칙 형태로 변환 | 서버 |
| Resolve | 확률 판정 + 결과 확정 | 서버 |
| 내러티브 생성 | server_result 기반 서술 | LLM |

---

## 3. Intent 모델 & JSON Schema

### 3.1 Intent JSON (v1)

```json
{
  "inputText": "칼을 피하고 오른쪽으로 굴러 화살을 쏜다",
  "intents": ["EVADE", "ATTACK_RANGED", "MOVE"],
  "targets": ["lizardman_01"],
  "constraints": ["right", "roll"],
  "riskLevel": "MED",
  "illegalFlags": []
}
```

### 3.2 필드 정의

| 필드 | 설명 |
|------|------|
| `inputText` | 원문 |
| `intents` | 의도 배열 (복합 가능) |
| `targets` | 타겟 (인물/사물/장소) |
| `constraints` | 방식 수식어 ("조심히", "빨리", "몰래" 등) |
| `riskLevel` | LOW / MED / HIGH (LLM이 추정) |
| `illegalFlags` | 규칙 위반 가능성 표식 |

### 3.3 전투 특화 Intent 출력 예시

```json
{
  "source": "RULE",
  "confidence": 0.85,
  "primary": "ATTACK",
  "modifiers": ["EVADE"],
  "weapon": "bow",
  "direction": "right",
  "intents": ["EVADE", "ATTACK_RANGED"],
  "targets": ["lizardman_01"]
}
```

- `source`: 파싱 출처 (RULE / LLM / MERGED)
- `confidence`: 신뢰도 수치 (0.0~1.0)

---

## 4. Intent Parsing 전략 (Rule Parser + LLM)

### 4.1 1차 룰 기반 파서 (Primary Parser)

- 대부분의 일반적인 입력은 룰 기반으로 처리
- LLM 호출 최소화
- 확정적인 DSL 생성

#### 키워드 매핑 (v1 구현 기준, 정본: `rule-parser.service.ts`)

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

#### 파싱 결과 분류

- ATTACK / EVADE / DEFEND / MOVE / USE_ITEM / COMBO (2개 이상 결합) / INVALID

### 4.2 LLM 보조 파싱 조건

`confidence >= 0.7`이면 LLM 호출 없이 룰 파서 결과를 사용한다. 다음 조건일 때만 LLM 호출:

- 룰 매칭 실패
- 복합 문장 구조
- 은유/비유 표현
- 모호한 대상
- 다중 NPC 상호작용

> **v1 구현 현황**: LLM 보조 파싱은 **미구현**. 현재 모든 입력은 100% Rule Parser로만 처리되며, `parsedBy`는 항상 `"RULE"`이다. 룰 매칭 실패 시 LLM fallback 없이 기본 동작(OBSERVE 등)으로 축소한다.

### 4.3 LLM 파싱 제한

LLM은 반드시:

- Intent JSON만 출력
- 새로운 능력/아이템 생성 금지
- 수치 판단 금지
- 성공/실패 확정 금지

LLM은 해석만 수행한다.

> **v1 구현 현황**: LLM 파싱 자체가 미구현이므로 이 제한은 v2에서 LLM 파싱 도입 시 적용 예정.

### 4.4 Intent Merge 전략

| Case | 조건 | 처리 |
|------|------|------|
| Case 1 | RULE 성공 | RULE 결과 사용 |
| Case 2 | RULE 부분 성공 | RULE + LLM 병합 |
| Case 3 | RULE 실패 | LLM 결과 사용 |
| Case 4 | LLM도 실패 | 기본 OBSERVE 또는 TALK로 축소 |

---

## 5. Action DSL (서버 실행 단위)

자유 입력은 아래 DSL로만 실행된다.

### 5.1 COMBAT

| ActionType | 설명 |
|------------|------|
| ATTACK_MELEE | 근접 공격 |
| ATTACK_RANGED | 원거리 공격 |
| DEFEND | 방어 |
| EVADE | 회피 |
| USE_ITEM | 아이템 사용 |
| MOVE | 이동 |
| FLEE | 도주 |
| INTERACT | 환경 이용 (기둥 뒤 숨기, 문 닫기 등) |

#### 전투 확장 타입 (v2 예정)

| ActionType | 설명 |
|------------|------|
| COUNTER | 반격 |
| POSITIONING | 위치 이동 |
| INTERRUPT | 행동 방해 |

### 5.2 SOCIAL

| ActionType | 설명 |
|------------|------|
| TALK | 설득/협박/거짓말/정보 요청 |
| OFFER | 제안/거래 |
| OBSERVE | 표정/상황 관찰 |
| SIGNAL | 손짓/암호 |

### 5.3 EXPLORATION

| ActionType | 설명 |
|------------|------|
| MOVE_AREA | 이동 |
| SEARCH | 탐색 |
| STEALTH | 은신 |
| PICKLOCK | 자물쇠/장치 |
| USE_TOOL | 횃불, 로프 등 |
| REST | 휴식 |

### 5.4 SYSTEM

| ActionType | 설명 |
|------------|------|
| CHECK_STATUS | 상태 확인 |
| INVENTORY | 인벤토리 정리 |
| NOTE | 메모/단서 정리 |
| SAVE_POINT_ACTION | 여관/쉼터에서 다음 RUN 선택 등 |

---

## 6. Policy & Transform 규칙

### 6.1 정책 모드

- **COOPERATIVE_TRANSFORM** (유연/협조적)
- 기본 전략:
  - DENY는 최후의 수단
  - 가능한 한 PARTIAL 또는 TRANSFORM으로 살린다
  - 플레이어가 "하고자 한 의도"를 최대한 보존한다

### 6.2 정책 결과 타입

| 타입 | 설명 |
|------|------|
| ALLOW | 그대로 실행 |
| TRANSFORM | 유사 행동으로 변환하여 실행 (기본) |
| PARTIAL | 일부만 실행 (불가능한 조각 제거) |
| DENY | 실행 자체 불가 (최소화) |

### 6.3 불변 규칙 (절대 금지)

#### 서버 SoT 불변
- 수치(HP/데미지/골드/드랍/상태변화)는 서버만 결정
- 이미 확정된 server_result를 입력/LLM이 변경 불가
- RNG 소비 순서/seed 기반 재현성 유지

#### 세계관 불변 (설정 제약)
- 존재하지 않는 능력/아이템/인물/장소를 "확정 생성" 불가
- 순간이동/시간정지 같은 초능력은 설정에 없으면 불가
- 장비/스킬 리셋 규칙(RUN 단위) 위반 불가

#### 시스템 불변 (행동 경제)
- 턴(=Step)당 처리 가능한 행동량 상한 유지
- stamina/자원 비용을 무시하는 행동 불가
- 노드 상태머신을 역행하는 행동 불가 (예: NODE_ENDED에서 전투 계속)

### 6.4 TRANSFORM 규칙 (핵심)

#### "불가능"을 "가능한 근접 행동"으로 변환
- "순간이동해서 뒤를 잡는다"
  → (설정상 불가) "기둥 뒤로 굴러 시야를 끊고 측면 이동" (EVADE + MOVE)

#### "과도한 다중 행동"을 "콤보 2단"으로 축약
- "구르고, 쏘고, 다시 달려들어 베고, 발로 걷어찬다"
  → "EVADE + ATTACK" (2단 콤보로 축약) + 나머지는 연출로만 반영

#### "확정 결과 요구"를 "시도(ActionTry)"로 변환
- "상대 무기를 빼앗아 바닥에 던진다"
  → "DISARM_TRY" (조건부 성공) + 실패 시 페널티 가능

#### "리소스 무시"를 "리소스 소모 증가"로 변환
- "무한히 연속 사격"
  → stamina 비용 증가 + 명중/집중 페널티로 균형

### 6.5 DENY 사용 조건 (극소)

DENY는 아래에만 사용한다:

- 설정적으로 절대 불가능 (세계관 불변)
- 시스템적으로 불가능 (행동량/상태머신 위반)
- 악성/치트 입력 (스탯 조작, 아이템 생성 확정 등)
- 안전/서비스 정책 위반 입력 (외부 요인)

DENY 시에도 UX는 "대체안 제시"를 기본으로 한다.

---

## 7. 판정 구조 & 리스크-보상

### 7.1 핵심: 서버는 "의도"가 아니라 "행동"을 판정한다

- Intent → ActionPlan 매핑 이후
- ActionPlan은 고정된 순서로 resolve 된다

**예시: EVADE + ATTACK_RANGED**

1. EVADE 체크
2. 성공이면 ATTACK_RANGED 보너스
3. 실패이면 페널티 (피격/자세 무너짐 등)

### 7.2 리스크-보상 구조

복합 행동일수록:

- stamina 소모 증가
- 실패 확률 증가
- 성공 시 보상 증가

**비교 예시:**

| 행동 | Cost | 안정성 | 비고 |
|------|------|--------|------|
| 단일 ATTACK | 1 | 안정적 | 기본 행동 |
| EVADE + ATTACK | 2 | 회피 실패 시 리스크 | 성공 시 크리티컬 보너스 확률 증가 |

---

## 8. 내러티브 & UX 가드레일

### 8.1 내러티브 일관성

- LLM은 "성공/실패"를 확정하지 않는다.
- LLM은 server_result.events를 기반으로 묘사만 한다.
- 수치(HP/데미지/골드)는 정성 표현 중심.

### 8.2 UX 규칙 (플레이어 체감 자유도)

입력이 DENY되면 끝이 아니라:
- "가능한 해석"을 1~2개 제시 (TRANSFORM 유도)
- 다음 추천 입력 예시를 제공

**나쁜 예:**
> "그건 불가능합니다"

**좋은 예:**
> "지금 상태에선 순간이동은 어렵습니다. 대신 (1) 기둥 뒤로 굴러 숨거나 (2) 방패로 막고 거리를 벌릴 수 있습니다."

### 8.3 응답 템플릿 (서버 → LLM 컨텍스트에 제공)

| 항목 | 내용 |
|------|------|
| 당신이 의도한 건 | `{intent_summary}` |
| 지금 가능한 건 | `{transformed_summary}` |
| 제약 이유 (짧게) | `{reason}` |
| 다음 입력 힌트 (1~2개) | `{suggestions}` |

### 8.4 문장 원칙

- "안 돼요"가 아니라 "지금은 이렇게 해보는 게 현실적"으로 말한다
- 플레이어의 의도를 인정하고(공감), 가능한 경로를 제시한다(유도)
- 수치/확률은 숨기고 정성적으로만 표현한다

---

## 9. 저장 & 결정성

> 턴별 저장 필드 정본: `schema/07_database_schema.md` turns
> 리플레이는 `server_action_plan` + `seed`로 재현 (RNG 소비 순서 고정)

---

## 10. 비용 전략

- 1차 룰 기반 파서에서 **70~85%** 처리 목표
- LLM 호출 비율 **15~30% 이하** 유지
- `confidence >= 0.7`이면 LLM 호출 없이 룰 파서 결과 확정

> **v1 구현 현황**: 현재 **100% 룰 기반** 처리. LLM 입력 파싱 호출 비용은 **0**이다. LLM은 내러티브 생성에만 사용되며, 입력 해석에는 관여하지 않는다. 향후 LLM 파싱 도입 시 위 비율 목표를 적용한다.

---

## 11. 확장 참고

- v2 전투 확장 타입: COUNTER, POSITIONING, INTERRUPT
- "조건부 성공" 파생 액션 (DISARM_TRY 등)
