# 25. LLM 모델 평가 보고서 — 9개 모델 종합 비교

> 2026년 4월 10일 실시한 LLM 모델 비교 평가 (v2).
> 그레이마르 텍스트 RPG 내러티브 생성에 최적인 모델을 선정.
> @마커 NPC 혼선은 파이프라인(NpcDialogueMarker) 이슈로 모든 모델 공통 발생 — 모델 평가에서 제외.
> v1 평가(Gemma 4 vs GPT-4.1-mini, 2026.4.5~6)는 본 문서 말미 부록 참조.
> **v3 평가(2026-07-22, DeepSeek V4 교차 채택 + 프로바이더 튜닝)는 부록 D — 현 운영 구성의 정본.**
> **v3.1(2026-07-22 당일 후속): 메인 31B 승격 확정 — 프로바이더 allowlist 전제. 부록 D-8.**
> **v5(2026-08-13): 교차 DeepSeek→gpt-5.6-luna 5:5 · Gemma allowlist 에서 ModelRun 제거(-80%) ·
> fallback 404 해소 · Gemini 후보 평가(보류). 부록 E — 현 운영 구성의 정본.**

## 1. 테스트 환경

- 서버: NestJS, OpenRouter 경유 (sort:latency, allow_fallbacks)
- 프롬프트: 실제 게임 프롬프트 (시스템 ~8K + 메모리/이벤트 ~3K + 유저 ~2K 토큰)
- 출력: 한국어 내러티브 서술 300~900자 (해라체, 중세 판타지 경어체 NPC 대사)
- 평가 기준: 초반 4턴 (컨텍스트 오염 전) 순수 모델 품질
- 동시접속: 2명 × 10턴 테스트 (모델별)
- 비용 환율: ₩1,500/USD 고정

### 평가 제외 항목 (파이프라인 이슈, 모델 무관)

| 항목 | 사유 |
|------|------|
| @마커 NPC 혼선 | NpcDialogueMarker 파이프라인 이슈 |
| 10턴 이후 반복 패턴 | locationSessionTurns 주입 파이프라인 이슈 |
| [MEMORY:] 태그 누출 | 후처리 필터링 이슈 |

---

## 2. 정량 비교 (10턴 × 2세션 실측)

| 모델 | OpenRouter ID | 평균 레이턴시 | 턴당 비용 | 평균 출력 토큰 |
|------|--------------|-------------|----------|-------------|
| Qwen3 235B A22B 2507 | `qwen/qwen3-235b-a22b-2507` | 14.0초 | ₩1.8 | 646 |
| Gemma 4 26B MoE | `google/gemma-4-26b-a4b-it` | 19.4초 | ₩2.1 | 460 |
| Gemini 2.5 Flash (reasoning off) | `google/gemini-2.5-flash` | 3.9초 | ₩4.7 | 362 |
| Qwen3 Next 80B A3B | `qwen/qwen3-next-80b-a3b-instruct` | 6.3초 | ₩2.7 | 654 |
| GPT-4.1 Mini | `openai/gpt-4.1-mini` | 7.6초 | ₩5.4 | 518 |
| Qwen3 32B | `qwen/qwen3-32b` | 28.2초 | ₩2.0 | 921 |
| Qwen3 30B A3B | `qwen/qwen3-30b-a3b` | 18.7초 | ₩3.3 | 951 |
| Gemini 2.5 Flash Lite | `google/gemini-2.5-flash-lite` | 5.4초 | ₩1.8 | 877 |
| Llama 4 Scout | `meta-llama/llama-4-scout` | 1.8초 | ₩1.5 | 300 |

### OpenRouter 가격표

| 모델 | Input $/M | Output $/M | 비고 |
|------|-----------|------------|------|
| Qwen3 235B A22B 2507 | $0.071 | $0.100 | MoE 22B active, non-thinking |
| Gemma 4 26B MoE | ~$0.10 | ~$0.40 | MoE 3.8B active |
| Gemini 2.5 Flash | $0.30 | $2.50 | reasoning.max_tokens=0 필수 |
| Qwen3 Next 80B A3B | $0.090 | $1.100 | MoE 3B active |
| GPT-4.1 Mini | $0.40 | $1.60 | |
| Qwen3 32B | $0.080 | $0.240 | 고정 파라미터 |
| Qwen3 30B A3B | $0.080 | $0.280 | MoE 3B active |
| Gemini 2.5 Flash Lite | $0.10 | $0.40 | thinking 없음 |
| Llama 4 Scout | $0.08 | $0.30 | MoE 17B active |

---

## 3. 품질 평가 (초반 4턴, @마커 제외)

평가 항목: **문체**(해라체 일관성) / **NPC 대사**(하오체, 캐릭터성) / **분위기**(감각 밀도) / **판정 반영**(SUCCESS/PARTIAL/FAIL 차별화) / **프리셋 반영**(배경 서술 반영도).

### 상위 모델 (4.0 이상)

#### Qwen3 235B A22B 2507 — 종합 4.6/5

| 문체 | NPC | 분위기 | 판정 | 프리셋 |
|-----|-----|-------|-----|-------|
| 5/5 | 5/5 | 5/5 | 4/5 | 4/5 |

샘플(T3 SUCCESS):
> "당신이 한 걸음 다가서자, 그의 시선이 순간 흔들리며 장부 위로 손을 빠르게 내리친다. 종이가 덜거리는 소리와 함께, 한 장이 살짝 비뚤어진다. 그 사이로 '공물 보고서 – 기밀'이라는 자필 제목이 스쳐간다."

- **강점**: 복수 NPC 동시 처리, 구체적 게임 단서 생성, 감각 묘사 밀도 최고.
- **약점**: 레이턴시 14초, 프롬프트 증가 시 20초+.

#### Gemma 4 26B MoE — 종합 4.4/5

| 문체 | NPC | 분위기 | 판정 | 프리셋 |
|-----|-----|-------|-----|-------|
| 5/5 | 5/5 | 4/5 | 4/5 | 5/5 |

샘플(T4 FAIL):
> "날카로운 눈매의 회계사가 그대의 움직임을 알아채고는 순간적으로 시선을 피한다. 그의 어깨가 움츠러들며, 무언가 숨기려는 듯 몸을 살짝 뒤로 뺀다."

- **강점**: 프리셋 반영 최고, 서술체 통일 완벽(849회 호출 혼용 0건), NPC 더듬기 표현("시-시세").
- **약점**: 레이턴시 19.4초로 가장 느린 축, 서술 길이 짧음(460자).

#### Gemini 2.5 Flash (reasoning off) — 종합 4.1/5

| 문체 | NPC | 분위기 | 판정 | 프리셋 |
|-----|-----|-------|-----|-------|
| 4/5 | 4/5 | 5/5 | 3/5 | 4/5 |

- **강점**: 레이턴시 3.9초로 고품질 모델 중 압도적 속도, 분위기 묘사 탁월(시각+후각).
- **약점**: 비용 ₩4.7/턴 (235B의 2.6배), SUCCESS/PARTIAL 판정 구분 약함.
- ⚠️ `reasoning: { max_tokens: 0 }` 설정 필수. 미설정 시 74~84초 스파이크 + 비용 급증.

### 중위 모델 (3.0~4.0)

| 모델 | 점수 | 레이턴시 | 비용 | 요약 |
|------|------|---------|------|------|
| Qwen3 Next 80B A3B | 3.8/5 | 6.3초 | ₩2.7 | 독창적 소재 생성력(코드/숫자), 활성 3B라 장기 컨텍스트 활용 약함 |
| GPT-4.1 Mini | 3.8/5 | 7.6초 | ₩5.4 | 안정적, 턴 간 소재 연결 우수, 비용 최고, 프리셋 반영 약함 |
| Qwen3 32B | 3.5/5 | 28.2초 | ₩2.0 | 분위기 양호, 속도 가장 느림, "카메라 소리" 세계관 이탈 사례 |
| Qwen3 30B A3B | 3.0/5 | 18.7초 | ₩3.3 | 기대 이하, 비용 대비 성능 아쉬움 |

### 하위 모델 (3.0 미만)

| 모델 | 점수 | 레이턴시 | 비용 | 요약 |
|------|------|---------|------|------|
| Gemini 2.5 Flash Lite | 2.4/5 | 5.4초 | ₩1.8 | 메타 서술 침투("플레이어가 X"), NPC 대사 복붙, 이전 기록 리터럴 인용 |
| Llama 4 Scout | 2.0/5 | 1.8초 | ₩1.5 | 한국어 어색, 서술 반복 심각, T3→T4 거의 동일 문장 복붙 |

---

## 4. 종합 순위

### 품질 순위

| 순위 | 모델 | 품질 | 속도 | 비용 |
|------|------|------|------|------|
| 1 | Qwen3 235B A22B 2507 | **4.6** | 14.0초 | ₩1.8 |
| 2 | Gemma 4 26B MoE | **4.4** | 19.4초 | ₩2.1 |
| 3 | Gemini 2.5 Flash (off) | **4.1** | 3.9초 | ₩4.7 |
| 4 | Qwen3 Next 80B A3B | **3.8** | 6.3초 | ₩2.7 |
| 5 | GPT-4.1 Mini | **3.8** | 7.6초 | ₩5.4 |
| 6 | Qwen3 32B | **3.5** | 28.2초 | ₩2.0 |
| 7 | Qwen3 30B A3B | **3.0** | 18.7초 | ₩3.3 |
| 8 | Gemini 2.5 Flash Lite | **2.4** | 5.4초 | ₩1.8 |
| 9 | Llama 4 Scout | **2.0** | 1.8초 | ₩1.5 |

---

## 5. 추천 조합

### 품질+비용 최적 (채택)

| 역할 | 모델 | 품질 | 속도 | 비용 |
|------|------|------|------|------|
| 메인 | Qwen3 235B A22B 2507 | 4.6 | 14초 | ₩1.8 |
| Fallback | GPT-4.1 Mini | 3.8 | 8초 | ₩5.4 |

### 속도 우선

| 역할 | 모델 | 품질 | 속도 | 비용 |
|------|------|------|------|------|
| 메인 | Gemini 2.5 Flash (off) | 4.1 | 3.9초 | ₩4.7 |
| Fallback | Flash Lite | 2.4 | 5.4초 | ₩1.8 |

### 균형

| 역할 | 모델 | 품질 | 속도 | 비용 |
|------|------|------|------|------|
| 메인 | Qwen3 235B A22B 2507 | 4.6 | 14초 | ₩1.8 |
| Fallback | Qwen3 Next 80B A3B | 3.8 | 6초 | ₩2.7 |

---

## 6. 기술 설정 참고

### Gemini 2.5 Flash thinking 비활성화

```typescript
reasoning: { max_tokens: 0 }  // 환경변수: GEMINI_REASONING_MAX_TOKENS=0
```

미설정 시 74~84초 레이턴시 스파이크 + output 비용 급증.

### 서버 환경변수 예시 (Qwen3 235B 메인)

```env
LLM_PROVIDER=openai
OPENAI_MODEL=qwen/qwen3-235b-a22b-2507
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_FALLBACK_PROVIDER=openai
LLM_FALLBACK_MODEL=openai/gpt-4.1-mini
```

---

## 7. 파이프라인 개선 과제 (모델과 무관)

| 과제 | 설명 | 우선순위 |
|------|------|---------|
| @마커 NPC 혼선 | NpcDialogueMarker 귀속 로직 강화 | P0 |
| 10턴 반복 패턴 | locationSessionTurns 서술 전체 대신 요약 전달 | P1 |
| [MEMORY:] 태그 누출 | 후처리 필터링 추가 | P1 |
| SUCCESS/PARTIAL 차별화 | 시스템 프롬프트에 판정별 서술 가이드 추가 | P2 |
| 메타 서술 금지 | "이전 턴에 X를 완수했다" 패턴 프롬프트에서 금지 | P2 |

---

## 부록 A. v1 평가 (구판, 2026.4.5~6)

v1은 **gpt-4.1-mini vs Gemma 4 계열** 4개 모델(E4B 로컬, 31B Gemini API, 26B MoE Gemini API, 26B MoE OpenRouter) 비교. 당시 결론:

- **채택**: Gemma 4 26B MoE via OpenRouter (9.0/10)
- 기존 gpt-4.1-mini(7.8/10) 대비 품질 +1.2, 속도 2.5배↑(7.6초 → ~3초), 비용 71%↓(₩3.24 → ₩0.95/턴)
- 탈락: E4B 로컬(한국어 경어체·태그 미준수), 31B Gemini(thinking 40초+), 26B MoE Gemini API(rate limit 분당 16K로 실서비스 불가)
- 핵심 강점: 서술체 통일 완벽(합니다체 혼용 0건), 프리셋 반영 매 턴, NPC 더듬기 표현

v2에서 Qwen3 235B가 품질/비용 모두에서 Gemma 4 26B MoE를 앞서면서 메인 모델이 교체됨. Gemma 4는 여전히 상위 2위로 유효한 선택.

## 부록 A-1. 운영 모델 변천 — Gemma 4 복귀 (2026.5)

v2 평가 결론(Qwen3 235B 메인)이 채택된 후, 운영 환경에서 Gemini 2.5 Flash Lite → Flash 로 차례 전환됐다가 **현재 Gemma 4 26B MoE 로 복귀**한 상태이다. 실제 운영값은 다음과 같다.

| 시점 | 메인 | Fallback | 사유 |
|---|---|---|---|
| v1 (2026.4) | Gemma 4 26B MoE | Claude Haiku 4.5 | 한국어 품질 + 가격 |
| v2 (2026.4) | Qwen3 235B A22B 2507 | GPT-4.1 Mini | 정량 평가 1위 |
| Flash Lite 전환 | Gemini 2.5 Flash Lite | GPT-4.1 Mini | 속도 2.7배 (Qwen 14초 → 5.4초) |
| Flash 전환 | Gemini 2.5 Flash | GPT-4.1 Mini | Flash Lite 메타서술/영어 누출 해소 |
| Gemma 복귀 (2026.5) | Gemma 4 26B MoE | GPT-4.1 Mini | 한국어 서술 일관성 + 안정성 |
| v3 교차 (2026.7) | Gemma 4 26B MoE + DeepSeek V4 Flash 교차 | GPT-4.1 Mini | v3 평가 — 어휘 편향 상쇄 교차 채택 (부록 D) |
| v3.1 (2026.7) | Gemma 4 31B dense + DS 교차, 31B allowlist ModelRun\|Friendli | GPT-4.1 Mini | 31B 승격 (풀 불안정은 allowlist로 해소, cerebras는 8배 단가로 미포함 — 부록 D-8) |
| **현재 (2026-08-03)** | **Gemma 4 31B dense + DS Flash 0731 교차 (3:7)** | **GPT-4.1 Mini** | v4 — 교차 모델만 0731 스냅샷 교체 (어미 준수 56.7→79.3% A/B 실측 — 부록 D-9) |

`server/.env` 정본:

```bash
LLM_PROVIDER=openai
OPENAI_MODEL=google/gemma-4-31b-it
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_FALLBACK_MODEL=openai/gpt-4.1-mini
LLM_ALTERNATE_MODEL=deepseek/deepseek-v4-flash-0731  # 교차 (v3 부록 D, 0731 스냅샷은 부록 D-9)
LLM_SHORT_RESPONSE_MIN_TOKENS=150                # 교차 이중 과금 방지 (부록 D §4)
LLM_PROVIDER_REQUIRE_PARAMS=true                 # penalty 레버 보장 (부록 D §5)
LLM_PROVIDER_IGNORE=cloudflare,dekallm           # 저 uptime 배제 (arch/62)
LLM_PROVIDER_ONLY_MAP=google/gemma-4-31b-it=ModelRun|Friendli  # 모델별 allowlist (부록 D-8)
```

> v2 표(부록 A 상단)는 평가 시점의 정량 데이터로 참고용. 운영 의사결정은 정량 점수 외에 한국어 자연스러움 / 톤 일관성 / 비용 안정성 / OpenRouter 게이트웨이 안정성을 종합 판단해 Gemma 4 로 복귀했다.

## 부록 B. 가격 출처

- OpenRouter 각 모델 가격 페이지 (2026.4 기준)
- OpenAI API 가격: https://openai.com/api/pricing/
- 환율: ₩1,500/USD (고정)

## 부록 C. 테스트 Run ID

| 모델 | User1 Run ID | User2 Run ID |
|------|-------------|-------------|
| Qwen3 235B | ce6bd62b-daf4-4d93-9537-1a198446dad0 | d32fb115-a020-4721-a8e7-1355b085d4fd |
| Qwen3 Next 80B | ad01afe2-2e3d-415e-a860-4358bc6aac8f | 5115aaa0-ee8f-4d25-89c2-6e6337a0a933 |
| Gemini Flash (off) | ff5dcf41-649a-4c62-8954-0312c93c1c2e | c45d7411-2a24-485a-bef4-2618dd39f4ef |
| Flash Lite | fe8e2e98-6e46-4fdd-83f8-d13ab07d63ae | e7ef7ed8-6c4d-47d3-97cf-6d1f256f3606 |
| Gemma 4 (5턴 비교) | bebed203-2720-4af4-a607-e073cfa55219 | — |
| GPT-4.1 Mini (5턴 비교) | 1d7d836e-81fe-4b6a-940e-002b599f6dbc | — |

---

## 부록 D. v3 평가 — DeepSeek V4 교차 채택 + 프로바이더 튜닝 (2026-07-22)

> 2026.4 평가 이후 신규 모델 재검토. 12턴 × 단일 세션, DESERTER, graymar_v1,
> `scripts/playtest.py` 게이트 10종 + `llm_call_logs` 실과금 기준 (환율 ₩1,500/USD).
> **결론: 메인 Gemma 26B 유지 + `LLM_ALTERNATE_MODEL`(짝수 턴)에 DeepSeek V4 Flash 투입.**

### D-1. 후보 스크리닝

OpenRouter 2026.4~6 신규 모델 중 가격 밴드(현행 ~₩1.5/턴) 내 후보를 선별:

- **테스트 진행**: DeepSeek V4 Flash($0.094/$0.188, 롤플레이 컬렉션 사용량 1위), Gemma 4 31B dense($0.10/$0.35), DeepSeek V4 Pro($0.435/$0.870 — 가풍 판별용 1런)
- **서류 탈락**: Qwen3.6 27B($0.289/$2.40 밴드 초과), Qwen3.5-35B-A3B(active 3B — Next 80B A3B의 장기 컨텍스트 약점 전례), MiniMax M3(output 고가), Xiaomi MiMo-V2.5(한국어 미문서화), Qwen3 235B 재채택(output $0.10→$0.55 인상 + 레이턴시 전례), EXAONE·HyperCLOVA(OpenRouter 미제공)

### D-2. 정량 비교 (서술 호출 실측, 12턴 지시 = 호출 14~16회)

| | Gemma 26B ①/② | Gemma 31B | DS Flash | DS Pro |
|---|---|---|---|---|
| 평균 레이턴시 | 9.3 / 8.6초 | 6.2초 | **4.0초** | 8.1초 |
| 최악 턴 | 15.8 / 16.9초 | 15.0초 | **6.0초** | 14.7초 |
| 턴당 실과금 | ₩1.45 / 1.48 | ₩3.72 | **₩0.87** | **₩22.09** |
| 평균 출력 tok | 266 / 257 | 245 | 300 | 390 |
| 과거형 혼용률 | 0% / 0% | 0% | 11% | 8% |
| 대명사 개시어율 | 22.0% / 18.3% | — | 20.2% | **5.3%** |

- 26B 2런의 유사 수치(레이턴시·비용)로 런 간 분산 소폭 확인 — 모델 간 차이는 유의미.
- **31B 탈락**: 품질 동급(판정 반영 우수)이나 실과금 2.6배. **Pro 탈락**: 대명사·서술 밀도 최고지만 실과금 15배.
- **표시가 ≠ 실과금**: `sort:throughput`이 고가 프로바이더를 잡으면 표시가의 3~4배 과금 (31B ₩6~9 턴, Pro 4배). 이후 모델 검토는 반드시 `llm_call_logs.cost_usd` 실측 기준.

### D-3. DeepSeek 가풍 (Flash·Pro 공통 — 크기 무관 확정)

1. **서술 과거형 혼용 8~11%** (Gemma 0%). soft 지시로 교정 낙관 불가.
2. **별칭 어휘 본문 혼입**: "일곱 상냥한 서빙꾼 차이가 나더군"(Flash), 자기소개 이름 자리 별칭 침투(Pro). 별칭 마커 시스템과 상성 주의.
3. **세계관 아나크로니즘**: 계산기·손목시계 (교차 런 짝수 턴 2건/7턴). audit_quality.py 금지어 사전 밖 — 자동 감지 불가 (소유자 수용 판단, 2026-07-22).
4. **기본 reasoning 활성**: 미차단 시 reasoning이 maxTokens를 소진해 content 0자 (1차 런 11/15턴 빈 서술 실측) → `reasoning: { enabled: false }` 주입으로 해소 (server a1a81af).

강점: 게임 단서 생성력·턴 간 소재 연속성 최고 (순찰표 교대 공백, 장부 필체 위조 아크 등 — v2의 Qwen3 235B 강점 계열), 전 턴 6초 이하 유일.

### D-4. 교차(alternate) 채택 검증

`LLM_ALTERNATE_MODEL=deepseek/deepseek-v4-flash` (짝수 턴) 2런 실측:

- **인접 턴 자카드 0.000** (순수 런 0.001~0.004) — 연속 턴이 항상 다른 모델이라 인접 반복이 구조적으로 소멸. 교차 취지(어휘 편향 상쇄) 지표 실증.
- 3-gram 총량은 0.009로 상승하나 출처 추적 결과 동일 모델 2턴 간격 자기반복 (크로스 오염 1건 — 시간대 전환 상용구뿐).
- **모델 경계 대화 인계 4/4 성공**: 같은 NPC·같은 어체(하오체)·같은 조사 아크가 GM↔DS를 넘나들며 7턴 지속. 문체 오염 전파 없음 (GM 턴 과거형 0% 유지).
- **ShortResponse 이중 과금**: 임계 200에서 DS 정상 짧은 서술(160~190tok)이 재시도에 걸려 2/7턴 2배 지불 → 임계 env 외부화(`LLM_SHORT_RESPONSE_MIN_TOKENS`, server 5bd5372) 후 150 설정으로 0회.

### D-5. OpenRouter 프로바이더 튜닝 실측

| 구성 | 결과 | 판정 |
|---|---|---|
| `require_parameters: true` 단독 | 10/10, 빈 서술 0, 전 턴 <7.2초 (DS 5.8/GM 3.6초) | ✅ **채택** |
| + `max_price: 0.10/0.35` | Gemma 풀 1곳으로 질식 → FAILED 턴 1, DS 18초 | ❌ (사용 시 0.15/0.45↑) |
| `order: DeepInfra` 우선 | DS 빈 스트림 3/7 — reasoning 지원 **선언≠실동작** | ❌ |

- **require 채택 근거**: DS Flash 프로바이더 19곳 중 4곳(GMICloud·Baidu·DigitalOcean·Alibaba)이 frequency_penalty 미지원 — 불변식 50의 반복 억제 레버가 라우팅 운에 따라 조용히 무력화되던 것을 차단.
- 프로바이더 간 동일 모델 가격 편차 최대 2.6배 — 런 간 비용 변동(₩0.87~1.68)의 원인.
- 캐시는 실재 (NextBit Gemma 폴백 턴에서 3.6k tok 적중 → 턴 비용 절반). 단 적중은 동일 프로바이더 연속 라우팅 전제라 throughput 랜덤 라우팅과 상성 나쁨 — 향후 과제.
- env 스위치 3종(`REQUIRE_PARAMS`/`MAX_PRICE`/`ORDER`)은 server 8866f70, 미설정 시 기존 동작.

### D-6. 파생 수정 (커밋)

| 커밋 | 내용 |
|---|---|
| server `a1a81af` | DeepSeek reasoning 비활성 주입 (Gemini 전용 분기 확장) |
| server `5bd5372` | ShortResponse 임계 env 외부화 |
| server `8866f70` | 프로바이더 튜닝 env 3종 + require 채택 |
| docs `132fdf3` | playtest `--model` 전환을 auth 이후로 이동 — JWT 가드 도입 후 401 조용한 실패로 무동작이던 버그 (1차 "DeepSeek 런"이 실제로는 Gemma로 돌았음) |

### D-7. v3 테스트 Run ID (12턴 단일 세션)

| 구성 | Run ID |
|---|---|
| Gemma 26B ① (기준) | 05b32518-f09f-49fb-9e40-5a2c92fa6a24 |
| Gemma 26B ② (대조 — --model 버그로 전환 실패한 런) | 36bd5b3b-f80b-4439-b2ce-09fa46319226 |
| Gemma 31B | 3928d1c2-4fac-4cd3-9343-55174225c5fe |
| DS Flash (reasoning 미차단 — 무효) | 13cb3b69-7c75-4d59-bb14-c48809c93aaa |
| DS Flash (정상) | 27c79abf-d746-4661-8aa6-437bc89b3d64 |
| DS Pro | afa2f4c2-aa40-4287-8a55-55cd9da5a8ea |
| 교차 1차 (임계 200) | f3d8c108-66c2-4df4-84e3-2650360ac7f5 |
| 교차 2차 (임계 150) | 4e307f8a-6061-4c24-bdd0-8a9923485708 |
| 튜닝 A+B (require+상한) | 7d0931fb-d11f-4195-9756-003f02a65b31 |
| 튜닝 C (DeepInfra 우선) | 2c48736c-9b8b-4695-a1cb-803fe3cccfac |
| 튜닝 require 단독 (채택 구성) | d0a0abfa-eb91-44e1-bbfe-2edd2229cc01 |

### D-8. v3.1 — 메인 31B 승격 (allowlist 전제, 2026-07-22 당일 후속)

v3에서 비용(실과금 2.6배)으로 탈락시켰던 31B를 당일 재검토해 **승격 확정**.
단 검증 런 2회 연속 프로바이더 풀 불안정(빈 서술)을 겪어 **모델별 프로바이더
allowlist(`LLM_PROVIDER_ONLY_MAP`) 구현이 전제조건**이 된 경위 포함:

1. **31B 교차 재검증** (26B 자리에 31B, DS 교차 유지): 9/10 PASS, 위화감 노트 0.
   정성 우위 실측 — 장거리 화제 회수(T4 임금 단서 → T15 타 장소 쪽지 재소환), 관찰자 인물
   복선 유지(T5→T7 외형 일관 재등장), 판정 층위 구분(SUCCESS 구체 발견 vs PARTIAL 부분 개방),
   어체·마커·사례금 금액 정합 무결점. 텍스트 결함은 사실상 전부 DS 짝수 턴 귀속
   (어체 혼용·볼드 라벨 누출·별칭 조사 파손 — 모델 무관 후처리 사각 2건 별도).
2. **비용 원인 규명**: 31B 고비용의 주범은 표시가가 아니라 `sort:throughput`의 **Cerebras
   라우팅**($0.99/$1.49 per M — 기본가 8배, 최속 1.3초). 적중률 런별 12~75% 변동.
   배제 시 호출당 $0.0019 수준(26B의 2.0배) — 단 비-cerebras 지연 꼬리 20.2초 1회 실측.
3. **3모델 실험 (DS 고정 + 26B/31B 홀수 교대)**: 패턴 정확 작동, 같은 모델 자기반복
   자카드 0.0597→0.0474~0.0502 소폭 개선. 그러나 **26B↔31B 가족 상관 1.76배 실증**
   (어휘 자카드 0.0618 vs Gemma↔DS 0.0351) — "3모델 ≠ 3문체". 인접 다양성은 2-way로
   이미 달성(핵심 이득 잔여분 미미), 비용 +49~110%·운영 복잡도 대비 실익 부족으로 **기각**.
   코드는 `LLM_MAIN_ALTERNATE_MODEL` env 게이트로 잔존(미설정 시 무동작) — 향후 실험 자산.
4. **승격 검증 실패 — 프로바이더 풀 불안정 (보류 사유)**: 승격 후 검증 런 2회 모두
   빈 서술 발생. ① cerebras 배제 런: 빈 서술 3턴(15,020ms 동일 타임아웃·0토큰) +
   raw JSON 프리픽스 누출 1턴(ModelRun) + 69.7초 재시도 1턴(WandB). ② cerebras 허용
   재검증 런: 더 악화 — **31B 8턴 중 5턴 0토큰**(15초 타임아웃 4 + Together 13초 1),
   Chutes 31.6초, Cerebras는 아예 미선택. 결론: cerebras 설정과 무관하게 **31B
   프로바이더 풀이 시간대별로 불안정** — 나쁜 꼬리(WandB·Venice·Chutes·Together)로
   밀리면 빈 서술. 정상 실적 프로바이더는 Cerebras(6콜 avg 1.6s)·ModelRun(7콜 3.5s,
   JSON 누출 1회)·Friendli(10콜 6.1s)·SambaNova(8콜, penalty 미지원이라 현 설정 배제).
5. **allowlist 구현·확정 (해소)**: `LLM_PROVIDER_ONLY_MAP` env 신설
   (openai.provider.ts `buildOpenRouterParams` — 형식 `modelId=ProvA|ProvB;...`,
   해당 모델 호출에만 `provider.only` 적용 → DS·nano 라우팅 무영향).
   확정 리스트 **ModelRun|Friendli** — 소유자 결정으로 Cerebras 제외
   ("8배 단가면 상위 모델을 쓰는 게 낫다"). 최종 검증 런: 31B 8턴 전원
   ModelRun(2)/Friendli(6) 라우팅, **빈 서술 0**, 레이턴시 1.9~8.0초(전 턴 <10초),
   턴당 실과금 $0.00106(≈₩1.6 — Cerebras 스파이크 소멸), 인접 자카드 0.000,
   9/10 PASS (V8 1건은 마커 귀속 정확·산문 모순성 FP 판정).

| 구성 | Run ID |
|---|---|
| 31B 교차 재검증 — 정상 (12턴 chatty) | 8a9c794b-b170-48a0-97bd-44436fa16b5e |
| 3모델 실험 (13턴 chatty) | 30d2d041-292a-494d-96ba-633f110fa281 |
| 승격 검증 1차 — cerebras 배제, 빈 서술 3턴 (12턴 chatty) | 01d79acc-5225-47ae-b284-77e7631d5a96 |
| 승격 검증 2차 — cerebras 허용, 빈 서술 5턴 (12턴 chatty) | 71637853-41c2-4d73-a811-45e770285555 |
| **확정 — allowlist ModelRun\|Friendli, 빈 서술 0 (12턴 chatty)** | **0e6cc9ec-285d-492b-99fd-cc2b0b9933ed** |

**후속(백로그)**: ① ~~빈 서술 DONE 경로 수리~~ **완료 (server ccadb18)** —
0토큰·공백 응답 3층 방어: caller `ensureNonEmpty` throw(재시도·fallback 체인 활용) +
`generateStream` 빈 스트림 throw(non-stream 전환) + 워커 최종 게이트(FAILED 커밋으로
retry-llm 보존). 유닛 5케이스 + 실런 스모크(빈 서술 0) 검증.
② ~~playtest 빈 서술 센서 추가~~ **완료 (docs — playtest.py V11)** — 빈 서술(DONE)·
서술 선두 raw JSON 1건이라도 FAIL, FAILED/TIMEOUT은 카운트만(방어 작동 = 게이트 비대상).
결함 런 2종 FAIL·정상 런 2종 PASS 오프라인 검증 + 라이브 11/11 편입. **센서 첫 검증에서
기존 리뷰가 놓친 실결함 발굴**: 확정 검증 런(0e6cc9ec) T5가 `{"content": "..."}` JSON
봉투 노출 — ModelRun의 JSON 형식 누출 2회째(01d79acc T5 프리픽스 + 0e6cc9ec 봉투).
③ ~~allowlist 운영 관찰·ModelRun 거취~~ **완결 (server 2e3b646, 2026-07-22)** —
ⓐ JSON 형태 구제 가드: `salvageNarrativeShape`(봉투 언랩·프리픽스 제거·불가 시
재시도 체인) — caller는 narrative 스테이지+비JSON모드 한정(nano 정당 JSON 오폭 방지),
워커 게이트가 스트리밍 경로 커버. ModelRun은 가드 전제로 **유지**.
ⓑ 제3 후보 스모크: Novita 14.6~16.3s / Parasail 14.5~25.1s (형식·한국어 정상,
평시 투입엔 저속) → **Novita를 가용성 백스톱으로 3순위 추가**
(`ModelRun|Friendli|Novita` — throughput 정렬상 평시 미선택, 동시 저하 시
FAILED 대신 15초 턴). ⓒ 채택 후 실과금 4런 누적 턴당 $0.001046(≈₩1.57) 안정.
잔여 감시는 상시 수단(V11 게이트 + FAILED 카운트)으로 이관.
④ Solar Pro 3는 penalty 미지원+지시 준수 불안정으로 후보 제외.

### D-9. v4 — 교차 모델 0731 스냅샷 교체 (2026-08-03)

DeepSeek이 2026-07-31 V4 Flash를 프리뷰에서 정식판 `deepseek-v4-flash-0731`로
승격(동일 284B MoE/13B 활성 아키텍처, **재사후학습(re-post-training)만** 적용).
OpenRouter에 별도 슬러그로 등재되어 기존 `deepseek/deepseek-v4-flash`는 4월
가중치에 고정된 상태였다 — 즉 우리는 AA Intelligence Index 기준 10점 낮은
구 스냅샷을 교차로 쓰고 있었다. A/B 실측 후 **교차 모델만 0731로 교체 확정**.

#### 스냅샷 비교 (OpenRouter API + 외부 벤치, 2026-08-03 조회)

| 항목 | 구판 `deepseek-v4-flash` (2026-04-24) | 신판 `-0731` (2026-07-31) |
|---|---|---|
| 가격 ($/1M in/out) | 0.14 / 0.28 | 동일 (DeepInfra 0.09/0.18) |
| AA Intelligence Index | ~40 (비추론 ~29 — 우리 사용 모드) | 50 (V4 Pro보다 6점 위) |
| DeepSWE / Terminal Bench 2.1 | 7.3 / 61.8 | 54.4 / 82.7 (벤더 발표) |
| 프로바이더 수 | 21곳 | 11곳 (본가·Cloudflare·Novita 99.9%+) |

`~deepseek-v4-flash-latest` 별칭(항상 최신 리다이렉트)은 **금지** — 어체 검증
없이 미래 스냅샷으로 무통보 교체되는 구조라 서술 모델로 부적합. 고정 슬러그 정본.

#### A/B 방법 (2026-08-03)

env `LLM_ALTERNATE_MODEL`만 0731로 교체 후 ① 15턴 플레이테스트 1회(0731 발화
6턴) ② NPA 감사 chat-edric(0731 발화 3턴). 어미 준수율은 NPA 정본 분류기
(`scripts/e2e/audit/dialogue-quality.ts` REGISTER_PATTERNS)를 최종 저장 서술에
적용, 별칭 화자(unknownAlias/shortAlias)까지 npcs.json speechRegister로 귀속.
대조군은 같은 지표로 **과거 14일 실데이터**(구판 693문장 / Gemma 958문장)를 측정.

#### 결과

| 지표 | 구판 (14일 실측) | 0731 (A/B) | Gemma 31B (참조) |
|---|---|---|---|
| 어미 일치율 | 56.7% (393/693) | **79.3% (23/29)** | 83.5~88.6% |
| narrative 레이턴시 avg/p50 | 6.2s / 5.5s (553건) | 8.4s / 8.3s (9건) | 3.1s / 2.9s (당일) |
| 평균 출력 토큰 | 336 | 396 | 260 |
| 호출당 비용 | $0.00114 | $0.00104 | $0.00116 |

- 구판 위반 43.3%는 arch/95 실측(잔존 위반 39.7%)과 정합 — 지표 타당성 교차 확인.
- **어미 열세(교차 축소 5:5→3:7의 원인)가 대폭 완화**되어 Gemma에 근접. 표본
  29문장은 소표본이므로 다음 정기 NPA에서 재확인 시 arch/95 잔존 이슈 종결 가능.
- 품질 게이트 회귀 없음: 플레이테스트 12/13 PASS(V12 프롬프트 재비대 경보는
  모델 무관 기존 이슈), NPA 종합 4.59/5(톤일치 5.0, ERROR 0).
- **관찰 항목**: 0731 레이턴시 avg +2.2s(출력 +18% 영향 포함, n=9). 누적 후
  `llm_call_logs` p95가 10초 전제를 위협하면 재평가.

| 구성 | Run ID |
|---|---|
| 15턴 플레이테스트 (0731 교차 6턴, 12/13 PASS) | a513bee7-f28c-45b8-b25f-4950f5e1263a |
| NPA chat-edric (0731 3턴, 종합 4.59) | 74403cc9-cfbf-4477-b749-0f31a392baef |

반영: `server/.env` `LLM_ALTERNATE_MODEL=deepseek/deepseek-v4-flash-0731` +
CLAUDE.md(Tech Stack·env 예시) 동기화. 서버 코드 변경 없음(env만). 메인 31B·
fallback·nano 라인은 불변.

---

## 부록 E. v5 — 교차 모델 Luna 전환 + Gemini 후보 평가 (2026-08-13)

> **현 운영 구성의 정본.** 메인 `google/gemma-4-31b-it`(allowlist 교체) +
> 교차 `openai/gpt-5.6-luna` 5:5 + fallback `openai/gpt-4.1-mini`(부활) + nano `gpt-4.1-nano`.

### E-0. 요약

| 항목 | 이전 | 이후 |
|---|---|---|
| 교차 모델 | deepseek-v4-flash-0731 (3:7) | **gpt-5.6-luna (5:5, 짝수 턴)** |
| Gemma allowlist | ModelRun\|Friendli\|Novita | **Friendli\|Venice\|Novita\|CoreWeave** |
| fallback | gpt-4.1-mini (**전 기간 0건 = 사망**) | gpt-4.1-mini (**부활**) |
| LLM_MAX_TOKENS | 1024 | 2048 (절단 보험) |

### E-1. 왜 DeepSeek 을 뺐나 — 화자 귀속 붕괴

30일 실측(`llm_model_used` 귀속 · 서버 정본 `llm_speech_audit`):

| 모델 | 턴 | 대사 | 마커 커버리지 | 어체 위반율 |
|---|---:|---:|---:|---:|
| gemma-4-31b-it | 1,321 | 1,545 | **99.6%** | 14.6% (1,483발화) |
| gpt-5.6-luna | 44 | 47 | **100%** | **6.4%** (47발화) |
| deepseek-0731 | 287 | 528 | 77.5% | 45.9% |
| deepseek-v4-flash | 552 | 946 | 74.8% | 43.0% |

무마커 대사는 초상화·화자 표시가 **둘 다** 실패해 "누가 말했는지 모르는 대사"가
된다. 실측 런(e3e19e2c) T15 에서 그것이 하필 **최대 정보 공개 장면**에 걸려
장부 행방·항만청·직원 통로를 넘기는 핵심 대사 4개가 연속으로 화자 없이 출력됐다.

5:5 복원 근거: 3:7 축소(2026-07-28, D-9 선행)의 사유가 DeepSeek 어미 열세였으므로
모델 교체와 함께 소멸. Luna 는 오히려 메인(Gemma)보다 어체 준수가 낫다.

### E-2. Luna 운영 함정 3종 (코드로 방어 — `providers/model-capabilities.ts`)

1. **temperature·penalty 미지원** — GPT-5 계열은 샘플링 고정. 보내면 무시되거나
   `require_parameters` 와 겹쳐 404. `samplingParams()` 가 자동 제거.
2. **추론 기본 ON** (`default_enabled: true`, `default_effort: medium`). 추론
   토큰은 **출력 단가로 과금**되고 `max_tokens` 예산까지 먹는다. 실측: 복잡
   프롬프트 + `max` 에서 469~575토큰 → 1024 예산이면 매 턴 `finish=length`.
   `LLM_REASONING_EFFORT_MAP=...=none` + 코드 기본값 `none` 이중 방어.
3. **`reasoning medium` 은 품질을 낮춘다** — 아래 E-3.

### E-3. max_tokens × reasoning A/B (실 프롬프트 10건 재생)

| 설정 | ms p50 | ms p90 | 추론 | 본문 | 원/턴 | 대사수 |
|---|---:|---:|---:|---:|---:|---:|
| **1024:none** (구 운영) | 3,020 | 4,881 | 0 | 382자 | 0.35 | 8 |
| **2048:none** (채택) | 3,066 | 3,916 | 0 | 408자 | 0.36 | **10** |
| 1024:medium | 5,158 | 8,549 | 260 | 368자 | 0.58 | 7 |
| 2048:medium | 4,569 | 11,524 | 316 | 331자 | 0.61 | **4** |

`medium` 은 비용 +74% · p90 +136% 인데 라벨 준수·합쇼체·절단은 전 설정 동일(이득 0).
**오히려 대사가 절반 이하로 준다**(10→4) — 10 프롬프트 중 5개에서 NPC 대사가
줄거나 사라졌다. 대사 중심 RPG 에서 NPC 목소리를 빼는 건 손해다.

`max_tokens` 2048 은 **현재 실익 0**(30일 상한 도달: Gemma 0/max 744 · Luna 0/max
450 · DeepSeek 8/max 1025 ← 제거됨). 추론 활성화나 장황한 모델 도입 대비 보험.

### E-4. Gemma allowlist — ModelRun 제거 (실과금 -80%)

2026-08-13 00:00 UTC 부터 Gemma 서술의 69.5%가 ModelRun 으로 몰렸다(7-22~8-12 매일
0%였던 계단 변화 — 전일 비-ModelRun 레이턴시가 12,000ms 로 치솟자 `sort=throughput`
이 옮겨간 결과, 설정대로 동작).

문제는 단가다. **ModelRun 은 in $0.75/M — 전 19 엔드포인트 중 2위 고가**이고
**fp4(최저 정밀도)** 다. 정밀도가 낮은 쪽에 5배를 내고 있었다.

| 프로바이더 | 원/턴 | 레이턴시(3회) | quant | |
|---|---:|---|---|---|
| ModelRun | **8.89** | 1,783 / 2,056 / 2,133 | fp4 | 제거 |
| Friendli | 1.76 | 5,763 / 6,336 / 7,585 | unknown | 유지 |
| Venice | **1.51** | 6,404 / 6,532 / 7,280 | bf16 | 추가 |
| CoreWeave | 1.28 | 10,195 / 11,640 / 12,075 | bf16 | 추가(백스톱) |
| Novita | 1.76 | 9,243 / 9,427 / 11,474 | bf16 | 유지 |
| DeepInfra | 1.17~3.38 | 6,894~9,440 | fp4/fp8 ×3 | **제외** (엔드포인트 3개 = 가격 변동) |
| Chutes 49~76초 · Parasail 13~21초 · SiliconFlow 404 | | | | 제외 |

빈 서술은 9곳 전부 0건 — allowlist 를 만든 원래 사유(31B 풀 불안정)는 재현되지 않았다.
**선정 기준은 단일 엔드포인트**(프로바이더명 지정으로 가격이 흔들리지 않을 것).

결과: 6.94원 → **1.42원/턴**(-80%). 레이턴시는 1.6초 → 6.1초. 재악화 시 ModelRun
복귀가 아니라 **Venice 고정(order)** 을 먼저 검토한다.

### E-5. live P0 — fallback 층이 3주간 죽어 있었다

`LLM_PROVIDER_REQUIRE_PARAMS=true`(불변식 50 레버 보장용, 2026-07-22 D-5)가
**전역**이라, penalty 미지원 모델은 라우팅 가능 프로바이더가 0개가 되어 404 가 난다.

```
openai/gpt-4.1-mini + penalty + require_parameters=true → 404 (항상)
openai/gpt-4.1-mini + penalty, require 없음            → 200 (Azure)
```

`LLM_FALLBACK_MODEL` 이 `llm_call_logs` **전 기간 0건** — 재시도 체인의 마지막
층이 없는 채로 서술 실패가 그대로 유저에게 갔다(실패 31/2,026턴).

**해법**: `require_parameters` 를 전역 스위치가 아니라 **"penalty 를 실제로 보내는가"**
에서 파생. 못 받는 모델은 penalty 를 떼고 require 도 빼서 정상 라우팅한다.
메인 서술(Gemma)의 레버는 그대로 보장된다.

카탈로그 전수 판정 (`model-capabilities.ts`):

| 계열 | temperature | penalty |
|---|---|---|
| gpt-5* · o1~o9* | ✗ | ✗ |
| gpt-4.1* | ✓ | ✗ |
| **gemini-\*** (19종) | ✓ | **✗** |
| **gemma-\*** (7종) | ✓ | ✓ |
| 그 외 | ✓ (가정) | ✓ (가정) |

### E-6. Gemini 후보 평가 — 채택 보류

실 프롬프트 40건 재생 + 실런 10턴.

| 지표 | Gemma 31B | **gemini-3.1-flash-lite** | Luna |
|---|---:|---:|---:|
| 원/턴 | 1.72 | 2.26~3.82 | **1.03** |
| ms p50 / p90 | 4,662 / — | **2,696 / 3,666** | 3,696 / 19,524 |
| **라벨 준수(n=40)** | **100%** | **89.9%** | 98.6% |
| 대사 수 / 대사0건 턴 | 70 / 8 | **79 / 3** | 72 / 11 |
| 3-gram 반복률 | 0.031 | **0.018** | 0.017 |
| 본문 | 485자 | **562자** | 479자 |
| 게이트(coercer) | 12/14 | **13/14** | 13/14 |
| 모더레이션 | 없음 | **없음** | 있음 |

**강점**: 레이턴시 최고(p90 3,666ms) · 대사 최다 · 반복 최소(penalty 없이 Gemma 의
58%) · 서술 최장 · V9_quality 통과(Gemma 는 '그대' 8회로 실패).

**결격**: **라벨 준수 89.9%**. DeepSeek 을 뺀 바로 그 기준을 적용하면 동일 사유로
탈락한다. 비용도 1.3~2.2배.

`gemini-3-flash-preview`(in $0.50/out $3.00)는 **5.95~7.13원/턴**으로 논외 —
`3.1-flash-lite` 가 가격 절반·속도 1.8배다.

> ⚠️ 첫 gemini 실런은 **메인 턴 전부 404 → fallback 강등**(성공 0건)이었다.
> E-5 의 capability 표에 Gemini 규칙이 없어 penalty 가 나갔기 때문. 수정 후 재측정.
> 역설적으로 이 사고가 **부활한 fallback 의 실전 검증**이 됐다 — 메인 100% 실패에도
> 15턴 런이 완주했다.

### E-7. 화자 귀속 실패의 정체 (30일 363건 분류)

| 유형 | 건수 | 비중 |
|---|---:|---:|
| 기명 NPC 인데 라벨 누락 (소설 문법) | 171 | 47.1% |
| 익명 배경 인물 | 158 | 43.5% |
| 연속 대사 (직전 줄이 대사) | 32 | 8.8% |
| 서술 첫 줄 | 2 | 0.6% |

프로덕션 귀속 형태:

| 모델 | 실명마커 | 무명마커 | 콜론잔존 | 맨따옴표 | 실패율 |
|---|---:|---:|---:|---:|---:|
| gemma-4-31b | 1,488 | 26 | 34 | 6 | **0.4%** |
| gpt-5.6-luna | 69 | 0 | 0 | 0 | **0.0%** |
| gemini-3.1 | 11 | 1 | 0 | 2 | 14.3% |
| deepseek-0731 | 379 | 32 | 0 | 120 | 22.6% |
| deepseek-v4-flash | 666 | 41 | 1 | 237 | 25.1% |

**363건 중 357건(98%)이 DeepSeek 몫**이고 그것은 제거됐다. `@[무명 인물]` 경로가
이미 작동하므로(Gemma 26 · DeepSeek 73건) **익명 라벨 폐기로는 최대 43.5%만 해소**된다.
현행 라인업의 실패율이 0.4% / 0.0% 이므로 **추가 조치 불요** — 익명 규칙 정비는
Gemini 채택을 전제로만 의미가 있다.

모델별 회피 전략 차이(원인): 배경 인물이 말해야 하는 장면에서 P0-B(발화자 필수)·
P2-J(배경 NPC 대사 금지)·D(이름 창작 금지)를 **동시에 만족할 방법이 없다**.
Gemma 는 작은따옴표로 규칙 밖으로 빠지고(8건), Luna 는 미등록 라벨을 지어내며(10건),
gemini 는 큰따옴표+무라벨을 택한다(8건) — 우리 파이프라인이 가장 아파하는 선택.

### E-8. 검증 도구 결함 6종 (동시 수정)

이번 평가에서 **"결과는 나오는데 틀린"** 도구 결함이 6건 나왔다. 그대로 믿었으면
모델 선택을 오판했다.

1. **교차 모델 오귀속** — 런 단위 집계가 alternate 턴을 설정 모델 몫으로. Luna 가
   94.1%로 저평가됐다(실제 100%). → `llm_model_used` 귀속 필수
2. **`usage.cost` 캐시 순서 오염** — 첫 설정이 캐시 미스를 전부 떠안아 동일 설정이
   0.93원 / 0.36원. → 입력 동일 A/B 는 **분석 단가**가 정본
3. **포인트 프리플라이트 부재** — 두 번째 모델이 0턴인데 비교표 출력. 잔액 필드는 `points`
4. **모델 전환 403** — `PATCH /v1/settings/llm` 은 `@AdminEndpoint`. 복원 실패 시
   **프로덕션이 테스트 모델로 남는다**
5. **TTFT 사문화** — `type=='token'` 만 셌으나 분류기 기본 ON 이라 `narration`/`dialogue` 만 emit
6. **합성 프롬프트로는 추론량 측정 불가** — Luna 추론은 프롬프트 복잡도 비례
   (단순 `max`=50토큰 vs 실 프롬프트 469~575)

정본 도구: `scripts/llm-config-ab.py`(실 프롬프트 재생 A/B) ·
`scripts/bench-models.py`(실런 벤치) · `scripts/verify-bench-quality.py`(품질 채점).

### E-9. 반영 커밋

| 레포 | 커밋 | 내용 |
|---|---|---|
| server | `0156706` | model-capabilities 신설 · require_parameters 파생 · fallback 404 해소 |
| server | `c0ccc34` | 교차 DeepSeek→Luna · 3:7→5:5 |
| server | `6604f85` | feat/llm-luna-support → main 병합 |
| server | `f62ad69` | 조사 교정 필드 2→4 + 좌측 경계 가드 |
| server | `6fe823d` | capability 테이블 Gemini 규칙 추가 |
| docs | `9ce9607` | ModelRun 제거 |
| docs | `82cdcbf` · `94527c9` | 교차 전환 · A/B 도구 + max_tokens 2048 |
