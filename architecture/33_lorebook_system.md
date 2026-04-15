# 33 — 로어북 시스템: 키워드 트리거 기반 세계관 지식 동적 주입

> 기존 블록 단위 전체 주입 방식을 키워드 트리거 기반 선택적 주입으로 전환.
> 플레이어 행동에서 키워드를 감지하여 관련 세계관 지식만 LLM 프롬프트에 주입.
>
> 작성: 2026-04-15

---

## 1. 현재 시스템 문제점

| 문제 | 원인 | 영향 |
|------|------|------|
| 무관 정보 주입 | NPC 등장 시 knownFacts 전부 주입 | 토큰 낭비 (30%+) |
| 단서 강제 노출 | 서버 이벤트에 의존한 정보 공개 | 플레이어 자유 탐색 불가 |
| 토큰 예산 포화 | 2,500토큰에 블록 전부 우겨넣기 | 중요 정보 트리밍 발생 |
| NPC 정보 과다 | 첫 만남에 personality 전체 주입 | LLM 지시 준수율 저하 |
| 장소 비밀 비활성 | 장소 secrets가 이벤트로만 발견 | 자유 탐색 보상 없음 |

---

## 2. 로어북 아키텍처 개요

```
플레이어 입력 (rawInput + actionType)
       ↓
[Phase 1] 키워드 추출
  rawInput에서 한글 명사 추출 + actionType + eventId
       ↓
[Phase 2] 로어북 매칭
  knownFacts.keywords / location.secrets.keywords / incident.stages.keywords
  → 매칭된 항목 선별 (importance + trust 가중)
       ↓
[Phase 3] 토큰 예산 내 우선순위 정렬
  LOREBOOK 블록 300토큰 예산
       ↓
[Phase 4] 프롬프트 주입
  "[관련 세계 지식]" 블록으로 LLM에 전달
  대사 분리: Stage B에도 관련 fact 전달
```

---

## 3. 데이터 구조 확장

### 3.1 NPC knownFacts 키워드 추가

**Before:**
```json
{
  "factId": "FACT_LEDGER_EXISTS",
  "detail": "부두 노동자들의 임금이 장부와 다르다는 소문",
  "importance": 0.5
}
```

**After:**
```json
{
  "factId": "FACT_LEDGER_EXISTS",
  "detail": "부두 노동자들의 임금이 장부와 다르다는 소문",
  "importance": 0.5,
  "keywords": ["장부", "임금", "급여", "노동", "조작"],
  "minTrust": 0,
  "revealOnce": false
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| keywords | string[] | 트리거 키워드 (1개 이상 매칭 시 활성화) |
| minTrust | number | 이 trust 이상이어야 공개 (기본 0) |
| revealOnce | boolean | true면 한 번 공개 후 비활성화 |

### 3.2 장소 비밀 (Location Secrets)

```json
{
  "locationId": "LOC_MARKET",
  "secrets": [
    {
      "secretId": "SECRET_FAKE_LEDGER",
      "detail": "3번째 노점 뒤 가죽 포대 안에 위조 장부 사본이 숨겨져 있다",
      "keywords": ["노점", "뒤", "가죽", "포대", "장부", "조사"],
      "importance": 0.9,
      "discoveredKey": "SECRET_FAKE_LEDGER",
      "requiresAction": ["INVESTIGATE", "SEARCH", "SNEAK"]
    },
    {
      "secretId": "SECRET_TUNNEL_ENTRANCE",
      "detail": "약초 노점 지하에 밀수 통로 입구가 있다",
      "keywords": ["지하", "통로", "바닥", "약초", "노점"],
      "importance": 0.8,
      "requiresAction": ["INVESTIGATE", "SNEAK"]
    }
  ]
}
```

### 3.3 사건 단계별 키워드 (Incident Stage Keywords)

```json
{
  "incidentId": "INC_SMUGGLING_RING",
  "stages": [
    {
      "stage": 0,
      "keywords": ["화물", "밀수", "창고", "밤", "수상한"],
      "hintOnMatch": "부두에 표식 없는 화물이 쌓여 있다는 소문이 있다",
      "nextStageHint": "화물의 출처를 추적하면 더 많은 것을 알 수 있을 것이다"
    },
    {
      "stage": 1,
      "keywords": ["경로", "문서", "해관", "세관", "서류"],
      "hintOnMatch": "해관청 서류에 위조된 반입 허가서가 섞여 있다",
      "prerequisite": "stage0_discovered"
    }
  ]
}
```

---

## 4. LorebookService 설계

### 4.1 서비스 구조

```typescript
@Injectable()
export class LorebookService {
  constructor(
    private readonly content: ContentLoaderService,
    @Inject(DB) private readonly db: DrizzleDB,
  ) {}

  /**
   * 플레이어 행동에서 키워드를 추출하고,
   * 관련 로어 항목을 매칭하여 프롬프트 주입용 텍스트 반환
   */
  async getRelevantLore(params: {
    rawInput: string;
    actionType: string;
    eventId: string | null;
    currentNpcIds: string[];
    locationId: string;
    npcStates: Record<string, NPCState>;
    runState: Record<string, unknown>;
    discoveredSecrets: string[];    // 이미 발견한 비밀 ID
    discoveredFacts: string[];      // 이미 공개된 fact ID
    turnNo: number;
  }): Promise<LorebookResult> {
    // 1. 키워드 추출
    const keywords = this.extractKeywords(params.rawInput, params.actionType);

    // 2. NPC knownFacts 매칭
    const npcLore = this.matchNpcFacts(keywords, params);

    // 3. 장소 비밀 매칭
    const locationLore = this.matchLocationSecrets(keywords, params);

    // 4. 사건 단서 매칭
    const incidentLore = this.matchIncidentHints(keywords, params);

    // 5. entity_facts 키워드 매칭
    const entityLore = await this.matchEntityFacts(keywords, params);

    // 6. 우선순위 정렬 + 토큰 예산 트리밍
    return this.assembleResult(npcLore, locationLore, incidentLore, entityLore);
  }
}
```

### 4.2 키워드 추출

```typescript
private extractKeywords(rawInput: string, actionType: string): string[] {
  const keywords: string[] = [];

  // 1. rawInput에서 한글 명사 추출 (2글자 이상)
  const words = rawInput.match(/[가-힣]{2,}/g) ?? [];
  keywords.push(...words);

  // 2. actionType 관련 키워드 추가
  const ACTION_KEYWORDS: Record<string, string[]> = {
    INVESTIGATE: ['조사', '단서', '흔적', '증거'],
    SNEAK: ['잠입', '숨어', '몰래'],
    TALK: ['대화', '이야기', '소문'],
    SEARCH: ['찾다', '뒤지다', '살펴'],
    STEAL: ['훔치다', '절도', '빼내'],
    BRIBE: ['뇌물', '돈', '거래'],
    THREATEN: ['위협', '협박'],
    OBSERVE: ['관찰', '지켜'],
  };
  if (ACTION_KEYWORDS[actionType]) {
    keywords.push(...ACTION_KEYWORDS[actionType]);
  }

  return [...new Set(keywords)]; // 중복 제거
}
```

### 4.3 NPC knownFacts 매칭

```typescript
private matchNpcFacts(
  keywords: string[],
  params: LorebookParams,
): LorebookEntry[] {
  const results: LorebookEntry[] = [];

  for (const npcId of params.currentNpcIds) {
    const npcDef = this.content.getNpc(npcId);
    if (!npcDef?.knownFacts) continue;

    const npcState = params.npcStates[npcId];
    const trust = npcState?.emotional?.trust ?? 0;

    for (const fact of npcDef.knownFacts) {
      // 이미 공개된 fact는 스킵
      if (params.discoveredFacts.includes(fact.factId)) continue;

      // trust 체크
      if (fact.minTrust !== undefined && trust < fact.minTrust) continue;

      // 키워드 매칭 (1개 이상 히트)
      const factKeywords = fact.keywords ?? [];
      const matched = factKeywords.some((kw) =>
        keywords.some((k) => k.includes(kw) || kw.includes(k)),
      );

      if (matched || factKeywords.length === 0) {
        results.push({
          type: 'NPC_FACT',
          source: npcId,
          text: fact.detail,
          importance: fact.importance,
          factId: fact.factId,
          matchedKeywords: factKeywords.filter((kw) =>
            keywords.some((k) => k.includes(kw) || kw.includes(k)),
          ),
        });
      }
    }
  }

  return results.sort((a, b) => b.importance - a.importance);
}
```

### 4.4 장소 비밀 매칭

```typescript
private matchLocationSecrets(
  keywords: string[],
  params: LorebookParams,
): LorebookEntry[] {
  const locationDef = this.content.getLocation(params.locationId);
  if (!locationDef?.secrets) return [];

  return locationDef.secrets
    .filter((secret) => {
      if (params.discoveredSecrets.includes(secret.secretId)) return false;
      if (secret.requiresAction && !secret.requiresAction.includes(params.actionType)) return false;
      return secret.keywords.some((kw) =>
        keywords.some((k) => k.includes(kw) || kw.includes(k)),
      );
    })
    .map((secret) => ({
      type: 'LOCATION_SECRET' as const,
      source: params.locationId,
      text: secret.detail,
      importance: secret.importance,
      secretId: secret.secretId,
      matchedKeywords: secret.keywords.filter((kw) =>
        keywords.some((k) => k.includes(kw) || kw.includes(k)),
      ),
    }));
}
```

### 4.5 출력 구조

```typescript
interface LorebookResult {
  /** 프롬프트에 주입할 텍스트 (토큰 예산 내) */
  contextText: string;
  /** 매칭된 항목 목록 (디버깅/로깅용) */
  matchedEntries: LorebookEntry[];
  /** Stage B 대사 생성에 전달할 fact */
  factToReveal?: { factId: string; detail: string; npcId: string };
  /** 새로 발견된 비밀 ID (RunState에 저장) */
  newDiscoveries: string[];
  /** 토큰 사용량 */
  tokensUsed: number;
}
```

---

## 5. 프롬프트 주입 형태

### 5.1 Stage A (서술 LLM)

```
[관련 세계 지식]
이 정보는 플레이어의 행동과 관련된 세계관 단서입니다.
서술에 자연스럽게 녹여내되, 직접 인용하지 마세요.

- [NPC] 부두 노동자들의 임금이 장부 기록과 다르다는 소문이 있다
- [장소] 3번째 노점 뒤 가죽 포대에 무언가 숨겨진 흔적이 있다
- [사건] 표식 없는 화물이 밤마다 부두에 쌓인다는 소문

⚠️ 위 정보를 모두 한 턴에 공개하지 마세요. 가장 관련 있는 1~2개만 암시적으로.
```

### 5.2 Stage B (대사 LLM)

```
[이번에 전달할 정보]
NPC가 이 사실을 간접적으로 암시하세요 (직접 말하지 말고):
"부두 노동자들의 임금이 장부 기록과 다르다"
```

### 5.3 기존 블록과의 관계

| 기존 블록 | 로어북 전환 후 |
|-----------|---------------|
| llmFactsText (entity_facts) | 키워드 매칭으로 선별 주입 |
| activeClues | 로어북 + 사건 단서로 대체 |
| npcKnowledge | 키워드 트리거 + trust 체크로 선별 |
| incidentContext | 단계별 키워드 연쇄로 진화 |

---

## 6. 토큰 예산 재설계

### Before (2,500토큰)

```
SCENE_CONTEXT:      150
INTENT_MEMORY:      200
ACTIVE_CLUES:       150
PREVIOUS_VISIT:     150
RECENT_STORY:       700
STRUCTURED_MEMORY:  450
BUFFER:             250
```

### After (2,500토큰 — 로어북 통합)

```
SCENE_CONTEXT:      150  (유지)
INTENT_MEMORY:      200  (유지)
LOREBOOK:           300  (신규 — ACTIVE_CLUES 흡수)
PREVIOUS_VISIT:     150  (유지)
RECENT_STORY:       700  (유지)
STRUCTURED_MEMORY:  350  (450→350, 로어북으로 이관)
BUFFER:             250  (유지)
```

LOREBOOK 블록 우선순위: 75 (CURRENT_FACTS=80 바로 아래)
→ 키워드 매칭된 관련 지식은 높은 우선도로 보호

---

## 7. 대사 분리 파이프라인 연동

```
Stage A: dialogue_slot 생성 시 로어북 컨텍스트 참조
  → NPC가 어떤 정보를 알고 있는지 인식
  → dialogue_slot.context에 "장부 조작 의심" 포함

Stage B: factToReveal 전달
  → 로어북에서 매칭된 NPC fact → Stage B에 전달
  → "이 사실을 간접적으로 암시하세요"
  → NPC 대사에 단서가 자연스럽게 녹아듦
```

---

## 8. RunState 확장

```typescript
interface RunState {
  // 기존 필드...
  lorebook?: {
    discoveredSecrets: string[];     // 발견한 장소 비밀 ID
    discoveredFacts: string[];       // 공개된 NPC fact ID
    incidentStageDiscovered: Record<string, number>;  // 사건별 발견 단계
  };
}
```

---

## 9. 마이그레이션 전략

### Phase 1: NPC knownFacts 키워드 트리거 (1~2일)

1. npcs.json의 knownFacts에 keywords 필드 추가 (43 NPC)
2. LorebookService 생성 (키워드 추출 + NPC fact 매칭)
3. context-builder에서 LorebookService 호출 → llmFactsText 대체
4. Stage B에 factToReveal 전달
5. 10턴 테스트 검증

### Phase 2: 장소 비밀 시스템 (1~2일)

1. locations.json에 secrets 배열 추가 (7 장소)
2. LorebookService에 장소 비밀 매칭 추가
3. RunState.lorebook.discoveredSecrets 관리
4. 발견 시 entity_facts에 자동 저장

### Phase 3: 사건 단서 연쇄 (2~3일)

1. incidents.json의 stages에 keywords + hintOnMatch 추가
2. 단계별 활성화 로직 (prerequisite 체크)
3. 발견 시 questProgression과 연동
4. 시그널 피드 알림 연동

### Phase 4: entity_facts 키워드 검색 (1일)

1. entity_facts 조회 시 키워드 매칭 조건 추가
2. 기존 entity/location 기반 필터 + 키워드 필터 AND 조건
3. 매칭된 fact만 nano 요약 주입

---

## 10. 기대 효과

| 항목 | Before | After |
|------|--------|-------|
| 토큰 효율 | 블록 전체 주입 (~450) | 키워드 매칭만 (~200) |
| 정보 적중률 | ~60% | ~95% |
| 플레이어 자유도 | 서버 이벤트 의존 | 키워드 기반 자유 탐색 |
| 단서 발견 경험 | "서버가 줌" | "내가 찾음" |
| NPC 대사 관련성 | 일반적 대사 | 대화 주제 연동 대사 |
| 사건 진행 | 이벤트 매칭 의존 | 키워드 연쇄 + 이벤트 보완 |

---

## 11. 참고

- NovelAI Lorebook: keyword trigger + category system
- SillyTavern World Info: regex + vector + probability trigger
- 기존 그레이마르 entity_facts: UPSERT 기반 사실 저장 (로어북 동적 항목)
- 기존 activeClues: importance 기반 단서 선별 (로어북 흡수 대상)
