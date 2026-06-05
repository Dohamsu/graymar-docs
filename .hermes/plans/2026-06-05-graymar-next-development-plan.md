# Graymar Next Development Plan

> **For Hermes:** 현재 소스/런타임 상태를 먼저 맞춘 뒤, `subagent-driven-development` 또는 Codex/gstack 방식으로 단계별 구현한다.

**Goal:** NPC 반복/오인 문제를 프로덕션 수준으로 안정화하고, 플레이 가능한 UX 회귀를 막는 다음 개발 사이클을 정의한다.

**Architecture:** Graymar는 루트 문서 레포, `server/` NestJS 백엔드 레포, `client/` Next.js 프론트엔드 레포가 분리되어 있다. 현재 실행 서버는 `server` 레포의 `feat/npc-repetition-guard` HEAD와 일치하므로, 이후 개발은 서버 브랜치 기준으로 검증하고 루트 문서 레포에는 상태/계획만 동기화한다.

**Tech Stack:** NestJS, Drizzle/PostgreSQL, LLM prompt/director services, Next.js, Zustand, Playwright/headless browser QA, launchd.

---

## 0. Verified Current State

- Root repo: `/Users/dohamsu/Workspace/graymar`
  - Branch: `main`
  - HEAD: `9893e40 docs: publish graymar docs and multi NPC playtest script`
  - Dirty state: clean
- Server repo: `/Users/dohamsu/Workspace/graymar/server`
  - Branch: `feat/npc-repetition-guard`
  - HEAD: `ea5f6bd fix: guard npc portrait misattribution`
  - Runtime `/v1/version`: `ea5f6bd`
  - Dirty state: clean
- Client repo: `/Users/dohamsu/Workspace/graymar/client`
  - Branch: `main`
  - HEAD: `50f5262 fix: keep choices visible and accessible`
  - Dirty state: clean
- Latest multi-NPC evaluation reports show 0 auxiliary utterance violations across latest sampled targets.

## 1. Development Priorities

1. **P0 — Runtime/source synchronization**
   - Treat `server@feat/npc-repetition-guard` as the active server source because runtime equals `ea5f6bd`.
   - Decide whether to merge `feat/npc-repetition-guard` into `server/main` or keep it as stabilization branch until QA is complete.

2. **P1 — NPC repetition guard stabilization**
   - Validate the deterministic transfer guard on more characters, locations, and encounter types.
   - Add regression cases for portrait attribution, speaker continuity, player-name echo, unknown NPC alias repetition, and focused NPC mode.

3. **P1 — Browser gameplay QA**
   - Static test/build checks are not enough for Graymar sign-off.
   - Run actual browser playtesting from start screen through character creation, first turns, combat/HUB transition, choice visibility, and NPC reaction scenes.

4. **P2 — Monitoring and operational recovery**
   - Verify `com.graymar.bug-monitor` status separately; current launchd query did not show an active running monitor.
   - Keep `com.graymar.server` launchd version aligned with server HEAD after rebuild/restart.

5. **P2 — Documentation and provenance**
   - Root docs should record which repo/branch is authoritative for current runtime.
   - Each verification report must separate Hermes-verified results from agent self-reports.

---

## Phase 1 — Baseline and Merge Decision

### Task 1.1: Capture clean baseline

**Objective:** Record the exact source/runtime state before further edits.

**Files:**
- Modify: root planning/status document if needed.

**Commands:**
```bash
cd /Users/dohamsu/Workspace/graymar
 git status --short --branch
 git -C server status --short --branch
 git -C client status --short --branch
 curl -sS --max-time 3 http://127.0.0.1:3000/v1/version
```

**Expected:** root/client/server dirty states are clean; server runtime reports `ea5f6bd` or the new rebuilt HEAD.

### Task 1.2: Decide server branch policy

**Objective:** Choose whether `server/feat/npc-repetition-guard` is merged to `main` now or after QA.

**Recommended decision:** Hold merge until Phase 2 QA passes, because the branch contains behavioral guard changes with LLM side effects.

**Verification:**
```bash
cd /Users/dohamsu/Workspace/graymar/server
 git log --oneline main..feat/npc-repetition-guard
```

---

## Phase 2 — NPC Guard Regression Expansion

### Task 2.1: Add high-risk repetition fixtures

**Objective:** Cover repeated user phrases and NPC-name contamination cases.

**Files:**
- Modify: `server/src/llm/npc-repetition-guard.service.spec.ts`
- Modify if needed: `server/src/llm/npc-reaction-director.service.spec.ts`

**Cases:**
- Player repeats exact command 3+ turns.
- Player mentions a non-present NPC name.
- Main NPC answer accidentally borrows previous NPC signature phrase.
- Portrait URL/name attribution cannot transfer between NPCs.

**Run:**
```bash
cd /Users/dohamsu/Workspace/graymar/server
 pnpm test npc-repetition-guard.service.spec.ts
 pnpm test npc-reaction-director.service.spec.ts
```

### Task 2.2: Add integration regression around worker output

**Objective:** Ensure guard behavior survives the full `LlmWorkerService` path, not only unit helpers.

**Files:**
- Modify: `server/src/llm/llm-worker.service.spec.ts`

**Assertions:**
- Guard removes/repairs repeated auxiliary utterance transfer.
- Guard does not strip legitimate main NPC response.
- Guard logs or classifies repair in a debuggable way.

### Task 2.3: Re-run multi-NPC evaluation with expanded targets

**Objective:** Move from sampled pass to stronger confidence.

**Files:**
- Use existing report path: `playtest-reports/`
- Do not create ad-hoc quality scripts unless extending canonical scripts.

**Acceptance:**
- At least 8 NPC targets.
- At least 5 turns per target.
- Auxiliary utterance violation rate remains `0.0`.
- Any false positive is recorded with raw excerpt and classification.

---

## Phase 3 — Browser Gameplay QA

### Task 3.1: Start/verify client and server runtime

**Objective:** Ensure QA targets the current branches.

**Commands:**
```bash
cd /Users/dohamsu/Workspace/graymar/server
 pnpm build
 # restart launchd/kickstart if runtime changed
 curl -sS --max-time 3 http://127.0.0.1:3000/v1/version

cd /Users/dohamsu/Workspace/graymar/client
 pnpm build
 pnpm dev -- --port 3001
```

**Acceptance:** server version equals intended server HEAD; client renders without build errors.

### Task 3.2: Manual/browser smoke path

**Objective:** Verify actual playable UX, not just build correctness.

**Coverage:**
- Start screen and character creation.
- Bonus stat allocation validation.
- First narrative scene.
- Choice buttons remain visible and clickable.
- Streaming block completion.
- At least one NPC interaction scene.
- One combat or HUB transition if reachable.

**Evidence:** screenshot(s), console/network error check, and short QA notes.

---

## Phase 4 — Operations and Monitoring

### Task 4.1: Verify bug monitor desired state

**Objective:** Determine whether bug monitor should remain disabled or be restored.

**Commands:**
```bash
launchctl print gui/$(id -u)/com.graymar.bug-monitor
ls -la ~/Library/LaunchAgents | grep graymar
```

**Acceptance:** Explicit decision recorded: disabled intentionally, or restored with PATH/docker fixed.

### Task 4.2: Server restart procedure check

**Objective:** Ensure production-like restart is reproducible.

**Commands:**
```bash
cd /Users/dohamsu/Workspace/graymar/server
 pnpm build
 launchctl kickstart -k gui/$(id -u)/com.graymar.server
 curl -sS --max-time 3 http://127.0.0.1:3000/v1/version
```

**Acceptance:** runtime commit matches current server HEAD after restart.

---

## Phase 5 — Merge and Documentation

### Task 5.1: Merge server stabilization branch

**Objective:** Move verified NPC guard work into `server/main`.

**Precondition:** Phase 2 and Phase 3 pass.

**Commands:**
```bash
cd /Users/dohamsu/Workspace/graymar/server
 git checkout main
 git merge --ff-only feat/npc-repetition-guard
 pnpm build
 pnpm test
```

**Acceptance:** fast-forward merge succeeds; build/tests pass.

### Task 5.2: Update root documentation provenance

**Objective:** Avoid future confusion between root repo, server repo, client repo, and runtime commit.

**Files:**
- Modify: root architecture/status docs as appropriate.
- Modify: this plan if execution results change priorities.

**Required note:**
- Root repo is docs/meta state.
- Server runtime is sourced from nested `server/` repo.
- Client UI is sourced from nested `client/` repo.

---

## Recommended Next Action

Start with **Phase 2 + Phase 3**, not new feature work. The project is currently in a stabilization window: server runtime already runs the NPC guard branch, latest sampled NPC evaluations are clean, and the remaining risk is whether the guard holds under broader browser gameplay and edge-case regression.
