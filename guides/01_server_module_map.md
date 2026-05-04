# 서버 모듈/서비스 맵

> 정본 위치: `server/src/`
> 최종 갱신: 2026-04-17

## 모듈 구조 (12 modules, 95 services, 10 controllers)

```
main.ts → AppModule
├── common/              ← Guards, Filters, Pipes, Decorators, Errors
│   ├── decorators/      ← user-id.decorator
│   ├── errors/          ← game-errors (GameError 클래스)
│   ├── filters/         ← game-exception.filter
│   ├── guards/          ← auth.guard
│   ├── pipes/           ← zod-validation.pipe
│   └── text-utils.ts    ← 텍스트 유틸리티
├── auth/                ← 인증 모듈
│   ├── auth.controller  ← POST /v1/auth/register, POST /v1/auth/login
│   ├── auth.service     ← JWT 세션 관리
│   └── auth.dto         ← 인증 DTO
├── db/                  ← Drizzle ORM
│   ├── schema/          ← 20 파일 / 22 pgTable (아래 참조)
│   └── types/           ← TypeScript types (42 파일, 아래 참조)
├── content/             ← 게임 콘텐츠 로더
│   ├── content-loader.service  ← graymar_v1 JSON 24개 로드
│   ├── content.types            ← NpcDefinition.unknownAlias/shortAlias, NpcTier 포함
│   ├── content.module
│   └── event-content.provider   ← 이벤트 콘텐츠 프로바이더
├── engine/              ← Core game logic (60 services)
│   ├── rng/             ← Deterministic RNG (splitmix64, seed+cursor)
│   ├── stats/           ← Stat snapshot calculation
│   ├── status/          ← Status effects lifecycle (tick/만료)
│   ├── combat/          ← Hit, Damage, EnemyAI, CombatService (4 services)
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
│   └── hub/             ← HUB 엔진 (37 services, 6 서브시스템 + 퀘스트 + TurnOrchestration, 아래 상세)
├── runs/                ← RUN/버그리포트
│   ├── runs.controller        ← POST /v1/runs, GET /v1/runs, GET /v1/runs/:runId
│   ├── runs.service
│   ├── bug-report.controller  ← POST/GET/PATCH /v1/bug-reports
│   └── bug-report.service     ← 버그 리포트 CRUD
├── turns/               ← POST/GET /v1/runs/:runId/turns, POST retry-llm
│   ├── turns.controller
│   └── turns.service    ← nanoCtx 빌드만 수행 (NanoEventDirector 호출은 LLM Worker로 이관)
├── llm/                 ← Async LLM narrative (19 services, 1 controller, 아래 상세)
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

## HUB 엔진 서비스 (37 services, 6 서브시스템)

`server/src/engine/hub/`

### 1. Base HUB (10 services)

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

### 2. Narrative Engine v1 (8 services)

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

### 6. Living World v2 (7 services) — 설계문서 21

| 서비스 | 파일 | 역할 |
|--------|------|------|
| LocationStateService | location-state.service.ts | 장소별 동적 상태 관리 (crowdLevel, mood, activeTags) |
| WorldFactService | world-fact.service.ts | 세계 사실 기록/조회 (최대 50개, FactCategory 5종) |
| NpcScheduleService | npc-schedule.service.ts | NPC 위치/스케줄 관리 (시간대별 이동) |
| NpcAgendaService | npc-agenda.service.ts | NPC 개별 의제/목표 추적 |
| ConsequenceProcessorService | consequence-processor.service.ts | 플레이어 행동 결과의 세계 반영 (연쇄 효과) |
| SituationGeneratorService | situation-generator.service.ts | 상황 동적 생성 (9종 SituationTrigger, questFact 바이패스) |
| PlayerGoalService | player-goal.service.ts | 플레이어 목표 추적/관리 (최대 5개) |

---

## LLM 모듈 서비스 (17 services, 1 controller)

`server/src/llm/`

| 서비스 | 파일 | 역할 |
|--------|------|------|
| LlmWorkerService | llm-worker.service.ts | Background poller (1s), PENDING→DONE, NanoEventDirector 비동기 호출, 스트리밍 파이프라인 진입점 |
| LlmCallerService | llm-caller.service.ts | LLM 공급자 호출 래퍼 (retry, timeout, fallback 모델, cost_usd 추적) |
| LlmConfigService | llm-config.service.ts | 런타임 LLM 설정 관리 (provider, model, JSON 모드) |
| ContextBuilderService | context-builder.service.ts | L0-L4 메모리 컨텍스트 빌드 + 선별 주입 |
| MemoryRendererService | memory-renderer.service.ts | StructuredMemory → 프롬프트 블록 |
| AiTurnLogService | ai-turn-log.service.ts | LLM 호출 로그 기록 (ai_turn_logs 테이블) |
| TokenBudgetService | token-budget.service.ts | 토큰 예산 관리 (2500 토큰), 저우선 블록 트리밍 |
| MidSummaryService | mid-summary.service.ts | 4턴 초과 시 중간 요약 생성 |
| NpcDialogueMarkerService | npc-dialogue-marker.service.ts | 서버 regex + nano LLM 하이브리드 @마커 삽입, 불일치 교정 (Step F) |
| NanoDirectorService | nano-director.service.ts | nano 전처리: 연출 지시서 생성 (첫 문장, NPC 행동, 반복 회피) |
| NanoEventDirectorService | nano-event-director.service.ts | nano 동적 이벤트: 컨셉/NPC/fact/선택지 생성 (LLM Worker 비동기) |
| NpcReactionDirectorService | npc-reaction-director.service.ts | nano 사전결정: NPC 반응(7종)+즉시목표+추상톤 3축(voiceQuality/emotionalUndertone/bodyLanguageMood). 메인 LLM이 추측 대신 결정 표현 — A56 |
| ChallengeClassifierService | challenge-classifier.service.ts | 자유 행동 주사위 스킵: 룰 게이트(NON_CHALLENGE/ALWAYS_CHALLENGE) + 회색지대 nano 분류 (FREE/CHECK) — A56 |
| DialogueGeneratorService | dialogue-generator.service.ts | 2-Stage 대사 분리 파이프라인 (서술+대사 분리, dialogue_slot, 하오체 검증) |
| FactExtractorService | fact-extractor.service.ts | Memory v4: nano 구조화 추출 (entity_facts UPSERT, 반복률 71% 감소) |
| LorebookService | lorebook.service.ts | 키워드 트리거 기반 세계 지식 동적 주입 (NPC/장소/사건/entity_facts) |
| LlmStreamBrokerService | llm-stream-broker.service.ts | 턴별 SSE 채널 관리 (OpenRouter stream:true 토큰 브로드캐스트) |
| StreamClassifierService | stream-classifier.service.ts | 스트리밍 토큰 실시간 분류 (narration vs dialogue, 문장 단위 버퍼링) |
| PromptBuilderService | prompts/prompt-builder.service.ts | 시스템 프롬프트 조립 + NPC 소개 분기 + PRESET_MANNERISMS |
| LlmSettingsController | llm-settings.controller.ts | GET/PATCH /v1/settings/llm (런타임 설정) |

**하위 모듈:**
- `providers/` — OpenAI(OpenRouter 경유), Claude, Gemini, Mock (4 providers) + LlmProviderRegistryService
- `prompts/` — PromptBuilder + system-prompts + intent-system-prompt
- `types/` — LLM 공급자 인터페이스 타입

---

## NPC Personal Memory 유틸

`server/src/engine/hub/memory-collector.service.ts` 내 NPC 개인 기록 관련 함수:

| 함수 | 역할 |
|------|------|
| recordNpcEncounter() | NPC 만남 기록 (턴, 장소, 행동, 결과) → NpcState.personalMemory에 축적 |
| selectNpcMemories() | 현재 턴에 등장하는 NPC의 personalMemory만 선별하여 LLM 컨텍스트에 주입 |

---

## DB 스키마 (20 파일, 22 pgTable)

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

## DB 타입 파일 (42 파일)

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
| index.ts | 통합 export |

---

## 최근 추가/변경 요약 (2026-04)

- **LLM 모듈 확장**: 8 → 17 services. FactExtractor (Memory v4), Lorebook (키워드 트리거 세계 지식), DialogueGenerator (2-Stage 대사 분리), LlmStreamBroker/StreamClassifier (OpenRouter stream:true + SSE + 문장 단위 분류).
- **Party 모듈**: 7 → 8 services. run-participants.service (Phase 3 중간 합류/이탈) 추가.
- **bug_reports 컬럼 확장**: client_snapshot, network_log, client_version 신규 추가. 기존 server_version + ui_debug_log 유지.
- **DB 신규 테이블**: entity_facts (Memory v4), scene_images, campaigns, playtest_results.
- **모듈 신규**: campaigns/, portrait/ (독립 모듈로 분리). scene-image/에 controller 추가.
- **turns.service 경량화**: NanoEventDirector 호출을 LLM Worker로 이관 (nanoCtx만 빌드).
