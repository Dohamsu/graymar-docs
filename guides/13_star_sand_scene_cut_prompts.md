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
