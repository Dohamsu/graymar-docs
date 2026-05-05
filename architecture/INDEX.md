# 설계 문서 INDEX (architecture/)

> 도메인별 1~2문단 요약. 상세는 각 md 파일 본문 참조.
> CLAUDE.md → INDEX.md → 상세 문서 순으로 진입.

## 빠른 진입

- 세계관/배경: [[architecture/01_world_narrative|world narrative]]
- 전체 아키텍처: [[architecture/04_server_architecture|server architecture]]
- 최근 파이프라인: `26_narrative_pipeline_v2.md`, [[architecture/35_llm_streaming|llm streaming]]
- 최신 전투: [[architecture/41_creative_combat_actions|creative combat actions]](창의 입력), [[architecture/42_combat_ui_buttonform|combat ui buttonform]](버튼형 UI)
- 최신 구현 가이드: `guides/01~06_*.md` (서비스맵·컴포넌트맵·HUB·LLM메모리·RunState상수·장소이미지)

CLAUDE.md에 구현 현황(Phase 표)과 정본 enum 목록이 있고, 본 INDEX는 "어느 설계 문서를 봐야 하는가" 의 선택 기준이다. specs/ 는 원본 스펙(정본), architecture/ 는 통합/연동 관점, guides/ 는 실제 코드 위치 매핑이다.

---

## 도메인별 요약

### 1. 세계관·세계

- [[architecture/01_world_narrative|world narrative]] — 그레이마르 왕국의 정치 음모 배경과 3 루트(부패 폭로/혼란 이익/근위 동맹) 서사 골격. 모든 서술의 톤과 사건 시드의 뿌리.
- [[architecture/09_npc_politics|npc politics]] — 5축 감정(trust/fear/respect/affection/hostility)과 NPC 소개 조건(FRIENDLY 1회/CAUTIOUS 2회/HOSTILE 3회), posture 전환 규칙. Leverage/거래는 부분 구현.
- `Narrative_Engine_v1_Integrated_Spec.md` — Narrative Engine v1 통합 스펙(Incident/4상 시간/Signal/NpcEmotional/Mark/Ending/Operation). 현 HUB 엔진의 기반 설계.
- [[architecture/06_graymar_content|graymar content]] — 프리셋 6종, NPC 43명, 장소 7개, Incident 13건 등 graymar_v1 콘텐츠 스키마와 시드 데이터 구조.

### 2. 게임 엔진

- [[architecture/02_combat_system|combat system]] — 정본 전투 공식(`hitRoll → varianceRoll → critRoll`, floor 적용), BattleState 저장, 거리/각도 처리. [[specs/combat_system|combat system]]와 정합.
- [[architecture/03_hub_engine|hub engine]] — HUB Action-First 파이프라인(플레이어 ACTION → 이벤트 매칭 → ResolveService 1d6+stat), Heat ±8 clamp, 대화 잠금 4턴, questFact 바이패스 규칙.
- [[architecture/08_node_routing|node routing]] — 24 노드 DAG + 3 루트 분기. HUB/LOCATION/COMBAT 전이 그래프와 조건부 분기.
- [[architecture/22_dice_roll_animation|dice roll animation]] — 1d6 판정 주사위 애니메이션과 순차 공식 노출 UX. 현재는 클라이언트 ResolveDisplay에 연동.
- [[architecture/41_creative_combat_actions|creative combat actions]] — 창의 전투 5-Tier 분류 시스템(등록 프롭/즉흥 카테고리/서술 커버/환상 재해석/허공 응시) + PropMatcher + CombatService effects 통합 + LLM 조건부 재해석 블록. 서버 결정론 유지, LLM은 합리적 치환만.
- [[architecture/42_combat_ui_buttonform|combat ui buttonform]] — 전투 UI 버튼 폼(적 카드 클릭 타겟 + 주요 5 버튼 + 특수 펼침 + 아이템 모달). 기존 17개 숫자 리스트 → 5~8 visible (-60%). 서버 로직 불변, 하위 호환 choiceId 유지.

### 3. 서버·데이터

- [[architecture/04_server_architecture|server architecture]] — NestJS 10 모듈, 65+ 서비스, Drizzle ORM 18 테이블, Server-Is-Source-of-Truth 원칙, Idempotency, RNG 결정론 등 정본.
- [[architecture/10_region_economy|region economy]] — 리전별 경제(골드 유동성, 상점 물가)와 장비/세트 연계. 장비 드랍은 완성, 리전별 동적 경제는 부분.
- [[architecture/12_equipment_system|equipment system]] — 장비 드랍/착용, 접미사, 세트 효과, Legendary. Phase 4에서 구현 완료.

### 4. 진행·라우팅

- [[architecture/07_game_progression|game progression]] — HUB 순환 → LOCATION 탐험 → 엔딩의 흐름. HUB 모드 도입 이후 업데이트 필요.
- [[architecture/14_user_driven_code_bridge|user driven code bridge]] — 플레이어 입력 → IntentV3Builder → IncidentRouter → WorldDelta → PlayerThread → Notification의 유저 드리븐 브릿지.
- [[architecture/21_living_world_redesign|living world redesign]] — Living World v2 전면 재설계(LocationDynamicState/WorldFact/NpcSchedule/NpcAgenda/SituationGenerator/ConsequenceProcessor/PlayerGoal).

### 5. LLM·서술 파이프라인

- [[architecture/05_llm_narrative|llm narrative]] — LLM 파이프라인 개요(L0~L4 컨텍스트, Token Budget 2500, LLM is narrative-only 불변). 모든 서술 문서의 진입점.
- [[architecture/11_llm_prompt_caching|llm prompt caching]] — 시스템/정적/동적 블록 분리와 프롬프트 캐싱 전략(OpenAI/Anthropic/OpenRouter).
- [[architecture/25_llm_model_evaluation|llm model evaluation]] — 모델 평가(v1+v2 통합). 현 선택: 메인 Gemini Flash(이후 Gemma4↔Flash Lite 교차 이력 포함) + fallback GPT-4.1 Mini.
- `26_narrative_pipeline_v2.md` — 3-Stage 파이프라인(NanoDirector → 메인 LLM → NanoProcessor)과 Narrative v2 / EventDirector / Procedural Event(`18/19/20` 통합) + AI 구현 가이드라인.
- [[architecture/30_marker_accuracy_improvement|marker accuracy improvement]] — @마커 오류율 개선 3전략(프롬프트 강화 + 서브 LLM 2차 검증 + JSON 모드).
- `31_memory_system_v4.md` — nano 구조화 추출 + `entity_facts` UPSERT + 직전 턴 nano 요약 주입. 메모리 반복률 대폭 감소.
- [[architecture/32_dialogue_split_pipeline|dialogue split pipeline]] — 2-Stage 대사 분리(서술/대사), `dialogue_slot` JSON, 서버 마커 자동 삽입, 하오체 검증+재시도.
- [[architecture/33_lorebook_system|lorebook system]] — 키워드 트리거 기반 세계 지식 동적 주입(NPC knownFacts/장소 비밀/사건 단서/entity_facts 키워드 검색).
- [[architecture/34_player_first_event_engine|player first event engine]] — Player-First 이벤트 엔진(TurnMode 3분류, NPC 5단계 우선순위, contextNpcId, EventMatcher targetNpcId 가중치). 현 최신.
- [[architecture/35_llm_streaming|llm streaming]] — LLM 스트리밍 설계(OpenRouter `stream:true` + `LlmStreamBroker` SSE + `StreamParser` 문장 단위 버퍼 + 2-Phase 렌더링). 폴링 fallback 포함.
- [[architecture/56_npc_reaction_director|npc reaction director]] — NPC Reaction Director(추상 톤 3축 nano 사전결정) + ChallengeClassifier(자유 행동 주사위 스킵) + speechStyle 어구 예시 추상화(9 NPC) + 마커 substring 합쳐짐 자동 복구. 어휘 폭주 39.7% → 6.2% 해소(-84%). NpcSignatureGenerator/SIGFIX/MEMBOOST는 P0 검증으로 폐기.

### 6. UI·클라이언트

- [[architecture/15_notification_system|notification system]] — Notification 아키텍처(설계/UI/브릿지 통합). 기존 `15/16/17` 3개 문서가 하나로 통합됨. 클라 실제 연결은 [[guides/02_client_component_map|client component map]].
- [[architecture/23_dialogue_ui_redesign|dialogue ui redesign]] — 대화 UI 고도화(메신저 형태, NPC 카드 연출, 홑따옴표 강조).

### 7. 멀티플레이

- [[architecture/24_multiplayer_party_system|multiplayer party system]] — 파티 Phase 1+2+3 통합 설계(CRUD/초대/SSE 채팅/로비/동시 턴/통합 판정/3인칭 서술/이동 투표/보상 분배/런 통합). 구현 API는 CLAUDE.md Endpoint 표와 server `party/` 모듈 참조.

### 8. 엔딩·아카이브

- [[architecture/39_ending_journey_archive|ending journey archive]] — 엔딩 직전/직후 연출 강화(Part B MIN_TURNS 가드, commitTurnRecord 순서 수정, arcRoute 12분기 에필로그, personalClosing 템플릿, SoftDeadline Signal + DeadlineBanner + LLM deadlineContext) + 여정 아카이브 Phase 1(`ending_summary` jsonb, SummaryBuilderService, EndingsController, EndingsListScreen/JourneySummaryScreen, lazy fallback).

### 9. 소지품·아이템

- [[architecture/40_inventory_item_integrity|inventory item integrity]] — 소지품 UX 개선(교체 확인 모달, USABLE_ITEMS 동적화 via `usableInHub`, EquipmentDropToast, 에러 한국어화 10종) + LLM-실획득 아이템 정합성(시스템 프롬프트 구체 증여 금지 규칙 + `[이번 턴 획득 아이템]` 블록 + `EventItemReward` payload 경로) + 콘텐츠 매핑(KEY_ITEM 3종 + 희귀 장비 2종).

### 10. 기타

- `Context Coherence Reinforcement.md` — 컨텍스트 일관성 강화 원칙(씬 연속성 7규칙, sceneFrame 3단계 억제, 씬 이벤트 1턴 유지). 모든 서술 파이프라인 문서의 공통 제약.
- `fixplan_history.md` — 완료된 플레이테스트 패치 내역(기존 `fixplan3/4/5` 통합). 히스토리 참조용이며, 신규 이슈는 본 히스토리와 중복되지 않도록 확인 필요.

---

## 상호 참조 맵

```
[세계관]
01 ─┬─► 06 (콘텐츠 시드)
    └─► 09 (NPC 정치/감정)
09 ◄── Narrative_Engine_v1 (Incident/Mark/Ending)

[엔진]
02 (전투) ─┬─► 08 (노드 라우팅)
           ├─► 41 (창의 전투 — 5-Tier 분류 + PropMatcher + 재해석)
           └─► 42 (전투 UI 버튼 폼 — 적 카드 타겟 + 5 주요 버튼)
03 (HUB)  ─┬─► 07 (게임 진행)
           └─► 14 (유저 드리븐 브릿지)
03 ◄── 21 (Living World v2: SitGen/WorldFact)
22 (주사위)   ─► 클라 ResolveDisplay

[LLM 파이프라인]
05 (개요)
 ├─► 11 (프롬프트 캐싱)
 ├─► 25 (모델 평가)
 ├─► 26 (3-Stage 파이프라인 v2)
 └─► 35 (스트리밍)
26 ─┬─► 30 (마커 정확도)
    ├─► 31 (Memory v4)
    ├─► 32 (대사 분리)
    ├─► 33 (로어북)
    └─► 34 (Player-First 이벤트)
archive/28 (Nano Event — 배경 설계)   ─► 34 (Player-First, 현행)

[UI]
15 (알림)   ─► guides/02 (client component map)
23 (대화)   ─► guides/02

[파티]
24 (설계)   ─► guides/01 (server party/ 모듈) + CLAUDE.md API 표
```

---

## 도메인별 최신 업데이트 기준 (2026-04-22)

| 도메인       | 최신 문서                          | 상태                |
| ------------ | ---------------------------------- | ------------------- |
| 세계/NPC     | 01, 06, 09                         | 구현됨              |
| 전투         | 02, 08, **41, 42**                 | 구현됨 (창의 Tier + 버튼 UI) |
| HUB/진행     | 03, 07, 14                         | 구현됨 (07 부분 업데이트 필요) |
| Living World | 21                                 | 구현됨              |
| 서버/데이터  | 04, 10, 12                         | 구현됨 (10 리전 경제 부분) |
| LLM 서술     | 05, 11, 26, 35                     | 구현됨 (스트리밍)   |
| 모델 평가    | 25                                 | 참고                |
| 메모리       | 31                                 | 구현됨 (v4)         |
| 대사/마커    | 30, 32, 33                         | 구현됨              |
| 이벤트 엔진  | 34                                 | 구현됨 (Player-First, 28은 archive 배경) |
| UI/클라      | 15, 23, **42**                     | 구현됨              |
| 파티         | 24                                 | 구현됨 (Phase 1~3)  |
| 주사위/UX    | 22                                 | 구현됨              |
| 엔딩/아카이브 | 39                                 | 구현됨 (Phase 1)    |
| 소지품/아이템 | 40                                 | 구현됨 (UX 개선 + LLM 정합성) |
| 창의 전투    | **41, 42** (신규)                  | 구현됨 (MVP + 버튼 UI) |
| 컨텍스트 일관성 | Context Coherence Reinforcement | 적용됨              |
| 플레이테스트 | fixplan_history.md                 | 히스토리            |

---

## 주의: 중복·구판 방지

- [[architecture/25_llm_model_evaluation|llm model evaluation]] 는 v1+v2 통합. 구판(v1) 모델 선택은 과거 이력일 뿐, 실제 현행 선택은 v2 본문과 CLAUDE.md 환경변수 표 기준.
- [[architecture/07_game_progression|game progression]] 는 HUB 모드 도입 이전 서술 일부 남아 있음 — 실제 구현은 [[architecture/03_hub_engine|hub engine]] + [[architecture/14_user_driven_code_bridge|user driven code bridge]] + [[architecture/21_living_world_redesign|living world redesign]] 조합을 우선.
- [[architecture/10_region_economy|region economy]] 의 리전 동적 경제 파트는 부분 구현. 장비/세트는 [[architecture/12_equipment_system|equipment system]] 가 정본.
- [[architecture/15_notification_system|notification system]] 는 기존 `15/16/17` 3개 문서 통합본. 구 파일명 참조는 본 문서로 리다이렉트.
- `fixplan_history.md` 는 완료 이슈 아카이브. 신규 플레이테스트 이슈 리포트는 `playtest-reports/` 와 별개.
- 아카이브됨(2026-04-22):
  · `archive/27_image_asset_plan.md` — 에셋 생성 계획 (부분 구현, 현행은 content/ 하위 실측)
  · `archive/28_nano_event_director.md` — Player-First의 배경 설계, 현행은 [[architecture/34_player_first_event_engine|player first event engine]]
  · `archive/37_streaming_transition_issues.md` — 36과 중복
  · `archive/38_stream_vs_nonstream_comparison.md` — 35와 중복
- 폐기됨(이미 파일 없음): [[specs/combat_resolve_engine_v1|combat resolve engine v1]] — floor 미적용 오류 버전. 정본은 [[specs/combat_system|combat system]] + [[architecture/02_combat_system|combat system]].
- 번호 공백(13, 27, 28, 29, 37, 38 등)은 합쳐졌거나 아카이브된 문서의 흔적 — 신규 문서는 빈 번호 대신 마지막 번호 이후(43~)를 사용.

---

## 진입 가이드 (작업 유형별)

| 작업 유형                | 먼저 볼 문서                                                                 |
| ----------------------- | -------------------------------------------------------------------------- |
| 새 서버 서비스 추가      | [[architecture/04_server_architecture|server architecture]] → [[guides/01_server_module_map|server module map]]             |
| LLM 프롬프트 수정        | [[architecture/05_llm_narrative|llm narrative]] → `26_narrative_pipeline_v2.md` → [[guides/04_llm_memory_guide|llm memory guide]] |
| 스트리밍/SSE 관련        | [[architecture/35_llm_streaming|llm streaming]] → [[guides/04_llm_memory_guide|llm memory guide]]                    |
| 이벤트/NPC 매칭          | [[architecture/34_player_first_event_engine|player first event engine]] → [[architecture/03_hub_engine|hub engine]] → [[guides/03_hub_engine_guide|hub engine guide]] |
| 메모리/컨텍스트 블록     | `31_memory_system_v4.md` → [[guides/04_llm_memory_guide|llm memory guide]]                 |
| @마커/대사 분리          | [[architecture/30_marker_accuracy_improvement|marker accuracy improvement]] + [[architecture/32_dialogue_split_pipeline|dialogue split pipeline]]      |
| 전투 밸런스/판정         | [[architecture/02_combat_system|combat system]] → [[specs/combat_system|combat system]]                           |
| 창의 전투(자유 입력)     | [[architecture/41_creative_combat_actions|creative combat actions]] → `server/src/engine/combat/prop-matcher.service.ts` |
| 전투 UI 변경             | [[architecture/42_combat_ui_buttonform|combat ui buttonform]] → `client/src/components/battle/*`            |
| HUB 엔진 이슈            | [[architecture/03_hub_engine|hub engine]] → [[architecture/21_living_world_redesign|living world redesign]] → [[guides/03_hub_engine_guide|hub engine guide]] |
| 콘텐츠(시드 데이터) 수정 | [[architecture/06_graymar_content|graymar content]] → `content/graymar_v1/`                            |
| 클라이언트 UI 변경       | [[guides/02_client_component_map|client component map]] (+ `15`, `23`)                         |
| 파티 기능                | [[architecture/24_multiplayer_party_system|multiplayer party system]] → server `party/` 모듈                    |
| 플레이테스트 이슈 회귀   | `fixplan_history.md` (중복 확인)                                           |
