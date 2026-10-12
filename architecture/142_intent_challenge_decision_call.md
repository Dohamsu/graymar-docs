# 142. 직접 입력 턴 결정 호출 통합 — 의도·판정 nano 를 한 번으로

> 상태: 설계 확정(2026-10-12 `/plan-eng-review`). **§4 원안(결정 nano 통합)은 리뷰 결정 R1~R3 로 대체됐다** — 판정 nano 선행 시작(D1) · 의도·판정 nano 2.5초 상한(D2) · 의도 nano 를 JEV 와 동시 시작(D3). 구현 기준은 아래 Decision ledger 와 Implementation Tasks. arch/141 남은 작업 2번.

## 1. 목표

직접 입력(ACTION) 장소 턴에서 서술 전에 차례로 기다리는 nano 호출 두 번(의도 분류 → 판정 분류)을 한 번의 "결정 호출"로 합쳐 첫 글자를 앞당긴다. 꼬리 지연(nano 타임아웃 5~6초 + 재시도)도 2.5초 상한으로 자른다.

- 대상: 직접 입력 턴(실유저 장소 턴의 35%). 선택지 턴은 규칙 판정이라 해당 없음.
- 비목표: 판정을 LLM 에 넘기는 것(주사위는 계속 서버 — 불변식 1·12), 의도·판정의 출력 계약 변경.

## 2. 현재 경로 (코드 지도)

`location-turn.service.ts handleLocationTurnInner`:

1. `llmIntentParser.parseWithInsistence` (3026)
   - 키워드 파서(동기) → **의도 JEV**(예산 `min(2s, 남은 5s)`) → JEV 확신(≥0.9) 실패 시 **의도 nano**(남은 5초 예산, `gpt-4.1-nano` 직호출 — LlmCaller 우회, 재시도 없음) → `mergeResults`(키워드 우선 규칙·고집 승격·targetNpc 는 키워드/JEV 만)
2. 행동 유형 재작성: 고백 강등(THREATEN→TALK, 3043) · 대화 잠금 강등(MOVE/FIGHT/STEAL→INVESTIGATE, 3087-3117) · 경계 처리(MOVE→INVESTIGATE, 3140-3189)
3. `challengeClassifier.classify({rawInput, actionType, target…})` 시작(3215) — **의도 확정 뒤에 시작**한다. 내부는 **판정 nano**(LlmCaller 경유, 타임아웃 5초(`.env` LLM_LIGHT_TIMEOUT_MS=5000 — 리뷰 정정)·재시도·fallback 모델) ∥ **판정 JEV**(FREE/CHECK 만, RULE_CHECK 행동은 생략) 병렬. 후처리: RULE_CHECK 행동은 CHECK 고정, OUT_OF_SCOPE 는 그대로, JEV 확신 시 FREE/CHECK 덮어쓰기.
4. 라우팅(이벤트 매칭 — 판정 호출과 병렬) → `await challengePromise`(3374) → 경계·세이프티·아크 규칙 적용 → resolve.

판정 nano 가 받는 의도 값은 **재작성 후 actionType 하나**뿐이다(대상 NPC 는 규칙 텍스트 매칭).

## 3. 실측 (14일, 직접 입력 장소 턴 46건 — 대부분 테스터)

| 호출 | 횟수 | p50 | p90 | 최대 |
|---|---|---|---|---|
| 의도 JEV | 46 | 0.42s | 0.49s | 0.67s |
| 의도 nano | 27 (59%) | 1.11s | 1.52s | 2.27s |
| 판정 nano | 42 | 1.17s | 2.19s | 2.98s |
| 판정 JEV | 34 | 0.42s | 0.48s | 0.50s |

arch/141 계측: POST 의도 구간 평균 2.18s(꼬리 5.0s = 의도 nano 타임아웃), 판정 대기 1.45s(라우팅과 겹친 뒤 남은 몫).

## 4. 설계 — 결정 호출

### 4.1 흐름

```
t0  키워드 파스(동기)
    ├─ 의도 JEV            (2s 예산, 지금과 동일)
    └─ 결정 nano(신규)      (2.5s 단일 시도) → {의도 필드 + 판정 필드}
t1  의도 확정 = JEV 확신이면 JEV, 아니면 결정 nano 의도부로 mergeResults(규칙 동일), 둘 다 실패면 키워드
t2  행동 유형 재작성(고백·잠금·경계) — 지금과 동일
t3  판정 확정
    ├─ 결정 nano 성공 && 그 actionType == 재작성 후 actionType
    │     → 결정 nano 판정부 + 판정 JEV(지금처럼 재작성 후 actionType 으로 시작, 라우팅과 병렬)
    │       후처리는 classify() 와 같은 규칙(RULE_FREE/RULE_CHECK/OUT_OF_SCOPE/JEV 덮어쓰기)
    └─ 그 외(불일치·결정 nano 실패·RULE_FREE)
          → 지금의 classify() 그대로 (불일치는 지금과 같은 순차 경로 — 회귀 없음)
```

- **의도 JEV 와 결정 nano 를 동시에 시작**한다. 지금은 JEV 실패를 확인한 뒤에야 nano 를 부른다.
- 결정 nano 의 판정부는 **자기가 고른 actionType 기준**이다. 최종 actionType 과 다르면(JEV 가 다른 행동으로 확정, 재작성 발생) 그 판정부는 버리고 기존 경로로 판정한다.

### 4.2 결정 nano 프롬프트

기존 두 프롬프트(`intent-system-prompt.ts` · `challenge-classifier.service.ts SYSTEM_PROMPT`)의 규칙을 그대로 합친다(새 규칙 추가 없음, 예시 문장 추가 없음 — 불변식 42·50). 출력 JSON:

```
{"intent":{"actionType","secondaryActionType","tone","target","targetNpc","riskLevel"},
 "challenge":{"result","statHint","difficultyMod","plausibility","physicalImpact","socialImpact","contentSafety","reason"}}
```

파싱은 기존 파서 두 개(`LlmIntentParserService.parseJsonResponse`, `ChallengeClassifierService.parseResponse`)를 각 하위 객체에 재사용한다. 한쪽만 파싱 실패하면 그쪽만 기존 경로로 떨어진다.

### 4.3 코드 구조

- `ChallengeClassifierService`: `classify()` 의 후처리(RULE_CHECK 고정·OUT_OF_SCOPE·JEV 덮어쓰기)를 순수 함수 `finalizeChallengeDecisionCore(ctx, appraisal, jevResult)` 로 뽑아 두 경로가 공유. 새 메서드 `classifyWithAppraisal(ctx, appraisal)` = 판정 JEV 만 부르고 core 로 마무리.
- 신규 `DecisionCallService`(llm/): 결정 nano 호출 + 두 하위 객체 파싱. 호출 경로는 LlmCaller 에 **재시도 0·fallback 모델 없음** 옵션으로(꼬리 상한을 지키려고). 기록 stage `'decision'`.
- `LlmIntentParserService.parseWithInsistence`: 의도 nano 대신 결정 nano Promise 를 받아 쓰는 경로 추가(JEV 와 병렬). 결정 결과 전체(판정부 포함)를 호출자에게 함께 돌려준다.
- `location-turn`: 재작성 후 actionType 과 결정 nano actionType 비교 → 일치하면 `classifyWithAppraisal`, 아니면 `classify`.
- 킬스위치: 런타임 플래그 `DECISION_CALL_ENABLED`(기본 true). false 면 지금 경로 그대로.

## 5. 기대 효과

| 경우 | 지금 | 이후 |
|---|---|---|
| 의도 JEV 실패(59%) | JEV 0.4 + 의도 nano 1.1 + 판정 nano 1.2(일부 라우팅과 겹침) | 결정 nano ~1.3~1.6 (JEV 와 병렬) |
| 의도 JEV 확신(41%) | JEV 0.4 + 판정 nano 1.2 | 결정 nano ~1.3~1.6 (JEV 와 병렬) — 소폭 |
| nano 지연 꼬리 | 의도 5s + 판정 6s·재시도 | 2.5s 상한 후 키워드/기존 경로 |

추정: 직접 입력 턴 POST 평균 −1.0~1.5s, 꼬리 −3~5s. 비용은 nano 두 번 → 한 번(출력 토큰은 비슷).

## 6. 위험

1. **프롬프트 합치기로 정확도 저하** — 두 과업을 한 호출에 넣으면 한쪽 지시가 희석될 수 있다(프롬프트 최소주의 원칙). → 오프라인 재생 A/B 로 게이트(§7).
2. **불일치율이 높으면 효과가 없다** — 결정 nano actionType 과 최종 actionType 이 자주 다르면 기존 순차 경로로 떨어진다. → A/B 에서 JEV 확정 행동과의 일치율 측정.
3. **세이프티 축 회귀** — contentSafety 판정이 합친 프롬프트에서 약해지면 유해 입력이 통과할 수 있다. L1 룰(content-safety.core)은 그대로라 절대선은 유지되지만 L2 회귀는 별도 확인. → 세이프티 스펙 말뭉치 재생.
4. **2.5초 상한 타임아웃 증가** — nano p90 2.19s 라 2.5s 에서 실패율 수 % 예상. 실패 시 의도는 키워드, 판정은 기존 classify() — 그 턴만 지금처럼 느려진다.

## 7. 검증 계획

1. **오프라인 재생 A/B** (머지 전 게이트): 최근 60일 직접 입력 원문 + 장소·NPC 맥락으로 기존 두 호출 vs 결정 호출을 같은 모델로 재생.
   - actionType 일치 ≥ 90%, FREE/CHECK 일치 ≥ 90%, plausibility 일치 ≥ 85%
   - contentSafety: 세이프티 스펙 말뭉치에서 기존이 잡은 건을 결정 호출이 놓치는 경우 0
   - 지연 p90 ≤ 2.5s
2. 단위 테스트: finalize core(기존 classify 스펙 케이스를 core 로도 통과), 결정 파싱(한쪽 실패), 불일치 시 기존 경로, 타임아웃 폴백, 킬스위치.
3. 배포 후 형식 플레이테스트 5~10턴 + `[TurnTiming:POST]` 전후 비교.

---

# /plan-eng-review — 2026-10-12

리뷰 대상: `architecture/142_intent_challenge_decision_call.md` (위 원안). 보고 파일도 이 문서다.

## Scope Challenge

복잡도: 바뀌는 비테스트 파일 약 7개(challenge-classifier·llm-intent-parser·location-turn·신규 decision-call·llm.module·runtime-flags·프롬프트), 신규 서비스 1개 → 8파일·2클래스 미만이라 구조 선택 질문은 생략한다.

발견:
1. [P1] (confidence: 9/10) `server/src/llm/challenge-classifier.service.ts:117` — 판정 nano 시스템 프롬프트가 "※ actionType이 아니라 실제 행동 성격에 맞춘다." 라고 지시하고, 사용자 메시지에서 행동 유형은 `타입: ${ctx.actionType}` 한 줄뿐이다(:415). 판정 nano 는 최종 actionType 을 기다릴 이유가 약하다 — 키워드 파서의 actionType(턴 시작 시 동기 확보)으로 의도 분류와 동시에 시작할 수 있다. 그러면 프롬프트를 합치지 않고, 새 서비스·불일치 폴백 없이 거의 같은 지연 이득을 얻는다. 최종 actionType 에 달린 규칙(RULE_FREE·RULE_CHECK 고정·판정 JEV)은 지금처럼 의도 확정 뒤 후처리에서 적용한다. (리뷰어: Claude 본 리뷰)
2. [P2] (confidence: 9/10) `server/src/llm/llm-caller.service.ts:151` — `if (category === 'RETRYABLE' && attempts < config.maxRetries)`. 원안 §4.3 의 "LlmCaller 에 재시도 0·fallback 모델 없음 옵션"은 존재하지 않는다(요청 단위 재시도·폴백 오버라이드 없음). 2.5초 꼬리 상한의 실현 수단이 미정이다.
3. 사실 정정 (confidence: 10/10) `server/.env:23` — `LLM_LIGHT_TIMEOUT_MS=5000`. 원안 §2 의 "타임아웃 6초"는 5초가 맞다(동작 무관, 문서만 정정).

## Decision ledger

### R1: 통합 방식 — 결정 nano 하나로 합치기 vs 판정 nano 선행 시작
Finding: Scope Challenge 1, P1, confidence 9/10, server/src/llm/challenge-classifier.service.ts:117, Claude 본 리뷰
Plan baseline: 원안 §4 — 의도·판정 프롬프트를 합친 결정 nano 1회(신규 DecisionCallService), 행동 유형 불일치 시 기존 classify() 로 폴백 (승인 없음, 원안 제안)
Runtime evidence: 판정 nano 는 의도 확정 뒤 시작(location-turn.service.ts:3212-3234), 받는 의도 값은 재작성 후 actionType 하나. 14일 실측 판정 nano p50 1.17s / p90 2.19s, 의도 nano p50 1.11s (llm_call_logs, 46턴)
Comparison grid:
| 선택 | 현재 | A | B |
|---|---|---|---|
| R1 통합 방식 | 원안 제안(미승인) | 판정 nano 를 키워드 actionType 힌트로 턴 시작 시 선행 시작, 프롬프트 2개 유지, 최종 actionType 규칙·판정 JEV 는 의도 확정 뒤 후처리 | 원안대로 결정 nano 1회(프롬프트 통합·신규 서비스·불일치 폴백) |
| R2 꼬리 상한 수단 | 미정(보류) | 보류 | 보류 |
Question D1:
D1 — 의도·판정 nano 를 어떻게 겹칠까요?
Project/branch/task: graymar main, arch/142 직접 입력 턴 결정 호출 통합 설계 리뷰.
ELI10: 지금은 "무슨 행동인지"(의도)를 다 판단한 뒤에야 "주사위를 굴릴지"(판정)를 묻기 시작해서 두 nano 를 차례로 기다립니다. 원안은 두 질문을 한 번의 nano 호출로 합치자는 것이고, 대안은 판정 nano 를 키워드로 추린 행동 유형을 들고 의도 분류와 동시에 출발시키는 것입니다. 판정 프롬프트가 이미 "행동 유형이 아니라 실제 행동 성격으로 판단하라"고 되어 있어, 판정은 최종 의도를 기다릴 필요가 거의 없습니다.
Stakes if we pick wrong: 합치기를 고르면 두 판단이 한 프롬프트에서 서로 희석돼 의도·판정·세이프티 정확도가 떨어질 수 있고, 선행 시작을 고르면 키워드 행동 유형이 틀린 턴에서 판정 nano 가 덜 정확한 힌트를 받습니다.
Recommendation: A because 프롬프트를 건드리지 않아 정확도 위험이 작고, 새 서비스 없이 지연 이득은 거의 같습니다(둘 다 서술 전 대기 ≈ 의도 경로 1.5초 안팎).
Completeness: A=9/10, B=8/10
Pros / cons:
A) 판정 nano 선행 시작 (recommended)
  ✅ 판정 nano 가 의도 분류와 동시에 돌아 서술 전 대기에서 판정 몫(p50 1.17초)이 거의 사라진다
  ✅ 기존 두 프롬프트·파서·스펙을 그대로 쓰고 바뀌는 곳은 location-turn 과 classify 분할뿐이다
  ❌ 키워드 행동 유형이 최종과 다른 턴은 판정 nano 가 틀린 힌트를 본다 — 재생 A/B 로 판정 일치율 확인이 필요하다 (human: ~1일 / CC: ~1시간)
B) 결정 nano 하나로 합치기
  ✅ nano 호출이 두 번에서 한 번으로 줄어 비용이 조금 내려간다
  ✅ 판정이 nano 가 고른 행동 유형과 같은 문맥에서 나온다
  ❌ 두 과업을 한 프롬프트에 넣어 지시가 희석될 수 있고(프롬프트 최소주의), 세이프티 축 재검증과 불일치 폴백 경로까지 새로 만들어야 한다 (human: ~3일 / CC: ~3시간)
Net: 같은 지연 이득을 프롬프트를 건드리는 큰 변경(B)으로 얻을지, 순서만 바꾸는 작은 변경(A)으로 얻을지의 선택입니다.
Header: 통합 방식
Options:
A) 판정 nano 선행 시작 (recommended)
판정 nano 를 턴 시작 시 키워드 actionType 힌트로 의도 분류와 동시에 시작한다. 프롬프트 2개·파서·스펙 유지. 최종 actionType 에 달린 규칙(RULE_FREE·RULE_CHECK 고정·OUT_OF_SCOPE)과 판정 JEV 는 의도 확정 뒤 후처리에서 적용한다. 검증: 재생 A/B 로 판정 일치율. 비용 동일. (human: ~1일 / CC: ~1시간)
B) 결정 nano 하나로 합치기
원안대로 의도·판정 프롬프트를 합친 결정 nano 1회 + 신규 DecisionCallService + 행동 유형 불일치 시 기존 classify() 폴백. nano 호출 1회 절약, 정확도·세이프티 재검증 필요. (human: ~3일 / CC: ~3시간)

State: approved
Actual answer: A) 판정 nano 선행 시작 (D1, 2026-10-12)
Accepted scope: 판정 nano 를 턴 시작 시 키워드 actionType 힌트로 의도 분류와 동시에 시작한다. 프롬프트 2개·파서·기존 스펙 유지. 최종 actionType 규칙(RULE_FREE·RULE_CHECK 고정·OUT_OF_SCOPE)과 판정 JEV 는 의도 확정 뒤 후처리. 원안의 결정 nano·DecisionCallService·불일치 폴백은 만들지 않는다. 검증: 재생 A/B 로 판정 일치율.
History: 원안(결정 nano 통합)은 D1 에서 기각

### R2: 지연 꼬리 상한 — nano 타임아웃·재시도
Finding: Scope Challenge 2, P2, confidence 9/10, server/src/llm/llm-caller.service.ts:151, Claude 본 리뷰
Plan baseline: 원안 §4.3 — 결정 nano 2.5초 단일 시도(실현 수단 미정). R1 승인으로 대상은 의도 nano·판정 nano 두 호출로 바뀐다
Runtime evidence: 의도 nano = 5초 공유 예산·단일 시도·직호출(llm-intent-parser.service.ts:47, 158-168). 판정 nano = LlmCaller 경유, 요청당 timeoutMs 5000(.env:23)·RETRYABLE 재시도(LLM_MAX_RETRIES=2)·fallback 모델(gpt-4.1-mini). 14일 판정 nano 최대 2.98s, 의도 nano 최대 2.27s. arch/141 T11 은 의도 nano 5초 타임아웃
Comparison grid:
| 선택 | 현재 | A | B | C |
|---|---|---|---|---|
| R1 통합 방식 | 승인: 판정 nano 선행 시작 (D1) | 동일 | 동일 | 동일 |
| R2 의도 nano 상한 | 5초 공유 예산 | 2.5초 | 5초(유지) | 2.5초 |
| R2 판정 nano 상한 | 5초·재시도·fallback 모델 | 2.5초 단일 시도(LlmCaller 요청 단위 재시도·fallback 끄기 옵션 신설) | 유지 | 유지 |
Question D2:
D2 — nano 가 느릴 때 얼마나 기다릴까요?
Project/branch/task: graymar main, arch/142 직접 입력 턴 결정 호출 리뷰 (D1: 판정 nano 선행 시작 승인).
ELI10: 가끔 nano 가 늦게 답해 한 턴이 5~7초 더 멈춥니다(arch/141 T11). 상한을 2.5초로 자르면 그 턴은 빨라지지만, 시간 안에 못 받은 판단은 대체값으로 처리됩니다. 의도는 키워드 결과로, 판정은 "주사위 굴림(CHECK)"으로 바뀌는데, 판정 JEV 가 확신하면 JEV 판단이 우선합니다.
Stakes if we pick wrong: 너무 짧게 자르면 잡담 턴인데 주사위를 굴리는 일이 늘고, 그대로 두면 느린 턴의 5~7초 정지가 남습니다.
Recommendation: A because 실측 p90 이 의도 1.5초·판정 2.2초라 2.5초 상한은 상위 몇 %만 자르고, 잘린 판정도 판정 JEV 가 대부분 구제합니다.
Completeness: A=9/10, B=6/10, C=8/10
Pros / cons:
A) 둘 다 2.5초 (recommended)
  ✅ 느린 턴의 최악 대기가 5~7초에서 2.5초로 내려가 첫 글자 꼬리가 크게 줄어든다
  ✅ LlmCaller 에 요청 단위 재시도·fallback 끄기 옵션이 생겨 다른 짧은 nano 호출에도 쓸 수 있다
  ❌ 판정 nano 가 2.5초를 넘는 턴(실측 기준 수 %)은 CHECK 대체값이 되고, JEV 가 확신하지 않으면 잡담에도 주사위가 뜬다 (human: ~4시간 / CC: ~30분)
B) 지금 그대로
  ✅ 판단 정확도·대체값 빈도가 지금과 같아 회귀 위험이 없다
  ✅ 코드 변경이 없다
  ❌ 느린 턴의 5~7초 정지가 남아 R1 효과가 꼬리에서 사라진다
C) 의도만 2.5초
  ✅ 의도 대체값(키워드 결과)은 안전해서 정확도 손실이 작다
  ✅ LlmCaller 를 건드리지 않는다
  ❌ 판정 nano 의 재시도·fallback 꼬리(최악 수 초)가 그대로 남는다 (human: ~1시간 / CC: ~10분)
Net: 꼬리 지연을 얼마나 확실히 자를지와, 잘린 턴에서 대체값(키워드 의도·CHECK 판정)을 얼마나 받아들일지의 교환입니다.
Header: 꼬리 상한
Options:
A) 둘 다 2.5초 (recommended)
의도 nano 예산 5초→2.5초, 판정 nano 는 요청당 2.5초 단일 시도(LlmCaller.call 에 요청 단위 재시도·fallback 끄기 옵션 신설). 잘린 의도는 키워드, 잘린 판정은 CHECK 대체값이며 판정 JEV 확신 시 JEV 가 우선. 테스트: 타임아웃 시 대체값 경로. (human: ~4시간 / CC: ~30분)
B) 지금 그대로
의도 5초 공유 예산·판정 5초+재시도+fallback 모델 유지. 코드 변경 없음, 느린 턴 꼬리 유지.
C) 의도만 2.5초
의도 nano 예산만 2.5초로 줄이고 판정 nano 는 현행 유지. LlmCaller 변경 없음. (human: ~1시간 / CC: ~10분)

State: approved
Actual answer: A) 둘 다 2.5초 (D2, 2026-10-12)
Accepted scope: 의도 nano 예산 5초→2.5초. 판정 nano 는 요청당 2.5초 단일 시도 — LlmCaller.call 에 요청 단위 재시도·fallback 끄기 옵션 신설. 잘린 의도는 키워드, 잘린 판정은 CHECK 대체값(판정 JEV 확신 시 JEV 우선). 테스트: 타임아웃 시 대체값 경로.
History: none

## Section 1 — Architecture

흐름(승인된 R1·R2 반영):

```
t0  키워드 파스(동기) → kwType
    ├─ 의도: 의도 JEV(≤2s) ─▶ (확신 실패 시) 의도 nano(남은 예산, 총 2.5s)   [R3 미정]
    └─ 판정 감정: 판정 nano(kwType 힌트, 2.5s 단일 시도, 실패→CHECK 대체)   ← 신규: t0 시작
t1  의도 확정 → 재작성(고백·잠금·경계·MOVE 조기 반환)
t2  판정 확정 = finalize(최종 actionType, 감정 Promise)
      RULE_FREE(최종) → FREE (감정 버림)
      판정 JEV(최종 actionType) ∥ 감정 대기 → RULE_CHECK 고정 / OUT_OF_SCOPE / JEV 덮어쓰기   ← 기존 classify 후처리 그대로
t3  라우팅과 판정 JEV 병렬 → resolve
```

발견:
1. [P2] (confidence: 8/10) `server/src/turns/location-turn.service.ts:3061-3074, 3140-3189` — EQUIP·MOVE 경로가 판정 이전에 조기 반환한다. 판정 감정을 t0 에 시작하면 이 턴들에서 nano 호출이 버려지고, 처리하지 않은 Promise 거부가 남을 수 있다. 승인된 R1 의 필요 구현으로 처리한다: 키워드 actionType 이 RULE_FREE(MOVE_LOCATION·REST·SHOP·EQUIP·UNEQUIP)면 감정을 시작하지 않고, 감정 Promise 는 생성 즉시 `.catch` 로 CHECK 대체값에 묶는다. 질문 없음(R1 의 구현 세부).
2. [P3] (confidence: 7/10) `server/src/turns/location-turn.service.ts:3203-3211` — `earlyChallengeNpcId` 는 동행자 허용 여부에 `intent.actionType` 을 쓴다. t0 에서는 kwType 을 쓴다. 대상 NPC 는 감정 프롬프트의 참고 정보일 뿐이라 영향이 작다. R1 의 구현 세부로 기록.
3. 실패 모드: 판정 nano 2.5초 초과 → CHECK 대체 → 판정 JEV(최종 actionType, 0.4s)가 확신하면 JEV 가 결정. 사용자에게는 드물게 잡담 턴에 주사위가 뜨는 형태로 보인다(조용한 실패 아님 — 판정 배너 노출). 로그 `challenge-classifier` fallback 사유로 계측된다.

Dispositions: 1·2 = R1 승인 범위의 구현 세부로 수용, 3 = R2 승인으로 수용.

### R3: 의도 nano 를 의도 JEV 와 동시에 시작할지
Finding: Section 1 / R2 파생, P2, confidence 8/10, server/src/engine/hub/llm-intent-parser.service.ts:145-168, Claude 본 리뷰
Plan baseline: 원안에 없음. 현재 동작은 JEV 실패 확인 후 nano 시작(공유 예산). R2 승인으로 공유 예산이 2.5초가 됨
Runtime evidence: `const jevBudget = Math.min(JEV_INTENT_TIMEOUT_MS, Math.max(1, deadline - Date.now()))` 뒤 `remainingMs > 0 ? await this.callLlm(..., remainingMs)` — JEV p50 0.42s·최대 0.67s(14일). 2.5초 공유 시 nano 몫 ≈ 2.1초(JEV 가 2초 타임아웃이면 0.5초). JEV 확신 41%·nano 진입 59%
Comparison grid:
| 선택 | 현재 | A | B |
|---|---|---|---|
| R1 통합 방식 | 승인: 판정 nano 선행 시작 (D1) | 동일 | 동일 |
| R2 상한 | 승인: 의도 2.5s·판정 2.5s 단일 (D2) | 동일 | 동일 |
| R3 의도 nano 시작 시점 | JEV 실패 확인 후(순차) | t0 에 JEV 와 동시 시작, 각자 2.5s, JEV 확신이면 nano 결과 버림 | 순차 유지(nano 는 남은 예산) |
Question D3:
D3 — 의도 nano 를 JEV 와 동시에 시작할까요?
Project/branch/task: graymar main, arch/142 리뷰 (D1 판정 선행·D2 2.5초 상한 승인).
ELI10: 의도 판단은 빠른 JEV(0.4초)가 먼저 보고, 확신이 없을 때만 nano 에게 다시 묻습니다. 그래서 59% 턴은 JEV 0.4초를 기다린 뒤 nano 를 또 기다립니다. 처음부터 둘을 같이 출발시키면 그 0.4초가 사라지고 nano 도 2.5초를 온전히 씁니다. 대신 JEV 가 확신한 41% 턴에서는 nano 호출이 그냥 버려집니다.
Stakes if we pick wrong: 동시 시작을 안 하면 2.5초 상한 아래 nano 몫이 줄어 키워드 대체가 늘고, 하면 nano 비용이 조금 늘어납니다.
Recommendation: A because 버려지는 nano 호출은 턴당 수 원의 수십 분의 일 수준인데, 59% 턴에서 0.4초를 줄이고 2.5초 상한 아래 키워드 대체 위험을 없앱니다.
Completeness: A=9/10, B=7/10
Pros / cons:
A) 동시 시작 (recommended)
  ✅ JEV 를 기다리던 0.4초(최대 2초)가 의도 경로에서 빠져 59% 턴이 더 빨라진다
  ✅ nano 가 2.5초 예산을 온전히 써 키워드 대체가 늘지 않는다
  ❌ JEV 가 확신한 41% 턴의 nano 호출은 버려져 nano 비용이 그만큼 는다 (human: ~2시간 / CC: ~15분)
B) 순차 유지
  ✅ nano 호출 수가 지금과 같다
  ✅ 의도 파서 코드를 바꾸지 않는다
  ❌ 2.5초 공유 예산에서 nano 몫이 2.1초 이하로 줄어 느린 턴은 키워드 결과로 떨어진다
Net: 의도 nano 를 일부 턴에서 헛돌리는 소액 비용으로 0.4초와 키워드 대체 위험을 사는 선택입니다.
Header: 의도 동시 시작
Options:
A) 동시 시작 (recommended)
의도 JEV 와 의도 nano 를 t0 에 함께 시작하고 각자 2.5초 상한. JEV 확신이면 JEV 를 쓰고 nano 결과는 버린다(기록은 남김). 테스트: JEV 확신 시 nano 결과 미사용·JEV 미확신 시 nano 사용. (human: ~2시간 / CC: ~15분)
B) 순차 유지
JEV 실패 확인 후 nano 를 남은 공유 예산(2.5초 - JEV 소요)으로 호출. 코드 변경 없음.

State: approved
Actual answer: A) 동시 시작 (D3, 2026-10-12)
Accepted scope: 의도 JEV 와 의도 nano 를 t0 에 함께 시작, 각자 2.5초 상한. JEV 확신이면 JEV 결과를 쓰고 nano 결과는 버린다(호출 기록은 남김). 테스트: JEV 확신 시 nano 결과 미사용·미확신 시 nano 사용.
History: none

## Section 2 — Code quality

발견(모두 승인된 R1~R3 의 구현 세부 — 새 질문 없음):
1. [P2] (confidence: 9/10) `server/src/llm/challenge-classifier.service.ts:193-240` — `classify()` 는 규칙 게이트·nano·JEV·후처리를 한 함수에 묶고 있다. `startAppraisal(ctx)`(nano 감정 + 2.5초 단일 시도 + 실패 시 CHECK 대체, 생성 즉시 catch)와 `finalize(ctx, appraisalPromise)`(RULE_FREE·판정 JEV 병렬·RULE_CHECK 고정·OUT_OF_SCOPE·JEV 덮어쓰기)로 나누고, `classify(ctx) = finalize(ctx, startAppraisal(ctx))` 로 기존 계약·스펙 426줄을 그대로 통과시킨다.
2. [P2] (confidence: 9/10) `server/src/llm/llm-caller.service.ts:122-205` — 요청 단위 재시도·fallback 끄기는 `LlmProviderRequest` 가 아니라 `call(request, stage, opts?: { maxRetries?: number; fallback?: boolean })` 세 번째 인자로 둔다(프로바이더 요청 타입을 오염시키지 않음). 기본값은 지금 동작과 같다.
3. [P3] (confidence: 9/10) `server/src/engine/hub/llm-intent-parser.service.ts:145-168` — 동시 시작 시 nano Promise 를 JEV 대기 전에 만들고 생성 즉시 catch 를 붙인다(JEV 확신으로 버려질 때 미처리 거부 방지). `INTENT_LLM_TIMEOUT_MS` 5000→2500.
4. [P3] (confidence: 8/10) `server/src/turns/location-turn.service.ts:3191` — "회색지대 nano" 주석은 이미 낡았다(nano 는 RULE_FREE 외 전 행동에 돈다). 같은 변경에서 고친다.

Dispositions: 1~4 수용(R1·R2·R3 승인 범위).

## Section 3 — Tests

```
CODE PATHS
[+] challenge-classifier.service.ts
  ├── classify() = finalize(start)          [★★★ TESTED] 기존 스펙 426줄이 래퍼로 그대로 통과해야 함
  ├── startAppraisal()
  │   ├── 2.5초 초과 → CHECK 대체            [GAP] 신규
  │   └── LlmCaller opts(재시도 0·fallback 끔) 전달  [GAP] 신규
  └── finalize(최종 actionType, 감정)
      ├── 감정 힌트(kwType=TALK)·최종 FIGHT → RULE_CHECK 로 CHECK 고정  [GAP] 신규
      ├── 최종 RULE_FREE(MOVE 등) → FREE, 감정 무시                     [GAP] 신규
      └── JEV 확신 덮어쓰기·OUT_OF_SCOPE 유지  [★★★ TESTED] 기존 스펙
[+] llm-caller.service.ts call(opts)
  ├── maxRetries 0 → RETRYABLE 이어도 1회      [GAP] 신규
  └── fallback false → fallback 모델 미호출     [GAP] 신규
[+] llm-intent-parser.service.ts
  ├── JEV 확신 → nano 결과 미사용(호출은 함)    [GAP] 신규 (기존 jev.spec:95 는 "nano 미호출"을 단언 — 동작 변경, 스펙 갱신)
  ├── JEV 미확신 → nano 결과 사용              [★★ TESTED] jev.spec:106
  └── nano 2.5초 초과 → 키워드 결과            [GAP] 신규
[+] location-turn 판정 감정 t0 시작 / RULE_FREE kwType 은 미시작   [→EVAL] 재생 A/B + TurnTiming 실측

LLM integration: [→EVAL] 판정 nano 에 kwType 힌트 vs 최종 actionType 힌트 — 최근 직접 입력 원문 재생으로 FREE/CHECK·plausibility·contentSafety 일치율
COVERAGE: 4/13 경로 기존 커버 | GAPS: 9 (1 eval)
```

필요 테스트(승인된 동작의 증거 — 질문 없음):
- `challenge-classifier.service.spec.ts` 확장: finalize 의 RULE_CHECK 고정(힌트≠최종), 최종 RULE_FREE 무시, startAppraisal 타임아웃 대체·opts 전달.
  Value: protects=최종 actionType 규칙이 선행 감정보다 우선; fails_when=finalize 가 감정의 FREE 를 그대로 쓰면; why_new=기존 스펙은 같은 actionType 으로 감정·확정; seam=none; no_claim=nano 실제 판단 품질(목)
- `llm-caller` 신규 스펙: opts.maxRetries 0·fallback false.
  Value: protects=꼬리 상한이 재시도·fallback 으로 늘지 않음; fails_when=opts 무시; why_new=caller 재시도 경로 스펙 없음; seam=none; no_claim=실제 지연(목)
- `llm-intent-parser.jev.spec.ts` 갱신: :95 "JEV 확신 시 nano 미호출" → "nano 호출되지만 결과 미사용"(R3 의 의도된 동작 변경), nano 타임아웃 → 키워드.
  Value: protects=JEV 확신 결과가 nano 에 덮이지 않음; fails_when=먼저 끝난 nano 가 JEV 를 이기면; why_new=동시 시작은 새 경쟁 조건; seam=none; no_claim=JEV 실제 확신도(목)
- 재생 A/B(원안 §7.1 의 판정 부분): kwType 힌트 vs 최종 actionType 힌트로 판정 nano 를 최근 직접 입력 원문에 재생, FREE/CHECK 일치 ≥ 90%·contentSafety 누락 0.

Tests to retire: none (jev.spec:95 는 갱신).

Dispositions: 필요 테스트 수용(R1~R3 증거), 재생 A/B 는 R1 승인 범위.

## Section 4 — Performance

1. [P3] (confidence: 8/10) 비용: 의도 nano 가 JEV 확신 턴(41%)에도 호출된다(R3 승인, gpt-4.1-nano 출력 ≤256토큰). 판정 nano 호출 수는 그대로이며 RULE_FREE kwType 은 감정을 시작하지 않는다. 규모: 직접 입력 장소 턴은 실유저 장소 턴의 35%.
2. 지연: 의도 경로 = max(JEV 0.4, nano ≤2.5) ≈ nano p50 1.1s, 판정 감정은 그와 병렬, 판정 JEV(0.4s)는 라우팅과 병렬. 추정 POST 의도+판정 몫 2.6~4.9s → 1.1~1.6s(p50 기준) [estimated], 꼬리 5~7s → 2.5s [estimated, re-measure before gate].

Dispositions: 1·2 수용.

## Outside Voice

Codex 실행 실패 — gstack 이 고른 계획 리뷰 모델 `gpt-6-astra` 가 이 ChatGPT 계정에서 지원되지 않음(400 invalid_request_error). 수리: `gstack-config set plan_review_tier smart` 또는 `gstack-config set model_frontier_openai <model-id>`. 네이티브 대체 리뷰는 이 세션에 TaskOutput 도구가 없어 수행하지 않음. 외부 의견 커버리지 없음(clean 으로 세지 않는다).

## Decision ledger — Approval readiness

Approval readiness: PASS — R1 (D1 A), R2 (D2 A), R3 (D3 A).

## Reality rows

REALITY: premise-table finding 원안 전제 8건 중 2건 거짓(타임아웃 6초→5초, LlmCaller 요청 단위 재시도 옵션 부재), unverified=0 server/.env:23, server/src/llm/llm-caller.service.ts:151
REALITY: already-done pass 대상 파일의 2026-10-12 이후 커밋 없음(최근 525820d·7a117a8 은 JEV 도입분) server/src/engine/hub/llm-intent-parser.service.ts:145
REALITY: surface-check finding LlmCaller.call 에 요청 단위 재시도·fallback 오버라이드 없음 → R2 에서 신설로 승인 server/src/llm/llm-caller.service.ts:151
REALITY: binding-decisions pass 브랜치 결정 기록 없음(gstack-decision-search 빈 결과), 불변식 1·12(서버 판정)·40(룰 게이트)·55(세이프티 L1) 유지 CLAUDE.md:356
REALITY: numbers pass 지연 수치는 llm_call_logs 14일 46턴 [measured: llm_call_logs], 절감 추정은 [estimated, re-measure before gate] server/src/turns/location-turn.service.ts:3212
REALITY: deferred-asks pass 소유자 요청(arch/141 남은 작업 2번 = 개선안 2 의도·판정 통합 + 개선안 3 타임아웃 2.5초)의 두 요소 모두 계획에 포함, 사전 결정 축소(3번)는 별도 작업으로 NOT in scope 에 명시 architecture/141_first_text_latency_breakdown.md:34-35
REALITY: pr-count pass PR 없이 main 직접 커밋(레포당 1커밋 관행), 추가 PR 비용 없음 CLAUDE.md:111

## NOT in scope

- 원안 결정 nano(프롬프트 통합)·DecisionCallService·불일치 폴백 — D1 에서 기각.
- 런타임 킬스위치 `DECISION_CALL_ENABLED` — 결정 nano 용이었고 R1 은 호출 순서만 바꾼다. 기존 `CHALLENGE_CLASSIFIER_ENABLED` 가 판정 nano 를 계속 끈다.
- 서술 전 사전 결정(NPC 반응·연출 방향) 축소 — arch/141 남은 작업 3번, 별도.
- 선택지 턴 — 규칙 판정이라 해당 없음.

## What already exists

- 판정 후처리(RULE_FREE·RULE_CHECK·OUT_OF_SCOPE·JEV 덮어쓰기) — `challenge-classifier.service.ts:193-240` 를 finalize 로 재사용(재작성 아님).
- 의도 nano 타임아웃 래퍼 — `llm-intent-parser.service.ts:222-289` 의 `Promise.race` 그대로.
- 판정 JEV — `classifyResultWithJev` 그대로, 최종 actionType 으로 호출.
- 판정·의도 파서·프롬프트 — 변경 없음.

## Failure modes

| 새 경로 | 현실적 실패 | 처리·테스트 | 사용자에게 |
|---|---|---|---|
| 판정 감정 t0 시작 | 키워드 actionType 이 최종과 달라 감정이 틀린 힌트로 나옴 | finalize 가 최종 actionType 규칙 우선 + 판정 JEV 덮어쓰기, 재생 A/B 로 일치율 게이트 | 드물게 판정 결과 차이(배너로 보임) |
| 판정 감정 2.5초 초과 | nano 지연 | CHECK 대체 + JEV 구제, 신규 스펙 | 잡담 턴에 주사위(보임) |
| 조기 반환 턴(MOVE·EQUIP) | 감정 Promise 미사용 | RULE_FREE kwType 은 미시작, 생성 즉시 catch | 없음 |
| 의도 nano 동시 시작 | JEV 확신인데 nano 가 먼저 끝남 | JEV 결과 우선, 신규 스펙 | 없음 |
| 의도 nano 2.5초 초과 | nano 지연 | 키워드 결과, 신규 스펙 | 의도 오분류 가능(서술에 반영) |

Critical gaps: 0 (조용한 실패 없음).

## Worktree parallelization strategy

Sequential implementation, no parallelization opportunity. (llm/ 과 turns/ 가 같은 판정 계약을 공유한다.)

## Implementation Tasks
Synthesized from this review's findings. Each task derives from a specific
finding above. Run with Claude Code or Codex; checkbox as you ship.

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — llm-caller — `call()` 에 요청 단위 `opts.maxRetries`·`opts.fallback` 추가(기본값 = 현행)
  - Surfaced by: Scope Challenge 2 / R2
  - Files: server/src/llm/llm-caller.service.ts (+ 신규 스펙)
  - Verify: 신규 스펙 — maxRetries 0·fallback false
- [ ] **T2 (P1, human: ~3h / CC: ~20min)** — challenge-classifier — `startAppraisal`(2.5초·재시도 0·fallback 끔·CHECK 대체)/`finalize` 분리, `classify` 는 둘의 합성
  - Surfaced by: Section 2-1 / R1·R2
  - Files: server/src/llm/challenge-classifier.service.ts, challenge-classifier.service.spec.ts
  - Verify: 기존 426줄 스펙 무수정 통과 + 신규(힌트≠최종 RULE_CHECK, 최종 RULE_FREE, 타임아웃 대체)
- [ ] **T3 (P1, human: ~2h / CC: ~15min)** — llm-intent-parser — 의도 JEV·nano t0 동시 시작, 각 2.5초, JEV 확신 우선
  - Surfaced by: R3 / Section 2-3
  - Files: server/src/engine/hub/llm-intent-parser.service.ts, llm-intent-parser.jev.spec.ts
  - Verify: jev.spec 갱신(:95 의도된 변경) + nano 타임아웃 → 키워드
- [ ] **T4 (P1, human: ~3h / CC: ~20min)** — location-turn — 판정 감정을 t0 에 kwType 으로 시작(RULE_FREE 제외), 재작성 후 finalize, 낡은 주석 정정
  - Surfaced by: R1 / Section 1-1·1-2 / Section 2-4
  - Files: server/src/turns/location-turn.service.ts
  - Verify: 전체 jest, `[TurnTiming:POST]` intent·challengeWait 전후 비교
- [ ] **T5 (P2, human: ~4h / CC: ~30min)** — 검증 — 판정 nano kwType 힌트 vs 최종 actionType 힌트 재생 A/B(FREE/CHECK ≥90%·contentSafety 누락 0)
  - Surfaced by: R1 accepted scope / Section 3 [→EVAL]
  - Files: 스크래치 재생 스크립트(레포 밖)
  - Verify: 일치율 표
- [ ] **T6 (P2, human: ~1h / CC: ~15min)** — 배포 검증 — 빌드·재시작·스모크 + 직접 입력 5~10턴 형식 플레이테스트 TurnTiming
  - Surfaced by: Section 4-2 [re-measure before gate]
  - Files: 없음
  - Verify: POST intent+challengeWait 중앙값·최대

## Unresolved decisions

없음.

## Completion summary

- Step 0: Scope Challenge — scope accepted as-is (원안 접근은 D1 로 교체, 기능 범위는 동일)
- Reality rows: 7/7 applicable rows emitted, 0 unverified premises
- Architecture Review: 3 issues found
- Code Quality Review: 4 issues found
- Test Review: diagram produced, 9 gaps identified
- Performance Review: 1 issue found
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 0 items proposed to user
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: codex, unavailable (계정 미지원 모델 gpt-6-astra, 네이티브 대체 도구 없음)
- Parallelization: 1 lane, 0 parallel / 1 sequential
- Lake Score: 0/3 = answers picking a 10/10 option / answers scored for Completeness (세 질문 모두 최고 점수가 9/10 — 10/10 선택지 없음)

## 구현 결과 (2026-10-12)

T1~T4 구현(서버 테스트 3,259 통과):
- `LlmCallerService.call(request, stage, opts?)` — 요청 단위 `maxRetries`·`fallback`(기본값 = 현행).
- `ChallengeClassifierService.startAppraisal`/`finalize` 분리, `classify = finalize(ctx, null)`. 판정 nano 2.5초 단일 시도(재시도·fallback 없음). 기존 스펙 27건 무수정 통과 + 신규 5건.
- `LlmIntentParserService` — 의도 JEV·nano 동시 시작, 상한 2.5초, 키워드 결과 콜백(`onKeywordResult`). jev.spec 의 "nano 미호출" 단언 2건은 R3 의 의도된 변경으로 "호출되지만 결과 미사용"으로 갱신.
- `location-turn` — 키워드 결과 콜백에서 판정 감정 시작, 재작성 후 `finalize(최종 ctx, 감정)`.

T5 재생 A/B (최근 60일 직접 입력 원문 577건, gpt-4.1-nano, 실제 판정 프롬프트·파서):
| 지표 | 결과 | 게이트 |
|---|---|---|
| 키워드 actionType ≠ 최종 actionType | 269/577 (46.6%) | — |
| FREE/CHECK 일치(불일치 턴 120건 표본, 최종 RULE_CHECK 고정 반영) | 93.3% | ≥ 90% ✅ |
| 같은 프롬프트 2회 잡음 기준선 | 97.5% | — |
| plausibility 일치 | 98.3% | ≥ 85% ✅ |
| contentSafety 일치 | 100% (누락 0) | 누락 0 ✅ |

불일치 8건은 방향이 고르게 갈린다(FREE→CHECK 4, CHECK→FREE 4) — 그중 3건은 최종 힌트끼리도 갈린 잡음. 운영에서는 판정 JEV(최종 actionType)가 확신 시 덮어써 차이가 더 줄어든다. 키워드 행동 유형이 절반 가까이 틀려도 판정이 거의 안 바뀌는 건, 판정 프롬프트가 행동 유형이 아니라 행동 성격으로 판단하기 때문이다(리뷰 Scope Challenge 1 의 전제 확인).

T6 배포 실측 (운영 서버 재시작 후 같은 직접 입력 10턴 프로브, run c91a2d64 vs 이전 d2acc8dd — 장소 턴 8개):
| 구간 | 이전 | 이후 |
|---|---|---|
| POST 의도 | 평균 2.18s (0.4~5.0) | 평균 1.17s (0.47~2.50) |
| POST 판정 대기 | 평균 1.45s (0.8~2.2) | 평균 0.38s (0.16~0.56) |
| POST 합계 | 2.7~7.2s | 1.1~2.9s |
| 첫 글자(클라이언트) | 평균 9.2s · 중앙값 8.1s | 평균 6.1s · 중앙값 5.9s |

T11 은 의도 nano 가 2.5초 상한에 걸려 키워드 결과로 진행(이전 같은 턴은 5초 타임아웃). 판정 nano 대체값 발생 0건. 남은 첫 글자 지연의 큰 몫은 워커 사전 결정(1.6~3.2s)과 서술 첫 조각(1.5~3.2s) — arch/141 남은 작업 3·5번.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | codex (`/plan-eng-review` outside voice) | Independent 2nd opinion | 1 | unavailable | 계정 미지원 모델 gpt-6-astra(400) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN | 17 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** codex, plan-review, unavailable(모델 미지원·네이티브 대체 도구 없음), 발견 없음.
- **VERDICT:** CLEAR 된 리뷰 없음 — Eng Review 는 17건을 구현 과제(T1~T6)로 매핑했고 미결 결정은 0건. eng review required (구현 후 `/review` 로 diff 리뷰 예정).

NO UNRESOLVED DECISIONS

