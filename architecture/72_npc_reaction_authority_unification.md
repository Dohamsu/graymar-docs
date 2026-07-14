# 72. NPC 반응 권한 통합 (목격자 반응 ↔ NpcReactionDirector)

> 상태: ✅ 구현됨 (2026-07-14) — (가) 스코프 분리 + 1회 발화 보장 + trust 밴드 재조정 + 목격 신호 ② 전달. §8 구현 기록. (나) 단일 권한자는 장기 목표로 유지 (§7).
> 관련: [[49_npc_resolver_authority]] (발화자 결정 단일화 — 같은 패턴), [[56_npc_reaction_director]] (NpcReactionDirector 도입), [[26_narrative_pipeline_v2]] (3-Stage 파이프라인)
> 발단: 버그 599a00a1 (친근 NPC 아바스가 평범한 질문에 냉랭히 거리 둠) — 트리거 수정(stopgap) 후 재검토에서 구조 결함 3건 확정, 본 문서로 통합 수정.

## 1. 문제 한 줄 요약

한 NPC의 "이번 턴 태도"를 **서로 모르는 두 시스템**이 각각 결정해 **둘 다 프롬프트에 주입**한다. 신호가 상충하면 메인 LLM이 임의로 하나를 골라 톤이 붕괴한다.

## 2. 두 시스템

### ① 목격자 반응 (Witnessed Reaction)
- **위치**: `turns/turns.service.ts` (~2140–2218)
- **취지**: 플레이어의 **위험 행동(FIGHT/STEAL/THREATEN)**을 근처 NPC가 **목격**했을 때의 방관자 반응 (Layer 3, architecture/CLAUDE Phase "NPC 능동 반응").
- **결정 방식**: 서버 규칙 — 목격 NPC의 `trust`로 분기.
  - trust ≥ 20 → `warn` "…조심하라고 경고한다"
  - trust ≥ -10 → `avoid` "…눈을 피하며 거리를 둔다"
  - trust ≥ -30 → `inform` "…경비대에 밀고했다" (Heat +5)
  - 그 미만 → `hostile`
- **출력**: `ui.npcReactions[] = { npcName, type, text, heatDelta }` — **하드코딩 완성 문장**.
- **주입** (`prompt-builder.service.ts` ~1174): `[NPC 반응 — 이전 행동을 목격한 NPC의 반응을 서술에 자연스럽게 포함하세요]` + `- {text}`. → **"자연스럽게 포함" 수준의 힌트**.

### ② NpcReactionDirector (나노)
- **위치**: `llm/npc-reaction-director.service.ts` + LLM Worker
- **취지**: **지금 대화 중인 그 NPC**가 이번 턴 취할 태도를 나노 LLM이 사전 결정 (architecture/56). "메인 LLM이 추측 대신 표현".
- **결정 방식**: 나노 LLM — NPC 감정·직전 흐름·판정 결과 종합.
- **출력**: `reactionType`(WELCOME/OPEN_UP/PROBE/DEFLECT/DISMISS/THREATEN/SILENCE) + `refusalLevel` + `immediateGoal` + `openingStance` + `dialogueHint` + 추상 톤 3축.
- **주입** (`prompt-builder.service.ts` ~1101): `[⚠️ P0 — NPC 즉시 반응 결정 (서버 사전 판단, 절대 위반 금지)]` + "NPC 대사·행동·태도·표정이 모두 위 결정과 일치해야 합니다". → **P0(최고 우선) "절대 위반 금지" 지시**.

## 3. 충돌의 구조

| 축 | ① 목격자 반응 | ② NpcReactionDirector |
|---|---|---|
| 대상 | 목격한 **모든** NPC (대화 상대 배제 없음) | **주 대화 상대** 1명 |
| 신호 형태 | **완성된 한글 문장** ("눈을 피하며 거리를 둔다") | **추상 태도** (OPEN_UP + 톤) |
| 프롬프트 우선순위 라벨 | "자연스럽게 포함" (약) | "P0 · 절대 위반 금지" (강) |
| 계산 주체 | 서버 규칙 | 나노 LLM |
| 상호 인지 | ❌ 서로 모름 | ❌ 서로 모름 |

**두 시스템은 같은 NPC를 겹쳐 지시할 수 있다** — ①은 목격 NPC를 배제 없이 반응시키므로, 그 NPC가 마침 대화 상대(②의 대상)면 한 NPC에 상반된 두 지시가 동시에 들어간다.

**역설**: ②가 "P0 절대 위반 금지"인데도 ①이 이긴다. ①은 **바로 쓸 수 있는 완성 문장**을 주고 ②는 **추상 태도**만 주므로, LLM이 손쉬운 ①의 텍스트를 복사한다(버그 599a00a1의 "눈을 피하며 거리를 둔다"가 정확히 ①의 하드코딩 문자열).

## 4. 버그 599a00a1로 드러난 사례

- 아바스(FRIENDLY, trust 10~15) 첫 조우. 플레이어 OBSERVE/TALK(평범·성공).
- ② 나노: `OPEN_UP`(마음 열기, goal="비밀을 더 캐기").
- ① 목격자: `avoid`("눈을 피하며 거리를 둔다") — **성공 행동이 `DANGEROUS_TAGS`의 'success'에 걸려 오발동**.
- 메인 LLM: ①의 완성 문장 채택 → 친근 NPC가 냉랭히 거리 둠 → 톤 붕괴.

### 이미 적용한 응급 수정 (stopgap)
`DANGEROUS_TAGS`에서 `'success'` 제거(commit 053dfd9). → 평범한 성공 행동이 ①을 **오발동**시키던 트리거 제거. **하지만 구조적 겹침은 잔존**: 실제 STEAL/THREATEN + 그 NPC가 대화 상대인 경우 ①·②가 여전히 동시 주입된다.

### 버그 데이터 재검토로 추가 확정된 사실 (2026-07-14, 턴 4·5 DB 실측)

- **턴 5에서 ①의 완성 문장 승리 확정**: ② nano는 `OPEN_UP`(goal "별고래 내부 탐험 장비의 비밀을 더 캐기")이었으나 서술은 ①의 avoid 문자열("눈을 피하며 슬며시 거리를 두더니") + 거절 대사 — §3 역설의 직접 증거. 턴 4는 신호가 유사해 LLM이 ②의 openingStance를 채택 — **상충 시에만 구체 문장이 이긴다**. (다)안이 신뢰 불가한 실증이기도 하다.
- **결함 A — 2턴 중복 발화**: 목격자 수집 윈도우가 `turnCreated ≥ turnNo-1`(최근 2턴)이라 턴 4의 오발동이 **턴 4·5 양쪽에 동일 하드코딩 문장**을 주입했다. PLAYER_ACTION fact는 같은 턴의 ConsequenceProcessor가 블록 직전에 생성하므로 2턴 윈도우는 순수 중복이다. (가) 이후에도 방관자에 대해 잔존하는 별개 결함.
- **결함 B — trust 밴드 캘리브레이션**: 아바스는 `basePosture: FRIENDLY`, trust 15인데 warn 밴드가 `trust ≥ 20`이라 **FRIENDLY NPC가 avoid(냉랭한 회피) 밴드에 떨어졌다**. 콘텐츠 초기 trust 분포(FRIENDLY 10~15)상 "우호적 반응" 밴드가 사실상 미도달. 트리거가 정당했어도 재현됐을 결함.
- **주입 표면이 2곳**: `ui.npcReactions`는 메인 프롬프트 외에 **NanoEventDirector**에도 주입된다(이벤트 컨셉/선택지 오염 경로). (다)안은 2곳을 다 패치해야 하고, (가)안은 소스(turns.service 루프) 수정이라 하류 전체에 일괄 적용된다.

## 5. 통합 선택지

### (가) 역할 분리 — 대상 스코프로 분리 (권장 후보)
- **원칙**: 대화 상대 NPC의 태도는 **오직 ②(NpcReactionDirector)**가 담당. ①(목격자 반응)은 **대화 상대가 아닌 주변(방관) NPC에만** 적용.
- **구현**: ① 루프에서 `primaryNpcId`(= ②의 대상, NpcResolver 결정) 제외.
- **장점**: 작은 변경(제외 1줄 수준). "말 거는 NPC" vs "옆에서 지켜보는 NPC" 의미가 자연스럽게 분리. ②의 P0 권위가 실제로 유지됨.
- **고려**: 대화 상대가 방금 목격한 위험 행동(예: 눈앞에서 STEAL)은 ②의 태도 결정에 그 맥락이 반영돼야 함(②에 "직전 목격" 신호 전달 필요).

### (나) 단일 권한자 — Reaction Resolver로 병합
- **원칙**: 한 NPC에 대해 "목격한 위험 + 대화 의도 + 감정"을 **함께 고려해 하나의 일관된 반응**을 출력하는 단일 리졸버. NpcResolver가 발화자 결정을 단일화한 것과 동형(architecture/49).
- **구현**: ①의 규칙 판정을 ②의 입력 컨텍스트로 흡수 → ②(또는 상위 리졸버)가 최종 `reactionType` 하나 산출. 프롬프트엔 **단 하나의 반응 블록**.
- **장점**: 근본 정합. 향후 반응 소스가 늘어도 단일 지점.
- **고려**: 공사 규모 중. 나노 프롬프트에 목격 맥락 추가 → 나노 호출 비용·지연 영향 점검.

### (다) 현행 유지 + 프롬프트 우선순위 명시
- ①·② 둘 다 주입하되, ①에 "단, [P0 NPC 반응]과 상충하면 P0을 따르라" 문구 추가.
- **장점**: 최소 변경. **단점**: Soft 지시라 LLM이 무시할 여지(불변식 LLM 원칙 #4). 근본 해결 아님.

## 6. 결정 (2026-07-14 확정)

1. **(가) 스코프 분리 즉시 실행** — 관찰 대기 없이. 겹침은 확률이 아니라 **결정론적 재현 시나리오**("NPC 눈앞에서 STEAL 성공 → 같은 NPC에게 TALK")가 있고, 변경 규모가 실측상 소규모였다.
2. **대화 상대의 "직전 목격" 맥락** — ②의 ctx에 이미 `recentPlayerActions`(rawInput/actionType/outcome)가 있어 절반은 배선돼 있었음. 추가한 것은 WITNESSED boolean 파생(`ui.primaryNpcWitnessedTags`) + nano 프롬프트 `[⚠️ 직전 목격]` 블록.
3. **하드코딩 문장 추상화** — (가)로 대화 상대와의 충돌이 사라져 긴급도 하락. 방관자 고정 문장 3종의 반복 어구 문제(LLM이 그대로 복사)는 **백로그**: "타입+NPC명만 주고 문장화는 LLM 위임".
4. **(나) 단일 권한자 재정의** — ①은 서술 힌트가 아니라 **Heat +5/+8 수치 판정 포함**(불변식 1). (나)를 하더라도 밀고/Heat 판정은 서버 규칙 잔존, ②로 통합하는 건 **표현 권한만** — 그러지 않으면 불변식 2(LLM narrative-only) 위반.

## 7. 권고 (갱신)

- **완료**: (가) 스코프 분리 + 결함 A(1회 발화) + 결함 B(trust 밴드) — §8.
- **백로그**: 방관자 반응 문장 추상화 (반복 어구 예방).
- **장기**: 반응 소스가 3개 이상으로 늘면 **(나) 단일 Reaction Resolver**로 승격 (NpcResolver 패턴 재사용, §6-4의 재정의 전제 — 표현 권한만 통합).

## 8. 구현 기록 (2026-07-14)

| 항목 | 변경 |
|------|------|
| (가) 스코프 분리 | `turns.service` 목격자 루프에서 `event.payload.primaryNpcId` 제외 — 대화 상대 태도는 ② 단일 권한. 제외된 목격 태그는 `ui.primaryNpcWitnessedTags`로 전달. |
| 결함 A — 1회 발화 | 목격자 수집을 `turnCreated === turnNo`(당턴 한정)로 교체. fact가 같은 턴 직전(ConsequenceProcessor)에 생성되므로 정확히 1회 발화. |
| 결함 B — 밴드 재조정 | 판정을 `turns/witness-reaction.core.ts`(export 정본)로 추출. **posture 1차 분기**: FRIENDLY→warn(숫자 무관), FEARFUL→avoid(trust 무관). 그 외 trust 밴드 — warn 임계는 `QUEST_BALANCE.WITNESS_WARN_TRUST`(20→15, config 외부화). Heat 수치(inform+5/hostile+8)는 서버 규칙 잔존 (불변식 1·2). |
| ② 목격 신호 | `NpcReactionContext.witnessedDangerTags` 신설 + llm-worker 배선 + nano 프롬프트 `[⚠️ 직전 목격]` 블록 ("아무 일 없던 듯한 WELCOME/OPEN_UP 금지"). |
| 프롬프트 스코프 명시 | ① 주입 라벨을 "[주변 NPC 반응 — … 대화 중인 상대에게는 적용 금지]"로 교체 (메인 prompt-builder + NanoEventDirector 2곳 — 이중 방어). |
| 테스트 | `witness-reaction.core.spec.ts` 6케이스 (아바스 FRIENDLY trust 15 → warn 회귀 가드 포함) + nano-event-director 라벨 spec 갱신. 전체 스위트 1151 passed. |
| 버그 처리 | 599a00a1 → resolved. |

**검증 재현 시나리오** (후속 플레이테스트 체크): ① 평범한 성공 대화 턴에 `ui.npcReactions` 0건 (아바스 케이스 회귀). ② 목격되는 STEAL 성공 → 같은 NPC TALK 시 npcReactions에 그 NPC 부재 + `primaryNpcWitnessedTags` 존재 + ②의 reactionType이 목격 반영(WELCOME 아님). ③ 방관 NPC 반응이 같은 목격으로 2턴 연속 뜨지 않음.
