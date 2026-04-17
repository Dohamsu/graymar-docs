# RUN, Node System & Planner v1.1

> 통합 설계서: RUN 구조 + Node 타입 (정본 enum) + Auto-Save + 플래너 정책
> 평균 RUN 길이: 9~12 Node (긴 몰입형) | 저장 단위: Node 종료 시 자동 저장
>
> Node 분포 예시 명칭과 정본 enum 대응:
> - INTRO_EVENT → EVENT (nodeMeta.isIntro: true)
> - SOCIAL_EVENT → EVENT
> - MAJOR_COMBAT → COMBAT (nodeMeta.isBoss: true)
> - RESOLUTION → EXIT

---

## 1. 노드 시스템

### 1.1 RUN 기본 길이

- 최소: 8 Node
- 평균: 10 Node
- 최대: 12 Node
- 보스형 RUN은 12 이상 가능

### 1.2 Node 타입 (정본 enum)

| enum 값 | 설명 |
|---------|------|
| COMBAT | 전투 노드. `nodeMeta.isBoss: true`이면 보스전 (기존 MAJOR_COMBAT) |
| EVENT | 이벤트/대화/조사 노드. RUN 첫 노드가 INTRO 역할을 겸함 |
| REST | 휴식 노드 (HP/Stamina 회복) |
| SHOP | 상점 노드 (장비 구매/판매, 아이템 거래) |
| EXIT | RUN 종료 노드 |

> 이 enum은 `schema/server_result_v1.json`, `llm_ctx_v1`, `TurnDetailResponse` 등 모든 스키마에서 공유한다.
> INTRO, MAJOR_COMBAT는 독립 타입이 아니라 플래그로 구분한다.

#### nodeMeta 플래그

| 필드 | 타입 | 설명 |
|------|------|------|
| isBoss | boolean | 보스전 여부 (COMBAT 노드 전용) |
| isIntro | boolean | RUN 첫 진입 이벤트 여부 (EVENT 노드 전용) |

### 1.3 SHOP 노드 규칙

- 서버가 상품 목록을 생성 (ACT/세력 평판/노드 위치 기반)
- 구매/판매는 CHOICE 입력으로 처리
- 장비는 RUN 내 임시 장착 (RUN 종료 시 리셋)
- 골드 부족 시 거래 거부 (422)
- SHOP 노드에서 전투 발생 불가

### 1.4 Node 분포 기본 모델

기본 10 Node 예시:

1. INTRO_EVENT
2. COMBAT
3. EVENT
4. COMBAT
5. SOCIAL_EVENT
6. REST
7. COMBAT
8. EVENT
9. MAJOR_COMBAT
10. RESOLUTION / EXIT

### 1.5 RUN 내 곡선 구조

- Node 1~3: 탐색/정보
- Node 4~7: 갈등 확대
- Node 8~9: 최고조 전투/정치 충돌
- Node 10: 선택/결과

### 1.6 정치 RUN 예시 — "귀족 암살 음모 조사"

1. 정보 수집
2. 경호병 충돌
3. 귀족 대화
4. 암살자 추적
5. 암살자 전투
6. 내부 배신자 노출
7. 정치 협상
8. 세력 개입
9. 최종 대치
10. 결론 선택

### 1.7 RUN 운영 규칙

- REST Node 최소 1 보장 (자원 고갈 방지)
- DOWNED 시스템 필수 (`core_game_architecture_v1.md` §8)

### 1.8 Auto-Save & 복구

**저장 원칙**
- Node 종료 시 자동 저장 (서버 트랜잭션 확정 이후)
- 플레이어가 별도로 저장할 필요 없음

**저장 대상**: run_state, node_state, battle_state, memory, political_tension, npc_relations

**복구**
- 마지막 완료 Node부터 재개
- LLM 재호출 없음
- server_result 기반 UI 재구성

**악용 방지**
- Node 중간 롤백 불가
- RNG 재시도 불가
- idempotencyKey로 중복 처리 방지

> 복구 상세 규칙: `server_api_system.md` Part 1 §5

---

## 2. 플래너

### 2.1 RUN 성향 확정

- 평균 RUN 길이: 9~12 노드 (긴 몰입형)
- 전투 밀도: 낮음 (EVENT 중심 구조)
- 생존 압박: 중간
- 보스: 확률 등장
- EXIT: 중반 이후 확률 등장
- 전체 톤: 성장 체감형 RPG

### 2.2 기본 Depth 구조 (권장)

- Depth 1~3: 서사 중심 (EVENT 다수)
- Depth 4~7: 성장 체감 구간 (COMBAT 점진적 증가)
- Depth 8~12: 클라이맥스 구간 (보스 확률 상승 + EXIT 등장 가능)

> 실제 Depth 구간 수치는 외부 플랫폼에서 확정한다.

### 2.3 노드 분포 정책 (상대적 비율)

- EVENT: 높음
- COMBAT: 낮음~중간
- REST: 중간
- SHOP: 낮음~중간
- EXIT: 중반 이후 활성화

> 정확한 확률 값은 외부 튜닝 대상

### 2.4 Phase별 정책

**PHASE 1 (초반, Depth 1~3)** — 세계관 적응 + 초기 성장 기반 형성
- EVENT 중심 / COMBAT는 약한 적 위주 / REST 중간 / SHOP 낮음

**PHASE 2 (중반, Depth 4~7)** — 빌드 방향 체감
- EVENT와 COMBAT 균형 / 성장 체감 강화 / SHOP 증가 / 보스 낮은 확률

**PHASE 3 (후반, Depth 8~12)** — 긴장 + 성장 확인 + 결말 유도
- 보스 확률 상승 / EXIT 후보 활성화 / EVENT는 분기/결말 성격 / REST 제한적

### 2.5 보스 정책

- RUN당 최소 0, 최대 1 보스 등장 (권장)
- 등장 조건: Depth 7 이상 + 이전에 보스 등장하지 않았을 것
- 보스는 개별 드랍 롤 적용

### 2.6 EXIT 정책

- Depth 6 이후 확률 활성화
- 보스 등장 이후 EXIT 확률 상승
- EXIT는 선택형 (플레이어 선택으로 종료)

### 2.7 생존 압박 정책

- REST는 RUN당 최대 2회 권장
- 연속 REST 금지 유지
- HP 30% 이하 시 REST 가중치 증가
- 전투 밀도 낮기 때문에 회복 기회는 중간 수준 유지

### 2.8 성장 체감 설계

- COMBAT는 수는 적지만 "질적으로 중요"
- EVENT에서 능력 성장/평판 상승 기회 다수 제공
- 후반부에 성장 체감이 극대화되도록 보스 배치

### 2.9 테스트 체크리스트

- 평균 RUN이 9~12 노드 내에서 종료되는지 확인
- EVENT가 전체 노드의 절반 이상인지 확인
- 보스가 과도하게 자주 등장하지 않는지 확인
- EXIT가 너무 일찍 등장하지 않는지 확인
- REST가 과도하게 많아지지 않는지 확인

> v1.1은 긴 몰입형, EVENT 중심, 성장 체감형 RPG 구조를 반영한 플래너 스펙이다. 세부 가중치 및 수치는 외부 플랫폼에서 밸런싱한다.
