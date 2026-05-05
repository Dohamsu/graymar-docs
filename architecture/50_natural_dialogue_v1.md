# 50. Natural Dialogue v1 — LLM 발화 로봇스러움 해소

> ⚠️ **STATUS: 폐기 — 시도 후 NPA 메트릭 후퇴로 전체 롤백 (2026-04-28)**
>
> **시도 결과 요약** (Phase 1+2+3 적용 → NPA 8 시나리오 검증):
> - 평균 종합: 3.29 → 3.01 (-0.28, 후퇴)
> - ERROR: 0 → 1~3건 (MARKER_NPCID_NULL "노점 상인" 등 익명 인물 회귀)
> - TopicFreedom: 3.31 → 2.31 (-1.0, 4-mode dispatch 약화 의심)
> - Humanity: 3.36 → 3.70 (+0.34, 의도된 향상)
>
> 부분 롤백(Phase 4b)도 ERROR 1→3으로 악화. **전체 롤백** 후 baseline 3.36 / ERROR 0 회복.
>
> **얻은 교훈**:
> 1. 프롬프트 압축 + 메타 지시 → 시스템 프롬프트 이동은 캐시되어 강도 약화 (CLAUDE.md "soft 지시 무시" 풍선효과 확인)
> 2. 익명 인물(NPC 아닌 행인) 마커 처리가 [NPC 등장] 블록 구조에 의존적
> 3. "자연스러움" ≠ NPA 점수 향상 — Humanity 향상 + TopicFreedom 손실로 상쇄
> 4. 측정 시스템(NPA)과 인간 직관 사이의 갭 존재 — v2에선 NPA 톤 측정 보강 필요
>
> **데이터 누적 보존 목적**으로 본 문서는 유지. 향후 v2 설계 시 참고.
>
> ---

> **목표**: 매 턴 LLM에 주입되는 "메타 지시"를 줄이고 "정보 제공"으로 전환해 NPC 발화의 자연성을 높인다. 모든 NPC가 동일한 "지령 수행" 패턴으로 출력되는 현상을 차단.
> **선행**: architecture/26 (3-Stage Pipeline) + 47 (NPA 검증) + 49 (NPC 결정 권한자).
> **검출**: NPA 8 시나리오 평균 종합 3.29. 사용자 보고: "마치 지령을 받은 듯 정해진 말만 한다."
> **작성**: 2026-04-28

---

## 1. 동기 — "지령받은 느낌"의 코드 진단

### 1.1 매 턴 LLM이 받는 프롬프트 (chat-rat-king T10 1239 토큰 sample)

10개 블록 + 12+ 메타 지시 동시 주입:

| # | 블록 | 핵심 패턴 |
|---|---|---|
| 1 | [상황 요약] | 행동 결과 한 줄 |
| 2 | [이번 턴 사건] | NPC 행동 boilerplate |
| 3 | [이번 턴 판정] | "자신감 있고 역동적" 톤 가이드 |
| 4 | ⚠️ [이번 턴 행동] | **"결과를 서술하세요. 첫 문장은 '당신은'으로 시작하지 마세요. 엔진 해석: PERSUADE"** |
| 5 | [현재 시간대] | "DUSK. 모순 단서 금지. 전환 시 '시간이 흘러' 사용" |
| 6 | [이번 턴 감각 초점] | **"시각 1~2개 포함하세요. 예시: 먼지가 빛줄기..."** |
| 7 | [이번 턴 플레이어 지목 대상] | "이 NPC가 반응 중심. 다른 NPC 가로채지 마세요" |
| 8 | [NPC 일상 화제] | **"쥐왕 평소 화제 (참고): '요새 새 얼굴들이...'"** + "강요 금지" |
| 9 | [NPC 등장] | "하를런 보스가 나타납니다. 자세 FRIENDLY. 대화 시드: 친근하게..." |
| 10 | [이번 턴 NPC 말투] | "쉰 목소리의 압도적... 빠른 말투 금지" + "⚠️ 이전 턴 다른 NPC 말투 적용 금지" |

### 1.2 5대 원인

**O1. 메타 지시 과다** — "~하세요/~지 마세요/⚠️" 12개+. LLM이 "자연 발화"보다 "지시 수행"을 우선시.

**O2. 화제 시드 직접 인용** — "참고: 요새 새 얼굴들이..." 텍스트를 LLM이 거의 그대로 따라 씀 → 모든 NPC가 비슷한 패턴.

**O3. 메타 정보 노출** — "엔진 해석: PERSUADE", "FALLBACK", "대화 시드" 같은 게임 내부 변수가 그대로 LLM에 전달.

**O4. 부정 지시 누적** — "강요 금지", "이전 턴 말투 적용 금지", "personality 직접 인용 금지" → LLM이 self-conscious해지며 톤 경직.

**O5. 시스템 프롬프트의 거대화** — NARRATIVE_SYSTEM_PROMPT 246줄 + 매 턴 user 메시지 1200토큰. 정상 NPC 발화에 비해 가이드가 압도적.

### 1.3 NPA 메트릭 증거

- AVOID_WORD_HEAVY: 모든 시나리오에서 WARNING (회피 어휘 30%+)
- LOW_USER_RESPONSE: 사용자 핵심어 응답률 평균 20% (사용자 단순 안부 → NPC 무거운 음모 답변)
- 종합 종합 점수 3.29 (★★★ 보통)
- Humanity score 평균 3.36 — Continuity/TopicFreedom보다 낮음

---

## 2. 핵심 원칙

### 2.1 Show, Don't Tell (메타 지시 → 정보 제공)

LLM에게 "감각 1~2개 포함하세요" 명령 대신 시스템 프롬프트의 **디폴트 룰**로 한 번만. 매 턴은 "이번 턴은 시각 중심" 같은 *정보*만.

### 2.2 Single Source of Truth (시스템 vs 매 턴 분리)

- **시스템 프롬프트(고정)**: 어체/시간일관/감각/금지어 같은 **항상 적용 규칙**
- **매 턴 메시지(동적)**: 이번 턴 입력/판정/NPC/이벤트 같은 **변하는 정보만**

### 2.3 Inspire, Don't Quote (영감 ≠ 직접 인용)

daily_topics text를 그대로 노출하면 LLM이 따라씀. 키워드/주제 영감만 주고 LLM이 자기 말로 풀어쓰게.

### 2.4 No Internal Variables Leaked

"엔진 해석", "FALLBACK", "대화 시드" 같은 메타 정보 제거 또는 자연어로 변환.

---

## 3. 작업 분류 (B 제외 결정 반영)

### A) 블록 압축 + 메타 지시 → 정보 제공 (가장 큰 효과)
### C) daily_topics 키워드화 (직접 인용 차단)
### D) 부정 지시 제거 + Positive framing
### E) personality 표현 강화 (콘텐츠 추가)

---

## 4. A — 블록 압축 + 메타 지시 정보 전환

### 4.1 변경 대상 블록 5개

| 블록 | 현재 | 개선 |
|---|---|---|
| [이번 턴 행동] | "결과를 서술하세요. 첫 문장은 '당신'으로 시작하지 마세요. 엔진 해석: PERSUADE" | "행동: {input}\n분류: {actionType}" (메타 지시 시스템 프롬프트로 이동) |
| [현재 시간대] | "DUSK. 모순 단서 금지. 전환 시 '시간이 흘러' 사용" 6줄 | "시간대: 황혼" 1줄 (모순 금지 시스템 프롬프트로) |
| [이번 턴 감각 초점] | "시각 1~2개 포함하세요. 예시: 먼지가 빛줄기..." 5줄 | 매 턴 미주입 — 시스템 프롬프트에 "감각 다양화" 일반 규칙으로 |
| [이번 턴 NPC 말투] | "쉰 목소리... 빠른 말투 금지 + ⚠️ 이전 턴 다른 NPC 말투 적용 금지" 4줄 | "{NPC} 말투: {speechStyle}" 1줄 (금지 규칙 시스템 프롬프트로) |
| [이번 턴 플레이어 지목 대상] | "이 NPC가 반응 중심. 다른 NPC 가로채지 마세요" 3줄 | "지목 NPC: {NPC}" 1줄 |

### 4.2 시스템 프롬프트 보강 (NARRATIVE_SYSTEM_PROMPT)

매 턴 반복되던 메타 지시를 시스템 프롬프트에 **한 번만** 추가:
```
## 자연 발화 원칙
- 사용자 입력 톤이 가벼우면 NPC도 가볍게 응답. 잡담을 음모 톤으로 끌어가지 마세요.
- 사용자가 단순 안부를 묻으면 NPC는 단순한 안부로 답하세요. fact를 갖다붙이지 마세요.
- "위험/조심하/곤란/입을 다물" 같은 회피 어휘는 회당 1회 이하.
- 사용자 입력의 핵심 명사 1개를 NPC 응답에 자연스럽게 반영하세요.
```

### 4.3 영향 범위

**파일**:
- `prompt-builder.service.ts` (2729줄, ~25 factsParts.push 중 5개 변경)
- `system-prompts.ts` NARRATIVE_SYSTEM_PROMPT (현재 246줄, +20~30줄)

**예상 토큰 변화**:
- 매 턴 user 메시지: 1239 → ~700 (44% 감소)
- 시스템 프롬프트: 246줄 → ~270줄 (10% 증가, but 캐시되어 1회만 비용)
- 총 LLM 호출 비용: ~30% 감소 (캐시 효과 + 매 턴 감소)

**회귀 위험**:
- 중간 — 매 턴 가이드 일부가 사라지면 LLM이 일부 규칙(예: "당신" 시작 금지) 잊을 수 있음
- 완화: 시스템 프롬프트에 명시적 이동 + NPA 시나리오로 회귀 검출

---

## 5. C — daily_topics 키워드화

### 5.1 현재 동작

`prompt-builder.service.ts:2117-2125`:
```ts
factsParts.push([
  `[NPC 일상 화제 — 자연 대화 풀]`,
  `${chatDisplayName}의 평소 화제 (참고): ${picked.text}`,
  `이 화제를 NPC 말투로 짧게 (1~3문장) 자연스럽게 녹이세요. 강요 금지.`,
  `※ 단서/사건/임무를 화두로 만들지 마세요. 이번 턴은 일상 대화입니다.`,
].join('\n'));
```

`picked.text`는 npcs.json의 `daily_topics[].text`. 예: "요새 새 얼굴들이 빈민가를 들락거리오. 누가 보내는지... 알아내야 할 것이오."

**문제**: NPC 말투로 작성된 *완성 문장*이라 LLM이 거의 그대로 인용.

### 5.2 변경

**옵션 A — 키워드만 노출 (즉시 적용 가능, 콘텐츠 변경 없음)**:
```ts
const keywords = (picked.keywords ?? []).slice(0, 3).join(', ');
factsParts.push([
  `[잡담 영감] ${chatDisplayName}: ${keywords || picked.category}`,
].join('\n'));
```
- npcs.json daily_topics에 이미 `keywords` 필드 있음 (대부분 NPC)
- 예: "쥐왕 일상: 새 얼굴, 외부인 출입, 정보망"

**옵션 B — 콘텐츠 변경 (장기)**:
- npcs.json daily_topics에 `keywords` 필드 강제 + `text` 제거
- 작업량 큼 (43 NPC × 평균 5 daily_topics)

### 5.3 영향 범위

- 코드 변경: prompt-builder.service.ts 1곳 (~10줄)
- 콘텐츠: 옵션 A는 변경 없음 (기존 keywords 활용)
- 회귀 위험: **낮음** — 잡담 모드만 영향. fact/handoff 분기에는 영향 없음
- NPA 영향: HumanityScore의 npcSignatureRate가 일시 하락 가능 (signature가 키워드 형태로 노출되므로). 그러나 실제 출력 다양성은 증가 예상

---

## 6. D — 부정 지시 제거 + Positive Framing

### 6.1 변경 대상

| 위치 | 현재 (부정 지시) | 개선 (positive) |
|---|---|---|
| [NPC 말투] | "⚠️ 이전 턴 다른 NPC 말투 적용 금지" | 시스템 프롬프트로 이동 (1회만) |
| [NPC 일상 화제] | "강요 금지" | 제거 (애매하고 효과 미미) |
| [NPC 등장] | "⚠️ NPC personality 설명을 직접 인용하지 마세요" | "행동·대사로 보여주세요" |
| [이번 턴 행동] | "행동 내용을 반복하거나 요약하지 말고" | "NPC 반응부터 시작하세요" (어차피 같은 의미, positive) |
| [이번 턴 행동] | "첫 문장은 '당신은/당신이'로 시작하지 마세요" | 시스템 프롬프트의 일반 규칙으로 (이미 있음 — 중복 제거) |

### 6.2 영향 범위

- 코드: prompt-builder.service.ts ~5곳 (각 1~3줄)
- 시스템 프롬프트: 보강 없음 (이미 동일 규칙 존재 — 중복 제거)
- 회귀 위험: **낮음** — 부정 지시 제거가 LLM 자유도 향상. 단, "당신" 시작 금지 같은 중요 규칙은 시스템 프롬프트에 명시 유지.

---

## 7. E — personality 표현 강화 (선택적)

### 7.1 daily_topics 다양화

- 현재 NPC당 평균 5개 → 8~10개로 확장
- 카테고리 다양화 (현재 WORK/PERSONAL/GOSSIP/OPINION/WORRY) → 추가 (HUMOR/REGRET/JOY/ANGER)

### 7.2 chat_tone vs serious_tone 분리

`personality.speechStyle` 외에 가벼운 잡담용 `personality.casualStyle` 추가:
```json
"personality": {
  "speechStyle": "쉰 목소리의 압도적이고 느린 경어. 문장을 끝맺지 않아 긴장감을 줌.",
  "casualStyle": "사적인 대화에선 짧고 시니컬한 농담을 던지기도 함. ~소 체는 유지."
}
```

prompt-builder가 mode에 따라 선택:
- A_FACT/B_HANDOFF/C_DEFAULT → speechStyle (무거운 톤)
- D_CHAT → casualStyle (가벼운 톤)

### 7.3 영향 범위

- 콘텐츠: npcs.json (43 NPC, 큰 작업)
- 코드: prompt-builder.service.ts mode별 분기 추가 (~10줄)
- 회귀 위험: **낮음** (콘텐츠 추가형)
- 작업량 큼 — 이번 v1에선 **미포함**, v2 이후로 분리

---

## 8. 비포함 (B 등)

### B) [NPC 등장] 빈도 제한 — **사용자 결정으로 제외**
- 이유: 콘텐츠 다양성 vs 단둘 대화 보호 trade-off, 잠금 외 시간엔 다른 NPC 자연 등장이 풍성함에 기여

### F) 시스템 프롬프트 전면 재구성 — 후속 v2
- 현재 246줄 가이드를 80~100줄로 압축할 수 있지만 회귀 위험 큼
- v1에선 추가/수정만, 전면 재구성은 별도 버전

---

## 9. 단계적 구현 계획

### Phase 1 — D 부정 지시 제거 (가장 안전, ~1h)
- prompt-builder.service.ts ~5곳 정리
- 회귀 가능성 가장 낮음

### Phase 2 — C daily_topics 키워드화 (~1.5h)
- 옵션 A 적용 (콘텐츠 변경 없음)
- 잡담 모드 출력만 영향

### Phase 3 — A 블록 압축 + 메타 지시 이동 (~3h)
- 시스템 프롬프트에 "자연 발화 원칙" 섹션 추가 (~30줄)
- 5개 블록 단순화
- 매 턴 user 메시지 1239 → ~700 토큰

### Phase 4 — NPA 검증 (~1h)
- 8 시나리오 재실행
- 메트릭 비교: 평균 종합, Humanity, AVOID_WORD_HEAVY, LOW_USER_RESPONSE
- 잔존 회귀 없으면 통과

### Phase 5 — 커밋·푸시

총 작업량 ~6.5h.

---

## 10. 회귀 위험 및 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| 시간대 모순 (예: 밤 햇살) | 중 | 시스템 프롬프트에 "현재 시간대 ${phase}" 단서만 매 턴 유지, 모순 금지 규칙은 시스템 프롬프트에 |
| "당신" 시작 회귀 | 작 | 시스템 프롬프트 §서술 문체에 이미 명시 |
| 감각 묘사 누락 | 작 | 시스템 프롬프트 §서술 원칙 §감각 어휘 다양화에 명시 |
| daily_topics signature 손실 | 중 | NpcSignatureRate 메트릭 모니터링. 5점 이하 떨어지면 "예시 1줄" 추가 |
| LLM 캐시 적중률 변화 | 작 | 시스템 프롬프트 안정 유지, 매 턴 동적 부분만 변화 |

---

## 11. 메트릭 목표

| 지표 | 베이스라인 | 목표 |
|---|---|---|
| 8 시나리오 평균 종합 | 3.29 | 3.6+ |
| Humanity score | 3.36 | 3.7+ |
| AVOID_WORD_HEAVY | 매 시나리오 WARN | ≤4 시나리오 WARN |
| LOW_USER_RESPONSE | 평균 25% | 50%+ |
| 매 턴 user 메시지 토큰 | 1239 | ~700 |
| ERROR | 0 | 0 (회귀 없음) |

---

## 12. Open Questions

### Q1. 시스템 프롬프트가 너무 길어지나?
NARRATIVE_SYSTEM_PROMPT 246줄 → ~270줄 예상. 캐시되어 비용 부담 X. 단 LLM이 모든 규칙을 동일 강도로 따르지 못하므로 핵심 규칙(어체/금지어/시간대)에 한정.

### Q2. NPC별 casualStyle 콘텐츠 작업?
v1에서 제외. 단 chat scenario에서 잡담 톤이 여전히 무겁다면 v2에서 우선.

### Q3. NPA의 잡담/심각 톤 분리 측정?
현재 NPA는 mode 분포만 측정. "잡담일 때 가볍게" 같은 톤 적합도 측정 필요. v2에서 추가 검토.

### Q4. 시스템 프롬프트 변경 시 모든 LLM 호출에 영향. 회귀 차단법?
- Phase 4 NPA 8 시나리오로 회귀 검출
- ERROR 발생 시 즉시 rollback
- 단계적(D → C → A) 적용으로 변경 격리

---

## 13. 관련 문서

- [[architecture/26_narrative_pipeline_v2|narrative pipeline v2]] — 3-Stage Pipeline (이 문서가 다루는 프롬프트 빌드의 토대)
- [[architecture/45_npc_free_dialogue|npc free dialogue]] — daily_topics 잡담 시스템 (C 변경 대상)
- [[architecture/47_dialogue_quality_audit|dialogue quality audit]] — NPA 검증 도구 (Phase 4)
- [[architecture/49_npc_resolver_authority|npc resolver authority]] — NPC 결정 단일 권한자
- `server/src/llm/prompts/prompt-builder.service.ts` — 변경 대상 (A/C/D 모두)
- `server/src/llm/prompts/system-prompts.ts` — 시스템 프롬프트 (A 보강 대상)
- CLAUDE.md "LLM 설계 원칙" — Negative보다 Positive, 풍선효과, soft 지시 무시
