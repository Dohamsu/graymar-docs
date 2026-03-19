# 20 — 몰입성 종합 점검 & 수정 방향

> 선행 문서: `05_llm_narrative.md`, `19_context_coherence_reinforcement.md`, `fixplan3.md`, `18_narrative_runtime_patch.md`
> 목적: 플레이어가 텍스트 게임 플레이 중 체감하는 **몰입 파괴 지점**을 전수 조사하고, 수정 방향을 우선순위별로 정리한다.
> 기준일: 2026-03-19
> 원칙: "플레이어가 한 번이라도 '어?' 하고 멈추면 몰입은 깨진 것이다."

---

# 0. 점검 범위 & 판정 기준

## 0.1 점검 축 (5개)

| 축 | 설명 | 대표 증상 |
|----|------|-----------|
| **NPC 일관성** | NPC가 같은 인물로 느껴지는가 | 갑자기 다른 사람, 태도 급변, 정보 망각 |
| **장면 연속성** | 지금 어디서 뭘 하고 있는지 자연스러운가 | 장소 점프, 맥락 없는 묘사 전환 |
| **기억 신뢰도** | 게임 세계가 플레이어의 행동을 기억하는가 | 정보 반복, 아이템 추적 실패, 재방문 기억 없음 |
| **입력 반응성** | 내가 쓴 문장이 의도대로 해석되는가 | 엉뚱한 액션 매핑, 장소 이동 실패, 에스컬레이션 오발 |
| **콘텐츠 다양성** | 같은 장소에서 반복감 없이 플레이 가능한가 | 이벤트 순환, 선택지 편향, 조기 엔딩 |

## 0.2 심각도 기준

| 등급 | 기준 | 체감 |
|------|------|------|
| 🔴 Critical | 1회 발생만으로 몰입 완전 파괴. 플레이 의욕 상실 | "이 게임 버그 있는 거 아니야?" |
| 🟠 High | 반복 발생 시 몰입 누적 훼손. 서사 신뢰도 저하 | "또 이런 식이네…" |
| 🟡 Medium | 불편하지만 플레이 지속 가능. 개선하면 체감 상승 | "좀 아쉽긴 한데" |
| ⚪ Low | 인지하기 어렵거나 미미한 수준. 개선 시 polish 향상 | "있으면 좋겠다" |

---

# 1. NPC 일관성 점검

## I-01. NPC가 갑자기 다른 인물로 교체된다

| 항목 | 내용 |
|------|------|
| **심각도** | 🔴 Critical |
| **증상** | "경비대장에게 더 물어본다" 입력 → 다음 턴에 상인 NPC가 등장 |
| **근본 원인** | EventMatcher가 `affordance(INVESTIGATE)` 키워드만 보고 이벤트 매칭. 직전 턴의 NPC를 고려하지 않음 |
| **영향 체인** | EventMatcher가 다른 NPC 이벤트 선택 → `actionContext.primaryNpcId` 변경 → `[현재 장면 상태]` 대화 상대 교체 → LLM 연속성 규칙과 서버 맥락 충돌 |
| **현재 상태** | Context Coherence Phase 1(NPC 연속성 가중치) **✅ 구현 완료**. +25/+10 보너스, BLOCK 예외 모두 동작 확인 |
| **관련 파일** | `event-matcher.service.ts`, `turns.service.ts` |
| **관련 문서** | `19_context_coherence_reinforcement.md` §2 |

### 수정 방향

1. **EventMatcher에 sessionNpcContext 전달 확인**: `turns.service.ts`의 LOCATION 턴 처리에서 `lastPrimaryNpcId`, `sessionTurnCount`, `interactedNpcIds`를 조립하여 EventMatcher에 실제로 전달하고 있는지 코드 확인
2. **NPC 연속성 가중치 동작 확인**: 직전 턴 NPC와 동일 NPC 이벤트에 +25 보너스, 방문 내 상호작용 NPC에 +10 보너스가 실제 적용되는지 로그 확인
3. **예외 처리 확인**: BLOCK matchPolicy 이벤트에서는 NPC 보너스 무시 ✅ (참고: `sessionTurnCount < 2` 가드는 코드에 미존재 — 첫 턴부터 보너스 적용됨)

### 검증 체크리스트

- [ ] 같은 NPC와 3턴 연속 대화 시 해당 NPC 이벤트가 우선 선택되는가
- [ ] NPC 없는 행동(SEARCH, OBSERVE)에서는 보너스가 0인가
- [ ] BLOCK 이벤트는 NPC 보너스를 무시하는가
- [ ] 로그에서 `npcContinuityBonus` 값을 확인할 수 있는가

---

## I-02. NPC가 이미 알려준 정보를 다시 처음 알려주는 척 한다

| 항목 | 내용 |
|------|------|
| **심각도** | 🔴 Critical |
| **증상** | 경비대장에게 밀수 증거를 보여줬는데, 다음 방문에서 "밀수라니, 무슨 말이오?" |
| **근본 원인** | (A) NPC Knowledge Ledger 수집 파이프라인 불완전 (B) `targetNpcId`가 null이면 수집 자체가 안 됨 |
| **영향 체인** | `MemoryCollector.collectNpcKnowledge()` 미트리거 → `npcKnowledge[npcId]` 비어 있음 → 프롬프트에 "이 인물이 알고 있는 것" 없음 → LLM이 NPC를 무지 상태로 서술 |
| **현재 상태** | Fixplanv1 PR4(NPC Knowledge)가 설계·구현됨. **수집 트리거 7종 대화형 actionType 경로 검증 필요** |
| **관련 파일** | `memory-collector.service.ts`, `prompt-builder.service.ts`, `memory-renderer.service.ts` |
| **관련 문서** | `19_context_coherence_reinforcement.md` §3, `04_llm_memory_guide.md` NPC Knowledge 섹션 |

### 수정 방향

1. **수집 트리거 검증**: 7종 대화형 actionType(TALK, PERSUADE, BRIBE, INVESTIGATE, OBSERVE, HELP, THREATEN) + SUCCESS/PARTIAL 판정 + `targetNpcId` 존재 시 실제로 `collectNpcKnowledge()` 호출되는지 확인
2. **targetNpcId 경로 확인**: `primaryNpcId` 우선 → 없으면 `eventTags`에서 `TAG_TO_NPC` 매핑 → 둘 다 없으면 null (수집 불가). 이벤트 라이브러리에서 NPC 관련 이벤트에 `primaryNpcId` 또는 적절한 eventTags가 있는지 전수 점검
3. **프롬프트 렌더링 확인**: `[등장 가능 NPC 목록]`에서 "이 인물이 알고 있는 것: ..." + "⚠️ 처음 듣는 것처럼 반응하면 안 됩니다" 경고가 실제 출력되는지 확인
4. **LLM `[MEMORY:NPC_KNOWLEDGE:ID]` 태그 파싱 확인**: `llm-worker.service.ts`에서 한국어 NPC ID 포함 regex가 정상 동작하는지 확인 (Fixplan5에서 `[\w:]` → `[^\]]` 변경됨)

### 검증 체크리스트

- [ ] TALK + SUCCESS 시 npcKnowledge에 엔트리가 생성되는가
- [ ] LLM이 `[MEMORY:NPC_KNOWLEDGE:ID]` 태그를 출력하면 파싱되는가
- [ ] NPC 재등장 시 프롬프트에 knowledge가 "이 인물이 알고 있는 것"으로 표시되는가
- [ ] NPC당 5개 초과 시 importance 낮은 것이 제거되는가

---

## I-03. NPC 태도가 맥락 없이 급변한다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟠 High |
| **증상** | CAUTIOUS 상태의 NPC가 갑자기 열쇠를 건네주며 친절하게 행동 |
| **근본 원인** | (A) LLM이 서사 진행을 위해 `effectivePosture`를 무시 (B) 프롬프트에 posture 강제 지시가 약함 |
| **현재 상태** | fixplan3 P6 — **✅ 구현 완료** (2026-03-19). posture별 행동 가이드 + 금지 규칙 삽입 |
| **관련 파일** | `prompt-builder.service.ts`, `system-prompts.ts` |

### 수정 방향

1. **프롬프트 posture 강제 지시 추가** (`prompt-builder.service.ts`):
   - `[현재 장면 상태]` 블록에 posture 표기 + 명시적 금지 규칙 삽입
   - 형식: `"이 NPC는 현재 {posture} 태도입니다. {posture}에 맞지 않는 행동(자발적 정보 제공, 호의적 태도)은 절대 서술하지 마세요."`
2. **resolveOutcome과 posture 연동 강화**:
   - CAUTIOUS NPC + PERSUADE → PARTIAL 판정이면 LLM에 "부분적으로만 응함" 명시
   - HOSTILE NPC + TALK → FAIL이면 "대화 자체를 거부하는 장면" 유도
3. **posture별 LLM 행동 가이드 테이블 추가** (`system-prompts.ts`):

```
CAUTIOUS: 경계. 질문에 모호하게 답함. 자발적 정보 제공 금지.
HOSTILE: 적대. 대화 거부 가능. 위협적 어조.
FRIENDLY: 호의적. 자발적 도움 가능. 단, resolve 결과에 따라 제한.
CALCULATING: 타산적. 대가 없는 정보 제공 금지. 교환 조건 제시.
FEARFUL: 두려움. 말을 아끼고, 시선을 피하며, 압박에 쉽게 무너짐.
```

### 검증 체크리스트

- [ ] CAUTIOUS NPC가 SUCCESS 판정 없이 핵심 정보를 자발 제공하는 서술이 나오지 않는가
- [ ] HOSTILE NPC가 PARTIAL 판정에서 협조적으로 서술되지 않는가
- [ ] posture 변경 시 LLM 서술이 자연스럽게 전환되는가

---

## I-04. NPC 이름이 영원히 공개되지 않는다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 7턴 연속 만나도 계속 "그 수상한 남자"로 호칭 |
| **근본 원인** | 이벤트에 `primaryNpcId`가 없고, TurnOrchestration NPC 주입도 안 되면 encounterCount가 영원히 0 |
| **현재 상태** | fixplan3 P2 — ✅ 완료 (TAG_TO_NPC 기반 보충). **이벤트 라이브러리 전수 검증 필요** |
| **관련 파일** | `turns.service.ts`, `events.json` |

### 수정 방향

1. **events.json 전수 점검**: 모든 LOCATION 이벤트에 `primaryNpcId` 또는 NPC 연결 가능한 `eventTags`가 있는지 확인
2. **encounterCount 로그 추가**: 턴 처리 후 effectiveNpcId + encounterCount 값을 디버그 로그에 기록
3. **unknownAlias 이탈 조건 확인**: `shouldIntroduce(npcState, posture)` 함수의 posture별 임계값(FRIENDLY=1, CAUTIOUS=2, HOSTILE=3)이 의도대로 동작하는지 확인

### 검증 체크리스트

- [ ] 모든 LOCATION의 NPC 관련 이벤트에 primaryNpcId 또는 TAG_TO_NPC 매핑 가능한 태그가 있는가
- [ ] `introduced === false`인 NPC의 실명이 incidentContext, signalContext 등 다른 블록에서 노출되지 않는가
- [ ] 소개 조건 도달 시 자연스러운 이름 공개 서술이 생성되는가

---

## I-05. NPC 대사가 부자연스럽게 반복된다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 같은 NPC가 매 턴 비슷한 뉘앙스의 대사를 반복 |
| **근본 원인** | `[이번 방문 대화]` 규칙 6번(정보 반복 금지)이 있으나, LLM이 충분한 맥락 없이 유사한 내용 재생성 |
| **현재 상태** | 규칙은 존재하지만 **NPC Knowledge + Narrative Thread**가 정상 동작해야 실효성 있음 |
| **관련 파일** | `system-prompts.ts`, `llm-worker.service.ts` |

### 수정 방향

1. I-02 해결이 선행 조건 — NPC Knowledge가 정상 수집·전달되면 LLM이 이전 대사 내용을 인지하고 반복 회피 가능
2. `[MEMORY:NPC_DIALOGUE]` 카테고리 추출 확인 — NPC가 구체적으로 말한 정보(이름, 장소, 시간, 숫자)가 추출되어야 다음 턴에서 반복 방지 가능
3. Narrative Thread(`[THREAD]`) 누적 확인 — 장면 요약에 "이미 한 대화"가 기록되어야 LLM이 다음 방향으로 서사를 진행

---

# 2. 장면 연속성 점검

## I-06. 매 턴 장면이 다른 장소로 점프한다

| 항목 | 내용 |
|------|------|
| **심각도** | 🔴 Critical |
| **증상** | 창고 앞에서 조사 중인데 갑자기 시장 한복판 묘사 등장 |
| **근본 원인** | EventMatcher가 매 턴 다른 이벤트 선택 → `eventSceneFrame` 변경 → LLM 장면 점프 |
| **현재 상태** | sceneFrame 3단계 억제 + `[현재 장면 상태]` 블록 + 씬 이벤트 1턴 유지 — **✅ 구현됨** |
| **잔존 위험** | LOCATION별 이벤트 풀이 극소수면 sceneFrame이 계속 바뀌어 억제 메커니즘의 효과 감소 |
| **관련 파일** | `context-builder.service.ts`, `prompt-builder.service.ts`, `event-matcher.service.ts` |

### 수정 방향

1. **sceneFrame 3단계 억제 동작 확인**:
   - 첫 턴: sceneFrame 그대로 전달
   - 1턴 진행: `[참고 배경]`으로 격하 + "인물/장소 전환 금지"
   - 2턴 이상: 완전 억제 + "장면 연속성 절대 우선"
2. **이벤트 풀 확충** (근본 해결): LOCATION별 매칭 가능 이벤트 수를 최소 10개 이상으로 확보. 현재 LOC_MARKET 등에서 실제 통과 가능한 이벤트가 몇 개인지 집계
3. **ProceduralEventService fallback 확인**: 고정 이벤트 → 절차적 이벤트 → atmosphere fallback 체인에서 절차적 이벤트가 실제 생성되는지 확인

### 검증 체크리스트

- [ ] 2턴 이상 진행 시 sceneFrame이 완전 억제되는가
- [ ] `[현재 장면 상태]` 블록에 대화 상대/위치/직전 행동이 정확히 기록되는가
- [ ] LOCATION별 매칭 가능 이벤트가 최소 10개 이상인가

---

## I-07. LOCATION 재방문 시 이전 행동 흔적이 없다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟠 High |
| **증상** | 시장에서 밀수 증거를 찾았는데, 재방문 시 아무 일도 없었던 것처럼 묘사 |
| **근본 원인** | visitLog가 장소별로 필터링되지 않거나, `[이 장소의 이전 방문]` 블록이 렌더링되지 않음 |
| **현재 상태** | Context Coherence Phase 4(장소별 재방문 기억) **✅ 구현 완료**. `memory-renderer.service.ts:270-318` renderLocationRevisitContext()에서 locationId 필터링 + NPC knowledge 통합 |
| **관련 파일** | `memory-renderer.service.ts`, `context-builder.service.ts`, `prompt-builder.service.ts` |

### 수정 방향

1. **`[이 장소의 이전 방문]` 블록 생성 확인**: 재방문 시 해당 locationId의 visitLog 엔트리가 별도 블록으로 렌더링되는지 확인
2. **`[이야기 요약]` 중복 제거 확인**: 현재 장소 엔트리가 `[이야기 요약]`에서 제외되는지 확인
3. **이전 방문의 NPC knowledge 포함 확인**: 해당 장소에서 획득한 NPC 정보가 블록에 포함되는지 확인

### 검증 체크리스트

- [ ] 재방문 시 `[이 장소의 이전 방문]` 블록이 프롬프트에 포함되는가
- [ ] 첫 방문 시 블록이 생략되는가
- [ ] `[이야기 요약]`에서 현재 장소 관련 엔트리가 중복 제거되는가

---

## I-08. 장소 전환 시 직전 장소 맥락이 끊긴다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 시장에서 중요한 단서를 발견하고 경비대로 이동 → 경비대 첫 턴에서 시장 맥락 완전 소실 |
| **근본 원인** | `previousVisitContext` 토큰 예산 150, `minTokens=0`이라 예산 압박 시 완전 제거 가능 |
| **현재 상태** | **✅ 구현 완료** (2026-03-19). `[직전 장소 정보]` 블록 + minTokens=50 보호 |
| **관련 파일** | `token-budget.service.ts`, `memory-integration.service.ts` |

### 수정 방향

1. **`previousVisitContext` minTokens를 50 이상으로 상향**: 완전 제거 방지. 최소한 keyActions(max 3) + unresolvedLeads(max 2) 정도는 보존
2. **Cross-Location Facts 확인**: 타 장소 사실 중 importance≥0.7인 것이 `[기억된 사실]` 블록에 `[장소명]` 접두사와 함께 포함되는지 확인 (max 3개)

### 검증 체크리스트

- [ ] 장소 전환 직후 첫 턴에 `[직전 장소 정보]` 블록이 포함되는가
- [ ] 토큰 예산 압박 시에도 최소 50토큰은 보존되는가
- [ ] 타 장소 중요 사실(importance≥0.7)이 `[기억된 사실]`에 포함되는가

---

## I-09. 전투 종료 후 탐험 장면으로 복귀 시 맥락 끊김

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 시장에서 도둑을 쫓다 전투 → 전투 종료 후 LOCATION 복귀 시 "조용한 시장 풍경" 묘사 |
| **근본 원인** | 전투 중 `skipLlm: true`로 내러티브 없이 진행 → 전투가 길면 탐험 맥락이 locationSessionTurns에서 밀려남 |
| **현재 상태** | 설계상 COMBAT 시 부모 LOCATION 턴이 locationSessionTurns에 포함됨. 장기 전투 시 누락 가능성 |
| **관련 파일** | `context-builder.service.ts` |

### 수정 방향

1. **전투 종료 → LOCATION 복귀 시 `currentSceneContext` 재구축 확인**: 전투 직전 탐험 장면의 NPC/위치/상황이 `[현재 장면 상태]`에 복원되는지 확인
2. **전투 결과 요약이 LOCATION 맥락에 반영되는지 확인**: VICTORY/FLEE 결과가 다음 LOCATION 턴의 `events[]` 또는 `summary.short`에 포함되어야 LLM이 자연스럽게 이어갈 수 있음

---

# 3. 기억 시스템 점검

## I-10. 6턴 이상 체류 시 초반 대화를 잊는다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟠 High |
| **증상** | 5턴 전 NPC가 알려준 핵심 정보를 LLM이 기억하지 못함 |
| **근본 원인** | locationSessionTurns 4턴 제한 + Mid Summary 200자에 NPC 대사 디테일 미포함 |
| **현재 상태** | Context Coherence Phase 3(경량 LLM 요약) **✅ 구현 완료**. `mid-summary.service.ts:26-50` 2-pass(서버 뼈대 + 경량 LLM 압축) + fallback |
| **관련 파일** | `mid-summary.service.ts`, `llm-caller.service.ts` |

### 수정 방향

**단기 (LLM 호출 없이):**

1. **Mid Summary에 NPC 대사 핵심 포함**: 현재 `summary.short` 기반인 요약에, `[MEMORY:NPC_DIALOGUE]`로 추출된 사실을 추가 삽입
2. **locationSessionTurns 4턴 이전 서술 100자 → 150자 상향**: 토큰 비용 증가 ~17토큰/턴. 8턴 방문 기준 +68토큰으로 RECENT_STORY 예산(700) 내 수용 가능

**중기 (Phase 3 구현):**

3. **2-pass Mid Summary**:
   - 1단계: 서버가 뼈대(actionType + outcome + eventId + relatedNpcId + summaryShort) 조립
   - 2단계: 경량 LLM이 서술 snippet 포함하여 400자 요약 생성
4. **경량 LLM 호출 인프라**: `llm-caller.service.ts`에 `callLight()` 추가, `llm-config.service.ts`에 경량 모델 설정
5. **실패 시 fallback**: 경량 LLM 실패 → 1단계 서버 뼈대만 사용 (현재 Mid Summary와 동일)

### 검증 체크리스트

- [ ] 6턴 초과 방문에서 Mid Summary에 NPC 대사 핵심이 포함되는가
- [ ] (Phase 3 후) 경량 LLM 호출이 발생하는가
- [ ] (Phase 3 후) 경량 LLM 실패 시 서버 뼈대 요약으로 fallback되는가
- [ ] 12턴 방문 시 재압축이 정상 동작하는가

---

## I-11. `[MEMORY]` 태그 추출 누락으로 장기 기억 소실

| 항목 | 내용 |
|------|------|
| **심각도** | 🟠 High |
| **증상** | NPC가 알려준 구체적 정보(이름, 시간, 장소)가 다음 방문에서 참조 불가 |
| **근본 원인** | LLM이 `[MEMORY]` 태그를 빠뜨리면 해당 정보가 영구 소실. 추출은 LLM 재량에 의존 |
| **현재 상태** | 태그 예산 확대(2→4개, 50→80자) + NPC_DIALOGUE 카테고리 추가 — **설계됨, 구현 확인 필요** |
| **관련 파일** | `llm-worker.service.ts`, `system-prompts.ts`, `memory-renderer.service.ts` |

### 수정 방향

1. **파싱 상한 변경 확인**: `MAX_MEMORY_TAGS = 4`, `MAX_MEMORY_LENGTH = 80`으로 실제 변경되었는지 확인
2. **System Prompt 지시 강화 확인**: "NPC_DIALOGUE: NPC가 구체적으로 알려준 정보는 반드시 추출하세요" 지시가 포함되었는지 확인
3. **llmExtracted 상한 확인**: 15→20개로 변경되었는지 확인
4. **서버 측 보완 수집**: LLM 태그 추출에만 의존하지 않고, `MemoryCollector.collectNpcKnowledge()`에서 `source: 'AUTO_COLLECT'`로 이벤트 태그 기반 자동 수집이 동작하는지 확인

### 검증 체크리스트

- [ ] `[MEMORY]` 태그가 턴당 최대 4개 파싱되는가
- [ ] `NPC_DIALOGUE` 카테고리가 정상 저장되는가
- [ ] llmExtracted가 20개 상한으로 동작하는가
- [ ] 항목당 80자 초과 시 절삭되는가

---

## I-12. 게임 후반 토큰 예산 초과로 중요 정보 무작위 손실

| 항목 | 내용 |
|------|------|
| **심각도** | 🟠 High |
| **증상** | 20턴 이후 프롬프트에서 중요 NPC 관계나 사건 일지가 갑자기 사라짐 |
| **근본 원인** | 동적 예산 트리밍(Phase 5) 미완성. 총 예산 2500 토큰 초과 시 잘리는 블록이 비결정적 |
| **현재 상태** | Context Coherence Phase 5 — **✅ 구현 완료**. `token-budget.service.ts:131-180` BlockPriority(20단계) + trimToTotalBudget() + THEME 절대 보호 |
| **관련 파일** | `token-budget.service.ts` |

### 수정 방향

1. **블록별 우선순위 체계 구현**: 19번 문서 §6.4의 `BlockPriority` enum 적용
2. **결정적 트리밍 알고리즘**: 낮은 우선순위부터 문장 경계 기준 트리밍 → `minTokens` 도달 시 다음 블록으로 이동 → `minTokens=0` 블록은 완전 제거 가능
3. **절대 보호**: THEME(L0)은 `priority=100`, 삭제 불가
4. **핵심 보호**: SCENE_CONTEXT `minTokens=80`, RECENT_STORY `minTokens=200`

### 검증 체크리스트

- [ ] 총 토큰 2500 초과 시 EQUIPMENT_TAGS → SIGNAL_CONTEXT 순으로 먼저 잘리는가
- [ ] THEME은 절대 잘리지 않는가
- [ ] SCENE_CONTEXT가 80 토큰 이하로 줄어들지 않는가
- [ ] llmExtracted 20개 초과 시 importance 기반 교체가 동작하는가

---

## I-13. structuredMemory 저장 파이프라인 안정성

| 항목 | 내용 |
|------|------|
| **심각도** | 🟠 High (재발 시 Critical) |
| **증상** | `[이야기 요약]`, `[NPC 관계]`, `[사건 일지]` 블록이 모두 빈 상태 |
| **근본 원인** | fixplan3 P1에서 진단된 `MemoryCollector.collect()` 미호출 또는 `finalizeVisit()` 누락 |
| **현재 상태** | fixplan3 P1 — ✅ 완료. **회귀 방지를 위한 지속 모니터링 필요** |
| **관련 파일** | `turns.service.ts`, `memory-collector.service.ts`, `memory-integration.service.ts` |

### 수정 방향

1. **매 LOCATION 턴에서 `MemoryCollector.collect()` 호출 확인**: handleLocationTurn 내 Resolve 완료 직후
2. **go_hub / MOVE_LOCATION / RUN_ENDED 3개 경로 모두에서 `finalizeVisit()` 호출 확인**
3. **VisitAction에 relatedNpcId 전달 확인**: 없으면 `updateNpcJournal()` NPC별 필터링 불가
4. **런타임 헬스체크 고려**: structuredMemory가 N턴 이상 비어있으면 경고 로그 출력

### 검증 체크리스트

- [ ] LOCATION 5턴 플레이 후 go_hub 시 `run_memories.structuredMemory`에 visitLog, npcJournal이 생성되는가
- [ ] RUN_ENDED 시에도 `finalizeVisit()`이 호출되는가
- [ ] VisitAction.relatedNpcId가 NPC 관련 행동에서 null이 아닌가
- [ ] lastExitSummary가 정상 생성되는가

---

# 4. 입력 해석 점검

## I-14. 자유 텍스트 파싱 실패 — 의도와 다른 행동 실행

| 항목 | 내용 |
|------|------|
| **심각도** | 🟠 High |
| **증상** | "조심스럽게 문 뒤를 살핀다" → OBSERVE가 아닌 엉뚱한 액션. 또는 매칭 실패로 기본 액션 축소 |
| **근본 원인** | 100% Rule Parser 기반. LLM 보조 파싱 미구현. 키워드 테이블에 없는 표현은 처리 불가 |
| **현재 상태** | IntentParserV2 키워드 테이블에 기본 키워드 등록 완료(살피/몰래/도와/훔치/거래 등). **추가 확충 여지 있음**. LLM fallback 경로 제한적 |
| **관련 파일** | `intent-parser-v2.service.ts`, `llm-intent-parser.service.ts`, `rule-parser.service.ts` |

### 수정 방향

**단기 (키워드 확충):**

1. **IntentParserV2 키워드 테이블 확충**: 현재 누락된 자연어 표현 추가
   - INVESTIGATE: "살피", "조사", "확인", "알아보", "파악", "뒤지"
   - SNEAK: "몰래", "살금살금", "숨어서", "은밀하게", "들키지 않게"
   - HELP: "도와", "구해", "치료", "간호"
   - STEAL: "훔치", "슬쩍", "빼앗", "가로채"
   - TRADE: "거래", "흥정", "매매", "교환", "구입", "구매"
2. **복합 문장 분해 개선**: "경비대장에게 밀수 증거를 보여주며 설득한다" → target: 경비대장, actionType: PERSUADE

**중기 (LLM fallback 활성화):**

3. **Rule Parser `confidence < 0.7` 시 LLM 보조 파싱 경로 활성화**
4. **LLM 파싱 결과 제한**: Intent JSON만 출력, 새 능력/아이템 생성 금지, 수치 판단 금지

### 검증 체크리스트

- [ ] "조심스럽게 문 뒤를 살핀다" → INVESTIGATE 또는 OBSERVE로 매핑되는가
- [ ] "몰래 뒷골목으로 빠진다" → SNEAK으로 매핑되는가
- [ ] "경비대장에게 증거를 보여준다" → target: 경비대장 + PERSUADE로 매핑되는가
- [ ] 매칭 완전 실패 시 OBSERVE(기본)로 축소되며 LLM에 적절한 서술 유도가 가능한가

---

## I-15. 장소 이동 자유 텍스트가 무시된다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | "다른 곳으로 가자", "여기서 나가고 싶다" → 아무 반응 없거나 OBSERVE로 축소 |
| **근본 원인** | LOCATION 내에서 자유 텍스트로 이동 의도 표현 시 go_hub CHOICE 안내 부족 |
| **현재 상태** | fixplan3 P4 — ✅ 완료 (MOVE_LOCATION → HUB 복귀 처리) |
| **관련 파일** | `intent-parser-v2.service.ts` |

### 수정 방향

1. **MOVE_LOCATION 키워드 확인**: "이동", "다른 장소", "떠나", "나가", "돌아가" 등이 IntentParserV2에 등록되어 있는지 확인
2. **처리 흐름 확인**: MOVE_LOCATION 파싱 성공 → go_hub와 동일 처리(finalizeVisit + HUB 복귀) + LLM에 "장소를 떠나는 장면" 서술 유도

---

## I-16. 고집 에스컬레이션이 의도치 않게 전투를 유발한다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 같은 유형 행동을 3번 시도 → 갑자기 전투 발생 (THREATEN → FIGHT 자동 승격) |
| **근본 원인** | 고집 시스템이 "같은 패턴 3회 억제 → 자동 에스컬레이션"인데, 플레이어 확인/경고 없음 |
| **현재 상태** | ✅ 구현 완료 (2026-03-19). 2회째 경고 이벤트 + 3회째 에스컬레이션 |
| **관련 파일** | `intent-parser-v2.service.ts` |

### 수정 방향

1. **에스컬레이션 전 경고 삽입**: 2회 억제 시 서버가 `serverResult.events[]`에 경고 이벤트 추가 → LLM이 "분위기가 험악해지고 있다" 류의 복선 서술
2. **에스컬레이션 행동을 CHOICE로 제시**: 3회째에 자동 승격 대신, "강행한다 / 물러선다" CHOICE 제공
3. **LOCATION 이동 또는 HUB 복귀 시 초기화 확인**: actionHistory 최대 10개, 장소 이탈 시 리셋

---

# 5. 콘텐츠 다양성 점검

## I-17. 같은 LOCATION에서 이벤트가 반복 순환한다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 시장에서 5턴 이상 머물면 비슷한 이벤트가 2-3개 순환 |
| **근본 원인** | LOCATION별 매칭 가능 이벤트가 극소수 + ProceduralEventService fallback 미작동 가능 |
| **현재 상태** | fixplan3 P5 — 씬 연속성 축소(2턴→1턴) 완료. **이벤트 풀 자체는 콘텐츠 문제** |
| **관련 파일** | `events.json`, `event-matcher.service.ts`, `procedural-event.service.ts`(존재 시) |

### 수정 방향

1. **LOCATION별 이벤트 풀 집계**: 각 LOCATION(시장/경비대/항만/빈민가)에서 현재 stage/conditions/gates를 통과하는 이벤트가 몇 개인지 실측. **최소 10개 이상** 확보 목표
2. **ProceduralEventService 동작 확인**: "고정 이벤트 → 절차적 이벤트 → atmosphere fallback" 체인이 실제 동작하는지 확인
3. **recentEventIds hard block 범위 확장 고려**: 현재 `recentEventIds[last]` 1개 → 최근 2개로 확장하면 기계적 2턴 반복 즉시 방지
4. **이벤트 추가 제작**: 장소별 범용 이벤트(환경 묘사, 행인 상호작용, 소문 등) 추가

### 검증 체크리스트

- [ ] LOC_MARKET에서 매칭 가능한 이벤트가 10개 이상인가
- [ ] LOC_GUARD에서 매칭 가능한 이벤트가 10개 이상인가
- [ ] LOC_HARBOR에서 매칭 가능한 이벤트가 10개 이상인가
- [ ] LOC_SLUMS에서 매칭 가능한 이벤트가 10개 이상인가
- [ ] ProceduralEventService가 fallback으로 호출되는가

---

## I-18. 선택지가 매번 비슷한 유형만 제안된다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 매 턴 INVESTIGATE, PERSUADE, OBSERVE만 반복 |
| **근본 원인** | (A) 이벤트 `affordances[]`가 특정 유형 편중 (B) LLM CHOICES 다양성 강제 없음 |
| **현재 상태** | fixplan3 P9 — **✅ 구현 완료** (2026-03-19). CHOICES 다양성 규칙 추가 |
| **관련 파일** | `system-prompts.ts`, `scene-shell.service.ts` |

### 수정 방향

1. **System Prompt CHOICES 규칙 강화**: "직전 2턴에서 제안된 affordance와 다른 유형을 최소 1개 포함하세요"
2. **SceneShellService 서버 측 다양성**: 선택지 3단 우선순위 로직에서 최근 N턴 affordance 이력 참조 → 미사용 affordance에 가중치 부여
3. **이벤트 affordances[] 다양화**: events.json에서 이벤트별 affordances가 3종 이상 포함되도록 콘텐츠 보강

### 검증 체크리스트

- [ ] 연속 3턴에서 동일한 affordance 조합이 나오지 않는가
- [ ] SNEAK, FIGHT, BRIBE, TRADE 등 다양한 유형이 선택지에 등장하는가

---

## I-19. 게임이 너무 빨리 끝난다

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | 13턴만에 NATURAL 엔딩 발동 |
| **근본 원인** | Incident 1개만 해결되면 ALL_RESOLVED 조건 충족 → 즉시 NATURAL 엔딩 |
| **현재 상태** | fixplan3 P7 — ✅ 완료 (최소 15턴 가드) |
| **잔존 위험** | 동시 활성 Incident가 1개뿐이면 15턴 이후에도 콘텐츠가 빈약해서 빠르게 종료 |
| **관련 파일** | `ending-generator.service.ts`, `incident-management.service.ts` |

### 수정 방향

1. **최소 턴 가드 확인**: `MIN_TURNS_FOR_NATURAL = 15` 가드 동작 확인
2. **Incident spawn 빈도 확인**: 20%/tick × 12 tick/day → 평균 2.4 사건/일. 동시 활성 Incident가 2개 이상 유지되는지 확인
3. **ALL_RESOLVED 조건 강화 고려**: "활성 Incident 0개" 뿐 아니라 "최소 2개 사건 해결" 같은 추가 조건 고려

---

## I-20. DEFEAT 시 아무런 서사 없이 즉시 종료

| 항목 | 내용 |
|------|------|
| **심각도** | 🟡 Medium |
| **증상** | HP 0 → 즉시 RUN_ENDED, 엔딩 생성 없음, "게임 오버" 한 줄 |
| **근본 원인** | Downed 시스템 미구현. 설계상 HP 0 = DOWNED → 구조 이벤트 → 페널티 적용이지만, 현재 DEFEAT → 즉시 종료 |
| **현재 상태** | 단기: **✅ 패배 엔딩 서술 구현** (2026-03-19). DEFEAT → EndingGenerator 호출 + 패배 내러티브. 중기: Downed 시스템 — ❌ 미구현 |
| **관련 파일** | `turns.service.ts`, `core_game_architecture_v1.md` §8 |

### 수정 방향

**단기 (엔딩 서술 추가):**

1. DEFEAT 시에도 `EndingGenerator`를 호출하여 패배 엔딩 서술 생성
2. LLM에 "시야가 어두워진다" 류의 패배 내러티브 요청

**중기 (Downed 시스템 구현):**

3. HP 0 → DOWNED 상태 전환 → 구조 이벤트(동료 개입/길드 구조대/포로 탈출) 발생
4. 페널티 적용(보상 감소, 스태미나 감소, NPC 신뢰도 하락) 후 안전 지점 복귀
5. 연속 DOWNED 시 점진적 불이익 (RUN 강제 종료 가능)

---

# 6. 종합 수정 우선순위

## 6.1 의존성 그래프

```
I-01 (NPC 교체) ─────────────────────┐
I-02 (NPC 정보 망각) ────────┐       │
I-13 (structuredMemory 안정) ┤       │
                             ↓       ↓
I-03 (NPC 태도 급변) ←── NPC 일관성 기반 완성
I-05 (NPC 대사 반복) ←┘
                             │
I-11 (MEMORY 태그 추출) ─────┤
                             ↓
I-10 (6턴+ 기억 상실) ←── 단기기억 품질 향상
                             │
                             ↓
I-07 (재방문 기억) ←──── 장기기억 렌더링 개선
I-08 (장소 전환 맥락) ←┘
                             │
                             ↓
I-12 (토큰 예산 트리밍) ←─ 모든 블록 안정 후 예산 관리

I-06 (장면 점프) ←── I-17 (이벤트 풀 확충)
I-14 (파싱 실패) ←── 독립 수정 가능
I-18 (선택지 편향) ←── 독립 수정 가능
I-16 (고집 에스컬레이션) ←── 독립 수정 가능
I-19 (조기 엔딩) ←── 독립 수정 가능 (✅ 가드 적용됨)
I-20 (DEFEAT 서사 없음) ←── 독립 수정 가능
```

## 6.2 권장 작업 순서

### Wave 1 — 검증 & 즉시 수정 (코드 변경 최소)

| 순서 | 이슈 | 작업 | 예상 공수 |
|------|------|------|-----------|
| 1-1 | I-13 | structuredMemory 파이프라인 회귀 검증 (collect + finalizeVisit 3경로) | 2h |
| 1-2 | I-01 | EventMatcher NPC 연속성 가중치 동작 확인 (로그 추가 + 테스트) | 3h |
| 1-3 | I-02 | NPC Knowledge 수집 트리거 7종 경로 검증 + events.json primaryNpcId 점검 | 4h |
| 1-4 | I-04 | events.json 전수 검증 — primaryNpcId 또는 TAG_TO_NPC 매핑 누락 점검 | 2h |
| 1-5 | I-11 | MEMORY 태그 파싱 상한(4개/80자), llmExtracted 상한(20개) 코드 확인 | 1h |

### Wave 2 — 프롬프트 & 설정 강화 (서버 로직 변경 없음)

| 순서 | 이슈 | 작업 | 예상 공수 |
|------|------|------|-----------|
| 2-1 | I-03 | prompt-builder에 posture 강제 지시 + posture별 행동 가이드 삽입 | 3h |
| 2-2 | I-18 | system-prompts CHOICES 다양성 규칙 추가 | 1h |
| 2-3 | I-16 | 고집 2회째 경고 이벤트 추가 (summary.short에 복선 삽입) | 2h |
| 2-4 | I-14 | IntentParserV2 키워드 테이블 확충 (INVESTIGATE, SNEAK, HELP, STEAL, TRADE) | 3h |

### Wave 3 — 시스템 구현 (서버 코드 변경)

> ⚠️ I-12(토큰 트리밍), I-10(Mid Summary), I-07(재방문 기억)은 코드 검증 결과 **이미 구현 완료**로 확인되어 Wave 3에서 제외함 (2026-03-19 점검).

| 순서 | 이슈 | 작업 | 예상 공수 |
|------|------|------|-----------|
| 3-1 | I-08 | previousVisitContext minTokens 50 상향 + Cross-Location Facts 확인 | 2h |
| 3-2 | I-20 | DEFEAT 시 EndingGenerator 호출 + 패배 내러티브 생성 | 4h |

### Wave 4 — 콘텐츠 확충 (events.json + 절차적 이벤트)

| 순서 | 이슈 | 작업 | 예상 공수 |
|------|------|------|-----------|
| 4-1 | I-17 | LOCATION별 이벤트 풀 집계 + 최소 10개 확보 | 8h |
| 4-2 | I-06 | ProceduralEventService fallback 체인 확인 + 활성화 | 4h |
| 4-3 | I-18 | events.json affordances[] 다양화 + SceneShell 다양성 가중치 | 4h |

---

# 7. 테스트 시나리오

## 7.1 NPC 일관성 시나리오

```
시나리오 A: NPC 연속 대화
1. LOC_MARKET 진입
2. "상인에게 말을 건다" (TALK) → NPC_A 등장
3. "그에게 밀수에 대해 물어본다" (INVESTIGATE) → 같은 NPC_A 유지되는가?
4. "더 자세히 알려달라고 설득한다" (PERSUADE) → 같은 NPC_A 유지되는가?
5. 검증: 3턴 연속 동일 NPC 이벤트 선택

시나리오 B: NPC 정보 기억
1. LOC_GUARD에서 경비대장에게 밀수 증거 제시 (PERSUADE + SUCCESS)
2. go_hub → LOC_MARKET → go_hub → LOC_GUARD 재방문
3. 경비대장과 대화 시 밀수 건을 이미 아는 것처럼 반응하는가?
4. 검증: npcKnowledge에 "밀수 증거 제시" 엔트리 존재, 프롬프트에 표시

시나리오 C: NPC 태도 일관성
1. CAUTIOUS 상태 NPC와 대화
2. TALK → PARTIAL 판정
3. 서술에서 NPC가 자발적으로 핵심 정보를 제공하지 않는가?
4. 검증: posture 강제 지시가 프롬프트에 포함, LLM 서술이 CAUTIOUS와 일치
```

## 7.2 장면 연속성 시나리오

```
시나리오 D: 장면 유지
1. LOC_HARBOR 진입 → 창고 앞 묘사
2. "창고 문을 조사한다" (INVESTIGATE) → 창고 앞 장면 유지되는가?
3. "안쪽을 살펴본다" (OBSERVE) → 같은 공간 맥락 유지되는가?
4. 검증: 2턴 이상에서 sceneFrame 완전 억제, [현재 장면 상태] 일관

시나리오 E: 재방문 기억
1. LOC_MARKET에서 5턴 탐험 → go_hub
2. LOC_GUARD에서 3턴 → go_hub
3. LOC_MARKET 재방문
4. 첫 서술에 이전 방문 흔적이 반영되는가?
5. 검증: [이 장소의 이전 방문] 블록 존재
```

## 7.3 기억 스트레스 시나리오

```
시나리오 F: 장기 체류
1. LOC_MARKET에서 8턴 연속 체류
2. 1~2턴째 NPC가 알려준 정보를 8턴째에 참조할 수 있는가?
3. 검증: Mid Summary에 핵심 정보 포함, [MEMORY:NPC_DIALOGUE] 추출 확인

시나리오 G: 게임 후반 토큰
1. 25턴 이상 진행 (4개 LOCATION 순회 + 전투 3회 이상)
2. 프롬프트 토큰이 2500 초과하는 시점 확인
3. 어떤 블록이 먼저 잘리는지 확인
4. 검증: THEME 절대 보존, SCENE_CONTEXT ≥ 80 토큰
```

---

# 8. 부록: 이전 fixplan과의 관계

| fixplan3 이슈 | 본 문서 매핑 | 상태 |
|---------------|-------------|------|
| P1 (structuredMemory) | I-13 | ✅ 완료, 회귀 감시 |
| P2 (NPC 이름 공개) | I-04 | ✅ 완료, 콘텐츠 검증 필요 |
| P3 (정보 반복) | I-02, I-05 | ✅ P1 해결로 개선, 추가 강화 필요 |
| P4 (MOVE_LOCATION) | I-15 | ✅ 완료 |
| P5 (이벤트 반복) | I-17 | ✅ 부분 완료, 콘텐츠 확충 필요 |
| P6 (NPC 태도 급변) | I-03 | ✅ 구현 완료 (2026-03-19) |
| P7 (조기 엔딩) | I-19 | ✅ 완료 |
| P8 (아이템 추적) | I-13 → 파생 | ✅ P1 해결로 개선 |
| P9 (선택지 편향) | I-18 | ✅ 구현 완료 (2026-03-19) |
| P10 (조사 문법) | — | ✅ 완료 |
| P11 (turnNo 갭) | — | ⚠️ 미구현 (의도된 동작) |

| Coherence Phase | 본 문서 매핑 | 상태 |
|-----------------|-------------|------|
| Phase 1 (EventMatcher NPC) | I-01 | ✅ 구현 완료 (2026-03-19 검증) |
| Phase 2 (NPC Knowledge) | I-02 | ✅ 구현 완료 (2026-03-19 검증) |
| Phase 3 (Mid Summary) | I-10 | ✅ 구현 완료 (2026-03-19 검증) — 2-pass + LLM + fallback |
| Phase 4 (재방문 기억) | I-07 | ✅ 구현 완료 (2026-03-19 검증) — locationId 필터링 + NPC knowledge |
| Phase 5 (토큰 트리밍) | I-12 | ✅ 구현 완료 (2026-03-19 검증) — BlockPriority 20단계 + trimToTotalBudget |

---

> **정본 파일**: 본 문서
> **갱신 정책**: Wave별 작업 완료 시 해당 이슈의 "현재 상태"와 "검증 체크리스트"를 갱신한다.