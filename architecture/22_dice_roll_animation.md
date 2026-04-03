# 22. Dice Roll Animation (주사위 판정 애니메이션)

> LOCATION 모드 판정 시 시각적 주사위 애니메이션으로 게임 몰입감을 향상한다.

## 1. 개요

### 목적

현재 LOCATION 판정 결과는 `ResolveOutcomeInline` 컴포넌트에서 유니코드 주사위 문자(&#x2680;)와 텍스트로만 표시된다. 이를 시각적으로 풍부한 주사위 애니메이션으로 교체하여:

- 판정 순간의 긴장감과 몰입감을 높인다
- 주사위 → 보정치 → 최종 결과의 계산 과정을 직관적으로 전달한다
- 텍스트 RPG 특유의 "다이스 롤" 경험을 제공한다

### 범위

| 적용 대상 | 설명 |
|-----------|------|
| LOCATION 판정 | ResolveService의 1d6 + stat 판정 (도전 행위만) |
| 비도전 행위 | NON_CHALLENGE_ACTIONS (OBSERVE, TALK, SEARCH 등)은 자동 SUCCESS이므로 애니메이션 제외 |
| COMBAT | 별도 설계 (향후 확장 섹션 참조) |

### 현재 구현 상태

`ResolveOutcomeInline` (파일: `components/hub/ResolveOutcomeBanner.tsx`)이 이미 존재하며:
- `DiceRolling` 컴포넌트: 유니코드 주사위 문자 순환 (100ms 간격) + `diceSpin` CSS 회전
- `BreakdownFormula` 컴포넌트: diceRoll + statBonus + baseMod = totalScore 텍스트 표시
- 단계: rolling (1.2s) -> revealed (결과 텍스트 + 분해 공식)

이번 설계는 기존 컴포넌트를 **대체(replace)** 하는 것이 아니라, 시각적 품질을 **향상(enhance)** 하는 방향이다.

---

## 2. 서버 데이터 (현재 상태)

### 이미 제공되는 필드

서버 `ResolveResult` (정본: `server/src/db/types/resolve-result.ts`)에서 주사위 관련 필드가 **이미 모두 제공**된다:

```
ResolveResult {
  score: number            // 최종 판정 점수
  outcome: ResolveOutcome  // SUCCESS | PARTIAL | FAIL
  diceRoll?: number        // 1d6 원시값 (1~6), 비도전 행위 시 undefined
  statKey?: string | null  // 판정에 사용된 스탯 키 (str, dex, per, wit, cha, con)
  statValue?: number       // 원시 스탯 값
  statBonus?: number       // floor(statValue / 4)
  baseMod?: number         // matchPolicy + friction + riskLevel + 세트효과 + 프리셋 보너스
  traitBonus?: number      // BLOOD_OATH + NIGHT_CHILD 합산
  gamblerLuckTriggered?: boolean  // FAIL -> PARTIAL 승격 여부
}
```

### 클라이언트 타입 (정본: `client/src/types/game.ts`)

```
ResolveBreakdown {
  diceRoll: number
  statKey: string | null
  statValue: number
  statBonus: number
  baseMod: number
  totalScore: number
  traitBonus?: number
  gamblerLuckTriggered?: boolean
}
```

### 결론: 서버 수정 불필요

주사위 원시값(`diceRoll`), 스탯 보정(`statBonus`), 기타 보정(`baseMod`, `traitBonus`), 최종 점수(`totalScore`)가 모두 `ResolveBreakdown`에 포함되어 있다. 추가 서버 작업 없이 클라이언트만으로 구현 가능하다.

---

## 3. 데이터 흐름

```
서버 ResolveService
  diceRoll = rng.range(1, 6)
  score = diceRoll + statBonus + baseMod + traitBonus
  outcome = computeOutcome(score)
      |
      v
POST /v1/runs/:runId/turns 응답
  serverResult.ui.resolveOutcome = outcome
  serverResult.ui.resolveBreakdown = { diceRoll, statKey, statBonus, baseMod, totalScore, ... }
      |
      v
result-mapper.ts
  StoryMessage { type: "RESOLVE", resolveOutcome, resolveBreakdown }
      |
      v
StoryBlock.tsx
  <ResolveOutcomeInline outcome={...} breakdown={...} />  <-- 이 컴포넌트를 개선
```

---

## 4. UI/UX 설계

### 4.1 트리거 조건

| 조건 | 트리거 여부 |
|------|------------|
| StoryMessage.type === "RESOLVE" && resolveBreakdown 존재 | 애니메이션 실행 |
| resolveBreakdown 없음 (비도전 행위) | 기존 텍스트 "성공" 표시 (애니메이션 없음) |
| 설정에서 애니메이션 OFF | 즉시 결과 표시 (애니메이션 건너뜀) |

### 4.2 표시 위치

현재와 동일하게 NarrativePanel 스크롤 영역 내부, RESOLVE 타입 StoryBlock 위치에 인라인 렌더링한다. 별도 오버레이 레이어는 사용하지 않는다.

이유:
- 대화 흐름 안에서 자연스럽게 판정 결과를 보여줘야 한다
- 오버레이는 모바일에서 터치 이벤트를 가로막을 수 있다
- 스크롤 히스토리에서 과거 판정을 다시 볼 수 있어야 한다

### 4.3 애니메이션 흐름 (4단계)

```
Phase 1: DICE_APPEAR (0.3s)
  주사위 면이 scale 0 -> 1로 등장
  도트 패턴이 있는 d6 면 비주얼

Phase 2: DICE_ROLL (0.8s)
  주사위 면이 빠르게 전환 (1->2->3->...->6->...)
  전환 속도: 처음 80ms -> 끝 200ms (감속 이징)
  최종값에서 정지

Phase 3: BREAKDOWN (0.4s)
  주사위 값 아래에 보정치가 하나씩 등장
  diceRoll  +  statBonus  +  baseMod  (+traitBonus)  =  totalScore
  각 항목이 순차적으로 fade-in (0.1s 간격)

Phase 4: OUTCOME (0.5s)
  최종 결과 라벨이 scale + glow 효과로 등장
  SUCCESS: 금-초록 글로우
  PARTIAL: 주황-금색 글로우
  FAIL: 붉은 글로우
  gamblerLuckTriggered 시 "도박꾼의 운!" 추가 이펙트

총 소요: ~2.0s (현재 1.2s + 0.2s에서 약간 증가)
```

### 4.4 주사위 비주얼

CSS로 구현하는 d6 면 표현:

```
 ___________
|           |
|  *     *  |    <- 도트 패턴으로 1~6 표현
|     *     |
|  *     *  |
|___________|

면 크기: 64x64px (모바일), 80x80px (데스크탑)
배경: var(--bg-card) 또는 약간 밝은 톤
테두리: 2px rounded-lg, var(--border-primary)
도트: 원형, 결과에 따라 색상 변경
  - rolling 중: var(--text-muted)
  - 정지 후: 결과 색상 (금/주황/붉은)
```

SVG 대신 CSS Grid를 사용하여 도트를 배치한다. 이유:
- 번들 크기 증가 없음
- 색상/크기 변경이 CSS 변수로 간단
- 6가지 면 패턴을 3x3 그리드로 표현 가능

### 4.5 도트 패턴 레이아웃 (3x3 Grid)

```
1: [_ _ _] [_ * _] [_ _ _]
2: [_ _ *] [_ _ _] [* _ _]
3: [_ _ *] [_ * _] [* _ _]
4: [* _ *] [_ _ _] [* _ *]
5: [* _ *] [_ * _] [* _ *]
6: [* _ *] [* _ *] [* _ *]
```

### 4.6 결과별 색상 토큰

기존 디자인 토큰(`globals.css`)을 그대로 사용:

| 결과 | 주사위 도트 | 글로우 | 텍스트 |
|------|-----------|--------|--------|
| SUCCESS | var(--success-green) | rgba(76, 175, 80, 0.3) | "성공" |
| PARTIAL | var(--gold) | rgba(255, 215, 0, 0.3) | "부분 성공" |
| FAIL | var(--hp-red) | rgba(244, 67, 54, 0.3) | "실패" |

### 4.7 gamblerLuckTriggered 특수 연출

GAMBLER_LUCK 특성으로 FAIL이 PARTIAL로 승격된 경우:
1. Phase 2에서 주사위가 정지한 뒤, FAIL 색상(붉은)으로 잠깐 표시 (0.3s)
2. 화면이 짧게 흔들리는 효과 (shake, 0.2s)
3. 색상이 PARTIAL(금색)으로 전환되며 "도박꾼의 운!" 텍스트가 플래시

---

## 5. 컴포넌트 구조

### 5.1 컴포넌트 트리

```
ResolveOutcomeInline (기존 파일 수정)
  |
  +-- DiceRollAnimation (신규)
  |     |
  |     +-- DiceFace (신규, CSS 도트 패턴)
  |     +-- BreakdownFormula (기존, 순차 fade-in 추가)
  |     +-- OutcomeLabel (기존 결과 라벨 분리)
  |
  +-- GamblerLuckFlash (신규, 조건부)
```

### 5.2 파일 위치

```
components/hub/ResolveOutcomeBanner.tsx    -- 기존 파일 수정
components/hub/DiceFace.tsx               -- 신규: CSS 주사위 면 컴포넌트
```

DiceFace를 별도 파일로 분리하는 이유: 향후 COMBAT 판정에서 재사용 가능.

### 5.3 Props 인터페이스 (의사 코드)

```
DiceRollAnimation {
  diceValue: number       // 1~6 최종 주사위 값
  breakdown: ResolveBreakdown
  outcome: ResolveOutcome
  onComplete: () => void  // 애니메이션 완료 콜백 (서술 텍스트 시작 트리거)
  skipAnimation: boolean  // 설정에서 OFF이거나 히스토리 재방문 시
}

DiceFace {
  value: number           // 1~6
  size: "sm" | "md"       // 64px | 80px
  dotColor: string        // CSS 색상값
  isRolling: boolean      // 롤링 중 여부 (blur 효과 적용)
}
```

### 5.4 게임 스토어 연동

게임 스토어에 별도 상태를 추가하지 않는다. 이유:
- 애니메이션은 StoryBlock 단위의 로컬 상태로 충분
- 전역 상태로 관리하면 불필요한 리렌더링 발생
- 과거 턴의 RESOLVE 블록은 skipAnimation=true로 즉시 표시

판단 기준: StoryMessage에 이미 `resolveBreakdown`이 포함되어 있으므로, 컴포넌트 마운트 시 로컬 useState로 phase를 관리하면 된다.

---

## 6. CSS 애니메이션 명세

### 6.1 신규 keyframes (globals.css에 추가)

```
@keyframes diceAppear
  0%   -> scale(0), opacity(0)
  60%  -> scale(1.1)
  100% -> scale(1), opacity(1)
  duration: 0.3s, ease-out

@keyframes diceSettle
  0%   -> transform: translateY(-2px)
  50%  -> transform: translateY(1px)
  100% -> transform: translateY(0)
  duration: 0.2s, ease-in-out
  -- 롤링 정지 후 "착지" 느낌

@keyframes breakdownItemAppear
  0%   -> opacity(0), translateX(-8px)
  100% -> opacity(1), translateX(0)
  duration: 0.15s, ease-out
  -- 각 보정치 항목에 순차 적용 (delay 0.1s 간격)

@keyframes outcomeGlow
  0%   -> box-shadow: 0 0 0 resultColor
  50%  -> box-shadow: 0 0 20px resultColor
  100% -> box-shadow: 0 0 8px resultColor
  duration: 0.6s, ease-in-out

@keyframes gamblerShake
  0%, 100% -> translateX(0)
  25%      -> translateX(-4px)
  75%      -> translateX(4px)
  duration: 0.2s
```

### 6.2 기존 keyframes 유지

`outcomeReveal`, `diceSpin`, `fadeIn`은 기존 코드 호환을 위해 유지하되, 새 애니메이션에서는 사용하지 않는다.

---

## 7. 성능 고려

### 7.1 GPU 가속

- 모든 애니메이션은 `transform`과 `opacity`만 사용하여 컴포지터 레이어에서 처리
- `box-shadow` 애니메이션(outcomeGlow)은 한 번만 실행 후 정적 값으로 전환
- `will-change: transform`은 롤링 phase에서만 적용, 완료 후 제거

### 7.2 리렌더링 방지

- DiceFace의 도트 패턴 데이터는 컴포넌트 외부 상수로 정의 (DICE_DOT_PATTERNS)
- 롤링 중 숫자 전환은 `setInterval` + `useState`로 최소 범위 리렌더링
- `React.memo`로 DiceFace를 감싸 불필요한 리렌더링 차단

### 7.3 번들 크기

- 외부 라이브러리 추가 없음 (Framer Motion 사용하지 않음)
- 순수 CSS keyframes + React useState로 구현
- DiceFace CSS 도트 패턴은 인라인 스타일이 아닌 Tailwind 유틸리티 클래스 활용

---

## 8. 토글 기능

### 8.1 설정 스토어 확장

`settings-store.ts`에 `diceAnimation` 필드를 추가한다:

```
SettingsState {
  ...기존 필드
  diceAnimation: boolean    // 기본값: true
  setDiceAnimation: (on: boolean) => void
}

localStorage 키: 'graymar_diceAnimation'
```

### 8.2 동작

| 설정 | 동작 |
|------|------|
| ON (기본) | 4단계 애니메이션 전체 실행 (~2.0s) |
| OFF | Phase 2~3 건너뛰고 즉시 결과 + 분해 공식 표시 (기존과 유사하게 ~0.3s) |

### 8.3 히스토리 재방문

스크롤하여 과거 턴의 RESOLVE 블록을 볼 때는 항상 skipAnimation=true (즉시 표시). 이는 기존 동작과 동일하며, StoryBlock이 마운트될 때 "최신 메시지인지" 여부로 판단한다.

---

## 9. 접근성

- 주사위 도트에 `aria-label="주사위 {값}"` 제공
- `prefers-reduced-motion` 미디어 쿼리 시 자동으로 애니메이션 건너뜀
- 판정 결과 텍스트("성공", "부분 성공", "실패")는 항상 텍스트로 표시 (시각 효과에만 의존하지 않음)
- 색상 외에 라벨 텍스트로 결과를 구분할 수 있으므로 색각 이상 사용자도 인식 가능

---

## 10. 모바일 대응

| 항목 | 데스크탑 | 모바일 (<768px) |
|------|---------|----------------|
| 주사위 면 크기 | 80x80px | 64x64px |
| 도트 크기 | 10px | 8px |
| 분해 공식 | 가로 한 줄 | 가로 한 줄 (텍스트 축소) |
| 총 애니메이션 시간 | ~2.0s | 동일 |

기존 NarrativePanel이 모바일에서 전체 폭을 사용하므로, 주사위 면은 중앙 정렬로 배치한다.

---

## 11. 테스트 시나리오

| 시나리오 | 검증 항목 |
|---------|----------|
| LOCATION에서 INVESTIGATE 행동 | diceRoll 값에 맞는 도트 패턴 표시, WIT 스탯 보정 표시 |
| PERSUADE 행동 + 세트효과 | baseMod에 +1 포함, 분해 공식에 보정 표시 |
| BLOOD_OATH + 저HP | traitBonus 표시 |
| GAMBLER_LUCK 발동 | shake + 색상 전환 + "도박꾼의 운!" 플래시 |
| 비도전 행위 (OBSERVE) | 애니메이션 없이 "성공" 텍스트만 표시 |
| 설정 OFF | 즉시 결과 표시 |
| 과거 턴 스크롤 | 애니메이션 없이 정적 표시 |
| 모바일 화면 | 64px 주사위, 레이아웃 깨짐 없음 |

---

## 12. 대안: 텍스트/ASCII 주사위 애니메이션

> 참고: Threads @choi.openai 텍스트 주사위 컨셉

CSS Grid 도트 패턴 대신, **텍스트 문자 자체로 주사위를 표현**하는 대안. 텍스트 RPG의 아이덴티티에 더 부합할 수 있다.

### 12.1 ASCII 주사위 면

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│         │    │  ●      │    │  ●   ●  │
│    ●    │    │    ●    │    │         │
│         │    │      ●  │    │  ●   ●  │
└─────────┘    └─────────┘    └─────────┘
   [ 1 ]          [ 3 ]          [ 4 ]
```

monospace 폰트(Geist Mono 또는 IBM Plex Sans KR)로 렌더링. NarrativePanel 안에서 서술 텍스트와 같은 텍스트 흐름 유지.

### 12.2 텍스트 롤링 애니메이션

```
Phase 1: 주사위 프레임 등장 (타이핑 효과)
  ┌─────────┐
  │         │   <- 한 줄씩 타이핑되듯 나타남 (0.3s)
  │         │
  │         │
  └─────────┘

Phase 2: 숫자 롤링 (도트가 빠르게 변경)
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │  ●   ●  │→ │  ●      │→ │  ●   ●  │  (0.6s, 감속)
  │  ●   ●  │  │    ●    │  │    ●    │
  │  ●   ●  │  │      ●  │  │  ●   ●  │
  └─────────┘  └─────────┘  └─────────┘

Phase 3: 정지 + 판정 수식
  ┌─────────┐
  │  ●   ●  │
  │    ●    │   🎲 5  +  민첩 2  +  보정 1  =  8
  │  ●   ●  │
  └─────────┘
              ━━ 성 공 ━━   (금색 글로우)

Phase 4: 서술 텍스트로 자연스럽게 전환
```

### 12.3 장점

| CSS Grid 도트 | 텍스트/ASCII |
|---------------|-------------|
| 시각적으로 세련됨 | 텍스트 RPG 분위기에 부합 |
| 별도 컴포넌트 필요 | 기존 텍스트 흐름에 자연스러움 |
| 모바일 크기 조정 필요 | monospace라 크기 자동 맞춤 |
| Canvas 느낌 | 터미널/TTRPG 느낌 |

### 12.4 구현 차이

- DiceFace를 CSS Grid 대신 `<pre>` 태그 + monospace로 렌더링
- 도트 문자: `●` (U+25CF) 또는 `⚫` 사용
- 프레임 문자: `┌ ┐ └ ┘ │ ─` (box drawing)
- 타이핑 효과: 각 줄을 0.05s 간격으로 순차 렌더링
- 기존 StoryBlock의 NARRATOR 메시지와 같은 폰트/스타일 유지

### 12.5 권장

**텍스트 RPG 특성상 ASCII 방식을 1순위로 추천.** 다크 판타지 분위기의 monospace 텍스트가 게임의 "필사본" 느낌과 일치하며, 별도 CSS 그래픽 없이 순수 텍스트만으로 구현 가능하다.

---

## 13. 향후 확장

### 12.1 COMBAT 판정 애니메이션

COMBAT의 hitRoll, varianceRoll, critRoll에도 유사한 주사위 연출을 적용할 수 있다. DiceFace 컴포넌트를 공유하되, BattlePanel 내에서 별도 트리거 로직을 구현한다.

### 12.2 주사위 스킨

커스텀 주사위 도트 색상/패턴을 설정할 수 있는 기능. localStorage에 저장하고 DiceFace의 dotColor prop으로 전달.

### 12.3 사운드 효과

주사위 굴림 사운드(dice_roll.mp3)를 Phase 2에서 재생. Web Audio API 사용, 설정에서 ON/OFF 토글. 사운드 파일은 `/public/sounds/` 에 배치하며 번들에 포함하지 않는다.

### 12.4 크리티컬 연출

totalScore가 매우 높거나 (8+) diceRoll이 6일 때 "대성공" 추가 이펙트 (파티클, 확대된 글로우). 서버에서 별도 필드 추가 없이 클라이언트에서 조건 판단 가능.

---

## 14. 구현 체크리스트

- [ ] `DiceFace.tsx` 생성 (CSS Grid 3x3 도트 패턴, 6면 지원)
- [ ] `ResolveOutcomeBanner.tsx`의 `DiceRolling` 컴포넌트를 `DiceRollAnimation`으로 교체
- [ ] 4단계 phase 상태 머신 구현 (DICE_APPEAR -> DICE_ROLL -> BREAKDOWN -> OUTCOME)
- [ ] `globals.css`에 신규 keyframes 추가 (diceAppear, diceSettle, breakdownItemAppear, outcomeGlow, gamblerShake)
- [ ] `settings-store.ts`에 `diceAnimation` 토글 추가
- [ ] `prefers-reduced-motion` 미디어 쿼리 대응
- [ ] gamblerLuckTriggered 특수 연출 구현
- [ ] 모바일 반응형 크기 조정
- [ ] 과거 턴 재방문 시 skipAnimation 처리 확인
- [ ] `pnpm build` 빌드 검증
