# 서버 모듈/서비스 맵

> 정본 위치: `server/src/`
> 최종 갱신: 2026-07-18

## 모듈 구조 (14 modules, 107 services, 12 controllers)

```
main.ts → AppModule
├── common/              ← Guards, Filters, Pipes, Decorators, Errors
│   ├── decorators/      ← user-id.decorator
│   ├── errors/          ← game-errors (GameError 클래스)
│   ├── filters/         ← game-exception.filter
│   ├── guards/          ← auth.guard
│   ├── pipes/           ← zod-validation.pipe
│   ├── text-utils.ts    ← 텍스트 유틸리티
│   ├── dialogue-act.ts  ← 사교 발화 감지 (GREETING/WELLBEING/THANKS/FAREWELL — 불변식 44)
│   └── korean.ts        ← 한국어 조사 처리 (korParticleRo 등, architecture/68)
├── auth/                ← 인증 모듈
│   ├── auth.controller  ← POST /v1/auth/register, POST /v1/auth/login
│   ├── auth.service     ← JWT 세션 관리
│   └── auth.dto         ← 인증 DTO
├── db/                  ← Drizzle ORM
│   ├── schema/          ← 20 파일 / 22 pgTable (아래 참조)
│   └── types/           ← TypeScript types (47 파일, 아래 참조)
├── content/             ← 게임 콘텐츠 로더 (멀티 팩)
│   ├── content-loader.service  ← 팩별 JSON 로드 + ContentPackState 캐시 (graymar/silverdeen/karnholt)
│   ├── content.types            ← NpcDefinition.unknownAlias/shortAlias, NpcTier 포함
│   ├── content.module
│   ├── event-content.provider   ← 이벤트 콘텐츠 프로바이더
│   ├── scenarios.controller     ← GET /v1/scenarios, GET /v1/scenarios/:id/creation-bundle (architecture/63⑥, 71)
│   ├── scenario-context.ts      ← AsyncLocalStorage 시나리오 스코프 (ensureScenario/enterScenario — architecture/63①)
│   └── dynamic-npc.ts           ← 동적 NPC stub 검증·등록 (자율 서사 P1 — architecture/75 §4.1)
├── engine/              ← Core game logic (65 services)
│   ├── rng/             ← Deterministic RNG (splitmix64, seed+cursor)
│   ├── stats/           ← Stat snapshot calculation
│   ├── status/          ← Status effects lifecycle (tick/만료)
│   ├── combat/          ← Hit, Damage, EnemyAI, PropMatcher, CombatService (5 services) + combat-tactic.core (적 기만 감정, arch/76 D3)
│   ├── input/           ← RuleParser → Policy → ActionPlan (3 services, 전투 입력용)
│   ├── nodes/           ← 노드별 리졸버 + 전이 (7 services)
│   │   ├── node-resolver.service   ← 노드 타입별 분기 진입점
│   │   ├── node-transition.service ← HUB↔LOCATION↔COMBAT 전이
│   │   ├── combat-node.service     ← COMBAT 노드 처리
│   │   ├── event-node.service      ← EVENT 노드 처리
│   │   ├── rest-node.service       ← REST 노드 처리
│   │   ├── shop-node.service       ← SHOP 노드 처리
│   │   └── exit-node.service       ← EXIT 노드 처리
│   ├── rewards/         ← 보상 + 인벤토리 + 장비 (5 services)
│   │   ├── rewards.service          ← 보상 계산
│   │   ├── inventory.service        ← 아이템 추가/제거
│   │   ├── equipment.service        ← 장비 장착/해제
│   │   ├── affix.service            ← 리전 접미사 처리
│   │   └── legendary-reward.service ← 전설 장비 보상 처리
│   ├── planner/         ← RUN 계획 (1 service)
│   │   └── run-planner.service ← RUN 구조 생성
│   └── hub/             ← HUB 엔진 (41 services, 6 서브시스템 + 퀘스트 + TurnOrchestration, 아래 상세)
│       └── (순수 모듈)  ← beat-gravity(비트 채택), autonomous-ending(규명율 종결), pack-meter, plot-seed-validator — 자율 서사 P3~P5 (architecture/75)
├── runs/                ← RUN/버그리포트
│   ├── runs.controller        ← POST /v1/runs, GET /v1/runs, GET /v1/runs/:runId
│   ├── runs.service
│   ├── bug-report.controller  ← POST/GET/PATCH /v1/bug-reports
│   └── bug-report.service     ← 버그 리포트 CRUD
├── turns/               ← POST/GET /v1/runs/:runId/turns, POST retry-llm
│   ├── turns.controller
│   ├── turns.service    ← 턴 파이프라인 조율 (arch/77 P3: Inner 4,440→1,937줄, 추출 메서드 다수)
│   ├── npc-agitation.core.ts     ← 감정→세계 행동화 (fear 도주/susp 신고/trust 접근, arch/76 D3)
│   ├── witness-reaction.core.ts  ← 목격자 반응 posture 우선 trust 밴드 (architecture/72)
│   └── run-state-apply.core.ts   ← 인벤토리 수량 병합 단일화 순수 함수 (5개 보상 경로 공통, arch/77 P3)
├── llm/                 ← Async LLM narrative (20 services, 1 controller, 아래 상세)
├── endings/             ← 여정 아카이브 조회
│   ├── endings.controller     ← GET /v1/endings, GET /v1/endings/:runId
│   └── endings.module         ← SummaryBuilderService(engine/hub)를 lazy fallback으로 사용
├── campaigns/           ← 캠페인(시즌/이벤트) 관리
│   ├── campaigns.controller   ← GET /v1/campaigns
│   └── campaigns.service
├── portrait/            ← 캐릭터 초상화 생성
│   ├── portrait.controller    ← POST /v1/portrait/generate
│   └── portrait.service       ← Gemini 이미지 생성 + 크롭
├── scene-image/         ← NPC/장면 이미지 생성
│   ├── scene-image.controller ← 씬 이미지 생성 엔드포인트
│   └── scene-image.service    ← Gemini 이미지 생성, rate limit
└── party/               ← 멀티플레이어 파티 시스템 (8 services, 1 controller)
    ├── party.controller       ← REST + SSE 엔드포인트
    ├── party.service          ← 파티 CRUD + 초대코드
    ├── chat.service           ← 파티 채팅
    ├── party-stream.service   ← SSE 연결 관리 + 브로드캐스트
    ├── lobby.service          ← 로비/준비 관리
    ├── party-turn.service     ← 통합 턴 처리
    ├── vote.service           ← 이동 투표
    ├── party-reward.service   ← 보상 분배
    └── run-participants.service ← 런 참여자 관리 (Phase 3: 중간 합류/이탈)
```

---

## HUB 엔진 서비스 (41 services, 6 서브시스템)

`server/src/engine/hub/`

### 1. Base HUB (12 services)

| 서비스 | 파일 | 역할 |
|--------|------|------|
| WorldStateService | world-state.service.ts | WorldState 관리 (Heat, Time, Safety) |
| HeatService | heat.service.ts | Heat 증감, 감쇠, 해결 |
| EventMatcherService | event-matcher.service.ts | 6단계 이벤트 매칭 알고리즘 (Player-First targetNpcId 가중치) |
| ResolveService | resolve.service.ts | 행동 판정 (1d6 + stat보너스 + baseMod) |
| AgendaService | agenda.service.ts | 플레이어 성향 추적 |
| ArcService | arc.service.ts | 아크 루트/커밋먼트 관리 |
| QuestProgressionService | quest-progression.service.ts | 퀘스트 단계 자동 전환 (FACT 발견 → stateTransitions 조건 체크) |
| SceneShellService | scene-shell.service.ts | 장면 분위기 + 선택지 생성 |
| IntentParserV2Service | intent-parser-v2.service.ts | 자연어 → ActionType 파싱 + 고집 에스컬레이션 |
| TurnOrchestrationService | turn-orchestration.service.ts | NPC 주입 (displayName) + 긴장도 관리 + TurnMode 3분류 결정 |
| NpcResolverService | npc-resolver.service.ts | NPC 화자 결정 단일 권한자 — 텍스트매칭/IntentV3/대화잠금/Nano/이벤트배정 5단계 통합 (architecture/49) |
| SuddenActionDetectorService | sudden-action-detector.service.ts | 돌발행동 분류 (CRITICAL 살해 의도 등) + N턴 맥락 보존 (architecture/43) |

### 2. Narrative Engine v1 (9 services)

| 서비스 | 파일 | 역할 |
|--------|------|------|
| IncidentManagementService | incident-management.service.ts | Incident 생명주기 (spawn/tick/resolve) |
| WorldTickService | world-tick.service.ts | preStepTick/postStepTick, 4상 시간 사이클 |
| SignalFeedService | signal-feed.service.ts | 5채널 시그널 생성/만료 |
| OperationSessionService | operation-session.service.ts | 멀티스텝 LOCATION 세션 (1-3스텝) |
| NpcEmotionalService | npc-emotional.service.ts | 5축 감정 모델 + posture 계산 |
| NarrativeMarkService | narrative-mark.service.ts | 12개 불가역 표식 시스템 |
| EndingGeneratorService | ending-generator.service.ts | 엔딩 조건 체크/결과 생성 (NATURAL ≥15턴, Quest S5+5) |
| ShopService | shop.service.ts | 상점 메카닉 |
| SummaryBuilderService | summary-builder.service.ts | RUN_ENDED 시 여정 요약(EndingSummary) 템플릿 조립 — LLM 호출 금지, 결정론적 (architecture/39) |

### 3. Structured Memory v2 (2 services)

| 서비스 | 파일 | 역할 |
|--------|------|------|
| MemoryCollectorService | memory-collector.service.ts | 매 LOCATION 턴 visitContext 실시간 수집 + NPC Knowledge 자동 수집 |
| MemoryIntegrationService | memory-integration.service.ts | 방문 종료 시 StructuredMemory 통합+압축 (NPC별 행동 필터, snippet summaryShort 기반) |

### 4. User-Driven Bridge (6 services) — 설계문서 14~17

| 서비스 | 파일 | 역할 |
|--------|------|------|
| IntentV3BuilderService | intent-v3-builder.service.ts | ParsedIntentV2 → ParsedIntentV3 확장 변환 |
| IncidentRouterService | incident-router.service.ts | IntentV3 기반 Incident 라우팅/매칭 |
| IncidentResolutionBridgeService | incident-resolution-bridge.service.ts | ResolveResult → Incident control/pressure 반영 |
| WorldDeltaService | world-delta.service.ts | 턴 전후 WorldState 차이 추적 |
| PlayerThreadService | player-thread.service.ts | 행동 성향 패턴 추적 (playstyleSummary, dominantVectors) |
| NotificationAssemblerService | notification-assembler.service.ts | Notification 조립 (scope×presentation) |

### 5. Narrative v2 & Event v2 (4 services) — 설계문서 18~20, 28, 34

| 서비스 | 파일 | 역할 |
|--------|------|------|
| IntentMemoryService | intent-memory.service.ts | actionHistory 분석 → 행동 패턴 감지 (6종) |
| EventDirectorService | event-director.service.ts | 5단계 정책 파이프라인 (Stage→Condition→Cooldown→Priority→Weighted) — NanoEventDirector fallback |
| ProceduralEventService | procedural-event.service.ts | 동적 이벤트 생성 (Trigger+Subject+Action+Outcome) |
| LlmIntentParserService | llm-intent-parser.service.ts | LLM 기반 의도 파싱 (고위험 KW 우선, KW_OVERRIDE 장소명 복합감지) |

### 6. Living World v2 (8 services) — 설계문서 21, 48

| 서비스 | 파일 | 역할 |
|--------|------|------|
| LocationStateService | location-state.service.ts | 장소별 동적 상태 관리 (crowdLevel, mood, activeTags) |
| WorldFactService | world-fact.service.ts | 세계 사실 기록/조회 (최대 50개, FactCategory 5종) |
| NpcScheduleService | npc-schedule.service.ts | NPC 위치/스케줄 관리 (시간대별 이동) |
| NpcAgendaService | npc-agenda.service.ts | NPC 개별 의제/목표 추적 |
| ConsequenceProcessorService | consequence-processor.service.ts | 플레이어 행동 결과의 세계 반영 (연쇄 효과) |
| SituationGeneratorService | situation-generator.service.ts | 상황 동적 생성 (9종 SituationTrigger, questFact 바이패스) |
| PlayerGoalService | player-goal.service.ts | 플레이어 목표 추적/관리 (최대 5개) |
| NpcWhereaboutsService | npc-whereabouts.service.ts | NPC 현재 위치 lookup (SAME/DIFFERENT_LOCATION + activity) — Discoverability Layer 2 (architecture/48) |

---

## LLM 모듈 서비스 (23 services, 1 controller)

`server/src/llm/`

| 서비스 | 파일 | 역할 |
|--------|------|------|
| LlmWorkerService | llm-worker.service.ts | Background poller (1s), PENDING→DONE, NanoEventDirector 비동기 호출, 스트리밍 파이프라인 진입점 (arch/77 P4: Inner 3,503→1,746줄, 금지선 4곳 마킹) |
| LlmCallerService | llm-caller.service.ts | LLM 공급자 호출 래퍼 (retry, timeout, fallback 모델, cost_usd 추적) |
| LlmConfigService | llm-config.service.ts | 런타임 LLM 설정 관리 (provider, model, JSON 모드) |
| ContextBuilderService | context-builder.service.ts | L0-L4 메모리 컨텍스트 빌드 + 선별 주입 |
| MemoryRendererService | memory-renderer.service.ts | StructuredMemory → 프롬프트 블록 |
| AiTurnLogService | ai-turn-log.service.ts | LLM 호출 로그 기록 (ai_turn_logs 테이블) |
| TokenBudgetService | token-budget.service.ts | 토큰 예산 관리 — 메모리 블록 2500 + 총량 백스톱 GRAND_TOTAL_CHAR_BUDGET 16,000자 (arch/79) |
| MidSummaryService | mid-summary.service.ts | 4턴 초과 시 중간 요약 생성 |
| NpcDialogueMarkerService | npc-dialogue-marker.service.ts | 서버 regex + nano LLM 하이브리드 @마커 삽입, 불일치 교정 (Step F) |
| NanoDirectorService | nano-director.service.ts | nano 전처리: 연출 지시서 생성 (첫 문장, NPC 행동, 반복 회피) |
| NanoEventDirectorService | nano-event-director.service.ts | nano 동적 이벤트: 컨셉/NPC/fact/선택지 생성 (LLM Worker 비동기) |
| NpcReactionDirectorService | npc-reaction-director.service.ts | nano 사전결정: NPC 반응(7종)+즉시목표+추상톤 3축(voiceQuality/emotionalUndertone/bodyLanguageMood). 메인 LLM이 추측 대신 결정 표현 — A56 |
| ChallengeClassifierService | challenge-classifier.service.ts | 자유 행동 주사위 스킵: 룰 게이트(NON_CHALLENGE/ALWAYS_CHALLENGE) + 회색지대 nano 분류 (FREE/CHECK) — A56 |
| ThemeClassifierService | theme-classifier.service.ts | NPC 대사 의미 테마 분류 — 동의어 우회 차단, 크로스 NPC 주제 반복 해소 (architecture/44 이슈②) |
| DialogueGeneratorService | dialogue-generator.service.ts | 2-Stage 대사 분리 파이프라인 (서술+대사 분리, dialogue_slot, 하오체 검증) |
| FactExtractorService | fact-extractor.service.ts | Memory v4: nano 구조화 추출 (entity_facts UPSERT, 반복률 71% 감소) |
| LorebookService | lorebook.service.ts | 키워드 트리거 기반 세계 지식 동적 주입 (NPC/장소/사건/entity_facts) |
| LlmStreamBrokerService | llm-stream-broker.service.ts | 턴별 SSE 채널 관리 (OpenRouter stream:true 토큰 브로드캐스트) |
| StreamClassifierService | stream-classifier.service.ts | 스트리밍 토큰 실시간 분류 (narration vs dialogue, 문장 단위 버퍼링) |
| PromptBuilderService | prompts/prompt-builder.service.ts | 시스템 프롬프트 조립 + NPC 소개 분기 + PRESET_MANNERISMS (arch/77 P1: 2,838→1,087줄) |
| LlmCallLogService | llm-call-log.service.ts | 턴당 LLM 호출 실측 로그 — llm_call_logs 테이블 배치(1행) 기록 (turn-context ALS와 연동) |
| PlotDirectorService | plot-director.service.ts | 자율 서사 Emergent Director — 비트 후보 2~3개 nano 선계산 → nextBeatCandidates 저장 (architecture/75 §5, AUTONOMOUS 전용) |
| PlotSeedGeneratorService | plot-seed-generator.service.ts | Plot Seed 생성 — nano 진상 생성 + validatePlotSeedCore 검증/재롤 + 결정론 폴백 (architecture/75 §3, createRun 백그라운드) |
| LlmSettingsController | llm-settings.controller.ts | GET/PATCH /v1/settings/llm (런타임 설정) |

**순수 모듈/유틸 (서비스 아님):**
- `narrative-filter.core.ts` — 서술 품질 후처리 필터 체인 export 정본 (플레이어 대사 방어→메타 서술→R1→미소개 실명→경어체→opening, arch/77 P4.1)
- `turn-context.ts` — 턴 단위 LLM 호출 로그 ALS 스코프 (유닛 이코노미 실측)
- `npc-relation-mention.ts` — NPC 관계 근황 발화 후보 선정 (arch/69 B4)
- `npc-utterance.util.ts` — @마커에서 특정 NPC 발화 추출

**하위 모듈:**
- `providers/` — OpenAI(OpenRouter 경유), Claude, Gemini, Mock (4 providers) + LlmProviderRegistryService
- `prompts/` — PromptBuilder + system-prompts + intent-system-prompt + speech-register(어체 규칙) + intro-directive(자기소개 디렉티브, arch/66) + injected-block-headers(주입 블록 헤더 정본)
- `types/` — LLM 공급자 인터페이스 타입

---

## NPC Personal Memory 유틸

`server/src/engine/hub/memory-collector.service.ts` 내 NPC 개인 기록 관련 함수:

| 함수 | 역할 |
|------|------|
| recordNpcEncounter() | NPC 만남 기록 (턴, 장소, 행동, 결과) → NpcState.personalMemory에 축적 |
| selectNpcMemories() | 현재 턴에 등장하는 NPC의 personalMemory만 선별하여 LLM 컨텍스트에 주입 |

---

## DB 스키마 (21 파일, 23 pgTable)

`server/src/db/schema/`

| 테이블 | 용도 |
|--------|------|
| users | 사용자 계정 |
| player_profiles | 플레이어 프로필 |
| hub_states | HUB 상태 |
| run_sessions | 런 세션 (runState JSONB) |
| node_instances | 노드 인스턴스 |
| turns | 턴 기록 (llm_prompt JSONB 컬럼 — 프롬프트 저장) |
| battle_states | 전투 상태 |
| run_memories | 런 메모리 (theme, storySummary, structuredMemory) |
| node_memories | 노드 메모리 (narrativeThread) |
| recent_summaries | 최근 요약 |
| entity_facts | Memory v4 구조화 팩트 저장 (NPC/장소/사건 키별 UPSERT, 반복 방어) |
| ai_turn_logs | LLM 호출 로그 (cost_usd, cacheCreationTokens 포함) |
| llm_call_logs | 턴 단위 LLM 유닛 이코노미 실측 (호출별 usage/cost 배치 1행) |
| scene_images | 씬 이미지 캐시/메타데이터 |
| campaigns | 시즌/이벤트 캠페인 메타 |
| playtest_results | 플레이테스트 자동 실행 결과 |
| bug_reports | 인게임 버그 리포트 (runId, turnNo, category, description, recent_turns, ui_debug_log, client_snapshot, network_log, client_version, server_version, status) |
| parties | 파티 (name, inviteCode, leaderId, status) |
| party_members | 파티 멤버 (partyId, userId, role, joinedAt) |
| chat_messages | 파티 채팅 메시지 (partyId, userId, content, createdAt) |
| party_turn_actions | 파티 턴 행동 (partyId, runId, turnNo, userId, inputType, rawInput) |
| party_votes | 이동 투표 (partyId, proposerId, targetLocationId, status) |
| run_participants | 런 참여자 (runId, userId, joinedAt, leftAt, isAi) |

---

## DB 타입 파일 (47 파일)

`server/src/db/types/`

### 핵심 타입
| 파일 | 내용 |
|------|------|
| enums.ts | 모든 게임 enum 정의 (정본) |
| server-result.ts | ServerResultV1 (UIBundle 포함) |
| world-state.ts | WorldState (globalClock, TimePhaseV2, incidents, signals, marks) |
| npc-state.ts | NPCState, getNpcDisplayName(), shouldIntroduce(), computeEffectivePosture() |
| resolve-result.ts | ResolveResult, ResolveOutcome (incidentPatches 포함) |

### Narrative Engine v1 타입
| 파일 | 내용 |
|------|------|
| incident.ts | IncidentDef, IncidentRuntime, IncidentOutcome, IncidentKind |
| signal-feed.ts | SignalChannel (5채널), SignalFeedItem |
| narrative-mark.ts | NarrativeMarkType (12종), NarrativeMark |
| operation-session.ts | OperationSession, OperationStep, StepStatus |
| ending.ts | EndingInput, EndingResult, NpcEpilogue, CityStatus |
| structured-memory.ts | StructuredMemory, VisitLogEntry, NpcJournalEntry, LlmExtractedFact |

### User-Driven Bridge 타입 (설계문서 14~17)
| 파일 | 내용 |
|------|------|
| parsed-intent-v3.ts | ParsedIntentV3 (V2 확장, contextNpcId 포함) |
| incident-routing.ts | IncidentRouter 출력 타입 |
| world-delta.ts | WorldDelta 상태 변화 타입 |
| player-thread.ts | PlayerThread 행동 성향 타입 |
| notification.ts | Notification 시스템 타입 (scope, presentation, kind) |

### Narrative v2 & Event v2 타입 (설계문서 18~20)
| 파일 | 내용 |
|------|------|
| event-director.ts | EventPriority, EventDirectorResult, EventCategory |
| procedural-event.ts | ProceduralSeed, SeedConstraints, ProceduralHistoryEntry |

### Living World v2 타입 (설계문서 21)
| 파일 | 내용 |
|------|------|
| location-state.ts | LocationDynamicState (crowdLevel, mood, activeTags) |
| world-fact.ts | WorldFact (FactCategory 5종, impact) |
| npc-schedule.ts | NpcScheduleEntry, NpcLocationState |
| player-goal.ts | PlayerGoal (priority, progress) |

### NPC/초상화 확장 타입
| 파일 | 내용 |
|------|------|
| npc-knowledge.ts | NPC knownFacts 점진 공개 구조 (SUCCESS/PARTIAL 매핑) |
| npc-portraits.ts | NPC/프리셋 초상화 경로/크롭 메타 |
| carry-over.ts | 런 종료 간 이어지는 보상/성장 데이터 |

### 자율 서사 타입 (architecture/75)
| 파일 | 내용 |
|------|------|
| plot-seed.ts | PlotSeed(진상·keyFacts·acts), Motif, NarrativeMode, BeatCandidate |
| pack-meter.ts | 팩별 게이지(packMeters — 광산 불안 등, endingTrigger 임계) |

### 기타 타입
| 파일 | 내용 |
|------|------|
| battle-state.ts | BattleStateV1, Distance, Angle, AIPersonality |
| parsed-intent-v2.ts | ParsedIntentV2, IntentActionType |
| parsed-intent.ts | ParsedIntent (v1, 전투용) |
| event-def.ts | EventDefV2 (eventCategory, cooldownTurns, effects 포함) |
| arc-state.ts | ArcState, ArcRoute |
| agenda.ts | PlayerAgenda |
| memory-types.ts | 메모리 타입 정의 |
| permanent-stats.ts | PermanentStats |
| hub-types.ts | HUB 관련 타입 |
| player-behavior.ts | PlayerBehaviorProfile |
| node-meta.ts | NodeMeta |
| equipment.ts | EquippedGear, ItemInstance |
| region-state.ts | RegionState |
| region-affix.ts | RegionAffix |
| action-plan.ts | ActionPlan (전투용) |
| graph-types.ts | 노드 그래프 타입 |
| narrative-theme.ts | NPC 대사 의미 테마 타입 (architecture/44 이슈②) |
| index.ts | 통합 export |

---

## 최근 추가/변경 요약 (2026-04)

- **LLM 모듈 확장**: 8 → 17 services. FactExtractor (Memory v4), Lorebook (키워드 트리거 세계 지식), DialogueGenerator (2-Stage 대사 분리), LlmStreamBroker/StreamClassifier (OpenRouter stream:true + SSE + 문장 단위 분류).
- **Party 모듈**: 7 → 8 services. run-participants.service (Phase 3 중간 합류/이탈) 추가.
- **bug_reports 컬럼 확장**: client_snapshot, network_log, client_version 신규 추가. 기존 server_version + ui_debug_log 유지.
- **DB 신규 테이블**: entity_facts (Memory v4), scene_images, campaigns, playtest_results.
- **모듈 신규**: campaigns/, portrait/ (독립 모듈로 분리). scene-image/에 controller 추가.
- **turns.service 경량화**: NanoEventDirector 호출을 LLM Worker로 이관 (nanoCtx만 빌드).

## 최근 추가/변경 요약 (2026-05~07 동기화)

- **HUB 확장**: 37 → 41 services. NpcResolver(architecture/49 단일 권한자), NpcWhereabouts(architecture/48), SuddenActionDetector(architecture/43), SummaryBuilder(architecture/39) 추가.
- **LLM 확장**: 19 → 20 services. ThemeClassifier(architecture/44 이슈② 크로스 NPC 테마 반복 해소) 추가.
- **combat 확장**: 4 → 5 services. PropMatcher(architecture/41 창의 전투) 추가.
- **모듈 신규**: endings/ (여정 아카이브 조회 컨트롤러).
- **DB 타입 신규**: narrative-theme.ts.

## 최근 추가/변경 요약 (2026-07-18 동기화)

- **자율 서사 P0~P6 (architecture/75)**: LLM에 PlotSeedGenerator·PlotDirector 서비스, engine/hub에 beat-gravity·autonomous-ending·pack-meter·plot-seed-validator 순수 모듈, content에 dynamic-npc(동적 NPC stub), db/types에 plot-seed.ts·pack-meter.ts 추가. AUTONOMOUS 팩(karnholt_v1) 전용 — AUTHORED 런은 무동작.
- **멀티 시나리오 (architecture/63)**: scenario-context.ts(AsyncLocalStorage 팩 스코프) + scenarios.controller(GET /v1/scenarios, creation-bundle) — 컨트롤러 11 → 12.
- **LLM 유닛 이코노미**: turn-context.ts(ALS) + LlmCallLogService + llm_call_logs 테이블 — 스키마 21 파일 / 23 pgTable.
- **arch/76 D3 (탈버킷)**: turns/npc-agitation.core(감정→행동화) · witness-reaction.core(architecture/72) · combat/combat-tactic.core(전투 기만) 순수 모듈.
- **arch/77 God method 리팩토링**: turns.service Inner -56% · llm-worker Inner -50%(금지선 4곳 마킹) · prompt-builder -62% · context-builder -64% · Combat -41%. narrative-filter.core.ts(후처리 필터 정본) · run-state-apply.core.ts(인벤토리 병합) 신설. 파일 구조는 동일, 메서드가 다수의 private 메서드/순수 모듈로 분해됨.
- **합계**: 104 → 107 services, 11 → 12 controllers, DB 타입 43 → 45 파일.
