# 15. Notification System

세 문서(`15_notification_system_design.md`, `16_notification_ui_build_plan.md`, `17_notification_client_bridge.md`)를 통합. 설계 → UI 빌드 → 클라이언트 브릿지까지 한 번에 참조한다.

Notification 계층은 단순 로그가 아니라 **세계 변화와 플레이어 행동의 후속 반응을 UI 신호로 번역하는 계층**이다.

핵심 원칙
- 플레이어가 자리를 비운 동안의 세계 변화를 놓치지 않게 한다.
- 방금 한 행동의 결과와 후폭풍을 즉시 이해시킨다.
- HUB는 전략 정보, LOCATION은 몰입 정보로 분리한다.
- 알림은 행동 유도 장치로 기능한다.

---

## 1. 설계

### 1.1 정보 계층 분리
- **Signal Feed**: 세계에서 발생한 원시 신호
- **World Delta**: 한 턴/한 복귀 단위의 상태 변화 묶음
- **Notification**: 플레이어 UI에 전달할 가공된 결과물

### 1.2 화면별 역할
| 화면 | 역할 | 노출 | 비노출 |
|------|------|------|--------|
| HUB | 전역 전략 대시보드 | pinned alert, world delta summary, incident tracker, signal feed, unread inbox | — |
| LOCATION | 현장 몰입 | 짧은 토스트, 결과 배너, 위험 경고 | 전역 장문 요약, 미방문 지역 로그 |
| TURN RESULT | 행동 결과 요약 | 1~2문장 배너 | — |
| COMBAT | 최소 정보 | 위협/상태이상/증원·퇴로 차단 | 일반 세계 요약, 허브형 피드 |

### 1.3 타입 정의

```ts
export type NotificationScope =
  | 'LOCATION' | 'TURN_RESULT' | 'HUB' | 'GLOBAL';

export type NotificationKind =
  | 'INCIDENT' | 'WORLD' | 'RELATION' | 'ACCESS' | 'DEADLINE' | 'SYSTEM';

export type NotificationPriority =
  | 'LOW' | 'MID' | 'HIGH' | 'CRITICAL';

export type NotificationPresentation =
  | 'TOAST' | 'BANNER' | 'FEED_ITEM' | 'PINNED_CARD' | 'MODAL';

export interface GameNotification {
  id: string;
  tickNo?: number;
  turnNo: number;
  scope: NotificationScope;
  kind: NotificationKind;
  priority: NotificationPriority;
  presentation: NotificationPresentation;

  title: string;
  body: string;

  locationId?: string | null;
  incidentId?: string | null;
  npcId?: string | null;
  factionId?: string | null;

  actionLabel?: string | null;
  actionTarget?: string | null;

  visibleFromTurn?: number;
  expiresAtTurn?: number | null;

  dedupeKey?: string | null;
  pinned?: boolean;
  read?: boolean;
  acknowledged?: boolean;

  tags?: string[];
}

export interface WorldDeltaSummaryUI {
  headline: string;
  visibleChanges: string[];
  urgency: 'LOW' | 'MID' | 'HIGH';
}
```

### 1.4 Kind별 예시
- **INCIDENT**: 단계 상승/하락, 압력 증가, deadline 접근, 경쟁 세력 개입, 방치 악화 예고
- **WORLD**: heat 상승, 도시 긴장, 지역 위험도, 야간 경계, 오프스크린 지역 변화
- **RELATION**: NPC 의심, 세력 평판, 적대/우호 플래그, 접촉 차단/개방
- **ACCESS**: 루트 잠금/해금, 상점·지역·인물 접근 변화, 사회적 접근 난이도
- **DEADLINE**: soft deadline 경고, 사건 임계치 도달, 미개입 경고

### 1.5 Priority 기준
| 레벨 | 기준 |
|------|------|
| LOW | 정보성, 분위기 전달 |
| MID | 행동 유도, 방치 시 손실 가능 |
| HIGH | 즉시 대응 권장, 루트 손상 가능 |
| CRITICAL | 절대 놓치면 안 되는 전역 경보, 허브 상단 고정 |

### 1.6 생성 타이밍
- **LOCATION 행동 직후** → scope=LOCATION, TOAST/BANNER (예: "누군가 당신을 지켜보고 있다.")
- **턴 결과 직후** → scope=TURN_RESULT, BANNER (예: "정보는 얻었지만 흔적을 남겼습니다.")
- **offscreenTick / worldTick 이후** → scope=HUB, FEED_ITEM/PINNED_CARD (예: "항만 봉쇄가 강화되었습니다.")
- **임계치 돌파** → scope=GLOBAL, CRITICAL, PINNED_CARD (예: "도시 긴장이 위험 수위에 도달했습니다.")

### 1.7 중복/병합 규칙
- `dedupeKey = ${incidentId}:${kind}:${priority}:${band}` 로 같은 턴 내 중복 제거.
- 같은 `locationId` + 같은 `incidentId` + 1~2턴 내 연속 + 의미상 "상황 악화" → 단일 요약으로 병합.
  - 예: "경비 증가 / 소문 확산 / 접근 악화" → "항만 상황 악화".
- 읽지 않은 CRITICAL이 있으면 유사 MID는 축약.
- Heat 변화는 임계 밴드 변경 시에만 재노출.
- 동일 flavor 텍스트는 2~3턴 내 재노출 금지.

### 1.8 서버 파이프라인

```text
resolve / worldTick / offscreenTick
  → signalFeed 생성
  → worldDelta 생성
  → notificationAssembler.build(...)
  → ui.notifications / ui.pinnedAlerts / ui.worldDeltaSummary / ui.hubInbox 반환
```

`notificationAssembler` 책임: raw signal 수집 → 우선순위 판별 → 중복 제거 → 병합 요약 → scope/presentation 결정 → pinned 분리.

### 1.9 서버 응답 계약

```ts
export type ServerResultUI = {
  // 기존
  availableActions: string[];
  targetLabels: Array<{ id: string; name: string; hint: string }>;
  actionSlots: { base: number; bonusAvailable: boolean; max: number };
  toneHint: string;
  worldState?: WorldStateUI;
  resolveOutcome?: 'SUCCESS' | 'PARTIAL' | 'FAIL';
  resolveBreakdown?: ResolveBreakdown;

  // 신규
  signalFeed?: SignalFeedItem[];
  notifications?: GameNotification[];
  pinnedAlerts?: GameNotification[];
  worldDeltaSummary?: WorldDeltaSummaryUI;
  hubInbox?: {
    unreadCount: number;
    items: GameNotification[];
  };
};
```

### 1.10 World Delta Summary 생성 규칙
- 최대 5줄.
- 전역 변화 > 플레이어 관련 변화 우선.
- 미방문 지역 변화도 포함 가능.
- flavor + actionable hint를 함께 제공.
- 예: "항만 창고 수색이 확대되었습니다." / "시장에서 당신의 개입을 두고 소문이 돌고 있습니다."

### 1.11 금지 패턴 / 문구 스타일
- 금지: `pressure +12`, `suspicion +5`, `world_state updated`, 매 턴 반복 메시지, LOCATION에서 전역 정보 남발, 전투 중 허브 피드.
- 권장: "수색이 본격화됩니다." / "당신의 이름이 퍼지고 있습니다." / "누군가 먼저 손을 썼습니다."

---

## 2. UI 빌드

### 2.1 화면 레이아웃

**HUB**
```text
[ Hub Header ]
[ PinnedAlertStack ]
[ WorldDeltaSummaryCard ]
[ Location Cards ] [ Heat Resolution ]
[ IncidentTracker ]
[ HubNotificationList ]
[ SignalFeedPanel ]
[ NpcRelationshipCard ]
[ Inbox Button / Unread Count ]
```

**LOCATION**
```text
[ Scene Header ]
[ TurnResultBanner ]
[ NarrativePanel ]
[ Choice / Input Panel ]
[ LocationToastLayer ]   // 화면 우상단 floating
```

**COMBAT**
```text
[ Combat HUD ]
[ CombatWarningStrip ]
[ Action Panel ]
```

### 2.2 컴포넌트 트리

```ts
HubScreen
 ├─ PinnedAlertStack
 ├─ WorldDeltaSummaryCard
 ├─ IncidentTrackerPanel
 ├─ HubNotificationList
 ├─ SignalFeedPanel
 └─ NotificationInboxButton

LocationScreen
 ├─ TurnResultBanner
 ├─ NarrativePanel
 ├─ ChoicePanel
 └─ LocationToastLayer   // = FloatingNotificationToasts

CombatScreen
 ├─ CombatWarningStrip
 └─ StatusEffectPanel
```

### 2.3 주요 컴포넌트 props

```ts
interface PinnedAlertStackProps {
  alerts: GameNotification[];              // CRITICAL/HIGH 위주, 최대 1~3개
  onAcknowledge?: (id: string) => void;
}

interface WorldDeltaSummaryCardProps {
  summary: WorldDeltaSummaryUI | null;     // headline + visibleChanges[] + urgency
}

interface HubNotificationListProps {
  items: GameNotification[];               // scope === 'HUB'
  onRead?: (id: string) => void;
}

interface TurnResultBannerProps {
  items: GameNotification[];               // scope === 'TURN_RESULT'
}

interface LocationToastLayerProps {
  items: GameNotification[];               // scope === 'LOCATION' && presentation === 'TOAST'
}
```

공통: `NotificationBadge`(priority 뱃지), `NotificationCard`(범용 카드), `NotificationInboxTab`(사이드패널 인박스).

### 2.4 UI 상태 전이
- **허브 복귀 시**: `worldDeltaSummary` 갱신 → `pinnedAlerts` 갱신 → unread count 증가.
- **새 턴 시작 시**: 만료된 토스트 제거, LOCATION 토스트 정리.
- **읽음 처리 시**: inbox unread count 감소. pinned alert는 `acknowledged` 전까지 유지 가능.

### 2.5 스타일 가이드
| 우선순위 | 표현 |
|---------|------|
| CRITICAL | 상단 고정 / 큰 배너 |
| HIGH | 카드형 강조 |
| MID | 일반 피드 항목 |
| LOW | 보조 텍스트 / 토스트 |

문장 길이: 토스트 1문장 / 결과 배너 1~2문장 / 허브 요약 3~5줄 / pinned alert 제목+짧은 설명. 숫자 중심 UI, 로그창 같은 빽빽한 리스트, 허브·로케이션 동일 디자인 반복은 피한다.

### 2.6 QA 체크리스트
- **HUB**: 복귀 시 summary 즉시 갱신 / pinned alert 우선순위 정렬 / unread count 정확.
- **LOCATION**: 토스트가 내러티브를 가리지 않음 / 같은 토스트 반복 폭주 없음 / 결과 배너 명확.
- **COMBAT**: 세계 노티 과도 개입 없음 / 전투 경고 즉시 인식.

---

## 3. 클라이언트 브릿지

### 3.1 현재 구조 진단
핵심 파일: `src/app/page.tsx`, `src/store/game-store.ts`, `src/types/game.ts`, `src/lib/result-mapper.ts`, `src/components/hub/{HubScreen,SignalFeedPanel,IncidentTracker}.tsx`, `src/components/input/InputSection.tsx`, `src/components/side-panel/SidePanel.tsx`.

기존 `game-store`에는 `worldState / signalFeed / activeIncidents / operationProgress / npcEmotional / resolveOutcome / inventoryChanges / messages / choices`가 있다. 완전히 새로 만들 필요는 없고, 이 위에 UI 전달용 상태를 확장한다.

제약
- 허브에 "이번 복귀 이후 변화" 섹션 없음 (요약/pinned/unread/severity 고정 모두 부재).
- LOCATION에 알림 전용 레이어 없음 (`LocationHeader → NarrativePanel → InputSection`).
- `types/game.ts`에 `GameNotification` / `WorldDeltaSummaryUI` / `PinnedAlert` 부재.
- `result-mapper.ts`는 메시지 생성 전용이라 별도 노티 분기가 없음.

### 3.2 적용 원칙
- **A. 메시지 패널과 노티 패널 분리**: `NarrativePanel`은 서사 로그, Notification UI는 상태 변화/압박 전달. 섞지 않는다.
- **B. 기존 `signalFeed` 유지**: 역할만 재정의 → `signalFeed`=원시 신호, `notifications`=가공 노티, `pinnedAlerts`=허브 상단 고정, `worldDeltaSummary`=허브 복귀 요약.
- **C. MVP는 허브부터**: 효과 순서 = 허브 요약 → 허브 pinned → LOCATION 배너 → LOCATION 토스트 → 인박스.

### 3.3 타입 확장 (`src/types/game.ts`)

§1.3의 `GameNotification` / `WorldDeltaSummaryUI`를 그대로 추가한다. 기존 `ServerResultV1.ui`는 §1.9와 같이 `notifications / pinnedAlerts / worldDeltaSummary` 필드를 선택 필드로 확장 — 서버가 빼먹어도 기존 흐름은 안전.

### 3.4 Zustand 스토어 확장 (`src/store/game-store.ts`)

```ts
type NotificationState = {
  notifications: GameNotification[];
  pinnedAlerts: GameNotification[];
  worldDeltaSummary: WorldDeltaSummaryUI | null;
  unreadHubNotificationCount: number;

  setNotifications: (items: GameNotification[]) => void;
  appendNotifications: (items: GameNotification[]) => void;
  markNotificationRead: (id: string) => void;
  markAllHubNotificationsRead: () => void;
  clearExpiredNotifications: (currentTurnNo: number) => void;
  clearWorldDeltaSummary: () => void;
  setPinnedAlerts: (items: GameNotification[]) => void;
  setWorldDeltaSummary: (summary: WorldDeltaSummaryUI | null) => void;
};
```

초기값은 모두 빈 배열/`null`/`0`.

서버 응답 반영 로직:
```ts
const incomingNotifications = result.ui?.notifications ?? [];
const incomingPinnedAlerts = result.ui?.pinnedAlerts ?? [];
const incomingWorldDeltaSummary = result.ui?.worldDeltaSummary ?? null;

set((state) => {
  const mergedNotifications = mergeNotifications(state.notifications, incomingNotifications);
  const unreadHubCount = mergedNotifications.filter(
    (item) => item.scope === 'HUB' && !item.read,
  ).length;

  return {
    notifications: mergedNotifications,
    pinnedAlerts: incomingPinnedAlerts,
    worldDeltaSummary: incomingWorldDeltaSummary,
    unreadHubNotificationCount: unreadHubCount,
  };
});
```

보조 함수는 `src/lib/notification-utils.ts`로 분리: `mergeNotifications`, `dedupeNotifications`, `dropExpiredNotifications`, `sortNotificationsByPriority`.

### 3.5 Phase별 반영 규칙
- **HUB 진입/복귀**: `worldDeltaSummary` 갱신, `pinnedAlerts` 갱신, `scope==='HUB'` 노티 추가.
- **LOCATION 진행**: `scope==='LOCATION' | 'TURN_RESULT'` 추가. `pinnedAlerts`는 갱신되지만 화면 노출 최소화.
- **COMBAT 진행**: `scope==='LOCATION' | 'TURN_RESULT'`만 부분 허용. `WORLD/HUB`성 노티는 저장만 하고 전투 종료 후 노출.

### 3.6 Selector (`src/store/game-selectors.ts` 신설)

```ts
export const selectHubPinnedAlerts = (s: GameState) => s.pinnedAlerts;
export const selectHubWorldDeltaSummary = (s: GameState) => s.worldDeltaSummary;

export const selectHubNotifications = (s: GameState) =>
  s.notifications.filter((i) => i.scope === 'HUB').sort(sortNotificationsByPriority);

export const selectTurnResultNotifications = (s: GameState) =>
  s.notifications.filter((i) => i.scope === 'TURN_RESULT');

export const selectLocationToastNotifications = (s: GameState) =>
  s.notifications.filter((i) => i.scope === 'LOCATION' && i.presentation === 'TOAST');

export const selectHubNotificationVM = (s: GameState) => ({
  pinnedAlerts: s.pinnedAlerts,
  worldDeltaSummary: s.worldDeltaSummary,
  feedItems: selectHubNotifications(s).filter((i) => i.presentation === 'FEED_ITEM'),
  unreadCount: s.unreadHubNotificationCount,
});
```

컴포넌트가 raw state 대신 selector로 view model을 받도록 한다.

### 3.7 기존 컴포넌트 수정 포인트

**`HubScreen.tsx`** — 본문 순서 변경:
```text
1. PinnedAlertStack             (신규)
2. WorldDeltaSummaryCard        (신규)
3. Location Cards
4. Heat Resolution
5. IncidentTracker
6. HubNotificationList          (신규)
7. SignalFeedPanel              (역할 축소: 분위기/루머/부가 신호 피드로)
8. NpcRelationshipCard
```
허브는 단순 이동 메뉴가 아니라 **세계 정세 브리핑 화면**이어야 한다.

**`SignalFeedPanel.tsx`** — 유지하되 역할 축소. 중요 경보는 `PinnedAlertStack`, 구조화된 변화는 `HubNotificationList`, 원시 신호는 `SignalFeedPanel`.

**`page.tsx`** — LOCATION phase에서 `NarrativePanel` 상단에 `TurnResultBanner`, 공통으로 `LocationToastLayer` 추가:
```tsx
<div className="flex flex-1 flex-col bg-[var(--bg-primary)]">
  {phase === 'LOCATION' && <TurnResultBanner items={turnResultNotifications} />}
  {phase !== 'HUB' && <LocationToastLayer items={locationToastNotifications} />}
  {phase === 'COMBAT' && enemies.length > 0 && <BattlePanel enemies={enemies} />}
  <NarrativePanel ... />
  <InputSection ... />
</div>
```

**`SidePanel.tsx`** — 현재 탭: 캐릭터/소지품/퀘스트. 퀘스트 탭이 비어 있으므로:
- 1차: 퀘스트 탭에 노티 인박스 병합 (구현 단순).
- 2차: `알림` 탭 분리 (확장성, unread 카운트 연동).

### 3.8 `result-mapper.ts` 정책
메시지 생성 전용 유지. 노티는 별도 레이어로 처리. 단, 서버가 `TURN_RESULT` 배너용 텍스트를 아직 안 주면 `resolveOutcome` 기반 임시 fallback 배너를 프론트에서 생성 가능 (SUCCESS/PARTIAL/FAIL). 최종적으로는 서버가 `notifications`를 주는 게 맞다.

### 3.9 단계별 구현 계획 & Claude Code 작업 단위

| Phase | 대상 | 완료 기준 |
|-------|------|----------|
| **1. 타입/스토어** | `types/game.ts`, `game-store.ts`, `game-selectors.ts` 신설 | 타입 컴파일 통과, 신규 필드 없어도 안전 동작 |
| **2. 허브 상단 브리핑** | `HubScreen.tsx`, `PinnedAlertStack`, `WorldDeltaSummaryCard`, `HubNotificationList` 신설 | `worldDeltaSummary`/`pinnedAlerts`/`scope==='HUB'` 노티 표시 |
| **3. LOCATION 배너/토스트** | `page.tsx`, `location/TurnResultBanner`, `location/LocationToastLayer` 신설 | `TURN_RESULT` 배너, `LOCATION+TOAST` 자동 소멸 토스트 |
| **4. 사이드패널 인박스** | `SidePanel.tsx`, `notifications/NotificationInboxTab` 신설 | unread count 표시, 읽음 처리, 퀘스트/알림 정책 확정 |

작업 단위 (12개):
1. 타입 추가 (`types/game.ts`)
2. 스토어 확장 (`game-store.ts`)
3. `game-selectors.ts` 생성
4. `PinnedAlertStack.tsx`
5. `WorldDeltaSummaryCard.tsx`
6. `HubNotificationList.tsx`
7. `HubScreen.tsx` 섹션 삽입
8. `TurnResultBanner.tsx`
9. `LocationToastLayer.tsx`
10. `page.tsx` LOCATION 연결
11. `NotificationInboxTab.tsx`
12. `SidePanel.tsx`에 인박스 탭 or 퀘스트 탭 임시 연결

### 3.10 최종 권장 범위
- **1차**: 타입/스토어 확장 + HUB 전용 3컴포넌트.
- **2차**: `page.tsx`에 `TurnResultBanner` / `LocationToastLayer`.
- **3차**: `SidePanel` 알림 인박스.

허브를 세계 브리핑 화면으로 먼저 강화하고, 그다음 현장 반응을 얹는 순서. 현재 구조를 거의 깨지 않고 "세계가 움직인다"는 체감을 가장 빠르게 만들 수 있다.

---

## 요약

| 레이어 | 정의 |
|--------|------|
| Signal Feed | 세계 원시 신호 |
| World Delta | 상태 변화 묶음 |
| Notification | 플레이어 UI 전달물 |

이 구조를 지키면 현장 몰입을 해치지 않으면서 전역 변화와 후속 압박을 명확히 인지시킬 수 있다.
