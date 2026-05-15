# 소지품 UX 개선 + LLM-실획득 아이템 정합성

> 작성 2026-04-20. 커밋: server 46a7a59 / client 0462ffc / docs 73ad71d

## 1. 소지품 UX 개선 (InventoryTab + 장비 토스트 + 에러 한국어화)

### 1-1. 장비 교체 확인 다이얼로그 (High)
- 파일: `client/src/components/side-panel/InventoryTab.tsx`
- 기존: "장착" 버튼 클릭 시 즉시 `equipItem` 호출 → 기존 슬롯 점유 시 자동 덮어쓰기, 경고 없음 (레어/레전드리 실수 유발)
- 수정:
  - `handleEquip()`에서 `characterInfo.equipment`의 slot 매치 확인
  - 빈 슬롯: 즉시 장착 (기존 동작)
  - 점유 슬롯: `equipConfirm` state로 모달 표시 → 해제될 장비(빨강 카드) + 장착할 장비(초록 카드) 비교 → [취소] / [교체]
- 컴포넌트: `EquipReplaceModal`, `EquipCompareCard` (파일 내 정의, rarity 색상/스탯 보너스 병치)

### 1-2. USABLE_ITEMS 동적화
- 기존: 하드코딩 Set 3개 (`ITEM_MINOR_HEALING`, `ITEM_SUPERIOR_HEALING`, `ITEM_STAMINA_TONIC`)
- 수정:
  - `ItemMeta.usableInHub?: boolean` 필드 추가
  - `isUsableInHub(itemId)` 헬퍼 export
  - HEAL_HP/RESTORE_STAMINA 효과 아이템만 `usableInHub: true`
  - 향후 items.json에 새 소모품 추가 시 catalog 한 줄만 추가하면 자동 반영
- 전투 중(`currentNodeType === 'COMBAT'`)엔 사용 버튼 `disabled` + 툴팁

### 1-3. EquipmentDropToast (장비 획득 토스트)
- 파일: `client/src/components/location/EquipmentDropToast.tsx`
- 기존: 소모품은 `InventoryTab` "NEW" 배지 + `+N` 애니메이션이 있지만 장비는 서술 LOOT 텍스트만 있어 놓치기 쉬움
- 수정:
  - 우측 하단 플로팅 배너
  - rarity별 색상 테두리 (COMMON 회색 / RARE 파랑 / UNIQUE 보라 / LEGENDARY 골드)
  - 썸네일 + `displayName` + "장비 획득" 라벨 + rarity
  - 5초 자동 페이드 + 클릭 시 즉시 닫힘, 최대 3개 동시 표시, 초과 시 "외 N개"
- 상태 관리:
  - `game-store.recentEquipmentDrops: EquipmentBagItem[]` + `clearRecentEquipmentDrops` 액션
  - 턴 응답 처리에서 `diff.equipmentAdded` 감지 시 세팅
- `GameClient`에서 HUB/LOCATION/COMBAT phase 모두 렌더

### 1-4. 에러 문구 한국어화
- `game-store.ts`에 `ERROR_MESSAGE_I18N` 매핑 테이블 (10 case)
- `translateApiMessage()` 헬퍼로 영어 메시지 → 한국어 변환
- 기존 `[CODE] message` 접두사 제거
- 주요 케이스
  - `Cannot use items during combat` → "전투 중에는 소모품을 사용할 수 없습니다"
  - `Item not found in inventory` → "해당 아이템이 소지품에 없습니다"
  - `Cannot equip this item` → "이 아이템은 장착할 수 없습니다"
  - `No equipment in slot` → "이 슬롯에는 해제할 장비가 없습니다"
  - 외 6종

---

## 2. LLM 서술-실획득 정합성 (A+B 구조)

### 2-1. 문제 배경
- 서버 diff 확정 타이밍은 정상(commit 전 diff 고정 후 LLM 호출)
- 그러나 시스템 프롬프트에 **아이템 언급 제한 규칙 전무** → LLM이 "열쇠를 건넸다"처럼 서버 diff와 무관하게 자의적 서술 가능
- GOLD_ACTIONS 외 행동(TALK/PERSUADE/BRIBE/INVESTIGATE)에선 **아이템 지급 경로 자체가 존재하지 않음** → LLM 서술만의 환상
- 결과: 플레이어가 "인장을 받았다" 서술을 보고 인벤토리를 열어도 비어있음 (UX 함정)

### 2-2. A. 프롬프트 제한 + 컨텍스트 주입
- `server/src/llm/prompts/system-prompts.ts` 최우선 금지 규칙에 항목 2개 추가
  - 3번: 구체적 아이템 획득/증여 서술 금지. `[이번 턴 획득 아이템]` 블록에 있는 아이템만 "건넸다/건네받는다/손에 쥐여졌다" 사용 가능. 없거나 매칭 안 되면 "무언가를 손에 쥐여준다" 같은 추상 표현 또는 대화·태도 변화로 대체
  - 4번: 골드(화폐) 증여도 동일 제한
- `server/src/llm/prompts/prompt-builder.service.ts`에 `[이번 턴 획득 아이템]` 블록 신설
  - `sr.diff.inventory.itemsAdded` + `sr.diff.equipmentAdded` + `goldDelta` 취합
  - 아이템 이름은 `content.getItem()`으로 한글 표시명 변환
  - **없을 때도 "없음"** 명시 + "구체적 아이템 서술 금지" 지침 주입 → 침묵 상태의 자의적 생성 억제

### 2-3. B. 이벤트 payload.itemRewards 경로
- `server/src/db/types/event-def.ts`에 신설
  ```ts
  type EventItemReward = {
    itemId: string;
    qty?: number; // default 1
    condition: 'SUCCESS' | 'SUCCESS_OR_PARTIAL';
  };
  type EventPayload = { ..., itemRewards?: EventItemReward[] };
  ```
- `server/src/turns/turns.service.ts` LOCATION 경로(2613~)에 지급 로직
  - `event.payload.itemRewards`를 `resolveResult.outcome`으로 필터
  - `updatedRunState.inventory.push` + `locationReward.items` 병합 (buildLocationResult가 자동으로 diff.inventory.itemsAdded 생성)
  - LOOT 이벤트 tags: `['LOOT','ITEM_REWARD']`
- GOLD_ACTIONS 제한과 **독립**: TALK/PERSUADE/BRIBE/INVESTIGATE 어느 행동에서든 콘텐츠가 선언한 itemRewards 지급 가능
- 지급된 아이템은 기존 diff 파이프라인을 통해 `InventoryTab` 하이라이트 + 토스트 자동 연결

### 2-4. 콘텐츠 매핑 (T1 + T2)
- `content/graymar_v1/events_v2.json` itemRewards 매핑 3건
  - `EVT_SLUMS_FACTION` → `ITEM_GUILD_BADGE` (하를런 길드 협력)
  - `EVT_GUARD_FACTION` → `ITEM_GUARD_PERMIT` (벨론 경비대 동맹)
  - `EVT_WAREHOUSE_DSC_1` → `ITEM_SMUGGLE_MAP` (창고 수첩 발견)
- `content/graymar_v1/shops.json` stockPool 2건
  - `SHOP_GUILD_TRADER += EQ_MERCHANT_CLOAK`
  - `SHOP_SLUMS_BLACK_MARKET += EQ_SHADOW_CLOAK`

### 2-5. 효과 — 획득 불가 아이템 0개
점검 결과 매트릭스에서 기존 7개 공백(KEY_ITEM 3종 전무 + EQUIPMENT 2종 희귀 + CONSUMABLE 2종 상점만)이 T1+T2 이후 전부 해결됨. EQ_RELIC_TIDE_COMPASS는 기존 `legendary-reward.service.ts` 경로 유지.

---

## 3. 현재 획득 매트릭스 (2026-04-20 기준)

| Type | 획득 경로 수 | 비고 |
|------|--------------|------|
| CONSUMABLE (5) | 5/5 획득 가능 | ITEM_SUPERIOR_HEALING, ITEM_SMOKE_BOMB는 상점 전용 |
| KEY_ITEM (3) | 3/3 획득 가능 (이벤트 itemRewards) | T1 매핑 적용 |
| CLUE (3) | 3/3 획득 가능 (인카운터 clueChance) | 기존 설계 유지 |
| EQUIPMENT (15) | 15/15 획득 가능 | 전투 드랍 + 상점 + 전설 보상 |

---

## 4. E2E 검증 (2026-04-20)

- 서버·클라 빌드 통과 + 전체 테스트 530/530 회귀
- 20턴 playtest 자동 실행 → `equipmentBag`에 실제 4개 장비 적재 확인 (순찰대 경갑 ×2, 정찰병 고글, 밀수업자 단검)
- Playwright로 로그인 → "이어하기" → InventoryTab 스크린샷: 4개 장비 + rarity 뱃지 + 스탯 + "장착" 버튼 정상
- "장착" 클릭 → 빈 슬롯이라 즉시 장착 후 가방 4→3 감소
- 브라우저에서 "창고를 뒤진다" 턴 제출 → 4초 후 `EquipmentDropToast` 실시간 캡처 (밀수업자의 단검 RARE, 파란 테두리)

---

## 5. 후속 과제 (선택)

- **LLM 서술 후처리 검열**: `[이번 턴 획득 아이템]`에 없는 아이템이 서술에 등장 시 regex 감지 → 검열 or 재생성 (풍선효과 방지, 현재는 프롬프트 규칙만)
- **arcRewards 실 지급**: 현 단일 런 구조에선 RUN_ENDED 후 소비 경로 없어 보류. 캠페인 연속 구조 도입 시 gold/reputation 자동 반영
- **콘텐츠 확장**: events_v2.json의 다른 NPC 대화 이벤트에도 itemRewards 점진 추가 (작가 작업)
- **SetBonus 사전 시뮬레이션**: 가방 아이템 hover 시 "이걸 장착하면 세트 N/4" 예측 표시
