# 94. 모바일 스크롤·뷰포트 정합

**상태**: ✅ 구현·배포됨 (2026-07-27) — 클라이언트 단독 (`graymar-client` 497ee66)
**관련**: [[86_pack_parity_mobile_ux]] (모바일 서술 스크롤 `min-h-0` 회귀) · [[93_location_backdrop]] (배경 레이어 — 같은 스크롤 컨테이너 위) · [[68_uiux_audit_v1]] (UI/UX 실사 리뷰 v1)

---

## 1. 점검 방식

헤드리스 Chromium(gstack browse)으로 실런에 로그인해 턴을 돌리며 측정했다.
뷰포트는 4종: `390x844`(표준 폰) · `390x480`(작은 폰) · `390x380`(키보드 노출 가정) ·
`844x390`(가로 모드).

측정 도구는 3개의 주입 스크립트:

| 스크립트 | 측정 대상 |
|---|---|
| `probe` | 스크롤 가능 컨테이너 전수 — `scrollHeight/clientHeight/overscrollBehaviorY` |
| `clip` | ① `overflow:hidden` 인데 내용이 넘치는 컨테이너 ② 화면 밖인데 **스크롤 가능한 조상이 없는** 컨트롤 |
| `hscan` | 가로 오버플로 (`getBoundingClientRect().right > clientWidth`) |

②가 핵심 판정이다. "화면 밖"만으로는 정상 스크롤과 구분되지 않는다.

---

## 2. 진단 — 층위별 원인

### 2.1 서술 스크롤 되돌림 (최다 체감)

`NarrativePanel`은 MutationObserver로 DOM이 바뀔 때마다 하단으로 `scrollTo`하고,
방어선은 **"하단에서 100px 이상 떨어졌는가"** 하나뿐이었다.

```
실측: scrollTop = max - 60  →  DOM 변화 1회  →  9042 → 9134 (즉시 하단 복귀)
```

모바일 드래그는 100px 미만이 흔하다. 스트리밍 중에는 문장마다 mutation이 발생하므로
"손가락으로 조금 올리면 계속 아래로 끌려감"이 된다. `behavior:'smooth'`가 터치 관성
스크롤과 겹치는 떨림도 같은 뿌리다.

400px 이상 올린 경우는 정상 유지됐다 — 즉 **임계값 문제가 아니라 판정 모델 문제**다.
"얼마나 멀리 갔나"가 아니라 "사용자가 개입했나"로 판정해야 한다.

### 2.2 스크롤이 아예 없는 화면

`overflow-hidden` + `h-full justify-center` 조합이라 넘치면 도달 수단이 없다.

| 화면 | 실측 | 결과 |
|---|---|---|
| 로그인(AUTH) | 390x390 | 제출 버튼 top 386 / bottom 434 → **4px만 노출**, `← 돌아가기` 도달 불가 |
| 타이틀(TITLE) | 844x390 | `새 캐릭터로 다시 시작`·`파티`·`로그아웃` 3개 도달 불가 |
| 타이틀 | 390x480 | `로그아웃` 도달 불가 |

두 화면 모두 `maxHeight: 600` + `transition: max-height 1.5s` 래퍼를 갖고 있었으나
**초기값과 목표값이 같아 실제로는 아무 애니메이션도 하지 않는 죽은 코드**였다.
클리핑만 남기고 있었다.

로그인 화면이 특히 문제인 이유: 이메일 입력 → 키보드가 300px 안팎을 먹으면
844 기기도 가시 높이가 이 조건에 들어간다. 첫 진입 경로다.

### 2.3 모달 — 내부 스크롤 부재

`fixed inset-0` + 고정 패널에 `max-h`/`overflow-y-auto`가 없는 모달이 16곳.

```
버그신고 모달 @ 390x380: panelTop -49 / panelBottom 380 / panelScrolls false
→ 제목·카테고리 버튼이 화면 위로 잘린 채 접근 불가
```

이 모달은 textarea 포커스 = 키보드가 뜨는 화면이라 정확히 이 조건에 들어간다.
(예외적으로 정상이던 곳: `LlmSettingsModal`(`max-h-[70vh]`), `LootDistribution`,
`PartyJoinModal`.)

### 2.4 고정 헤더가 덮는 상단 81px

`MobileHeader`는 `fixed top-[env(safe-area-inset-top)]`이고 실측 높이 **81px**
(h-12 48 + 상태줄 h-8 32 + 보더 1). 여기에 세 가지가 어긋나 있었다.

| 대상 | 값 | 어긋남 |
|---|---|---|
| 비-이야기 탭 스페이서 | `h-20` = 80px | 1px 부족 + **safe-area inset 전체가 누락** (노치 47~59px) |
| `DeadlineBanner` | in-flow, y=0 | 헤더 뒤에 완전히 가려짐 |
| `PartyHUD` | in-flow, y=0 (두 레이아웃 **바깥** 최상단) | 모바일에서 완전히 가려짐 |

`elementFromPoint(195,15)`·`(195,70)` 모두 HEADER 반환으로 점유를 확인했다.

### 2.5 safe-area 커버리지

앱은 `viewport-fit=cover`인데 `env(safe-area-inset-*)` 사용처가 **3곳뿐**이었다:
모바일 헤더 top · 서술 패널 상단 패딩 · 모바일 입력창 하단. 나머지(타이틀·로그인·
캐릭터 생성·엔딩·여정 기록·사이드 탭·파티 로비·전투 액션바)는 노치와 홈 인디케이터
아래로 들어갔다.

### 2.6 스크롤 체이닝

모든 스크롤 컨테이너가 `overscroll-behavior-y: auto`(실측). 서술 맨 위·맨 아래에서
계속 끌면 Android Chrome은 **당겨서 새로고침**(플레이 중 리로드), iOS는 문서
러버밴딩이 붙는다. 파티 컴포넌트 3곳만 `overscroll-contain`이 적용돼 있었다.

### 2.7 키보드

viewport meta에 `interactive-widget`이 없고 `dvh`/`visualViewport` 처리도 없다.
Android Chrome 기본값(`resizes-visual`)에서는 레이아웃이 줄지 않아 `sticky bottom-0`
입력창이 키보드 뒤로 들어간다.

### 2.8 정상 확인된 것

- 문서 자체 스크롤 없음 (`scrollHeight == clientHeight == 844`) — 이중 스크롤 없음
- 가로 오버플로 0건 (`scrollWidth == clientWidth == 390`)
- `min-h-0 flex-1` 체인 정상 — **arch/86 회귀 없음**
- 모바일 헤더 자동 숨김 정상 (스트리밍 중 오작동 없음)

---

## 3. 수정

### 3.1 follow 모델 (`NarrativePanel.tsx`)

거리 임계 단일 판정을 폐기하고 세 축으로 나눴다.

| 축 | 규칙 |
|---|---|
| ① 추적 해제 | 사용자 스크롤이 하단 `FOLLOW_RESUME_PX`(32px)를 벗어나면 `follow = false`, 하단권으로 돌아오면 재개 |
| ② 이벤트 출처 구분 | 자동 스크롤은 `programmaticUntil` 창(smooth 500ms / auto 80ms)을 세우고, 그 창 안의 `scroll` 이벤트는 판정에서 제외 |
| ③ 사용자 우선 | `touchstart`·`wheel`·`pointerdown`·`keydown` 수신 시 그 창을 **즉시 무효화**. 손가락이 닿아 있는 동안(`touching`)에는 자동 스크롤 자체를 중단 |

②가 없으면 smooth 스크롤이 만들어내는 중간 위치가 "사용자가 위로 올림"으로 오판되고,
③이 없으면 프로그램 스크롤과 터치 드래그가 경합해 떨린다.

선택지가 열리는 순간의 강제 하단 노출(`shouldForceChoiceIntoView`)은 조작 대상이므로
기존 동작을 유지했다.

### 3.2 상단 고정 영역 단일 정본

```ts
// GameClient.tsx
const MOBILE_HEADER_OFFSET = "calc(env(safe-area-inset-top) + 81px)";
```

- 비-이야기 탭 스페이서를 이 값으로 교체 (구 `h-20`)
- `PartyHUD`를 두 레이아웃 **바깥**에서 각 레이아웃 **내부**로 이동
- 배너·HUD가 있으면(`hasMobileTopBar`) 이야기 탭도 스페이서를 켜고
  `NarrativePanel topInset={false}` + **헤더 자동 숨김 비활성**
  (숨는 순간 in-flow 스페이서만 남아 상단에 빈 띠가 생기므로)
- 배너 표시 조건의 정본은 `DeadlineBanner`에 두고 `useDeadlineBannerVisible()`을
  export — 호출부가 조건을 복제하지 않는다

### 3.3 화면 스크롤 구조

`overflow-hidden` + `maxHeight:600`(죽은 값) 제거 → **바깥 `h-full overflow-y-auto`
+ 안쪽 `min-h-full` 중앙정렬**. 타이틀은 배경 이미지를 바깥 레이어에 고정하고
콘텐츠 레이어만 스크롤한다.

> ⚠️ 스크롤러 자신에게 `min-h-full`을 주면 안 된다. 높이가 내용에 따라 자라
> 상위 `overflow-hidden`(PageTransition)에 다시 잘린다. **높이 제약은 바깥,
> 최소 높이는 안쪽**이 규약.

### 3.4 모달 2패턴

| 유형 | 처방 |
|---|---|
| 중앙형 13곳 | 오버레이에 `overflow-y-auto overscroll-contain py-4`, 패널에 `m-auto` |
| 바텀시트 3곳 | 패널에 `max-h-[88dvh] overflow-y-auto overscroll-contain` + `pb-[env(safe-area-inset-bottom)]` |

패널 `m-auto`가 핵심이다. flex `items-center`만으로 스크롤시키면 **위쪽으로 넘친
영역에 도달할 수 없다**(flex 중앙정렬의 알려진 함정). `margin:auto`는 양방향 모두
스크롤 가능하다.

`vh` → `dvh` 전환도 함께 했다(모바일 URL 바 신축 대응).

### 3.5 그 외

- `overscroll-contain`을 전 스크롤 컨테이너에 적용
- safe-area 패딩: `CreationLayout`(헤더/푸터) · 엔딩·여정 기록 · 모바일 탭 하단 ·
  파티 로비 헤더/푸터 · 전투 액션바 · 타이틀/로그인/캠페인
- viewport meta에 `interactive-widget=resizes-content`
- `NpcDossierTab` 인물 카드 `shrink-0` (짧은 화면에서 잘림 대신 스크롤)

---

## 4. 검증

`eslint` 0 · `next build` 통과 · 실런 재측정.

| 항목 | 수정 전 | 수정 후 |
|---|---|---|
| 서술 스크롤 (60px 위) | DOM 변화 1회에 하단 복귀 | 실제 턴 스트리밍 9회 샘플 전 구간 `8793` 고정 |
| 추적 재개 | — | 하단 10px 복귀 → mutation 후 `distFromBottom 0` |
| `overscroll-behavior-y` | `auto` | `contain` |
| 타이틀 844x390 | 도달 불가 3개 | **0개** |
| 로그인 390x390 | 제출 버튼 4px 노출 | 스크롤로 전체 도달 (`sh 550 / ch 390`) |
| 버그신고 모달 390x380 | `top -49` / 스크롤 불가 | `top 46` / `panelScrolls true` |
| 설정 모달 390x400 | 하단 잘림 | 오버레이 `sh 464 > ch 400` → 하단 도달 |
| 상단 스페이서 | 80px vs 헤더 81px | 헤더 하단 81 = 스페이서 81 = 콘텐츠 시작 81 |
| 가로 오버플로 | 0 | 0 (유지) |

프로덕션(dimtale.com) 재확인: viewport meta 반영, 타이틀 844x390·390x390 클리핑 0건.

잔여 `clippedContainers` 1건은 `LocationBackdrop`의 의도적 `overflow-hidden`(배경 레이어).

---

## 5. 규약 (신규)

1. **모바일 상단 오프셋의 정본은 `MOBILE_HEADER_OFFSET` 하나다.**
   `MobileHeader` 마크업(높이)을 바꾸면 이 상수도 함께 갱신한다. 현재 81px =
   `h-12`(48) + 상태줄 `h-8`(32) + 보더(1).
2. **화면 루트는 "바깥 높이 제약 + 안쪽 `min-h-full`"**. 스크롤러에 `min-h-full`을
   주지 않는다 (§3.3).
3. **새 스크롤 컨테이너는 `overscroll-contain`을 기본으로 단다.** 빠뜨리면 Android
   당겨서 새로고침으로 플레이 중 리로드가 발생한다.
4. **새 모달은 §3.4의 2패턴 중 하나를 따른다.** 중앙형은 패널 `m-auto` 필수.
5. **`viewport-fit=cover`이므로 화면 최상/최하단 요소는 safe-area 패딩을 갖는다.**
   하단 패딩은 실제 최하단 요소에 준다 (스크롤 영역이 아니라 그 아래 푸터가
   최하단이면 푸터에 — 파티 로비에서 한 번 잘못 넣었다가 교정).

---

## 6. 잔여

- **실기기 확인 필요**: 헤드리스 Chromium은 `env(safe-area-inset-*)`를 항상 0으로
  보고한다. §3.2·§3.5의 safe-area 항목은 **계산식 정합까지만** 검증됐다. 노치
  아이폰에서 ① 인물/소지품/퀘스트 탭 상단 ② 캐릭터 생성 화면 하단 버튼 육안 확인 권장.
- **iOS 키보드**: `interactive-widget`은 Android Chrome 계열에서 동작한다. iOS Safari는
  `visualViewport` 기반 대응이 별도로 필요할 수 있으나, 이번 수정으로 스크롤 도달성이
  확보되어 "제출 못 함"류 차단 이슈는 해소됐다. 추가 대응은 실기기 관찰 후 판단.
- `-webkit-overflow-scrolling: touch`는 추가하지 않았다 — iOS 13+ 기본 동작이라
  실효가 없고, 파티 컴포넌트 3곳에 남은 것은 레거시다.
