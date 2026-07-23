# 10 — 별빛모래(star_sand_v1) 아이템 이미지 프롬프트

> 생성한 이미지를 **아래 표기된 파일명 그대로** `client/public/items/`에 저장하면 인벤토리·획득 연출에서 자동 표시됩니다.
> 파일명 = `itemId`의 소문자(그레이마르 26종과 동일 규약, 예: `ITEM_SS_MINOR_HEALING` → `item_ss_minor_healing.webp`). 확장자는 webp 권장(png 병행 가능).
> **주의**: 아이템 아이콘은 arch/80 팩 에셋 풀(초상화/장소, `content/<pack>/assets/`)과 **별개 경로**다. `sync_pack_assets.py`는 초상화/장소만 처리하며, 아이템은 `client/public/items/`에 직접 배치한다(공용 폴더지만 `_ss_` 접두사라 타 팩과 충돌 없음).
> 세계관: 극야(極夜)의 얼어붙은 해안. 하늘에서 떨어져 죽은 거대 별고래의 사체 위에 선 마을. 별고래 심장액·별기름·별소금이 자원이고, 오로라가 누출되며 사람들이 '오염된 꿈'에 잠긴다.

## 공통 스타일 (모든 프롬프트 앞에 붙이기)

**아이템 아이콘 공통 프리픽스** (그레이마르 아이콘 스타일 계승, 정사각 단일 오브젝트):
```
Game inventory item icon, single object centered on a dark desaturated background,
dark fantasy digital painting, dramatic rim lighting, polar-night coastal theme
with aurora teal and cold blue accents, subtle frost and faint starlight glow,
crisp readable silhouette, no text, no border, no hands, square 1:1 composition.
```

레어리티 톤 힌트: 일반 소비품은 은은한 발광, `RARE`(별기름 램프)는 또렷한 푸른 발광, `UNIQUE`(꿈 나침반)는 오로라빛 몽환적 광휘를 더한다.

---

## 1. 소비품 (CONSUMABLE) 5종

| 파일명 | 프롬프트 (공통 프리픽스 뒤에) |
|---|---|
| `item_ss_minor_healing.webp` | A small glass vial of diluted pale-red whale heart-fluid, simple cork stopper, faint rosy glow through frosted glass, a common cheap remedy. |
| `item_ss_superior_healing.webp` | An ornate refined vial of concentrated glowing crimson heart-fluid, silver filigree cap, dense dreamy luminescence, a few drops swirling, potent and slightly ominous. |
| `item_ss_stamina.webp` | A leather-wrapped flask of golden star-whale oil tonic, warm amber glow cutting through the cold blue, cork tied with cord, restorative warmth. |
| `item_ss_dream_ward.webp` | A woven charm amulet of pale crystalline star-salt threads, faint protective bluish aura, tiny knotted cord, convent craftsmanship, wards off dreams. |
| `item_ss_smoke_vial.webp` | A fragile round glass vial with dense swirling white mist trapped inside, hairline cracks, cold vapor seeping, ready to shatter for a smokescreen. |

## 2. 핵심 아이템 (KEY_ITEM) 3종

| 파일명 | 프롬프트 (공통 프리픽스 뒤에) |
|---|---|
| `item_ss_star_chart.webp` | An old worn parchment star chart, faded ink arcs tracing a great whale's fall across the sky, aurora-leak points circled, curled brittle edges, cartographic mystery. |
| `item_ss_dream_drug.webp` | A forbidden 'white door' dream-drug — pale luminous powder in a small black-market cloth pouch tied with dark thread, eerie soft glow, illicit and dangerous. |
| `item_ss_name_ledger.webp` | A worn leather-bound ledger of names, open to handwritten true names and vanished-dates in cramped ink, a thin quill resting across it, somber and secretive. |

## 3. 장비 (EQUIPMENT) 2종

| 파일명 | 레어리티 / 슬롯 | 프롬프트 (공통 프리픽스 뒤에) |
|---|---|---|
| `eq_ss_whaleoil_lamp.webp` | RARE / TACTICAL | A dockmaker's brass-and-iron lantern burning a cold blue whale-oil flame that never dies, steady bright glow against darkness, weathered metal, clearly enchanted light source. |
| `eq_ss_dream_compass.webp` | UNIQUE / RELIC | A strange ornate brass compass whose needle points not north but toward a whale's heart, dreamlike aurora shimmer reflecting on its cracked glass, worn engravings, otherworldly relic aura. |

---

## 반영 절차

1. 위 프롬프트로 이미지 10종 생성 (Gemini 2.5 Flash 등, 정사각 아이콘).
2. 표기 파일명 그대로 `client/public/items/`에 저장 (webp 권장).
3. client push → Vercel 자동 배포 (서버 재시작 불필요 — 아이템 이미지는 정적 자산, 파일명 규약만 맞으면 즉시 표시).
4. 파일명이 `itemId` 소문자와 정확히 일치해야 매칭됨. 불일치 시 기본 아이콘/무표시.

---

## 부록: 새 아이템 추가 전체 프로세스 (서버·클라·이미지 3층)

아이템 1종을 온전히 추가하려면 **3곳**을 손봐야 한다. 하나라도 빠지면 아래 "누락 시 증상"처럼 부분 동작한다.

### 1층 — 서버 콘텐츠: `content/<pack>/items.json`
게임 로직(효과·수치)의 정본. 필드:
- `itemId` — ID 규약: `ITEM_*`(소비/핵심), `EQ_*`(장비), `CLUE_*`(단서). 팩 고유 아이템은 팩 접두사 권장(`ITEM_SS_*`) — 공용 `client/public/items/` 폴더에서 타 팩과 파일명 충돌 방지.
- `name`, `type`(`CONSUMABLE`|`KEY_ITEM`|`CLUE`|`EQUIPMENT`), `description`
- **소비품**: `combat.effect` = `HEAL_HP` | `RESTORE_STAMINA` | `FLEE_BONUS` 등 (실제 효과·수치는 서버가 처리)
- **장비**: `rarity`, `slot`, `statBonus`(예: `{acc:3, eva:1}`), `setId`(세트효과 시)
- **반영**: 서버 재시작(`pnpm build` + `launchctl kickstart`) — 콘텐츠는 팩 로드 시 1회 캐시.

### 2층 — 클라 카탈로그: `client/src/data/items.ts` `ITEM_CATALOG`
UI 표시·버튼 노출 메타. `itemId → ItemMeta { name, type, description?, usableInHub?, rarity?, slot?, statBonus?, icon?, setId? }`
- **`usableInHub`** = 서버 `combat.effect`가 `HEAL_HP`/`RESTORE_STAMINA`일 때만 `true`. → 전투 밖(HUB/LOCATION) **사용 버튼** 노출 조건. `FLEE_BONUS`·단서·핵심템은 생략(false).
- CONSUMABLE/KEY_ITEM은 `icon` 생략, EQUIPMENT는 graymar 관례상 `icon`(lucide명) 넣지만 **이미지가 있으면 이미지 우선**이라 생략 가능.

### 3층 — 이미지: `client/public/items/<itemId 소문자>.webp`
- 경로 규약: `getItemImagePath(id)` = `/items/${id.toLowerCase()}.webp` (예: `EQ_SS_DREAM_COMPASS` → `eq_ss_dream_compass.webp`).
- 프롬프트: 이 문서 §공통 스타일 프리픽스 + 오브젝트 묘사. 레어리티별 발광 톤 차등.
- **arch/80 팩 에셋 풀(초상화/장소, `content/<pack>/assets/`)과 별개 경로** — `sync_pack_assets.py` 대상 아님. 파일을 직접 배치한다.
- **반영**: client `main` push → Vercel 자동 배포(정적 자산, 서버 재시작 불필요).

### 누락 시 증상
| 빠뜨린 층 | 증상 |
|---|---|
| 1층(items.json) | 아이템 자체가 게임에 없음(획득/드랍/상점 불가) |
| 2층(ITEM_CATALOG) | 이미지는 떠도 소비품 **HUB 사용 버튼 미노출**(`usableInHub` 미동작), 일부 UI 메타 누락 |
| 3층(이미지) | 이미지 없이 **기본 아이콘/무표시**(파일명 불일치도 동일) |

### 체크리스트
- [ ] `items.json` 정의 (효과 `combat.effect` / 장비 `rarity·slot·statBonus·setId`)
- [ ] `ITEM_CATALOG` 등록 (`usableInHub`는 effect 기준 판정)
- [ ] 이미지 생성 + `itemId` 소문자 `.webp`로 `client/public/items/` 배치
- [ ] 서버 재시작(콘텐츠 변경 시) + 클라 `main` push

