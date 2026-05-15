# 엔딩 연출 개선 + 여정 아카이브 Phase 1

> 작성 2026-04-20. 커밋: server 46a7a59 / client 0462ffc / docs 73ad71d

이 문서는 두 개 주제를 한 곳에 묶는다:
1. **엔딩 직전·직후 연출 강화** — 톤 가이드, 배너, 분기 에필로그, 개인화 마지막 서술
2. **여정 아카이브** — 과거 RUN_ENDED 세션의 엔딩 요약을 나중에 다시 열람할 수 있는 기능

## 1. 엔딩 연출 개선 (6항목)

### 1-1. Part B 트리거 가드 (High)
- 파일: `server/src/turns/turns.service.ts:3133~` · `server/src/engine/hub/ending-generator.service.ts`
- 기존: `s5Turns >= 5` 만 체크해서 turnNo<15에 모든 incident를 CONTAINED로 마킹하면 `checkEndingConditions`의 MIN_TURNS 가드로 인해 엔딩이 **영구 누락**
- 수정: `MIN_TURNS_FOR_NATURAL = 15` 상수를 ending-generator에서 export하고 Part B 조건에 `turnNo >= MIN_TURNS_FOR_NATURAL` 추가

### 1-2. commitTurnRecord 순서 수정 (High)
- 기존: commit → ui.endingResult 할당 순서라 DB에 endingResult 저장 안 됨
- 수정: 엔딩 생성 + ui 할당 + events push를 commit 이전으로 이동 → RUN_ACTIVE 상태 업데이트와 campaign 저장만 commit 이후에 남김
- 효과: 재접속 시 엔딩 데이터 복원 가능

### 1-3. Arc Route 분기 엔딩 적용
- content `endings.json arcRouteEndings` 12분기(EXPOSE_CORRUPTION / PROFIT_FROM_CHAOS / ALLY_GUARD / NONE × STABLE/UNSTABLE/COLLAPSED) 매핑 로직 신설
- `EndingResult`에 `arcRoute / arcTitle / arcEpilogue / arcRewards` 필드 추가
- 클라 `EndingScreen`에 "당신의 길" 카드 신규 렌더 (arcTitle 골드 헤더 + arcEpilogue 긴 문단 + arcRewards 뱃지)

### 1-4. personalClosing (개인화 마지막 서술)
- `ending-generator.buildPersonalClosing()` 템플릿 조립 (LLM 호출 없음)
- 4문장 구조: 여정 길이 → 사건 결과 요약 → 최고/최저 trust NPC 여운 → dominant vector 마무리
- `EndingScreen` 골드 세로선 인용 스타일로 배치
- 6가지 vector(SOCIAL/STEALTH/VIOLENT/ECONOMIC/PRESSURE/OBSERVATIONAL)별 마지막 문장 테이블

### 1-5. Soft Deadline 시그널 자동 생성 + DeadlineBanner
- 서버: `SignalFeedService.generateSoftDeadlineSignal` 신규 — 3단계 톤
  - `daysLeft === 3` → NEAR (severity 4)
  - `daysLeft ≤ 2` → URGENT (severity 5, 일수 명시)
  - `triggered` 또는 `daysLeft < 0` → EXCEEDED (severity 5)
- WorldTickService.postStepTick에서 매 tick 호출 + mainArcClock.triggered 자동 동기화
- 클라: `components/location/DeadlineBanner.tsx` — 데스크톱/모바일 Header 아래 sticky
  - 주황(D-3) / 빨강(D-2/1/0) / 빨강 강조(시한 초과)
  - 조건 미충족 시 `null` 반환 → DOM 제로 오버헤드

### 1-6. LLM 프롬프트 deadlineContext 조건부 주입
- `ContextBuilderService.buildDeadlineContext()` static 헬퍼 (테스트 친화)
- `PromptBuilderService`에서 조건부 `[결말 임박]` memoryParts push
- NEAR: "직접 언급 금지" · URGENT: "긴박감, 초조함" · EXCEEDED: "체념·가속"
- 평소(daysLeft ≥ 4) `null` 반환 → 프롬프트 미포함

### 1-7. 페이지 전환 연출 (기존 확인)
- `PageTransition` HUB/LOCATION/COMBAT→RUN_ENDED 전환에 FADE_LONG (1s slowFadeToBlack + 1.2s fadeFromBlack) 이미 설정되어 있음. 코드 변경 없음

---

## 2. 여정 아카이브 Phase 1

### 2-1. 데이터 모델
- DB 컬럼 추가: `run_sessions.ending_summary jsonb` (nullable)
  - 마이그레이션: `server/drizzle/0003_add_ending_summary.sql`
- 타입 정의: `server/src/db/types/ending.ts`
  - `JourneyKeyEvent { kind, day?, text, outcome? }`
  - `JourneyKeyNpc { npcId, npcName, bondLabel, oneLine, posture }`
  - `EndingSummary { runId, completedAt, characterName, presetId, presetLabel, gender, synopsis, keyEvents, keyNpcs, finale, stats }`
  - `EndingSummaryCard` — 리스트 표시용 경량 타입

### 2-2. 서버: SummaryBuilderService (신규)
- 파일: `server/src/engine/hub/summary-builder.service.ts`
- 순수 함수 조합, LLM 호출 없음 → 결정론적
- synopsis 4문장 조립:
  1. 도입 (프리셋 + 이름 + 여정 길이, `topicParticle` 자동 조사)
  2. 여정 방식 (dominantVectors 상위 2개 → 12개 쌍 테이블 매칭, 미매칭 시 Top1 단일 벡터 fallback)
  3. 전환점 (첫 CONTAINED incident 또는 첫 NarrativeMark — `MARK_TEXT` 12종)
  4. 결말 (arcRoute × stability 12분기 테이블)
- keyEvents 우선순위: ESCALATED(4) > CONTAINED(3) = MARK(3) > EXPIRED(2) > DISCOVERY(1), clock 오름차순, 최대 6
  - incident outcome variant 순환 (CONTAINED 4종 / ESCALATED 3종 / EXPIRED 3종) — 반복 서술 방지
- keyNpcs 선별: trust ≥ 30 상위 2 → trust ≤ -30 최하 1 → attachment ≥ 50 → respect ≥ 50 → CORE tier appearanceCount → tierPriority, 최대 5
  - content 정의 없는 NPC는 자동 제외 (ID 문자열 노출 방지)
- 한국어 조사 헬퍼 내장 (`korParticle`, `topicParticle`, `objParticle`, `subjParticle`, `withParticle`)

### 2-3. 저장 타이밍
- `turns.service.ts`의 RUN_ENDED 분기 3곳(NATURAL/DEADLINE, HP≤0 DEFEAT, COMBAT DEFEAT)에서 `buildEndingSummary()` 호출 후 `runSessions.ending_summary` 업데이트
- try/catch로 감싸 요약 생성 실패가 엔딩 저장을 막지 않음

### 2-4. API
- `GET /v1/endings?limit=20&cursor=<runId>` — `{ items: EndingSummaryCard[], page: { hasMore, nextCursor } }` cursor 기반 seek pagination
- `GET /v1/endings/:runId` — `EndingSummary` 직접 반환
- 과거 RUN_ENDED 런은 `ensureEndingSummary()`에서 lazy 생성 + 캐시
- `GET /v1/runs`의 응답에 `endingsCount: number` 필드 추가

### 2-5. 클라이언트
- 컴포넌트
  - `components/screens/EndingsListScreen.tsx` — 카드 그리드 (stability 뱃지, 캐릭터/일수/턴/날짜, cursor 페이지네이션)
  - `components/screens/JourneySummaryScreen.tsx` — 양피지 스타일 단일 페이지 (6 섹션: 헤더 / 줄거리 / 핵심 사건 / 남은 인연 / 결말 / 통계 / 액션바)
- `game-store` 확장: `archivedEndings`, `archiveCursor`, `archiveTotal`, `activeSummary`, `endingsCount` + `loadEndings`, `loadSummary`, `clearSummary` 액션
- phase enum 확장: `ENDINGS_LIST`, `ENDINGS_DETAIL`
- `StartScreen` 조건부 버튼: `endingsCount >= 1` 일 때만 "여정 기록 (N)" 표시
- `PageTransition` 4개 매핑 추가

---

## 3. 단위 테스트

- `signal-feed.service.spec.ts` (10) — soft deadline 시그널 3단계, 중복 방지, channel/expires
- `ending-generator.service.spec.ts` (18) — MIN_TURNS 가드, arcRoute 분기 5, stability 판정, personalClosing 4, endingType
- `summary-builder.service.spec.ts` (20) — synopsis 분기 6, keyEvents 우선순위 4, keyNpcs 선별 4, finale/meta 6
- `context-builder.deadline.spec.ts` (8) — buildDeadlineContext 조건별 분기
- 전체 회귀: 530/530 통과

## 4. 검증 결과 (E2E)

- 20턴 playtest로 신규 런 생성 → RUN_ACTIVE 유지 상태에서 Playwright 로그인
- 자동 드랍된 장비 4개(순찰대 경갑 ×2 / 정찰병 고글 / 밀수업자 단검) InventoryTab에 정확히 표시
- 브라우저에서 "창고를 뒤진다" 턴 제출 → 4초 후 EquipmentDropToast (밀수업자의 단검 RARE) 실시간 캡처
- Journey Summary 화면: synopsis + keyEvents 6건 + keyNpcs 4명 + finale 전부 렌더링 정상 확인

## 5. 관련 Invariants

- RUN_ENDED 시 ending_summary 저장은 최선형(실패 시에도 기존 엔딩 저장은 유지)
- ending_summary가 NULL이면 조회 시 lazy 생성 + 캐시 (과거 런 호환)
- StartScreen "여정 기록" 버튼은 `endingsCount === 0` 일 때 **완전히 숨김** (UI 군더더기 방지)
- `EndingResult.arcRewards`는 UI 표시용. 실제 gold/reputation 지급은 현 단일 런 구조상 의미 없어 구현 보류 (다중 런/캠페인 구조로 확장 시 재검토)
