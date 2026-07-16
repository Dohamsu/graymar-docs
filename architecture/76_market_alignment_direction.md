# 76. 시장 조사 대응 방향 — "이해하고 기억해주는 경험" 정렬

> 상태: ✅ 구현됨 (D1·D2·D3 + 자유도 체감 A/B + D4·D1-c 계측 + D3-b′/c′/combat 감정·행동화 탈버킷 + 후속 2건[의미 단서 교체·전투 앵커링 해소], 2026-07-16) — 원안 D3-b/c는 폐기·재설계로 대체, 잔여는 §5 미실측 항목 관찰. **P8 1차 캠페인(2026-07-17, arch/75 §19)으로 D4 baseline 확보**(반복률 0.006~0.010·무진행 신호 없음), D1-c 표본 5(정합 2/5 — 계속 축적), 감정 블렌드 실측(런당 2~6명 변동·suspicion 축 활성). REPORT/APPROACH는 무작위 봇 임계 미달로 미발동 — 지향 시나리오 필요. 소유자 제공 시장 조사(AI 텍스트 RPG 이용자 긍/부정 요인)를 현 구조와 대조해 수정 방향을 도출·구현. 조사 원문의 결론: **"내가 상상한 행동을 게임이 이해하고 기억해주는 경험에는 돈을 내지만, AI가 저지른 오류를 내가 계속 수정해야 하는 경험에는 돈을 내지 않는다."**
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

##### 통합 nano 감정 — 보편 적용 (2026-07-16, server 0b1424c)

**기상천외 입력 실측이 룰 게이트 우회 노출:** "고대의 마법 주문으로 불길"을 FIGHT로 표현하면 RULE_CHECK로 nano를 건너뛰어 plausibility 미검사 → **마법이 그대로 재생**("불길이 일렁이며 열기를 뿜어내자")되고 "불길 흔적"까지 저장. 또 "간판을 뜯어냄"이 INVESTIGATE로 오분류돼 물리 흔적 게이트를 놓침.

**해소 — appraisal을 회색지대뿐 아니라 모든 유의미 행동에 보편 적용:** RULE_FREE(구조적 이동/휴식/상점)만 즉결, 나머지(FIGHT 등 포함)는 nano 감정을 타되 **result만 CHECK로 고정**(주사위 스킵 방지), plausibility·statHint·difficulty는 nano 판단. + **physicalImpact(신규)**: "이 행동이 물리 흔적을 남기나"를 nano가 직접 판단 → 흔적 게이트를 actionType 추측이 아닌 nano 판단으로 전환(오분류 우회). IMPLAUSIBLE이면 physicalImpact=false 서버 강제(마법 흔적 차단).

**재검증(동일 기상천외 6입력, 항만):** ① 마법-as-FIGHT → `plaus=IMPLAUSIBLE phys=false`, 서술 재해석("허세 섞인 몸짓과 헛된 외침"), difficultyMod-2로 FAIL, **불길 흔적 미생성** ② 동료 소환 → NPC 자연 거부("부르짖는다고 나타나지 않소") ③ 간판 뜯어냄(INVESTIGATE 오분류) → `phys=true`로 흔적 추출됨 ④ propsTraces 실저장(흩어진 주사위·영수증 조각). classifier +3, 1285 passed. **트레이드오프**: 도전 행동도 감정 nano 호출(killswitch 유지). **잔여**: 빠른 연속 턴에서 CAS 충돌로 흔적 일부 유실(soft data 허용), intent 오분류 자체는 존속(physicalImpact가 우회).

#### D3-a 흔적(propsState) + B 되짚기 (2026-07-16 구현 · 미커밋)

**출력 측 — 내 행동이 세계에 남는다.** 입력 자유화(위)의 짝. 조사 발견: 세계는 이미 PLAYER_ACTION fact·NpcPersonalMemory로 **기록**은 하나, 물리 흔적은 없고 되짚기는 소극적.

- **A. propsState (흔적 — 신규, nano 추출형):** enum 고정이 아니라 **nano가 서술에서 물리 흔적을 추출**(생성 아님 → 환각 없음, 정형화 회피). `FactExtractorService.extractSceneTrace`(전용 nano, maxTokens 40, killswitch `PROPS_TRACE_DISABLED`) → 워커 fire-and-forget(DONE 이후, 레이턴시 0) → `applyRunStatePatch`(arch/60 fresh CAS)로 `locationDynamicStates[loc].propsTraces` 링버퍼(max 6, 중복·evict). `parseSceneTrace` 엄격 검증(null·서술체 종결·20자 초과 배제, 유닛 9). context-builder가 현재 장소 흔적을 positive 지시로 주입("이 장소에 남은 흔적: … 관련 상황이면 반영, 매 턴 반복 금지"). **narrative-only** — 판정·수치 무영향(불변식 1·2).
- **B. 되짚기 (기존 재사용 + 좁은 확장):** NpcPersonalMemory는 이미 주입 중(만남 로그·trust). 기존 arch/69 B3 지시는 **선제 언급 억제**(부록 M — 잡담 단서 0). 이를 회귀시키지 않도록, **고임팩트 과거 행동(위협/전투/절도/도움/뇌물)만** "상황과 맞물리면 먼저 되짚어도 좋다(새 정보·단서 유출은 여전히 금지)"로 좁게 허용. "네가 나를 협박했잖아"는 되지만 클루 덤핑은 안 됨.

**경계(정직):** 흔적 추출은 LOCATION 턴마다 nano 1콜 추가(async·killswitch). 대사·이동 등 흔적 없는 턴은 nano가 null 반환(비용은 있으나 레이턴시 0). D3-b(WEIRD→suspicion 감정축)·D3-c(공포 행동화)는 미착수 — statHint가 오분류의 스탯 부분만 흡수.

**검증:** 서버 빌드·**1284 passed**(scene-trace +9)·린트 0. 파일: `location-state`(propsTraces 타입), `fact-extractor.service`(extractSceneTrace·parseSceneTrace), `llm-worker`(extractAndStoreSceneTrace CAS), `context-builder`(흔적 주입 + B 되짚기 지시).

**실플레이 검증 + 핫픽스 (2026-07-16, server 944be95):** 12턴 플레이테스트가 결함 2건 실측 — ① `parseSceneTrace`가 "흔적 없음"(부정 접두)을 흔적으로 통과(null 정규식이 정확 매칭만) → 부정 표현 위치 무관 차단. ② 비물리 턴(TRADE/INVESTIGATE)에서 배경 묘사("긁힌 양피지 모서리") 오추출 → **물리 행동(FIGHT/STEAL/THREATEN/SNEAK)·창의(plausibility≠NORMAL) 턴만** 추출 게이트 + 프롬프트를 "이번 턴 플레이어가 만든 변화만"으로 강화. 재검증: 전부 비물리인 10턴 런에서 [SceneTrace] 0·"흔적 없음" 0(과잉 제거 확인), D3 statHint 라이브 정확(TRADE→cha·조사→per). scene-trace.spec +2 회귀 가드. **미확인**: 물리 행동 발생 시 흔적 저장 positive 경로는 게이트 후 전용 재현 안 함(추출·저장 경로 자체는 1차 런에서 발화 실측, 게이트 조건만 변경).

#### D3-b′/c′/combat 재설계 — 감정·행동화 탈버킷 (2026-07-16 확정, 원안 D3-b/c 폐기)

**폐기 사유:** 원안 D3-b(WEIRD→suspicion)·D3-c(fear 임계 3종)는 그 자체가 또 하나의 버킷/임계 특수 룰 — D3 탈버킷이 판정 계층에서 해소한 문제를 감정 계층에서 재생산한다. 원칙("플레이어 입력에 다양하게 반응, 누적 기억으로 세계 형성")에 맞춰 통합 nano 감정 패턴으로 일반화한다. 실측 근거 3가지: ① 감정 갱신이 `ACTION_IMPACT` 11-actionType 정적 테이블뿐(내용 무관 — 기행이 TALK로 trust+5) ② NpcReactionDirector가 이미 `emotionalShiftHint`(4축 ±3)를 산출하나 **서버 상태 미적용(죽은 출력)** ③ NPC 능동 행동이 trust 밴드+당턴 목격 경로만(누적 감정의 세계 출구 없음).

**D3-b′ — 감정 탈버킷 (입력측, LOCATION):**
- 통합 nano 감정(ChallengeClassifier — 기존 호출, 신규 콜 0)에 `socialImpact` 확장: 이 행동이 상대·목격 NPC에게 주는 인상을 5축 델타(각 clamp ±5, 서버 검증)로 제안.
- 적용: `applyActionImpact(state, actionType, outcome, direct, nanoImpact?)` — **nano 존재 시** 축별 `round(base×0.4 + nano×2)` 블렌드(테이블=진폭 뼈대, nano=의미 보정), outcome 배율·FAIL 부호 분기·directMod는 기존 유지. nano 부재(파싱 실패·killswitch) 시 기존 테이블 100% — 안전 fallback.
- NpcReactionDirector `emotionalShiftHint` 배선: 워커에서 반응 생성 후 `applyRunStatePatch`(fresh CAS, arch/60)로 대화 NPC 감정에 ±3 보정 적용(다음 턴 반영) — NPC 개별 해석 층. posture 재파생 포함.

**D3-c′ — 감정→세계 행동화 (출력측):**
- 순수 코어 `npc-agitation.core.ts`: 누적 감정 종합+posture → 능동 행동 결정(결정론 — 감정 자체가 이미 nano 판단의 누적이므로 카테고리 매핑은 서버 룰이 불변식 1에 부합). 우선순위 fear > suspicion > trust:
  - fear ≥ 임계(60): FEARFUL/CAUTIOUS → **FLEE_LOCATION**(`ws.npcLocations` 이탈 — 다음 방문 시 부재), 그 외 → **AVOID**(거리두기 디렉티브)
  - suspicion ≥ 60 & trust < -10: HOSTILE/CALCULATING → **REPORT**(Heat+5, 서버 매핑), 그 외 → AVOID
  - trust ≥ 50 & attachment ≥ 30: **APPROACH**(NPC가 먼저 다가와 귀띔 — 긍정 행동화)
- 트리거: 당턴 감정 갱신 직후 eventPrimaryNpc 대상, NPC당 쿨다운(6턴, `npcState.lastAgitationTurn`). **권한 경계**: 당턴 witness 반응 발화 NPC 제외(급성=witness/만성=agitation), 발화·태도 문장은 여전히 NpcReactionDirector 권한 — 본 경로는 세계 결과(Heat/이동/이벤트)+LLM 디렉티브만.
- 시그널 피드 연동은 후속(이벤트+Heat 우선 — 정직 스코프).

**D3-b′-combat — 전투 기만·전술 감정 (전투 확장):**
- 게이트: ACTION && PropMatcher **Tier 3/4**(프롭·카테고리 미매칭 창의 입력) && rawInput 실질 길이 — 평타/버튼 전투는 nano 0회 유지(레이턴시 보호). killswitch `COMBAT_TACTIC_DISABLED`.
- nano 전술 감정: `{tactic: NONE|DISTRACTION|INTIMIDATION|FEINT, plausibility}` — "운석이 떨어진다고 소리침"=DISTRACTION(가능한 거짓말), "운석을 떨어뜨림"=IMPLAUSIBLE(기존 fantasy 재해석). 키워드 테이블이 구분 못 하는 지점을 nano가 커버.
- 서버 매핑(순수 코어 `combat-tactic.core.ts`): DISTRACTION → fleeBonus(성향 가중 평균) + 당턴 적 acc-2 / INTIMIDATION → 겁 많은 적 acc-3 / FEINT → 당턴 명중 +2. **성향 차등**: COWARDLY ×1.5 · AGGRESSIVE/SNIPER ×1.0 · TACTICAL ×0.5 · BERSERK ×0. **동일 tactic 전투 내 1회**(`battleState.usedTactics` — 재사용 시 효과 0 + "더는 속지 않는다" 이벤트).

**구현 반영 (2026-07-16, D3-b′/c′/combat — 미커밋):**
- **D3-b′**: classifier `socialImpact` 5축(±5 clamp, IMPLAUSIBLE 양수 trust 서버 차단, 전 축 0=null) + `applyActionImpact(..., nanoImpact?)` 블렌드(`round(base×0.4 + nano×2)`, nano 부재 시 테이블 100%) + ACTION 턴만 배선(CHOICE는 라벨이라 제외) + 워커 `emotionalShiftHint` CAS 배선(`npcEmotionalShift` 패치, 다음 턴 반영). 유닛: classifier +4, npc-emotional 신설 +7.
- **D3-c′**: `npc-agitation.core.ts`(fear≥60→FLEE/AVOID · susp≥60&trust<-10→REPORT(Heat+5)/AVOID · trust≥50&attach≥30→APPROACH, 쿨다운 6턴) + turns.service 배선(당턴 witness NPC 제외 — 급성/만성 권한 분리) + `ui.npcAgitation`→프롬프트 "[NPC 능동 행동]" 디렉티브(헤더 레지스트리 등록) + FLEE는 `ws.npcFleeOverrides`(untilDay=day+1, **스케줄 재계산이 npcLocations를 매번 재구축해 즉시 쓰기만으론 복귀해버리는 결함 실측** → schedule 우선 적용·만료 정리). 임계·비용은 quest-balance.config. 유닛: agitation +10, schedule 신설 +3.
- **combat**: `appraiseCombatTactic`(nano, killswitch `COMBAT_TACTIC_DISABLED`) + `combat-tactic.core.ts`(성향 민감도 COWARDLY1.5/TACTICAL0.5/BERSERK0) + Tier 3/4 ACTION 게이트(버튼·평타 nano 0) + combat.service 소비(FLEE 보너스 합산·적 acc 디버프·FEINT 명중+2·TACTIC 이벤트). 유닛: tactic +6.
- **부수 버그 수정(기존)**: `getAmbushEncounterId`가 팩에 없는 `enc_generic`을 반환 → 무기 위협(KILL_ATTEMPT) 전투 전이가 **500 크래시**(graymar 실측, 검증 중 발견). 존재 검증 후 팩 첫 encounter fallback (content-loader 단일 지점 규약).

**후속 — R2 어휘 인용 가이드 → 의미 단서 교체 (2026-07-16, 미커밋):** 운석 기만 턴 서술이 가짜 운석을 폭발음·진동으로 **반쯤 실체화**하는 결함 실측. 원인 3중주: ① R2 키워드 가이드(A51)가 거짓 외침 속 단어('떨어진다')를 콕 집어 인용 지시 ② 감각 초점(청각+촉각)이 폭발음·진동 채움 유도 ③ "기만이 통했다" 이벤트에 해석 규칙 부재. 소유자 방향("어휘 주입 대신 전후 상황 단서")에 따라 **기만턴 특수 분기 없이 일반 교체**: 낱말 리스트 지시 삭제(`extractTopUserKeywords` 제거) → "주제 반영 + 입력 속 주장·외침은 '말한 것'일 뿐, 정본은 [이번 턴 사건]·판정" 의미 가이드로 대체 + `actionContext.appraisalNote`(LOCATION=nano reason, COMBAT=기만 성격 문장 — 동일 채널)를 가이드에 병기. 재검증: 운석 실체화 완전 소멸("외치자 … 적들은 하늘을 올려다보았고 … 하늘을 쳐다보는 게 무의미하다는 듯 돌아섰다"). **관찰**: R2 제거가 응답률(NPA)에 주는 영향은 다회 계측 몫 — 질문 우선 블록·주제 반영 지시가 잔존 방어.

**후속 — 전투 턴 장소 NPC 앵커링 해소 (2026-07-16, 미커밋):** FEINT 검증에서 전투 중 오웬이 유일 화자로 등판·서버 이벤트와 모순 대사("페인트가 통했다" vs "속임수는 통하지 않소") 실측. 원인 4단 연쇄: ① **triggerCombat 조기 커밋이 actionHistory 기록(정상 지점보다 앞) 건너뜀** → FIGHT 턴 이력 누락 (DB 실측 `["BRIBE","TALK"]`) ② 대화 잠금이 직전 TALK 기준 오산출("오웬과 2턴째 연속 대화 중" — 불변식 26이 데이터 누락으로 무력화) ③ [대화 연속 상태]+R6("이 턴은 오웬만 말합니다")가 COMBAT 턴에 그대로 주입(연속 블록 게이트가 `!isHub`뿐) ④ 전투 서술 초점 디렉티브 부재. 수정 A+B: **A** 전투 전이 분기에 actionHistory 기록 추가(이력 소비자 전반 — 고집·중복 방지 — 도 복구) / **B** prompt-builder `isCombat` 게이트(대화 잠금·직전 발화 이어받기·focused·턴 카운터 4블록) + `[전투 장면 — 서술 초점]` positive 디렉티브(헤더 등록). 재검증: 서술 중심이 적(깡패 표정·후퇴)으로 이동, 주변 인물은 배경 반응, 오웬 대사 소멸. **잔여 관찰**: 배경 인물 1명 짧은 대사("잡아라!") — soft 위반, 다회 계측 몫.

**실런 검증:** ① 위협 누적 → 오웬 fear 100·posture FEARFUL → **T13 `[NPC_AGITATION, FLEE_LOCATION]` 발동**·ui 전달 ② 기행-as-TALK에서 suspicion 상승·trust 억제(블렌드 실측) ③ KILL_ATTEMPT → COMBAT 전이(크래시 해소 확인) → "운석이 떨어진다!" 외침 → **nano DISTRACTION 분류** → 상대가 BERSERK 해적 2체라 민감도 0 → "아무도 속지 않았다" 이벤트(**성향 차등이 설계 그대로 발화**) → 도주 성공. 전체 1318 passed·린트 0. **미실측**: REPORT/APPROACH 발동(유닛만)·npcFleeOverrides 실런 지속(스케줄 유닛으로 커버)·COWARDLY 상대 기만 보너스 실효.

### D4 — 반복 서사 방어 계측 상시화 〔P1 · 계측〕
- 73 §8 n-gram + premise 다양성 + "미해결 스레드 존재 시 신규 스레드 억제" 확인을 playtest 정본 지표로 승격.
- 자율 팩 다회 런에서 "무한 생성되지만 진행 안 됨" 패턴 감시 (3막+인력이 설계상 방어하나 실측 필요 — P8과 통합).

**구현 반영 (2026-07-16, D4 + D1-c — 미커밋):** `scripts/playtest.py`에 "서사 방향 계측" 섹션 신설(리포트+JSON `directionMetrics` 저장, **게이트 아님** — baseline 축적 전 임계 미설정). ① **D4-1 n-gram 반복률**: 턴 간 3-gram 중복 비율 + 인접 턴 자카드 평균(@마커 제거 후 한글 word-gram). ② **D4-2 이벤트·premise 다양성**: 매칭 소스 히스토그램(BEAT/SIT/PROC/EVT/FREE_*) + distinct eventId 비율. ③ **D4-3 스레드 억제**: 생성 시점 미해결 스레드 2+ 공존한 신규 스레드 수 — **post-hoc 근사**(최종 status·lastTurnNo로 당시 생존 추정)이며 PlayerThread가 플레이어 행동 패턴 자동 파생이라 봇 무작위 행동 영향 포함(해석 주의). ④ **D4-4 무진행 감시**: plotProgress 채택/폐기/keyFact 대비 — 채택 3+ & fact 0이면 stall 플래그.

**D1-c 구현(서버+계측):** 채택 시 `plotProgress.beatAdoptions[]`에 {turnNo, beatId, actionType, aligned, premise 60자} 기록(계측 전용, 판정 무영향). `aligned` 정의: 비트 affordances ∋ actionType = true / 지정·불일치 = false / **미지정(행동 무관 비트) = null → 정합률 분모 제외**. 순수 헬퍼 `isBeatIntentAligned`(beat-gravity.ts) + 유닛 3종. playtest가 정합률·premise 다양성(채택 premise 간 2-gram 자카드 역수)을 리포트.

**실측 (카른홀트 12턴 1런):** 채택 3·폐기 0·keyFact 3(무진행 아님), **정합률 33%**(일치 1/불일치 2/무관 0), premise 다양성 1.00, 3-gram 반복률 0.005, 스레드 억제 위반 3건. 표본 1런이라 판단 유보 — 단 **affordance 불일치 채택이 구조적으로 가능함**(장소+fact 보너스만으로 `BEAT_ADOPT_MIN_SCORE` 도달)은 확인. 채택 임계에 affordance 정합을 필수화할지는 다회 축적 후 별도 결정(지금은 계측만 — D1 목적은 관찰). AUTHORED(graymar) dry-run에서 신규 섹션 무해 확인(자율 데이터 없음 안내). 서버 1288 passed·린트 0.

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
| D5 | 과금 3원칙 CLAUDE.md 등재 | 문서만 | ✅ | docs 0bd41f9 |
| D1-a | 강제창(1.5-C)에서 대화 잠금 활성 턴 제외 | 엔진 소 | ✅ | f7a92b6 |
| D1-b | 사교 발화·REST 의도 턴 비트 채택 금지 | 엔진 소 | ✅ | f7a92b6 |
| D1-c | P8 계측에 "의도 정합 채택률" 추가 | 계측 | ✅ | 미커밋 |
| D1-d | 신규 불변식 D("비트는 정합 시만 — 강제 진행 금지") CLAUDE.md 등재 (불변식 47) | 문서만 | ✅ | docs 0bd41f9 |
| D2-a | FREE 판정 스킵 사유 표시 | 클라 소 | ✅ | f7a92b6·client af4b065 |
| D2-b | 보정치 출처 분해 노출 (스탯/특기/이벤트/상태) | 서버+클라 소 | ✅ | f7a92b6·client af4b065 |
| D2-c | FAIL 턴 "무엇이 부족했나" 표시 | 클라 소 | ✅ | client af4b065 |
| D3-①stat | statHint — 행동-특정 스탯(nano 제안·서버 검증) | 엔진 소 | ✅ | f7a92b6 |
| D3-②diff | difficultyMod — 과감함 보정 clamp[-2,2] | 엔진 소 | ✅ | f7a92b6 |
| D3-③plaus | plausibility — IMPLAUSIBLE 서술 치환(LOCATION 이식) | 엔진 소 | ✅ | f7a92b6 |
| D3-univ | 통합 nano 감정 — plausibility·physicalImpact 보편 적용(룰 게이트 우회 해소) | 엔진 소 | ✅ | 0b1424c |
| D3-a | 사물 상태 경량(propsState) — nano 추출 흔적 링버퍼 | 엔진 중 | ✅ | f7a92b6·핫픽스 944be95 |
| D3-B | 되짚기 — 고임팩트 과거 행동 NPC 언급 허용(정보 억제 유지) | 엔진 소 | ✅ | f7a92b6 |
| D3-b′ | 감정 탈버킷 — socialImpact + shiftHint 배선 (원안 D3-b 폐기·재설계) | 엔진 중 | ✅ | 미커밋 |
| D3-c′ | 감정→세계 행동화 — agitation 코어 + Heat/도주/디렉티브 (원안 D3-c 폐기·재설계) | 엔진 중 | ✅ | 미커밋 |
| D3-cb | 전투 기만 전술 — tacticalImpact nano + 성향 차등 + 1회 감쇠 | 엔진 중 | ✅ | 미커밋 |
| D4 | 반복 서사 계측 상시화 (n-gram·premise·스레드 억제 → playtest 정본 지표) | 계측 | ✅ | 미커밋 |
| D6 | 팩 저작 도구 | 장기 보류 | 🅿️ 보류 | — |

### 5.1 다음 세션 이어작업 (2026-07-16 인계)

**배포 상태 (프로덕션):** server `0b1424c`(launchd 3000, `/v1/version` 확인) · client `af4b065`(미배포·D2 UI) · docs `2491b51`. **push 안 함** — 로컬 3레포 main 커밋만. 전체 1285 passed, 린트 0.

**완료 (D1·D2·D3 + 자유도 체감 A/B):** 강제창 의도 존중(불변식 47)·과금 3원칙·판정 투명성(보정 분해/FAIL 부족분/FREE 스킵)·actionType 탈버킷(통합 nano 감정: statHint·difficultyMod·plausibility·physicalImpact)·물리 흔적(propsState nano 추출)·되짚기. 기상천외 입력 실측으로 마법-as-FIGHT 재생·흔적 과잉·오분류 우회까지 해소 검증.

**완료 (감정·행동화 탈버킷, 2026-07-16 미커밋):** 원안 D3-b/c 폐기 → D3-b′(socialImpact 감정 블렌드 + shiftHint 배선)·D3-c′(agitation 코어 + Heat/도주 오버라이드/디렉티브)·D3-cb(전투 기만 전술 + 성향 차등) 재설계 구현. §2 D3-b′/c′/combat 재설계 절 참조. 부수: enc_generic 500 크래시 수정. **남은 관찰**: REPORT/APPROACH 실런 발동·COWARDLY 기만 보너스 실효·감정 블렌드 일관성(NPA 감정축 다회 계측).

**완료 (계측 트랙, 2026-07-16 미커밋):** D4 서사 방향 계측 4종(`playtest.py` §4.5 + `directionMetrics` JSON) + D1-c 의도 정합 채택률(서버 `plotProgress.beatAdoptions` + `isBeatIntentAligned`). 카른홀트 12턴 실측: 정합률 33%(표본 1런), affordance 불일치 채택이 구조적으로 가능함 확인 — 다회 축적 후 임계 필수화 여부 별도 결정. §2 D4 구현 반영 절 참조.

**잔여 관찰(비차단):** ① propsTrace가 빠른 연속 턴에서 CAS 충돌로 일부 유실(soft data 허용) ② intent 파서 오분류("간판 뜯어냄"→INVESTIGATE) 존속 — physicalImpact가 흔적은 우회하나 NPC 반응 매핑엔 영향. 근본 교정은 intent parser 튜닝(별도 트랙).

**killswitch:** `CHALLENGE_CLASSIFIER_ENABLED`(감정 전체), `PROPS_TRACE_DISABLED`(흔적 추출), `PLOT_DIRECTOR_DISABLED`(자율 디렉터).

**참고:** 미착수 항목은 §1 대조표(왜)→§2 해당 D절(무엇을)→§3 금지사항 순으로 읽고 착수. 기상천외 입력 재현은 커스텀 rawInput 테스트가 필요(playtest.py는 자동 생성 행동만) — GLADIATOR 프리셋 + go_harbor 진입 + 파괴/마법/소환 입력 조합이 회귀 검증 세트.
