# 46. Fact Pool + NPC Continuity — Fact를 일급 객체로 분리

> **목표**: NPC 점프 근본 차단. fact 매칭이 NPC를 강제 등장시키지 않도록 분리하고, NPC 결정은 사용자 의도(텍스트 호명/대화 잠금/맥락) 기반으로.
> **계기**: Bug 892fa819 — 마이렐과 4턴 대화 중 "내부 조사" 키워드로 에드릭이 갑자기 등장. conversationLock 4턴 만료 + EventMatcher의 단일 primaryNpc 매칭이 NPC를 강제로 바꿈.
> **선행**: architecture/34 (Player-First Event Engine) · architecture/45 (NPC Free Dialogue) · architecture/33 (Lorebook)
> **작성**: 2026-04-25

---

## 1. 동기

### 1.1 현재 결함 (Bug 892fa819)

```
T4~T7 마이렐과 자연스러운 대화 (FACT_INSIDE_JOB 화제)
T8 입력: "더 자세한 내부 조사 내용을 묻는다"
T8 결과: 에드릭 베일이 갑자기 등장 ❌
```

원인 추적:
- `conversationLock` 4턴(T4~T7) 만료 → T8에 잠금 해제
- `EventMatcher`가 "내부 조사" 키워드로 EVT_GUARD_INT_2 (primaryNpc=에드릭) 매칭
- 그런데 **마이렐도 FACT_INSIDE_JOB을 다른 시각으로 알고 있음**
  - 마이렐: "경비대 내부 밀수 연결... 야간 순찰 보고서 빈 시간대"
  - 에드릭: "장부 도난 내부자... 권한 3명"
- 시스템이 같은 fact 다른 시각 중 EventMatcher 우선순위로 에드릭 선택
- 사용자 인식: 같은 NPC 같은 화제 / 시스템 동작: 새 NPC 점프

### 1.2 진단

`fact ↔ NPC 강제 결합`이 근본 결함:
- fact가 NPC.knownFacts 안에 묶여있음
- 키워드 매칭 → 그 fact의 owner NPC 등장
- 사용자 의도와 무관하게 NPC가 점프

→ 해법: **Fact를 일급 객체로 분리** + **NPC 결정 자체를 사용자 의도 기반으로**

---

## 2. 목표 / 비목표

### 2.1 목표

- NPC 결정과 Fact 결정 **완전 분리**
- 같은 fact를 여러 NPC가 다른 시각으로 보유 가능 (이미 구현됨)
- 현재 대화 NPC가 fact를 알면 → 그 NPC의 detail 사용
- 모르면 → 인계 가이드 또는 default 텍스트
- conversationLock 시간 제한 폐기 (명시적 해제만)

### 2.2 비목표 (Phase 2+)

- RUMORED 레이어 (소문 NPC) — 데이터 보강 후
- fact priority 필드 — 현재 quest stage로 충분
- lorebook 통합 — 별도 트랙
- NPC 자율 발화 (initiative) — 다른 설계

---

## 3. 데이터 모델 — 변경 거의 없음

### 3.1 현재 데이터 (그대로 활용)

```jsonc
// quest.json
"facts": {
  "FACT_INSIDE_JOB": {
    "description": "경비대/회계 내부에서 누군가 밀수에 협조 중",
    "nextHint": "...",
    "discoveryLocations": ["LOC_GUARD", "LOC_HARBOR"],
    "primarySources": ["NPC_EDRIC_VEIL", "NPC_MAIREL", "NPC_TOBREN", ...],  // 이미 분산
    "stage": "S2→S3"
  }
}

// npcs.json[i].knownFacts
{
  "factId": "FACT_INSIDE_JOB",
  "detail": "경비대 내부 밀수 연결... 야간 순찰 보고서 빈 시간대",  // NPC별 시각
  "keywords": ["내부", "소행", "접근", "권한", "도난"]
}
```

→ **데이터 마이그레이션 불필요**. quest.facts (description/stage) + npcs.knownFacts.detail이 이미 분산.

### 3.2 추가 필드 (선택, P2)

- npcs.knownFacts[i].level: 'KNOWN' | 'RUMORED' (Phase 2)
- quest.facts[i].handoffNpcs: ["NPC_EDRIC_VEIL"] (인계 가이드용)

P0에서는 추가 안 함. 기존 데이터로 작동.

---

## 4. 알고리즘 — NPC 결정 / Fact 결정 분리

### 4.1 NPC 결정 (Continuity Engine)

**우선순위 (위에서 아래로 검사, 첫 매칭 사용)**:

```
1. 텍스트 NPC 호명 매칭
   - "미렐라에게..." / "회계사 양반..." 등 명시 호명
   - npcs.json name / unknownAlias / shortAlias / aliases 매칭
   - 매칭 시 그 NPC로 즉시 전환 (이전 잠금 해제)

2. 명시적 NPC 전환 신호
   - "다른 사람과 얘기" / "저 사람" / "주변 다른 인물" 의도
   - 잠금 해제 + EventMatcher로 위임

3. 명시적 해제 신호 (이동/공간 변화)
   - "다른 곳으로 이동" / "자리를 뜬다" / "돌아간다"
   - 잠금 해제

4. conversationLock NPC (시간 제한 폐기)
   - 잠금 NPC 그대로 유지 (4턴 만료 X)
   - 위 1/2/3 신호 없으면 무한 유지

5. 직전 턴 primaryNpcId carry-over
   - 잠금 없을 때 직전 턴 NPC

6. EventMatcher 새 매칭 (마지막 폴백)
   - 위 5단계 모두 실패 시
```

### 4.2 Fact 결정 (Pool Engine)

```
1. 입력 키워드 추출 (한글 명사 2자+ + actionType 키워드)
2. 모든 fact 풀에서 키워드 매칭 → 후보 풀 추출
3. discoveredQuestFacts 제외 (이미 발견된 fact)
4. quest 현재 stage 우선순위 적용:
   - 현재 stage 진행에 필요한 fact 우선
   - 다음 stage fact는 후순위
5. recentTopics 회피 (같은 fact 반복 차단)
6. 결정된 NPC가 후보 fact 중 보유 여부 검사 → 4-mode 분기
```

### 4.3 4-mode 분기 (사용자 결정 필요)

| 매칭 fact | 현재 NPC 보유 | 다른 NPC 보유 | 모드 | 동작 |
|---|---|---|---|---|
| 0 | - | - | **잡담** | daily_topics 주입 (기존 Phase 2) |
| ≥1 | ✅ | - | **Fact 공개** | NPC detail 사용 + revealMode (기존) |
| ≥1 | ❌ | ≥1 | **인계** ⚠️ | "그건 X에게 물어보시오" 가이드 |
| ≥1 | ❌ | 0 | **default** ⚠️ | quest.description 활용한 일반 답변 |

⚠️ **인계 / default 동작 결정 필요** (Open Question 1)

### 4.4 우선순위 알고리즘 (B3-B5 해결)

같은 키워드가 여러 fact 매칭 시:

```python
def selectFact(candidates, currentNpcId, currentStage, recentTopics):
    # 1. 이미 발견된 fact 제외
    candidates = [f for f in candidates if f.factId not in discoveredQuestFacts]
    # 2. 현재 NPC가 보유한 fact 우선
    own_facts = [f for f in candidates if currentNpcId in f.knownBy]
    # 3. quest 현재 stage 매칭 우선
    if currentStage == 'S0_ARRIVE':
        own_facts.sort(key=lambda f: 0 if f.stage == 'S0→S1' else 1)
    # 4. recentTopics 회피
    own_facts = [f for f in own_facts if f.factId not in recentTopics]
    # 5. 첫 번째 선택
    return own_facts[0] if own_facts else None
```

---

## 5. 14 빈틈 반영 — 결정 사항

### 5.1 P0 — 즉시 결정 필요 (3건)

#### B6/B10. NPC가 모르는 fact 매칭 시 동작 ⚠️

**옵션 A — 인계 가이드** (권장)
- "그건 잘 모르오. 회계사한테 물어보시오"
- 자연스러운 정보 분산 게임플레이
- 게임 깊이 증가 (다른 NPC 찾아가는 동기)

**옵션 B — 잡담 모드 fallback**
- 단순히 daily_topic 주입
- 사용자 질문 무시 효과
- 단순 구현

**제 추천: A** — fact 분산이 게임 디자인 의도와 맞음.

#### B7/B8. NPC Continuity Engine 범위

**옵션 A — 텍스트 호명 + 잠금 무한 유지** (권장)
- 사용자가 명시적 NPC 부르거나 이동/전환 신호 줄 때만 전환
- conversationLock 시간 제한 폐기

**옵션 B — 텍스트 호명만**
- 잠금은 4턴 유지 그대로
- 조금 보수적

**제 추천: A** — 사용자 신고 케이스(마이렐 점프) 직접 해결.

#### B14. NPC 누구도 모를 때 default 텍스트

**옵션 A — quest.facts.description 활용** (권장)
- 이미 있는 데이터: "공물 장부가 존재하며 도난당했다는 사실"
- LLM이 일반 서술로 변형
- 데이터 추가 0

**옵션 B — 새 default 필드 추가**
- 데이터 작업 부담

**제 추천: A** — 추가 데이터 없음, 기존 description 활용.

### 5.2 P1 — 설계 명확화 (3건)

- **B10 모드 경계** 4×4 테이블 위에 명시. Open ❓.
- **B11 trust/posture** — 기존 revealMode 그대로 사용 (잠금 NPC + revealMode 결합).
- **B14 default** — quest.description 활용 (위 결정).

### 5.3 P2 — 추후 (5건)

- B1 LEDGER_CONTENTS quest 추가 결정 (별도 콘텐츠 검토)
- B2 primarySources 동기화 (자동 스크립트 가능)
- B9 lorebook 통합 (현재 둘 분리 운영, 추후 통합)
- B12 RUMORED 레이어 (데이터 보강 후)
- B13 priority 필드 (당분간 stage로 충분)

---

## 6. 구현 영역

### Phase 0 — 설계/검토 (현재)

- 설계 문서 작성 (이 문서)
- 14 빈틈 결정 (Open Questions)

### Phase 1 — NPC Continuity Engine (코드 변경)

**파일**: `server/src/turns/turns.service.ts` (Player-First 엔진 진입부)

```typescript
// 기존 NPC 결정 5단계 우선순위에 추가:
// 0. 텍스트 NPC 호명 매칭 (이미 있음)
// 1. 명시적 전환 신호 감지 (신규)
// 2. 명시적 해제 신호 감지 (신규)
// 3. conversationLock — 시간 제한 폐기, 무한 유지 (수정)
// 4. 직전 턴 carry-over (이미 있음)
// 5. EventMatcher 폴백 (이미 있음)
```

규모: ~50줄 추가 + conversationLock 만료 로직 1줄 변경

### Phase 2 — Fact Pool 결정

**파일**: `server/src/llm/context-builder.service.ts:1322`

```typescript
// 기존: primaryNpcId.knownFacts 단독 검색
// 변경:
// 1. 입력 키워드로 모든 fact 후보 추출 (helper)
// 2. discoveredQuestFacts 제외
// 3. quest stage 우선순위
// 4. 현재 NPC 보유 검사 → 4-mode 분기
```

규모: ~80줄 (헬퍼 함수 + 4-mode 분기 포함)

### Phase 3 — 인계 가이드 프롬프트

**파일**: `server/src/llm/prompts/prompt-builder.service.ts:1930~`

```typescript
// 인계 모드 시 새 블록:
factsParts.push([
  `[NPC 모름 — 인계 가이드]`,
  `${currentNpcDisplayName}은(는) "${factTopic}"에 대해 잘 모릅니다.`,
  `다른 NPC가 알고 있다는 것을 자연스럽게 암시하세요:`,
  `예: "그건 잘 모르오. 시장의 회계사한테 물어보면 알 수도 있겠지."`,
  `대상 NPC: ${otherNpcsHint}`,
].join('\n'));
```

규모: ~30줄

### Phase 4 — default 텍스트 활용

기존 quest.description을 LLM에 자연 서술 가이드로 주입.
규모: ~15줄

### Phase 5 — P2 데이터 정리 (선택)

- primarySources 자동 동기화 스크립트
- LEDGER_CONTENTS quest 통합 결정

---

## 7. 위험 및 완화

| 위험 | 확률 | 영향 | 완화 |
|---|---|---|---|
| Quest stateTransitions 회귀 | 낮음 | 매우 높음 | discoveredQuestFacts 추적 그대로 유지 |
| conversationLock 무한 유지 → 다른 NPC 등장 못 함 | 중 | 중 | 명시적 전환/해제 신호 정확히 감지 |
| 텍스트 호명 매칭 오탐 | 중 | 중 | NPC 이름 정확 매칭 + 별칭 사전 |
| 인계 가이드 오류 | 낮음 | 낮음 | LLM에 명시 가이드 |
| EventMatcher 약화 → World 이벤트 누락 | 낮음 | 중 | WORLD_EVENT turnMode는 별도 흐름 유지 |
| LLM 프롬프트 길이 증가 | 낮음 | 낮음 | 인계/default 블록 짧게 (1~2줄) |

---

## 8. 측정 메트릭

### 도입 전 (현재)
- NPC 점프 빈도: bug 892fa819 형태 발생 ~10% 추정
- 같은 NPC 연속 대화 평균: 4턴 (잠금 만료)
- fact 발견 후 stage 전환 정확도: ~80%

### 도입 후 목표
- NPC 점프 (사용자 의도와 무관): **<2%**
- 같은 NPC 연속 대화 평균: **8~12턴** (사용자 의도까지)
- 인계 시나리오 활용: 사용자가 다른 NPC로 이동하는 빈도 +30%
- fact 발견 후 stage 전환: 100%
- 잡담/fact 분기 정확도: 95%+

### 측정 방법
- bug 892fa819 시나리오 자동 재현 (마이렐 4턴+ 후 키워드 입력)
- E2E `scripts/e2e/regression.ts`에 추가
- 사용자 피드백 (버그 리포트 narrative 카테고리 발생률)

---

## 9. Open Questions — 사용자 결정 필요

### Q1. 인계 모드 (B6) 동작
- A. 인계 가이드 ("X에게 물어보시오") — 권장
- B. 단순 잡담 fallback

### Q2. NPC Continuity 범위 (B7/B8)
- A. 텍스트 호명 + 잠금 무한 유지 — 권장
- B. 텍스트 호명만, 잠금은 4턴 유지

### Q3. default 텍스트 (B14)
- A. quest.description 활용 — 권장
- B. 새 default 필드 추가

### Q4. RUMORED 레이어 (B12) — P2
- A. 도입 (소문 NPC 데이터 보강)
- B. 단순화 (KNOWN만)

### Q5. lorebook 통합 (B9) — P2
- A. FactPool과 통합 (한 시스템)
- B. 분리 유지 (현재대로)

### Q6. priority 필드 (B13) — P2
- A. 추가 (fact별 우선순위)
- B. quest stage로만 (현재 충분)

---

## 10. 구현 일정 추산

| Phase | 시간 |
|---|---|
| 0 — 설계/결정 | 1시간 (현재) |
| 1 — NPC Continuity | 1.5시간 |
| 2 — Fact Pool 결정 | 2시간 |
| 3 — 인계 가이드 | 30분 |
| 4 — default 활용 | 30분 |
| 검증/테스트 | 1시간 |
| **합계 P0** | **6시간** |
| 5 — P2 데이터 (선택) | 별도 |

---

## 11. 관련 문서

- `architecture/34_player_first_event_engine.md` — NPC 결정 5단계 (이 설계는 그 위)
- `architecture/45_npc_free_dialogue.md` — Phase 2 잡담 풀 (이 설계와 통합)
- `architecture/33_lorebook_system.md` — 키워드 트리거 인프라 (활용)
- `CLAUDE.md` §26 — 대화 잠금 (이 설계로 대체)
- `CLAUDE.md` §34 — Player-First 5단계 (이 설계가 강화)

---

## 12. 변경 사항 vs 기존 시스템

| 시스템 | 기존 | 신규 |
|---|---|---|
| NPC 결정 | EventMatcher 우선 | 사용자 의도 우선 (Continuity Engine) |
| conversationLock | 4턴 만료 | 무한 유지 (명시적 해제만) |
| Fact 공개 | primaryNpc.knownFacts 단독 | Fact Pool + 현재 NPC 보유 검사 |
| 모르는 fact | (해당 케이스 없음, 강제 공개) | 인계 또는 default |
| 데이터 구조 | 변경 없음 | 변경 없음 |
| DB 스키마 | 변경 없음 | 변경 없음 |
| Quest progression | 기존 흐름 | 기존 흐름 (discoveredQuestFacts 그대로) |
