# 06 — 로케이션 이미지 생성 프롬프트

> 그레이마르 항구 도시 및 4개 LOCATION별 이미지 생성 프롬프트
> 기반 데이터: `content/graymar_v1/locations.json`, `content/graymar_v1/scene_shells.json`
> 조합: 시간대(DAY/NIGHT) × 안전도(SAFE/ALERT/DANGER) 중 대표 선별

---

## 공통 스타일 키워드

모든 프롬프트에 공통 적용되는 스타일 지침:

| 항목 | 값 |
|------|-----|
| 장르 | Dark Fantasy, Medieval Port City |
| 화풍 | Digital Painting / Oil Painting, Cinematic Composition |
| 톤 | Gritty Realism, Political Intrigue |
| 색감 | Muted earth tones, rust, teal, weathered gold |
| 해상도 | 16:9 landscape 권장 |

---

## 1. 그레이마르 항구 도시 — 전체 조감도

**용도**: 게임 타이틀, 로딩 화면, 도시 소개

```
A sweeping aerial view of a medieval port city called Graymar Harbor,
nestled along a rugged southern coastline. The city is built on tiered
terrain — a bustling harbor district at sea level with wooden piers and
tall-masted trade ships, a crowded market district climbing the hillside
with colorful awnings and narrow streets, a fortified guard quarter with
stone barracks and watchtowers flying pennants, and a sprawling slum
district in the shadowed lower quarters with ramshackle buildings and
winding dark alleys. The overall atmosphere is gritty and politically
tense — a place where corruption festers beneath the surface of commerce.
Overcast sky with shafts of golden light breaking through clouds.
Dark fantasy aesthetic, muted earth tones with accents of rust, teal,
and weathered gold. Oil painting style, highly detailed, cinematic
composition.
```

---

## 2. 시장 거리 (LOC_MARKET)

### 2-1. 낮 / SAFE

**용도**: 시장 거리 기본 배경

```
A lively medieval marketplace street in a port city. Sunlight streams
down onto rows of merchant stalls piled high with exotic fruits, spices,
and bolts of fabric. Hawkers shout over each other to attract customers.
Children dart between wooden carts. The smell of grilled meat hangs in
the air. Colorful canvas awnings in faded reds, yellows, and greens
stretch over the cobblestone street. In the background, a stone clock
tower rises above the rooftops. The crowd is diverse — sailors,
merchants, housewives haggling, and a few hooded figures listening to
whispered gossip. Warm golden lighting, bustling energy, gritty medieval
realism. Dark fantasy aesthetic with a sense of hidden intrigue beneath
the cheerful surface. Detailed digital painting, cinematic perspective.
```

### 2-2. 밤 / SAFE

**용도**: 야시장 분위기, 밤 탐색

```
A medieval night market illuminated by hanging oil lanterns and torches.
Stalls that weren't there during the day line the narrow street, selling
exotic goods and illicit wares. Gamblers huddle around a dice table under
flickering light. Laughter and the clink of tankards spill from a tavern
doorway. Warm amber glow against deep blue-black shadows. Cobblestones
glisten with moisture. Mysterious hooded figures browse the stalls. The
atmosphere is lively but secretive — deals happen in whispers. Dark
fantasy, painterly style, rich chiaroscuro lighting.
```

### 2-3. 낮 / DANGER

**용도**: 긴장 고조, 계엄 분위기

```
A medieval marketplace under oppressive martial control. Empty merchant
stalls line the cobblestone street — their owners fled or arrested.
Armed patrol squads in heavy armor march past, scanning every face. Fresh
wanted posters plaster the stone walls. A lone merchant packs his wares
with trembling hands. The colorful awnings are torn and faded. The clock
tower looms in the background under a grey, threatening sky. The once
bustling street feels like a ghost town under occupation. Cold desaturated
palette — grey stone, muted fabric, steel glint of weapons. Dark fantasy,
oppressive atmosphere, cinematic wide shot.
```

---

## 3. 경비대 지구 (LOC_GUARD)

### 3-1. 낮 / SAFE

**용도**: 경비대 지구 기본 배경

```
A fortified military district in a medieval port city. A stone-paved
plaza fronts a large guard headquarters building with iron-reinforced
doors and narrow arrow-slit windows. Banners with the city crest flutter
from tall poles. Armored soldiers in formation perform a shift change,
their plate armor gleaming dully. A courier rushes past with sealed
documents. Citizens queue at a petition window. The architecture is
imposing — thick stone walls, watchtowers, iron gates. Everything is
orderly and disciplined, but an underlying tension suggests surveillance
and control. Cool grey and steel blue palette with military precision.
Overcast lighting, detailed medieval military architecture. Digital
painting, cinematic composition.
```

### 3-2. 밤 / ALERT

**용도**: 야간 순찰 강화, 긴장감

```
A medieval military district at night under heightened alert. Torch-
bearing patrols march through the streets in pairs, their armor clanking
in the silence. Every intersection is manned by armed sentries checking
papers. The barracks windows glow with urgent candlelight — shadows of
officers in heated discussion. A rider urgently mounts a horse in the
courtyard. The atmosphere is tense and oppressive — anyone without
authorization risks immediate arrest. Cold blue moonlight contrasts with
warm orange torchlight. Stone walls cast long shadows. Dark fantasy
military aesthetic, dramatic lighting, cinematic tension.
```

### 3-3. 낮 / DANGER

**용도**: 계엄 상태, 클라이맥스

```
A medieval military district under full martial law. Barricades block
every entrance to the quarter. Fully armored soldiers with halberds
inspect each person passing through. A siege engine is being wheeled into
position in the main plaza. The headquarters building is fortified with
additional wooden palisades. Officers shout orders from the watchtower.
Citizens are nowhere to be seen — only military personnel occupy the
streets. The sky is dark and overcast, casting the entire district in
cold shadow. Steel grey and iron black palette. Imposing, authoritarian
atmosphere. Dark fantasy, hyper-detailed architecture, dramatic low-angle
cinematic composition.
```

---

## 4. 항만 부두 (LOC_HARBOR)

### 4-1. 낮 / SAFE

**용도**: 항만 부두 기본 배경

```
A busy medieval harbor dock stretching along the waterfront. Large
merchant galleons and smaller fishing boats are moored at weathered
wooden piers. Dockworkers haul massive cargo crates with ropes and
pulleys. Sailors tie rigging on deck. Seagulls circle overhead against
a pale sky. The salty sea breeze carries the scent of brine and tar.
Wooden warehouses with barnacle-encrusted stilts line the waterfront.
Coils of rope, barrels of fish, and stacked crates fill the foreground.
The dock has a rough, working-class energy — muscular laborers, grizzled
ship captains, and the occasional merchant inspecting goods. Muted
coastal palette — grey-blue sea, weathered brown wood, faded canvas
sails. Realistic dark fantasy, detailed painting style.
```

### 4-2. 밤 / ALERT

**용도**: 밀수 분위기, 야간 탐색

```
A medieval harbor dock shrouded in thick night fog. A lighthouse beam
sweeps across dark water at regular intervals. Small suspicious rowboats
silently approach the pier under cover of darkness. Shadowy figures
unload unmarked crates and scatter when distant patrol torches approach.
Behind a warehouse, silhouettes lean close in whispered negotiation. The
fog swallows sound — everything feels muffled and clandestine. Smuggling
operations in progress. Moonlight barely penetrates the mist. Dark teal
and charcoal palette with isolated warm light from hidden lanterns.
Atmospheric, noir-influenced dark fantasy, highly detailed digital
painting.
```

### 4-3. 밤 / DANGER

**용도**: 부두 전투, 혼란 상태

```
A medieval harbor dock engulfed in chaos at night. A ship burns at its
mooring, flames reflecting off the black water and casting hellish orange
light across the scene. Smugglers and city guards clash in sporadic
skirmishes along the pier. Crates are overturned, barrels smashed.
Screams and the clash of steel echo across the waterfront. Smoke billows
into the night sky, obscuring the stars. Half the dock is barricaded.
Armed dock thugs openly brandish weapons in the street. Fire-orange and
pitch-black palette with dramatic contrast. Dark fantasy action scene,
visceral energy, cinematic wide-angle composition.
```

---

## 5. 빈민가 (LOC_SLUMS)

### 5-1. 낮 / SAFE

**용도**: 빈민가 기본 배경

```
A cramped medieval slum district with narrow, winding alleys between
leaning, decrepit buildings. Laundry hangs on lines strung between upper
floors, fluttering in a weak breeze. Children play near the alley
entrance. Despite the poverty — cracked walls, patched roofs, puddles on
unpaved ground — there's a sense of community and daily life persisting.
A woman hangs herbs to dry on a window ledge. An old man sits on a
broken crate. Faded graffiti and faction marks on walls hint at
territorial control. Shafts of light barely reach the ground level
through the tight building gaps. Desaturated earth tones — brown, grey,
muddy green. Gritty realism, dark fantasy aesthetic, empathetic but
unflinching. Detailed digital painting.
```

### 5-2. 밤 / SAFE

**용도**: 빈민가 야간, 서정적 분위기

```
A medieval slum at night. A small campfire crackles in a clearing between
ramshackle buildings, casting warm light on gathered residents sharing
stories. Someone plays a worn violin. Children sleep in makeshift beds
nearby. Stars are visible through gaps in the crooked rooftops above.
The scene is intimate and melancholic — poverty and danger surround this
fragile moment of peace. Deep shadows fill the alleys beyond the
firelight. The mood is bittersweet — warmth within, darkness without.
Warm amber firelight against deep indigo night sky. Dark fantasy,
painterly style, emotional depth, cinematic framing.
```

### 5-3. 밤 / DANGER

**용도**: 극한 위험, 클라이맥스

```
A medieval slum consumed by violence and fear at night. A corpse lies
abandoned in a narrow alley — aftermath of a gang turf war. Armed thugs
carrying torches pound on doors, searching for someone. Smoke rises from
somewhere deeper in the district. Broken furniture and shattered glass
litter the streets — signs of looting. The only escape is deeper into
the darkness. Blood-red torchlight against absolute blackness. The
atmosphere is desperate and predatory. Crimson and black palette with
harsh dramatic lighting. Dark fantasy horror tone, visceral detail,
cinematic composition.
```

---

## 프롬프트 요약

| # | 대상 | 시간 | 안전도 | 핵심 분위기 |
|---|------|------|--------|------------|
| 1 | 그레이마르 전체 | — | — | 조감도, 도시 전경 |
| 2-1 | 시장 거리 | DAY | SAFE | 활기찬 상거래, 소문 |
| 2-2 | 시장 거리 | NIGHT | SAFE | 야시장, 은밀한 거래 |
| 2-3 | 시장 거리 | DAY | DANGER | 계엄, 텅 빈 거리 |
| 3-1 | 경비대 지구 | DAY | SAFE | 질서, 군사 위엄 |
| 3-2 | 경비대 지구 | NIGHT | ALERT | 야간 순찰, 긴장 |
| 3-3 | 경비대 지구 | DAY | DANGER | 완전 계엄, 봉쇄 |
| 4-1 | 항만 부두 | DAY | SAFE | 활기찬 항구, 노동 |
| 4-2 | 항만 부두 | NIGHT | ALERT | 밀수, 안개, 은밀함 |
| 4-3 | 항만 부두 | NIGHT | DANGER | 화재, 충돌, 혼란 |
| 5-1 | 빈민가 | DAY | SAFE | 가난하지만 생활 |
| 5-2 | 빈민가 | NIGHT | SAFE | 모닥불, 서정적 |
| 5-3 | 빈민가 | NIGHT | DANGER | 폭력, 공포, 추적 |

**총 13장** — 도시 전체 1장 + 로케이션별 3장씩

---

## 스타일 변형 팁

필요에 따라 프롬프트 끝에 아래 키워드를 추가하여 스타일 변형 가능:

| 변형 | 추가 키워드 |
|------|------------|
| 더 회화적 | `oil painting on canvas, visible brushstrokes, museum quality` |
| 더 사실적 | `photorealistic, unreal engine 5, ray tracing, 8K resolution` |
| 수채화풍 | `watercolor illustration, soft edges, muted washes, paper texture` |
| 픽셀아트 | `pixel art, 32-bit retro style, limited palette, clean pixels` |
| 애니메이션풍 | `anime style, studio ghibli inspired, cel shading, vibrant colors` |
