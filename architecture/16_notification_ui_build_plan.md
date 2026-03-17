# 16. Notification UI Build Plan

## 1. 목표

본 문서는 Notification System Design을 실제 클라이언트 UI에 반영하기 위한 구축 계획서다.

핵심 목표는 다음과 같다.

1. 허브를 **전역 상황 대시보드**로 강화한다.
2. 로케이션에서는 **몰입형 알림만 최소 노출**한다.
3. 전투 화면은 **상태 경고만 유지**한다.
4. 알림 UI를 컴포넌트 단위로 분리해 점진 적용 가능하게 만든다.

---

## 2. 화면별 UI 목표

## 2.1 HUB
허브는 세계 전체 변화를 요약해 주는 전략 화면이다.

반드시 보여야 하는 요소:
- 긴급 경보 pinned alerts
- world delta summary
- signal feed
- active incident 변화
- unread notification count

## 2.2 LOCATION
로케이션은 행동 중심의 현장 몰입 화면이다.

보여줄 요소:
- 결과 배너
- 짧은 토스트
- 현장 위험 경고

보여주지 않을 요소:
- 전역 변화 장문 요약
- 모든 지역 상태 로그

## 2.3 COMBAT
전투는 빠른 판단 화면이다.

보여줄 요소:
- 위협 경고
- 상태이상
- 외부 개입(증원/퇴로 차단) 알림

---

## 3. 정보 구조

## 3.1 HUB 레이아웃
권장 순서:

1. 상단 헤더
2. 긴급 경보 영역
3. world delta summary 카드
4. incident tracker / world status 카드
5. signal feed 리스트
6. inbox 진입 버튼

### 간단 와이어프레임
```text
[ Hub Header ]
[ Pinned Alerts ]
[ World Delta Summary ]
[ Incident Tracker ] [ World Status ]
[ Signal Feed List ]
[ Inbox Button / Unread Count ]
```

## 3.2 LOCATION 레이아웃
```text
[ Scene Header ]
[ Result Banner ]
[ Narrative Panel ]
[ Choice / Input Panel ]
[ Floating Toast Area ]
```

## 3.3 COMBAT 레이아웃
```text
[ Combat HUD ]
[ Warning Strip ]
[ Action Panel ]
```

---

## 4. React 컴포넌트 구조 제안

## 4.1 HUB 컴포넌트
```ts
HubScreen
 ├─ PinnedAlertStack
 ├─ WorldDeltaSummaryCard
 ├─ IncidentTrackerPanel
 ├─ SignalFeedPanel
 └─ NotificationInboxButton
```

## 4.2 LOCATION 컴포넌트
```ts
LocationScreen
 ├─ TurnResultBanner
 ├─ NarrativePanel
 ├─ ChoicePanel
 └─ FloatingNotificationToasts
```

## 4.3 COMBAT 컴포넌트
```ts
CombatScreen
 ├─ CombatWarningStrip
 └─ StatusEffectPanel
```

---

## 5. 타입 설계

```ts
export type WorldDeltaSummaryUI = {
  headline: string;
  visibleChanges: string[];
  urgency: 'LOW' | 'MID' | 'HIGH';
};

export type NotificationInboxUI = {
  unreadCount: number;
  items: GameNotification[];
};
```

허브 화면용 selector 결과는 아래처럼 단순한 view model로 만드는 것이 좋다.

```ts
export type HubNotificationViewModel = {
  pinnedAlerts: GameNotification[];
  worldDeltaSummary: WorldDeltaSummaryUI | null;
  feedItems: GameNotification[];
  unreadCount: number;
};
```

---

## 6. 상태 관리 계획

Zustand 기준으로 아래 상태를 store에 추가한다.

```ts
type NotificationState = {
  notifications: GameNotification[];
  pinnedAlerts: GameNotification[];
  worldDeltaSummary: WorldDeltaSummaryUI | null;
  unreadNotificationCount: number;

  setNotifications: (items: GameNotification[]) => void;
  appendNotifications: (items: GameNotification[]) => void;
  markNotificationRead: (id: string) => void;
  clearExpiredNotifications: (currentTurn: number) => void;
  setWorldDeltaSummary: (summary: WorldDeltaSummaryUI | null) => void;
  setPinnedAlerts: (items: GameNotification[]) => void;
};
```

---

## 7. Selector 분리

컴포넌트가 원본 상태를 직접 읽지 않고 selector를 통해 view model을 생성하도록 한다.

## 7.1 허브 selector
```ts
export const selectHubNotificationVM = (state: GameStore): HubNotificationViewModel => {
  return {
    pinnedAlerts: state.pinnedAlerts,
    worldDeltaSummary: state.worldDeltaSummary,
    feedItems: state.notifications.filter(
      (item) => item.scope === 'HUB' && item.presentation === 'FEED_ITEM'
    ),
    unreadCount: state.unreadNotificationCount,
  };
};
```

## 7.2 로케이션 selector
```ts
export const selectLocationNotifications = (state: GameStore) => {
  return state.notifications.filter(
    (item) => item.scope === 'LOCATION' || item.scope === 'TURN_RESULT'
  );
};
```

---

## 8. 단계별 구축 계획

## Phase 1. 허브 요약만 도입
대상:
- `WorldDeltaSummaryCard`
- `PinnedAlertStack`

목표:
- 서버 응답으로 받은 `worldDeltaSummary`, `pinnedAlerts`를 허브에 표시
- 알림 인박스는 아직 없음

## Phase 2. Signal Feed와 노티 피드 분리
대상:
- 기존 `SignalFeedPanel`
- feed item 렌더러

목표:
- raw signal과 가공 notification의 시각 구분
- 요약형 피드 카드 제공

## Phase 3. LOCATION 토스트 / 결과 배너 추가
대상:
- `TurnResultBanner`
- `FloatingNotificationToasts`

목표:
- 행동 직후 결과 전달 강화
- 몰입 방해 최소화

## Phase 4. Inbox 추가
대상:
- `NotificationInboxButton`
- `NotificationInboxDrawer`

목표:
- 읽음 처리
- 누적 알림 확인

---

## 9. UI 상태 전이 규칙

### 허브 복귀 시
- `worldDeltaSummary` 갱신
- `pinnedAlerts` 갱신
- unread count 증가

### 새 턴 시작 시
- 만료된 토스트 제거
- LOCATION 토스트 정리

### 읽음 처리 시
- inbox unread count 감소
- pinned alert는 acknowledged 전까지 유지 가능

---

## 10. 스타일 가이드

## 10.1 시각적 우선순위
- Critical: 상단 고정 / 큰 배너
- High: 카드형 강조
- Mid: 일반 피드 항목
- Low: 보조 텍스트 또는 토스트

## 10.2 문장 길이
- 토스트: 1문장
- 결과 배너: 1~2문장
- 허브 요약: 3~5줄
- pinned alert: 제목 + 짧은 설명

## 10.3 피해야 할 것
- 숫자 중심 UI
- 로그창 같은 빽빽한 리스트
- 허브와 로케이션의 동일 디자인 반복

---

## 11. QA 체크리스트

### HUB
- 허브 복귀 시 summary가 즉시 갱신되는가
- pinned alert가 우선순위대로 정렬되는가
- unread count가 정확한가

### LOCATION
- 토스트가 내러티브를 가리지 않는가
- 같은 토스트가 반복 폭주하지 않는가
- 결과 배너가 행동 결과를 명확히 전달하는가

### COMBAT
- 세계 노티가 과도하게 끼어들지 않는가
- 전투 경고가 즉시 인식 가능한가

---

## 12. Claude Code 작업 단위 제안

### Task 1
- 타입 추가
- `GameNotification`, `WorldDeltaSummaryUI` 정의

### Task 2
- store 확장
- notifications / pinned / summary 상태 추가

### Task 3
- `WorldDeltaSummaryCard`, `PinnedAlertStack` 구현

### Task 4
- `HubScreen` 연결

### Task 5
- `TurnResultBanner`, `FloatingNotificationToasts` 구현

### Task 6
- `LocationScreen` 연결

### Task 7
- Inbox Drawer 구현

---

## 13. 최종 적용 순서

추천 적용 순서는 아래와 같다.

1. 타입 정의
2. 서버 응답 매핑
3. store 연결
4. 허브 카드 2종 추가
5. 로케이션 알림 추가
6. 인박스 추가
7. polish / QA

---

## 14. 결론

UI 구축은 한 번에 끝내는 방식보다, **허브 요약 → 허브 경보 → 로케이션 알림 → 인박스** 순으로 점진 도입하는 것이 맞다.

이 순서를 따르면 현재 게임의 정보 구조를 깨지 않으면서 세계 변화 체감과 플레이어 피드백 품질을 동시에 높일 수 있다.
