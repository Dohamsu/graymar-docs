# 71. 캠페인 자유 시나리오 선택 (첫 시나리오 자유 · 클리어 개방 · 이력 이월)

> 상태: ✅ 구현됨 (2026-07-14) — P1~P4 구현 + 단위 8케이스 + 라이브 API 검증 (§9). 열린 결정: 1=A(재진입 불가), 2=A(소모품 골드 환산) 확정
> 관련: [[70_campaign_progression]] (순차 진행 — 본 문서가 게이팅 정책을 대체), [[63_multi_scenario_content_decoupling]] (멀티 팩 로더 — 본 설계의 기반), [[39_ending_journey_archive]] (SummaryBuilder — 서사 이월에 재사용)

## 1. 목표 (사용자 의도)

1. **처음부터 어느 시나리오든 선택**해 그 시나리오 기준으로 캐릭터를 생성할 수 있다.
2. 선택한 시나리오를 **클리어하면 다른 시나리오가 개방**된다 (자유 순서).
3. 다음 시나리오는 **이전 시나리오의 이력(서사)과 아이템을 가진 같은 캐릭터**로 이어한다.

arch/70의 "graymar → silverdeen → star_sand 고정 순서" 모델에서 **"첫 시나리오 자유 + 이후 자유"** 모델로 전환한다. `order`는 진행 강제가 아닌 **표시 순서/추천 순서**로 의미가 격하된다.

## 2. 현재 상태 대비 간극 (실측)

arch/70 델타 2까지 구현되어 "원점(graymar) 먼저 → 이후 자유 선택"이다. 캐리오버 엔진(수치·정체성 머지, 재진입 차단, 활성 런 가드)은 재사용 가능하고, 간극은 5개다.

### G1. 첫 시나리오가 원점(graymar)으로 고정 — 게이팅 정책
- `campaigns.service.ts getScenarioProgress()`: 원점(최소 order) 미완료면 **원점만 CURRENT, 나머지 LOCKED**.
- `runs.service.ts createRun` 0-a 블록: LOCKED 시나리오 진입 시 400 ("먼저 원점 시나리오를 완료하세요").
- → **미완료 전부 진입 가능**으로 정책 변경. LOCKED 상태 자체가 소멸한다.

### G2. 클라이언트 프리셋이 graymar 하드코딩 — 팩별 프리셋 미서빙 (최대 공사)
- `client/src/data/presets.ts`: `PRESETS` = graymar 6종 고정. silverdeen은 **regex 텍스트 치환**(`adaptPresetsForScenario`)으로 흉내 — arch/63 부록 B에 "근본 해법(서버 팩 프리셋 fetch)은 후속"으로 이미 기록된 부채.
- star_sand는 **고유 프리셋 6종**(`SS_DOCKHAND`~`SS_SURVIVOR`)이라 치환으로 커버 불가. 클라가 이 프리셋들을 아예 모른다.
- 특성(traits.json)도 동일 — 팩별 파일이 있으나 클라는 graymar 것만 안다.
- → **서버가 팩 프리셋·특성을 서빙**하는 API 신설이 필수 (§4.2).

### G3. 캠페인 캐릭터 생성이 축약판 — identity 이월이 사실상 빈 값
- 캠페인 경로(`CAMPAIGN_PRESET` 화면)는 **프리셋+성별만** 선택. 솔로 경로의 6단계(프리셋→성별→이름→특성→보너스 스탯→초상화)를 안 탄다.
- `startCampaignRun(campaignId, scenarioId, presetId?, gender?)` — characterName/traitId/bonusStats/portraitUrl **미전송**. 서버 `createRun`은 이미 전부 받는데 클라가 안 보낸다.
- 결과: 완주 시 확정되는 `carryOver.identity`의 characterName/traitId/portraitUrl이 **null로 확정** — "같은 사람이 이어간다"는 arch/70 §3.3 의도가 캠페인 경로에서 미달성.
- → 캠페인 첫 시나리오 캐릭터 생성을 **솔로 6단계 플로우와 통일** (§4.3).

### G4. 아이템 이월의 실질 공백 — 장비 인스턴스 미이월 + 크로스팩 ID 해석 불가
- `CarryOverState.items` = `Array<{itemId, qty}>` **소지품만** 이월. `permanentStats.equipped`(착용 장비)·`equipmentBag`(장비 인스턴스, affix/세트/Legendary 포함)은 **이월 대상에서 누락** — 완주하면 장비가 증발한다.
- itemId는 **활성 팩 items.json 기준으로 해석**됨. graymar 아이템 ID를 들고 star_sand에 진입하면 메타(이름/타입/효과) 조회 실패 — 표시·사용 불가.
- → 장비 인스턴스 이월 + 크로스팩 아이템 정책 필요 (§4.4).

### G5. "이력" 이월 미배선 — 서사가 전달되지 않음
- `ScenarioResult.narrativeSummary`·`closingLine`·`keyDecisions` = 항상 빈 값. `CarryOverState.campaignSummary`도 빈 문자열 유지.
- 다음 시나리오 LLM 컨텍스트에 **전작 여정이 한 줄도 주입되지 않는다**. npcCarryOver·reputation은 팩 로컬 ID라 크로스팩에서는 의미 없음 (재진입 불가 정책상 같은 팩을 다시 안 가므로 사실상 사장).
- → 완주 시 요약 생성 + 다음 팩 테마 메모리 주입 (§4.5). 사용자가 말한 "이력을 가지고 이어하기"의 체감 핵심.

### 부수 간극
- `campaigns.currentScenarioOrder` 컬럼: 자유 순서에서 "다음 order" 의미 상실 → **완주 수+1** 의미로 재정의(표시용)하거나 deprecated.
- `carryOverRules.statBonusPerScenario`: scenario.json에 정의되어 있으나 **적용 배선 확인 필요** — `mergeCarryOver`는 `prev.statBonuses`를 그대로 통과시키기만 하고 증분 코드가 안 보인다 (구현 시 검증 항목).
- `SCENARIO_UI_LABELS`(클라): graymar/silverdeen만 정의 — star_sand 누락. 팩이 늘 때마다 클라 수정이 필요한 구조라 서버 전달(scenario.json `hub.name` 재사용)로 전환.

## 3. 진행 모델 (기획 정본)

```
Campaign (userId 1:1 활성)
  ├─ carryOverState.completedScenarios: 완주 집합 (순서 무관)
  ├─ carryOverState.identity: 첫 완주 시 확정, 이후 불변 (arch/70 §3.3 유지)
  └─ 진입 가능 = 전체 − 완주 − (활성 런 존재 시 그 시나리오만)
```

### 3.1 시나리오 상태 (LOCKED 소멸)
| 상태 | 조건 | UI |
|------|------|-----|
| `AVAILABLE` | 미완주 (활성 런 없음) | 선택 가능 |
| `IN_PROGRESS` | 이 시나리오의 RUN_ACTIVE 런 존재 | "이어하기"로만 진입 |
| `COMPLETED` | completedScenarios에 존재 | 잠금 (재진입 불가) |

- **첫 캐릭터 생성**: `completedScenarios가 비어 있고 활성 런이 없을 때` — 어느 시나리오를 고르든 **그 팩의 프리셋·특성으로 6단계 생성**. (arch/70의 "원점에서 중립 프리셋 생성" 정책 폐기)
- **완주 후**: 미완주 전부 AVAILABLE. 프리셋·성별·이름 미전송 → carryOver 수치+identity 이월 (현행 유지).
- **되돌아가기 불가 유지**: 완주 시나리오 재진입 차단 (회차 플레이 욕구는 **새 캠페인**으로 해소 — 캠페인은 "한 캐릭터의 일대기" 단위).
- **동시 1개 유지**: 캠페인당 활성 런 1개 (현행 가드 유지). RUN_ABORTED 시맨틱(미완주·재도전, 첫 시나리오면 캐릭터 재생성 허용)도 arch/70 §3.3 그대로.

### 3.2 완주·실패 시맨틱 — arch/70 §3.3 그대로 유지
RUN_ENDED(성패 무관) = 완주 → 머지·개방. RUN_ABORTED = 미완주 → 같은 시나리오 재도전. 변경 없음.

### 3.3 밸런스 원칙 — "모든 팩은 1번째로도 N번째로도 플레이 가능"
- 각 팩의 프리셋 기본 스탯·적·판정은 **신규 캐릭터 기준**으로 유지 (이미 팩별 presets.json이 그렇게 설계됨).
- 이월 캐릭터의 우위는 판정식 `1d6 + floor(stat/4)` 특성상 완만 (스탯 +4당 +1). 골드·장비 우위는 목적지 팩의 `carryOverRules`(goldRate/reputationDecay — 이미 존재)로 감쇠 가능.
- `statBonusPerScenario`는 "완주한 시나리오 **수**에 비례"로 의미 정립 (order 무관). 적용 배선 확인 후 필요 시 수선.
- 별도 난이도 스케일링(적 스탯 보정 등)은 **도입하지 않는다** — 플레이테스트 계측 후 필요하면 후속.

## 4. 변경 명세

### 4.1 서버 — 게이팅 개방 (소규모)
| 파일 | 변경 |
|------|------|
| `campaigns.service.ts getScenarioProgress` | 원점 분기 제거. `completed → COMPLETED`, 활성 런의 시나리오 → `IN_PROGRESS`, 나머지 전부 `AVAILABLE`. `ScenarioStatus` 타입 교체 (`CURRENT`/`LOCKED` → `AVAILABLE`/`IN_PROGRESS`). |
| `campaigns.service.ts resolveNextScenarioId` | "첫 AVAILABLE" 유지하되, 자유 선택에선 **명시 scenarioId 필수**로 승격 검토 (자동 선택은 order 최소 미완주로 폴백). |
| `runs.service.ts` 0-a 블록 | LOCKED 거부 분기 제거. COMPLETED 거부는 유지. IN_PROGRESS(활성 런 가드)는 기존 가드가 커버. |
| `campaigns.service.ts saveScenarioResult` | `currentScenarioOrder + 1` → `completedScenarios.length + 1` (표시용 재정의). |

### 4.2 서버 — 팩 캐릭터 생성 번들 서빙 (신규 API)
```
GET /v1/scenarios/:scenarioId/creation-bundle
→ { presets: presets.json, traits: traits.json, uiLabels: { hubName, fallbackLocation } }
```
- ContentLoader의 팩 캐시(`ensureScenario`) 재사용 — 활성 시나리오 교체 없이 읽기만.
- 이미지 경로(프리셋 초상화)는 기존 컨벤션(클라 public) 유지하되 presetId 기반 경로 규약으로.
- **불변식 45 정합**: 이 API가 생기면 클라의 `PRESETS` 하드코딩·`adaptPresetsForScenario` regex 치환·`SCENARIO_UI_LABELS`를 전부 제거할 수 있다 (arch/63 부록 B 부채 청산).

### 4.3 클라이언트 — 캠페인 캐릭터 생성 6단계 통일 (핵심 공사)
| 항목 | 변경 |
|------|------|
| `CAMPAIGN_PRESET` 화면 | **폐기**. 시나리오 선택(첫 플레이) 후 솔로 6단계 생성 플로우(SELECT_PRESET→…→초상화)로 합류. 완료 시 campaignId+scenarioId를 함께 전송. |
| 프리셋·특성 데이터 | `creation-bundle` fetch 기반으로 전환. `client/src/data/presets.ts`의 PRESETS는 로딩 폴백/타입 정의로만 축소. |
| `startCampaignRun` | 시그니처 확장: `characterName`, `traitId`, `bonusStats`, `portraitUrl` 전달 (서버 createRun은 이미 수용). |
| `CAMPAIGN_SCENARIO` 화면 | order 뱃지 → 상태 뱃지(완료 ✓ / 진행 중 / 선택 가능). "완주 N / 전체 M" 진행도 표시. 이월 진입 시 "○○(이름)으로 이어서 시작" 확인 문구 (identity 노출). |
| 이어하기 | IN_PROGRESS 시나리오 카드 → 기존 이어하기 경로 연결. |

### 4.4 아이템·장비 이월 실질화
| 대상 | 정책 |
|------|------|
| **장비 인스턴스** (`equipped` + `equipmentBag`) | **그대로 이월** — `CarryOverState`에 `equipment: { equipped, bag }` 필드 추가. ItemInstance는 스탯·affix가 자체 완결(self-contained)이므로 크로스팩에서도 동작 (구현 시 렌더·세트효과 조회가 팩 items.json에 의존하지 않는지 검증 — 의존하면 인스턴스에 표시 메타 스냅샷 내장). |
| **소모품 (일반)** | 팩 로컬 ID라 크로스팩 해석 불가 → **매각가 골드 환산**하여 이월 골드에 합산 (환산율 `quest-balance.config.ts` 외부화 — 불변식 30). |
| **KEY 아이템** | 시나리오 전용 서사 물품 — **이월 제외** (완주 시 소멸, 여정 아카이브에 기록만). |
| **골드** | 현행 유지 (`goldRate`). |

이월 시점(`mergeCarryOver`)에 위 분류를 수행 — 진입 시점이 아니라 **완주 시점에 정산**해 carryOver를 자체 완결 상태로 만든다.

### 4.5 서사 이월 — "이력을 가지고 이어한다"의 체감 배선
| 단계 | 내용 |
|------|------|
| **완주 시 요약 생성** | `saveScenarioResult`에서 SummaryBuilder(여정 아카이브용 ending_summary — 이미 존재) 재사용해 `ScenarioResult.narrativeSummary`(2~3문장: 어디서 무엇을 겪고 어떤 결말을 맺었나 + 대표 NarrativeMark 1개) 채움. LLM 불필요 — 기존 템플릿 빌더로 충분. |
| **campaignSummary 누적** | 완주 요약을 시간순 연결, 상한 ~400자 (오래된 것부터 1문장으로 압축). |
| **다음 팩 LLM 주입** | ① scenario.json `themeMemories`의 `{PROTAGONIST_THEME}` 결합부에 전작 이력 1문장 삽입 (L0 테마 — 불변식 5 대상이므로 경량 유지). ② ContextBuilder에 `[과거 여정]` 블록 신설 — campaignSummary를 토큰 예산 저우선 블록으로 주입 (선별 주입 원칙 — 불변식 24). |
| **프롤로그 훅** | 이월 캐릭터는 프리셋 `prologueHook`(팩 로컬) 대신 **campaignSummary 기반 훅** — "{전작 지역}에서의 일을 마치고 흘러들어온" 톤. scenario.json prologue의 `{HOOK}` 치환 지점 재사용. |
| **크로스팩 인물 참조 금지** | 전작 NPC 실명은 요약에 포함하되, LLM에게 "회고로만 언급 가능, 현재 장면 등장 불가" 디렉티브 (Procedural Plot Protection과 동류의 가드). |

### 4.6 콘텐츠
- scenario.json: `order`는 표시 순서로 유지, `prerequisites`는 전 팩 빈 배열 그대로 (죽은 필드 — 제거해도 무방).
- 변경 필수 없음. 단, star_sand `carryOverRules`가 "3번째 진입" 전제로 튜닝됐다면 자유 순서 기준으로 재점검 (goldRate 1.0·reputationDecay 0.5는 순서 무관으로 무해).

## 5. API 계약 변경 요약
| 엔드포인트 | 변경 |
|------|------|
| `GET /v1/campaigns/:id/scenarios` | `status: COMPLETED\|IN_PROGRESS\|AVAILABLE` (LOCKED 소멸 — 값 교체는 클라 동시 배포 전제, 과도기엔 CURRENT를 AVAILABLE 별칭으로 허용) |
| `GET /v1/scenarios/:scenarioId/creation-bundle` (신규) | 팩 프리셋·특성·UI 라벨 서빙 |
| `POST /v1/runs` | 계약 변경 없음 — 캠페인 첫 시나리오에서 identity 필드를 클라가 **보내기 시작**할 뿐 (이미 수용됨) |

## 6. 불변식 영향
- **불변식 45 (콘텐츠 ID 리터럴 금지)**: 클라 PRESETS 하드코딩·regex 치환 제거로 오히려 강화.
- **단일 활성 시나리오 정책**: 유지 — 자유 선택이어도 동시 플레이는 없음. 멀티 팩 로더(arch/63 ①)가 creation-bundle의 팩 캐시 읽기를 지원.
- **불변식 5 (L0 테마 불변)**: 전작 이력 주입은 L0 결합 1문장 + 저우선 블록으로 한정 — L0 비대화 금지.
- **arch/70 §3.3 (완주·실패 시맨틱)·identity 불변·활성 런 가드**: 전부 유지. 본 설계는 arch/70의 **게이팅(§3.1~3.2)만 대체**한다.

## 7. 작업 단계 (Phase)

| Phase | 내용 | 규모 | 가치 |
|-------|------|------|------|
| **P1 게이팅 개방** | 서버 원점 분기 제거 + 상태 enum 교체 + 클라 뱃지 (§4.1, §4.3 일부) | 소 | 완주 후 자유 선택 즉시 체감 |
| **P2 캐릭터 생성 통일** | creation-bundle API + 캠페인 6단계 합류 + identity 전송 (§4.2~4.3) | **대** | 첫 시나리오 자유 선택의 전제 · identity 이월 정상화 |
| **P3 아이템·장비 이월** | equipment 이월 + 소모품 골드 환산 + KEY 제외 (§4.4) | 중 | "아이템을 가지고 이어한다" 실질화 |
| **P4 서사 이월** | narrativeSummary 빌드 + campaignSummary 누적 + LLM 주입 + 프롤로그 훅 (§4.5) | 중 | "이력을 가지고 이어한다" 체감 |
| **P5 검증·밸런스** | E2E: star_sand 첫 시작(여성·SS_PILGRIM) → 완주 → graymar 이월(identity·장비·이력 확인). 되돌아가기 400. 플레이테스트 10~15턴 × 신규/이월 각 1회 | 소 | — |

P1은 독립 배포 가능. P2가 크리티컬 패스 (P3·P4는 P2와 병렬 가능).

## 8. 열린 결정 (확정 — 2026-07-14)
1. **완주 시나리오 재진입** — **A안 확정: 불가**. 회차 플레이는 새 캠페인. (허용하면 carryOver 이중 머지·중복 사례금 파밍 등 경제 루프 붕괴 지점이 많다.)
2. **소모품 이월** — **A안 확정: 골드 환산** (`CARRY_CONSUMABLE_GOLD_RATE`, quest-balance.config).
3. **statBonusPerScenario 적용 배선** — 실측 결과 **미배선이었음** (mergeCarryOver가 prev.statBonuses 통과만). 완주 1회당 적립으로 배선: MaxHP → `maxHpBonus` 경로(createRun carryMaxHp), ATK→str/DEF→con 매핑은 `STAT_BONUS_KEY_MAP`.

## 9. 구현 노트 (2026-07-14)

### 구현 중 발견·수정한 기존 버그 (설계 문서에 없던 것)
1. **이월 스탯이 기본값으로 리셋** — `mergeCarryOver`의 `extra.stats` 참조는 RunState에 없는 필드라 항상 undefined → `finalStats`가 영구히 `{}` → 이후 시나리오가 DEFAULT 스탯으로 시작. **playerProfiles.permanentStats 스냅샷**으로 수정.
2. **이월 런 runState에 identity 미기록** — carried 분기가 characterName/portraitUrl/traitId/traitEffects/actionBonuses를 누락 → 표시·프롬프트·판정에서 캐릭터 증발. 기록 추가.
3. **크로스팩 trait 이중 적용 위험** — 이월 런에서 traitId를 활성 팩 getTrait로 재해석하면, 같은 ID가 우연히 존재할 때 maxHpBonus가 이월 스탯에 이중 적용. **이월 런은 traitDef 미해석 + identity.traitEffects 스냅샷** 사용으로 차단.

### 설계 대비 구현 조정
- `[과거 여정]` ContextBuilder 블록 신설은 **불필요했음** — `campaign_history` L0 테마 주입 배선이 이미 존재(runs.service)했고 campaignSummary가 빈 문자열이라 죽어 있었을 뿐. campaignSummary를 채우는 것으로 활성화.
- 이월 런의 프롤로그 `{HOOK}`: 대체 문구 대신 **{HOOK} 라인 통째 생략** (화자 어체 훼손·빈 따옴표 방지, 콘텐츠 무수정).
- 장비 스냅샷: `ItemInstance.carrySnapshot` (slot/rarity/statBonus 합산/narrativeTags) — `EquipmentService.equip/getGearModifiers/getNarrativeTags`에 미해석 폴백. 세트 보너스는 팩 경계 비이월(자연 소멸).
- identity에 `traitEffects`/`actionBonuses`/`protagonistTheme` 스냅샷 추가 (팩 로컬 ID 미해석 대비).
- 솔로 "새 게임"도 전 시나리오 선택 개방 (원점 한정 정책 폐기, enterScenarioGate). 빠른 시작은 이전 프리셋이 선택 팩에 없으면 생성 흐름으로 유도.

### 검증 (라이브 API — server eafab24+)
- `GET /v1/scenarios/star_sand_v1/creation-bundle`: SS_ 프리셋 6종 + SS_ 특성 6종 + 아이템 표시명 해석 ✓
- 새 캠페인 → 3팩 전부 `AVAILABLE` ✓ → **star_sand(order 3)를 첫 시나리오로 시작** (SS_PILGRIM·female·세라·SS_DREAM_TOUCHED·보너스 스탯) ✓
- runState: characterName 세라, traitEffects maxHpBonus 5(HP 105), actionBonuses 프리셋+특성 병합 ✓
- 활성 런 중 타 시나리오 진입 400 ✓ / star_sand `IN_PROGRESS` ✓ / abort → 전부 `AVAILABLE` 복귀 ✓ / graymar 재선택 생성 ✓
- 단위: campaigns.service.spec.ts 8케이스 (소모품 환산·스냅샷·연쇄 이월·요약 압축), 전체 스위트 1145 passed.
