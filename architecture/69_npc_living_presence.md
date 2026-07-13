# 69. NPC Living Presence — B축 구축 계획

> 목표(사용자): NPC가 살아있는 존재처럼 다채롭고 내부 기억을 가진 채 활동한다.
> 이방인이 말을 걸었을 때 별도 대사가 없는 한 먼저 단서를 언급하거나
> 부자연스럽게 행동하지 않는다.
>
> A축(선제 단서 억제)은 arch/68 부록 M에서 완료. 본 문서는 B축(살아있음).
> 상태: **B0~B4 구현·검증 완료** (2026-07-13). 후속(어미 다양화)은 재배정
> 완료, 어체 검증 경로는 **C1 완료**·C2~C3 착수 대기.
> 개정: 2026-07-13 코드 실측 검토 반영 — 진단 정밀화(§1), B0 계측 선행 신설,
> dialogueAct 전달·정제 파이프·introduced 게이트·테스트 전략 추가(§3), B2 병행
> 허용(§4).
> 개정 2: 2026-07-13 B4 정밀 설계 — 범위 확정(B4-0 결정 표), 관계 근황 발화
> 코어 설계(B4-1: selectRelationMentionCore + rel: 쿨다운 재사용), 목격 파이프
> 기존 배선 명시(B4-2), 능동 세계를 3채널로 축소·백로그 분리(B4-3).
> 개정 3: 2026-07-13 어체 검증 경로 완성 설계 — A안/B안 절충 C안 확정
> (C1 레거시 무해화 → C2 화자 인지 계측 → C3 조건부 선별 재생성). B안 3중
> 난이도 중 2개는 기존 인프라(extractNpcUtterances·done 교체)로 기해소 실측.
> §4·§5 현행화(B4 구현 완료, 리스크 실측 정정).

---

## 1. 진단 — 데이터는 완비, "방향"이 문제

### 이미 있는 것 (놀랍게도 대부분 존재)

| 데이터 | 위치 | 주입 여부 |
|--------|------|-----------|
| `schedule` (4상 일과) | npcs.json, activityLocations | lorebook·context-builder·prompt-builder 주입됨 |
| `daily_topics` (잡담 화제) | npcs.json | 잡담 모드(D)에서 주입 (arch/45) |
| `agenda` / `currentGoal` | npc-state | 상태 보유 |
| `personalMemory` | npc-state (Memory v3) | context-builder focused 주입 |
| `personality.innerConflict` / `softSpot` | npcs.json | prompt-builder·reaction-director 주입 |
| `personality.npcRelations` | npcs.json | prompt-builder 등장 NPC 필터 주입 |
| Living World 서비스 | npc-agenda·npc-schedule·npc-whereabouts·situation-generator | 존재 |

즉 "살아있음"에 필요한 **데이터와 주입 경로는 이미 있다.** 문제는 활용
방향이다.

### 진짜 갭 (3가지)

1. **반응 목표가 정보 편향** — `NpcReactionDirector`의 `immediateGoal`이 대화
   방향을 결정하는데, ctx에 **agenda·schedule·daily 관심사가 전달되지 않는다**
   (실측: reaction-director ctx에 해당 필드 없음). 그래서 immediateGoal이
   "정보 파악/떠보기" 일변도가 되고, reactionType도 PROBE로 수렴. NPC가
   trust 43·FRIENDLY여도 "정보를 조심스럽게 다루는" 방향으로만 반응한다
   (앞선 "성격과 별개로 배척" 논의의 근원과 동일).

   **정밀화 (검토 2026-07-13)**: posture·trust·감정 5축은 reaction 프롬프트에
   **이미 주입되고 있다** (npc-reaction-director 238~251행 — `현재 태도`,
   감정 5축). 그런데도 PROBE 수렴하는 원인은 두 갈래:
   (a) 시스템 프롬프트의 immediateGoal 정의·R4("단서 진전") 규칙이 **정보
   축으로만 짜여** 있고, (b) 대안 목표(장사·일과·잡담) 데이터가 ctx에 없어
   LLM이 고를 선택지 자체가 없다. 따라서 B1은 "데이터 추가 주입"(b)과
   "기존 규칙의 정보 편향 재작성"(a)의 짝이며, 이미 주입된 posture/감정을
   중복 주입하거나 규칙을 새로 얹는 방향이 되면 안 된다 (§2 프롬프트
   최소주의).

2. **잡담 모드가 화제 나열 수준** — 잡담 모드(D)는 daily_topics에서 1개를
   뽑아 주입할 뿐, NPC의 현재 활동(schedule)·목적(agenda)과 결합하지 않는다.
   "화제는 있으나 삶의 맥락이 없는" 발화. A축(부록 M)으로 잡담 모드 발동
   빈도가 올라가므로, 이 품질이 이제 더 중요해졌다.

3. **개인 기억의 대화 반영이 약함** — personalMemory가 주입되지만 "관계
   정보" 위주. "지난번 그 일 이후로" 같은 재등장 연속성·구체 기억 참조가
   대화 톤에 잘 안 드러난다.

---

## 2. 설계 원칙 (CLAUDE.md LLM 원칙 준수)

- **데이터 주입 > 프롬프트 규칙** — 이미 큰 프롬프트에 규칙을 더 얹지 않는다.
  있는 데이터(schedule/agenda)를 반응 결정(immediateGoal)에 연결하는 게 핵심.
- **Positive > Negative** — "정보 흘리지 마" 대신 "지금 NPC는 X를 하는 중"을
  준다. A축이 이미 입력 단계에서 단서를 막았으니, B축은 그 자리를 자기 삶으로
  채우는 positive 작업.
- **A50 롤백 전례 경계** — 자연 대화 개선이 전 메트릭 후퇴로 전체 롤백된 적
  있음(arch/50). 단계별로 A/B 검증하며 진행, 회귀 시 즉시 롤백.
- **프롬프트 최소주의** — 새 블록은 기존 블록 희석. schedule/agenda는 이미
  주입되므로, 새 주입보다 "반응 결정에 참조"로 연결.

---

## 3. 단계별 구축 계획

### Phase B0 — 계측 선행: 반응 분포 베이스라인 (신설, B1 착수 조건)

**원칙**: 측정 먼저, 수정 다음. A50이 전체 롤백된 건 전 메트릭 후퇴를
**사후에** 발견했기 때문 — 기준선 없는 A/B는 성립하지 않는다.

**작업**:
- **계측 저장 방식 (보강 2, 2026-07-13)**: reactionType/immediateGoal은 현재
  로그(npc-reaction-director 224행 `[NpcReaction] type=/refuse=/goal=`)로만
  남고 **DB 미저장·휘발성**이다. playtest 계측을 위해 **turn debug JSONB에
  npcReaction 결과를 저장**한다 (로그 파싱 대비: 재현 가능·디버깅 겸용). B0
  첫 산출물은 이 저장 배선 + 조회.
- V11(반응 다양성) 계측기를 B1 **이전에** 구축: posture별 reactionType 분포,
  immediateGoal의 정보/자기목적 분류 비율. 위 저장된 npcReaction을 소스로.
- 현 시스템으로 베이스라인 1회 측정·기록 (playtest N턴, posture별 표본).
- 정보 획득 회귀 지표 병설: S5 완주 턴수·fact 발견 턴수 (아크 커밋 3사이클
  프로세스 재사용). B1이 자기목적을 강조해도 이 지표가 후퇴하면 안 됨.

**검증**: 베이스라인 수치가 기록되어 B1 A/B의 비교 기준으로 사용 가능.

**베이스라인 측정 결과 (2026-07-13, playtest 30턴 표본 24건)**:

| posture | reactionType 분포 | immediateGoal 분류 |
|---------|-------------------|--------------------|
| CALCULATING (5) | PROBE 4, OPEN_UP 1 | INFO 4, MIXED 1 |
| CAUTIOUS (14) | PROBE 7, OPEN_UP 7 | INFO 12, OTHER 2 |
| FRIENDLY (5) | OPEN_UP 3, PROBE 2 | **INFO 5 (100%)** |

- **정보 편향도(INFO/전체) = 88%, SELF(자기목적) = 0%.** §1 진단이 수치로 확정.
- **핵심**: `reactionType`은 posture별로 **이미 어느 정도 분화**된다(CALCULATING→
  PROBE 80%, FRIENDLY→OPEN_UP 60%) — 태도 5축이 주입되는 덕(§1 정밀화 확인).
  그러나 `immediateGoal`(대화가 무엇을 **원하는가**)은 **posture 무관하게 정보
  축**이다. FRIENDLY 오웬(선술집 주인, trust15)조차 잡담에 "정보 탐색" 5/5.
- **따라서 B1의 타겟은 reactionType이 아니라 immediateGoal의 정보 편향**이다
  (R4·정의 재작성 + 자기목적 데이터 주입). B1 성공 지표: SELF/MIXED 비중 상승,
  특히 FRIENDLY·사교 턴에서 INFO 비율 하락.

계측 정본: `scripts/measure_reaction_diversity.py` (V11). 저장 소스:
`turns.llm_npc_reaction`(B0 배선).

### Phase B1 — 반응에 NPC 자기 목적 주입 (최우선, 근본)

**문제**: immediateGoal이 정보 파악 일변도 → 모든 대화가 떠보기/경계.

**작업**:
- `NpcReactionContext`에 `currentActivity`(schedule 현재 4상 활동)·`agenda`·
  `dialogueAct` 필드 추가. startNpcReaction(llm-worker 705행)에서 빌드해
  direct()에 전달.
  - **topInterest 이관 (구현 정정 2026-07-13)**: 당초 daily_topics 대표를
    topInterest로 넣으려 했으나, daily_topics.text는 구체 대사 예시("한때
    항해사였소…")라 reaction ctx 주입 시 anchor 유발(원칙 42/56). B1
    immediateGoal 전환에는 currentActivity+agenda로 충분하므로 topInterest는
    **B2(잡담 모드)로 이관** — 잡담은 화제 자체가 목적이라 그 경로가 적합.
  - ctx 조립은 **export 순수 함수**(예: `buildNpcSelfContextCore`)로 추출해
    유닛 테스트 동반 (테스트 감사 2026-07-12 확립 패턴 — 인라인은 테스트
    불가 구조로 굳는다). 기존 npc-reaction-director.service.spec(30케이스)에
    "FRIENDLY+장사 중 → 자기목적 immediateGoal" 케이스 추가.
  - **currentActivity 공용 헬퍼화 (보강 1, 2026-07-13)**: schedule 현재 활동
    추출은 **이미 선례가 있다** — prompt-builder 648~656행이
    `scheduleDefault[phaseV2].activity`로 현재 활동을 뽑는다(phaseV2 소스는
    `worldState.phaseV2`, 4상 DAWN/DAY/DUSK/NIGHT). 이 로직을
    `getNpcCurrentActivity(npcDef, phaseV2)` 공용 export로 추출해 **3곳**
    (prompt-builder 기존 · B1 reaction · B2 잡담)이 재사용 — 복제 drift 방지.
    B1 착수 시 이 헬퍼를 먼저 뽑고 prompt-builder를 그 호출로 치환한다.
- **`dialogueAct` 전달 (검토 추가)**: 서버가 이미 감지하는 사교 발화
  (GREETING/WELLBEING/THANKS/FAREWELL — 불변식 44)를 ctx에 포함.
  "사교 턴 → 자기 삶 반응, 정보 턴 → 정보 반응" 분기가 규칙이 아닌
  **데이터로** 명확해진다 — "플레이어가 정보를 파고들 때만"이라는 조건
  판단을 LLM 추론에 맡기지 않는다.
- reaction-director 프롬프트의 immediateGoal 지시를 재조정:
  "NPC는 지금 [currentActivity] 중이며 [agenda]를 원한다. immediateGoal은
  **플레이어가 정보를 파고들 때만** 정보 중심으로, 그 외엔 NPC 자기 목적
  (장사·일과·경계·잡담)을 우선한다."
  - §1 정밀화에 따라 **기존 R1~R6·immediateGoal 정의의 정보 편향을 덜어내는
    재작성**이 본체 — 규칙 추가가 아니라 기존 규칙 재조정. posture/감정
    5축은 이미 주입되므로 중복 주입 금지.
- reactionType의 posture 분화는 프롬프트 재작성 + dialogueAct 데이터로
  유도: FRIENDLY+trust>20 → WELCOME/OPEN_UP 편향, CALCULATING/HOSTILE →
  PROBE/DEFLECT 유지.

**효과**: 오웬(trust43·FRIENDLY·장사 중)이 "손님 접대하며 자연스레 응대"로,
정보상(CALCULATING)이 "경계하며 떠보기"로 — 성격·상태별 반응 분화.

**검증**: B0 베이스라인 대비 reactionType 분포가 posture별로 갈리는지,
immediateGoal 자기목적 언급률, "성격과 별개 배척" 체감 개선, **정보 획득
지표(S5 완주·fact 발견 턴수) 무후퇴**.

**구현 완료 + A/B 결과 (2026-07-13)**:

| 지표 | 베이스라인(B0) | B1 후 |
|------|----------------|-------|
| INFO(정보 편향) | **88%** | **40%** |
| SELF(자기목적) | 0% | 25% |
| MIXED | 4% | 15% |
| SELF+MIXED | 4% | **40%** |
| reactionType | PROBE 편중 | THREATEN 등장·posture 분화 |

- 구현: (a) `getNpcSchedulePhaseEntry`/`getNpcCurrentActivity` 공용 헬퍼
  (npc-schedule.ts, prompt-builder 치환) (b) `buildNpcSelfContextCore` export
  순수 함수 + NpcReactionContext에 currentActivity/selfAgenda/dialogueAct
  (c) buildUserMessage 주입 (d) immediateGoal 정의·R4 재작성(정보 편향 →
  자기목적 기본, 정보는 파고들 때만). 유닛 7 + 전체 1094 passed.
- **정보 편향 88→40%, 자기목적 계열 4→40%.** 정보상 "거래 유지", 토브렌
  "가족 안전 확보", 브렌 "위협 관망하며 긴장 유지"로 성격별 분화.
- 남은 INFO 40%는 이 세션이 **장부 퀘스트 조사 위주**여서 (에드릭 8건 전부
  플레이어의 조사 대응) — R4 의도대로 "플레이어가 캐물으면 정보". 잡담 턴
  단서 억제는 부록 M(A축)이 별도 담보.
- 정보 획득 무후퇴: playtest 10/10 PASS(베이스라인 9/10), 퀘스트 정상 진행.
- measure SELF_KW 실측 보강(거래/안전/가족/관망 등) 반영.

### Phase B2 — 잡담 모드 고도화 (화제 나열 → 삶의 맥락)

> 검토 (2026-07-13): B2는 잡담 모드(D) 경로, B1은 reaction 경로 — **파이프가
> 달라 실제 결합도가 낮다.** A축(부록 M)으로 잡담 빈도가 올라간 지금 B1과
> **병행 가능** (§4 참조). B1의 A/B 검증이 길어지면 체감 개선을 먼저 낼 수
> 있는 저위험 경로.

**문제**: 잡담이 daily_topic 나열 수준.

**작업**:
- 잡담 모드 주입에 `currentActivity`(schedule) 결합: "재고 정리하며 흘리듯",
  "손님 접대 사이에". 화제를 NPC 현재 상황에 얹는다.
- daily_topic을 agenda/currentGoal과 연결해 "화제에 NPC 목적이 배도록".
- 잡담 recentTopics 회피는 유지(반복 방지), 화제 풀 확장 여지 콘텐츠 검토.

**검증**: 잡담 발화에 현재 활동·목적 언급률, 화제 다양성(TTR).

**구현 완료 + 실측 (2026-07-13)**: 잡담 모드(prompt-builder 2577) 주입에
`getNpcCurrentActivity`(B1 공용 헬퍼 재사용) 결합 — `[NPC 일상 — 지금 이
순간]` 블록에 "지금 ~하는 중" + "하던 일 이어가며 화제 흘리듯" 지시. 오웬
(선술집 주인) 잡담 3턴 실측: 전 턴에서 schedule 활동(잔 닦기)이 서술에 자연
결합 — "닦고 있던 잔을 내려놓고 인사", "행주로 잔을 닦는 손길을 멈추고". 화제
나열 → 삶의 맥락 전환 확인. 단서 선제 노출 0(A축 유지). topInterest는 이
경로로 이관 완료(B1 정정).

### Phase B3 — 개인 기억 축적·활용 강화 (연속성)

**문제**: 재등장 시 "지난번" 참조가 약함.

**작업**:
- personalMemory 축적 정밀화: 플레이어 주요 행동(도움/위협/거래)을 기억에
  구조화 저장. (일부 있음 — 강화.)
- 재등장 턴에 "직전 만남 요약"을 대화 톤에 positive 주입: "지난번 그
  일 이후로…". 단, A축 원칙 유지 — 기억이 단서 선제 노출로 새지 않게.
- **정제 파이프 구현 정정 (2026-07-13 실측)**: 당초 재등장 요약에
  discoveredQuestFacts를 필터링하는 별도 정제 단계를 두려 했으나, 실측 결과
  personalMemory.knownFacts에 저장되는 건 `event.payload.sceneFrame`(이 NPC와
  실제 상호작용한 장면)으로 **출처가 이 NPC 공유분에 한정**된다 — 다른 NPC의
  단서가 섞이는 오염 경로가 구조상 없다(축적 지점 turns.service 2921).
  따라서 별도 필터 파이프는 불필요. 남은 실질 리스크는 "이미 공유한 사실을
  NPC가 재등장 때마다 먼저 들추는 부자연스러움"이며, 이는 **렌더 지시의 선제
  금지 명시**(A축 일관)로 해소한다.
- introduced NPC 재대면 연속성 (encounters ≥ 2 시 관계 톤 지시).

**검증**: 재등장 대화의 이전 맥락 참조율, 단서 누출 0 — **부록 M의 선제
단서 센서를 재사용**해 계측.

**구현 완료 + 실측 (2026-07-13)**: renderRelevantNpcMemory(context-builder)에
`encounters ≥ 2` 시 재등장 관계 톤 지시 1줄 추가 — "초면처럼 굴지 말고 아는
사이의 결로 대하되 지난 일을 매번 들추지 마라, 알려진 사실 선제 금지". 오웬
5턴 대화 실측: encounters 5건 축적 → 톤 발동, **5턴 전부 단서 선제 0**(A축
유지), "아는 사이" 응대 자연·"지난번" 반복 없음. schedule 활동 결합(B2)도
지속. 정제 파이프는 knownFacts 출처가 이 NPC 공유분 한정이라 불필요(위 정정).

### Phase B4 — NPC 간 살아있는 세계 (선택, 후순위 — 정밀 설계 2026-07-13)

**목표**: 화자 NPC의 입을 통해 "다른 NPC도 각자의 삶을 사는 중"이라는 감각을
전달한다. 신규 시스템을 만들지 않고, **이미 돌아가는 데이터**(npcRelations
정적 관계 + recentAgendaEvents 동적 사건)를 잡담 경로에 연결한다.

#### B4-0. 설계 결정 (범위 확정)

| 결정 | 근거 |
|------|------|
| 주입 경로는 **잡담 모드(D) 블록 확장만** | reaction 경로(B1)는 불가침 — 근황 언급은 "대화가 원하는 것"이 아니라 잡담의 재료. 정보 턴에 끼면 노이즈. |
| "근황"의 소스는 `recentAgendaEvents` | world-tick 219~227행이 매 tick NPC 아젠다 진행분을 `{npcId, signal}[]`로 ws에 저장 — **근황 데이터는 이미 생산 중**, 소비 채널만 없다. |
| "관계 톤"의 소스는 `personality.npcRelations` | 실측: graymar 17/43명 보유, 관계 서술 텍스트 (예: 오웬→레닉 "술친구이자 정보원. 신뢰하지만 입이 가벼운 게 걱정"). |
| 미소개 대상은 **언급 생략** (별칭 치환 아님) | NPC끼리 서로를 플레이어용 별칭("날카로운 눈매의 회계사")으로 부르는 건 부자연. 제3자 실명 호명은 이름 공개 경로(arch/66 외부 fallback)와 간섭하므로, introduced=true 대상만 후보 풀에 넣어 **구조적으로** 차단 (불변식 15). |
| "능동적 세계"는 **전달 채널 정리로 축소** | 세계는 이미 플레이어 없이 돈다(world-tick·NpcSchedule·NpcAgenda). 부족한 건 전개가 아니라 **체감 채널** — signalFeed(있음)·[목격 장면](있음)·근황 발화(B4 신설)의 3채널로 정의하고, 그 이상(장소 재방문 변화 언급 등)은 백로그. |

#### B4-1. 관계 근황 발화 — 잡담 모드 확장

**후보 선정 (export core, 유닛 동반)**:

```
selectRelationMentionCore(
  speakerDef,            // npcRelations 보유 화자
  npcStates,             // introduced 판정
  recentAgendaEvents,    // ws의 {npcId, signal}[] (없으면 [])
  recentTopics,          // 화자 npcState.llmSummary.recentTopics
  witnessNpcId,          // 이번 턴 [목격 장면] 대상 (중복 프레임 방지)
): { targetNpcId, targetName, relationText, recentSignal|null } | null
```

- 후보 = 화자 `npcRelations` 키 중 `npcStates[target].introduced === true`.
- 제외: ① `recentTopics`에 `rel:<npcId>` 기록 존재 (아래 쿨다운) ② 이번 턴
  `agendaWitnessHint` 대상과 동일 NPC (같은 사건을 목격+전언 이중 서술 방지).
- 우선순위: recentAgendaEvents에 signal이 있는 대상 > 관계만 있는 대상.
  복수 후보면 잡담 화제 선택과 동일하게 랜덤 (기존 D 경로 관행).
- **쿨다운은 기존 메커니즘 재사용**: 주입 시 `recentTopics`에
  `{topic: 'rel:<npcId>'}` 기록 → daily_topic과 동일한 FIFO 회피가 자동
  적용된다 (신규 상태 필드 0개).

**프롬프트 주입** (잡담 [NPC 일상] 블록에 1~2줄 추가, 잡담 턴 한정):

```
[주변 인물 근황] (화자가 아는 것)
{targetName}: {relationText}
(최근 소식: {recentSignal})        ← signal 있을 때만
→ 잡담 중 자연스러우면 한 문장으로만 곁들이세요. 관계 서술 범위 밖의
  사건을 만들지 말고, 어색하면 생략하세요.
```

- recentSignal이 없으면 관계 톤만 — "그 친구 잘 지내나 모르겠군" 수준.
  **사건 창작 방지는 positive 경계**("관계 서술 범위 안")로 처리.
- 토큰 영향 ~80자, 잡담 턴 한정이라 예산(불변식 17) 영향 미미.

#### B4-2. 목격 파이프 — 재사용 예정이었으나 **버그 발견·수정** (2026-07-13)

[목격 장면] 배선은 존재하나(world-tick `recentAgendaEvents` →
`buildAgendaWitnessHint` → prompt-builder 2671행 주입, 질문 턴 억제), **위치
판정 버그로 상시 무력**이었다: `buildAgendaWitnessHint`가 `schedule.default`를
`{ default?: string }`로 오독 — 실제로는 4상 객체(`{DAWN:{...},DAY:{...}}`)라
`객체 !== playerLocation`이 항상 참 → 전 NPC 탈락 → agendaWitnessHint 상시
null. B1의 `getNpcSchedulePhaseEntry(schedule, phaseV2)`로 현재 phase의
locationId를 올바르게 판정하도록 수정하고, 반환을 `{text, npcIds}`로 바꿔
witnessNpcIds를 B4-1 중복 제외에 노출. B4-1은 이 동일 데이터를 "현장
목격"(같은 장소)과 "전언 근황"(다른 장소 소식)의 두 프레임으로 나눠 쓰며,
후보 제외 규칙 ②가 두 프레임의 같은 턴 중복을 막는다.

#### B4-3. 백로그 (이번 범위 밖)

- 장소 재방문 시 변화 언급 ("지난번보다 경비가 늘었군") — locationDynamicStates 활용.
- NPC 간 관계의 동적 변화 (사건이 npcRelations 톤을 바꾸는 것) — 콘텐츠
  정적 필드라 런타임 오버레이 설계 필요.
- silverdeen_v1 npcRelations 콘텐츠 보강 (현재 graymar 17명 위주).
- rel: 쿨다운 완전 지속 — 현재는 recentTopics 읽기 회피 + 랜덤(B4-1 정정).
  turns.service 기록 경로 추가 시 지속 (실측 반복 관찰 시).
- **factsParts 총량 예산 가드** (code-review 2026-07-13 발견) — 불변식 #17의
  `enforceTotal`(총 2500 트림)은 `memoryParts`(assistant role)에만 적용되고,
  `factsParts`(user role, 이번 턴 정보)는 총량 트리밍 밖이다. B2 `[NPC 일상]`·
  B4 `[주변 인물 근황]`을 포함해 기존 수십 개 factsParts 블록 전체가 우선순위
  맵 미등록 — 새 블록 고유 문제가 아닌 factsParts 설계 특성. 잡담·재등장 한정
  + 블록당 ~80~150자라 실害 미미하나, factsParts 무제한 성장을 막는 총량 가드
  (우선순위 맵 확장 또는 별도 enforceTotal)는 별도 리팩터로 다룬다.

**검증**:
- 유닛 (export core): introduced 필터·rel: 쿨다운·목격 중복 제외·signal
  우선순위·후보 0 → null.
- 잡담 실측 N턴: 근황 언급 발생·자연스러움, 같은 대상 반복 0, **미소개 실명
  노출 0** (audit 실명 센서 + R7 스트림 새니타이즈 재사용 — 후보 필터로
  구조 차단이 1차, 센서는 회귀 감지용).
- signal 텍스트 경유 제3 실명 누출 여부 (LLM이 signal 원문을 옮길 때) —
  기존 미소개 실명 후처리가 커버하는지 1회 확인.

**구현 완료 + 실측 (2026-07-13)**:
- 유닛 8케이스 통과(`npc-relation-mention.spec`), 전체 1102 passed.
- **B4-1 근황 발화 발동**: playtest 30턴 중 T18 "[주변 인물 근황] 에드릭
  베일: 상단과의 뒷거래 연결고리" 주입 — introduced 대상이라 실명 노출 정상,
  **미소개 실명 노출 0**(playtest V8 PASS). 30턴 1건 = 잡담+관계+introduced
  조건상 자연스러운 빈도.
- **B4-2 목격 버그 수정 검증**: recentAgendaEvents 실제 생산 확인
  (`{npcId:EDRIC, signal:"회계 장부 수정 흔적"}`). 이 세션 목격 0건은 에드릭
  (LOC_MARKET/NOBLE)과 플레이어(LOC_HARBOR)의 **위치 불일치 = 올바른 동작**
  (전엔 위치 무관 100% 무력, 후엔 위치 겹칠 때만). 근황 전언(B4-1)이 위치
  무관하게 소식을 대신 전달.
- **쿨다운 구현 정정**: 당초 recentTopics rel: 기록 재사용을 계획했으나,
  실측 결과 기존 recentTopics 기록(turns.service 2934)이 `topic`에
  sceneFrame/null을 넣어 daily_topic 쿨다운조차 불완전. 프롬프트 조립 시점
  (prompt-builder)에서 화자 recentTopics를 **읽어 회피**(구현) + 복수 후보
  랜덤으로 1차 방어. 잡담 발동 빈도가 낮아(fact 매칭 0 조건) 반복 실害 미미 —
  실측에서 반복 관찰 시 turns.service 기록 경로 추가는 백로그.
- **근황 대상 화자 오귀속 방어 (통합 검증 2026-07-13)**: 통합 플레이테스트
  40턴에서 근황 대상(부재 인물)이 LLM에 의해 화자로 소환되어 대사+@마커가
  붙는 V8 오귀속 1건 발견(T10, 에드릭 베일). "한 문장 곁들이세요"가 soft해
  LLM이 부재 인물을 장면에 등장시킴. 프롬프트를 "그 인물은 지금 이 자리에
  없다 — 화자 {name}이 스치듯 언급만, 그의 대사·@마커 금지"로 강화. 재검증
  40턴에서 오귀속 0/1, V8 PASS 복구. 후처리 방어(근황 대상이 장면 참석자
  아니면 마커 무효)는 프롬프트로 잡히지 않을 때 백로그.

### B축 통합 검증 (40턴 × 2세션, 2026-07-13)

| 축 | 실측 | 판정 |
|----|------|------|
| A축 잡담 단서 선제 | V7 누출 없음 | ✅ |
| B1 반응 자기목적 | 정보 편향 40% 유지(베이스라인 88%) | ✅ |
| B2 잡담 활동 결합 | 18턴 발동 | ✅ |
| B3 재등장 연속성 | 17턴 발동 | ✅ |
| B4 근황 발화 | 발동 + 오귀속 0/1(수정 후) | ✅ |
| B4-2 목격 | 0턴(위치 미겹침, 정상) | — |

전 기능이 40턴 플레이에서 활발히 작동·공존. V8 회귀 1건 수정 완료(위).
V9_quality 실패는 어휘 반복(그는×43 등) — LLM 어휘 편향, arch/68 부록 F
계측 대상, B축 무관.

---

## 4. 우선순위·의존

```
B0 (계측 베이스라인) ── B1 착수 조건. 측정 먼저.
  └ B1 (반응 자기목적) ─ 근본. "배척 일변도" 해소. 최우선.
  └ B2 (잡담 고도화) ── B1과 병행 가능 (파이프 상이 — 잡담 D vs reaction).
      └ B3 (기억 연속성) ─ 재등장 깊이.
          └ B4 (NPC 세계) ─ ✅ 구현·검증 완료 (근황 발화 + 목격 버그 수정).
후속: 어미 다양화(✅ 재배정) → 어체 검증 C1(레거시 무해화) → C2(계측) →
C3(조건부 개입 — C2 수치 게이트).
```

**B1이 핵심**: immediateGoal의 정보 편향이 "성격과 별개 배척"과 "부자연스러운
단서 언급" 양쪽의 공통 뿌리. B1만으로도 체감 개선이 크다. B2~B4는 다채로움을
누적하는 확장. B2는 의존 사슬에서 분리해 B1의 A/B 검증과 병행할 수 있다.

---

## 5. 리스크·완화

| 리스크 | 완화 |
|--------|------|
| 자연 대화 개선의 전면 후퇴 (A50 전례) | **B0 베이스라인 선측정** + 단계별 A/B 검증, 회귀 시 즉시 롤백. B1부터 소범위. |
| 프롬프트 비대화 (이미 큼) | 새 주입 최소화 — 있는 데이터를 반응 결정에 연결. 규칙 추가 대신 **기존 R1~R6 재작성**. |
| 자기목적 강조로 정보 획득 저하 | A축(주제 매칭 시 공개)은 유지 — 플레이어가 물으면 여전히 나옴. **S5 완주·fact 발견 턴수를 B0/B1 검증 지표에 포함** (선언이 아닌 계측으로 방어). |
| 기억 참조가 단서 선제 노출로 회귀 | B3에서 A축 게이트 준수 — 기억은 톤에만, 단서는 명시 질문 시만. ~~정제 파이프~~ → 실측 결과 knownFacts 출처가 이 NPC 공유분 한정이라 **불필요 판정**(B3 정정), 렌더 선제 금지 지시 + 부록 M 센서 계측으로 대체. 실측 5턴 누출 0. |
| NPC 간 언급이 미소개 실명 노출 통로화 | B4 후보 풀 자체를 introduced=true로 한정 (구조 차단, 별칭 치환 아님 — B4-0) + audit 실명 센서·R7 회귀 감지. |
| 근황 언급이 사건 창작(hallucination)으로 확대 | 관계 서술·recentSignal **범위 안** positive 경계 (B4-1 프롬프트) — signal 없으면 관계 톤만. |
| 근황 언급 자체가 반복 패턴화 | recentTopics **읽기 회피** + 복수 후보 랜덤 (구현 정정 — 기록 경로는 기존 recentTopics 기록 자체가 불완전해 백로그) + 목격 중복 제외 (B4-1). |
| C1 치환 제거 후 하오체 NPC "자네" 오사용 방어 공백 | forbidHint 프롬프트 1차 방어 + **C2 계측이 오사용률을 수치 감시** — 임계 초과 시에만 C3 선별 재생성. 기존 교정은 방향이 잘못돼 순훼손(해체 17명 오염 > 하오체 10명 방어)이었으므로 제거가 순이익. |
| C3 재생성 대사가 원문 맥락 이탈 | "의미 유지, 어미만 교정" positive 지시 + 실패 시 원문 유지 (무개입 > 오교정). 위반 대사 1건 단위라 비용 제한적. |
| ctx 조립 로직이 인라인으로 굳어 무테스트화 | B1 ctx 빌드를 export 순수 함수로 추출 + 유닛 동반 (테스트 감사 2026-07-12 패턴). |

---

## 6. 검증 인프라 (playtest 확장 후보)

- **V11 — 반응 다양성** (✅ B0 구축 완료 — `scripts/measure_reaction_diversity.py`):
  posture별 reactionType 분화·immediateGoal 분류. 베이스라인/B1 A/B 실측 완료.
- **어체 준수 계측 (C2 예정)**: 화자별 대사 추출 × validateSpeechRegister —
  turn debug 저장 + NPA 어미 메트릭(arch/55) 교차. C3 발동 게이트.
- **자기목적 언급률**: 대화 발화에 NPC 현재 활동·목적이 드러나는 비율 (계측).
- **정보 획득 무후퇴 지표**: S5 완주 턴수·fact 발견 턴수 (아크 커밋 3사이클
  프로세스 재사용) — B1 이후 각 Phase 검증에 상시 포함.
- 기존 V10(선택지-서술 정합)·부록 M(선제 단서)과 함께 "NPC 자연스러움" 축
  강화. B3는 부록 M 센서, B4는 실명 노출 센서(R7·audit)를 재사용.

## 후속 — NPC 어미 다양화 (성별·개별 말투 구분, 2026-07-13)

**문제(사용자 지적)**: 여성/남성 NPC 말투가 비슷하게 들린다.

**진단**:
- speechStyle 콘텐츠 개성(화제·태도)은 양호하나, **43명 중 25명(58%)이
  하오체**이고 speechStyle에 전원 "~소/~하오 체 + 경어"를 명시 → 어미·격식이
  지배해 "다 비슷한 사극체"로 수렴.
- gender는 서술 대명사(그/그녀)·목록 표기[여/남]에만 쓰이고 **대사 어조엔
  미반영**. 하오체 어미(~소/~하오)는 성별 중립이라 여성 하오체(세라·비올라·
  헬가)가 남성과 구분 안 됨.

**개선 — 어미 다양화 (26명 재배정)**:
- 하오체 25 → 10, 해체 1→17, 합쇼 8→14, 반말 2 유지, **해요 7→0**.
- 캐릭터 부합: 귀족·군 상관·집사→합쇼, 상인·노인→하오, 뒷골목·과묵·거친→해체.
- **HAEYO(해요체) 전면 제거**: 실측 결과 해요체(~해요)가 사극 세계관 톤
  관성으로 하오체로 새어남(로넨 CORE조차). 세계관에 이질적이라 합쇼/해체/하오로
  재조정. 원래 HAEYO 6명 중 로자는 speechStyle이 "~하오 체"로 register와 모순
  이던 것도 함께 정합.
- HAECHE 가이드 톤 중립 확장(speech-register.ts·dialogue-generator.ts):
  기존 "노인 느슨한 반말" → "낮춤체(노인·거친·무심 모두, 톤은 speechStyle이
  결정)". HAECHE 1→17명 대응.

**실측 (playtest 40턴 ×2)**:
- HAOCHE(에드릭·오웬)·HAPSYO(단정한 장교 합쇼12)·HAECHE(토브렌 해체12) 배정대로
  반영 확인. 해요체 제거 후 로넨도 합쇼체로 이동.
- 여성 하오체 4→3(미렐라·로자·리나), 세라·헬가·비올라·마리엘·엘사→해체,
  이졸데·엘리자→합쇼로 남성 하오체와 어미 분화.

**백로그**:
- **메인 LLM @마커 대사 어체 검증** — 점검 결과 단순 "fallback 부재"가 아니라
  **하오체 강제 레거시가 재배정을 훼손**하는 문제로 심화 확인됨. 아래
  "어체 검증 경로 점검" 참조.
- BG NPC(골목 아이 등) 어미 반영이 경량 프롬프트로 약함.
- 어미 재배정을 A/B로 검증할 "NPC 간 말투 유사도" 계측기(기존 NpcDistinctness는
  개별 준수만 측정).

### 어체 검증 경로 점검 (2026-07-13, 어미 다양화 후속)

어미 다양화 후 "메인 대사 어체 fallback" 백로그를 점검하다 **레거시 후처리가
재배정을 적극 훼손**하는 것을 발견. 완성 설계는 아래 C안(C1~C3)으로 확정 —
구현 착수 대기.

#### 현황 — 어체 처리 두 경로

| 경로 | 위치 | 상태 |
|------|------|------|
| **dialogue_slot** (2-stage 대사 분리) | dialogue-generator.service.ts `validateSpeechRegister`(140행) + 재시도(351행) | ✅ 정상 — 5종 어체 어미 검증 + 혼용 감지 + 1회 재시도 후 fallback |
| **메인 서술 @마커 대사** | llm-worker.service.ts 후처리(1626~1642행) | ⚠️ fallback 없음 + **하오체 강제 레거시가 유해** |

#### 발견한 문제 (메인 서술 경로)

전 NPC가 하오체이던 시절 만든 후처리가 남아, **화자 어체와 무관하게 서술
전체(narrative)를 하오체 기준으로** 처리한다:

1. **P3 전역 텍스트 치환** (1635·1640행) — 실제 훼손:
   - `narrative.replaceAll('자네', '그대')`
   - `narrative.replaceAll('이보게', '듣고 계시오')`
   - `자네`·`이보게`는 **해체(HAECHE)의 정상 호칭**인데 하오체 격식 호칭으로
     되돌린다. 재배정으로 해체가 1→17명이 된 지금 대량 오염.
   - **실측(playtest 40턴)**: 토브렌(해체) "그대" ×6, 관리인(해체) "그대" ×1 —
     해체 NPC가 하오체 격식 호칭을 쓰는 부자연 확인. (토브렌은 해체 적합한
     "너"도 썼으나 "그대"가 지배.)

2. **P2 SPEECH_VIOLATION 정규식** (1627행) — 로그만(무해하나 기준 오류):
   - `자네|이보게|~일세…`(해체), `해요|세요|합니다|입니다…`(해요·합쇼),
     `~야|~해|~거든…`(반말·해체)를 **전부 "위반"으로 검출**.
   - 교정은 안 하고 `[NarrativeFilter] violations` 로그(1868행)에만 남으므로
     텍스트 훼손은 없으나, 하오체 유일 정답 전제가 다중 어체와 배치.

#### 완성 설계 — C안: 제거 → 계측 → 조건부 선별 개입 (2026-07-13 확정)

A안(치환 제거만)은 방어 공백을, B안(마커별 검증·교정 전면 이식)은 3중
난이도를 남긴다. **B안의 난이도 3개 중 2개는 기존 인프라로 이미 해소돼
있음을 실측 확인** — 남는 것은 "교정의 문장 파괴 위험"뿐이며, 이는 교정
대신 재생성으로 회피한다. 이를 3단계로 나눈다 (B0과 같은 원칙: 측정이
개입에 선행).

| B안의 3중 난이도 | 실측 결과 |
|------------------|-----------|
| (a) @마커↔화자 npcId↔register 매핑 | **이미 있음** — 후처리 시점에 appearedNpcIds·npcStates(speechRegister) 확보됨 |
| (b) 대사 구간만 잘라내기 | **이미 있음** — `extractNpcUtterances(narrative, target)` (npc-utterance.util, 유닛 보유) |
| (c) 교정의 문장 파괴 | 교정 포기 — 위반 대사만 **재생성**(dialogue-generator 검증+재시도 인프라 재사용) |

**Phase C1 — 레거시 무해화 (즉효, 저위험)**

- P3 전역 치환 2건(`자네→그대`, `이보게→듣고 계시오`) **제거**. 해체 17명의
  정상 호칭을 하오체로 오염시키는 유일한 실훼손 지점 (실측: 토브렌 "그대"×6).
- P2 SPEECH_VIOLATION 정규식 **제거** — 검출만 하고 미교정이라 기능 손실 0,
  하오체 유일 전제의 오검출 로그만 사라진다. 화자 인지 검출은 C2가 대체.
- **부작용과 수용 근거**: 하오체/합쇼 NPC가 "자네"를 섞을 때 자동 교정이
  사라진다. 수용하는 이유 — ① 기존 교정은 방향이 잘못돼 순훼손이 더 컸고
  (해체 17명 vs 하오체 10명), ② `buildRegisterLines` forbidHint가 1차 방어,
  ③ C2 계측이 실제 오사용률을 수치로 감시하므로 "감으로 수용"이 아니다.

**구현 완료 (2026-07-13)**: llm-worker P2 SPEECH_VIOLATION 정규식 + P3 전역
치환(자네→그대, 이보게→듣고 계시오) 제거(1626행). 빌드 통과. 실측(playtest
40턴): 전체 서술에 "자네" 9회·"이보게" 1회 **정상 유지**(이전엔 전량 하오체로
치환됨), 해체 NPC "그대" 오염 **0건**(직전 세션 토브렌 "그대"×6 → 0). 9/10
PASS(잔여 V9는 어휘 반복, 무관).

**Phase C2 — 화자 인지 어체 계측 (교정 없이 측정 먼저)**

- done 최종본 확정 후: 등장 NPC별로 `content.getNpc(id).speechRegister` ×
  `extractNpcUtterances(narrative, {npcId, displayNames})`로 **화자별 대사를
  잘라** `validateSpeechRegister`(dialogue-generator 140행 — **export로 전환**
  필요, 현재 module-private)에 통과시켜 위반을 turn debug JSONB에 기록 (B0의
  npcReaction 저장과 동일 관행).
- **대상 한정 (보강 1)**: **npcId 매핑 성공 + speechRegister 배정된 NPC만**
  검증한다. `@[무명 인물]`·register 미배정 화자는 **스킵** — `getRegisterRule`
  이 미배정 시 하오체로 fallback(100행)하므로, 무명을 넣으면 하오체 기준
  오검출이 된다. 계측 대상은 "실명/별칭으로 npcId가 해소되고 register가 있는
  화자"로 못박는다.
- **검증 단위 정합 (보강 2)**: `validateSpeechRegister`는 "한 대사 내 어미
  혼용"을 본다. extractNpcUtterances 반환 대사가 여러 문장일 때의 판정 단위를
  **NPA 어미 메트릭(arch/55, utterance 단위)과 일치**시킨다 — 착수 시 두 경로가
  같은 위반을 세는지 먼저 맞추고 계측을 시작한다(아래 교차 검증의 전제).
- export core (`auditUtteranceRegisterCore` 등) + 유닛. 텍스트는 **바꾸지
  않는다** — 계측 전용.
- NPA 어미 메트릭(arch/55)과 교차 검증 — 오프라인 audit과 런타임 계측이 같은
  위반율을 가리키는지 1회 대조.
- 산출물: register별·NPC별 위반율 베이스라인. **C3 진행 여부를 이 수치로
  결정한다** (B0→B1과 같은 게이트).

**Phase C3 — 조건부 선별 개입 (C2 위반율 임계 초과 시에만)**

- 발동 조건: C2 실측에서 특정 NPC/register 위반율이 임계(제안: 대사 기준
  15%) 초과 시. 미만이면 C3는 하지 않는다 — 프롬프트 방어로 충분하다는 뜻.
- 개입 방식: done 최종본 교체 시점에 **위반 대사만** dialogue-generator의
  기존 검증+재시도 인프라(LLM_DIALOGUE_MODEL, 어체별 재시도→fallback)로
  재생성해 치환. regex 어미 교정은 채택하지 않는다 (문장 파괴 — LLM 원칙
  "사후 삭제는 최후 수단").
- 스트리밍 충돌은 **기해소 패턴**: 마커 교정(Step E/F)과 동일하게 "타이핑
  중 원문 → done 최종본 교체" 프로토콜(arch/64 R7)이 이미 이 목적으로
  존재한다. 재생성 비용은 위반 대사 1건 단위(대사 1~2문장)라 제한적.
- 부작용 관리: 재생성 대사가 원문 맥락과 어긋날 위험 → 재생성 입력에 원문
  대사를 "의미 유지, 어미만 교정" positive 지시로 전달. 실패 시 원문 유지
  (무개입이 오교정보다 낫다).
- **UX 이질감 (보강 3)**: R7 마커 교체는 별칭(짧음)이라 눈에 덜 띄지만, **대사
  전체 재생성 교체는 "타이핑된 대사가 done 시점에 확 바뀌는" 이질감이 크다.**
  "어미만 교정" positive로도 LLM 재생성은 내용이 흔들릴 수 있다. 완화: ① C3
  발동을 고위반 NPC로 좁게 제한(임계 초과만), ② 재생성 실패·과변형 시 원문
  유지, ③ 재생성 대사와 원문의 의미 유사도(길이·핵심어) 가드로 과변형 방어.
  이 이질감은 C3의 상시 부작용이므로, C2 위반율이 낮으면 **C3를 아예 하지
  않는 게 최선**임을 재확인한다.

**장기 (백로그 유지)**: dialogue_slot(검증 O)/메인 서술(검증 X) 이원화의
근본 해소 — 대사 생성을 dialogue_slot 경로로 수렴. 스트리밍 2-Phase 렌더와
충돌하므로 별도 설계 문서로 다룬다. C1~C3는 이원화를 전제로 한 실용 봉합이다.

**검증**: C1 후 40턴 실측 — 해체 NPC "그대" 오염 0, 하오체 NPC "자네" 오사용
률(C2 수치) 기록. C2 위반율 베이스라인 산출. C3 발동 시 재생성 대사의 어체
준수·의미 보존 수동 확인 + NPA 어미 메트릭 무후퇴.
