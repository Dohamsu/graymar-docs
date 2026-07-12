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

## 부록 C — 4차 완주 평가 + 카드 재결정 순서 수정 (2026-07-12, server 83038d2)

### 4차 엔딩 완주 런 (28턴, 8/9)

- nano 감사 수정 유지 확인: reaction fallback 0(재시도 3회 전부 구제),
  이중 스트리밍 0. 자기소개 2/2 자연 성사(역할 맥락 포함 — "은장부 상단에서
  회계를 맡고 있는 에드릭 베일이라 하오"), 피날레 작동.
- **첫 관측 2건**: incident 기반 조기 엔딩(S3에서 28턴, 아크 "황금빛 그림자"
  — 설계된 경로, 빈도는 기획 판단 여지) + LOCATION 장비 드랍 실동작
  (EQ_RUSTY_BLADE — P4 드랍 경로 첫 실증).

### V8 실패 추적 → 카드 재결정 순서 결함 (T20)

audit "T15"는 내부 인덱스 — 실제 대상 T20에서 **서버 실결함 재확정**:
DB 최종 카드=브렌 유지, 서술=토브렌 자기소개만. 근본 원인은 **순서** —
카드 재결정(5.9)이 자기소개 삽입(5.11)보다 앞이라 후단 생성 마커가
판정에 반영될 수 없는 구조 (부록 A의 수집·경계 수정으로도 못 잡는 층위).

**수정**: 재결정 블록(164줄)을 후처리 최후단(5.13, narrative 최종본 확정
이후·DONE 직전)으로 이동 — 블록의 목적("최종본 기반 재결정")에 위치가
비로소 부합. `[CardResolve]` 결정 로그 3분기(교체/제거/마커0 유지·제거)
신설 — 경로상 설명 불가한 잔여 케이스 재현 시 즉시 원인 확정.

검증: 1016 passed(실패 0 유지) + 실런 9/9, 카드 표시 3턴 전부 정합
(CardResolve 무발동 = 재결정 개입 불필요의 정상 신호).

## 부록 D — 자유 입력 대화 검증 + 4건 수정 (2026-07-12, server 7157617)

### 검증 방법

봇 고정 문구가 아닌 **실제 유저 방식의 자유 문장 10턴** — 인사→개방 질문→
직전 답변 이어받기→화제 전환→사과→작별→비대화 행동→재대화. 응답을 읽고
다음 입력을 결정하는 인터랙티브 진행.

### 건재 확인 (대사 내용 층)

문답 정합(개방 질문·화제 전환·개인 질문), 감정 반응(사과→태도 완화),
작별 인식(FAREWELL 감지+fact 스킵+품격 응답), 캐릭터 일관(에드릭 회계
은유 전 턴 유지), 맥락 단어 추적 — 전부 견고.

### 발견 4건 → 수정

| 실측 | 수정 |
|------|------|
| T5 "부두 노동자들**에게** 얼마나 쥐여줘야…"(3인칭 질문)가 하를룬 소환 + "그 정도면 충분한 액수요" 문답 비정합 | ①-a MENTION_QUESTION_RE에 얼마나/[가이] 말한 계열 추가 + **가드를 1b 호명 조사·MEDIUM 역할 키워드 경로로 확장** (정당한 "~에게 말을 건다" 전환은 보존) |
| T5 기록=에드릭 vs 표시=하를룬 분리 → T6 잠금 혼선 (대화 상대 핑퐁) | ①-b buildLocationResult의 레거시 extractTargetNpcFromInput **재계산 제거** — resolver 동기화 값(event.payload.primaryNpcId) 단일 소스. 단일 권한자(arch/49) 원칙의 잔존 이원화 해소 |
| T8 작별 교환 직후 "반갑소, 만나게 되어 기쁘오" 자기소개 삽입 (맥락 역전) | ② FAREWELL 턴 소개 비활성 (엔딩 턴 가드와 동일 패턴) — pendingIntroduction 이월로 다음 등장 턴 재시도 |
| T9 직전 대사 복창 (이어받기 지시에도 확률적 위반) | ③ [DialogueRepeat] 감지 센서 — 빈도 계측 후 강개입 판단 |

### 재검증 (동일 시나리오 재현)

- T5 유형: **에드릭 유지** + 3인칭 질문 정합 응답("노동자들에게 돈을
  쥐여준다고 해서 입을 열 자가 어디 있겠소")
- T10 유형("~가 말한"): **가드 발동 로그**(CONVERSATION_LOCK lock=true)
  + 잠금 유지 + 정합 응답
- 회귀: FAREWELL 소개 미발화 + 가드 3건(재현·정당 전환 보존), 1020 passed

부수: prompt-builder `typeof this` 타입 표기가 빌드 특이점 유발 — 명시
타입으로 교체.

## 부록 E — 전 장소 순회 자유 대화 검증 + LockSeed (2026-07-12, server 54461a3)

### 순회 검증 (시장→경비대→항만→빈민가, 자유 문장 12턴)

- **어체 4종 전환 전부 정확**: 렌닉(하오+능글)·마이렐(하오+위엄)·하를룬
  (하오+형제)·골목 아이(반말). 장소 간 이월 0, 이어받기·되질문 처리·호의
  행동 반응성(빵값→경계 해제 "아까는 내가 좀 예민했어") 우수. 자기소개
  2건 성사(레닉 삽입·하를룬 자연). 3인칭 언급 가드 유지 확인.

### 발견 ① → LockSeed 수정

"나는 **떠돌이** 용병이오"(자기 지칭)가 취객(VAGRANT)을 소환해 마이렐
대화 단절 — 근본 2겹: (a) 진입 직후 첫 대화 턴은 이벤트 미배정으로
primaryNpcId=null 기록, 워커 carry-over가 serverResult만 고치고
**actionHistory에는 null 잔존** → 다음 턴 잠금 미형성, (b) 잠금 공백에
이벤트 자유 배정 침입.

**수정**: carry-over 시 같은 턴 actionHistory 엔트리의 primaryNpcId를
CAS 채널로 보충 ([LockSeed] 로그). 재현 검증: 동일 입력에서 마이렐 유지
+ 정합 응답 ("용병이라니, 그대의 말에 무게가 실리는구려").

### 잔여 관찰 → 후속 수정 대상

- ② 유저가 밝힌 자기 정보("처음 온 사람")를 NPC가 기억하지 못함
  ("그대도 오래 계셨다면" 모순)
- ③ 플레이어→NPC 금전 증여 서술("이걸로 빵 사 먹으렴")이 골드 미차감으로 수용
