# 07 --- 게임 진행 & 성장 시스템

> ⚠️ **부분 구식 (2026-04-22)**: HUB 순환 모드 도입 이전 서술 일부 포함.
> 실제 현행 흐름은 아래 조합이 정본:
> - HUB 구조: `03_hub_engine.md`
> - 유저 드리븐 진행: `14_user_driven_code_bridge.md`
> - 동적 세계: `21_living_world_redesign.md`
>
> 원본: `02_game_systems.md` (622 lines) 압축본
> 원본 정본: `run_node_system.md`, `run_planner_v1_1.md`, `character_growth_v1.md`, `rewards_and_progression_v1.md`

---

## 1. RUN 구조 & 현재 게임 모드

### 1.1 현재 모드: 장소 기반 자유 탐험 (구현됨)

현재 구현된 게임 모드는 **장소 기반 자유 탐험**이다. 기존 HUB 허브스포크 구조에서, 장소 간 직접 이동이 가능한 구조로 확장되었다.

```
LOCATION(7개) ⇄ LOCATION (직접 이동) ⇄ COMBAT
  LOC_TAVERN이 탐험 거점 역할
```

- 7개 LOCATION(시장/경비대/항만/빈민가/귀족 구역/선착장 주점/부두 창고지대)
- **장소 간 직접 이동 가능**: MOVE_LOCATION으로 장소에서 장소로 직접 이동
- **LOC_TAVERN이 거점**: HUB 대신 선착장 주점이 탐험의 기준점 역할
- **이동 비용**: 인접 장소 1턴, 비인접 장소 2턴 소요
- LOCATION에서 Action-First 파이프라인으로 이벤트 진행
- COMBAT 발생 시 전투 처리 후 현재 LOCATION으로 복귀
- Arc 시스템(EXPOSE/PROFIT/ALLY)으로 장기 목표 추적
- WorldState(Heat/Time/Safety)로 세계 상태 관리

#### 장소 인접 관계

```
LOC_TAVERN ─── LOC_MARKET ─── LOC_NOBLE
    │              │
LOC_HARBOR ─── LOC_GUARD
    │
LOC_DOCKS_WAREHOUSE ─── LOC_SLUMS
```

- 연결선이 있는 장소는 **인접** (이동 1턴)
- 연결선이 없는 장소는 **비인접** (이동 2턴)
- HUB 노드는 여전히 존재하며, 목표 장소 불명확 시 HUB 복귀 fallback으로 동작

> 캐릭터 프리셋 4종(부두 노동자/탈영병/밀수업자/약초상)이 구현되어 있다.
> 각 프리셋의 스탯 분배는 LOCATION 판정에 `floor(stat/3)` 보너스로 반영된다.
> 상세: `03_hub_engine.md`, `content/graymar_v1/presets.json`

### 1.2 원본 설계: 선형 RUN 구조 (미구현)

원래 설계된 RUN은 8~12 Node 선형 진행 구조였다.

| 항목 | 값 |
|------|-----|
| 최소 | 8 Node |
| 평균 | 10 Node |
| 최대 | 12 Node |
| 보스형 RUN | 12 이상 가능 |

기본 10 Node 예시:

```
INTRO_EVENT → COMBAT → EVENT → COMBAT → SOCIAL_EVENT
→ REST → COMBAT → EVENT → BOSS_COMBAT → EXIT
```

> 이 선형 RUN 구조는 향후 **구조화된 미션(Structured Mission)** 모드로 재활용 가능.
> Phase별 노드 분포, 보스/EXIT 정책 등은 해당 모드 도입 시 적용한다.

### 1.3 Phase별 노드 분포 정책 (원본 설계, 미구현)

선형 RUN에서의 Phase 구분:

- **PHASE 1 (Depth 1~3)**: 서사 중심 --- EVENT 위주, 약한 적 COMBAT
- **PHASE 2 (Depth 4~7)**: 갈등 확대 --- EVENT/COMBAT 균형, SHOP 등장 증가
- **PHASE 3 (Depth 8~12)**: 클라이맥스 --- 보스 확률 상승, EXIT 활성화

보스 정책:
- RUN당 최소 0, 최대 1
- Depth 7 이상에서만 등장

EXIT 정책:
- Depth 6 이후 확률 활성화
- 보스 등장 이후 EXIT 확률 상승
- 플레이어 선택으로 종료

---

## 2. Node 타입

### 2.1 정본 enum

```typescript
// server/src/db/types/enums.ts
export const NODE_TYPE = ['COMBAT', 'EVENT', 'REST', 'SHOP', 'EXIT', 'HUB', 'LOCATION'] as const;
```

### 2.2 주요 타입 (HUB 탐험 모드)

| enum 값 | 설명 | 구현 상태 |
|---------|------|-----------|
| HUB | 탐험 거점. LOCATION 선택, Heat 해결, 아크 진행 | ✅ |
| LOCATION | 행동 처리 노드. Action-First 파이프라인 적용 | ✅ |
| COMBAT | 전투 노드. `nodeMeta.isBoss`로 보스전 구분 | ✅ |

### 2.3 레거시 타입 (선형 RUN용)

| enum 값 | 설명 | 비고 |
|---------|------|------|
| EVENT | 이벤트/대화/조사 노드 | `isIntro` 플래그로 INTRO 구분 |
| REST | 휴식 노드 (HP/Stamina 회복) | RUN당 최소 1 보장 설계 |
| SHOP | 상점 노드 (구매/판매) | CHOICE 기반 거래 |
| EXIT | RUN 종료 노드 | 선택형 종료 |

> 레거시 타입은 enum에 존재하지만 현재 HUB 탐험 모드에서는 사용하지 않는다.
> 향후 구조화된 미션 모드에서 재활용 예정.

### 2.4 nodeMeta 플래그

| 필드 | 타입 | 설명 |
|------|------|------|
| isBoss | boolean | 보스전 여부 (COMBAT 전용) |
| isIntro | boolean | RUN 첫 이벤트 (EVENT 전용) |

---

## 3. Auto-Save & 복구

### 저장 원칙

- Node 종료 시 자동 저장 (서버 트랜잭션 확정 이후)
- 플레이어 별도 저장 불필요

### 저장 대상

`run_state`, `node_state`, `battle_state`, `memory`, `political_tension`, `npc_relations`

### 복구 규칙

- 마지막 완료 Node부터 재개
- LLM 재호출 없음 (server_result 기반 UI 재구성)
- Node 중간 롤백 불가, RNG 재시도 불가
- `idempotencyKey`로 중복 처리 방지

---

## 4. 캐릭터 프리셋 & 스탯 (구현됨)

현재 GP 기반 영구 성장 대신, **캐릭터 프리셋**으로 초기 스탯이 결정된다.

| 프리셋 | 특징 | MaxHP | ATK | DEF | EVA | CRIT |
|--------|------|-------|-----|-----|-----|------|
| DOCKWORKER (부두 노동자) | 근접 탱커 | 120 | 16 | 14 | 2 | 4 |
| DESERTER (탈영병) | 균형형 전투 | 100 | 17 | 11 | 3 | 5 |
| SMUGGLER (밀수업자) | 회피/치명타 | 80 | 14 | 7 | 7 | 8 |
| HERBALIST (약초상) | 아이템 활용 | 90 | 11 | 9 | 4 | 4 |

LOCATION 판정 시 관련 스탯이 `floor(stat/3)` 보너스로 적용된다.

> 상세: `content/graymar_v1/presets.json`

---

## 5. GP 시스템 설계 (미구현)

### 5.1 핵심 철학

각 RUN은 "임무 수행"이며, 종료는 실패가 아닌 **임무 완료/철수**. RUN마다 경험 축적, 성장 방향은 자유 선택. 빌드 강제 없이 플레이 성향이 자연스럽게 형성된다.

### 5.2 GP 획득 & 투자

- **획득 경로**: RUN 완료, 메인 아크 진행, 정치적 선택, 고위험 RUN 성공
- **투자**: 허브에서만 가능, 영구 기본 스탯 또는 특성 트리에 투자
- **비용 공식**: `cost = baseCost x (1 + currentLevel x 0.15)`

### 5.3 영구 스탯 (Permanent Stats)

GP로 투자 가능한 13종 영구 능력치:

| 분류 | 스탯 |
|------|------|
| 기본 전투 | Max HP, Max Stamina, Base Attack, Base Defense |
| 명중/회피 | Base ACC, Base EVA, Base SPEED |
| 치명타 | Crit Base, Crit DMG (기본 1.5 → 최대 2.5) |
| 저항 | Base RESIST |
| 특수 | Tactical Awareness (위치 판정), Political Influence (설득 판정) |
| 슬롯 | 특성 슬롯 해금 (고정 8GP, 최대 6) |

> GP 수입 예상: ACT1 ~15GP ~ ACT6 ~65GP
> 전 스탯 최대 투자 불가 (선택의 의미 유지)
> 비용 테이블 상세: 원본 `02_game_systems.md` SS3.5 참조

---

## 6. 특성 트리 (미구현)

3개 트리, 각 트리는 조건 완화 / 보너스 강화 위주:

### 전술 (Tactical Path)
- 보너스 슬롯 조건 완화, 완벽 회피 확률 증가
- 측면 판정 보너스, ENGAGED 유지 보너스, 다수 적 페널티 감소

### 정치 (Diplomatic Path)
- 설득 성공률/세력 평판 획득량 증가
- 협상 비용 감소, 허브 이벤트 추가 선택지, 정치 긴장 완화

### 전략/정보 (Strategic Path)
- 적 AI 의도 예측 힌트, 환경 태그 판정 보너스
- 함정 탐지, 자원 효율 증가, 마법 비용 감소

### 마법 연계 (미구현)
- 특정 특성 해금 시 마법 시스템 연동
- 마법 비용 감소, 정치 반작용 감소, 세력 의심도 완화

### 성장 한계
- 모든 트리 완전 마스터 불가 (GP 제한)

---

## 7. 보상 시스템

### 7.1 보상 카테고리

| 카테고리 | 설명 | 영속성 |
|----------|------|--------|
| 골드 | 경제 자원. SHOP 구매, 강화/제작 | 영구 |
| 아이템 | 장비, 소비 아이템, 퀘스트 아이템 | 영구 |
| EXP | 런 단위 누적, 레벨업 기반 성장 | 미구현 |
| 평판/호감도 | 세력 평판, NPC 호감도 → 이벤트/퀘스트 분기 영향 | 영구 |

### 7.2 전투 보상

- **지급 시점**: VICTORY 즉시 지급
- **드랍 방식**: 랜덤 드랍 테이블 기반
  - 잡몹: 전투 단위 1회 롤
  - 보스/엘리트: 개별 롤
- **상한**: 전투당 최대 드랍 수 존재 (난이도별 조정)

### 7.3 EVENT 및 퀘스트 보상

- EVENT: 선택지 고정 보상 (서버 SoT), 일부 드랍 테이블
- 퀘스트: 완료 즉시 지급하지 않음, 허브/EXIT에서 일괄 정산

### 7.4 EXP & 레벨업 (미구현)

- 런 단위 누적, 레벨업 임계값은 외부 테이블
- 레벨업 시 행동 통계 기반 성장 (근접 공격 위주 → ATK, 회피 중심 → EVA 등)

### 7.5 장비 리셋 (원본 설계)

선형 RUN 모드 설계:
- RUN 시작 시 소속 기관에서 기본 장비 배급
- RUN 종료 시 장비 회수 (길드 소유 자산)
- RUN 내부 성장(임시 장비/버프/스킬)은 RUN 종료 시 초기화

> 현재 HUB 모드에서는 장비 시스템 미구현.

---

## 8. 인벤토리 & 패배/도주 처리

### 8.1 인벤토리 (기본 구현)

- `inventory[]` 배열로 아이템 관리 (슬롯 제한 미적용)
- `InventoryService`로 아이템 추가/제거 처리
- 슬롯 상한(설계: 20) 및 초과 시 드랍 선택은 미구현

### 8.2 패배 처리 (DEFEAT) --- 구현됨

- RUN 즉시 종료 (`turns.service.ts` — DEFEAT → `status: 'RUN_ENDED'`)
- HP≤0 가드: LOCATION 턴 진입 시 hp≤0이면 즉시 RUN_ENDED
- `calculateDefeatPenalty()`는 `{gold:0, items:[], exp:0}` 반환 (보상 상실 미구현)
- 엔딩 생성 없음 (EndingGenerator 미호출)

### 8.3 도주 처리 (FLEE_SUCCESS) --- 구현됨

- 전투 보상 없음
- 골드 손실 없음 (설계의 -10% 패널티는 미구현)
- 아이템 유지
- FLEE_SUCCESS → NODE_ENDED → 부모 LOCATION으로 복귀

### 8.4 보상 RNG 정책 (미구현)

- 전투 RNG(seed+cursor)와 분리된 보상 전용 RNG seed
- 보상 RNG는 전투 결과와 독립적 관리

### 8.5 밸런스 가드레일

- 보상 상한 존재 (폭주 방지)
- 최소 보상 보장 없음
- 난이도 상승 시 드랍 확률 보정 가능

---

## 9. 구현 상태 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| **게임 모드** | | |
| 장소 기반 자유 탐험 | ✅ 구현 | LOCATION ⇄ LOCATION 직접 이동 (LOC_TAVERN 거점, 인접 1턴/비인접 2턴) |
| 선형 RUN (8~12 Node) | ❌ 미구현 | 향후 미션 모드로 재활용 가능 |
| **Node 타입** | | |
| HUB / LOCATION / COMBAT | ✅ 구현 | 현재 HUB 모드 주요 타입 |
| EVENT / REST / SHOP / EXIT | ⚠️ enum 존재 | 선형 RUN용, 현재 미사용 |
| nodeMeta (isBoss, isIntro) | ✅ 구현 | |
| **자동 저장** | | |
| Auto-Save (Node 종료 시) | ✅ 구현 | 서버 트랜잭션 기반 |
| idempotencyKey 중복 방지 | ✅ 구현 | |
| **캐릭터** | | |
| 캐릭터 프리셋 4종 | ✅ 구현 | 스탯 분배, floor(stat/3) 보너스 |
| GP 시스템 | ❌ 미구현 | 허브 UI 포함 |
| 영구 스탯 투자 (13종) | ❌ 미구현 | baseCost 테이블 설계됨 |
| 특성 트리 (3개) | ❌ 미구현 | 전술/정치/전략 |
| 마법 연계 | ❌ 미구현 | 특성 해금 조건 |
| **보상** | | |
| 전투 보상 (VICTORY 즉시) | ✅ 구현 | 기본 골드 드랍 |
| 보상 카테고리 (골드/아이템/EXP/평판) | ⚠️ 부분 | 골드/아이템 기본 구현 |
| 인벤토리 (기본) | ⚠️ 부분 | InventoryService 존재, 슬롯 제한 미적용 |
| EXP 테이블 / 레벨업 | ❌ 미구현 | 행동 통계 기반 성장 |
| 드랍 테이블 | ❌ 미구현 | 외부 정의 대상 |
| 보상 RNG 분리 | ❌ 미구현 | 전투 RNG와 별도 seed |
| **진행 제어** | | |
| DEFEAT → RUN 종료 | ✅ 구현 | 즉시 RUN_ENDED (보상 상실 로직 미구현) |
| FLEE → LOCATION 복귀 | ✅ 구현 | 골드 손실 없음 (설계 -10% 미구현) |
| Phase별 노드 분포 | ⚠️ 설계만 | 가중치 수치 미확정 |
| 보스 정책 (Depth 7+) | ⚠️ 설계만 | 선형 RUN용 |
| EXIT 정책 (Depth 6+) | ⚠️ 설계만 | 선형 RUN용 |

---

> **참조 문서**
> - `03_hub_engine.md` --- HUB 엔진, Action-First 파이프라인, WorldState
> - `04_combat_engine.md` --- 전투 시스템, DOWNED, 보상 처리
> - `content/graymar_v1/presets.json` --- 캐릭터 프리셋 정의
> - `content/graymar_v1/items.json` --- 아이템 카탈로그

---

## 부록 A: 장비 리셋 스토리 정당화

> 원본 참조: `specs/character_growth_v1.md` §2

### 장비 리셋 설정

플레이어는 용병/탐험가/조사관 소속이다. 각 RUN 시작 시:
- 소속 기관(용병 집합소, 기사단, 길드, 마을 의회 등)에서 기본 장비 배급
- 임무 종료 후 장비 회수

### 스토리적 근거

| 이유 | 설명 |
|------|------|
| 길드 소유 자산 | 장비는 개인이 아닌 기관 소유 |
| 임무 전용 | 고위 장비는 특정 임무에만 허가 |
| 정화/격리 | 위험 지역 장비는 사후 처리 필요 |
| 군수 체계 | 개인 소유 불가, 반납 의무 |

> RUN 내부 임시 성장(장비/버프/스킬 해금)은 RUN 종료 시 전부 초기화.
> 현재 HUB 모드에서는 장비 시스템 미구현이나, 향후 Region/Economy 스펙에서 5슬롯(Weapon/Armor/Tactical/Political/Relic) 장비 시스템 도입 예정.

---

## 부록 B: 보상 상한 & 패배/도주 경제 상세

> 원본 참조: `specs/rewards_and_progression_v1.md`

### 보상 상한 정책

- 전투당 최대 드랍 수 상한 존재 (난이도/노드 타입별 조정)
- 보상 RNG는 전투 RNG(seed+cursor)와 **분리된 전용 RNG seed** 사용
- 보상 RNG는 전투 결과와 독립적 관리
- 밸런스 가드레일: 최소 보상 보장 없음, 난이도 상승 시 드랍 확률 보정 가능

### DEFEAT 경제

- RUN 즉시 종료 (DEFEAT → `status: 'RUN_ENDED'`)
- `calculateDefeatPenalty()` → `{gold:0, items:[], exp:0}` (보상 상실 로직 미구현)
- 영구 메타 자산 유지 여부는 별도 메타 스펙에서 정의

### FLEE_SUCCESS 경제

- 전투 보상 **없음**
- 골드 손실 **없음** (설계의 -10%는 미구현)
- 아이템 유지, LOCATION으로 복귀

### 드랍 롤 구조

| 대상 | 방식 |
|------|------|
| 잡몹 | 전투 단위 1회 롤 |
| 보스/엘리트 | 개별 롤 |

---

## 부록 C: Phase별 노드 생성 가중치 상세

> 원본 참조: `specs/run_planner_v1_1.md`

선형 RUN 구조에서의 Phase별 상세 가중치 정책. 현재는 미구현이나 구조화된 미션 모드 도입 시 적용.

### Phase 구분

| Phase | Depth | 기조 | 목표 |
|-------|-------|------|------|
| PHASE 1 | 1~3 | 서사 중심 | 세계관 적응 + 초기 성장 |
| PHASE 2 | 4~7 | 갈등 확대 | 빌드 방향 체감 |
| PHASE 3 | 8~12 | 클라이맥스 | 긴장 + 성장 확인 + 결말 유도 |

### 노드별 가중치 (상대적)

| Node Type | PHASE 1 | PHASE 2 | PHASE 3 |
|-----------|---------|---------|---------|
| EVENT | 높음 | 중간 | 중간 (분기/결말) |
| COMBAT | 낮음 (약한 적) | 중간 | 높음 |
| REST | 중간 | 중간 | 낮음 (제한적) |
| SHOP | 낮음 | 중간 (증가) | 낮음 |
| EXIT | 없음 | 없음 | Depth 6+ 활성 |

### 보스 정책

- RUN당 최소 0, 최대 1 보스
- Depth 7 이상에서만 등장
- 개별 드랍 롤 적용

### EXIT 정책

- Depth 6 이후 확률 활성화
- 보스 등장 이후 EXIT 확률 상승
- 플레이어 선택으로 종료

### 생존 압박

- REST는 RUN당 최대 2회 권장
- 연속 REST 금지
- HP 30% 이하 시 REST 가중치 증가
- 전투 밀도 낮음 → 회복 기회는 중간 수준

### 성장 체감 설계

- COMBAT 수는 적지만 질적으로 중요
- EVENT에서 능력 성장/평판 상승 기회 다수
- 후반부 보스 배치로 성장 체감 극대화
