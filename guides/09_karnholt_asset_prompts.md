# 09 — 카른홀트 에셋 생성 프롬프트 (arch/80 팩 에셋 풀용)

> 생성한 이미지를 **아래 표기된 파일명 그대로** `content/karnholt_v1/assets/portraits/`(초상화) · `assets/locations/`(장소)에 저장하면 자동 매칭됩니다.
> 파일명의 한글 키워드가 매칭 힌트입니다 — 확장자는 webp 권장(png/jpg 가능).
> 세계관: 왕국 북부 산악 국경의 은광·주조 도시. 안개 낀 갱도, 주화를 찍는 화로, 무게가 안 맞는 주화가 도는 검은 시장.

## 공통 스타일 (모든 프롬프트 앞에 붙이기)

**초상화 공통 프리픽스** (그레이마르 초상 스타일 계승, 4:5 세로):
```
Dark fantasy character portrait, digital oil painting, chest-up bust shot,
muted earth tones with cold iron-gray and silver accents, dramatic side lighting
from a forge glow, plain dark textured background, gritty medieval realism,
detailed face, no text, aspect ratio 4:5.
```

**장소 공통 프리픽스** (16:9 가로):
```
Dark fantasy environment concept art, digital painting, cinematic wide shot,
medieval mining frontier town in northern mountains, muted earth tones,
iron gray, silver, ember orange highlights, fog and cold air, gritty realism,
no people in focus, no text, aspect ratio 16:9.
```

---

## 1. 코어 NPC 초상화 6장

| 파일명 | 프롬프트 (공통 프리픽스 뒤에) |
|---|---|
| `f_메린_과부_의뢰인.webp` | A resolute widow in her late 30s, plain wool dress and a miner's scarf around her shoulders, tired eyes that refuse to break, jaw set with quiet determination, work-worn hands clasped, candlelight warmth against cold gray stone. |
| `m_발드릭_감독관_관료.webp` | A cold royal mint warden in his 50s, immaculate black-and-gold official robe with a silver chain of office, thin lips, calculating stare over a ledger, frost-pale skin, precise and humorless, bureaucratic authority. |
| `m_토르그_길드장_광부.webp` | A burly mining guildmaster in his 50s, gray-streaked beard, scarred forearms, leather vest over a rough tunic, coal dust in the creases of his weathered face, weary but protective eyes of a man carrying his people. |
| `f_카이라_밀수_두목.webp` | A sharp-eyed smuggler boss in her 30s, dark hooded traveling coat with hidden pockets, a faint confident smirk, a counterfeit silver coin held between two fingers, shrewd intelligence, lantern light from below. |
| `f_오슬라_술집_안주인.webp` | A shrewd tavern keeper in her 40s, rolled-up sleeves and a stained apron, dish rag over one shoulder, knowing half-smile of someone who hears every rumor in town, warm hearth light, sturdy and unshakable. |
| `m_옌_각인_조각공.webp` | A timid coin engraver in his 20s, thin frame hunched over, magnifying lens strapped to his forehead, ink and metal-dust stained fingers, nervous darting eyes that know too much, workshop clutter behind. |

## 2. 범용 동적 NPC 초상화 10장 (자율 생성 인물용)

카른홀트가 즉석에서 만들어내는 인물들이 씁니다. 직군 키워드가 역할 텍스트와 매칭됩니다 — **여러 장 만들수록 새 인물이 다양한 얼굴을 갖습니다.**

| 파일명 | 프롬프트 (공통 프리픽스 뒤에) |
|---|---|
| `m_광부_중년.webp` | A middle-aged silver miner, soot-blackened face, headlamp candle on a leather cap, pickaxe over shoulder, hollow cheeks, cautious eyes. |
| `m_광부_젊은.webp` | A young miner barely out of his teens, dirt-smudged hopeful face, oversized borrowed helmet, rope coiled across his chest. |
| `f_광부_강단.webp` | A tough female miner in her 30s, hair tied back with a rag, coal dust freckles, defiant tired gaze, gloved hands. |
| `m_경비_초소병.webp` | A border post guard, dented kettle helmet and patched gambeson, spear resting on shoulder, bored but bribable expression, breath visible in cold air. |
| `f_서기_장부.webp` | A young female clerk of the mint office, ink-stained fingers, tight bun, wire-frame spectacles, guarded polite expression, ledger clutched to chest. |
| `m_상인_행상.webp` | A traveling peddler with a heavy fur-lined coat, scales and coin pouch at his belt, friendly merchant smile that never reaches the eyes. |
| `f_상인_노점.webp` | A market stall woman in her 50s, layered shawls against the cold, sharp bargaining eyes, weighing a suspicious coin in her palm. |
| `m_밀수_거간.webp` | A wiry smuggler's middleman, scarred eyebrow, collar turned up, glancing sideways, half his face in shadow under a brim hat. |
| `f_노파_소문.webp` | An old woman of the miners' camp, deeply lined face, knitted headscarf, eyes that have watched this town for sixty years, small knowing smile. |
| `m_잡부_뜨내기.webp` | A drifting laborer of no fixed trade, patched coat, stubble, wary hunted look of a man who owes someone money. |

## 3. 장소 이미지 8곳 (+밤 변형 권장 3곳)

파일명의 영문 키워드가 장소 ID와 매칭됩니다 (`day`/`night`는 시간대 필터).

| 파일명 | 프롬프트 (공통 프리픽스 뒤에) |
|---|---|
| `tavern_day.webp` | Interior of "The Broken Pickaxe" tavern — low-beamed miner's alehouse, long scarred wooden tables, pewter mugs, a cracked pickaxe mounted above the hearth, murky daylight through small windows, smoke and rumor in the air. |
| `tavern_night.webp` | Same tavern at night — packed with off-shift miners, roaring hearth as the only light, long shadows, dice and hushed conversations in corners. |
| `foundry_day.webp` | The royal coin foundry — glowing crucibles pouring molten silver, coin press machines stamping, sparks and steam, guards at every door, wealth and heat under strict watch. |
| `mine_day.webp` | Silver mine gallery entrance carved into a fog-wrapped mountainside, timber supports, ore carts on rails, lantern chain fading into darkness, drip of water echoing. |
| `mine_night.webp` | The mine mouth at night — a black maw in the mountainside, one swaying lantern, snow dusting the ore carts, unsettling silence. |
| `camp_day.webp` | Miners' shantytown clinging to the slope below the mine — leaning plank shacks, frozen laundry lines, thin smoke from stovepipes, mud paths, poverty and quiet resentment. |
| `office_day.webp` | The mint warden's administration hall — cold stone interior, towering shelves of ledgers, brass scales on every desk, wax seals, a portrait of the king, oppressive orderliness. |
| `market_day.webp` | Back-alley black market between leaning timber buildings — crowded stalls under canvas, furs and contraband, coins tested by biting, watchful faces in doorways. |
| `market_night.webp` | The black market after dark — lantern-lit stalls, silhouettes exchanging pouches, snow falling through torchlight, danger in the quiet. |
| `gate_day.webp` | The kingdom's border checkpoint — palisade wall and wooden watchtower across a mountain pass, barrier arm over a rutted road, guards inspecting a cart, mist rolling down the peaks. |
| `deepshaft_day.webp` | The abandoned deep shaft — flooded lower gallery of a spent silver vein, collapsed beams, black water reflecting a single lantern, air thick and wrong, something hidden in the dark. |

## 4. 보너스 (선택)

| 파일명 | 용도 · 프롬프트 |
|---|---|
| `banner_카른홀트.webp` → `locations/`에 | 시나리오 선택 배너 (풀 첫 이미지가 배너로 쓰이므로 파일명 사전순 앞이 유리 — `a_banner_카른홀트.webp` 권장): Sweeping aerial view of Karnholt — a fortified mining town wedged in a snowy mountain pass, smoke rising from the royal foundry, mine entrances dotting the slopes, gray peaks and low fog, last light of dusk. |

---

**저장 후 절차**: 저에게 "이미지 넣었어"라고 알려주시면 sync → 서버 재시작 → 클라 배포를 진행합니다 (CLAUDE.md 팩 에셋 풀 정책).
