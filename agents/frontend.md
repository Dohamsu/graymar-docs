# Frontend Agent

> Role: 클라이언트 UI 전담. 서버가 확정한 게임 결과를 즉시 표시하고, LLM 서술을 비동기로 수신하여 렌더링한다.

---

## Tech Stack

| 기술 | 버전/옵션 | 용도 |
|------|----------|------|
| **Next.js** | 15+ (App Router) | 라우팅, SSR(랜딩/인증), 클라이언트 SPA(게임) |
| **TypeScript** | strict mode | 전체 코드 |
| **Tailwind CSS** | v4 | 스타일링 |
| **TanStack Query** | v5 | 서버 상태 관리, 폴링, mutation |
| **EventSource (SSE)** | 브라우저 네이티브 | LLM 서술 실시간 수신 |
| **Zustand** (권장) | v5 | 클라이언트 전용 상태 (UI State Machine) |

---

## 핵심 책임

### 1. UI State Machine 구현

7개 상태를 정확히 구현한다. (정본: `design/core_game_architecture_v1.md` §7)

```
IDLE → TURN_SUBMITTING → TURN_CONFIRMED → TURN_DISPLAYED → NODE_TRANSITION → IDLE
                              ↓
                         LLM_PENDING → TURN_DISPLAYED

TURN_SUBMITTING → ERROR → (retry) TURN_SUBMITTING | (cancel) IDLE
```

상태 전이 규칙:
- `TURN_CONFIRMED`: serverResult 수신 즉시 HUD 반영 (HP, 스태미나, 골드, 상태이상, 선택지)
- `LLM_PENDING`: 서술 영역에 로딩 표시. 게임 진행 잠금 여부는 정책으로 결정
- `TURN_DISPLAYED`: llm.output을 서술 영역에 렌더링. 수치는 이미 HUD에 반영되어 있음
- `NODE_TRANSITION`: 노드 종료 애니메이션 → 다음 노드 진입

### 2. 서버 통신

| Endpoint | 방식 | TanStack Query 패턴 |
|----------|------|---------------------|
| `POST /v1/runs` | mutation | `useMutation` |
| `POST /v1/runs/{runId}/turns` | mutation | `useMutation` + idempotencyKey 생성 |
| `GET /v1/runs/{runId}` | query | `useQuery` (복구/재접속) |
| `GET /v1/runs/{runId}/turns/{turnNo}` | query | `useQuery` (턴 상세) |
| `GET /v1/runs/{runId}/turns` | query | `useInfiniteQuery` (히스토리, cursor 기반) |
| `SSE /v1/runs/{runId}/events` | EventSource | 별도 훅 (`useLLMStream`) |

### 3. LLM 서술 수신 전략

**기본: 폴링** (정본: `design/server_api_system.md` §19.1)
```
초기: 500ms~1500ms 간격
백그라운드: 3~5초 간격
```

**확장: SSE** (정본: `design/server_api_system.md` §19.2)
- `/v1/runs/{runId}/events`에서 turnNo별 llm_status 업데이트 수신
- DONE/FAILED 수신 시 서술 영역 갱신

### 4. 복구 (Recovery)

`GET /v1/runs/{runId}` 한 번의 호출로 현재 화면 복원. (정본: `design/server_api_system.md` §5)

복구 시:
1. `lastResult.summary.short` 표시
2. `llm_output` 존재 시 표시
3. HUD는 `diff` 또는 `battleState` 기반 복원
4. **LLM 재호출 없음**

### 5. 페이지 구조 (권장)

```
app/
├── (landing)/          ← SSR: 랜딩, 인증
│   ├── page.tsx
│   └── login/
├── (game)/             ← Client SPA: 게임 본체
│   ├── layout.tsx      ← "use client", GameProvider
│   ├── play/
│   │   └── [runId]/
│   │       └── page.tsx  ← 메인 게임 화면
│   └── hub/
│       └── page.tsx      ← 허브 화면
└── api/                ← 필요 시 BFF (프록시)
```

---

## 금지 사항

### 절대 하지 않는 것

1. **수치 계산 금지** — HP 변화량, 데미지, 확률, 드랍을 클라이언트에서 계산하지 않는다
2. **diff 생성 금지** — diff는 서버가 생성. 클라이언트는 수신한 diff를 표시만 한다
3. **선택지 생성 금지** — choices[]는 서버가 제공. 클라이언트는 렌더링만 한다
4. **LLM 직접 호출 금지** — LLM API를 프론트에서 호출하지 않는다
5. **turnNo 자체 관리 금지** — 서버의 `expectedNextTurnNo`를 따른다

### serverResult vs llm_output 분리 원칙

```
serverResult (즉시 반영)          llm_output (비동기 덧씌움)
─────────────────────────         ──────────────────────────
HUD 숫자 변경                     서술 텍스트
상태이상 아이콘                    전투 묘사
선택지 버튼                       NPC 대사
전투 로그 (summary.short)         분위기 연출
```

**llm_output은 같은 turnNo의 narration만 덧씌운다. 수치 변경 금지.**

---

## 주의 사항

### 멱등성

- 모든 POST /turns 요청에 `idempotencyKey`를 포함한다 (UUID v4 권장)
- 네트워크 재시도 시 같은 key를 사용하여 중복 턴 생성 방지
- TanStack Query의 retry에서 같은 key가 유지되도록 mutation 설계

### 에러 처리

| HTTP | 의미 | UI 대응 |
|------|------|---------|
| 409 (TURN_NO_MISMATCH) | 턴 번호 불일치 | GET /runs 재조회 후 동기화 |
| 409 (TURN_CONFLICT) | 동시 요청 충돌 | 기존 결과 표시 |
| 422 (POLICY_DENY) | 행동 거부 | 거부 사유 표시, IDLE로 복귀 |
| 422 (INVALID_INPUT) | 입력 검증 실패 | 입력 필드 에러 표시 |
| 500 | 서버 오류 | ERROR 상태 → retry/cancel |

(정본: `design/server_api_system.md` §8)

### 노드 타입별 UI

| Node Type | 주요 UI 요소 |
|-----------|-------------|
| COMBAT | 전투 HUD (HP/스태미나/적 목록/거리/각도), 행동 선택, 보너스 슬롯 |
| EVENT | 서술 패널, 선택지 버튼 (choices[]) |
| REST | 휴식 옵션 (짧은/깊은), 회복 결과 |
| SHOP | 상품 목록 (catalog[]), 구매 버튼, 골드 표시 |
| EXIT | 귀환/계속 선택, RUN 정산 요약 |

(정본: `design/node_resolve_rules_v1.md` §5~8)

### 전투 HUD 특수 규칙

- `distance`/`angle`은 **enemies[] 각 항목에 표시** (per-enemy 정본)
- `playerState`에는 distance/angle이 없다
- `bonusSlot: true` 시 보너스 행동 UI 활성화
- DOWNED 상태 진입 시 전투 종료 → 구조 이벤트 연출

(정본: `design/combat_system.md`, `design/core_game_architecture_v1.md` §8)

---

## 참조 문서

| 문서 | 참조 내용 |
|------|----------|
| `design/core_game_architecture_v1.md` | UI State Machine §7, Downed §8, 에러 처리 §9 |
| `design/server_api_system.md` | API 전체, 폴링/SSE §19, 에러 코드 §8 |
| `design/node_resolve_rules_v1.md` | 노드별 UI 힌트 §10, 입력 형태 |
| `schema/OpenAPI 3.1.yaml` | 전체 API 스키마 |
| `schema/server_result_v1.json` | server_result JSON Schema |
| `samples/` | 모든 샘플 페이로드 |
