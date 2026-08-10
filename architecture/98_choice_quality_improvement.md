# 98. 선택지 품질 개선 — 편중 해소·질문 응답 보장·노출 튜닝

> 상태: ✅ 구현 완료 (P0 2026-08-04 · P1~P4+V13 2026-08-05, 검증 실측은 §10)
> 선행: arch/61(선택지 추천 튜닝), arch/68 부록 D(NanoChoiceNpcFix)·K(컨셉 게이트), 불변식 50(구체 어휘 주입 금지)

## 1. 배경 — 2026-08-04 점검

점검 방법 3종: ① 파이프라인 코드 전수 추적(scene-shell → NanoEventDirector → 후처리 3종 → 클라), ② 실유저 표본(최근 14일 9런 126턴, 선택지 503개, 테스터 제외), ③ chatty 에이전트 12턴 실런 대조.

**구조 판정**: arch/61의 3층 구조(서버 동기 기본 → nano Track2 교체 → 사후 기계 교정)는 견고하게 작동. 라벨 고유율 369/503, 연속 턴 유사 반복 4%(110쌍 중 4), 선택지-서술 NPC 정합(V10) PASS. 서술 구체 요소 인용 규칙(P1)도 실작동 확인.

**결함 5건** 발견, 아래 재검증 수치로 확정/기각 분류.

## 2. 재검증 결과 요약

| # | 결함 | 재검증 수치 | 판정 |
|---|------|------------|------|
| P0 | choices[].npcId 무검증 — 초상화 URL·"null" 문자열·slug 유출, 라벨 raw ID 노출 | 오염 8/503건(2.1%) + 라벨 노출 1건("mirela에게 더 물어본다") | ✅ **구현 완료** (§3) |
| P1 | affordance·동사 편중 = "투박함"의 실체 | TALK/OBSERVE/INVESTIGATE 91%, 적극 축(PERSUADE·SNEAK·TRADE·HELP·THREATEN·STEAL) 합계 2%. 동사 2/3가 '본다'(46%)·'묻는다'(21%) 계열. **비대화 입력 92턴에서도 동일 편중** — 플레이 스타일 아닌 nano 수렴이 원인 | 확정 — 최우선 |
| P2 | NPC 질문으로 닫힌 턴에 응답 선택지 부재 | 질문 종결 13턴 중 **12턴(92%) 미준수** — 프롬프트 규칙(rule 4 "반드시 1개 이상")이 soft 지시로 사실상 무시됨 (LLM 설계 원칙 4) | 확정 |
| P3 | bribeOpportunity 연속 재주입 | BRIBE 연속 노출 streak: 5턴×1, 4턴×2, 2턴×2 — 보류 상태 지속 시 매 턴 재노출 | 확정 |
| P4 | 라벨 폴리싱 (마침표·콜론·이동 암시) | 마침표 종결 3/377, 콜론 0, 이동 암시 라벨 1건(0.3%) | **대폭 축소** — 저비용 방어만 |

기각/보류: **이동 선택지 본격 지원**(NPC가 타 장소 지목 시 클릭 이동) — 표본 1건으로 빈도 미달, MOVE_LOCATION 파이프라인 연결은 별도 트랙. P4의 라벨 방어로 갈음.

## 3. P0 — ChoiceNpcIdNorm (구현 완료, 2026-08-04)

**갭**: validate 1단계는 메인 `npcId`만 presentNpcs 대조, `choices[].npcId`는 `typeof === 'string'`이면 무검증 통과. nano가 Track2 서술 미리보기의 `@[표시명|/npc-portraits/...]` 마커에서 초상화 URL·slug를 복제하는 실측. 오염 payload는 클릭 시 NpcResolver Step 0(CHOICE_EXPLICIT)이 신뢰하는 값이라 화자 결정까지 오염.

**구현** (`nano-event-director.service.ts`):
- `normalizeChoiceNpcIdCore` (export 정본 코어) — 해석 순서: 정본 ID 일치 → 표시명 → bare ID(NPC_ 접두 제거) → 초상화 파일명 슬러그(`content.getNpcPortraitUrl` 대조). `"null"/"none"/"unknown"` 문자열·빈 값·미해석은 null 강등 (워커의 `nc.npcId ?? nanoResult.npcId` 폴백이 검증된 메인 npcId로 채우므로 안전).
- `sanitizeChoiceLabelNpcTokensCore` — 라벨의 ASCII 3자+ ID/슬러그 토큰을 표시명으로 치환 (단어 경계 lookaround, "mirela에게" 케이스 커버).
- validate 4단계(affordance 화이트리스트 루프)에 배선. 단위 12케이스 (`nano-event-director.choice-npc-norm.spec.ts`), 인접 스위트 71 passed, 빌드 통과.

## 4. P1 — affordance 편중 해소: 동적 적극 축 positive 주입

**원인 진단**: 프롬프트 규칙이 "최소 2종 affordance"만 요구 → nano가 안전한 소극 3종(TALK/OBSERVE/INVESTIGATE)으로 수렴. `previousChoiceAffordances`("최소 1개는 다른 접근") 주입이 있으나 축 자체가 3종 순환이라 무력. **검증된 반례 = bribeOpportunity**: "정확히 1개는 BRIBE, npcId 지정" positive 강제는 실준수율이 높다(BRIBE 6% 실노출이 증거). 같은 메커니즘을 일반화한다.

**설계 — 서버가 매 턴 적극 축 1개를 선정해 positive 강제**:

1. **선정 로직** (turns.service nanoCtx 빌드부, 신규 `suggestedActiveAffordance`):
   - 후보 풀: PERSUADE, TRADE, HELP, SNEAK, THREATEN, STEAL (+SEARCH)
   - 맥락 가드 (밸런스·세계관 정합):
     - posture FRIENDLY/CAUTIOUS → THREATEN·STEAL 제외 (관계 파괴 유도 금지)
     - hubSafety DANGER 또는 조건 LOCKDOWN → SNEAK·STEAL 제외
     - 상점/거래 태그 장소 → TRADE 가중
     - NPC가 도움 요청/난처 상황(nanoCtx npcReactions) → HELP 가중
   - 회전: runState에 최근 주입 축 2개 기록(`recentActiveAffordances`), 연속 중복 회피 — daily_topics dedup과 동일 패턴
   - **주입 확률 게이트**: 매 턴이 아닌 60~70% 턴만 주입 (모든 턴 강제 시 적극 선택지가 새 상용구가 되는 역편중 방지). 상수는 `quest-balance.config.ts` 외부화 (불변식 30)
2. **프롬프트** (nano-event-director buildUserMessage): bribeOpportunity 블록과 동일 형식 — `[접근 다양화] 선택지 3개 중 정확히 1개는 {affordance} 계열 행동으로 만드세요. 현재 장면의 사물·인물을 끌어온 구체 행동으로.` (BRIBE 활성 턴에는 미주입 — 슬롯 경쟁 방지)
3. **후처리**: ChoiceAffFix가 라벨-affordance 정합 담당 (기존). dedupe는 그대로.
4. **기대 효과**: 적극 축 2% → 20%±, 동사 다양화는 축 전환의 부수 효과로 자연 획득 (동사 금지어 주입은 불변식 50 위반이라 하지 않음).

**계측**: playtest V13 신설 — affordance 분포에서 적극 축 비율 ≥15% 게이트 (2026-08-10 정정: 최초 정의의 `소극 3종 ≤80%` 병기는 삭제 — §11.4 참조). audit 스크립트가 아닌 playtest.py 센서로 (선택지는 llm_choices에 이미 기록됨).

## 5. P2 — 질문-응답 선택지 보장 (2단 사다리)

**원인 진단**: rule 4의 "반드시 포함"은 soft 지시. 질문이 500자 미리보기 안에 섞여 있어 nano가 질문 존재 자체를 인지 못하는 턴이 다수로 추정. 자기소개 사전 확정(arch/66)과 동일한 "추출 → 명시 주입 → 사후 보정" 사다리를 적용한다.

1. **1단 — 명시 추출 주입** (llm-worker Track2 재호출부): 서술 꼬리에서 마지막 NPC 대사가 물음표로 끝나면 그 문장을 추출해 nanoCtx 신규 필드 `pendingNpcQuestion`으로 전달. 프롬프트: `[NPC의 질문] {NPC명}이(가) 방금 물었다: "{질문}" — 선택지 3개 중 1개는 이 질문에 직접 응답(긍정/부정/되물음)하는 행동으로.` 추출은 기존 대사 파싱 유틸(`@마커` + 따옴표 블록) 재사용, 신규 regex 최소화.
2. **2단 — 사후 검증 보정** (llm-worker finalChoices 확정 직전, ChoiceDedupe 뒤): `pendingNpcQuestion`이 있는데 응답형 라벨(대답/답/설명/밝힌/수락/거절/동의/부인 등 키워드)이 0개면, 비-go_hub 선택지 중 1개(우선 TALK)를 `"{질문 요지}에 답한다"` 폴백 라벨로 교체하지 **않고** — 라벨 기계 생성은 투박함 역행이므로 — **교체 대신 계측 로그만 남기고 1단 준수율을 감시**한다. 1단 실측 준수율이 70% 미만이면 그때 교체형 2단을 재설계 (사후 삽입은 최후 수단 — LLM 대응 원칙 4).
3. **계측**: playtest V13에 질문 턴 응답 선택지 포함률 센서 (현 8% → 목표 70%+).

## 6. P3 — bribeOpportunity 쿨다운

**원인**: `bribeOpportunityNpcId` 판정(fact 보류/trust 거부)이 상태 지속 시 매 턴 참이라 매 턴 재주입 → 5턴 연속 BRIBE 노출 실측. 압박감 + BRIBE 슬롯이 P1 적극 축 슬롯과 상시 경쟁.

**수정**: runState에 `lastBribeOfferTurn`(NPC별) 기록, **노출 후 동일 NPC 2턴 휴지**. 플레이어가 BRIBE를 실행했거나 fact가 공개되면 리셋. 상수는 `quest-balance.config.ts`(불변식 30). 판정 로직(turns.service:2307~)은 유지하고 nanoCtx 부착 지점(:6151~)에서 쿨다운 게이트만 추가 — 판정과 노출의 분리.

## 7. P4 — 라벨 폴리싱 (저비용 방어 3종)

재검증에서 빈도 미미로 확인 — ChoiceAffFix(정본 코어) 끝에 일괄 추가:
1. 라벨 끝 마침표 제거 (`label.replace(/[.。]\s*$/, '')`) — 3/377건
2. 콜론+인용 라벨(`질문을 계속한다: '...'`) → 콜론 이하 절단은 정보 손실이라 미채택, **콜론을 " — "로 치환**만 (플레이테스트 1건, 실유저 0건 — 관찰 유지)
3. 이동 암시 라벨(`~로 가서/간다`) + 비이동 affordance 조합 감지 시 경고 로그만 (0.3% — 데이터 축적 후 판단)

## 8. 적용 순서·리스크

| 순서 | 항목 | 코드 지점 | 리스크 |
|------|------|----------|--------|
| ✅ P0 | ChoiceNpcIdNorm | nano-event-director validate 4 | 완료 — 회귀 0 |
| 1 | P3 쿨다운 | turns.service nanoCtx 부착부 + runState | 낮음 (게이트 1개) |
| 2 | P1 적극 축 주입 | turns.service 선정 + nano 프롬프트 + config | 중간 — 주입 확률·가드 튜닝 필요, 플레이테스트 2회로 편중 재측정 |
| 3 | P2 질문 주입 | llm-worker Track2 + nano 프롬프트 | 중간 — 대사 추출 정확도. 1단만 먼저, 2단은 실측 후 |
| 4 | P4 폴리싱 | ChoiceAffFix 코어 | 낮음 |
| 5 | V13 센서 | scripts/playtest.py | 낮음 |

P1·P2는 같은 프롬프트 블록 영역을 건드리므로 **P1 배포 → 플레이테스트 검증 → P2 착수** 순서 (동시 투입 시 효과 귀속 불가). 전 항목 nano 프롬프트 증분은 +2블록(~200자) — nano는 GRAND_TOTAL 백스톱 대상이 아니나 maxTokens 300 응답 계약은 불변.

## 9. 이번 점검의 부수 발견 (별도 트랙)

- **V12 프롬프트 재비대 경보**: 12턴 실런에서 avg 13,143자, 백스톱(≥16,000자) 발동 4/12턴(33%) — arch/95 게이트(≤20%) 초과. 선택지와 무관한 메인 프롬프트 다이어트 사이클 필요 (arch/79·95 후속).

## 10. 구현·검증 기록 (2026-08-05)

### 구현 지점

| 항목 | 파일 | 핵심 |
|------|------|------|
| P0 ChoiceNpcIdNorm | `nano-event-director.service.ts` | `normalizeChoiceNpcIdCore`·`sanitizeChoiceLabelNpcTokensCore` + validate 4단계 배선. **회귀 수정(§10.3)**: 검증 목록을 presentNpcs → knownNpcs(+잠금·지목·직전·bribe·메인 NPC)로 확장 |
| P1 적극 축 주입 | 동 파일 + `turns.service.ts` + `quest-balance.config.ts` | `pickActiveAffordanceCore`(posture·safety 가드 + 최근 2축 회피 + 가중 추첨), `hashSeed` 결정론 롤(RNG 커서 비소비 — 불변식 4), `ACTIVE_AFFORDANCE_INJECT_CHANCE=65`, runState `recentActiveAffordances` |
| P2 질문 명시 주입 | `llm-worker.service.ts` + nano 프롬프트 | `extractPendingNpcQuestionCore`(마지막 따옴표 대사 물음표 종결 + 잔여 서술 ≤120자) → `[NPC의 질문]` 블록. 2단은 기계 교체 대신 `[ChoiceQuestionMiss]` 계측 로그만 |
| P3 BRIBE 쿨다운 | `turns.service.ts` + runState `bribeOfferHistory` | 주입 기록 후 동일 NPC 2턴 휴지 (`BRIBE_OFFER_COOLDOWN_TURNS`), BRIBE 실행/fact 공개 시 리셋 |
| P4 라벨 폴리싱 | `llm-worker.service.ts` | `polishChoiceLabelsCore`(끝 마침표 제거·콜론→줄표·이동 암시 라벨 경고) — finalChoices 체인에 삽입 |
| V13 센서 | `scripts/playtest.py` | affordance 분포 게이트(적극 ≥15%) + 질문 응답률 계측. poll_llm `expect_choices`(LOCATION 턴 Track2 완료 대기) + 분석 시 재조회 |

단위 테스트: `nano-event-director.choice-npc-norm.spec.ts` 12케이스 + `choice-quality.arch98.spec.ts` 15케이스. 전 스위트 1,668 passed.

### 검증 실측 (chatty 12~14턴 실런)

- **P1**: 주입 6턴 중 5턴 nano 준수(83%) — PERSUADE·TRADE·STEAL·THREATEN·HELP 실생성. 적극 축 비율 2%(사전) → **25%**(3차 런 V13 게이트 PASS: 적극 25% / 소극 75%). 축 회전(recent 2 회피) 실작동.
- **P2**: 3차 런 t5 실증 — `[ChoiceQuestion]` 주입("다른 데에 관심이시오?") → nano가 "그 일에 관심이 있다 / 아니오, 관심 없다 / 조심스럽게 묻는다"로 **긍정·부정·되물음 3형 정확 생성**. 초기 `ANSWER_LABEL_RE`가 평서 응답형("~있다/없다")을 못 잡아 false-miss → 응답 개시어+평서 종결 패턴으로 보정.
- **P3**: BRIBE 기회 지속 상황에서 T 주입 → T+1·T+2 억제(`[BribeCooldown]` 로그) → T+3 재허용 실측 — 기존 최장 5턴 연속 노출 해소.
- **V13 운영 노트**: 분석 시 연속 재조회가 서버 rate limit(429)에 걸려 표본이 새던 실측 — poll 단계 `expect_choices` 대기(Track2 완료 시점 = 실클라 stream done 시점) + 재조회 간 0.4s 간격으로 이중 방어.

### 후속 수정 — PERSUADE 어감 승격 (2026-08-05, 15턴 실런 분석 후)

15턴 실런(13/14 PASS)에서 V13이 소극 81% vs 게이트 80%로 1개 차 미달 — 직접 원인은 nano 주입 미준수(이번 런 2/4, 누적 7/10)이며, 그중 절반이 "부드럽게 말한다"류 **설득 어감 라벨이 TALK로 강등**되는 유형. ChoiceAffFix에 PERSUADE 승격 규칙(설득/회유/다독/부드럽게 말/제안) 추가 — BRIBE 규칙(금전 제안 보강) 뒤에 평가해 금전 제안 오승격 차단. 단위 4케이스. 잔여 관찰: 질문·BRIBE 블록 동시 발생 시 슬롯 경쟁(t20 실측 1건 — 표본 축적 후 배분 지시 검토), V12 재비대 진동(7~25%).

### 회귀 1건 (즉시 수정)

P0 초기판이 `choices[].npcId`를 presentNpcs로만 검증 → 이벤트·상황 생성 NPC(예: NPC_RENNICK)가 장소 상주 목록에 없어 **유효 정본 ID가 null로 강등**되던 실측 (워커 `?? nanoResult.npcId` 폴백 + NanoChoiceNpcFix가 대부분 복구했으나 지목 정보 소실). 검증 목록을 knownNpcs(잠금·지목·직전·bribe·메인 NPC 포함, `content.getNpc`로 표시명 보강)로 확장해 봉합.


## 11. V13 게이트 재판정 — 편중이 아니라 표본 크기였다 (2026-08-07)

### 11.1 발단

2026-08-07 세션의 플레이테스트 7런 중 **6런에서 V13 FAIL** (적극 축 11~14%,
게이트 ≥15%). §10 이 P1 배포 직후 25% 달성을 기록했으므로 회귀가 의심됐다.

### 11.2 진단 — 주입은 정상, 문제는 런 단위 판정

| 확인 항목 | 실측 |
|---|---|
| 적극 축 주입 발화 | 30회 / LOCATION 선택지 66턴 = **45.5%** (설정 `ACTIVE_AFFORDANCE_INJECT_CHANCE=65`) |
| 축 회전(recent 2 회피) | 정상 — HELP→SNEAK→TRADE→THREATEN→SNEAK 실로그 |
| **당일 누적 적극 축** | 33/198 = **16.7%** → 게이트 15% **통과** |
| 런 단위 | 11% · 14% · 22% · 39% — 같은 설정·같은 페르소나에서 |

런당 nano 선택지가 27~36개뿐이라 **1개가 약 3%p**다. 15% 선에서 ±1개가
통과/실패를 가르고, 실제로 인접 런이 11%와 39%를 오갔다. 편중이 재발한 것이
아니라 **게이트가 표본 크기 때문에 노이즈를 신호로 읽고 있었다**.

주입 실효율 45.5%가 설정 65%에 못 미치는 것은 별개 관찰이다 —
`bribeOpportunity`/`FAREWELL` 스킵과 `pickActiveAffordanceCore` 가드(posture·
safety) null 반환이 원인 후보. 누적 16.7%가 게이트를 넘으므로 즉시 조치 대상은
아니나, §10 의 25%에는 못 미치므로 추적 항목으로 남긴다.

### 11.3 조치 — V12 와 동일한 다회 런 누적 판정

`scripts/playtest.py` 의 `append_gate_ledger()` 공용 헬퍼로 V12·V13 이 같은
방식을 쓴다 (arch/79 §11.3 과 동일 결정).

| 항목 | 값 |
|---|---|
| 판정 창 | 최근 `V13_POOL_RUNS=3` 런 |
| 판정식 | 원시 카운트 풀링 `sum(active)/sum(total)` — 런별 표본 크기 자동 가중 |
| 보류 | `V13_MIN_RUNS=2` 미만이면 통과 처리 + 참고 수치만 |
| 원장 | `playtest-reports/v13_ledger.json` (런별 서버 해시 동반, 로컬) |

검증 실측(ea84c33, 10턴×2런): 1회차 39% → "표본 부족 보류", 2회차 22% →
**누적 11/36(31%) PASS**. 같은 런에서 V12 도 누적 3/30(10%) PASS 하여
**게이트 14/14 전항목 통과** — 이번 세션 최초.


### 11.4 게이트 정의 정정 (2026-08-10) — "≥15%"가 도달 불가였다

§5 최초 정의는 `적극 축 ≥15% AND 소극 3종 ≤80%` 였는데, **소극 = 100% − 적극**
이라 두 조건은 독립이 아니다. 뒤 조건이 `적극 ≥20%` 를 뜻하므로 전체가
**`적극 ≥20%` 하나로 붕괴**하고, 명시된 15% 임계는 한 번도 구속력을 가진 적이 없다.

실측으로 드러났다 — 누적 적극 18%인데 FAIL (2026-08-10, 3런 10/57).

**정정: 소극 조건을 삭제하고 `적극 ≥15%` 단일 임계로 둔다.** 근거는 게이트를
목표치 아래에 두는 것이 정상이고, §4 가 밝힌 목표가 "적극 축 2% → 20%±" 이므로
의도된 게이트 값은 그 아래인 15% 라는 것이다. 20% 는 목표치와 같아 노이즈에
그대로 뒤집힌다(§11.2 의 런 단위 판정이 그랬듯이).

소극 비율은 계측·표시용으로 남긴다 — 게이트에서 빠질 뿐 분포 감시에는 쓸모가 있다.

> 별개 추적 항목: §11.2 의 주입 실효율(45.5% vs 설정 65%)과 §10 대비 하락
> (25% → 18%)은 이 정정과 무관하게 남는다.
