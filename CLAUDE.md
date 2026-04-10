# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Slack 작업 알림 (필수)

모든 유의미한 작업(코드 구현, 버그 수정, 분석, 플레이테스트 등) 완료 시 Slack 웹훅으로 알림을 보낸다.
간단한 질문 응답이나 파일 읽기만 하는 경우는 제외.

### 완료 알림
```bash
curl -s -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"✅ [작업 요약 메시지]\"}" \
  "$(grep SLACK_WEBHOOK_URL /Users/dohamsu/Workspace/graymar/.env | cut -d= -f2)"
```

### 중간 진행 알림 (10분 이상 소요 작업)
10분 이상 소요가 예상되는 작업 시, 약 10분 간격으로 중간 보고를 보낸다.
```bash
curl -s -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"🔄 [진행 상황 메시지]\"}" \
  "$(grep SLACK_WEBHOOK_URL /Users/dohamsu/Workspace/graymar/.env | cut -d= -f2)"
```

- 웹훅 URL: 프로젝트 루트 `.env` 파일의 `SLACK_WEBHOOK_URL`
- 완료 시 `✅`, 중간 보고 시 `🔄` 이모지 사용
- 중간 보고 예시: `🔄 플레이테스트 진행 중 — 3/10 런 완료, 현재 이슈 없음`

## 서버 프로세스 관리 (필수)

`pnpm start:dev &` 등 백그라운드로 서버를 시작하면, Claude Code 세션 종료 후에도 프로세스가 좀비로 남는다.
**서버를 시작하기 전에 반드시 기존 좀비 프로세스를 정리하라.**

### 서버 시작 전 정리 절차
```bash
# 1) 기존 graymar NestJS/pnpm 좀비 전체 정리
pkill -f 'graymar/server.*nest.js start --watch' 2>/dev/null
pkill -f 'graymar/server.*pnpm start:dev' 2>/dev/null
sleep 1
# 2) 포트 점유 프로세스 최종 확인
lsof -ti:3000 | xargs kill -9 2>/dev/null
```

### 규칙
- **서버 시작 전**: 위 정리 절차를 반드시 먼저 실행한다. `pnpm start:dev &`를 바로 실행하지 않는다.
- **클라이언트도 동일**: Next.js 시작 전에 `lsof -ti:3001 | xargs kill -9 2>/dev/null`로 기존 프로세스 정리.
- **다른 프로젝트 주의**: `mdfile` 등 다른 워크스페이스의 좀비도 남아있을 수 있으므로, 포트 충돌 발생 시 `ps aux | grep 'nest.js start'`로 전체 확인.

## 워크플로우 규칙

- **디버깅**: 버그 수정 시, 표면적 수정 전에 반드시 근본 원인을 조사하라. 사용자가 파악한 원인이 초기 분석과 다르면 확인 질문을 하라.
- **계획 요청**: 사용자가 계획을 요청하면 계획 문서를 직접 작성하라. 명시적으로 요청하지 않는 한 깊은 중첩 에이전트 탐색을 피하라.
- **빌드 검증**: 코드 변경 후 반드시 `pnpm build`(server/client 각각)를 실행하여 빌드 성공을 확인하라.
- **설정 영속화**: 설정은 항상 CLAUDE.md 또는 설정 파일에 영속화하라. 세션 간 상태는 커밋된 파일에 저장해야 한다.
- **설계 문서 검토**: 설계 문서를 동기화하거나 검토할 때, 분석이나 계획을 작성하기 전에 반드시 관련 폴더(`specs/`, `architecture/`, `guides/`)의 모든 파일을 확인하라.

## 플레이테스트

- **정본 스크립트**: `scripts/playtest.py` — 이 파일만 사용. 새 스크립트를 생성하지 않는다.
- **커맨드**: `/playtest` (`.claude/commands/playtest.md`)
- **API 필드 확인**: 플레이테스트 스크립트 수정 시, 파싱 로직 작성 전에 API 응답 필드명을 정확히 확인하라 (예: `id` vs `choiceId`). 실제 API 응답 구조를 샘플 호출로 먼저 확인하라.

## Repository Overview

LLM-powered turn-based text RPG — **정치 음모 RPG**에서 이름 없는 용병이 왕국의 권력 투쟁을 거쳐 성장한다. 서버가 모든 게임 로직을 결정론적으로 처리하고, LLM은 내러티브 텍스트만 생성한다.

## Project Structure

```
├── server/              ← NestJS + Drizzle ORM + PostgreSQL 백엔드
├── client/              ← Next.js 16 + Zustand + Tailwind v4 프론트엔드
├── specs/               ← 원본 상세 설계 스펙 (20 md, 정본 참조)
├── architecture/        ← 통합 아키텍처 문서 (30 md, 실무 참조)
├── guides/              ← 코드 구현 지침 (6 md, 서비스맵/컴포넌트맵/구현가이드)
├── schema/              ← DB 스키마, JSON Schema, OpenAPI (3 files)
├── samples/             ← 샘플 페이로드 (JSON, 10 files)
├── content/             ← 게임 콘텐츠 시드 데이터 (graymar_v1, 43 NPC, 7 locations, 13 incidents)
├── agents/              ← 에이전트 역할 정의서 (4 md)
├── scripts/             ← 플레이테스트 등 자동화 스크립트 (playtest.py)
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

### Server — 10 modules, 65+ services, 6 controllers

| 모듈 | 서비스 수 | 역할 |
|------|----------|------|
| common/ | - | Guards, Filters, Pipes, Decorators |
| auth/ | 1 | JWT 인증 (register/login) |
| db/ | - | Drizzle ORM (18 tables, 35 타입 파일) |
| content/ | 1 | 게임 콘텐츠 로더 (graymar_v1 JSON 24개, traits.json 포함) |
| engine/rng,stats,status | 3 | RNG, 스탯 계산, 상태효과 |
| engine/combat | 4 | Hit, Damage, EnemyAI, CombatService |
| engine/input | 3 | RuleParser → Policy → ActionPlan |
| engine/nodes | 7 | 노드별 리졸버 + 전이 |
| engine/rewards | 5 | 보상, 인벤토리, 장비, 접미사, Legendary |
| engine/hub | 37 | HUB 엔진 6 서브시스템 + 퀘스트 (아래 참조) |
| engine/planner | 1 | RUN 구조 생성 (RunPlannerService) |
| runs/ | 1 | RUN 생성/조회 |
| turns/ | 1 | 턴 제출/조회 |
| llm/ | 11 | LLM Worker, Context Builder, Token Budget, Prompt, NpcDialogueMarker, NanoDirector, NanoEventDirector |
| scene-image/ | 1 | AI 초상화/이미지 생성 (Gemini, rate limit) |
| bug-report/ | 1 | 인게임 버그 리포트 (BugReportService + BugReportController) |
| party/ | 7 | 파티 시스템 (Party, Chat, Stream, Lobby, PartyTurn, Vote, Reward) |

### HUB 엔진 6 서브시스템 (37 services)

| 서브시스템 | 수 | 핵심 서비스 |
|-----------|---|------------|
| Base HUB | 10 | WorldState, Heat, EventMatcher, Resolve, IntentParserV2, QuestProgression, SceneShell, Agenda, Arc, TurnOrchestration |
| Narrative Engine v1 | 8 | Incident, WorldTick, Signal, NpcEmotional, Mark, Ending, Operation, Shop |
| Structured Memory v2 | 2 | MemoryCollector, MemoryIntegration |
| User-Driven Bridge | 6 | IntentV3Builder, IncidentRouter, WorldDelta, PlayerThread, Notification |
| Narrative v2 & Event v2 | 4 | IntentMemory, EventDirector, ProceduralEvent, LlmIntentParser |
| Living World v2 | 7 | LocationState, WorldFact, NpcSchedule, NpcAgenda, ConsequenceProcessor, SituationGenerator, PlayerGoal |

> 상세: `guides/03_hub_engine_guide.md`

### Client — 40+ components, 3 stores

| 영역 | 수 | 핵심 |
|------|---|------|
| narrative/ | 2 | NarrativePanel, StoryBlock |
| input/ | 2 | InputSection, QuickActionButton |
| hub/ | 12 | HubScreen, SignalFeed, Incident, NPC, Notifications, CollapsibleSection |
| location/ | 2 | TurnResultBanner, LocationToastLayer |
| screens/ | 4 | StartScreen, EndingScreen, RunEndScreen, NodeTransitionScreen |
| side-panel/ | 5 | SidePanel, CharacterTab, InventoryTab, EquipmentTab, SetBonusDisplay |
| ui/ | 6 | ErrorBanner, LlmFailureModal, BugReportButton, BugReportModal |
| layout/ | 2 | Header (자동 숨김), MobileBottomNav (햄버거 메뉴) |
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
| LLM | Gemini 2.5 Flash Lite (메인) / Claude Haiku 4.5 (fallback) / GPT-4.1-nano (경량) | Multi-provider via OpenRouter |

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
12. **LOCATION 판정 = 1d6 + floor(stat/4) + baseMod** — SUCCESS ≥ 5, PARTIAL 3~4, FAIL < 3.
13. **이벤트 고유 선택지 우선** — payload.choices > suggested_choices > LOCATION 기본.
14. **LOCATION 단기기억** — locationSessionTurns(최대 6턴+MidSummary) LLM 전달. 떠날 때 요약 저장.
15. **NPC 이름 비공개→공개** — FRIENDLY 1회 / CAUTIOUS 2회 / HOSTILE 3회 소개.
16. **장면 연속성 보장** — sceneFrame 3단계 억제 + 씬 이벤트 1턴 유지 + 7개 연속성 규칙.
17. **Token Budget 2500** — 블록별 예산 배분, 저우선 블록 트리밍.
18. **Procedural Plot Protection** — 동적 이벤트에서 arcRouteTag/commitmentDelta 절대 금지.
19. **NATURAL 엔딩 최소 15턴** — ALL_RESOLVED 엔딩은 totalTurns ≥ 15 이상이어야 발동.
20. **RUN_ENDED 시 메모리 통합** — go_hub/MOVE_LOCATION 없이 런 종료 시에도 finalizeVisit() 호출.
21. **MOVE_LOCATION fallback** — 목표 장소 불명확 시 HUB 복귀 처리 (이동 의도 무시 방지). KW MOVE_LOCATION은 장소명+이동접미사 복합감지 시에만 LLM보다 우선. 단순 키워드 1-hit은 LLM 신뢰.
22. **Living World 초기화** — createRun 시 locationDynamicStates(7개 장소), worldFacts(빈 배열), npcLocations, playerGoals 초기화 필수.
23. **NPC 3계층** — CORE(6) 우선 상황 생성, BACKGROUND(25) 배경만, SUB(12) 일반.
24. **선별 주입(Selective Injection)** — LLM 컨텍스트에 메모리를 주입할 때, 전체가 아닌 현재 턴에 관련된 것만 선별: NpcPersonalMemory는 등장 NPC만, LocationMemory는 현재 장소만, IncidentMemory는 관련 사건만, ItemMemory는 장착/획득(RARE 이상) 아이템만.
25. **프리셋 배경 참조** — 프리셋별 npcPostureOverrides(NPC 초기 태도 오버라이드), actionBonuses(행동 보너스), LLM 배경 텍스트가 게임 메카닉과 서술 모두에 반영.
26. **대화 잠금(Conversation Lock)** — 대화 계열 행동(TALK/PERSUADE/BRIBE/THREATEN/HELP) 시 같은 이벤트/NPC 최대 4턴 연속 유지. 비대화 행동(SNEAK/STEAL/FIGHT) 시 NPC 연속성 해제.
27. **NPC knownFacts 점진 공개** — SUCCESS/PARTIAL 판정 + 정보행동 시 NPC의 knownFacts 중 미공개 단서를 순서대로 공개. 이벤트 discoverableFact는 SUCCESS=100%, PARTIAL=50%. FAIL은 미공개.
28. **퀘스트 자동 전환** — discoveredQuestFacts 누적 → quest.json stateTransitions 조건 충족 시 questState 자동 전환 (S0→S1→...→S5).
29. **questFactTrigger SitGen 바이패스** — 미발견 fact 이벤트가 있는 장소에서 매 턴 이벤트 매칭 허용. 이때 SituationGenerator를 건너뛰고 EventDirector로 직행하여 fact 이벤트 매칭을 보장.
30. **밸런스 상수 외부화** — SitGen 확률, PARTIAL 발견률, weight 부스트 등 핵심 밸런스 상수는 `quest-balance.config.ts`에서 관리. 코드 내 하드코딩 금지.
31. **보너스 스탯 합계 = 6** — 캐릭터 생성 시 bonusStats 각 값 0~6, 합계 정확히 6. 서버에서 검증.
32. **특성 런타임 효과** — GAMBLER_LUCK(FAIL→50%PARTIAL, 크리티컬 비활성), BLOOD_OATH(저HP 보너스 +2/+3, 치료 50%↓), NIGHT_CHILD(밤+2, 낮-1). traitEffects는 runState에 저장, resolve/combat에서 참조.

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
| IncidentKind | `incident.ts` | CRIMINAL, POLITICAL, SOCIAL, ECONOMIC, MILITARY |
| IncidentOutcome | `incident.ts` | CONTAINED, ESCALATED, EXPIRED |
| SignalChannel | `signal-feed.ts` | RUMOR, SECURITY, NPC_BEHAVIOR, ECONOMY, VISUAL |
| NarrativeMarkType | `narrative-mark.ts` | BETRAYER, SAVIOR, KINGMAKER, SHADOW_HAND, MARTYR, PROFITEER, PEACEMAKER, WITNESS, ACCOMPLICE, AVENGER, COWARD, MERCIFUL |
| StepStatus | `operation-session.ts` | PENDING, IN_PROGRESS, COMPLETED, SKIPPED |
| Status ID | `specs/status_effect_system_v1.md` §10 | BLEED, POISON, STUN, WEAKEN, FORTIFY |
| ResolveOutcome | `resolve-result.ts` | SUCCESS, PARTIAL, FAIL |
| Client Phase | `game-store.ts` | TITLE, LOADING, HUB, LOCATION, COMBAT, NODE_TRANSITION, RUN_ENDED, ERROR |
| StoryMessageType | `game.ts` | SYSTEM, NARRATOR, PLAYER, CHOICE, RESOLVE |
| CharacterPreset | `presets.json` | DOCKWORKER, DESERTER, SMUGGLER, HERBALIST, FALLEN_NOBLE, GLADIATOR |
| CharacterTrait | `traits.json` | BATTLE_MEMORY, STREET_SENSE, SILVER_TONGUE, GAMBLER_LUCK, BLOOD_OATH, NIGHT_CHILD |
| NpcTier | `content.types.ts` | CORE, SUB, BACKGROUND |
| FactCategory | `world-fact.ts` | PLAYER_ACTION, NPC_ACTION, WORLD_CHANGE, DISCOVERY, RELATIONSHIP |
| SituationTrigger | `situation-generator.service.ts` | LANDMARK, INCIDENT_DRIVEN, NPC_ACTIVITY, NPC_CONFLICT, ENVIRONMENTAL, CONSEQUENCE, DISCOVERY, OPPORTUNITY, ROUTINE |

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
| POST | `/v1/bug-reports` | 버그 리포트 생성 (runId, turnNo, category, description) |
| GET | `/v1/bug-reports` | 버그 리포트 목록 조회 (페이징) |
| GET | `/v1/bug-reports/:id` | 버그 리포트 상세 조회 |
| PATCH | `/v1/bug-reports/:id` | 버그 리포트 상태 변경 (resolved 등) |
| POST | `/v1/portrait/generate` | AI 초상화 생성 (presetId, gender, appearanceDescription) |
| GET | `/v1/version` | 서버 버전 조회 (git hash, startedAt, uptime) |
| POST | `/v1/parties` | 파티 생성 (name) |
| GET | `/v1/parties/my` | 내 파티 조회 |
| GET | `/v1/parties/search` | 파티 검색 (?q=) |
| POST | `/v1/parties/join` | 초대코드로 가입 (inviteCode) |
| POST | `/v1/parties/:partyId/leave` | 파티 탈퇴 |
| POST | `/v1/parties/:partyId/kick` | 멤버 추방 (userId) |
| DELETE | `/v1/parties/:partyId` | 파티 해산 |
| POST | `/v1/parties/:partyId/messages` | 채팅 전송 (content) |
| GET | `/v1/parties/:partyId/messages` | 채팅 히스토리 (cursor, limit) |
| GET | `/v1/parties/:partyId/stream` | SSE 실시간 스트림 (?token=JWT) |
| GET | `/v1/parties/:partyId/lobby` | 로비 상태 조회 |
| POST | `/v1/parties/:partyId/lobby/ready` | 준비 완료 토글 (ready) |
| POST | `/v1/parties/:partyId/lobby/start` | 던전 시작 (리더 전용) |
| POST | `/v1/parties/:partyId/runs/:runId/turns` | 파티 행동 제출 (inputType, rawInput, idempotencyKey) |
| POST | `/v1/parties/:partyId/votes` | 이동 투표 제안 (targetLocationId) |
| POST | `/v1/parties/:partyId/votes/:voteId/cast` | 투표 참여 (choice: yes/no) |
| POST | `/v1/parties/:partyId/lobby/invite-run` | 내 세계에 초대 — 리더 솔로 런에 합류 (Phase 3) |
| GET | `/v1/parties/:partyId/runs/:runId/turns/:turnNo` | 파티 턴 상세 조회 (partyActions + serverResult + llm) |
| POST | `/v1/parties/:partyId/runs/:runId/leave` | 던전 이탈 (보상 정산 + AI 전환) |

## Environment Variables (`server/.env`)

```
DATABASE_URL=postgresql://user:password@localhost:5432/textRpg
LLM_PROVIDER=openai          # openai | claude | gemini | mock
OPENAI_API_KEY=sk-...
OPENAI_MODEL=google/gemini-2.5-flash-lite   # OpenRouter 메인 모델 (이전: gemma-4-26b-a4b-it)
OPENAI_BASE_URL=https://openrouter.ai/api/v1  # optional, OpenAI-compatible endpoint
CLAUDE_API_KEY=               # optional
GEMINI_API_KEY=               # optional
LLM_MAX_RETRIES=2
LLM_TIMEOUT_MS=8000
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.8
LLM_FALLBACK_PROVIDER=claude          # fallback: Claude Haiku 4.5 (이전: mock)
```

## Implementation Phase Status (구현 단계)

| Phase | 범위 | 상태 |
|-------|------|------|
| **Phase 1** | HUB 순환 탐험 + LOCATION 판정 + 전투 + LLM 내러티브 + 프리셋/인증 | ✅ 완료 |
| **Phase 2** | NPC 소개 + 5축 감정 | ✅ 완료 |
| **Phase 2** | DAG 노드 라우팅 | ✅ 완료 — 24노드 DAG 그래프 + 3루트 분기 |
| **Phase 3** | Turn Orchestration (NPC 주입, pressure) | ✅ 완료 |
| **Narrative v1** | Incident + 4상시간 + Signal + NpcEmotional + Mark + Ending + Operation | ✅ 완료 |
| **Memory v2** | StructuredMemory + [MEMORY]/[THREAD] 태그 + Scene Continuity | ✅ 완료 |
| **Narrative v2** | Token Budget + Mid Summary + Intent Memory + Active Clues | ✅ 완료 |
| **Event v2** | Event Director + Event Library(123개) + Procedural Event | ✅ 완료 |
| **Bridge** | IntentV3 + IncidentRouter + WorldDelta + PlayerThread + Notification | ✅ 완료 |
| **Client** | Notification UI + 엔딩 행동 성향 | ✅ 완료 |
| **Fixplan3** | P1 메모리통합 + P2 NPC소개 + P4 이동 + P5 씬연속 + P7 엔딩가드 + P10 조사 | ✅ 완료 |
| **Living World v2** | LocationState + WorldFact + NpcSchedule + SituationGenerator + ConsequenceProcessor + PlayerGoal | ✅ 완료 |
| **Phase 4** | 장비 v2 (세트/리전) + 리전 경제 | ✅ 완료 — 장비 드랍/착용, 동적 경제, 세트효과, Legendary |
| **Memory v3** | NpcPersonalMemory + LocationMemory + IncidentMemory + ItemMemory (선별 LLM 주입) | ✅ 완료 |
| **Preset v2** | 프리셋 배경 시스템 (npcPostureOverrides, actionBonuses, LLM 배경 참조) | ✅ 완료 |
| **Bug Report** | 인게임 버그 리포트 시스템 (bug_reports 테이블, API 4개) | ✅ 완료 |
| **Assets** | 캐릭터 초상화 8장 + 장소 이미지 24장 (Gemini 생성) | ✅ 완료 |
| **Mobile UX** | 헤더 자동 숨김 + 하단 네비 햄버거 + 대화창 최대화 + OG 메타데이터 | ✅ 완료 |
| **LLM Multi-Provider** | Claude provider 구현 (@anthropic-ai/sdk) + cacheCreationTokens 추적 | ✅ 완료 |
| **프롬프트 최적화** | 시스템 프롬프트 압축 21% + HUB 턴 경량화 37% + posture baseline 재설계 | ✅ 완료 |
| **NPC 대화 개선** | 대화 잠금 4턴 + 턴카운터 + 행동반응매핑 + 직전대사추출 + speechStyle 예시 제거 | ✅ 완료 |
| **NPC 콘텐츠 강화** | 43명 gender + role 다채화 + 18명 knownFacts/linkedIncidents | ✅ 완료 |
| **퀘스트 시스템** | QuestProgressionService + 6단계 전환 + 3 Arc 루트 + FACT 점진 공개 | ✅ 완료 |
| **프론트엔드 디자인 점검** | error boundary + PWA + 색상 토큰 통일 + HUB 접기/펼치기 + 핀치줌 차단 | ✅ 완료 |
| **NPC 초상화** | CORE 6명 초상화 생성 + 첫 등장 시 표시 시스템 | ✅ 완료 |
| **프롬프트 최적화 v2** | NPC 감정 블록 선별 주입 + 장소 블록 보완 + dry-run 프롬프트 추출 | ✅ 완료 |
| **라우트 재구성** | / → 랜딩(SEO), /play → 게임(SPA), api.dimtale.com 고정 터널 | ✅ 완료 |
| **퀘스트 밸런싱** | Fact 이벤트 11개 추가 + NPC ID 정규화 + P0~P5 매칭 개선 (SitGen 바이패스, weight 부스트, PARTIAL 50%, 밸런스 config 외부화, FREE 힌트) | ✅ 완료 |
| **캐릭터 생성** | 프리셋 6종(+몰락귀족/검투사) + 특성 6종 + 이름 입력 + AI 초상화 생성 + 보너스 스탯 +6 배분 + 6단계 UI + 특성 런타임 효과 | ✅ 완료 |
| **Intent Parser 강화** | MOVE_LOCATION KW_OVERRIDE 오탐 방지 + LLM 판정 신뢰 강화 (장소명 복합감지) | ✅ 완료 |
| **타이틀 UX 개선** | 로딩 애니메이션 (dotPulse) + 버튼 stagger fade-in + ads.txt | ✅ 완료 |
| **아이템 이미지 수정** | items/ 26개 중 10개 초상화 오류 → Gemini 2.5 Flash로 아이콘 재생성 | ✅ 완료 |
| **LLM Gemma 4 전환** | gpt-4.1-mini → Gemma 4 26B MoE (OpenRouter), openai provider baseURL 지원, 이미지 생성 비활성화 (과금 방지) | ✅ 완료 |
| **서술 품질 개선** | unknownAlias 매칭 강화 + encounterCount 4단계 NPC 관계 깊이 + PRESET_MANNERISMS 6종 + NPC 팩트 반복 버그 수정 | ✅ 완료 |
| **speakingNpc 버그 수정** | PROC_/SIT_ 이벤트 injectedNpc 분리 + 무명 인물 실루엣 아이콘 | ✅ 완료 |
| **린트 0/0** | 서버 unused-vars 62건 + unsafe 404건 수정, 클라이언트 린트 0/0, TS2871 빌드 에러 수정 | ✅ 완료 |
| **NPC 초상화 확장** | CORE + SUB NPC 초상화 12개 클라이언트 배치 | ✅ 완료 |
| **파티 Phase 1** | 파티 CRUD + 초대코드 + 실시간 채팅(SSE) + 로비 UI + PartyHUD | ✅ 완료 |
| **파티 Phase 2** | 파티 던전: 로비 준비→시작→4인 동시 턴→통합 판정→LLM 3인칭 서술→이동 투표→보상 분배→던전 종료 | ✅ 완료 |
| **파티 Phase 2 보강** | 이탈자 자동행동 + 재접속 AI해제 + HUB 투표이동 + 솔로동기화 + 개별HP + 턴상세API + 주사위 애니메이션 + 카운트다운 UI + party:error SSE + 멀티탭 방어 | ✅ 완료 |
| **파티 Phase 3** | 런 통합(내 세계에 초대) + run_participants 테이블 + 던전 중간 합류/이탈 + 보상 정산 | ✅ 완료 |
| **NPC 대사 마커 v2** | 하이브리드 @마커 시스템 (서버 regex 6단계 + nano 개별 판단), 정확도 30%→100%, 프롬프트 따옴표 규칙, 홑따옴표 강조 UI | ✅ 완료 |
| **서술 파이프라인 v2** | 3-Stage Pipeline (NanoDirector→Gemma4→NanoProcessor), 서술 다양성 개선, @마커 규칙 Gemma4에서 분리 | ✅ 완료 |
| **NPC 주도 행동** | trust 기반 dialogueSeed 5단계 + 비대화 행동 NPC 끼어들기 + 대화 잠금 LLM 전달 | ✅ 완료 |
| **OpenRouter 최적화** | provider sort:latency 적용 (평균 33초→7초) | ✅ 완료 |
| **클라이언트 UX 개선** | 세그먼트 기반 타이핑 + 페이지 전환 7종 + 장소 이미지 켄 번스 + NPC 카드 연출 + 시간대 알림 + 판정 순차 공식 + 네트워크 상태 | ✅ 완료 |
| **LLM Gemini Flash Lite 전환** | Gemma4 → Gemini 2.5 Flash Lite (속도 2.7배, 비용 17% 절감), Claude Haiku fallback | ✅ 완료 |
| **대사 오인 방지** | rawInput 유사도 필터 + 인용 조사 필터 + 불완전 마커 자동 정리 + role 매칭 강화 | ✅ 완료 |
| **NanoEventDirector** | nano LLM 기반 동적 이벤트 엔진: 매 턴 이벤트 컨셉/NPC/fact/선택지 생성, NPC 선택 행동별 전환 규칙, sourceNpcId 연속성, 기존 EventDirector fallback | ✅ 완료 |
| **연쇄 반응 시스템** | Layer 2: 치안/불안 임계값 → LOCKDOWN/RIOT 조건 자동 발동, 판정 보정(blockedActions -2), 시그널 피드 알림 | ✅ 완료 |
| **IntentParser 강화 v2** | 고위험 키워드(FIGHT/STEAL/THREATEN/BRIBE) LLM보다 KW 우선, targetNpcId KW 우선 (플레이어 NPC 지목) | ✅ 완료 |
| **NPC 능동 반응** | Layer 3: WITNESSED NPC trust 기반 경고/회피/밀고(Heat+5)/적대(Heat+8), LLM [NPC 반응] 블록 주입 | ✅ 완료 |
| **동시접속 최적화** | LLM Worker 5턴 병렬(Promise.allSettled) + DB 풀 max30 + 폴링 1초 + DB 쿼리 병렬 + 레이트 리미터 + Throttle 완화 + PM2 클러스터 설정 → 10명 동시접속 10/10 성공 | ✅ 완료 |

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
| node_routing_v2.md | ✅ 구현됨 | DAG 24노드 + 조건부 분기 |
| llm_context_memory_v1_1.md | 📎 참고 | v1.md 확장판 |

### architecture/ — 통합 아키텍처 (26 md)

| 파일 | 상태 | 비고 |
|------|------|------|
| 01_world_narrative.md | ✅ 정본 | 세계관/정치 |
| 02_combat_system.md | ✅ 정본 | 전투 통합 |
| 03_hub_engine.md | ✅ 구현됨 | HUB Action-First |
| 04_server_architecture.md | ✅ 정본 | 서버 아키텍처 |
| 05_llm_narrative.md | ✅ 정본 | LLM 파이프라인 |
| 06_graymar_content.md | ✅ 구현됨 | 콘텐츠 데이터 |
| 07_game_progression.md | ⚠️ 업데이트 필요 | HUB 모드 |
| 08_node_routing.md | ✅ 구현됨 | DAG 24노드 + 3루트 분기 |
| 09_npc_politics.md | ⚠️ 부분 | 감정/소개 ✅, Leverage ❌ |
| 10_region_economy.md | ⚠️ 부분 | 장비/세트 ✅, 리전 경제 미완 |
| 11_llm_prompt_caching.md | 📎 설계 | 최적화 전략 |
| 12_equipment_system.md | ✅ 구현됨 | 장비 드랍/착용, 세트효과, Legendary |
| 14_user_driven_code_bridge.md | ✅ 구현됨 | IntentV3→Incident→Router→Ending |
| 15_notification_system_design.md | ✅ 구현됨 | Notification 아키텍처 |
| 16_notification_ui_build_plan.md | ✅ 구현됨 | UI 빌드 체크리스트 |
| 17_notification_client_bridge.md | ✅ 구현됨 | 클라이언트 Notification |
| 18_narrative_runtime_patch.md | ✅ 구현됨 | Token Budget + Mid Summary |
| 19_event_orchestration.md | ✅ 구현됨 | Event Director + Library |
| 20_procedural_event_extension.md | ✅ 구현됨 | 동적 이벤트 생성 |
| Narrative_Engine_v1_Integrated_Spec.md | ✅ 정본 | Narrative Engine v1 통합 |
| ai_implementation_guidelines_for_narrative_patch.md | ✅ 적용됨 | 구현 원칙/금지사항 |
| fixplan3.md | ✅ 구현됨 | 플레이테스트 15턴 이슈 수정 (P1~P10) |
| 21_living_world_redesign.md | ✅ 구현됨 | Living World v2 전체 재설계 |
| 22_dice_roll_animation.md | ✅ 구현됨 | 주사위 판정 애니메이션 |
| 23_dialogue_ui_redesign.md | ✅ 설계 | 대화 UI 고도화 (메신저 형태) |
| fixplan4.md | ✅ 구현됨 | 플레이테스트 이슈 수정 (fixplan4) |
| fixplan5.md | ✅ 구현됨 | 플레이테스트 이슈 수정 (fixplan5) |
| Context Coherence Reinforcement.md | ✅ 구현됨 | 컨텍스트 일관성 강화 |
| 24_multiplayer_party_system.md | ✅ 구현됨 | 멀티플레이어 파티 시스템 Phase 1+2 |
| 25_llm_model_evaluation.md | 📎 참고 | LLM 모델 비교 평가 (GPT-4.1-mini vs Gemma 4) |
| 26_narrative_pipeline_v2.md | ✅ 구현됨 | 3-Stage LLM Pipeline (NanoDirector→Gemma4→NanoProcessor) |
| 27_image_asset_plan.md | 📎 계획 | 추가 이미지 에셋 (선술집, BG NPC 초상화, 이벤트 씬) |
| 28_nano_event_director.md | ✅ 구현됨 | NanoEventDirector 동적 이벤트 엔진 설계 (4단계 파이프라인) |

### guides/ — 코드 구현 지침 (6 md)

| 파일 | 내용 |
|------|------|
| 01_server_module_map.md | 서버 전체 서비스 맵 (60+ services, 35 타입 파일) |
| 02_client_component_map.md | 클라이언트 컴포넌트 맵 (31 components, stores, CSS) |
| 03_hub_engine_guide.md | HUB 엔진 구현 (판정, EventDirector, Narrative, NPC, 평판) |
| 04_llm_memory_guide.md | LLM 파이프라인, 메모리 L0~L4, Token Budget, Scene Continuity |
| 05_runstate_constants.md | RunState JSONB 구조, 핵심 상수, Content Data |
| 06_location_image_prompts.md | 장소별 이미지 프롬프트 가이드 |

## Working Language

설계 문서와 게임 콘텐츠는 한국어. 기술 식별자(enum, field name, schema key)는 영어.
