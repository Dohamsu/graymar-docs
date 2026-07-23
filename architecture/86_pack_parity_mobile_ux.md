# 86. 비-graymar 팩 정합 + 모바일 UX 마감

> 관련: [[63_multi_scenario_content_decoupling|멀티 시나리오 디커플링]] · [[80_pack_asset_pool|팩 에셋 풀]] · [[../guides/10_star_sand_item_prompts|아이템 프롬프트·프로세스]]
> 작성: 2026-07-23 · 상태: ✅ 구현·배포

별빛모래(star_sand_v1) 실플레이에서 드러난 **비-graymar 팩 정합 결함**과 **모바일 UX 결함**을 일괄 수정했다. 공통 뿌리는 "graymar가 기본 팩이라 우연히 동작하던 경로가, 고유 콘텐츠를 가진 팩(별빛모래·카른홀트)에서 깨진다"는 것이다.

## 1. 팩 정합 — 비-graymar 아이템/초상화

### 1-1. equip/unequip/useItem 팩 스코프 누락 (server 8651b01)
**증상**: 별빛모래 고유 장비(`EQ_SS_WHALEOIL_LAMP`) 장착 시 "Cannot equip this item" 거부, 소비품 사용도 불가.
**원인**: `equipItem`·`unequipItem`·`useItem`이 `enterScenario`(AsyncLocalStorage 팩 스코프)를 설정하지 않아, `EquipmentService.equip`의 `getItem(baseItemId)`이 **기본 팩(graymar)에서 조회 → 고유 아이템 미해석 → itemDef undefined → 거부**. `getRun`·`submitTurn` 등 다른 진입점은 모두 스코프를 잡는데 이 세 곳만 누락(arch/63 규약 사각지대).
**수정**: 세 메서드 초입에 `ensureScenario(run.scenarioId) + enterScenario(run.scenarioId)` 추가. 실증: 별빛모래 램프 장착 200(`equipped.TACTICAL`).
**규약 (불변)**: **런의 팩 콘텐츠(`getItem`/`getItemSetMap` 등)를 참조하는 모든 서비스 진입점은 `enterScenario`로 팩 스코프를 먼저 잡는다.** graymar 기본 팩 fallback으로 우연히 통과하는 경로를 신뢰하지 않는다.

### 1-2. 팩 프리셋 초상화 미표시 (client 9c72d51)
**증상**: 별빛모래·카른홀트 캐릭터 창에 초상화가 안 뜸(생성 화면에선 보이는데 게임 진입 시 사라짐).
**원인**: 이미지 파일(`preset-portraits/<pack>/*.webp`)과 매핑(`PRESET_PORTRAITS`)은 다 있으나, 게임 내 `character.portrait`(game-store.helpers)가 `adaptPresetsForScenario().find(presetId).portraits`를 참조 — 이 함수는 star_sand/karnholt에 **graymar 6종만 반환**해 SS_*/KH_* 프리셋을 못 찾아 `undefined`. StartScreen은 통합 맵 `PRESET_PORTRAITS`를 써서 뜨던 **불일치**.
**수정**: `character.portrait`를 전 팩 통합 맵 `PRESET_PORTRAITS[presetId]?.[gender]`로 조회.
**규약**: 프리셋 초상화는 팩 무관하게 `PRESET_PORTRAITS` 통합 맵으로 조회한다(graymar도 동일 결과).

### 1-3. 아이템 3층 파이프라인 (별빛모래 10종)
비-graymar 팩 아이템을 온전히 추가하려면 **서버 items.json + 클라 ITEM_CATALOG + 이미지** 3층을 모두 채워야 한다(하나라도 빠지면 부분 동작). 상세·누락 증상·체크리스트는 **guides/10 부록**. 이번에 별빛모래 10종(이미지 client 65aab2e + 카탈로그 532b2e9)을 완비했다.

## 2. 모바일 UX

### 2-1. 서술 스크롤 고정 (client a55288b)
**증상**: 모바일에서 서사 출력 후 스크롤 고정(위로 안 됨).
**원인**: flex column 스크롤 체인(GameClient 모바일·데스크톱 + NarrativePanel `overflow-y-auto` div)에 **`min-h-0` 누락**. flex item 기본 `min-height:auto`가 콘텐츠 높이를 최소로 삼아, 서사가 뷰포트를 넘으면 스크롤 컨테이너가 콘텐츠만큼 팽창 → `overflow-y-auto` 무력화 + 부모 `overflow-hidden`에 하단 잘림.
**수정**: 스크롤 체인 4곳에 `min-h-0`. 실증(browse 375×812): clientHeight 755 고정 / scrollHeight 2938, 위로 스크롤 정상.

### 2-2. 모바일 장비 해제 탭 부재 (client 9c72d51)
**증상**: 모바일 캐릭터 창에 장비는 보이나 해제 메뉴 없음.
**원인**: 해제 기능은 `EquipmentTab`(unequip)에 있는데 데스크톱 SidePanel에만 배선. 모바일 탭(Header 햄버거 메뉴)에 `equipment` 항목·렌더가 없었다. CharacterTab은 장비 표시 전용.
**수정**: Header 햄버거 메뉴에 "장비" 탭 + GameClient `mobileTab==="equipment"` → `EquipmentTab` 렌더. 실증: 램프 해제 동작.

### 2-3. 무명 인물 vs BACKGROUND 단역 아바타 차별 (client 060b7f0)
**증상**: 초상화 없는 화자(무명 인물·BACKGROUND 단역)가 동일한 `User` 아이콘으로 렌더 — 구분 불가(버그 리포트 cd14ed12 후속).
**배경**: BACKGROUND NPC는 초상화 미배정이 설계(불변식 23, 정적맵 CORE+SUB만). 무명 인물(npcId=null)과 시각 구분이 없어 위화감.
**수정 (DialogueBubble)**: 초상화 없는 화자를 2종 분기 — 무명 인물(정체 미상)은 `HelpCircle` 물음표+흐림+italic, BACKGROUND 단역(역할 식별됨)은 `User` 실루엣+또렷+역할명. CORE/SUB 초상화는 현행.

### 2-4. MobileBottomNav orphan 삭제 (client 39683b9)
모바일 탭 전환은 Header 햄버거 메뉴가 담당하며, `MobileBottomNav`는 어디서도 import·렌더되지 않는 dead code였다. 삭제(guides/02 layout 2→1 반영).

## 3. 검증
- 서버: build + 1465 유닛 + 재시작, equip 실증(API 200).
- 클라: lint·build, browse 모바일(375×812) 실증 — 초상화 로드·장비 탭 해제·스크롤 회복.
- 배포: server 8651b01, client(060b7f0·a55288b·65aab2e·532b2e9·9c72d51·39683b9) main push → Vercel.

## 4. 잔여
- karnholt·silverdeen 고유 아이템 미저작(graymar 복제만). 아이템 이미지도 별빛모래만 완비.
- 카른홀트 프리셋 초상화(KH_*)는 매핑·수정은 됐으나 이미지 파일 투입 여부 별도 확인 필요.
