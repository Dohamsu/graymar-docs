# 14 — 주사위 면 텍스처 이미지 프롬프트 (Dice3D Tier 2)

> 판정 연출 `Dice3D`(client `components/hub/Dice3D.tsx`, 2026-08-06 A안)의 6면을
> CSS 그라데이션 대신 **소유자 제작 이미지**로 교체하기 위한 프롬프트 문서.
> 생성한 이미지를 아래 파일명 그대로 `client/public/dice/<배리에이션>/`에 넣고
> 알려주시면 Claude가 CSS 배선(`globals.css .dice3d-face` background 교체)을 진행한다.
>
> **배리에이션 3종 중 1종만 채택**해도 되고, 셋 다 생성해 인게임 비교 후 골라도 된다
> (폴더가 나뉘어 있어 공존 가능 — 배선 시 1종 지정).

## 파일 규약

| 항목 | 값 |
|---|---|
| 경로 | `client/public/dice/ivory/` · `client/public/dice/obsidian/` · `client/public/dice/bronze/` |
| 파일명 | `face_1.webp` ~ `face_6.webp` (눈 개수 = 파일 번호) + 선택 `blank.webp` |
| 규격 | **512×512 정사각**, webp 권장 (png 병행 가능) |
| 구도 | **주사위 한 면만 정면 탑다운** — 큐브 전체·원근·기울기 금지 (CSS가 3D 회전을 담당) |
| 여백 | 면이 캔버스를 **가장자리까지 꽉 채움** (모서리 라운딩은 CSS가 처리하므로 이미지에 라운딩·테두리 그림자 불필요) |

### 눈(pip) 배치 표준 — 현행 CSS와 동일해야 함

3×3 그리드 기준 (섞어 써도 위화감 없도록 고정):

```
1: 중앙 1개          2: 우상 + 좌하 (대각)     3: 우상 + 중앙 + 좌하 (대각)
4: 네 모서리         5: 네 모서리 + 중앙       6: 좌우 세로 3개씩 두 줄
```

### ⚠️ 생성 검수 체크리스트 (AI가 자주 틀리는 부분)

- **눈 개수가 파일 번호와 정확히 일치하는가** — 2·3·6에서 개수 오류 빈발. 생성 후 반드시 눈으로 세어 확인.
- 배치가 위 표준과 같은가 (특히 6 = 세로 두 줄, 3 = 대각선).
- 원근·기울기 없이 완전 정면인가.
- 텍스트·서명·워터마크 없음.

### 폴백: 눈 개수 오류가 계속되면 `blank.webp` 1장만

눈 없는 **재질 면 1장**(`blank.webp`)만 생성해도 된다 — 이 경우 재질은 이미지,
눈은 기존 CSS 도트를 색만 맞춰 오버레이하는 하이브리드로 배선한다 (눈 개수
정확성 100% 보장, 이미지 1장으로 6면 해결). 각 배리에이션의 blank 프롬프트는
아래 표의 "면 프롬프트"에서 **눈 문구를 통째로 빼면** 된다.

---

## 공통 스타일 (모든 프롬프트 앞에 붙이기)

```
Single die face texture, viewed perfectly straight-on from above, flat orthographic
top-down view, the square face fills the entire frame edge to edge, no perspective,
no tilt, no full cube, dark fantasy tabletop game aesthetic, painterly realistic
material detail, subtle even lighting from upper left, no text, no watermark,
no border vignette, square 1:1.
```

눈(pip) 문구는 각 면 프롬프트 끝에 붙는다 (아래 표). 프롬프트의 pip 표현이
안 먹는 생성기면 "engraved dots arranged like the N face of a standard die,
diagonal/two-columns layout"처럼 배치를 풀어 써서 재시도.

---

## 배리에이션 A — 상아 (Ivory) : 현행 톤 계승

낡은 상아 주사위. 현재 CSS 면(양피지빛 상아 + 짙은 갈색 눈)의 질감 업그레이드판.
게임의 양피지·골드 UI와 가장 무난하게 어울린다.

**배리에이션 프리픽스** (공통 스타일 뒤에):
```
Aged ivory bone die face, warm cream-white surface with fine natural bone grain
and hairline cracks, edges slightly yellowed by decades of handling, tiny chips
and wear marks, pips carved as small round pits stained with dark walnut-brown ink.
```

| 파일명 | 눈 문구 (배리에이션 프리픽스 뒤에) |
|---|---|
| `ivory/face_1.webp` | Exactly one carved pip at the exact center of the face. |
| `ivory/face_2.webp` | Exactly two carved pips on a diagonal: one at the top-right area, one at the bottom-left area. |
| `ivory/face_3.webp` | Exactly three carved pips on a diagonal line: top-right, center, bottom-left. |
| `ivory/face_4.webp` | Exactly four carved pips, one in each corner area. |
| `ivory/face_5.webp` | Exactly five carved pips: one in each corner area and one at the exact center. |
| `ivory/face_6.webp` | Exactly six carved pips in two vertical columns of three: left column and right column. |

## 배리에이션 B — 흑요석 (Obsidian) : 다크 럭셔리

칠흑의 돌에 금빛 눈. 판정 순간의 존재감이 가장 강하고, 골드 어센트 UI와 대비가
극적이다. SUCCESS/FAIL 글로우 색과도 잘 분리돼 보인다.

**배리에이션 프리픽스** (공통 스타일 뒤에):
```
Polished black obsidian die face, deep glassy volcanic stone with faint smoky
internal swirls and subtle glossy reflections, fine chipped edges hinting at
hand-cut stone, pips inlaid with molten gold, softly glowing warm metallic dots.
```

| 파일명 | 눈 문구 (배리에이션 프리픽스 뒤에) |
|---|---|
| `obsidian/face_1.webp` | Exactly one gold-inlaid pip at the exact center of the face. |
| `obsidian/face_2.webp` | Exactly two gold-inlaid pips on a diagonal: top-right area and bottom-left area. |
| `obsidian/face_3.webp` | Exactly three gold-inlaid pips on a diagonal line: top-right, center, bottom-left. |
| `obsidian/face_4.webp` | Exactly four gold-inlaid pips, one in each corner area. |
| `obsidian/face_5.webp` | Exactly five gold-inlaid pips: one in each corner area and one at the exact center. |
| `obsidian/face_6.webp` | Exactly six gold-inlaid pips in two vertical columns of three: left column and right column. |

## 배리에이션 C — 청동 (Bronze) : 용병의 주사위

전장을 떠도는 이름 없는 용병의 소지품이라는 그레이마르 주인공 서사에 가장 밀착.
긁히고 움푹 팬 청동에 초록 녹청이 앉았고, 눈은 깊게 각인돼 그늘이 진다.

**배리에이션 프리픽스** (공통 스타일 뒤에):
```
Battle-worn cast bronze die face, dull warm metal covered in scratches, dents and
sword nicks, green-blue verdigris patina settled into crevices and corners, edges
darkened by campfire soot, pips stamped deep into the metal as shadowed round
indentations with darker oxidized bottoms.
```

| 파일명 | 눈 문구 (배리에이션 프리픽스 뒤에) |
|---|---|
| `bronze/face_1.webp` | Exactly one deep stamped pip at the exact center of the face. |
| `bronze/face_2.webp` | Exactly two deep stamped pips on a diagonal: top-right area and bottom-left area. |
| `bronze/face_3.webp` | Exactly three deep stamped pips on a diagonal line: top-right, center, bottom-left. |
| `bronze/face_4.webp` | Exactly four deep stamped pips, one in each corner area. |
| `bronze/face_5.webp` | Exactly five deep stamped pips: one in each corner area and one at the exact center. |
| `bronze/face_6.webp` | Exactly six deep stamped pips in two vertical columns of three: left column and right column. |

---

## 반영 절차

1. 원하는 배리에이션의 6면(또는 폴백 `blank.webp` 1장) 생성 — 위 체크리스트로 검수.
2. `client/public/dice/<배리에이션>/face_N.webp`에 표기 파일명 그대로 저장.
3. Claude에게 배치 완료 + 채택 배리에이션을 알리면 CSS 배선 진행:
   - 6면 모드: `.dice3d-face` background-image를 면별 지정, CSS 눈 숨김.
   - blank 모드: 재질만 이미지, CSS 눈 유지(색상만 배리에이션에 맞춤).
4. client push → Vercel 자동 배포 (정적 자산이라 서버 재시작 불필요).
5. 미배치 상태에서는 현행 CSS 그라데이션 면이 그대로 동작한다 (이미지 없어도 무손상).
