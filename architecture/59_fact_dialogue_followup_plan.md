# 59. Fact Dialogue Follow-up — 58 검증에서 발견된 3건 수정 계획

> **목표**: architecture/58 라이브 검증(2026-07-04)에서 실측된 기존 이슈 3건 수정.
> **선행**: architecture/58 (기록·서술 단일화) · architecture/49 (NpcResolver 단일 권한자)
> **작성**: 2026-07-04
> **Status**: 📋 계획 (확정)

---

## 실측 증거 (검증 런 cf98f7c0, 항만 부두)

```
T4 입력 "하를런에게 동쪽 부두의…"  → [NpcResolver] npcId=NPC_TOBREN source=EVENT_PRIMARY conf=0.6
                                     → actionContext.primaryNpcId=NPC_HARLUN (extractTargetNpcFromInput)
T6 입력 "하를런 보스에게 길드…"    → [NpcResolver] npcId=NPC_HARLUN source=STRONG_EXPLICIT_NAME conf=1
T7 발견 → pendingQuestHint set (mode=DOCUMENT) → T8 프롬프트에 [단서 방향] 없음
T8 로그 "pendingQuestHint set … mode=undefined"  ← HINT_MODES[5] 범위 초과
```

## 수정 순서 (확정)

| 순서 | 이슈 | 근거 |
|------|------|------|
| **1** | 판정 NPC ≠ 지목 NPC | 유저 체감 최대("A에게 물었는데 B가 대답") + 58의 주제 매칭이 엉뚱한 NPC에서 돌아 효과 반감. 행동 변화가 커서 가장 먼저 넣고 검증 시간을 확보 |
| **2** | [단서 방향] nextHint 사장 | 죽은 기능 복구. 58과 동일한 desync 클래스라 동일 패턴(ui 전달)로 수정 — 구조 통일 |
| **3** | rng.range off-by-one | 2와 같은 코드 경로(HINT_MODES 선택)이므로 **2에 포함해 수정** (별도 커밋) |

---

## 이슈 1 — 판정 NPC ≠ 지목 NPC

### 원인 (실측 확정)

NPC 텍스트 매처가 **이중화**되어 있고 감도가 다르다:

- `NpcResolverService.resolve()` (판정·이벤트 경로 정본): "하를런"(부분 이름) **미인식** → EVENT_PRIMARY fallback
- `extractTargetNpcFromInput()` (actionContext/서술 경로): 부분 이름·shortAlias **인식**

→ 경로 2(단서 판정)·대화 잠금은 리졸버 결과(토브렌)를 따르고, 서술·마커는 actionContext(하를런)를 따라 분열.
부작용: T4에서 actionHistory에 토브렌이 기록돼 **T5 대화 잠금까지 토브렌**으로 오염.

### 수정 방법

**1a. NpcResolver 이름 매칭 강화 (근본)** — `npc-resolver.service.ts`
- STRONG_EXPLICIT_NAME 판정에 부분 이름 매칭 추가: 공백 분리 이름 토큰(예: "하를런 보스" → "하를런"/"보스" 중 고유 토큰), `shortAlias`, 조사 접미("~에게/한테/에겐") 인식
- 2글자 미만 토큰·중의 토큰(여러 NPC 공유)은 제외 — 기존 name 2글자 가드 준수
- 스펙 테스트: "하를런에게 묻는다"→HARLUN, "하를런 보스에게"→HARLUN, 중의 토큰은 EVENT_PRIMARY 유지

**1b. 경로 2 판정 npcId 정합 안전망 (즉효)** — `turns.service.ts` 경로 2
- 판정 npcId를 actionContext.primaryNpcId와 **같은 우선순위**로 계산:
  `extractTargetNpcFromInput(rawInput) ?? eventPrimaryNpc`
- 두 매처가 공존하는 동안에도 "판정 NPC == 서술 NPC" 불변식이 성립 (questReveal.npcId = 서술 NPC)

**후속(스코프 밖)**: `extractTargetNpcFromInput`을 NpcResolver로 흡수해 이중 매처 자체를 해소 — arch/49 완성편. 별도 작업으로 분리.

### 검증
- 단위: resolver 부분 이름 스펙 + 경로 2 npcId 우선순위
- 라이브: 58 검증 셋업 재사용 — "하를런에게 ~" 입력 시 `[Quest:NpcReaction] npc=NPC_HARLUN` == `actionContext.primaryNpcId` 확인, 대화 잠금이 하를런으로 걸리는지 확인

### 리스크
- 매칭 감도 상승 → 오탐(환경 명사 오인) 가능. 고유 토큰 + 2글자 가드 + 스펙으로 방어. NPC 결정 우선순위(불변식 34) 순서 자체는 불변.

---

## 이슈 2 — [단서 방향] nextHint가 프롬프트에 도달하지 못함

### 원인 (실측 확정)

`pendingQuestHint`가 runState로 전달되는데, 비동기 LLM 워커는 **커밋 후** runState를 읽는다:
- 발견 턴 N: `setAtTurn+1 === turnNo` 조건에 걸려 미전달 (의도된 동작)
- 다음 턴 N+1: 턴 처리 **초입의 만료 정리**(`setAtTurn < turnNo` → null)가 커밋에 포함 → 워커가 null을 봄

→ 어느 턴에도 `[단서 방향]`이 발화하지 않는 죽은 기능. **58과 동일한 desync 클래스** (runState 시점 문제).

### 수정 방법 — ui 전달 패턴 (58과 동일)

- `turns.service.ts` 턴 N+1 처리: `pendingQuestHint.setAtTurn === turnNo - 1`이면
  `result.ui.questDirectionHint = { hint, mode }` 부착 후 `pendingQuestHint = null`
  (LOCATION 턴에만 부착. HUB 턴은 현행대로 만료만 — 장소 단서 연출은 LOCATION 전용)
- `server-result.ts`: `UIBundle.questDirectionHint?: { hint: string; mode: string }` 추가
- `context-builder.service.ts` `buildQuestDirectionHint()`: runState 대신 `serverResult.ui.questDirectionHint`를 읽도록 변경 (sanitizeNpcNames 유지). 프롬프트 블록(`[단서 방향]` 5모드 연출)은 무변경
- 만료 정리 로직은 안전망으로 유지 (재접속/HUB 이탈 시 잔존 방지)

### 검증
- 단위: buildQuestDirectionHint가 ui 값을 읽는 스펙
- 라이브: fact 발견 → 다음 턴 DB `llm_prompt`에 `[단서 방향]` + 해당 fact의 nextHint 문자열 실출현 확인 (58 검증에서 "없음"이었던 지점)

### 리스크
- 낮음 — 죽어 있던 기능의 복구라 기존 동작 후퇴 없음. 유일한 체감 변화는 "발견 다음 턴에 연출 힌트가 실제로 나오기 시작"하는 것. 과도하면 quest-balance.config로 발동 확률 외부화 (후속)

---

## 이슈 3 — rng.range 최대값 포함으로 HINT_MODES 범위 초과

### 원인 (실측 확정)

`RngService.range(min, max)`는 **max 포함** (`floor(next * (max - min + 1)) + min`).
`HINT_MODES[rng.range(0, HINT_MODES.length)]` → 1/6 확률로 `HINT_MODES[5] = undefined` (로그 실측: `mode=undefined`).

### 수정 방법

- `turns.service.ts` 2개소 (staleHint 경로 + nextHint 경로): `rng.range(0, HINT_MODES.length - 1)`
- **`rng.range` 시그니처·의미는 절대 불변** — 게임 전역 RNG 결정론(불변식 4)과 기존 확률 분포에 영향 금지
- 전수 감사 완료: `range(0, *.length)` 패턴은 위 2개소뿐

### 검증
- 이슈 2 라이브 검증에서 mode가 5종 중 하나로만 나오는지 로그 확인 (`mode=undefined` 재발 없음)

---

## 커밋 단위

1. `fix(npc): NpcResolver 부분 이름 매칭 + 경로 2 판정 NPC 정합 (이슈 1)` — server
2. `fix(quest): [단서 방향] nextHint ui 전달 복구 + HINT_MODES off-by-one (이슈 2+3)` — server
3. `docs: architecture/59 반영` — docs (본 문서 Status 갱신 + CLAUDE.md Phase 행)

각 커밋 후 `pnpm build` + 관련 jest, 마지막에 로컬 라이브 재검증(58 셋업 재사용) 1회.
