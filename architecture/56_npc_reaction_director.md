# A56 — NPC Reaction Director + 어휘 폭주 해소

> **상태**: ✅ 구현됨 (server commit 37b4d83 + 4e3d85c, graymar 22aca6a) — 2026-05-04
>
> **목적**: NPC가 진짜 사람처럼 "성격/어조는 고정, 매번 다른 대화, 매번 다른 기억"을 하도록 LLM 파이프라인을 강화한다.

## 배경 — 어휘 폭주 문제

playtest 분석에서 NPC 대화에 일관된 패턴 발견:
- 회계사 에드릭이 "수지가 맞지 않다 / 셈이 맞지 않다" 5턴+ 반복 (시그니처 어구율 39.7%)
- 마이렐 단 경이 "쓸데없는 ___ 시간을 낭비하지 마시오" 4턴 동일 구조
- 동일 제스처 ("안경테를 밀어 올린다") 5턴+ 반복

근본 원인 진단 (5회 A/B 검증으로 추적):
- 콘텐츠 작가가 어조 가이드를 명확히 하려고 `personality.signature` 배열 + `personality.speechStyle` 본문에 **구체 어구 예시**를 박았음
- 메인 LLM이 이 예시를 "권장 사용 표현"으로 해석하여 매 턴 직접 인용 → anchor 효과
- "가끔 사용하라" 같은 soft 지시는 LLM이 무시 (CLAUDE.md "LLM 설계 원칙" #4 패턴)

## 설계 요약 — 4가지 통합 작업

### 1. NpcReactionDirector (nano LLM) — server/src/llm/npc-reaction-director.service.ts

메인 서술 LLM 호출 전에 nano LLM 1회 추가하여 NPC 반응 + 즉시 목표 + 추상 톤 3축을 사전 결정한다. 메인 LLM은 "추측"이 아닌 "결정된 반응"을 받아 표현만 한다.

**입력 (NpcReactionContext)**:
- NPC 프로필: personality.core / role / speechStyle / signature
- 감정 상태: NpcEmotionalState (trust/fear/respect/suspicion/attachment)
- 상황: rawInput / actionType / resolveOutcome / locationName / hubHeat
- 직전 컨텍스트: recentNpcDialogue / sceneSummary

**출력 (NpcReactionResult)**:
```typescript
{
  reactionType: 'WELCOME' | 'OPEN_UP' | 'PROBE' | 'DEFLECT'
              | 'DISMISS' | 'THREATEN' | 'SILENCE',
  refusalLevel: 'NONE' | 'POLITE' | 'FIRM' | 'HOSTILE',
  immediateGoal: string,        // NPC가 이 대화에서 원하는 것 (15~30자)
  openingStance: string,        // NPC 첫 반응 행동 (10~25자, 외면적)
  emotionalShiftHint: { trust, fear, respect, suspicion },  // 각 -3~3
  dialogueHint: string,         // NPC 말할 의도 방향 (20~40자, 대사 X)

  // ⚠️ 추상 톤 3축 — 예시 절대 없음, 추상 묘사만
  voiceQuality: string,         // 목소리 질감 (15~25자)
  emotionalUndertone: string,   // 감정 저류 (15~25자)
  bodyLanguageMood: string,     // 신체 분위기 (10~20자)
}
```

**핵심 원칙**:
- 구체 어휘/대사 예시 절대 출력 금지 (LLM 자유 변형 공간 확보)
- 톤/분위기/질감만 추상적으로 묘사
- 메인 LLM이 자유롭게 어휘 선택

**환경변수**: `NPC_REACTION_DIRECTOR_ENABLED=true|false` (기본 true)

**Fallback**: LLM 실패/타임아웃 시 posture + resolveOutcome 기반 안전 결정 (HOSTILE+FAIL → THREATEN+HOSTILE 등)

### 2. ChallengeClassifier (nano LLM) — server/src/llm/challenge-classifier.service.ts

ResolveService 호출 직전에 nano LLM이 "이 행동에 저항/결과 분기가 있는가"를 분류. FREE면 주사위 스킵, CHECK면 정상 1d6 판정.

**룰 1차 게이트 (LLM 호출 0)**:
- `NON_CHALLENGE_ACTIONS` (MOVE_LOCATION/REST/SHOP/EQUIP/UNEQUIP) → 즉시 FREE
- `ALWAYS_CHALLENGE_ACTIONS` (FIGHT/STEAL/SNEAK/THREATEN/BRIBE/PERSUADE) → 즉시 CHECK
- 회색지대 (TALK/OBSERVE/INVESTIGATE/SEARCH/HELP/TRADE) → nano LLM 호출

**입력**: rawInput / actionType / targetNpcName / posture / locationName

**출력**: `{ result: 'FREE' | 'CHECK', reason, source: 'rule' | 'llm' | 'fallback' }`

**효과**: "태양을 본다", "안녕이라고 인사한다" 같은 비도전 행동에 dice 안 굴림 → 자유 행동의 자연스러운 SUCCESS.

**환경변수**: `CHALLENGE_CLASSIFIER_ENABLED=true|false` (기본 true)

### 3. speechStyle 어구 예시 추상화 — content/graymar_v1/npcs.json

콘텐츠 작가가 정체성 가이드로 박아둔 어구 예시가 LLM의 anchor가 되는 문제 해결. 9 NPC `personality.speechStyle`에서 따옴표로 인용된 구체 어구를 모두 제거하고 추상 어조 가이드만 유지.

**수정 NPC 9명**:
- CORE 6: NPC_HARLUN, NPC_EDRIC_VEIL, NPC_MAIREL, NPC_LORD_VANCE, NPC_RAT_KING, NPC_RONEN
- SUB 3: NPC_MOON_SEA, NPC_OWEN_KEEPER, NPC_GUARD_FELIX

**원칙**:
- 따옴표 인용 어구 예시 제거
- 어조/어미/속도/태도/금지 사항 유지
- 화제 카테고리는 유지 ("도박/회계 농담"은 카테고리, "수지가 맞지 않는"은 어구 예시)
- "구체 숫자 인용" 같은 메타 가이드는 유지

**예시 비교**:
```
[변경 전] NPC_MAIREL.speechStyle:
  "...회피 어휘 대신 군인 직설 — '낭비 마시오', '시간을 헛되이' 등."

[변경 후] NPC_MAIREL.speechStyle:
  "...회피 어휘 대신 군인 직설로 시간·효율·기강을 강조한다 (같은 표현 반복 금지)."
```

### 4. 마커 substring 합쳐짐 방어 — server/src/llm/llm-worker.service.ts

LLM 출력 별칭이 NPC unknownAlias와 substring 충돌하여 잘못 합쳐지는 버그 방어:

**버그 사례**:
```
[LLM 원문]    "잠긴 닻 선술집 주인: \"...\""
[잘못된 결과] "@[넉넉한 체구의 선넉넉한 체구의 선술집 주인|owen.webp]"
              "선술집 주인" 공통 substring으로 두 별칭이 잘못 결합
```

**방어 메커니즘** (5.5 단계 끝에 통합):
1. **감지**: `@[X|...]` 별칭 안에 동일 substring(8자+) 2회 등장하면 합쳐짐 의심
2. **자동 복구**: 알려진 NPC unknownAlias 중 별칭에 부분 포함된 것을 정상 별칭으로 복원
3. **로깅**: `[MarkerCollision]` 경고 로그로 발생 상황 추적

## 검증 결과 (5회 A/B)

| 지표 | baseline | 최종 (4가지 통합) | 개선 |
|---|---|---|---|
| 시그니처 어구율 (수지/셈/맞지) | 39.7% | **6.2%** | -84% |
| 마이렐 패턴 반복 | 9.7% | **0%** | 완전 제거 |
| 안경테 제스처 반복 | 5턴+ | **0%** | 완전 제거 |
| TTR (어휘 다양성) | 0.7518 | **0.8085** | +0.057 |
| 고유 단어 수 | 181 | **209** | +15% |
| 최대 3-gram 반복 | 1.7 | **0** | 완전 제거 |
| 최대 2-gram 반복 | 4.6 | **0** | 완전 제거 |
| V8 NPC 정합성 (마커 합쳐짐 후) | 일부 실패 | **100% PASS** | 완전 해소 |

**일반 시나리오 검증** (3회, 다양한 행동):
- 시그니처율 7.3% (baseline -82%)
- 11명 NPC 모두 자기 정체성 유지하면서 매번 다른 표현
- TTR 0.86~0.92 (매우 높은 다양성)

## 시도 후 폐기된 접근 (P0 검증으로 데이터 기반 폐기)

### NpcSignatureGenerator (B안) — 폐기
nano LLM이 매 턴 vocabHints (어구 변형 예시) 생성. 메인 LLM에 노출.
- **문제**: vocabHints 자체가 또 다른 anchor 역할. 5회 A/B 결과 효과 없음 또는 부정적
- **결론**: "예시 풀을 동적 생성해도 LLM은 그 풀에 묶임"

### SIGFIX (signature를 회피 리스트로 변환) — 부분 효과
positive 노출("가끔 사용하라") → negative 노출("이번 턴 절대 사용 금지").
- **결과**: 시그니처율 39.7% → 29.0% (27% 개선)
- **한계**: 작가가 만든 정적 풀에 여전히 의존 → A_REMOVE(노출 자체 제거)가 더 우수

### MEMBOOST (재등장 시 회상 명시 가이드) — 의도와 반대 효과
재등장 NPC에 "직전 대화 회상하세요" 명시 지시.
- **결과**: 시그니처율 16.7% → 29.2% (악화), 기억 회상률 26.4% → 18.5% (악화)
- **원인**: "회상하세요" 명시 지시가 LLM에 부메랑 — 이전 대사 단편 끌어오면서 시그니처 어구도 함께 등장
- **결론**: 명시적 회상 지시는 역효과. 자연스러운 회상은 LLM이 충분한 컨텍스트만 받으면 알아서 함.

## 데이터 흐름 — 강화된 LLM 파이프라인

```
턴 진입 (turns.service.ts)
  ↓
IntentParserV2 → actionType + targetNpcId
  ↓
EventMatcher → primaryNpcId
  ↓
NpcResolver (5단계 우선순위)
  ↓
ChallengeClassifier (nano LLM)
  ├─ 룰 게이트 (NON_CHALLENGE / ALWAYS_CHALLENGE)
  └─ 회색지대 → nano LLM ⇒ FREE | CHECK
  ↓
ResolveService
  ├─ FREE → buildAutoSuccess() (주사위 스킵)
  └─ CHECK → 1d6 + stat 판정
  ↓
DB commit → ServerResultV1 응답 즉시 반환
  ↓
[비동기 LLM Worker]
  ↓
NanoEventDirector (이벤트 컨셉)
  ↓
NpcReactionDirector (반응 + 즉시목표 + 추상톤 3축) ← 신규
  ↓
NanoDirector (legacy fallback)
  ↓
PromptBuilder
  ├─ 시스템 프롬프트
  ├─ Memory 블록 (L0~L4)
  ├─ NpcEmotional 블록 (signature 노출 제거됨)
  ├─ NpcReaction 블록 (톤 가이드 + 추상)
  └─ ...
  ↓
메인 LLM (Gemma 4 26B MoE — OpenRouter)
  ↓
[5.5 마커 후처리]
  ├─ A 단계: nano DialogueMarker
  ├─ B-0~B-2: 마커 변환
  ├─ NpcMismatch 교정
  └─ MarkerCollision 자동 복구 ← 신규
  ↓
DB persist
```

## 환경변수 토글

```
NPC_REACTION_DIRECTOR_ENABLED=true|false  # 기본 true
CHALLENGE_CLASSIFIER_ENABLED=true|false   # 기본 true
```

둘 다 true가 권장 운영 설정. false로 즉시 롤백 가능.

## 향후 검토 영역

- **personality.signature 배열 안 어구 예시** (14 NPC): 메인 서술 LLM에는 노출 안 됨. 다만 아래 부록에서 실제로 2개의 다른 소비처가 이 배열을 재노출하고 있던 회귀가 발견·수정됨 — "노출 안 됨"은 소비처별로 개별 확인이 필요하다는 교훈.
- **기억 회상률 강화**: A_REMOVE에서 26.4%, ABSTRACT에서 17.5%로 약간 후퇴. 명시 지시(MEMBOOST)가 아닌 다른 접근(예: 컨텍스트 풍부도 향상) 검토 필요.
- **마커 합쳐짐 통계 누적**: `[MarkerCollision]` 로그 카운트로 자동 복구 빈도 모니터링.
- **speechStyle의 문형 단위 앵커** (부록 2, 에드릭 사례): 단어 나열("수지/계산/장부")을 지워도 "회피 어휘 대신 ~가 맞지 않다 식으로 표현"이라는 문형 지시 자체가 남아있으면 풍선효과로 다른 단어("숫자")가 같은 자리를 채운다. 다른 CORE NPC의 speechStyle에도 유사한 "표현 방식(문형)" 지시가 있는지 전수 점검 후, 문형 지시를 특정 템플릿이 아닌 더 열린 형태로 바꾸는 실험이 필요.

## 부록 — signature 노출 재발 발견 및 수정 (2026-07-06)

**발견 경위**: NPC 대사 흐름 점검(성격/어조/단서/언급 프롬프트 배치 감사) 중 코드 대조로 확인.

**재발 지점** — 본문의 "signature 노출 완전 제거"는 메인 서술 LLM 경로(`prompt-builder.service.ts`)에만 적용돼 있었고, 이후 추가된 2개 소비처가 같은 배열을 다시 원문 그대로 노출하고 있었음:

| 파일 | 상태 | 노출 내용 |
|------|------|-----------|
| `npc-reaction-director.service.ts:242-243` | **활성** (`NPC_REACTION_DIRECTOR_ENABLED` 기본 true — 매 턴 실행) | `시그니처: ${ctx.signature.slice(0,3).join(', ')}` — 14개 NPC의 인용구 그대로 nano LLM 프롬프트에 주입 |
| `dialogue-generator.service.ts:298-299` | 휴면 (`LLM_JSON_MODE=false`라 현재 도달 불가, 재활성화 시 즉시 재발) | `시그니처 표현: ${personality.signature.join(', ')}` |

**수정**: 두 파일 모두 해당 라인 삭제 (메인 경로와 동일하게 "참조 자체 제거" 전략 채택 — signature 내용을 추상화하는 대신 speechStyle+core만으로 충분하다고 판단). `llm-worker.service.ts:452`의 `signature` 필드 전달도 함께 제거(죽은 플러밍 정리), `NpcReactionContext.signature` 타입 필드 삭제.

**검증**: 관련 스펙 24개 통과, lint 신규 이슈 0, `pnpm build` 성공. 10턴 플레이테스트 스팟체크(`playtest_20260706_114135.json`, DESERTER/male) — signature 보유 NPC(로넨/에드릭/마이렐/펠릭스) 등장 구간에서 과거 앵커 패턴(에드릭 "수지가 맞지" 반복 등) 재발 없음, V7 프롬프트 누출 없음, V8 NPC 정합성 양호. 8시나리오 정밀 배터리는 회귀 신호가 없어 이번엔 생략.

**결론/교훈**: "signature 노출 제거"처럼 여러 LLM 호출 경로가 같은 콘텐츠 필드를 참조하는 구조에서는, 수정을 한 소비처에 적용했다고 문서에 "완료"로 적기 전에 **해당 필드의 모든 참조처를 grep으로 재확인**해야 한다 (본 세션에서 이전에 발견한 한글 키워드 토크나이저 3중복·`matchParticleAll` 위치 조건 비대칭과 같은 유형의 회귀).

## 부록 2 — NPA 8시나리오 재검증 + 에드릭 speechStyle 단어앵커 발견 (2026-07-06/07)

**목적**: 부록의 signature 리크 fix가 실제 회귀 없이 적용됐는지, architecture/51이 설계한 NPA 8시나리오 배터리 중 fix와 직접 관련된 3개(`chat-edric`/`chat-mairel`/`chat-rat-king`)로 정밀 검증.

**결과**:

| 시나리오 | 종합 | NPC차별화 | 톤일치 | ERROR/WARN |
|---|---|---|---|---|
| chat-edric (수정 전) | 3.50/5 | 3.50 | 2.50 | 0/0 |
| chat-mairel | 4.35/5 | 5.00 | 5.00 | **1 ERROR** |
| chat-rat-king | 4.00/5 | 5.00 | 5.00 | **1 WARN** |

- **signature 리크 fix 자체는 유효함 확인** — rat-king 원래 앵커("너는 뭘 줄 수 있지?") 재발 없음, mairel "그대" 호칭 정상, signature 원문 유출 없음.
- **무관한 부수 발견** (이번 fix 범위 밖, 기록만): chat-mairel T2(설정 단계)에서 `speakingNpc.npcId=null`인데 displayName="경비대원" — architecture/46 영역 회귀로 추정. chat-rat-king 호칭 일관성 44%(PRONOUN_INCONSISTENT WARN).

**새 발견 — 에드릭 speechStyle 단어앵커**: 앞선 부록의 10턴 일반 플레이테스트 스팟체크에서는 안 보였으나(에드릭 등장 밀도가 낮아 미검출), 10턴 전량을 에드릭에게 쓰는 `chat-edric` 시나리오에서 실제 발화(`npcUtterances`)를 직접 대조하니 **"수지가 맞지 않는"/"수지타산이 맞지 않는" 조합이 11턴 중 5회** 등장. 원인은 signature가 아니라 `personality.speechStyle` 본문:

> 수정 전: "...회피 어휘(위험/조심) 대신 회계 비유로 정황을 표현한다 (**수지/계산/장부** 어휘 영역에서 자유 변형, 같은 어구 반복 금지)."

"수지"라는 구체 단어를 카테고리명으로 직접 명시한 탓에, LLM이 "같은 어구 반복 금지"라는 soft 지시를 무시하고 그 단어로 만들 수 있는 가장 자연스러운 관용구("수지가 맞지 않다")로 수렴 — signature 인용구 anchor와 같은 계열이지만 **단어 앵커** 형태.

**수정**: speechStyle에서 "수지/계산/장부" 나열을 제거하고 기능 단위로 추상화.

> 수정 후: "...회피 어휘(위험/조심) 대신 **돈과 문서를 다루는 직업 특유의 비유**로 정황의 심각성을 표현한다 (매번 다른 표현으로 변주, 같은 어구 반복 금지)."

**재검증**: `chat-edric` 재실행 — 종합 3.50→**3.68**, NPC차별화 3.50→**4.00**. "수지" 계열 표현 **0회**로 완전히 사라짐.
다만 **풍선효과 재확인**: "수지"를 지우자 LLM이 같은 문형("[재정 명사]가 맞지 않다")을 **"숫자가 맞지 않는" 2회**로 재구성 — CLAUDE.md "LLM 설계 원칙" #5(풍선효과: 단어 금지 시 의미적 동의어로 우회)의 실제 사례. 5회→2회로 확실히 개선됐으나, 원인이 단어가 아니라 "회피 어휘 대신 ~가 맞지 않다 식으로 표현하라"는 **문형 자체**라 완전 해소는 아님.

**결정**: 여기서 중단 — 개선폭이 명확하고(5→2), 문형 자체를 건드리는 추가 개입은 별도 검증 사이클(A/B)이 필요한 새 작업이라 판단. 향후 검토 시 참고할 것.

## 관련 커밋

- server `fa71d53` — Challenge Classifier
- server `37b4d83` — NpcReactionDirector + signature 노출 제거
- graymar `22aca6a` — speechStyle 어구 예시 추상화 (9 NPC)
- server `4e3d85c` — 마커 substring 합쳐짐 방어
