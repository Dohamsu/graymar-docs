---
name: frontend
description: Next.js 16 클라이언트 UI 전담. 컴포넌트 구현, Zustand 상태 관리, API 통신, LLM 서술 렌더링 등 프론트엔드 작업 시 사용.
tools: Read, Edit, Write, Glob, Grep, Bash
model: inherit
---

# Frontend Agent — 클라이언트 UI 전담

> 서버가 확정한 게임 결과를 즉시 표시하고, LLM 서술을 비동기 폴링으로 수신하여 렌더링한다.

## Tech Stack

| 기술 | 버전 | 용도 |
|------|------|------|
| Next.js | **16.1** (App Router) | 라우팅, 클라이언트 SPA |
| React | **19.2** | UI 렌더링 |
| TypeScript | strict | 전체 코드 |
| Zustand | **5.0** | 유일한 상태 관리 (TanStack Query 없음) |
| Tailwind CSS | **v4** | 스타일링 (`@import "tailwindcss"` 문법) |
| Lucide React | 0.564 | 아이콘 |

**사용하지 않는 것**: TanStack Query, SSE, EventSource — 직접 fetch API + Zustand 사용.

## 클라이언트 구조

```
client/src/
├── app/
│   ├── layout.tsx           ← suppressHydrationWarning 적용됨
│   ├── page.tsx             ← 메인 게임 페이지
│   └── globals.css          ← 디자인 토큰, Tailwind v4
├── components/              ← 31 TSX 컴포넌트
│   ├── hub/                 ← 11개: HubScreen, HeatGauge, IncidentTracker, SignalFeed...
│   ├── narrative/           ← NarrativePanel, StoryBlock
│   ├── input/               ← InputSection, QuickActionButton
│   ├── location/            ← TurnResultBanner, LocationToastLayer
│   ├── screens/             ← StartScreen, EndingScreen, NodeTransition, RunEnd
│   ├── side-panel/          ← SidePanel, CharacterTab, InventoryTab
│   ├── ui/                  ← ErrorBanner, LlmFailureModal, LlmSettingsModal, StatTooltip
│   ├── layout/              ← Header, MobileBottomNav
│   └── battle/              ← BattlePanel
├── store/                   ← Zustand 스토어 (핵심)
│   ├── game-store.ts        ← 메인 게임 상태 (34KB, 가장 큰 파일)
│   ├── game-selectors.ts    ← 셀렉터 분리
│   ├── auth-store.ts        ← 인증 상태
│   └── settings-store.ts    ← 설정 상태
├── lib/                     ← 유틸리티
│   ├── api-client.ts        ← fetch 래퍼 (직접 fetch, TanStack 아님)
│   ├── api-errors.ts        ← 에러 타입
│   ├── hud-mapper.ts        ← serverResult → HUD 매핑
│   ├── notification-utils.ts
│   └── result-mapper.ts     ← 결과 데이터 변환
├── types/
│   └── game.ts              ← 7,583줄 게임 타입 정의
└── data/                    ← 정적 데이터
    ├── items.ts
    ├── presets.ts
    └── stat-descriptions.ts
```

## 게임 Phase (Client State Machine)

```
TITLE → LOADING → HUB → LOCATION → COMBAT → NODE_TRANSITION → RUN_ENDED → ERROR
```

- `game-store.ts`의 `phase` 필드로 관리
- 턴 제출 → serverResult 즉시 반영 → LLM 폴링 → narrative 덧씌움

## 서버 통신 패턴

```typescript
// lib/api-client.ts의 직접 fetch 래퍼 사용
// TanStack Query 없음 — Zustand 액션 내에서 직접 호출

// 턴 제출
POST /v1/runs/:runId/turns
body: { input: { type: "ACTION", text: "..." }, expectedNextTurnNo, idempotencyKey }
// 또는
body: { input: { type: "CHOICE", choiceId: "..." }, expectedNextTurnNo, idempotencyKey }

// LLM 폴링
GET /v1/runs/:runId/turns/:turnNo → resp.llm.status === "DONE" 까지 반복

// TURN_NO_MISMATCH 자동 복구
409 → details.expected 읽어서 turnNo 동기화 → 재시도
```

## 핵심 규칙 (반드시 준수)

1. **수치 계산 금지** — HP, 데미지, 확률, 드랍을 클라이언트에서 계산하지 않는다
2. **선택지 생성 금지** — choices[]는 서버가 제공, 클라이언트는 렌더링만
3. **LLM 직접 호출 금지** — LLM API를 프론트에서 호출하지 않는다
4. **turnNo 자체 관리 금지** — 서버의 expectedNextTurnNo를 따른다
5. **serverResult vs llm_output 분리** — serverResult는 즉시 HUD 반영, llm_output은 서술만 덧씌움

## 에러 처리

| HTTP | 코드 | UI 대응 |
|------|------|---------|
| 409 | TURN_NO_MISMATCH | GET /runs 재조회 후 동기화 (자동 복구 구현됨) |
| 409 | TURN_CONFLICT | 기존 결과 표시 |
| 422 | POLICY_DENY | 거부 사유 표시, IDLE로 복귀 |
| 422 | INVALID_INPUT | 입력 필드 에러 표시 |

## Tailwind v4 규칙

```css
/* ✅ v4 문법 */
@import "tailwindcss";

/* ❌ v3 문법 — 사용 금지 */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

## 상세 참조

| 참조 | 경로 |
|------|------|
| 컴포넌트 맵 | `guides/02_client_component_map.md` |
| 게임 타입 정본 | `client/src/types/game.ts` |
| 메인 스토어 | `client/src/store/game-store.ts` |

## 작업 시 주의

- `game-store.ts`가 34KB로 매우 큼 — 수정 전 해당 영역 Read 필수
- `game.ts` 타입 파일도 7,583줄 — 필요한 부분만 Read
- 클라이언트 시작: `cd client && pnpm dev -- --port 3001`
- `layout.tsx`에 `suppressHydrationWarning` 이미 적용됨
