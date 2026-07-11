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
