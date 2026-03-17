# 플레이테스트 통합 보고서

**테스트 일시**: 2026-02-21
**테스트 방법**: API 직접 호출 (curl), LLM Provider: OpenAI gpt-4o-mini
**테스트 범위**: 2 runs × 5+ 턴, 프리셋 2종(SMUGGLER/DOCKWORKER), LOCATION 2종(항만/시장)

---

## 전체 점수

| 카테고리 | Run 1 (SMUGGLER) | Run 2 (DOCKWORKER) | 평균 |
|---------|:---:|:---:|:---:|
| 프롤로그 | 8 | 9 | **8.5** |
| IntentParser | 9 | 6 | **7.5** |
| 이벤트 매칭 | 5 | 6 | **5.5** |
| LLM 내러티브 | 7 | 7 | **7.0** |
| 판정 일관성 | 9 | 8 | **8.5** |
| 맥락 연속성 | 6 | 5 | **5.5** |
| 선택지 품질 | 7 | 7 | **7.0** |
| **종합** | **7.3** | **6.9** | **7.1** |

---

## 우선순위별 수정 필요사항

### P0 — 즉시 수정 (게임 경험 파괴)

#### 1. 이벤트 Display 반복
- **증상**: 같은 LOCATION에서 연속 행동 시 동일한 이벤트 텍스트 반복 표시.
- **영향**: 3턴 연속 "선원 서너 명이 도박을 벌이고 있다"가 표시되면 진행감 0.
- **수정 방안**:
  - `EventMatcher`에 cooldown 로직 추가: 직전 턴에 매칭된 이벤트는 2턴간 재매칭 방지.
  - 또는 같은 이벤트 재매칭 시 "후속 상태" 텍스트를 사용하는 variant 시스템.
- **파일**: `server/src/engine/hub/event-matcher.service.ts`

#### 2. LLM 생성 NPC 맥락 소실
- **증상**: Turn N에서 LLM이 "경비원" 등장 → Turn N+1에서 해당 NPC 증발, 다른 NPC로 교체.
- **영향**: 플레이어가 경비원에게 말을 거는데 상인이 응답 → 몰입 파괴.
- **수정 방안**:
  - 시스템 프롬프트에 "서버가 제공한 이벤트의 NPC만 사용. 새 NPC 등장 금지" 규칙 추가.
  - 또는 L3 locationSessionTurns에 이전 LLM narrative 포함 시, LLM이 자체 생성한 NPC를 추적하도록 프롬프트 보강.
- **파일**: `server/src/llm/prompts/system-prompts.ts`, `server/src/llm/context-builder.service.ts`

### P1 — 빠른 수정 (품질 저하)

#### 3. IntentParser PERSUADE 인식률 개선
- **증상**: "진정하시오", "설명하겠소", "권리가 있소" 등 설득 대사가 INVESTIGATE로 파싱.
- **수정 방안**: PERSUADE 키워드에 "진정", "설명", "해명", "변명", "권리", "이해해주", "납득" 등 추가.
- **파일**: `server/src/engine/hub/intent-parser-v2.service.ts`

#### 4. 세계관 파괴 단어 방지
- **증상**: "막걸리" 등 한국 고유 단어 사용.
- **수정 방안**: 시스템 프롬프트에 "서양 중세 판타지 세계관. 동양 고유 음식/물건 금지. 에일/미드/포도주 등 사용." 명시.
- **파일**: `server/src/llm/prompts/system-prompts.ts`

#### 5. LLM 내면 서술 위반
- **증상**: "당신은 ~할 필요를 느꼈다", "당신은 ~해야 할지 고민했다" 등 반복.
- **수정 방안**: 프롬프트에 "주인공의 내면(생각, 결심, 고민)을 서술하지 마세요. 행동/시선/표정/감각만 묘사하세요." 반복 강조 + few-shot 예시.
- **파일**: `server/src/llm/prompts/system-prompts.ts`

#### 6. NPC 말투 가이드 확대
- **증상**: 로넨 외 NPC의 말투가 경어/반말 혼재.
- **수정 방안**: "모든 NPC는 중세 판타지 경어체(~소/~오/~하오)를 기본으로 사용. 현대 반말 금지." 일반 규칙.
- **파일**: `server/src/llm/prompts/system-prompts.ts`

### P2 — 차후 개선 (부가 품질)

#### 7. 내러티브 후반 사족 제거
- **증상**: 거의 모든 턴 마지막이 "당신은 ~해야 할지를 고민하게 된다" 식.
- **수정**: "장면을 감각 묘사로 끝내세요. 결론/안내형 마무리 금지." 프롬프트.

#### 8. 여성 캐릭터 성별 반영
- **증상**: gender: female이지만 내러티브에 성별 반영 없음.
- **수정**: LLM context에 주인공 성별 정보 전달.

#### 9. FALLBACK 이벤트 텍스트 개선
- **증상**: "특별한 일은 일어나지 않지만" → 긴장감 저하.
- **수정**: FALLBACK 이벤트 텍스트를 LOCATION별로 더 흥미롭게 리라이팅.

#### 10. followup 선택지 구체화
- **증상**: "얻은 것을 활용해 다른 이에게 접근한다", "비슷한 기회가 더 없는지 살핀다" 등 generic.
- **수정**: followup 선택지에 직전 이벤트 맥락 반영. "선원들에게 더 물어본다" → "도박에서 진 선원에게 접근한다" 등.

---

## 시스템별 상세 평가

### IntentParserV2
- OBSERVE, INVESTIGATE, BRIBE, SNEAK, THREATEN 파싱은 대체로 정확 (5/6).
- PERSUADE 인식 취약: 설득 대사에 "확인", "조사" 키워드가 포함되면 INVESTIGATE로 우선 매칭.
- 복합 대사(도박 참여 + 정보 캐기)에서는 주 행동이 아닌 부수 행동으로 파싱되는 경우 있음.

### EventMatcher
- LOCATION별 이벤트 풀은 잘 작동 (항만: GAMBLE, 시장: CARGO 등).
- **핵심 문제**: 같은 이벤트 반복 매칭. cooldown이 없어서 3~4턴 연속 동일 이벤트.
- FALLBACK 이벤트가 플레이어의 구체적 행동을 "특별한 일 없음"으로 치환하는 것은 UX 악영향.

### ResolveService
- 판정 공식(1d6 + floor(stat/3) + baseMod)이 정상 작동.
- SMUGGLER의 EVA(7)로 SNEAK SUCCESS, SPEED(7)로 BRIBE SUCCESS — 캐릭터 특성 반영됨.
- DOCKWORKER의 INVESTIGATE PARTIAL — ATK(16) 특화인데 ACC(4)로 INVESTIGATE에 불리한 점이 결과에 반영됨.

### LLM Narrative
- 평균 600~700자, 지시 범위(400~700자)에 대체로 부합.
- 프롬프트 지시 준수율: ~70%. 내면 서술 금지, 세계관 일관성 등에서 위반 존재.
- 이전 턴 대화 반영: locationSessionTurns 덕분에 직전 대사를 참조하는 연속성은 작동.
- **최대 약점**: 서버 이벤트와 플레이어 행동이 괴리될 때, LLM이 양쪽을 억지로 연결하거나 NPC를 자체 생성하여 맥락 꼬임 유발.

### 선택지 시스템
- LOCATION 진입 시 이벤트 고유 선택지가 잘 생성됨 (항만: 도박 참여/관찰/속임수, 시장: 상자 확인/절취/감시).
- followup 선택지는 generic하여 반복감.
- go_hub 항상 포함 — 탈출 경로 보장 작동.

---

## 결론

서버 엔진(판정, 파싱, 전투)은 견고하게 작동하며, 캐릭터 스탯이 결과에 실질적 영향을 주는 점이 좋습니다. **가장 시급한 문제는 이벤트 반복과 LLM-서버 간 맥락 괴리**입니다. 이 두 문제가 해결되면 전반적 플레이 경험이 크게 향상될 것으로 예상됩니다.

개별 보고서:
- [Run 1: SMUGGLER 보고서](./run1_smuggler_report.md)
- [Run 2: DOCKWORKER 보고서](./run2_dockworker_report.md)
