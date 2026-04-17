# 클라이언트 컴포넌트 맵

> 정본 위치: `client/src/`
> 최종 갱신: 2026-04-17

## 컴포넌트 구조 (60 components, 5 stores)

실측 기준 (`find client/src/components -name '*.tsx' | wc -l` = **60**).
영역별: narrative 4 / input 2 / hub 14 / location 3 / screens 4 / side-panel 7 / ui 12 / layout 2 / battle 1 / party 11.

```
app/
├── layout.tsx          ← 루트 레이아웃 (글꼴: A2G, IBM Plex Sans KR, Noto Serif KR)
├── page.tsx            ← 엔트리 (/) → landing/page.tsx 렌더
├── error.tsx           ← React 에러 바운더리 (렌더 에러 복구)
├── global-error.tsx    ← 루트 에러 바운더리
├── globals.css         ← CSS 변수, 애니메이션 정의
├── sitemap.ts          ← /sitemap.xml
├── robots.ts           ← /robots.txt
├── GameClient.tsx      ← /play 게임 셸 (SplashScreen, NetworkStatus, PageTransition 마운트)
├── play/
│   └── page.tsx        ← 게임 클라이언트 진입점 (/play)
└── landing/
    ├── page.tsx        ← 랜딩 페이지 (SEO 메타)
    ├── AuthRedirect.tsx← 로그인 시 /play 리다이렉트
    ├── FeatureCard.tsx ← 랜딩 섹션 카드
    └── MobileNav.tsx   ← 랜딩 모바일 네비

components/ (60개)
├── narrative/          ← 메시지 표시 (4)
│   ├── NarrativePanel.tsx    ← 메시지 스크롤 영역
│   ├── StoryBlock.tsx        ← 메시지 렌더러 (타이핑, NPC 카드, 보정치 뱃지, 대사/서술 혼합)
│   ├── StreamingBlock.tsx    ← 스트리밍 중 실시간 렌더링 (SSE 토큰 → 점진적 텍스트)
│   └── DialogueBubble.tsx    ← NPC 대사 말풍선 (어체·speechRegister별 색조, 초상화 썸네일)
├── input/              ← 입력 처리 (2)
│   ├── InputSection.tsx      ← 텍스트 입력 + 퀵 액션 (LOCATION 전용)
│   └── QuickActionButton.tsx ← 빠른 행동 버튼
├── hub/                ← HUB 화면 (14)
│   ├── HubScreen.tsx              ← HUB 메인 화면 (4 지역 카드)
│   ├── HeatGauge.tsx              ← 도시 열기 (0~100) 시각화
│   ├── TimePhaseIndicator.tsx     ← DAWN/DAY/DUSK/NIGHT 표시
│   ├── TimePhaseTransition.tsx    ← DAY↔NIGHT 전환 알림
│   ├── LocationHeader.tsx         ← 지역 헤더
│   ├── ResolveOutcomeBanner.tsx   ← 판정 결과 배너 (순차 fade-in 공식)
│   ├── ResolveOutcomeBanner.backup.tsx ← 레거시 백업 (미사용, 참고용)
│   ├── DiceFace.tsx               ← 주사위 눈 SVG (1~6, 판정 애니메이션)
│   ├── SignalFeedPanel.tsx        ← 5채널 시그널 피드
│   ├── IncidentTracker.tsx        ← 활성 사건 control/pressure 게이지
│   ├── NpcRelationshipCard.tsx    ← NPC 5축 감정 요약
│   ├── HubNotificationList.tsx    ← 피드형 알림 목록
│   ├── PinnedAlertStack.tsx       ← 긴급 알림 고정 표시 (최대 3개)
│   └── WorldDeltaSummaryCard.tsx  ← 턴 간 세계 변화 요약
├── location/           ← LOCATION 알림/배경 (3)
│   ├── LocationImage.tsx          ← 장소 배경 이미지 (켄 번스 페이드)
│   ├── TurnResultBanner.tsx       ← 판정 결과 배너 (5초 자동 해제)
│   └── LocationToastLayer.tsx     ← 플로팅 토스트 (3초 페이드)
├── screens/            ← 전체 화면 (4)
│   ├── StartScreen.tsx            ← 프리셋/특성/이름/초상화 생성 + 인증
│   ├── RunEndScreen.tsx           ← 런 종료
│   ├── EndingScreen.tsx           ← 엔딩 (NPC epilogues, 행동 성향)
│   └── NodeTransitionScreen.tsx   ← 노드 전환
├── side-panel/         ← 사이드 패널 (7)
│   ├── SidePanel.tsx              ← 6탭 컨테이너 (Character/Inventory/Equipment/NPC/Quest/SetBonus)
│   ├── CharacterTab.tsx           ← 능력치 6개, 장비 슬롯
│   ├── InventoryTab.tsx           ← 소지품/골드
│   ├── EquipmentTab.tsx           ← 장비 관리 (장착/해제, 세트 보너스)
│   ├── SetBonusDisplay.tsx        ← 장비 세트 보너스 시각화
│   ├── NpcDossierTab.tsx          ← NPC 관계/호감도 상세 (초상화, 공개된 knownFacts)
│   └── QuestTab.tsx               ← 퀘스트 진행(S0~S5) + 발견된 fact 목록
├── ui/                 ← 공통 UI (12)
│   ├── ErrorBanner.tsx            ← 에러 표시
│   ├── NetworkStatus.tsx          ← 오프라인 감지 + 재연결 UI
│   ├── PageTransition.tsx         ← 페이지 전환 애니메이션 (7종)
│   ├── SplashScreen.tsx           ← 앱 부팅 스플래시 (로고 + dotPulse)
│   ├── InstallPrompt.tsx          ← PWA 설치 유도 배너
│   ├── LlmSettingsModal.tsx       ← LLM 설정 모달
│   ├── LlmFailureModal.tsx        ← LLM 실패 모달 (재시도/건너뛰기/닫기)
│   ├── StatTooltip.tsx            ← 스탯 툴팁
│   ├── NewsModal.tsx              ← 그레이마르 호외 (양피지 모달 + nano 기사)
│   ├── PortraitCropModal.tsx      ← 초상화 크롭 (react-easy-crop, 4:5)
│   ├── BugReportButton.tsx        ← 인게임 버그 리포트 트리거 버튼
│   └── BugReportModal.tsx         ← 버그 리포트 + 클라 스냅샷/DOM 요약 전송
├── layout/             ← 레이아웃 (2)
│   ├── Header.tsx                 ← 데스크톱 HUD (HP/Stamina 바, 자동 숨김)
│   └── MobileBottomNav.tsx        ← 모바일 하단 네비 (햄버거 메뉴)
├── battle/             ← 전투 화면 (1)
│   └── BattlePanel.tsx            ← 적 카드 (HP, 상태효과, 거리/각도)
└── party/              ← 파티 시스템 (11)
    ├── PartyMainScreen.tsx        ← 파티 메인 (내 파티 + 검색)
    ├── PartyCreateModal.tsx       ← 파티 생성 모달
    ├── PartyJoinModal.tsx         ← 초대코드 가입 모달
    ├── PartyHUD.tsx               ← 던전 중 파티 HUD (멤버 HP/상태)
    ├── PartyLobby.tsx             ← 로비 (준비 토글 + 시작)
    ├── PartyMemberCard.tsx        ← 멤버 카드 (초상화, 준비/AI 상태)
    ├── PartyChatWindow.tsx        ← 채팅 히스토리 (SSE 실시간)
    ├── PartyChatInput.tsx         ← 채팅 입력
    ├── PartyTurnStatus.tsx        ← 4인 동시 턴 제출 상태 + 카운트다운
    ├── VoteModal.tsx              ← 이동 투표 제안/참여
    └── LootDistribution.tsx       ← 던전 종료 보상 분배 화면
```

> StoryBlock 이번 세션 반영: `renderNarrationLines` 헬퍼로 서술 개행 처리, `StreamTyper` once-guard (StreamTyper→onComplete 중복 방지), 공통 `font-narrative` 부모 래퍼 통일(L888/L989), `data-dialogue-bubble` DOM 스캔으로 대사/서술 영역 분리.

---

## 상태 관리 (5 stores)

```
store/
├── game-store.ts       ← Zustand (게임 전체 상태)
├── auth-store.ts       ← JWT 인증 (login/register/hydrate)
├── settings-store.ts   ← 텍스트 속도 + 스트리밍 토글 (localStorage)
├── party-store.ts      ← 파티 상태 (로비, 채팅, 투표, SSE 구독)
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
  isStreaming: boolean;              // LLM 스트림 수신 중
  streamBuffer: string;              // StreamTyper가 읽어 소진하는 큐
  // actions
  startNewGame(presetId, gender, traitId, bonusStats, name, portraitUrl): void;
  submitAction(text): void;
  submitChoice(choiceId): void;
  pollLlm(): void;
  retryLlmNarrative(): void;
  skipLlmNarrative(): void;
  startLlmStream(runId, turnNo): void;  // SSE 연결
  stopLlmStream(): void;
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

## 라이브러리 (10 files)

```
lib/
├── api-client.ts        ← Server API 래퍼 (retryLlm, party 엔드포인트 포함)
├── result-mapper.ts     ← ServerResultV1 → StoryMessage[] (RESOLVE 포함)
├── hud-mapper.ts        ← Diff → PlayerHud/Inventory/Enemy update
├── api-errors.ts        ← ApiError 클래스
├── notification-utils.ts← 알림 중복 제거, 정렬, 만료 필터
├── stream-parser.ts     ← 문장 단위 버퍼링 상태 머신 (토큰 → 문장 경계 감지)
├── llm-stream.ts        ← LLM SSE 연결 유틸 (EventSource 래퍼, 재연결, 토큰 인증)
├── sse-client.ts        ← 범용 SSE 클라이언트 (파티 스트림 공용)
├── network-logger.ts    ← fetch/SSE 왕복 시간 + 상태 로깅 (버그 리포트 스냅샷용)
└── ui-logger.ts         ← UI 이벤트 로그 (typer, stream, transition) — 콘솔/localStorage
```

---

## 데이터 (3 files)

```
data/
├── presets.ts             ← 6 캐릭터 프리셋 정의 (클라이언트용)
├── items.ts               ← 아이템 카탈로그 (40+, ITEM_CATALOG)
└── stat-descriptions.ts   ← 스탯 설명 텍스트
```

---

## 타입 정의

```
types/
└── game.ts   ← WorldStateUI, BattleEnemy, IncidentSummaryUI,
                 SignalFeedItemUI, NpcEmotionalUI, OperationProgressUI,
                 EndingResult, GameNotification, PartyStateUI 등
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

## BugReportModal 확장

버그 리포트 제출 시 서버로 함께 전송되는 스냅샷:
- `serializeMessage(msg)` — StoryMessage 요약(id/type/role/textLen/createdAt)
- `collectClientSnapshot()` — phase/runId/turn/playerHud/worldState/네트워크 로그(network-logger)
- `collectDomSummary()` — data-dialogue-bubble/StreamingBlock DOM 개수·가시성 요약
- `clientVersion` — `process.env.NEXT_PUBLIC_CLIENT_VERSION` (빌드 태그)

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

> 경고: `--panel-bg`, `--accent-blue`, `--border-color`는 미정의 — 사용 금지.
