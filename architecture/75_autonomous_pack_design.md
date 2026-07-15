# 75. 자율 서사 팩 상세설계 — "진상 선확정 디렉터 모드"

> 상태: 📐 상세설계 확정 (2026-07-15) — 미구현. [[74_autonomous_narrative_direction]]의 문답식 의사결정 14건을 확정해 구체화한 정본. **검토 반영 (2026-07-15): §11 실측 대조 리뷰 신설(getNpc 127곳 정정·stub 필드표면·시드 정합·규명 도달성), P0 범위 확장 + G2 2차 관문 신설.** **P0 스파이크 통과 (2026-07-15): 해석 심 + E2E 라이브 검증 완료 — §12.** **G2 프로토타입 조건부 통과 (2026-07-15): Plot Seed 정합·해결가능성 실증, 수렴은 다양성 제어로 해소 — §13.**
> 결정 방식: 소유자 문답 4라운드 (2026-07-15). 각 결정은 §1 표에 고정 — 재론 시 본 문서 갱신이 정본.
> 관련: [[74_autonomous_narrative_direction]] (스펙트럼·역설·인프라 진단), [[73_scenario_differentiation]] (B1 packMeters — 본 설계의 선행 의존), [[71_campaign_free_scenario_selection]] (재진입 정책 예외 지점), [[31_memory_system_v4]] (entity_facts — 동적 레지스트리 원형).

---

## 1. 확정 결정 (14건 — 정본)

| # | 축 | 결정 | 비고 |
|---|-----|------|------|
| 1 | 자율 수준 | **L3** — 메인 플롯도 매 런 생성 | 74 §6 최고 자율 레벨 |
| 2 | NPC 생성 범위 | **코어 외 전부** (SUB·BG 전원 런타임 생성) | 코어 NPC만 저작 |
| 3 | 장소 | **저작 유지** | 이미지·이동 그래프·LocationState 결합 회피 |
| 4 | 서브→메인 | **메인 분기까지 영향** | 불변식 18 모드 분기 필요 (§7) |
| 5 | 진상 확정 시점 | **런 시작 시 선확정** — 숨겨진 정본(Plot Seed) | 단서 모순·표류 방지의 축 |
| 6 | 종결 보장 | **3막 턴 예산 + 세계 게이지 임계 혼합** | 불변식 19(최소 15턴) 유지 |
| 7 | 코어 NPC 배역 | **매 런 캐스팅** + 저작 금지 배역 제약 | 회차 가치 극대화 |
| 8 | 모드 배치 | **신규 팩으로 시작** — 기존 팩 무변경 | A/B 비교 가능 |
| 9 | 팩 소재 | **그레이마르 세계 확장** (같은 왕국 다른 도시) | 로어·톤 재사용, 캠페인 이월 자연스러움 |
| 10 | 모티프 앵커 | **저작 모티프 풀(8~12) 조합** — 완전 자유 생성 배제 | 74 §3 역설(제네릭 수렴) 방어 |
| 11 | 디렉터 타이밍 | **비동기 선계산** — 다음 비트 후보를 백그라운드 생성 | 레이턴시 10초 미만 제약 준수 |
| 12 | 반복 플레이 | **자율 팩만 캠페인 재진입 허용** (새 진상 생성, 경제 보상 회차 감쇠) | arch/71 재진입 불가 정책의 명시적 예외 |
| 13 | 동적 NPC 영속 | **일부 주민화** — 관계 깊은 동적 NPC(trust 상위 1~2)는 런 간 재등장 | 세계 연속감 |
| 14 | 미규명 종결 | **규명율 반영 엔딩** — 실패도 "미제 사건"류 유효한 결말로 서술 | 배드엔딩 강제 없음 |

## 2. 팩 계약 — AUTONOMOUS 모드

scenario.json에 `narrativeMode: "AUTONOMOUS"` 신설 (기본값 `"AUTHORED"` — 기존 팩 무변경).

AUTONOMOUS 팩의 저작물 (이것만 손으로 쓴다):

| 저작물 | 내용 | 비고 |
|--------|------|------|
| 세계관 | world.settingLine/regionSummary + **감각 팔레트**(73 A4) | 기존 계약 재사용 |
| 장소 7~8개 | locations/scene_shells/이미지 — 기존과 동일 | 생성물의 "무대" |
| 코어 NPC ~6명 | npcs.json CORE tier만. **신규 필드 `castingConstraints`**: `{ forbiddenRoles: [], preferredRoles: [], fixedTraits: "불변 성격 요소" }` | 배역은 매 런 캐스팅, 인격은 불변 |
| **motifs.json (신규)** | 사건 모티프 8~12개: `{ motifId, name, summary, requiredLocationTags?, taboo? }` + 팩 금기 소재 | 진상 생성의 조합 재료 |
| meters (73 B1) | 세계 게이지 1개 이상 — **선행 의존**: 73 B1 packMeters 구현 필수 | 종결 임계의 절반 |
| endingTones | 규명율×게이지 매트릭스별 엔딩 톤 가이드 (서술은 생성) | quest.json·endings.json 아크 그리드 대체 |

**AUTONOMOUS 팩에 없는 것**: quest.json(S0~S5), events_v2 대량 저작(폴백 소량만), SUB/BG npcs, arc_events, facts.json — 전부 런타임 생성으로 대체.

## 3. Plot Seed — 진상 정본 (결정 5)

런 생성 시 1회 생성(시작 로딩 구간 — 런 생성 레이턴시 +수 초 허용), 서버 검증 후 `runState.plotSeed`에 **숨겨진 정본**으로 동결.

```jsonc
runState.plotSeed = {
  "motifs": ["MOTIF_SMUGGLING", "MOTIF_FALSE_IDENTITY"],   // 팩 풀에서 2~3개 조합
  "truth": {                                                // 숨겨진 정답 — 런 중 불변
    "what": "…이 …을 은폐했다",
    "culpritNpcId": "NPC_CORE_X | NPC_DYN_1",              // 코어 캐스팅 or 동적 stub
    "why": "동기 1문장", "whereLocationId": "LOC_…"          // 장소는 저작 ID 검증
  },
  "casting": { "NPC_CORE_A": "CLIENT", "NPC_CORE_B": "RED_HERRING", … },
  "keyFacts": [                                             // 8~12개 — 규명율의 분모
    { "factId": "FACT_DYN_1", "summary": "…", "holders": ["NPC_DYN_2"], "revealHint": "…" }
  ],
  "endingCandidates": [ { "id": "E1", "premise": "…" }, … ],// 3~4개 — 서브 결과가 가중 변경
  "acts": [ { "no": 1, "turnBudget": 8, "goal": "사건 인지" },
            { "no": 2, "turnBudget": 12, "goal": "심층 규명" },
            { "no": 3, "turnBudget": 8, "goal": "대결/해소" } ]
}
```

서버 검증(생성 직후, 위반 시 재롤 — 최대 N회 후 폴백 시드):
- casting이 코어 `castingConstraints.forbiddenRoles` 위반 금지 (결정 7).
- 장소 ID 실재, keyFacts 수 규약(8~12), 동적 인물은 §4 stub 스키마 통과.
- **진상 불변 규약**: plotSeed.truth는 런 중 수정 금지 (신규 불변식 후보 — §7).

## 4. Dynamic NPC Registry (결정 2·13)

### 4.1 stub 스키마 + 검증 (P0 필드 표면 조사로 확정 — 2026-07-15)

**필드 표면 전수 조사 결과** (getNpc/getAllNpcs 소비 22파일 대조): NpcDefinition 24필드를 3계층 분류.

| 계층 | 필드 | stub 처리 |
|------|------|-----------|
| **T1 MUST supply** (~11) | npcId·name·unknownAlias·shortAlias·**aliases[]**·role·**gender**·basePosture·tier·personality.{speechRegister,speechStyle/core} | stub이 공급 |
| **T2 옵셔널·graceful** | schedule·longTermAgenda(undefined=미구동)·knownFacts(lorebook `if(!x)`, 런타임은 npcState 축적)·agenda·daily_topics·roleKeywords·entityAliases·activityLocations·faction·title·initialTrust·nameStyle | 안전 기본값 |
| **T3 죽은 필드** | **combatProfile**(전투 적은 enemies.json 별도 map), **linkedIncidents**(읽는 곳 0) | undefined (무시) |

→ **핵심: §11-A 리스크가 예상보다 작다.** 우려했던 rich 필드(전투·사건·스케줄)는 죽었거나(combat/incident) graceful degrade(schedule/knownFacts). stub은 초안 8필드에 **`gender`·`aliases`만 추가**하면 됨(gender는 앞서 고친 neutral 대명사 버그 방지).

확정 stub (nano 생성, 서버 등록: `NPC_DYN_<seq>` id 부여 후 `runState.dynamicNpcs[]` 영속):

```jsonc
{ "npcId": "NPC_DYN_3", "name": "일사 크레번", "tier": "SUB",
  "unknownAlias": "낡은 외투의 여인",        // 5~10자 규약 (arch/68 부록 I)
  "shortAlias": "외투 여인",
  "aliases": ["일사 크레번", "외투 여인"],    // 마커 해석용(resolveNpcId) — 최소 [name]
  "gender": "female",                        // 대명사·초상화 (neutral 버그 방지)
  "basePosture": "CAUTIOUS",                 // 5종 enum 강제
  "speechRegister": "HAEYO",                 // 5종 enum 강제 — 어체 검증/fallback 재사용
  "role": "밀수 중개인", "oneLinePersonality": "…" }
```

**seam 확장 규약** — `getNpc(id)` 폴백 시 stub → NpcDefinition 형태로 확장: T1은 stub, T2는 안전 기본값(schedule=undefined, faction=null, title=null, initialTrust=0, nameStyle='soft'…), T3은 undefined. 이 확장으로 127 호출 지점이 전부 well-formed NpcDefinition을 받음.

검증 실패 → 재시도 1회 → 실패 시 그 턴은 무명 인물로 서술(기존 실루엣 규약). 초상화는 실루엣 폴백 고정(생성은 과금 이슈로 후순위 — 74 §7-5).

### 4.2 해석 심(seam) — P0 스파이크의 본질
74 검토에서 확정된 사실: NPC 소비는 `getNpc()` 직접 호출 **19파일 127곳**(실측 재확인)이라 "NpcResolver 풀 확장만"으로는 안 된다. **(a) ContentLoader 통합안**을 정본 후보로 스파이크 검증:
- scenario-context(ALS)를 `{ scenarioId, dynamicNpcs? }`로 확장. 진입점 4곳(turns/worker/runs/party)에서 runState.dynamicNpcs를 컨텍스트에 적재.
- `getNpc(id)`: 콘텐츠 팩 → 컨텍스트 동적 레지스트리 순 폴백. `getAllNpcs()`: 합집합.
- 트레이드오프 수용: content 서비스가 런 스코프 데이터를 보게 됨(층위 침범) — 단일 심 1곳에 국한.
- **워커 경로 규약**: dynamicNpcs는 runState JSONB 소속 → LLM 워커의 fresh 부분 패치 규약(arch/60 lost-update) 준수. 등록은 턴 동기 경로에서만, 워커는 읽기 전용.

### 4.3 주민화 (결정 13)
런 종료 시 trust 상위 1~2명의 동적 NPC를 `campaigns.carryOverState.packResidents[packId][]`로 승격 저장 (스탯 아닌 인물 스냅샷: stub + 관계 요약 1문장). 재진입 런 생성 시 Plot Seed 캐스팅 풀에 코어와 함께 후보로 제공 — 디렉터가 재등장·재배역 가능. 비캠페인 솔로 런은 주민화 없음(1단계 스코프 아웃).

## 5. Emergent Director (결정 1·4·11)

### 5.1 비동기 선계산 파이프
NanoEventDirector 비동기 분리 패턴 재사용:
```
턴 N 처리(동기, 판정·상태는 기존 엔진 그대로)
  → 워커: 서술 생성 + [PlotDirector] 다음 비트 후보 2~3개 선계산
      입력: plotSeed(미공개 keyFacts·acts 진행) + 코어/동적 NPC 상태 + PlayerThread + WorldFact + 게이지
      출력: beatCandidates[] { premise, involvedNpcIds, hintedFactId?, choiceSeeds[], subThreadSeed? }
  → runState.nextBeatCandidates 저장
턴 N+1: 플레이어 행동과 정합한 후보 채택 → 기존 이벤트 파이프(EventDirector 자리)로 주입
        정합 없음 → 후보 폐기, 기존 폴백 체인(SituationGenerator→기본 이벤트)으로 그 턴 진행
```
- **불변식 2 보존**: 디렉터 실패/미도착 턴도 기존 폴백으로 게임 진행. 체감 레이턴시 추가 ≈ 0.
- **인력(gravity)**: 미공개 keyFacts 중 현재 장소·등장 NPC와 연관된 것을 우선 비트화 — questFactTrigger/weight 부스트 패턴 재사용. 막 예산 잔여가 적을수록 인력 가중 상승(표류 방지 — 74 §7-2의 튜닝 손잡이).

### 5.2 서브 스토리 → 메인 분기 (결정 4)
서브 비트의 결과는 ① 게이지/평판/골드(자원), ② 캐스팅 관계 변화(예: RED_HERRING의 혐의 해소), ③ **endingCandidates 가중 변경** 또는 keyFact 추가 공개로 메인에 개입한다. 단 **truth 자체는 불변** — 서브가 바꾸는 것은 "어느 결말로 가는가"와 "얼마나 빨리 규명되는가"이지 정답이 아니다.

## 6. 종결 — 3막 + 게이지 + 규명율 (결정 6·14)

- **막 전환**: acts.turnBudget 소진 시 디렉터에 막 전환 디렉티브(2막: 압박 사건, 3막: 대결 무대 강제). 총합 상한 ~35턴, 최소 15턴(불변식 19) 미만 종결 금지.
- **게이지 임계**: packMeter(73 B1) 임계 도달 시 잔여 예산 무관 클라이맥스 진입 — "세계가 기다려주지 않는다".
- **엔딩 산출**: `규명율 = 발견 keyFacts / 전체 keyFacts` × 게이지 상태 → endingTones 매트릭스에서 톤 선택 → 엔딩 서술 생성. 미규명(규명율 낮음)도 "미제로 남다/떠나다"류 유효 결말(결정 14). 여정 아카이브(ending_summary)에 규명율·진상 요약 기록 — 재진입 회차에서 "지난 사건" 회고 재료(71 서사 이월과 접속).
- **재진입 경제**: 사례금·보상은 회차마다 감쇠(파밍 방지 — 결정 12). 감쇠율은 quest-balance.config 외부화.

## 7. 불변식 영향 (구현 전 확정 필요)

| 불변식 | 영향 | 처리 |
|--------|------|------|
| 1·2 (서버 정본·LLM 서술 전용) | **유지** — 생성은 전부 "제안→서버 검증·등록" | 본 설계의 대전제 |
| 18 (Procedural Plot Protection) | AUTONOMOUS 모드에서 **정반대** (서브가 메인 개입) | `narrativeMode` 분기 — AUTHORED 팩은 기존 규칙 유지 |
| 19 (NATURAL 최소 15턴) | 유지 | acts 예산 설계에 반영 |
| 26·15 등 NPC 계열 | 동적 NPC에 동일 적용 | stub enum 강제 + 해석 심으로 기존 방어선 재사용 |
| **신규 후보 A** | "진상 정본 불변" — plotSeed.truth 런 중 수정 금지 | CLAUDE.md 등재 예정 |
| **신규 후보 B** | "미등록 엔티티 서술 금지" — 마커·카드에 등록 NPC만 | 마커 새니타이즈에 동적 풀 포함 |
| **신규 후보 C** | "디렉터 무응답 턴도 진행 보장" — 폴백 체인 필수 | §5.1 |

**감사·테스트 도구 대응** (74 검토 반영): audit V8/NPA/playtest의 NPC 정본 참조에 dynamicNpcs 소스 추가. 회귀는 골든 대조 대신 **분포 지표 + 불변식 위반 감지**(73 §8 + 규명율 분포·종결 턴 분포·표류 감지 = 같은 비트 3회 반복 등).

## 8. 구현 단계 (의존 순서)

| Phase | 내용 | 성격 | 의존 |
|-------|------|------|------|
| **P0 스파이크** ✅ **통과** | 동적 NPC 해석 심 — ALS 확장 + getNpc 폴백 + 워커 경로에서 마커·소개·반응 디렉터가 동적 NPC로 도는지. getNpc 127곳 읽기 필드 전수 조사 완료(3계층 §4.1). **결과 §12** — seam 단위 5/5 + 멀티턴 E2E(해석→반응→대화잠금→마커→HAEYO→자기소개) 통과 | 검증 완료 | — |
| **P1** | Dynamic NPC Registry 정식화 (stub 검증·등록 API·감사 도구 대응·실루엣 폴백) | 엔진 중 | P0 통과 |
| **P2** | 73 B1 packMeters (자율 팩 종결의 선행 의존) | 엔진 중 | — (병행 가능) |
| **P3** | Plot Seed 생성·검증·동결 + `narrativeMode` 팩 계약 | 엔진 중 | P1 |
| **P4** ✅ **구현 완료** | Emergent Director (비동기 선계산 + 폴백 체인 + 인력) — §15 구현 로그·E2E 실측 | 엔진 대 | P1·P3 |
| **G2 관문** | **2차 관문 (신설 §11-D)** — Plot Seed + 디렉터가 실제로 **정합·공정·해결가능한 미스터리**를 뽑는가(§11-B/C). 규명율 분포·표류·시드 정합 실측. 실패 시 **L2(디렉터 없이 저작/반저작 시드)로 후퇴** | 검증 | P3·P4 |
| **P5** | 종결 파이프 (3막 예산 + 게이지 임계 + 규명율 엔딩 + 아카이브) | 엔진 중 | **G2 통과** · P2 |
| **P6** | 신규 팩 콘텐츠 저작 — 그레이마르 세계 확장 도시 (장소 7~8·코어 6·motifs 10±·팔레트·endingTones) | 콘텐츠 | P3 계약 확정 후 병행 |
| **P7** | 주민화 + 재진입(캠페인 예외·보상 감쇠) | 엔진 소 | P5 |
| **P8** | 계측·플레이테스트 (분포 지표, 10~15턴 다회) | 검증 | 전체 |

**이중 관문 구조** (검토 반영): **P0**(해석 심 비용) 실패 → L1/L2로 후퇴. **G2**(생성 미스터리 정합·공정) 실패 → L2(저작/반저작 시드)로 후퇴하되 동적 NPC(P1)는 유지. P0만으론 부족한 이유는 §11-A/D — 진짜 미검증 가정(정합한 미스터리 생성)은 P3~P4에서야 드러나기 때문. 두 관문 다 통과해야 P5~P8(종결·콘텐츠·주민화) 대공사에 커밋한다.

> **P0 관문 상태 (2026-07-15): ✅ 통과** — §12 참조. "동적 NPC 인프라가 가능하다"까지 확정.
>
> **G2 관문 상태 (2026-07-15): ✅ 조건부 통과 (프로토타입)** — §13 참조. 엔진 밖 프로토타입으로 Plot Seed의 정합·해결가능성을 실증(독립 탐정이 keyFacts만으로 범인 재구성). 진짜 리스크는 §11-B의 "안 풀리는 미스터리"가 아니라 §74 역설(수렴)이었고, 설계 내장 다양성 제어(§7·§9.5)가 값싸게 해소함을 확인. **정식 G2(P3/P4 뒤 실런 다회 계측)로 재확인 전제.**

## 9. 리스크 대장 (74 §7 승계 + 확정 설계 반영)

1. **비용/레이턴시** — 선계산으로 체감 0이 목표지만 워커 부하 증가(비트 생성 + stub 생성 + 규명 추출). 유닛 이코노미 계측 필수.
2. **표류 vs 인력** — 막 잔여 예산 연동 인력 가중(§5.1)이 1차 손잡이. 튜닝은 P8 실측으로.
3. **선계산 적중률** — 플레이어가 매 턴 예측 밖 행동이면 선계산이 낭비. 적중률 계측 후 후보 수(2~3) 조정.
4. **주민화 저장 위치** — 캠페인 carryOverState 종속이라 비캠페인 솔로 반복에선 미작동. 1단계 스코프 아웃 명시.
5. **모티프 풀 고갈 체감** — 8~12 모티프 × 2~3 조합이라 이론 조합은 크지만, 동일 모티프 재등장 체감은 있음. 회차 시 직전 런 모티프 제외 규칙으로 완화.
6. **74 §3 역설 재검증** — 앵커(모티프·코어 캐스팅·팔레트)에도 불구하고 생성 서브 스토리가 제네릭으로 수렴하는지 n-gram 지표(73 §8)로 상시 계측.

## 10. 실버딘 폐기와의 관계 (2026-07-15 소유자 결정)

silverdeen_v1은 폐기 예정 — 팩 2개(그레이마르·별빛모래) + 본 자율 팩이 3번째가 된다. 폐기 시 멀티팩 격리 스펙 등 5개 스펙 파일의 픽스처를 star_sand로 이관해야 하며(74 검토 §4), 그 격리 인프라는 본 설계의 전제(팩별 narrativeMode 공존)이기도 하다.

## 11. 검토 반론·보강 (2026-07-15 — 실측 대조 리뷰)

기술 주장 실측 검증 결과: getNpc **19파일·127곳**(문서 116→127 정정), ALS scenario-context·불변식 18 문면·carryOverState 전부 실재 확인. 근거는 견고. 아래는 착수 전 보강 필요 지점.

### 11-A. 🔴 stub 스키마가 127개 호출 지점의 필드 표면을 못 덮는다 (P0 범위 확장으로 반영)
`getNpc` 폴백이 127곳에 걸리면 그 지점들은 §4.1 stub(~7필드)에 없는 필드를 읽는다: **knownFacts**(fact 공개 경로), **linkedIncidents**, **schedule/agenda**(Living World v2가 전 NPC 순회), **combatProfile**(동적 NPC 전투 진입), personality.signature/mannerism, faction. P0가 마커·소개·반응 3개만 검증하면 통과하지만 **P1+에서 fact-공개·전투·스케줄 경로가 터진다.** → P0 범위에 "127곳 읽기 필드 전수 조사 + 필드별 graceful-degradation 기본값 정의"를 추가(§8 P0 갱신). 동적 NPC의 전투/스케줄/fact-보유를 명시적으로 처리(예: combatProfile 없으면 비전투 인물로 강제, knownFacts는 plotSeed.keyFacts.holders로 대체).

### 11-B. 🟡 Plot Seed 검증이 "구조"만이고 "정합성"이 아니다 (G2 프로토타입으로 등급 하향 🔴→🟡 — §13)
§3 검증 항목이 전부 구조적(ID·개수·enum)이라 **"미스터리가 공정하게 풀리는가"를 검증 못 한다.** culprit/동기/keyFacts/endingCandidates의 서사 정합, 단서만으로 진상 도달 가능성은 구조 검사로 안 잡힌다. 구조상 유효하나 서사상 엉성한 시드 = 김빠지는 런. → (a) 시드 통짜 생성 후 **LLM 자기검증 패스**(공정성/해결가능성 채점) 추가, 또는 (b) 생성을 **"해결 형태가 알려진 템플릿 스켈레톤"**(모티프 조합별 정답 골격)으로 제약. "재롤 N회"는 정합성을 보장하지 않는다. G2 관문에서 실측.

### 11-C. 🟠 keyFact 도달가능성 미보장 → 규명율 불공정
`규명율 = 발견/전체`인데 keyFact 보유자가 끝내 안 만나는 동적 NPC면 그 fact는 **구조적 발견 불가** → 실력 무관 상한 <100. → 디렉터가 "막 예산 내 모든 keyFact에 최소 1개 표면화 경로 보장"(reachability)을 지도록 인력(§5.1)에 규약 추가. 미보장 시 규명율 지표 자체가 불공정. G2에서 keyFact 도달률 계측.

### 11-D. 🟠 L3-우선의 관문이 P0에만 있었다 → 이중 관문으로 보강 (§8 G2 신설)
P0 후퇴선은 **해석 심 비용**만 커버했으나, 진짜 미검증 가정은 **11-B/C(생성 미스터리의 정합·공정)**이고 이건 P3~P4에서야 드러난다. → P3/P4 뒤 **G2 관문** 신설: Plot Seed+디렉터가 플레이 가능한 미스터리를 뽑는지 검증, 실패 시 L2(저작/반저작 시드, 동적 NPC는 유지)로 후퇴. 두 관문 통과해야 P5~P8 대공사 커밋.

### 11-E. 🟡 기타
- **레이턴시 곱셈**: 턴당 워커가 서술+비트2~3+stub+규명추출. 선계산 적중 실패 턴의 동기 폴백이 **디렉터 없이** 도는지 명시 필요(§5.1 폴백 체인이 SituationGenerator→기본이벤트로 끝나야 함, 디렉터 재호출 금지).
- **"저작 최소"의 시점**: 회차당은 최소가 맞으나 P6(새 도시 전체 저작)+P1~P5 엔진 대공사가 선행 → **초기 비용은 큼.** "저작 최소"는 런타임 한정임을 명확히.
- **초기 목표가 L3**: 74는 L1 먼저를 권했다. 이중 관문·후퇴선으로 L3-우선의 리스크를 관리하나, 대안(L1→L2 점증)이 총비용상 더 쌀 가능성은 G2 전까지 열어둔다.

## 12. P0 스파이크 결과 — ✅ 통과 (2026-07-15)

브랜치 `spike/dynamic-npc-p0` @ `ba9026c` (미푸시, main 무반영). 실험 후 프로덕션 main 복구.

### 12.1 구현 (최소 침습)
| 파일 | 변경 |
|------|------|
| `content/scenario-context.ts` | `DynamicNpcStub` 타입(T1 필드) + scenarioId와 독립된 두 번째 ALS(`currentDynamicNpcs`/`runWithDynamicNpcs`) + spike env 훅(`spikeDynamicNpcs`, `SPIKE_DYN_NPC=1`) |
| `content/content-loader.service.ts` | `getNpc` 폴백(팩 miss→동적 레지스트리) + `getAllNpcs` 합집합 + `expandDynamicStub`(T1 공급/T2 안전기본값/T3 undefined, signature=[] 불변식41) + `applyDynamicNpcs` 래퍼 |
| `turns/turns.service.ts` · `llm/llm-worker.service.ts` | `enterScenario` 직후 `applyDynamicNpcs()` 배선 (진입점 2곳) |
| `content/content-loader.dynamic-npc.spec.ts` | seam 5케이스 |

→ **해석 심 단 1곳 + ALS.** 나머지 **127 getNpc 소비 지점과 모든 하위 시스템은 코드 무변경**으로 동작.

### 12.2 검증
- **단위**: dynamic-npc.spec 5/5 + content-loader 회귀 24/24 (getNpc 폴백·getAllNpcs 합집합·컨텍스트 격리·무회귀).
- **E2E 라이브** (`SPIKE_DYN_NPC=1`, 테스트 NPC "카렌 보그"/`NPC_DYN_SPIKE_1`, npcs.json 부재):
  - 단일 턴: 플레이어 "부두 여인" 지목 → `actionContext.targetNpcId=NPC_DYN_SPIKE_1`(해석) → NanoEventDirector·NpcReactionDirector가 실명으로 동작 → 마커 `@[낯선 부두 여인]`(unknownAlias) → 대사 HAEYO(`~예요/~에요`, speechRegister 반영) → 태도 CAUTIOUS·"그녀"(gender=female) 반영.
  - **멀티턴(5턴 대화)**: 대화잠금 연속성 유지 + **자기소개 발동** — "낯선 부두 여인이 …입을 연다 / '반가워요, 저는 **카렌 보그**라고 해요'"(불변식 15, 소개 턴 별칭 마커→실명 대사). 무크래시.

→ **동적 NPC가 저작 NPC와 구분 불가능하게 전 파이프라인(해석·이벤트디렉터·반응디렉터·대화잠금·마커·어체·자기소개) 통과.** §11-A 필드표면 리스크 실측 해소.

### 12.3 P1 이관 TODO (정식화 시)
- **spike env 훅 제거** → `runState.dynamicNpcs` 정식 배선(`applyDynamicNpcs(runState.dynamicNpcs)`). RunState 타입에 필드 추가 + 워커 fresh 부분 패치 규약(arch/60) 준수.
- stub **검증 게이트**(enum·별칭 길이·어체) + 등록 API + 실루엣 초상화 폴백.
- 감사 도구(V8/NPA/playtest)의 NPC 정본 참조에 dynamicNpcs 소스 추가.
- 소개 후 실명 마커 전환(IntroMarkerNorm, 불변식 15 후반)은 E2E에서 소개 턴까지 확인 — 다음 턴 실명 전환은 P1 회귀 스위트로 고정.

### 12.4 한계 (정직)
P0는 **"동적 NPC 인프라가 가능하다"까지만** 확정한다. 자율 트랙의 진짜 품질 리스크(생성 미스터리의 정합·공정 — §11-B/C)는 **G2**에 남아 있으며, 아래 §13에서 엔진 밖 프로토타입으로 선제 검증했다.

## 13. G2 프로토타입 결과 — ✅ 조건부 통과 (2026-07-15)

정식 G2(P3/P4 뒤)를 짓기 전에, "LLM이 앞뒤 맞고 공정하게 풀리는 Plot Seed를 실제로 뽑는가"를 **엔진 밖 프롬프트 실험**으로 싸게 선검증. 모델은 운영 메인(Gemma 4 26B), 앵커는 graymar 코어 6명·장소 7·모티프 풀 8개.

### 13.1 방법
- **생성**: 세계+NPC+장소+모티프 → Plot Seed(truth/casting/keyFacts 8~12/endingCandidates/acts) JSON 생성 프롬프트.
- **자기채점**(§11-B 옵션 a): LLM-judge가 coherence/solvability/fairness/distinctness 1~5 채점.
- **해결가능성 실측**(가장 약한 근거 보강): keyFacts summary만 준 **독립 LLM 탐정**이 범인을 재구성하는지 — LLM-judge 관대함을 우회한 객관 검증.
- 다양성: 제어 OFF(2R1) vs 제어 ON(직전 범인·모티프 제외 + 비진부 강제 = 설계 §7·§9.5 시뮬).

### 13.2 결과
| 축 | 결과 | 근거 |
|----|------|------|
| **정합성** | ✅ 강함 | 자기채점 coherence 5/5 (양 라운드) |
| **해결가능성** | ✅ **실증** | keyFacts만 준 독립 탐정이 범인 정확 재구성(HIGH 확신), red herring 배제(장부 권한+잉크 일치로 흑막 특정, 실행범과 구분) |
| **공정성** | ✅ 양호 | red herring 반증 단서 + holder 5명 분산 |
| **다양성** | ⚠️ **제어 필수** | 제어 OFF → 3/3 수렴(전부 에드릭·도박빚·창고, §74 역설 실증) / 제어 ON → 3/3 유니크(마이렐·로넨·밴스, distinctness 3→4↑) |

부수 발견: 생성이 fact holder로 `NPC_GUARD`·`NPC_TAVERN_OWNER` 등 **동적 NPC를 자연 생성** → P0(동적 NPC 등록)와 정확히 맞물림.

### 13.3 결론
1. **§11-B의 최대 공포("안 풀리는/앞뒤 안 맞는 미스터리")는 실측상 근거 약함** → 등급 🔴→🟡 하향. 이 모델·이 세계에선 공정·해결가능한 시드를 안정 생성.
2. **진짜 리스크는 §74 역설(수렴)** 이었고, **설계 내장 다양성 제어(§7 매 런 캐스팅·§9.5 직전 모티프 제외)가 값싼 프롬프트 제약만으로 수렴을 깨면서 정합성을 유지**함을 확인.
3. → **P0(인프라)+G2(품질) 두 관문 모두 긍정 신호.** 하이브리드 디렉터 모드의 실현 가능성이 실측으로 뒷받침됨.

### 13.4 한계 (정직)
- 표본 작음(생성 3+3+1), 단일 모델, **풍부한 저작 세계(graymar) 기반** — 얇은 세계 미검증.
- 다양성 제어의 **제외 셋이 회차 누적 시 코어 6명으론 고갈** → 동적 NPC를 범인 풀에 넣어 확장(생성이 이미 동적 holder 생성). 장기 튜닝 과제.
- solvability는 **1회 독립 추리 성공** → 정식 G2에서 다회 반복 계측 필수(규명율 분포·오답률).
- 이 프로토타입은 "런 시작 1회 시드 생성"만 검증. **런 중 디렉터의 점진 공개·인력(§5)이 시드를 실제로 플레이 가능하게 풀어내는지는 미검증**(P4+G2 본검증 몫).

## 14. 착수 판단 (2026-07-15 — 소유자 요청, 엔지니어 판단)

### 14.1 결론
> **"개발 착수 가능한가"에는 예 — 단 P1/P2 한정.** "전체 L3를 지금 몰빵해도 되는가"에는 **아직 아니오.** 두 관문(P0·G2)이 초록불이라 *기술적 방향*은 실측으로 뒷받침되나, *최대 미지수*는 여전히 미검증이다.

### 14.2 검증됨 vs 미검증 (현 시점)
| 항목 | 상태 | 근거 |
|------|------|------|
| 동적 NPC 인프라 | ✅ 견고 | P0 코드+E2E (§12) |
| Plot Seed 정합·해결가능성 | ✅ 프로토타입 실증 | G2 (§13) — 소표본·단일모델·풍부 세계 |
| 다양성(수렴 방어) | ✅ 제어로 해소 실증 | G2 R2 (§13.2) |
| **런타임 디렉터 루프 (§5)** | ❌ **미검증 · 최대 리스크** | 엔진 밖 프로토 불가 → P4가 곧 시험대 |
| keyFact 도달가능성 (§11-C) | ❌ 미검증 | P4+G2 |
| 레이턴시·유닛 이코노미 (§7.1) | ❌ 미검증 | 실런 계측(P8) |

**핵심**: "시드를 생성한다"는 검증됐으나 "플레이하며 그 시드를 공정하게 풀어낸다"는 통째로 미검증. 이건 엔진 밖에서 못 푼다 → 설계상 P4에 있고 P4 자체가 이 리스크의 시험대다.

### 14.3 리스크 등급별 착수 판단
- **P1(동적 NPC 정식화) — 지금 착수 가능.** 저리스크 + **자율 트랙이 멈춰도 재사용 가능**(NanoEventDirector·NPC Living Presence 등). 매몰 위험 낮음.
- **P2(packMeters, 73 B1) — 병행 가능.** 자율과 무관하게 **시나리오 차별화(73)에 독립적으로 유용** → 헛일 안 됨.
- **P3~P4 — 진짜 도박.** P4(디렉터, "엔진 대")는 최대 미검증 리스크. 진입 시 **"개발 속 스파이크" 취급 + L2 폴백 킬스위치 필수.**
- **P5~P8·P6(새 도시 저작) — 정식 G2(P4 뒤) 통과 확인 후.**

### 14.4 "할 수 있나(can)"보다 먼저 "지금 해야 하나(should)" (§11-D 승계)
기술 실현성은 대체로 정리됐다. 그러나 **진짜 결정은 제품 우선순위다**:
- 이 이니셔티브 전체가 **"팩이 비슷하다"는 관찰 하나**에 근거하며 **유저 수요 신호가 없다.**
- P1~P8+P6는 솔로 오너에게 **수 주~수 개월** 공사. 관문 초록불이 이 규모를 줄이지 않는다.
- **대안**: A2 마무리 → 실플레이어 노출 → "정말 비슷하다고 느끼는가" 신호부터 수집이 단위 노력당 학습이 더 클 수 있다.

### 14.5 권고 착수 순서
1. **A2 짧게 마무리** (또는 현 52개로 동결) — 현재 게임 즉시 개선, 저리스크. 자율 채택 시 폴백 풀로 생존.
2. **P1(동적 NPC 정식화) 착수** — 재사용 가능한 저리스크 인프라. spike 훅→runState.dynamicNpcs 정식 배선(§12.3 TODO).
3. **P2(packMeters) 병행** — 73 차별화와 공유.
4. **실플레이 신호 수집** — "비슷함"이 실제 유저 불만인지 확인. 없으면 P3+ 보류.
5. **신호 확인 시 P3→P4(킬스위치)** — 여기서 정식 G2. 통과해야 P5~P8·P6 대공사 커밋.

→ 요지: **저리스크·재사용 가능한 P1/P2는 진행하되, L3 대공사(P4+)는 "제품 신호 + P4 관문" 이중 확인 뒤.** 성공한 프로토타입의 관성으로 수개월 공사에 바로 진입하지 않는다.

## 15. P4 구현 로그 (2026-07-15 착수 — 소유자 지시)

> **세션 단절 대비 정본 기록.** 각 단계 완료 시 이 표와 하위 절을 갱신한다.
> 코드는 **server 레포 `feat/dynamic-npc-registry` 브랜치**(P0~P3 위에 적재), 문서는 root 레포.
> 착수 근거: §14의 "제품 신호 후 P4" 권고에도 불구하고 소유자가 P4 진행을 명시 지시 (2026-07-15).
> P4 완성 조건: **킬스위치 포함** + G2 정식 계측으로 넘길 수 있는 상태 (§14.3 "개발 속 스파이크" 취급).

### 15.1 단계 체크리스트

| 단계 | 내용 | 상태 | 커밋 |
|------|------|------|------|
| P4-1 | BeatCandidate 타입 + RunState(nextBeatCandidates·plotProgress) + 킬스위치 config | ✅ | server `4e96c04` |
| P4-2 | PlotDirectorService(비트 후보 2~3 nano 생성) + 인력 순수 함수 + 유닛 | ✅ | server `f5543f2` |
| P4-3 | 워커 배선 — AUTONOMOUS 런 서술 후 비트 선계산 → applyRunStatePatch 저장 | ✅ | server `27fc3e3` |
| P4-4 | 턴 동기 채택 — selectBeatForAdoption + eventDef 주입 + 후보 소비 + 폴백 보존 | ✅ | server `a690894` |
| P4-5 | keyFact 발견 추적(plotProgress.discoveredKeyFactIds) + 동적 Fact 해석 심 | ✅ | server `66ec9fa` |
| P4-6 | dev 픽스처(graymar 임시 AUTONOMOUS) + 라이브 E2E 멀티턴 검증 + 실측 버그 수정 | ✅ | server `e3bad52` |

**P4 전 단계 완료 (2026-07-16).** 전체 1240 passed (AUTHORED 무회귀). 브랜치 `feat/dynamic-npc-registry` (main 미병합, 미푸시).

### 15.2 설계 고정점 (구현 중 흔들리면 여기로 복귀)

- **비트 저장 필드는 워커 소유**: `runState.nextBeatCandidates`는 llm-worker의 `applyRunStatePatch`(arch/60 fresh CAS)로만 쓴다. `forTurnNo` 스탬프로 stale 후보 채택 차단.
- **채택은 턴 동기 경로 1곳**: turns.service WORLD_EVENT 분기, SituationGenerator보다 **앞**. 미정합 시 후보 폐기 후 기존 체인(SitGen→EventDirector→Procedural) 그대로 — **디렉터 동기 재호출 금지** (§11-E).
- **truth 불변**: 디렉터는 keyFacts 공개·endingCandidates 가중만 만진다. plotSeed.truth 수정 금지 (신규 불변식 A).
- **AUTHORED 무동작**: narrativeMode !== 'AUTONOMOUS'면 모든 P4 경로가 no-op. 기존 팩 회귀 0이 P4-6 통과 조건.
- **킬스위치**: config로 디렉터 off 시 AUTONOMOUS 팩도 폴백 체인만으로 진행 (불변식 C).
- **동적 인물 등록은 동기 경로만**: 비트가 제안한 신규 인물 stub은 채택 턴의 동기 경로에서 registerDynamicNpc (워커는 제안만).

### 15.3 단계별 기록

**P4-1 (`4e96c04`)** — BeatCandidate/NextBeats/PlotProgress 타입(plot-seed.ts) + RunState.nextBeatCandidates(워커 소유)·plotProgress(동기 경로 소유) + AUTONOMOUS_BALANCE(후보 수 3·stale 2턴·인력 가중 5종·채택 임계 30) + `isPlotDirectorEnabled()` 킬스위치(`PLOT_DIRECTOR_DISABLED=1`).

**P4-2 (`f5543f2`)** — `engine/hub/beat-gravity.ts` 순수 모듈: getActProgress(막을 turnNo에서 파생 — 별도 상태 없음)·scoreBeatCandidate(장소 하드 게이트 + 장소 30/행동 20/타겟 NPC 25(직전 NPC는 절반)/미발견 fact 20 + 막 압박 인력 최대 40은 fact 힌트 비트에만)·selectBeatForAdoption(age 1..2만 유효, 임계 미달 null). `llm/plot-director.service.ts`: nano로 비트 후보 2~3개 생성, 막 잔여 1/3 이하 시 "최소 2개 단서 표면화" 강제. parseBeatCandidates 후보 단위 정제(미지 NPC 필터·NPC_DYN_NEW+proposedNpc 짝·발견 fact 힌트 제거·locationId 현재 장소 고정). 유닛 24개.

**P4-3 (`27fc3e3`)** — llm-worker 4-e: LOCATION 턴 DONE 후 fire-and-forget `precomputeNextBeats()` (체감 레이턴시 0). 게이트: AUTONOMOUS+킬스위치+plotSeed+currentLocationId. 저장은 `applyRunStatePatch('nextBeats')` fresh CAS.

**P4-4 (`a690894`)** — determineTurnModeCore 3.6: `beatAvailable` → WORLD_EVENT 승격 (NPC 지목·대화 연속이 항상 우선 — Player-First 유닛 4케이스). WORLD_EVENT 분기 SitGen 앞에서 채택: eventDef 변환(OPPORTUNITY·sceneFrame=premise·discoverableFact=hintedFactId) + 후보 소비 + proposedNpc 동기 등록(registerDynamicNpc→applyDynamicNpcs 재적재). 미정합 시 후보 보존(stale까지 재기회)+계측. SitGen에 `!matchedEvent` 가드.

**P4-5 (`66ec9fa`)** — **동적 Fact 해석 심**: scenario-context에 Fact ALS 신설, `applyDynamicFacts(plotSeed.keyFacts→FactDefinition 변환)`을 진입점 2곳에 배선. getFact/getFactsByKeywords/getFactsKnownBy/npcKnowsFact 폴백 합류 → questReveal 서술 주입·주제 우선 선택(경로 2)·fact-awareness가 **코드 무변경**으로 keyFact에 동작. addFact에서 발견 factId ∈ keyFacts면 plotProgress.discoveredKeyFactIds 기록(경로 1/2/3 전부 커버). 유닛 6케이스.

**P4-6 (`e3bad52`)** — 라이브 E2E(graymar 임시 AUTONOMOUS 픽스처·port 3100·15턴 실런)에서 실측 버그 1건: 채택 블록의 runState 신규 필드 대입이 커밋(updatedRunState 얕은 복사)에서 유실 → 3곳 교정. 검증 결과:
- plotSeed nano 생성·동결 성공 (fallback 아님 — "경비대·밀수 결탁 성물 은폐", 모티프 3조합, 캐스팅 6, keyFacts 8)
- 워커 선계산 매 턴 1~3개(fact 힌트 포함), CAS 저장·갱신 확인
- **채택 2회 실측**: BEAT_6_0 score=97 / BEAT_13_0 score=82 — 채택 비트가 서술 견인 (짐꾼 밀담 "장부 조작" = FACT_1 힌트 정합)
- **keyFact 규명 1건**: FACT_2가 경로 2(동적 fact 심·NPC 공개)로 발견 → plotProgress 1/8
- **킬스위치**: 디렉터 완전 무동작 + 게임 정상 진행 (불변식 C)
- AUTHORED 무회귀 (전체 스위트 + 픽스처 원복)

### 15.4 관찰·후속 (G2/P8로 이월)

- **대화 스티키니스로 채택 빈도 낮음**: contextNpc 존재 시 INVESTIGATE/OBSERVE(SOCIAL 계열)가 CONVERSATION_CONT로 빠져, 비트 채택은 사실상 비대화 행동(SNEAK 등)·NPC 조우 전 턴에서만 발화. Player-First 고정점(§15.2)의 의도된 결과지만, 대화 위주 플레이에선 디렉터 체감이 약함 — **G2에서 채택률 계측 후 판단** (예: 대화 잠금 해제 턴·막 전환 턴에 한해 우선순위 조정).
- 정식 G2 계측 항목: 규명율 분포, keyFact 도달률(§11-C), 채택/폐기 비율(plotProgress 계측 필드), 비트 premise 다양성(n-gram).
- 실런 검증 잔여: proposedNpc 동적 등록 경로는 유닛+P0 E2E로만 커버 (이번 실런에선 nano가 기존 NPC 위주로 생성) — G2 다회 런에서 자연 발생 확인.
- P5(종결 파이프)가 acts 소진·게이지 임계·규명율 엔딩을 이어받는다. getActProgress가 이미 막 파생을 제공.
