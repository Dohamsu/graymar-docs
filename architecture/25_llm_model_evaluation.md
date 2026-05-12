# 25. LLM 모델 평가 보고서 — 9개 모델 종합 비교

> 2026년 4월 10일 실시한 LLM 모델 비교 평가 (v2).
> 그레이마르 텍스트 RPG 내러티브 생성에 최적인 모델을 선정.
> @마커 NPC 혼선은 파이프라인(NpcDialogueMarker) 이슈로 모든 모델 공통 발생 — 모델 평가에서 제외.
> v1 평가(Gemma 4 vs GPT-4.1-mini, 2026.4.5~6)는 본 문서 말미 부록 참조.

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
| **현재 (2026.5)** | **Gemma 4 26B MoE** | **GPT-4.1 Mini** | 한국어 서술 일관성 + 안정성 |

`server/.env` 정본:

```bash
LLM_PROVIDER=openai
OPENAI_MODEL=google/gemma-4-26b-a4b-it
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_FALLBACK_MODEL=openai/gpt-4.1-mini
LLM_ALTERNATE_MODEL=google/gemma-4-26b-a4b-it
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
