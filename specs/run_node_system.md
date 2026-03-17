# RUN & Node System v1

> 통합 설계서: RUN 구조 + Node 타입 (정본 enum) + Auto-Save
> 평균 RUN 길이: 8~12 Node | 저장 단위: Node 종료 시 자동 저장
>
> Node 분포 예시에서 사용된 명칭과 정본 enum의 대응:
> - INTRO_EVENT → EVENT (nodeMeta.isIntro: true)
> - SOCIAL_EVENT → EVENT
> - MAJOR_COMBAT → COMBAT (nodeMeta.isBoss: true)
> - RESOLUTION → EXIT

---

## 1. RUN 기본 길이

- 최소: 8 Node
- 평균: 10 Node
- 최대: 12 Node
- 보스형 RUN은 12 이상 가능

---

## 2. Node 타입 (정본 enum)

| enum 값 | 설명 |
|---------|------|
| COMBAT | 전투 노드. `nodeMeta.isBoss: true`이면 보스전 (기존 MAJOR_COMBAT) |
| EVENT | 이벤트/대화/조사 노드. RUN 첫 노드가 INTRO 역할을 겸함 |
| REST | 휴식 노드 (HP/Stamina 회복) |
| SHOP | 상점 노드 (장비 구매/판매, 아이템 거래) |
| EXIT | RUN 종료 노드 |

> 이 enum은 `schema/server_result_v1.json`, `llm_ctx_v1`, `TurnDetailResponse` 등 모든 스키마에서 공유한다.
> INTRO, MAJOR_COMBAT는 독립 타입이 아니라 플래그로 구분한다.

### nodeMeta 플래그

| 필드 | 타입 | 설명 |
|------|------|------|
| isBoss | boolean | 보스전 여부 (COMBAT 노드 전용) |
| isIntro | boolean | RUN 첫 진입 이벤트 여부 (EVENT 노드 전용) |

---

## 3. SHOP 노드 규칙

- 서버가 상품 목록을 생성 (ACT/세력 평판/노드 위치 기반)
- 구매/판매는 CHOICE 입력으로 처리
- 장비는 RUN 내 임시 장착 (RUN 종료 시 리셋)
- 골드 부족 시 거래 거부 (422)
- SHOP 노드에서 전투 발생 불가

---

## 4. Node 분포 기본 모델

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

---

## 5. RUN 내 곡선 구조

Node 1~3:
- 탐색/정보

Node 4~7:
- 갈등 확대

Node 8~9:
- 최고조 전투/정치 충돌

Node 10:
- 선택/결과

---

## 6. 정치 RUN 예시

예: "귀족 암살 음모 조사"

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

---

## 7. RUN 운영 규칙

- REST Node 최소 1 보장 (자원 고갈 방지)
- DOWNED 시스템 필수 (`core_game_architecture_v1.md` §8)

---

## 8. Auto-Save & 복구

### 저장 원칙

- Node 종료 시 자동 저장 (서버 트랜잭션 확정 이후)
- 플레이어가 별도로 저장할 필요 없음

### 저장 대상

- run_state
- node_state
- battle_state
- memory
- political_tension
- npc_relations

### 복구

- 마지막 완료 Node부터 재개
- LLM 재호출 없음
- server_result 기반 UI 재구성

### 악용 방지

- Node 중간 롤백 불가
- RNG 재시도 불가
- idempotencyKey로 중복 처리 방지

> 복구 상세 규칙: `server_api_system.md` Part 1 §5
