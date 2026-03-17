# 10 — 리전 · 장비 · 세트 · 경제 시스템

> 원본 참조: `Region_Item_Economy_Spec_v1.md`, `specs/character_growth_v1.md`, `specs/rewards_and_progression_v1.md`
> 상태: **부분 구현** — RegionState 타입+초기값 정의됨, Shop 서비스 구현됨. 동적 경제(수급/물가 변동) 미구현. Phase 4.
> 의존: WorldState (구현됨), 보상 시스템 (부분 구현), Modifier Stack (전투 엔진, 구현됨)

---

## 1. RegionState 계층

### 1.1 계층 구조

```
WorldStateGlobal (전역, 영속)
  └─ RegionState (리전별, 영속)
      └─ RunState (에피소드 단위, 휘발)
```

- **Run**은 임시 — 리전 진입 시 스냅샷, 종료 시 결과를 리전에 반영
- **Region**과 **World**는 영속 — Run 간 상태 유지

### 1.2 RegionState 스키마

```typescript
interface RegionState {
  regionId: string;              // "REG_GRAYMAR_HARBOR"
  name: string;                  // "Graymar Harbor"
  chapterIndex: number;          // 리전 진행 순서
  clock: {
    timePhase: TimePhase;        // DAY | NIGHT
    timeCounter: number;         // 리전 내 시간 진행 카운터
  };
  heat: {
    hubHeat: number;             // 0~100
    hubSafety: HubSafety;        // SAFE | ALERT | DANGER
  };
  tension: {
    localTension: number;        // 0~10
    stage: 'STABLE' | 'RISING' | 'PEAK' | 'DECLINING';
  };
  factions: {
    reputation: Record<string, number>;  // 세력별 평판
    flags: Record<string, boolean>;      // 세력 플래그
  };
  npcs: {
    npcStates: Record<string, any>;      // NPC 영속 상태
    generatedNpcPool: Record<string, any>;  // 동적 생성 NPC 풀
  };
  quests: {
    active: Record<string, any>;         // 진행 중 퀘스트
    completed: string[];                 // 완료된 퀘스트 ID
  };
  arcs: {
    currentRoute: string | null;         // 현재 아크 루트
    commitment: number;                  // 0~3
    resolvedRoutes: string[];            // 완료된 루트들
  };
  locations: {
    unlockedLocationIds: string[];       // 해금된 LOCATION 목록
  };
  economy: {
    priceIndex: number;                  // 물가 지수 (기본 1.0)
    shopStocks: Record<string, any>;     // 상점별 재고 상태
  };
  history: {
    majorEvents: string[];               // 주요 사건 기록
  };
}
```

### 1.3 RunState ↔ RegionState 동기화

- Run 시작: RegionState에서 스냅샷 → RunState 초기화
- Run 종료: RunState 결과 → RegionState에 반영 (reputation, quests, npcs, economy 등)
- 중간 동기화 없음 — Run은 격리된 에피소드

---

## 2. Equipment System (장비)

### 2.1 희귀도

| Rarity | 획득 경로 | 특징 |
|--------|----------|------|
| Rare | 일반 드랍, 상점 | 기본 강화 |
| Unique | 엘리트 드랍, 상점 (후반) | 고유 효과 |
| Legendary | 퀘스트 전용 | 세계 영향 효과, Relic 슬롯 전용 |

Legendary 아이템:
- 높은 난이도 전용 퀘스트로만 획득
- **절대 드랍/상점 판매 안 됨**
- Relic 슬롯 전용
- 리전 고정 (매 플레이스루 동일 보상)

### 2.2 슬롯 구조 (5슬롯)

| Slot | 이름 | 용도 |
|------|------|------|
| 1 | Weapon | 무기 — ATK, CRIT 영향 |
| 2 | Armor | 방어구 — DEF, HP 영향 |
| 3 | Tactical | 전술 장비 — EVA, SPEED, 환경 보너스 |
| 4 | Political | 정치 장비 — PERSUADE, BRIBE 보너스 |
| 5 | Relic | 제한 — 세계 영향 효과 허용, Legendary 전용 |

- **World-impact 효과는 Relic 슬롯에서만 허용**
- 나머지 슬롯은 수치/서술 효과만

### 2.3 Modifier Stack 연동

장비는 Modifier Stack의 **GEAR layer (priority 200)**에 삽입:

```
BASE (100) → GEAR (200) → BUFF (300) → DEBUFF (400) → FORCED (900) → ENV (950)
```

장비 statBonus가 Snapshot 계산에 자동 반영.

### 2.4 아이템 확장 필드 (items.json)

기존 필드에 추가:
```typescript
interface ItemV2 extends Item {
  rarity: 'RARE' | 'UNIQUE' | 'LEGENDARY';
  slot: 'WEAPON' | 'ARMOR' | 'TACTICAL' | 'POLITICAL' | 'RELIC';
  statBonus: Partial<Record<StatKey, number>>;  // { ATK: 3, CRIT: 2 } 등
  setId?: string;             // 세트 소속 ID
  narrativeTags: string[];    // 서술 태그 (LLM 톤 영향)
}
```

---

## 3. Set System (세트)

### 3.1 리전별 세트 구성

각 리전은 2개 세트:
- **1 Combat Set** — 전투 보너스
- **1 Political/Utility Set** — 정치/유틸 보너스

### 3.2 세트 보너스 구조

| 피스 수 | 효과 |
|---------|------|
| 2-piece | 안정 보너스 (수치 강화) |
| 3-piece | 시스템 영향 (비파괴적 특수 효과) |

### 3.3 드랍 구조

| 파트 | 획득처 |
|------|--------|
| Part 1 | 일반 적 드랍 |
| Part 2 | 엘리트 적 드랍 |
| Part 3 | 보스 전용 + 퀘스트 진행 게이트 |

### 3.4 중복 처리

중복 파트는 자동 분해 → **리전 재료(Region Materials)**로 변환.

---

## 4. Legendary System (전설)

- 리전 고정 보상 (동일 플레이스루 동일 결과)
- 정치적 위기 + 세력 commitment 트리거
- 포함 요소:
  - 2+ 메카닉스 (복합 효과)
  - 1 제한적 세계 영향 효과
  - **Run당 1회 사용 제한**
- Relic 슬롯 전용
- **서사적 이정표** — 경제 아이템이 아닌 스토리 보상

---

## 5. Shop & Economy System (상점 · 경제)

### 5.1 상점 구조

| 규칙 | 설명 |
|------|------|
| 세트 아이템 미판매 | 세트는 드랍 전용 |
| Rare/Unique만 판매 | Legendary 절대 미판매 |
| 시간 기반 갱신 | Region clock에 연동 |
| 부분 갱신 모델 | 50% 교체 (나머지 유지) |

### 5.2 점진적 품질 스케일링

시간 경과에 따라:
- Unique 가중치 증가
- 특수 상인 등장 확률 증가
- Legendary는 절대 판매 안 됨

### 5.3 경제 변수

```typescript
interface RegionEconomy {
  priceIndex: number;          // 물가 지수 (기본 1.0)
  shopStocks: Record<string, ShopStock>;
}

interface ShopStock {
  items: StockItem[];
  lastRefreshTurn: number;     // 마지막 갱신 시점
  refreshInterval: number;     // 갱신 주기 (턴 수)
}
```

- `priceIndex`는 리전 상태(tension, crime 등)에 영향받음
- 높은 tension → 가격 상승 (물자 부족)
- 낮은 security → 암시장 아이템 증가

---

## 6. Narrative Tag System (서술 태그)

### 6.1 장비 태그 (Equipment Tags)

노드 시작 시 장착 장비 기반 생성.

| 카테고리 | 설명 | 예시 |
|----------|------|------|
| CombatStyle | 전투 스타일 | "heavy_weapon", "dual_wield" |
| PoliticalInfluence | 정치적 영향 | "noble_signet", "guild_badge" |
| WorldImpression | 외적 인상 | "intimidating", "scholarly" |

최대 **6개 태그**.

### 6.2 행동 태그 (Behavioral Tags)

Run 종료 시 행동 통계 기반 생성.

- 최대 **5개** 유지
- 점수 기반 순위 — 높은 점수 태그 유지
- 오래된 태그는 자연 감쇠

### 6.3 태그 영향 범위

**영향 O** (서술 전용):
- NPC 톤 (친근/경계/공포)
- 대화 스타일 (존대/하대/암시)
- 세계 묘사 (분위기, 반응)

**영향 X** (절대 금지):
- 서버 수치 계산
- 퀘스트 상태
- NPC 생존 여부
- 전투 판정

> **서버 SoT 원칙 유지**: 태그는 LLM 서술에만 영향, 게임 메카닉에는 절대 영향 없음.

---

## 7. 설계 원칙

1. **서버 is SoT** — 모든 수치/판정은 서버가 확정
2. **LLM handles narration only** — 장비/태그는 서술 톤에만 영향
3. **Equipment influences tone, not math** — 장비 서술 효과와 수치 효과 분리
4. **Legendary is narrative milestone** — 경제 아이템이 아닌 스토리 이정표
5. **Region drives identity** — 리전이 성장과 정체성의 단위

---

## 8. 장비 리셋 정당화 참조

> 원본: `specs/character_growth_v1.md` §2

현재 설계에서 RUN 종료 시 장비 리셋은 스토리적으로 정당화됨:
- 장비는 소속 기관(길드/기사단) 소유 자산
- 임무 종료 후 반납 의무
- 위험 지역 장비는 정화/격리 필요

Region/Economy 시스템 도입 시:
- RUN 내 장비는 임시 (기존 규칙 유지)
- 영구 장비는 Region 단위로 별도 관리 (향후 설계)

---

## 9. 구현 로드맵

| Phase | 범위 | 비고 |
|-------|------|------|
| Phase 1 | 보상 기초 (골드/아이템 기본 드랍) | ✅ 구현됨 |
| Phase 2 | WorldState 확장, per-location 상태 | Phase 2 선행 |
| Phase 4a | RegionState 타입 + RunState 연동 | 독립 선행 가능 |
| Phase 4b | Equipment 5슬롯 + Modifier Stack 연결 | 전투 엔진 의존 |
| Phase 4c | Set System + Legendary | 장비 시스템 의존 |
| Phase 4d | Shop & Economy (priceIndex, 갱신) | RegionState 의존 |
| Phase 4e | Narrative Tag System | LLM 연동 |
