# 17. Notification Client Bridge

## 문서 목적

이 문서는 다음 두 문서를 실제 클라이언트 코드에 연결하기 위한 브리지 문서입니다.

- `15_notification_system_design.md`
- `16_notification_ui_build_plan.md`

즉, **알림 시스템 설계 → 현재 graymar-client 구조 → 실제 적용 순서**를 잇는 구현 기준 문서입니다.

본 문서는 현재 업로드된 `graymar-client-main.zip` 구조를 기준으로 작성합니다.

---

## 1. 현재 클라이언트 구조 요약

현재 클라이언트는 Next.js App Router + Zustand 기반이며, 노티 시스템과 직접 연결될 핵심 지점은 아래와 같습니다.

### 핵심 파일

- `src/app/page.tsx`
- `src/store/game-store.ts`
- `src/types/game.ts`
- `src/lib/result-mapper.ts`
- `src/components/hub/HubScreen.tsx`
- `src/components/hub/SignalFeedPanel.tsx`
- `src/components/hub/IncidentTracker.tsx`
- `src/components/input/InputSection.tsx`
- `src/components/side-panel/SidePanel.tsx`

### 현재 상태 구조

`game-store.ts`에는 이미 다음 상태가 존재합니다.

- `worldState`
- `signalFeed`
- `activeIncidents`
- `operationProgress`
- `npcEmotional`
- `resolveOutcome`
- `inventoryChanges`
- `messages`
- `choices`

즉, **노티 시스템을 완전히 새로 만들 필요는 없고**, 현재 있는 `signalFeed`, `resolveOutcome`, `worldState`, `activeIncidents` 위에 UI 전달용 상태를 확장하는 방식이 적합합니다.

---

## 2. 현재 구조에서 확인된 제약 사항

### 2-1. 허브 정보는 있으나 “세계 변화 요약”이 없다

현재 `HubScreen.tsx`는 아래 요소를 렌더링합니다.

- Location Cards
- Heat Resolution Options
- `IncidentTracker`
- `SignalFeedPanel`
- `NpcRelationshipCard`

문제는 허브가 아직 **이번 복귀 이후 무엇이 변했는가**를 별도 섹션으로 보여주지 않는다는 점입니다.

즉, `signalFeed`는 있으나:

- 요약이 없고
- pinned alert가 없고
- unread 개념이 없고
- severity 높은 정보가 고정되지 않습니다.

### 2-2. LOCATION에서 알림 전용 레이어가 없다

현재 `page.tsx` 구조상 LOCATION phase에서는:

- `LocationHeader`
- `NarrativePanel`
- `InputSection`

정도로만 이어집니다.

즉, 위치 장면에서 **짧은 배너 / 토스트 / 위험 경고**를 보여줄 공식 슬롯이 없습니다.

### 2-3. 알림 타입이 타입 시스템에 아직 없다

`src/types/game.ts`에는 현재:

- `SignalFeedItemUI`
- `IncidentSummaryUI`
- `WorldStateUI`

까지만 있고, `GameNotification`, `WorldDeltaSummary`, `PinnedAlert`가 없습니다.

### 2-4. 서버 결과 매핑은 메시지 중심이다

`result-mapper.ts`는 현재:

- system event → `SYSTEM` message
- resolve result → `RESOLVE` message
- narrator summary → `NARRATOR` message
- choices → `CHOICE` message

로 매핑합니다.

즉, 현재 구조는 **스토리 패널에 메시지를 뿌리는 구조**이고, 별도의 노티 UI용 분기 처리가 없습니다.

---

## 3. 적용 원칙

이번 노티 시스템을 현재 코드에 붙일 때는 아래 원칙을 지킵니다.

### 원칙 A. 메시지 패널과 노티 패널을 분리한다

- `NarrativePanel`은 서사 로그
- `Notification UI`는 상태 변화/압박 전달

둘을 섞으면 같은 정보가 중복 출력되고, 장면 서사와 시스템 반응이 뒤엉킵니다.

### 원칙 B. 기존 `signalFeed`는 유지한다

`signalFeed`는 버리지 않습니다.

역할을 다음처럼 재정의합니다.

- `signalFeed`: 세계 원시 신호 목록
- `notifications`: 현재 프론트에서 직접 보여줄 가공 노티
- `pinnedAlerts`: 허브 상단 고정 경보
- `worldDeltaSummary`: 허브 복귀 요약

### 원칙 C. MVP는 허브부터 붙인다

현재 구조상 가장 효과가 큰 곳은 LOCATION이 아니라 HUB입니다.

순서는 다음이 맞습니다.

1. 허브 월드 변화 요약
2. 허브 pinned alert
3. LOCATION 결과 배너
4. LOCATION 현장 토스트
5. 사이드패널 inbox / 보관함

---

## 4. 타입 확장 계획

파일: `src/types/game.ts`

다음 타입을 추가합니다.

```ts
export type NotificationScope =
  | 'LOCATION'
  | 'TURN_RESULT'
  | 'HUB'
  | 'GLOBAL';

export type NotificationKind =
  | 'INCIDENT'
  | 'WORLD'
  | 'RELATION'
  | 'ACCESS'
  | 'DEADLINE'
  | 'SYSTEM';

export type NotificationPriority =
  | 'LOW'
  | 'MID'
  | 'HIGH'
  | 'CRITICAL';

export type NotificationPresentation =
  | 'TOAST'
  | 'BANNER'
  | 'FEED_ITEM'
  | 'PINNED_CARD';

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
  pinned?: boolean;
  read?: boolean;
  acknowledged?: boolean;
  expiresAtTurn?: number | null;
  dedupeKey?: string | null;
  tags?: string[];
}

export interface WorldDeltaSummaryUI {
  headline: string;
  visibleChanges: string[];
  urgency: 'LOW' | 'MID' | 'HIGH';
}
```

### 기존 `ServerResultV1.ui` 확장

```ts
ui: {
  availableActions: string[];
  targetLabels: Array<{ id: string; name: string; hint: string }>;
  actionSlots: { base: number; bonusAvailable: boolean; max: number };
  toneHint: string;
  worldState?: WorldStateUI;
  resolveOutcome?: 'SUCCESS' | 'PARTIAL' | 'FAIL';
  resolveBreakdown?: ResolveBreakdown;

  // 신규
  notifications?: GameNotification[];
  pinnedAlerts?: GameNotification[];
  worldDeltaSummary?: WorldDeltaSummaryUI;
}
```

### 이유

이 확장은 기존 `ServerResultV1`를 깨지 않고, `ui` 하위에 추가 정보만 넣는 형태라 안전합니다.

---

## 5. Zustand 스토어 확장 계획

파일: `src/store/game-store.ts`

현재 `GameState`에 아래를 추가합니다.

```ts
notifications: GameNotification[];
pinnedAlerts: GameNotification[];
worldDeltaSummary: WorldDeltaSummaryUI | null;
unreadHubNotificationCount: number;
```

### 추가 액션

```ts
markNotificationRead: (id: string) => void;
markAllHubNotificationsRead: () => void;
clearExpiredNotifications: (currentTurnNo: number) => void;
clearWorldDeltaSummary: () => void;
```

### 초기값

```ts
notifications: [],
pinnedAlerts: [],
worldDeltaSummary: null,
unreadHubNotificationCount: 0,
```

### 적용 위치

서버 응답을 스토어에 반영하는 지점에서 아래 로직을 추가합니다.

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

### 보조 함수 권장

`game-store.ts` 내부 또는 `src/lib/notification-utils.ts`로 분리:

- `mergeNotifications`
- `dedupeNotifications`
- `dropExpiredNotifications`
- `sortNotificationsByPriority`

---

## 6. 서버 응답 반영 정책

현재 구조상 노티는 **모든 phase에서 같게 보관하되, 화면에서 scope별로 필터링**하는 방식이 가장 좋습니다.

### phase별 반영 규칙

#### HUB 진입/복귀 시
- `worldDeltaSummary` 갱신
- `pinnedAlerts` 갱신
- `scope === 'HUB'` 노티 추가

#### LOCATION 진행 시
- `scope === 'LOCATION'` / `TURN_RESULT` 노티 추가
- `pinnedAlerts`는 갱신 가능하지만 화면 노출은 최소화

#### COMBAT 진행 시
- `scope === 'LOCATION'` 또는 `TURN_RESULT`만 일부 허용
- `WORLD/HUB`성 노티는 저장만 하고 전투 종료 후 노출

---

## 7. 새 컴포넌트 추가 계획

### 7-1. 허브 전용 컴포넌트

폴더: `src/components/hub/`

#### `PinnedAlertStack.tsx`
역할:
- `pinnedAlerts` 표시
- CRITICAL / HIGH 위주
- 허브 상단 1~3개 제한

권장 props:

```ts
interface PinnedAlertStackProps {
  alerts: GameNotification[];
  onAcknowledge?: (id: string) => void;
}
```

#### `WorldDeltaSummaryCard.tsx`
역할:
- 허브 복귀 후 세계 변화 요약 카드
- `headline + visibleChanges[] + urgency`

권장 props:

```ts
interface WorldDeltaSummaryCardProps {
  summary: WorldDeltaSummaryUI | null;
}
```

#### `HubNotificationList.tsx`
역할:
- `scope === 'HUB'` 노티 목록 표시
- 기존 `SignalFeedPanel`보다 “행동 압박” 중심

권장 props:

```ts
interface HubNotificationListProps {
  items: GameNotification[];
  onRead?: (id: string) => void;
}
```

### 7-2. LOCATION 전용 컴포넌트

폴더: `src/components/location/` 신설 권장

#### `TurnResultBanner.tsx`
역할:
- 직전 행동의 결과 요약
- `scope === 'TURN_RESULT'`

#### `LocationToastLayer.tsx`
역할:
- `scope === 'LOCATION' && presentation === 'TOAST'`
- 화면 우상단 또는 내러티브 패널 상단에 떠서 자동 사라짐

### 7-3. 공통 컴포넌트

폴더: `src/components/notifications/` 신설 권장

#### `NotificationBadge.tsx`
- priority 뱃지

#### `NotificationCard.tsx`
- kind / priority / CTA 포함 범용 카드

#### `NotificationInboxTab.tsx`
- 사이드패널 또는 차후 퀘스트 탭 대체용

---

## 8. 기존 컴포넌트 수정 포인트

### 8-1. `HubScreen.tsx`

현재 허브 본문 구조는 대략 아래입니다.

1. Location Cards
2. Heat Resolution
3. IncidentTracker
4. SignalFeedPanel
5. NpcRelationshipCard

이를 아래 순서로 수정합니다.

```text
1. PinnedAlertStack
2. WorldDeltaSummaryCard
3. Location Cards
4. Heat Resolution
5. IncidentTracker
6. HubNotificationList
7. SignalFeedPanel
8. NpcRelationshipCard
```

### 이유

허브는 이제 단순 이동 메뉴가 아니라 **세계 정세 브리핑 화면**이어야 하기 때문입니다.

### 8-2. `SignalFeedPanel.tsx`

현재 `SignalFeedPanel`은 severity만 기준으로 나열합니다.

이 컴포넌트는 유지하되 역할을 축소합니다.

- 기존: 허브에서 사실상 메인 경보창 역할
- 변경 후: 분위기/루머/부가 신호 피드 역할

즉, 중요한 경보는 `PinnedAlertStack`, 구조화된 변화는 `HubNotificationList`, 원시 신호는 `SignalFeedPanel`로 분리합니다.

### 8-3. `page.tsx`

현재 `page.tsx`는 phase별로 `NarrativePanel`, `InputSection`, `SidePanel`을 조합합니다.

여기에 아래를 추가합니다.

#### Desktop
- LOCATION phase에서 `NarrativePanel` 상단에 `TurnResultBanner`
- 공통적으로 `LocationToastLayer`

예시 배치:

```tsx
<div className="flex flex-1 flex-col bg-[var(--bg-primary)]">
  {phase === 'LOCATION' && <TurnResultBanner items={turnResultNotifications} />}
  {phase !== 'HUB' && <LocationToastLayer items={locationToastNotifications} />}
  {phase === 'COMBAT' && enemies.length > 0 && <BattlePanel enemies={enemies} />}
  <NarrativePanel ... />
  <InputSection ... />
</div>
```

### 8-4. `SidePanel.tsx`

현재 탭은:

- 캐릭터
- 소지품
- 퀘스트

여기서 `퀘스트` 탭이 아직 비어 있으므로, 2단계 이후 아래 둘 중 하나로 전환 가능합니다.

#### 안 A. 퀘스트 탭 내부에 노티 인박스 병합
- 퀘스트 + 알림 혼합
- 초기 구현이 쉬움

#### 안 B. 새 탭 `알림`
- 추후 확장성 높음
- 허브 unread 카운트 연동 쉬움

추천은 **1차는 퀘스트 탭 재활용**, 2차에서 `알림` 탭 분리입니다.

---

## 9. selector 설계

렌더링을 안정화하려면 `page.tsx`, `HubScreen.tsx`에서 raw state를 바로 쓰지 말고 selector를 두는 게 좋습니다.

파일: `src/store/game-selectors.ts` 신설 권장

### 예시

```ts
export const selectHubPinnedAlerts = (s: GameState) => s.pinnedAlerts;

export const selectHubWorldDeltaSummary = (s: GameState) => s.worldDeltaSummary;

export const selectHubNotifications = (s: GameState) =>
  s.notifications
    .filter((item) => item.scope === 'HUB')
    .sort(sortNotificationsByPriority);

export const selectTurnResultNotifications = (s: GameState) =>
  s.notifications.filter((item) => item.scope === 'TURN_RESULT');

export const selectLocationToastNotifications = (s: GameState) =>
  s.notifications.filter(
    (item) => item.scope === 'LOCATION' && item.presentation === 'TOAST',
  );
```

### 이유

- phase별 필터링 로직이 컴포넌트에 흩어지는 것을 막음
- 후속 리팩토링 시 범위가 줄어듦

---

## 10. `result-mapper.ts`와의 관계

현재 `result-mapper.ts`는 메시지 생성 전용입니다.

이번 노티 시스템에서 `result-mapper.ts`는 크게 건드리지 않는 것을 권장합니다.

### 유지 이유

- 메시지 패널은 여전히 `SYSTEM / RESOLVE / NARRATOR / CHOICE` 흐름으로 충분함
- 노티는 별도 UI 레이어로 처리하는 것이 중복과 책임 분리에 유리함

### 단, 예외

`TURN_RESULT` 배너용 텍스트가 서버에서 아직 오지 않는다면, 임시로 `resolveOutcome` 기반의 간단한 배너 문구를 프론트에서 생성할 수 있습니다.

예:

```ts
function fallbackResolveBanner(outcome: ResolveOutcome | null): GameNotification[] {
  if (!outcome) return [];

  if (outcome === 'SUCCESS') {
    return [{
      id: `resolve-success-${Date.now()}`,
      turnNo: 0,
      scope: 'TURN_RESULT',
      kind: 'SYSTEM',
      priority: 'MID',
      presentation: 'BANNER',
      title: '행동이 성공했습니다',
      body: '현장 반응을 확인하십시오.',
    }];
  }

  return [];
}
```

하지만 이건 임시 처리입니다. 최종적으로는 서버가 `notifications`를 주는 게 맞습니다.

---

## 11. 단계별 적용 계획

## Phase 1. 타입/스토어 확장

대상 파일:
- `src/types/game.ts`
- `src/store/game-store.ts`
- `src/store/game-selectors.ts` 신설

목표:
- 새 타입 추가
- 상태 저장 가능하게 만들기
- 아직 화면에는 붙이지 않음

산출물:
- 타입 컴파일 통과
- 응답에 신규 필드가 없어도 안전하게 동작

---

## Phase 2. 허브 상단 브리핑 UI 추가

대상 파일:
- `src/components/hub/HubScreen.tsx`
- `src/components/hub/PinnedAlertStack.tsx` 신설
- `src/components/hub/WorldDeltaSummaryCard.tsx` 신설
- `src/components/hub/HubNotificationList.tsx` 신설

목표:
- 허브를 세계 변화 브리핑 화면으로 업그레이드

완료 기준:
- `worldDeltaSummary`가 있으면 허브 상단에 표시됨
- `pinnedAlerts`가 있으면 상단 고정 표시됨
- `scope === 'HUB'` 노티가 허브 리스트에 표시됨

---

## Phase 3. LOCATION 배너/토스트 추가

대상 파일:
- `src/app/page.tsx`
- `src/components/location/TurnResultBanner.tsx` 신설
- `src/components/location/LocationToastLayer.tsx` 신설

목표:
- 행동 직후 결과가 장면 바깥 로그가 아니라 즉시 보이게 함

완료 기준:
- `TURN_RESULT`는 배너로 표시
- `LOCATION + TOAST`는 자동 소멸 토스트로 표시

---

## Phase 4. 사이드패널 인박스 추가

대상 파일:
- `src/components/side-panel/SidePanel.tsx`
- `src/components/notifications/NotificationInboxTab.tsx`

목표:
- 읽지 않은 허브 알림 관리
- 장기 누적 알림 보관

완료 기준:
- unread count 표시
- 읽음 처리 가능
- 퀘스트/알림 정책 확정

---

## 12. 권장 구현 우선순위

### 반드시 먼저
1. 타입 확장
2. 스토어 확장
3. 허브 브리핑 UI

### 그다음
4. LOCATION 결과 배너
5. LOCATION 토스트

### 나중
6. 인박스/읽음 처리
7. 필터/보관/CTA 이동

---

## 13. Claude Code 작업 단위 분해

### 작업 1
`src/types/game.ts`에 Notification 관련 타입 추가

### 작업 2
`src/store/game-store.ts`에 notifications / pinnedAlerts / worldDeltaSummary 상태 및 액션 추가

### 작업 3
`src/store/game-selectors.ts` 생성

### 작업 4
`src/components/hub/PinnedAlertStack.tsx` 생성

### 작업 5
`src/components/hub/WorldDeltaSummaryCard.tsx` 생성

### 작업 6
`src/components/hub/HubNotificationList.tsx` 생성

### 작업 7
`src/components/hub/HubScreen.tsx`에 새 섹션 삽입

### 작업 8
`src/components/location/TurnResultBanner.tsx` 생성

### 작업 9
`src/components/location/LocationToastLayer.tsx` 생성

### 작업 10
`src/app/page.tsx`에 LOCATION 배너/토스트 연결

### 작업 11
`src/components/side-panel/NotificationInboxTab.tsx` 생성

### 작업 12
`src/components/side-panel/SidePanel.tsx`에 인박스 탭 또는 퀘스트 탭 임시 연결

---

## 14. 최종 권장안

현재 코드베이스 기준으로 가장 안전한 방향은 아래입니다.

### 1차 적용 범위
- `types/game.ts` 확장
- `game-store.ts` 확장
- HUB 전용 `PinnedAlertStack`, `WorldDeltaSummaryCard`, `HubNotificationList` 추가

### 2차 적용 범위
- `page.tsx`에 `TurnResultBanner`, `LocationToastLayer` 추가

### 3차 적용 범위
- `SidePanel` 알림 인박스 추가

즉, **먼저 허브를 세계 브리핑 화면으로 강화하고, 그 다음 현장 반응을 얹는 순서**가 맞습니다.

이 순서를 따르면 현재 구조를 거의 깨지 않고, 사용자가 체감하는 “세계가 움직인다”는 감각을 가장 빠르게 만들 수 있습니다.
