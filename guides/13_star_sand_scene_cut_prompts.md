# 별빛모래 장면 컷 이미지 프롬프트 — 3차 배치 (arch/96 · guides/11 규약)

> guides/12 의 2차 배치(#37~44, star_sand 최초 8종)를 잇는 **star_sand_v1 전용 확장 15종**.
> 번호는 전 팩 통합 진행 관리를 위해 #45부터 이어간다.
>
> 근거 데이터: star_sand_v1 실런 서술 코퍼스 **311턴** (2026-07-14 ~ 07-26, DB 실측).
>
> - 행동 분포: INVESTIGATE 57 · TALK 51 · PERSUADE 30 · OBSERVE 27 · STEAL 7 · THREATEN 5
> - 장소 체류: 꿈잠 여관(LOC_SS_INN) 214 ≫ 수녀원 36 > 갈비평원 33 > 흰숨 부두 23 > 관측탑 5 (시장·심장 웅덩이·무음 해변 세션 0 — 단 대화 언급은 다수)
> - 고빈도 소재: 고래기름 177 · 등불 162 · 바람 114 · 그림자 92 · 주머니 78 · 침묵 63 · 파도 58 · 외투 58 · 웅덩이 57 · 성에 56 · 흔적 54 · 금속 53 · 좌판 48 · 램프 40 · 절벽 39 · 지도 37 · 호기심 37 · 심장 32 · 심지 30 · 검은얼음 29 · 대가 29
> - 감정 신호: 시선 175 · 고개 145 · 손끝 102 · 미소 48 · 경계 41 · 창백 31 · 떨리- 24
> - NPC 등장: 이렌 311(사실상 전 턴) ≫ 유르마 44 ≈ 루오르 43 > 아바스 30 > 순례자 23 > 세피 14 > 카일룬·토바 9
>
> ⚠️ **태그 함정 실측 (이 팩 고유)**: '검'(105)·'창'(112)·'금'(268)·'국'(90)은 대부분
> '검은얼음'·'창문/창백'·'지금/조금'·'국물' 등의 파편 — 1~2글자 일반어 태그 금지.
> '꿈'은 138회 최상위지만 **1글자 토큰이라 sync가 무시**한다 — 꿈 서사 컷은
> 잠꼬대·뒤척·침상 등 주변 어휘로 태깅할 것.

## 0. 제작 체크리스트 (위에서부터 노출 효율순 — 완성 시 ☑)

| # | ☐ | 파일명 (= 태그) | 유형 | 실측 근거 |
|---|---|----------------|------|----------|
| 45 | ☑ | `이렌_미소_안도_감사.webp` | 인물·감정 | 이렌 311 전 턴 최다·미소 48 — 의뢰 보고·정산 대면(arch/89), 기존 근심 컷의 감정 대비 |
| 46 | ☑ | `지도_흔적_수색_등불.webp` | 상황·조사 | INVESTIGATE 57 최다 행동 + 지도 37·흔적 54·수색 16 — 팩에 조사 컷 부재 |
| 47 | ☑ | `잠꼬대_뒤척_침상_night.webp` | 상황·공통몽 | 꿈 138(태그 불가→주변어) + 잠꼬대 9·뒤척- 12 — 팩 핵심 서사(공통몽) 컷 |
| 48 | ☑ | `램프_심지_고래기름_불빛.webp` | 상황·램프 | 고래기름 177·램프 40·심지 30 — 팩 최다 소재 상용구 |
| 49 | ☑ | `유르마_순례자_무장_수색.webp` | 인물·감정 | 유르마 44(NPC 2위)·순례자 23 — 동생 수색 동행 서사 |
| 50 | ☑ | `이렌_창백_충격_떨림.webp` | 인물·감정 | 창백 31·떨리- 24 — 꿈 목격담·예언 문장 흘리는 순간 |
| 51 | ☑ | `아바스_장인_램프_유리.webp` | 인물·감정 | 아바스 30 — 램프 불빛이 미래를 비춘다고 믿는 장인 |
| 52 | ☑ | `절벽_파도_바람_극야.webp` | 정경 | 바람 114·파도 58·절벽 39 — 수녀원 절벽·해안 전환 턴 |
| 53 | ☑ | `루오르_경계_침묵_환자.webp` | 인물·감정 | 루오르 43·경계 41·환자 25 — 기록 은폐 서사 (기존 차분 컷의 감정 대비) |
| 54 | ☑ | `주머니_대가_건넨_거래.webp` | 상황·거래 | 주머니 78·대가 29·건넨 21 — 경제 루프·정보 구매 |
| 55 | ☑ | `검은얼음_시장_좌판_지하.webp` | 장소·시장 | 검은얼음 29·좌판 48·지하 16 — 미방문이나 언급 다수, 카일룬 무대 |
| 56 | ☑ | `세피_호기심_안내_오로라.webp` | 인물·감정 | 세피 14·호기심 37·오로라 14 — 눈먼 어린 안내인 |
| 57 | ☑ | `관측탑_오로라_금속_계단.webp` | 장소·관측탑 | 관측탑 16·금속 53·계단 15 — 사엘·오드린 무대 |
| 58 | ☑ | `심장_웅덩이_액체_빛나는.webp` | 장소·성지 | 웅덩이 57·심장 32·액체 19 — 퀘스트 후반 핵심 무대 |
| 59 | ☑ | `무음_해변_고래_얼음.webp` | 장소·종반 | 언급 0 (플레이테스트 단축런이 미도달) — 엔딩 동선 선행 대비 |

> #55·57·58·59는 현재 체류 실측이 0~5턴이지만 퀘스트 동선상 실유저 장기런의 필수
> 무대라 선행 투입 가치가 있다 (노출은 도달 시점부터).

## 1. 공통 스타일 프리픽스 (guides/12 §7과 동일 — 모든 프롬프트 앞에 붙임)

```
Dark fantasy polar-night coastal illustration, painterly digital art, cold
indigo and bone-white palette with faint starlight glimmer, long polar
twilight, quiet melancholic wonder, no text, no watermark, cinematic
composition, 16:9
```

인물 감정 컷 규칙 (graymar와 다른 점):
- **star_sand는 초상화 풀이 비어 있다** (`assets.json portraits: []`) — 참조할 초상이
  없으므로 **기존 감정 컷이 얼굴 정본**이다: 이렌은 `이렌_근심_걱정_여관주인.webp`,
  루오르는 `루오르_차분_기록_촛불.webp` 를 참조 이미지로 같은 얼굴 유지.
- 유르마·아바스·세피는 **이번이 첫 컷 = 이후 얼굴 정본**이 된다. 생성 결과를 보관해
  후속 감정 컷 제작 시 참조할 것.
- 상반신~바스트샷, 배경은 그 인물의 활동 장소를 흐리게 (규약 동일).

## 2. 상황씬 프롬프트 (조사·공통몽·램프·거래)

**#46 지도_흔적_수색_등불** — INVESTIGATE 57턴의 대표 컷
```
weathered coastal map and scribbled notes spread on a rough table, gloved
finger tracing a route, whale-oil lantern glow, frost creeping on the
window behind, search-planning tension
```

**#47 잠꼬대_뒤척_침상_night** — 공통몽 서사 축 (여관 투숙객들이 같은 꿈을 꾼다)
```
dim inn dormitory at polar night, several sleepers tossing restlessly under
fur blankets, one murmuring with furrowed brow, faint star-blue glow seeping
through frosted shutters, uneasy shared-dream atmosphere
```

**#48 램프_심지_고래기름_불빛**
```
close-up of hands trimming the wick of a whale-oil lamp, warm amber flame
flaring, glass and brass fittings, oil sheen, small workbench clutter,
intimate pool of light against polar darkness
```

**#54 주머니_대가_건넨_거래**
```
close-up of a small coin pouch being passed between fur-gloved hands over
a plank counter, breath fog between the two figures, wary bargaining mood,
lantern-lit dockside stall edge
```

## 3. 장소·정경씬 프롬프트

**#52 절벽_파도_바람_극야**
```
towering dark sea cliffs under the polar night, waves bursting white
against ice-glazed rock, wind-torn snow streaming sideways, distant
convent lanterns dotting the cliff top, vast lonely grandeur
```

**#55 검은얼음_시장_좌판_지하**
```
clandestine underground market in a frozen sewer tunnel, stalls of bone
charms and glowing vials on plank counters, black glossy ice walls
reflecting candle flames, hooded traders haggling in whispers
```

**#57 관측탑_오로라_금속_계단**
```
interior of a metal observation tower, spiral iron staircase rising past
rime-coated struts, a great viewing aperture open to swirling green-violet
aurora, charts and instruments on landings, cold scientific solitude
```

**#58 심장_웅덩이_액체_빛나는**
```
a luminous pool of molten starlight liquid cradled in dark whale-flesh
stone, gentle pulsing glow lighting the cavern from below, thin ritual
walkway at the rim, awe and danger in equal measure
```

**#59 무음_해변_고래_얼음** — 엔딩 동선 대비 컷
```
utterly still beach where a colossal whale head lies buried under clear
ice, one immense eye glowing faintly like a star beneath the surface,
no waves, snow hanging motionless in the air, sacred unnatural silence
```

## 4. 인물 감정 컷 프롬프트 (등장 실측순)

> 규약: 파일명 첫 토큰 = **실명** (매칭 키). §1의 얼굴 정본 규칙 준수.

**#45 이렌_미소_안도_감사** — 의뢰 보고·정산 대면 컷 (graymar #13 로넨_안도 대응)
```
[이렌_근심_걱정_여관주인.webp 참조 — 동일 얼굴] middle-aged innkeeper woman,
shoulders easing with quiet relief, soft grateful smile, offering a warm
drink across the counter, hearth glow behind, the calm of a burden shared
```

**#50 이렌_창백_충격_떨림** — 꿈 목격담·예언 순간
```
[이렌_근심_걱정_여관주인.webp 참조 — 동일 얼굴] the innkeeper gone pale
mid-sentence, eyes unfocused as if seeing something distant, trembling hand
gripping her apron, candle flame bending, prophetic dread
```

**#49 유르마_순례자_무장_수색** — 첫 컷 = 이후 얼굴 정본
```
stern young female pilgrim in travel-worn furs over light armor, short
spear slung at her back, holding up a worn portrait locket, resolute
grief-hardened eyes, snowy pilgrim road behind blurred
```

**#51 아바스_장인_램프_유리** — 첫 컷 = 이후 얼굴 정본
```
unhurried old male craftsman with soot-lined hands cradling a finished
whale-oil lamp, gazing into its flame as if reading something there, calm
knowing half-smile, cluttered dockside workshop blurred behind
```

**#53 루오르_경계_침묵_환자**
```
[루오르_차분_기록_촛불.webp 참조 — 동일 얼굴] the gray-habited nun stepping
protectively before a curtained sickbed, ledger clasped shut against her
chest, level guarded stare, lantern-lit infirmary hush
```

**#56 세피_호기심_안내_오로라** — 첫 컷 = 이후 얼굴 정본
```
small blind girl guide with pale unfocused eyes and a bright wondering
smile, face tilted up toward aurora light she cannot see, small hand
raised as if smelling the colors, lantern rope tied at her waist, falling
snow sparkling
```

## 5. 투입 절차 (리마인드)

```
1) 생성 → webp 변환 → 체크리스트의 파일명 그대로 저장
2) content/star_sand_v1/assets/scenes/ 에 넣기 (몇 장씩 나눠 넣어도 됨)
3) python3 scripts/sync_pack_assets.py star_sand_v1
4) 서버 재시작 + client push (public/pack-assets 포함)
5) 체크리스트 ☑ + 유르마·아바스·세피 첫 컷은 얼굴 정본으로 별도 보관
```

---

# 4차 배치 (#60~75) — 상황 다변화 + 초상화 배리에이션 (2026-08-02)

> 3차 15종 투입 완료 후 확장: 같은 311턴 코퍼스에서 **미커버 최상위 소재**
> (냉기 57 · 성에 56 · 손님 63 · 중개인 38 · 응시 33 · 불꽃 31 · 열쇠 31 ·
> 투숙객 29 · 수군- 29 · 일렁- 25 · 기억 23 · 실종 20 · 잃은 18 · 명부 16)와
> **CORE 미커버 4인**(카일룬·나하트·사엘·마레크 — 중후반 퀘스트 필수 대면)을 채운다.
>
> ⚠️ 이 배치로 팩 총량 39장 — guides/11 권장(12~20장)을 초과하지만, 쿨다운 3턴 +
> 런 내 1회 제한으로 **노출 총량은 불변, 다양성만 상승**한다 (반복 노출 체감 억제 목적).
> 태그 함정 추가 실측: '죽'(40)·'개'(233)·'새'(411)는 죽다/지금개/새벽 파편 — 태그 금지.
> '손끝'(102)은 범용 제스처라 프리스크린 과통과 유발 — 단독 태그 금지.

## 6. 4차 체크리스트

| # | ☐ | 파일명 (= 태그) | 유형 | 실측 근거 |
|---|---|----------------|------|----------|
| 60 | ☑ | `성에_창문_서리_냉기.webp` | 정경·한기 | 성에 56·냉기 57 — 미커버 최상위 소재 (여관·수녀원 창가) |
| 61 | ☑ | `투숙객_술잔_벽난로_수군.webp` | 상황·술자리 | 투숙객 29·벽난로 25·수군- 29 — 여관 밤 사교 무대 |
| 62 | ☑ | `이렌_접객_분주_손님.webp` | 인물·감정 | 손님 63 — 이렌 일상 환대 배리에이션 (기존 3종: 근심·미소·창백) |
| 63 | ☑ | `오로라_일렁_밤하늘.webp` | 정경·하늘 | 오로라 14·일렁- 25 — 하늘 정경 (별빛 해변 컷과 별개 구도) |
| 64 | ☑ | `열쇠_복도_문틈_night.webp` | 상황·잠입 | 열쇠 31·복도 7·문틈 6 — 객실 조사·STEAL 7 |
| 65 | ☑ | `명부_실종_이름_촛불.webp` | 상황·조사 | 명부 16·실종 20 — 투숙 명부·실종자 대조 (헬룬 서사 연계) |
| 66 | ☑ | `헬룬_장례사_회고_침묵.webp` | 인물·감정 | 여관 장기 투숙(체류 1위 무대 상주) — 실종자 마지막 말 기록 |
| 67 | ☑ | `유르마_침통_울음_동생.webp` | 인물·감정 | 울음 10·동생 6 — 결의 컷의 감정 대비(슬픔) |
| 68 | ☑ | `아바스_불꽃_응시.webp` | 인물·감정 | 응시 33·불꽃 31 — 램프 불빛에서 미래를 읽는 순간 (장인 컷 대비) |
| 69 | ☑ | `채굴_갈비_등불_그림자.webp` | 상황·채굴 | 갈비평원 체류 3위(33턴)인데 상황 컷 부재 — 채굴 8·그림자 92 |
| 70 | ☑ | `카일룬_능글_꿈약_유리병.webp` | 인물·CORE 첫 컷 | 카일룬 9 — 검은얼음 시장 조제사, 시장 컷과 세트 |
| 71 | ☑ | `마레크_수색꾼_길잡이_밧줄.webp` | 인물·CORE 첫 컷 | 수색 16·밧줄 13 — 별고래 내부 진입 동선 필수 대면 |
| 72 | ☑ | `사엘_학자_관측_기록.webp` | 인물·CORE 첫 컷 | 관측 20·기록 34 — 관측탑 컷과 세트, 기록 조작 서사 |
| 73 | ☑ | `토바_중개인_계산_흥정.webp` | 인물·감정 | 중개인 38 — 흰숨 부두 정보 판매·왕실 보고선 서사 |
| 74 | ☑ | `카시엔_장로_침묵_모피.webp` | 인물·감정 | 모피 36·침묵 63 — 전승 봉인 서사 |
| 75 | ☑ | `나하트_잃은_기억_허공.webp` | 인물·CORE 첫 컷 | 기억 23·잃은 18·허공 10 — 팩 핵심 반전의 얼굴 |

## 7. 4차 프롬프트 — 상황·정경 (공통 프리픽스 §1 동일)

**#60 성에_창문_서리_냉기**
```
close-up of a frost-flowered windowpane from inside a warm room, intricate
ice crystals spreading across dark glass, faint aurora glow bleeding
through, candle reflection, hush of deep cold pressing in
```

**#61 투숙객_술잔_벽난로_수군**
```
inn common room at night, fur-clad lodgers hunched over mugs around the
great hearth, heads leaning together in low murmured rumor-trading,
firelight on worried faces, snow ticking at the windows
```

**#63 오로라_일렁_밤하늘**
```
vast polar night sky filled with rippling green-violet aurora curtains
folding over themselves, thin snowbound rooftops and lantern dots tiny at
the frame bottom, silent overwhelming sky
```

**#64 열쇠_복도_문틈_night**
```
dim timber inn corridor at night, a hand slipping an iron key toward a
door, thin candlelight leaking through the door crack, floorboard shadows
long, held-breath trespass tension
```

**#65 명부_실종_이름_촛불**
```
worn guest ledger open on a counter, column of handwritten names with
several struck through or faded, fingertip pausing on a missing lodger's
line, candle flame, quiet dread of a pattern emerging
```

**#69 채굴_갈비_등불_그림자**
```
miners working inside the colossal whale rib vault, pick strokes echoing,
hanging oil lamps swaying huge rib shadows across bone walls, dust motes
in cold light, uneasy industry inside a sacred carcass
```

## 8. 4차 프롬프트 — 인물 감정 컷

> 얼굴 정본 규칙(§1) 유지: 이렌·유르마·아바스는 기존 컷 참조. 헬룬·카일룬·마레크·
> 사엘·토바·카시엔·나하트는 **이번이 첫 컷 = 이후 얼굴 정본** — 결과물 보관.

**#62 이렌_접객_분주_손님** — 일상 환대 배리에이션
```
[이렌_근심_걱정_여관주인.webp 참조 — 동일 얼굴] the innkeeper mid-bustle,
balancing steaming bowls along one arm, warm practiced hosting smile that
doesn't quite reach tired eyes, firelit common room alive behind her
```

**#66 헬룬_장례사_회고_침묵** — 첫 컷 = 얼굴 정본
```
gaunt elderly man in a threadbare formal coat sitting in the inn's darkest
corner, thin notebook open, gazing past the fire into memory, undertaker's
composed stillness, faint unease of a man who fears sleepers more than the
dead
```

**#67 유르마_침통_울음_동생** — 결의 컷의 감정 대비
```
[유르마_순례자_무장_수색.webp 참조 — 동일 얼굴] the armed pilgrim alone at
night, spear leaned against the wall, pressing the small portrait locket to
her forehead with both hands, silent tears, grief breaking through armor
```

**#68 아바스_불꽃_응시** — 장인 컷의 감정 대비
```
[아바스_장인_램프_유리.webp 참조 — 동일 얼굴] the lamp craftsman utterly
still, face lit from below by a single flame, pupils reflecting the fire,
reading something in the light that isn't there, reverent unease
```

**#70 카일룬_능글_꿈약_유리병** — 첫 컷 = 얼굴 정본
```
lean sly apothecary in a patched fur coat, holding a small glowing vial up
between two fingers with a playful dangerous grin, teeth showing, black-ice
market stall clutter blurred behind, charm hiding menace
```

**#71 마레크_수색꾼_길잡이_밧줄** — 첫 컷 = 얼굴 정본
```
weathered blunt-faced tracker coiling a climbing rope across his chest,
hard practical eyes scanning off-frame, frost in his beard stubble, bone
cavern mouth blurred behind, a man of distances and traces not words
```

**#72 사엘_학자_관측_기록** — 첫 컷 = 얼굴 정본
```
austere androgynous scholar in a high-collared coat at a chart-strewn desk,
pen paused mid-entry, gaze caught by something beautiful through the tower
aperture, cold discipline cracking into wonder, guilt at the edge of it
```

**#73 토바_중개인_계산_흥정** — 첫 컷 = 얼굴 정본
```
sharp-eyed businesslike woman in practical furs at a dockside desk of
manifests, weighing a coin absently between gloved fingers, appraising
stare that prices everything, ship masts through frosted glass behind
```

**#74 카시엔_장로_침묵_모피** — 첫 컷 = 얼굴 정본
```
ancient hunter elder wrapped in heavy sea-mammal furs, deep-lined wind-cut
face, eyes closed mid-refusal as if holding a sealed story, bone charms
braided in white hair, snowfall settling on his shoulders
```

**#75 나하트_잃은_기억_허공** — 첫 컷 = 얼굴 정본 (팩 핵심 반전)
```
androgynous returnee with an unsettling serene childlike face, hollow eyes
fixed on empty air slightly above the viewer, faint star-flecks drifting in
the irises, threadbare blanket around shoulders, presence both small and
immense
```

---

# 5차 배치 (#76~91) — 사건(Incident)·퀘스트 후반 무대 + SUB 잔여 (2026-08-02)

> 4차까지로 일상·조사·거점 인물은 대부분 커버 — 5차는 **아직 코퍼스에 없는 장면**을
> 콘텐츠 정의에서 선행 태깅한다. 근거가 실측 빈도가 아니라 **콘텐츠 주입 어휘**라는
> 점이 이전 배치와 다르다:
>
> - **Incident 10종** (incidents.json): 공통몽 확산·갈비평원 붕괴·심장액 역류·수녀원
>   강제 이송·꿈약 중독자 폭주·부두 봉쇄·별빛 짐승 출현(MILITARY 전투) 등 — 발동 시
>   서술이 반드시 그 어휘로 쓰인다 (scene_shells ALERT/DANGER 텍스트도 동일 주입).
> - **퀘스트 fact 문구** (facts.json): questReveal 이 fact description 을 서술에 동일
>   주입(불변식 27)하므로 '별소금'·'하얀 문'·'꿈의 닻'·'하늘 바다' 태그는 해당 단계
>   도달 턴에 확정적으로 등장한다.
> - 검증 가능한 것은 코퍼스로 재확인: 소금 95 · 걸음 89 · 바다 75 · 내부 26 · 통로 16 ·
>   잿빛 18 · 열쇠판 11 · 사슬 10 · 하얀 13 · 별소금 3(조기 노출 확인).
>
> ⚠️ '닻'·'문'·'눈'은 1글자 토큰이라 태그 불가 — 사슬·통로·눈동자 등 주변어로 우회.
> 이 배치로 팩 총량 55장 — 노출 총량은 쿨다운으로 불변, 미도달 구간 대비가 목적.

## 9. 5차 체크리스트

| # | ☐ | 파일명 (= 태그) | 유형 | 근거 |
|---|---|----------------|------|------|
| 76 | ☑ | `별소금_침상_소금_흔적.webp` | 상황·단서 | FACT_SS_STAR_SALT(S1 초입 fact) — 소금 95·흔적 54, 조기 노출 기대 최상 |
| 77 | ☑ | `몽유_맨발_눈길_night.webp` | 사건·공통몽 확산 | scene_shells ALERT "맨발로 문을 나서려던 몽유병자" — 주입 어휘 선행 태깅 |
| 78 | ☑ | `브란_채굴_반장_불면.webp` | 인물·SUB 첫 컷 | 갈비평원(체류 3위) 반장 — 밤마다 고래 울음에 불면 서사 |
| 79 | ☑ | `꿈약_난동_시장_발광.webp` | 사건·중독 폭주 | Incident CRIMINAL — 꿈약 9·시장 131 |
| 80 | ☑ | `짐승_별빛_그림자_night.webp` | 사건·전투 | Incident MILITARY '별빛 짐승 출현' — 유일 전투 컷 |
| 81 | ☑ | `붕괴_갈비_무너진_잔해.webp` | 사건·재해 | Incident '갈비평원 붕괴' — 갈비 20 |
| 82 | ☑ | `역류_심장_넘치는_액체.webp` | 사건·이변 | Incident '심장액 역류' + FACT_SS_HEART_REFILL |
| 83 | ☑ | `이송_환자_수레_night.webp` | 사건·수녀원 | Incident POLITICAL '수녀원 강제 이송' — 환자 25·수레 13 |
| 84 | ☑ | `봉쇄_부두_선박_왕실.webp` | 사건·봉쇄 | Incident ECONOMIC '부두 봉쇄' + 토바 왕실 보고선 서사 |
| 85 | ☑ | `미렌_환자_떨림_허공.webp` | 인물·SUB 첫 컷 | 심장 웅덩이 목격자 — "손이 아직 뼈 안에 있다" 망상 |
| 86 | ☑ | `에드_서기관_수첩_이름.webp` | 인물·SUB 첫 컷 | 이름 수집가 — '이름 상실' Incident·나하트 추적 연계 |
| 87 | ☑ | `오드린_보조원_불안_기록.webp` | 인물·SUB 첫 컷 | 관측 보고서 은폐 Incident 의 내부 고발자 |
| 88 | ☑ | `하얀_통로_환영_빛무리.webp` | 무대·S2 | FACT_SS_WHITE_DOOR "하얀 문" — 하얀 13·통로 16 ('문' 1글자 우회) |
| 89 | ☑ | `하늘_바다_기억_유영.webp` | 무대·S3 | S3_INSIDE "하늘 바다의 기억 속에서 실종자를 만난다" — 바다 75·기억 23 |
| 90 | ☑ | `사슬_실종_붙잡힌.webp` | 무대·S4 | FACT_SS_DREAM_ANCHOR "꿈의 닻" — 사슬 10·실종 20 ('닻' 1글자 우회) |
| 91 | ☑ | `별고래_눈동자_대면_거대.webp` | 무대·S5 | S5_RESOLVE "별고래의 눈 앞에서 최종 선택" — 별고래 54·눈동자 42 |

> #88~91은 무음 해변 컷(#59)과 같은 선행 대비 성격 — 도달 전엔 조용히 잠들어 있다.
> 잔여 미커버: 리바·페나 (저노출 SUB — 시장·웅덩이 체류 데이터가 쌓이면 다음 배치).

## 10. 5차 프롬프트 — 사건·단서 (공통 프리픽스 §1 동일)

**#76 별소금_침상_소금_흔적** — S1 핵심 단서의 시각화
```
empty inn bed with blankets thrown back, a human-shaped scatter of
glittering star-salt crystals where the sleeper lay, faint blue shimmer,
lantern raised over the scene, wrongness made beautiful
```

**#77 몽유_맨발_눈길_night**
```
nightgowned figure walking barefoot away down a snow lane under the polar
night, arms slack, unhurried trance gait, footprints trailing from an open
inn door spilling warm light, silent horror
```

**#79 꿈약_난동_시장_발광**
```
underground market chaos, a wild-eyed addict knocking over a stall of
glowing vials, spilled dream-draught pooling in luminous streaks, traders
recoiling, scattered wares, jagged panic energy
```

**#80 짐승_별빛_그림자_night**
```
huge indistinct beast of drifting starlight and shadow prowling at the
snowfield's edge, form flickering like a constellation half-remembered,
hunters' lanterns tiny before it, dread and awe
```

**#81 붕괴_갈비_무너진_잔해**
```
collapsed section of the great rib vault, splintered bone pillars and
rubble half-burying mining scaffolds, dust hanging in lantern beams,
workers scrambling at the edge of the ruin
```

**#82 역류_심장_넘치는_액체**
```
the heart pool overflowing its rim, luminous liquid running in glowing
rivulets across dark stone toward the viewer, pulsing brighter than it
should, ritual markers toppled, beautiful and wrong
```

**#83 이송_환자_수레_night**
```
covered cart being loaded with blanketed patients outside the convent gate
at night, soldiers with lanterns overseeing, a nun protesting with raised
hand, snow falling on the grim procession
```

**#84 봉쇄_부두_선박_왕실**
```
the frozen dock barred with hasty barricades, an imposing dark ship with
official banners moored beyond, soldiers turning back fishermen, breath
fog and simmering resentment in the cold
```

## 11. 5차 프롬프트 — 퀘스트 후반 무대 (S2~S5)

**#88 하얀_통로_환영_빛무리**
```
dreamlike vision of a pale white door standing alone in a dark corridor of
mist, soft light bleeding through its seams, drifting motes, the viewer's
reaching hand faintly translucent, threshold of somewhere else
```

**#89 하늘_바다_기억_유영**
```
inverted dream-sea inside the whale's memory, figures drifting weightless
among schools of light like stars, horizon curving upward into deep indigo
water-sky, serene and unmoored from reality
```

**#90 사슬_실종_붙잡힌**
```
sleeping figures suspended in dark dream-water, each tethered by a faint
luminous chain running down into an unseen deep, hair and clothes drifting,
peaceful faces betraying their captivity, sorrowful stillness
```

**#91 별고래_눈동자_대면_거대**
```
lone tiny figure standing before a colossal ancient eye opening in a wall
of dark flesh and ice, iris swirling with galaxies, reflected silhouette
in the vast pupil, the moment before a final answer
```

## 12. 5차 프롬프트 — 인물 감정 컷 (전원 첫 컷 = 얼굴 정본)

**#78 브란_채굴_반장_불면**
```
broad rough foreman slumped on a bone ledge with a cold pipe, deep
exhausted shadows under bloodshot eyes, jaw tight as if hearing a sound
no one else does, rib-vault mining site blurred behind
```

**#85 미렌_환자_떨림_허공**
```
gaunt former miner in an infirmary cot, staring at his own trembling
raised hand as if it belongs elsewhere, sweat-damp hair, lantern-lit
sickroom blurred, quiet unraveling
```

**#86 에드_서기관_수첩_이름**
```
scruffy wandering scribe hunched over a battered notebook dense with
crossed-out names, murmuring as he writes, ink-stained fingerless gloves,
eyes too eager, inn corner table clutter
```

**#87 오드린_보조원_불안_기록**
```
young nervous archivist clutching a folder of original charts to his
chest, glancing over his shoulder down the tower stairs, torn between
loyalty and truth, candlelight trembling
```

---

# 6차 배치 (#110~142) — 인물 감정 3종 체제 (2026-08-14)

> 목표: **CORE·SUB 18명 전원이 감정 컷 최소 3종**을 갖게 한다. 5차까지는 대부분
> 1종(직능 소개 컷)이라, 그 인물이 나오는 턴이면 관계·국면과 무관하게 늘 같은 얼굴이
> 떴다. 이번 배치로 star_sand 인물 컷은 22장 → **55장**이 된다.
>
> 근거 데이터: star_sand_v1 실런 서술 코퍼스 **355턴 / 176,741자** (2026-07-14 ~ 08-12, DB 실측).
> 5차 작성 시점(311턴) 대비 +44턴이며 인물 노출 순위는 변동 없다.

## 13. 왜 3종인가 — 매칭 엔진이 감정을 고르는 실제 원리

`SceneCutMatcher` 의 렉시컬 프리스크린은 **태그가 서술에 몇 개나 등장하는지(hits)를
세어 많은 순으로 정렬**하고, 상위 후보만 nano 판정에 넘긴다
(`scene-cut-matcher.service.ts` — `narrative.includes(kw)` / `sort(b.hits - a.hits)`).

여기서 이 배치의 설계 규칙이 나온다.

1. **첫 토큰 = 실명**. 그 인물이 서술에 등장한 턴에만 후보가 되고(hits ≥ 1), 다른
   인물 턴에는 아예 안 걸린다. 인물 컷의 진입권이자 오귀속 방지선이다.
2. **같은 인물의 컷끼리 감정 토큰이 겹치면 안 된다.** 겹치면 세 컷이 모두 hits=1로
   동률이 되고, 동률은 `runId+turnNo` 시드 셔플로 갈린다 — 즉 **감정과 무관한 무작위
   선택**이 된다. 토큰을 달리 배분해야 "창백" 이 쓰인 턴엔 창백 컷이 hits=2로 이긴다.
3. **감정 토큰은 실측 상위 어휘에서 고른다.** 코퍼스에 안 나오는 낱말(`분노` 1 ·
   `공포` 0 · `발작` 0)로 태그하면 그 컷은 영원히 hits=1이라 2번의 이점을 못 받는다.

### 이 팩의 감정 어휘 실측 (355턴)

| 사용 가능 (2글자+·중빈도) | 회 | | 회 | | 회 |
|---|---:|---|---:|---|---:|
| 침묵 | 72 | 창백 | 53 | 응시 | 35 |
| 흔들 | 64 | 경계 | 46 | 고요 | 27 |
| 정적 | 60 | 끄덕 | 44 | 떨리(떨림 17) | 26 |
| 눈빛 | 59 | 입술 | 36 | 움츠 | 19 |
| 미소 | 57 | 물러 | 36 | 불안 | 15 |

| 상황 어휘 | 회 | | 회 | | 회 |
|---|---:|---|---:|---|---:|
| 금기 | 76 | 명부 | 25 | 밧줄 | 14 |
| 긴장 | 75 | 속삭 | 22 | 매달 | 13 |
| 골목 | 47 | 손짓 | 21 | 수레 | 13 |
| 모피 | 42 | 옷자락 | 20 | 발견 | 12 |
| 허가 | 39 | 수첩 | 20 | 서류 · 은밀 | 11 |
| 운반 | 33 | 계단 | 18 | 울음 · 움켜 | 10 |
| 짐꾼 | 27 | 기도 | 14 | 잠들 | 9 |

⚠️ **태그 금지어 (이번에 확인)**: `등불`(200) · `목소리`(191) · `고개`(169) ·
`시선`(194) · `손끝`(118) · `낮은`(98) · `다가`(128) 는 사실상 전 턴 등장이라
hits 를 무의미하게 부풀린다. `분노`·`공포`·`거절`·`항의`·`발작`·`원본`·`밀수`·
`붕괴`·`동행`·`추격`은 **0~1회**라 태그로서 죽은 낱말이다.

### 인물 노출 실측 (서술 내 실명 등장, 355턴)

| 인물 | 회 | 보유 컷 | 인물 | 회 | 보유 컷 |
|---|---:|---:|---|---:|---:|
| 이렌 | 357 | 4 ✔ | 카일룬 | 9 | 1 |
| 유르마 | 44 | 2 | 토바 | 9 | 1 |
| 루오르 | 43 | 2 | 리바 | 6 | **0** |
| 아바스 | 30 | 2 | 에드 | 6 | 1 |
| 세피 | 14 | 1 | 사엘·마레크·나하트·브란·오드린·헬룬·미렌·카시엔·페나 | 0 | 1 (페나 0) |

> 하위 9명이 0회인 것은 컷이 필요 없다는 뜻이 아니라 **플레이테스트 단축런(10~15턴)이
> 중후반 동선에 도달하지 못한다**는 뜻이다 (5차에서 이미 확인된 패턴). 이렌만 4종을
> 갖춘 현 상태는 실유저 장기런에서 "이렌 외 전원은 표정이 하나"로 체감된다.

## 14. 6차 체크리스트 (노출 실측 우선순위순)

| # | ☐ | 파일명 (= 태그) | 감정 국면 | 태그 근거 (실측 회) |
|---|---|----------------|----------|-------------------|
| 110 | ☑ | `유르마_경계_긴장_움켜.webp` | 전투 경계 | 경계46·긴장75·움켜10 (기존 수색·침통과 무겹침) |
| 111 | ☑ | `루오르_흔들_명부_봉인.webp` | 은폐가 흔들림 | 흔들64·명부25·봉인5 |
| 112 | ☑ | `아바스_창백_경고_두려움.webp` | 불길한 예감 | 창백53·경고3·두려움7 |
| 113 | ☑ | `세피_옷자락_매달_불안.webp` | 아이의 매달림 | 옷자락20·매달13·불안15 |
| 114 | ☑ | `세피_기도_회랑_고요.webp` | 기도 중 정적 | 기도14·회랑4·고요27 |
| 115 | ☑ | `카일룬_속삭_경고_은밀.webp` | 농담 뒤 진담 | 속삭22·경고3·은밀11 |
| 116 | ☑ | `카일룬_물러_긴장_골목.webp` | 발뺌·도주 | 물러36·긴장75·골목47 |
| 117 | ☑ | `토바_긴장_보고선_눈빛.webp` | 왕실 압박 | 긴장75·보고선6·눈빛59 |
| 118 | ☑ | `토바_은밀_속삭_서류.webp` | 정보 매매 | 은밀11·속삭22·서류11 |
| 119 | ☑ | `에드_발견_명부_움켜.webp` | 이름 발견 | 발견12·명부25·움켜10 |
| 120 | ☑ | `에드_창백_잠들_두려움.webp` | 수집의 대가 | 창백53·잠들9·두려움7 |
| 121 | ☑ | `리바_운반_수레_밧줄.webp` | **첫 컷 = 정본** | 운반33·수레13·밧줄14 |
| 122 | ☑ | `리바_긴장_골목_물러.webp` | 단속 회피 | 긴장75·골목47·물러36 |
| 123 | ☑ | `리바_은밀_손짓_창백.webp` | 발각 직전 | 은밀11·손짓21·창백53 |
| 124 | ☑ | `사엘_흔들_침묵_계단.webp` | 진실 앞 주저 | 흔들64·침묵72·계단18 |
| 125 | ☑ | `사엘_응시_창가_고요.webp` | 미(美)에 굴복 | 응시35·창가6·고요27 |
| 126 | ☑ | `마레크_침묵_굳어_잠들.webp` | 꿈 얘기에 굳음 | 침묵72·굳어4·잠들9 |
| 127 | ☑ | `마레크_결심_움켜_긴장.webp` | 진입 결단 | 결심5·움켜10·긴장75 |
| 128 | ☑ | `나하트_미소_고요_눈빛.webp` | 아이 같은 평온 | 미소57·고요27·눈빛59 |
| 129 | ☑ | `나하트_정적_움츠_속삭.webp` | 거대한 것이 말함 | 정적60·움츠19·속삭22 |
| 130 | ☑ | `브란_긴장_움켜_경고.webp` | 갱도 위험 경고 | 긴장75·움켜10·경고3 |
| 131 | ☑ | `브란_창백_울음_침묵.webp` | 고래 울음에 질림 | 창백53·울음10·침묵72 |
| 132 | ☑ | `오드린_결심_내밀_계단.webp` | 내부 고발 | 결심5·내밀9·계단18 |
| 133 | ☑ | `오드린_창백_멈칫_긴장.webp` | 들킬 뻔함 | 창백53·멈칫6·긴장75 |
| 134 | ☑ | `헬룬_수첩_유언_속삭.webp` | 마지막 말 기록 | 수첩20·유언1·속삭22 |
| 135 | ☑ | `헬룬_경고_잠들_두려움.webp` | 잠들지 말라 | 경고3·잠들9·두려움7 |
| 136 | ☑ | `미렌_비명_침상_움켜.webp` | 발작 | 비명2·침상6·움켜10 |
| 137 | ☑ | `미렌_고요_창가_끄덕.webp` | 드문 맑은 순간 | 고요27·창가6·끄덕44 |
| 138 | ☑ | `카시엔_금기_경고_봉인.webp` | 전승 봉인 | **금기76**·경고3·봉인5 |
| 139 | ☑ | `카시엔_기도_고요_정적.webp` | 침묵의 의례 | 기도14·고요27·정적60 |
| 140 | ☑ | `페나_허가_서류_봉인.webp` | **첫 컷 = 정본** | 허가39·서류11·봉인5 |
| 141 | ☑ | `페나_경계_금기_물러.webp` | 규정 방패 | 경계46·금기76·물러36 |
| 142 | ☑ | `페나_은밀_움츠_눈빛.webp` | 묵인·뒷거래 | 은밀11·움츠19·눈빛59 |

> 이렌(4종)은 이번 배치 제외 — 이미 근심·미소·창백·접객으로 4국면을 덮는다.
> 이 배치로 팩 총량 88장. 쿨다운 3턴 + 런 내 1회 제한이라 **노출 총량은 불변**이고
> 같은 인물을 다시 만났을 때 표정이 달라질 확률만 오른다.

## 15. 공통 스타일 프리픽스 (§1과 동일 — 모든 프롬프트 앞에 붙임)

```
Dark fantasy polar-night coastal illustration, painterly digital art, cold
indigo and bone-white palette with faint starlight glimmer, long polar
twilight, quiet melancholic wonder, no text, no watermark, cinematic
composition, 16:9
```

**얼굴 정본 규칙 (§1 연장)** — star_sand 는 초상화 풀이 비어 있어 기존 컷이 얼굴
정본이다. 아래 15명은 대괄호의 참조 파일을 반드시 함께 넣어 같은 얼굴을 유지한다.
**리바·페나는 이번이 첫 컷 = 이후 얼굴 정본**이므로 결과물을 따로 보관할 것.

## 16. 6차 프롬프트 — 상위 노출 인물 (유르마·루오르·아바스·세피)

**#110 유르마_경계_긴장_움켜**
```
[유르마_순례자_무장_수색.webp 참조 — 동일 얼굴] the armed pilgrim in a low
ready stance, short spear gripped across her body, weight shifted back,
eyes tracking something beyond the frame, jaw set, snow-blurred rocks behind
```

**#111 루오르_흔들_명부_봉인**
```
[루오르_차분_기록_촛불.webp 참조 — 동일 얼굴] the gray-habited nun standing
over a closed dream-ledger with a wax seal, one hand half-lifted toward it
and stopped, composure cracking at the mouth, candle guttering, the moment
a keeper doubts her own keeping
```

**#112 아바스_창백_경고_두려움**
```
[아바스_장인_램프_유리.webp 참조 — 동일 얼굴] the lamp craftsman drawn back
from his workbench, face bloodless in the flame light, one hand raised in
warning toward the viewer, the other still holding the lamp, dread of
something he has just understood
```

**#113 세피_옷자락_매달_불안**
```
[세피_호기심_안내_오로라.webp 참조 — 동일 얼굴] the small blind girl guide
clutching a fistful of an adult's coat hem, pressed close to their side,
head turned away listening hard, brows drawn with worry, dim convent
corridor behind
```

**#114 세피_기도_회랑_고요**
```
[세피_호기심_안내_오로라.webp 참조 — 동일 얼굴] the blind girl kneeling
alone in a lantern-lit cloister walk, small hands folded, lips barely
moving in a memorized prayer, dust and snow motes hanging still in the
lamp beams, deep hush
```

## 17. 6차 프롬프트 — 중간 노출 인물 (카일룬·토바·에드·리바)

**#115 카일룬_속삭_경고_은밀**
```
[카일룬_능글_꿈약_유리병.webp 참조 — 동일 얼굴] the sly apothecary leaning
in close, hand cupped beside his mouth, the playful grin gone flat as he
says something true for once, eyes hard and level, black-ice stall shadows
swallowing the rest
```

**#116 카일룬_물러_긴장_골목**
```
[카일룬_능글_꿈약_유리병.webp 참조 — 동일 얼굴] the apothecary backing away
down a narrow ice-walled alley, palms raised in mock surrender, smile
stretched too thin, coat already turning for flight, lantern light
receding behind him
```

**#117 토바_긴장_보고선_눈빛**
```
[토바_중개인_계산_흥정.webp 참조 — 동일 얼굴] the dockside broker standing
at a frosted window, watching an official dark-hulled ship at the quay,
manifest forgotten in her hand, calculation hardening into unease behind
her eyes
```

**#118 토바_은밀_속삭_서류**
```
[토바_중개인_계산_흥정.webp 참조 — 동일 얼굴] the broker sliding a folded
paper across a plank desk with two fingers, chin tipped low, speaking
without moving her lips, eyes flicking to the door, transaction that is
not on any manifest
```

**#119 에드_발견_명부_움켜**
```
[에드_서기관_수첩_이름.webp 참조 — 동일 얼굴] the wandering scribe seizing
an open guest ledger with both hands, finger jabbed onto a struck-through
name, mouth open mid-exclamation, eyes lit with unwholesome delight,
candle knocked askew
```

**#120 에드_창백_잠들_두려움**
```
[에드_서기관_수첩_이름.webp 참조 — 동일 얼굴] the scribe awake at a dark
table refusing to sleep, notebook shut under white knuckles, deep hollows
under his eyes, staring at nothing, a man who has collected one name too
many
```

**#121 리바_운반_수레_밧줄** — 첫 컷 = 이후 얼굴 정본
```
wiry young female runner in a patched hooded coat, hauling a rope-lashed
handcart of covered crates over packed snow, breath fogging, quick
practical eyes, black-ice market tunnel mouth blurred behind
```

**#122 리바_긴장_골목_물러**
```
[리바_운반_수레_밧줄.webp 참조 — 동일 얼굴] the runner flattened against an
alley wall of black ice, cart abandoned mid-frame, head turned toward
approaching lantern glow, body coiled to bolt, held breath
```

**#123 리바_은밀_손짓_창백**
```
[리바_운반_수레_밧줄.webp 참조 — 동일 얼굴] the runner making a small
covert hand sign to someone off-frame, hood pushed back from a
blood-drained face, crate lid ajar with faint glow leaking out, caught
between delivering and confessing
```

## 18. 6차 프롬프트 — 중후반 동선 인물 (사엘·마레크·나하트·브란·오드린)

**#124 사엘_흔들_침묵_계단**
```
[사엘_학자_관측_기록.webp 참조 — 동일 얼굴] the scholar halted on the iron
tower stair, one hand on the frozen rail, a sealed chart tube held against
the chest, looking back up toward the aperture in silence, courage failing
at the step
```

**#125 사엘_응시_창가_고요**
```
[사엘_학자_관측_기록.webp 참조 — 동일 얼굴] the scholar at the great
aperture with aurora light washing over an upturned face, pen and record
forgotten at the side, cold discipline dissolved into pure wonder,
absolute stillness
```

**#126 마레크_침묵_굳어_잠들**
```
[마레크_수색꾼_길잡이_밧줄.webp 참조 — 동일 얼굴] the tracker gone rigid
mid-motion at a mention he did not want, rope half-coiled in frozen hands,
stare fixed on the middle distance, the practical man briefly somewhere
else entirely
```

**#127 마레크_결심_움켜_긴장**
```
[마레크_수색꾼_길잡이_밧줄.webp 참조 — 동일 얼굴] the tracker cinching a
harness strap tight with a fist, chin down, shoulders squared toward a
dark bone-cavern mouth, resignation hardened into go-now resolve
```

**#128 나하트_미소_고요_눈빛**
```
[나하트_잃은_기억_허공.webp 참조 — 동일 얼굴] the nameless returnee smiling
with uncomplicated childlike delight at something small, head tilted,
star-flecks drifting slow in the irises, blanket slipping from one
shoulder, disarming warmth
```

**#129 나하트_정적_움츠_속삭**
```
[나하트_잃은_기억_허공.webp 참조 — 동일 얼굴] the returnee curled small with
knees drawn up, mouth moving in a near-soundless murmur, the air around the
figure oddly still as if the room is listening, something vast speaking
through something tiny
```

**#130 브란_긴장_움켜_경고**
```
[브란_채굴_반장_불면.webp 참조 — 동일 얼굴] the mining foreman gripping a
worker's arm to haul them back, other hand thrown out toward a fissured
rib-wall, shout half-formed, lamp swinging wild shadows
```

**#131 브란_창백_울음_침묵**
```
[브란_채굴_반장_불면.webp 참조 — 동일 얼굴] the foreman frozen with one
palm flat against the bone wall, head bowed close to it, face drained
white as he listens to a sound in the rib, the whole dig gone silent
behind him
```

**#132 오드린_결심_내밀_계단**
```
[오드린_보조원_불안_기록.webp 참조 — 동일 얼굴] the young archivist thrusting
a folder of charts forward into the viewer's space at the foot of the tower
stair, arms locked straight, terrified and committed at once
```

**#133 오드린_창백_멈칫_긴장**
```
[오드린_보조원_불안_기록.webp 참조 — 동일 얼굴] the archivist stopped dead
halfway through a doorway with papers clutched to his chest, head snapped
toward a sound above, all color gone from his face, caught
```

## 19. 6차 프롬프트 — 여관·수녀원·허가 인물 (헬룬·미렌·카시엔·페나)

**#134 헬룬_수첩_유언_속삭**
```
[헬룬_장례사_회고_침묵.webp 참조 — 동일 얼굴] the gaunt undertaker bent
close over his thin notebook, pencil moving, lips shaping the words he is
copying down from memory, hearth light barely reaching him, reverence for
last sentences
```

**#135 헬룬_경고_잠들_두려움**
```
[헬룬_장례사_회고_침묵.webp 참조 — 동일 얼굴] the old undertaker gripping the
viewer's forearm across a table, notebook shut and pushed aside, eyes wide
and urgent, warning someone not to sleep tonight
```

**#136 미렌_비명_침상_움켜**
```
[미렌_환자_떨림_허공.webp 참조 — 동일 얼굴] the contaminated patient bolting
upright in the infirmary cot mid-cry, fists knotted in the blankets, cords
standing in his neck, nun's lantern swinging into frame at the edge
```

**#137 미렌_고요_창가_끄덕**
```
[미렌_환자_떨림_허공.webp 참조 — 동일 얼굴] the patient sitting calm by a
frosted infirmary window in a rare lucid hour, blanket around his
shoulders, giving a small slow nod, exhausted clarity in his eyes
```

**#138 카시엔_금기_경고_봉인**
```
[카시엔_장로_침묵_모피.webp 참조 — 동일 얼굴] the hunter elder holding up a
flat forbidding palm, other hand closed over the bone charms at his
throat, deep-lined face set in refusal, firelight from below, a door
closing on a story
```

**#139 카시엔_기도_고요_정적**
```
[카시엔_장로_침묵_모피.webp 참조 — 동일 얼굴] the elder seated cross-legged
before low embers with eyes closed and head bowed, breath fog rising slow,
furs heavy with settled snow, the whole camp silent around him
```

**#140 페나_허가_서류_봉인** — 첫 컷 = 이후 얼굴 정본
```
brisk middle-aged female permit officer in a fur-lined official coat at a
field desk, pressing a seal onto a harvest permit, stacked forms weighted
with a stone, ledger discipline in a place that deserves awe, heart-pool
glow faint behind
```

**#141 페나_경계_금기_물러**
```
[페나_허가_서류_봉인.webp 참조 — 동일 얼굴] the permit officer stepping into
the path with an arm barred across it, permit board held like a shield,
flat unmoved stare, refusing passage to restricted ground
```

**#142 페나_은밀_움츠_눈빛**
```
[페나_허가_서류_봉인.webp 참조 — 동일 얼굴] the officer half-turned away with
shoulders drawn in, pocketing something small without looking at it, gaze
sliding sideways to check who saw, official rectitude quietly for sale
```

## 20. 투입 절차 (§5와 동일)

```
1) 생성 → webp 변환 → 체크리스트의 파일명 그대로 저장
2) content/star_sand_v1/assets/scenes/ 에 넣기 (몇 장씩 나눠 넣어도 됨)
3) python3 scripts/sync_pack_assets.py star_sand_v1
4) 서버 재시작 + client push (public/pack-assets 포함)
5) 체크리스트 ☑ + 리바·페나 첫 컷은 얼굴 정본으로 별도 보관
```

> 부분 투입해도 안전하다 — 한 인물의 3종 중 1장만 넣으면 그 컷만 후보에 오르고
> 나머지는 조용히 없는 상태로 동작한다 (§13의 hits 규칙은 존재하는 컷끼리만 겨룬다).

---

# 7차 배치 (#143~152) — 감정 축 편중 해소 + 죽은 태그 리네임 (2026-08-14)

> 6차는 **개수**를 채웠다(18명 전원 3종). 7차는 **국면**을 채운다. 55장의 인물 컷을
> 감정 축으로 분류해 보면 경계·긴장 / 창백·두려움 두 축에 쏠려 있고, 실제 서술에
> 자주 등장하는 **우호·적대·거래** 국면에는 컷이 거의 없다.
>
> 근거 데이터: star_sand_v1 실런 서술 코퍼스 **395턴 / 193,649자** (DB 실측, 6차 대비 +40턴).

## 21. 무엇이 비어 있나 — 감정 축 커버리지 실측

인물 컷 55장을 NPC posture 5축으로 분류한 결과다.

| 감정 축 | 보유 컷 | 코퍼스 어휘 (등장 턴 수 / 395) |
|---|---|---|
| 경계·긴장 (CAUTIOUS) | 다수 | 긴장 84 · 침묵 78 · 경계 47 |
| 공포 (FEARFUL) | 다수 | 창백 49 · 떨림 17 · 두려움 7 |
| **우호 (FRIENDLY)** | **이렌 1장** | **미소 63 · 부드럽 26 · 따뜻 19 · 웃음 13** |
| **적대 (HOSTILE)** | **0장** | **차갑 28 · 거칠 14 · 내뱉 12 · 불쾌 5** |
| **거래·계산 (CALCULATING)** | **토바 1장** | **대가 34 · 값 11 · 거래 9 · 계산 8 · 흥정 8** |

즉 어휘는 서술에 살아 있는데 받아줄 컷이 없다. 특히 **기본 태도가 FRIENDLY 인 4명**
(이렌·세피·아바스·유르마) 중 3명이 우호 컷 0장이고, **CALCULATING 5명**
(사엘·카일룬·리바·토바·페나) 중 리바는 밀수 운반책이면서 거래 컷이 없다.

### 인물별 빈 국면 (노출 실측순)

| 인물 | 기본 태도 | 등장턴 | 그 턴들의 실측 감정 | 이번에 채우는 것 |
|---|---|---:|---|---|
| 이렌 | FRIENDLY | 155 | 우호 68 · 공포 50 · **적대 21 · 계산 15** | 적대 + 계산 |
| 루오르 | CAUTIOUS | 15 | 공포 8 · 계산 6 · 우호 4 | (8차 이월) |
| 아바스 | FRIENDLY | 12 | **우호 5 · 계산 3** | 우호 + 거래 |
| 유르마 | FRIENDLY | 11 | **우호 3 · 적대 3** | 우호 + 적대 |
| 세피 | FRIENDLY | 5 | **우호 3** | 우호 |
| 카일룬 | CALCULATING | 3 | 우호 3 | 리네임으로 흡수 (미소) |
| 에드 | CAUTIOUS | 3 | **적대 2** | 적대 |
| 리바 | CALCULATING | 2 | (표본 부족) | 거래 |
| 카시엔 | CAUTIOUS | 0 | — | 적대 (금기 침범 축출) |

> ⚠️ 교차 집계 한계: "그 인물이 등장한 턴에 그 감정어가 있었다"이지 감정의 주체가
> 그 인물이라는 보증은 아니다. 이렌 155턴은 전체의 39%라 특히 과대계상 여지가 있다.
> 노출 0턴 9명은 단축런이 중후반 동선에 도달하지 못한 것이므로 우선순위만 뒤로 미룬다.

## 22. 7차 체크리스트 — 신규 10장

§13의 3규칙(첫 토큰=실명 / 형제 컷끼리 감정 토큰 무겹침 / 실측 상위 어휘만)을 그대로 적용했다.

| # | ☐ | 파일명 (= 태그) | 감정 국면 | 태그 근거 (등장 턴) |
|---|---|----------------|----------|-------------------|
| 143 | ☑ | `이렌_차갑_입술_물러.webp` | 선을 긋는 냉대 | 차갑28·입술41·물러33 |
| 144 | ☑ | `이렌_대가_거래_계산.webp` | 셈을 하는 주인 | 대가34·거래9·계산8 |
| 145 | ☑ | `아바스_미소_따뜻_부드럽.webp` | 장인의 호의 | 미소63·따뜻19·부드럽26 |
| 146 | ☑ | `아바스_대가_값_흥정.webp` | 값 흥정 | 대가34·값11·흥정8 |
| 147 | ☑ | `유르마_미소_끄덕_따뜻.webp` | 동행 신뢰 | 미소63·끄덕47·따뜻19 |
| 148 | ☑ | `유르마_거칠_내뱉_불쾌.webp` | 분노·의심 | 거칠14·내뱉12·불쾌5 |
| 149 | ☑ | `세피_미소_웃음_끄덕.webp` | 아이의 웃음 | 미소63·웃음13·끄덕47 |
| 150 | ☑ | `에드_차갑_내뱉_입술.webp` | 거래 거절 | 차갑28·내뱉12·입술41 |
| 151 | ☑ | `카시엔_차갑_거칠_물러.webp` | 금기 침범 축출 | 차갑28·거칠14·물러33 |
| 152 | ☑ | `리바_대가_값_주머니.webp` | 대금 흥정 | 대가34·값11·주머니63 |

**태그로 쓰면 안 되는 낱말 (이번에 재확인)** — `거절` 0 · `갱도` 0 · `등돌` 0 · `한발` 0 ·
`지친` 2 · `한숨` 3 · `돌아서` 3. 6차 금지어(`등불` 200 · `시선` 194 · `목소리` 191 ·
`고개` 169 · `다가` 128 · `손끝` 118 · `낮은` 98)도 그대로 유효하다. 참고로 `어깨` 66 ·
`손님` 66 · `주머니` 63 은 17% 수준이라 허용 범위다.

## 23. 태그 리네임 8장 — 이미지 재생성 없음

6차의 "실측 상위 어휘로만 태그" 원칙이 5차 이전 컷에는 적용되지 않았다. 아래 8장은
**코퍼스 0턴 태그**를 포함해, 실명 + `charCutOwner` 보정(+2)만으로 형제 컷과 동률이 되고
**시드 셔플로 감정과 무관하게 뽑힌다**. 이미지는 그대로 두고 파일명만 바꾼다
(각 컷의 실제 그림을 확인하고 맞춘 태그다).

| 현재 파일명 | 죽은 태그 | → 새 파일명 | 그림 근거 |
|---|---|---|---|
| `이렌_접객_분주_손님` | 접객0·분주2 | `이렌_손님_난로_분주` | 국그릇 나르는 홀, 난로 불빛 |
| `이렌_미소_안도_감사` | 안도0·감사3 | `이렌_미소_건넨_따뜻` | 두 손으로 그릇을 건넴 |
| `이렌_근심_걱정_여관주인` | 근심0 | `이렌_걱정_불안_눈빛` | 행주 쥔 채 근심 어린 눈 |
| `카일룬_능글_꿈약_유리병` | 능글0 | `카일룬_미소_꿈약_유리병` | 웃으며 발광 유리병 들어 보임 |
| `오드린_보조원_불안_기록` | 보조원0 | `오드린_불안_기록_촛불` | 기록 뭉치 껴안고 돌아봄, 촛불 |
| `유르마_침통_울음_동생` | 침통0 | `유르마_울음_동생_떨림` | 로켓을 이마에 대고 눈물 |
| `헬룬_장례사_회고_침묵` | 회고0·장례사1 | `헬룬_침묵_기억_난로` | 수첩 든 노인, 난로 곁 응시 |
| `브란_채굴_반장_불면` | 불면0·반장3 | `브란_채굴_모피_눈빛` | 모피 코트·파이프, 갈비평원 |

```bash
cd content/star_sand_v1/assets/scenes
mv 이렌_접객_분주_손님.webp        이렌_손님_난로_분주.webp
mv 이렌_미소_안도_감사.webp        이렌_미소_건넨_따뜻.webp
mv 이렌_근심_걱정_여관주인.webp    이렌_걱정_불안_눈빛.webp
mv 카일룬_능글_꿈약_유리병.webp    카일룬_미소_꿈약_유리병.webp
mv 오드린_보조원_불안_기록.webp    오드린_불안_기록_촛불.webp
mv 유르마_침통_울음_동생.webp      유르마_울음_동생_떨림.webp
mv 헬룬_장례사_회고_침묵.webp      헬룬_침묵_기억_난로.webp
mv 브란_채굴_반장_불면.webp        브란_채굴_모피_눈빛.webp
cd - && python3 scripts/sync_pack_assets.py star_sand_v1
```

> ⚠️ **부작용 1건**: `sync_pack_assets.py` 는 컷 id 를 **원본 파일명 stem 의 sha1 앞 8자**로
> 만든다(스크립트 85~110행). 리네임하면 id 가 바뀌므로 **진행 중인 런의
> `sceneCutState.usedIds` 에 있던 기록이 무효화**되어, 그 8장은 해당 런에서 한 번 더
> 뜰 수 있다. 런 내 1회 제한이 리셋되는 것뿐이라 피해는 경미하고 신규 런은 무관하다.

## 24. 7차 프롬프트 (공통 프리픽스 §1·§15 동일)

**#143 이렌_차갑_입술_물러**
```
[이렌_손님_난로_분주.webp 참조 — 동일 얼굴] the innkeeper straightened behind
her counter, cloth set down, lips pressed to a thin line, all warmth gone
from her eyes, taking one deliberate step back from the guest, hearth glow
behind her reading cold
```

**#144 이렌_대가_거래_계산**
```
[이렌_손님_난로_분주.webp 참조 — 동일 얼굴] the innkeeper counting coins into
a row on the counter, one flat palm covering the rest, weighing what the
request is worth, tally sticks and a ledger beside the lamp, businesslike
rather than unkind
```

**#145 아바스_미소_따뜻_부드럽**
```
[아바스_장인_램프_유리.webp 참조 — 동일 얼굴] the lamp artisan holding out a
finished whale-oil lamp with both hands, deep crinkled smile, workshop glow
warm on his face, offering it like a gift rather than goods
```

**#146 아바스_대가_값_흥정**
```
[아바스_장인_램프_유리.webp 참조 — 동일 얼굴] the artisan rapping a lamp's
brass fitting with one knuckle, other hand raised naming a price on his
fingers, eyebrows up in cheerful haggling, unsold lamps ranked on the bench
behind him
```

**#147 유르마_미소_끄덕_따뜻**
```
[유르마_순례자_무장_수색.webp 참조 — 동일 얼굴] the armed pilgrim giving a
short firm nod of agreement, spear butt resting on the ice, a rare warm
smile breaking through the hard face, shoulder turned to make room for
someone to walk beside her
```

**#148 유르마_거칠_내뱉_불쾌**
```
[유르마_순례자_무장_수색.webp 참조 — 동일 얼굴] the pilgrim rounding hard on
someone, jaw set, words thrown out sharp, gloved hand shoved flat against a
chest to push them back, breath steaming in the cold
```

**#149 세피_미소_웃음_끄덕**
```
[세피_호기심_안내_오로라.webp 참조 — 동일 얼굴] the young guide laughing
openly with her head tipped back, nodding yes with her whole body, mittened
hands clasped together, cloister lanterns warm behind her
```

**#150 에드_차갑_내뱉_입술**
```
[에드_서기관_수첩_이름.webp 참조 — 동일 얼굴] the wandering scribe snapping
his notebook shut against his chest, mouth a flat line, cold refusal in the
eyes, already half-turned away from whoever asked
```

**#151 카시엔_차갑_거칠_물러**
```
[카시엔_장로_침묵_모피.webp 참조 — 동일 얼굴] the elder risen to full height,
fur mantle hanging straight, one weathered hand out flat commanding a stop,
cold finality in the face, driving an outsider back off the shrine ground
```

**#152 리바_대가_값_주머니**
```
[리바_운반_수레_밧줄.webp 참조 — 동일 얼굴] the courier weighing a small coin
pouch in her palm, her other hand still resting on the crate she has not
handed over yet, price named and waiting, stacked alley crates behind her
```

## 25. 투입 절차 (§20과 동일 + 리네임)

```
1) §23 의 mv 8줄 먼저 실행 (이미지 생성 불필요 — 즉시 효과)
2) #143~152 생성 → webp 변환 → 체크리스트의 파일명 그대로 저장
3) content/star_sand_v1/assets/scenes/ 에 넣기 (몇 장씩 나눠 넣어도 됨)
4) python3 scripts/sync_pack_assets.py star_sand_v1
5) 서버 재시작 + client push (public/pack-assets 포함)
6) 체크리스트 ☑
```

투입 후 팩 총량은 88 → **98장**, 인물 컷은 55 → **65장**이 된다. 쿨다운 3턴 + 런 내
1회 제한이라 노출 총량은 불변이고, "같은 인물을 다시 만났을 때 그 순간의 감정에 맞는
얼굴이 뜰 확률"만 오른다.

### 8차 이월 (지금은 안 만드는 것)

- **루오르 공포·우호 2장** — 실측 공포 8턴/15턴으로 근거는 있으나 6차 3종이 막 투입돼
  실발화 이력이 0건이다. 며칠 쌓고 재측정 후 판단.
- **노출 0턴 9명**(사엘·마레크·나하트·브란·오드린·헬룬·미렌·카시엔·페나)의 우호 축 —
  단축런이 중후반 동선에 도달하지 못해 실측 근거가 없다. 장기런 코퍼스가 쌓이면 착수.
- **적대 축 확대** — 7차 3장(이렌·유르마·에드·카시엔)이 실제로 발화되는지부터 확인.
  `차갑`/`거칠`/`내뱉` 이 NPC 발화인지 환경 묘사인지 구분이 안 된 상태의 추정이다.
