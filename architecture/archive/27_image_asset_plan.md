# 27 --- 이미지 에셋 추가 계획

> 게임 몰입감 강화를 위한 추가 이미지 에셋 계획.
> 우선순위별 정리 + 각 이미지의 AI 생성 프롬프트 포함.
>
> 작성: 2026-04-09

---

## 1순위: 선술집(HUB) 장소 이미지 (2장)

HUB는 가장 자주 보이는 화면인데 장소 이미지가 없음. 장소 이동 시 켄 번스 효과가 적용될 대상.

### 1-1. tavern_night_safe.png
- **용도**: HUB 복귀 시 기본 이미지 (밤, SAFE 상태)
- **크기**: 1200×800px, 16:9 비율
- **스타일**: 중세 판타지 다크톤, 따뜻한 실내 조명
- **프롬프트**:
```
Medieval fantasy tavern interior at night, warm amber candlelight, 
dark wooden beams and stone walls, a few patrons sitting at heavy oak tables, 
tankards of ale, a flickering fireplace in the background, 
the sign reads "The Locked Anchor" in wrought iron letters, 
moody atmospheric lighting with deep shadows, 
oil painting style, muted color palette with warm orange highlights,
no text overlay, game art style, 16:9 aspect ratio
```

### 1-2. tavern_night_alert.png
- **용도**: HUB ALERT 상태 (Heat 높을 때)
- **크기**: 1200×800px
- **스타일**: 같은 선술집이지만 긴장감 있는 분위기
- **프롬프트**:
```
Medieval fantasy tavern interior at night, tense atmosphere,
dark wooden beams and stone walls, fewer patrons with suspicious glances,
dim candlelight casting harsh shadows, overturned tankard on a table,
a hooded figure in the corner, the fireplace embers barely glowing,
cold blue undertones mixed with warm spots, sense of danger,
oil painting style, muted dark palette,
no text overlay, game art style, 16:9 aspect ratio
```

---

## 2순위: BACKGROUND NPC 초상화 (10장)

코드는 이미 구현됨 (enc>=1이면 초상화 표시). 이미지만 추가하면 바로 적용.
기존 CORE/SUB 초상화와 동일한 스타일 유지.

### 공통 스타일 가이드
```
Medieval fantasy portrait, bust shot, dark moody background,
oil painting style, dramatic lighting from one side,
character looking slightly to the side, detailed face,
muted color palette, game character art style,
4:5 aspect ratio (512×640px)
```

### 2-1. NPC_BG_FRUIT_VENDOR — 웃는 얼굴의 과일장수
- **파일명**: `npc-portraits/bg_fruit_vendor.png`
- **프롬프트**:
```
Medieval fantasy portrait of a cheerful middle-aged fruit vendor,
round face with laugh lines, tanned skin from working outdoors,
wearing a simple linen shirt and leather apron stained with fruit juice,
holding a ripe red apple, warm smile, bright eyes,
market stall background with colorful fruits,
oil painting style, warm lighting, 4:5 aspect ratio
```

### 2-2. NPC_BG_HERB_CRONE — 약초 파는 노파
- **파일명**: `npc-portraits/bg_herb_crone.png`
- **프롬프트**:
```
Medieval fantasy portrait of an elderly herbalist woman,
deeply wrinkled face with wise sharp eyes, white hair in a messy bun,
wearing a dark shawl with dried herbs hanging from her neck,
gnarled hands holding a bundle of dried lavender,
mysterious and slightly unsettling expression,
dim candlelit background with hanging herbs and bottles,
oil painting style, cool green tones, 4:5 aspect ratio
```

### 2-3. NPC_BG_STREET_KID — 재빠른 골목 아이
- **파일명**: `npc-portraits/bg_street_kid.png`
- **프롬프트**:
```
Medieval fantasy portrait of a scrappy street urchin, around 12 years old,
dirty face with bright cunning eyes, messy brown hair,
wearing torn oversized tunic and a too-big cap,
mischievous grin showing a missing tooth,
dark alley background with faint lantern light,
oil painting style, cool shadows with warm highlights, 4:5 aspect ratio
```

### 2-4. NPC_BG_DRUNK — 입이 가벼운 술꾼
- **파일명**: `npc-portraits/bg_drunk.png`
- **프롬프트**:
```
Medieval fantasy portrait of a talkative drunkard,
ruddy nose and flushed cheeks, bloodshot eyes with a sly look,
unkempt beard with crumbs, wearing a stained wool vest,
holding a half-empty tankard, leaning forward conspiratorially,
tavern background blurred, warm amber lighting,
oil painting style, warm reddish tones, 4:5 aspect ratio
```

### 2-5. NPC_BG_BARMAID — 경계하는 술집 여종업원
- **파일명**: `npc-portraits/bg_barmaid.png`
- **프롬프트**:
```
Medieval fantasy portrait of a cautious tavern barmaid,
young woman in her mid-20s, dark hair tied back practically,
alert watchful eyes, carrying a wooden tray,
wearing a simple dress with an apron, slightly guarded expression,
tavern interior background, warm candlelight,
oil painting style, warm tones, 4:5 aspect ratio
```

### 2-6. NPC_BG_DOCKER — 과묵한 부두 인부
- **파일명**: `npc-portraits/bg_docker.png`
- **프롬프트**:
```
Medieval fantasy portrait of a quiet dockworker,
broad-shouldered muscular man, weathered skin, short-cropped hair,
stoic expression with tired eyes, rope-calloused hands,
wearing a sleeveless work tunic, salt stains on clothing,
harbor background with ship masts, overcast lighting,
oil painting style, cool blue-gray tones, 4:5 aspect ratio
```

### 2-7. NPC_BG_BEGGAR — 겁 먹은 거지
- **파일명**: `npc-portraits/bg_beggar.png`
- **프롬프트**:
```
Medieval fantasy portrait of a fearful beggar,
gaunt face with hollow cheeks, wide nervous eyes,
tangled dirty hair, ragged cloak pulled tight around shoulders,
hunched posture, one hand extended timidly,
dark slum alley background, dim cold light,
oil painting style, desaturated dark tones, 4:5 aspect ratio
```

### 2-8. NPC_BG_CUSTOMS — 계산적인 세관원
- **파일명**: `npc-portraits/bg_customs.png`
- **프롬프트**:
```
Medieval fantasy portrait of a calculating customs officer,
thin face with sharp features, neatly groomed, cold analytical eyes,
wearing an official uniform with brass buttons and insignia,
holding a quill and ledger, lips pressed in a thin line,
office background with stacked documents, cold institutional lighting,
oil painting style, cool neutral tones, 4:5 aspect ratio
```

### 2-9. NPC_BG_FISHMONGER — 호탕한 생선장수
- **파일명**: `npc-portraits/bg_fishmonger.png`
- **프롬프트**:
```
Medieval fantasy portrait of a boisterous fishmonger,
large man with a booming presence, thick arms, ruddy complexion,
wearing a heavy leather apron with fish scales on it,
laughing with mouth open, gold tooth visible,
harbor market background with fish crates, bright morning light,
oil painting style, cool blue and warm orange contrast, 4:5 aspect ratio
```

### 2-10. NPC_BG_VAGRANT — 의심 많은 부랑자
- **파일명**: `npc-portraits/bg_vagrant.png`
- **프롬프트**:
```
Medieval fantasy portrait of a suspicious vagrant,
lean weathered man with darting eyes, patchy stubble,
wearing a patchwork cloak with a deep hood partially covering face,
arms crossed defensively, leaning against a wall,
dark back-alley background, single torch casting harsh shadows,
oil painting style, dark moody tones, 4:5 aspect ratio
```

---

## 3순위: 이벤트 씬 일러스트 (5장)

특수 이벤트 시 전체화면/반화면 일러스트. 현재 미구현이므로 이미지 준비 후 코드 연동 필요.

### 공통 스타일 가이드
```
Medieval fantasy scene illustration, cinematic wide shot,
dramatic lighting, oil painting style with painterly brushstrokes,
muted color palette with selective color highlights,
no text overlay, game illustration style, 16:9 aspect ratio (1200×675px)
```

### 3-1. event_combat_encounter.png — 전투 돌입
- **용도**: COMBAT 진입 시 전체화면 플래시
- **프롬프트**:
```
Medieval fantasy combat scene, a lone warrior facing shadowy enemies in a dark alley,
swords clashing with sparks flying, dramatic red and orange backlight,
rain falling, puddles reflecting firelight, intense close combat,
motion blur on weapons, adrenaline-filled atmosphere,
cinematic wide angle, oil painting style, 16:9 aspect ratio
```

### 3-2. event_chase_scene.png — 추격전/도주
- **용도**: FLEE 판정, 추격 이벤트
- **프롬프트**:
```
Medieval fantasy chase scene through narrow dark alleys at night,
a cloaked figure running desperately, leaping over market crates,
guards with torches pursuing in the background,
wet cobblestone reflecting moonlight, dynamic perspective,
sense of urgency and motion, cape billowing,
cinematic wide angle, oil painting style, 16:9 aspect ratio
```

### 3-3. event_secret_deal.png — 비밀 거래/뇌물
- **용도**: BRIBE/TRADE 이벤트 성공
- **프롬프트**:
```
Medieval fantasy secret deal scene in a shadowy corner,
two figures exchanging a small pouch of coins under a table,
candlelight illuminating only their hands, faces in shadow,
tension and secrecy, a wine glass on the table,
dark tavern atmosphere, smoke wisps in the air,
cinematic close-up angle, oil painting style, 16:9 aspect ratio
```

### 3-4. event_stealth_infiltration.png — 잠입
- **용도**: SNEAK 판정 이벤트
- **프롬프트**:
```
Medieval fantasy stealth scene, a figure pressed against a stone wall,
peeking around a corner at patrolling guards in the distance,
moonlight casting long shadows, the figure blending into darkness,
a guard post with a single torch ahead, breath visible in cold air,
quiet tension, cinematic wide angle, oil painting style, 16:9 aspect ratio
```

### 3-5. event_discovery.png — 핵심 단서 발견
- **용도**: 퀘스트 FACT 발견 이벤트
- **프롬프트**:
```
Medieval fantasy discovery scene, a hand holding an old torn document,
candlelight revealing hidden text and a wax seal on parchment,
dusty desk with scattered papers and an inkwell,
dramatic spotlight on the document, everything else in shadow,
sense of revelation and importance, dust particles in light beam,
cinematic close-up, oil painting style, 16:9 aspect ratio
```

---

## 코드 연동 참고

### 2순위 (NPC 초상화) — 즉시 적용 가능
`server/src/db/types/npc-portraits.ts`에 추가:
```typescript
NPC_BG_FRUIT_VENDOR: '/npc-portraits/bg_fruit_vendor.png',
NPC_BG_HERB_CRONE: '/npc-portraits/bg_herb_crone.png',
// ...
```
이미지를 `client/public/npc-portraits/`에 배치하면 말풍선 초상화 자동 적용.

### 1순위 (선술집) — location-images.ts 수정 필요
`client/src/data/location-images.ts`에 LOC_TAVERN 매핑 추가.

### 3순위 (이벤트 씬) — 별도 코드 구현 필요
이벤트 ID별 일러스트 매핑 + 전체화면 오버레이 컴포넌트 신규 개발.
