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

## 부록 A — 카드-서술 불일치 근본 수정 (server b09d8fd, docs ed7576b)

잔여 관찰 항목이던 V8 불일치를 정밀 분석 — **audit 오탐 1겹 + 서버 실결함
1겹의 복합**으로 확정:

- **audit 턴 매핑 밀림**: 스크립트 로컬 카운터가 자동 진입 턴(+2)과 어긋나
  다른 턴끼리 대조 — 기록 turnNo를 응답 turnNo로 동기화.
- **결함 A**: `_appearedNpcIds` 수집 지점(B-1/B-2/콜론 승격)이 서버 중간 형식
  마커만 대상 — 스트리밍 완전형 `@[표시명|url]`이 안 잡혀 "실제 등장 NPC로
  카드 교체" 로직이 죽어 있었음 (실측 T4: 카드=브렌 유지, 서술=토브렌만).
  5.9 초입 완전형 마커 전수 역해석으로 보충 → 교체 로직 부활.
- **결함 B**: mentioned 검사가 includes — "**토브렌**" 속 '브렌'(alias 2자)
  부분 문자열 오매칭. 앞 경계 `(?<![가-힣])` 요구 (한국어 이름 뒤 조사
  때문에 뒤 경계는 미적용).

검증: 회귀 4건 + 실런 V8 통과·카드 표시 턴 정합 3/3.

## 부록 B — 테스트·검증 시스템 감사 (server 7012bb8, docs 92e78b1)

서버 설계 대량 변경 대비 테스트 기준 정합 전수 검토. 발견 3건 수정:

1. **stream-classifier 구 정책 테스트 방치** — 'NPC 후보 일반 단어 제거'
   (bug 6ba6fd6b) 변경 후 미갱신 실패 2건이 장기간 "기존 실패 무관"으로
   지나쳐짐 (상수 노이즈가 진짜 회귀를 가리는 구조). 현행 기준으로 반전
   갱신 → **전체 스위트 실패 0 달성**.
2. **audit V9-a 광역 오탐** — `허.{5,15}지`가 "허투루 넘기지" 등 정상
   문장에 유령 경고 (실측). 알려진 unknownAlias 밀착 융합만 잡는 회귀
   센서로 재정의 — 정상 3런 오탐 0 / 융합 실재 런 정탐 3/3.
3. **로직 복제 spec drift 실증** — 무명 라벨 복제본이 1단어 구버전으로
   어긋난 채 통과 중이었음. `ANON_SPEAKER_LABEL_RE` export 상수로 추출해
   spec이 정본을 직접 import — **향후 신규 후처리 regex는 export 우선 원칙**.

건전 확인: V1~V7 상태 관찰형 검증 서버 필드 정합, 최근 spec들 신선,
npc-name-reveal 신정책 갱신 완료. 잔여 권고: LockRace·timeoutMs 통합
커버리지는 실런 의존 유지.
