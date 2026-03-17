# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

LLM-powered turn-based text RPG — **정치 음모 RPG**에서 이름 없는 용병이 왕국의 권력 투쟁을 거쳐 성장한다. 서버가 모든 게임 로직을 결정론적으로 처리하고, LLM은 내러티브 텍스트만 생성한다.

## Project Structure

```
├── server/              ← NestJS + Drizzle ORM + PostgreSQL 백엔드
├── client/              ← Next.js 16 + Zustand + Tailwind v4 프론트엔드
├── specs/               ← 원본 상세 설계 스펙 (20 md, 정본 참조)
├── architecture/        ← 통합 아키텍처 문서 (21 md, 실무 참조)
├── guides/              ← 코드 구현 지침 (5 md, 서비스맵/컴포넌트맵/구현가이드)
├── schema/              ← DB 스키마, JSON Schema, OpenAPI (3 files)
├── samples/             ← 샘플 페이로드 (JSON, 10 files)
├── content/             ← 게임 콘텐츠 시드 데이터 (graymar_v1, 22 files)
├── agents/              ← 에이전트 역할 정의서 (4 md)
├── playtest-reports/    ← 플레이테스트 분석 리포트
└── CLAUDE.md
```

## Development Commands

### Server (NestJS, port 3000)
```bash
cd server
pnpm install
pnpm start:dev          # nest start --watch
pnpm test               # jest (unit tests)
pnpm test:cov           # jest --coverage
pnpm build              # nest build
pnpm lint               # eslint --fix
```

### Client (Next.js 16, port 3001)
```bash
cd client
pnpm install
pnpm dev -- --port 3001  # next dev
pnpm build               # next build
pnpm lint                # eslint
```

### Database (PostgreSQL via Docker)
```bash
cd server
docker compose up -d                           # DB 컨테이너 시작
npx drizzle-kit push                           # 스키마 push
npx drizzle-kit generate                       # 마이그레이션 생성
DATABASE_URL=postgresql://user:password@localhost:5432/textRpg
```

### Run a single test
```bash
cd server && pnpm jest -- --testPathPattern=rng.service
```

## Architecture (요약)

> 상세 서비스 맵: `guides/01_server_module_map.md`
> 상세 컴포넌트 맵: `guides/02_client_component_map.md`

### Server — 9 modules, 60+ services, 5 controllers

| 모듈 | 서비스 수 | 역할 |
|------|----------|------|
| common/ | - | Guards, Filters, Pipes, Decorators |
| auth/ | 1 | JWT 인증 (register/login) |
| db/ | - | Drizzle ORM (10 tables, 35 타입 파일) |
| content/ | 1 | 게임 콘텐츠 로더 (graymar_v1 JSON 22개) |
| engine/rng,stats,status | 3 | RNG, 스탯 계산, 상태효과 |
| engine/combat | 4 | Hit, Damage, EnemyAI, CombatService |
| engine/input | 3 | RuleParser → Policy → ActionPlan |
| engine/nodes | 7 | 노드별 리졸버 + 전이 |
| engine/rewards | 4 | 보상, 인벤토리, 장비, 접미사 |
| engine/hub | 29 | HUB 엔진 5 서브시스템 (아래 참조) |
| runs/ | 1 | RUN 생성/조회 |
| turns/ | 1 | 턴 제출/조회 |
| llm/ | 8 | LLM Worker, Context Builder, Token Budget, Prompt |

### HUB 엔진 5 서브시스템 (29 services)

| 서브시스템 | 수 | 핵심 서비스 |
|-----------|---|------------|
| Base HUB | 9 | WorldState, Heat, EventMatcher, Resolve, IntentParserV2 |
| Narrative Engine v1 | 8 | Incident, WorldTick, Signal, NpcEmotional, Mark, Ending |
| Structured Memory v2 | 2 | MemoryCollector, MemoryIntegration |
| User-Driven Bridge | 6 | IntentV3Builder, IncidentRouter, WorldDelta, PlayerThread, Notification |
| Narrative v2 & Event v2 | 4 | IntentMemory, EventDirector, ProceduralEvent |

> 상세: `guides/03_hub_engine_guide.md`

### Client — 31 components, 3 stores

| 영역 | 수 | 핵심 |
|------|---|------|
| narrative/ | 2 | NarrativePanel, StoryBlock |
| input/ | 2 | InputSection, QuickActionButton |
| hub/ | 11 | HubScreen, SignalFeed, Incident, NPC, Notifications |
| location/ | 2 | TurnResultBanner, LocationToastLayer |
| screens/ | 4 | StartScreen, EndingScreen |
| side-panel/ | 3 | SidePanel, CharacterTab, InventoryTab |
| ui/ | 4 | ErrorBanner, LlmFailureModal |
| layout/ | 2 | Header, MobileBottomNav |
| battle/ | 1 | BattlePanel |

### Key Data Flow

```
HUB: CHOICE → moveToLocation → LOCATION 노드 생성 → Scene Shell
LOCATION: ACTION/CHOICE → IntentParserV2 → EventDirector → ResolveService(1d6+stat)
  → ServerResultV1 (DB commit) → [async] LLM Worker → narrative text
COMBAT: ACTION/CHOICE → RuleParser → Policy → NodeResolver → ServerResultV1
```

## Tech Stack

| Layer | Tech | Version |
|-------|------|---------|
| Backend | NestJS | 11.0 |
| ORM | Drizzle ORM | 0.45 |
| DB | PostgreSQL | 16 |
| Validation | Zod | 4.3 |
| Frontend | Next.js | 16.1 |
| React | React | 19.2 |
| State | Zustand | 5.0 |
| Styling | Tailwind CSS | 4 |
| LLM | OpenAI / Claude / Gemini | Multi-provider |

## Critical Design Invariants

1. **Server is Source of Truth** — 모든 수치 계산, 확률 롤, 상태 변경은 서버에서만.
2. **LLM is narrative-only** — LLM 출력은 게임 결과에 영향 없음. 실패해도 게임 진행.
3. **Idempotency** — `(run_id, turn_no)` + `(run_id, idempotency_key)` unique.
4. **RNG determinism** — `seed + cursor` 저장. COMBAT: hitRoll → varianceRoll → critRoll. LOCATION: EventMatcher(가중치) → ResolveService(1d6).
5. **Theme memory (L0) 불변** — 토큰 예산 압박에도 삭제 금지.
6. **Action slot cap = 3** — Base 2 + Bonus 1. 초과 불가.
7. **diff → client only** — LLM에는 events/summary만 전달, 수치 diff는 클라이언트 HUD용.
8. **distance/angle per-enemy** — BattleState.enemies에만 존재, playerState에 없음.
9. **HUB Heat ±8 clamp** — 한 턴에 Heat 변동은 ±8 제한. 0~100 범위.
10. **Action-First 파이프라인** — LOCATION에서 플레이어 ACTION이 먼저, 이벤트 매칭이 후.
11. **고집(Insistence) 에스컬레이션** — suppressedActionType 3회 연속 → 강한 actionType 승격.
12. **LOCATION 판정 = 1d6 + floor(stat/3) + baseMod** — SUCCESS ≥ 6, PARTIAL 3~5, FAIL < 3.
13. **이벤트 고유 선택지 우선** — payload.choices > suggested_choices > LOCATION 기본.
14. **LOCATION 단기기억** — locationSessionTurns(최대 6턴+MidSummary) LLM 전달. 떠날 때 요약 저장.
15. **NPC 이름 비공개→공개** — FRIENDLY 1회 / CAUTIOUS 2회 / HOSTILE 3회 소개.
16. **장면 연속성 보장** — sceneFrame 3단계 억제 + 7개 연속성 규칙.
17. **Token Budget 2500** — 블록별 예산 배분, 저우선 블록 트리밍.
18. **Procedural Plot Protection** — 동적 이벤트에서 arcRouteTag/commitmentDelta 절대 금지.

## Canonical Enums (정본)

모든 서버 enum의 정본 위치: `server/src/db/types/enums.ts`

| Enum | 정본 위치 | 값 |
|------|-----------|-----|
| Node Type | `enums.ts` | COMBAT, EVENT, REST, SHOP, EXIT, HUB, LOCATION |
| Node State | `enums.ts` | NODE_ACTIVE, NODE_ENDED |
| Run Status | `enums.ts` | RUN_ACTIVE, RUN_ENDED, RUN_ABORTED |
| Input Type | `enums.ts` | ACTION, CHOICE, SYSTEM |
| LLM Status | `enums.ts` | SKIPPED, PENDING, RUNNING, DONE, FAILED |
| Event Kind | `enums.ts` | BATTLE, DAMAGE, STATUS, LOOT, GOLD, QUEST, NPC, MOVE, SYSTEM, UI |
| Policy Result | `enums.ts` | ALLOW, TRANSFORM, PARTIAL, DENY |
| ActionType (Combat) | `enums.ts` | ATTACK_MELEE, ATTACK_RANGED, DEFEND, EVADE, MOVE, USE_ITEM, FLEE, INTERACT |
| ActionType (Non-Combat) | `enums.ts` | TALK, SEARCH, OBSERVE |
| CombatOutcome | `enums.ts` | ONGOING, VICTORY, DEFEAT, FLEE_SUCCESS |
| NodeOutcome | `enums.ts` | ONGOING, NODE_ENDED, RUN_ENDED |
| Distance | `enums.ts` | ENGAGED, CLOSE, MID, FAR, OUT |
| Angle | `enums.ts` | FRONT, SIDE, BACK |
| AI Personality | `enums.ts` | AGGRESSIVE, TACTICAL, COWARDLY, BERSERK, SNIPER |
| IntentActionType | `enums.ts` | INVESTIGATE, PERSUADE, SNEAK, BRIBE, THREATEN, HELP, STEAL, FIGHT, OBSERVE, TRADE, TALK, SEARCH, MOVE_LOCATION, REST, SHOP |
| HubSafety | `enums.ts` | SAFE, ALERT, DANGER |
| TimePhase | `enums.ts` | DAY, NIGHT |
| TimePhaseV2 | `world-state.ts` | DAWN, DAY, DUSK, NIGHT |
| MatchPolicy | `enums.ts` | SUPPORT, BLOCK, NEUTRAL |
| Affordance | `enums.ts` | INVESTIGATE, PERSUADE, SNEAK, BRIBE, THREATEN, HELP, STEAL, FIGHT, OBSERVE, TRADE, ANY |
| EventTypeV2 | `enums.ts` | RUMOR, FACTION, ARC_HINT, SHOP, CHECKPOINT, AMBUSH, ENCOUNTER, OPPORTUNITY, FALLBACK |
| ArcRoute | `enums.ts` | EXPOSE_CORRUPTION, PROFIT_FROM_CHAOS, ALLY_GUARD |
| NpcPosture | `enums.ts` | FRIENDLY, CAUTIOUS, HOSTILE, FEARFUL, CALCULATING |
| IncidentKind | `incident.ts` | SMUGGLING, CORRUPTION, THEFT, STRIKE, ASSASSINATION |
| IncidentOutcome | `incident.ts` | CONTAINED, ESCALATED, EXPIRED |
| SignalChannel | `signal-feed.ts` | RUMOR, SECURITY, NPC_BEHAVIOR, ECONOMY, VISUAL |
| NarrativeMarkType | `narrative-mark.ts` | BETRAYER, SAVIOR, KINGMAKER, SHADOW_HAND, MARTYR, PROFITEER, PEACEMAKER, WITNESS, ACCOMPLICE, AVENGER, COWARD, MERCIFUL |
| StepStatus | `operation-session.ts` | PENDING, IN_PROGRESS, COMPLETED, SKIPPED |
| Status ID | `specs/status_effect_system_v1.md` §10 | BLEED, POISON, STUN, WEAKEN, FORTIFY |
| ResolveOutcome | `resolve-result.ts` | SUCCESS, PARTIAL, FAIL |
| Client Phase | `game-store.ts` | TITLE, LOADING, HUB, LOCATION, COMBAT, NODE_TRANSITION, RUN_ENDED, ERROR |
| StoryMessageType | `game.ts` | SYSTEM, NARRATOR, PLAYER, CHOICE, RESOLVE |
| CharacterPreset | `presets.json` | DOCKWORKER, DESERTER, SMUGGLER, HERBALIST |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/auth/register` | 회원가입 (email, password, nickname) |
| POST | `/v1/auth/login` | 로그인 (email, password) → JWT |
| POST | `/v1/runs` | 새 RUN 생성 (presetId, gender) |
| GET | `/v1/runs` | 활성 RUN 조회 (userId 기반) |
| GET | `/v1/runs/:runId` | RUN 상태 조회 (turnsLimit 옵션) |
| POST | `/v1/runs/:runId/turns` | 턴 제출 (ACTION/CHOICE, idempotencyKey 필수) |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 (LLM 폴링용, includeDebug 옵션) |
| POST | `/v1/runs/:runId/turns/:turnNo/retry-llm` | LLM 재시도 (FAILED → PENDING 리셋) |
| GET | `/v1/settings/llm` | LLM 설정 조회 (API 키 마스킹) |
| PATCH | `/v1/settings/llm` | LLM 설정 변경 (런타임) |

## Environment Variables (`server/.env`)

```
DATABASE_URL=postgresql://user:password@localhost:5432/textRpg
LLM_PROVIDER=openai          # openai | claude | gemini | mock
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
CLAUDE_API_KEY=               # optional
GEMINI_API_KEY=               # optional
LLM_MAX_RETRIES=2
LLM_TIMEOUT_MS=8000
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.8
LLM_FALLBACK_PROVIDER=mock
```

## Implementation Phase Status (구현 단계)

| Phase | 범위 | 상태 |
|-------|------|------|
| **Phase 1** | HUB 순환 탐험 + LOCATION 판정 + 전투 + LLM 내러티브 + 프리셋/인증 | ✅ 완료 |
| **Phase 2** | NPC 소개 + 5축 감정 | ✅ 완료 |
| **Phase 2** | DAG 노드 라우팅 | ❌ 미구현 |
| **Phase 3** | Turn Orchestration (NPC 주입, pressure) | ✅ 완료 |
| **Narrative v1** | Incident + 4상시간 + Signal + NpcEmotional + Mark + Ending + Operation | ✅ 완료 |
| **Memory v2** | StructuredMemory + [MEMORY]/[THREAD] 태그 + Scene Continuity | ✅ 완료 |
| **Narrative v2** | Token Budget + Mid Summary + Intent Memory + Active Clues | ✅ 완료 |
| **Event v2** | Event Director + Event Library(88개) + Procedural Event | ✅ 완료 |
| **Bridge** | IntentV3 + IncidentRouter + WorldDelta + PlayerThread + Notification | ✅ 완료 |
| **Client** | Notification UI + 엔딩 행동 성향 | ✅ 완료 |
| **Phase 4** | 장비 v2 (세트/리전) + 리전 경제 | ⚠️ 부분/미구현 |

## Document Status (설계 문서 현황)

### specs/ — 상세 스펙 (20 md)

| 파일 | 상태 | 비고 |
|------|------|------|
| combat_system.md | ✅ 정본 | 전투 공식 (floor 적용) |
| combat_engine_resolve_v1.md | ✅ 정본 | 구현 연동 |
| battlestate_storage_recovery_v1.md | ✅ 정본 | 저장 구조 |
| node_resolve_rules_v1.md | ✅ 정본 | 노드 처리 |
| llm_context_system_v1.md | ✅ 정본 | L0~L4 컨텍스트 |
| server_api_system.md | ✅ 정본 | API 계약 |
| status_effect_system_v1.md | ✅ 정본 | 상태이상 |
| core_game_architecture_v1.md | ✅ 정본 | 역할 분리 |
| political_narrative_system_v1.md | ✅ 참고 | 정치/관계 |
| protagonist_world_v1.md | ✅ 참고 | 세계 서사 |
| rewards_and_progression_v1.md | ✅ 참고 | 보상/성장 |
| run_node_system.md | ✅ 참고 | 런/노드 구조 |
| run_planner_v1_1.md | ✅ 참고 | 런 플래너 |
| vertical_slice_v1.md | ✅ 참고 | 버티컬 슬라이스 |
| character_growth_v1.md | 📎 향후 | 캐릭터 성장 |
| magic_system_consolidated_v1.md | 📎 향후 | 마법 시스템 |
| input_processing_pipeline_v1.md | ⚠️ 부분 | 전투 입력만 구현 |
| combat_resolve_engine_v1.md | ❌ 폐기 | floor 미적용 오류 → combat_system.md |
| node_routing_v2.md | ❌ 미구현 | DAG 분기 (Phase 2) |
| llm_context_memory_v1_1.md | 📎 참고 | v1.md 확장판 |

### architecture/ — 통합 아키텍처 (21 md)

| 파일 | 상태 | 비고 |
|------|------|------|
| 01_world_narrative.md | ✅ 정본 | 세계관/정치 |
| 02_combat_system.md | ✅ 정본 | 전투 통합 |
| 03_hub_engine.md | ✅ 구현됨 | HUB Action-First |
| 04_server_architecture.md | ✅ 정본 | 서버 아키텍처 |
| 05_llm_narrative.md | ✅ 정본 | LLM 파이프라인 |
| 06_graymar_content.md | ✅ 구현됨 | 콘텐츠 데이터 |
| 07_game_progression.md | ⚠️ 업데이트 필요 | HUB 모드 |
| 08_node_routing.md | ❌ 미구현 | Phase 2 |
| 09_npc_politics.md | ⚠️ 부분 | 감정/소개 ✅, Leverage ❌ |
| 10_region_economy.md | ❌ 미구현 | Phase 4 |
| 11_llm_prompt_caching.md | 📎 설계 | 최적화 전략 |
| 12_equipment_system.md | ⚠️ 부분 | Phase 4 |
| 14_user_driven_code_bridge.md | ✅ 구현됨 | IntentV3→Incident→Router→Ending |
| 15_notification_system_design.md | ✅ 구현됨 | Notification 아키텍처 |
| 16_notification_ui_build_plan.md | ✅ 구현됨 | UI 빌드 체크리스트 |
| 17_notification_client_bridge.md | ✅ 구현됨 | 클라이언트 Notification |
| 18_narrative_runtime_patch.md | ✅ 구현됨 | Token Budget + Mid Summary |
| 19_event_orchestration.md | ✅ 구현됨 | Event Director + Library |
| 20_procedural_event_extension.md | ✅ 구현됨 | 동적 이벤트 생성 |
| Narrative_Engine_v1_Integrated_Spec.md | ✅ 정본 | Narrative Engine v1 통합 |
| ai_implementation_guidelines.md | ✅ 적용됨 | 구현 원칙/금지사항 |

### guides/ — 코드 구현 지침 (5 md)

| 파일 | 내용 |
|------|------|
| 01_server_module_map.md | 서버 전체 서비스 맵 (60+ services, 35 타입 파일) |
| 02_client_component_map.md | 클라이언트 컴포넌트 맵 (31 components, stores, CSS) |
| 03_hub_engine_guide.md | HUB 엔진 구현 (판정, EventDirector, Narrative, NPC, 평판) |
| 04_llm_memory_guide.md | LLM 파이프라인, 메모리 L0~L4, Token Budget, Scene Continuity |
| 05_runstate_constants.md | RunState JSONB 구조, 핵심 상수, Content Data |

## Working Language

설계 문서와 게임 콘텐츠는 한국어. 기술 식별자(enum, field name, schema key)는 영어.
