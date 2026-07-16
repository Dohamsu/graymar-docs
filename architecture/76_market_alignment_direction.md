# 76. 시장 조사 대응 방향 — "이해하고 기억해주는 경험" 정렬

> 상태: 📐 방향 확정 대기 (2026-07-16) — 소유자 제공 시장 조사(AI 텍스트 RPG 이용자 긍/부정 요인)를 현 구조와 대조해 수정 방향을 도출. 조사 원문의 결론: **"내가 상상한 행동을 게임이 이해하고 기억해주는 경험에는 돈을 내지만, AI가 저지른 오류를 내가 계속 수정해야 하는 경험에는 돈을 내지 않는다."**
> 관련: [[75_autonomous_pack_design]] (재플레이성 트랙 — P6 카른홀트까지 배포), [[73_scenario_differentiation]] (반복 서사 계측 지표), arch/75 P5 리뷰의 NPC 반응 평가 (사물·기행·공포 행동화 갭).

---

## 1. 대조표 — 조사 요인 ↔ 현 구조

### 1.1 긍정 요인 (사용자가 돈을 내는 것)

| 조사 항목 | 현 상태 | 판정 |
|---|---|---|
| 자유 입력 행동·기상천외한 시도 | 자유 입력 + 창의 전투 5-Tier + ChallengeClassifier(FREE/CHECK) | **보유** — 단 비전투 사물 상호작용·기행은 서술로만 소화 (§2 D3) |
| 선택이 실제 게임 상태를 바꿈 | **서버 정본 (불변식 1)** — 인벤토리·관계·퀘스트·시간·골드 전부 서버 관리, LLM 무권한 | **구조적 최대 강점** — 조사가 지목한 경쟁 서비스 최대 약점의 정반대 |
| 매번 달라지는 재플레이성 | AUTONOMOUS 팩 (P0~P6, 카른홀트 배포) — 매 런 새 진상·캐스팅·동적 NPC | **방금 구축한 트랙이 정확히 이 수요** — 투자 방향 실증 |
| 세계·캐릭터 제작 도구 | 팩 저작은 개발자 전용 JSON | **장기 갭** (§2 D6) |
| 솔로 + 비동기 멀티 | 솔로 기본 + 파티 Phase 1~3 | 보유 |
| 장기 기억 | Memory v2~v4 + NpcPersonalMemory + entity_facts + 로어북 + 선별 주입 | **강점** — 전면에 내세울 가치 (조사: "핵심 가치로 인식") |
| 명확한 무료 체험·비 P2W | 무과금 프로토타입 — **원칙 미등재** | §2 D5 등재 필요 |

### 1.2 부정 요인 (사용자가 떠나는 것)

| 조사 항목 | 현 노출도 | 판정 |
|---|---|---|
| 기억 상실·설정 불일치 (최다·치명) | 서버 정본 + 마커 무결성(arch/64) + 소개 정합 + IntroRollback + 카드 정합 다층 방어 | **구조적 최강 방어 — 핵심 차별점.** 죽은 NPC 재등장·퀘스트 재제시·관계 초기화가 구조상 불가능 |
| 자의적·불공정 판정 | 1d6+floor(stat/4)+baseMod 공식 + 주사위 애니메이션 + 판정 순차 공식 노출 | **부분** — FREE 스킵 사유·보정치 출처·FAIL 원인이 미노출 (§2 D2) |
| 플레이어가 AI를 계속 교정 ("AI 관리 업무") | 설정집·요약·관계 수동 갱신 없음 — 전부 서버 자동 | 방어됨 |
| 반복적·목적 없는 서사 | 퀘스트 6단계 / 자율 팩 3막+인력(gravity) = 목적성 구조 보장. 반복 표현은 지속 개선 중(어휘 폭주 -84% 등) | 부분 — 계측 상시화 필요 (§2 D4) |
| **의도 무시 강제 진행** | **⚠️ 신규 노출** — P4 규칙 1.5-C 강제창(BEAT_FORCE_AFTER_TURNS=4)이 "대화하려는데 사건 끼워넣기" 패턴과 정확히 충돌 가능 | **§2 D1 — 최우선** |
| 생성 실패에도 비용 차감 | LLM 실패해도 게임 진행(불변식 2) + retry-llm 무료 | 방어됨 (과금 도입 시 D5로 봉인) |
| 느린 응답·품질 변동 | 레이턴시 10초 미만 원칙 + provider sort + fallback 모델 | 방어됨 — 원칙 유지 |
| 불투명 크레딧 | 해당 없음 (미과금) | D5 설계 시 단일 화폐 원칙 |

**요약**: 조사가 꼽은 3대 핵심(서버 사실 관리 / 판정 근거 / 부가가치 과금) 중 ①은 창립 불변식으로 이미 완성, ②는 부분 구현, ③은 미등재. 최대 신규 리스크는 우리가 방금 만든 디렉터의 강제 진행 성향.

## 2. 수정 방향 (우선순위)

### D1 — "플레이어 의도 존중" 명문화 + 강제창 재검토 〔P0 · 엔진 소〕
조사에서 자유도 약속과 충돌하는 최다 불만 축. 자율 팩 디렉터는 "세계가 움직인다"와 "의도 무시" 사이의 칼날 위에 있다.
- (a) 강제창(1.5-C) 발동 조건에서 **대화 잠금 활성 턴 제외** — 몰입 중인 대화를 사건이 끊지 않는다.
- (b) **사교 발화·REST 의도 턴은 비트 채택 금지** — "휴식을 원해도 전투 발생" 패턴 원천 차단 (dialogueAct 게이트 재사용).
- (c) P8 계측에 **의도 정합 채택률**(채택 비트가 플레이어 행동 계열과 affordance 일치한 비율) 추가.
- **신규 불변식 후보 D**: "디렉터 비트는 플레이어 의도와 정합할 때만 채택 — 서사 강제 진행 금지. 인력(gravity)은 유인이지 강제가 아니다."

**구현 반영 (2026-07-16, D1-a/b + D1-d + D5 — 미커밋):** CLAUDE.md 불변식 47(불변식 D) + 과금 3원칙 등재(D5·D1-d). 엔진(`turns.service.ts`): (a) `conversationLockActive`(직전 대화 NPC + 대화 계열 행동) 계산 → `determineTurnModeCore` 규칙 1.5의 강제창 분기를 `beatForceWindow && !conversationLockActive`로 가드(대화 잠금 4턴 캡이 정체를 자연 해소하므로 굶주림 없음). (b) `intentSuppressesBeat`(REST 또는 순수 사교 발화 `SOCIAL_SPEECH_ACTS`) → 규칙 1.5·3.6 승격 금지 + 채택 블록(`if (beatAvailable && !intentSuppressesBeat && plotSeed)`) 이중 가드. 탐색 행동(A) 승격은 유지. 유닛 6종 추가(player-first.spec — 대화 잠금 유지·탐색 예외·사교/REST 억제), 전체 1266 passed. **미검증(계측)**: 실제 의도 정합 채택률은 D1-c(P8 계측)에서 확인.

### D2 — 판정 투명성 마감 〔P0 · 클라 소〕
골격(공식+주사위)은 이미 시장 상위권. 남은 갭만 마감:
- FREE 판정 스킵 턴에 사유 표시 ("일상 행동 — 판정 불필요").
- 판정 턴에 보정치 출처 분해 노출 (스탯 +2 / 프리셋 특기 +1 / 이벤트 -1 / 상태이상 -2).
- FAIL 턴에 "무엇이 부족했나" (필요 5, 굴림 3+보정 1 = 4).
- 위치: TurnResultBanner·주사위 연출 툴팁 — 서버는 이미 다 아는 값이라 UI 전달만.

**구현 반영 (2026-07-16, D2-a/b/c — 미커밋):** 서버는 이미 diceRoll/statBonus/baseMod/totalScore를 `resolveBreakdown`으로 전달 중이었고(클라 `ResolveOutcomeInline` 공식 렌더 기존), 남은 갭만 마감. **D2-b**: `resolve.service` baseMod 누적을 `addMod(label,value)`로 바꿔 `modifiers: Array<{label,value}>` 출처 분해 생성(지형 유리/불리·소란·위험 감수·언변 세트·배경 경험·장소 제약/이점) → `ResolveResult`·`ResolveBreakdown`·turns.service 전달 → 클라 `BreakdownFormula`가 단일 "보정" 대신 항목별 렌더(modifiers 없으면 합산 fallback). **D2-c**: 판정 임계를 `RESOLVE_SUCCESS_THRESHOLD=5`/`PARTIAL=3` 상수로 정본화(computeOutcome 참조) → breakdown에 successThreshold 전달 → FAIL 턴 "성공 필요 5 · N만큼 부족" 표시. **D2-a**: ChallengeClassifier `result==='FREE'`(구조적 MOVE/REST/SHOP 제외) 시 `ui.resolveSkipped=true` → 클라 "✓ 일상 행동 — 판정 불필요" 안내. 검증: 서버/클라 빌드·1268 passed(resolve +2·player-first 유지)·양쪽 린트 0. 전 시나리오 공통(AUTHORED/AUTONOMOUS 무관).

### D3 — 자유도 체감 3종 (NPC 반응 평가와 교차점) 〔P1 · 엔진 중〕
조사의 "기상천외한 행동 성공의 만족감" + "상태를 바꾸는 경험"을 자유 입력에서 완성. arch/75 P5 리뷰에서 실측한 갭과 동일:
- **사물 상태 경량 구현**: 장소별 `propsState`(파괴·전도·탈취 흔적 몇 개) — 다음 턴 서술·NPC 반응이 참조. 전면 오브젝트 시스템이 아니라 "흔적 5~10개 링버퍼" 수준.
- **기행 감정축**: 비정형 행동의 오분류(TALK→trust+5) 교정 — WEIRD 신호 → suspicion 상승.
- **공포 행동화**: fear 임계 초과 NPC의 회피·신고·도주 능동 행동 (수치가 세계를 움직이게).

#### D3-입력 자유화 — actionType 탈버킷 (2026-07-16 구현 · 미커밋)

**배경 (소유자 실측 지적):** actionType(15종) 버킷이 **판정(스탯·난이도)까지 고정**해, 창의 행동이 버킷에 갇히는 느낌("탁자에 올라가 춤춘다"→TALK→카리스마 판정). 실측: actionType의 기계적 역할은 **스탯 선택 + 소수 보정뿐**이고, 서술은 이미 rawInput 원문을 받으며, 전투엔 이미 창의 처리(arch/41)가 있으나 LOCATION엔 없음.

**설계:** actionType은 "판정 가족"으로만 남기고, **행동-특정 3파라미터를 ChallengeClassifier(이미 도는 nano FREE/CHECK 호출)에 확장** — 새 nano 호출 0. nano 제안 → **서버 검증**(불변식 1 보존).
- **① statHint** — 이 행동에 맞는 스탯을 nano가 제안, 서버가 허용집합(`str/dex/wit/con/per/cha`) 검증 → `ACTION_STAT_MAP` 기본 대신 사용. 벽 타기가 TALK로 분류돼도 dex 판정.
- **② difficultyMod** — 행동 과감함/규모, clamp `[-2,+2]` → `modifiers`에 "행동 난이도"로 누적(D2 투명성 UI에 노출). "왕을 반역시킨다"가 실제로 어려워짐.
- **③ plausibility** — `NORMAL/UNUSUAL/IMPLAUSIBLE`. IMPLAUSIBLE(마법·순간이동·세계 밖)은 **거부 아닌 서술 치환**(전투 crFlags.fantasy 철학을 LOCATION에 이식 — prompt-builder `[행동 재해석 지시]` 블록). 기계적 제한은 ②의 난이도 페널티로 자연 발생. "한계=버킷 강제"에서 "한계=그럴듯함 치환/난이도"로 전환.

**경계(정직):** 회색지대(창의·자유 행동)만 nano 확장 — 룰 게이트 행동(FIGHT/PERSUADE 등)은 기본값 유지(FIGHT는 arch/41이 별도 처리). 성공 시 *효과 어휘*(heat/gold/관계/아이템)는 여전히 서버 바운드. ①②③은 "어떤 스탯·얼마나 어렵게·어떻게 서술"만 자유화.

**검증:** 서버 빌드·**1275 passed**(classifier +4·resolve +3)·린트 0. 파일: `challenge-classifier.service`(타입·프롬프트·파싱·검증), `resolve.service`(statHint override·difficultyMod), `turns.service`(배선·actionContext.plausibility), `prompt-builder`(치환 디렉티브), `injected-block-headers`(드리프트 가드 등록).

#### D3-a 흔적(propsState) + B 되짚기 (2026-07-16 구현 · 미커밋)

**출력 측 — 내 행동이 세계에 남는다.** 입력 자유화(위)의 짝. 조사 발견: 세계는 이미 PLAYER_ACTION fact·NpcPersonalMemory로 **기록**은 하나, 물리 흔적은 없고 되짚기는 소극적.

- **A. propsState (흔적 — 신규, nano 추출형):** enum 고정이 아니라 **nano가 서술에서 물리 흔적을 추출**(생성 아님 → 환각 없음, 정형화 회피). `FactExtractorService.extractSceneTrace`(전용 nano, maxTokens 40, killswitch `PROPS_TRACE_DISABLED`) → 워커 fire-and-forget(DONE 이후, 레이턴시 0) → `applyRunStatePatch`(arch/60 fresh CAS)로 `locationDynamicStates[loc].propsTraces` 링버퍼(max 6, 중복·evict). `parseSceneTrace` 엄격 검증(null·서술체 종결·20자 초과 배제, 유닛 9). context-builder가 현재 장소 흔적을 positive 지시로 주입("이 장소에 남은 흔적: … 관련 상황이면 반영, 매 턴 반복 금지"). **narrative-only** — 판정·수치 무영향(불변식 1·2).
- **B. 되짚기 (기존 재사용 + 좁은 확장):** NpcPersonalMemory는 이미 주입 중(만남 로그·trust). 기존 arch/69 B3 지시는 **선제 언급 억제**(부록 M — 잡담 단서 0). 이를 회귀시키지 않도록, **고임팩트 과거 행동(위협/전투/절도/도움/뇌물)만** "상황과 맞물리면 먼저 되짚어도 좋다(새 정보·단서 유출은 여전히 금지)"로 좁게 허용. "네가 나를 협박했잖아"는 되지만 클루 덤핑은 안 됨.

**경계(정직):** 흔적 추출은 LOCATION 턴마다 nano 1콜 추가(async·killswitch). 대사·이동 등 흔적 없는 턴은 nano가 null 반환(비용은 있으나 레이턴시 0). D3-b(WEIRD→suspicion 감정축)·D3-c(공포 행동화)는 미착수 — statHint가 오분류의 스탯 부분만 흡수.

**검증:** 서버 빌드·**1284 passed**(scene-trace +9)·린트 0. 파일: `location-state`(propsTraces 타입), `fact-extractor.service`(extractSceneTrace·parseSceneTrace), `llm-worker`(extractAndStoreSceneTrace CAS), `context-builder`(흔적 주입 + B 되짚기 지시).

**실플레이 검증 + 핫픽스 (2026-07-16, server 944be95):** 12턴 플레이테스트가 결함 2건 실측 — ① `parseSceneTrace`가 "흔적 없음"(부정 접두)을 흔적으로 통과(null 정규식이 정확 매칭만) → 부정 표현 위치 무관 차단. ② 비물리 턴(TRADE/INVESTIGATE)에서 배경 묘사("긁힌 양피지 모서리") 오추출 → **물리 행동(FIGHT/STEAL/THREATEN/SNEAK)·창의(plausibility≠NORMAL) 턴만** 추출 게이트 + 프롬프트를 "이번 턴 플레이어가 만든 변화만"으로 강화. 재검증: 전부 비물리인 10턴 런에서 [SceneTrace] 0·"흔적 없음" 0(과잉 제거 확인), D3 statHint 라이브 정확(TRADE→cha·조사→per). scene-trace.spec +2 회귀 가드. **미확인**: 물리 행동 발생 시 흔적 저장 positive 경로는 게이트 후 전용 재현 안 함(추출·저장 경로 자체는 1차 런에서 발화 실측, 게이트 조건만 변경).

### D4 — 반복 서사 방어 계측 상시화 〔P1 · 계측〕
- 73 §8 n-gram + premise 다양성 + "미해결 스레드 존재 시 신규 스레드 억제" 확인을 playtest 정본 지표로 승격.
- 자율 팩 다회 런에서 "무한 생성되지만 진행 안 됨" 패턴 감시 (3막+인력이 설계상 방어하나 실측 필요 — P8과 통합).

### D5 — 과금 3원칙 등재 〔P0 · 문서만〕
CLAUDE.md 설계 불변식 인근에 등재 (지금 코드 변경 없음, 미래 결정 봉인):
1. **정상 작동은 무료** — 기억·일관성·판정·진행은 과금 등급과 무관하게 동일.
2. **과금은 부가가치만** — 이미지·문체 프리셋·추가 캠페인/팩.
3. **실패 턴 무과금** — 오류·빈 응답·재생성에 비용 차감 금지 (retry-llm 무료 유지).

### D6 — 팩 저작 도구 (장기 백로그)
조사: AI Dungeon의 핵심 경쟁력 = 커뮤니티 콘텐츠·제작 도구. AUTONOMOUS 팩 계약이 저작량을 크게 줄여놔서(장소 7~8 + 코어 6 + 모티프 10 + 톤 매트릭스 — quest.json·이벤트 대량 저작 불필요) **유저 제작의 진입장벽이 AUTHORED보다 훨씬 낮다** — 자율 팩 트랙이 제작 도구의 기술적 기반을 겸한다. 시점: 실플레이어 신호 확인 후.

## 3. 하지 말 것 (조사가 경고하는 함정)

- **기억·일관성을 프리미엄 기능화하지 않는다** — "정상 작동에 과금"은 조사 최악 평가 축.
- **판정을 LLM에 위임하지 않는다** — 불변식 1·2는 시장 검증된 차별점. 자율 트랙이 확장되어도 "생성은 제안, 판정은 서버" 유지.
- **목적 없는 이벤트 남발 금지** — 신규 콘텐츠 생성력(디렉터)이 생겼다고 밀도를 올리면 "무한 생성·무진행" 불만 축으로 직행. 인력·막 예산이 상한.
- **완성도 미달을 AI 탓으로 정당화하지 않는다** — 반복·오류는 AI 특성이 아니라 품질 결함으로 취급 (기존 감사 체계 유지).

## 4. 실행 순서 제안

1. **D5** (문서 등재, 10분) + **D1-(a)(b)** (강제창 가드, 엔진 소) — 즉시.
2. **D2** (판정 투명성 UI) — 클라 소규모, 독립 진행 가능.
3. **D3** (자유도 체감 3종) — 설계 1건 필요 (사물 상태 스코프 확정).
4. **D4** (계측 상시화) — P8과 통합 실행.
5. **D6** — 실플레이어 신호 후 재론.

## 5. 진행 체크리스트 (세션 단절 대비 — 각 항목 완료 시 갱신)

> 코드 작업은 어느 브랜치에서 하든 **완료 시 이 표와 해당 절에 커밋 해시를 기록**한다. arch/75 §15 관례와 동일.

| # | 항목 | 규모 | 상태 | 커밋 |
|---|------|------|------|------|
| D5 | 과금 3원칙 CLAUDE.md 등재 | 문서만 | ✅ | 미커밋 |
| D1-a | 강제창(1.5-C)에서 대화 잠금 활성 턴 제외 | 엔진 소 | ✅ | 미커밋 |
| D1-b | 사교 발화·REST 의도 턴 비트 채택 금지 | 엔진 소 | ✅ | 미커밋 |
| D1-c | P8 계측에 "의도 정합 채택률" 추가 | 계측 | ⬜ | — |
| D1-d | 신규 불변식 D("비트는 정합 시만 — 강제 진행 금지") CLAUDE.md 등재 (불변식 47) | 문서만 | ✅ | 미커밋 |
| D2-a | FREE 판정 스킵 사유 표시 | 클라 소 | ✅ | 미커밋 |
| D2-b | 보정치 출처 분해 노출 (스탯/특기/이벤트/상태) | 서버+클라 소 | ✅ | 미커밋 |
| D2-c | FAIL 턴 "무엇이 부족했나" 표시 | 클라 소 | ✅ | 미커밋 |
| D3-①stat | statHint — 행동-특정 스탯(nano 제안·서버 검증) | 엔진 소 | ✅ | 미커밋 |
| D3-②diff | difficultyMod — 과감함 보정 clamp[-2,2] | 엔진 소 | ✅ | 미커밋 |
| D3-③plaus | plausibility — IMPLAUSIBLE 서술 치환(LOCATION 이식) | 엔진 소 | ✅ | 미커밋 |
| D3-a | 사물 상태 경량(propsState) — nano 추출 흔적 링버퍼 | 엔진 중 | ✅ | 미커밋 |
| D3-B | 되짚기 — 고임팩트 과거 행동 NPC 언급 허용(정보 억제 유지) | 엔진 소 | ✅ | 미커밋 |
| D3-b | 기행 감정축 (WEIRD → suspicion) — statHint가 오분류 일부 흡수 | 엔진 소 | 🅿️ 부분 | — |
| D3-c | 공포 행동화 (fear 임계 → 회피/신고/도주) | 엔진 중 | ⬜ | — |
| D4 | 반복 서사 계측 상시화 (n-gram·premise·스레드 억제 → playtest 정본 지표) | 계측 | ⬜ | — |
| D6 | 팩 저작 도구 | 장기 보류 | 🅿️ 보류 | — |

**이어작업 안내**: 미착수 세션은 §1 대조표(왜)→§2 해당 D절(무엇을)→§3 금지사항 순으로 읽고 착수. D1은 P4 규칙 1.5(server `783d400`, turns.service determineTurnModeCore 1.5절)와 AUTONOMOUS_BALANCE.BEAT_FORCE_AFTER_TURNS가 대상. D3은 arch/75 P5 리뷰의 NPC 반응 평가(npc-emotional ACTION_IMPACT·sudden-action-detector·witness-reaction.core 참조)가 배경.
