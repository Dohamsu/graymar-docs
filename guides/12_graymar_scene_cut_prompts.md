# 그레이마르 장면 컷 이미지 프롬프트 (arch/96 · guides/11 규약)

> 테스트런 실측 기반 제작 목록 — **위에서부터 차례대로 만들면 노출 효율 순**이다.
> 근거 데이터: 최근 30일 1,363턴 서술 코퍼스 (graymar_v1 중심).
>
> - 행동 분포: TALK 312 · PERSUADE 178 · INVESTIGATE 175 · OBSERVE 70 · TRADE 27 · THREATEN 16 · FIGHT/STEAL/SNEAK 29
> - 장소 체류: 시장 445 ≫ 경비대 134 > 항만 84 > 선술집 39 > 빈민가 12 / 시간대: 낮 85%·밤 15%
> - 고빈도 소재: 서류 319 · 새벽 218 · 골목 165 · 경비 161 · 생선 134 · 장부 124 · 잉크 77 · 등불 57 · 좌판 51 · 에일 50 · 약초 47 · 향신료 44 · 안개 35
> - 감정 신호: 한숨 64 · 움찔 43 · 속삭임 39 · 찌푸린 미간 34
> - NPC 등장(반응 계측): 에드릭 303 ≫ 마이렐 52 ≈ 로넨 50 > 라이라 25 > 브렌 14 ≈ 하를런 14 > 펠릭스·미렐라 13 > 쥐왕 9

## 0. 제작 체크리스트 (진행 관리 — 완성 시 ☑)

| # | ☐ | 파일명 (= 태그) | 유형 | 실측 근거 |
|---|---|----------------|------|----------|
| 1 | ☑ | `장부_서류_잉크_촛불.webp` | 상황·조사 | 서류 319+장부 124+잉크 77, INVESTIGATE 175턴 |
| 2 | ☑ | `에드릭_미간_신경질_계산.webp` | 인물·감정 | 에드릭 등장 1위 303, 미간 34 |
| 3 | ☑ | `시장_좌판_향신료_인파_day.webp` | 장소·시장 | 시장 체류 1위 445, 좌판 51+향신료 44 |
| 4 | ☑ | `새벽_안개_항만_돛대.webp` | 정경 | 새벽 218+안개 35+항만 179 |
| 5 | ☑ | `로넨_불안_초조_움찔.webp` | 인물·감정 | 로넨 50, 움찔 43, DISMISS 반응 실측 |
| 6 | ☑ | `골목_밀담_속삭임_두건_night.webp` | 상황·밀담 | 골목 165+속삭임 39, 음모 서사 축 |
| 7 | ☑ | `경비_제복_순찰_창.webp` | 장소·경비대 | 경비 161+제복 25+순찰 18, 체류 2위 |
| 8 | ☑ | `흥정_금화_주머니_손.webp` | 상황·거래 | TRADE 27+BRIBE 12, 주머니 28, 경제 루프 |
| 9 | ☑ | `에드릭_한숨_피로_지친.webp` | 인물·감정 | 한숨 64, 도박 빚 서사 |
| 10 | ☑ | `마이렐_단호_명령_야간_night.webp` | 인물·감정 | 마이렐 52, 야간 책임자 |
| 11 | ☑ | `부두_생선_그물_상자_day.webp` | 장소·항만 | 생선 134+창고 48, 체류 3위 |
| 12 | ☑ | `선술집_에일_술잔_난로.webp` | 장소·선술집 | 에일 50, 사랑방 개방 무대 |
| 13 | ☑ | `로넨_안도_감사_미소.webp` | 인물·감정 | WELCOME 5, 의뢰 보고 동선(arch/89 정산 대면) |
| 14 | ☑ | `난투_주먹다짐_몸싸움_소란.webp` | 상황·소동 | FIGHT 10+brawler 검증 축, 시드 컷 교체분 |
| 15 | ☑ | `창고_어둠_등불_궤짝_night.webp` | 상황·잠입 | 창고 48+등불 57, SNEAK/STEAL 19 |
| 16 | ☑ | `에드릭_경계_곁눈질_은밀.webp` | 인물·감정 | DISMISS 12+PROBE 50 — 회피·경계 반응 |
| 17 | ☑ | `마이렐_피로_보고서_집무.webp` | 인물·감정 | PROBE 15, 부하 복지 집착 서사 |
| 18 | ☑ | `라이라_긴장_문서_비밀.webp` | 인물·감정 | 라이라(문서실) 25, PROBE 우세 17 |
| 19 | ☑ | `브렌_갈등_침통_압박.webp` | 인물·감정 | 브렌 14, 병원비 압박 서사 |
| 20 | ☑ | `약초_붕대_치료_노점.webp` | 상황·치료 | 약초 47, 미렐라 노점·회복 장면 |
| 21 | ☑ | `추격_도주_골목_돌바닥_night.webp` | 상황·긴박 | 돌바닥 65, FLEE·agitation 행동화(arch/76) |
| 22 | ☑ | `쥐왕_지하_촛불_거만.webp` | 인물·감정 | 쥐왕 9, 빈민가 정보 독점 |
| 23 | ☑ | `펠릭스_당황_풋내기_경례.webp` | 인물·감정 | 펠릭스 13, 이상주의 신참 서사 |
| 24 | ☑ | `하를런_팔짱_중재_거친.webp` | 인물·감정 | 하를런 14, 은퇴 복서·중재자 |
| 25 | ☑ | `빈민가_판자_그림자_웅크림.webp` | 장소·빈민가 | 체류 12 (낮지만 쥐왕 동선 필수 무대) |
| 26 | ☑ | `비명_고함_창문_소동_night.webp` | 상황·사건 | Incident·호외 연출 보조 |

> ✅ 2026-08-01 전량(26/26) 제작·투입 완료 — 시드 컷 3장은 일괄 교체됨. 실런 검증: SCN_15(시장 좌판) 매칭 발화·렌더 확인.

## 1. 공통 스타일 프리픽스 (모든 프롬프트 앞에 붙임)

```
Dark fantasy medieval harbor city illustration, painterly digital art,
muted earthy palette with cold sea-gray undertones, dramatic chiaroscuro
lighting, gritty noir realism, political intrigue mood, no text, no
watermark, cinematic composition, 16:9
```

인물 감정 컷 추가 규칙:
- **기존 배정 초상화를 참조 이미지로 사용해 같은 얼굴을 유지**할 것 (얼굴이 바뀌면 오귀속 위화감).
- 상반신~바스트샷, 배경은 그 인물의 활동 장소를 흐리게.
- 태그의 실명은 소개(introduced) 후 서술에만 등장하므로 미소개 노출 걱정 없음 — 시스템이 자동 차단.

## 2. 상황씬 프롬프트 (조사·거래·잠입·소동)

**#1 장부_서류_잉크_촛불** — INVESTIGATE 턴의 대표 컷
```
close-up of weathered accounting ledgers and scattered documents on a
dark wooden desk, ink pot and quill, single candle flame, magnified
scrutiny mood, shadows of columns of figures
```

**#6 골목_밀담_속삭임_두건_night**
```
two hooded figures whispering in a narrow rain-slick back alley at night,
single hanging lantern, long shadows on wet cobblestone, conspiratorial
tension, breath visible in cold air
```

**#8 흥정_금화_주머니_손**
```
close-up of two hands exchanging a small coin pouch over a market counter,
gold coins spilling slightly, one hand hesitant, tense negotiation mood
```

**#14 난투_주먹다짐_몸싸움_소란**
```
sudden tavern-street brawl, two rough men grappling mid-punch, crowd
recoiling in a circle, overturned crates, dust and motion blur
```

**#15 창고_어둠_등불_궤짝_night**
```
dim warehouse interior at night, stacked wooden crates and barrels, a
single shuttered lantern casting narrow light beam, rope coils, someone's
silhouette slipping between shelves
```

**#20 약초_붕대_치료_노점**
```
herbalist's market stall close-up, dried herb bundles hanging, mortar and
pestle, linen bandages being wrapped around a forearm, warm daylight
```

**#21 추격_도주_골목_돌바닥_night**
```
figure sprinting through a twisting night alley, cloak flying, wet
cobblestones reflecting torchlight behind, pursuers' shadows on the wall,
urgent motion
```

**#26 비명_고함_창문_소동_night**
```
night street scene, windows lighting up one by one, residents leaning out,
people rushing toward a commotion off-frame, lantern smoke, alarm mood
```

## 3. 장소 분위기씬 프롬프트

**#3 시장_좌판_향신료_인파_day** — 최다 체류 무대의 낮 활기
```
bustling medieval market street at midday, canvas awnings over stalls,
spice sacks and hanging fish, dense crowd haggling, warm dusty sunlight
shafts
```

**#4 새벽_안개_항만_돛대** — '새벽 218회'의 정경 컷 (시간대 무표기 = 전 시간대)
```
harbor at first light, thick sea fog around tall ship masts, pale blue-gray
dawn, mooring ropes and silent gulls, lone figure on the quay
```

**#7 경비_제복_순찰_창**
```
city guard post exterior, two guards in worn uniforms with spears standing
watch, iron brazier, stone wall with wanted notices, disciplined cold mood
```

**#11 부두_생선_그물_상자_day**
```
working dock at day, fishermen hauling nets, fish crates and salt barrels,
gulls circling, laborers carrying sacks up a gangplank
```

**#12 선술집_에일_술잔_난로**
```
cozy dim tavern interior, foaming ale mugs on scarred oak tables, hearth
fire glow, patrons mid-conversation in booths, low wooden beams
```

**#25 빈민가_판자_그림자_웅크림**
```
slum quarter of leaning plank shacks, narrow muddy lane, figures huddled
around a small fire, ragged laundry lines overhead, oppressive shadows
```

## 4. 인물 감정 컷 프롬프트 (등장·반응 실측순)

> 규약: 파일명 첫 토큰 = **실명** (매칭 키). 기존 초상 참조로 동일 얼굴 유지.

**#2 에드릭_미간_신경질_계산** — 등장 1위(303턴), 찌푸린 미간 34회
```
[에드릭 초상 참조] middle-aged nervous accountant, brow furrowed deep,
pinching bridge of nose over a ledger, ink-stained fingers, twitchy
irritation, counting-house background blurred
```

**#5 로넨_불안_초조_움찔**
```
[로넨 초상 참조] thin young guild clerk glancing over his shoulder,
startled flinch, clutching documents to chest, sweat on brow, harbor
office background blurred
```

**#9 에드릭_한숨_피로_지친** — 한숨 64회·도박 빚 서사
```
[에드릭 초상 참조] the accountant slumped back exhaling a long sigh, dark
circles under eyes, loosened collar, scattered gambling chits beside the
ledger, guttering candle
```

**#10 마이렐_단호_명령_야간_night**
```
[마이렐 초상 참조] stern female night-watch commander giving a curt order,
jaw set, hand resting on sword pommel, torchlit barracks yard behind,
veteran authority
```

**#13 로넨_안도_감사_미소** — 의뢰 보고·정산 대면 컷
```
[로넨 초상 참조] the clerk's shoulders dropping in relief, tentative
grateful smile, offering a small reward pouch with both hands, warm
lamplight
```

**#16 에드릭_경계_곁눈질_은밀** — DISMISS·PROBE 반응
```
[에드릭 초상 참조] the accountant giving a wary sidelong glance, half
turning away, hand covering a page of the ledger, guarded suspicion
```

**#17 마이렐_피로_보고서_집무**
```
[마이렐 초상 참조] the commander rubbing her eyes over piled night-duty
reports, single lamp, armor half unbuckled, weight of responsibility
```

**#18 라이라_긴장_문서_비밀**
```
[라이라 초상 참조] quiet young archivist frozen mid-page, eyes wide at a
coded memo, finger pressed to lips, candlelit document room, a cat on the
shelf behind
```

**#19 브렌_갈등_침통_압박**
```
[브렌 초상 참조] upright officer staring down at an unopened letter, fists
clenched on desk, torn between duty and family, gray morning light
```

**#22 쥐왕_지하_촛불_거만**
```
[쥐왕 초상 참조] slum underboss lounging on a salvaged merchant's chair,
smug half-smile, candle-lit cellar court, ragged retainers in shadow
```

**#23 펠릭스_당황_풋내기_경례**
```
[펠릭스 초상 참조] young idealistic guard caught off-balance mid-salute,
flustered wide eyes, slightly oversized helmet, earnest country-boy energy
```

**#24 하를런_팔짱_중재_거친**
```
[하를런 초상 참조] retired boxer with crossed thick arms stepping between
two quarrelers, broken-nosed calm authority, dockside crowd behind
```

## 5. 타 팩 우선 1건 (참고)

star_sand_v1은 이렌 54턴·여관 91턴이 최상위 — 착수 시 `이렌_*` 감정 컷 1~2장 +
`여관_난로_*` 장소 컷 1장부터 (동일 규약, `content/star_sand_v1/assets/scenes/`).

## 6. 투입 절차 (리마인드)

```
1) 생성 → webp 변환 → 체크리스트의 파일명 그대로 저장
2) content/graymar_v1/assets/scenes/ 에 넣기 (몇 장씩 나눠 넣어도 됨)
3) python3 scripts/sync_pack_assets.py graymar_v1
4) 서버 재시작 + client push (public/pack-assets 포함)
5) 체크리스트 ☑ + 시드 컷 3장은 #3·#14 완성 시점에 일괄 교체
```


---

# 2차 배치 (#27~44) — 커버리지 확장 (2026-08-01 실측 재분석)

> 1차 26종 투입 후 공백 분석: graymar 잔여 고빈도 소재(종소리 114 · 스튜 37 · 미렐라 40 ·
> 쪽지 33+인장 22 · 황혼 24 · 무기 21 · 오웬 19)와 **star_sand_v1 최초 세트**
> (여관 104 · 부두 61 · 얼음 54 · 별빛 50 · 외투 48 · 이렌 54턴).
>
> ⚠️ **태그 함정 실측**: '잠긴'은 124회로 최상위지만 대부분 선술집 이름("잠긴 닻")의
> 일부다 — 태그로 쓰면 선술집 서술마다 오매칭 후보가 된다. 이런 **고유명사 파편 토큰은
> 태그 금지** (guides/11 §2 원칙 추가 사례).

## 5. 2차 체크리스트

| # | ☐ | 파일명 (= 태그) | 팩 | 유형 | 실측 근거 |
|---|---|----------------|----|------|----------|
| 27 | ☑ | `종소리_종탑_항만_황혼.webp` | graymar | 정경 | 종소리 114(항만 종 상용구)+황혼 24 |
| 28 | ☑ | `쪽지_인장_밀랍_봉인.webp` | graymar | 상황·단서 | 쪽지 33+인장 22 — questReveal 턴 대표 컷 |
| 29 | ☑ | `미렐라_인자_주름_노련.webp` | graymar | 인물·감정 | 미렐라 40회 — 40년 터줏대감 약초상 |
| 30 | ☑ | `스튜_김_나무그릇_식사.webp` | graymar | 상황·식사 | 스튜 37 — 선술집·여관 식사 장면 |
| 31 | ☑ | `오웬_너털웃음_술통_뱃사람.webp` | graymar | 인물·감정 | 오웬 19 — 전직 항해사 선술집 주인 |
| 32 | ☑ | `무기_단검_뽑아든_위협_night.webp` | graymar | 상황·전투 | 무기 21+THREATEN 16 — 전투·위협 진입 |
| 33 | ☑ | `항만_밀수_창고_어선_night.webp` | graymar | 상황·밀수 | 밀수 서사 축 (1차 교체로 빠진 밤 부두 복원) |
| 34 | ☑ | `시장_파장_등불_어스름_night.webp` | graymar | 장소·시장 밤 | 시장 체류 1위인데 밤 컷 부재 (밤 15%) |
| 35 | ☑ | `비_빗줄기_처마_웅덩이.webp` | graymar | 정경·날씨 | 비 17 — 날씨 전환 턴 |
| 36 | ☑ | `레닉_능글_귓속말_술잔.webp` | graymar | 인물·감정 | 레닉 10 — 뒷골목의 귀, 소문 거래 |
| 37 | ☑ | `여관_난로_아늑_목조.webp` | star_sand | 장소·여관 | 여관 104 — 팩 체류 1위(꿈잠 여관) |
| 38 | ☑ | `이렌_근심_걱정_여관주인.webp` | star_sand | 인물·감정 | 이렌 54턴 — 의뢰인·OPEN_UP 42 |
| 39 | ☑ | `별빛_모래_해변_밤하늘_night.webp` | star_sand | 정경 | 별빛 50 — 팩 정체성 컷 |
| 40 | ☑ | `고래_갈비뼈_뼈대_거대.webp` | star_sand | 장소·무덤 | 갈비뼈 14+심장 23 — 별고래의 무덤 |
| 41 | ☑ | `얼음_부두_어선_그물_day.webp` | star_sand | 장소·부두 | 얼음 54+부두 61 — 흰숨 부두 |
| 42 | ☑ | `루오르_차분_기록_촛불.webp` | star_sand | 인물·감정 | 루오르 22 — 꿈기록 수녀 |
| 43 | ☑ | `외투_눈보라_추위_웅크림.webp` | star_sand | 정경·날씨 | 외투 48 — 극지 한기 상용구 |
| 44 | ☑ | `수녀원_회랑_등불_기도_night.webp` | star_sand | 장소·수녀원 | 등불 39+수녀 11 — 등불수녀원 |

> ✅ 2026-08-02 2차 전량(18/18) 제작·투입 완료.
> star_sand 투입 경로: `content/star_sand_v1/assets/scenes/` + `sync_pack_assets.py star_sand_v1`.
> karnholt_v1은 체류 데이터가 아직 적어(용광로 23턴) 다음 배치에서 — 착수 시 `대장간_모루_불꽃` 계열부터.
>
> **3차 배치(#45~59, star_sand 전용 15종)는 [[13_star_sand_scene_cut_prompts|guides/13]]** —
> star_sand 311턴 실측 재분석 기반 (2026-08-02).

## 6. 2차 프롬프트 — graymar (기존 공통 프리픽스 사용)

**#27 종소리_종탑_항만_황혼**
```
harbor bell tower silhouetted against amber dusk sky, great bronze bell
mid-swing, gulls scattering, rooftops and masts below in fading light
```

**#28 쪽지_인장_밀랍_봉인**
```
close-up of a folded secret note with a cracked red wax seal bearing a
noble crest, held in gloved fingers by candlelight, ominous discovery mood
```

**#29 미렐라_인자_주름_노련** — 인물 규약(기존 초상 참조·동일 얼굴)
```
[미렐라 초상 참조] elderly herbalist woman with kind deep wrinkles and
knowing eyes, faint warm smile, sorting dried herbs at her stall, decades
of market wisdom in her bearing
```

**#30 스튜_김_나무그릇_식사**
```
steaming wooden bowl of thick stew on a rough tavern table, torn bread
beside, spoon resting, hearth glow, humble hearty meal
```

**#31 오웬_너털웃음_술통_뱃사람**
```
[오웬 초상 참조] burly tavern keeper laughing heartily while tapping an ale
barrel, old sailor's tattoos on forearms, bottles and rope decor behind the
bar
```

**#32 무기_단검_뽑아든_위협_night**
```
close low-angle of a hand drawing a dagger from a belt sheath in a dim
alley, blade catching lantern light, confrontation about to break
```

**#33 항만_밀수_창고_어선_night**
```
night harbor backwater, small boat unloading unmarked crates into a
warehouse side door, hooded figures, single shuttered lantern, smuggling
tension
```

**#34 시장_파장_등불_어스름_night**
```
market street at closing time after dusk, merchants packing stalls under
hanging lanterns, long shadows, scattered crates, quiet end-of-day mood
```

**#35 비_빗줄기_처마_웅덩이**
```
rain falling on a medieval street, water streaming off tiled eaves,
puddles rippling on cobblestone, a figure sheltering under an awning
```

**#36 레닉_능글_귓속말_술잔**
```
[레닉 초상 참조] sly former actor leaning close to whisper over a wine cup,
theatrical smirk, one eyebrow raised, shadowy tavern corner booth
```

## 7. 2차 프롬프트 — star_sand (프리픽스 변형)

star_sand 공통 프리픽스 (극야 해안 톤 — graymar 프리픽스 대신 사용):
```
Dark fantasy polar-night coastal illustration, painterly digital art, cold
indigo and bone-white palette with faint starlight glimmer, long polar
twilight, quiet melancholic wonder, no text, no watermark, cinematic
composition, 16:9
```

**#37 여관_난로_아늑_목조**
```
cozy timber inn common room in polar night, large stone hearth blazing,
fur throws on benches, frost-edged windows glowing warm against the dark
```

**#38 이렌_근심_걱정_여관주인**
```
[이렌 초상 참조] middle-aged innkeeper woman pausing mid-work, worried
distant gaze, wiping hands on apron, firelit common room behind, carrying
an unspoken burden
```

**#39 별빛_모래_해변_밤하늘_night**
```
vast dark beach of glimmering star-sand under an immense aurora-lit night
sky, tiny lone figure walking the shoreline, sand sparkling like fallen
constellations
```

**#40 고래_갈비뼈_뼈대_거대**
```
colossal whale ribcage arching over a snowy shore like a cathedral,
travelers dwarfed beneath the bleached bones, faint blue glow within
```

**#41 얼음_부두_어선_그물_day**
```
ice-crusted fishing dock in pale polar daylight, boats locked in frost,
frozen nets and ropes, fishermen in heavy furs breaking ice off moorings
```

**#42 루오르_차분_기록_촛불**
```
[루오르 초상 참조] serene young nun in gray habit writing in a dream-ledger
by candlelight, calm attentive expression, ink-stained fingertips, stone
cell with hanging lanterns
```

**#43 외투_눈보라_추위_웅크림**
```
figure hunched in a thick fur coat pushing through a snow squall, scarf
pulled over face, breath crystallizing, lantern glow barely visible ahead
```

**#44 수녀원_회랑_등불_기도_night**
```
lantern-lined convent cloister at polar night, row of hanging oil lamps
receding into darkness, a nun kneeling in silent prayer, snow drifting in
```

---

# 3차 배치 (#92~109) — 그레이마르 커버리지 확장 (2026-08-02)

> #45~91은 star_sand 3~5차([[13_star_sand_scene_cut_prompts|guides/13]]) — 번호는 전 팩 통합 연번.
> 근거: graymar_v1 최신 45일 991턴 코퍼스 재실측 + 콘텐츠 주입 어휘(퀘스트 fact·
> Incident — star_sand 5차와 같은 원리: fact description은 questReveal로, Incident
> 제목·서술은 발동 시 서술에 확정 등장).
>
> - 미커버 실측 상위: 수레 114 · 조작 87 · 필체 63 · 광장 63 · 지붕 58 · 갈매기 55 ·
>   깃발 50 · 활기 39 · 땀 37 · 지도 36 · 도박 34 · 자루 73 · 짐꾼 21 · 증거 15
> - NPC 최신 언급: 로넨 357(1위) · 에드릭 298 · 미렐라 42 · 하를런 39 — **미커버**:
>   밴스 경(CORE 유일 미커버·아크 배후) · 쉐도우(FACT_SHADOW_INTEL 직결) ·
>   이졸데(귀족 음모 무대) · 토브렌(동부 부두 fact 무대) — 전원 기존 초상화 보유.
>
> ⚠️ **태그 함정 추가 실측**: '서리'(99)는 모서리, '다리'(40)는 기다리-, '독'(39)은
> 유독/지독, '럼'(182)은 그럼 파편 — 태그 금지. '바람'(374)·'발걸음'(203)·'소음'(89)·
> '고요'(94)는 범용어라 프리스크린 과통과 — 단독 태그 금지.

## 8. 3차 체크리스트

| # | ☐ | 파일명 (= 태그) | 유형 | 근거 |
|---|---|----------------|------|------|
| 92 | ☑ | `짐꾼_수레_자루_하역_day.webp` | 상황·항만 노동 | 수레 114·자루 73·짐꾼 21·하역 17 — 미커버 1위 소재군 |
| 93 | ☑ | `필체_조작_장부_흔적.webp` | 상황·단서 | 조작 87·필체 63 + FACT_TAMPERED_LOGS("다른 필체, 잉크 차이") 시각화 |
| 94 | ☑ | `로넨_고백_결심_장부.webp` | 인물·감정 | 로넨 357(언급 1위)인데 2컷뿐 — 내부 사정 고백 순간 (기존 불안·안도 대비) |
| 95 | ☑ | `광장_인파_활기_day.webp` | 장소·광장 | 광장 63·활기 39 — 시장 좌판 컷과 별개의 광각 구도 |
| 96 | ☑ | `지붕_도주_그림자_night.webp` | 상황·긴박 | 지붕 58 — 골목 추격 컷(#21)의 지붕 위 변주 |
| 97 | ☑ | `갈매기_항구_하늘_day.webp` | 정경 | 갈매기 55 — 낮 항만 휴지 턴 |
| 98 | ☑ | `도박_주사위_탁자_night.webp` | 상황·도박 | 도박 34 — 에드릭 도박 빚 서사의 무대 (뒷방 도박판) |
| 99 | ☑ | `지도_표식_골목_조사.webp` | 상황·조사 | 지도 36 — 도주 경로·밀수로 추적 턴 |
| 100 | ☑ | `증거_문서_사본_제시.webp` | 상황·담판 | 증거 15·사본 6 — S4~S5 증거 대질·아크 커밋 턴 |
| 101 | ☑ | `밀회_목격_선술집_night.webp` | 사건·목격 | FACT_MAIREL_GUILD_EVIDENCE("선술집에서 목격") — fact 주입 어휘 선행 |
| 102 | ☑ | `깃발_함성_부두_파업.webp` | 사건·파업 | Incident SOCIAL '항만 노동자 파업' + 깃발 50 |
| 103 | ☑ | `역병_기침_격리_빈민가.webp` | 사건·역병 | Incident SOCIAL '빈민가 역병' — 발동 시 확정 어휘 |
| 104 | ☑ | `진압_봉기_빈민가_night.webp` | 사건·진압 | Incident MILITARY '빈민가 강제 진압'·'빈민가 봉기' 겸용 |
| 105 | ☑ | `암살_음모_단도_night.webp` | 사건·음모 | Incident POLITICAL '암살 음모' — 무기 컷(#32)과 별개의 잠입 구도 |
| 106 | ☑ | `쉐도우_브로커_두건_거래.webp` | 인물·감정 | FACT_SHADOW_INTEL 직결 — 실행범·도주 경로 정보의 출처 |
| 107 | ☑ | `밴스_의원_온화_집무.webp` | 인물·감정 | CORE 유일 미커버 — 온건한 중재자 가면의 배후 |
| 108 | ☑ | `이졸데_사교_부채_연회.webp` | 인물·감정 | 귀족 음모·사교계 무대 (Incident POLITICAL 연계) |
| 109 | ☑ | `토브렌_창고_관리자_난처.webp` | 인물·감정 | FACT_ROUTE_TO_EAST_DOCK("동부 부두 3번 창고") 무대의 열쇠 인물 |

> #101~105는 star_sand 5차와 같은 선행 대비 — 해당 fact 공개·Incident 발동 턴에만
> 뜬다. 잔여 미커버 SUB: 벨론·세라·로자 (저노출 — 체류 데이터 축적 후 다음 배치).
> 이 배치로 팩 총량 54장 — 쿨다운 3턴·런 내 1회 제한으로 노출 총량 불변.

## 9. 3차 프롬프트 — 상황·정경 (§1 공통 프리픽스 사용)

**#92 짐꾼_수레_자루_하역_day**
```
dock laborers heaving grain sacks from a laden handcart onto a gangplank,
sweat and strain, rope-bound crates queued behind, overseer counting loads,
gritty working-harbor morning
```

**#93 필체_조작_장부_흔적**
```
extreme close-up of a ledger page under a magnifying lens, two subtly
different handwritings meeting mid-column, fresher ink glinting over faded
entries, fingertip pinning the seam of the forgery
```

**#95 광장_인파_활기_day**
```
wide view of the market square from a colonnade, dense crowd currents
between fountain and stalls, banners strung between buildings, carts
threading through, city alive under dusty midday light
```

**#96 지붕_도주_그림자_night**
```
cloaked figure leaping a gap between tiled rooftops at night, chimney smoke
streaking, pursuers' lanterns bobbing in the alley far below, moonlit
silhouette mid-stride
```

**#97 갈매기_항구_하늘_day**
```
gulls wheeling in a bright cold harbor sky above anchored masts, one
perched on a mooring post in sharp focus, glittering water and distant
cargo cranes, breathing-room calm
```

**#98 도박_주사위_탁자_night**
```
smoky backroom gambling table, dice mid-tumble in lantern light, piled
coins and torn IOU chits, tense ringed fingers gripping the table edge,
watchers in shadow
```

**#99 지도_표식_골목_조사**
```
city map of harbor district spread on a barrel head, charcoal circles
marking three alley routes, a knife pinning one corner, gloved hand
tracing a smuggler's path, lantern glow
```

**#100 증거_문서_사본_제시**
```
document folder slapped open on a polished desk, copied ledger pages and
sealed testimonies fanned out toward an unseen opponent, accusing hand flat
beside them, high-stakes confrontation stillness
```

## 10. 3차 프롬프트 — 사건 컷 (fact·Incident 주입 어휘)

**#101 밀회_목격_선술집_night**
```
view between shelf bottles into a tavern's darkest booth, an armored figure
and a guild merchant leaning close over a slid envelope, the watcher's
blurred shoulder in frame's edge, caught-secret tension
```

**#102 깃발_함성_부두_파업**
```
dock workers massed behind a hoisted patchwork banner, fists and tools
raised mid-chant, halted cranes and idle ships behind, foremen facing them
down, powder-keg morning
```

**#103 역병_기침_격리_빈민가**
```
slum lane strung with warning cloths across doorways, hunched figure
coughing into a rag, neighbors keeping wide wary distance, smoke of
cleansing fires drifting, dread quiet
```

**#104 진압_봉기_빈민가_night**
```
line of guards with shields and torches pressing into a slum street,
thrown debris mid-air, residents scattering between shacks, harsh torchlit
chaos of a night crackdown
```

**#105 암살_음모_단도_night**
```
moonlit study window easing open from outside, gloved hand and bared
dagger entering first, sleeping household unaware beyond the curtain,
coiled lethal patience
```

## 11. 3차 프롬프트 — 인물 감정 컷 (기존 초상 참조 — 동일 얼굴)

**#94 로넨_고백_결심_장부** — 언급 1위의 3컷째: 겁먹은 서기의 용기
```
[로넨 초상 참조] the thin clerk placing both palms flat on a closed ledger,
jaw set through visible fear, eyes lifted in reluctant resolve to finally
tell what he knows, harbor office lamplight
```

**#106 쉐도우_브로커_두건_거래**
```
[쉐도우 초상 참조] hooded information broker half-lit in an alley doorway,
gloved hand extending a folded slip, face mostly shadow except a knowing
mouth, price-of-secrets poise
```

**#107 밴스_의원_온화_집무**
```
[밴스 초상 참조] silver-haired councilman smiling warmly across his study
desk, fingers steepled over an unsigned decree, eyes a degree colder than
the smile, velvet menace of a patient schemer
```

**#108 이졸데_사교_부채_연회**
```
[이졸데 초상 참조] society matriarch behind a half-raised lace fan at a
candlelit salon, appraising amused gaze over the rim, jewels and murmuring
nobles blurred behind, secrets traded in glances
```

**#109 토브렌_창고_관리자_난처**
```
[토브렌 초상 참조] weary warehouse manager caught between manifest and
questioner, rubbing his neck with forced casualness, eyes flicking toward
warehouse three's sealed door, a family man in too deep
```
