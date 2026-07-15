# 75. 자율 서사 팩 상세설계 — "진상 선확정 디렉터 모드"

> 상태: 📐 상세설계 확정 (2026-07-15) — 미구현. [[74_autonomous_narrative_direction]]의 문답식 의사결정 14건을 확정해 구체화한 정본. **검토 반영 (2026-07-15): §11 실측 대조 리뷰 신설(getNpc 127곳 정정·stub 필드표면·시드 정합·규명 도달성), P0 범위 확장 + G2 2차 관문 신설.**
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

### 4.1 stub 스키마 + 검증
nano가 생성, 서버가 등록: `NPC_DYN_<seq>` id 부여 후 `runState.dynamicNpcs[]` 영속.

```jsonc
{ "npcId": "NPC_DYN_3", "name": "일사 크레번", "tier": "SUB",
  "unknownAlias": "낡은 외투의 여인",        // 5~10자 규약 (arch/68 부록 I)
  "shortAlias": "외투 여인",
  "basePosture": "CAUTIOUS",                 // 5종 enum 강제
  "speechRegister": "HAEYO",                 // 5종 enum 강제 — 어체 검증/fallback 재사용
  "role": "밀수 중개인", "oneLinePersonality": "…" }
```
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
| **P0 스파이크** | 동적 NPC 해석 심 — ALS 확장 + getNpc 폴백 + 워커 경로에서 마커·소개·반응 디렉터가 동적 NPC로 도는지. **+ getNpc 127곳 읽기 필드 전수 조사**: knownFacts(fact 공개)·linkedIncidents·schedule/agenda(Living World 순회)·combatProfile(전투 진입)·faction·personality를 동적 NPC가 만났을 때 필드별 graceful-degradation 기본값 정의 (§11-A) | 검증 (74 §8 재정의판) | — |
| **P1** | Dynamic NPC Registry 정식화 (stub 검증·등록 API·감사 도구 대응·실루엣 폴백) | 엔진 중 | P0 통과 |
| **P2** | 73 B1 packMeters (자율 팩 종결의 선행 의존) | 엔진 중 | — (병행 가능) |
| **P3** | Plot Seed 생성·검증·동결 + `narrativeMode` 팩 계약 | 엔진 중 | P1 |
| **P4** | Emergent Director (비동기 선계산 + 폴백 체인 + 인력) | 엔진 대 | P1·P3 |
| **G2 관문** | **2차 관문 (신설 §11-D)** — Plot Seed + 디렉터가 실제로 **정합·공정·해결가능한 미스터리**를 뽑는가(§11-B/C). 규명율 분포·표류·시드 정합 실측. 실패 시 **L2(디렉터 없이 저작/반저작 시드)로 후퇴** | 검증 | P3·P4 |
| **P5** | 종결 파이프 (3막 예산 + 게이지 임계 + 규명율 엔딩 + 아카이브) | 엔진 중 | **G2 통과** · P2 |
| **P6** | 신규 팩 콘텐츠 저작 — 그레이마르 세계 확장 도시 (장소 7~8·코어 6·motifs 10±·팔레트·endingTones) | 콘텐츠 | P3 계약 확정 후 병행 |
| **P7** | 주민화 + 재진입(캠페인 예외·보상 감쇠) | 엔진 소 | P5 |
| **P8** | 계측·플레이테스트 (분포 지표, 10~15턴 다회) | 검증 | 전체 |

**이중 관문 구조** (검토 반영): **P0**(해석 심 비용) 실패 → L1/L2로 후퇴. **G2**(생성 미스터리 정합·공정) 실패 → L2(저작/반저작 시드)로 후퇴하되 동적 NPC(P1)는 유지. P0만으론 부족한 이유는 §11-A/D — 진짜 미검증 가정(정합한 미스터리 생성)은 P3~P4에서야 드러나기 때문. 두 관문 다 통과해야 P5~P8(종결·콘텐츠·주민화) 대공사에 커밋한다.

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

### 11-B. 🔴 Plot Seed 검증이 "구조"만이고 "정합성"이 아니다 (최대 품질 리스크 — G2로 반영)
§3 검증 항목이 전부 구조적(ID·개수·enum)이라 **"미스터리가 공정하게 풀리는가"를 검증 못 한다.** culprit/동기/keyFacts/endingCandidates의 서사 정합, 단서만으로 진상 도달 가능성은 구조 검사로 안 잡힌다. 구조상 유효하나 서사상 엉성한 시드 = 김빠지는 런. → (a) 시드 통짜 생성 후 **LLM 자기검증 패스**(공정성/해결가능성 채점) 추가, 또는 (b) 생성을 **"해결 형태가 알려진 템플릿 스켈레톤"**(모티프 조합별 정답 골격)으로 제약. "재롤 N회"는 정합성을 보장하지 않는다. G2 관문에서 실측.

### 11-C. 🟠 keyFact 도달가능성 미보장 → 규명율 불공정
`규명율 = 발견/전체`인데 keyFact 보유자가 끝내 안 만나는 동적 NPC면 그 fact는 **구조적 발견 불가** → 실력 무관 상한 <100. → 디렉터가 "막 예산 내 모든 keyFact에 최소 1개 표면화 경로 보장"(reachability)을 지도록 인력(§5.1)에 규약 추가. 미보장 시 규명율 지표 자체가 불공정. G2에서 keyFact 도달률 계측.

### 11-D. 🟠 L3-우선의 관문이 P0에만 있었다 → 이중 관문으로 보강 (§8 G2 신설)
P0 후퇴선은 **해석 심 비용**만 커버했으나, 진짜 미검증 가정은 **11-B/C(생성 미스터리의 정합·공정)**이고 이건 P3~P4에서야 드러난다. → P3/P4 뒤 **G2 관문** 신설: Plot Seed+디렉터가 플레이 가능한 미스터리를 뽑는지 검증, 실패 시 L2(저작/반저작 시드, 동적 NPC는 유지)로 후퇴. 두 관문 통과해야 P5~P8 대공사 커밋.

### 11-E. 🟡 기타
- **레이턴시 곱셈**: 턴당 워커가 서술+비트2~3+stub+규명추출. 선계산 적중 실패 턴의 동기 폴백이 **디렉터 없이** 도는지 명시 필요(§5.1 폴백 체인이 SituationGenerator→기본이벤트로 끝나야 함, 디렉터 재호출 금지).
- **"저작 최소"의 시점**: 회차당은 최소가 맞으나 P6(새 도시 전체 저작)+P1~P5 엔진 대공사가 선행 → **초기 비용은 큼.** "저작 최소"는 런타임 한정임을 명확히.
- **초기 목표가 L3**: 74는 L1 먼저를 권했다. 이중 관문·후퇴선으로 L3-우선의 리스크를 관리하나, 대안(L1→L2 점증)이 총비용상 더 쌀 가능성은 G2 전까지 열어둔다.
