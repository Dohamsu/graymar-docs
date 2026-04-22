# 41. Creative Combat Actions — 즉흥 전투 시스템 설계

> **목표**: 플레이어의 자유 텍스트 입력("의자를 집어 던진다", "드래곤 브레스!")이 기계적 공격과 구분되어 전투 경험에 **즉흥성·서사성**을 부여한다.
>
> **핵심 원칙**: 불변식 1(서버=Source of Truth) · 2(LLM=narrative-only) 준수. 모든 수치·효과 산정은 서버가 결정, LLM은 서술만.

---

## 1. 5-Tier Action Classification

서버가 rawInput을 스캔하여 5단계로 분류하고, 각 Tier별 처리·서술 스타일을 적용한다.

| Tier | 이름 | 조건 | 기계적 효과 | 서술 스타일 |
|------|------|------|-------------|-------------|
| T1 | Registered Prop | 전투 씬 `environmentProps[]`에 명시된 소품 키워드 일치 | 구체 효과 (STUN/BLEED/damageBonus 등) + 프롭 일회성 | 프롭 이름 서술 강제 |
| T2 | Category Improvised | 일반 카테고리 키워드(무거움/날카로움/광원/시야차단/얽매기) 일치 | 공통 효과 (소폭 보너스/상태) | 입력 묘사 반영 |
| T3 | Narrative Cover | Tier 1·2 미매칭 + 현실적으로 가능한 행동 | 기본 공격만 | 입력 묘사 그대로 살림 |
| T4 | Comedic Fantasy | 환상 키워드 매칭 (드래곤·마법·순간이동·시간 되돌림 등) | 기본 공격, 보너스 없음, `fantasyFlag=true` | 자각 → 재연출 (재치 있게) |
| T5 | Absurd | 행동 대상·논리 부재 (추상 개념, 4th wall break) | 턴 소진 (자동 DEFEND), `abstractFlag=true` | 허공 응시·호흡 고름 |

---

## 2. 데이터 모델

### 2.1 환경 소품 (Tier 1)

콘텐츠 파일: `content/graymar_v1/environment_props.json`

```typescript
interface EnvironmentProp {
  id: string;                    // 'chair_wooden'
  name: string;                  // '나무 의자'
  keywords: string[];            // ['의자','나무 의자','스툴']
  locationTags: string[];        // ['tavern','indoor'] — 어느 장소에 기본 등장
  effects: {
    damageBonus?: number;        // 1.2 = ×1.2 피해
    stunChance?: number;         // 0~100
    bleedStacks?: number;
    blindTurns?: number;
    accReduceTarget?: number;    // 적 ACC -3
    defBuffNextTurn?: number;    // 다음 턴 DEF +2
    moveToCover?: boolean;       // 엄폐 이동
    restrainTurns?: number;
  };
  oneTimeUse?: boolean;          // true → 사용 후 프롭 목록에서 제거
  rarity?: 'common' | 'rare';    // 등장 빈도 (전투 씬 생성 시 가중치)
}
```

**초기 프롭 카탈로그 (약 40종, 장소 7개 × 5~8)**

| 장소 | 프롭 예시 |
|------|-----------|
| LOC_TAVERN (선술집) | 의자, 병, 촛대, 테이블, 난로 장작 |
| LOC_MARKET (시장) | 나무 상자, 천막 줄, 과일 더미, 모래 바구니, 멜대 |
| LOC_GUARD (경비대) | 훈련용 목검, 방패, 사슬, 철창, 물통 |
| LOC_HARBOR (항만) | 밧줄, 그물, 돛대 나무, 물통, 밧줄 갈고리 |
| LOC_SLUMS (빈민가) | 깨진 벽돌, 쥐구멍 장작, 철망, 먼지 더미, 나무 막대 |
| LOC_NOBLE (상류 거리) | 장식 조각상, 꽃병, 촛대, 커튼 줄, 은쟁반 |
| LOC_DOCKS_WAREHOUSE (항만 창고) | 화물 상자, 빈 술통, 쇠갈고리, 천막, 기름 항아리 |

### 2.2 즉흥 카테고리 (Tier 2)

서버 상수: `server/src/engine/combat/improvised-categories.ts`

```typescript
export const IMPROVISED_CATEGORIES: ImprovisedCategory[] = [
  {
    id: 'heavy',
    keywords: ['돌','벽돌','나무','상자','목재','덩어리','뭉치','덩이'],
    effects: { damageBonus: 1.1, stunChance: 10 },
  },
  {
    id: 'sharp',
    keywords: ['파편','유리','조각','날','침','가시','못','쇠꼬챙이'],
    effects: { bleedStacks: 1 },
  },
  {
    id: 'light_source',
    keywords: ['등불','촛불','등잔','기름','불꽃','횃'],
    effects: { blindTurns: 1 },
  },
  {
    id: 'obscurant',
    keywords: ['연기','먼지','재','모래','흙','그을음'],
    effects: { accReduceTarget: -3 },
  },
  {
    id: 'restraint',
    keywords: ['끈','줄','포','천','밧줄','사슬'],
    effects: { restrainTurns: 1 },
  },
  {
    id: 'liquid',
    keywords: ['물','술','기름','잉크','피'],
    effects: { moveToCover: false, accReduceTarget: -2 },
  },
];
```

### 2.3 환상 키워드 (Tier 4)

서버 상수: `server/src/engine/combat/fantasy-keywords.ts`

```typescript
export const FANTASY_KEYWORDS: Record<string, string[]> = {
  magic: ['마법','주문','봉인','강령','저주','축복','성화','신력'],
  creature: ['드래곤','용','유니콘','그리폰','정령','악마','천사'],
  element: ['번개','화염','얼음','폭풍','화산','지진','허리케인'],
  spacetime: ['순간이동','이동술','시간','되돌림','멈춤','예지','환영'],
  summon: ['소환','부름','불러냄','창조','제물'],
  resurrection: ['부활','환생','영생','불사'],
};
```

rawInput에 위 어느 카테고리든 키워드 포함 → `fantasyFlag = true`.

### 2.4 추상 키워드 (Tier 5)

```typescript
export const ABSTRACT_KEYWORDS: string[] = [
  '주인공','플레이어','점수','레벨','경험치 추가',
  'HP 회복하기','게임','시스템','저장','로드','버그',
];
```

3개 이상 매칭 또는 명시적 메타 단어 → `abstractFlag = true`, 턴 소진.

---

## 3. 처리 파이프라인

```
[rawInput]
   │
   ▼
┌────────────────────────────────────────────┐
│ IntentParser (server/src/engine/input/)     │
│ ① Tier 1 매칭: environmentProps.keywords   │
│ ② Tier 2 매칭: IMPROVISED_CATEGORIES       │
│ ③ Tier 4 매칭: FANTASY_KEYWORDS            │
│ ④ Tier 5 매칭: ABSTRACT_KEYWORDS           │
│ else → Tier 3                               │
└────────────────────────────────────────────┘
   │
   ▼
ActionPlan {
  type: ATTACK_MELEE | DEFEND,
  targetEnemyId,
  prop?: { id, name, effects },     ← Tier 1
  improvised?: { categoryId, effects }, ← Tier 2
  tier: 1|2|3|4|5,
  flags: { fantasyFlag?, abstractFlag? },
}
   │
   ▼
┌────────────────────────────────────────────┐
│ CombatService.resolveCombatTurn             │
│ · hit/damage 공식 실행 (기본)                │
│ · prop.effects / improvised.effects 적용     │
│ · fantasyFlag: 추가 효과 없음               │
│ · abstractFlag: 턴 소진 → 기본 DEFEND 처리  │
│ · Tier 1 프롭 oneTimeUse → 프롭 목록 제거   │
│ · events에 propUsed 태그 포함               │
└────────────────────────────────────────────┘
   │
   ▼
ServerResult (flags 포함)
   │
   ▼
┌────────────────────────────────────────────┐
│ LLM Prompt (prompt-builder.service.ts)       │
│ · [사용 프롭] 블록 (Tier 1/2 시)            │
│ · [환상 재해석] 블록 (fantasyFlag 시)       │
│ · [허공 응시] 블록 (abstractFlag 시)        │
└────────────────────────────────────────────┘
   │
   ▼
Narrative (LLM)
```

---

## 4. 주요 파일·함수 변경

### 4.1 신규 파일

```
content/graymar_v1/environment_props.json      ← Tier 1 카탈로그
server/src/engine/combat/improvised-categories.ts  ← Tier 2
server/src/engine/combat/fantasy-keywords.ts       ← Tier 4
server/src/engine/combat/abstract-keywords.ts      ← Tier 5
server/src/engine/combat/prop-matcher.service.ts   ← 통합 매처
```

### 4.2 수정 파일

| 파일 | 변경 |
|------|------|
| `server/src/engine/input/intent-parser.service.ts` | PropMatcher 호출, ActionPlan에 prop/flags 주입 |
| `server/src/engine/combat/combat.service.ts` | ActionUnit 실행 시 prop.effects / improvised.effects 반영, oneTimeUse 소모 |
| `server/src/engine/hub/resolve.service.ts` | 비전투에서도 prop 시각 힌트용 로그 (선택) |
| `server/src/db/types/action-plan.ts` | `prop?`, `improvised?`, `tier`, `flags` 필드 추가 |
| `server/src/db/types/server-result.ts` | `flags.propUsed`, `flags.fantasyFlag`, `flags.abstractFlag` 추가 |
| `server/src/llm/prompts/prompt-builder.service.ts` | Tier별 [프롭]/[재해석]/[허공] 블록 추가 |
| `server/src/llm/prompts/system-prompts.ts` | 환상 재해석 스타일 가이드 섹션 추가 |
| `content/graymar_v1/nodes.json` (또는 씬별) | 각 LOCATION 씬에 `environmentProps` 배열 추가 |

### 4.3 신규 타입

```typescript
// server/src/db/types/action-plan.ts
interface ActionPlan {
  // … 기존 필드 유지
  prop?: { propId: string; name: string; effects: PropEffects };
  improvised?: { categoryId: string; effects: PropEffects };
  tier: 1 | 2 | 3 | 4 | 5;
  flags?: { fantasy?: boolean; abstract?: boolean; unlistedProp?: boolean };
}

// server/src/db/types/server-result.ts
interface ServerResultV1 {
  // … 기존
  flags?: {
    propUsed?: string;       // 사용 프롭 이름 (LLM 서술 힌트)
    propCategory?: string;   // Tier 2 카테고리 ID
    fantasyFlag?: boolean;
    abstractFlag?: boolean;
  };
}
```

---

## 5. LLM 프롬프트 통합

### 5.1 환상 재해석 블록 (prompt-builder)

fantasyFlag=true일 때 assistant 메시지에 **조건부 주입**(플래그 있을 때만):

```
[환상 재해석 지시]
플레이어가 현재 세계관에서 직접 구현 불가능한 능력("{rawInput}")을 시도했습니다.
거부하지 말고, **의도를 살려 합리적 동작으로 치환**하세요.

재해석 규칙 4가지 — 반드시 준수
① **합리적 치환**: 의도의 불꽃은 살리되 실제 가능한 동작으로 자연스럽게 연결.
   "드래곤 브레스" → 횃불·기름·등불을 잡아 휘두르는 동작, 또는 불붙은 나뭇조각을
   적에게 던지는 식. "순간이동" → 반 발짝 옆으로 미끄러지며 측면으로 파고드는 식.
   세계관이 마법을 완전히 부정하지 않고 "지금 이 상황에서는 이렇게 실현된다"는 톤.

② **외침은 홑따옴표 '인용'만 사용**: 캐릭터가 외치는 말은 **서술자의 간접 인용**으로
   처리. 큰따옴표 "..." 금지(플레이어 대사 금지 규칙 준수). 홑따옴표 '...'로 4~6자
   짧게. 의미 교환이 아니라 **의지·허세의 발화**임을 표현.

③ **비웃음·설교·메타 거부 금지**: "그런 힘은 없습니다" / "불가능합니다" / 픽 웃는 묘사
   모두 금지. 허세·결의·절박감·발작적 위트 등 인간 감정을 포착해 위트로 풀어낸다.

④ **짧고 경쾌**: 한 호흡(2~3문장) 안에 자각/치환/결과까지 담는다.

예시(참고용, 복사 금지)
> 용은 이곳에 없었지만, 손에는 횃불이 있었다. 손을 내지르며 '드래곤 브레스!'
> 외친 순간, 불꽃 묻은 끝이 적의 얼굴을 스쳤다. 그는 뒷걸음치며 비명을 삼켰다.
```

### 5.2 허공 응시 블록 (abstractFlag)

abstractFlag=true일 때 **조건부 주입**:

```
[허공 응시 지시]
플레이어가 서술 세계 바깥을 건드리는 행동("{rawInput}")을 시도했습니다.
거부하지 말고, 캐릭터의 정지·집중력 이탈·잠깐의 혼란을 서사로 풀어
해당 턴을 "아무 일도 일어나지 않은 한 호흡"으로 만드세요.
전투 긴장감은 유지 — 적의 발소리·기척·다음 동작 예고로 마무리.
```

### 5.3 사용 프롭 블록 (Tier 1/2)

Tier 1 또는 Tier 2 매칭 시 **조건부 주입**:

```
[사용한 소품]
플레이어가 "{propName}"을(를) 활용했습니다.
서술에 반드시 해당 소품의 물리적 상호작용(잡기·던지기·부서짐)을
1회 이상 구체적으로 묘사하세요. 그 소품 때문에 생긴 결과(기절/출혈/
시야 가림 등)가 있다면 적의 반응으로 드러냅니다.
```

### 5.4 기존 규칙과의 예외 조항

시스템 프롬프트(system-prompts.ts)에 아래 조항 추가:

```
## 창의 전투 입력 예외 (Tier 4 환상 재해석 시)

플레이어 대사 금지 규칙의 예외:
- 평상시: 플레이어의 모든 상호작용은 큰따옴표 없이 행동·표정으로만 표현
- Tier 4 환상 입력 시(서버가 지시): 플레이어의 외침을 **홑따옴표 '...'
  인용** 형식으로 서술자가 간접 인용하는 것만 허용
  · 큰따옴표 "..." 사용 금지 (대사 금지 규칙 유지)
  · 4~6자 짧게, 의미 교환이 아닌 의지·허세 표출
  · 예: 손을 내지르며 '드래곤 브레스!' 외쳤다

표현 다양성 규칙과 건조화 지시의 관계:
- "표현 다양성"(어휘 중복 방지)과 "반복 환상 입력 시 서술 건조화"
  (톤 강도 하강)는 서로 다른 축. 공존 가능.
```

### 5.5 조건부 프롬프트 주입 원칙

- **§5.1 환상 재해석**: `serverResult.flags.fantasyFlag === true` 시에만 주입
- **§5.2 허공 응시**: `serverResult.flags.abstractFlag === true` 시에만 주입
- **§5.3 사용 프롭**: `serverResult.flags.propUsed || propCategory` 시에만 주입
- 평상시 전투에서는 세 블록 모두 미주입 → 기존 토큰 예산 그대로 유지
- 각 블록 ≤200자 타이트 관리, [환상 재해석]만 약 350자 허용 (핵심 규칙이므로)

### 5.6 메모리 기록 — 일반 턴과 동일

Tier 4/5 턴이라도 **sessionTurns·structuredMemory에 일반 턴과 동일하게 저장**.

- NPC가 플레이어의 허세/외침을 기억하고 반응하는 것은 **자연스러운 상호작용**으로 간주
- 예: 다음 턴에 NPC가 "용이 오기 전에 끝내 주지" 같은 비꼼 대사 허용
- 별도 `ephemeral` 플래그 불필요
- 단, `tier` 값은 기록되어 퀘스트·엔딩 집계 시 참조됨 (§5.7 참조)

### 5.7 퀘스트·엔딩 성향 추적 제외

Tier 4/5 턴은 **성향 추적에서만 제외**. 서술·메모리는 정상 저장.

- ActionPlan에 `excludeFromArcRoute: true` (Tier 4/5)
- ActionPlan에 `excludeFromCommitment: true` (Tier 4/5)
- 이유: 허세·메타 입력이 arcRoute(EXPOSE_CORRUPTION 등)나 commitmentDelta에
  반영되면 의도치 않은 성향 편향 발생. Invariant 18 Procedural Plot Protection과
  동일 맥락의 안전 장치
- Tier 1~3은 일반 판정과 동일하게 성향 집계에 포함

---

## 6. 균형·운영 장치

### 6.1 반복 페널티

- 같은 Tier 1 프롭 3턴 연속 사용 → 다음 사용부터 효과 0.8x
- 같은 Tier 4 환상 키워드 연속 사용 → LLM 서술이 점점 건조해짐(시스템 프롬프트에 "반복 환상 발언 식상함 강조" 지시)

### 6.2 프롭 동적 갱신

- 전투 진입 시 서버가 씬의 `environmentProps[]` 스냅샷 생성 → BattleState에 포함
- 일회성 프롭 사용 → BattleState에서 제거
- BattleState에 남은 프롭이 5개 미만이면 LLM 프롬프트 "주변 소품" 힌트에 자동 갱신

### 6.3 클라이언트 노출

- BattlePanel 하단에 `[이 공간: 의자 · 병 · 모래]` 칩 표시 (hover 시 효과 요약)
- 칩 클릭 시 입력창에 템플릿 삽입 (`"의자를 집어 던진다"`)
- 사용 후 칩 회색 처리

---

## 7. 단계별 구현 계획

### Phase 1 — MVP (2~3일)
1. `environment_props.json` 카탈로그 작성 (7 장소 × 5~8 = 약 40종)
2. `improvised-categories.ts` / `fantasy-keywords.ts` / `abstract-keywords.ts` 상수 작성
3. `prop-matcher.service.ts` 신규 — 5-tier 분류기
4. `intent-parser.service.ts` 수정 — PropMatcher 호출, ActionPlan 확장
5. `combat.service.ts` 수정 — prop.effects 적용, oneTimeUse 처리
6. `prompt-builder.service.ts` 수정 — Tier별 블록 주입
7. 유닛 테스트: prop-matcher 20건, combat.service 확장 10건
8. 플레이테스트: `scripts/playtest.py` 확장 옵션 `--creative-input` 추가

### Phase 2 — 클라이언트 UX (2일)
1. BattlePanel에 `environmentProps` 칩 UI
2. 프롭 칩 클릭 → 입력창 템플릿 삽입
3. 사용한 프롭 회색 처리
4. Tier별 피드백(텍스트 색/아이콘) 미세 조정

### Phase 3 — 운영 최적화 (1~2일)
1. 반복 페널티 로직
2. 프롭 카탈로그 확장 (레어 · 특수 상황)
3. fantasy 반복 시 LLM 서술 건조화 지시 추가
4. 플레이테스트 10건 분석 → 콘텐츠 조정

---

## 8. 검증 기준

- [ ] rawInput에 Tier 1 프롭 키워드 포함 시 `ActionPlan.prop` 주입 → 효과 적용
- [ ] 같은 입력 반복 시 결정적 결과 (RNG seed 고정)
- [ ] Tier 4 입력(드래곤 브레스 등) → fantasyFlag=true, 기본 공격으로 치환
- [ ] LLM 서술에 "그런 힘은 없다" 류 메타 거부 0건 (regex 검출)
- [ ] 같은 프롭 4회 사용 시 효과 감소 확인
- [ ] oneTimeUse 프롭 사용 후 프롭 목록에서 제거 확인
- [ ] Tier 5 입력 → 턴 소진, 적 AI 정상 반응
- [ ] 플레이테스트 20턴 중 최소 3턴 창의 입력 → 모두 적절히 처리

---

## 9. 리스크·완화

| 리스크 | 완화책 |
|--------|--------|
| 환상 키워드 오탐 (정상 문맥에 "번개" 포함 등) | 단어 경계 `\b` 매칭, 2단어 이상 추가 검증 |
| LLM이 재해석 스타일 가이드 무시 | 가이드 문구를 짧고 강하게, 예시 1개 포함, 사후 regex 검증("그런 힘은"/"불가능합니다" 매칭 시 낮은 퀄리티 플래그) |
| 프롭 카탈로그 유지보수 부담 | 7 장소 × 5~8개 초기 고정, 이후 버그 리포트 기반 점진 확장 |
| 플레이어가 Tier 5 남발 → 턴 낭비 | 연속 3회 abstract 감지 시 튜토리얼 힌트(선택지 강제 노출) |
| Tier 1 oneTimeUse 재사용 시도 | BattleState에서 제거된 프롭 키워드 매칭 시 "이미 부서진 의자는 없다" 서술 유도 |

---

## 10. 문서 연관

- `architecture/02_combat_system.md` — 전투 공식 · 흐름
- `specs/combat_engine_resolve_v1.md` — resolveCombatTurn 구현
- `specs/input_processing_pipeline_v1.md` — IntentParser 구조
- `CLAUDE.md` Invariant 1/2/4/6/18 — 불변식 준수 포인트

---

## 11. 대화식 전투 서사 구조 (A안 — 세그먼트 서사)

현재 CombatService.resolveCombatTurn는 한 턴(플레이어 + 적) 결과를 한 덩어리로 서술.
이를 **세그먼트 기반 서사**로 분할하여 대화 리듬을 구현.

### 11.1 세그먼트 구조

한 턴의 LLM 서술을 3개 문단으로 분리 — 서버 로직 변경 없이 프롬프트 지시만 추가:

```
[세그먼트 ①] 플레이어 행동과 즉각 결과 (1~2문단)
  — rawInput이 어떻게 실행되었는지, 적의 즉각적 반응 일부 포함
  — 사용 프롭(Tier 1/2), 환상 치환(Tier 4), 허공 응시(Tier 5) 여기서 서술

[빈 줄 구분]

[세그먼트 ②] 적의 반응과 공격 (1~2문단)
  — SPEED 순서대로 생존 적 행동 묘사
  — ENEMY_MISS/DAMAGE/STATUS 이벤트 기반 서술

[빈 줄 구분]

[세그먼트 ③] 상태 정리 (1문장)
  — 남은 적 수, 거리 변화, 분위기 마무리
  — 다음 턴으로 이어지는 긴장감
```

### 11.2 구현 변경점

**최소 변경**:
- 서버 로직: **변경 없음** — resolveCombatTurn 그대로 유지
- LLM 프롬프트: system-prompts.ts 전투 섹션에 "3 세그먼트 구조" 규칙 추가
- StreamClassifier: 기존 `paragraphStart` 플래그가 `\n\n` 경계 감지 → 세그먼트 단위 자동 스트리밍

**클라이언트 보강**:
- BattlePanel: 세그먼트 ② 시작 시 해당 적 카드에 펄스 애니메이션
- "적 행동 중…" 로딩 인디케이터 (세그먼트 ② 대기 시)
- 세그먼트 간 짧은 delay(300ms)로 호흡감 연출

### 11.3 창의 전투 시스템(Tier 1~5)과의 통합

| Tier | 세그먼트 ① 서술 | 세그먼트 ② 서술 | 세그먼트 ③ 서술 |
|------|----------------|----------------|----------------|
| T1 Prop | 프롭 사용 + 효과 묘사 | 적 반응 (STUN 시 쓰러짐) | 프롭 소모·흩어짐 |
| T2 Category | 즉흥 묘사 + 카테고리 효과 | 적 반응 | 일반 정리 |
| T3 Narrative | 입력 묘사 그대로 | 적 반응 | 일반 정리 |
| T4 Fantasy | 합리적 치환 + 홑따옴표 외침 | 적 반응 (허세 비꼼 허용) | 일반 정리 |
| T5 Abstract | 허공 응시 | 적이 빈틈을 노림 | 기척 예고 |

### 11.4 예상 효과

- 첫 세그먼트 노출까지의 체감 시간 유지 (스트리밍 그대로)
- 전체 서술 길이는 동일, **리듬**이 생김
- 세그먼트 ②에서 적 카드 애니메이션 → 전투감 증가
- 추후 B안(서브턴) 도입 시에도 세그먼트 구조가 기반으로 재사용 가능

### 11.5 검증 기준 추가

- [ ] 전투 LLM 서술에 3 세그먼트 구조(2개 이상 `\n\n`) 준수율 ≥ 90%
- [ ] 세그먼트 ① → ② → ③ 순서 준수 (적 반응이 ①에 섞이지 않음)
- [ ] Tier 4 외침은 ① 세그먼트 내에서 홑따옴표 인용으로만 등장
- [ ] 클라이언트 세그먼트 ② 시작 시 적 카드 펄스 확인

---

**작성일**: 2026-04-21
**최종 수정**: 2026-04-22 — §5.1/5.4/5.5/5.6/5.7 · §11 추가 (유저 피드백 반영)
**상태**: 📎 설계 — 구현 대기
