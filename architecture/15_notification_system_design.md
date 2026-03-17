# 15. Notification System Design

## 1. 목적

Notification 계층은 단순 로그 출력이 아니라, **세계 변화와 플레이어 행동의 후속 반응을 플레이어가 이해 가능한 UI 신호로 번역하는 계층**이다.

핵심 목표는 다음과 같다.

1. 플레이어가 자신이 없는 동안 발생한 세계 변화를 놓치지 않게 한다.
2. 플레이어가 방금 만든 결과와 후폭풍을 즉시 이해하게 한다.
3. 허브에서는 전역 전략 정보를, 로케이션에서는 현장 몰입 정보를 분리해 제공한다.
4. 알림을 행동 유도 장치로 사용한다.

---

## 2. 시스템 원칙

### 2.1 정보 계층 분리
- **Signal Feed**: 세계에서 발생한 원시 신호
- **World Delta**: 한 턴/한 복귀 단위의 상태 변화 묶음
- **Notification**: 플레이어 UI에 전달할 가공된 결과물

### 2.2 화면별 역할 분리
- **LOCATION**: 몰입형 현장 알림
- **TURN RESULT**: 행동 결과 요약
- **HUB**: 전략형 전역 알림
- **COMBAT**: 최소 정보만 전달

### 2.3 스팸 방지
- 같은 성격의 경고는 병합한다.
- 중요하지 않은 반복 메시지는 숨긴다.
- Critical 알림은 고정한다.

---

## 3. Notification 구조

## 3.1 Scope
```ts
export type NotificationScope =
  | 'LOCATION'
  | 'TURN_RESULT'
  | 'HUB'
  | 'GLOBAL';
```

## 3.2 Kind
```ts
export type NotificationKind =
  | 'INCIDENT'
  | 'WORLD'
  | 'RELATION'
  | 'ACCESS'
  | 'DEADLINE'
  | 'SYSTEM';
```

## 3.3 Priority
```ts
export type NotificationPriority =
  | 'LOW'
  | 'MID'
  | 'HIGH'
  | 'CRITICAL';
```

## 3.4 Presentation
```ts
export type NotificationPresentation =
  | 'TOAST'
  | 'BANNER'
  | 'FEED_ITEM'
  | 'PINNED_CARD'
  | 'MODAL';
```

## 3.5 GameNotification
```ts
export type GameNotification = {
  id: string;
  tickNo: number;
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

  visibleFromTurn: number;
  expiresAtTurn?: number | null;

  dedupeKey?: string | null;
  pinned?: boolean;
  read?: boolean;
  acknowledged?: boolean;

  tags?: string[];
};
```

---

## 4. 분류 체계

### 4.1 Incident 알림
- 사건 단계 상승/하락
- 사건 압력 증가
- deadline 접근
- 경쟁 세력 개입
- 방치 시 자동 악화 예고

### 4.2 World 알림
- heat 상승
- 도시 긴장 증가
- 특정 지역 위험도 상승
- 야간 경계 강화
- 오프스크린 지역 변화

### 4.3 Relation 알림
- NPC 의심 증가
- 세력 평판 변화
- 적대/우호 플래그 생성
- 접촉 차단/개방

### 4.4 Access 알림
- 루트 잠금
- 새로운 접근 벡터 해금
- 상점/지역/인물 접근 가능
- 사회적 접근 난이도 변화

### 4.5 Deadline 알림
- soft deadline 경고
- 사건 임계치 도달
- 미개입 경고

---

## 5. 생성 타이밍

### 5.1 LOCATION 행동 직후
- 현장 반응 알림 생성
- scope: `LOCATION`
- presentation: `TOAST`, `BANNER`

예시:
- "누군가 당신을 지켜보고 있다."
- "경비가 이 구역으로 이동한다."

### 5.2 턴 결과 직후
- 행동 결과 요약 알림 생성
- scope: `TURN_RESULT`
- presentation: `BANNER`

예시:
- "정보는 얻었지만 흔적을 남겼습니다."
- "설득은 실패했지만 상대의 의도를 읽었습니다."

### 5.3 offscreenTick / worldTick 이후
- 허브 복귀용 전역 변화 알림 생성
- scope: `HUB`
- presentation: `FEED_ITEM`, `PINNED_CARD`

예시:
- "항만 봉쇄가 강화되었습니다."
- "빈민가에서 당신의 이름이 퍼지고 있습니다."

### 5.4 임계치 돌파 시
- scope: `GLOBAL`
- priority: `CRITICAL`
- presentation: `PINNED_CARD`

예시:
- "주요 사건이 폭발 직전입니다."
- "도시 긴장이 위험 수위에 도달했습니다."

---

## 6. 우선순위 기준

### LOW
- 정보성 메시지
- 분위기 전달

### MID
- 행동 유도
- 방치 시 손실 가능

### HIGH
- 즉시 대응 권장
- 중요한 루트 손상 가능

### CRITICAL
- 절대 놓치면 안 되는 전역 경보
- 허브 상단 고정

---

## 7. 중복 제거 및 병합 규칙

### 7.1 dedupeKey 기준
같은 턴 내 동일 종류의 이벤트는 `dedupeKey`로 중복 제거한다.

예시:
```ts
const dedupeKey = `${incidentId}:${kind}:${priority}:${band}`;
```

### 7.2 병합 규칙
다음 조건은 단일 요약 노티로 묶는다.
- 같은 locationId에서 발생
- 같은 incidentId에 연관
- 1~2턴 내 연속 발생
- 의미상 "상황 악화"로 요약 가능

예시:
- 항만 경비 증가
- 항만 소문 확산
- 항만 접근 악화

위 3개는 아래 1개로 병합:
- **항만 상황 악화** — 경비가 늘고 소문이 퍼졌으며 접근 난도가 올라갔습니다.

### 7.3 억제 규칙
- 읽지 않은 Critical이 있으면 유사 Mid는 축약한다.
- Heat 변화는 임계 밴드 변경 시에만 다시 노출한다.
- 동일한 flavor 텍스트는 2~3턴 내 재노출 금지.

---

## 8. 화면 노출 정책

## 8.1 LOCATION
노출:
- 짧은 현장 토스트
- 턴 결과 배너
- 위험 경고

비노출:
- 장문의 도시 전체 변화
- 모든 미방문 지역 변화

## 8.2 HUB
노출:
- 긴급 경보
- world delta summary
- 사건 추적 변화
- signal feed
- unread inbox

## 8.3 COMBAT
노출:
- 전투 상태 관련 알림
- 증원/퇴로 차단
- 전투 외부 영향 최소 정보

비노출:
- 일반 세계 요약
- 허브형 피드

---

## 9. 서버 파이프라인

```text
resolve / worldTick / offscreenTick
→ signalFeed 생성
→ worldDelta 생성
→ notificationAssembler.build(...)
→ ui.notifications / ui.worldDeltaSummary / ui.pinnedAlerts 반환
```

## 9.1 notificationAssembler 책임
- raw signal 수집
- 우선순위 판별
- 중복 제거
- 병합 요약
- scope / presentation 결정
- pinned 분리

---

## 10. 서버 응답 계약 확장안

```ts
export type WorldDeltaSummaryUI = {
  headline: string;
  visibleChanges: string[];
  urgency: 'LOW' | 'MID' | 'HIGH';
};

export type ServerResultUI = {
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

---

## 11. World Delta Summary 생성 규칙

### 11.1 목적
허브 복귀 시 플레이어가 **"내가 없는 동안 무슨 일이 있었는지"**를 3~5줄로 파악하게 한다.

### 11.2 구성 규칙
- 최대 5줄
- 전역 변화 우선
- 플레이어와 직접 관련된 변화 우선
- 미방문 지역 변화도 포함 가능
- flavor + actionable hint를 같이 준다

### 11.3 예시
- 항만 창고 수색이 확대되었습니다.
- 시장에서는 당신의 개입을 두고 소문이 돌고 있습니다.
- 야간 순찰이 늘어 빈민가 접근이 더 까다로워졌습니다.

---

## 12. MVP 구현 단계

### Phase 1
- `worldDeltaSummary`만 구현
- 허브 복귀 시 3~5줄 출력

### Phase 2
- `pinnedAlerts` 구현
- Critical / High 상단 고정

### Phase 3
- `LOCATION` 토스트 / 배너 구현

### Phase 4
- `hubInbox` 및 읽음 처리 구현

---

## 13. 금지 패턴

다음은 피해야 한다.

- 숫자만 보여주는 로그형 알림
- 매 턴 같은 메시지 반복
- 플레이어가 의미를 해석해야만 하는 추상 알림
- LOCATION 화면에서 전역 정보 남발
- 전투 중 허브형 피드 노출

---

## 14. 권장 문구 스타일

좋은 예:
- "수색이 본격화됩니다."
- "당신의 이름이 퍼지고 있습니다."
- "누군가 먼저 손을 썼습니다."

나쁜 예:
- `pressure +12`
- `suspicion +5`
- `world_state updated`

---

## 15. 결론

Notification 계층은 다음 공식을 기준으로 유지한다.

- **Signal Feed = 세계 원시 신호**
- **World Delta = 상태 변화 묶음**
- **Notification = 플레이어 UI 전달물**

이 구조를 유지하면, 유저는 현장 몰입을 해치지 않으면서도 전역 변화와 후속 압박을 명확히 인지할 수 있다.
