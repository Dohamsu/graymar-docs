# Fixplan History — 플레이테스트 패치 아카이브

> 이 문서는 fixplan3/4/5를 통합한 역사 아카이브. 완료된 플레이테스트 패치 내역.
> 원본 3개 파일(총 1,061줄)을 압축하여 단일 히스토리로 재구성.

---

## Fixplan 3 — 초기 플레이테스트 10대 이슈 (2026-03-17)

첫 공식 플레이테스트에서 발견된 11개 이슈. P1~P11 번호로 분류, 대부분 완료.

| 이슈 | 심각도 | 상태 | 핵심 수정 |
|------|--------|------|----------|
| P1 structuredMemory 미작동 | Critical | ✅ 완료 | RUN_ENDED 전 `finalizeVisit()` 호출 추가 |
| P2 NPC 이름 공개 미작동 | Critical | ✅ 완료 | TAG_TO_NPC 기반 encounterCount 보충, context-builder NPC 이름 노출 |
| P3 정보 반복 루프 | High | ✅ 자동 개선 | P1 해결로 structuredMemory 정상화 |
| P4 MOVE_LOCATION 파싱 실패 | High | ✅ 완료 | 목표 불명확 시 HUB 복귀 처리 |
| P5 이벤트 2턴 반복 패턴 | Medium | ✅ 완료 | 씬 연속성 2턴→1턴 축소 (`consecutiveCount < 1`) |
| P6 NPC 태도 급변 | Medium | ✅ 완료 (03-19) | 프롬프트 posture 금지 규칙 + 행동 가이드 삽입 |
| P7 조기 NATURAL 엔딩 | Medium | ✅ 완료 | `checkEndingConditions`에 최소 15턴 가드 |
| P8 아이템 추적 실패 | Medium | ✅ 자동 개선 | P1 해결로 structuredMemory 추적 복구 |
| P9 선택지 affordance 편향 | Low | ✅ 완료 (03-19) | CHOICES 다양성 규칙 추가 |
| P10 NPC 에필로그 조사 오류 | Low | ✅ 완료 | `korParticle()` 조사 유틸 적용 |
| P11 turnNo 갭 (T3 누락) | Low | ⚠️ 미구현 | 의도된 동작 (SYSTEM 턴 소비) |

### 주요 진단 포인트

- **P1**: turns.service.ts의 handleLocationTurn에서 MemoryCollector.collect() 누락, go_hub 분기에서 finalizeVisit() 누락. VisitAction의 relatedNpcId 전달도 필요.
- **P2**: `effectiveNpcId` 통합 이슈 — matchedEvent.payload.primaryNpcId 우선, TurnOrchestration NPC 주입 fallback. 둘 다 없으면 encounterCount가 영원히 0. 이벤트 라이브러리에 primaryNpcId 보강 필요.
- **P4**: LOCATION 내 ACTION 자유 텍스트 이동 의도 처리. IntentParserV2에 MOVE_LOCATION 키워드 추가("이동", "떠나", "나가" 등) + go_hub와 동일 처리(장기기억 저장 + HUB 복귀).
- **P5**: LOC_MARKET의 매칭 가능 이벤트 풀이 5개뿐 → 쿨다운 있어도 순환. 이벤트 추가 + ProceduralEventService fallback 체인 확인 + recentEventIds hard block 최근 2개로 확장.
- **P7**: INC_MARKET_THEFT가 control ≥ 80으로 CONTAINED → 13턴 만에 NATURAL 엔딩. `MIN_TURNS_FOR_NATURAL=15` 가드 추가.
- **P10**: `${name}은(는)` 하드코딩 → `attachPostposition(name, '은는')` 로 배치 판정 유틸 치환.

### 권장 작업 순서
P1 → P2 → P4 → P5. P1 해결 시 P3/P8 자동 개선. P10은 독립적.

---

## Fixplan 4 — 20턴 플레이테스트 6대 이슈 (2026-03-18)

20턴 확장 플레이테스트에서 발견된 Incident·NPC 시스템 정상화 이슈.

| 이슈 | 심각도 | 상태 | 핵심 수정 |
|------|--------|------|----------|
| F1 Incident 미발생 | Critical | ✅ 완료 | 초기 hubHeat 0→15, spawn 확률 20%→40% |
| F2 NPC encounterCount 미증가 | Critical | ✅ 완료 | primaryNpcId 보강 + TAG_TO_NPC 확장 + NPC_LOCATION_AFFINITY 보강 |
| F3 NPC posture = None (API) | High | ✅ 완료 | API 직렬화 경로 확인 |
| F4 감정축 비활성 (trust/fear) | Medium | ✅ F2 의존 | F2 해결로 applyActionImpact 호출 복구 |
| F5 structuredMemory API 빈 응답 | Critical | ✅ 완료 | GET /runs/:id 응답에 structuredMemory 포함 |
| F6 resolveOutcome 필드 위치 | Low | ✅ 오진 | `serverResult.ui.resolveOutcome` 경로 (스크립트 수정) |

### 주요 진단 포인트

- **F1**: day=1, heat=0에서 eligible한 사건이 INC_MARKET_THEFT 1개뿐. 초기 hubHeat를 15로 부스트하면 INC_SMUGGLING_RING(minHeat:10)까지 2개 즉시 활성.
- **F2**: encounterCount 증가 3경로(eventPrimaryNpc / TAG_TO_NPC / orchestration)에서 누락 NPC 다수. NPC_MIRELA/RENNICK/ROSA/CAPTAIN_BREN 등 4명이 NPC_LOCATION_AFFINITY에 없음.
- **F5 [PRIMARY]**: `runs.service.ts` L490-495 memory 응답에 theme/storySummary만 포함, structuredMemory는 DB 저장되지만 API 미반환. 1줄 추가로 해결.
- **F6**: 플레이테스트 스크립트의 `serverResult.resolveOutcome` 접근 경로가 틀림. `ui.resolveOutcome`이 정본. 비도전 행위(TALK/REST)는 `hideResolve=true`로 의도적으로 숨김.

### 수정 파일 요약
- `world-state.service.ts` — hubHeat 초기값
- `incident-management.service.ts` — spawn 확률
- `runs.service.ts` — structuredMemory API 노출
- `turns.service.ts` — MemoryCollector 에러 로깅
- `content/graymar_v1/events_*.json` — primaryNpcId 보강
- `memory-collector.service.ts` — TAG_TO_NPC 확장
- `turn-orchestration.service.ts` — NPC_LOCATION_AFFINITY 보강

---

## Fixplan 5 — 몰입성 종합 점검 (2026-03-19)

5축(NPC 일관성/장면 연속성/기억 신뢰도/입력 반응성/콘텐츠 다양성) 전수 조사.
20개 이슈(I-01~I-20) 중 대부분 구현 완료, 일부 콘텐츠 확충 잔존.

### 1. NPC 일관성 (I-01 ~ I-05)

| 이슈 | 심각도 | 상태 | 핵심 수정 |
|------|--------|------|----------|
| I-01 NPC 갑자기 다른 인물 교체 | Critical | ✅ 완료 | EventMatcher NPC 연속성 +25/+10 가중치, BLOCK 예외 |
| I-02 NPC 정보 망각 | Critical | ✅ 완료 | NPC Knowledge Ledger 7종 actionType 트리거 + primaryNpcId/TAG_TO_NPC 경로 |
| I-03 NPC 태도 맥락 없이 급변 | High | ✅ 완료 | prompt-builder posture 강제 지시 + 5종 posture별 LLM 행동 가이드 |
| I-04 NPC 이름 영원히 비공개 | Medium | ✅ 완료 | events.json primaryNpcId / TAG_TO_NPC 매핑 전수 검증 |
| I-05 NPC 대사 부자연 반복 | Medium | ✅ I-02 의존 | NPC Knowledge 정상화로 LLM이 이전 대사 인지 |

**posture별 LLM 가이드 (system-prompts.ts)**
- CAUTIOUS: 경계, 모호한 답변, 자발 정보 제공 금지
- HOSTILE: 대화 거부 가능, 위협적 어조
- FRIENDLY: 자발 도움 가능, resolve 결과에 따라 제한
- CALCULATING: 대가 없는 정보 금지, 교환 조건
- FEARFUL: 말을 아낌, 시선 피함, 압박에 쉽게 무너짐

### 2. 장면 연속성 (I-06 ~ I-09)

| 이슈 | 심각도 | 상태 | 핵심 수정 |
|------|--------|------|----------|
| I-06 장면 장소 점프 | Critical | ✅ 완료 | sceneFrame 3단계 억제(그대로→격하→완전 억제) |
| I-07 LOCATION 재방문 기억 없음 | High | ✅ 완료 | renderLocationRevisitContext() locationId 필터링 + NPC knowledge 통합 |
| I-08 장소 전환 직전 맥락 끊김 | Medium | ✅ 완료 | previousVisitContext minTokens=50 보호 + Cross-Location Facts(importance≥0.7) |
| I-09 전투→탐험 복귀 맥락 끊김 | Medium | ⚠️ 잔존 위험 | 장기 전투 시 locationSessionTurns에서 탐험 맥락 밀림 |

### 3. 기억 시스템 (I-10 ~ I-13)

| 이슈 | 심각도 | 상태 | 핵심 수정 |
|------|--------|------|----------|
| I-10 6턴+ 체류 시 초반 망각 | High | ✅ 완료 | Mid Summary 2-pass (서버 뼈대 + 경량 LLM 압축) + fallback |
| I-11 MEMORY 태그 추출 누락 | High | ✅ 완료 | 파싱 상한 2→4개/50→80자, NPC_DIALOGUE 카테고리, llmExtracted 15→20 |
| I-12 후반 토큰 예산 초과 | High | ✅ 완료 | BlockPriority 20단계 + trimToTotalBudget + THEME 절대 보호 |
| I-13 structuredMemory 파이프라인 안정성 | High | ✅ 완료 | collect + finalizeVisit 3경로(go_hub/MOVE/RUN_ENDED) 회귀 감시 |

### 4. 입력 해석 (I-14 ~ I-16)

| 이슈 | 심각도 | 상태 | 핵심 수정 |
|------|--------|------|----------|
| I-14 자유 텍스트 파싱 실패 | High | ⚠️ 부분 | IntentParserV2 키워드 확충(살피/몰래/도와/훔치/거래), LLM fallback 제한적 |
| I-15 장소 이동 자유 텍스트 무시 | Medium | ✅ 완료 | MOVE_LOCATION 키워드 ("이동"/"떠나"/"나가") + HUB 복귀 처리 |
| I-16 고집 에스컬레이션 오발 전투 | Medium | ✅ 완료 | 2회째 경고 이벤트 + 3회째 에스컬레이션 |

### 5. 콘텐츠 다양성 (I-17 ~ I-20)

| 이슈 | 심각도 | 상태 | 핵심 수정 |
|------|--------|------|----------|
| I-17 같은 LOCATION 이벤트 순환 | Medium | ⚠️ 부분 | 씬 연속성 축소 ✅, LOCATION별 이벤트 풀 10개+ 확충은 콘텐츠 작업 잔존 |
| I-18 선택지 유형 편향 | Medium | ✅ 완료 | CHOICES 다양성 규칙 (직전 2턴과 다른 affordance 1개+) |
| I-19 게임 조기 종료 | Medium | ✅ 완료 | MIN_TURNS_FOR_NATURAL=15 가드, Incident spawn 빈도 검토 |
| I-20 DEFEAT 시 서사 없이 종료 | Medium | ✅ 단기 완료 | DEFEAT → EndingGenerator 호출 + 패배 내러티브. Downed 시스템은 중기 과제 |

### Coherence Phase별 상태 (2026-03-19 검증)

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | EventMatcher NPC 연속성 가중치 | ✅ 완료 (+25/+10, BLOCK 예외) |
| Phase 2 | NPC Knowledge Ledger | ✅ 완료 (7종 트리거, TAG_TO_NPC) |
| Phase 3 | Mid Summary 2-pass 경량 LLM | ✅ 완료 (fallback 포함) |
| Phase 4 | 장소별 재방문 기억 | ✅ 완료 (locationId 필터링) |
| Phase 5 | 토큰 트리밍 BlockPriority | ✅ 완료 (20단계 + THEME 보호) |

### Wave별 작업 요약

**Wave 1 — 검증 & 즉시 수정 (최소 변경)**
- I-13 structuredMemory 회귀 검증 (2h)
- I-01 NPC 연속성 가중치 동작 확인 (3h)
- I-02 NPC Knowledge 트리거 + events.json primaryNpcId 점검 (4h)
- I-04 events.json 전수 검증 (2h)
- I-11 MEMORY 태그 상한 코드 확인 (1h)

**Wave 2 — 프롬프트 & 설정 강화**
- I-03 posture 강제 지시 + 행동 가이드 (3h)
- I-18 CHOICES 다양성 규칙 (1h)
- I-16 고집 2회째 경고 이벤트 (2h)
- I-14 IntentParserV2 키워드 확충 (3h)

**Wave 3 — 시스템 구현**
- I-08 previousVisitContext minTokens 상향 (2h)
- I-20 DEFEAT 패배 내러티브 (4h)

**Wave 4 — 콘텐츠 확충**
- I-17 LOCATION별 이벤트 풀 10개+ 확보 (8h)
- I-06 ProceduralEventService fallback 활성화 (4h)
- I-18 events.json affordances[] 다양화 (4h)

---

## 종합

- Fixplan 3 (11개 이슈): 9 완료 / 1 자동해결 / 1 미구현(의도)
- Fixplan 4 (6개 이슈): 5 완료 / 1 오진(코드변경 불필요)
- Fixplan 5 (20개 이슈): 18 완료 / 2 부분완료(콘텐츠 확충 잔존: I-14 LLM fallback, I-17 이벤트 풀)

**잔존 콘텐츠 작업**
- LOCATION별 이벤트 풀 최소 10개 확보 (시장/경비대/항만/빈민가)
- IntentParserV2 LLM fallback 활성화 (confidence < 0.7)
- Downed 시스템 (HP 0 → 구조 이벤트 → 페널티)

> 구체적 코드 변경 내역과 파일 경로는 git 커밋 히스토리 참조.
