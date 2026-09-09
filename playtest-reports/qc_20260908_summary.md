# 품질 사이클 3회차 (2026-09-08)

전제: 보안 감사 후속 배포 직후(server `814e786`, Solar Pro 4 전턴). 페르소나·팩 로테이션 — ① graymar·chatty ② star_sand·coercer ③ (아래).

## 1회차 (graymar · chatty · SMUGGLER, run c9f7020f, 10턴) — 수정 2건 + 하네스 회귀 1건

게이트 14/15 (V9 어휘 반복 FAIL — 단일 런 계측, 직전 사이클과 동형 노이즈). 정독 14턴 전문.

| # | 증상 | 결정적 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 1-A | **이동 턴에 NPC 가 퇴장** — "다른 장소로 이동한다" 턴 서술이 에드릭이 일어나 문고리를 잡고 "아래층 돌계단·복도" 로 나가는 장면 + "장면이 접힌다" | T8: `그가 일어나 문고리를 잡는다. … 아래층 돌계단을 향한 발소리가 복도에 짧게 울리고, 걸음이 골목을 향해 멀어지며 장면이 접힌다.` 30일 MOVE_LOCATION 턴 57건 표본 6건 중 2건 동형 | `[이동 전환 턴]` 지시에 **떠나는 주체가 없음** — "지금 장소를 떠나는 과정" 만 있고 직전 화자 대사·프레이밍이 NPC 를 행위자로 앵커 | **수정** `prompt-builder.service.ts` 이동 전환 지시에 "떠나는 사람은 당신(플레이어) — 이 장소의 인물은 자리에 남고 그들의 퇴장·이동은 서술하지 않는다" 명시 |
| 1-B | **거점 복귀 셸이 방금 떠난 곳으로 향함** — 시장→거점 복귀 턴이 "거점을 벗어나 시장 거리로 향하는 갈림길이 가까워진다" | T9 HUB SYSTEM MOVE 턴. 프롬프트에 `⚠️ 이동 중 … 도착지를 묘사하지 않습니다` 와 함께 `[참고 선택지] - 시장 거리로 향한다 …` 목록이 동시 주입. 30일 복귀 셸 192건 중 목적지 명시 2건(1%), **'갈림길' 모티프 68건(35%)** | 선택지 경계 블록이 노드 타입 무관 주입 — 복귀 셸에서는 지시와 데이터가 모순 | **수정** `isHubReturnShell`(HUB + MOVE 이벤트) 이면 `[참고 선택지]` 블록 생략. 골든 스냅샷 014_HUB_t14 갱신(diff = 블록 10줄 제거뿐) |
| 1-C | **V12 프롬프트 예산 게이트 스킵** — "프롬프트 표본 없음 (includeDebug 미보존?)" | 보안 감사 M1 로 `includeDebug` 의 `llmPrompt` 가 프로덕션에서 null | 하네스가 플레이어 권한으로 시스템 프롬프트를 읽던 경로에 의존 | **수정** `turns.controller` 가 `x-admin-token`(timingSafeEqual) 동반 요청에만 `debugAuthorized` 로 llmPrompt 반환, `playtest.py` 는 admin 헤더 첨부. 플레이어 요청은 계속 null |

재확인(기존 트랙): 유령 수치 단서("전체의 서른여섯 갑절", "어제 일곱 닢·그제 아홉 닢" — qc_series 잔여 #5), 어체 HAOCHE→해체 침투 1건(`…문제지.` T6, R5v2 맵 트랙), 호칭 대명사 "무엇을 확인하시겠습니까, **당신**."(arch/113 v2 호칭), 선택지 라벨 에코("당신이 아까 내 말에 더 관심을 둔다니"), 이동 턴 무명 인물 대사 1줄(arch/68 부록 K 즉흥 무명 대사), 경비대 본부 서술에 부두 소품(창문 너머 부두·젖은 화물 상자 — 장소 소품 혼입 관찰), "갈림길" 모티프 반복(V9 계열). 정합 확인: 에드릭 자기소개 3턴 임계(CALCULATING) T6 정상, questReveal 2건(FACT_LEDGER_EXISTS observe / FACT_MAIREL_GUARD_EVIDENCE direct·주제 매칭) 서술 = 기록.

**재검증(프로브 run 94b77b31, 서버 재기동 후)**: 이동 턴 `회계사의 손끝에 묻은 잉크 냄새가 엷게 가라앉고, 당신은 그 자리를 떠난다 … 당신은 걸음을 옮긴다` (주체 = 플레이어 ✓), 복귀 셸 목적지 낭독 없음 ✓(갈림길 어휘는 잔존), `llmPrompt` 무헤더 null · 어드민 헤더 10,147자 ✓, 프롬프트에 `[참고 선택지]` 부재 · `떠나는 사람은 당신` 존재 ✓. 전체 jest 2,586 passed.

## 2회차 (star_sand · coercer · SS_SURVIVOR, run a91ffe78, 10턴) — 수정 3건

게이트 **15/15** (V12 프롬프트 표본 수집 복구 확인 — 1-C 효과). 1회차 수정 자연 재현: T8 이동 턴 "당신은 자리에서 일어난다 … 여관 주인이 당신을 배웅하지 않는다"(주체 = 플레이어), T9 복귀 셸 3문장·목적지 낭독 없음.

| # | 증상 | 결정적 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 2-A | **군중의 반말 대사 2줄이 이렌(해요체)에게 귀속** → 어체 위반 2건 | T7 원문(ai_turn_logs raw): `낯선 목소리 둘의 낮은 말이 벽 안쪽에 스치듯 걸린다.` 뒤 무라벨 `"또 그 문장이라던데."` `"누군가 남긴 거 말이지."` → 저장본 `@[이렌\|NPC_SS_IREN] "또 그 문장이라던데."` | arch/113 화자 연속 귀속의 군중 신호 `CROWD_CUE_RE` 가 `목소리가` 만 알고 **복수·낯선 목소리**("목소리 둘", "낯선 목소리", "낮은 말이")를 몰랐다 | **수정** `speaker-continuity.core.ts` CROWD_CUE_RE 에 `목소리 (둘\|셋\|몇)`·`낯선 (목소리\|이\|사내\|여인\|손님)`·`낮은 말이` 추가 + 스펙 3케이스 |
| 2-B | **부두 도착 셸에 "시장 한쪽에서 들린 수군거림:"** — 부두인데 출처가 시장 | T11: `시장 한쪽에서 들린 수군거림: 죽은 이들이 사라진 자리에 꿈만 남는다더군.` 30일 **35턴**이 `시장 (곳곳\|한쪽)에서 … 수군` 축자, 22턴이 `수군거림이 떠돈다\|수군거림: ` | `[무명 화자 프레이밍]` 지시의 완성문 예시 `"시장 곳곳에서 ~라는 수군거림이 떠돈다" 식으로` 가 anchor (arch/105 P0-3·불변식 50 동형 — 이 예시만 남아 있었다) | **수정** 예시 제거 → 구성 요소 지시("이 장소의 구체 지점(어느 자리·어떤 무리)에서 흘러온 말 조각 … 다른 장소 이름을 출처로 쓰지 않기"). 골든 스냅샷 003·013 갱신(diff = 이 문장뿐) |
| 2-C | 코드형 쓰레기 토큰 `없다..join하는 몸짓` | T2, 30일 1건 | Solar 디제너레이션 — 기존 stripModelJunkCore (a)~(i) 가 마침표 뒤 한글에 붙은 소문자 토큰을 안 잡음 | **수정** (j) `(?<=[가-힣.,])\.?[a-z]{2,12}(?=[가-힣])` 제거(마침표 보존) + 스펙(URL 비영향) |

재확인(기존 트랙): HUB `go_ss_dock` 턴이 "꿈잠 여관의 나무문을 등 뒤로 닫자" 로 두 턴 전 출발을 재서술(장면 경계 A축), 선택지 라벨 에코("방금 하신 말씀…"), 마커 인라인 산문(arch/113), 오탈자·문법 잔해("홀드의 공기", "잔실이", "바람도 없는데요") 관찰, 작별 뒤 대사("길 잃지 않게 신중하세요" — 이미 문밖) 1건. 정합 확인: 토바 `그녀` = 콘텐츠 female ✓, FACT_SS_FIRST_DREAM direct·주제 매칭 ✓, coercer 압박 T7 nano POLITE 거절 + FAIL 판정이 "목이 먼저 막히네요" 로 번역 ✓, 인계 힌트(등불수녀원 수녀) ✓.

재검증: 2-A 는 단위 스펙(군중 신호 3케이스 + 기존 연속 귀속 유지), 2-B 는 앵커 제거라 다음 런에서 `시장 … 수군` 부재로 관측, 2-C 스펙. 표적 jest 203 passed, 서버 재기동.

## 3회차 (graymar · weirdo · HERBALIST, run e5aabc0f, 10턴) — 수정 3건

게이트 14/15 (V9 어휘 반복 — 페르소나 특성상 `날카로운 회계사`·`탁자` 집중, 계측 노이즈). 2-B 관측: 이 런에 `시장 (곳곳|한쪽)에서 … 수군` 0건. 정독 14턴.

| # | 증상 | 결정적 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 3-A | **기행 턴이 단서를 낙하** — "탁자 위로 점핑하면서 춤을 춘다, '나는 왕의 사촌이다!'" 가 FACT_LEDGER_EXISTS(T4)·FACT_OFFICIAL_INQUIRY(T12) 를 발견 | `[Quest] Fact discovered: FACT_OFFICIAL_INQUIRY (source: event:SIT_ACTIVITY_NPC_MAIREL…)`, parsedType TALK · resolveSkipped true · matchedByTopic false. 30일 `TALK·FREE·observe·비주제` 공개 13건 | 이벤트 경로 1 = "SUCCESS 면 discoverableFact 자동 발견" 인데 ChallengeClassifier FREE 가 자동 SUCCESS 라 무관 대화도 통과 — 불변식 44(대화 계열은 주제 매칭 시에만)가 이벤트 경로엔 없었다 | **수정** `location-quest.service` 경로 1 에 `freeAutoSuccess && 대화 계열(TALK/PERSUADE/HELP/TRADE/REST/SHOP) && 키워드 무매칭` 이면 스킵(로그 `event fact skipped`). 호출부가 `challengeDecision.result==='FREE' && !refused && !worldNoGain` 전달. 스펙 4케이스(`location-quest.free-dialogue-gate.spec.ts`) |
| 3-B | **기록된 fact 가 서술에 없음** — T12 questReveal=FACT_OFFICIAL_INQUIRY 인데 마이렐 대사는 체통 훈계뿐 | T12 프롬프트: nano `[정보 전달] 관찰을 통해 암시합니다` 만 있고 fact 본문 블록 없음 + `[NPC 일상] … 단서·사건·임무 화두 금지` 동거. `server_result.ui.resolveOutcome` 이 FREE 턴엔 비어 있음(`hideResolve`) | context-builder 의 arch/58 주입 게이트가 `outcome ∈ {SUCCESS, PARTIAL}` 를 요구하는데 FREE 턴은 UI 배너용 outcome 을 숨겨 undefined → 블록 미주입(30일 FREE 공개 ≈80턴 동형). 구 02337e51 수정은 rumor 만 구제 | **수정** `context-builder` 가 `resolveSkipped` 면 `factOutcome='SUCCESS'` 로 간주해 주입 |
| 3-C | **보유자 밖·4단계 앞선 fact 를 활동 이벤트가 관찰 공개** — 마이렐(knownFacts: INSIDE_JOB)이 knownBy=[GUARD_CAPTAIN, LORD_VANCE]·stage S4→S5 인 OFFICIAL_INQUIRY 를 T12(questState S1) 에 | 30일 공개 132건 중 현재 단계+2 이상 **31건(23%)**, 보유자 불일치 7건 | SituationGenerator 가 장소 저작 템플릿(discoverableFact 포함)을 스케줄 NPC 활동 이벤트에 그대로 얹음 — 보유자·단계 무관 | **수정(보유자만)** `findTemplatePreferFact(…, npcId)` 보유 fact 템플릿 우선 + 미보유면 활동 이벤트의 discoverableFact 제거(로그 `[SitGen] discoverableFact … 제거`). **단계 게이트는 미적용** — NPC 경로 조기 공개(31건 대부분 direct/indirect)는 "자유 순서 탐색" 설계와 맞물려 소유자 판단 사항 |

재확인(기존 트랙): 기행 입력 nano 분류 흔들림(같은 문구가 TALK/FIGHT/BRIBE — qc_series 잔여 #2), 유령 수치("삼백이십칠 장", "지급란 열세 칸·열두 묶음", "36.7퍼센트" — #5), HUB `go_*` 이동 턴에 NPC 등장·대사(T2 조용한 실무자 반말 1건; 30일 545건 중 마커 131건 24% — 지시 "인물 조우·대사는 다음 턴" 의 soft 한계, A축), 이동 턴 NPC 대사 1줄("그럼 가시오"), 복귀 셸 "시장 쪽 길이 갈라지는 지점"(1-B 잔존 1건), 프리셋 리터럴 앵커("풀 냄새가 밴 손등·약초 냄새"), 마감 따옴표 파손 1건(`"…그대."그대가 진짜…` — E축).

**재검증**: 3-A 스펙 4/4(FREE·TALK·비주제 스킵 / 판정 SUCCESS 는 종전 / 키워드 매칭 시 발견 / OBSERVE 는 비대상). 라이브 프로브 2회는 nano 가 기행을 FIGHT·BRIBE 로 분류해 이벤트 경로가 열리지 않아 **게이트 자체를 라이브로 못 밟았다**(BRIBE 공개 턴엔 fact 블록 주입 확인 — 3-B 의 CHECK 경로 정상). 3-B FREE 경로·3-C 는 다음 런 관측(로그 `event fact skipped` / `[SitGen] … 제거`). 전체 jest **2,588 passed**, 서버 재기동 3회.

## 총괄

| 회차 | 팩·페르소나 | 게이트 | 수정 | 재확인 |
|---|---|---|---|---|
| 1 | graymar·chatty | 14/15 | 이동 턴 주체 명시 · 복귀 셸 [참고 선택지] 제외 · 하네스 llmPrompt 어드민 게이트 | 6 |
| 2 | star_sand·coercer | 15/15 | 군중 신호 확장 · "시장 곳곳" 앵커 제거 · 코드형 토큰 필터 | 5 |
| 3 | graymar·weirdo | 14/15 | FREE·대화 이벤트 fact 게이트 · FREE 턴 fact 본문 주입 · 활동 이벤트 보유자 게이트 | 7 |

게이트가 잡은 결함 0, 전부 정독. 사이클 간 확인: 1회차 수정 두 건은 2·3회차에서 자연 재현, 2-B 앵커는 3회차 0건.

**커밋됨 — server `96e9d5a`** (2026-09-08): server 12 파일 + 신규 스펙 1 (`situation-generator`·`context-builder`·`narrative-filter.core(+spec)`·`prompt-builder(+snap)`·`speaker-continuity.core(+spec)`·`location-quest`·`location-turn`·`turns.controller`·`turns.service`·`location-quest.free-dialogue-gate.spec`), docs `scripts/playtest.py`, 이 보고서(gitignore).

**소유자 판단 요청**: 단계 앞선 fact 조기 공개(23%) 에 단계 게이트를 둘지 — 두면 탐색 자유도가 줄고, 안 두면 "미조우 개체·종반부 단서 조기 발화" 가 정독 체크리스트 1번으로 계속 잡힌다.

---

# 품질 사이클 2차 시리즈 — 4~6회차 (2026-09-08 오후)

전제: arch/114 리팩토링(server `3656c03`) 배포 직후 — T1·T2·T3 회귀 관측 겸용. 로테이션: ④ star_sand·chatty ⑤ graymar·devotee ⑥ (아래). 테스터 잔액 충전 코드 `9L4F-JCBT`(500p×3, 1회 사용).

## 4회차 (star_sand · chatty · SS_PILGRIM, run ac289514, 10턴) — 수정 3건

게이트 **15/15**. 정독 13턴 전문. arch/114 회귀 징후 없음(단계 파이프라인·CAS·블록 레지스트리 경유 서술 정상, 스모크 PASS).

| # | 증상 | 결정적 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 4-A | **별빛모래 런 서술에 그레이마르 NPC 실명 "로넨"** — 주인공 지칭으로 등장 | T2(go_ss_inn): `로넨이 이 여관에 들어오는 건 처음이지만 문 앞에 선 순간만큼은 …`. 캐릭터 이름 미지정 런. 프롬프트 grep: 모든 턴 시스템 프롬프트에 `로넨` 3회 | `system-prompts.ts` P0-A 예시 `"로넨이 고개를 숙인다."`·P1-D 예시 `"로넨은 두려움을 느꼈다" ❌ → "로넨의 손이 …"`·형식 금지 예 `- 로넨: 대사` — 엔진 코드에 콘텐츠 표시명 리터럴(불변식 45) + 완성문 예시 앵커(불변식 50). 30일 star_sand 923턴 중 1턴 실현(이 런) — 빈도는 낮으나 팩 무관 상시 주입 | **수정** 3곳을 역할 명사(행인·노인)로 교체. 골든 스냅샷 17건 갱신(diff = 이 3줄뿐) |
| 4-B | **"주민에게 말을 건다" 기본 선택지가 설득 판정** — 인사 턴에 주사위 + `triumph` 톤 | T4·T12 parsedType=PERSUADE·resolve SUCCESS·toneHint=triumph. 30일 동일 라벨 **99턴 중 92턴 PERSUADE**(SUCCESS 54 = triumph 톤 / PARTIAL 37 / FAIL 1 — 인사가 38% 실패·부분). "경비병에게 접근한다" 42턴(FAIL 3·PARTIAL 16)·"상인에게 소문을 묻는다" 41턴(FAIL 9) 동형 | `scene-shell.service` 기본 선택지 `explore_talk` 외 8종(`market_talk`·`guard_talk`·`harbor_talk`·`slums_talk`·`fu_grd_p_retry`·`fu_enc_p_retry`·`fu_enc_s_deepen`·`fu_grd_s_use`)의 `affordance: 'PERSUADE'` 가 `choice-challenge.core` ALWAYS_CHECK 에 걸려 인사에도 즉결 CHECK. 최초 HUB 커밋(726bbee) 이래 원안 | **수정 (5회차에서 재설계)** — 1차안 "affordance TALK 전환" 은 **철회**: 같은 라벨 99턴 중 71턴(72%)이 저작 이벤트(PERSUADE affordance) 매칭이라 TALK 로 바꾸면 첫 진입 이벤트 funnel 이 끊긴다(EXPLORE_ACTIONS 에도 없음). 최종안: 저작 접근 선택지 9종에 `riskLevel: 1` 선언 + `choice-challenge.core` 가 "저작(비nano) PERSUADE + riskLevel 1" 을 ALWAYS_CHECK 면제 → 판돈 규칙(미발견 fact·BLOCK·라벨 주제·riskLevel≥2)만 적용, 없으면 FREE. affordance·이벤트 매칭·V13 집계 불변. 스펙 3(면제 FREE / fact·BLOCK 은 CHECK / nano PERSUADE 는 CHECK 유지) |
| 4-C | **nano `[첫 문장]` 이 인물 감정 완성문** — 우호 NPC 에 "차갑게", 밝은 홀에 "어둠 속" | T6 프롬프트 `[첫 문장] "이렌의 눈빛이 차갑게 빛난다."`(이렌 FRIENDLY·trust 69) → 서술 첫 줄 축자 복제. T4 `"어둠 속에서 희미한 목소리가 들려온다."`(새벽 등불 켜진 홀) 축자. 30일 `[첫 문장]` 1,687턴: 축자 첫 줄 142(8%)·본문 어딘가 포함 924(55%)·**인물 감정 문형(눈빛·차갑게·날카롭게·긴장감·굳은) 333(20%), 그중 229(69%) 복제**. 최빈 opening: "이렌의 눈빛이 잠시 흔들리며 긴장감이 감돈다"·"장교의 눈빛이 날카롭게 빛난다" | NanoEventDirector `RULE_OPENING` 은 "감각 묘사" 인데 nano(4.1-nano)가 인물 감정 클리셰를 내고, 서버 가드(3·NanoConceptGuard·지목 불일치)가 이 유형을 안 잡음. NpcReactionDirector 가 톤 3축을 이미 결정하므로 이 채널은 감정 이중 채널(2026-08-14 잔여 백로그)의 실체 | **수정** `nano-event-director` 가드 3b `OPENING_EMOTION_CLICHE`(눈빛·눈매·표정·차갑게·날카롭게·긴장감·굳은·굳어·경계심·미소) → opening 비움 + `[NanoOpeningGuard]` 로그 + RULE_OPENING 을 positive 로("환경 감각 하나로 연다, 인물 눈빛·표정·감정 금지"). 스펙 1(억제 2·유지 1). **5회차 실발동에서 오탐 정정**: 첫 배포가 "이른 새벽 공기가 차갑게 느껴지고"(환경 온도)를 억제 → 패턴을 인물 문형(눈빛·눈매·표정·미소·경계심·긴장감·`시선/목소리가 차갑/날카롭/굳`·`얼굴이 굳`)으로 좁힘, 30일 적용률 328/1,692(19%)·환경 "차갑" 75건 통과. 회귀 스펙 +2 |

재확인(기존 트랙): nano `[톤]` "긴장감" 30일 872/1,687(52%) — 서버 toneHint=calm 인 턴에서도 148건(감정 이중 채널 백로그, 수치만 갱신) · 이동 턴 이렌 대사 어체 위반 1(HAEYO→합쇼 "알려드리지요/미끄럽습니다", R5v2 트랙) · **이동·HUB 턴 성별 대명사 drift**(T1 "그는/그녀의" 혼용, T8 "그의 손끝" — female. `[등장 가능 NPC 목록]` 의 `[ID, 여, 대명사:그녀]` 태그가 대화 턴(T4·T6)에만 있고 이동 턴 프롬프트엔 부재 — 관찰 등재) · T10 도착 턴 전문 과거형 + "너는"(30일 1/3,493, Solar drift) · T9 복귀 셸 "어제 저녁 문을 나설 때"(방금 나섬, 시간 착오) + "갈림길" 모티프 · T13 "검은얼음 시장에서 넘어온 듯한 종이 조각" 유령 소품 · T5 "제가 지금 묻는 것에" 인칭 오류(Solar 문법 트랙) · 토바 T10 인사 후 T12 화자 아바스(미완결 등장 트랙, 토바는 스케줄상 현장 ✓).

정합 확인: FACT_SS_FIRST_DREAM(T6)·FACT_SS_SAME_WORDS(T7) direct·주제 매칭 = 서술 ✓ · '눈이 아직 바다를 보고 있다' 는 프롤로그(scenario.json 이렌 대사)에서 선지식 → nano 라벨 노출은 단서 누출 아님 ✓ · T13 FREE·TALK·비주제 → questReveal 없음(3회차 3-A 게이트 자연 재현 ✓) · 아바스 자기소개 2턴째(FRIENDLY 임계 1) ✓ · 이동 턴 주체 플레이어(1-A 재현 ✓) · 복귀 셸 목적지 낭독 없음(1-B 재현 ✓).

검증: 표적 jest 11 스위트 222 passed · 스냅샷 17 갱신 · 전체 jest **2,615 passed**(190 스위트) · eslint 0 · build + kickstart + 스모크 PASS(3턴). 4-B·4-C 실발동은 5회차 런에서 `parsedType`·`[NanoOpeningGuard]` 로그로 관측.

## 5회차 (graymar · devotee · FALLEN_NOBLE, run 0bb5bbb5, 10턴) — 신규 수정 0 · 4회차 수정 2건 재설계·정정

게이트 **15/15**. 정독 13턴 전문. 4-A 재현: 이 런은 graymar 라 로넨 등장이 정당(의뢰인) — 시스템 프롬프트 grep `로넨` 0 확인. 4-C 실발동 1건이 **오탐**("새벽 공기가 차갑게")이라 패턴 축소(위 4-C 정정). 4-B 는 30일 이벤트 매칭 실측으로 **1차안 철회 후 재설계**(위 4-B) — 이 런 T4(`market_talk`)가 `EVT_MARKET_OPP_LOST_CARGO` 를 PERSUADE affordance 로 매칭한 것이 결정적 근거.

| # | 증상 | 결정적 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 5-A | **거점→장소 이동 턴에 의뢰인이 동행** — 로넨이 앞장서 시장 입구까지 같이 걷고 멈춤 | T2(go_market): `로넨이 앞서 걸음을 멈추고 뒤를 돌아본다 … 두 사람이 시장 거리의 입구 표지판이 걸린 모퉁이에 다다른다. 로넨이 입구에서 발을 멈춘다.` 프롬프트: `최근 상호작용 상대: 로넨` + "출발과 이동 과정까지만" 지시(동행 금지 문구 없음). 30일 graymar `go_*` HUB 턴 409 중 로넨 언급 56(14%)·**동행 동사(앞서/따라/함께/나란히) 3(0.7%)** | 1-A(장소→거점 이동 턴 주체 명시)의 거울상 — 거점→장소 이동 지시에는 "거점 인물은 남는다" 가 없다. 빈도 0.7% | **관찰 등재** — 프롬프트 최소주의(원칙 6)상 1% 미만 현상에 규칙을 추가하지 않는다. 재발 시 1-A 문구를 이동 선택 지시에도 병기 |

재확인(기존 트랙): T7 rumor 모드 FACT_LEDGER_EXISTS "공물 장부가 있었고 사라졌다는 사실이 제자리를 찾는다" — 프롤로그 기지 사실의 재발견(rumor stale 타이밍 잔여) · T13 산문 귀속 무라벨 대사 3줄(`책임자가 말한다. "…"`·`장교가 말한다. "…"` — Solar 인라인 산문, 30일 Solar 454턴 중 1턴) + 대시 절단 어체 위반 1 · T13 서술의 "그대"(마이렐 하오체 호칭이 지문으로 침투, V9 그대×7 — arch/113 v2 호칭) · T11 "교대 사이렌"(시대착오 어휘, 30일 1/3,510) · T9 복귀 셸 "저물녘 빛" vs T8 "아침 햇살"·runState phaseV2=DAY(Solar 시간 착오) · T1·T3 전문 과거형 · T2 로넨 HAPSYO→하오 위반 1 · 토브렌 자기소개 T7(대화 4턴째, FRIENDLY 임계 1 — 지연 원인 로그 미확인, 관찰) · "그의 손끝에서 밀랍과 젖은 양피지 냄새"(T11 셸 즉흥 인물).

정합 확인: FACT_INSIDE_JOB(T6) direct·주제 매칭 — 대사 "안에서 누가 지시하는지 … 시키는 쪽이 발 빼면" = 기록 ✓ · T7 FREE·TALK 턴 questReveal 은 rumor 경로만(3-A 게이트 ✓) · 이동 턴(T8) 주체 플레이어·토브렌 잔류 ✓ · 마이렐 CALCULATING 미소개 유지(임계 3) ✓ · V13 적극 33%(nano BRIBE·HELP·STEAL·PERSUADE 2) — devotee 페르소나에서 적극 축 정상.

검증: 표적 jest(choice-challenge 20·nano-event-director 43·scene-shell) passed · build + kickstart + 스모크 PASS. 4-B 재설계 실발동은 6회차 런의 `[Challenge] CHOICE 룰 즉결: FREE` 로그와 접근 선택지 턴 `resolveSkipped` 로 관측.

## 6회차 (star_sand · sneaky_liar · SS_SMUGGLER, run 521faf04, 10턴) — 수정 3건

게이트 **15/15**. 정독 13턴 전문. 4-C 실발동 ✓(`[NanoOpeningGuard] "이렌의 눈빛이 잠시 흔들리며 주변을 살핀다."` 억제, 오탐 정정 후 환경 감각 opening 통과). 이동 턴(T8) "이렌은 방 안쪽으로 시선을 거둔 채 그대로 남았다" — 1-A 재현 ✓.

| # | 증상 | 결정적 근거 | 근본 원인 | 조치 |
|---|---|---|---|---|
| 6-A | **"훔쳐본다"(엿봄)가 절도로 판정돼 골드·전리품 실지급** | T4 `문고리와 손잡이를 조심스레 만지며 안쪽을 살짝 훔쳐본다.` → parsedType **STEAL**·SUCCESS(1d6=6) → events `GOLD·LOOT` 발생, 서술 "하급 심장액 물약 하나가 굴러 떨어졌고 … 작은 돈주머니가 툭", T8 "돈주머니를 허리춤에 단단히 밀어 넣고". 90일 `훔쳐보|훔쳐본` 입력 6건 중 **STEAL 5** | `intent-parser-v2` STEAL 키워드 `'훔쳐'` 가 "훔쳐보다" 에 부분 매칭(불변식 52 의 `총→총각` 과 같은 부류). `location-turn.hasExplicitStealIntent` 도 같은 목록 | **수정** `normalizePeekVerbs()` — 매칭 전 `훔쳐 ?(보\|본\|봐\|봤\|볼)` → `엿보`(SNEAK 키워드) 치환, parse()·hasExplicitStealIntent 양쪽 적용. 스펙 2(엿봄→SNEAK / "돈을 훔쳐 나온다" STEAL 유지). 프로브: 같은 문장이 라이브에서 **OBSERVE**(LLM 인텐트 경로) — 절도 아님·지급 없음 ✓ |
| 6-B | **4-B 면제 누락** — `encounter_talk`("말을 건네본다")가 즉결 CHECK·triumph | T5 `말을 건네본다` → PERSUADE·SUCCESS·triumph, 로그 `CHOICE 룰 즉결: CHECK (always-challenge PERSUADE)` | 이 선택지는 `scene-shell` 이 아니라 콘텐츠 `content/<pack>/suggested_choices.json` ENCOUNTER 템플릿(두 팩 동일) — 4-B 목록이 코드만 훑었다 | **수정** 두 팩 `encounter_talk` 에 `riskLevel: 1`(SuggestedChoice 타입·로더 통과 기확인). `audit_content` ERROR 0 |
| 6-C | **FREE 접근 턴이 여전히 triumph** — 4-B 재검증 프로브에서 발견 | 프로브 run c581ca34 T4 `market_talk` → FREE(no stakes)·resolveSkipped ✓ 이나 toneHint **triumph** | `tone-hint.core` 가 `outcome==='SUCCESS' && PERSUADE` 로 승리를 판정하는데 FREE 자동 SUCCESS 가 그대로 들어온다(입력 주석 "판정 스킵 턴은 undefined" 와 실제 불일치) | **수정** `ToneHintInput.resolveSkipped` 추가(location-result 가 `hideResolve` 전달) → 판정 스킵 사회 행동은 `calm`. 스펙 1. 재프로브 run 820cc9b8 `explore_talk` → PERSUADE·FREE·**calm** ✓ |

재확인(기존 트랙): T6 무라벨 인용 1줄(`"이렌은 그날 이후로 …"` — 대사 안에서 자기 이름을 3인칭으로, Solar 30일 무라벨 인용 6/471) · T13 닫는 따옴표 뒤 대사 이어짐(`…같소."손님이 아까 지나온 …들렸소만.` 깨진 인용 2/471) + "손님이 아까 지나온 검은얼음 시장"(가지 않은 경로 환각) · T4 헬룬 하오체 "자리요" 어체 감사 위반 1(하오체 축약 `-요` 를 해요체로 집계 — 감사기 오탐 의심, 관찰) · T2 "성벽 위 발소리"(해안 팩 소품) · T11 "보고선의 불빛" 어휘 · T1·T8·T9·T11 과거형 · 선택지 라벨 에코("방금 하신 말씀…"). 정합: FACT_SS_FIRST_DREAM direct·주제 ✓ · T7 서랍 INVESTIGATE PARTIAL 은 소프트 힌트만(공개 없음) ✓ · 아바스 자기소개 2턴째 ✓ · 인계 힌트(등불 수녀) ✓ · sneaky_liar T4 nano POLITE 제지 + 헬룬 개입 ✓.

검증: 표적 jest(intent-parser 91·tone-hint/location-result 15·choice-challenge) · **전체 jest 2,621 passed**(190 스위트, 스냅샷 17) · eslint 0 · `audit_content` ERROR 0 · build + kickstart + 스모크 PASS · 프로브 2회(graymar market_talk / star_sand explore_talk).

## 종합 (4~6회차)

| 회차 | 팩·페르소나 | 게이트 | 수정 | 재확인 |
|---|---|---|---|---|
| 4 | star_sand·chatty | 15/15 | 시스템 프롬프트 콘텐츠 실명 제거 · 접근 선택지 판정 면제(재설계) · nano 첫 문장 감정 클리셰 가드 | 8 |
| 5 | graymar·devotee | 15/15 | (4-B 철회·재설계, 4-C 오탐 정정) | 10 |
| 6 | star_sand·sneaky_liar | 15/15 | 훔쳐보다≠절도 정규화 · encounter_talk riskLevel · FREE 접근 톤 calm | 8 |

게이트가 잡은 결함 0, 전부 정독·프로브. arch/114 리팩토링 회귀 징후 없음(3런 + 스모크 4회). **1차안을 30일 실측으로 철회한 사례 1건**(4-B TALK 전환 — 저작 이벤트 funnel 72%)이 이번 시리즈의 핵심 교훈: 기본 선택지 affordance 는 판정 축이 아니라 **이벤트 매칭 축**이라 바꾸면 안 되고, 판정·톤은 각각의 코어(`choice-challenge`·`tone-hint`)에서 풀어야 했다.

**커밋됨 — server `a74f9fa` · docs `f5b114a`** (2026-09-08, 재기동 해시 일치·스모크 PASS): server 13 파일 — `system-prompts.ts`·`prompt-builder.snapshot.spec.ts.snap`·`nano-event-director.service(+spec)`·`scene-shell.service`·`choice-challenge.core(+spec)`·`intent-parser-v2.service(+spec)`·`location-turn.service`·`location-result.service`·`tone-hint.core(+spec)`. docs 레포 2 파일 — `content/graymar_v1/suggested_choices.json`·`content/star_sand_v1/suggested_choices.json`. 서버는 build+kickstart 로 라이브(해시 `3656c03` + 미커밋 변경).

**센서 메모**: V13 적극 축이 셸 턴의 서버 기본 선택지(PERSUADE)를 함께 센다 — 4회차 적극 3/19 중 1 이 explore_talk. nano 품질 게이트라면 서버 기본은 분모·분자에서 빼는 편이 정확(playtest.py, 별도 판단). nano `[톤]` "긴장감" 52% 는 감정 이중 채널 백로그 수치 갱신.
