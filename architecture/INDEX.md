# 설계 문서 INDEX (architecture/)

> 도메인별 1~2문단 요약. 상세는 각 md 파일 본문 참조.
> CLAUDE.md → INDEX.md → 상세 문서 순으로 진입.

## 빠른 진입

- 세계관/배경: [[architecture/01_world_narrative|world narrative]]
- 전체 아키텍처: [[architecture/04_server_architecture|server architecture]]
- 최근 파이프라인: `26_narrative_pipeline_v2.md`, [[architecture/35_llm_streaming|llm streaming]]
- 최신 전투: [[architecture/41_creative_combat_actions|creative combat actions]](창의 입력), [[architecture/42_combat_ui_buttonform|combat ui buttonform]](버튼형 UI)
- 최신 구현 가이드: `guides/01~08_*.md` (서비스맵·컴포넌트맵·HUB·LLM메모리·RunState상수·장소이미지·LivingWorld·파티)

CLAUDE.md에 구현 현황(Phase 표)과 정본 enum 목록이 있고, 본 INDEX는 "어느 설계 문서를 봐야 하는가" 의 선택 기준이다. specs/ 는 원본 스펙(정본), architecture/ 는 통합/연동 관점, guides/ 는 실제 코드 위치 매핑이다.

---

## 도메인별 요약

### 1. 세계관·세계

- [[architecture/01_world_narrative|world narrative]] — 그레이마르 왕국의 정치 음모 배경과 3 루트(부패 폭로/혼란 이익/근위 동맹) 서사 골격. 모든 서술의 톤과 사건 시드의 뿌리.
- [[architecture/09_npc_politics|npc politics]] — 5축 감정(trust/fear/respect/affection/hostility)과 NPC 소개 조건(FRIENDLY 1회/CAUTIOUS 2회/HOSTILE 3회), posture 전환 규칙. Leverage/거래는 부분 구현.
- `Narrative_Engine_v1_Integrated_Spec.md` — Narrative Engine v1 통합 스펙(Incident/4상 시간/Signal/NpcEmotional/Mark/Ending/Operation). 현 HUB 엔진의 기반 설계.
- [[architecture/06_graymar_content|graymar content]] — 프리셋 6종, NPC 43명, 장소 7개, Incident 13건 등 graymar_v1 콘텐츠 스키마와 시드 데이터 구조.
- [[architecture/63_multi_scenario_content_decoupling|multi scenario content decoupling]] — 멀티 시나리오 선행작업 ②~⑤: 엔진 하드코딩 콘텐츠 ID 외부화(표시명/활동장소/별칭/프롤로그/L0 테마), DAG graph.json화, 시스템 프롬프트 세계관 주입, silverdeen_v1 미니 팩 + scenarioId 런 경로. 단일 활성 시나리오 정책(① 멀티 팩 로더는 후속).
- [[architecture/70_campaign_progression|campaign progression]] — ✅ 구현됨. 캠페인 순차 진행(한 캐릭터 이어달리기, 되돌아가기 불가): `?? 'DOCKWORKER'` 폴백 7곳 제거(star_sand 진입 400 언블록) + 집합 기반 다음 순번 게이팅(status COMPLETED/CURRENT/LOCKED) + 캐릭터 정체성(gender/이름/특성) 이월 + RUN_ABORTED 재도전 시맨틱. 캐리오버 엔진 ~75% 기구현 위 배선.
- [[architecture/64_npc_name_reveal_integrity|npc name reveal integrity]] — NPC 이름 공개 무결성: 롤백-재소개 상쇄(A)·소개 힌트 실명 오염(C)·injected 2턴 분리(D)·별칭 접두 중복(E) 수정 + 핍 케이스 실증. B(AppearanceIntro 후보화)는 후속.
- [[architecture/73_scenario_differentiation|scenario differentiation]] — 📎 설계(제안, 미구현). 시나리오 동형 수렴 층위 진단(첫인상=프리셋 명명 / 중반=이벤트 밀도 / 종반=ArcRoute 삼각) + Tier A(콘텐츠 탈템플릿)/B(packMeters·아크 팩화)/C 개선안 + 검증 지표 6종. packMeters(B1)는 별빛모래에 선반영.

### 2. 게임 엔진

- [[architecture/02_combat_system|combat system]] — 정본 전투 공식(`hitRoll → varianceRoll → critRoll`, floor 적용), BattleState 저장, 거리/각도 처리. [[specs/combat_system|combat system]]와 정합.
- [[architecture/03_hub_engine|hub engine]] — HUB Action-First 파이프라인(플레이어 ACTION → 이벤트 매칭 → ResolveService 1d6+stat), Heat ±8 clamp, 대화 잠금 4턴, questFact 바이패스 규칙.
- [[architecture/08_node_routing|node routing]] — 24 노드 DAG + 3 루트 분기. HUB/LOCATION/COMBAT 전이 그래프와 조건부 분기.
- [[architecture/22_dice_roll_animation|dice roll animation]] — 1d6 판정 주사위 애니메이션과 순차 공식 노출 UX. 현재는 클라이언트 ResolveDisplay에 연동.
- [[architecture/41_creative_combat_actions|creative combat actions]] — 창의 전투 5-Tier 분류 시스템(등록 프롭/즉흥 카테고리/서술 커버/환상 재해석/허공 응시) + PropMatcher + CombatService effects 통합 + LLM 조건부 재해석 블록. 서버 결정론 유지, LLM은 합리적 치환만.
- [[architecture/42_combat_ui_buttonform|combat ui buttonform]] — 전투 UI 버튼 폼(적 카드 클릭 타겟 + 주요 5 버튼 + 특수 펼침 + 아이템 모달). 기존 17개 숫자 리스트 → 5~8 visible (-60%). 서버 로직 불변, 하위 호환 choiceId 유지.
- [[architecture/65_economy_loop_v1|economy loop v1]] — 경제 루프 v1: 단서·진전 사례금(quest.json rewards — factGold/transitionGold, 총량 유한) + 정보 보류 턴 BRIBE 선택지 노출(bribeOpportunity) + BRIBE 비용 config 외부화(-6/-3). 부록 B: 엔딩 완주 평가 P1~P4(이동 상용구 KW_OVERRIDE·작별 잠금 해제·접두 융합 별칭·전환 장비 보상). 부록 C: 마커·대사 정합 마감(콜론 라벨 3-Tier). 부록 D: 엔딩 턴 피날레 디렉티브.

### 3. 서버·데이터

- [[architecture/80_pack_asset_pool|pack asset pool]] — ✅ 구현됨. 팩 에셋 풀 이미지 자동 매칭: 소유자가 content/<pack>/assets/에 이미지 투입 → sync_pack_assets.py(ASCII 슬러그 정규화 — URL 실명 치환 404 실측 방어) → 저작 NPC 결정론 배정 + 동적 NPC 등록 시 배정(성별·키워드 스코어, 런 내 고정·중복 배제) + 클라 장소 리졸버. 풀 비면 완전 무동작. 카른홀트 최초 적용 (2026-07-19).
- [[architecture/81_day_night_system|day night system]] — ✅ 구현·배포. 밤낮 이중 시간계 근본 해소: ①행동 가중 timeCost(사교 0/이동·휴식 2/기타 1) ②전환 서술 주입(recentPhaseTransition → 전환 턴만 [시간대 전환] 디렉티브) ③4상 UI 승격(phaseV2·day, 황혼 오표기 해소) ④**이중 시간계 통합**(deriveTimePhaseFromV2 — v1 advanceTime 토글 폐지, timePhase=phaseV2 미러, 전투 경로 불일치 해소, 불변식 49). 실측 전환 5회→1회. 잔여: 시간대별 특이 이벤트(콘텐츠) (2026-07-20).
- [[architecture/82_npc_dialogue_naturalness|npc dialogue naturalness]] — ✅ 구현·배포. A: 어체 자기모순 3건 교정(speechRegister↔speechStyle, 펠릭스·라이라·올드릭 HAPSYO→HAOCHE, 3팩 스캔 FP 21/24). B: 자연스러움 3종 — #5 감시자 advance-or-dismiss(정적 "훑어본다" 반복→진전/퇴장) · #6 제스처 앵커 제거 L0(recommendPool 삭제)+L1(frequency/presence_penalty, "목덜미" 0회) · #7 첫 조우 개방 깊이 티어(trust+encounterCount 긍정 프레이밍). 저모델 반복 억제 원칙(불변식 50, memory feedback_concrete_vocab_anchor) (2026-07-20).

- [[architecture/04_server_architecture|server architecture]] — NestJS 10 모듈, 65+ 서비스, Drizzle ORM 18 테이블, Server-Is-Source-of-Truth 원칙, Idempotency, RNG 결정론 등 정본.
- [[architecture/77_god_method_refactoring|god method refactoring]] — 대형 파일 구조 개선(✅ 전 Phase 완료 2026-07-18). P1 prompt-builder -62% · P2 context-builder -64% · P3 turns.service Inner -56% · P4 llm-worker Inner -50%(금지선 4곳 마킹) · 전투/DAG -41%(골드 무바닥 수정) · P5 클라 3파일 -26~-45%. 매 스텝 유닛 green + playtest/E2E 게이트, 회귀 0. §9 진행 로그가 정본. 잔여: §5 재비대화 래칫(ESLint max-lines warn)만.
- [[architecture/10_region_economy|region economy]] — 리전별 경제(골드 유동성, 상점 물가)와 장비/세트 연계. 장비 드랍은 완성, 리전별 동적 경제는 부분.
- [[architecture/12_equipment_system|equipment system]] — 장비 드랍/착용, 접미사, 세트 효과, Legendary. Phase 4에서 구현 완료.

### 4. 진행·라우팅

- [[architecture/07_game_progression|game progression]] — HUB 순환 → LOCATION 탐험 → 엔딩의 흐름. HUB 모드 도입 이후 업데이트 필요.
- [[architecture/14_user_driven_code_bridge|user driven code bridge]] — 플레이어 입력 → IntentV3Builder → IncidentRouter → WorldDelta → PlayerThread → Notification의 유저 드리븐 브릿지.
- [[architecture/21_living_world_redesign|living world redesign]] — Living World v2 전면 재설계(LocationDynamicState/WorldFact/NpcSchedule/NpcAgenda/SituationGenerator/ConsequenceProcessor/PlayerGoal).
- [[architecture/71_campaign_free_scenario_selection|campaign free scenario selection]] — 캠페인 자유 시나리오 선택(원점 정책 폐기, AVAILABLE/IN_PROGRESS/COMPLETED) + creation-bundle API(팩 프리셋·특성 서빙) + 캐릭터 생성 6단계 통일 + 장비 carrySnapshot 이월 + 소모품 골드 환산 + campaignSummary 서사 이월. 70의 순차 게이팅을 대체.

### 5. LLM·서술 파이프라인

- [[architecture/05_llm_narrative|llm narrative]] — LLM 파이프라인 개요(L0~L4 컨텍스트, Token Budget 2단 — 메모리 2500+총량 백스톱 16,000자 arch/79, LLM is narrative-only 불변). 모든 서술 문서의 진입점.
- [[architecture/11_llm_prompt_caching|llm prompt caching]] — 시스템/정적/동적 블록 분리와 프롬프트 캐싱 전략(OpenAI/Anthropic/OpenRouter).
- [[architecture/25_llm_model_evaluation|llm model evaluation]] — 모델 평가(v1+v2 통합). **현 운영(2026-05): 메인 Gemma 4 26B MoE (OpenRouter) + fallback GPT-4.1 Mini.** Qwen3 235B → Gemini Flash Lite → Flash 교차 이력을 거쳐 Gemma 4 로 복귀.
- `26_narrative_pipeline_v2.md` — 3-Stage 파이프라인(NanoDirector → 메인 LLM → NanoProcessor)과 Narrative v2 / EventDirector / Procedural Event(`18/19/20` 통합) + AI 구현 가이드라인.
- [[architecture/30_marker_accuracy_improvement|marker accuracy improvement]] — @마커 오류율 개선 3전략(프롬프트 강화 + 서브 LLM 2차 검증 + JSON 모드).
- `31_memory_system_v4.md` — nano 구조화 추출 + `entity_facts` UPSERT + 직전 턴 nano 요약 주입. 메모리 반복률 대폭 감소.
- [[architecture/32_dialogue_split_pipeline|dialogue split pipeline]] — 2-Stage 대사 분리(서술/대사), `dialogue_slot` JSON, 서버 마커 자동 삽입, 하오체 검증+재시도.
- [[architecture/33_lorebook_system|lorebook system]] — 키워드 트리거 기반 세계 지식 동적 주입(NPC knownFacts/장소 비밀/사건 단서/entity_facts 키워드 검색).
- [[architecture/34_player_first_event_engine|player first event engine]] — Player-First 이벤트 엔진(TurnMode 3분류, NPC 5단계 우선순위, contextNpcId, EventMatcher targetNpcId 가중치). 현 최신.
- [[architecture/35_llm_streaming|llm streaming]] — LLM 스트리밍 설계(OpenRouter `stream:true` + `LlmStreamBroker` SSE + `StreamParser` 문장 단위 버퍼 + 2-Phase 렌더링). 폴링 fallback 포함.
- [[architecture/43_sudden_action_context_preservation|sudden action context preservation]] — 돌발행동(살해 등 고충격 행위) 분류 + N턴 맥락 보존. SuddenActionDetectorService(engine/hub) 구현.
- [[architecture/44_npc_dialogue_quality_v2|npc dialogue quality v2]] — 환각 융합 별칭 선제 차단(이슈①, marker) + 크로스 NPC 주제 반복 해소(이슈②, ThemeClassifier + narrativeThemes 기록).
- [[architecture/45_npc_free_dialogue|npc free dialogue]] — NPC 자유 대화: 키워드 트리거 + daily_topic 잡담 풀 + FACT/DAILY 공개 항목. "알고 있는 전부가 단서" 문제 해소.
- [[architecture/46_fact_pool_continuity|fact pool continuity]] — Fact를 일급 객체(facts.json)로 분리, fact 매칭이 NPC를 강제 등장시키지 않도록 NPC 결정과 분리. NPC 점프 근본 차단.
- [[architecture/47_dialogue_quality_audit|dialogue quality audit]] — NPA(NPC 대사 품질) 정량 감사 시스템 설계. `scripts/e2e/audit/` 구현.
- [[architecture/48_npc_discoverability_v1|npc discoverability v1]] — NPC 발견 가능성 Layer 설계(NpcWhereaboutsService 등). 49로 통합.
- [[architecture/49_npc_resolver_authority|npc resolver authority]] — NpcResolverService 단일 권한자: 텍스트매칭/IntentV3/대화잠금/Nano/이벤트배정 5단계 우선순위 통합.
- [[architecture/50_natural_dialogue_v1|natural dialogue v1]] — 📜 폐기. 전 phase 메트릭 후퇴로 전체 롤백, 51로 대체.
- [[architecture/51_npc_distinctness_v1|npc distinctness v1]] — A50 회고 + NPA v2 메트릭 + R1 회피 어휘 룰 + CORE mannerism 확장.
- [[architecture/55_npa_metric_v2|npa metric v2]] — NPA 메트릭 v2: utterance 단위 자기 NPC register/호칭 평가로 다중 NPC 정확 측정.
- [[architecture/56_npc_reaction_director|npc reaction director]] — NPC Reaction Director(추상 톤 3축 nano 사전결정) + ChallengeClassifier(자유 행동 주사위 스킵) + speechStyle 어구 예시 추상화(9 NPC) + 마커 substring 합쳐짐 자동 복구. 어휘 폭주 39.7% → 6.2% 해소(-84%). NpcSignatureGenerator/SIGFIX/MEMBOOST는 P0 검증으로 폐기.
- [[architecture/58_fact_reveal_unification|fact reveal unification]] — 단서 기록·서술 단일화: 주제 우선 fact 선택(selectRevealableFact) + `ui.questReveal` 전달 + 미기록 detail 보류 가이드. "발견 로그와 NPC 대사가 다른 단서" 데스싱크 근본 차단.
- [[architecture/59_fact_dialogue_followup_plan|fact dialogue followup plan]] — 58 검증 실측 3건 수정: 판정 NPC = 서술 NPC 정합(부분 이름 매칭) + [단서 방향] nextHint ui 전달 복구 + HINT_MODES off-by-one. ✅ 구현됨.
- [[architecture/60_clue_flow_tuning|clue flow tuning]] — 흐름 점검 4건: LLM 워커 runState lost update 해소(P0, fresh 부분 패치) + 주제 불일치 fallback 금지(인계 양보) + [단서 방향] 공개 턴 이월 + 비주제 공개 확률 게이트. ✅ 구현됨.
- [[architecture/61_choice_recommendation_tuning|choice recommendation tuning]] — 선택지 추천 점검 P1~P6: nano 미리보기 머리150+꼬리350(끝 NPC 질문 반영) + dialogueAct 전달(작별 턴 자기모순 차단) + 직전 라벨 반복 금지 + go_hub 라벨-결과 정합 + modifier/hint 복원 + "~한다" 문체 통일. ✅ 구현됨 (2026-07-09).
- [[architecture/62_latency_optimization|latency optimization]] — LLM 턴 레이턴시 최적화 4건: Track1∥NpcReaction 병렬 + Challenge∥이벤트매칭 병렬 + 워커 즉시 킥(wake) + 첫 토큰 타임아웃(LLM_FIRST_TOKEN_TIMEOUT_MS→non-stream fallback). 부록 A: OpenRouter provider sort/ignore. 병목은 nano 직렬 체인. ✅ 구현됨 (2026-07-09).
- [[architecture/78_narrative_opener_pronoun_cycle|narrative opener pronoun cycle]] — 서술 개시어·대명사 편중 억제: D5 센서 + 임계 3→2 + 대명사 12종 합산(1차 -20.2%) + **2차 [서술 지칭 규칙] 디렉티브**(대화 턴 상시·주어 생략 기본·별칭 문단 1회 — 풍선효과 방어 3반복 튜닝). 대화 턴 29~35%→18.8% (chatty 10.0%, devotee 단일 NPC 잠금은 잔존 — 후처리 옵션만 남음). 즉흥 별칭 가설 실측 기각. ✅ 2차까지 완료 (2026-07-19).
- [[architecture/79_prompt_token_optimization|prompt token optimization]] — ✅ P3~P4 완료. 측정 기반 프롬프트 예산: P1 회고 1,556턴(hard 규칙 15k 강건/soft 문체 11k 절벽) → 예산 10k → 실행 4파트(재시도 스킵 16.5%→0 · 시스템 -62% · NPC 클러스터 압축 · 총량 백스톱 16,000자). 최종 avg 7,495tok(-31%)·절벽 턴 0%·게이트 7런 10/10·회귀 0. 대화 턴 대명사 기저는 크기 무관 확정(교란 재해석 §9.1) — arch/78 백로그 이관 (2026-07-19).
- [[architecture/66_npc_self_introduction|npc self introduction]] — NPC 자기소개 사전 확정 3단 사다리: nano 실명 대사 사전 생성(서버 검증+어체 템플릿) → 프롬프트 positive 주입 → 미반영 시 서버 삽입(지연 0턴). 전 성향 통일 임계(FRIENDLY/FEARFUL 1회·CAUTIOUS 2회·CALCULATING/HOSTILE 3회), 소개 턴 별칭 마커→다음 턴 실명(IntroMarkerNorm). 성사 0%→5/5 실측 — 불변식 15의 정본.
- [[architecture/67_nano_engine_audit|nano engine audit]] — Nano 엔진 전수 감사: 요청 단위 timeoutMs(light 5s/dialogue 10s 죽은 설정 부활) + 워커 이중 처리 락(.returning 선점) + NpcReaction JSON 재시도 + nano 모델 env 고정. 부록 A·B: 카드 정합 근본 수정(V8 3중 원인)·테스트 시스템 감사. 부록 D: 자유 대화 정합 4종(언급 질문 가드·화자 단일화·작별 소개 이월·재탕 센서).
- [[architecture/72_npc_reaction_authority_unification|npc reaction authority unification]] — NPC 반응 권한 통합: 목격자 반응(Layer 3)↔NpcReactionDirector 이중 권한 해소 — 대화 상대 목격자 루프 제외(② 단일 권한) + 당턴 1회 발화 + posture 우선 trust 밴드(witness-reaction.core) + [직전 목격] nano 블록. 버그 599a00a1.
- [[architecture/74_autonomous_narrative_direction|autonomous narrative direction]] — 📎 논의. "핵심 NPC+세계관만 저작, LLM이 스토리·NPC 생성" 바람 ↔ 불변식 1·2 충돌 지점 실측 + 3층 하이브리드 디렉터 모드 + 자율 L0~L3 + 기본값편향 역설. 상세설계는 75로 확정.
- [[architecture/75_autonomous_pack_design|autonomous pack design]] — 📐 상세설계 확정 → **P0~P6+P8 구현·배포**(2026-07-16, karnholt_v1 AUTONOMOUS 팩). 진상 선확정 Plot Seed(PlotSeedGenerator+검증/폴백) + Emergent Director 비트 선계산(PlotDirector, 워커 비동기 CAS)+동기 채택(beat-gravity, 불변식 47 의도 정합) + 동적 NPC(dynamic-npc stub) + 규명율 엔딩(autonomous-ending) + 킬스위치. §19 P8 계측: 디렉터 존재감 낮음(채택 0~2/12턴) — stale 창 확대 vs 수용 소유자 결정 대기.
- [[architecture/69_npc_living_presence|npc living presence]] — B축(살아있는 NPC), B0~B4 ✅ 구현. B0 계측(정보 편향 88% 실측)·B1 반응 자기목적 주입(INFO 88→40%)·B2 잡담 활동 결합·B3 재등장 연속성·B4 NPC 간 세계(잡담 경로 관계 근황 발화 selectRelationMentionCore, introduced 후보 한정+rel: 쿨다운; 목격 파이프 위치 판정 버그 수정으로 부활). 공용 헬퍼 getNpcSchedulePhaseEntry/getNpcCurrentActivity 4곳 재사용. 후속: 어미 다양화(26명 재배정·HAEYO 제거) + 어체 검증 경로 **완결** — C1 하오체 강제 후처리 제거 → C2 화자 인지 계측(llm_speech_audit, 검증기 버그 7건 발견·수정) → C2.5 forbidHint·검증기 정비 → **C2.6 시스템 프롬프트 하오체 전역 강제 레거시 정정(진짜 원인)** → 하오체 침식 80→9.1%로 C3(선별 재생성) 미발동 확정. 잔여 과제는 문서 §7 통합. A축(선제 단서 억제)은 arch/68 부록 M.

### 6. UI·클라이언트

- [[architecture/15_notification_system|notification system]] — Notification 아키텍처(설계/UI/브릿지 통합). 기존 `15/16/17` 3개 문서가 하나로 통합됨. 클라 실제 연결은 [[guides/02_client_component_map|client component map]].
- [[architecture/23_dialogue_ui_redesign|dialogue ui redesign]] — 대화 UI 고도화(메신저 형태, NPC 카드 연출, 홑따옴표 강조).
- [[architecture/68_uiux_audit_v1|uiux audit v1]] — 헤드리스 신규 유저 경로 실사 리뷰 + 6건 수정(인물 도감 조우 필터+이어하기 복원, 모바일 상태줄/인물 탭, 호외 모달 타이밍, "(으)로" 조사, 개발자 정보 dev 게이트). 부록 A: C-2~C-7 폴리싱(어포던스·배너·뮤트 팔레트·라벨·lucide·체크박스). 부록 B: C-1 거점 사랑방 개방(LOC_TAVERN/LOC_SD_INN hubAccessible, 서버 0줄). 부록 C: 자유 입력 발견성(코치마크+placeholder 예시+튜토리얼). 부록 D: NanoChoiceNpcFix(nano 선택지 sourceNpcId 오염 서버 검증 게이트, 버그 5f31d803). 부록 E: 상점 노출 동선(구매 dead path 부활 + ui.shops 클라 소비 — 칩/진열/구매 버튼). 부록 F: 3사이클 완주 프로세스 + 아크 커밋 HUB 명시 분기(routeCommitChoices)·봇 확장·어휘 계측·도착 디렉티브 완화. 부록 G: 선술집 BG 초상화 6종(비올라 여성 개명·헬가 gender 정정). 부록 H: 오웬 별칭 반복(저장 직전 최종 정리 + 우호 상주 appearanceCount 조기 소개). 백로그 전량 해소.

### 7. 멀티플레이

- [[architecture/24_multiplayer_party_system|multiplayer party system]] — 파티 Phase 1+2+3 통합 설계(CRUD/초대/SSE 채팅/로비/동시 턴/통합 판정/3인칭 서술/이동 투표/보상 분배/런 통합). 구현 API는 CLAUDE.md Endpoint 표와 server `party/` 모듈 참조.

### 8. 엔딩·아카이브

- [[architecture/39_ending_journey_archive|ending journey archive]] — 엔딩 직전/직후 연출 강화(Part B MIN_TURNS 가드, commitTurnRecord 순서 수정, arcRoute 12분기 에필로그, personalClosing 템플릿, SoftDeadline Signal + DeadlineBanner + LLM deadlineContext) + 여정 아카이브 Phase 1(`ending_summary` jsonb, SummaryBuilderService, EndingsController, EndingsListScreen/JourneySummaryScreen, lazy fallback).

### 9. 소지품·아이템

- [[architecture/40_inventory_item_integrity|inventory item integrity]] — 소지품 UX 개선(교체 확인 모달, USABLE_ITEMS 동적화 via `usableInHub`, EquipmentDropToast, 에러 한국어화 10종) + LLM-실획득 아이템 정합성(시스템 프롬프트 구체 증여 금지 규칙 + `[이번 턴 획득 아이템]` 블록 + `EventItemReward` payload 경로) + 콘텐츠 매핑(KEY_ITEM 3종 + 희귀 장비 2종).

### 10. 기타

- `Context Coherence Reinforcement.md` — 컨텍스트 일관성 강화 원칙(씬 연속성 7규칙, sceneFrame 3단계 억제, 씬 이벤트 1턴 유지). 모든 서술 파이프라인 문서의 공통 제약.
- `fixplan_history.md` — 완료된 플레이테스트 패치 내역(기존 `fixplan3/4/5` 통합). 히스토리 참조용이며, 신규 이슈는 본 히스토리와 중복되지 않도록 확인 필요.
- [[architecture/76_market_alignment_direction|market alignment direction]] — 시장 조사 대응 방향: AI 텍스트 RPG 이용자 긍/부정 요인 ↔ 현 구조 대조 + D1(의도 존중 가드=불변식 47)·D2(판정 투명성 UI)·D3(actionType 탈버킷+감정 행동화)·D4(반복 계측)·D5(과금 3원칙) ✅ 구현. 잔여는 D6(저작 도구)뿐. §5 진행 체크리스트.
- `36_llm_pipeline_changelog_20260417.md` — 📜 이력. 2026-04-17 LLM 파이프라인·렌더링·품질 수정 Before/After 정리.

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

## 도메인별 최신 업데이트 기준 (2026-07-18)

| 도메인       | 최신 문서                          | 상태                |
| ------------ | ---------------------------------- | ------------------- |
| 세계/NPC     | 01, 06, 09, **63, 64, 66, 69**     | 구현됨 (멀티 시나리오 + 이름 공개 무결성 + 자기소개 + Living Presence) |
| 전투         | 02, 08, **41, 42**                 | 구현됨 (창의 Tier + 버튼 UI + arch/76 전투 기만) |
| HUB/진행     | 03, 07, 14, **70, 71**             | 구현됨 (07 부분 업데이트 필요, 캠페인은 71이 정본) |
| Living World | 21                                 | 구현됨              |
| 서버/데이터  | 04, 10, 12, **77**                 | 구현됨 (10 리전 경제 부분, 77 God method 완료) |
| LLM 서술     | 05, 11, 26, 35, **62**             | 구현됨 (스트리밍 + 레이턴시 최적화) |
| 모델 평가    | 25                                 | 참고                |
| 메모리       | 31                                 | 구현됨 (v4)         |
| 대사/마커    | 30, 32, 33, **44, 45, 56, 58~61, 67** | 구현됨 (품질 v2 + 자유 대화 + Reaction Director + 단서 단일화·튜닝 + 선택지 튜닝 + nano 감사) |
| 이벤트 엔진  | 34, **43, 46**                     | 구현됨 (Player-First + 돌발행동 + Fact 일급 객체, 28은 archive 배경) |
| NPC 결정/품질 | **48, 49, 51, 47, 55, 72**        | 구현됨 (NpcResolver 단일 권한자 + Distinctness + NPA 감사/메트릭 + 반응 권한 통합, 50은 폐기) |
| UI/클라      | 15, 23, **42, 68**                 | 구현됨 (UI/UX 실사 리뷰 + 부록 A~M) |
| 파티         | 24                                 | 구현됨 (Phase 1~3)  |
| 주사위/UX    | 22                                 | 구현됨              |
| 엔딩/아카이브 | 39                                 | 구현됨 (Phase 1)    |
| 소지품/아이템 | 40                                 | 구현됨 (UX 개선 + LLM 정합성) |
| 경제         | **65**                             | 구현됨 (사례금 + BRIBE 정보 구매) |
| 자율 서사    | **74(논의), 75(설계·P0~P8)**       | 구현됨·프로덕션 (karnholt_v1, P7/P8 후속 대기) |
| 시장 대응    | **76**                             | 구현됨 (D6 저작 도구만 잔여) |
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
- 번호 공백(13, 27, 28, 29, 37, 38, 52~54 등)은 합쳐졌거나 아카이브된 문서의 흔적 — 신규 문서는 빈 번호 대신 마지막 번호 이후(78~)를 사용.
- **57번 문서 부재**: server 코드/커밋(`focused 모드 보조 NPC strip`, `익명 배경 인물 신원 hard 차단`)이 `architecture/57`을 참조하나 문서 파일이 레포에 없음 — 작성 필요.

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
