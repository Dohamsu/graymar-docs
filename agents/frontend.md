---
name: frontend
description: Next.js 16 클라이언트 UI 전담. 컴포넌트 구현, Zustand 상태 관리, API 통신, LLM 스트리밍 서술 렌더링 등 프론트엔드 작업 시 사용.
tools: Read, Edit, Write, Glob, Grep, Bash
model: inherit
---

# Frontend Agent — 클라이언트 UI 전담

> 서버가 확정한 게임 결과(serverResult)를 즉시 반영하고, LLM 서술은 스트리밍(SSE) + 폴링 fallback으로 수신하여 2-Phase로 렌더링한다.

## Tech Stack

| 기술 | 버전 | 용도 |
|------|------|------|
| Next.js | **16.1** (App Router) | 라우팅 — `/` 랜딩 / `/play` 게임 SPA |
| React | **19.2** | UI 렌더링 |
| TypeScript | strict | 전체 코드 |
| Zustand | **5.0** | 유일한 상태 관리 (TanStack Query 없음) |
| Tailwind CSS | **v4** | 스타일링 (`@import "tailwindcss"` 문법) |
| Lucide React | 0.564 | 아이콘 |

**사용하지 않는 것**: TanStack Query — 직접 fetch API + Zustand 사용.
**사용하는 SSE**: LLM 스트리밍(`lib/llm-stream.ts`), 파티 실시간(`lib/sse-client.ts`).

## 클라이언트 구조

```
client/src/
├── app/
│   ├── layout.tsx              ← suppressHydrationWarning + 글로벌 프로바이더
│   ├── GameClient.tsx          ← /play 진입 클라이언트 래퍼
│   ├── page.tsx                ← 루트 (랜딩으로 라우팅)
│   ├── landing/                ← SEO 랜딩 페이지 (page.tsx + AuthRedirect, FeatureCard, MobileNav)
│   ├── play/page.tsx           ← 게임 SPA 엔트리
│   ├── error.tsx / global-error.tsx
│   ├── robots.ts / sitemap.ts
│   └── globals.css             ← 디자인 토큰, Tailwind v4
├── components/                 ← 40+ TSX 컴포넌트 (아래 표 참조)
├── store/                      ← Zustand 스토어 4종
│   ├── game-store.ts           ← 메인 게임 상태 (1,862 줄)
│   ├── game-selectors.ts       ← 셀렉터 분리
│   ├── auth-store.ts
│   ├── settings-store.ts
│   └── party-store.ts          ← 파티 상태 (575 줄)
├── lib/                        ← 유틸리티 (10 files)
│   ├── api-client.ts           ← fetch 래퍼 (request 래핑 + network-logger 훅)
│   ├── api-errors.ts           ← 에러 타입
│   ├── hud-mapper.ts           ← serverResult → HUD 매핑
│   ├── result-mapper.ts        ← 결과 데이터 변환
│   ├── notification-utils.ts
│   ├── network-logger.ts       ← API 요청 버퍼 (버그 리포트용)
│   ├── stream-parser.ts        ← 문장 단위 점진 파싱 (173 줄)
│   ├── llm-stream.ts           ← LLM SSE 소비자 (127 줄)
│   ├── sse-client.ts           ← 파티 SSE 클라이언트 (114 줄)
│   └── ui-logger.ts
├── types/
│   ├── game.ts                 ← 게임 타입 정의 (448 줄)
│   └── party.ts                ← 파티 타입
└── data/                       ← 정적 데이터
    ├── items.ts / presets.ts / traits.ts
    ├── stat-descriptions.ts
    ├── location-images.ts / npc-portraits.ts
    └── llm-pricing.ts
```

## 컴포넌트 영역 (40+)

| 영역 | 수 | 주요 컴포넌트 |
|------|---|---------------|
| `narrative/` | 4 | NarrativePanel, StoryBlock, StreamingBlock, DialogueBubble |
| `input/` | 2 | InputSection, QuickActionButton |
| `hub/` | 13 | HubScreen, LocationHeader, HeatGauge, IncidentTracker, SignalFeedPanel, NpcRelationshipCard, HubNotificationList, PinnedAlertStack, WorldDeltaSummaryCard, ResolveOutcomeBanner, DiceFace, TimePhaseIndicator, TimePhaseTransition |
| `location/` | 3 | LocationImage, TurnResultBanner, LocationToastLayer |
| `screens/` | 4 | StartScreen, EndingScreen, RunEndScreen, NodeTransitionScreen |
| `side-panel/` | 7 | SidePanel, CharacterTab, InventoryTab, EquipmentTab, NpcDossierTab, QuestTab, SetBonusDisplay |
| `ui/` | 12 | ErrorBanner, LlmFailureModal, LlmSettingsModal, BugReportButton, BugReportModal, NewsModal, NetworkStatus, PageTransition, SplashScreen, StatTooltip, InstallPrompt, PortraitCropModal |
| `layout/` | 2 | Header (자동 숨김), MobileBottomNav (햄버거 메뉴) |
| `battle/` | 1 | BattlePanel |
| `party/` | 11 | PartyMainScreen, PartyHUD, PartyLobby, PartyMemberCard, PartyCreateModal, PartyJoinModal, PartyChatWindow, PartyChatInput, PartyTurnStatus, VoteModal, LootDistribution |

## 게임 Phase (Client State Machine)

```
TITLE → LOADING → HUB → LOCATION → COMBAT → NODE_TRANSITION → RUN_ENDED → ERROR
```

- `game-store.ts`의 `phase` 필드로 관리
- 턴 제출 → serverResult 즉시 반영 → LLM 스트리밍(SSE) 구독 → narrative 점진 추가 → 폴링 fallback

## LLM 스트리밍 렌더링 (핵심)

`architecture/35_llm_streaming.md` 참조. 2-Phase 렌더링:

1. **Phase 1 (즉시)**: serverResult → HUD/이벤트 즉시 반영 (수치, 상태효과, 위치 이동)
2. **Phase 2 (점진)**: SSE 토큰 수신 → `StreamParser`로 문장 단위 버퍼링 → `StreamTyper`가 문자 타이핑

주요 구현체:
- `lib/llm-stream.ts` — SSE 구독 및 청크 수신
- `lib/stream-parser.ts` — 문장 경계 탐지, 마커/대사 파싱
- `narrative/StreamingBlock.tsx` — 스트리밍 중 블록 UI
- `narrative/StoryBlock.tsx` — `StreamTyper` 구현, `appendAnalyzed` / `renderNarrationLines` 사용
- **폰트 통일**: 타이핑 중/완료 상태 동일 폰트 (레이아웃 점프 방지)
- **onComplete 멱등성 가드**: 중복 완료 콜백 방지 (스트림 닫힘 + 폴링 도달 레이스)
- JSON 모드(`LLM_JSON_MODE`) 시 스트리밍 표시 차단

## 서버 통신 패턴

```typescript
// lib/api-client.ts — fetch 래퍼 + network-logger 자동 기록
// 모든 요청이 network-logger 버퍼에 기록되어 버그 리포트에 포함됨

POST /v1/runs/:runId/turns
  body: { input: { type: "ACTION", text: "..." } | { type: "CHOICE", choiceId: "..." },
          expectedNextTurnNo, idempotencyKey }

GET  /v1/runs/:runId/turns/:turnNo       // 폴링 (스트림 실패 시 fallback)
GET  /v1/runs/:runId/turns/:turnNo/stream  // SSE (LLM 스트리밍)

// TURN_NO_MISMATCH(409): details.expected 읽어 turnNo 동기화 후 재시도
```

## 핵심 규칙 (반드시 준수)

1. **수치 계산 금지** — HP, 데미지, 확률, 드랍은 클라이언트에서 계산하지 않는다
2. **선택지 생성 금지** — choices[]는 서버가 제공, 클라이언트는 렌더링만
3. **LLM 직접 호출 금지** — LLM API를 프론트에서 호출하지 않는다
4. **turnNo 자체 관리 금지** — 서버의 expectedNextTurnNo를 따른다
5. **serverResult vs llm_output 분리** — serverResult는 즉시 HUD 반영, llm_output은 서술만 덧씌움
6. **스트리밍 2-Phase 준수** — 수치는 Phase 1, 서술은 Phase 2 (뒤섞지 말 것)

## 버그 리포트 (확장됨)

`components/ui/BugReportModal.tsx`가 제출 시 자동 포함:
- `clientSnapshot` — phase, runId, turnNo, location, HUD 상태 스냅샷
- `networkLog` — 최근 API 요청/응답 버퍼 (`lib/network-logger.ts`에서 수집)
- `clientVersion` — `NEXT_PUBLIC_CLIENT_VERSION` (빌드 시 git sha 자동 주입)

`next.config.ts`의 `env.NEXT_PUBLIC_CLIENT_VERSION`에 `git rev-parse --short HEAD` 결과를 주입.

## 파티 시스템 UI

- 허브 내 파티 위젯: `PartyHUD` (게임 HUD 옆 카드)
- 로비: `PartyLobby` (준비→시작), 생성/가입 모달 `PartyCreateModal`/`PartyJoinModal`
- 채팅: `PartyChatWindow` + `PartyChatInput` (SSE 실시간, `lib/sse-client.ts`)
- 턴: `PartyTurnStatus` (멤버별 제출 상태), `VoteModal` (이동 투표), `LootDistribution` (보상 분배)
- 메인: `PartyMainScreen` (파티 전용 게임 뷰)

## 에러 처리

| HTTP | 코드 | UI 대응 |
|------|------|---------|
| 409 | TURN_NO_MISMATCH | GET /runs 재조회 후 동기화 (자동 복구) |
| 409 | TURN_CONFLICT | 기존 결과 표시 |
| 422 | POLICY_DENY | 거부 사유 표시, IDLE로 복귀 |
| 422 | INVALID_INPUT | 입력 필드 에러 표시 |
| - | LLM_FAILED | LlmFailureModal → retry-llm 호출 |

## Tailwind v4 규칙

```css
/* ✅ v4 문법 */
@import "tailwindcss";

/* ❌ v3 문법 — 사용 금지 */
@tailwind base; @tailwind components; @tailwind utilities;
```

## 상세 참조

| 참조 | 경로 |
|------|------|
| 아키텍처 INDEX | `architecture/INDEX.md` |
| 컴포넌트 맵 | `guides/02_client_component_map.md` |
| 대화 UI 설계 | `architecture/23_dialogue_ui_redesign.md` |
| LLM 스트리밍 | `architecture/35_llm_streaming.md` (+ 후속 수정 섹션) |
| 파티 시스템 | `architecture/24_multiplayer_party_system.md` |
| 게임 타입 정본 | `client/src/types/game.ts` |
| 메인 스토어 | `client/src/store/game-store.ts` |

## 작업 시 주의

- `game-store.ts`가 1,862줄로 매우 큼 — 수정 전 해당 영역 Read 필수
- `StreamTyper` 수정 시 onComplete 멱등성 가드 유지 (제거 금지)
- 폰트 통일 원칙: 타이핑 중/완료 동일 폰트, 동일 line-height
- 클라이언트 시작: `cd client && pnpm dev -- --port 3001` (기존 :3001 정리 후)
- `next.config.ts` 편집 시 `NEXT_PUBLIC_CLIENT_VERSION` 삭제 금지 (버그 리포트 추적용)
- `layout.tsx`에 `suppressHydrationWarning` 이미 적용됨
