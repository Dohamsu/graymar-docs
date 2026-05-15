# 45. NPC 자유 대화 — 키워드 트리거 + 잡담 풀 + 메모리 강화

> **목표**: NPC가 "명령 받은 직원"이 아닌 살아있는 인격체로 발화. 플레이어 입력의 주제와 매칭될 때만 fact 공개, 그 외엔 NPC 고유의 일상/감정/관계 대화.
> **배경**: 2026-04-25 사용자 피드백 — "지금 NPC는 알고있는 전부가 그 단서같다." Bug 322aa1a3 분석 과정에서 코드 흐름 확인.

---

## 1. 동기

### 1.1 현재 시스템의 결함 (코드 추적)

**`server/src/llm/context-builder.service.ts:1320-1376`**:

```ts
if (outcome === 'SUCCESS' || outcome === 'PARTIAL') {
  // 1) primaryNpcId 추출
  // 2) NPC의 knownFacts 중 "미공개 첫 번째 fact" 무조건 선택 (순서대로)
  // 3) npcRevealableFact 설정
}
```

**`server/src/llm/prompts/prompt-builder.service.ts:1930-2044`**:
- `npcRevealableFact`가 있으면 `[이번 턴 NPC가 공개할 정보]` 블록을 LLM 프롬프트에 **강제 주입**
- LLM에게 "NPC 말투로 자연스럽게 대화에 녹이세요" 명령
- LLM은 무조건 fact 전달용 대사 생성

### 1.2 결함의 결과

- 키워드 매칭 **없음** — 사용자가 무엇을 물어보든 미공개 fact 자동 공개
- 잡담 모드 **부재** — 일상/관계/감정 대화 분기 없음
- 사용자 체감: **"명령 받은 직원같다"** — 플레이어 입력과 무관하게 NPC가 fact 토해냄

### 1.3 측정 (가정)

기존 게임 플레이 분석 (수동):
- LOCATION 턴 중 SUCCESS/PARTIAL 비율 ~70%
- → 그 70% 턴이 모두 fact 공개 턴
- 같은 NPC와 4~5턴 대화 시 거의 매 턴 fact 노출

---

## 2. 목표 / 비목표

### 2.1 목표

- 플레이어 입력 키워드와 fact 주제가 매칭될 때만 fact 공개
- 미매칭 시 NPC 고유 daily_topics 풀에서 잡담 발화
- 같은 화제 반복 회피 (recentTopics 강화)
- 결정론 유지 (서버 키워드 매칭, nano LLM 추가 호출 없음)

### 2.2 비목표 (Phase 4+)

- NPC가 먼저 화제 꺼내기 (initiative)
- NPC 거짓말 / 정보 모순
- 대화 토픽 트리 UI
- Conversation Stage 강제 게이팅 (자연스러움 해칠 위험)

---

## 3. 설계 원칙 (CLAUDE.md 매핑)

| 원칙 | 적용 |
|---|---|
| Server is Source of Truth | 키워드 매칭은 서버에서 정규식/사전. nano LLM 추가 호출 없음 |
| Stateless 보완 = 명시적 주입 | recentTopics + daily_topics를 프롬프트에 명시적 데이터로 주입 |
| Negative보다 Positive 풀 | 잡담 풀(daily_topics) 제공 → LLM이 매 턴 다양한 화제 선택 |
| 선택지 축소로 유도 | fact 강제 주입 제거, 매칭 시에만 후보화 |
| 사후 삭제 최후 수단 | 입력(프롬프트) 단계에서 해결 |
| 카테고리 단위 통제 | fact / daily_topic / recent 3 풀로 풍선효과 차단 |

---

## 4. 전체 흐름 변경

### 4.1 Before

```
플레이어 입력 → 행동 판정 → SUCCESS/PARTIAL?
  ↓ 예
  → 미공개 첫 fact 자동 선택 → 프롬프트 강제 주입 → LLM이 fact 토해냄
```

### 4.2 After

```
플레이어 입력 → 키워드 추출 → fact 풀 매칭 시도
  ↓
  매칭 ↑ → SUCCESS/PARTIAL이면 → 매칭된 fact 후보 → 프롬프트 주입 → LLM이 자연 대사
  ↓
  매칭 ↓ → 잡담 모드 → daily_topics 1~2개 + recentTopics 회피 주입 → LLM이 자유 대화
```

---

## 5. Phase 1 — 키워드 매칭 게이팅 (1~2일)

### 5.1 데이터 스키마 변경

**`content/graymar_v1/npcs.json`** — `knownFacts[i]` 에 `keywords[]` 필드 추가:

```jsonc
{
  "npcId": "NPC_HARLUN",
  "knownFacts": [
    {
      "factId": "FACT_HARLUN_LEDGER_HINT",
      "detail": "장부는 항만 창고구의 회계실에 있다 들었소",
      "keywords": ["장부", "회계", "기록", "창고", "공물"],  // ← 신규
      "topic": "QUEST_LEDGER",                                 // ← 신규 (선택)
      "priority": 1                                            // ← 신규 (선택)
    }
  ]
}
```

`keywords` 정의 가이드:
- 4~8개 권장
- fact 자체 단어 + 동의어 + 관련 화제 단어
- 너무 일반적인 단어 회피 ("말", "사람" 등)

### 5.2 코드 변경 — `context-builder.service.ts`

```ts
// 1322 line — npcRevealableFact 추출 직전
import { extractKeywords } from '../utils/keyword-extractor.js';  // 신규 또는 lorebook 재사용

const inputKeywords = extractKeywords(rawInput, actionType);  // 기존 lorebook 헬퍼

if (outcome === 'SUCCESS' || outcome === 'PARTIAL') {
  // ... factNpcId 추출 ...
  if (factNpcId) {
    const npcDef = this.content.getNpc(factNpcId);
    if (npcDef?.knownFacts) {
      const revealedFactIds = new Set(...);

      // 신규: 키워드 매칭으로 후보 선별
      const candidates = npcDef.knownFacts
        .filter((f) => !revealedFactIds.has(f.factId))
        .filter((f) => {
          const factKw = f.keywords ?? [];
          return factKw.length === 0 ||                                 // keywords 미정의 fact는 호환 (점진 마이그레이션)
                 factKw.some((kw) => inputKeywords.includes(kw)) ||
                 inputKeywords.some((ik) => factKw.some((fkw) => fkw.includes(ik) || ik.includes(fkw)));
        })
        .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));

      const matched = candidates[0];
      if (matched) {
        npcRevealableFact = { ...기존 로직... };
      }
      // ⚠️ 매칭 안 되면 npcRevealableFact = null 유지 (잡담 모드 진입)
    }
  }
}
```

### 5.3 검증 (Phase 1만으로)

- 단위 테스트: `keywords[]`가 빈 fact는 기존 동작 유지 (호환)
- E2E: 같은 NPC와 5턴 대화. fact 공개 빈도 측정 → 70% → 30~40% 목표
- V9 단어 반복: 같은 fact 키워드가 반복 안 되어 자연스레 감소

### 5.4 마이그레이션 전략

- 기존 NPC knownFacts에 `keywords[]` 비워두면 **현재 동작 유지** (회귀 0)
- CORE NPC 6명 우선 추가 (HARLUN/MAIREL/EDRIC/MIRELA/RAT_KING/RONEN)
- 측정 후 SUB 12명 → BG 25명 순으로 확장

---

## 6. Phase 2 — daily_topics 콘텐츠 확장 (3~5일)

### 6.1 데이터 스키마

**`content/graymar_v1/npcs.json`** — NPC당 `daily_topics[]` 추가:

```jsonc
{
  "npcId": "NPC_HARLUN",
  "daily_topics": [
    {
      "topicId": "TOPIC_HARLUN_DOCK_LIFE",
      "category": "WORK",
      "text": "요즘 부두에 새 일꾼이 안 들어와서 형제단이 점점 늙어가오. 젊은 놈들은 다 시장으로 빠져버렸지.",
      "keywords": ["일꾼", "노동", "부두", "형제단", "젊은이"]
    },
    {
      "topicId": "TOPIC_HARLUN_OLD_GLORY",
      "category": "PERSONAL",
      "text": "복서 시절엔 한 손으로 술잔 쥐고 다른 손으론 상대 코를 부수곤 했소. 이제 그 손이 다 굳어버렸지만.",
      "keywords": ["복서", "옛날", "주먹", "젊었을"]
    },
    {
      "topicId": "TOPIC_HARLUN_CITY_RUMOR",
      "category": "GOSSIP",
      "text": "북쪽에서 또 세금이 오를 거란 소문이 돌더이다. 빈민가는 또 한바탕 시끄럽겠소.",
      "keywords": ["세금", "소문", "북쪽", "빈민가"]
    }
  ]
}
```

카테고리: `WORK / PERSONAL / GOSSIP / OPINION / WORRY` (확장 가능)

### 6.2 풀 규모

- CORE 6명 × 5개 = 30
- SUB 12명 × 4개 = 48
- BG 25명 × 2개 = 50
- **총 128개** (Phase 2 완료 시점)

콘텐츠 작성 가이드: 각 NPC의 personality/role/agenda에 부합. NPC 별칭/실명/직업 자연스레 반영.

### 6.3 코드 변경

**`prompt-builder.service.ts`** — npcRevealableFact가 null일 때만 발동:

```ts
// 5.X 신규 블록 — 잡담 모드 (npcRevealableFact 직후)
if (!ctx.npcRevealableFact && targetNpcIds.size > 0) {
  const npcId = [...targetNpcIds][0];
  const npcDef = this.content.getNpc(npcId);
  const dailyTopics = npcDef?.daily_topics ?? [];

  if (dailyTopics.length > 0) {
    // recentTopics에서 사용한 topicId 제외
    const recentTopicIds = new Set(npcStates[npcId]?.llmSummary?.recentTopics?.map(t => t.topic) ?? []);
    const fresh = dailyTopics.filter(t => !recentTopicIds.has(t.topicId));

    // 입력 키워드와 매칭되는 topic 우선
    const matched = fresh.filter(t =>
      t.keywords?.some(kw => inputKeywords.includes(kw))
    );
    const candidates = matched.length > 0 ? matched : fresh;

    if (candidates.length > 0) {
      const picked = candidates[0];  // 또는 random pick
      factsParts.push([
        `[NPC 일상 화제 — 자연스러운 대화 풀]`,
        `${npcDef.name}의 평소 화제: ${picked.text}`,
        `이 화제를 NPC 말투로 짧게 (1~3문장) 녹이세요. 강요하지 말고 자연스럽게.`,
      ].join('\n'));
    }
  }
}
```

### 6.4 카테고리별 가중치 (Phase 2.5 옵션)

| actionType | 우선 카테고리 |
|---|---|
| TALK / OBSERVE | GOSSIP / OPINION |
| HELP | PERSONAL |
| BRIBE / TRADE | WORK |
| REST | PERSONAL / WORRY |

---

## 7. Phase 3 — recentTopics 강화 (1일)

### 7.1 현재 상태

`NPCState.llmSummary.recentTopics` 이미 존재. 그러나:
- fact 공개만 추적
- 잡담 topicId는 안 들어감

### 7.2 변경

```ts
interface RecentTopicEntry {
  turn: number;
  topic: string;     // factId 또는 topicId
  keywords: string[];
  type: 'FACT' | 'DAILY';   // ← 신규
}
```

- 8턴 윈도우 (현재 N? 확인 후 결정)
- 같은 topic ID 재사용 차단 (자연스러운 변주는 LLM에 위임)
- 풀 고갈 시 → 가장 오래된 topic 재사용 허용 (예: 8턴 전)

---

## 8. 프롬프트 변경 예시

### 8.1 Before (사용자 입력: "오늘 날씨 어때요?")

```
[이번 턴 NPC가 공개할 정보]
전달 방식: 직접 대화
하를런 보스가 플레이어에게 직접 다음 정보를 알려줍니다:
"장부는 항만 창고구의 회계실에 있다 들었소"
NPC의 말투로 자연스럽게 대화에 녹이세요.
```

→ 결과: NPC가 날씨 얘기 묻혀버리고 장부 얘기 함. **부자연.**

### 8.2 After Phase 1 (매칭 안 됨)

```
(npcRevealableFact 블록 없음)
```

→ 결과: NPC가 자유롭게 응답. 하지만 잡담 풀 없으면 LLM이 generic한 답변.

### 8.3 After Phase 2 (잡담 풀 주입)

```
[NPC 일상 화제 — 자연스러운 대화 풀]
하를런 보스의 평소 화제: 요즘 부두에 새 일꾼이 안 들어와서 형제단이 점점 늙어가오.
이 화제를 NPC 말투로 짧게 (1~3문장) 녹이세요. 강요하지 말고 자연스럽게.
```

→ 결과: NPC가 부두 일꾼 한탄 → "오늘 같은 날엔 부두 일도 잘 안 풀리오..." 자연스러운 톤.

### 8.4 After Phase 1+2 (사용자: "장부 얘기 들었소?")

```
[이번 턴 NPC가 공개할 정보]
전달 방식: 직접 대화
하를런 보스가 플레이어에게 직접 다음 정보를 알려줍니다:
"장부는 항만 창고구의 회계실에 있다 들었소"
NPC의 말투로 자연스럽게 대화에 녹이세요.
```

→ 결과: 사용자가 직접 묻자 NPC가 fact 공개. 자연스러운 흐름.

---

## 9. 측정 메트릭

| 메트릭 | 현재 (가정) | Phase 1 후 | Phase 2 후 |
|---|---|---|---|
| Fact 공개 빈도 (LOC 턴 대비) | ~70% | 30~40% | 30~40% |
| 잡담 턴 비율 | 0% | 30~40% | 30~40% |
| daily_topic 발화 / NPC | 0 | 0 | 평균 2~4회 |
| V9 단어 반복 (3턴 윈도우) | 5+회/런 | ~3회 | ~2회 |
| 사용자 체감 (버그 리포트 narrative 카테고리) | 베이스라인 | -30% | -50% |

---

## 10. 위험과 완화

| 위험 | 완화 |
|---|---|
| keywords 정의 누락 → fact 영원히 공개 안 됨 | 기존 호환 (keywords 빈 배열은 모든 입력 매칭) + 점진 마이그레이션 |
| 키워드 매칭 너무 엄격 → 자연 대화 흐름 깨짐 | 부분 일치(includes) + 동의어 + actionType 기본 키워드 |
| daily_topics 콘텐츠 작성 부담 | CORE 우선, SUB → BG 점진 확장. nano LLM으로 초기 생성 후 사람 검수 가능 |
| LLM이 daily_topic 무시하고 generic 답변 | "[NPC 일상 화제] {N}의 평소 화제..." 명시 + 짧게(1~3문장) 가이드 |
| 잡담 모드 + 자유 대화 = 게임 진행 더뎌짐 | UX: SUCCESS/PARTIAL 시 게임 표시 (resolveOutcome 배지) 유지 / 진행도 별도 |

---

## 11. 구현 체크리스트

### Phase 1
- [ ] `npcs.json` 스키마 확장 — knownFacts[i].keywords[] 옵셔널 필드
- [ ] CORE 6명 NPC의 knownFacts에 keywords 추가
- [ ] `context-builder.service.ts:1320` 키워드 매칭 게이팅 로직
- [ ] `lorebook.service.ts`의 extractKeywords / ACTION_KEYWORDS 재사용
- [ ] 단위 테스트: keywords 빈 fact 호환 / 키워드 매칭 / 부분 일치
- [ ] E2E full-run 실행 후 fact 공개 빈도 측정

### Phase 2
- [ ] `npcs.json` 스키마 확장 — daily_topics[]
- [ ] CORE 6명 × 5 = 30개 daily_topics 작성
- [ ] `prompt-builder.service.ts` 잡담 풀 주입 블록
- [ ] (선택) actionType별 카테고리 우선순위
- [ ] E2E: 잡담 턴 비율 30~40% 도달 확인
- [ ] SUB / BG 확장

### Phase 3
- [ ] `RecentTopicEntry` type 확장 (`type: 'FACT' | 'DAILY'`)
- [ ] 잡담 topicId도 recentTopics에 누적
- [ ] 8턴 윈도우 회피 (재사용 룰 정의)
- [ ] 풀 고갈 fallback 정의

---

## 12. 관련 문서

- [[architecture/33_lorebook_system|lorebook system]] — 키워드 트리거 인프라 (Phase 1이 이 위에 구축)
- [[architecture/31_memory_system_v4|memory system v4]] — recentTopics / npcStates 구조
- [[architecture/26_narrative_pipeline_v2|narrative pipeline v2]] — 3-Stage 파이프라인 (이 변경은 Stage 1 컨텍스트 빌드 단계)
- [[architecture/09_npc_politics|npc politics]] — NPC 감정/소개 (trust/posture 게이팅 컨텍스트)
- [[CLAUDE]] §LLM 설계 원칙 — Stateless 보완 / Positive 풀 / 카테고리 통제 (이 설계 직접 적용)

---

## 13. Open Questions

- Q1. keywords 정의를 npcs.json에 인라인 vs 별도 keyword-table.json?
  → 인라인 추천. fact와 keywords가 1:1 결합되어 가독성 높음. 분리 시 동기화 비용.
- Q2. daily_topic의 keywords와 fact의 keywords가 충돌하면?
  → fact 우선 (priority 1). daily_topic은 매칭 fallback.
- Q3. 같은 daily_topic을 N턴 후 재사용 허용?
  → recentTopics 8턴 윈도우 만료 후 허용. 단 같은 NPC와의 직전 1턴은 절대 금지.
- Q4. 잡담 모드에서도 resolveOutcome 표시?
  → 표시. 단 PARTIAL/FAIL이라도 fact 미주입이면 사용자 체감 동일. UX 별 차이 없음.
- Q5. nano LLM으로 daily_topics 초기 생성?
  → 가능. NPC personality/role 기반 5개 생성 → 사람 검수 → 콘텐츠 push. Phase 2 작업 시간 1/3로 단축.

---

## 14. 향후 확장 포인트 (Phase 4+)

- NPC initiative — 첫 턴에 NPC가 화제 꺼냄 (`이번 턴 NPC가 먼저 말함` 블록)
- Mood/Tension 게이팅 — heat/위험도/시간대로 잡담 ↔ fact 가중치 변동
- Compatibility — traits 궁합 기반 daily_topic 우선순위 (BLOOD_OATH가 의리 NPC와 매칭 시 우선)
- 사회적 컨텍스트 — 다른 NPC 청취 시 fact 거부 (사적 자리 필요)
