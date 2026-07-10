# 멀티 시나리오 지원 — 콘텐츠 디커플링 (2·3·4·5)

> 작성 2026-07-10. 상태: **구현 완료** (부록 A 참조).
> 배경: 현재 게임은 graymar_v1 단일 시나리오. 두 번째 시나리오를 추가하려면
> "graymar가 코드가 아는 유일한 세계"라는 가정을 제거해야 한다.

## 0. 범위와 보류

2026-07-10 조사에서 선행작업 7개를 식별했고, 이 문서는 그중 **②③④⑤를 설계·구현**한다.

| # | 항목 | 이번 범위 |
|---|------|-----------|
| ① | ContentLoader 싱글톤 → 멀티 팩 스코프 | ✅ 구현 — **팩 캐시 + ALS 스코프** (부록 D). 단일 활성 시나리오 정책 폐지 |
| ② | 엔진 코드 콘텐츠 ID 하드코딩 외부화 | ✅ 구현 |
| ③ | RunPlanner DAG 그래프 콘텐츠화 | ✅ 구현 |
| ④ | 시스템 프롬프트 세계관 분리 | ✅ 구현 |
| ⑤ | 신규 시나리오 팩 제작 + 최소 플레이 경로 | ✅ 구현 (미니 팩) |
| ⑥ | 클라이언트 동적화 (이미지 매핑·시나리오 선택 UI) | ✅ 구현 — **시나리오 선택 UI 방식** (부록 C) |
| ⑦ | 검증 인프라 시나리오 인자화 | ❌ 보류 (⑤ 검증은 curl/직접 API로 수행) |

### 단일 활성 시나리오 정책 (① 보류의 귀결)

`ContentLoaderService`는 싱글톤이고 `loadScenario()`는 전역 콘텐츠를 통째로 교체한다.
①이 완료되기 전까지는 **서버 프로세스당 하나의 시나리오만 활성**이다:

- 서로 다른 시나리오의 런을 동시에 플레이하면 LLM Worker가 턴마다 콘텐츠를 교체하며
  상호 오염된다 (launchd 이중 워커 사건과 동일 계열). **운영 환경에서 신규 시나리오
  런 생성은 개발·검증 목적에 한정**한다.
- 완화 가드: 턴 제출 시 `run.scenarioId !== content.currentScenarioId`면
  `loadScenario(run.scenarioId)`를 먼저 수행 (재시작 후 이어하기 대응).
  단, 이 가드는 "순차 전환"만 보장하며 동시 혼합은 여전히 금지.

## 1. 이미 존재하는 배선 (재확인)

- `content/<packId>/` 팩 단위 디렉토리 + `scenario.json` (carryOverRules 포함)
- `ContentLoaderService.loadScenario(scenarioId)` — contentDir 교체 + 전체 리로드
- `run_sessions.scenario_id`·`campaign_id` 컬럼, campaigns 모듈 (CarryOver)
- 클라 api-client에 scenarioId/campaignId 파라미터 (UI 미노출)
- 콘텐츠 파일 필수/선택: **필수 5** (enemies, encounters, items, player_defaults,
  presets — catch 없음), 나머지는 `.catch` fallback으로 **선택**

## 2. ② 하드코딩 외부화 — 전수 목록

`grep "'LOC_|'NPC_|'EVT_"` 96건 중 enum·접두사 검사 오탐을 제외한 **실제 콘텐츠 결합**:

| 위치 | 내용 | 이전 방식 |
|------|------|-----------|
| `turn-orchestration.service.ts:48-59` | NPC 11명 활동장소 맵 | npcs.json `activityLocations` **명시 필드** — 정합성 검증 결과 schedule 파생과 9/11 불일치 (맵은 스케줄과 별개의 의도적 큐레이션이라 파생 불가 확정) |
| `memory-collector.service.ts:48-70+` | LLM 출력 별칭/토픽→NPC ID 정규화 맵 22건 | npcs.json `entityAliases: string[]` 필드 신설, ContentLoader `resolveEntityAlias()` 파생 |
| `turns.service.ts:416-419` | `go_market`→LOC 맵 | 기계적 파생 규칙: `go_` + locationId에서 `LOC_` 제거 후 소문자. ContentLoader `getHubChoiceLocationMap()` |
| `turns.service.ts:6088-6162` | 이동 의도 장소 키워드 매처 (7장소 × 키워드) | locations.json `moveKeywords: string[]` 필드 신설 |
| `turns.service.ts:788,5193` / `:4930` | fallback `LOC_MARKET` / `LOC_HARBOR` | scenario.json `hub.defaultLocationId` |
| `turns.service.ts:654` | 프롤로그 화자 NPC_RONEN 고정 | scenario.json `prologue: { npcId, displayName, imageUrl }` |
| `turns.service.ts:814,1050` | "잠긴 닻 선술집으로 …" 복귀 서술 | scenario.json `hub.name` 기반 생성 |
| `scene-shell.service.ts:594-612` | HUB 기본 이동 선택지 4개 | locations.json `hubAccessible: true` 필드 + 파생 |
| `npc-agenda.service.ts:158` | fallback `LOC_TAVERN` | scenario.json `hub.locationId` |
| `llm-worker.service.ts:453,975,1115,3052` | go_hub 라벨 "'잠긴 닻' 선술집으로 돌아간다" ×4 | scenario.json `hub.returnLabel` (단일 소스) |
| `context-builder.service.ts:2026+,2144+` | LOC→표시명 맵 ×2 | locations.json `name` 파생 (`getLocationDisplayName()`) |
| `intent-system-prompt.ts:181` | LOC→라벨 목록 (MOVE_LOCATION 감지) | locations.json 파생 동적 생성 |
| `party/vote.service.ts:301,332` `party.controller.ts:448` | LOC↔go_ 맵, LOC→표시명 | 위 파생 API 재사용 |
| `situation-generator.service.ts:310` `consequence-processor.service.ts:151` | `locationId.replace('LOC_','')` 표시명 흉내 | `getLocationDisplayName()` |

**오탐 (외부화 대상 아님)**: `NPC_DETAIL`/`NPC_DIALOGUE`/`NPC_BEHAVIOR`/`NPC_FACT`/
`NPC_ACTION`/`NPC_POSTURE_CHANGE`/`PLOT_HINT` (enum 리터럴), `startsWith('NPC_')`
류 접두사 검사, `'NPC_ID'` 센티널. 접두사 규약(`NPC_`/`LOC_`/`EVT_`)은 **팩 공통
계약**으로 유지한다 (신규 팩도 이 접두사를 따른다).

## 3. ③ DAG 그래프 콘텐츠화

- `run-planner.service.ts getGraymarGraph()` 26노드 → `content/<pack>/graph.json`
- 스키마: `PlannedNodeV2[]` 그대로 (nodeId, nodeType, nodeMeta, environmentTags,
  edges[{targetNodeId, condition, priority}])
- ContentLoader `getGraph()` 신설 (선택 파일 — 없으면 빈 배열, dag 모드 런 생성 시 검증 에러)
- **검증: 외부화 전후 graymar 그래프 JSON byte-equal** (기존 사이클 검사 유지)
- 참고: DAG는 `mode: 'dag'` 런 전용. 기본 hub 모드는 그래프를 사용하지 않으므로
  런타임 영향 낮음.

## 4. ④ 시스템 프롬프트 세계관 분리

scenario.json 확장 (graymar_v1 값 = 현행 하드코딩 그대로):

```jsonc
{
  "world": {
    "settingLine": "중세 판타지 왕국",
    "regionSummary": "그레이마르 7개 지역 자유 탐험. 선술집이 거점. Heat(경계도) 변동. 시간대별 분위기 차이."
  },
  "hub": {
    "locationId": "LOC_TAVERN",
    "name": "잠긴 닻 선술집",
    "returnLabel": "'잠긴 닻' 선술집으로 돌아간다",
    "defaultLocationId": "LOC_MARKET"
  },
  "prologue": { "npcId": "NPC_RONEN", "displayName": "로넨", "imageUrl": "/npc-portraits/ronen.webp" }
}
```

- `system-prompts.ts`의 `NARRATIVE_SYSTEM_PROMPT`/`PARTY_NARRATIVE_SYSTEM_PROMPT`
  상수 → **빌더 함수**로 전환 (`buildNarrativeSystemPrompt(world)`), 호출부에서
  ContentLoader의 scenario meta 주입. 프롬프트 문면은 graymar 기준 **문자 동일** 유지
  (LLM 회귀 방지 — 캐싱 키도 시나리오당 안정).
- 주입 지점: system-prompts 3곳 + intent-system-prompt 장소 목록 동적화.

### 정합성 검증 반영 (2026-07-10)

- 기존 `ScenarioMetaContent` 타입(content.types.ts)에 `world`/`hub`/`prologue`
  **optional 필드 확장** — 기존 팩 로드 호환.
- graymar 하드코딩 값의 **fallback은 ContentLoader accessor 단일 지점**에만 둔다
  (scenario.json 필드 누락 시 안전). 엔진 서비스 파일에는 리터럴 금지 유지.
- **questState 시작 상태는 `S0_ARRIVE` 명명 규약** — turns.service 기본값이
  `S0_ARRIVE` 리터럴이므로 팩 계약으로 명문화 (quest.json stateTransitions의
  시작 상태명 고정). silverdeen quest.json도 동일 규약.

## 5. ⑤ 신규 시나리오 팩 — silverdeen_v1 (미니 팩)

은광 산악 마을 "실버딘". 붕괴 사고로 위장된 은광 갱도 매몰 사건의 진상 추적.
**목표는 콘텐츠 완성도가 아니라 "팩 계약 검증"** — graymar 대비 축소 규모:

| 항목 | graymar_v1 | silverdeen_v1 |
|------|-----------|---------------|
| 장소 | 7 | 5 (갱도/광장/대장간/예배당 + 허브 "잿빛 램프" 여관) |
| NPC | 43 (CORE 6/SUB 12/BG 25) | 12 (CORE 2/SUB 4/BG 6) |
| 퀘스트 | 6단계 3루트 | 6단계 3루트 (S0~S5, 정본 ArcRoute enum 3종) |
| 사건 | 13 | 3 |
| 이벤트 | 123 | ~12 + fact 이벤트 |
| 아이템/장비/적 | 고유 | **graymar에서 ID 재사용** (클라 에셋 재활용 — ⑥ 보류와 정합) |

- 필수 5 파일 + locations/npcs/scenario/quest/facts/incidents/events_v2 포함.
  graph.json은 hub 전용 팩이라 **의도적 생략** (dag 모드 미지원 — 선택 파일 fallback 검증 겸함).
  sets/equipment_drops/text_replacements도 생략해 catch fallback을 검증
- 장소 ID 규약: `LOC_SD_*` (접두사 계약 준수). **이미지 에셋 없음** — 클라
  location-images는 미매핑 시 fallback, NPC 초상화는 실루엣 (⑥에서 해결)

### 최소 플레이 경로

- `POST /v1/runs`의 `options.scenarioId`를 캠페인 없이도 허용 →
  `loadScenario(scenarioId)` + `run_sessions.scenario_id` 기록
- 턴 제출 시 시나리오 일치 가드 (§0) — 재시작 후 이어하기 대응
- 검증: 신규 팩으로 런 생성 → HUB 진입 → 장소 이동 → 대화/조사 수 턴 → LLM 서술 확인

## 6. 검증 계획

1. **graymar 회귀 (외부화 정확성)**: 외부화 전 현행 하드코딩 값을 스냅샷 →
   외부화 후 파생 API 결과와 **완전 일치** 단위 테스트 (그래프 byte-equal 포함)
2. 빌드 + 전체 테스트 (기존 실패 2건 외 신규 0)
3. graymar 라이브 스모크: 기존 런 이어하기 + 신규 런 수 턴
4. silverdeen 스모크: §5 최소 플레이 경로
5. 커밋·푸시 + 서버 재시작 한 세트 (워크플로우 규칙)

## 7. 불변식 영향 (CLAUDE.md)

- **불변식 22** "locationDynamicStates(7개 장소)" → **팩의 locations 수**로 상대화
- **불변식 23** "CORE(6)/BACKGROUND(25)/SUB(12)" → 계층 구조는 팩 공통, 수치는 graymar 고유
- 신규 불변식 후보: **"콘텐츠 ID는 팩 내부에서만 유효하며 엔진 코드는 ID 리터럴을
  가질 수 없다 (접두사 규약·enum 제외)"** — 구현 완료 후 CLAUDE.md 반영

## 8. 후속 (이 문서 범위 밖)

- ① ContentPack 멀티 캐시 + 조회 API 시나리오 스코프 (동시 혼합 허용의 전제)
- ⑥ 클라: 시나리오 선택 UI vs 캠페인 연속 — **사용자 결정 대기**. 이미지 경로 규약
  (`/locations/<packId>/…`) 포함
- ⑦ audit/playtest 스크립트 `--scenario` 인자화
- silverdeen 콘텐츠 밀도 보강 + 전용 에셋 (Gemini 파이프라인 재가동 — 과금 확인 필요)

---

## 부록 A — 구현 결과 (2026-07-10)

### 구현 완료 항목

- **②** 외부화 전수 완료 + 계획에 없던 발견분 추가:
  - 따옴표 없는 객체 키(`LOC_MARKET:`)가 초기 grep을 빠져나가 실제 범위는 **표시명 맵 11곳**
    (intent-v3-builder / memory-integration / npc-whereabouts / player-thread / memory-renderer /
    prompt-builder / context-builder ×4 / turns ×2) — 전부 `getLocationDisplayName`/`getLocationShortName` 파생.
  - `resolve.service` AMBUSH encounter 맵 → locations.json `ambushEncounterId`.
  - `world-state` 초기 locationStates → locations.json `hubState`.
  - **프롤로그 시스템 전체 외부화** (계획 초과분): runs.service의 분위기 4종 + 도입 스크립트,
    turns.service accept 지시문, L0 themeMemories, initialNpcRelations, quest 이벤트 텍스트
    → scenario.json `prologue`/`themeMemories`/`initialNpcRelations`.
  - **loadAll 병합 버그 수정**: Map을 clear 없이 재적재해 시나리오 전환 시 구 팩 항목이
    잔존하던 잠복 결함 — 왕복 전환 테스트로 잔존 0 확인.
- **③** getGraymarGraph() 26노드 → `graph.json` (dist 덤프로 byte-equal 보장).
  graphMap 캐시에 scenarioId 무효화 추가. 시작 노드 = 그래프 첫 노드 규약.
- **④** NARRATIVE/PARTY 시스템 프롬프트 → 빌더 함수. **graymar 값 대입 시 HEAD 상수와
  문자 단위 동일** 검증 통과. intent 프롬프트 장소 라벨 동적화.
- **⑤** silverdeen_v1 미니 팩 (장소 5 / NPC 12 / 퀘스트 6단계 / fact 8 / 사건 3 / 이벤트 12) +
  scenarioId 직접 지정 런 생성 + 턴 제출·LLM 워커 시나리오 일치 가드.

### 검증 결과

- 테스트 883 중 880 passed (실패 2 = 기존 stream-classifier, 신규 0). 스펙 픽스처 5파일에
  파생 API fake 보강.
- graymar 회귀: 신규 런 프롤로그 문면 동일, HUB 선택지 4곳 동일 (go_market …).
- silverdeen 라이브: 런 생성 → 프롤로그(도른) → accept → HUB 선택지 `go_sd_*` 4곳 파생 →
  광장 이동 → 카야 대화 턴에서 `questReveal`(FACT_SD_COLLAPSE_ODD, 주제 매칭) →
  **questState S0_ARRIVE→S1_GET_ANGLE 자동 전환** → LLM 서술 실버딘 세계관 (BANMAL 어체 준수,
  graymar 오염 0).
- 팩 계약에서 걸린 필수 필드 2건 수정: incidents `resolutionConditions.deadlineTicks` 계열,
  events `payload.tags` (없으면 런 생성/FREE 판정 크래시 — **팩 필수 필드**로 계약에 추가).

### 잔여 (후속)

- scene-shell `LOCATION_FOLLOW_UPS`/`DEFAULT_LOCATION_CHOICES` — graymar 장소별 flavor 풀.
  미등록 장소는 GENERIC_EXPLORE_CHOICES fallback으로 **동작 안전** 확인. 콘텐츠 밀도 이슈로 후속.
- world-state 초기 reputation 키(CITY_GUARD 등) + memory-integration FACTION_NAMES — factions.json
  로더 신설과 함께 후속.
- `db/types/npc-portraits.ts` 초상화 맵, event-content.provider(dag 전용 프롤로그 이벤트) — 후속.
- silverdeen 발견 이슈: BG/SUB unknownAlias가 길면 마커 별칭 중복 표기 발생
  ("팔뚝 굵은 광부 팔뚝 굵은 광부 조합장") — deduplicateAliases 후처리 보강 후보.
- ①(멀티 팩 로더) 및 ⑥(클라)은 §0 그대로 보류.

---

## 부록 B — 코드 리뷰 반영 (2026-07-10, /code-review Standards+Spec 2축)

### Standards hard 6건 수정

1. scene-shell go_hub 라벨/힌트 리터럴 2곳 → `ContentLoader.buildGoHubChoice()` 신설로
   **사내 6곳(scene-shell 2 + llm-worker 4) 단일 조립 지점화**.
2. runs.service `NPC_HARBOR_BOSS/NPC_SLUM_LEADER` 잔존 → scenario.json initialNpcRelations 병합.
3. runs.service accept_quest hint·party theme 리터럴 → `prologue.acceptChoiceHint` /
   themeMemories(location) 파생.
4. `?? 'graymar_v1'` fallback 2곳 중복 + 가드 블록 복붙 → `ContentLoader.ensureScenario()`
   단일화 (DEFAULT_SCENARIO_ID는 로더 상수).
5. `?? 'enc_generic'` → `getAmbushEncounterId()` (fallback 로더 단일 지점).
6. FACTION_NAMES → factions.json 로더 신설 + `getFactionDisplayName()` (shortName 필드로 문면 보존).

### 판단 콜 반영

- 사장 API `getLocationIdByHubChoiceId` 삭제 → `getHubChoiceLocation()`(hubAccessible 한정)로
  교체, turns.service가 사용.
- spec fake 3벌 복붙 → `llm/prompts/testing/fake-scenario-meta.ts` 공용화.
- korParticle 4벌 분산 → `common/korean.ts` 신설 (turns/scene-shell/system-prompts 수렴,
  ending-generator/summary-builder는 잔여).
- `'HUB'→'거점'` 특례 2곳 → `getLocationShortName()` 흡수.
- `getPrologueMeta()` 반환 타입을 `ScenarioPrologueMeta` 전체로 확장 — 호출부 `as unknown as`
  캐스트 3곳 제거. World/Hub/Prologue **named type** (`carry-over.ts`) 도입.

### Spec 발견 반영

- **moveKeywords 우선순위 역전 수정** — `moveKeywordsFallback` 필드 신설(범용 어휘는 전 장소
  전용 키워드 뒤 검사). "창고로 돌아가"→LOC_DOCKS_WAREHOUSE 구 동작 재현, 계약 테스트로 고정.
- **settingLine 조사 하드코딩** → `korParticle(settingLine, '을', '를')` (graymar 문면 동일 유지,
  '그레이마르' 류 값도 안전).
- **계약 회귀 테스트 신설** — `content-loader.scenario.spec.ts` 13건: 그래프 26노드,
  HUB 선택지 id/순서, go_hub 문면, 이동 키워드 우선순위(회귀 케이스 포함), AMBUSH 맵,
  entityAliases, 세력/장소 표기, silverdeen 규모·전환 격리·참조 무결성.
- silverdeen BG NPC 6명 `name: null` → 이름 부여 (NpcDefinition.name: string 계약).
- 문서 정정: §3 26노드, §4 예시 값 실제 일치, §5 3루트·graph 의도적 생략 명시,
  선택 파일 3종(sets/equipment_drops/text_replacements) 제거로 fallback 검증 충족.

### 잔여 (기록)

- system-prompts '로넨' 예시 4곳(대사 형식 예시) — 팩 고유 NPC지만 형식 교보재 성격, 후속.
- intent-parser-v2 장소 키워드(diff 밖), ending-generator/summary-builder korParticle 사본,
  vote LOC_TEMPLE 유령 라벨(콘텐츠에 없는 장소 — 파생 fallback으로 id 표시).
- [장소 기억] '그레이마르 시장'→'시장 거리' 등 표기 통일은 의도적 변경으로 확정.
- getAffinityEntries 등 매 호출 재생성 — 규모상 영향 미미, 필요 시 scenarioId 키 캐시.

---

## 부록 C — ⑥ 클라이언트 구현 (2026-07-10, 시나리오 선택 UI 방식)

### 서버

- `GET /v1/scenarios` 신설 (`content/scenarios.controller.ts`) — 캠페인 없이 팩 목록 조회.
- createRun/getRun 응답 `run.scenarioId` 포함 — 클라 시나리오 인지의 소스.
- `ScenarioPrologueMeta.imageUrl` optional화 — 초상화 없는 팩은 무명 실루엣 규약
  (`speakingNpc.imageUrl: undefined`)을 따른다. silverdeen의 존재하지 않는
  `unknown_silhouette.webp` 참조 제거 (마커도 `@[도른]` URL 생략형 — 클라 파서 지원 확인).

### 클라이언트

- **여정 선택 화면** (`StartScreen` `SELECT_SCENARIO`): "새 게임" 진입 시
  `GET /v1/scenarios` 조회 — 팩이 2개 이상일 때만 선택 화면 노출 (1개면 기존 흐름).
  새 캐릭터 생성·이전 캐릭터 퀵스타트 양 경로 모두 게이트 통과. 선택값은
  `createRun body.scenarioId`로 전달 (E2E로 body 캡처 검증).
- **store.scenarioId** — 런 로드 3경로(신규/이어하기/캠페인)에서 응답 `run.scenarioId` 저장.
- **HUB 라벨 시나리오 인지** — GameClient/HubScreen의 "그레이마르 거점" 하드코딩 →
  `SCENARIO_UI_LABELS` (presets.ts, 클라 표기 단일 지점).
- **프리셋 표기 어댑터** — `adaptPresetsForScenario()`: 실버딘 선택 시 프리셋
  subtitle/description의 세계 종속 표현 치환 (서버 silverdeen presets.json 생성 규칙과 동일).
  SELECT_PRESET 렌더 + characterInfo 빌더(사이드패널 subtitle) 적용.
- **location-images 팩 인지 구조** — locationId 접두(`LOC_SD_*`)로 팩 판별.
  이미지 없는 팩은 `null` 반환 → LocationImage 그라디언트 degradation +
  result-mapper 필드 생략 (**graymar 전경 fallback 오염 차단**). 에셋 경로 규약
  `/locations/<packId>/…` 명문화.

### 검증 (Playwright E2E)

가입 → 새 게임 → **여정 선택 화면(2개 카드)** → 실버딘 선택 → 캐릭터 생성 6단계 완주 →
`POST /v1/runs` body에 `"scenarioId":"silverdeen_v1"` 캡처 → 인게임 진입:
헤더 "실버딘 거점" + 프리셋 "광산의 주먹" + 실버딘 프롤로그 (그레이마르 오염 0).

### 잔여

- 클라 `PRESETS` 데이터 자체의 서버 fetch 전환 (현재는 치환 어댑터) — 팩별 고유 프리셋
  구조가 생기면 필수.
- silverdeen 전용 이미지 에셋 (장소·NPC 초상화) — Gemini 파이프라인 재가동 필요 (과금 확인).
- ⚠️ **단일 활성 시나리오 정책 여전** — 선택 UI 공개로 서로 다른 팩의 런이 동시에 생길 수
  있는 환경이 됐다. ensureScenario 가드가 순차 전환은 보장하나 동시 혼합 시 loadScenario
  스래싱 발생 — **① 멀티 팩 로더가 사실상 다음 필수 작업**.

---

## 부록 D — ① 멀티 팩 로더 구현 (2026-07-10)

**단일 활성 시나리오 정책 폐지** — 서로 다른 시나리오의 런을 동시에 플레이해도
상호 오염이 없다.

### 구조

- **ContentPackState + 팩 캐시**: 로더의 전역 상태 필드 31개를 팩 컨테이너로 추출,
  `Map<scenarioId, ContentPackState>` 상주 캐시 (`ensurePack` lazy 로드 1회).
  `loadAll`의 전역 교체·clear 개념 소멸. 기존 accessor 63개는 **private getter 위임**
  (`private get npcs() { return this.pack().npcs; }`)으로 무수정 보존.
- **AsyncLocalStorage 스코프** (`scenario-context.ts`): 어느 팩을 볼지는 비동기
  실행 컨텍스트가 결정. 병렬 경로(HTTP 동시 요청, LLM 워커 5턴 병렬) 격리.
- **호출 규약** — ALS enterWith의 함정(async callee 내부 설정은 await 경계에서
  복원되어 caller에 전파 안 됨)을 테스트로 실증하고 확보/설정을 분리:
  `await content.ensureScenario(id)` (팩 확보) + `content.enterScenario(id)`
  (caller 동기 컨텍스트 설정). 진입점 4곳: turns.submitTurn / llm-worker processTurn /
  runs.createRun / runs.getRun.
- **하위호환**: `loadScenario()`는 "컨텍스트 없는 경로의 기본 팩 전환"(fallbackScenarioId)
  의미로 유지 — 기존 테스트·스크립트 무수정. `pack()` 해석: ALS → fallback → 기본 팩
  폴백(경고) → 부팅 중(로더 init 전)엔 빈 팩(구 구조의 빈 필드와 등가 — ContentValidator
  onModuleInit 순서 크래시 실측 후 보정).

### 검증

- 격리 계약 스펙 4건 (`content-loader.multipack.spec.ts`): 중첩 컨텍스트 격리,
  비동기 인터리브 격리(**ALS 함정 재현 테스트가 설계 결함을 사전에 잡음**),
  팩 상주(스래싱 제거), loadScenario 하위호환.
- 실런 인터리브: graymar·silverdeen 런 동시 생성 → 수락/이동/ACTION **동시 제출** —
  각자 자기 세계(로넨/go_market/시장 ↔ 도른/go_sd_*/광장), LLM 병렬 서술 교차 오염 0,
  `[Pack] loaded` 각 1회 (구 구조의 턴당 Scenario loaded 왕복 소멸).
- 전체 테스트 923 passed (기존 실패 2건 외 신규 0).

### 잔여

- ContentValidator onModuleInit이 로더 init 순서에 따라 빈 팩을 검증할 수 있음 —
  구 구조와 동일 동작이나, 검증을 ensurePack 직후로 옮기는 개선 후보.
- 팩 캐시 무효화(콘텐츠 파일 변경 시 리로드)는 없음 — 콘텐츠 수정 후엔 재시작 (기존 동일).
