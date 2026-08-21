# 108 — 자연스러운 장비 획득 경로

> 상태: ✅ 구현됨 · 2026-08-21 (server 커밋 예정)
> 실증: A 관계 선물(하를런 trust 40 → TALK 턴 방수 조끼 지급, npcGifts 1회) · B 단서
> 은닉(FACT_SHADOW_INTEL 발견 → 빈민가 조사 성공 시 그림자 망토, claimedFactCaches 1회,
> FAIL 턴은 재시도 가능) · C 코어 스펙 23건 · HELP 드랍 제거 · audit_content 모양 검사 통과
> 관련: [[65_economy_loop_v1|arch/65]] (bribeOpportunity·사례금) · [[89_quest_reward_attribution|arch/89]]
> (지급 주체 원칙) · [[40_inventory_item_integrity|arch/40]] ([이번 턴 획득 아이템] 정합) ·
> 불변식 1(서버 정본) · 44(사교 발화 게이트) · 45(콘텐츠 ID 외부화)

## 1. 배경 — 실측

30일 LOCATION 자유행동 1,102턴 중 장비 드랍 자격(GOLD_ACTIONS: STEAL·THREATEN·FIGHT·
SEARCH·HELP + SUCCESS/PARTIAL)이 있는 턴은 **104턴(9.4%)**. 지배적 플레이인
TALK(283)+INVESTIGATE(242)+PERSUADE(143) = **61%가 장비 획득 경로에서 배제**된다.
"게임이 권장하는 대화·조사 플레이를 할수록 장비를 못 얻는" 역설. 나머지 획득도
무작위 테이블 롤이라 서사적 근거(왜 거기 있었는지)가 없다.

**설계 원칙**: 자연스러움은 확률이 아니라 **관계·단서라는 서사적 근거**에서 나온다.
대화 턴 무작위 드랍 재개방은 역회귀(2026-07-09 "인사했더니 만도" 게이트 이력)이므로
하지 않는다. 모든 신규 경로는 ① 서버 결정론 발동(불변식 1) ② 런당 1회(파밍 불가)
③ `[이번 턴 획득 아이템]` 블록 경유 서술 정합(arch/40) ④ 콘텐츠 필드 저작(불변식 45)
의 4계약을 지킨다.

## 2. A — NPC 관계 선물 (대화 플레이 보상)

신뢰가 임계에 도달한 NPC가 자기 직업·성격에 맞는 장비를 **1회** 건넨다.

- **콘텐츠 계약** (`npcs.json`, optional):
  ```json
  "gift": { "itemId": "EQ_PATROL_ARMOR", "trustMin": 30, "note": "인정의 표시" }
  ```
- **발동 (서버 결정론, LOCATION 턴 파이프라인)**: 판정 NPC(primaryNpc)가 gift 보유 &&
  `emotional.trust >= trustMin` && 대화 계열 행동(TALK/PERSUADE/HELP/TRADE) &&
  outcome ≠ FAIL && dialogueAct ≠ FAREWELL && `runState.npcGifts`에 미기록.
- **지급**: `grantQuestEquipment` 재사용(무접미사 기본 인스턴스) → equipmentBag +
  `diff.equipmentAdded`(획득 블록 발화) + ItemMemory("〈NPC〉의 선물") +
  `npcGifts.push(npcId)`.
- **임계 근거**: D족 실측 trust p99=31 — 30선이면 "공들인 유저만 도달"하는 희소성.

## 3. B — 단서 연계 은닉 장비 (조사 플레이 보상)

발견한 fact가 가리키는 장소에서 조사하면 **확정 획득**. 단서가 아이템의 존재 이유를
설명한다 ("장부에서 은닉처를 알아냈다 → 그 창고에 실제로 있다").

- **콘텐츠 계약** (`facts.json`, optional):
  ```json
  "cache": { "itemId": "EQ_SHADOW_DAGGER", "locationId": "LOC_HARBOR" }
  ```
- **발동**: 현재 장소 == `cache.locationId` && actionType ∈ {INVESTIGATE, SEARCH} &&
  outcome ∈ {SUCCESS, PARTIAL} && factId ∈ `discoveredQuestFacts` &&
  `runState.claimedFactCaches`에 미기록. 복수 후보면 첫 미수령 1건만.
- **지급**: A와 동일 경로 + ItemMemory("단서로 찾아낸 은닉물") + `claimedFactCaches.push`.
- 주사위는 그대로 굴린다(INVESTIGATE/SEARCH는 도전 행동) — FAIL이면 다음 턴 재시도
  가능(단서를 이미 아는 상태라 재도전이 서사적으로 자연).

## 4. C — NPC 개인 거래 (골드 소비처)

정식 상점이 아닌 NPC가 맥락상 팔 만한 물건 1점을 제안·판매한다.

- **콘텐츠 계약** (`npcs.json`, optional):
  ```json
  "personalTrade": { "itemId": "EQ_MERCHANT_RING", "price": 25 }
  ```
- **발견성**: `nanoEventCtx.tradeOffer { npcId, itemName, price }` — bribeOpportunity
  (arch/65)와 동일한 "선택지 3개 중 정확히 1개 강제" 메커니즘. 대화 잠금 중이거나
  primaryNpc가 해당 NPC이고 미판매·잔액 충분일 때 노출.
- **실행 (결정론, 선택지 클릭과 자유 입력 모두)**: actionType == TRADE && 대상 NPC 일치
  && outcome ≠ FAIL && gold ≥ price → 골드 −price + 지급(A 경로) +
  `personalTradesDone.push(npcId)`. nano 선택지는 발견성 보조일 뿐, 실행 판정은
  서버가 인텐트로 한다(choiceId 왕복 의존 없음 — arch/98 nano riskLevel 교훈).
- 사례금(fact 5G)·BRIBE(-6/-3)와의 가격 정합: price는 장비 가치에 맞춰 20~40G 선.
  경제 루프의 골드 소비처 부족(arch/89) 보완.

## 5. 대화 턴 랜덤 드랍 제거 (소유자 지시 2026-08-21)

`GOLD_ACTIONS`에서 **HELP만 대화 계열**(불변식 44: TALK/PERSUADE/TRADE/HELP)인데
장비 드랍 자격에 포함돼 있었다 — "도와줬더니 무기가 떨어지는" 마지막 랜덤 경로.

- 신설 `EQUIPMENT_DROP_ACTIONS = {STEAL, THREATEN, FIGHT, SEARCH}` (물리 탐색·탈취만).
  **장비 드랍 게이트만** 이 집합으로 교체하고, 골드 보상(GOLD_ACTIONS)은 불변 —
  HELP 성공의 골드 사례는 유지된다 (호의에 대한 금전 답례는 자연스러움).
- HELP의 장비 보상은 A(관계 선물)로 대체된다 — HELP가 trust를 올리므로 경로가
  "무작위 → 관계 축적"으로 자연 이동.

## 6. 콘텐츠 파일럿 (graymar_v1)

| 경로 | 대상 | 내용 |
|------|------|------|
| gift | CORE NPC 2명 | 직업 정합 장비 (trustMin 30) |
| cache | fact 2건 | 기존 장소 드랍 테이블의 상위 아이템을 단서 연계로 이전 |
| personalTrade | SUB 상인계 NPC 1명 | 액세서리류 20~40G |

`audit_content.py`에 모양 검사 신설(사문 배선 방지 — arch/21 Part 11 교훈):
gift/cache/personalTrade의 itemId·locationId 참조 실존, price > 0, trustMin 수치형.

## 7. 파일 변경 요약

| 파일 | 변경 |
|------|------|
| `engine/rewards/rewards.service.ts` | `EQUIPMENT_DROP_ACTIONS` 신설 |
| `turns/turns.service.ts` | 드랍 게이트 교체 + A·B·C 발동 로직 (지급은 공용 헬퍼) |
| `content/content-loader.service.ts` | gift/cache/personalTrade 접근 API |
| `content.types.ts` | NPC/Fact 타입 확장 |
| `db/types/permanent-stats.ts` (RunState) | `npcGifts`·`claimedFactCaches`·`personalTradesDone` |
| `llm/nano-event-director.service.ts` | `tradeOffer` 컨텍스트 (bribe 미러) |
| `content/graymar_v1/{npcs,facts}.json` | 파일럿 저작 |
| `scripts/audit_content.py` | 모양 검사 3종 |

## 8. 테스트·검증

1. 단위: 발동 조건 스펙 (임계·1회 한정·FAIL 제외·FAREWELL 제외·잔액 부족).
2. E2E 프로브: trust 주입 → 대화 턴 선물 실측 / fact 발견 → cache 장소 조사 실측 /
   TRADE 구매 실측 / HELP SUCCESS 턴 장비 드랍 0 확인.
3. 게이트: 기존 스모크·단위 전체 회귀 0.

## 9. 잔여·후속

- star_sand·karnholt 콘텐츠 확장 (파일럿 검증 후).
- gift 발동률·cache 수령률 계측 (arch/101 디텍터 후보).
- C의 nano tradeOffer 노출 빈도 튜닝 (과노출 시 장사꾼화).
