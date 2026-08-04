# 97. 캐릭터 생성 간략화 — 배경 1택 체제

> 상태: ✅ 구현됨 (2026-08-04 — 설계 당일 소유자 4건 확정 후 즉시 구현. §6 미결은 전부 해소)
> 관련: arch/71 (creation-bundle·자유 시나리오 선택), arch/86 (팩 프리셋 초상화), 불변식 31·32

## 1. 문제

첫 플레이 진입까지 **6단계** (출신 → 초상화 → 이름 → 스탯 → 특성 → 확인)를 통과해야
한다. 신규 유저 관점에서:

- **스탯 +6 배분**은 게임을 해보기 전엔 판단 근거가 없는 선택이다 (LOCATION 판정
  `1d6 + floor(stat/4)` 를 모르는 상태에서 str vs per 를 고를 수 없음).
- **특성 6종**도 같은 문제 — 효과 설명이 런타임 경험 없이는 추상적.
- 실질적으로 유저의 정체성 결정은 **배경(프리셋) 1택**에 담겨 있고, 나머지 단계는
  마찰(friction)이다. 파티 신규 유저 시작 불가 백로그(2026-08-01)도 "로비에서 6단계
  생성을 요구할 수 없다"는 동일 뿌리.

## 2. 목표

- 필수 선택을 **배경 + 성별 1화면**으로 축소. 전체 2~3단계.
- 스탯·특성이 주던 개성은 **배경에 흡수** — 정보 손실 없이 선택 부담만 제거.
- 서버 계약 하위 호환 유지 (bonusStats/traitId 는 optional 로 이미 존재 —
  playtest.py 가 둘 다 안 보내고 정상 동작 중임이 실증).

## 3. 안 비교

| 안 | 플로우 | 단계 | 비고 |
|---|---|---|---|
| A (최소) | 스탯 단계만 제거 | 5 | 지시의 문자적 최소. 특성 선택 마찰 잔존 |
| **B (권장)** | 스탯 제거 + 특성→배경 흡수 + 이름·초상·확인 통합 | **2** | 배경 → 마무리 |
| C (급진) | 배경 카드 클릭 = 즉시 시작 | 1 | 이름·초상 커스텀 접근성 상실. 기존 QUICK(이전 캐릭터 재사용)과 역할 중복 |

**B 채택 근거**: C 의 즉시성은 기존 퀵스타트 경로가 이미 제공한다. 신규 유저에게
이름/초상은 "선택하고 싶은 사람만 하는" 가벼운 커스텀으로 남기되 한 화면으로 접는
것이 애착 형성(초상·이름은 여정 아카이브·파티 표시에 쓰임)과 간략화의 균형점.

## 4. 상세 설계 (B안)

### 4.1 새 플로우

```
시나리오 선택(2팩 이상일 때만) → ① 배경 선택 → ② 마무리 → 시작
```

- **① 배경 선택** (기존 SELECT_PRESET 확장): 프리셋 카드 + 성별. 카드에 **시그니처
  특성 뱃지** 노출 (예: "전장의 기억" 칩 + 한 줄 효과). 스탯은 기존 레이더 차트
  유지(보기 전용) — 선택이 아니라 정보.
- **② 마무리** (NAME + PORTRAIT + CONFIRM 통합 신설 `CHARACTER_FINISH`):
  - 초상: 프리셋 기본 초상 즉시 표시 (arch/86 PRESET_PORTRAITS 정본) + "바꾸기"
    버튼으로 업로드/AI 생성 접근 (접힘, 고급 옵션)
  - 이름: 단일 입력, placeholder 자동명, 빈 값 허용 (기존 건너뛰기와 동일 의미)
  - 요약 칩(배경·특성·시작 골드/아이템) + [여정 시작]
- 폐지 phase: `CHARACTER_STATS`, `CHARACTER_TRAIT`. 통합: `CHARACTER_NAME`
  + `CHARACTER_PORTRAIT` + `CHARACTER_CONFIRM` → `CHARACTER_FINISH`.

### 4.2 스탯 +6 흡수 (콘텐츠)

각 프리셋 `stats` 에 컨셉 방향의 +6 을 **상수 반영** (엔진 0줄, presets.json 수정만).
파워 총량이 현행 "기본 + 유저배분 6" 과 동일해 밸런스 중립. 예 (graymar):

| 프리셋 | +6 배분(안) |
|---|---|
| DOCKWORKER | str+2 con+2 per+1 cha+1 |
| DESERTER | str+2 dex+2 wit+1 con+1 |
| SMUGGLER | dex+2 per+2 wit+1 cha+1 |
| HERBALIST | wit+2 per+2 dex+1 con+1 |
| FALLEN_NOBLE | cha+2 wit+2 per+1 dex+1 |
| GLADIATOR | str+2 dex+2 con+2 |

4팩 전체(graymar·silverdeen·star_sand·karnholt) 동일 적용. 세부 수치는 소유자 확정.

### 4.3 특성 흡수 — defaultTraitId (콘텐츠 + 서버 소폭)

- `presets.json` 프리셋별 `defaultTraitId` 신설. graymar 는 6:6 1:1 매핑이 자연스러움:

| 프리셋 | 시그니처 특성(안) | 근거 |
|---|---|---|
| DOCKWORKER | BLOOD_OATH | 저HP 탱커 컨셉 정합 (불변식 32 보너스) |
| DESERTER | BATTLE_MEMORY | 전장 출신 |
| SMUGGLER | STREET_SENSE | 뒷골목 감각 |
| HERBALIST | NIGHT_CHILD | 야간 채집·밤 보정 |
| FALLEN_NOBLE | SILVER_TONGUE | 언변 |
| GLADIATOR | GAMBLER_LUCK | 검투장 도박판 정서 |

- **서버**: `createRun` 에서 `traitId` 미지정 시 `preset.defaultTraitId` 자동 적용.
  → 클라 구버전·playtest.py·파티 로비 경로 전부 특성을 받게 됨 (현재는 무특성).
  content.types `PresetDefinition.defaultTraitId?: string` + 팩 로드 시 존재 검증
  + creation-bundle 서빙 포함 (arch/71 §4.2).
- traitEffects 런타임(불변식 32)·traits.json 은 무변경. 특성 없는 팩(silverdeen)은
  defaultTraitId 미정의 = 현행 무특성 그대로.

### 4.4 서버 계약

- `bonusStats`: **deprecated** (전송 시 기존 합계 6 검증은 유지 — 구클라 호환).
  신클라는 전송 안 함.
- `traitId`: 유지 (전송 시 우선). 미전송 시 defaultTraitId 폴백 — 위 4.3.
- **불변식 31 개정**: "보너스 스탯 합계 = 6" → "bonusStats 는 deprecated optional.
  전송 시에만 합계 6 검증. 신규 생성의 스탯 개성은 프리셋 stats 에 내장."

### 4.5 파티 로비 연계 (백로그 해소 경로)

신규 유저 파티 시작 불가(로비 프리셋 선택 UI 부재, 2026-08-01 백로그)는 본 설계
이후 "로비에서 배경 카드 1택 + 성별" 미니 시트로 해소 가능해진다 — 6단계 생성
플로우를 로비에 이식할 필요가 사라짐. 본 설계의 후속 작업으로 권장.

## 5. 영향 범위·비변경

- **무변경**: 캠페인 이월(carriedIdentity — 2번째 시나리오부터는 생성 자체를 안 함),
  QUICK 퀵스타트, 초상화 업로드/생성/크롭 모듈(마무리 화면에서 재사용), 레이더 차트
  (보기 전용 전환), 여정 아카이브.
- **클라 제거 대상**: CHARACTER_STATS·CHARACTER_TRAIT 화면, bonusStats 상태·검증
  로직, BONUS_POINTS_TOTAL. StartScreen 이 큰 파일(1900줄+)이라 단계 통합 시
  start-screen/ 하위 분리 병행 권장.
- **문서**: CLAUDE.md 불변식 31 개정, arch/71 creation-bundle 필드 추가 반영.
- **밸런스 게이트**: 흡수 후 프리셋별 스탯 합이 현행 (기본+6) 과 동일한지 스크립트
  검증 1회 (4팩 × 6프리셋).

## 6. 확정 사항 (2026-08-04 소유자 결정)

1. **+6 배분·특성 매핑 = 에이전트 판단 위임** — 효과-스탯-서사 정합 기준으로 확정
   (§4.2 graymar 표 + 아래 §6.1 타 팩 표). 4팩 22프리셋 전수 반영.
2. **"특성 바꾸기" 옵션 완전 제거** — 마무리 화면에 특성은 표시 전용.
3. **파티 로비 미니 생성 시트는 분리** — 본 작업 범위 외, 후속 백로그.

### 6.1 확정 매핑 — star_sand·karnholt (효과 기준)

| star_sand 프리셋 | 특성 | +6 배분 |
|---|---|---|
| SS_DOCKHAND 흰숨 짐꾼 | SS_ICE_HARDENED (FIGHT+1·HP+15) | str+2 con+2 per+1 cha+1 |
| SS_PILGRIM 고래길 순례자 | SS_PILGRIM_FAITH (HELP+1·HP+10) | cha+2 wit+2 con+2 |
| SS_SMUGGLER 폐광 밀항자 | SS_SALT_TONGUE (PERSUADE/THREATEN+1) | dex+2 per+2 cha+2 |
| SS_HEALER 심장액 치유사 | SS_STAR_MARKED (OBSERVE+1·HP+10) | wit+2 con+2 per+2 |
| SS_OBSERVER 파문된 관측생 | SS_LANTERN_EYE (INVESTIGATE/SNEAK+1) | wit+2 per+2 dex+2 |
| SS_SURVIVOR 돌아온 실종자 | SS_DREAM_TOUCHED (OBSERVE/INVESTIGATE+1·HP+5 — "실종자의 꿈" 서사 당사자) | per+2 con+2 wit+2 |

| karnholt 프리셋 | 특성 | +6 배분 |
|---|---|---|
| KH_MINER 은광 광부 | KH_TUNNEL_SENSE (SEARCH/INVESTIGATE+1) | str+2 con+2 per+2 |
| KH_RUNNER 국경 밀매꾼 | KH_BORDER_FOOT (SNEAK/STEAL+1) | dex+2 per+2 cha+2 |
| KH_CLERK 파면된 서기 | KH_LEDGER_MIND (PERSUADE/INVESTIGATE+1) | wit+2 per+2 cha+2 |
| KH_SELLSWORD 떠돌이 용병 | KH_FURNACE_GRIT (FIGHT/THREATEN+1·HP+10) | str+2 dex+2 con+2 |

karnholt 잔여 특성 KH_COIN_EYE·KH_MINERS_BOND 는 미배정 보존 (향후 프리셋 추가분).
graymar 확정 매핑은 §4.3 표 그대로 (GLADIATOR=GAMBLER_LUCK, HERBALIST=NIGHT_CHILD 포함),
silverdeen 은 graymar 와 동일 프리셋 세트라 동일 적용.

## 7. 구현 기록 (2026-08-04)

- **콘텐츠**: 4팩 presets.json — stats +6 흡수 + defaultTraitId (22프리셋).
- **서버**: PresetDefinition.defaultTraitId 타입 + createRun traitId 폴백
  (carriedIdentity > options.traitId > preset.defaultTraitId) + creation-bundle
  defaultTraitId 서빙. 빌드·유닛 68/68.
- **클라**: ScreenPhase 5→1 (CHARACTER_FINISH 통합 — 초상·이름·요약·시작),
  bonusStats/selectedTraitId 상태·전송 제거, 배경 카드 특성 뱃지, 폴백 프리셋
  (data/presets.ts) 스탯·defaultTraitId 서버 정본 동기화. StartScreen -437줄.
- **CLAUDE.md**: 불변식 31 개정 (bonusStats deprecated).
