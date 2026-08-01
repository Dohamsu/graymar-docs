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
