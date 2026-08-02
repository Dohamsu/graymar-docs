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
