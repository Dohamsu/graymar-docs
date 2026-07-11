# 65. 경제 루프 v1 — 단서 사례금 + 정보 구매 (2026-07-11)

## 배경 (실측)

2026-07-11 분석: 최근 30일 441턴 중 골드 이벤트 **4건**, 상점 구매 **0건**, 전투 노드 **0턴**.
14턴 런들의 최종 골드가 시작값 그대로 (DESERTER 45→45, DOCKWORKER 30→30).

원인은 행동 분포와 보상 게이트의 불일치:

| 행동 | 비중 (최근 270턴) | GOLD_ACTIONS 대상? |
|------|------|------|
| TALK / PERSUADE / INVESTIGATE | **86%** | ✗ |
| STEAL/THREATEN/FIGHT/SEARCH/HELP | 0.4% (1턴) | ✓ |

2026-07-09 점검(arch/40 부록)의 GOLD_ACTIONS 게이트 + FREE 제외는 부정 획득(잡담 턴 드랍)을
정확히 막았지만, 정치 음모 RPG의 핵심 루프(대화→단서→퀘스트)에 경제가 연결되지 않아
골드·장비·상점이 장식 숫자가 된 상태였다. SEARCH가 0인 것은 intent 파서가 수색류 입력을
INVESTIGATE로 흡수하기 때문 (플레이어가 수색을 안 해서가 아님).

## 설계 — 한 문장 루프

> **단서를 캐서 받은 사례금으로, 입을 닫은 자의 입을 연다.**

- **소스**: fact 발견 / questState 전환 시 사례금 (콘텐츠 정의, 총량 유한 → 파밍 불가)
- **싱크**: 정보 보류 NPC에게 BRIBE 선택지 노출 (기존 비용·클램프 로직 재사용)

## 구현

### 1. 소스 — 퀘스트 사례금 (quest.json rewards)

```jsonc
// content/<pack>/quest.json
"rewards": {
  "factGold": 5,                       // fact 1건 발견당
  "transitionGold": {                  // 단계 전환당 (키는 stateTransitions와 동일, 유니코드 →)
    "S0_ARRIVE→S1_GET_ANGLE": 10,
    "S1_GET_ANGLE→S2_PROVE_TAMPER": 15,
    "S2_PROVE_TAMPER→S3_TRACE_ROUTE": 15,
    "S3_TRACE_ROUTE→S4_CONFRONT": 20,
    "S4_CONFRONT→S5_RESOLVE": 25
  }
}
```

- 조회 API: `QuestProgressionService.getFactGoldReward()` / `getTransitionGoldReward(from, to)`
  — 미정의 시 0 (하위호환). 팩별 quest.json이므로 멀티 시나리오(arch/63) 자동 대응.
- 지급: `turns.service.ts` — `addFact()`마다 factGold, `checkTransition` 성공(본전환 +
  staleHint 자동발견 재체크) 시 transitionGold를 `questGoldReward`에 누적.
  `totalGoldDelta`(BRIBE 비용+행동 보상)는 fact 발견보다 앞서 적용되므로 별도 가산.
- 연출: `[사례금] 조사 진전의 대가 N골드` GOLD 이벤트 (`QUEST_REWARD` 태그) —
  행동 보상 `[골드]` 이벤트와 출처 구분. diff.inventory.goldDelta에는 합산 반영 (HUD).
- 총량(graymar): fact 26건 × 5 + 전환 85 = 이론 최대 215G. 실측 런(fact 5~8건, 전환 1~2회)
  기준 +45~70G — 시작 골드 30~60G와 균형.

### 2. 싱크 — 정보 구매 (BRIBE 노출)

- **감지** (`turns.service.ts` 경로 2): NPC가 미공개 fact를 보유한 채 공개가 막힌 턴
  ① 비주제 fallback 확률 게이트/질문 턴 차단으로 보류 ② trust<-20 거부 또는 판정 FAIL
  (이때 `selectRevealableFact` 조회 전용 재사용으로 보유 확인). BRIBE/THREATEN 턴 자체는 제외.
- **전달**: `bribeOpportunityNpcId` → `nanoEventCtx.bribeOpportunity = { npcId }`
  (nanoCtx 빌드는 보류 판정보다 앞이라 ui 부착 직전 주입).
- **노출** (`nano-event-director.service.ts`): `[정보 보류 국면]` 블록 — 선택지 3개 중
  정확히 1개를 affordance `BRIBE` + 해당 npcId로 생성. 라벨은 "은화 몇 닢을 슬쩍
  밀어 넣는다" 류 자연 표현 (노골적 "뇌물" 금지).
- **비용**: BRIBE 기본 비용 상향 -3/-2 → **-6/-3** (SUCCESS/PARTIAL).
  fact 사례금(5G)보다 싸면 싱크 역할 불가. `quest-balance.config.ts`
  `BRIBE_DEFAULT_COST_SUCCESS/PARTIAL`로 외부화 (불변식 30). 플레이어 명시 금액은 기존대로
  우선, 잔액 클램프(arch/40 점검 ③)도 기존 로직 그대로.

### BRIBE로 fact를 사는 경제성

BRIBE SUCCESS(-6) → bypassTrust 공개 → factGold(+5) = **순 -1G**. 정보를 돈으로 사는
행위는 소폭 적자 — 설득/신뢰 경로보다 빠르지만 공짜가 아니다. 전환 사례금이 걸린
마지막 fact에서는 흑자가 되는데, 이는 "결정적 단서에 돈을 아끼지 않는" 자연스러운 긴장.

## 검증

- `quest-progression.rewards.spec.ts` — 실팩 2종(graymar/silverdeen) rewards 파싱 +
  팩 컨텍스트 격리 조회 + rewards 미정의 하위호환 0 반환.
- `resolve.service.spec.ts` — BRIBE 기본 비용 config 참조로 기대값 갱신.
- 전체 스위트 926 passed (기존 실패 stream-classifier 2건은 무관 — 변경 전에도 실패).

## 후속 (미착수)

- INVESTIGATE 물리 수색 문맥(대상이 사물/장소) 소액 보상 — 파서 문맥 판정 정확도 확보 후.
- 장비 드랍 풀 중복 완화 + 상점 접근 노출 — 전투 빈도 활성화 논의와 함께.
- 사례금 곡선 튜닝 — 실런 15턴 골드 곡선 실측 후 quest.json 수치만 조정.

## 부록 A — 실런 검증 + CHOICE_EXPLICIT 수정 (2026-07-11)

### 플레이테스트 (20턴, DESERTER)

- 골드 45 → **152G(+107)**: `[사례금]` 6건 +75G(fact + 전환 3회) + `[골드]` 행동 보상 4건 +32G.
  이벤트 합 = diff 합 = 잔액 3자 정합. 같은 턴 이중 출처(T4: 골드12+사례금15) 분리 표기 확인.
- BRIBE 노출 0건 — 20턴 전체 `willReveal=true`(FAIL 0, trust<-20 없음, 보류 게이트 미발동).
  조건 미발생으로 인한 정상 무발동.

### BRIBE 노출 경로 강제 재현 (쥐왕, trust -10, FACT_SHADOW_INTEL 보류)

- 보류 조건 5턴 연속 `bribeOpportunity` 세팅 + nano BRIBE 선택지 매 턴 생성
  ("은화 몇 닢을 슬쩍 밀어 넣는다" 등 자연 라벨, npcId 지정) ✅
- BRIBE SUCCESS 비용 -6 차감(config 반영), FAIL 시 비용 0 ✅

### 발견 → 수정: CHOICE 명시 NPC가 대화 잠금에 밀림 (server 284d165)

쥐왕 지정 BRIBE 선택지를 클릭해도 NpcResolver가 잠금 상대(로사)를 배정 —
뇌물 대상 어긋남 + fact 구매 실패. 선택지 payload의 `sourceNpcId`/`npcId`는
구조화된 명시 지정이므로 `resolve()` **Step 0 `CHOICE_EXPLICIT`(conf 0.95)** 로
대화 잠금보다 우선 반환 (존재하지 않는 NPC는 기존 경로 fallback, ACTION 미적용).
수정 후 실런: `[NpcResolver] npcId=NPC_RAT_KING source=CHOICE_EXPLICIT` 확정.
회귀 4건 (`npc-resolver.choice-explicit.spec.ts`).

### 열린 항목

- **B. staleHint 자동 발견 fact 사례금 미지급** — 자동 구제 경로는 `addFact()` 밖에서
  직접 push하여 factGold 미적용. **현상 유지로 확정 (2026-07-11)**: 자동 발견은 시스템이
  떠먹여준 구제라 "단서 보고의 대가" 명분과 어긋나고, 지급 시 "막혀도 기다리면 벌리는"
  인센티브가 생김. 전환 사례금은 자동 발견 경유여도 정상 지급 (의도된 동작).
- BRIBE SUCCESS → 보류 NPC fact 실구매(questReveal) 최종 한 수는 런 auto-ending
  (S5+5턴)으로 미실측 — bypassTrust 공개는 기존 경로라 위험 낮음.

## 부록 B — 엔딩 완주 평가 후속 P1~P4 (2026-07-11)

엔딩 완주 테스트런(40턴, RUN_ENDED 도달) 종합 평가에서 발견된 4개 이슈의 수정 기록.
공통 뿌리: 39턴 중 26턴이 단일 장소(시장)에 갇히고 토브렌이 25턴 상주 — P1+P2의 합작.

### P1 — 무목적지 순수 이동 상용구 흡수 (server 69e8f98)

"다른 장소로 이동한다"를 LLM 파서가 TALK로 오판, merge에서 KW=MOVE_LOCATION(conf=1)이
패배 → 이동 4회 연속 대화 흡수. `detectPureMoveIntent()` — **문장 전체**가 이동
상용구인 경우만 KW_OVERRIDE (전체 매칭이라 불변식 21의 문장 속 1-hit 오탐과 비충돌).
한글 음절 합성 함정: "떠나"는 "떠난다"의 prefix가 아님 → 활용형 계열(`떠[나난날]`) 명시.
KW 단독 경로(가중치 +10, 1-hit 안전망 예외)도 정합. 회귀 17건 + 실런 확인
(`→ MOVE_LOCATION (source=RULE)` 결정론화).

### P2 — NPC 작별 발화 후 잠금 잔존 (server c4f46f9)

토브렌이 "이만 가봐야겠소" 작별을 고하고도 잠금 유지. 플레이어 FAREWELL(불변식 26)만
잠금을 끊고 NPC 쪽 경로가 없었음. `isNpcFarewellUtterance()` + 워커 5.12(최종 서술에서
primary NPC **마지막 대사** 작별 감지 → `applyRunStatePatch` CAS로 actionHistory에
`npcFarewell` 마킹) + findConversationLock/findLockFromHistory/다운그레이드 가드 3곳
break. 재대화 시 새 잠금은 허용. 회귀 20건 (실서술 fixture 체인 포함).

### P3 — 접두 융합 별칭 + 무명 화자 라벨 (server d1b0411)

"토단정한 제복의 장교 하위크" — 브렌 대위 unknownAlias에 토브렌 조각이 공백 없이
융합된 크로스 NPC 환각 (기존 stripAliasPrefixDup는 공백 있는 중복만 처리).
`stripFusedAliasPrefix`(한글 1~2자 밀착 접두 제거, 완료 후처리 + 스트리밍 새니타이즈
양쪽) + `stripAnonymousSpeakerLabels`(`행상인 1: "…"` 줄 시작 라벨, 따옴표 직전만).
회귀 7건 (실측 원문 fixture + 오탐 가드).

### P4 — 장비 유휴 (docs 5ddc821 + server 191df97)

35턴 완주에 장비 0개 (대화·조사 86% → 드랍 기대값 <0.5, 전투 0회) + 좁은 풀 중복
(EQ_RUSTY_BLADE ×2). ① quest.json `rewards.transitionEquipment` — S1→S2 순찰대 경갑,
S3→S4 정찰병 고글 (의뢰 경비 지원 서사, 전환당 1개 유한) → equipmentBag/diff/ItemMemory/
`[사례금] 의뢰 지원 장비` 이벤트. ② 드랍 보유 중복 감쇠 chance ×0.3 (rng 호출 수 동일
— 결정론 보존, 완전 차단 아님). 검증: 15턴 실런 T12 S1→S2에서 경갑 지급 전 구간 확인.
**스코프 제외**: 상점 노출 (SHOP affordance nano 미지원 + intent.target 필수 — 열린 항목),
전투 빈도 활성화 (별도 주제).

### 부록 B 이후 열린 항목

- 상점 접근성 (nano affordance SHOP 추가 + 재고 노출 UI)
- V8 카드-서술 정합 유형 (npcPortrait 갱신 로직)
- 사례금·장비 곡선 장기 튜닝 (quest.json 수치만)

## 부록 C — 마커·대사 시스템 정밀 분석 + 1·2번 수정 (2026-07-11)

재테스트(부록 B 이후)에서 부상한 이슈 2건의 수정과, 등장인물·마커·대사 시스템
전수 분석(4런 96턴, 마커 82건) 기록.

### 1번 — 무명 오귀속 (server b853c91)

Gemma가 별칭 축약형("책임자: …") 콜론 라벨을 쓰면 isKnownNpcAlias의 단방향
포함(라벨 ⊇ 별칭)이 전부 미매칭 → primary NPC 연속 발화의 마지막 대사가
@[무명 인물] 처리 (실측 6건/27턴). 경로 배제로 특정: dialogue-generator 미가동,
Step A(nano 발화자/미할당 2차 검증)는 스트리밍 스킵 — 콜론 구제가 유일 삽입기.

**`resolveColonLabelNpc` 3-Tier 유일성 매칭**: 정확 일치 → 라벨이 별칭 전체 포함
(기존 방향) → 축약(unknownAlias 마지막 1~2단어 접미/shortAlias). 각 Tier에서
**유일 후보일 때만** 승격 — '여인'(3 NPC)/'장교'(2 NPC) 다중은 무명 유지라
새 오귀속 없이 구제만 추가 (단조 개선). 승격 시 표시명+초상화 완전 마커 생성.
검증: 별칭 전수 대조(실측 라벨 전부 유일 매칭) + 실런 무명 6→1건(잔여는 즉흥
배경 인물 — 의도 동작) + 회귀 8건.

### 2번 — 카드-서술 정합 + 진입 턴 이월 (server aca9def, docs 1032d05)

① 장소 진입 턴(SYSTEM+MOVE)에 소개 카드(newly=true)가 떴는데 서술은 직전 장소
인물만 그림 — 5.9 카드 갱신의 '마커 0 + primary 일치 시 유지' 예외가 서술
미언급 케이스까지 통과 → **mentionedInNarrative 검사** 추가.
② 진입 서술 첫 문장이 직전 장소 NPC로 시작(주어 파편의 실체) — 도착 디렉티브가
대사만 금지하고 '배경 활동 허용' 틈으로 노드 무관 최근 5턴 연속성 메모리의
인물이 이월 → **'직전 인물은 이전 장소에 남음 — 등장·언급 금지' + 등장 풀을
[등장 가능 NPC 목록]으로 한정**.
③ audit V8 발화동사 '물'이 "일렁이는 물결"에 오매칭 → 활용형 정밀화.
검증: **9/9 PASS 최초 달성**, 진입 턴 3곳 이월 0건.

### 마커·대사 시스템 전수 분석 (수정 후)

| 지표 | 결과 |
|------|------|
| 고립 마커 / 8자 미만 대사 파편 | 0 / 0 |
| 무명 마커 | 수정 전 6/29 → 후 1/17~19 (잔여 = 즉흥 인물 의도 처리) |
| 미공개 실명 노출 (introduced 이전) | 0건 — arch/64 무결성 유지 |
| 하오체 화자 어체 위반 | 0/32 |
| 실명 전환 2턴 분리 | 정합 (미렐라 introducedAtTurn=31 → T31 별칭 = 설계) |
| 마커 밖 나체 대사 8건 | 전부 "행인 수군거림" fact 힌트 연출 — 의도 패턴 |

**판정**: 구조적 결함 소진 — "결함 수정" 단계에서 "관찰·튜닝" 단계로 전환.

### audit V9-c 무명 계수 정밀화 (docs 4c5a63e)

의도된 무명(즉흥 인물)이 매 검증 경고로 계수되어 진짜 회귀를 가리는 노이즈 →
직전 120자 문맥에 알려진 NPC 별칭(+유일 축약 3자 이상 — 2자 '인부'는 일반
직업명 충돌 실측으로 제외)이 있을 때만 '의심' 경고. 즉흥 오탐 0/2런 확인.
한계: 직전 문맥이 대명사뿐인 결함은 미탐 — 근본은 서버 회귀 8건으로 고정.

### 잔여 약점 처분 (2026-07-11 결정)

- **관찰 전환**: 화자-마커 어긋남(1/82), 다중 축약 무명(발생 0), 수군거림
  스트림 표시(체감 보고 0), 소품 명사 반복
- **데이터 축적 후**: 사례금·장비 곡선 튜닝 (표본 10런+)
- **별도 기획 트랙**: 상점 노출(nano SHOP affordance), 전투 빈도, 시간대 체감
- **다음 사이클 첫 후보**: 엔딩 턴 서술 피날레 (완주 2런 모두 일반 서술로 종료)
