# 26 --- 서술 파이프라인 v2: 3-Stage LLM Pipeline

> 서술 품질 개선을 위한 LLM 파이프라인 재설계.
> 단일 LLM 호출에서 역할 분리된 3단계 파이프라인으로 전환하여
> 서술 다양성, NPC 대사 정확도, 몰입도를 동시에 향상시킨다.
>
> 작성: 2026-04-08

---

## 1. 현재 상태와 문제점

### 1.1 현재 파이프라인 (v1)

```
서버 판정 → ContextBuilder → PromptBuilder → Gemma4 1회 호출 → 후처리
                                                    ↓
                                          묘사 + NPC 대사 + @마커 + 선택지
                                          (모든 것을 한 번에 생성)
```

- **모델**: Gemma 4 26B (OpenRouter, 메인) + GPT-4.1-nano (후처리/판단)
- **프롬프트**: ~10,000 토큰 (시스템 + 메모리 + 직전 턴 + 이번 턴 정보)
- **출력**: ~450자 산문 (묘사 + 대사 + 선택지 혼합)

### 1.2 달성한 성과

| 항목 | 결과 |
|------|------|
| @마커 정확도 | 30% → 100% (하이브리드 서버 regex + nano + 서브 LLM 2차 검증, see `30_marker_accuracy_improvement.md`) |
| 잔여 태그 노출 | 0건 |
| NPC 실명 누출 | 0건 (정상 사용 제외) |
| 힌트 반복 | 0회 (pendingQuestHint 1회 전달) |
| 문체 위반 | 0건 |

### 1.3 남은 문제 (20턴 플레이테스트 기반)

| 문제 | 심각도 | 원인 |
|------|--------|------|
| "당신은" 시작 78% | 높음 | Gemma4가 프롬프트 규칙 무시 |
| 같은 NPC 8턴 연속 등장 | 높음 | 이벤트 시스템 + LLM 관성 |
| NPC 등장 패턴 동일 ("그림자에서 나타남") | 중간 | LLM이 같은 컨텍스트 → 같은 출력 |
| NPC 제스처 반복 ("안경 올리기" 5회) | 중간 | LLM에 이전 사용 표현 정보 없음 |
| "수비대 습관" 과잉 반복 (5회) | 낮음 | 프리셋 특성이 매 턴 강조 |
| 서술 시작어 단조로움 | 중간 | 감각/환경 시작 지시를 LLM이 무시 |

### 1.4 근본 원인

**Gemma4에 너무 많은 규칙을 동시에 요구**:
- 좋은 서술을 쓰라
- @마커를 붙여라
- 발화자를 명시하라
- "당신은"으로 시작하지 마라
- 이전 표현을 반복하지 마라
- 선택지를 생성하라

→ 규칙이 많을수록 개별 준수율 하락. 특히 26B 모델의 instruction following 한계.

---

## 2. 목표

1. **서술 다양성**: 첫 문장, NPC 등장 방식, 제스처가 매 턴 다르게
2. **대사 정확도 유지**: @마커 100% 유지
3. **Gemma4 규칙 부담 감소**: 마커/포맷 규칙 제거 → 서술 품질에 집중
4. **추가 비용 최소화**: nano 호출 2회 추가 (< $0.0001/턴)
5. **지연 시간 최소화**: 추가 < 1초 (Gemma4 8~30초 대비 무시 가능)

---

## 3. 설계: 3-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    3-Stage LLM Pipeline                      │
│                                                              │
│  [Stage 1] NanoDirector (전처리)                              │
│  nano · ~300ms · ~100토큰                                    │
│  입력: 직전 2턴 요약 + 이번 턴 이벤트/판정                      │
│  출력: 연출 지시서 JSON                                       │
│    {opening, npcEntrance, npcGesture, avoid, mood}           │
│                          ↓                                   │
│  [Stage 2] Gemma4 MainNarrative (메인 서술)                   │
│  gemma-4-26b · ~10초 · ~450토큰                              │
│  입력: 기존 프롬프트 (마커 규칙 제거) + 연출 지시                  │
│  출력: 순수 산문 (묘사 + 대사, 마커 없음) + [CHOICES]             │
│                          ↓                                   │
│  [Stage 3] Server + NanoProcessor (후처리)                    │
│  서버 regex + nano · ~500ms · ~50토큰                         │
│  입력: Gemma4 출력 + NPC DB                                   │
│  출력: @마커 삽입 + 문체 교정 + 실명 sanitize                    │
│                          ↓                                   │
│  최종 서술 (turns.llmOutput)                                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Stage 1: NanoDirector (전처리)

**목적**: Gemma4가 매 턴 다른 서술을 생성하도록 구체적 연출 지시를 사전 생성.

**서비스**: `NanoDirectorService` (`server/src/llm/nano-director.service.ts`)

**입력** (~150토큰):
```
[직전 서술]
T-2: 잉크 냄새가 코끝을 스쳤다. 대사: "계산이 맞지 않소"
T-1: 에드릭이 안경을 밀어올리며 다가왔다. 대사: "숫자는 거짓말을 하지 않소"

[직전 opening]
"잉크 냄새가 채 가시지 않은 양피지 조각이 바닥에 흩어져 있다." (후각)

[이번 턴]
행동: 주변을 살펴본다
판정: SUCCESS
이벤트: EVT_MARKET_DSC_3
등장NPC: 날카로운 눈매의 회계사
```

**출력** (maxTokens=150, temperature=0.9):
```json
{
  "opening": "차가운 돌벽의 감촉이 손바닥에 와닿는다.",
  "npcEntrance": "에드릭은 노점 뒤편 의자에 앉아 조용히 장부를 넘기고 있다.",
  "npcGesture": "펜을 쥔 손을 탁자에 내려놓으며",
  "avoid": ["안경 밀어올리기", "서류 움켜쥐기", "계산이 맞지"],
  "mood": "의혹이 깊어지는"
}
```

**핵심 규칙**:
- `opening`: 직전 opening과 다른 감각 카테고리 사용 (시각→청각→후각→촉각→시간 순환)
- `npcEntrance`: "그림자에서 나타남", "다가옴" 금지. 이미 그 자리에 있거나 다른 방식으로 등장
- `npcGesture`: 직전 2턴에서 사용된 제스처 금지
- `avoid`: 직전 서술에서 2회 이상 반복된 표현

**호출 조건**:
- LOCATION 턴 + inputType !== 'SYSTEM' (진입 턴 제외)
- HUB, COMBAT 턴은 건너뜀

### 3.2 Stage 2: Gemma4 MainNarrative (메인 서술)

**변경점**: 프롬프트에서 @마커 관련 규칙 전부 제거.

**제거되는 프롬프트 섹션** (~200토큰 절약):
```diff
- ## NPC 대사 마커 (필수)
- NPC가 대사를 할 때 큰따옴표 직전에 @NPC_ID 마커를 붙이세요...
- 형식: @NPC_ID "대사 내용"
- 예시: @NPC_TOBREN "여기서 뭘 하시오?"
- ...

- ## 대사 발화자 명시 (필수)
- ⚠️ 모든 큰따옴표 대사 직전에 반드시 발화자를 명시하라...
```

**축소되어 남는 규칙**:
```
## NPC 대사 규칙
- 대사 앞에 반드시 발화자의 호칭이나 역할명을 명시하세요.
- 대사는 큰따옴표("")로 감싸세요.
- 마커(@NPC_ID)는 붙이지 마세요. 시스템이 자동 처리합니다.
- 대사가 문단 첫줄에서 시작하면 안 됩니다.
```

**NanoDirector 지시 삽입 위치**: user 메시지 마지막 (factsParts)
```
[연출 지시 — 반드시 따르세요]
[첫 문장] "차가운 돌벽의 감촉이 손바닥에 와닿는다."
[NPC 등장] 에드릭은 노점 뒤편 의자에 앉아 조용히 장부를 넘기고 있다.
[NPC 행동] 펜을 쥔 손을 탁자에 내려놓으며
[분위기] 의혹이 깊어지는
[반복 금지] 안경 밀어올리기, 서류 움켜쥐기, 계산이 맞지
```

**기대 출력**:
```
차가운 돌벽의 감촉이 손바닥에 와닿는다. 좁은 골목 너머로 시장의 소란이
어렴풋이 들려온다. 노점 뒤편 의자에 앉아 조용히 장부를 넘기던 회계사가
당신의 기척을 느꼈는지 고개를 돌린다. 그는 펜을 쥔 손을 탁자에 내려놓으며
당신의 얼굴을 찬찬히 훑는다.

"숫자를 다루는 사람 치고는 발소리가 제법 무겁구려."

그는 장부의 특정 페이지를 손끝으로 가리키며 미간을 좁힌다.
```

→ 마커 없음, 발화자 명시됨, 첫 문장 다양, NPC 행동 변주

### 3.3 Stage 3: Server + NanoProcessor (후처리)

**기존 하이브리드 마커 시스템 그대로 유지**:

```
3-1. 서버 regex 6단계 매칭
     DB직접 → 대명사역추적 → 일반명사 → 직업명 → 문맥호칭 → fallback
3-2. nano 개별 발화자 판단 (미매칭 대사만)
     전후 1~2문장 + "발화자가 누구?" 한 단어 답변
3-3. @NPC_ID → @[표시이름|초상화URL] 변환
3-4. 안전망 (한글/일본어 마커 제거, 할루시네이션 ID 제거)
3-5. 실명 sanitize
3-6. 문체 교정 (자네→그대, 경어체 치환 등)
3-7. 첫 문장 보정: "당신은" 시작 감지 시 NanoDirector opening으로 교체
```

### 3.4 Fallback (graceful degradation)

| Stage | 실패 시 | Fallback |
|-------|---------|----------|
| Stage 1 (NanoDirector) | nano 호출 실패 | directorHint = null → 기존 프롬프트 그대로 |
| Stage 2 (Gemma4) | LLM 호출 실패 | SceneShell fallback (기존 동작) |
| Stage 3 (Processor) | nano 판단 실패 | 서버 regex만으로 마커 삽입 |

모든 Stage가 독립적이므로 어느 하나 실패해도 게임이 중단되지 않음.

---

## 4. 비용/성능 분석

### 4.1 비용 비교

| 항목 | v1 (현재) | v2 (3-Stage) | 차이 |
|------|-----------|--------------|------|
| Gemma4 프롬프트 | ~10,000 토큰 | ~9,800 토큰 | -200 |
| Gemma4 완성 | ~450 토큰 | ~450 토큰 | 0 |
| nano (후처리) | ~80 토큰 | ~80 토큰 | 0 |
| nano (Director) | 0 | ~250 토큰 | +250 |
| **합계** | **~10,530** | **~10,580** | **+50 (0.5%)** |

### 4.2 지연 시간

| Stage | 시간 |
|-------|------|
| NanoDirector | 200~400ms |
| Gemma4 | 8,000~30,000ms |
| NanoProcessor | 300~500ms |
| **합계** | **8,500~31,000ms** |

v1 대비 추가 지연: ~500ms (사용자 체감 불가)

---

## 5. 기대 효과

### 5.1 Before/After 비교

| 지표 | v1 (현재) | v2 (목표) |
|------|-----------|-----------|
| "당신은" 시작 비율 | 78% | < 10% |
| NPC 등장 패턴 반복 | "그림자에서 나타남" 5회 | 매 턴 다른 방식 |
| NPC 제스처 반복 | "안경 올리기" 4~5회 | 0~1회 |
| "수비대 습관" 반복 | 5회 | 1~2회 |
| @마커 정확도 | 100% | 100% (유지) |
| 잔여 태그 | 0건 | 0건 (유지) |

### 5.2 몰입도 개선 포인트

1. **첫 문장 다양성**: nano가 감각 카테고리를 순환 → 매 턴 다른 도입부
2. **NPC 등장 변주**: "이미 그 자리에 있음", "지나가다 멈춤", "뒤에서 소리" 등
3. **제스처 회전**: 직전 사용 제스처 금지 → 새로운 행동 패턴 강제
4. **반복 표현 차단**: avoid 리스트로 클리셰 사전 방지
5. **Gemma4 품질 향상**: 규칙 부담 감소 → 서술 자체의 문학적 품질에 집중

---

## 6. 구현 파일 목록

| 파일 | 변경 | 내용 |
|------|------|------|
| `src/llm/nano-director.service.ts` | 수정 | opening 반복 방지, 감각 카테고리 순환 |
| `src/llm/llm-worker.service.ts` | 수정 | 3-Stage 파이프라인 오케스트레이션 |
| `src/llm/prompts/system-prompts.ts` | 수정 | @마커 규칙 제거, NPC 대사 규칙 간소화 |
| `src/llm/prompts/prompt-builder.service.ts` | 수정 | directorHint 삽입, 마커 관련 지시 제거 |
| `src/llm/llm.module.ts` | 수정 | NanoDirectorService 등록 (완료) |

---

## 7. 구현 단계

### Phase A: 핵심 전환
1. Gemma4 프롬프트에서 @마커 규칙 제거 + 간소화
2. NanoDirector opening 반복 방지 (직전 opening 입력 + 감각 순환)
3. Stage 3에서 첫 문장 "당신은" → opening 교체 로직 추가
4. 10턴 테스트 → 마커 정확도 유지 확인

### Phase B: 미세 조정
5. NanoDirector 프롬프트 튜닝 (temperature, 예시 추가)
6. 20턴 테스트 → 몰입도 지표 측정
7. NPC 등장 패턴 다양성 검증

### Phase C: 확장 (향후)
8. NPC별 제스처 풀 콘텐츠 데이터화 (content/npc/*.json)
9. 장소별 감각 키워드 풀 (content/locations/*.json)
10. 파티 모드 NanoDirector 대응

---

## 8. 위험 요소와 대응

| 위험 | 확률 | 영향 | 대응 |
|------|------|------|------|
| 마커 정확도 하락 | 낮음 | 높음 | Stage 3 하이브리드가 독립적으로 작동, Gemma4 의존 없음 |
| nano opening이 부자연스러움 | 중간 | 중간 | Gemma4가 opening을 자연스럽게 확장/변형 가능하도록 "참고" 수준으로 지시 |
| Gemma4가 발화자 명시 안 함 | 중간 | 중간 | Stage 3의 nano 개별 판단이 백업, fallback NPC 귀속 |
| nano 비용 증가 | 낮음 | 낮음 | 턴당 +$0.00003 (월 1000턴 = $0.03) |

---

## 부록 A. AI 구현 가이드라인 (ai_implementation_guidelines_for_narrative_patch 통합)

Narrative 패치 구현 시 적용되는 원칙.

### 기본 원칙
1. 서버가 상태의 단일 진실 소스 (SoT)
2. LLM은 서술만 담당
3. 이벤트 결정은 서버 로직에서 수행

### 구현 위치
- **Intent Parser**: ParsedIntentV3 생성
- **Event System**: EventMatcher + Event Director 정책
- **Narrative Generator**: 서버 결과 기반 장면 서술

### 금지 사항
- LLM이 게임 상태 직접 변경
- Procedural Event가 메인 플롯 변경
- Incident 시스템 우회

### 권장 구현 순서
1. Narrative Context Patch 적용
2. Event Director 정책 추가
3. Event Library 정비
4. Procedural Event Extension 적용

---

## 부록 B. Narrative v2 / Event 구현 요약 (기존 18/19/20 통합)

Narrative Engine v1의 맥락 유지·토큰 효율·이벤트 선택·동적 이벤트 생성 축을 구현한 세 문서(18/19/20)를 압축 통합한다. 구현 세부는 `engine/hub/narrative/`, `engine/hub/event/`, `engine/hub/procedural/` 참조.

### 18 — Narrative Runtime Patch v1.1

**목적**: Narrative Engine v1의 맥락 유지 성능을 강화하고 LLM 토큰 효율을 개선한다.

**Context Layers**: Scene Context / Player Intent Memory / Active Clues / Recent Story / Structured Memory.

**Token Budget (≈2500 tokens)**

| Layer | Tokens |
|-------|--------|
| System | 300 |
| Scene Context | 150 |
| Intent Memory | 200 |
| Active Clues | 150 |
| Recent Story | 700 |
| Previous Visit | 150 |
| Structured Memory | 450 |
| User Input | 200 |
| Buffer | 250 |

**Recent Story 정책**: 최대 4턴 유지, 이후 Mid Summary 생성. Mid Summary 요약 대상은 resolved incidents / new clues / npc state change / location state change.

**Previous Visit Context (Fixplanv1 PR3)**
- `VisitExitSummary`: locationId, locationName, turnCount, keyActions(max 3), keyDialogues(max 3), unresolvedLeads(max 2)
- `StructuredMemory.lastExitSummary`에 저장, LlmContext에 `previousVisitContext: string | null` 추가
- `[이야기 요약]` 뒤, `[NPC 관계]` 앞에 `[직전 장소 정보]` 블록 삽입
- 토큰 예산: PREVIOUS_VISIT 150 (priority=57, minTokens=0)

**Cross-Location Facts (Fixplanv1 PR3)**
- `renderLlmFacts()`: 타 장소 사실도 importance≥0.7이면 포함 (max 3). 타 장소 사실은 `[장소명]` 접두사 부여.

**Intent Memory**: 플레이어 행동 패턴 기록 (예: aggressive interrogation, stealth exploration, evidence focused investigation).

### 19 — Event Orchestration System v1.2

**목적**: 현재 LOCATION과 상태에 맞는 이벤트 선택. SituationGenerator가 우선, 실패 시 EventMatcher fallback.

**SituationGenerator 3계층 (Living World v2)**

| Layer | 이름 | 입력 | 설명 |
|-------|------|------|------|
| Layer 1 | Landmark | LocationDynamicState | 장소 고유 상태(security, crime, unrest) 기반 랜드마크 이벤트 |
| Layer 2 | Incident-Driven | ActiveIncidents + WorldFact | 활성 사건과 누적 사실에서 파생되는 상황 |
| Layer 3 | World-State | NpcAgenda + NpcSchedule + WorldFact | NPC 자율 행동과 월드 사실 조합으로 창발적 상황 생성 |

**실행 흐름**: Layer 1→2→3 순차 시도 → 유효 상황 생성 시 SituationEvent 반환, 모두 실패 시 null → EventMatcher fallback. SituationGenerator 이벤트도 반복 페널티 추적 포함. Procedural Plot Protection 불변식 유지(arcRouteTag/commitmentDelta 생성 금지).

**Event Director 선택 알고리즘**: Stage Filter → Condition Filter → Cooldown Filter → Priority Sort → Weighted Random. Priority weight: critical=10, high=6, medium=3, low=1.

**Event Library 현황 (2026-04-01)**: 총 123개 이벤트, 7개 LOCATION, discoverableFact 43개 이벤트.

| LOCATION | 이벤트 | Fact |
|----------|--------|------|
| LOC_MARKET | 22 | 13 |
| LOC_GUARD | 22 | 11 |
| LOC_HARBOR | 22 | 7 |
| LOC_SLUMS | 22 | 6 |
| LOC_TAVERN | 11 | 3 |
| LOC_DOCKS_WAREHOUSE | 10 | 2 |
| LOC_NOBLE | 9 | 1 |

**이벤트 매칭 밸런싱 (P0~P5)**
- shouldMatchEvent 게이트: 첫 턴 + 사건 압력 + 강한 라우팅 + questFactTrigger(미발견 fact 이벤트 존재 시 매 턴)
- questFactTrigger 시 SitGen 바이패스 (fact 이벤트 매칭 보장)
- 미발견 fact weight 부스트: EventMatcher +35 (`quest-balance.config.ts`)
- PARTIAL 발견 확률: 50%
- SitGen template fact 우선: SitGen 실행 시에도 미발견 discoverableFact 이벤트를 template으로 우선 선택

### 20 — Procedural Event Extension v1.1

**목적**: 고정 이벤트가 부족한 구간에서 동적 이벤트 생성.

**Procedural Event 구조**: Trigger + Subject + Action + Outcome. 예: `npc_nervous_reaction + dock_guard + denies + suspicion_up`.

**Seed Types**: Trigger / Subject / Action / Outcome.

**Context Filter 입력 요소**: location, stage, time, npc, active clues, player intent.

**Anti-Repetition Rules**

| rule | value |
|------|-------|
| trigger cooldown | 3 turns |
| subject-action cooldown | 5 turns |
| same outcome repeat | max 2 |
| same npc focus | max 3 |

**Fallback 순서**: atmosphere event → low priority fixed event → narrative reaction only.
