# 69. NPC Living Presence — B축 구축 계획

> 목표(사용자): NPC가 살아있는 존재처럼 다채롭고 내부 기억을 가진 채 활동한다.
> 이방인이 말을 걸었을 때 별도 대사가 없는 한 먼저 단서를 언급하거나
> 부자연스럽게 행동하지 않는다.
>
> A축(선제 단서 억제)은 arch/68 부록 M에서 완료. 본 문서는 B축(살아있음).
> 상태: **계획** (2026-07-13). 구현 착수 시 단계별 진행·검증.
> 개정: 2026-07-13 코드 실측 검토 반영 — 진단 정밀화(§1), B0 계측 선행 신설,
> dialogueAct 전달·정제 파이프·introduced 게이트·테스트 전략 추가(§3), B2 병행
> 허용(§4).

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

### Phase B3 — 개인 기억 축적·활용 강화 (연속성)

**문제**: 재등장 시 "지난번" 참조가 약함.

**작업**:
- personalMemory 축적 정밀화: 플레이어 주요 행동(도움/위협/거래)을 기억에
  구조화 저장. (일부 있음 — 강화.)
- 재등장 턴에 "직전 만남 요약"을 대화 톤에 positive 주입: "지난번 그
  일 이후로…". 단, A축 원칙 유지 — 기억이 단서 선제 노출로 새지 않게.
- **주입 전 정제 파이프 (검토 추가)**: "기억은 톤에만"은 게이트 선언만으로
  성립하지 않는다 — 기억 내용에 fact가 섞여 있으면 톤 주입이 곧 단서
  노출이다. 재등장 요약 생성 시 `discoveredQuestFacts`·NPC knownFacts 관련
  키워드를 **필터링하는 정제 단계**를 파이프에 명시적으로 둔다.
- introduced NPC 재대면 연속성 (encounterCount 4단계 관계 깊이와 연동).

**검증**: 재등장 대화의 이전 맥락 참조율, 단서 누출 0 — **부록 M의 선제
단서 센서를 재사용**해 계측.

### Phase B4 — NPC 간 살아있는 세계 (선택, 후순위)

**작업**:
- npcRelations를 대화에 반영: "오웬 그 친구가 요새…" 같은 NPC 간 근황 언급.
  - **introduced 게이트 (검토 추가)**: NPC 간 실명 언급은 **미소개 실명
    차단(불변식 15, arch/64)을 우회하는 통로**가 될 수 있다. 언급 대상
    NPC가 introduced 상태일 때만 실명 허용, 미소개면 별칭(unknownAlias)으로
    치환하거나 언급 자체를 생략하는 게이트를 주입 단계에 둔다.
- 다른 NPC 아젠다 목격([목격 장면], 이미 존재)을 잡담·반응에 자연 연결.
- 세계가 플레이어 없이도 돌아가는 감각 (NpcAgenda/situation-generator 활용).

**검증**: NPC 간 언급 자연스러움, 세계 능동성 체감, **미소개 실명 노출 0**
(R7 스트림 새니타이즈·audit 실명 센서 재사용).

---

## 4. 우선순위·의존

```
B0 (계측 베이스라인) ── B1 착수 조건. 측정 먼저.
  └ B1 (반응 자기목적) ─ 근본. "배척 일변도" 해소. 최우선.
  └ B2 (잡담 고도화) ── B1과 병행 가능 (파이프 상이 — 잡담 D vs reaction).
      └ B3 (기억 연속성) ─ 재등장 깊이.
          └ B4 (NPC 세계) ─ 선택. 여력 시.
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
| 기억 참조가 단서 선제 노출로 회귀 | B3에서 A축 게이트 준수 — 기억은 톤에만, 단서는 명시 질문 시만. **주입 전 fact 키워드 정제 파이프** + 부록 M 센서 계측. |
| NPC 간 언급이 미소개 실명 노출 통로화 | B4 introduced 게이트 — 미소개 NPC는 별칭 치환/언급 생략 (불변식 15). |
| ctx 조립 로직이 인라인으로 굳어 무테스트화 | B1 ctx 빌드를 export 순수 함수로 추출 + 유닛 동반 (테스트 감사 2026-07-12 패턴). |

---

## 6. 검증 인프라 (playtest 확장 후보)

- **V11 — 반응 다양성** (B0에서 선구축): reactionType이 posture별로 분화되는지
  (FRIENDLY가 PROBE 일변도가 아닌지). **B1 착수 전 현 시스템 베이스라인 측정이
  첫 산출물.**
- **자기목적 언급률**: 대화 발화에 NPC 현재 활동·목적이 드러나는 비율 (계측).
- **정보 획득 무후퇴 지표**: S5 완주 턴수·fact 발견 턴수 (아크 커밋 3사이클
  프로세스 재사용) — B1 이후 각 Phase 검증에 상시 포함.
- 기존 V10(선택지-서술 정합)·부록 M(선제 단서)과 함께 "NPC 자연스러움" 축
  강화. B3는 부록 M 센서, B4는 실명 노출 센서(R7·audit)를 재사용.
