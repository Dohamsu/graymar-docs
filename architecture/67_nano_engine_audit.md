# 67. Nano 엔진 전수 감사 + 수정 (2026-07-11)

## 범위와 방법

nano/경량 LLM 8계열 전수 점검: NanoEventDirector · NanoDirector ·
NpcReactionDirector · ChallengeClassifier · LlmIntentParser ·
DialogueGenerator(+IntroDialogue) · FactExtractor · MidSummary.
코드 설정 수집(모델·토큰·온도·타임아웃·fallback) + 로그 실측(~650턴).

## 발견과 수정 (server 81b9036)

### P1-1. 요청 단위 타임아웃 부재 (+죽은 설정)

`getLightModelConfig().timeoutMs(5000)`가 반환만 되고 어디서도 미사용 —
`llmCaller.call()`에 timeout 파라미터 자체가 없어 모든 nano가 전역
`LLM_TIMEOUT_MS=60000`을 상속. 메인 LLM **앞에 직렬**로 도는
NpcReaction·NanoDirector·IntroDialogue가 provider 지연 시 각 60초 상한
(레이턴시 10초 원칙과 충돌 잠재).

**수정**: `LlmProviderRequest.timeoutMs` 신설 → openai/claude provider
per-request 적용(SDK requestOptions) → 연결: light 계열 5초(lightConfig),
dialogue 26B 10초, intent 5초(기존 Promise.race 5초와 이중 안전),
`callLight()` 헬퍼 일괄. 실패 시 기존 fallback 사다리 그대로.

### P1-2. 워커 동일 턴 이중 처리 — 7/650턴 (1.1%)

같은 (turn, run)에 스트리밍 2회 시작 + **서로 다른 서술 2벌 생성** 실측
(len 373/395 각각 후처리 완주). 원인: `processTurn` 락 UPDATE에 CAS
조건(`llmStatus='PENDING'`)은 있으나 **갱신 행 수 미확인** — `wake()`
즉시 트리거와 1초 interval 폴링이 같은 PENDING을 동시 select하면 둘 다
진입. LLM 비용 2배 + 최종 서술 비결정(나중에 끝난 쪽 승리) + nano 체인 2벌.

**수정**: `.returning()` 0행 = 다른 사이클 선점 → 즉시 반환
(`[LockRace]` 로그). wake()의 "중복 호출 안전" 주석이 이제 사실이 됨.

### P1-3. NpcReactionDirector JSON 파싱 실패 10.4% (63/604)

전부 parse failed — 1회 실패 즉시 fallback이라 그 턴의 반응 유형·즉시
목표·톤 3축이 무작위 기본값(대사 품질 사전 결정 무력화). gpt-4.1-nano +
temp 0.7 + 자유 JSON 조합.

**수정**: JSON 형식 리마인더 + temperature 하향(0.4) 재시도 1회
(IntroDialogue와 동일 패턴). 검증 런 실측: 재시도 2회 발동 **2건 모두
구제** — fallback 0.

### P2-4·5. 설정 명시화 (.env)

DialogueGenerator 모델이 `LLM_DIALOGUE_MODEL ?? LLM_ALTERNATE_MODEL ??
light` 폴백으로 **우연히 Gemma 26B** — alternate는 모델 교차 실험 변수라
바꾸면 대사 품질이 암묵 연동되는 결합. `.env`에 명시 고정:
`LLM_LIGHT_MODEL=gpt-4.1-nano` / `LLM_LIGHT_TIMEOUT_MS=5000` /
`LLM_DIALOGUE_MODEL=google/gemma-4-26b-a4b-it`.

### P3. 정상 확인 (안심 항목)

- NanoEventDirector 779회 실패 0 — 검증·보정 로직으로 가장 견고
- Intent LLM→RULE fallback 9.5% — 설계된 사다리 (+기존 5초 레이싱 존재 확인)
- ChallengeClassifier·FactExtractor·NanoDirector 실패 로그 0
- reaction ∥ Track1 병렬화 등 직렬 레이턴시 최적화 기적용 확인

## 검증

전체 1010 passed + 15턴 실런: reaction fallback 0(재시도 2/2 구제),
이중 스트리밍 0, 타임아웃 이상 0. 게이트 실패 2건은 기존 유형
(소품 명사 반복 / 카드-서술 저빈도 불일치)으로 무관.

## 잔여 관찰

- 카드-서술 불일치 저빈도 유형 — 빈도 유지 시 5.9 `appearedNpcIds > 0`
  분기 갭 정밀 추적
- gemini provider는 per-request timeout 미적용 (현 운영 미사용 경로)
- LLM_LIGHT_MODEL 4.1-nano 유지 — reaction JSON 실패율 재상승 시
  responseFormat json_object 도입 검토
