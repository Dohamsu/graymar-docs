# 42. Combat UI Button Form — 전투 UI 버튼 기반 재설계

> **목표**: 전투 선택지를 리스트(17개 숫자 목록)에서 **버튼형 레이아웃**으로 전환.
> 적 카드 직접 클릭으로 타겟 선택(🅒) + 주요 5 행동 버튼(🅓) 조합.
>
> **효과**: 인지 부담 -60%, 모바일 터치 친화, 창의 입력 유도 향상.

---

## 1. 목적 및 성공 기준

### 1.1 문제 정의
- **현재**: NarrativePanel에 `1. 적A 근접 공격 / 2. 적B 근접 공격 / ...` 식 17개 숫자 리스트
- **문제**: 적 3명이면 콤보가 ×2 폭발, 모바일 스크롤 지옥, 비슷한 선택지 중복
- **부작용**: 창의 입력창(`InputSection`)이 리스트 아래에 묻혀서 창의 전투 시스템 활용도 ↓

### 1.2 성공 기준
- [ ] 상시 표시 버튼 수 ≤ 5개 (아이콘 + 레이블)
- [ ] 적 3명 기준 visible 선택 경로 17개 → 7~8개 (−60%)
- [ ] 타겟 선택 = 적 카드 직접 클릭 (선택지에서 분리)
- [ ] 모바일(393×852)·데스크톱(1440×900) 모두 1화면 내 완료
- [ ] 자유 입력창이 버튼과 동등하거나 우선 위치에 노출
- [ ] 기존 전투 로직(CombatService, ActionPlan)은 변경 없음

---

## 2. 레이아웃 설계

### 2.1 데스크톱 (1440×900)

```
┌──────────────────────────────────────────────────────────────────┐
│ [상단 바] 그레이마르 왕국  그레이마르 항만  밤 안전  HP STA G   │
├──────────────────────────────────────────────────────────────────┤
│ [적 패널 — sticky]                                               │
│ ┌───────────┬───────────┬───────────┐                            │
│ │ 건달 A ⭕ │ 건달 B   │ 칼잡이   │  ← 클릭 시 테두리 강조      │
│ │ 3/14 HP   │ 14/14    │ 18/18    │                              │
│ │ 밀착/정면 │ 밀착/측면│ 중거리   │                              │
│ └───────────┴───────────┴───────────┘                            │
├──────────────────────────────────────────────────────────────────┤
│ [서술 패널 — 주 영역, 스크롤]                                    │
│   ...Dual-Track Streaming 서술...                                │
├──────────────────────────────────────────────────────────────────┤
│ [CombatActionBar — 전투 전용]                                    │
│ ┌──────┬──────┬──────┬──────┬──────┐                             │
│ │ ⚔️   │ 🛡️  │ 🧪   │ ✨   │ 🏃   │  ← 5 주요 버튼 (72px 정사각) │
│ │ 공격 │ 방어 │ 아이템│ 특수 │ 이탈 │                             │
│ └──────┴──────┴──────┴──────┴──────┘                             │
│  (특수 탭 펼침 시)                                               │
│  ┌─────────┬─────────┬─────────┬─────────┐                        │
│  │ 연속공격│ 회피    │ 환경    │ 이동    │                        │
│  └─────────┴─────────┴─────────┴─────────┘                        │
├──────────────────────────────────────────────────────────────────┤
│ [자유 입력창 — 강조]                                              │
│  ┌────────────────────────────────────────────────┐              │
│  │ 예: 의자를 집어 던진다 / 드래곤 브레스!         │  [⚡ 실행]  │
│  └────────────────────────────────────────────────┘              │
│  💡 창의적 행동은 직접 입력하세요                                │
└──────────────────────────────────────────────────────────────────┘
                      [우측 SidePanel 별도]
```

### 2.2 모바일 (393×852)

```
┌──────────────────────────────┐
│ [상단 바, 축약]               │
├──────────────────────────────┤
│ [적 패널 — 수직 스택]         │
│ ┌──────────────────────────┐ │
│ │ 건달 A ⭕  3/14          │ │
│ ├──────────────────────────┤ │
│ │ 건달 B    14/14          │ │
│ ├──────────────────────────┤ │
│ │ 칼잡이    18/18          │ │
│ └──────────────────────────┘ │
├──────────────────────────────┤
│ [서술 패널]                   │
│ ...                           │
├──────────────────────────────┤
│ [CombatActionBar]             │
│ ┌────┬────┬────┬────┬────┐   │
│ │ ⚔️ │ 🛡️│ 🧪 │ ✨ │ 🏃 │   │
│ └────┴────┴────┴────┴────┘   │
│ 공격  방어 아이템 특수 이탈   │
├──────────────────────────────┤
│ [자유 입력창]                 │
│ ┌──────────────────────┐[⚡]│
│ └──────────────────────┘    │
└──────────────────────────────┘
```

---

## 3. 컴포넌트 구조

### 3.1 신규 컴포넌트
```
client/src/components/battle/
├── BattlePanel.tsx              (기존, 적 카드 렌더)
├── EnemyCard.tsx                (신규 분리, 클릭 이벤트 + selected prop)
├── CombatActionBar.tsx          (신규, 5 주요 버튼 + 특수 펼침)
├── CombatActionButton.tsx       (신규, 아이콘 + 레이블 + tooltip)
├── CombatItemPickerModal.tsx    (신규, 아이템 사용 모달)
└── CombatTargetIndicator.tsx    (신규, 선택된 타겟 표시 작은 위젯)
```

### 3.2 컴포넌트 트리
```
GameClient
└── (phase === 'COMBAT')
    ├── BattlePanel
    │   └── EnemyCard × N (onClick → setSelectedTargetId)
    ├── NarrativePanel (서술만, 선택지 영역 전투 시 숨김)
    ├── CombatActionBar (신규)
    │   ├── CombatActionButton × 5  (공격/방어/아이템/특수/이탈)
    │   ├── CombatActionButton × 4  (특수 펼침 시)
    │   └── CombatTargetIndicator   (현재 선택 타겟 표시)
    └── InputSection (기존, 강조 스타일 보강)
```

---

## 4. 상태 관리

### 4.1 Zustand Store 확장
```typescript
// client/src/store/game-store.ts 확장
interface GameState {
  // 기존 필드 유지
  // ...

  // 전투 UI 신규
  combatSelectedTargetId: string | null;  // 선택된 적 id
  combatExpandedPanel: 'none' | 'special' | 'items';  // 펼친 탭
  setCombatTarget: (id: string | null) => void;
  toggleCombatPanel: (panel: 'special' | 'items') => void;
}
```

### 4.2 선택 로직 (확정 2026-04-22)
- **기본 타겟 = 마지막 공격한 적** (`lastAttackedEnemyId`)
  - 전투 진입 시엔 없음 → 첫 ENGAGED 적 임시 지정
  - 플레이어가 `attack_melee_enemy_X` 수행할 때마다 store 갱신
  - 사망 시 가장 최근에 공격했던 다른 생존 적으로 이동
- 사용자가 적 카드 클릭으로 수동 재선택 가능

---

## 5. 버튼 매핑 규칙

### 5.1 주요 5 버튼
| 아이콘 | 레이블 | 동작 | 선택 조건 |
|--------|--------|------|-----------|
| ⚔️ Sword | 공격 | `attack_melee_{selectedTargetId}` | 항상 활성 |
| 🛡️ Shield | 방어 | `defend` | 항상 활성 |
| 🧪 Flask | 아이템 | CombatItemPickerModal | inventory에 CONSUMABLE+combat 있을 때만 |
| ✨ Sparkles | 특수 | 하단 특수 패널 토글 | 항상 활성 |
| 🏃 Running | 이탈 | `combat_avoid` (flee+avoid 통합) | 항상 활성 |

### 5.2 특수 펼침 (✨ 클릭 시)
| 아이콘 | 레이블 | 동작 | 선택 조건 |
|--------|--------|------|-----------|
| ⚡ Zap | 연속 공격 | `combo_double_attack_{selectedTargetId}` | stamina ≥ 2 |
| 💨 Wind | 회피 태세 | `evade` | 항상 활성 |
| 🌀 Cyclone | 환경 활용 | `env_action` | 항상 활성 |
| ➡️ ArrowRight | 전방 이동 | `move_forward` | 적 MID/FAR 존재 |
| ⬅️ ArrowLeft | 후방 이동 | `move_back` | 적 ENGAGED 존재 |

### 5.3 자동 숨김 규칙
- stamina 0: 연속 공격 비활성 (grayed out)
- inventory 비어있으면 🧪 아이템 버튼 숨김
- 모든 적 사망: 전체 Action Bar 숨김

---

## 6. 서버 측 변경 (최소)

### 6.1 buildCombatChoices() 리팩토링
**Before**: 17개 선택지 배열 반환
**After**: 최소한의 CHOICE id만 반환 (UI가 타겟 조합하므로)

```typescript
private buildCombatChoices(...): ChoiceItem[] {
  return [
    // 클라이언트가 선택된 타겟을 조합해서 attack_melee_{enemyId} 생성
    { id: 'attack_melee', label: '공격', ... },
    { id: 'defend', label: '방어', ... },
    { id: 'evade', label: '회피', ... },
    { id: 'env_action', label: '환경 활용', ... },
    { id: 'combat_avoid', label: '전투 이탈', ... },
    // 콤보/이동/아이템은 클라이언트가 필요 시 호출 (기존 choiceId 그대로 유지)
  ];
}
```

**하위 호환성 유지**: 기존 choiceId(예: `attack_melee_enemy_01`)는 서버에서 여전히 인식. 클라이언트가 타겟 ID를 조합해 전송.

### 6.2 mapCombatChoiceToActionPlan() 변경 없음
기존 로직 그대로 — 클라이언트가 타겟을 포함한 choiceId를 보내면 정상 처리.

---

## 7. UX 세부 사항

### 7.1 타겟 선택 상호작용
- **기본 선택**: 첫 ENGAGED 적 (자동)
- **적 카드 hover**: 커서 pointer + 약한 glow
- **적 카드 클릭**: 선택 상태 전환, 카드 테두리 골드 색
- **타겟 변경 피드백**: Action Bar 버튼의 `공격` 레이블 아래에 `→ 건달 A` 표시
- **모든 공격 계열 버튼**: 현재 선택된 타겟을 암묵적 타겟으로 사용

### 7.2 특수 패널 펼침 애니메이션
- ✨ 버튼 클릭 → 하단 패널 slide-down (200ms)
- 배경색으로 구분 (var(--bg-secondary))
- 다른 주요 버튼 클릭 시 자동 닫힘

### 7.3 자유 입력창 강조
- placeholder 예시 순환: "의자를 집어 던진다" / "드래곤 브레스!" / "옆으로 피하며 검을 긋는다"
- 💡 힌트 라인 추가: "창의적 행동은 직접 입력하세요"
- 입력창 높이 기존 대비 +20% (더 눈에 띄게)

### 7.4 단축키
**없음** (확정 2026-04-22) — 모바일/데스크톱 UX 혼선 방지, 버튼 탭/클릭 중심.

---

## 8. 단계별 구현 로드맵

### Phase 1 — BattlePanel 분리 + 타겟 선택 (0.5일)
1. `EnemyCard.tsx` 분리 (기존 inline component → 독립 파일)
2. `EnemyCard`에 `onClick` prop + `selected` 스타일
3. `game-store.ts`에 `combatSelectedTargetId` 추가
4. 전투 진입 시 첫 ENGAGED 적 자동 선택
5. E2E 테스트: 적 카드 클릭 → 선택 상태 반영

### Phase 2 — CombatActionBar 신규 (1일)
1. `CombatActionBar.tsx` 신규 컴포넌트
2. 주요 5 버튼 (공격/방어/아이템/특수/이탈) 렌더
3. 각 버튼 onClick 시 handleChoiceSelect 호출 — 타겟은 store에서 읽음
4. 특수 펼침 패널 (연속 공격/회피/환경/이동)
5. 아이템 버튼 → CombatItemPickerModal (기존 InventoryTab 재사용 가능?)
6. GameClient에서 `phase === 'COMBAT'`일 때 CombatActionBar 렌더
7. NarrativePanel의 선택지 영역은 전투 시 숨김

### Phase 3 — 자유 입력 강조 + 반응형 (0.5일)
1. InputSection에 combat 모드 prop 추가 (placeholder 변경)
2. placeholder 예시 순환 애니메이션
3. 모바일 레이아웃 조정 (세로 스택)
4. 단축키 핸들러 추가

### Phase 4 — 서버 buildCombatChoices() 축약 (0.5일)
1. 반환 배열 축소 (5~6 기본 + 아이템)
2. 클라이언트 레거시 choiceId 그대로 전송 (backwards compat)
3. 서버 테스트 확장

---

## 9. 검증 기준

- [ ] 전투 진입 시 자동 타겟 선택 (첫 ENGAGED 적)
- [ ] 적 카드 클릭으로 타겟 변경 가능
- [ ] 타겟 적 사망 시 자동 재선택
- [ ] 주요 5 버튼 항상 표시 (또는 조건부 숨김/disabled)
- [ ] 특수 펼침 토글 동작
- [ ] 아이템 모달 → inventory consumable 표시 + 사용
- [ ] 자유 입력창 창의 전투 (Tier 1/4/5) 정상 동작
- [ ] 모바일·데스크톱 각각 1화면 내 완결
- [ ] 기존 CombatService 로직 변경 없음
- [ ] 서버 테스트 567/567 여전히 PASS

---

## 10. 리스크 및 완화

| 리스크 | 완화책 |
|--------|--------|
| 기존 선택지 CHOICE 경로 깨짐 | buildCombatChoices 하위 호환 유지, 클라이언트만 레거시 id 전송 |
| 타겟 자동 선택이 의도와 다름 | 선택 변경 UI 명확(하이라이트), 적 카드 hover tooltip |
| 특수 펼침 발견성 낮음 | ✨ 아이콘 +"특수" 텍스트 명확, 펼침 상태 시각 피드백 |
| 모바일 적 3명 세로 스택 높이 부담 | 적 카드 compact 모드 (한 줄 높이 60px) |
| NarrativePanel 선택지 숨김으로 타 상황 혼동 | `phase === 'COMBAT'` 조건 정확히 분리, LOCATION 선택지는 그대로 |
| 자유 입력창 + 버튼 동시 사용 시 혼선 | 버튼 클릭 시 입력창 텍스트 자동 지움 (optional) |

---

## 11. 문서 연관

- [[architecture/41_creative_combat_actions|creative combat actions]] — 창의 전투 MVP (입력창 강조 연관)
- `client/src/components/battle/BattlePanel.tsx` — 기존 구현
- `server/src/engine/combat/combat.service.ts` — buildCombatChoices
- [[specs/combat_engine_resolve_v1|combat engine resolve v1]] — CHOICE → ActionPlan 매핑

---

**작성일**: 2026-04-22
**상태**: 📎 설계 — 구현 대기
