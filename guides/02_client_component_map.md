# 클라이언트 컴포넌트 맵

> 정본 위치: `client/src/`
> 최종 갱신: 2026-03-25

## 컴포넌트 구조 (37 components, 3 stores)

```
app/
├── layout.tsx       ← 루트 레이아웃 (글꼴: A2G, IBM Plex Sans KR, Noto Serif KR)
├── page.tsx         ← GamePage (메인 라우터, phase 기반 렌더링)
└── globals.css      ← CSS 변수, 애니메이션 정의

components/ (31개)
├── narrative/       ← 메시지 표시
│   ├── NarrativePanel.tsx    ← 메시지 스크롤 영역
│   └── StoryBlock.tsx        ← 메시지 렌더러 (타이핑 애니메이션)
├── input/           ← 입력 처리
│   ├── InputSection.tsx      ← 텍스트 입력 + 퀵 액션 (LOCATION 전용)
│   └── QuickActionButton.tsx ← 빠른 행동 버튼
├── battle/          ← 전투 화면
│   └── BattlePanel.tsx       ← 적 카드 (HP바, 상태효과, 거리/각도)
├── layout/          ← 레이아웃
│   ├── Header.tsx            ← 데스크톱 HUD (HP/Stamina 바)
│   └── MobileBottomNav.tsx   ← 모바일 하단 네비게이션
├── hub/             ← HUB 화면 (11 components)
│   ├── HubScreen.tsx              ← HUB 메인 화면 (4 지역 카드)
│   ├── HeatGauge.tsx              ← 도시 열기 (0~100) 시각화
│   ├── TimePhaseIndicator.tsx     ← DAWN/DAY/DUSK/NIGHT 표시
│   ├── LocationHeader.tsx         ← 지역 헤더
│   ├── ResolveOutcomeBanner.tsx   ← 판정 결과 배너
│   ├── SignalFeedPanel.tsx        ← 5채널 시그널 피드
│   ├── IncidentTracker.tsx        ← 활성 사건 control/pressure 게이지
│   ├── NpcRelationshipCard.tsx    ← NPC 5축 감정 요약
│   ├── HubNotificationList.tsx    ← 피드형 알림 목록
│   ├── PinnedAlertStack.tsx       ← 긴급 알림 고정 표시 (최대 3개)
│   └── WorldDeltaSummaryCard.tsx  ← 턴 간 세계 변화 요약
├── location/        ← LOCATION 알림 레이어
│   ├── TurnResultBanner.tsx       ← 판정 결과 배너 (5초 자동 해제)
│   └── LocationToastLayer.tsx     ← 플로팅 토스트 (3초 페이드)
├── screens/         ← 전체 화면
│   ├── StartScreen.tsx            ← 프리셋 선택 + 인증
│   ├── RunEndScreen.tsx           ← 런 종료
│   ├── EndingScreen.tsx           ← 엔딩 (NPC epilogues, 행동 성향)
│   └── NodeTransitionScreen.tsx   ← 노드 전환
├── side-panel/      ← 사이드 패널
│   ├── SidePanel.tsx              ← 4탭 컨테이너
│   ├── CharacterTab.tsx           ← 능력치 6개, 장비 슬롯
│   ├── InventoryTab.tsx           ← 소지품/골드
│   ├── EquipmentTab.tsx           ← 장비 관리 (장착/해제, 세트 보너스)
│   └── SetBonusDisplay.tsx        ← 장비 세트 보너스 시각화
└── ui/              ← 공통 UI
    ├── ErrorBanner.tsx            ← 에러 표시
    ├── LlmSettingsModal.tsx       ← LLM 설정 모달
    ├── LlmFailureModal.tsx        ← LLM 실패 모달 (재시도/건너뛰기/닫기)
    ├── StatTooltip.tsx            ← 스탯 툴팁
    ├── BugReportButton.tsx        ← 인게임 버그 리포트 트리거 버튼
    └── BugReportModal.tsx         ← 버그 리포트 작성 모달 (category, description)
```

---

## 상태 관리 (3 stores)

```
store/
├── game-store.ts       ← Zustand (게임 전체 상태)
├── auth-store.ts       ← JWT 인증 (login/register/hydrate)
├── settings-store.ts   ← 텍스트 속도 (localStorage)
└── game-selectors.ts   ← Notification 쿼리 셀렉터
```

### game-store.ts 주요 상태/액션

```typescript
interface GameState {
  phase: GamePhase;
  runId: string | null;
  currentTurnNo: number;
  messages: StoryMessage[];
  playerHud: PlayerHud;
  characterInfo: CharacterInfo;
  worldState: WorldStateUI;
  choices: ChoiceItem[];
  notifications: GameNotification[];
  pinnedAlerts: GameNotification[];
  worldDeltaSummary: WorldDeltaSummaryUI | null;
  // actions
  startNewGame(presetId, gender): void;
  submitAction(text): void;
  submitChoice(choiceId): void;
  pollLlm(): void;
  retryLlmNarrative(): void;
  skipLlmNarrative(): void;
}
```

### game-selectors.ts Notification 셀렉터

```typescript
selectHubNotifications()       // HUB/GLOBAL scope
selectLocationNotifications()  // LOCATION/TURN_RESULT scope
selectBannerNotifications()    // BANNER presentation
selectToastNotifications()     // TOAST presentation
selectFeedNotifications()      // FEED_ITEM presentation
```

---

## 라이브러리 (4 files)

```
lib/
├── api-client.ts       ← Server API 래퍼 (retryLlm 포함)
├── result-mapper.ts    ← ServerResultV1 → StoryMessage[] (RESOLVE 포함)
├── hud-mapper.ts       ← Diff → PlayerHud/Inventory/Enemy update
├── api-errors.ts       ← ApiError 클래스
└── notification-utils.ts ← 알림 중복 제거, 정렬, 만료 필터링
```

---

## 데이터 (3 files)

```
data/
├── presets.ts             ← 4 캐릭터 프리셋 정의 (클라이언트용)
├── items.ts               ← 아이템 카탈로그 (40+, ITEM_CATALOG)
└── stat-descriptions.ts   ← 스탯 설명 텍스트
```

---

## 타입 정의

```
types/
└── game.ts   ← WorldStateUI, BattleEnemy, IncidentSummaryUI,
                 SignalFeedItemUI, NpcEmotionalUI, OperationProgressUI,
                 EndingResult, GameNotification 등
```

---

## Client State Machine

```
TITLE → LOADING → HUB → LOCATION ⇄ COMBAT → HUB (순환)
                   ↕         ↕
                 ERROR    RUN_ENDED → EndingScreen
```

Phase는 `derivePhase(nodeType, result)` 함수로 도출:
- HUB: nodeType === 'HUB' 또는 null
- LOCATION: nodeType === 'LOCATION' (+ 기존 EVENT/REST/SHOP/EXIT)
- COMBAT: nodeType === 'COMBAT'

---

## Notification System (scope × presentation)

| Scope | Presentation | 컴포넌트 | 설명 |
|-------|-------------|---------|------|
| HUB | FEED_ITEM | HubNotificationList | HUB 피드형 알림 |
| HUB/GLOBAL | BANNER (pinned) | PinnedAlertStack | 긴급 고정 알림 (최대 3개) |
| HUB | CARD | WorldDeltaSummaryCard | 세계 변화 요약 |
| TURN_RESULT | BANNER | TurnResultBanner | 판정 결과 (5초 자동 해제) |
| LOCATION | TOAST | LocationToastLayer | 플로팅 토스트 (3초 페이드) |

---

## CSS 변수 (Dark Theme)

```css
--bg-primary: #0F0F0F         /* 메인 배경 */
--bg-secondary: #0A0A0A       /* 보조 배경 */
--bg-card: #141414             /* 카드 배경 */
--text-primary: #FAF8F5        /* 주 텍스트 */
--text-secondary: #888         /* 보조 텍스트 */
--text-muted: #666             /* 약한 텍스트 */
--gold: #C9A962                /* 강조/골드 */
--hp-red: #E74C3C              /* HP 바 */
--stamina-green: #27AE60       /* 기력 바 */
--info-blue: #60A5FA           /* 정보 파란색 */
--border-primary: #1F1F1F      /* 기본 테두리 */
```

> ⚠️ `--panel-bg`, `--accent-blue`, `--border-color`는 미정의 — 사용 금지
