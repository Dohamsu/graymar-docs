# 119 — JEV 완전 판단 대체 계약 검토

2026-09-22. 소스 기반 설계 검토. 운영 변경·API 호출·로컬 게임 실행 없음. 사용자 우선순위: 비용보다 속도, 정확도, 확장성. 순서: Challenge 전체 판단 → 발화자 식별. 아래 제안은 아직 채택/배포된 계약이 아니다.

## 결론

Challenge는 문구 생성 호출이 아니라 거의 전부 닫힌 판단이다. JEV 한 번의 다중 질문으로 바꾸는 실험이 적절하다. 다만 FREE/CHECK만 정확해서는 충분하지 않다. 세계 경계, 안전성, 수치 보정, 사회적 인상, 서술 의미 단서가 모두 소비된다. 정상 경로에 nano를 남기지 않고 전체 계약을 평가해야 한다.

발화자 식별은 순수 선택형 대체에 적합하나 현재 nano 1회뿐 아니라 미할당 대사에 서브 생성 모델 검증까지 있다. 둘 다 제거해야 완전 대체다. 스트리밍은 이미 이 호출들을 건너뛰므로 이 경로에 JEV를 추가해서는 안 된다.

## 1. 현재 Challenge 계약과 소비처

| 필드 | 실제 역할/보존 조건 | 소스 |
|---|---|---|
| result | FREE는 단순 무판정이 아니라 자동 성공으로 연결된다. refused/noGain 분기가 먼저 적용돼야 한다. | [location-turn:3329](../server/src/turns/location-turn.service.ts#L3329) |
| statHint | str/dex/wit/con/per/cha 또는 null. 실제 행동의 스탯으로 기본 actionType 매핑을 덮는다. | [classifier:458](../server/src/llm/challenge-classifier.service.ts#L458), [resolve:110](../server/src/engine/hub/resolve.service.ts#L110) |
| difficultyMod | [-2,+2] 정수. 양수는 쉬움, 음수는 어려움. 실제 주사위 보정과 UI 내역에 반영된다. | [classifier:463](../server/src/llm/challenge-classifier.service.ts#L463), [resolve:139](../server/src/engine/hub/resolve.service.ts#L139) |
| plausibility | NORMAL/UNUSUAL/IMPLAUSIBLE/OUT_OF_SCOPE. 뒤 두 경우 noGain, 서술 치환/거절에 영향. OUT_OF_SCOPE는 FREE 강제. | [classifier:340](../server/src/llm/challenge-classifier.service.ts#L340), [boundary:236](../server/src/turns/world-boundary.core.ts#L236), [location-turn:4164](../server/src/turns/location-turn.service.ts#L4164) |
| physicalImpact | 흔적 추출 실행 여부와 서술 소란 가이드에 영향. IMPLAUSIBLE/OUT_OF_SCOPE는 false 강제. | [classifier:478](../server/src/llm/challenge-classifier.service.ts#L478), [worker:2552](../server/src/llm/llm-worker.service.ts#L2552), [prompt:2635](../server/src/llm/prompts/prompt-builder.service.ts#L2635) |
| socialImpact | 다섯 축 정수 [-5,+5]. ACTION 자유입력에서만 감정 보정. null은 기본 테이블100%, 객체는 round(base×0.4+impact×2), 이후 판정/직접대상 배율을 적용한다. | [classifier:485](../server/src/llm/challenge-classifier.service.ts#L485), [location-turn:1633](../server/src/turns/location-turn.service.ts#L1633), [emotion:76](../server/src/engine/hub/npc-emotional.service.ts#L76) |
| safetyCategory | NONE 또는 정책상 4개 범주. 서버가 정책을 매핑하고 refused 경로로 모든 델타를 차단한다. 모델이 정책 문자열을 직접 정하지 않는다. | [classifier:146](../server/src/llm/challenge-classifier.service.ts#L146), [safety:234](../server/src/turns/content-safety.core.ts#L234), [location-turn:3297](../server/src/turns/location-turn.service.ts#L3297) |
| reason/source | 로그 외에 source=llm인 reason을 appraisalNote로 전달, 메인 서술에 행동 성격 단서로 주입한다. rule의 특정 reason은 NPC 추궁성 감정 룰에도 사용된다. 단순 삭제/소스 이름 교체는 의미 손실 가능. | [location-turn:4181](../server/src/turns/location-turn.service.ts#L4181), [prompt:2401](../server/src/llm/prompts/prompt-builder.service.ts#L2401), [location-turn:1651](../server/src/turns/location-turn.service.ts#L1651) |

현재 ACTION은 이벤트 매칭과 병렬로 조기 분류를 시작한다. 실제 입력의 NPC posture와 eventTitle은 null이며 이름도 조기 텍스트 매칭에 의존한다. CHOICE/SYSTEM은 이 모델을 호출하지 않는다. 평가에서 최종 이벤트·최종 화자 정보를 제공하면 운영보다 유리한 실험이 된다. [location-turn:3074](../server/src/turns/location-turn.service.ts#L3074)

현재 JEV는 회색지대 result만 nano와 병렬 분류하고, FIGHT/STEAL/SNEAK/THREATEN/BRIBE/PERSUADE는 JEV result 호출조차 생략한다. 전체 대체 평가는 이 강행동의 현실성·안전성까지 포함해야 한다. [classifier:210](../server/src/llm/challenge-classifier.service.ts#L210), [classifier:245](../server/src/llm/challenge-classifier.service.ts#L245)

## 2. 제안: 단일 요청의 닫힌 Challenge 계약

기존 JEV 서비스는 질문 이름별 choice와 confidence를 지원한다. 자유 문자열 설명을 생성시키지 않고 아래 선택지를 한 요청으로 묶는다. [JEV 계약](../server/src/llm/jev-decision.service.ts#L4)

| 질문 | 정확한 선택 집합 | 서버 어댑터 |
|---|---|---|
| challenge | FREE, CHECK | 기존 result |
| stat | DEFAULT, STR, DEX, WIT, CON, PER, CHA | DEFAULT→null, 나머지 소문자 |
| difficulty | VERY_EASY, EASY, NORMAL, HARD, VERY_HARD | +2,+1,0,-1,-2 |
| plausibility | NORMAL, UNUSUAL, IMPLAUSIBLE, OUT_OF_SCOPE | 그대로 |
| physicalImpact | NO, YES | boolean |
| safety | NONE, SEXUAL_EXPLICIT, MINOR_HARM, GRATUITOUS_CRUELTY, SELF_HARM | NONE→undefined, 나머지는 기존 정책 매핑 |
| socialTrust/socialFear/socialRespect/socialSuspicion/socialAttachment | NEG_5,NEG_4,NEG_3,NEG_2,NEG_1,ZERO,POS_1,POS_2,POS_3,POS_4,POS_5 | 정수 -5…5, 클램프 후 전축0이면 null |
| actionMeaning | ORDINARY, INFORMATION_SEEKING, PERSUASION, THREAT, DECEPTIVE_SPEECH, FEIGNED_ACTION, PHYSICAL_ACTION, GOODWILL, SOCIAL_ODDITY, IMPOSSIBLE_EFFECT, WORLD_EXIT, SYSTEM_REQUEST, OTHER | 고정 한국어 의미 문안. OTHER는 구체 설명 없이 기존 일반 가이드 유지 |

이 계약은 12개 질문이다. 축별 신뢰도·오류·채택 여부를 기록하되, 특정 축만 기존 nano에 추가로 묻는 운영 경로는 만들지 않는다. reason 자유 생성 대신 actionMeaning 고정 문안을 사용한다. DECEPTIVE_SPEECH/FEIGNED_ACTION은 말한 내용과 실제 현상을 분리하는 의미를 반드시 보존한다. 기존 프롬프트에도 이 일반 가드가 있으므로 임의의 원문 재인용은 필요 없다. [prompt:2396](../server/src/llm/prompts/prompt-builder.service.ts#L2396)

서버 모델 provenance와 의미 단서를 분리하는 확장 인터페이스가 좋다. 예: source는 기존 rule/llm/fallback을 유지하면서 provider=jev, contractVersion, reasonCode를 별도 기록한다. 기존 rule reason 조건을 함부로 문자열 코드로 바꾸지 않는다. 처음 비교 실험은 운영과 동등한 수치 범위를 유지하고, 사회적 인상을 몇 가지 프로필로 축소하는 밸런스 변경은 별도 실험으로 분리한다.

### 필수 안전 게이트

1. 질문 누락, 미지 선택, 비정상 신뢰도, timeout은 전체 계약 오류로 기록. 안전/현실성 미확정을 NONE/NORMAL로 조용히 승격하지 않는다.
2. 기존 L1 세계 경계/안전 룰을 모델보다 우선한다. 현재 경계 적용 후 안전 적용이며 OUT_OF_SCOPE는 safety 함수에서 그대로 반환하는 정책이다. 이 우선순위의 변경은 모델 대체와 분리해서 검토한다. [location-turn:3290](../server/src/turns/location-turn.service.ts#L3290), [safety:268](../server/src/turns/content-safety.core.ts#L268)
3. 강행동 CHECK, OUT_OF_SCOPE FREE, 양쪽 경계 physicalImpact=false, IMPLAUSIBLE positive trust=0, refused/noGain 우선순위를 어댑터·소비처 전체에서 검증한다. L1 경계 룰은 spread로 기존 부가 필드를 보존하므로 모델 단계만 정규화하는 것으로 충분하지 않다. [boundary:185](../server/src/turns/world-boundary.core.ts#L185)
4. socialImpact가 최종 전축0이면 null이어야 한다. 특히 trust 차단 이후 재정규화한다. 기존 구현은 trust 차단 전에 nonZero를 계산하므로 이 모서리에서는 영벡터 객체가 남을 수 있다. 이를 고치면 기존 동작과 달라짐을 평가에 명시한다. [classifier:490](../server/src/llm/challenge-classifier.service.ts#L490)
5. 운영 비상경로를 사전에 정한다. CHECK 기본값은 안전성 fallback이 아니며, safety/현실성 누락을 가린다. 완전 nano-free 장애 대응은 무상태변경/재시도 안내 같은 명시 정책이 필요하다. 기존 nano 전체 호출 복귀를 택하면 그것은 예외 fallback이지 완전 무호출 보장은 아니다. 평가에서 timeout을 제외하지 않는다.
6. 한 축 오판의 영향이 다르다. 안전 누락/세계 밖 보상/거짓 현상 실체화는 중대 오류로 별도 0건 게이트; stat/difficulty는 허용 답 집합과 오차, social은 최종 감정 delta·부호로 평가한다. nano 일치율은 정답률이 아니다.

## 3. 발화자 계약과 숨은 fallback

모델 판별은 NPC 상태가 있고 JSON 파싱 서술이 아니며 대사가 있는 경우에만 들어간다. 스트리밍은 미표시 대사의 regex 백필만 하며 모델 호출은 없다. [postprocess:120](../server/src/llm/worker/narrative-postprocess.service.ts#L120), [postprocess:261](../server/src/llm/worker/narrative-postprocess.service.ts#L261)

현재 후보는 npcStates+eventNpcIds 앞 15개다. 별칭, 실명, role은 있으나 gender는 모델 프롬프트에 명시되지 않는데 성별 필터 규칙은 요구한다. 무단서 첫 NPC fallback도 배열 첫 NPC와 서버 primaryNpcId가 같다는 보장이 없다. [postprocess:177](../server/src/llm/worker/narrative-postprocess.service.ts#L177), [postprocess:184](../server/src/llm/worker/narrative-postprocess.service.ts#L184), [postprocess:280](../server/src/llm/worker/narrative-postprocess.service.ts#L280)

현재 nano 반환 NPC_ID는 형태만 검사하며 실제 후보 포함 여부를 확인하지 않는다. 실명/별칭 DB 매칭은 전체 NPC DB에서 한다. 한글 호칭도 substring 비교가 남아 있다. 새 closed-choice 계약은 이 동작을 그대로 복제하지 않고 정확한 후보집합 검증으로 좁혀야 한다. [postprocess:323](../server/src/llm/worker/narrative-postprocess.service.ts#L323), [postprocess:349](../server/src/llm/worker/narrative-postprocess.service.ts#L349)

미할당 대사가 1~4개면 marker-verify라는 별도 생성 모델을 호출한다. 일부만 할당돼도 nanoSuccess=true가 되어 regex fallback을 전체 생략한다. 완전 대체 비교는 nano batch 단독이 아니라 이 검증 호출까지 포함한 기존 전체 체인과 비교해야 한다. [postprocess:375](../server/src/llm/worker/narrative-postprocess.service.ts#L375), [postprocess:510](../server/src/llm/worker/narrative-postprocess.service.ts#L510)

### 제안 계약

- 요청 state: 각 대사 index, 기존과 같은 앞120자/대사50자/뒤40자, candidate IDs와 알려진 alias/name/role, 명시적 primaryNpcId. 공정 1차 비교에서는 같은 문맥량; 확대 문맥은 후속 실험.
- 질문: dialogue_0, dialogue_1… 각각 `NPC_<candidate id> | UNKNOWN`. 후보 밖 ID, 임의 한글 호칭 생성은 금지. NPC 수0이면 요청하지 않는다.
- 별칭 매핑은 서버 소유. 같은 별칭의 다중 후보는 primary 힌트만으로 확정하지 않고 UNKNOWN 허용. 플레이어 말, 서술 인용, 현재 후보에 없는 인물도 UNKNOWN으로 처리.
- 후보순서를 섞어도 선택이 유지되는지 검증. primary와 등장 인물을 먼저 확보하고 15개 한도 내 포함시킨다. 후보 자체 변경의 효과는 모델 변경과 구분해 기록한다.
- 정확 일치 검증 및 대사별 신뢰도 미달은 서버 regex의 고신뢰 배정만 사용하거나 미할당 유지. 부분 채택 때도 미할당 대사만 fallback 처리. nano/marker-verify를 이어 호출하지 않는다.
- 스트리밍의 model call0 유지, JSON/masked marker/짧은 대사/입력 인용 필터 유지. 사용자에게 노출되는 이름은 기존 introduced/unknownAlias 정책의 후속 변환을 보존한다. [postprocess:210](../server/src/llm/worker/narrative-postprocess.service.ts#L210), [postprocess:528](../server/src/llm/worker/narrative-postprocess.service.ts#L528), [postprocess:558](../server/src/llm/worker/narrative-postprocess.service.ts#L558)

## 4. 평가에서 별도로 표시할 미확인 사항

- 현재 계약 입력에는 최근 발화, 실제 NPC 자세, 현재 재고/장비, 확정 이벤트가 없다. 대명사·생략 행동·대상 상태가 필요한 사례의 한계는 모델 탓과 입력 부족을 분리한다.
- 합성 기준은 허용 답 집합과 작성 근거가 필요하다. 실제 운영 로그/첫 서술 시간/완료시간 검증을 수행하지 않았다면 그렇게 명시한다.
- Challenge는 이벤트 매칭과 이미 병렬이다. 개별 분류 ms 개선이 전체 첫 서술 시간을 같은 만큼 줄인다는 주장은 할 수 없다.
- speaker는 서술 후처리이므로 주로 완료/저장 지연에 영향. 스트리밍 첫 토큰 속도 향상 후보로 설명하면 부정확하다.
- JEV 질문 수 증가에 따른 실제 지연, 신뢰도 보정, 오류율은 이번 소스 검토만으로 알 수 없다. 다중축 API 평가가 필요하다.
- 신규 NPC 반응·대사·기억·흔적 문구 생성은 이번 대체 범위 밖이다. physicalImpact 판단을 바꿔도 DONE 이후 흔적 추출 nano까지 없애는 작업은 아니다.

## 권고 판정

전체 Challenge 다중질문 실험부터 시행하되 정확도와 latency를 함께 평가한다. 통과 전에는 운영의 nano를 제거하지 않는다. 이후 speaker를 별도 batch로 평가하고, 실제 스트리밍 호출에는 새 분류를 추가하지 않는다. 모든 모델은 판단만 제안하고 정책·수치 적용·표시명 결정은 서버 정본으로 유지한다.
