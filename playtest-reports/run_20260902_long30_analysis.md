# 30턴 롱런 정밀 분석 — run 792a8c98 (graymar_v1 · HERBALIST · chatty)

- 일시: 2026-09-02 14:0x · 서버 527511f (로컬 HEAD 일치) · 리포트 `run_20260902_long30.json`
- 실행: `scripts/playtest.py --turns 30 --agent chatty --scenario graymar_v1 --preset HERBALIST`
- **런은 턴 30(플레이어 제출 23턴)에서 `arc_finale` 로 RUN_ENDED** — 요청한 30 제출턴을 채우지 못한 이유 자체가 최상위 결함(§2-A).
- 게이트 14/15 (V14 FAIL 은 직전 star_sand 런의 BACKGROUND 고착 1건이 3런 풀링에 남은 것 — 이 런 bgOver=0).
- 정독 방식: DB `turns` 전 턴 전문 + `llm_prompt` 대조 + 30일 DB 재집계 (`scratchpad/deep30.py`, `dump_run.py`).

## 0. 계측 요약

| 항목 | 값 |
|---|---|
| 판정 | SUCCESS 7 · PARTIAL 2 · FAIL 2 (FREE 4) |
| fact 공개 | 2건 (T7 LEDGER_EXISTS rumor · T21 WAGE_FRAUD_PATTERN rumor) — **둘 다 rumor 폴백, 주제 매칭 0** |
| questState | S0→S1 (T7) 이후 종료까지 S1 고정. discoveredQuestFacts 는 6개 — 4개는 아크 스테이지 보상으로 서술 없이 유입 |
| 화자 | 에드릭 4 · 마이렐 4 · 토브렌 4 · 쉐도우 3 — 대화 잠금 4턴 상한이 정확히 작동, 매 상한 도달 후 에이전트가 이동 |
| 어체 위반 | 0/31 발화 (5 NPC) |
| 반복 | 문장 완전 중복 0 · 4-gram 3턴+ 1건("그 자리에 선 채로") · 대명사 개시어 1.7% |
| 되묻기 | NPC 마지막 대사가 질문으로 끝난 턴 0/15 (server 4937281 억제 유지) |
| 프롬프트 | avg 12,039 · max 17,372 (>16,500 1턴) |
| 레이턴시 | avg 5.8s · p50 6.2 · p90 9.2 · max 11.8s(T28) |
| 시간 | DAWN→DAY(T12)→DUSK(T15)→NIGHT(T20)→DAWN(T28) · clock 13 · day 2 |
| 선택지 표면 | nano 11 · server 4 · nano MOVE_LOCATION 승격 1건 |
| 빈손 가드 | 발동 0 (§3-④ 참조) |

## 1. 타임라인 (LOCATION 만)

| T | 장소 | 입력 | 판정 | 화자 | 비고 |
|---|---|---|---|---|---|
| 4~7 | 시장 | 소문 → 질문 → 이해 → 조작 흔적 | FAIL·FAIL·FREE·PARTIAL | 에드릭 | T7 rumor 공개. "삼할" 2회 |
| 12~15 | 경비대 | 접근 → 기록 질문 → 친근 → 서류 | SUCCESS·FREE·FREE·SUCCESS | 마이렐 | **SUCCESS 2턴 모두 fact 0 → LLM 이 순찰표 누락·봉급 덧칠·지워진 서명을 창작** |
| 20~23 | 부두 | 선원 → 상자 → 표식 언급 → 표식 캐묻기 | SUCCESS×4 | 토브렌 | T20 EVT_HARBOR_ARC_HINT 로 currentRoute=PROFIT 세팅(commitment 0), T21 **아크 stage 1 안내+완수 동시** |
| 28~30 | 빈민가 | 주민 접근 → 행인 관찰 → 결말 | SUCCESS·PARTIAL | 쉐도우 | T28 stage 2, T29 stage 3 완수 → `arc_finale` 노출 → T30 엔딩 "황금빛 그림자" |

## 2. 신규 결함

### A. 아크 3막이 커밋 없이 열리고, 안내 턴에 즉시 완수된다 (P0 — 런 조기 종료)

**증상**: 커밋 선택지(`arc_commit_*`)를 한 번도 고르지 않았는데 T21·T28·T29 에 stage 1·2·3 이 각각 **안내와 완수가 같은 턴**에 처리됐고, T29 에 `arc_finale` 가 노출돼 T30 에 엔딩. questState S1, 장부 행방은 미해결, 로넨 보고 0회.

**근거**
- `arcState` 최종: `{commitment: 0, currentRoute: PROFIT_FROM_CHAOS, completedStages: [1,2,3], finaleReady: true}`.
- T20 이벤트 `EVT_HARBOR_ARC_HINT`(ARC_HINT 타입) 의 `arcRouteTag` 가 `turns.service:4091` 경로로 `switchRoute` 를 불러 currentRoute 를 세팅(commitment 0 유지).
- `arc-stage.core.ts getNextArcStage` 는 주석("무커밋·소진 시 null")과 달리 **`currentRoute` 유무만** 본다. 실제 커밋(`hub-turn.service:83~`)은 `switchRoute + progressCommitment(2)` 로 commitment 2 를 남기므로 "커밋됨"의 정본 신호는 commitment 이지 currentRoute 가 아니다.
- 스테이지 판정은 대화 계열이면 진행 가능(`isArcStageProgressAction`) + SUCCESS/PARTIAL 완료 → 안내 턴의 성공 판정이 곧 완수. T28 프롬프트 `[이번 턴 사건]` 에 stage 2 안내문 전문("노동 길드가 물건을 들이고, 상인 길드가 세탁하며…")이 실려 쉐도우 대사로 거의 그대로 낭독됨(불변식 50 앵커).
- 30일 DB(ARC_STAGE 발화 런 11): **commitment 0 인데 스테이지가 진행된 런 5** — b5cc9803·6dc4880d·83988f74 (turn 5 에 stage 1 완수, S1), 1fc6211d (S3 에서 finale 엔딩), 792a8c98 (S1 에서 finale 엔딩). graymar 30일 활성 런 중 currentRoute 세팅+commitment 0 이 5건.

**근본 원인**: arch/103 배선 시 "커밋"을 `currentRoute != null` 로 근사했는데, 그 필드는 ARC_HINT 이벤트가 커밋 전에도 채운다(arch/68 부록 F 이전부터 있던 루트 성향 추적). 두 의미가 한 필드에 겹침.

**제안**
1. 커밋 시 `arcState.committedAt`(turnNo) 또는 `committed: true` 를 명시 기록하고 `getNextArcStage` 는 그 플래그(+레거시 `commitment >= 2`)만 인정. ARC_HINT 의 currentRoute 세팅은 유지(성향 추적 목적).
2. 스테이지 **안내 턴은 완수 불가**(announced 후 다음 진행 턴부터 판정) — 3막이 3턴에 끝나는 것을 막고 안내문이 같은 턴 대사로 낭독되는 앵커도 끊는다.
3. 회귀 스펙: (a) currentRoute 만 있고 commitment 0 → activeStage null (b) 안내 턴 SUCCESS → completed false. 기존 arc-stage 스펙 18케이스 유지.

### B. "[정보 전달] 이번 턴에서 중요한 단서가 드러납니다" 가 서버 fact 없이 주입된다 (P0 — 단서 환각의 상류)

**증상**: T12 마이렐이 첫 만남에 "누락된 순찰표… 그 시간표에 접근할 권한을 가진 자는 외부 도둑보다 먼저 조사해야 하오" — S4→S5 fact(FACT_MAIREL_GUARD_EVIDENCE, 보유자 브렌·펠릭스)에 해당하는 내용을 **범인 본인이** 창작 발화. questReveal 없음. T14 "봉급 액수 끝자리 덧칠·지워진 서명", T15 "그대가 찾아낸 그 얼룩" 도 같은 부류. 이후 T13 마이렐이 "그대가 언급한 누락된 자료"라며 자기가 만든 단서를 플레이어 발언으로 귀속.

**근거**
- T12 프롬프트 `[이벤트 컨셉]` 블록: `[정보 전달] 관찰을 통해 암시합니다: 이번 턴에서 중요한 단서가 드러납니다.` — 그런데 서버 `ui.questReveal = null`, 같은 프롬프트에 `[보류]`(정보 보류) 가이드도 공존.
- 생성 경로: `prompt-builder.service.ts:3872` 는 `nanoEventHint.fact && nanoEventHint.factRevealed` 만 본다. `factRevealed` 는 **nano(gpt-4.1-nano) 가 JSON 으로 스스로 답한 값**이며(`nano-event-director.service.ts:752`), 인터페이스 주석 "서버 RNG로 최종 확정"에 해당하는 대조 코드는 워커·turns.service 어디에도 없다(사문 계약). nano 에 넘기는 `availableFacts`(turns.service:1202) 는 장소 이벤트의 미발견 discoverableFact 전부(rate 1, 중복 포함, 주제·확률 게이트 미반영)라 nano 는 거의 항상 "드러난다"고 답한다.
- 이 런: LOCATION CHOICE 15턴 중 지시 주입 9턴, 그중 실제 questReveal 1턴(T7). **FAIL 판정 T4 에도 주입**.
- 30일 DB(LOCATION, 프롬프트 보유): questReveal 없는 턴 2,016 중 **676 턴(34%)** 에 지시 주입, 실제 공개 턴은 131. 판정별 무공개 주입: SUCCESS 329/519(63%) · PARTIAL 75/246 · **FAIL 34/94(36%)** · 무판정 238/1,157.
- 피해 프록시: 무공개 턴에서 단서형 어휘(단서·흔적이·기록이·증거·누락·비어 있) 출현율 — 지시 있음 **29.3%** vs 없음 12.1% (2.4배). 마이렐 30일 171턴 중 순찰표·출입 기록·빈 시간대 언급 25턴, 그중 16턴이 questReveal 없음.

**근본 원인**: nano 의 소프트 판단(factRevealed)이 서버 정본(questReveal)과 대조 없이 하드 지시로 승격됨 — 불변식 2 의 "하드 상태는 서버만"을 프롬프트 지시 층에서 어긴 형태. arch/58 의 "기록 fact = 서술 fact" 는 공개 턴만 다뤘고, **비공개 턴에 '공개하라'는 지시가 남아 있는 경우**를 못 봤다.

**제안**
1. `buildNanoEventConceptBlock` 게이트를 `serverResult.ui.questReveal` 존재로 교체(또는 워커에서 `nanoEventHint.factRevealed = !!questReveal` 로 정규화 후 공급). nano 의 `fact/factRevealed` 출력은 계측용으로만 보존.
2. 무공개 턴은 반대로 `[보류]`/빈손 가이드가 단독으로 서게 된다 — 이미 있는 채널이라 프롬프트 순증 0.
3. nano `availableFacts` 중복 제거(FACT_INSIDE_JOB ×3) 는 곁가지.
4. 검증: 30일 프롬프트 재생으로 지시 주입 676→0 확인 + 실런 1회에서 SUCCESS 무공개 턴의 단서형 어휘율이 baseline(12%)으로 내려오는지.

### C. 에드릭 speechStyle 의 어구 예시 "(삼할/두 자루/엿새 전 등)" 앵커 (P1 — 콘텐츠, 불변식 42)

**증상**: T4 "삼할쯤 모자란 셈", T6 "삼할만 어긋나도" — 다른 수치가 아니라 예시 그대로.
**근거**: `npcs.json:344` speechStyle 에 `구체 숫자(삼할/두 자루/엿새 전 등) 1개 이상 자연 인용`. 30일 에드릭 화자 352턴 중 **"삼할" 165턴(47%)**, "두 자루|엿새" 50턴. 3팩 speechStyle 전수 스캔에서 발화 내용을 괄호 예시로 준 곳은 이 1건뿐(나머지 괄호는 화제 범주·호칭 지정).
**제안**: "비율·개수·날짜 중 하나를 매 답변 다른 값으로" 식 구성 요소 지시로 교체(arch/105 P0-3 와 같은 처방). `audit_content.py` 에 `SPEECHSTYLE_LITERAL_EXAMPLE`(괄호 안 `/` 구분 + "등)" 종결) 규칙 추가. mannerism 배열의 같은 문구는 프롬프트 미노출이라 무해하나 함께 정리.

## 3. 기존 트랙 재확인 (수정하지 않음)

| # | 관찰 | 귀속 트랙 | 이 런 근거 |
|---|---|---|---|
| ① | rumor 폴백 공개 2/2 — "그간 주워들은 이야기가 하나로 맞물린다"는데 실제로 들은 적 없음 | arch/60 잔여(rumor 타이밍) | T7·T21 revealMode=rumor, matchedByTopic=false. 플레이어 입력 주제가 fact 키워드에 한 번도 닿지 않았다(에드릭 '장부' 는 이미 발견분) |
| ② | 잡담 화제가 질문·주제 턴에 끼어듦 — T13 기록 질문에 "병영 식사", T5 정보 질문에 "책상물림", T22 표식 언급에 "가족 명분" | arch/104 잡담 게이트 잔여 | 이 런 주입 5턴 중 3턴이 비사교 입력. 30일 TALK 질문형 입력(질문·묻·캐묻) 172턴 중 **78턴(45%)** 화제 주입. 화이트리스트 `actionType === TALK` 가 질문 턴을 거르지 못함 → `dialogueAct` 가 QUESTION 성이면 제외하는 조건 추가 검토 |
| ③ | 프리셋 "약초 냄새가 밴 손가락" 4회(T1·T10·T18·T26) | 불변식 45·50 (엔진 리터럴 앵커) | `context-builder.service.ts:2109` 의 6프리셋 `base` 문구가 엔진 하드코딩 + 완성 어구. 30일 HERBALIST HUB 턴 11 중 5(45%) 축자 재현. presets.json 으로 외부화하면서 구성 요소형으로 축약 필요 |
| ④ | 빈손 가드 미발동 — 마이렐 4턴 대화에 fact 0 인데 인계 없음 | 2026-09-02 신설 가드의 설계 갭 | `npcHasUndiscoveredFact` 는 보유 fact 유무만 본다. 마이렐은 FACT_INSIDE_JOB 을 보유하나 플레이어 질문이 키워드(내부·권한·범인…)에 안 닿아 4턴 내내 미공개. "보유"가 아니라 **"이번 입력으로 공개 가능"** 또는 "N턴 연속 미공개"를 신호로 삼아야 §2-B 와 맞물려 "모른다/다른 이에게" 유도가 산다 |
| ⑤ | nano 소품 환각 "손뿔"(T22 `[NPC 행동] 경비 책임자 수상한 관리인이 무심히 손뿔을 만지작거린다`) → 본문 2회 복제, 역할명 혼동(경비 책임자=마이렐) | arch/67 nano 감사 잔여(자유 텍스트 미검증) | 1턴, 계측만 |
| ⑥ | 군중 인용 "청소부: '…' / 노점상: '…'"(T22) 콜론 라벨 | 종합 보고서 §6 군중 인용 재사용 | 형식은 규칙 준수, 인물 풀 반복은 미증가 |
| ⑦ | 마이렐이 부두 NIGHT 에 3턴 연속 원경 등장(T21~23 "멀리서 야간 경비 책임자가 부하들에게…") | 정상 — 스케줄 NIGHT=LOC_HARBOR + agenda stage1 "항만 전면 수색" 시그널 | 결함 아님. 3턴 같은 원경 비트는 반복 억제 대상 후보 |

## 4. 수정 검증 (직전 배포분)

- **nano 이동 라벨 승격** 1건 정상(MOVE_LOCATION+target), 잔존 이동 라벨×비이동 affordance 0.
- **대화 잠금 4턴 상한** 3회 모두 정확히 4턴에서 이동 선택지(quest_forward·go_hub) 노출 → 에이전트 이동.
- **되묻기 억제** 0/15, **어체** 0/31, **실명 치환** 오염 0(토브렌 "단정한 장교" 별칭 정상), **NpcMismatch** 로그 0.
- **레이턴시** p90 9.2s (10s 기준 이내), 프롬프트 백스톱 미발동.
- 빈손 가드는 조건 미성립(§3-④)이라 공허한 통과.

## 5. 권고 순서

1. **B** (게이트 1줄 + 워커 정규화) — 30일 676턴 규모, 수정 비용 최소, 단서 환각의 상류.
2. **A** (커밋 플래그 + 안내 턴 완수 금지) — 5/11 런에서 3막이 무커밋 진행, 2런이 미완 상태로 엔딩. 스펙 2건 추가.
3. **C** (콘텐츠 1줄 + 감사 규칙) — 코드 0줄.
4. ③ 프리셋 리터럴 외부화, ④ 빈손 가드 신호 재정의, ② 잡담 화이트리스트 질문 턴 제외는 위 3건 배포 후 후속.

검증 계획: B·A 는 30일 프롬프트/런 재생(정적) → 스펙 → 실런 1회(chatty·graymar) 에서 (i) `[정보 전달]` 주입 = questReveal 턴만 (ii) ARC_STAGE_INTRO 가 arc_commit 이후에만 (iii) 안내 턴 완수 0.

## 6. 조치 결과 (2026-09-02 같은 날 수정)

| 결함 | 수정 | 검증 |
|---|---|---|
| A 아크 무커밋 진행 | `ArcState.committedAt` 신설(hub-turn 커밋 시 기록) + `isArcCommitted`(committedAt 또는 레거시 commitment ≥ 2)가 `getNextArcStage`·S5 타이머 finaleReady 의 유일한 게이트 + `isArcStageAnnounced` 로 안내 턴 완수 금지 | 스펙 +4 · 실런 프로브(run 8e5158b8, 부두): route-only → arc 이벤트 0 / committedAt 부여 후 첫 턴 ARC_STAGE_INTRO 만 / 둘째 턴 PARTIAL 완수 |
| B 유령 `[정보 전달]` | `llm/nano-fact-reveal.core.ts normalizeNanoFactRevealCore` — 워커가 `ui.questReveal.factId` 로 정렬(없으면 지시 제거, 있으면 서버 factId 로 교체), 로그 `[NanoFactRevealNorm]`. 부수: nano `availableFacts` factId 중복 제거. **B-2** 이벤트 경로(1·3) 발견도 `ui.questReveal`(primaryNpc 있으면 observe, 없으면 rumor)로 배선 — 기록만 되고 서술에 안 실리던 공백(run bcaab205 T4) | 스펙 +5 · 프로브(run bcaab205): 무공개 턴 지시 제거, 공개 턴 2건 모두 nano 가 다른 fact 를 답했는데 서버 factId 로 교정 · 프로브 2(이벤트 경로): T4 FREE 턴 자동 발견이 questReveal 로 전달됨 |
| C 에드릭 "삼할" | speechStyle 구성 요소 지시로 교체 + mannerism 동일 정리 + `audit_content.py` `SPEECHSTYLE_LITERAL_EXAMPLE`(WARN, 구 문구 검출·범주 나열 무검출 확인) | 골든 스냅샷 1건(말투 줄만) 갱신 · 프로브 에드릭 3턴 "삼할" 0 |

전체 2,524 passed · 콘텐츠 감사 ERROR 0/WARN 0 · 스모크 PASS. 미커밋.
