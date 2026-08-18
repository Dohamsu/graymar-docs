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
| LLM | Gemma 4 31B dense (메인) + gpt-5.6-luna (5:5 교차) / GPT-4.1 Mini (fallback) / gpt-4.1-nano (경량) | OpenRouter Multi-provider |

## Project Structure

```
├── server/              ← NestJS 백엔드 (16 modules, 117 services, 27 tables)
├── client/              ← Next.js 16 프론트엔드 (71 components, 7 stores)
├── admin/               ← 어드민 콘솔 (독립 레포 graymar-admin, Vercel 별도 배포)
├── content/             ← 게임 콘텐츠 시드 데이터 (3팩: graymar_v1 / star_sand_v1 / karnholt_v1)
├── specs/               ← 상세 설계 스펙 (17 md)
├── architecture/        ← 통합 아키텍처 문서 (91 md + INDEX)
├── guides/              ← 코드 구현 지침 (14 md)
├── schema/              ← DB 스키마, JSON Schema, OpenAPI
├── samples/             ← 샘플 페이로드 (JSON)
├── scripts/             ← 자동화 스크립트 (playtest, e2e, audit_quality)
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

### 시나리오 팩 4종

| 팩 | 성격 |
|----|------|
| graymar_v1 | 정본 시나리오 — 항만 도시 그레이마르 정치 음모 |
| star_sand_v1 | 별빛모래 — 사막 여관 무대 |
| karnholt_v1 | AUTONOMOUS — 진상 선확정 디렉터 모드 자율 서사 팩 |

아래 프리셋·장소·NPC 수치는 정본 팩 graymar_v1 기준이다 (팩별 상이).

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

2단계 (배경 선택 → 마무리) — 스탯 +6은 프리셋에 내장, 특성은 `preset.defaultTraitId` 자동 부여 (arch/97). AI 초상화 생성/업로드 선택 가능.

### 7개 탐험 장소

시장 거리, 경비대 지구, 항만 부두, 빈민가, 상류 거리, 잠긴 닻 선술집, 항만 창고구

### NPC 3계층 (43명)

- **CORE** (6명): 메인 스토리 핵심 NPC — 전용 초상화
- **SUB** (12명): 퀘스트/이벤트 연계 NPC — 전용 초상화
- **BACKGROUND** (25명): 배경/분위기 NPC

NPC별 다중 어체: HAOCHE(19) / HAPSYO(9) / HAEYO(7) / HAECHE(6) / BANMAL(2)

### 퀘스트 시스템

6단계 자동 전환 (S0→S5) + 3개 Arc 루트 (EXPOSE_CORRUPTION / PROFIT_FROM_CHAOS / ALLY_GUARD)

### LLM 파이프라인

```
NanoDirector → Stage A(서술 LLM) → dialogue_slot → Stage B(대사 LLM) → 서버 조립
                                     ↓
                              로어북 키워드 매칭 → 관련 세계 지식 주입
                                     ↓
                              Memory v4: entity_facts UPSERT → nano 요약 주입
```

### 주요 시스템

| 시스템 | 설명 |
|--------|------|
| Player-First 이벤트 엔진 | TurnMode 3분류 (PLAYER_DIRECTED/CONVERSATION_CONT/WORLD_EVENT) + NPC 5단계 우선순위 |
| Action-First 파이프라인 | 플레이어 행동 → 이벤트 매칭 → 판정 (1d6+stat) |
| Event Director | 123개 이벤트 라이브러리 + NanoEventDirector 동적 생성 |
| Living World v2 | 장소 상태, NPC 스케줄·아젠다, 상황 생성, 결과 처리 |
| Narrative Engine v1 | 사건 생명주기, 4상 시간, 시그널 피드, NPC 감정 5축 |
| Memory v4 | entity_facts UPSERT + nano 요약 주입 (반복률 71% ↓) |
| Token Budget | 2500 토큰 예산, 블록별 배분 + 저우선 트리밍 |
| 전투 시스템 | 거리/각도 포지셔닝, 5종 상태이상, AI 성격별 행동 |
| 장비 시스템 | 세트 효과, 지역 접미사, Legendary, 획득 토스트·교체 모달 |
| LLM 스트리밍 | OpenRouter stream:true + SSE + 2-Phase 렌더링 |
| 엔딩 연출 | Part B MIN_TURNS 가드 + arcRoute 12분기 에필로그 + personalClosing + DeadlineBanner |
| 여정 아카이브 | ending_summary 캐시 + EndingsListScreen + JourneySummaryScreen 양피지 스타일 |
| 포인트 시스템 | 채팅 1턴 = 5p 종량제 (충전 코드 → 차감, 실패 턴 환불, 가입 보너스 50p) — arch/85 |
| 파티 던전 | 파티 CRUD + SSE 실시간 채팅 + 동시 턴 제출·통합 판정 + 투표·보상 분배 — arch/24·84 |
| 장면 컷 시스템 | 사전 제작 태그 이미지를 서술 태그 매칭(nano confidence)으로 인라인 삽입 — arch/96 |
| 어드민 콘솔 | 관제 API 15종 + AdminGuard 하이브리드 인증 + 감사 로그, 별도 레포/배포 — arch/87 |
| 자율 서사 팩 | Plot Seed 선확정 + 비트 선계산·의도 정합 채택 디렉터 (karnholt_v1 AUTONOMOUS) — arch/75 |

## API Endpoints (주요 — 전체 82 routes)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/auth/register` | 회원가입 (가입 보너스 포인트) |
| POST | `/v1/auth/login` | 로그인 → JWT |
| GET | `/v1/scenarios` | 시나리오(팩) 목록 + creation-bundle |
| POST | `/v1/runs` | 새 RUN 생성 (presetId, gender, scenarioId) |
| GET | `/v1/runs` | 활성 RUN 조회 |
| GET | `/v1/runs/:runId` | RUN 상태 조회 |
| POST | `/v1/runs/:runId/turns` | 턴 제출 |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 (LLM 폴링) |
| GET | `/v1/runs/:runId/turns/:turnNo/stream` | SSE 서술 스트리밍 |
| POST | `/v1/runs/:runId/turns/:turnNo/retry-llm` | LLM 재시도 (무료) |
| GET | `/v1/settings/llm` | LLM 설정 조회 |
| PATCH | `/v1/settings/llm` | LLM 설정 변경 (admin) |
| POST | `/v1/runs/:runId/bug-report` | 버그 리포트 생성 (인게임) |
| GET | `/v1/bug-reports` | 버그 리포트 목록 (admin) |
| POST | `/v1/portrait/generate` | AI 초상화 생성 |
| GET | `/v1/version` | 서버 버전 조회 |
| GET | `/v1/stats/public` | 공개 통계 (무인증) |
| GET | `/v1/endings` | 완료된 엔딩 요약 목록 (여정 아카이브) |
| GET | `/v1/endings/:runId` | 특정 엔딩 상세 (JourneySummary) |
| POST | `/v1/runs/:runId/equip` | 장비 장착 (슬롯 자동 배치) |
| POST | `/v1/runs/:runId/unequip` | 장비 해제 |
| POST | `/v1/runs/:runId/use-item` | 소모품 사용 (HEAL_HP / RESTORE_STAMINA) |
| GET | `/v1/points/balance` | 포인트 잔액 · `/redeem` 충전 코드 사용 |
| POST | `/v1/parties` | 파티 생성 (+ 채팅/로비/투표/파티 턴 21 routes) |
| GET | `/v1/admin/stats/overview` | 어드민 관제 (users/runs/llm/health 15 routes) |

## Design Invariants

1. **Server is Source of Truth** — 모든 수치 계산, 확률, 상태 변경은 서버에서만
2. **LLM is narrative-only** — LLM 출력은 게임 결과에 영향 없음
3. **Idempotency** — `(run_id, turn_no)` + `(run_id, idempotency_key)` unique
4. **RNG determinism** — `seed + cursor` 저장, 재현 가능
5. **Theme memory (L0) 불변** — 토큰 예산 압박에도 삭제 금지
6. **Action slot cap = 3** — Base 2 + Bonus 1
7. **HUB Heat +-8 clamp** — 한 턴에 Heat 변동 제한
8. **Token Budget 2단** — 메모리 블록 2500 tok + 프롬프트 총량 백스톱 16,500자
9. **Procedural Plot Protection** — 동적 이벤트에 arcRouteTag/commitmentDelta 불포함
10. **NATURAL 엔딩 최소 15턴** — ALL_RESOLVED 엔딩은 totalTurns >= 15

## Documentation

| 폴더 | 내용 |
|------|------|
| `specs/` | 전투, 노드, LLM, API 등 상세 스펙 17편 |
| `architecture/` | 통합 아키텍처 문서 91편 + `INDEX.md` 도메인 색인 (archive 4편) |
| `guides/` | 서버 모듈맵, 클라이언트 컴포넌트맵, HUB 엔진 가이드, 팩 에셋·장면 컷 프롬프트 등 14편 |
| `CLAUDE.md` | 프로젝트 작업 가이드라인 + LLM 설계 원칙 + 40+ Invariant |
| `portfolio.md` | 프로젝트 포트폴리오 (기술 하이라이트·아키텍처·회고) |

## License

MIT
