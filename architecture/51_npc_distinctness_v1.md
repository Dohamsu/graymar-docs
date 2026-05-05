# 51. NPC Distinctness v1 — Personality 신호 강화 + 단계적 실험

> **목표**: 모든 NPC가 동일한 "지령 수행" 톤으로 수렴하는 현상을 NPC personality 신호 강화 + 측정 가능한 강제 룰로 해소. A50 실패 교훈을 반영해 큰 변경 X, 단일 단위 실험 + A/B 비교로 객관 검증.
> **선행**: architecture/47 (NPA 검증) + 49 (Resolver Authority) + 50 (Natural Dialogue, ⚠️ 폐기).
> **검출**: NPA 8 시나리오 평균 3.36 / ERROR 0 안정 baseline. 사용자 보고: "여전히 약간의 로봇스러움이 있고, 마치 지령을 받은 듯하게 정해진 말만 한다."
> **작성**: 2026-04-28

---

## 1. A50 실패 회고

### 1.1 A50의 가설과 결과

**가설**: 매 턴 LLM이 받는 10개 블록 + 12개+ 메타 지시 → "지령 수행" 톤. 압축 + 시스템 프롬프트 이동 → 자연 발화.

**결과**:
| 단계 | 평균 | ERR |
|---|---|---|
| Pre-A50 | 3.29 | 0 |
| Phase 4 (전체 적용) | 3.01 | 1 |
| Phase 4b (부분 롤백) | 3.01 | 3 |
| Rollback | **3.36** | **0** ✓ |

→ Humanity는 +0.34 향상됐으나 TopicFreedom -1.0 손실로 상쇄. ERROR 0→1~3 회귀.

### 1.2 5가지 교훈

**T1. 프롬프트 양은 본질 문제가 아니다**
압축해도 톤 변화 미미. "프롬프트 압축 = 자연 발화"는 잘못된 가설.

**T2. 시스템 프롬프트 이동 = 강도 약화**
캐시된 일반 규칙은 매 턴 새 지시보다 약함 (CLAUDE.md "soft 지시 무시" 풍선효과 확인).

**T3. 블록 간 의존성 복잡**
[NPC 등장] 압축 → 익명 인물 마커 회귀. 부분 롤백이 추가 회귀 유발(1→3건).

**T4. 자연스러움 ≠ NPA 점수**
NPA가 "톤 적합도/personality 차별화" 미측정. 측정 시스템과 인간 직관 갭.

**T5. 큰 변경 한꺼번에 = 디버깅 불가**
Phase 1+2+3 동시 적용 → 어느 변경이 회귀 유발인지 파악 어려움. 각 변경 독립 검증 필요.

---

## 2. 문제 재정의

### 2.1 진짜 원인 가설 (A50과 다름)

> **"지령받은 느낌"의 본질은 프롬프트 양이 아니라 NPC personality 신호의 약함이다.**

근거:
- 모든 NPC(쥐왕/미렐라/마이렐/에드릭)가 "독/뿌리/위험/조심하시오" generic mysterious tone으로 수렴
- speechStyle 텍스트는 있지만 LLM이 NPC별 distinct 시그니처를 출력하지 못함
- 사용자 입력 톤(가벼운 잡담)을 LLM이 무시 — 항상 무거운 톤
- chat-edric (도박꾼/신경질적) personality가 거의 안 드러남 — Humanity 2.93 가장 낮음

### 2.2 새 가설

```
Old (A50): 줄이면 자연스러워진다.
New (51):  signal-to-noise ratio를 높여야 자연스러워진다.
           = 메타 지시는 줄이지 말고, NPC distinct 신호를 더 강하게.
```

### 2.3 측정 가능 vs 측정 불가능

A50의 한계는 NPA가 "Humanity"만 측정하고 NPC distinct 차별화/사용자 톤 매칭을 측정 못 한다는 것. 새 메트릭 필요:
- **NpcDistinctness**: 각 NPC 발화의 고유 패턴 (signature 단어/문장 구조) 비율
- **ToneMatch**: 사용자 입력 톤 vs NPC 응답 톤 일치도

이 메트릭이 없으면 A50처럼 "Humanity는 향상됐는데 다른 게 손실"되는 trade-off를 객관 평가 불가.

---

## 3. 3가지 개선 방향

### 3.1 방향 1 — NPC distinct mannerism 강화 (콘텐츠)

**현재 문제**: speechStyle 텍스트가 generic
- 쥐왕: "쉰 목소리의 압도적이고 느린 경어. 문장을 일부러 끝맺지 않아 상대를 긴장시킨다." → LLM이 "쉰 목소리"를 못 보여줌
- 미렐라: "약초 비유를 즐겨 쓴다" → 모든 답에 "독/뿌리" 반복 → 차별화가 단조로 변환

**개선**:
- speechStyle을 "trait → 구체적 mannerism rule" 형태로 재구조화
- NPC별 distinct rules — 매 턴 매칭 가능한 구체 패턴
  - 쥐왕: 문장 끝 "..." 50% 이상, 손가락 벽 긁기
  - 미렐라: 약초 비유 1회/턴 (반복 차단), "이 할미가" 시작 호칭
  - 하를런: "형제" 호칭 사용, 주먹 쥐었다 펴기 동작
  - 마이렐: "그대" 호칭, 단호 ~소/~시오
  - 에드릭: 숫자 1개 인용 (예: "삼할" "두 자루"), 안경테 만지기, 신경질적 더듬기 ("~~ 그러니까... ~~")
  - 로넨: 절박할 때 더듬기, 주변 살피기, 손 비비기

**작업량**: NPC당 ~30분 × CORE 6명 = ~3h
**리스크**: 작음 — 콘텐츠만, 코드 변경 X

### 3.2 방향 2 — 검증 가능한 강제 룰 (코드 후처리)

**현재 문제**: 시스템 프롬프트의 "soft 지시" 무시 (회피 어휘 ≤1회/턴 등)

**개선**: LLM 출력 후 코드로 검증 + 위반 시 재요청 또는 후처리 교정.
- **R1 회피 어휘 ≤1/턴**: "위험/조심하/곤란/입을 다물" 카운트. 2회 이상이면 1개만 남기고 제거.
- **R2 사용자 입력 키워드 포함**: 사용자 입력의 핵심 명사 1개 이상 NPC 응답에 미포함이면 재요청 (1회 한정).
- **R3 응답 길이 매칭**: 사용자 입력 ≤15자 + actionType=TALK면 NPC 응답 ≤25자 강제 (현재 응답이 길면 첫 1~2문장만).

**작업량**: ~3h (각 룰 ~1h)
**리스크**: 중 — 후처리가 LLM 출력 자르면 부자연스러울 수 있음. 룰별 단계 적용 + A/B 비교.

### 3.3 방향 3 — NPA 메트릭 v2 (선행 작업)

**현재 NPA 한계**:
- Continuity / TopicFreedom / Humanity 3 score만 측정
- "개별 NPC가 distinct하게 말하는가" 미측정
- "사용자 톤(가벼움/심각함) vs NPC 톤 일치" 미측정

**추가 메트릭**:

**NpcDistinctness** — NPC별 distinct 시그니처 비율
- 입력: NPC ID + 발화
- 측정: NPC.personality.signature/traits에서 추출한 "고유 패턴" 등장률
- 점수: 8 시나리오에서 동일 NPC가 다른 시나리오와 vs 다른 NPC와의 차이 거리

**ToneMatch** — 사용자 ↔ NPC 톤 일치도
- 사용자 입력 톤 분류 (gravitas/casual)
  - casual: 짧은 길이, 의문문, "?" 포함, 가벼운 명사
  - gravitas: 긴 길이, fact 키워드, 무거운 명사
- NPC 응답 톤 분류 (회피 어휘 비율 + 길이)
- 일치도 = 일치 턴 / 전체 턴

**작업량**: ~3h (메트릭 정의 + 구현 + 시나리오 검증)
**리스크**: 작음 — NPA 측정만 추가, 코드 회귀 영향 X

---

## 4. 단계적 실험 계획

A50의 큰 실수(한꺼번에 변경)를 반복하지 않기 위해 **각 단계 독립 검증** + **A/B 비교**.

### Step 1 (선행) — NPA 메트릭 v2 (~3h)

**목적**: 객관 측정 토대 마련. 측정 못 하면 개선 방향도 객관화 불가.

1.1. NpcDistinctness 메트릭 추가 (dialogue-quality.ts)
1.2. ToneMatch 메트릭 추가
1.3. 베이스라인 측정 — 현재 8 시나리오에서 두 메트릭 점수 기록

**완료 기준**: 8 시나리오 baseline distinctness/toneMatch 점수 측정 완료. 회귀 0.

### Step 2 — 단일 NPC mannerism 강화 (방향 1 일부, ~1h)

**목적**: 작은 실험으로 효과 검증. 효과 있으면 확장.

2.1. NPC_RAT_KING(쥐왕) 1명만 mannerism 강화
- speechStyle 보강: "..." 패턴 명시, 손가락 벽 긁기 mannerism 강조
- daily_topics 키워드 보강 (text는 그대로 유지 — A50 Phase 2 회귀 학습)
- traits에 distinct mannerism 추가
2.2. chat-rat-king 시나리오만 NPA 검증 — A/B 비교
- A: 변경 전 baseline
- B: 쥐왕 mannerism 강화 후
- 비교: NpcDistinctness, Humanity, 종합

**완료 기준**: 쥐왕 NpcDistinctness +0.5 이상 향상. 다른 메트릭 회귀 없음.

### Step 3 — Step 2 효과 있으면 CORE 6명 확장 (~3h)

Step 2 통과 시 — 미렐라/하를런/마이렐/에드릭/로넨/밴스 경 mannerism 강화. 각 NPC NPA 시나리오로 검증.

### Step 4 — R1 회피 어휘 강제 룰 (방향 2 일부, ~1h)

**목적**: 가장 명확한 룰 1개부터 후처리 검증.

4.1. llm-worker.service.ts 후처리 단계에 R1 추가:
- 회피 어휘("위험/조심하/곤란") 카운트
- 2회 이상이면 1개만 남기고 제거
4.2. 8 시나리오 NPA — A/B 비교
- A: R1 미적용
- B: R1 적용
- 비교: AVOID_WORD_HEAVY, Humanity, 종합

**완료 기준**: AVOID_WORD_HEAVY WARN 50% 감소. 다른 메트릭 회귀 없음.

### Step 5 — Step 4 효과 있으면 R2/R3 추가 (~2h)

Step 4 통과 시 — R2 (사용자 키워드 포함) + R3 (응답 길이 매칭) 적용. 각 룰 독립 A/B.

### Step 6 — 통합 검증 + 커밋·푸시 (~1h)

Step 1~5 모두 통과 시 통합 검증. 회귀 없으면 커밋·푸시.

---

## 5. 데이터 모델 변경 (선택)

### 5.1 NpcPersonality 확장

```ts
export type NpcPersonality = {
  core: string;
  traits: string[];
  speechStyle: string;
  speechRegister?: 'HAOCHE' | 'HAEYO' | 'BANMAL' | 'HAPSYO' | 'HAECHE';
  innerConflict: string;
  softSpot: string;
  signature: string[];
  npcRelations?: Record<string, string>;
  /** architecture/51 — NPC distinct mannerism rules.
   * 매 턴 매칭 가능한 구체 패턴 (예: "문장 끝 '...' 50%", "약초 비유 1회/턴").
   * speechStyle 텍스트는 generic하지만 mannerismRules는 enforce 가능. */
  mannerismRules?: string[];
};
```

### 5.2 NPA 새 score type

```ts
export interface NpcDistinctnessScore {
  score: number;
  perNpcDistinctness: Record<string, number>;
  notes: string[];
}

export interface ToneMatchScore {
  score: number;
  perTurnMatch: Array<{ turn: number; userTone: string; npcTone: string; matched: boolean }>;
  notes: string[];
}

export interface DialogueQualityV2 extends DialogueQuality {
  npcDistinctness: NpcDistinctnessScore;
  toneMatch: ToneMatchScore;
  overallV2: number; // 5 score 평균
}
```

---

## 6. 위험 및 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| 콘텐츠 강화가 LLM에 더 무겁게 작용 (역효과) | 중 | Step 2에서 단일 NPC만 → A/B 비교로 차단 |
| 후처리 룰이 LLM 출력 자르면 부자연 | 중 | Step 4에서 단일 룰 1개부터 → 부자연 검출 시 즉시 롤백 |
| NpcDistinctness/ToneMatch 측정이 정확하지 않을 수 있음 | 작 | 베이스라인 측정 후 시각 검증 (실제 발화 spot check) |
| Step 1 NPA v2 메트릭 자체가 회귀 유발 | 작 | dialogue-quality.ts 추가만, 기존 측정에 영향 X |

---

## 7. A50과의 차이점 (의도적)

| 항목 | A50 (실패) | 51 (이번) |
|---|---|---|
| 가설 | "프롬프트 양 줄이면 자연" | "personality 신호 강화하면 자연" |
| 변경 단위 | 프롬프트 5블록 동시 | 단일 NPC, 단일 룰부터 |
| 측정 | 기존 NPA만 (한계) | NPA v2 선행 (객관) |
| A/B 비교 | 없음 (전후 비교만) | Step 단위 A/B |
| 롤백 단위 | 전체 또는 부분 (둘 다 회귀) | 단일 단위라 깨끗한 롤백 |
| 위험 | 큰 변경 한꺼번에 | 점진 누적 |

---

## 8. 메트릭 목표 (v2 기준)

| 지표 | 베이스라인 | Step 5 후 목표 |
|---|---|---|
| 평균 종합 (기존 3 score) | 3.36 | 3.36 유지 (회귀 X) |
| ERROR | 0 | 0 유지 |
| **NpcDistinctness** (신규) | TBD (Step 1 측정) | Step 1 대비 +0.5 |
| **ToneMatch** (신규) | TBD | Step 1 대비 +0.3 |
| AVOID_WORD_HEAVY WARN | 5건/8 | ≤2건 |
| 사용자 만족도 (정성) | "여전히 로봇스러움" | "personality 차별화 느껴짐" |

---

## 9. Open Questions

### Q1. mannerismRules를 LLM에 어떻게 주입?
- 옵션 A: speechStyle 텍스트에 통합 (현재 형태 유지, 길이 증가)
- 옵션 B: 별도 [NPC mannerism] 블록 추가 (새 블록 — A50 교훈상 위험)
- 추천: A (안전)

### Q2. R1 회피 어휘 후처리 위치
- llm-worker Step F (NPC 마커 교정) 이후 단계로 추가
- 또는 dialogue-generator (대사 분리 단계)
- 추천: dialogue-generator — 대사 텍스트를 직접 다룸

### Q3. NPA v2 메트릭이 false positive를 만들 가능성
- NpcDistinctness가 너무 엄격하면 baseline도 낮게 나옴
- baseline 측정 후 threshold 조정

### Q4. Step 4 R1 후처리가 문장 구조를 깨면?
- "위험" 단어를 "근심" 등으로 치환
- 또는 그 문장 통째로 제거
- A/B로 어느 게 자연스러운지 비교

### Q5. A50의 [잡담 영감] 키워드화 시도는 재시도?
- A50에서 TopicFreedom 회귀 유발 (균등 2.08)
- v2 NPA로 객관 측정 가능해진 후 별도 검토. 본 v1에선 미포함.

---

## 10. 관련 문서

- [[architecture/26_narrative_pipeline_v2|narrative pipeline v2]] — 3-Stage Pipeline (후처리 단계 통합)
- [[architecture/45_npc_free_dialogue|npc free dialogue]] — daily_topics 잡담 시스템
- [[architecture/47_dialogue_quality_audit|dialogue quality audit]] — NPA 검증 도구 (v2 확장 대상)
- [[architecture/49_npc_resolver_authority|npc resolver authority]] — NPC 결정 단일 권한자
- [[architecture/50_natural_dialogue_v1|natural dialogue v1]] — 시도 후 폐기 (본 문서의 직접 선행)
- `server/src/llm/prompts/prompt-builder.service.ts` — Step 2/3 콘텐츠 활용
- `server/src/llm/dialogue-generator.service.ts` — Step 4/5 후처리 위치
- `scripts/e2e/audit/dialogue-quality.ts` — Step 1 NPA v2 메트릭 추가 대상
- CLAUDE.md "LLM 설계 원칙" — Stateless / Negative→Positive / 풍선효과 / 사후 삭제 최후 수단

---

## 11. 결론

A50 실패의 핵심 교훈: "줄이기"가 아니라 "**signal 강화 + 측정**"이 정답일 수 있다.

본 v1은 A50의 모든 실수(큰 변경/A/B 비교 부재/객관 측정 부재)를 의도적으로 회피하고, 단일 단위 실험을 누적하는 점진 접근. **Step 1 NPA v2 메트릭 강화부터** — 객관 측정 없이는 다음 단계도 의미 없음.

총 작업량: ~13h (Step 1~6).
