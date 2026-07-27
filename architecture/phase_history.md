# 구현 단계 이력 (Phase History)

> CLAUDE.md 의 `Implementation Phase Status` 표 **원문 전량**.
> 상시 로드되는 CLAUDE.md 를 가볍게 유지하려고 여기로 옮겼다 (2026-07-27).
> CLAUDE.md 에는 최근 항목의 압축본만 남는다 — 상세·근거·실측 수치는 이 파일과
> 각 `architecture/NN` 문서가 정본이다.

## 전체 이력 (163 항목, 최초 구현 → 2026-07-27)

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
| **LLM 모델 평가 v2** | 9개 모델 비교 평가 (Qwen3 235B 1위), Fallback GPT-4.1 Mini 전환, cost_usd DB 추적 | ✅ 완료 |
| **서술 파이프라인 v3** | 반복 패턴 해결(2중주입 제거), 판정 리마인더, 메타 서술 금지, 태그 누출 방어 | ✅ 완료 |
| **NPC 마커 nano 전환** | 발화자 판단 주 파이프라인: regex→nano LLM, regex는 fallback 격하. 호칭 강화 프롬프트 | ✅ 완료 |
| **서술 파이프라인 v4** | sessionTurns THREAD 하이브리드 + 톤 가이드 동적화 + 감각 순환 폐기 + 모델 교차(Next80B/FlashLite) | ✅ 완료 |
| **마커 안정화** | distance 60→100 + 대사 최소 8자 + 위치 검증 + 클라이언트 재배치 방어 + NPC 목록 확장 + 호칭 정확 매칭 | ✅ 완료 |
| **E2E 테스트** | Playwright 기반 자동 테스트: 회원가입→캐릭터생성→게임진입→20턴 플레이→렌더링 검증 | ✅ 완료 |
| **과금 모델 추가** | Qwen3/Llama4/Flash Lite 가격표 + PWA 캐시 초기화 버튼 + 플레이어 대사 방어 | ✅ 완료 |
| **NanoEventDirector** | nano LLM 기반 동적 이벤트 엔진: 매 턴 이벤트 컨셉/NPC/fact/선택지 생성, NPC 선택 행동별 전환 규칙, sourceNpcId 연속성, 기존 EventDirector fallback | ✅ 완료 |
| **연쇄 반응 시스템** | Layer 2: 치안/불안 임계값 → LOCKDOWN/RIOT 조건 자동 발동, 판정 보정(blockedActions -2), 시그널 피드 알림 | ✅ 완료 |
| **IntentParser 강화 v2** | 고위험 키워드(FIGHT/STEAL/THREATEN/BRIBE) LLM보다 KW 우선, targetNpcId KW 우선 (플레이어 NPC 지목) | ✅ 완료 |
| **NPC 능동 반응** | Layer 3: WITNESSED NPC trust 기반 경고/회피/밀고(Heat+5)/적대(Heat+8), LLM [NPC 반응] 블록 주입 | ✅ 완료 |
| **동시접속 최적화** | LLM Worker 5턴 병렬(Promise.allSettled) + DB 풀 max30 + 폴링 1초 + DB 쿼리 병렬 + 레이트 리미터 + Throttle 완화 + PM2 클러스터 설정 → 10명 동시접속 10/10 성공 | ✅ 완료 |
| **Quest→Ending** | S5+5턴 auto-ending (Incident resolved=CONTAINED), factToIncident 매핑, questEndingApproach LLM 톤 주입 | ✅ 완료 |
| **NPC 마커 오귀속 방지** | 매칭 실패 시 마커 미삽입, nano 결과 후보 별칭 검증, 하오체 보조 감지 | ✅ 완료 |
| **초상화 크롭** | react-easy-crop 카카오톡 스타일 드래그+줌, 4:5 비율 고정 | ✅ 완료 |
| **NPC 태도 변화 알림** | posture 전환 시 골드색 이벤트 표시, POSTURE_CHANGE 태그 | ✅ 완료 |
| **그레이마르 호외** | 양피지 모달 + nano 기사 변환 (장소/시간/사건 컨텍스트), 세계 변화 시그널 확장 (퀘스트/장소/NPC 아젠다) | ✅ 완료 |
| **NPC 아젠다 목격** | 같은 장소에서 NPC 행동을 [목격 장면] LLM 프롬프트로 자연 삽입 | ✅ 완료 |
| **메타 서술 방어** | 턴 번호/플레이어 3인칭/행동 복붙/활성 단서 후처리 제거, 프롬프트 행동 지시 개선 | ✅ 완료 |
| **NPC 소개 카드 정합성** | LLM 서술 기반 npcPortrait 갱신, 서술에 없는 NPC 카드 제거, 소개 턴 초상화 표시 | ✅ 완료 |
| **품질 검증 V7~V9** | V7 프롬프트 누출 9패턴, V8 NPC 정합성(카드↔마커↔화자), V9 서술 품질(반복/하오체) | ✅ 완료 |
| **UI 개선** | 타이핑 전 서식 정제, 행동 입력 시 선택지 즉시 제거, 페이지 전환 페이드 통일, 고립 @마커 제거 | ✅ 완료 |
| **@마커 오류율 개선** | 3전략: 프롬프트 강화(호칭 패턴/교차 대화/금지 규칙) + 서브 LLM 2차 검증(미할당 대사 GPT-4.1-mini 재판단) + JSON 구조화 출력 모드(LLM_JSON_MODE) | ✅ 완료 |
| **Memory v4** | nano 구조화 추출(entity_facts UPSERT) + 직전 턴 원문→nano 요약 전환 + nano 요약 주입 (반복률 71% 감소) | ✅ 완료 |
| **별칭 반복 해소** | shortAlias 18명 추가 + 서버 후처리(deduplicateAliases) + NPC lookup에 shortAlias/name includes 매칭 | ✅ 완료 |
| **행동별 프리셋 묘사** | PRESET_MANNERISMS 6종 × 4~5행동 = 26개 세부 묘사, actionType 기반 동적 주입 | ✅ 완료 |
| **LLM Flash 전환** | Gemini Flash Lite → Flash (영어 누출/메타 서술 해소, 비용 +81%, 속도 +17%) | ✅ 완료 |
| **대사 분리 파이프라인** | 2-Stage LLM (서술+대사 분리), DialogueGeneratorService, dialogue_slot JSON, 서버 마커 자동 삽입, 하오체 검증+재시도 | ✅ 완료 |
| **로어북 시스템** | 키워드 트리거 기반 세계 지식 동적 주입 (NPC knownFacts 34개 + 장소 비밀 13개 + 사건 단서 19개 + entity_facts 키워드 검색) | ✅ 완료 |
| **다중 어체 시스템** | NPC별 speechRegister 5종 (HAOCHE/HAEYO/BANMAL/HAPSYO/HAECHE), 어체별 검증+fallback, 43명 배정 | ✅ 완료 |
| **NPC_ID 정확도 강화** | NPC 목록 [ID:NPC_XXX] 병기, resolveNpcId 퍼지매칭(레벤슈타인 거리 2), 서술 본문 한글 fallback, name 2글자 가드 | ✅ 완료 |
| **테스트 검증 강화** | V9-a sanitize 오탐, V9-b CHOICE 대화 맥락, V9-c fallback 감지, --choice-rate/--model 옵션 | ✅ 완료 |
| **Player-First 이벤트 엔진** | TurnMode 3분류(PLAYER_DIRECTED/CONVERSATION_CONT/WORLD_EVENT) + NPC 우선순위 변경 + 맥락 NPC 연결 + EventMatcher targetNpcId 가중치 | ✅ 완료 |
| **NanoEventDirector 비동기 분리** | turns.service → llm-worker로 이동, nanoCtx만 빌드 후 LLM Worker에서 generate() 호출, 턴 응답 300~1000ms 절감 | ✅ 완료 |
| **NPC 불일치 후처리** | Step E(대사 내 NPC이름: 프리픽스 제거) + Step F(primaryNpcId와 LLM NPC 불일치 강제 교정) | ✅ 완료 |
| **LLM 스트리밍** | OpenRouter stream:true + LlmStreamBroker(SSE) + StreamParser(문장 단위 버퍼링) + 2-Phase 렌더링 | ✅ 완료 |
| **이미지 WebP 최적화** | 81개 이미지 PNG→WebP 변환 (114MB→1.9MB, 98% 절감) + npc-portraits rewrites 제거 + imageSizes 커스텀 | ✅ 완료 |
| **프롤로그 합쇼체 전환** | 로넨 대사 HAPSYO 전환 + 6종 프리셋 prologueHook 합쇼체 | ✅ 완료 |
| **단위 테스트 강화** | Player-First 엔진 101개 테스트 (determineTurnMode 35개 + extractTargetNpc 16개 + NanoEventDirector 25개 + 후처리 20개 + EventMatcher 5개) | ✅ 완료 |
| **스트리밍 렌더 안정화** | StreamTyper once-guard + onComplete 멱등성(텍스트 사라짐 방지) + 타이핑 중/후 DOM/폰트 래퍼 통일(스타일 점프 제거) + analyzeText 문단 재조합(문장별 \n 제거) + 대사 내부 raw 마커 후처리 | ✅ 완료 |
| **버그 리포트 수집 확장** | bug_reports에 client_snapshot/network_log/client_version 컬럼 추가 + 메시지 상세 직렬화 + DOM 요약 + 자동 네트워크 타임라인 로거(request 래퍼) | ✅ 완료 |
| **엔딩 연출 개선** | Part B MIN_TURNS 가드 + commitTurnRecord 순서 수정 + arcRoute 분기 에필로그(12분기) + personalClosing + ui.endingResult 누락 수정 + SignalFeed soft deadline + DeadlineBanner 상단(D-3/2/1/0/초과) + LLM deadlineContext 조건부 주입 | ✅ 완료 |
| **여정 아카이브 Phase 1** | run_sessions.ending_summary jsonb + SummaryBuilderService(synopsis/keyEvents/keyNpcs/finale 템플릿) + EndingsController(GET /v1/endings, /:runId) + lazy fallback + EndingsListScreen + JourneySummaryScreen 양피지 스타일 + StartScreen "여정 기록" 버튼 | ✅ 완료 |
| **아이템 정합성 (A+B)** | 시스템 프롬프트 3/4번(구체 아이템·골드 증여 금지 규칙) + prompt-builder [이번 턴 획득 아이템] 블록 + EventItemReward 타입 + turns.service payload.itemRewards 지급 경로 + KEY_ITEM 3종 이벤트 매핑(길드 인장/허가증/밀수 지도) + 희귀 장비 2종 상점 추가 | ✅ 완료 |
| **소지품 UX 개선** | InventoryTab 교체 확인 모달(EquipReplaceModal + 비교 카드) + USABLE_ITEMS 동적화(ItemMeta.usableInHub) + 전투 중 사용 버튼 자동 disabled + EquipmentDropToast(rarity별 5초 자동 페이드) + 에러 문구 한국어 매핑 10종 | ✅ 완료 |
| **NPA v2 메트릭** | NpcDistinctness(distinct pool 매칭률) + ToneMatch(baseline-aware mismatch) 신설, 5축 점수(연결성·자유도·사람다움·차별화·톤일치) | ✅ 완료 |
| **NPC Distinctness v1** | R1 회피 어휘 강제 룰(2회+ 등장 시 약한 표현 치환) + CORE 6명 mannerism 확장(speechStyle/signature) + rat-king dark 톤 화제 한정 — 차별화 4.83/5, ERR 0 | ✅ 완료 |
| **A51 R2~R6 + A52 시스템 프롬프트 압축** | R2 사용자 키워드 인용 가이드 + R4 NPC 권장 호칭 자동 추출 + R5 HAOCHE 어미 후처리 + R6 단일 NPC 응답 강제 + C1 P0/P1/P2 우선순위 박스 + 프롬프트 11,400→9,000자(-21%) | ✅ 완료 |
| **NPA 메트릭 v2 (다중 NPC 정확화)** | toneConsistency / pronounConsistency를 utterance 단위로 자기 NPC register/호칭 평가 + system 프롬프트 자기모순 정정(실제 NPC unknownAlias 금지 예시 제거) | ✅ 완료 |
| **A56 NPC Reaction Director + 어휘 폭주 해소** | NpcReactionDirector(추상 톤 3축 nano 사전결정) + ChallengeClassifier(자유 행동 주사위 스킵) + speechStyle 어구 예시 추상화(9 NPC) + 마커 substring 합쳐짐 자동 복구. 시그니처 어구 39.7% → 6.2% (-84%), 마이렐 패턴 0% (완전 제거), TTR +0.057, 5회 A/B + 일반 시나리오 3회 검증 | ✅ 완료 |
| **Fact 일급 객체 도입** | facts.json 신규 + ContentLoader API — Fact 를 NPC·Incident 와 동일 레벨의 콘텐츠 원자로 승격, 매칭/조회 일관화 | ✅ 완료 |
| **잠금 NPC + Fact awareness 통합** | 대화 잠금 중 NPC 의 fact 인식 상태를 LLM 컨텍스트에 통합 전달 — architecture/46 | ✅ 완료 |
| **NPC 점프 완전 차단** | event.payload.primaryNpcId 동기화 누락 수정 + NPC 후보 names에서 일반 단어 제거(스트림 점프 차단) + 대화 잠금 중 MOVE_LOCATION 차단(회귀 방지) | ✅ 완료 |
| **NPC 결정 권한 단일 통합** | NpcResolverService 신설 — 텍스트매칭/IntentV3/대화잠금/Nano/이벤트배정 5단계 우선순위를 단일 권한자로 통합. Discoverability + Content 검증 — architecture/48/49 | ✅ 완료 |
| **직전 NPC 대사 슬롯 + 회피 패턴 정상화** | 사용자 응답 복사 / 위치 회피 해소 — 직전 NPC 대사가 슬롯 누락 시 LLM 이 사용자 입력을 복사하는 버그 + 동일 NPC 의 위치 회피 부자연스러움 동시 해소 | ✅ 완료 |
| **메인 LLM Gemma 4 26B 복귀** | Gemini Flash → Gemma 4 26B MoE (OpenRouter) 메인 복귀, fallback GPT-4.1 Mini 유지. 한국어 서술 일관성·톤·OpenRouter 게이트웨이 안정성 종합 판단 — architecture/25 부록 A-1 | ✅ 완료 |
| **nano 선택지 DB/stream desync 봉합** | llm-worker.service.ts 의 첫 UPDATE 에서 llmChoices 분리 → Track 2 완료 후 finalChoices 단일 변수로 DB UPDATE + stream emit 동시 사용. Single Source of Truth 복원. 9턴 연속 DB↔API 라벨 SET byte-equal 검증 통과 | ✅ 완료 |
| **Fact 공개 단일화** | 단서 기록·서술 데스싱크 해소 — selectRevealableFact(주제 우선 선택) + ui.questReveal 전달 + 보류 가이드(factWithheldHint). 기록 fact = 서술 fact 보장 — architecture/58 | ✅ 완료 |
| **단서 대화 후속 안정화** | 판정 NPC=서술 NPC 정합(NpcResolver 부분 이름 매칭) + [단서 방향] nextHint ui 전달 복구 + HINT_MODES off-by-one — architecture/59 | ✅ 완료 |
| **단서 흐름 튜닝 + 워커 정합성** | LLM 워커 runState lost update 해소(fresh 부분 패치) + 주제 불일치 fallback 금지(인계 양보) + [단서 방향] 공개 턴 이월 + 비주제 공개 확률 게이트 — architecture/60 | ✅ 완료 |
| **NPC 대화 자연화 3종** | ① 대화 행위 감지(인사/안부/감사/작별 — 사교 턴 fact 공개 게이트 + FAREWELL 잠금 해제 + 톤 가이드) ② primary NPC 직전 발화 이어받기(마커 기반 추출 → 메인 LLM positive 블록 + nano recentNpcDialogues 정밀화) ③ 질문 우선 응답(디렉티브 + 감각초점/목격장면 억제 + fact 키워드 2-hit 스코어링 + 질문 턴 비주제 fallback 차단). NPA 검증: 인사 단서 덤핑 제거, 응답률 에드릭 56→70% | ✅ 완료 |
| **NPA 어미 메트릭 수정** | HAOCHE 최빈 종결 '-소' 누락 + 말끝 흐림 파편 집계 버그 — 하오체 준수 NPC가 45~59%로 오측정되던 것 88~100% 정상화 (로넨 45→100%, 위반 0건). 수정 전후 어미 일치율 직접 비교 불가 — architecture/55 부록 A | ✅ 완료 |
| **NPC 이름 공개 무결성** | A~E + B(pendingIntroduction) + 연출 3층 방어(경로 분기/introAttempts/IntroFallback) + **R7 스트림 문장 새니타이즈**(emit 전 미공개 실명·별칭 중복 차단, done 최종본 교체 프로토콜 확인, 죽은 배선 정리). 회귀 26건 — architecture/64 | ✅ 완료 |
| **멀티 시나리오 ① 멀티 팩 로더** | ContentPackState 팩 캐시 + AsyncLocalStorage 스코프 — 단일 활성 시나리오 정책 폐지, 서로 다른 팩 런 동시 플레이 격리. ensureScenario(팩 확보)+enterScenario(동기 컨텍스트) 규약, 진입점 4곳. 인터리브 실런·격리 스펙 4건 검증 — architecture/63 부록 D | ✅ 완료 |
| **멀티 시나리오 ⑥ 클라 선택 UI** | GET /v1/scenarios + StartScreen 여정 선택 화면(2팩 이상일 때) + store.scenarioId + HUB 라벨/프리셋 표기 시나리오 인지 + location-images 팩 인지(null=이미지 생략). E2E 완주 검증 — architecture/63 부록 C | ✅ 완료 |
| **경제 루프 v1** | 단서·진전 사례금(quest.json rewards, 팩별) + 정보 보류 턴 BRIBE 선택지 노출(nanoCtx.bribeOpportunity) + BRIBE 기본 비용 -6/-3 config 외부화. 실측 근거: 30일 441턴 골드 이벤트 4건, 대화·조사 86% — architecture/65 | ✅ 완료 |
| **엔딩 완주 평가 P1~P4** | P1 순수 이동 상용구 KW_OVERRIDE(26턴 갇힘 해소) + P2 NPC 작별 발화 잠금 해제(npcFarewell 마킹) + P3 접두 융합 별칭·무명 라벨 후처리 + P4 퀘스트 전환 장비 보상(transitionEquipment)·드랍 중복 감쇠 — architecture/65 부록 B | ✅ 완료 |
| **마커·대사 정합 마감** | 콜론 라벨 3-Tier 유일성 매칭(무명 오귀속 6→1, 잔여는 의도) + 카드 서술 언급 검사 + 진입 턴 직전 인물 이월 차단 + audit V8/V9-c 노이즈 정밀화 — 9/9 PASS 최초, 구조 결함 소진 판정 — architecture/65 부록 C | ✅ 완료 |
| **엔딩 턴 피날레 + 자기소개 사전 확정** | 엔딩 확정 턴 [마지막 장면] 디렉티브(endingType별 종결 톤)+nano 스킵+소개 비활성 (arch/65 부록 D) · NPC 자기소개 3단 사다리(nano 사전 생성→positive 주입→서버 삽입, 전 성향 통일, sanitize 소개 턴 역할 재정렬) — 자기소개 성사 0%→보장 — architecture/66 | ✅ 완료 |
| **Nano 엔진 감사** | 요청 단위 timeoutMs(light 5s/dialogue 10s — 죽은 설정 부활) + 워커 이중 처리 락(.returning 선점 확인, 7/650 실측) + NpcReaction JSON 재시도(실패 10.4%→구제) + nano 모델 env 명시 고정 — architecture/67 | ✅ 완료 |
| **카드 정합 근본 수정 + 테스트 시스템 감사** | V8 복합 원인(audit 턴 매핑 밀림 + 완전형 마커 미수집 + 부분 문자열 오매칭) 해소, 카드 교체 로직 부활 · 구 정책 테스트 갱신(스위트 실패 0)·V9-a 융합 센서 재정의·복제 drift를 export 정본 참조로 전환 — architecture/67 부록 A·B | ✅ 완료 |
| **자유 대화 정합 4종** | 언급 질문 가드 확장(조사·역할 경로, 얼마나/~가 말한) + 화자 표시·기록 소스 단일화(레거시 재계산 제거) + 작별 턴 소개 이월 + 재탕 감지 센서 — 자유 입력 '대화 상대 핑퐁' 해소 실측 — architecture/67 부록 D | ✅ 완료 |
| **멀티 시나리오 디커플링 ②~⑤** | 엔진 하드코딩 콘텐츠 ID 외부화(표시명 11곳·활동장소·entityAliases·프롤로그 스크립트·L0 테마·moveKeywords·HUB 선택지) + DAG graph.json화 + 시스템 프롬프트 세계관 주입(문면 동일 검증) + silverdeen_v1 미니 팩(장소5/NPC12/퀘스트 6단계) + scenarioId 런 경로 + 시나리오 일치 가드. 단일 활성 시나리오 정책 — ①멀티 팩 로더/⑥클라는 보류. architecture/63 | ✅ 완료 |
| **UI/UX 실사 리뷰 v1** | 헤드리스 신규 유저 경로 순회 + 6건 수정: 인물 도감 조우 필터(enc/app ≥1)+이어하기 복원(GET run npcEmotional 조립) · 모바일 상태줄(HP/STA/골드/시간) · 모바일 인물 탭 · 호외 모달 서술 완료 후 표시 · "(으)로" 조사 처리(korParticleRo ㄹ예외+7곳) · 개발자 정보 dev 게이트 — architecture/68 | ✅ 완료 |
| **UI/UX 폴리싱 C-2~C-7** | 선택지 rest 어포던스(.choice-btn 골드 카드) · 시나리오 카드 배너(getScenarioBannerImage, fallback 그라데이션) · 스탯 뮤트 앤틱 팔레트(--stat-* 토큰, 중복 3곳 정본 수렴) · 라벨 정리(카리스마 줄바꿈·레이더 한글·범례 제3명칭 통일) · 모바일 메뉴 lucide · 골드 체크박스(.checkbox-gold) — architecture/68 부록 A | ✅ 완료 |
| **C-1 거점 사랑방 개방 (A안)** | HUB 자유 입력은 서버 계약(CHOICE 전용) 유지 — 대신 팩별 거점 사랑방 장소를 HUB에 개방: graymar LOC_TAVERN·silverdeen LOC_SD_INN `hubAccessible: true` (서버 0줄, go_* 기계 파생) + 클라 HubInputNotice 안내. 자유 대화는 기존 LOCATION 파이프라인 100% 재사용, 실측 검증 — architecture/68 부록 B | ✅ 완료 |
| **자유 입력 발견성** | 첫 LOCATION 1회 코치마크(인라인 골드 배너, localStorage 플래그+포커스/닫기 소멸, useSyncExternalStore) + placeholder 행동 예시 4종 로테이션 + 시작 튜토리얼 자유 입력 안내 1줄 — architecture/68 부록 C | ✅ 완료 |
| **NanoChoiceNpcFix** | nano 선택지 sourceNpcId 오염 서버 검증 게이트(버그 5f31d803) — 대화 연속 턴에서 대화 계열 선택지의 NPC가 대화 상대와 다르면 교정(지목형 라벨·작별 턴 예외), finalChoices 확정 직전 단일 지점, export 코어+유닛 7케이스 — architecture/68 부록 D | ✅ 완료 |
| **상점 노출 동선** | 구매 dead path 부활(SHOP 인텐트 도달 불능 — TRADE+구매 표현 진입 확장, 상점 없는 장소 은유 침묵) + 클라 ui.shops 소비 신설: store shops 상태 · LocationHeader 상점 칩 · InventoryTab 진열+구매 버튼(submitAction 재사용). E2E 실구매 검증(전 DB 최초 [상점] 이벤트) — architecture/68 부록 E | ✅ 완료 |
| **NPC 선제 단서 억제 (부록 M)** | 이방인 잡담 시 NPC가 먼저 단서 흘리는 부자연스러움 제거 — 대화 계열(TALK/PERSUADE/TRADE/HELP)은 주제 매칭 시에만 fact 공개, 조사·탐색은 fallback 유지, 차단 fact는 뇌물 기회 이월. 실측: 잡담 단서 0·명시 질문 공개. B축(NPC 살아있음)은 후속 — architecture/68 부록 M | ✅ 완료 |
| **이벤트-서술 NPC 분열 (부록 L)** | 버그 185a8ddd — 첫 진입 WORLD_EVENT로 음유시인 조우 이벤트 매칭, 서술은 정보상·선택지는 음유시인 분열. EVT_TAVERN_ENC_BARD primaryNpcId 명시(콘텐츠) + 유저 명시 지목≠이벤트 NPC 시 이벤트 선택지 폐기 게이트(코드). 조우 이벤트 NPC 명시 규약은 후속 — architecture/68 부록 L. 검증 인프라: EventChoiceGate export 정본화+유닛 5케이스, playtest V10(이벤트 NPC≠서술 화자 분열 감지) | ✅ 완료 |
| **판정·서술 불일치 + 초상화 오귀속 (부록 K)** | 버그 f4bf2e66 — bribeOpportunity가 nano 이벤트 컨셉 오염(OBSERVE인데 뇌물 서술) → NanoConceptGuard(비강압 행동+뇌물 신호 시 서술필드 억제, 선택지 유지)+빈 concept 스킵+프롬프트 positive. 배경 대사 초상화 오귀속 → 마커 등장 후 무마커 대사 무명화. 유닛 3케이스 — architecture/68 부록 K | ✅ 완료 |
| **후처리 순서 의존성 정비 (부록 J)** | 소개·별칭 후처리 순서 사각지대(5.11 재삽입이 5.10 정리 이후) 해소 — 순수 텍스트 정리 5종을 멱등 배리어 sanitizeAliasArtifacts로 묶어 5.10(1차)+5.14(최종) 동일 호출. 5.14 2→5종 확장, 재삽입 완전 커버. 동작 보존(1047 passed) — architecture/68 부록 J | ✅ 완료 |
| **긴 별칭 일괄 정비 (부록 I)** | CORE/SUB 15/18명 긴 unknownAlias 편중 해소 — graymar 14명 압축(12~14자→5~10자, 첫인상 형용사 유지) + BACKGROUND shortAlias 25명 신설 + silverdeen 대칭. 코드 0줄(콘텐츠), 충돌·오류 0, 실전 검증(긴 별칭 완전 소멸) — architecture/68 부록 I | ✅ 완료 |
| **오웬 별칭 반복 수정 (부록 H)** | 사랑방 개방 후 오웬(9자 긴 별칭) 미소개 반복 결함 — 저장 직전 최종 별칭 정리(5.14, IntroFallback 재삽입 커버) + shouldIntroduce appearanceCount 강제소개 posture 차등(FRIENDLY/FEARFUL 3회, 우호 상주 조기 소개). 실전 검증: 오웬 T4 자기소개→실명 전환, 긴 별칭 소멸 — architecture/68 부록 H | ✅ 완료 |
| **선술집 BG 초상화 6종** | 사용자 제작 초상화(비올라·헬가·그래디·갤러스·제롬·마일로) 클라/서버 매핑 + 비올라 여성 개명(구 단테)·헬가 gender 정정 — 사랑방 개방 후속, 실전 검증(여성 지칭 전층 반영) — architecture/68 부록 G | ✅ 완료 |
| **아크 커밋 동선 + 3사이클 프로세스** | S5 완주 3연속 실증 + 결정 4건: 아크 루트 HUB 명시 분기(arc_commit_*, 콘텐츠 routeCommitChoices, 팩 조건부 — "정의의 대가" 12분기 최초 진입) · 봇 확장(아크/상점/사랑방) · 어휘 반복 계측 · 도착 디렉티브 MOVE 이벤트 완화(무명 인사 구멍) · 구매 target 파서 누락 보충 — architecture/68 부록 F | ✅ 완료 |
| **캠페인 자유 시나리오 선택** | 첫 시나리오 자유 선택(원점 정책 폐기, AVAILABLE/IN_PROGRESS/COMPLETED) + GET /v1/scenarios/:id/creation-bundle(팩 프리셋·특성 서빙, 클라 하드코딩 대체) + 캠페인 6단계 캐릭터 생성 통일(identity 이월 정상화) + 장비 carrySnapshot 이월 + 소모품 골드 환산 + statBonusPerScenario 배선 + campaignSummary 서사 이월 + 이월 스탯 리셋 버그 수정 — architecture/71 | ✅ 완료 |
| **NPC 반응 권한 통합** | 목격자 반응(Layer 3)↔NpcReactionDirector 이중 권한 해소: 대화 상대 목격자 루프 제외(② 단일 권한) + 당턴 1회 발화(2턴 중복 주입 제거) + posture 우선 trust 밴드(witness-reaction.core, FRIENDLY→warn) + ui.primaryNpcWitnessedTags→nano [직전 목격] 블록 + 주입 라벨 방관자 스코프 명시(메인+NanoEventDirector). 버그 599a00a1 — architecture/72 | ✅ 완료 |
| **자율 서사 팩 배포 (karnholt_v1, 2026-07-16)** | arch/74 논의 → arch/75 상세설계 → **P0~P6+P8 구현·배포** — "진상 선확정 디렉터 모드" AUTONOMOUS 팩. PlotSeedGeneratorService(진상 선확정 Plot Seed+검증/폴백) + PlotDirectorService(3막 비트 선계산·워커 비동기 CAS)+동기 채택(beat-gravity, 불변식 47 의도 정합만) + 동적 NPC 등록(dynamic-npc) + 규명율 기반 엔딩(autonomous-ending) + 킬스위치. content/karnholt_v1 팩(장소/NPC 저작·코어 외 생성) + 클라 AUTONOMOUS 라벨. P8 계측: 디렉터 존재감 낮음(채택 0~2/12턴, 의도 정합률 33%) — 후속은 arch/83 안 A+C로 구현 완료 — architecture/75 | ✅ 구현·배포 (P7 후속) |
| **시장 조사 대응 (자유도·판정 투명성)** | D1 강제창 의도 존중(불변식 47: 대화 잠금·사교·REST 제외) + 과금 3원칙 등재 + D2 판정 투명성(보정 출처 분해 modifiers·FAIL 부족분·FREE 스킵 안내) + D3 actionType 탈버킷(통합 nano 감정: statHint 행동-특정 스탯·difficultyMod·plausibility 서술 치환·physicalImpact) + propsState nano 흔적 추출(링버퍼·CAS) + 되짚기(고임팩트 과거 행동 언급). 기상천외 입력 실측으로 마법-as-FIGHT 재생·흔적 과잉 해소. + **D4·D1-c 계측 트랙**: playtest 서사 방향 계측 4종(n-gram 반복률·이벤트 다양성·스레드 억제·무진행 감시) + 의도 정합 채택률(plotProgress.beatAdoptions·isBeatIntentAligned, 카른홀트 실측 33%) — architecture/76 | ✅ 완료 |
| **감정·행동화 탈버킷 (D3-b′/c′/combat)** | 원안 D3-b/c 폐기·재설계 — ① 감정 탈버킷: nano socialImpact 5축(±5) + `applyActionImpact` 블렌드(base×0.4+nano×2, 부재 시 테이블 100%) + NpcReactionDirector emotionalShiftHint 죽은 출력 CAS 배선 ② 감정→세계 행동화: npc-agitation.core(fear→도주/회피, susp→신고 Heat+5, trust→접근, 쿨다운 6턴, witness 당턴 제외) + ws.npcFleeOverrides(스케줄 재구축 우선 적용) + [NPC 능동 행동] 디렉티브 ③ 전투 기만: appraiseCombatTactic nano(Tier 3/4만) + combat-tactic.core 성향 차등(COWARDLY 1.5/TACTICAL 0.5/BERSERK 0) + 전투 내 1회 감쇠. 실런: 오웬 FLEE_LOCATION 발동·운석 기만 DISTRACTION 분류·BERSERK 무효 실측. 부수 수정: enc_generic 500 크래시(getAmbushEncounterId fallback). **후속 2건**: ① R2 어휘 인용 가이드 → 의미 단서 교체(키워드 리스트 삭제, appraisalNote 채널 — 가짜 운석 실체화 해소) ② 전투 턴 장소 NPC 앵커링 해소(triggerCombat 조기 커밋의 actionHistory 누락 수정 + isCombat 프롬프트 게이트 4블록 + [전투 장면] 디렉티브) — architecture/76 | ✅ 완료 |
| **어체 정합 근원 수정 (2026-07-17)** | 3층 결함 동시 해소 — ① 시스템 프롬프트 P0-A 자기모순(하오체 무조건 열거 → speechRegister 준수) ② 구 R5 오폭 폐기(primary 일괄 하오체 치환이 합쇼체 보조 화자 대사 파괴 — llm_speech_audit 자가 계측 실증) → **R5v2 화자 인지 정규화**(마커 화자별 register 해석 후 그 어체 어미만 교정, 낮춤체·일반 ~소는 계측만) ③ validateSpeechRegister 혼용 감지에 해요체 추가 + speech-register 합쇼체 예시 모순 교정 + silverdeen BG 6명 register 배정. 3배치 실측: 합쇼체→하오체 끌림 11→1건. 부수: 인계 가이드 지칭을 unknownAlias 인용 → shortAlias 직책 호칭으로 (따옴표 제거) | ✅ 완료 |
| **감정→행동화 실증 완결 + 밸런스 (2026-07-17~18)** | agitation 4종 전부 실발동 실증 — FLEE(마이렐 fear 89.5)·AVOID·REPORT(에드릭 susp 63.5, heat+5 + **시그널 피드 SECURITY 가시화** 신설)·APPROACH(하를런 trust 57/attach 26.8, devotee 30턴 롱런). 임계 실측 조정 2회: attach 30→10, trust 50→42 (로그 감속 곡선 — 15턴 38→30턴 45). 전투 기만 COWARDLY는 실콘텐츠 사슬 스펙 4케이스로 검증(라이브 도달은 창고 잠입·보스전 한정). 검증 페르소나 3종 신설(brawler/sneaky_liar/devotee) | ✅ 완료 |
| **서술 품질·계측 정비 (2026-07-17)** | ① 개시어 편중 동적 억제 — overusedOpeners(세션 3회+ 개시어 추출→[최근 사용 표현] 블록 확장, 26런 2,162문장 계측 15.3%→11.8% 실측, 롱런 잔여는 백로그: 임계 3→2·대명사 계열 합산) ② PlayerThread COMPLETED 데드 상태 해소(사건 해소 정산 배선) + **스레드 억제 정책 기각**(행동 카운터라 억제=기록 누락) + D4-3 재조준(사건 공존 계측) ③ V10 센서 정밀화(이벤트 선택지 실노출 조건 — 게이트 폐기 턴 FP 제거) | ✅ 완료 |
| **arch/77 Phase 2 (2026-07-17~18)** | context-builder `build()` God method **1,528→553줄 (-64%)** — P2.1~P2.10 동작 보존 컷-페이스트(FactPool/장면연속성/NPC기록/World/NarrativeEngine/Aux억제/메모리로드/프리셋배경/직전장소/소개상태). 캡처 하네스 대신 기존 유닛+playtest 게이트(Phase 3 실용 기준 적용), 게이트 2회 전부 10/10. 암묵 클로저 의존 4건 명시화 | ✅ 완료 |
| **서술 개시어·대명사 억제 사이클 (2026-07-18)** | D5 계측 센서(playtest.py — 대명사 개시어율·지칭 명사구 CONTENT/NON_ALIAS 분류) + 개시어 임계 3→2 + 대명사 화이트리스트 12종 1키 합산(동률 우선). 12턴×5런 실측: 20.3%→16.2%(상대 -20.2%, 기준 -30% 미달 — soft 지시 천장, chatty 짝은 -30.4%). 즉흥 별칭 가설 실측 기각(전부 콘텐츠 별칭·축약형 — "책임자"=마이렐 별칭 축약). 2차 처방(디렉티브 승격/후처리/수용)은 결정 대기 — architecture/78 | ⚠️ 부분 달성 |
| **팩 에셋 풀 (2026-07-19)** | 이미지 자동 매칭 시스템 — content/<pack>/assets/ 투입 + sync_pack_assets.py(ASCII 슬러그 — URL 실명 치환 404 방어) → 저작 NPC 팩 로드 시 결정론 배정 + 동적 NPC 등록 시 배정(registerDynamicNpc 3rd arg) + getNpcPortraitUrl/Map 통합 리졸버(소비처 5곳) + 클라 LOC_KH_* 매니페스트 장소 리졸버·배너. 유닛 6케이스, 카른홀트 실런 검증(마커 pack-assets URL 실부착) — architecture/80 | ✅ 완료 |
| **프롬프트 토큰 최적화 (2026-07-19)** | arch/79 P3~P4 — ShortResponse 재시도 스킵(16.5%→0%) + 시스템 프롬프트 재압축(12,154→4,668자, P0/P1/P2 박스 정본 승격) + NPC 발화 가이드 클러스터 지시 압축(데이터 무손실) + 총량 백스톱(GRAND_TOTAL_CHAR_BUDGET 16,000자, 기억 블록 보호). 최종 avg 7,495tok(-31%)·12k+ 절벽 턴 0%·게이트 7런 10/10·회귀 0·devotee 관계 누적 정상. 대화 턴 대명사 기저(~29%)는 크기 무관 별개 문제 확정 — architecture/79 | ✅ 완료 |
| **arch/77 전 Phase 마감 (2026-07-18)** | God method 리팩토링 완결 — **P3** turns.service Inner **4,440→1,937줄(-56%)** P3.1~P3.15(HUB복귀 2벌 단일화·Quest 528줄·Step1~3 턴모드+비트채택 473줄 포함) · **P4** llm-worker Inner **3,503→1,746줄(-50%)** 금지선 4곳 마킹 + narrative-filter.core 정본화(유닛 16, P5 경어체 규칙 = 한글 `\b` 불성립 죽은 규칙 발견) + 마커 대단위 920줄 · **전투/DAG** Combat 544→319줄(-41%) + **DAG 골드 무바닥 결함 수정**(유일한 의도적 동작 변경) · **P5 클라** StartScreen -26%/game-store -42%(공개 훅 유지)/StoryBlock -45%(StreamTyper 멱등성 잔존). 서버 25커밋+클라 3커밋, 매 스텝 유닛 1,390 green + playtest/E2E/browse 게이트, 회귀 0(V9 4건 전부 flaky 인과 배제). 신규 관찰: LLM 즉흥 별칭 반복은 콘텐츠 별칭 억제 커버리지 밖 | ✅ 완료 |
| **밤낮 시스템 재설계 (2026-07-20)** | 이중 시간계 근본 해소 — ① 행동 가중 timeCost(사교 0·이동/휴식 2·기타 1, 기계식 전환 제거) ② 전환 서술 주입(recentPhaseTransition → 전환 턴만 [시간대 전환] 디렉티브, 급전환 방지) ③ 4상 UI 승격(WorldStateUI phaseV2·day, 클라 새벽/낮/황혼/밤, 황혼 오표기 해소) ④ **이중 시간계 통합**(deriveTimePhaseFromV2 — v1 advanceTime 토글 폐지, timePhase = phaseV2 파생 미러, 전투 경로 불일치 해소). 실측 chatty 15턴 전환 5회→1회·brawler 정합. 신규 불변: timePhase = phaseV2 미러 — architecture/81 | ✅ 완료 |
| **어체 자기모순 교정 (2026-07-20)** | 고정 팩 speechRegister↔speechStyle 모순 3건(펠릭스·라이라·올드릭, 전부 HAPSYO↔하오체 산문) 교정 — 프롬프트 상충 주입이 어체 혼용 유발. 3팩 전수 스캔(금지목록 제거+명칭 우선, 정본 regex 1차 24건 중 21건 FP). field를 산문(정본)에 맞춰 HAOCHE. 실측 펠릭스 순수 하오체·로넨 무피해. content-validator 하드닝은 백로그 — architecture/82 A | ✅ 완료 |
| **NPC 자연스러움 3종 (2026-07-20)** | 대화 분석(자연스러움·연속성) 도출 — #5 배경 감시자 advance-or-dismiss(정적 "훑어본다" 반복→진전/퇴장 강제) · #6 제스처 앵커 제거 L0+L1(recommendPool 삭제 — 정적 풀=anchor 불변식 41/42 + frequency/presence_penalty 0.4/0.3 미사용 모델 레버 투입, "목덜미" 상투구 0회) · #7 첫 조우 개방 깊이 티어(trust+encounterCount 긍정 프레이밍, 낯선 이 과다 개방 억제). memory feedback_concrete_vocab_anchor 신설 — architecture/82 B |
| **포인트 시스템 (2026-07-23)** | 소프트 베타 비용 통제 — 코드 발급→충전→채팅 차감(5p/턴, 전 턴 일괄, 다회용 코드, 가입 50p). DB 4종(users.points + point_transactions 원장 + redeem_codes + code_redemptions) + PointsService(원자적 차감/멱등/D5 환불) + `/v1/points/*` + `/v1/admin/codes`(AdminTokenGuard). 차감=디스패치 직전+거부 throw 환불, D5 실패 환불=워커 FAILED 2경로. 클라: points-store + Header 💎 잔액 + PointsModal 충전 + 402 자동 유도. 라이브 8경로 검증·서버lint0·유닛6·클라빌드. server 1db5ce4 배포 — architecture/85 | ✅ 완료 |
| **자율 디렉터 존재감 튜닝 (2026-07-21)** | arch/75 P8 후속 — 안 A(비트 신선도 stale 2→3턴)+안 C(GRAVITY_NPC 25→30·직전 상호작용 가중 ½→⅔) 구현, 안 B(강제창 4→3) 보류. 채택 0~2→2.0/12턴·keyFact↑·강제 진행 회귀 0 + §11 무명 화자 프레이밍(서술형 소문 우선·익명 마커 ≤1, 무명 12→5·7회) — architecture/83 | ✅ 완료 |
| **LLM 31B 승격 + 프로바이더 allowlist (2026-07-22)** | 메인 Gemma 26B→31B dense + LLM_PROVIDER_ONLY_MAP 모델별 allowlist(ModelRun·Friendli·Novita — 풀 불안정 빈 서술 3~5/12턴 실측 대응) + 빈 서술 3층 방어(ensureNonEmpty·빈 스트림 throw·워커 FAILED 게이트) + JSON 형태 구제 가드(salvageNarrativeShape) + playtest V11 게이트(빈 서술·raw JSON 하드 FAIL). 3모델 로테이션 실험 기각(26B↔31B 가족 상관 1.76배 실증) · Solar Pro 3 후보 제외 · 턴당 실과금 ₩1.57 — architecture/25 부록 D-8 | ✅ 완료 |
| **파티 던전 클라이언트 배선 (2026-07-23)** | 파티 던전이 서버 엔진 완성/클라 UI 협동 입력 미배선이던 것 해소(2중 검증 발견). 서버: submitLeaderHubChoice(프롤로그·Heat CHOICE 리더 대표 통과)·가드 화이트리스트·턴 타이머+deadline 수정·멤버 데이터 경로(GET .../runs/:id/state + turnDetail choices). 클라: game-store 파티 분기(리더도 파티 엔드포인트 경유)·applyPartyTurnResult+서사 폴링·멤버 진입 복원(getPartyRunState)·투표 후 재복원. 프롤로그 accept_quest 소프트락 해소(전 팩 신규 파티 진입 불능이던 회귀). arc_commit 파티 투표화는 백로그. 서버 API 2인 협동·솔로 회귀 무 실증 — architecture/84 | ✅ 완료 |
| **어드민 콘솔 (2026-07-23)** | arch/87 — 서버 admin/ 모듈(관제 API 12종: overview KPI·llm-cost·points 시계열·유저 검색/조정·런 목록/스턱/abort/retry·failures·health) + 하이브리드 AdminGuard(x-admin-token OR JWT+users.role, @AdminEndpoint 정본=가드+감사 로그 admin_audit_logs) + **보안 결함 2건 봉쇄**(settings/llm PATCH·bug-reports 목록/상세/PATCH 일반 유저 개방) + 별도 앱 graymar-admin(4번째 레포, Vercel graymar-admin, 5탭 UI). 헤드리스 QA 5탭 검증, 잔여=admin.dimtale.com DNS·GitHub 앱 접근 1클릭 | ✅ 완료 |
| **비-graymar 팩 정합 + 모바일 UX (2026-07-23)** | 별빛모래 실플레이 결함 일괄 — ① equip/unequip/useItem 팩 스코프(enterScenario) 누락 → getItem 기본팩 조회 → 고유 아이템(EQ_SS_*) 장착·사용 거부. 세 메서드 스코프 추가(규약: 런 팩 콘텐츠 참조 진입점은 enterScenario 필수) ② 팩 프리셋 초상화 — character.portrait가 adaptPresetsForScenario 목록(graymar 6종)에 없는 SS_*/KH_* 미표시 → 통합맵 PRESET_PORTRAITS 조회 ③ 아이템 3층(이미지 client/public/items + ITEM_CATALOG + 서버 items.json, 별빛모래 10종, guides/10 프로세스) ④ 모바일 — 서술 스크롤 flex min-h-0 누락(overflow 무력화) 수정·장비 해제 탭 Header 햄버거 배선·무명 인물vsBACKGROUND 단역 아바타 차별(DialogueBubble)·MobileBottomNav orphan 삭제. server 8651b01 + client 6커밋 — architecture/86 | ✅ 완료 |
| **S5 엔딩 동선 + encounterCount 수정 (2026-07-23)** | 활성 star_sand 런 분석 도출 2건 — **B** S5 종착 상태 최종 선택(arc 커밋) 동선 부재: star_sand에 arc_events.json 자체가 없어 routeCommitChoices 빈 배열 → arc_commit 선택지 미노출 → 모든 런 currentRoute=null 무커밋(NONE) 엔딩(3루트 엔딩 콘텐츠 사장). 콘텐츠 arc_events.json 신규(해방/봉인/전이) + QuestProgression.isTerminalState() + 종착·미커밋 시 거점 복귀 pendingQuestHint(아크 자산 없는 팩 무영향). 팩 계약 신설: arcRouteEndings 정의 팩은 routeCommitChoices 필수. **C** encounterCount 전 NPC 0 고착(관계 깊이 티어링 무동작): 증가 게이트 actionHistory.some(primaryNpcId===npcId)를 워커 LockSeed(서술 화자 백필)가 오염 → NPC가 환경 이벤트 턴에 화자로 먼저 등장 시 증가 영구 스킵. per-visit 키를 nodeInstanceId 명시 플래그(NPCState.lastEncounterNodeId)로 교체 → isFirstEncounter/재회·shouldIntroduce·NpcReactionDirector 복원. 검증: star_sand 12턴 IREN/ED enc=1(dedup 정상). server 24b781e + content 1b1cc90 — architecture/88 | ✅ 완료 |
| **플레이어 이름 인지 (2026-07-26)** | arch/91 — 캐릭터 이름이 캐릭터 생성→UI 표기→엔딩 요약으로만 흐르고 플레이 안에서 전혀 안 쓰이던 것(실측 800+턴 중 등장 1건, 그마저 첫 만남 NPC의 무근거 호명) 해소. **A** 프롤로그 통성명 왕복(`{NAME_ASK}` 덩어리 토큰 — 이름 미지정 런 41%는 3줄 통째 제거, 4팩) + 의뢰인 `knowsPlayerName` 선세팅. **B** `NPCState.knowsPlayerName`/`playerNameLearnedTurn`/`lastEncounterTurn` 신설 + `shouldCallPlayerName` 게이트 + 자기소개 nano 되받기(어체 유지 실측) + 마커 안전망(PLAYER_ALIASES 런별 동적화·부분포함 오귀속 방어) + `[PlayerNameLeak]` 계측. **A안 후속(§9)**: 재회 단독 트리거가 실전 미발동 → 원인이 `encounterCount`(arch/88 이후 "서로 다른 방문 수")의 실플레이 고착임을 규명(실유저 런 전수: 서술 15회 등장 NPC도 조우 1, 재회 0건). `computeFamiliarity`(방문+서술÷2, 통성명 시 최소 2) 파생 지표 신설 → 관계 깊이 4단계·`isReEncounter`·`isFirstEncounter` 전환 — **전 NPC 영구 "첫 만남" 고착 + "첫 만남이라 경계"⊕"마음을 열기 시작했다" 모순 9턴 연속 실측 해소**. 호명 게이트는 ①통성명 직후 턴 ②새 방문 첫 턴 2경로. **R4 권장 호칭("항상 X로 부른다")이 호명 지시를 덮어쓰던 충돌**을 단일 문구로 통합(순서 의존: canCallPlayerName 선계산). 실측: T14 통성명→T15 "지운, 자네는 참 집요하네"·오웬 재회 호명·관계 깊이 첫만남5/재회4 분화·20턴 중 이름 3턴(남발 0) | ✅ 완료 |
| **랜딩 리디자인 P1~P4 (2026-07-25~26)** | arch/90 — 상용 6종(F&F·Hidden Door·크랙 등)+서사 게임 카피 6종(Disco·산나비 등) 실측 벤치마크 → 카피 톤 원칙 5(대칭 슬로건 금지·구체 사물·동사 비틀기·구어 마무리·시스템은 벌어지는 일) 확립. P1 카피 전면 교체(기능 카드 4→6, 영문 헤더 한국어화, '전부 무료'→free-to-start 교정) + P2 섹션 재배치·시나리오 카탈로그 4팩 카드 + P3 게임플레이 재현(CSS 12초 루프: 입력→1d6 판정→서술→NPC 대사) + P4 사회적 증명(`GET /v1/stats/public` 무인증·10분 캐시·테스터 제외 + LiveStats ISR 1h, 실측 1,494턴·230런, 소표본 fallback). 프로덕션 dimtale.com 검증 | ✅ 완료 |
| **거점 정체성 충돌 + 검증 인프라 (2026-07-26)** | arch/92 — 별빛모래 실플레이에서 "꿈잠 여관에서 꿈잠 여관으로 이동" 발견. 원인은 설계 오류가 아니라 **이름 중복**(엔진의 거점=추상 상태 `currentLocationId=null` ↔ 콘텐츠 `hub.name`=거점 장소 고유명). arch/68 부록 B 가 거점 장소를 `hubAccessible` 로 개방할 때 이름·프레이밍을 분리하지 않은 것이 뿌리. A안 채택: 4팩 `hub.name`/`returnLabel` 추상형 전환 + `world.regionSummary`·L0 `hub_system` 프레이밍 교체(라벨만 고치면 LLM 이 계속 "거점=그 건물"로 학습) + 자기 자신 이동 선택지 제거 + HUB 복귀 턴 도착 디렉티브 분기(없는 장소 환경 묘사 강제 → 극야에 "밝은 햇살" 실측) + SYSTEM 턴 이력 제외 해소 + 하드코딩 '도시' 제거(불변식 45). **스핀오프**: V9 반복 센서 정밀화(77런 실패 17%→6%, 92%가 센서 아티팩트 — `scripts/repetition_core.py` 정본 분리) · `_npc_alias_pool`/`events_v2.json` 이 graymar 경로 하드코딩이라 비-graymar 런이 남의 팩으로 판정되던 것 · V10 부재 NPC 화자 승격(별칭 관형어 부분 매칭 — `'수상한 곳'`→`'수상한 관리인'`) 근본 수정. 잔여=D9 거점 진입 4턴(B안 백로그) | ✅ 완료 |
| **장소 배경 지속화 (2026-07-27)** | arch/93 — 이미지 채널 5개 중 대화 중 살아있는 것이 초상화뿐이라, 장면이 한 번도 안 뜨는 구간이 중앙값 3턴·p90 6턴·최장 23턴(2,117턴/532구간 실측). "부족한 것은 인물이 아니라 장면"이고 공백은 지속으로만 메워진다는 판단 → 서술 패널 뒤 배경 레이어(알파+스크림), 장소·시간대 변경 시에만 교체. 헤더 밴드안은 모바일 뷰포트 25% 잠식(arch/86 서술 영역 반납)으로 기각. orphan `LocationImage.tsx`(90줄, 미import)는 크로스페이드 로직만 이식 후 삭제. 신규 에셋 0, 서술 파이프라인 무접촉. §7 후속으로 장소 라벨 정본화 | ✅ 완료 |
| **모바일 스크롤·뷰포트 정합 (2026-07-27)** | arch/94 — 헤드리스 모바일 4뷰포트(390x844/390x480/390x380/844x390) 실런 전수 점검 → 11종 수정. **P1** ① 서술 스크롤 되돌림: "하단 100px" 단일 임계를 follow 모델로 교체(사용자 제스처 감지 시 프로그램 스크롤 창 무효화·하단 32px 밖이면 추적 해제·터치 중 자동 스크롤 중단) — 실측 60px 위 스크롤 시 DOM 변화 1회에 하단 복귀하던 것이 스트리밍 전 구간 위치 유지로 ② `overscroll-contain` 전면 적용(Android 당겨서 새로고침 = 플레이 중 리로드 차단) ③ 타이틀·로그인 `overflow-hidden`+죽은 `maxHeight:600` 제거 → 바깥 `h-full overflow-y-auto`+안쪽 `min-h-full`(844x390 도달 불가 3개→0) ④ 모달 16곳 2패턴(중앙형 오버레이 스크롤+패널 `m-auto`, 바텀시트 `max-h-[88dvh]`+내부 스크롤). **P2** 상단 스페이서 `h-20`→`MOBILE_HEADER_OFFSET`(=`calc(env(safe-area-inset-top)+81px)` 단일 정본) · DeadlineBanner/PartyHUD가 fixed 헤더 뒤에 가리던 문제(PartyHUD를 레이아웃 내부로 이동, 배너 조건은 `useDeadlineBannerVisible()` export) · safe-area 미적용 7화면 보정 · viewport `interactive-widget=resizes-content`. 신규 규약 5(§5). 잔여=노치 실기기 육안 확인 | ✅ 완료 |
