# 28 --- NanoEventDirector: nano LLM 기반 이벤트 엔진 재설계

> 정적 이벤트 풀 매칭에서 nano LLM 기반 동적 이벤트 생성으로 전환.
> 선택지→이벤트 맥락 단절 해소, NPC 연속성 보장, fact 발견의 자연스러운 통합.
>
> 작성: 2026-04-10

---

## 1. 현재 문제

### 1.1 맥락 단절
- 유저가 마이렐과 대화 중 선택지 선택 → 갑자기 에드릭이 등장
- 원인: 선택지 2~3번에 sourceEventId 없음 → 새 이벤트 매칭 → 다른 NPC 이벤트 선택
- 이벤트 엔진이 "직전 대화 맥락"을 충분히 고려하지 않음

### 1.2 이벤트 풀 한계
- ~80개 고정 이벤트 → 반복 체감
- 이벤트별 primaryNpcId 고정 → NPC-이벤트 조합 제한
- 장소별 이벤트가 소진되면 FREE 턴(이벤트 없는 자유 서술)으로 전환

### 1.3 선택지-이벤트 이음새 부족
- 유저는 선택지가 "같은 상황의 다른 접근"이라고 기대
- 실제로는 선택지마다 완전히 다른 이벤트로 점프 가능
- 특히 LLM 생성 선택지는 sourceEventId/affordance 메타데이터 불안정

---

## 2. 재설계 목표

1. **선택지 맥락 연속**: 어떤 선택지를 골라도 직전 대화/NPC가 자연스럽게 이어짐
2. **NPC 연속성**: 대화 중인 NPC가 갑자기 바뀌지 않음
3. **fact 발견 자연스러움**: 퀘스트 단서가 대화/탐색 흐름 속에서 유기적으로 등장
4. **무한 다양성**: 고정 이벤트 풀 제한 없이 매 턴 새로운 상황
5. **서버 판정 유지**: 수치(1d6+stat), RNG, 상태 변경은 서버가 결정

---

## 3. 아키텍처: NanoEventDirector

### 3.1 새 파이프라인

```
┌─────────────────────────────────────────────────────────────┐
│                  NanoEventDirector Pipeline                   │
│                                                              │
│  플레이어 행동 → IntentParser → ResolveService(1d6 판정)       │
│                                    ↓                         │
│  [Stage 0] 서버 사전 준비                                     │
│  - 현재 장소 NPC 목록 (스케줄 기반)                             │
│  - 발견 가능 fact 목록 + 확률                                  │
│  - 직전 2턴 NPC/이벤트 맥락                                    │
│  - 판정 결과 (SUCCESS/PARTIAL/FAIL)                           │
│                    ↓                                         │
│  [Stage 1] NanoEventDirector (nano LLM, ~300ms)              │
│  입력: 맥락 데이터 (~200tok)                                  │
│  출력: 이벤트 컨셉 JSON (~200tok)                             │
│    {concept, npc, tone, fact, factRevealed,                  │
│     factDelivery, opening, npcGesture, choices[3]}           │
│                    ↓                                         │
│  [Stage 2] 서버 검증 + 보정                                   │
│  - NPC가 현재 장소에 있는지 확인                                │
│  - fact 발견 확률 서버에서 최종 결정 (RNG)                      │
│  - 선택지 유효성 검증                                         │
│                    ↓                                         │
│  [Stage 3] Flash Lite (메인 서술, ~5초)                       │
│  입력: 기존 프롬프트 + NanoEventDirector 컨셉                  │
│  출력: 서술 텍스트                                            │
│                    ↓                                         │
│  [Stage 4] 서버 후처리 (기존)                                 │
│  @마커 삽입 + 문체 교정 + 실명 sanitize                       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 기존 vs 신규 비교

| 항목 | 기존 (EventDirector) | 신규 (NanoEventDirector) |
|------|---------------------|------------------------|
| 이벤트 선택 | JSON 풀 가중치 매칭 | nano가 맥락 기반 생성 |
| NPC 선택 | 이벤트 payload 고정 | nano가 직전 NPC 유지/전환 판단 |
| fact 발견 | 이벤트-fact 고정 매핑 | nano가 확률 기반 추천 + 서버 RNG 확정 |
| 선택지 | 이벤트 고유 + LLM 생성 | nano가 맥락 기반 3개 생성 |
| scene frame | 이벤트 payload 고정 | nano가 매 턴 새로 생성 |
| 다양성 | ~80개 이벤트 | 무한 (맥락 기반 생성) |
| NanoDirector | 별도 서비스 (연출 지시) | 통합 (이벤트+연출 한 번에) |

---

## 4. NanoEventDirector 상세 설계

### 4.1 입력 (서버 → nano, ~200토큰)

```
[맥락]
장소: 경비대 지구
시간: 밤 (NIGHT)
Heat: 20/100, Safety: ALERT

[직전 상황]
T5: 마이렐 단 경(CALCULATING)과 대화 중. 야간 순찰 기록에 대해 물음.
T6: 마이렐이 "야간 순찰 기록에 빈 시간대가 있다"고 암시.

[플레이어]
선택: "경비대 지구의 최근 분위기에 대해 묻는다"
판정: SUCCESS
행동 유형: TALK

[이 장소 NPC]
- 마이렐 단 경 (trust:-10, CALCULATING, 직전 대화 NPC)
- 브렌 대위 (trust:-15, HOSTILE)
- 펠릭스 (trust:-10, HOSTILE)

[발견 가능 fact]
- FACT_INSIDE_JOB: 내부자 소행 (확률 40%, SUCCESS+TALK)
- FACT_OFFICIAL_INQUIRY: 공식 조사 (확률 20%, PERSUADE+SUCCESS)

[퀘스트]
현재: S2_PROVE_TAMPER
다음 전환: FACT_INSIDE_JOB 필요
```

### 4.2 출력 (nano → 서버, ~200토큰)

```json
{
  "npc": "마이렐 단 경",
  "npcId": "NPC_MAIREL",
  "concept": "마이렐이 최근 분위기가 좋지 않다며, 야간 순찰 기록의 빈칸이 상부의 지시인지 누군가의 은폐인지 고민하는 모습을 보인다",
  "tone": "계산적이지만 약간의 불안",
  "opening": "차가운 밤바람이 깃발을 흔든다",
  "npcGesture": "두 손을 뒤로 깍지 끼며 광장을 응시한다",
  "fact": "FACT_INSIDE_JOB",
  "factRevealed": true,
  "factDelivery": "indirect",
  "avoid": ["팔짱을 끼다", "그림자에서 나타나다"],
  "choices": [
    {"label": "야간 기록의 빈칸에 대해 추궁한다", "affordance": "PERSUADE", "npcId": "NPC_MAIREL"},
    {"label": "다른 순찰병에게 확인을 시도한다", "affordance": "INVESTIGATE", "npcId": null},
    {"label": "마이렐의 반응을 조용히 관찰한다", "affordance": "OBSERVE", "npcId": "NPC_MAIREL"}
  ]
}
```

### 4.3 nano 시스템 프롬프트

```
당신은 텍스트 RPG의 이벤트 감독이다.
직전 맥락과 플레이어 선택을 보고, 이번 턴의 이벤트 컨셉을 JSON으로 생성하라.

규칙:
1. npc: 직전 대화 NPC를 우선 유지. 전환이 필요하면 자연스러운 이유를 concept에 포함.
2. concept: 30~60자. 구체적 상황 묘사. 판정 결과(SUCCESS/PARTIAL/FAIL)에 맞는 전개.
3. fact: 발견 가능 fact 목록 중 맥락에 맞는 것을 선택. 없으면 null.
   factRevealed: true/false. factDelivery: direct/indirect/observe.
4. choices: 정확히 3개. 최소 2종 affordance. 현재 NPC와 이어지는 선택지 포함.
   각 선택지에 npcId 포함 (같은 NPC면 대화 연속, null이면 전환).
5. opening: 감각 묘사 15~30자. "당신은" 금지. 직전과 다른 감각.
6. avoid: 직전 2턴에서 사용된 표현 2~3개.
```

### 4.4 서버 검증 (Stage 2)

nano 출력을 서버가 검증/보정:

```typescript
interface NanoEventResult {
  npc: string;
  npcId: string;
  concept: string;
  tone: string;
  opening: string;
  npcGesture: string;
  fact: string | null;
  factRevealed: boolean;
  factDelivery: 'direct' | 'indirect' | 'observe';
  avoid: string[];
  choices: Array<{label: string; affordance: string; npcId: string | null}>;
}

// 서버 검증
function validateNanoEvent(result: NanoEventResult, context: EventContext): NanoEventResult {
  // 1. NPC가 현재 장소에 있는지 (스케줄 확인)
  if (!presentNpcs.includes(result.npcId)) {
    result.npcId = context.lastPrimaryNpcId ?? presentNpcs[0];
  }
  
  // 2. fact 발견 확률을 서버 RNG로 최종 결정
  if (result.factRevealed && result.fact) {
    const factDef = getFactDef(result.fact);
    const roll = rng.next(); // 0~1
    const threshold = resolveOutcome === 'SUCCESS' ? factDef.successRate 
                    : resolveOutcome === 'PARTIAL' ? factDef.partialRate : 0;
    result.factRevealed = roll < threshold;
  }
  
  // 3. 선택지 affordance 유효성
  for (const choice of result.choices) {
    if (!VALID_AFFORDANCES.includes(choice.affordance)) {
      choice.affordance = 'TALK';
    }
  }
  
  // 4. choices에 sourceNpcId 부여 (대화 연속용)
  for (const choice of result.choices) {
    choice.sourceNpcId = choice.npcId ?? result.npcId;
  }
  
  return result;
}
```

### 4.5 Flash Lite 프롬프트 주입

NanoEventDirector 결과가 기존 NanoDirector + 이벤트 정보를 대체:

```
[이벤트 컨셉 — 이 방향으로 서술하세요]
마이렐이 최근 분위기가 좋지 않다며, 야간 순찰 기록의 빈칸이 상부의 지시인지
누군가의 은폐인지 고민하는 모습을 보인다.

[NPC] 마이렐 단 경 (CALCULATING, trust:-10)
[톤] 계산적이지만 약간의 불안
[첫 문장] "차가운 밤바람이 깃발을 흔든다."
[NPC 행동] 두 손을 뒤로 깍지 끼며 광장을 응시한다
[반복 금지] 팔짱을 끼다, 그림자에서 나타나다

[정보 전달]
이번 턴에 NPC가 간접적으로 다음 사실을 암시하세요:
"내부자의 소행이라는 증거가 점점 쌓이고 있다"
```

---

## 5. Fact 발견 통합

### 5.1 현재 시스템
```
이벤트 콘텐츠에 discoverableFact 고정 매핑
→ 해당 이벤트 매칭 시 → SUCCESS/PARTIAL 판정 → fact 발견
```

### 5.2 새 시스템
```
서버가 현재 장소의 발견 가능 fact + 확률을 계산
→ nano에게 "이 fact들 중 맥락에 맞는 것을 골라라" 전달
→ nano가 선택 (또는 null)
→ 서버 RNG로 최종 확정 (확률 기반)
→ 확정된 fact를 Flash Lite 프롬프트에 주입
```

### 5.3 fact 확률 계산

```typescript
function getAvailableFacts(locationId: string, questState: string, discoveredFacts: string[]): FactCandidate[] {
  const allFacts = questConfig.getFactsForLocation(locationId);
  return allFacts
    .filter(f => !discoveredFacts.includes(f.factId))
    .map(f => ({
      factId: f.factId,
      successRate: f.baseRate * (questState needs this fact ? 1.5 : 1.0),
      partialRate: f.baseRate * 0.5,
      description: f.hintText,
    }));
}
```

---

## 6. 선택지 연속성 보장

### 6.1 현재 문제
선택지에 sourceEventId가 없으면 다음 턴에서 완전히 다른 이벤트 매칭.

### 6.2 새 설계: sourceNpcId 기반

모든 선택지에 `sourceNpcId`를 부여:
```json
{
  "id": "choice_1",
  "label": "야간 기록의 빈칸에 대해 추궁한다",
  "action": {
    "type": "CHOICE",
    "payload": {
      "affordance": "PERSUADE",
      "sourceNpcId": "NPC_MAIREL"
    }
  }
}
```

다음 턴에서:
1. `sourceNpcId`가 있으면 → NanoEventDirector에 "이 NPC와 이어가라" 지시
2. 없으면 (null) → nano가 자유롭게 NPC 선택 (장소 전환 기회)

---

## 7. Fallback (graceful degradation)

| 단계 | 실패 시 |
|------|---------|
| nano 호출 실패 | 기존 EventDirector로 fallback (정적 이벤트 매칭) |
| nano JSON 파싱 실패 | 서버 기본값 사용 (직전 NPC + 기본 컨셉) |
| NPC 검증 실패 | 현재 장소 첫 번째 NPC로 교체 |
| fact 검증 실패 | fact 없이 진행 (null) |

기존 이벤트 풀(~80개 JSON)은 삭제하지 않고 fallback으로 유지.

---

## 8. 비용/성능 분석

### 8.1 비용

| 항목 | 기존 | 신규 | 차이 |
|------|------|------|------|
| NanoDirector | ~100tok | 통합 (삭제) | -100tok |
| NanoEventDirector | 0 | ~400tok | +400tok |
| Flash Lite 프롬프트 | ~11,000tok | ~9,000tok (-이벤트 정보 축소) | -2,000tok |
| **합계** | ~11,100tok | ~9,400tok | **-1,700tok (15% 절감)** |

턴당 비용: 기존 2.0원 → 신규 ~1.7원 (15% 절감)
nano 추가 비용이 프롬프트 축소로 상쇄됨.

### 8.2 지연

| 단계 | 시간 |
|------|------|
| NanoEventDirector | ~400ms |
| Flash Lite | ~5초 (프롬프트 축소로 약간 개선) |
| 서버 후처리 | ~500ms |
| **합계** | **~6초** (기존과 동일) |

---

## 9. 구현 계획

### Phase A: 핵심 전환 (1~2일)
1. NanoEventDirectorService 신규 생성
2. 기존 NanoDirectorService 기능 통합 (opening, avoid, mood)
3. llm-worker에서 NanoEventDirector 호출 → Flash Lite 프롬프트 주입
4. 기존 EventDirector를 fallback으로 유지

### Phase B: 서버 검증 (1일)
5. NPC 장소 검증 (스케줄 기반)
6. fact 확률 계산 + RNG 확정
7. 선택지 sourceNpcId 부여

### Phase C: 선택지 연속 (1일)
8. ChoiceItem에 sourceNpcId 추가
9. 다음 턴에서 sourceNpcId → NanoEventDirector에 전달
10. 클라이언트 영향 없음 (payload에 추가될 뿐)

### Phase D: 검증 + 미세 조정 (1~2일)
11. 10턴 플레이테스트 → NPC 연속성 확인
12. 20턴 스피드런 → fact 발견 속도 확인
13. nano 프롬프트 튜닝

---

## 10. 위험 요소

| 위험 | 확률 | 대응 |
|------|------|------|
| nano가 맥락 무시한 이벤트 생성 | 중간 | 서버 검증(Stage 2)에서 보정 |
| fact 발견이 너무 빠르거나 느림 | 중간 | 서버 RNG 확률 조정 |
| 선택지 품질 저하 | 낮음 | nano 프롬프트 예시 추가 |
| nano 호출 실패율 | 낮음 | 기존 EventDirector fallback |
| 기존 이벤트 콘텐츠 낭비 | - | fallback + 참고 데이터로 활용 |

---

## 11. 기존 시스템과의 공존

기존 이벤트 엔진을 삭제하지 않고, 환경변수로 전환:

```
EVENT_ENGINE=nano     # NanoEventDirector 사용 (기본)
EVENT_ENGINE=legacy   # 기존 EventDirector 사용
```

A/B 테스트, 점진적 전환, 즉시 롤백 가능.

---

## 12. 구현 현황 (2026-04-10)

### 12.1 완료

| 항목 | 상태 | 비고 |
|------|------|------|
| NanoEventDirectorService | ✅ | nano-event-director.service.ts 신규 |
| turns.service 통합 | ✅ | resolve 후 NanoEventContext 조립 → nano 호출 |
| LLM 프롬프트 주입 | ✅ | [이벤트 컨셉] 블록 → Flash Lite |
| 선택지 sourceNpcId | ✅ | NPC 연속성 보장 |
| fact RNG 확정 | ✅ | nano 추천 → 서버 RNG → discoveredQuestFacts |
| NPC 선택 개선 | ✅ | 행동별 전환 규칙 + 5턴 강제 전환 + targetNpc/wantNewNpc |
| activeConditions 전달 | ✅ | 장소 조건 → nano/LLM에 반영 |
| 모델 확정 | ✅ | gpt-4.1-nano (1.69s, 100% JSON 준수) |

### 12.2 연쇄 반응 (Layer 2)

치안/불안 임계값 → 조건 자동 발동:
- security < 30 → INCREASED_PATROLS (SNEAK/STEAL -2 판정 패널티)
- security < 15 → LOCKDOWN (봉쇄, -2 패널티)
- unrest > 60 → UNREST_RUMORS (INVESTIGATE/PERSUADE +1 보너스)
- unrest > 80 → RIOT (FIGHT/STEAL +1, TRADE -2)
- 회복 시 자동 해제 (security≥35 순찰 해제 등)
- 시그널 피드에 세계 변화 알림 생성

### 12.3 NPC 능동 반응 (Layer 3)

WITNESSED NPC trust 기반 반응:
- trust ≥ 20: 경고 ("조심하시오")
- trust -10~20: 회피 (거리를 둔다)
- trust -30~-10: 밀고 → Heat +5
- trust < -30: 경비대 호출 → Heat +8
- LLM [NPC 반응] 블록으로 서술에 자연스럽게 포함

### 12.4 IntentParser 연동

- FIGHT/STEAL/THREATEN/BRIBE 키워드 → LLM보다 KW 우선 (KW_OVERRIDE)
- targetNpcId: KW 매칭 성공 시 LLM보다 우선 (플레이어 명시적 NPC 지목)

### 12.5 10턴 테스트 결과

| 항목 | 수정 전 | 수정 후 |
|------|---------|---------|
| NPC 고착 | 7턴 연속 같은 NPC | 최대 2턴 연속 |
| NPC 다양성 | 1종 | 3종 |
| NPC 전환 | 1회 | 5회 |
| Fact 발견 | 2개 | 2개 |
| Opening 고유 | 10/10 | 10/10 |
| "당신은" | 0건 | 0건 |
| 조건 발동 (Layer 2) | 미구현 | LOCKDOWN+UNREST 발동 확인 |
