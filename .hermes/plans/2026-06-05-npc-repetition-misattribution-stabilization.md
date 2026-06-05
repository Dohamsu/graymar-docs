# NPC 반복/오인 방지 안정화 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** `npc-repetition-guard`, `npc-reaction-director`, `llm-worker`를 묶어 NPC 대사 반복·rawInput echo·화자/초상화 오인을 회귀 테스트로 고정하고 운영 안정성을 높인다.

**Architecture:** 플레이어 원문은 보존하고, nano director는 semantic frame/avoid list만 생성한다. 메인 LLM 이후에는 결정적 repetition/speaker/portrait guard가 탐지·부분 보정·로그를 담당하며, Playwright/API playtest가 실제 multi-turn 품질을 검증한다.

**Tech Stack:** NestJS, TypeScript, Jest, Playwright/tsx regression scripts, existing Graymar playtest scripts.

---

## Provenance / Harness

- **Runner:** Hermes 직접 구현 또는 Codex/Claude Code 위임 가능. 구현 시 task별 작은 커밋 권장.
- **Baseline checks:**
  - `git status --short`
  - `cd server && pnpm test -- npc-repetition-guard.service.spec.ts npc-reaction-director.service.spec.ts npc-speaker-continuity.helper.spec.ts npc-dialogue-marker.service.spec.ts`
  - `cd server && pnpm build`
- **Do-not-discard:** 기존 `NpcReactionDirector` semanticFrame, `NpcRepetitionGuard`, `applyNpcSpeakerContinuity`, `NpcDialogueMarkerService`, `scripts/playtest.py`의 V8/V9 판정 로직.
- **Verification gates:** unit tests → server build → API scripted multi-NPC playtest → UI regression smoke.

---

## Acceptance Criteria

1. `rawInput`은 main prompt까지 원문 그대로 전달되고, nano 결과가 replacement input으로 사용되지 않는다.
2. `NpcReactionDirector.semanticFrame.avoidEchoPhrases`에 최근 플레이어 표현, 최근 NPC 표현, 반복 gesture/signature 후보가 들어간다.
3. `NpcRepetitionGuard`는 대사/마커를 깨지 않고 반복을 감지하며, 안전한 서술문만 제거한다.
4. `llm-worker` 후처리 순서는 `marker/speaker normalization → repetition guard → compound title fix → introduction/appearance update → DB/stream emit`로 유지된다.
5. 초상화 `npcId/imageUrl/name`과 narrative marker/speaker가 불일치하면 테스트에서 실패한다.
6. 4명 이상 NPC × 5턴 이상 playtest에서 aux interruption, raw echo, portrait/speaker mismatch가 0이어야 한다.

---

## Task 1: 현재 guard 계약을 테스트로 동결

**Objective:** 기존 동작을 망가뜨리지 않도록 regression baseline을 고정한다.

**Files:**
- Modify: `server/src/llm/npc-repetition-guard.service.spec.ts`
- Modify: `server/src/llm/npc-reaction-director.service.spec.ts`

**Steps:**
1. `NpcRepetitionGuard`에 다음 실패 케이스를 추가한다.
   - rawInput echo는 `LOG_ONLY`이며 대사를 삭제하지 않는다.
   - avoid phrase가 topic atom이면 false positive로 제외한다.
   - `@[이름|portrait] "대사"` 내부는 절대 제거하지 않는다.
2. `NpcReactionDirector`에 다음 계약 테스트를 추가한다.
   - LLM JSON에 `rewrittenInput`이 있어도 반환 타입/호출자가 사용하지 않는다.
   - malformed semanticFrame이면 fallback frame을 만들되 `rawInput`은 보존한다.
3. Run:
   - `cd server && pnpm test -- npc-repetition-guard.service.spec.ts npc-reaction-director.service.spec.ts`

---

## Task 2: avoidEchoPhrases 수집 품질 강화

**Objective:** 반복 후보를 prompt 전에 더 넓게 수집하되 topic nouns는 보존한다.

**Files:**
- Modify: `server/src/llm/npc-reaction-director.service.ts`
- Modify: `server/src/llm/npc-reaction-director.service.spec.ts`

**Implementation:**
- `sanitizeSemanticFrame()` 또는 현재 equivalent 함수에서 다음 후보를 합친다.
  - rawInput clauses: 8자 이상 clause
  - recentNpcDialogues에서 gesture/prose 후보
  - `signature` 배열 중 구체 동작/문장형 표현
  - `recentPlayerActions.rawInput`의 직전 1~2개 clause
- `topicAtoms`와 완전 일치하는 핵심 명사는 avoid에서 제외하거나 guard에서 allow 처리한다.
- 후보 길이/개수 제한: phrase 4~30자, 최대 8개.

**Verification:**
- `avoidEchoPhrases`가 `수지타산`, `안경테를 밀어 올린다`, 직전 player clause를 포함하는지 테스트.
- `장부`, `로넨` 같은 topic atom 단독어는 제거 후보로 오염되지 않는지 테스트.

---

## Task 3: post-generation repetition guard를 “탐지 + 안전 보정”으로 분리

**Objective:** guard가 대사/마커를 깨지 않고 서술문 반복만 줄이게 한다.

**Files:**
- Modify: `server/src/llm/npc-repetition-guard.service.ts`
- Modify: `server/src/llm/npc-repetition-guard.service.spec.ts`

**Implementation:**
- `detect*`와 `repair*` 단계를 내부적으로 분리한다.
- 안전 보정 허용 범위:
  - 따옴표 밖 일반 서술문
  - `@[...]` marker 없는 sentence
  - 같은 normalized sentence가 3회 이상 반복되는 경우
- 보정 금지 범위:
  - NPC 직접 대사
  - marker alias/portrait segment
  - speaker label로 추정되는 문장 시작부
- result에 `metrics` 추가를 검토한다.
  - `rawInputEchoCount`
  - `avoidPhraseEchoCount`
  - `ngramRepeatCount`
  - `gestureRepeatCount`

**Verification:**
- 기존 spec + 신규 spec 통과.
- narrative mutation이 있으면 before/after issue가 남는다.

---

## Task 4: llm-worker 통합 순서와 target NPC 추적 보강

**Objective:** reaction 대상 NPC와 후처리 대상 NPC가 어긋나지 않게 한다.

**Files:**
- Modify: `server/src/llm/llm-worker.service.ts`
- Add/Modify: focused worker spec가 가능하면 `server/src/llm/llm-worker.*.spec.ts`

**Implementation:**
- `reactionNpcId` 산정 결과를 local constant로 보존하고 repetition guard에도 전달한다.
- 현재 guard target 산정(`focusedNpcId → primaryNpcId → speakingNpc`)과 reaction 대상이 다를 때 debug log를 남긴다.
- guard input에 `recentNpcDialogues`도 전달해 recent NPC echo 탐지 기반을 넓힌다.
- stream emit 전 최종 narrative만 DB/stream에 동일하게 사용되는지 주석/테스트로 고정한다.

**Verification:**
- `cd server && pnpm build`
- 가능한 경우 worker unit/integration test에서 `npcReaction.semanticFrame`이 prompt와 guard 양쪽에 전달되는지 확인.

---

## Task 5: 화자/초상화 오인 판정 helper 추출

**Objective:** `scripts/playtest.py`에 흩어진 V8/V9 로직을 TS/Python 중 한쪽에서 재사용 가능한 회귀 판정으로 만든다.

**Files:**
- Create: `scripts/e2e/npc_identity_audit.ts` 또는 `scripts/npc_identity_audit.py`
- Modify: `scripts/playtest.py` 또는 `scripts/e2e/regression.ts`

**Checks:**
- portrait card `npcId`가 narrative marker에 없거나 NPC name/alias와 매칭되지 않으면 fail.
- `XX가 말했다/물었다/답했다`의 XX와 바로 뒤 marker name이 다르면 fail.
- `/npc-portraits/*.webp` 경로가 다른 NPC alias와 결합되면 fail.
- `@[무명 인물]` fallback이 target NPC 턴에서 발생하면 fail.

**Verification:**
- fixture JSON 2개 작성:
  - 정상: speaker/portrait 일치.
  - 실패: 로넨 portrait + 에드릭 speaker mismatch.
- `pnpm exec tsx scripts/e2e/npc_identity_audit.ts --fixture ...` 또는 Python equivalent 실행.

---

## Task 6: 초상화/화자 오인 UI 회귀 테스트 확대

**Objective:** 브라우저/UI 레벨에서 portrait card와 narrative speaker가 동시에 안정적인지 확인한다.

**Files:**
- Modify: `scripts/e2e/regression.ts`
- Possibly Modify: `scripts/e2e/_helpers.ts`

**Implementation:**
- 신규 체크 그룹 추가: `NPC identity regression`.
- 캐릭터 생성 후 첫 LOCATION 대화까지 진행한다.
- DOM에서 다음을 수집한다.
  - 보이는 NPC portrait image src/alt/name
  - narrative text marker 또는 speaker name
  - choice payload/sourceNpcId가 노출되는 경우 해당 값
- 최소 assertion:
  - portrait src가 빈 값이 아님.
  - portrait name과 narrative의 등장 NPC가 불일치하지 않음.
  - 시스템 prompt/marker raw syntax가 UI에 누출되지 않음.

**Verification:**
- `pnpm exec tsx scripts/e2e/regression.ts`
- non-critical UI timing failure와 NPC identity critical failure를 분리한다.

---

## Task 7: scripted multi-NPC 품질 게이트 추가

**Objective:** 실제 LLM 턴에서 반복/오인/aux interruption을 숫자로 확인한다.

**Files:**
- Modify: `scripts/multi_npc_play.py`
- Add: `playtest-reports/` generated output only, commit 여부는 별도 판단

**Scenario:**
- NPC: `edric`, `harlun`, `jwiwang`, `ronen`
- Turns: 각 5턴 이상
- 입력 패턴:
  - 사과 후 재질문
  - 같은 topic 반복 질문
  - 위협/회유 actionType 급변
  - NPC 이름이 들어간 질문

**Metrics:**
- `raw_input_echo_count == 0`
- `avoid_phrase_echo_count == 0` 또는 허용 topic atom 제외
- `aux_utterance_violations == 0`
- `portrait_speaker_mismatch == 0`
- `unknown_speaker_fallback == 0`

**Verification:**
- `python scripts/multi_npc_play.py --scenario repetition_guard --turns 5`
- 최신 report JSON 요약을 최종 보고에 첨부.

---

## Task 8: 문서/운영 토글 정리

**Objective:** 안정화 결과와 롤백 방법을 문서화한다.

**Files:**
- Modify: `architecture/56_npc_reaction_director.md`
- Possibly Modify: `CLAUDE.md`

**Content:**
- `NPC_REACTION_DIRECTOR_ENABLED=false` 롤백 경로.
- repetition guard는 LLM call 없이 deterministic postprocess임을 명시.
- 품질 sign-off는 unit/build가 아니라 multi-turn playtest report 기준임을 명시.

**Final Verification:**
- `git status --short`
- `cd server && pnpm test -- npc-repetition-guard.service.spec.ts npc-reaction-director.service.spec.ts npc-speaker-continuity.helper.spec.ts npc-dialogue-marker.service.spec.ts`
- `cd server && pnpm build`
- `pnpm exec tsx scripts/e2e/regression.ts`
- `python scripts/multi_npc_play.py --scenario repetition_guard --turns 5`

---

## Suggested Commit Sequence

1. `test: lock npc repetition and semantic frame contracts`
2. `feat: strengthen npc avoid phrase collection`
3. `feat: separate npc repetition detection and safe repair`
4. `fix: align llm worker npc reaction and guard targets`
5. `test: add npc identity portrait speaker audit`
6. `test: expand e2e npc identity regression`
7. `docs: document npc dialogue stabilization gates`
