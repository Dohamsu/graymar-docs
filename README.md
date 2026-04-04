# Graymar — LLM 기반 정치 음모 텍스트 RPG

> 이름 없는 용병이 항만 도시 **그레이마르**의 권력 투쟁을 거쳐 성장하는 턴제 텍스트 RPG.
> 서버가 모든 게임 로직을 결정론적으로 처리하고, LLM은 내러티브 텍스트만 생성한다.

## Live Demo

- **플레이**: [www.dimtale.com](https://www.dimtale.com)
- **게임 진입**: [www.dimtale.com/play](https://www.dimtale.com/play)

## Tech Stack

| Layer | Tech | Version |
|-------|------|---------|
| Backend | NestJS | 11 |
| ORM | Drizzle ORM | 0.45 |
| DB | PostgreSQL | 16 |
| Validation | Zod | 4.3 |
| Frontend | Next.js | 16.1 |
| React | React | 19.2 |
| State | Zustand | 5.0 |
| Styling | Tailwind CSS | 4 |
| LLM | OpenAI / Claude / Gemini | Multi-provider |

## Project Structure

```
├── server/              ← NestJS 백엔드 (73 services, 13 tables)
├── client/              ← Next.js 16 프론트엔드 (40 components, 3 stores)
├── content/             ← 게임 콘텐츠 시드 데이터 (24 JSON, 42 NPC, 7 locations)
├── specs/               ← 상세 설계 스펙 (20 md)
├── architecture/        ← 통합 아키텍처 문서 (26 md)
├── guides/              ← 코드 구현 지침 (6 md)
├── schema/              ← DB 스키마, JSON Schema, OpenAPI
├── samples/             ← 샘플 페이로드 (JSON)
├── scripts/             ← 자동화 스크립트 (playtest, portrait gen)
├── playtest-reports/    ← 플레이테스트 리포트
└── agents/              ← 에이전트 역할 정의서
```

## Quick Start

### 1. 데이터베이스

```bash
cd server
docker compose up -d
```

### 2. 서버

```bash
cd server
pnpm install
cp .env.example .env          # 환경 변수 편집
npx drizzle-kit push          # DB 스키마 동기화
pnpm start:dev                # http://localhost:3000
```

### 3. 클라이언트

```bash
cd client
pnpm install
pnpm dev -- --port 3001       # http://localhost:3001
```

## Game Overview

### 핵심 루프

```
HUB (도시 거점) → 7 LOCATION 탐험 → COMBAT (턴제 전투) → HUB (순환)
```

### 캐릭터 프리셋 6종

| ID | 이름 | 컨셉 |
|----|------|------|
| DOCKWORKER | 부두 노동자 | 근접 탱커 |
| DESERTER | 탈영병 | 균형 전투 |
| SMUGGLER | 밀수업자 | 은밀 특화 |
| HERBALIST | 약초상 | 방어 유틸 |
| FALLEN_NOBLE | 몰락 귀족 | 정치 특화 |
| GLADIATOR | 검투사 | 공격 특화 |

### 특성 6종

| ID | 효과 |
|----|------|
| BATTLE_MEMORY | 전투 경험 보너스 |
| STREET_SENSE | 위험 감지 |
| SILVER_TONGUE | 설득/협상 보너스 |
| GAMBLER_LUCK | FAIL→50% PARTIAL, 크리티컬 비활성 |
| BLOOD_OATH | 저HP 보너스 +2/+3, 치료 50% 감소 |
| NIGHT_CHILD | 밤 +2, 낮 -1 |

### 캐릭터 생성

이름 입력 → 프리셋 선택 → 특성 선택 → 보너스 스탯 +6 배분 → AI 초상화 생성 (Gemini)

### 7개 탐험 장소

시장 거리, 경비대 지구, 항만 부두, 빈민가, 상류 거리, 잠긴 닻 선술집, 항만 창고구

### NPC 3계층 (42명)

- **CORE** (5명): 메인 스토리 핵심 NPC — 전용 초상화
- **SUB** (12명): 퀘스트/이벤트 연계 NPC — 전용 초상화
- **BACKGROUND** (25명): 배경/분위기 NPC

### 퀘스트 시스템

6단계 자동 전환 (S0→S5) + 3개 Arc 루트 (EXPOSE_CORRUPTION / PROFIT_FROM_CHAOS / ALLY_GUARD)

### 주요 시스템

| 시스템 | 설명 |
|--------|------|
| Action-First 파이프라인 | 플레이어 행동 → 이벤트 매칭 → 판정 (1d6+stat) |
| Event Director | 123개 이벤트 라이브러리 + 동적 이벤트 생성 |
| Living World | 장소 상태, NPC 스케줄, 상황 생성, 결과 처리 |
| Narrative Engine | 사건 생명주기, 4상 시간, 시그널 피드, NPC 감정 5축 |
| Structured Memory | 선별 주입 (NPC/장소/사건/아이템별) |
| Token Budget | 2500 토큰 예산 관리 |
| 전투 시스템 | 거리/각도 포지셔닝, 5종 상태이상, AI 성격별 행동 |
| 장비 시스템 | 세트 효과, 지역 접미사, Legendary |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/auth/register` | 회원가입 |
| POST | `/v1/auth/login` | 로그인 → JWT |
| POST | `/v1/runs` | 새 RUN 생성 |
| GET | `/v1/runs` | 활성 RUN 조회 |
| GET | `/v1/runs/:runId` | RUN 상태 조회 |
| POST | `/v1/runs/:runId/turns` | 턴 제출 |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 (LLM 폴링) |
| POST | `/v1/runs/:runId/turns/:turnNo/retry-llm` | LLM 재시도 |
| GET | `/v1/settings/llm` | LLM 설정 조회 |
| PATCH | `/v1/settings/llm` | LLM 설정 변경 |
| POST | `/v1/bug-reports` | 버그 리포트 생성 |
| GET | `/v1/bug-reports` | 버그 리포트 목록 |
| GET | `/v1/bug-reports/:id` | 버그 리포트 상세 |
| PATCH | `/v1/bug-reports/:id` | 버그 리포트 상태 변경 |
| POST | `/v1/portrait/generate` | AI 초상화 생성 |
| GET | `/v1/version` | 서버 버전 조회 |

## Design Invariants

1. **Server is Source of Truth** — 모든 수치 계산, 확률, 상태 변경은 서버에서만
2. **LLM is narrative-only** — LLM 출력은 게임 결과에 영향 없음
3. **Idempotency** — `(run_id, turn_no)` + `(run_id, idempotency_key)` unique
4. **RNG determinism** — `seed + cursor` 저장, 재현 가능
5. **Theme memory (L0) 불변** — 토큰 예산 압박에도 삭제 금지
6. **Action slot cap = 3** — Base 2 + Bonus 1
7. **HUB Heat +-8 clamp** — 한 턴에 Heat 변동 제한
8. **Token Budget 2500** — 블록별 예산 배분
9. **Procedural Plot Protection** — 동적 이벤트에 arcRouteTag/commitmentDelta 불포함
10. **NATURAL 엔딩 최소 15턴** — ALL_RESOLVED 엔딩은 totalTurns >= 15

## Documentation

| 폴더 | 내용 |
|------|------|
| `specs/` | 전투, 노드, LLM, API 등 상세 스펙 20편 |
| `architecture/` | 통합 아키텍처 문서 26편 |
| `guides/` | 서버 모듈맵, 클라이언트 컴포넌트맵, HUB 엔진 가이드 등 6편 |

## License

MIT
