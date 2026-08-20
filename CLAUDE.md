# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Slack 작업 알림 (비활성 — 2026-07-09)

**사용자 지시로 Slack 작업 알림을 보내지 않는다** (완료 알림·중간 보고 모두). 아래 절차는 재활성화를 대비한 기록이다.

모든 유의미한 작업(코드 구현, 버그 수정, 분석, 플레이테스트 등) 완료 시 Slack 웹훅으로 알림을 보낸다.
간단한 질문 응답이나 파일 읽기만 하는 경우는 제외.

### 완료 알림
```bash
curl -s -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"✅ [작업 요약 메시지]\"}" \
  "$(grep SLACK_WEBHOOK_URL /Users/dohamsu/Workspace/graymar/.env | cut -d= -f2)"
```

### 중간 진행 알림 (10분 이상 소요 작업)
10분 이상 소요가 예상되는 작업 시, 약 10분 간격으로 중간 보고를 보낸다.
```bash
curl -s -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"🔄 [진행 상황 메시지]\"}" \
  "$(grep SLACK_WEBHOOK_URL /Users/dohamsu/Workspace/graymar/.env | cut -d= -f2)"
```

- 웹훅 URL: 프로젝트 루트 `.env` 파일의 `SLACK_WEBHOOK_URL`
- 완료 시 `✅`, 중간 보고 시 `🔄` 이모지 사용
- 중간 보고 예시: `🔄 플레이테스트 진행 중 — 3/10 런 완료, 현재 이슈 없음`

## 🚫 이미지 생성 API 호출 절대 금지 (최상위 금지 조항 — 2026-08-02 소유자 지시)

**Claude(에이전트)는 어떤 경우에도 이미지 생성 API를 직접 호출해 이미지를 생성하지 않는다.**
Gemini·DALL·E·Stable Diffusion·OpenRouter 이미지 모델 등 수단 불문, curl/스크립트/코드 실행 경유 불문.

- 게임 에셋 이미지(장면 컷·초상화·장소 등)의 **생성은 소유자 수동 작업 전용** — 에이전트는
  프롬프트 문서 작성·투입 검증·sync·매칭 시스템까지만 담당한다.
- 서버 `scene-image` 모듈(Gemini 장면 이미지)은 **봉인 유지** — 에이전트가 봉인 해제·호출·
  활성화하지 않는다. 해제는 소유자의 명시적 별도 지시로만.
- 예외 없음. "테스트용 1장", "플레이스홀더"도 생성 금지 — 필요 시 **기존 에셋 복사**만
  허용하며 그것도 목적을 보고하고 진행한다.

## 서버 프로세스 관리 (필수)

**⚠️ 서버는 launchd 상주 서비스 `com.graymar.server`(KeepAlive)가 관리한다** —
`node dist/src/main.js`를 graymar/server cwd로 실행하며, kill해도 수 초 내 자동 리스폰된다.
`pnpm start:dev`를 병행하면 launchd 앱과 **포트 경쟁 + LLM 워커 이중 폴링**(신·구 코드가 턴을 번갈아 처리)이
발생한다 (2026-07-09 선택지 검증에서 실측). 관련: `com.graymar.cloudflared`(api.dimtale.com 터널).

### 서버 재시작 (정본 절차)
```bash
cd server && pnpm build && launchctl kickstart -k "gui/$(id -u)/com.graymar.server"
sleep 5 && curl -s http://localhost:3000/v1/version   # 해시·startedAt 확인
cd .. && SMOKE_NO_BROWSER=1 npx -y tsx scripts/e2e/smoke.ts   # 기동 스모크 (~30초·3턴) — 실패 시 배포 실패로 간주
```
스모크는 버전 해시가 못 잡는 기동 시점 결함(팩 로드 실패·env 오타·마이그레이션 불일치)을
잡는다 (하네스 보강 #3, 2026-08-06). 회원가입→런 생성→3턴이 실제로 돌아야 배포 완료.

### dev watch 모드가 꼭 필요할 때만
```bash
launchctl bootout "gui/$(id -u)/com.graymar.server"   # 상주 서비스 내리고
cd server && pnpm start:dev                            # watch 실행
# 작업 후 복귀: launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.graymar.server.plist
```

### 좀비 정리 (포트 충돌 시)
```bash
pkill -f 'graymar/server.*nest.js start --watch' 2>/dev/null
pkill -f 'graymar/server.*pnpm start:dev' 2>/dev/null
# 주의: launchd 앱은 명령줄이 상대경로(dist/src/main.js)라 경로 pkill에 안 걸린다.
# cwd 기준 확인: lsof -c node | awk '$4=="cwd" && /graymar\/server/{print $2}'
lsof -ti:3000 | xargs kill -9 2>/dev/null   # launchd가 자동 재기동함 (정상)
```

### 규칙
- **재시작 = build + kickstart**. `pnpm start:dev`를 launchd 서비스 위에 겹쳐 띄우지 않는다.
- **클라이언트**: Next.js 시작 전 `lsof -ti:3001 | xargs kill -9 2>/dev/null`로 기존 프로세스 정리.
- **다른 프로젝트 주의**: 포트 충돌 시 `ps aux | grep 'nest.js start'` + cwd 확인으로 전체 점검.

## 워크플로우 규칙

- **커밋 푸시 = 서버 재시작까지 한 세트** (2026-07-10): 커밋/푸시는 명시적 요청 시에만 수행하되, 수행할 때는 서버 코드 변경이 포함되면 `pnpm build + launchctl kickstart` 재시작 후 `/v1/version` 해시 일치 확인까지 한 작업 단위로 완결한다. 문서만 변경된 커밋은 재시작 불필요.
- **디버깅**: 버그 수정 시, 표면적 수정 전에 반드시 근본 원인을 조사하라. 사용자가 파악한 원인이 초기 분석과 다르면 확인 질문을 하라.
- **계획 요청**: 사용자가 계획을 요청하면 계획 문서를 직접 작성하라. 명시적으로 요청하지 않는 한 깊은 중첩 에이전트 탐색을 피하라.
- **빌드 검증**: 코드 변경 후 반드시 `pnpm build`(server/client 각각)를 실행하여 빌드 성공을 확인하라.
- **설정 영속화**: 설정은 항상 CLAUDE.md 또는 설정 파일에 영속화하라. 세션 간 상태는 커밋된 파일에 저장해야 한다.
- **설계 문서 검토**: 설계 문서를 동기화하거나 검토할 때, 분석이나 계획을 작성하기 전에 반드시 관련 폴더(`specs/`, `architecture/`, `guides/`)의 모든 파일을 확인하라.

## 브랜치 정책 (2026-07-15)

솔로 개발 + 대부분 저·중리스크 작업 → **main 직접 커밋이 정본**. 브랜치는 "위험한 대공사"에만.

- **main 직접**: 콘텐츠·소규모 엔진·문서 등 저·중리스크 작업은 브랜치 없이 main에 직접 커밋한다 (3레포 공통: server/graymar-server, docs/graymar-docs, client/graymar-client 각각 main).
- **브랜치는 도박에만**: 되돌리기 어렵고 미검증인 대공사(예: 자율 서사 L3 P3~P4 디렉터)만 `feat/*`·`spike/*`로 격리한다.
- **명명 규약**: `spike/*`(관문 검증용, 통과 후 결과를 문서에 남기고 **삭제** — 코드는 정식 `feat/*`로 이관) · `feat/*`(병합 목표) · 폐기 시 `archive/*` 태그로 커밋 보존 후 삭제.
- **수명 제한**: 병합·폐기 즉시 삭제(로컬+원격). 살아있는 `feat/*`는 **2주마다 main에서 rebase**해 behind 누적을 막는다(장수 브랜치 = 병합 지옥).
- **정리 이력**: 2026-07-15 stale 8개 삭제(병합완료 7 + 방치실험 1), 자율 트랙 `spike/dynamic-npc-p0`·`feat/npc-repetition-guard`는 `archive/*` 태그 보존 후 삭제. `feat/dynamic-npc-registry`(자율 서사 P1~P6 통합)는 2026-07-16 관문 통과 후 main 병합·삭제. **현재 살아있는 feat 브랜치 = 0개** (3레포 모두 main만).

## 플레이테스트

- **정본 스크립트**: `scripts/playtest.py` — 이 파일만 사용. 새 스크립트를 생성하지 않는다.
- **테스터 계정 = 정본 재사용 (수집+제외, 삭제 금지)**: `playtest.py`는 정본 `playtest@test.com`을 register-or-login 재사용(`--new-account` 시에만 신규). 테스터 로그는 **보존**하되 어드민 대시보드가 도메인 기반으로 실유저 집계(가입·활성·런·턴·포인트)에서 제외한다(`server/src/common/tester.util.ts`). **테스터 대량 삭제 금지** — arch/87 §10.
- **커맨드**: `/playtest` (`.claude/commands/playtest.md`)
- **기본 턴 수 = 10~15턴** (2026-07-13 지시): 일반 테스트는 `--turns 10`~`15`로 짧게 실행한다. 40턴 같은 롱런은 **엔딩 완주·롱런 검증 등 별도 명시 지시가 있을 때만**. 표본이 더 필요하면 40턴 단회 대신 10~15턴 **다회 누적**으로 축적한다 (키 한도·시간 비용 절감).
- **API 필드 확인**: 플레이테스트 스크립트 수정 시, 파싱 로직 작성 전에 API 응답 필드명을 정확히 확인하라 (예: `id` vs `choiceId`). 실제 API 응답 구조를 샘플 호출로 먼저 확인하라.
- **실행 경로 주의**: 반드시 레포 루트(`/Users/dohamsu/Workspace/graymar`)에서 실행. 서버 커밋 작업 후 shell cwd가 `server/`에 남아 `scripts/playtest.py`를 못 찾는 함정이 반복 실측됨 — 절대 경로 또는 `cd` 명시.
- **에이전트 플레이어 모드**: `--agent coercer|chatty|weirdo|brawler|sneaky_liar|devotee` — LLM이 서술을 읽고 페르소나 유지 플레이 + 위화감 자동 노트. 검증 목적별: coercer(압박·fear축적) / chatty(대화·roaming) / weirdo(기행·재해석) / brawler(폭력·전투기만) / sneaky_liar(REPORT — susp만 축적) / devotee(APPROACH — 한 NPC 전담 우호).

## 팩 에셋 풀 — 이미지 투입 정책 (arch/80)

소유자가 NPC·장소 이미지를 제공하면 고정 매핑 없이 자동 매칭한다 (카른홀트 최초 적용, 타 팩 확장 가능).

- **투입 위치**: `content/<pack>/assets/portraits/` (NPC 초상화), `content/<pack>/assets/locations/` (장소).
- **정본 스크립트**: `python3 scripts/sync_pack_assets.py <packId>` — **이 스크립트만 사용, client/public 수동 복사 금지**. 파일명의 한글 실명이 URL에 남으면 미소개 실명→별칭 치환 안전망이 URL까지 치환해 404 발생 (2026-07-19 실측: '오슬라'→'행주 쥔 안주인'). sync가 ASCII 슬러그(portrait_01.webp)로 정규화해 방어한다.
- **파일명 힌트 (선택)**: `_`/`-` 토큰 구분. 성별 `m/f/남/여`(초상화만), 키워드 = NPC 이름·role·locationId 토큰, `day`/`night` = 장소 시간대 필터. 무힌트 = 범용 (동적 NPC 몫).
- **반영 절차**: 이미지 배치 → sync → **서버 재시작** (저작 NPC 배정은 팩 로드 시 1회) → client push (public/ 포함 Vercel 자동 배포).
- **배정 원칙**: 런 내 같은 얼굴 고정(runState 영속)·이미지당 1인(중복 배제, 소진 시 실루엣)·풀 비면 완전 무동작·타 팩 이미지 fallback 금지. 상세: architecture/80.

## 품질 검사 워크플로우 (필수)

품질 검사를 수행할 때 반드시 **정본 스크립트 `scripts/audit_quality.py`** 만 사용한다 (v4). 임시 스크립트(`/tmp/audit_*.py`)를 새로 작성하지 말고, 개선이 필요하면 정본에 반영한다.

### 심층 검사 3단계 (audit_quality.py에 내장)
1. **1차 regex 탐지** — 예외/서술체/대사체/금지어/세계관 전범주
2. **각 감지 이슈마다 자동 심층 검사**:
   - 원문 50자 context 추출
   - `server/src/llm/prompts/system-prompts.ts` grep — 명시 금지어 여부 확인
   - 대사 내부(`"..."` 내) / 외부(서술) 문맥 판정
   - `/npc-portraits/xxx.webp` URL 내부 여부 확인
3. **자동 분류**: `real`(실제 위반) / `gray`(회색지대) / `fp`(false positive)

### 금지 사항
- 감지 결과를 **원문 대조 없이** 사용자에게 그대로 보고하지 않는다.
- regex 매칭 성공 = 위반 ❌ (항상 심층 검사 통과 후 판정)
- word boundary 없이 키워드 매칭하지 않는다 (예: "한복" 이 "한복판"에 오매칭).
- 사용자가 "이전 검증이 맞는지 재검토"를 요청하기 전에 **1차 보고 단계에서 FP 자동 필터링이 완료되어야 한다**.

### 새 감지 패턴 추가 시
1. `system-prompts.ts` 에서 실제 금지어 명시 여부 확인
2. `audit_quality.py` 의 `META_NARR_FORBID` / `EASTERN_FORBID` / `CURRENCY_FORBID` 딕셔너리에 word boundary 포함한 regex로 추가
3. `check_prompt_explicit()` 로 프롬프트 대조 가능한지 검증

## 콘텐츠 정합성 감사 (필수 — 팩 편집 시)

콘텐츠 팩(`content/<pack>/`)을 편집·추가했으면 **정본 스크립트 `scripts/audit_content.py`** 를 돌린다.
서술 품질을 보는 `audit_quality.py` 와 역할이 다르다 — 이쪽은 **파일 간 참조와 도달성**을 본다.
서버 부팅 시 도는 `ContentValidatorService` 는 NPC 단위 4개 룰만 보므로 이걸 대체하지 않는다.

```bash
python3 scripts/audit_content.py                 # 전 팩 (ERROR 있으면 종료코드 1)
python3 scripts/audit_content.py star_sand_v1    # 단일 팩
python3 scripts/audit_content.py --json          # 기계 판독
```

3계층: **L1 참조 무결성**(모든 ID 참조가 실제 정의로 해소되는가) · **L2 팩 계약**(불변식 45 questState
명명·`resolutionConditions`·`payload.tags`, 불변식 31 `defaultTraitId`, ArcRoute enum) · **L3 심층 점검**
(획득 불가 fact → 도달 불가 questState 전환 → 엔딩 차단, 도달 불가 장소, 사문 배선 스키마).

- **확인됨(ack)**: 오탐·의도된 항목은 `--ack '<KEY>' --note '사유'` 로 `content/<pack>/.audit-ack.json`
  에 등록하면 다음 실행부터 억제된다 (`--show-acked` 로 확인, `--unack` 로 해제). 반복 오탐이 신호를
  덮는 걸 막는 장치이므로, **끄기 전에 반드시 원문을 대조**한다.
- **사문 배선(silently-dead) 검출이 핵심 값어치**: `NPC_SCHEDULE_SHAPE` 는 콘텐츠가 엔진이 못 읽는
  모양으로 저작돼 조용히 무시되는 경우를 잡는다 (arch/21 Part 11 의 `agenda` vs `longTermAgenda` 부류).
  새 콘텐츠 필드를 엔진에 추가하면 **여기에 모양 검사를 같이 넣는다.**
- 규칙 추가는 정본에 반영한다. 임시 스크립트를 새로 만들지 않는다.

## Repository Overview

LLM-powered turn-based text RPG — **정치 음모 RPG**에서 이름 없는 용병이 왕국의 권력 투쟁을 거쳐 성장한다. 서버가 모든 게임 로직을 결정론적으로 처리하고, LLM은 내러티브 텍스트만 생성한다.

## Project Structure

```
├── server/              ← NestJS + Drizzle ORM + PostgreSQL 백엔드
├── client/              ← Next.js 16 + Zustand + Tailwind v4 프론트엔드
├── admin/               ← 어드민 콘솔 (독립 레포 graymar-admin, Vercel 별도 배포 — arch/87)
├── specs/               ← 원본 상세 설계 스펙 (17 md, 정본 참조)
├── architecture/        ← 통합 아키텍처 문서 (91 md + INDEX.md 색인, 실무 참조, archive 4 md)
├── guides/              ← 코드 구현 지침 (14 md, 서비스맵/컴포넌트맵/구현가이드/팩 에셋·아이템·장면 컷·주사위 프롬프트)
├── schema/              ← DB 스키마, JSON Schema, OpenAPI (3 files)
├── samples/             ← 샘플 페이로드 (JSON, 10 files)
├── content/             ← 게임 콘텐츠 시드 데이터 (graymar_v1 + star_sand_v1 별빛모래 + karnholt_v1 자율 서사 AUTONOMOUS 팩 (silverdeen_v1 은 2026-08-18 제거))
├── agents/              ← 에이전트 역할 정의서 (5 md)
├── scripts/             ← 플레이테스트 등 자동화 스크립트 (playtest.py, audit_quality.py, audit_content.py 외)
├── playtest-reports/    ← 플레이테스트 분석 리포트
└── CLAUDE.md
```

## Development Commands

### Server (NestJS, port 3000)
```bash
cd server
pnpm install
pnpm start:dev          # nest start --watch
pnpm test               # jest (unit tests)
pnpm test:cov           # jest --coverage
pnpm build              # nest build
pnpm lint               # eslint --fix
```

### Client (Next.js 16, port 3001)
```bash
cd client
pnpm install
pnpm dev -- --port 3001  # next dev
pnpm build               # next build
pnpm lint                # eslint
```

### Database (PostgreSQL via Docker)
```bash
cd server
docker compose up -d                           # DB 컨테이너 시작
npx drizzle-kit push                           # 스키마 push
npx drizzle-kit generate                       # 마이그레이션 생성
DATABASE_URL=postgresql://user:password@localhost:5432/textRpg
```

### Run a single test
```bash
cd server && pnpm jest -- --testPathPattern=rng.service
```

## Architecture (요약)

> 상세 서비스 맵: [[guides/01_server_module_map|server module map]]
> 상세 컴포넌트 맵: [[guides/02_client_component_map|client component map]]

### Server — 16 modules, 117 services, 21 controllers

| 모듈 | 서비스 수 | 역할 |
|------|----------|------|
| common/ | - | Guards, Filters, Pipes, Decorators |
| auth/ | 1 | JWT 인증 (register/login) |
| db/ | - | Drizzle ORM (27 tables / 25 schema files, 45 타입 파일) |
| content/ | 2 | 게임 콘텐츠 로더 — 멀티 팩(4팩) 캐시 + AsyncLocalStorage 스코프 + scenarios.controller (GET /v1/scenarios, creation-bundle) |
| engine/rng,stats,status | 3 | RNG, 스탯 계산, 상태효과 |
| engine/combat | 5 | Hit, Damage, EnemyAI, PropMatcher, CombatService |
| engine/input | 3 | RuleParser → Policy → ActionPlan |
| engine/nodes | 7 | 노드별 리졸버 + 전이 |
| engine/rewards | 5 | 보상, 인벤토리, 장비, 접미사, Legendary |
| engine/hub | 41 | HUB 엔진 6 서브시스템 (아래 참조) |
| engine/planner | 1 | RUN 구조 생성 (RunPlannerService) |
| runs/ | 2 | RUN 생성/조회 + BugReportService |
| turns/ | 6 | 턴 제출/조회 + 도메인 분할 서브서비스 5종 (TurnShared·EquipShopTurn·DagTurn·HubTurn·CombatTurn — arch/77 §18) |
| llm/ | 24 | Worker, ContextBuilder, TokenBudget, Prompt, NpcDialogueMarker, NanoDirector, NanoEventDirector, NpcReactionDirector, ChallengeClassifier, ThemeClassifier, DialogueGenerator, LlmStreamBroker, StreamClassifier, SceneCutMatcher, FactExtractor, Lorebook, MemoryRenderer, PlotDirector, PlotSeedGenerator, LlmCallLog 외 |
| scene-image/ | 1 | AI 장면 이미지 (Gemini, rate limit) |
| portrait/ | 1 | 초상화 업로드/생성 (독립 모듈) |
| campaigns/ | 1 | 캠페인 구조 (독립 모듈) |
| endings/ | - | 여정 아카이브 조회 (GET /v1/endings, SummaryBuilder는 engine/hub 소속) |
| party/ | 8 | 파티 시스템 (Party, Chat, Stream, Lobby, PartyTurn, Vote, Reward, RunParticipants) |
| points/ | 1 | 포인트 차감·환불·충전 코드 (arch/85) |
| admin/ | 3 | 관제 API — stats/users/runs/llm/health/audit/parties 컨트롤러 7종 + 공개 통계 (arch/87) |

### HUB 엔진 6 서브시스템 (41 services)

| 서브시스템 | 수 | 핵심 서비스 |
|-----------|---|------------|
| Base HUB | 12 | WorldState, Heat, EventMatcher, Resolve, IntentParserV2, QuestProgression, SceneShell, Agenda, Arc, TurnOrchestration, NpcResolver, SuddenActionDetector |
| Narrative Engine v1 | 9 | Incident, WorldTick, Signal, NpcEmotional, Mark, Ending, Operation, Shop, SummaryBuilder |
| Structured Memory v2 | 2 | MemoryCollector, MemoryIntegration |
| User-Driven Bridge | 6 | IntentV3Builder, IncidentRouter, WorldDelta, PlayerThread, Notification |
| Narrative v2 & Event v2 | 4 | IntentMemory, EventDirector, ProceduralEvent, LlmIntentParser |
| Living World v2 | 8 | LocationState, WorldFact, NpcSchedule, NpcAgenda, ConsequenceProcessor, SituationGenerator, PlayerGoal, NpcWhereabouts |

> 상세: [[guides/03_hub_engine_guide|hub engine guide]]

### Client — 71 components, 7 stores

| 영역 | 수 | 핵심 |
|------|---|------|
| narrative/ | 6 | NarrativePanel, StoryBlock, StreamingBlock, DialogueBubble, NpcPortraitCard, narrative-text(+compact-dialogue 연속 대사 초상화 생략 규칙) |
| input/ | 2 | InputSection, QuickActionButton |
| hub/ | 8 | HeatGauge, TimePhaseIndicator/Transition, LocationHeader, ResolveOutcomeBanner, DiceFace, Dice3D, PackMeterGauge (HUB 본체는 GameClient/NarrativePanel 렌더) |
| location/ | 5 | TurnResultBanner, LocationToastLayer, LocationBackdrop(장소 배경 지속화 arch/93), DeadlineBanner, EquipmentDropToast |
| screens/ | 11 | StartScreen(+start-screen/ 하위 5), EndingScreen, RunEndScreen, NodeTransitionScreen 외 |
| side-panel/ | 7 | SidePanel, CharacterTab, InventoryTab, EquipmentTab, SetBonusDisplay, NpcDossierTab, QuestTab |
| ui/ | 14 | ErrorBanner, LlmFailureModal, BugReportButton, BugReportModal, NetworkStatus, PageTransition, SplashScreen, InstallPrompt, NewsModal, PortraitCropModal, PointsModal, HpReadout |
| layout/ | 1 | Header (데스크톱 HUD + 모바일 MobileHeader 햄버거 탭 메뉴, 자동 숨김) |
| battle/ | 4 | BattlePanel 외 (창의 전투 버튼 폼 + 적 카드 + 펼침 + 아이템 모달) |
| party/ | 12 | PartyHUD, PartyLobby, LobbyLoadoutPicker, PartyChatWindow, PartyChatInput, PartyTurnStatus, VoteModal, LootDistribution 외 |
| brand/ | 1 | 브랜드 로고/타이포 |

Stores: game-store(+game-store.helpers), game-selectors, settings-store, auth-store, party-store, points-store.

### Key Data Flow

```
HUB: CHOICE → moveToLocation → LOCATION 노드 생성 → Scene Shell
LOCATION: ACTION/CHOICE → IntentParserV2 → EventDirector → ResolveService(1d6+stat)
  → ServerResultV1 (DB commit) → [async] LLM Worker → narrative text
COMBAT: ACTION/CHOICE → RuleParser → Policy → NodeResolver → ServerResultV1
```

## Tech Stack

| Layer | Tech | Version |
|-------|------|---------|
| Backend | NestJS | 11.0 |
| ORM | Drizzle ORM | 0.45 |
| DB | PostgreSQL | 16 |
| Validation | Zod | 4.3 |
| Frontend | Next.js | 16.1 |
| React | React | 19.2 |
| State | Zustand | 5.0 |
| Styling | Tailwind CSS | 4 |
| LLM | Gemma 4 31B dense (메인, stream:true, provider allowlist Friendli·Venice·Novita·CoreWeave) / **gpt-5.6-luna** (5:5 교차 — 짝수 턴. 2026-08-13 DeepSeek 교체: 어체 위반 43~46%→6.4%, 마커 커버리지 75%→100% 실측) / GPT-4.1 Mini (fallback) / GPT-4.1-nano (경량) | Multi-provider via OpenRouter (arch/25 부록 D·D-8) |

## LLM 설계 원칙 (필수 참고)

LLM 관련 기능(서술 생성, 프롬프트, 후처리)을 추가/수정할 때 **반드시** 다음 특성을 선제 고려한다.

### 본질적 한계
1. **Stateless** — 매 호출마다 독립. 이전 턴/대사/제스처 자동 기억 없음. "너 지난번에 뭐 썼어" 모름.
2. **학습된 기본값 편향** — "안경테를 밀어 올리며", "약속이라도 한 듯" 같은 문학적 관용구를 **무의식적 기본값**으로 재사용. 프롬프트 규칙만으론 제어 안 됨.
3. **비슷한 context → 비슷한 출력** — 확률적 샘플링이지만 유사 프롬프트면 유사 응답 수렴.
4. **Soft 지시 무시** — "자제", "피하세요", "~지 마세요" 같은 부드러운 지시는 자주 무시.
5. **풍선효과** — 단일 어휘 금지 시 **의미적 동의어**로 우회 (예: "시선을 피하다" 금지 → "고개를 돌린다" 증가).

### 대응 원칙
1. **Stateless 보완 = 명시적 주입** — LLM에게 "너 이전에 뭘 썼어"를 **데이터로 제공**. NPC state(사용 제스처), 세션 등장 횟수, overused phrases 등을 프롬프트에 구조화해서 넘김.
2. **Negative(금지)보다 Positive(권장 풀) 우선** — "X 사용 금지" 대신 "다음 중 하나를 선택: Y, Z, W"가 LLM 준수율 높음.
3. **선택지 축소로 유도** — 프롬프트 목록에서 과사용 옵션을 **먼저 제거**하면 LLM이 새 옵션 고를 수밖에 없음 (예: BG NPC 로테이션 풀).
4. **사후 삭제는 최후 수단** — 출력을 regex로 제거하면 문장 구조 파괴 위험. 입력(프롬프트) 단계에서 해결 가능하면 우선 시도.
5. **카테고리 단위 통제** — 풍선효과 방지 위해 동의어 묶음(제스처/감각/배경 NPC 집합) 단위로 제어.
6. **프롬프트 최소주의** — 규칙 추가는 기존 규칙 희석. 동일 효과를 **서버 로직/데이터 주입**으로 달성 가능하면 그쪽 우선.

### 이 원칙이 깨진 실제 사례 (반면교사)
- "반복 구문 금지" 프롬프트 규칙 추가 → LLM 무시 → 사후 삭제 regex 추가 → 문장 파괴 → 또 다른 동의어로 우회 → 악순환. 근본 해결은 "NPC State 에 사용 제스처 축적 + 프롬프트에 Positive framing 주입".

## Critical Design Invariants

1. **Server is Source of Truth** — 모든 수치 계산, 확률 롤, 상태 변경은 서버에서만.
2. **LLM is narrative-only (하드 상태 한정)** — LLM은 **하드 상태**(HP·골드·인벤토리·questState·판정 결과)를 절대 쓸 수 없다. 실패해도 게임 진행 (턴은 LLM 호출 전에 커밋, llmStatus 게이트 없음). 단 **소프트 상태**는 나노 LLM 출력이 `applyRunStatePatch` CAS(fresh 재조회 + jsonb 낙관적 잠금, llm-worker.service.ts) **경유로만** 역류가 허용된 설계된 회색지대다: NPC 감정 블렌드(emotionalShiftHint, arch/76 D3-b′)·작별 감지(npcFarewell)·소개 성사(NpcAppearance)·테마 기록·nextBeats·propsTrace·장면 컷 상태(sceneCutState, arch/96). 새 역류 경로 추가 시 ① 하드 상태 금지 ② CAS 경유 ③ 이 목록 등재의 3조건을 지킨다.
3. **Idempotency** — `(run_id, turn_no)` + `(run_id, idempotency_key)` unique.
4. **RNG determinism** — `seed + cursor` 저장. COMBAT: hitRoll → varianceRoll → critRoll. LOCATION: EventMatcher(가중치) → ResolveService(1d6).
5. **Theme memory (L0) 불변** — 토큰 예산 압박에도 삭제 금지.
6. **Action slot cap = 3** — Base 2 + Bonus 1. 초과 불가.
7. **diff → client only** — LLM에는 events/summary만 전달, 수치 diff는 클라이언트 HUD용.
8. **distance/angle per-enemy** — BattleState.enemies에만 존재, playerState에 없음.
9. **HUB Heat ±8 clamp** — 한 턴에 Heat 변동은 ±8 제한. 0~100 범위.
10. **Action-First 파이프라인** — LOCATION에서 플레이어 ACTION이 먼저, 이벤트 매칭이 후.
11. **고집(Insistence) 에스컬레이션** — suppressedActionType 3회 연속 → 강한 actionType 승격.
12. **LOCATION 판정 = 1d6 + floor(stat/4) + baseMod** — SUCCESS ≥ 5, PARTIAL 3~4, FAIL < 3.
13. **이벤트 고유 선택지 우선** — payload.choices > suggested_choices > LOCATION 기본.
14. **LOCATION 단기기억** — locationSessionTurns(최대 6턴+MidSummary) LLM 전달. 떠날 때 요약 저장.
15. **NPC 이름 비공개→공개 — 자기소개 사전 확정** — FRIENDLY·FEARFUL 1회 / CAUTIOUS 2회 / CALCULATING·HOSTILE 3회 임계 도달 시 **본인이 직접 자기소개** (전 성향 통일, posture별 톤 차등). nano가 실명 포함 대사를 사전 생성(서버 검증+어체별 템플릿 보장) → 프롬프트 positive 주입 → 미반영 시 그 턴에 별칭 마커로 서버 삽입 (지연 0턴). 성사 판정은 "실명이 따옴표 대사 안에 등장". 2턴 분리는 **마커 표시명** 기준(소개 턴 별칭 마커, 다음 턴부터 실명 — IntroMarkerNorm)이며 본문·대사 실명은 소개 턴부터 허용. 재등장 공개·생성 실패 예외만 외부 경로(제3자 호명/단서) fallback. 미소개 실명 차단·IntroRollback은 유지 — architecture/66.
16. **장면 연속성 보장** — sceneFrame 3단계 억제 + 씬 이벤트 1턴 유지 + 7개 연속성 규칙.
17. **Token Budget 2단** — 메모리 블록 2500(블록별 배분·저우선 트리밍) + 프롬프트 총량 백스톱 `GRAND_TOTAL_CHAR_BUDGET` 16,500자(≈10.06k tok — 11k부터 soft 지시 절벽 실측, 마진 0.9k tok. 2026-07-28 상향은 압축 선행 후에만 허용). 백스톱 제거 순서는 [세계 상태] → [NPC 일상] → 기억 부분 절삭 — 기억·L0 절대 보호. **백스톱은 하드 상한이 아니다** — 제거 대상 블록이 없거나 작으면 초과분이 그대로 남는다 (실측 494/2,781턴 = **17.8%가 16,500 초과**, 최대 16,620자. arch/101 자기점검 1회차). 상한처럼 읽고 여유를 계산하면 틀린다. 재비대는 플레이테스트 V12 게이트(발동률 ≤20%·avg ≤15,000자)가 감시 — arch/79 2·3차.
18. **Procedural Plot Protection** — 동적 이벤트에서 arcRouteTag/commitmentDelta 절대 금지.
19. **NATURAL 엔딩 최소 15턴 (자동 발동 한정 — arch/103 개정)** — ALL_RESOLVED 엔딩의 **자동 발동**(S5+5 타이머·incident 자연 해소)은 totalTurns ≥ 15 이상이어야 한다. 명시 결말 선택(`arc_finale` — 커밋+스테이지 완주 후)은 이 가드의 예외.
20. **RUN_ENDED 시 메모리 통합** — go_hub/MOVE_LOCATION 없이 런 종료 시에도 finalizeVisit() 호출.
21. **MOVE_LOCATION fallback** — 목표 장소 불명확 시 HUB 복귀 처리 (이동 의도 무시 방지). KW MOVE_LOCATION은 장소명+이동접미사 복합감지 시에만 LLM보다 우선. 단순 키워드 1-hit은 LLM 신뢰.
22. **Living World 초기화** — createRun 시 locationDynamicStates(팩의 locations 전체), worldFacts(빈 배열), npcLocations, playerGoals 초기화 필수.
23. **NPC 3계층** — CORE 우선 상황 생성, BACKGROUND 배경만, SUB 일반 (수치는 팩별 — graymar 6/25/12). **화자 결정 단계에도 적용(arch/104)** — BACKGROUND 는 대화 잠금 대상에서 제외한다. 명시 지목 턴에는 그 턴 화자로 설 수 있으나 붙잡히지는 않는다. 과거 이 규칙이 상황 생성에만 걸려 있어 배경 NPC 가 17턴 주 화자로 눌러앉은 실측이 있다.
24. **선별 주입(Selective Injection)** — LLM 컨텍스트에 메모리를 주입할 때, 전체가 아닌 현재 턴에 관련된 것만 선별: NpcPersonalMemory는 등장 NPC만, LocationMemory는 현재 장소만, IncidentMemory는 관련 사건만, ItemMemory는 장착/획득(RARE 이상) 아이템만.
25. **프리셋 배경 참조** — 프리셋별 npcPostureOverrides(NPC 초기 태도 오버라이드), actionBonuses(행동 보너스), LLM 배경 텍스트가 게임 메카닉과 서술 모두에 반영.
26. **대화 잠금(Conversation Lock) — 3상태 + streak 상한 (arch/104, 2026-08-18 개정)** — 판정 정본은 `engine/hub/conversation-lock.core.ts` 단일 순수 함수이며, 접근은 `NpcResolverService.getLockState()` 하나뿐이다(구 `findLockFromHistory`/`findConversationLock` 복제 제거). 행동을 3분류한다: **RENEW**(TALK/PERSUADE/BRIBE/THREATEN/HELP — 유지 + streak +1) · **HOLD**(OBSERVE/INVESTIGATE/SEARCH/TRADE/REST — 유지하되 streak 불변) · **BREAK**(FIGHT/STEAL/SNEAK/MOVE_LOCATION 등 + 미상 행동 — 해제). 상한은 CORE·SUB 4턴, **BACKGROUND 0(잠금 대상 제외 — 불변식 23)**. 상한 도달은 소프트 해제(배제 아님). 작별(dialogueAct=FAREWELL 또는 워커 마킹 npcFarewell) 이후 해제, 무화자 턴은 `ANCHOR_WINDOW`=4턴까지만 건너뛴다. 상태를 저장하지 않고 매 턴 재계산한다. **배경**: 구 구현은 화자 있는 첫 이력에서 즉시 return/break 해 연속 카운터가 없었고, 갱신 집합에 OBSERVE·INVESTIGATE·TRADE 가 포함돼 혼자 서류를 보는 턴이 "대화"로 집계됐다 — BACKGROUND NPC 가 17턴 독점(그 구간 대화 행동 2턴)·fact 획득 0 실측.
27. **NPC knownFacts 점진 공개 + 기록·서술 단일화** — SUCCESS/PARTIAL 판정 + 정보행동 시 NPC 보유 fact 중 **입력 주제 매칭 우선**(없으면 순서) 공개. 발견 fact는 `ui.questReveal`로 LLM 서술에 동일 주입되어 기록 fact = 서술 fact 보장 (architecture/58). 이벤트 discoverableFact는 SUCCESS=100%, PARTIAL=50%. FAIL은 미공개.
28. **퀘스트 자동 전환** — discoveredQuestFacts 누적 → quest.json stateTransitions 조건 충족 시 questState 자동 전환 (S0→S1→...→S5).
29. **questFactTrigger SitGen 바이패스** — 미발견 fact 이벤트가 있는 장소에서 매 턴 이벤트 매칭 허용. 이때 SituationGenerator를 건너뛰고 EventDirector로 직행하여 fact 이벤트 매칭을 보장.
30. **밸런스 상수 외부화** — SitGen 확률, PARTIAL 발견률, weight 부스트 등 핵심 밸런스 상수는 `quest-balance.config.ts`에서 관리. 코드 내 하드코딩 금지.
31. **bonusStats deprecated + 배경 시그니처 특성 (arch/97, 2026-08-04 개정)** — 생성 간략화로 스탯 +6은 프리셋 stats에 내장, 특성은 `preset.defaultTraitId`를 서버 createRun이 자동 부여(전송 traitId가 우선). bonusStats는 구클라 호환용 optional — 전송 시에만 합계 6 검증. 새 프리셋 추가 시 defaultTraitId 지정 + 배분 +6 내장 필수.
32. **특성 런타임 효과** — GAMBLER_LUCK(FAIL→50%PARTIAL, 크리티컬 비활성), BLOOD_OATH(저HP 보너스 +2/+3, 치료 50%↓), NIGHT_CHILD(밤+2, 낮-1). traitEffects는 runState에 저장, resolve/combat에서 참조.
33. **TurnMode 3분류** — PLAYER_DIRECTED(기본값, NPC 지목 시) / CONVERSATION_CONT(대화 연속) / WORLD_EVENT(첫진입/pressure≥70/questFact). determineTurnMode()에서 이벤트 매칭 전 결정.
34. **NPC 결정 5단계 우선순위** — 텍스트매칭 > IntentV3.targetNpcId > 대화잠금 > NanoEventDirector추천(WORLD_EVENT만) > 이벤트배정. Player-First 원칙. **선행 예외(Step 0/0b)**: CHOICE 선택지의 명시 npcId(arch/65), 그리고 **이벤트 고유 선택지(sourceEventId=매칭 이벤트) 클릭 시 이벤트 primaryNpcId**가 대화잠금보다 우선 (V10-② 2026-07-17 — 심문 이벤트 선택지 응답이 직전 대화 상대로 어긋난 분열 해소).
35. **맥락 NPC 연결** — FIGHT/STEAL 후 TALK 시 직전 턴 primaryNpcId를 contextNpcId로 유지. 대화 잠금이 아닌 약한 연결. **역방향(2026-07-17)**: TALK/THREATEN 후 대상 미명시 FIGHT/STEAL도 직전 상대에게 잇는다 — NpcResolver Step 5b(CONTEXT_CONTINUITY)가 EVENT_PRIMARY보다 우선.
36. **NanoEventDirector 비동기** — turns.service에서 nanoCtx만 빌드, LLM Worker에서 비동기 generate(). 턴 응답에서 nano LLM 대기 제거.
37. **LLM 스트리밍** — OpenRouter stream:true + SSE 브로커 + 문장 단위 버퍼링. JSON 모드에서는 스트리밍 표시 차단.
38. **NPC 불일치 교정** — LLM 서술의 첫 @마커 NPC가 primaryNpcId와 다르면 마커+본문을 강제 교체 (Step F).
39. **NpcReactionDirector + 추상 톤 3축** — 메인 LLM 호출 전 nano로 NPC 반응(7종)+즉시목표+추상톤 3축(voiceQuality/emotionalUndertone/bodyLanguageMood) 사전 결정. 메인 LLM은 추측 대신 결정 표현. 톤 가이드는 추상만(예시 어구 절대 금지).
40. **자유 행동 주사위 스킵** — ChallengeClassifier가 룰 게이트(NON_CHALLENGE/ALWAYS_CHALLENGE) + 회색지대 nano 분류로 FREE/CHECK 결정. FREE면 주사위 스킵 + 자동 SUCCESS.
41. **personality.signature 메인 LLM 노출 금지** — 정적 어구 풀이 LLM에 노출되는 한 positive/negative 무관하게 anchor 발생. PromptBuilder에서 signature 노출 모두 제거. speechStyle/core만 어조 가이드.
42. **personality.speechStyle 어구 예시 금지** — speechStyle 본문에 따옴표로 인용된 구체 어구 예시는 LLM 학습 → 매 턴 직접 사용 → 어휘 폭주 유발. 어조/어미/속도/태도/금지사항만 추상 묘사. (예: "회피 어휘 대신 군인 직설 — '낭비 마시오' 등" → "회피 어휘 대신 군인 직설로 시간·효율·기강 강조")
43. **마커 substring 합쳐짐 자동 복구** — `@[X|...]` 별칭 안 동일 substring(8자+) 2회 등장 감지 시 알려진 unknownAlias로 복원 + `[MarkerCollision]` 경고 로그.
44. **사교 발화 fact 게이트** — 순수 사교 발화(dialogueAct: GREETING/WELLBEING/THANKS/FAREWELL, `common/dialogue-act.ts`) 턴은 NPC fact 공개 경로·인계/보류 힌트를 타지 않는다 (잡담 모드로 전환). 질문 턴은 비주제 fallback fact 공개 금지 — 물은 것과 무관한 단서로 답하지 않는다. BRIBE/THREATEN은 면제. **대화 계열(TALK/PERSUADE/TRADE/HELP)은 주제 매칭 시에만 fact 공개** — 잡담·인사에 NPC가 먼저 단서를 흘리지 않는다(선제 단서 억제, arch/68 부록 M). 조사·탐색(INVESTIGATE/SEARCH/OBSERVE)은 확률 fallback 유지. **잡담(daily_topic) 주입 게이트는 화이트리스트(arch/104, 2026-08-18)** — 정본은 `llm/small-talk-gate.core.ts`. 기본 OFF 이며 `dialogueAct ∈ {GREETING, WELLBEING}` 또는 `actionType === TALK` 일 때만 켜진다(actionType 소스는 `ui.actionContext.parsedType`, legacy `actionType` 은 항상 null). 구 게이트는 "fact 4종이 모두 없음"을 잡담 신호로 삼았는데 이 프록시는 TALK 턴에서만 성립해, 조사·잠입·협박 턴에 잡담이 켜졌다(69% 주입·사교 발화 턴 0건 실측). **화제 풀 소진 시 즉흥 생성 금지** — 블록 자체를 넣지 않는다(구 폴백이 "몸 상태·날씨 체감·일감 걱정"을 예시해 그대로 출력됐다).
45. **엔진 코드 콘텐츠 ID 리터럴 금지** — 시나리오 팩(콘텐츠)의 NPC/장소/이벤트 ID·표시명·스크립트는 엔진 서비스 코드에 리터럴로 둘 수 없다. 콘텐츠 JSON 필드 + ContentLoader 파생 API로만 접근 (fallback은 content-loader 단일 지점 — `DEFAULT_SCENARIO_ID` export가 정본, 접두사 규약 `NPC_`/`LOC_`/`EVT_`·enum 리터럴은 예외). **의도적 예외 1건**: `engine/hub/procedural-seeds.ts`의 fallback 시드 풀 (LOC_* 한정 시드는 타 팩에서 자연 비활성, 무한정 시드는 세계관 중립 — 팩별 커스텀 수요 발생 시 외부화, 2026-07-20 검토 종결). 팩 계약: questState는 S0_ARRIVE~S5_RESOLVE 명명, incidents `resolutionConditions`·events `payload.tags` 필수 — architecture/63.
46. **경제 루프 — 퀘스트 사례금 + 정보 구매** — fact 발견/questState 전환 시 quest.json `rewards`(factGold/transitionGold) 사례금이 발생하되 **즉시 지급이 아니라 적립**된다(`RunState.pendingQuestReward`, 총량은 콘텐츠로 유한 → 파밍 불가). 실지급(정산)은 지급 주체가 납득되는 3시점뿐 — ① 의뢰인(`quest.json clientNpcId`, 미정의 시 `prologue.npcId` fallback) 대면 ② 거점 복귀 ③ 런 종료. **적립 이벤트(`QUEST_REWARD_ACCRUE`)는 LLM 프롬프트 `[이번 턴 사건]`에서 제외**한다 — 지급 주체가 장면에 없는데 금액을 주입하면 LLM이 현장 NPC에게 임의 귀속시켜 "추궁당한 상대가 사례금을 건네는" 서술이 나온다(실측 72턴 중 35%). 정산 이벤트(`QUEST_REWARD_SETTLE`)는 주체 명시형이라 전달 허용. `diff.goldDelta`·기억 goldDelta는 정산액 기준. NPC가 미공개 fact를 보류/거부한 턴은 `nanoEventCtx.bribeOpportunity`로 nano 선택지에 BRIBE 1개 노출. BRIBE 기본 비용은 `quest-balance.config.ts`(-6/-3) — fact 사례금(5G)보다 싸지 않게 유지 — architecture/65 + **89**.
47. **디렉터 비트 = 의도 정합 시에만 채택 (불변식 D)** — 자율 서사(AUTONOMOUS) 디렉터의 선계산 비트는 **플레이어 의도와 정합할 때만** 채택한다. 인력(gravity)은 유인이지 강제가 아니다 — 서사 강제 진행 금지. 구체: 강제창(`BEAT_FORCE_AFTER_TURNS`, turns.service `determineTurnModeCore` 규칙 1.5-C)은 **대화 잠금 활성 턴·사교 발화(GREETING/WELLBEING/THANKS/FAREWELL)·REST 의도 턴에는 발동하지 않는다**. **상호작용 단위 확장(버그 d20c1de8, 2026-07-17)**: 직전 턴과 동일 NPC 연속 상호작용(contextNpcId — 사교든 폭력이든) 중이면 그 NPC를 포함하지 않는 비트는 승격(1.5·3.6)·채택(requiredNpcId 하드 게이트) 모두 금지 — 채택 비트가 화자를 가로채 구타 대상이 스왑되던 실측 차단. "대화·휴식하려는데 사건 끼워넣기" 패턴이 조사 최다 이탈 요인("의도 무시 강제 진행")이므로 원천 차단. 정합률은 P8 계측(의도 정합 채택률)으로 감시 — architecture/76 D1.
48. **콘텐츠 캐시 객체 변조 금지 — 로더가 기계 강제 (2026-07-20 전환)** — 이벤트 캐시(`pack.eventsV2`)는 로드 시 **deepFreeze**되어 제자리 변조가 즉시 TypeError로 실패하고, `getEventById`는 **딥카피를 반환**한다 (content-loader). 배경: 과거 캐시 참조 반환 + 소비처 딥카피 관례 의존 구조에서 제자리 변조(primaryNpcId 동기화 등)가 캐시 원본에 영구 반영되어 이후 모든 런의 이벤트 정의를 오염시킨 실측(2026-07-17: coercer 런의 NPC 지목이 EVT_GUARD_INT_1 정의를 변조 → chatty 런에서 EventChoiceGate·Step 0b 동시 무력화, 브렌↔펠릭스 분열 4연속). 턴 파이프라인 수렴점의 `structuredClone(matchedEvent!)`은 심층 방어로 유지(EventMatcher 경로는 여전히 frozen 참조), EventChoiceGate 기준은 클론 직후 캡처한 `eventContentPrimaryNpc`. `getEventsByLocation`/`getAllEventsV2` 반환물은 읽기 전용 — 변조 필요 시 structuredClone. 어체 사후 교정도 화자 단위로만(R5v2 — 구 R5의 primary 일괄 치환은 타 화자 대사 파괴 실측).
49. **timePhase = phaseV2 파생 미러 (단일 시간 정본) + 시간은 이동·시간 소요 행동에서만 흐름** — 시간의 단일 정본은 phaseV2(globalClock 12tick=1일)이며, v1 `timePhase`(DAY/NIGHT)는 `deriveTimePhaseFromV2(phaseV2)`로만 파생한다. 과거 `advanceTime`가 timeCounter 5턴마다 timePhase를 독립 토글해 phaseV2와 충돌(전투 경로 timePhase=NIGHT vs phaseV2=DAY 실측)했던 이중 시간계를 폐지. timePhase를 독립적으로 변경하는 코드 추가 금지. 시간 진행 소유자는 WorldTickService 2경로뿐: `preStepTick`(행동 턴, timeCost는 `turns/time-cost.ts` 정본 — **대화 계열·사교 발화 0(시간 정지)**·시간 소요 행동 1·REST 2) + `advanceClockForTravel`(이동 턴 — 직행 2tick·HUB 경유 편도 1tick, Incident/packMeter 틱 없음). 대화 중 시간대 전환 금지 — architecture/81 (2차 재설계 2026-07-25).
50. **저모델 반복 억제 = 구체 어휘 주입 금지** — 메인 서술 LLM(저모델)은 프롬프트에 넣은 구체 어구·제스처 풀을 positive/negative 무관하게 복제/변형 반복한다(불변식 41/42 연장). 반복 억제는 정적 풀 노출이 아니라 ① 앵커 제거 ② 모델 레버(frequency_penalty 0.4/presence_penalty 0.3 — 메인 서술만, nano/추출 제외) ③ 추적 차원 축소(무한 문구→유한 상위 차원)로 한다. 하드 whitelist는 whack-a-mole — architecture/82, memory feedback_concrete_vocab_anchor. **적용 범위에 `daily_topics` 포함(arch/104)** — 완성 문장으로 저작된 화제는 그대로 낭독된다(마이렐 6건 축자 복사 실측). 프롬프트는 `화제 소재 (참고)` + "원문을 그대로 옮기지 말라"로 억제 중이며, 콘텐츠를 소재어로 축약하는 것이 근본 해결(4팩 368개, 미착수). **프롬프트 코드 자체에도 적용(arch/105)** — `예: "…"` 로 넣은 완성 문장은 그대로 복제된다(DB 4,145턴 실측: 관찰 예시 40턴·간접 흘림 예시 21턴·인계 예시 5턴). 예시 대신 **구성 요소**를 지시한다. 새 예시를 넣었다면 `llm_output` 에서 그 문구를 세어 보고, 세어 보지 않았다면 anchor 로 가정한다.

51. **미소개 실명 치환은 `maskHiddenNpcNames` 정본만** — 문자열 치환으로 개체를 다루면 다른 개체를 파괴한다. `replaceAll(name, alias)` 를 새로 쓰지 말고 `db/types/npc-state.ts` 의 정본을 호출한다 (Phase A 공개 실명 보호 → B 긴 패턴 우선 토큰화 → C 복원). 같은 부류 3회 재발: arch/80 이미지 URL 404('오슬라'→'행주 쥔 안주인') · 버그 86bff72b 별칭이 공개 실명 내부 융합 · arch/105 미소개 `브렌`이 공개 `토브렌 하위크`를 때려 프롬프트 15곳이 `토단정한 장교 하위크`로 파손(6턴 오호칭). Phase A 의 어절 토큰 보호는 **미공개 패턴이 그 토큰의 진부분문자열일 때만** — 무조건 보호하면 공용어(`대위`)가 잠겨 역회귀가 난다. 팩 추가 시 이름·별칭 substring 충돌을 전수 확인한다.

52. **경계 거절은 3부류** — 무대 이탈(이동, `move-boundary.core`) 외에 **META**(게임 종료·수치 조작·로그아웃 — 세계 안에서 실행 자체가 없음 → `OUT_OF_SCOPE` + 주사위 스킵 + `[세계 밖 요청 지시]`)와 **ANACHRONISM**(시대착오 물품 — 물건만 없음 → `IMPLAUSIBLE` + `[행동 재해석 지시]`)를 `turns/world-boundary.core.ts` 가 담당한다. L1 룰 목록은 안전망이고 일반해는 L2(nano plausibility 루브릭) — 목록 확장은 whack-a-mole 이므로 L2 를 먼저 손본다. 오탐 통제: 한국어 일반 단어에 부분 매칭될 토큰(`총`→총각, `전기`→전기수, `시계`→시계탑)은 등재 금지, 복합어만 — architecture/105.

53. **분위기(toneHint)는 장면 성질에서 도출** — 판정 결과의 파생값으로 두면 축이 죽는다. 구 구현(`SUCCESS → triumph`)은 30일 LOCATION 2,162턴에서 `triumph` 57%를 만들고 `tense`·`calm`·`mysterious` 를 **한 번도 쓰지 않았다**(6값 중 3개 사문, 잠입 8턴 내내 승리감 주입). 정본은 `turns/tone-hint.core.ts` — 세계 밖 시도 → 위험 → 긴장 행동 → 경계 상태 → 사교 → 사회적 성취 → 탐색 → 시간대 순. `triumph` 는 상대를 넘어선 성취(PERSUADE·BRIBE·HELP 성공)에만, 단서 발견은 `mysterious`. **부산물이 아니라 의도를 신호로 삼는다**(불변식 44 잡담 게이트와 같은 교훈) — architecture/105.

54. **플레이어 행동은 소문이 되지 않는다 (조용한 행동 한정)** — `SignalFeedService.generateFromActionResult` 는 플레이어 자신의 행동을 익명 제3자 목격담으로 세계 배경에 되먹인다. 조사·관찰·대화까지 전부 소문이 되면 `"누군가 무언가를 조사하고 있었다."`(=플레이어)가 매 턴 쌓이고, 만료가 clock 기반이라 대화 턴(불변식 49 시간 정지)에는 줄지도 않는다(11턴에 17건 중 8건 실측). 눈에 띄는 행동(FIGHT·THREATEN·STEAL) 또는 **실패**만 시그널화하고, 동일 문구는 중복 적재하지 않는다 — architecture/105.

55. **입력 콘텐츠 세이프티는 경계 거절의 4번째 부류** — 유해 입력(성적 노골·미성년/약자 폭력·자해) 방어의 정본은 `turns/content-safety.core.ts`이며, world-boundary(불변식 52)와 같은 L1 룰 + L2 nano(ChallengeClassifier `contentSafety` 축) + L3 서술 지시 3층이다. 감지 시 `ChallengeDecision.refused` → `resolve.forceRefusal`(주사위 스킵 + **모든 델타 0**)로 처리한다 — 유해 행동에 `FREE`를 주면 `forceAutoSuccess`(불변식 40)로 **자동 성공**이 되는 함정을 피하려 REFUSED 경로를 따로 둔다. **REDIRECT**(대부분)는 `[유해 행동 제지 지시]`로 세계가 제지하는 서술, **HARD_REFUSE**(MINOR_HARM 등 절대선)는 LLM 미호출 + 서버 고정 문안(`commitTurnRecord` narrativeOverride). 유해 거절 턴은 무과금(refund). MVP 4종 활성(HATE 정의만 비활성). 오탐 통제는 **조합 게이트 우선**(대상×행위 동시) — 일반 전투·선의·비속어 단독은 통과. 킬스위치 `CONTENT_SAFETY_ENABLED` — architecture/106.

## 과금 원칙 (채팅 과금 채택 — 2026-07-23 결정)

**결정 (2026-07-23)**: 초기 시장조사 잠정 결론 "정상 작동에는 과금하지 않는다"(arch/76 D5, 봉인)를 **폐기**하고, **채팅 1턴 = 5p 과금을 정식 모델로 픽스**한다. 비율(`POINTS_PER_CHAT`, 현 5p)은 운영 상황을 보며 조정한다. arch/85 포인트 시스템이 이 모델의 구현체이며, 아래가 구 3원칙을 대체한다.

1. **채팅은 기본 과금 단위** — 1턴 = `POINTS_PER_CHAT`(현 5p). 서버 정본 진행·판정·기억을 포함한 정상 플레이가 과금 대상이다. (구 "정상 작동은 무료" 원칙 폐기 — 초기 테스트 단계의 잠정안이었음.)
2. **실패 턴 무과금** — LLM 오류·빈 응답·재생성에 차감 금지. 차감은 디스패치 직전, 실패 시 환불(arch/85 D5 환불 2경로, `retry-llm` 무료). — 유지.
3. **부가가치는 별도 과금 가능** — 이미지·문체 프리셋·추가 캠페인/팩 등 선택적 확장. — 유지.

## Canonical Enums (정본)

서버 enum 의 기본 정본은 `server/src/db/types/enums.ts` 이지만, **도메인 타입 파일에 붙어 있는 것들이 있다**
(아래 표의 정본 위치가 실제 선언 파일이다 — `enums.ts` 만 뒤지면 못 찾는다). 경로는 모두 `server/src/db/types/` 기준.

| Enum | 정본 위치 | 값 |
|------|-----------|-----|
| Node Type | `enums.ts` | COMBAT, EVENT, REST, SHOP, EXIT, HUB, LOCATION |
| Node State | `enums.ts` | NODE_ACTIVE, NODE_ENDED |
| Run Status | `enums.ts` | RUN_ACTIVE, RUN_ENDED, RUN_ABORTED |
| Input Type | `enums.ts` | ACTION, CHOICE, SYSTEM |
| LLM Status | `enums.ts` | SKIPPED, PENDING, RUNNING, DONE, FAILED |
| Event Kind | `enums.ts` | BATTLE, DAMAGE, STATUS, LOOT, GOLD, QUEST, NPC, MOVE, SYSTEM, UI |
| Policy Result | `enums.ts` | ALLOW, TRANSFORM, PARTIAL, DENY |
| ActionType (Combat) | `enums.ts` | ATTACK_MELEE, ATTACK_RANGED, DEFEND, EVADE, MOVE, USE_ITEM, FLEE, INTERACT |
| ActionType (Non-Combat) | `enums.ts` | TALK, SEARCH, OBSERVE |
| CombatOutcome | `enums.ts` | ONGOING, VICTORY, DEFEAT, FLEE_SUCCESS |
| NodeOutcome | `enums.ts` | ONGOING, NODE_ENDED, RUN_ENDED |
| Distance | `enums.ts` | ENGAGED, CLOSE, MID, FAR, OUT |
| Angle | `enums.ts` | FRONT, SIDE, BACK |
| AI Personality | `enums.ts` | AGGRESSIVE, TACTICAL, COWARDLY, BERSERK, SNIPER |
| IntentActionType | `parsed-intent-v2.ts` | INVESTIGATE, PERSUADE, SNEAK, BRIBE, THREATEN, HELP, STEAL, FIGHT, OBSERVE, TRADE, TALK, SEARCH, MOVE_LOCATION, REST, SHOP |
| HubSafety | `world-state.ts` | SAFE, ALERT, DANGER |
| TimePhase | `world-state.ts` | DAY, NIGHT |
| TimePhaseV2 | `world-state.ts` | DAWN, DAY, DUSK, NIGHT |
| MatchPolicy | `event-def.ts` | SUPPORT, BLOCK, NEUTRAL |
| Affordance | `event-def.ts` | INVESTIGATE, PERSUADE, SNEAK, BRIBE, THREATEN, HELP, STEAL, FIGHT, OBSERVE, TRADE, ANY |
| EventTypeV2 | `event-def.ts` | RUMOR, FACTION, ARC_HINT, SHOP, CHECKPOINT, AMBUSH, ENCOUNTER, OPPORTUNITY, FALLBACK |
| ArcRoute | `arc-state.ts` | EXPOSE_CORRUPTION, PROFIT_FROM_CHAOS, ALLY_GUARD |
| NpcPosture | `npc-state.ts` | FRIENDLY, CAUTIOUS, HOSTILE, FEARFUL, CALCULATING |
| IncidentKind | `incident.ts` | CRIMINAL, POLITICAL, SOCIAL, ECONOMIC, MILITARY |
| IncidentOutcome | `incident.ts` | CONTAINED, ESCALATED, EXPIRED |
| SignalChannel | `signal-feed.ts` | RUMOR, SECURITY, NPC_BEHAVIOR, ECONOMY, VISUAL |
| NarrativeMarkType | `narrative-mark.ts` | BETRAYER, SAVIOR, KINGMAKER, SHADOW_HAND, MARTYR, PROFITEER, PEACEMAKER, WITNESS, ACCOMPLICE, AVENGER, COWARD, MERCIFUL |
| StepStatus | `operation-session.ts` | PENDING, IN_PROGRESS, COMPLETED, SKIPPED |
| Status ID | [[specs/status_effect_system_v1|status effect system v1]] §10 | BLEED, POISON, STUN, WEAKEN, FORTIFY |
| ResolveOutcome | `resolve-result.ts` | SUCCESS, PARTIAL, FAIL |
| Client Phase | `client/src/store/game-store.ts` | TITLE, LOADING, HUB, LOCATION, COMBAT, NODE_TRANSITION, RUN_ENDED, ERROR |
| StoryMessageType | `client/src/types/game.ts` | SYSTEM, NARRATOR, PLAYER, CHOICE, RESOLVE |
| CharacterPreset | `content/<pack>/presets.json` | DOCKWORKER, DESERTER, SMUGGLER, HERBALIST, FALLEN_NOBLE, GLADIATOR |
| CharacterTrait | `content/<pack>/traits.json` | BATTLE_MEMORY, STREET_SENSE, SILVER_TONGUE, GAMBLER_LUCK, BLOOD_OATH, NIGHT_CHILD |
| NpcTier | `content.types.ts` | CORE, SUB, BACKGROUND |
| FactCategory | `world-fact.ts` | PLAYER_ACTION, NPC_ACTION, WORLD_CHANGE, DISCOVERY, RELATIONSHIP |
| SituationTrigger | `situation-generator.service.ts` | LANDMARK, INCIDENT_DRIVEN, NPC_ACTIVITY, NPC_CONFLICT, ENVIRONMENTAL, CONSEQUENCE, DISCOVERY, OPPORTUNITY, ROUTINE |

## API Endpoints

실제 라우트 84개 전수 (2026-08-14 컨트롤러 21개 기준, SSE 2 포함). **admin** 표시는 `@AdminEndpoint`
(x-admin-token OR JWT+users.role, 감사 로그 `admin_audit_logs` — arch/87). 그 외는 JWT 인증,
`/v1/stats/public` 만 무인증.

### 인증·런·턴

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/auth/register` | 회원가입 (email, password, nickname) — 회원번호 자동 부여 + 가입 보너스 포인트 |
| POST | `/v1/auth/login` | 로그인 → JWT |
| GET | `/v1/auth/me` | 현재 로그인 유저 (회원번호 `memberNo` 포함) |
| POST | `/v1/runs` | 새 RUN 생성 (presetId, gender, scenarioId) |
| GET | `/v1/runs` | 활성 RUN 조회 (userId 기반) |
| GET | `/v1/runs/:runId` | RUN 상태 조회 (turnsLimit 옵션) |
| POST | `/v1/runs/:runId/abort` | RUN 중단 (RUN_ABORTED) |
| POST | `/v1/runs/:runId/equip` | 장비 착용 |
| POST | `/v1/runs/:runId/unequip` | 장비 해제 |
| POST | `/v1/runs/:runId/use-item` | 소모품 사용 |
| POST | `/v1/runs/:runId/turns` | 턴 제출 (ACTION/CHOICE, idempotencyKey 필수) |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 (LLM 폴링용, includeDebug 옵션) |
| GET | `/v1/runs/:runId/turns/:turnNo/stream` | **SSE** 서술 스트리밍 (arch/35) |
| POST | `/v1/runs/:runId/turns/:turnNo/retry-llm` | LLM 재시도 (FAILED → PENDING, 무료) |
| GET | `/v1/runs/:runId/turns/llm-usage` | 런 LLM 사용량·비용 집계 |

### 시나리오·캠페인·엔딩

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/scenarios` | 시나리오(팩) 목록 |
| GET | `/v1/scenarios/:scenarioId/creation-bundle` | 팩 프리셋·특성 서빙 (arch/71) |
| POST | `/v1/campaigns` | 캠페인 생성 |
| GET | `/v1/campaigns` | 활성 캠페인 조회 |
| GET | `/v1/campaigns/:id` | 캠페인 상세 |
| GET | `/v1/campaigns/:id/scenarios` | 캠페인 시나리오 진행 상태 (AVAILABLE/IN_PROGRESS/COMPLETED) |
| GET | `/v1/endings` | 여정 아카이브 목록 |
| GET | `/v1/endings/:runId` | 여정 요약 상세 |

### 포인트·초상화·버그 리포트

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/points/balance` | 포인트 잔액 |
| GET | `/v1/points/transactions` | 포인트 원장 조회 |
| POST | `/v1/points/redeem` | 충전 코드 사용 |
| POST | `/v1/admin/codes` | **admin** 충전 코드 발급 |
| GET | `/v1/admin/codes` | **admin** 코드 목록 |
| POST | `/v1/portrait/generate` | AI 초상화 생성 |
| POST | `/v1/portrait/upload` | 초상화 업로드 (multipart) |
| POST | `/v1/runs/:runId/bug-report` | 버그 리포트 생성 (인게임) |
| GET | `/v1/bug-reports` | **admin** 버그 리포트 목록 (페이징) |
| GET | `/v1/bug-reports/:id` | **admin** 상세 |
| PATCH | `/v1/bug-reports/:id` | **admin** 상태 변경 |

### 설정·장면 이미지·시스템

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/settings/llm` | LLM 설정 조회 (API 키 마스킹) |
| PATCH | `/v1/settings/llm` | **admin** LLM 설정 변경 (런타임) |
| POST | `/v1/runs/:runId/turns/:turnNo/scene-image` | 장면 이미지 생성 (현재 봉인) |
| GET | `/v1/scene-images/status` | 이미지 생성 가용 상태 |
| GET | `/v1/runs/:runId/scene-images` | 런 장면 이미지 목록 |
| GET | `/v1/version` | 서버 버전 (git hash, startedAt, uptime) |
| GET | `/v1/stats/public` | **무인증** 공개 통계 (랜딩 LiveStats, 10분 캐시·테스터 제외) |
| GET | `/` | 헬스 체크 |

### 파티

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/parties` | 파티 생성 (name) |
| GET | `/v1/parties/my` | 내 파티 조회 |
| GET | `/v1/parties/search` | 파티 검색 (?q=) |
| POST | `/v1/parties/join` | 초대코드로 가입 (inviteCode) |
| POST | `/v1/parties/:partyId/leave` | 파티 탈퇴 |
| POST | `/v1/parties/:partyId/kick` | 멤버 추방 (userId) |
| DELETE | `/v1/parties/:partyId` | 파티 해산 |
| POST | `/v1/parties/:partyId/messages` | 채팅 전송 (content) |
| GET | `/v1/parties/:partyId/messages` | 채팅 히스토리 (cursor, limit) |
| GET | `/v1/parties/:partyId/stream` | **SSE** 실시간 스트림 (?token=JWT) |
| GET | `/v1/parties/:partyId/lobby` | 로비 상태 조회 |
| POST | `/v1/parties/:partyId/lobby/loadout` | 로비 배경(프리셋) 선택 — 솔로 이력 없는 신규 유저 시작 지원 (2026-08-07) |
| POST | `/v1/parties/:partyId/lobby/ready` | 준비 완료 토글 (ready) |
| POST | `/v1/parties/:partyId/lobby/start` | 던전 시작 (리더 전용) |
| POST | `/v1/parties/:partyId/lobby/invite-run` | 내 세계에 초대 — 리더 솔로 런에 합류 |
| POST | `/v1/parties/:partyId/runs/:runId/turns` | 파티 행동 제출 |
| GET | `/v1/parties/:partyId/runs/:runId/state` | 파티 런 상태 (멤버 진입 복원용, arch/84) |
| GET | `/v1/parties/:partyId/runs/:runId/turns/:turnNo` | 파티 턴 상세 (partyActions + serverResult + llm) |
| POST | `/v1/parties/:partyId/runs/:runId/leave` | 던전 이탈 (보상 정산 + AI 전환) |
| POST | `/v1/parties/:partyId/votes` | 이동 투표 제안 (targetLocationId) |
| POST | `/v1/parties/:partyId/votes/:voteId/cast` | 투표 참여 (choice: yes/no) |

### 어드민 (arch/87 — 전부 `@AdminEndpoint`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/admin/stats/overview` | KPI 대시보드 (가입·활성·런·턴·포인트, 테스터 제외) |
| GET | `/v1/admin/stats/llm-cost` | LLM 비용 시계열 |
| GET | `/v1/admin/stats/points` | 포인트 발행·소비 시계열 |
| GET | `/v1/admin/stats/cost-reconciliation` | OpenRouter 실과금 대조 (management 키 필요) |
| GET | `/v1/admin/users` | 유저 검색·목록 |
| GET | `/v1/admin/users/:id` | 유저 상세 |
| POST | `/v1/admin/users/:id/points-adjust` | 포인트 조정 |
| POST | `/v1/admin/users/:id/password` | 비밀번호 재설정 |
| DELETE | `/v1/admin/users/:id` | 유저 삭제 |
| GET | `/v1/admin/runs` | 런 목록 |
| GET | `/v1/admin/runs/scenarios` | 시나리오 필터 옵션 목록 |
| GET | `/v1/admin/runs/stuck` | 스턱 런 조회 |
| POST | `/v1/admin/runs/:id/abort` | 런 강제 종료 |
| POST | `/v1/admin/runs/:id/turns/:turnNo/retry-llm` | 턴 LLM 재시도 |
| GET | `/v1/admin/llm/failures` | LLM 실패 로그 |
| GET | `/v1/admin/llm/flags` | 런타임 킬스위치 플래그 조회 (비영속) |
| PATCH | `/v1/admin/llm/flags` | 런타임 킬스위치 플래그 변경 (비영속) |
| GET | `/v1/admin/parties` | 파티 목록 |
| GET | `/v1/admin/parties/:id` | 파티 상세 |
| GET | `/v1/admin/audit-logs` | 어드민 감사 로그 조회 (admin_audit_logs) |
| GET | `/v1/admin/health` | 시스템 헬스 |

## Environment Variables (`server/.env`)

```
DATABASE_URL=postgresql://user:password@localhost:5432/textRpg
LLM_PROVIDER=openai          # openai | claude | gemini | mock
OPENAI_API_KEY=sk-...
OPENAI_MODEL=google/gemma-4-31b-it   # OpenRouter 메인 모델 (Gemma 4 31B dense — 2026-07-22 승격, allowlist 전제. 이전 26B MoE)
LLM_ALTERNATE_MODEL=openai/gpt-5.6-luna  # 교차 모델 — 5:5(턴%10∈{0,2,4,6,8}=짝수). 2026-08-13 DeepSeek→Luna 교체 + 3:7→5:5 복원: 3:7 축소 사유(DeepSeek 어미 열세)가 모델 교체로 소멸. 30일 실측 — 어체 위반 Luna 6.4% / Gemma 14.6% / DeepSeek 43~46%, 마커 커버리지 Luna 100% / Gemma 99.6% / DeepSeek 74.8~77.5%. DeepSeek 무마커 대사는 초상화·화자 표시가 모두 실패(실측 런에서 최대 정보 공개 턴에 4연속 발생). 추론은 LLM_REASONING_EFFORT_MAP 으로 none 고정 필수 — 미지정 시 default_effort=medium 으로 켜져 출력 단가 과금. 계약은 model-alternation.spec.ts 가 고정
OPENAI_BASE_URL=https://openrouter.ai/api/v1  # optional, OpenAI-compatible endpoint
CLAUDE_API_KEY=               # optional
GEMINI_API_KEY=               # optional
LLM_MAX_RETRIES=2
LLM_TIMEOUT_MS=8000
LLM_MAX_TOKENS=2048                   # 비전투 서술만 (nano 자체값·COMBAT 512 캡). 30일 상한 도달 0건 — 절단 보험용
LLM_TEMPERATURE=0.8
LLM_LIGHT_MODEL=gpt-4.1-nano          # nano/경량 계열 (arch/67 — 명시 고정)
LLM_LIGHT_TIMEOUT_MS=5000             # nano 요청 단위 타임아웃 (전역 60s 대체)
LLM_DIALOGUE_MODEL=google/gemma-4-26b-a4b-it  # 대사 생성(Stage B+자기소개) — 하오체 준수용 Flash급+
LLM_FIRST_TOKEN_TIMEOUT_MS=5000       # 스트리밍 첫 토큰 타임아웃 — 초과 시 non-stream fallback (arch/62, 0=off)
LLM_STREAM_STALL_TIMEOUT_MS=20000     # 스트림 정체 타임아웃 — 첫 토큰 후 무델타 지속 시 절단→non-stream fallback (0=off, narrative max 270s 실측 대응 2026-07-31)
LLM_PROVIDER_SORT=throughput          # OpenRouter 라우팅 정렬 — 생성 tok/s 우선 (arch/62)
LLM_PROVIDER_IGNORE=cloudflare,dekallm  # OpenRouter 배제 provider (저 uptime — arch/62 부록)
LLM_PROVIDER_ONLY_MAP=google/gemma-4-31b-it=Friendli|Venice|Novita|CoreWeave  # 모델별 프로바이더 allowlist — 31B 풀 불안정(빈 서술) 대응 (arch/25 D-8). 2026-08-13 ModelRun 제거: fp4(최저 정밀도)인데 8.89원/턴으로 전 19곳 중 2위 고가였고, throughput 정렬이 이걸 고르면서 실과금이 1.9→6.9원으로 튐. 대체 4곳은 전부 단일 엔드포인트(가격 고정)·3곳 bf16. 교체 후 실측 1.42원/턴(-80%)·서술 6.1s(ModelRun 1.6s)
LLM_NO_PENALTY_MODELS=                # penalty 미지원 모델 강제 지정 (기본은 코드 판정 — model-capabilities.ts)
LLM_NO_TEMPERATURE_MODELS=            # temperature 미지원 모델 강제 지정
LLM_REASONING_EFFORT_MAP=openai/gpt-5.6-luna=none  # GPT-5 계열 추론 강도. Luna는 default_effort=medium 이라 미지정 시 추론이 켜진 채 출력 단가로 과금
LLM_FALLBACK_PROVIDER=openai          # fallback: 같은 OpenRouter 경유
LLM_FALLBACK_MODEL=openai/gpt-4.1-mini  # fallback 모델 (이전: Claude Haiku 4.5)
GEMINI_REASONING_MAX_TOKENS=0         # Gemini Flash thinking 비활성화 (0=off, DeepSeek는 코드에서 enabled:false 자동 주입)
LLM_JSON_MODE=false               # JSON 구조화 출력 (스트리밍과 비호환, false 권장). false 는 2-Stage 대사 분리를 무력화한다는 부작용이 있다 — arch/104 §P2-4
LLM_SHORT_RESPONSE_MIN_TOKENS=150     # ShortResponse 재시도 임계 (기본 200 — 교차 모델 짧은 서술 이중 과금 방지)
LLM_PROVIDER_REQUIRE_PARAMS=true      # penalty 미지원 프로바이더 배제 (불변식 50 레버 보장, 2026-07-22 채택)

# ── 인프라·보안 ──
PORT=3000                             # 기본 3000 (launchd 상주 서비스가 사용)
JWT_SECRET=<secret>                   # 토큰 서명 키 — 프로덕션에서 반드시 교체
CORS_ORIGINS=https://dimtale.com,...  # 콤마 구분 허용 오리진 (클라·어드민·로컬)
ADMIN_TOKEN=<secret>                  # 어드민 헤더 인증 x-admin-token (arch/87, JWT+users.role 과 OR)

# ── 포인트 (arch/85) ──
POINTS_ENABLED=true                   # false 면 과금 전면 비활성 (기본 true)
POINTS_PER_CHAT=5                     # 채팅 1턴 차감 포인트
SIGNUP_BONUS_POINTS=50                # 가입 보너스

# ── LLM 보조 경로 ──
CLAUDE_MODEL=claude-haiku-4-5-20251001  # claude provider 사용 시 모델
GEMINI_MODEL=gemma-4-26b-a4b-it         # gemini provider 사용 시 모델
LLM_LIGHT_PROVIDER=openai               # nano 계열 provider (기본 openai)
LLM_MAIN_ALTERNATE_MODEL=              # 메인 교차 모델 오버라이드 (미설정 시 LLM_ALTERNATE_MODEL)
LLM_DIALOGUE_SPLIT=true                 # 2-Stage 대사 분리 (arch/32) — ⚠️ **LLM_JSON_MODE=true 가 전제**. 현재 JSON 모드가 false 라 이 설정과 LLM_DIALOGUE_MODEL 은 사문이며, 대사는 메인 서술 LLM 이 직접 생성해 어체 검증(validateSpeechRegister+재시도)을 타지 않는다. JSON 모드는 스트리밍과 비호환(arch/35)이라 되돌릴 수 없어, 어체 정합은 사후 교정(R5v2)이 담당 — arch/104 §P2-4. 부팅 시 무효 조합 경고 있음
LLM_STREAM_CLASSIFIER=true              # 스트림 분류기 (기본 true, 'false' 로 차단)
LLM_PROVIDER_ORDER=                     # OpenRouter provider 우선순위 (콤마)
LLM_PROVIDER_MAX_PRICE=                 # provider 단가 상한
INTENT_LLM_ENABLED=                     # LLM 인텐트 파서 on/off
INTENT_LLM_PROVIDER=openai              # 인텐트 파서 provider
INTENT_LLM_MODEL=gpt-4.1-nano           # 인텐트 파서 모델

# ── 킬스위치 (기본 전부 켜짐 — 문제 시 개별 차단) ──
PLOT_DIRECTOR_DISABLED=                 # '1' 이면 자율 서사 디렉터 정지 (arch/75)
COMBAT_TACTIC_DISABLED=false            # 'true' 면 전투 기만 평가 정지 (arch/76)
CHALLENGE_CLASSIFIER_ENABLED=true       # 'false' 면 자유 행동 주사위 스킵 판정 정지
NPC_REACTION_DIRECTOR_ENABLED=true      # 'false' 면 NPC 반응 사전결정 정지 (arch/56)
PROPS_TRACE_DISABLED=                   # '1' 이면 흔적(propsState) 추출 정지
INLINE_IMAGE_MATCH_DISABLED=            # '1' 이면 장면 컷 매칭 정지 (arch/96)
SCENE_CUT_MIN_CONFIDENCE=0.65           # 장면 컷 nano 판정 채택 임계

# ── 개발·검증 전용 ──
PROMPT_FIXTURE_CAPTURE=                 # 설정 시 프롬프트 픽스처 덤프
PLAYTEST_NPC_REACTION=                  # 플레이테스트 NPC 반응 계측 토글
OPENROUTER_MANAGEMENT_KEY=              # 어드민 실과금 대조 — Activity API. 일반 추론 키는 403 (arch/87 §9)
```

## Implementation Phase Status (구현 단계)

> **전체 이력(163 항목)의 원문은 [[architecture/phase_history|phase history]]**.
> 아래는 최근 74개 항목의 압축본이며, 근거·실측 수치·기각안은 `arch/NN` 문서가 정본이다.
> CLAUDE.md 는 매 세션 전량 로드되므로 여기서는 "무엇을 이미 했는가" 판단에 필요한 만큼만 남긴다.

### 기반 구축 (최초 ~ 2026-06, 89 항목 — 상세는 phase_history)

| 묶음 | 범위 | 상태 |
|------|------|------|
| **코어 루프** | Phase 1~4 (HUB 순환·LOCATION 판정·전투·LLM 서술·프리셋/인증 → NPC 소개+5축 감정 → DAG 24노드 라우팅 → Turn Orchestration → 장비 v2/리전 경제) | ✅ 완료 |
| **서사 엔진** | Narrative v1(Incident·4상 시간·Signal·Mark·Ending·Operation) → Memory v2/v3/v4 → Narrative v2(Token Budget·Mid Summary) → Event v2(EventDirector·라이브러리 123) → Bridge(IntentV3·Router·PlayerThread) → Living World v2(7 서비스) | ✅ 완료 |
| **대사·마커** | @마커 v2 하이브리드 → nano 전환 → 오류율 개선 3전략 → 대사 분리 2-Stage → 로어북 → 다중 어체 5종 → 별칭 반복 해소 → 마커 안정화·오귀속 방지 | ✅ 완료 |
| **서술 파이프라인** | v2(3-Stage) → v3(반복·메타 서술) → v4(THREAD 하이브리드·모델 교차) + LLM 스트리밍(SSE 2-Phase) + NanoEventDirector(+비동기 분리) + Player-First 이벤트 엔진 | ✅ 완료 |
| **퀘스트·경제** | 퀘스트 6단계 전환 + fact 점진 공개 + 밸런싱(SitGen 바이패스·PARTIAL 50%·config 외부화) + Quest→Ending 자동 전환 | ✅ 완료 |
| **파티** | Phase 1(CRUD·초대·SSE 채팅) → Phase 2(동시 턴·통합 판정·투표·보상)+보강 → Phase 3(런 통합·중간 합류/이탈) | ✅ 완료 |
| **클라이언트·UX** | 캐릭터 생성 6단계 + 초상화(생성·크롭·확장) + 모바일 UX + 클라 UX 개선 7종 + 호외/태도 알림 + 이미지 WebP(-98%) + 라우트 재구성 | ✅ 완료 |
| **품질·운영** | 품질 검증 V7~V9 + E2E + 단위 테스트 강화 + 린트 0/0 + 동시접속 최적화(10/10) + 버그 리포트 수집 확장 + LLM 모델 전환 이력(Gemma4↔Flash↔Qwen3↔26B 복귀) | ✅ 완료 |

### 최근 작업 (2026-06 ~ 2026-07)

| 작업 | 요약 | 상태 |
|------|------|------|
| **엔딩 연출 개선** | [arch/39] 엔딩 직전·직후 연출 강화 — MIN_TURNS 가드, arcRoute 12분기 에필로그, personalClosing, SoftDeadline 배너(D-3~초과)와 LLM deadlineContext 주입 | ✅ 완료 |
| **여정 아카이브 Phase 1** | [arch/39] 런 종료 시 SummaryBuilder 가 ending_summary(jsonb) 를 만들고, GET /v1/endings + 양피지 스타일 여정 기록 화면으로 노출 | ✅ 완료 |
| **아이템 정합성 (A+B)** | [arch/40] LLM 이 없는 아이템을 주던 문제를 프롬프트 금지 규칙 + [이번 턴 획득 아이템] 블록 + EventItemReward 실지급 경로로 봉합. KEY_ITEM 3종 매핑 | ✅ 완료 |
| **소지품 UX 개선** | [arch/40] 장비 교체 확인 모달(비교 카드), usableInHub 기반 사용 판정 동적화, 전투 중 사용 차단, 드랍 토스트, 에러 문구 한국어화 10종 | ✅ 완료 |
| **NPA v2 메트릭** | NpcDistinctness(distinct pool 매칭률) + ToneMatch(baseline-aware mismatch) 신설, 5축 점수(연결성·자유도·사람다움·차별화·톤일치) | ✅ 완료 |
| **NPC Distinctness v1** | [arch/51] R1 회피 어휘 강제 치환(2회+ 등장 시) + CORE 6명 mannerism 확장 — 차별화 4.83/5, ERR 0 | ✅ 완료 |
| **A51 R2~R6 + A52 시스템 프롬프트 압축** | 사용자 키워드 인용·권장 호칭 자동 추출·어미 후처리·단일 NPC 응답 강제 + P0/P1/P2 우선순위 박스. 시스템 프롬프트 11,400→9,000자(-21%) | ✅ 완료 |
| **NPA 메트릭 v2 (다중 NPC 정확화)** | [arch/55] 톤·호칭 일치를 utterance 단위로 자기 NPC register 기준 평가해 다중 NPC 턴 오측정 해소 + 시스템 프롬프트 자기모순(실제 별칭을 금지 예시로 노출) 정정 | ✅ 완료 |
| **A56 NPC Reaction Director + 어휘 폭주 해소** | [arch/56] nano 가 톤 3축을 사전 결정하고 speechStyle 어구 예시를 추상화 — 시그니처 어구 39.7→6.2%(-84%), 마이렐 패턴 완전 소멸 | ✅ 완료 |
| **Fact 일급 객체 도입** | facts.json 신규 + ContentLoader API — Fact 를 NPC·Incident 와 동일 레벨의 콘텐츠 원자로 승격, 매칭/조회 일관화 | ✅ 완료 |
| **잠금 NPC + Fact awareness 통합** | [arch/46] 대화 잠금 중 NPC 의 fact 인식 상태를 LLM 컨텍스트에 통합 전달 | ✅ 완료 |
| **NPC 점프 완전 차단** | event.payload.primaryNpcId 동기화 누락 수정 + NPC 후보 names에서 일반 단어 제거(스트림 점프 차단) + 대화 잠금 중 MOVE_LOCATION 차단(회귀 방지) | ✅ 완료 |
| **NPC 결정 권한 단일 통합** | [arch/49] 텍스트매칭·IntentV3·대화잠금·nano·이벤트배정 5단계를 NpcResolverService 한 곳으로 통합해 화자 결정 권한을 단일화 | ✅ 완료 |
| **직전 NPC 대사 슬롯 + 회피 패턴 정상화** | 사용자 응답 복사 / 위치 회피 해소 — 직전 NPC 대사가 슬롯 누락 시 LLM 이 사용자 입력을 복사하는 버그 + 동일 NPC 의 위치 회피 부자연스러움 동시 해소 | ✅ 완료 |
| **메인 LLM Gemma 4 26B 복귀** | [arch/25] Gemini Flash → Gemma 4 26B MoE 메인 복귀(fallback GPT-4.1 Mini 유지). 한국어 서술 일관성·톤·게이트웨이 안정성 종합 판단 | ✅ 완료 |
| **nano 선택지 DB/stream desync 봉합** | 워커 첫 UPDATE 에서 llmChoices 를 떼고 Track 2 완료 후 finalChoices 단일 변수로 DB·스트림 동시 사용. 9턴 연속 라벨 byte-equal 검증 | ✅ 완료 |
| **Fact 공개 단일화** | [arch/58] 기록 단서와 서술 단서가 어긋나던 데스싱크를 주제 우선 선택(selectRevealableFact) + ui.questReveal 동일 주입으로 봉합 | ✅ 완료 |
| **단서 대화 후속 안정화** | [arch/59] 판정 NPC=서술 NPC 정합(NpcResolver 부분 이름 매칭) + [단서 방향] nextHint ui 전달 복구 + HINT_MODES off-by-one | ✅ 완료 |
| **단서 흐름 튜닝 + 워커 정합성** | [arch/60] LLM 워커 runState lost update 해소(fresh 부분 패치) + 주제 불일치 fallback 금지(인계 양보) + [단서 방향] 공개 턴 이월 + 비주제 공개 확률 게이트 | ✅ 완료 |
| **NPC 대화 자연화 3종** | 사교 발화 감지로 잡담 턴 단서 덤핑 차단 + 직전 발화 이어받기 + 질문 우선 응답. 응답률 에드릭 56→70% | ✅ 완료 |
| **NPA 어미 메트릭 수정** | [arch/55] 하오체 최빈 종결 '-소' 누락과 말끝 흐림 집계 버그로 45~59%로 오측정되던 준수율이 88~100%로 정상화(로넨 45→100%) | ✅ 완료 |
| **NPC 이름 공개 무결성** | [arch/64] 롤백-재소개 상쇄·소개 힌트 실명 오염·2턴 분리를 3층 방어로 잡고, R7 스트림 새니타이즈로 emit 전 미공개 실명 차단. 회귀 26건 | ✅ 완료 |
| **멀티 시나리오 ① 멀티 팩 로더** | [arch/63] ContentPackState 캐시 + AsyncLocalStorage 스코프로 단일 활성 시나리오 정책을 폐지 — 서로 다른 팩 런의 동시 플레이를 격리 | ✅ 완료 |
| **멀티 시나리오 ⑥ 클라 선택 UI** | [arch/63] GET /v1/scenarios + 여정 선택 화면(2팩 이상일 때) + HUB 라벨·프리셋·장소 이미지의 시나리오 인지. E2E 완주 검증 | ✅ 완료 |
| **경제 루프 v1** | [arch/65] 단서·진전 사례금(팩별 quest.json)과 정보 보류 턴 BRIBE 노출 신설. 근거는 30일 441턴에 골드 이벤트가 4건뿐이라는 실측 | ✅ 완료 |
| **엔딩 완주 평가 P1~P4** | [arch/65] 이동 상용구로 26턴 갇히던 결함, 작별 후 잠금 해제, 접두 융합 별칭, 퀘스트 전환 장비 보상 — 완주를 막던 4건 해소 | ✅ 완료 |
| **마커·대사 정합 마감** | [arch/65] 콜론 라벨 3-Tier 유일성 매칭으로 무명 오귀속 6→1, 카드 서술 언급 검사·진입 턴 이월 차단 추가. 9/9 PASS 최초 달성 | ✅ 완료 |
| **엔딩 턴 피날레 + 자기소개 사전 확정** | [arch/66] 엔딩 턴 [마지막 장면] 디렉티브 + nano 사전 생성→positive 주입→서버 삽입 3단 사다리로 자기소개 성사 0%→보장 | ✅ 완료 |
| **Nano 엔진 감사** | [arch/67] 죽어 있던 요청 단위 timeout 부활, 워커 이중 처리 락(7/650 실측), NpcReaction JSON 재시도(실패 10.4% 구제), nano 모델 env 고정 | ✅ 완료 |
| **카드 정합 근본 수정 + 테스트 시스템 감사** | [arch/67] V8 3중 원인(턴 매핑 밀림·완전형 마커 미수집·부분 문자열 오매칭) 해소로 카드 교체 부활 + 복제 drift 를 export 정본 참조로 전환 | ✅ 완료 |
| **자유 대화 정합 4종** | [arch/67] 언급 질문 가드 확장·화자 표시 단일화·작별 턴 소개 이월·재탕 센서로 자유 입력의 '대화 상대 핑퐁' 해소 | ✅ 완료 |
| **멀티 시나리오 디커플링 ②~⑤** | [arch/63] 엔진에 박혀 있던 콘텐츠 ID 를 전부 외부화(표시명·별칭·프롤로그·L0 테마·HUB 선택지)하고 DAG 를 graph.json 으로. silverdeen_v1 미니 팩 신설 | ✅ 완료 |
| **UI/UX 실사 리뷰 v1** | [arch/68] 헤드리스로 신규 유저 경로를 순회해 6건 수정 — 도감 조우 필터·이어하기 복원·모바일 상태줄/인물 탭·호외 타이밍·조사 처리·dev 게이트 | ✅ 완료 |
| **UI/UX 폴리싱 C-2~C-7** | [arch/68] 선택지 rest 어포던스, 시나리오 배너, 스탯 뮤트 앤틱 팔레트(토큰 3곳 정본 수렴), 라벨 정리, 골드 체크박스 | ✅ 완료 |
| **C-1 거점 사랑방 개방 (A안)** | [arch/68] HUB 자유 입력(서버 계약 CHOICE 전용)은 유지하고 거점 사랑방 장소를 hubAccessible 로 열어 기존 LOCATION 파이프라인을 그대로 재사용. 서버 0줄 | ✅ 완료 |
| **자유 입력 발견성** | [arch/68] 첫 LOCATION 1회 코치마크 + placeholder 행동 예시 로테이션 + 튜토리얼 한 줄로 "선택지 클릭 게임" 오해 차단 | ✅ 완료 |
| **NanoChoiceNpcFix** | [arch/68] nano 선택지의 sourceNpcId 오염을 finalChoices 확정 직전 단일 지점에서 교정(지목형·작별 턴 예외). 유닛 7케이스 | ✅ 완료 |
| **상점 노출 동선** | [arch/68] 도달 불능이던 구매 경로를 TRADE+구매 표현으로 확장하고 ui.shops 를 클라가 소비(칩·진열·구매 버튼). 전 DB 최초 [상점] 이벤트 기록 | ✅ 완료 |
| **NPC 선제 단서 억제 (부록 M)** | [arch/68] 이방인 잡담에 NPC 가 먼저 단서를 흘리지 않도록 대화 계열은 주제 매칭 시에만 fact 공개, 차단분은 뇌물 기회로 이월 | ✅ 완료 |
| **이벤트-서술 NPC 분열 (부록 L)** | [arch/68] 조우 이벤트에 primaryNpcId 를 명시하고, 유저 지목이 이벤트 NPC 와 다르면 이벤트 선택지를 폐기하는 게이트 추가. playtest V10 센서 신설 | ✅ 완료 |
| **판정·서술 불일치 + 초상화 오귀속 (부록 K)** | [arch/68] bribeOpportunity 가 nano 컨셉을 오염시키던 것을 NanoConceptGuard 로 억제(선택지는 유지), 마커 등장 후 무마커 대사는 무명화 | ✅ 완료 |
| **후처리 순서 의존성 정비 (부록 J)** | [arch/68] 재삽입이 정리 뒤에 오던 순서 사각지대를 멱등 배리어 sanitizeAliasArtifacts 로 묶어 1차·최종 동일 호출. 동작 보존 1047 passed | ✅ 완료 |
| **긴 별칭 일괄 정비 (부록 I)** | [arch/68] 12~14자 unknownAlias 를 5~10자로 압축(첫인상 형용사 유지) + BACKGROUND shortAlias 25명 신설. 코드 0줄, 긴 별칭 완전 소멸 | ✅ 완료 |
| **오웬 별칭 반복 수정 (부록 H)** | [arch/68] 저장 직전 최종 별칭 정리로 IntroFallback 재삽입까지 커버 + 우호 NPC 강제소개 임계 차등. 오웬 T4 자기소개 실측 | ✅ 완료 |
| **선술집 BG 초상화 6종** | [arch/68] 사용자 제작 초상화 6장 매핑 + 비올라 여성 개명·헬가 gender 정정. 사랑방 개방 후속 | ✅ 완료 |
| **아크 커밋 동선 + 3사이클 프로세스** | [arch/68] S5 완주 3연속 실증 후 아크 루트를 HUB 명시 분기(routeCommitChoices)로 노출 — "정의의 대가" 12분기 최초 진입 | ✅ 완료 |
| **캠페인 자유 시나리오 선택** | [arch/71] 원점 정책을 폐기하고 첫 시나리오 자유 선택 + creation-bundle API 로 팩 프리셋 서빙 + 장비·소모품·서사 이월 배선 | ✅ 완료 |
| **NPC 반응 권한 통합** | [arch/72] 목격자 반응과 NpcReactionDirector 의 이중 권한 해소 — 대화 상대는 목격자 루프에서 제외하고 당턴 1회 발화로 제한 | ✅ 완료 |
| **자율 서사 팩 배포 (karnholt_v1, 2026-07-16)** | [arch/75] "진상 선확정 디렉터 모드" AUTONOMOUS 팩(karnholt_v1) 배포 — Plot Seed 선확정 + 비트 선계산·의도 정합 채택 + 동적 NPC + 규명율 엔딩 | ✅ 구현·배포 (P7 후속) |
| **시장 조사 대응 (자유도·판정 투명성)** | [arch/76] 강제 진행 차단(불변식 47)·판정 투명성 UI·actionType 탈버킷·흔적 추출·되짚기 구현 + 서사 방향 계측 4종 | ✅ 완료 |
| **감정·행동화 탈버킷 (D3-b′/c′/combat)** | [arch/76] 원안 폐기 후 재설계 — nano socialImpact 5축 블렌드 + 감정→세계 행동화(도주/회피/신고/접근) + 전투 기만 성향 차등 | ✅ 완료 |
| **어체 정합 근원 수정 (2026-07-17)** | [arch/82] 3층 동시 해소 — 시스템 프롬프트 하오체 강제 정정, 구 R5 일괄 치환 폐기 후 화자 인지 R5v2, 혼용 감지 확장. 합쇼체 끌림 11→1건 | ✅ 완료 |
| **감정→행동화 실증 완결 + 밸런스 (2026-07-17~18)** | [arch/76] agitation 4종(FLEE·AVOID·REPORT·APPROACH) 전부 실발동 실증 + 임계 2회 조정(로그 감속 곡선 반영) + 검증 페르소나 3종 신설 | ✅ 완료 |
| **서술 품질·계측 정비 (2026-07-17)** | 개시어 편중 동적 억제(15.3→11.8%) + PlayerThread 데드 상태 해소 + 스레드 억제 정책 기각(행동 카운터라 억제=기록 누락) + V10 센서 FP 제거 | ✅ 완료 |
| **arch/77 Phase 2 (2026-07-17~18)** | context-builder build() 1,528→553줄(-64%). 동작 보존 컷-페이스트 10단계, 게이트 2회 전부 10/10, 암묵 클로저 의존 4건 명시화 | ✅ 완료 |
| **서술 개시어·대명사 억제 사이클 (2026-07-18)** | [arch/78] D5 센서 + 개시어 임계 3→2 + 대명사 12종 합산. 20.3→16.2%(상대 -20.2%, 기준 미달 — soft 지시 천장). 즉흥 별칭 가설은 실측 기각 | ⚠️ 부분 달성 |
| **팩 에셋 풀 (2026-07-19)** | [arch/80] 이미지를 폴더에 넣고 sync 하면 저작·동적 NPC 와 장소에 자동 배정(성별·키워드 스코어, 런 내 고정). 슬러그 정규화로 실명 URL 404 방어 | ✅ 완료 |
| **프롬프트 토큰 최적화 (2026-07-19)** | [arch/79] 재시도 스킵(16.5→0%)·시스템 프롬프트 -62%·클러스터 압축·총량 백스톱 16,000자. avg 7,495tok(-31%), 절벽 턴 0% | ✅ 완료 |
| **arch/77 전 Phase 마감 (2026-07-18)** | God method 리팩토링 완결 — turns.service -56%, llm-worker -50%, 전투/DAG -41%, 클라 3파일 -26~-45%. DAG 골드 무바닥 결함 수정 | ✅ 완료 |
| **밤낮 시스템 재설계 (2026-07-20)** | [arch/81] 행동 가중 timeCost + 전환 턴 서술 주입 + 4상 UI 승격 + 이중 시간계 통합(timePhase = phaseV2 미러). 15턴 전환 5회→1회 | ✅ 완료 |
| **어체 자기모순 교정 (2026-07-20)** | [arch/82] speechRegister 와 speechStyle 이 충돌하던 3명을 산문 기준으로 통일 — 프롬프트 상충 주입이 어체 혼용의 원인이었다 | ✅ 완료 |
| **NPC 자연스러움 3종 (2026-07-20)** | 대화 분석(자연스러움·연속성) 도출 — #5 배경 감시자 advance-or-dismiss(정적 "훑어본다" 반복→진전/퇴장 강제) · #6 제스처 앵커 제거 L0+L1(recommendPool 삭제 — 정적 풀=anchor 불변식 41/42 + frequency/presence_penalty 0.4/0.3 미사용 모델 레버 투입, "목덜미" 상투구 0회) · #7 첫 조우 개방 깊이 티어(trust+encounterCount 긍정 프레이밍, 낯선 이 과다 개방 억제). memory feedback_concrete_vocab_anchor 신설 — architecture/82 B |
| **포인트 시스템 (2026-07-23)** | [arch/85] 채팅 1턴 5p 차감(코드 발급→충전→차감), 실패 턴 환불 2경로, 클라 잔액·충전 모달·402 유도. 소프트 베타 비용 통제 | ✅ 완료 |
| **자율 디렉터 존재감 튜닝 (2026-07-21)** | [arch/83] 병목이 임계가 아니라 "기회 창×신선도" 동시 성립임을 진단하고 stale 2→3턴·GRAVITY 상향. 채택 0~2→2.0/12턴, 강제 진행 회귀 0 | ✅ 완료 |
| **LLM 31B 승격 + 프로바이더 allowlist (2026-07-22)** | [arch/25] 메인 26B→31B dense + 모델별 프로바이더 allowlist(빈 서술 3~5/12턴 대응) + 빈 서술 3층 방어. 턴당 실과금 ₩1.57 | ✅ 완료 |
| **파티 던전 클라이언트 배선 (2026-07-23)** | [arch/84] 서버 엔진은 완성인데 클라 협동 입력이 미배선이던 것 해소 + 프롤로그 소프트락(전 팩 신규 파티 진입 불능) 제거 | ✅ 완료 |
| **어드민 콘솔 (2026-07-23)** | [arch/87] 관제 API 12종 + 하이브리드 AdminGuard·@AdminEndpoint 감사 로그 + 별도 앱. 일반 유저에 열려 있던 보안 결함 2건 봉쇄 | ✅ 완료 |
| **비-graymar 팩 정합 + 모바일 UX (2026-07-23)** | [arch/86] 팩 스코프 누락으로 고유 아이템을 못 쓰던 것, 팩 프리셋 초상화 미표시, 아이템 3층 프로세스, 모바일 서술 스크롤 min-h-0 회귀 | ✅ 완료 |
| **S5 엔딩 동선 + encounterCount 수정 (2026-07-23)** | [arch/88] arc_events.json 부재로 3루트 엔딩이 사장되던 것과, 워커 백필이 조우 카운트를 오염시켜 관계 티어링이 죽어 있던 것 수정 | ✅ 완료 |
| **플레이어 이름 인지 (2026-07-26)** | [arch/91] 프롤로그 통성명 + 통성명 기반 재회 호명. 재회 트리거 미발동의 원인이 encounterCount 고착임을 규명해 computeFamiliarity 로 전환 | ✅ 완료 |
| **랜딩 리디자인 P1~P4 (2026-07-25~26)** | [arch/90] 상용·게임 카피 12종 벤치마크로 톤 원칙 5 확립 후 카피 전면 교체 + 시나리오 카탈로그 + 게임플레이 CSS 재현 + 공개 통계 API | ✅ 완료 |
| **거점 정체성 충돌 + 검증 인프라 (2026-07-26)** | [arch/92] "여관에서 여관으로 이동"의 원인이 설계가 아니라 이름 중복임을 규명하고 4팩 거점 명명을 추상형으로 전환. V9 반복 센서 정밀화도 함께 | ✅ 완료 |
| **장소 배경 지속화 (2026-07-27)** | [arch/93] 대화 중 장면이 없는 구간(중앙값 3턴·최장 23턴)을 배경 레이어로 메움. 헤더 밴드안은 뷰포트 25% 잠식으로 기각 | ✅ 완료 |
| **회원번호 도입 (2026-07-27)** | 문의·지원에서 부를 수 있는 가입순 정수 식별자 — `users.member_no`(DB 시퀀스 부여, 재사용 없음) + 기존 31명 가입순 백필 + `GET /v1/auth/me` + 설정 모달 "내 계정"에 `#0016` 표시·복사 | ✅ 완료 |
| **모바일 스크롤·뷰포트 정합 (2026-07-27)** | [arch/94] 헤드리스 4뷰포트 점검으로 11종 수정 — 스크롤 되돌림 follow 모델, overscroll-contain, 타이틀·로그인 스크롤 구조, 모달 16곳, safe-area | ✅ 완료 |
| **NPC 엔진 분석 + 프롬프트 재비대 2·3차 (2026-07-27~28)** | [arch/79·95] 3주 재비대(백스톱 발동 35%→[NPC 일상] 상시 삭제) 규명·압축 13종·순서 교체·상한 16,500·V12 재비대 게이트. 어미 하락 진범=DeepSeek 교차 실측→비율 5:5→3:7. 역전 설계는 파일럿 실증 후 폐기(arch/95 종결, archive 태그) | ✅ 완료 |
| **장면 컷 시스템 arch/96 (2026-08-01)** | 소유자 사전 제작·태그화 이미지(content/<pack>/assets/scenes/ + sync scenes 확장)를 서술 태그 매칭으로 인라인 삽입 — SceneCutMatcher 3단 게이트(프리필터·렉시컬 프리스크린·nano confidence) + 워커 DONE 직전 ui.sceneCut + sceneCutState CAS + 전달 3경로(스트림·폴링·복원). Phase A(장소·NPC 컷)는 기구현 확인. 실런 E2E 발화·쿨다운·복원 검증, 단위 11케이스 | ✅ 완료 |
| **잡담 화제 시스템 확장 Task#1 A (2026-07-30)** | 4팩 daily_topics 368개 체제 + CORE·SUB 전원 호칭 명시(content 3548eb3) + 화제 소진 폴백·R4 어체 기본 호칭 폴백 + dedup 실동화 — 선택 topicId를 recentTopics에 CAS 역기록, carry-over·매칭 경로 fresh 우선 (server 9e2fb90~edaf2c0) | ✅ 완료 |
| **재회 빈도·시간 정체 해소 Task#2 (2026-07-30)** | 지연 틱(world-tick) + 아는 NPC 재회 가중(situation-generator) + 의뢰인 보고 동선(time-cost·turns) + 퀘스트 전환 보고 프레이밍 실노출 — go_hub 리라벨 + 워커 보존 (server 38e2d1c·9a10f1b, 배포 확인) | ✅ 완료 |
| **레이턴시 롱테일 + 어체 정합 (2026-07-31)** | ① SDK 이중 재시도 제거(openai/claude 클라이언트 maxRetries 0 — nano 5초 컷이 19~40초로 부풀던 원인, llm_call_logs 실측) ② 스트림 정체 타임아웃 신설(무델타 20s 절단→fallback, narrative max 270s 대응) ③ R5v2 하게체·반말 침투 교정 확장(~라네·~더군·~겠나·~이야·~었어 — DeepSeek 잔존 위반 39.7% 대응) + HAEYO 판정 갭 보완(~어요·~거든요 오집계) ④ NPA 자유도 축 chatOnly 시나리오 overall 제외(구조적 캡핑 2.88 해소) | ✅ 완료 |
| **잡담 응답률 + 파티 2인 QA (2026-08-01)** | ① 잡담 질문 턴 화제 경쟁 해소 — 무매칭 시 새 화제 주입 중단 + 입력 화제어 동적 주입 (응답률 67→83/71%, 어미 81→91/88% 실측, server 24c9a81) ② 파티 2인 실시간 UI QA 9종 전부 PASS + 결함 3건 수정 — 시작 실패 레디 소모(리셋을 런 생성 성공 후로, c010d6c)·로비 에러 무표시(배너)·초상화 404(presetPortraitUrl 정본 헬퍼, client 0ed3d6f). 레이턴시 fix 실측: nano p95 3.4s·max 6.5s(이전 max 40.5s). **잔여 백로그: 신규 유저끼리 파티 던전 시작 불가** — 로비 프리셋 선택 UI 부재, 리더 프리셋은 최근 솔로 런에서만 (동선 신설 필요) | ✅ 완료 (백로그 1) |
| **CHOICE 판돈 룰 보강 (2026-08-07)** | 버그 9fc337c9 — "밀수 루트를 묻는다"(TALK·nano 선택지)가 무판정 처리. 12e4868의 판돈 룰 5조건을 전부 비껴갔고 nano 동적 선택지엔 `payload.riskLevel`이 아예 없어 라벨 의미를 볼 경로가 없었다. 3층 보강(server 0a45000): ① nano 선택지 riskLevel 산출(비동기 경로, 지연 0) ② 저작 INVESTIGATE/SEARCH 승격(nano 제외 — 이중 승격 방지) ③ **라벨 주제어 ↔ 미발견 fact** 매칭 — fact 공개 경로와 같은 매처(getFactsByKeywords) 재사용으로 "판정 없는데 단서는 나오는" 역데스싱크 차단. 후속 69ee51f: nano→ChoiceItem 변환이 Track 1·2에 복제돼 riskLevel이 실런에서 0건이던 결함을 `buildNanoChoiceItemsCore` 통합으로 해소(Track 2가 덮어쓰는 구조라 Track 1만 고치면 무효). 실측 4런 — A-3 실발동 확인, riskLevel 분포 정상(≥2가 48~56%), FREE 잔존은 잡담·거래뿐(판정 인플레 0). **주의: 초기 예상치 34%→55%는 오산** — 시뮬레이션이 choiceId 기반 기존 룰 2종을 모델링하지 못해 baseline을 과소평가했고, 실제 기존 룰만으로 이미 80%다(신규 기여 ~+7pt) | ✅ 완료 |
| **파티 로비 배경 선택 (2026-08-07)** | 신규 유저끼리 던전 시작 불가 해소 (2026-08-01 백로그). 로비가 멤버 프리셋을 "가장 최근 솔로 런"에서만 가져와, 솔로 이력이 없으면 리더 presetId=null 로 createRun 이 거부됐다. `party_members` 에 lobby_preset_id·gender·scenario 추가 + `POST /v1/parties/:id/lobby/loadout`(팩 스코프 프리셋 검증) + canStart 에 프리셋 확정 검사·missingPresetNicknames + 클라 LobbyLoadoutPicker. E2E(신규 2명·솔로 이력 0): 시작 성공. server ea84c33 · client 8feb5ff | ✅ 완료 |
| **게이트 누적 판정 전환 (2026-08-07)** | V12·V13 이 런당 표본(14~20턴 / 27~36선택지)에서 1건이 3~5%p 라 노이즈로 뒤집히던 것을 최근 3런 **원시 카운트 풀링**으로 전환 (`append_gate_ledger`, 2런 미만 보류). V12 재초과는 신규 커밋 무관으로 확정(프롬프트 유입 0·CHECK 턴이 FREE 턴보다 작음·발동 다수가 FREE) — 원인은 규칙 28%×대화 컨텍스트 29% 중첩. V13 도 편중 재발이 아니라 표본 착시(당일 누적 16.7% 통과). 전환 후 **게이트 14/14 전항목 통과**. arch/79 §11 · arch/98 §11 | ✅ 완료 |
| **turns.service 도메인 분할 (2026-08-07)** | arch/77 §5 재비대화 래칫 발화(함수 2,075/2,000·파일 9,194/9,000)에 대응. 상한 상향 없이 분할 — 공용 헬퍼(turn-shared)·장비상점·DAG·HUB·전투 5개 서브서비스 + 순수 코어(turns.core, 순환 임포트 차단) + 본문 블록 2개 private 메서드화. **9,194→6,864줄 · 2,075→1,860줄**, 경고 해소. 래칫 재설정 max-lines 9,000→7,900(새 최대치+15%, 이전 여유 3%는 3주 만에 상시 경고화). 근거: 호출 그래프가 트리(피호출 대부분 1회)·공유 헬퍼 7개·**가변 인스턴스 상태 0건**. arch/77 §18 | ✅ 완료 |
| **프롬프트 중복·충돌 정리 (2026-08-12)** | ① speechStyle 3중 주입 해소 — `[NPC 대화 자세]`·`[NPC 감정 상태]`·`[이번 턴 NPC 말투]`가 같은 말투를 각각 기술하던 것을 근접 위치 정본 하나로(스냅샷 7종 -131자/프롬프트, 어체 오염 0). ② `[NPC 등장]` 헤더 충돌 — NanoDirector 자유 묘사(①)와 orchestration 등장 선언(②)이 같은 헤더로 서로 다른 인물을 지목하던 것을 ② 우선으로 게이트(실측 1,353턴 중 동시 25턴·인물 모순 7건). **둘 다 측정 가능한 품질 피해는 확인되지 않았고 값은 정합성** — ②는 충돌률 1.8%라 짧은 플레이테스트로 개선 폭 측정이 성립하지 않는다(30턴 관측 확률 43%). arch/79 §11.4.2 · arch/49 부록 | ✅ 완료 |
| **nano 엔진 점검 후속 4종 (2026-08-13~14)** | nano 전수 점검(정합 ✅·하드 결함 0) 후 실효 상위 항목 일괄: ① **NanoEventDirector Track 다이어트** — T1 선택지(T2가 상시 덮어씀)·T2 연출 필드(소비처 없음)의 이중 풀 출력을 outputMode 분리(direction/choices/full)로 제거, T1 maxTokens 430→240 (서술 크리티컬 패스 단축, 비스트리밍은 full 보험 유지) + **R2 반복 가드 배선**(applyR2Guard가 caller 0곳으로 영구 무발동이던 것을 llmNpcReaction 계측 컬럼 복원으로 연결) e5cf111 ② **경계 거절 3층**(버그 95db0e75 "다른 대륙으로 떠난다" 무시) — L1 룰(move-boundary.core, 거시 경계 명사 positive)·L2 nano(Plausibility 4단계 OUT_OF_SCOPE, FREE 강제)·L3 [경계 거절 지시](세계 내 장애물로 가로막기), E2E 실증 295fd34 · arch/76 D3-④ ③ **쓰레기 토큰 새니타이즈**(Luna·Gemma ~1% 디제너레이션: 한자 뭉치·`/en-thought` 토큰·고립 라틴 대문자) stripModelJunkCore 5.10.11 2b88ea4 ④ **V12 다이어트 5차** — 658턴 해부로 PLAYER_DIRECTED 50% 발동·구제곡선(-500~700자면 해소) 규명 → NPC 지시 스택 표적 압축 -598자/프롬프트, 게이트 24%→11% 복귀·14/14 PASS db73039 · arch/79 §12. 잔여 백로그: fire-and-forget nano 로그 유실(계측)·factRevealed 게이트·감정 이중 채널 계측 | ✅ 완료 |
| **세계 자율 진행 복구 (2026-08-13)** | "무엇을 해도 세계가 고요하다" 피드백을 30일 실측으로 대조. 원인은 하나가 아니라 **사문 배선 3건**이었고 전부 `actionType`/`parsedType`(arch/100 §14)과 같은 "조용히 꺼진" 부류라 어느 게이트에도 안 걸렸다. ① 엔진은 `longTermAgenda`(구조체)를 읽는데 저작된 건 `agenda`(프롬프트용 동기 **문자열**) — 구조체 보유 5명뿐, NPC_RONEN 은 문자열이라 무시 ② 저작된 15 스테이지가 **전부 `day >= 2~10`** 인데 158런 중 144런(91%)이 day 1 종료(평균 1.10) → `globalClock` 지원 추가 후 재기준화 ③ `conditionApply` 키 불일치(콘텐츠 `targetLocation` ↔ 엔진 `locationId`)로 `addCondition` 항상 false. + 대화 지연 틱 6→2·발효 상한 2(arch/81 3차)·행동화/목격 반응 조사 폴백 `이(가)` 8곳(유저 노출)·흔적 관측 로그. **실측 대비**: worldFact `NPC_ACTION` 30일 전체 10건 → 15턴 한 런에 **8건**(카테고리 비중 0.5%→40%), npcGoals 6명·agenda 시그널 8건. 회귀 0(대화 턴 전환 0건, 불변식 49 유지). 게이트 12/14 — V9·V12 는 변경 **전** 런에서도 동일 실패. **미달 1건**: 시계 실효 0.39→0.43 tick/턴으로 예상(≈0.64)에 못 미침, 단일 런이라 누적 재측정 필요. **잔여**: worldFact `WORLD_CHANGE`/`RELATIONSHIP` 쓰기 지점 0곳 · 시그널 템플릿 14/55 도달 불능(`triggerPressure` 60~85 vs 압력 63%가 ≤10) · karnholt agenda(디렉터 충돌 판단 선행). arch/21 Part 11 · arch/81 3차 | ✅ 완료 |
| **선택지 품질 개선 (2026-08-04~05)** | [arch/98] 실유저 503개 선택지 표본에서 결함 5건 확정 — npcId 오염(2.1%)·TALK/OBSERVE/INVESTIGATE 91% 편중·질문 턴 응답 부재 92%·BRIBE 5턴 연속. P0~P4 구현 + V13 센서 신설, 적극 축 2%→25% 실측. §11 누적 게이트 전환은 별도 항목 참조 | ✅ 완료 |
| **퀘스트탭 실효성 (2026-08-05)** | [arch/99] 활성 목표 데드코드·HUB 턴 quest 번들 미부착(arc 커밋 직후 스테일)·요약 중복·팩 격차(karnholt D-14 오정보)·배지 부재 5건 — 서버 attachQuestUiBundle 6곳 + hasArcCommit, 클라 섹션 정리·AUTONOMOUS 시한 게이팅·단서 발견 점 배지 | ✅ 완료 |
| **자기점검 하네스 (2026-08-12)** | [arch/101] "전 게이트 통과한 채 조용히 꺼진" 결함 7건에서 역설계한 코드·문서·DB 3소스 교차 대조 루프 — 디텍터 5족(`scripts/selfcheck/` + ledger.jsonl) + 검증 사다리(정적→과거 원문 재생→런 5회 예산) + 오탐 통제(분모 강제·baseline expires). 1회차 수행 산출물이 불변식 17의 백스톱 초과 17.8% 실측 | ✅ 완료 |
| **이미지 정본 단일화 (2026-08-14)** | [arch/102] 장소 이미지 결정이 100% 클라 하드코딩이라 장면 컷 장소 후보가 graymar·star_sand에서 영구 0이던 결함 해소 — location_images.json 콘텐츠 승격(URL 불변, 매처 스펙 17케이스) + 초상화 npcs.json portraitUrl 외부화(클라 미러 맵 삭제) + 마커 와이어 포맷 URL→npcId 전환(혼재 허용) + 장소 이미지 URL 서버 이관. 잔여: 클라 레거시 리졸버 최종 삭제·E-2 실런 검증 10턴 | ✅ 완료 |
| **아크 종반부 3막 (2026-08-18)** | [arch/103] 버그 3c501bf7("커밋 후 어떻게 끝나는지 모르겠다") 근본 해소 — ① 사문이던 arc 스테이지 이벤트(`getArcEvents` 소비 0곳, 2026-02-18 이래) 배선: 커밋 후 전용 발화·판정형(FAIL 2회 후 자동 PARTIAL)·순차 완료만 강제 ② stage 3 완료 → "결말을 맞이한다"(`arc_finale`) 상시 선택지 → 기존 ALL_RESOLVED 엔딩 직행 ③ S5+5 안전망 타이머 코어 추출 + HUB 배선(마킹+선택지 노출, 자동 종료 아님) ④ 커밋 턴 힌트·nextObjectives 공백 봉합. 코어 스펙 18케이스 + E2E 전항목 PASS(ALLY_GUARD 3막 완주→"질서의 수호자" 엔딩, HUB 타이머 경로). 잔여: 실LLM 서술 품질 1런 | ✅ 완료 |
| **NPC 대화 게이트 재설계 (2026-08-18)** | [arch/104] 정성 리뷰(3런 70턴 전문 정독)에서 출발 — "로봇 같다/대화가 안 이어진다/맥락을 못 잡는다/같은 대사 반복" 4개 증상이 **두 게이트에서 갈라진 같은 뿌리**임을 규명. 둘 다 "문서에 있는 규칙이 구현에 없다" 부류. ① **잡담 게이트**가 의도가 아니라 "fact 4종 부재"라는 부산물을 신호로 써, TALK 에서만 성립하는 프록시가 조사·잠입·협박 턴에 항상 참이 됨(69% 주입·사교 발화 턴 0건). 화이트리스트로 반전 + 소진 폴백 제거(프롬프트가 예시한 "몸 상태·날씨 체감"이 그대로 출력되던 증폭기) + 원문 인용 금지 ② **대화 잠금**에 연속 카운터가 없고(화자 있는 첫 이력에서 즉시 return) 갱신 집합에 OBSERVE·INVESTIGATE·TRADE 가 포함돼, BACKGROUND NPC 가 **17턴 독점**(그 구간 대화 행동 2턴·fact 획득 0). RENEW/HOLD/BREAK 3상태 + streak 상한(CORE 4·BACKGROUND 0) + 복제 drift 차단(getLockState 단일 접근) ③ `[NPC 고정]`이 else-if 첫 가지라 기존 `[NPC 피로]`가 영원히 도달 못하던 **자기강화 루프** 차단(전환 예고 병기). 실측: 잡담 50%→TALK 전용(위반 0/40턴)·BACKGROUND 화자 17턴→0·화자 2명 32턴→5명 분산·게이트 14/14·NPC 점프 회귀 0. 신규 스펙 39. 잔여: daily_topics 소재어 축약(368개)·되묻기 억제·미완결 등장 | ✅ 완료 |
| **silverdeen_v1 팩 제거 (2026-08-18)** | 소유자 지시로 미니 팩 완전 제거. 서버 프로덕션 코드 참조는 **전부 주석**이었다(불변식 45 준수 덕에 로직 분기 0) — 팩 탐색이 `readdir` 기반이라 폴더 삭제만으로 반영. 테스트 5종은 계약을 잃지 않도록 대체: 멀티팩 격리→star_sand, 팩 계약→**karnholt**(`arc_events.json` 부재라 "아크 자산 없는 팩 = 커밋 선택지 미노출" 계약을 그대로 검증), 팩 수 하한 4→3. 클라 카탈로그·프리셋 치환·이미지 분기 제거. DB 런 2건(RUN_ABORTED)은 보존하고 팩 부재 상태 조회 정상 확인. **부수 발견(미수정)**: karnholt 8개 장소 전부 `ambushEncounterId=enc_generic` 인데 encounters 에 부재 → 매복 조우 영구 미발동, audit_content 에 ambush 규칙도 없음 | ✅ 완료 |
| **실런 리뷰 결함 수정 (2026-08-19)** | [arch/105] arch/104 배포 확인차 **런 하나(`6dc4880d`, 11턴)를 전문 정독**했더니 아래 층에서 8건이 나왔다. 전부 게이트 14개를 통과한 상태였다. **P0-1 실명 치환 substring 오염** — 미소개 `브렌`이 공개된 `토브렌 하위크` 내부를 때려 프롬프트 15곳이 `토단정한 장교 하위크`로 파손, 서술이 6턴 동안 창고 관리인을 "단정한 장교"로 호칭(마커·초상화는 토브렌 → 카드/본문 불일치). **골든 스냅샷 8건에 이미 박제**돼 있었다 — 스냅샷은 "안 바뀜"만 보증한다. naive `replaceAll` 3곳 + 복제본 1곳을 `maskHiddenNpcNames` 정본으로 수렴, Phase A 어절 토큰 보호 추가(단 **미공개 패턴이 진부분문자열일 때만** — 무조건 보호는 `대위` 공용어를 잠가 역회귀). 전 팩 충돌 5쌍(star_sand `귀환자⊃환자`·`멜라/오벨 수녀⊃수녀`). **P0-2 소재 안내 자기모순** — 같은 프롬프트가 "토브렌이 중심이어야"와 "'수상한 관리인'은 부재/화자 금지"를 동시 지시(둘 다 NPC_TOBREN, npcLocations desync). 현재 장면 인물 제외 + 소개 후 실명. **P0-3 프롬프트 완성 문장 예시** — DB 4,145턴 전수로 복제 실적 확인(관찰 예시 40턴·간접 흘림 21턴·인계 5턴), 3곳 모두 구성 요소 지시로 교체. **P0-4 세계 밖 요청 무처리** — 경계 거절 3층이 이동 전용이라 "스마트폰으로 사진 찍고 스탯 100" 이 SUCCESS로 서술됨. `world-boundary.core` 신설(META→OUT_OF_SCOPE+주사위 스킵, ANACHRONISM→IMPLAUSIBLE) + L2 루브릭 확장. **P1** 미완결 등장(대사 금지+등장 허용의 어긋난 조합)·선택지 라벨(대명사 20/32·화폐 기계어·환각)·장소 데스싱크. **P2** toneHint 탈주사위(30일 2,162턴 중 triumph 57%, tense/calm/mysterious **0회**)·시그널 자가오염(11턴에 17건 중 8건이 플레이어 자신). **철회 1건**: "토브렌 어체 혼용"은 오판 — 59문장 실측 전부 낮춤이고 콘텐츠 정의대로였다. 신규 스펙 43·전체 2,122 passed·게이트 15/15. **검증 한계**: P0-1·P0-2는 실런에서 조건 미성립(공허한 통과, 근거는 스냅샷 diff+단위 스펙)·실유저 런 0건 | ✅ 완료 |
## Document Status (설계 문서 현황)

> **중간 색인**: [[architecture/INDEX|INDEX]] — 도메인별 1문단 요약 + 상호 참조 맵. 상세 문서 진입 전 확인 권장.

### specs/ — 상세 스펙 (17 md)

| 파일 | 상태 | 비고 |
|------|------|------|
| combat_system.md | ✅ 정본 | 전투 공식 (floor 적용) |
| combat_engine_resolve_v1.md | ✅ 정본 | 구현 연동 |
| battlestate_storage_recovery_v1.md | ✅ 정본 | 저장 구조 |
| node_resolve_rules_v1.md | ✅ 정본 | 노드 처리 |
| llm_context_system.md | ✅ 정본 | L0~L4 컨텍스트 (v1 + memory v1_1 통합) |
| server_api_system.md | ✅ 정본 | API 계약 |
| status_effect_system_v1.md | ✅ 정본 | 상태이상 |
| core_game_architecture_v1.md | ✅ 정본 | 역할 분리 |
| political_narrative_system_v1.md | ✅ 참고 | 정치/관계 |
| protagonist_world_v1.md | ✅ 참고 | 세계 서사 |
| rewards_and_progression_v1.md | ✅ 참고 | 보상/성장 |
| run_node_planner.md | ✅ 참고 | 런/노드 구조 + 플래너 (run_node_system + run_planner_v1_1 통합) |
| vertical_slice_v1.md | ✅ 참고 | 버티컬 슬라이스 |
| character_growth_v1.md | 📎 향후 | 캐릭터 성장 |
| magic_system_consolidated_v1.md | 📎 향후 | 마법 시스템 |
| input_processing_pipeline_v1.md | ⚠️ 부분 | 전투 입력만 구현 |
| node_routing_v2.md | ✅ 구현됨 | DAG 24노드 + 조건부 분기 |

### architecture/ — 통합 아키텍처 (91 md + INDEX)

> 아래는 **파일명·상태·한 줄 성격**만. 도메인별 1~2문단 요약과 상호 참조 맵은
> [[architecture/INDEX|INDEX]] 가 정본이다 (같은 설명을 두 곳에 두지 않는다).

| 파일 | 상태 | 비고 |
| INDEX.md | 📇 색인 | 도메인별 요약 + 상호 참조 (CLAUDE.md ↔ 상세 문서 중간 레이어) |
| 01_world_narrative.md | ✅ 정본 | 세계관/정치 |
| 02_combat_system.md | ✅ 정본 | 전투 통합 |
| 03_hub_engine.md | ✅ 구현됨 | HUB Action-First |
| 04_server_architecture.md | ✅ 정본 | 서버 아키텍처 |
| 05_llm_narrative.md | ✅ 정본 | LLM 파이프라인 개요 |
| 06_graymar_content.md | ✅ 구현됨 | 콘텐츠 데이터 |
| 07_game_progression.md | ⚠️ 업데이트 필요 | HUB 모드 |
| 08_node_routing.md | ✅ 구현됨 | DAG 24노드 + 3루트 분기 |
| 09_npc_politics.md | ⚠️ 부분 | 감정/소개 ✅, Leverage ❌ |
| 10_region_economy.md | ⚠️ 부분 | 장비/세트 ✅, 리전 경제 미완 |
| 11_llm_prompt_caching.md | 📎 설계 | 최적화 전략 |
| 12_equipment_system.md | ✅ 구현됨 | 장비 드랍/착용, 세트효과, Legendary |
| 14_user_driven_code_bridge.md | ✅ 구현됨 | IntentV3→Incident→Router→Ending |
| 15_notification_system.md | ✅ 구현됨 | Notification 설계 + UI + 클라이언트 브릿지 (15/16/17 통합) |
| 21_living_world_redesign.md | ✅ 구현됨 | Living World v2 설계 배경 (구현 API는 guides/07) + **Part 11 세계 자율 진행 복구**(2026-08-13 — agenda 사문 배선 3건·worldFact NPC_ACTION 부활) |
| 22_dice_roll_animation.md | ✅ 구현됨 | 주사위 판정 애니메이션 |
| 23_dialogue_ui_redesign.md | ✅ 설계 | 대화 UI 고도화 (메신저 형태) |
| 24_multiplayer_party_system.md | ✅ 구현됨 | 파티 설계·Phase 1~3 (구현 API는 guides/08) |
| 25_llm_model_evaluation.md | ✅ 정본 | LLM 모델 평가 (v1~v5 통합) + 운영 모델 변천. **부록 E(2026-08-13)가 현 구성 정본** — 교차 Luna 5:5·ModelRun 제거·fallback 404 해소·Gemini 보류·검증도구 결함 6종. **부록 F(2026-08-14)** — Gemini 3.x 후보 평가(3.6-flash 탈락·3.5-flash-lite 보류) + flex 티어/Vertex temperature 함정 + 도구 결함 7·8 |
| 26_narrative_pipeline_v2.md | ✅ 구현됨 | 3-Stage Pipeline + Narrative v2/Event(18/19/20 부록) + AI… |
| archive/27_image_asset_plan.md | 📜 아카이브 | 에셋 계획 — 부분 구현, content/ 하위 실측 참조 |
| archive/28_nano_event_director.md | 📜 아카이브 | 34_player_first_event_engine 의 배경 설계 |
| 30_marker_accuracy_improvement.md | ✅ 구현됨 | @마커 오류율 개선 3전략 |
| 31_memory_system_v4.md | ✅ 구현됨 | Memory v4: entity_facts UPSERT + nano 요약 주입 |
| 32_dialogue_split_pipeline.md | ✅ 구현됨 | 2-Stage 대사 분리 파이프라인 |
| 33_lorebook_system.md | ✅ 구현됨 | 키워드 트리거 로어북 |
| 34_player_first_event_engine.md | ✅ 구현됨 | Player-First 이벤트 엔진 |
| 35_llm_streaming.md | ✅ 구현됨 | LLM 스트리밍 설계 + Dual-Track 구현 + 후속 수정 |
| 36_llm_pipeline_changelog_20260417.md | 📜 이력 | 2026-04-17 LLM 파이프라인·렌더링·품질 수정 Before/After 정리 |
| 39_ending_journey_archive.md | ✅ 구현됨 | 엔딩 연출 6항목 + 여정 아카이브 Phase 1 |
| 40_inventory_item_integrity.md | ✅ 구현됨 | 소지품 UX 개선 + LLM-실획득 정합성 A+B + 콘텐츠 매핑 |
| 41_creative_combat_actions.md | ✅ 구현됨 | 창의 전투 5-Tier 분류 MVP |
| 42_combat_ui_buttonform.md | ✅ 구현됨 | 전투 UI 버튼 폼 |
| 43_sudden_action_context_preservation.md | ✅ 구현됨 | 돌발행동 맥락 보존 |
| 44_npc_dialogue_quality_v2.md | ✅ 구현됨 | NPC 대사 품질 v2 |
| 45_npc_free_dialogue.md | ✅ 구현됨 | NPC 자유 대화 |
| 46_fact_pool_continuity.md | ✅ 구현됨 | Fact 일급 객체(facts.json) + NPC 연속성 |
| 47_dialogue_quality_audit.md | ✅ 구현됨 | NPA Audit 시스템 설계 (scripts/e2e/audit/로 구현) |
| 48_npc_discoverability_v1.md | ✅ 구현됨 | NPC Discoverability |
| 49_npc_resolver_authority.md | ✅ 구현됨 | NpcResolverService 단일 권한자 (server 56446b0) |
| 50_natural_dialogue_v1.md | 📜 폐기 | A50 자연 대화 v1 |
| 51_npc_distinctness_v1.md | ✅ 구현됨 | NPC Distinctness v1 |
| 55_npa_metric_v2.md | ✅ 구현됨 | NPA 메트릭 v2 |
| 56_npc_reaction_director.md | ✅ 구현됨 | NpcReactionDirector + ChallengeClassifier + speechStyle 추상화… |
| 58_fact_reveal_unification.md | ✅ 구현됨 | 단서 기록·서술 단일화 |
| 59_fact_dialogue_followup_plan.md | ✅ 구현됨 | 판정 NPC 정합 + [단서 방향] 복구 + off-by-one |
| 60_clue_flow_tuning.md | ✅ 구현됨 | 워커 lost update(P0) + 인계 양보 + 힌트 이월 + fallback 확률 게이트 |
| 61_choice_recommendation_tuning.md | ✅ 구현됨 | 선택지 추천 튜닝 P1~P6 |
| 62_latency_optimization.md | ✅ 구현됨 | 레이턴시 최적화 4건 |
| 63_multi_scenario_content_decoupling.md | ✅ 구현됨 | 멀티 시나리오 선행작업 ②~⑤ |
| 64_npc_name_reveal_integrity.md | ✅ 구현됨 | NPC 이름 공개 정합 |
| 65_economy_loop_v1.md | ✅ 구현됨 | 경제 루프 v1 |
| 66_npc_self_introduction.md | ✅ 구현됨 | NPC 자기소개 사전 확정 |
| 67_nano_engine_audit.md | ✅ 구현됨 | Nano 엔진 전수 감사 + 부록 A~E: 카드 정합 · 테스트 감사 · 완주 평가 · 자유 대화(가드·화자… |
| 68_uiux_audit_v1.md | ✅ 구현됨 | UI/UX 실사 리뷰 v1 |
| 69_npc_living_presence.md | ✅ 구현됨 | NPC Living Presence B축 |
| 70_campaign_progression.md | ⚠️ 게이팅 대체됨 | 캠페인 순차 진행 |
| 71_campaign_free_scenario_selection.md | ✅ 구현됨 | 캠페인 자유 시나리오 선택 |
| 72_npc_reaction_authority_unification.md | ✅ 구현됨 | NPC 반응 권한 통합 |
| 73_scenario_differentiation.md | 📎 설계(제안) | 시나리오 차별화 |
| 74_autonomous_narrative_direction.md | 📎 논의(제안) | 자율 서사·NPC 생성 심층 논의 |
| 75_autonomous_pack_design.md | ✅ 구현·배포 (P7 후속 대기, P8 후속=83 완료) | 자율 서사 팩 "진상 선확정 디렉터 모드" |
| 76_market_alignment_direction.md | ✅ 구현됨 (D6 저작 도구만 잔여) | 시장 조사 대응 방향 |
| 77_god_method_refactoring.md | ✅ 구현됨 | God method 리팩토링 |
| 78_narrative_opener_pronoun_cycle.md | ✅ 2차까지 완료 | 개시어·대명사 억제 |
| 80_pack_asset_pool.md | ✅ 구현됨 | 팩 에셋 풀 — 이미지 폴더 투입→sync(슬러그 정규화)→저작·동적 NPC·장소 자동 매칭 (성별·키워드… |
| 81_day_night_system.md | ✅ 구현됨 (3차 포함) | 밤낮 시스템 재설계 (3차 2026-08-13 — 대화 지연 틱 6→2·발효 상한 2) |
| 82_npc_dialogue_naturalness.md | ✅ 구현됨 | NPC 대화 자연스러움 |
| 83_director_presence_tuning.md | ✅ 구현됨 | 자율 디렉터 존재감 튜닝 |
| 84_party_dungeon_client_wiring.md | ✅ 구현됨 | 파티 던전 클라이언트 배선 완성 |
| 85_point_system.md | ✅ 구현·배포됨 | 포인트 시스템 — 코드 발급→충전→채팅 5p 차감(전 턴 일괄·다회용·가입 50p). DB 4종… |
| 88_endgame_arc_commit_encounter_fix.md | ✅ 구현됨 | S5 엔딩 동선(arc 커밋) 복구 + encounterCount 추적 수정 |
| 89_quest_reward_attribution.md | ✅ 구현됨 | 사례금 귀속 재설계 |
| 91_player_name_recognition.md | ✅ 구현됨 | 플레이어 이름 인지 |
| 92_hub_base_location_collision.md | ✅ 구현됨 | 거점(HUB) ↔ 거점 장소 정체성 충돌 |
| 93_location_backdrop.md | ✅ 구현됨 | 장소 배경 지속화 |
| 94_mobile_scroll_viewport.md | ✅ 구현됨 | 모바일 스크롤·뷰포트 정합 |
| 95_prompt_split_analysis.md | 📜 종결 (폐기) | 프롬프트 이분할·역전 설계 전면 폐기 (2026-07-28 소유자 결정) — 파일럿 실측은 §7 보존 (archive/spike-dialogue-precommit 태그). 잔존: DeepSeek 짝수 턴 어미 열세는 별개 이슈 |
| 96_inline_image_insertion.md | ✅ 구현됨 | 장면 컷 시스템 — 소유자 태그 풀(assets/scenes) → 렉시컬 프리스크린 + nano 매칭 → 서술 인라인 컷 (A 기구현 확인·C 본체 구현) |
| 97_creation_simplification.md | ✅ 구현됨 | 캐릭터 생성 간략화 — 6단계→2단계(배경→마무리), 스탯 +6 프리셋 내장 + defaultTraitId 자동 특성 (4팩 22프리셋) |
| 90_landing_page_redesign.md | ✅ 구현됨 | 랜딩 리디자인 P1~P4 |
| 87_admin_console.md | ✅ 구현됨 | 어드민 콘솔 — users.role+AdminGuard 하이브리드+@AdminEndpoint(감사 로그)+관제… |
| 86_pack_parity_mobile_ux.md | ✅ 구현됨 | 비-graymar 팩 정합 + 모바일 UX 마감 |
| 79_prompt_token_optimization.md | ✅ 구현됨 | 측정 기반 프롬프트 예산 |
| 100_competitor_prompt_analysis.md | 📎 분석 | 경쟁 텍스트게임 프롬프트 구조 역추론 — 서술 기법 이식 검토 (착수 2·결정대기 2·기각권고 1) |
| 98_choice_quality_improvement.md | ✅ 구현됨 | 선택지 품질 개선 — ChoiceNpcIdNorm·적극 축 주입(2%→25%)·질문 응답 보장·BRIBE 쿨다운 + V13 누적 게이트(≥15% 단일 임계, §11) |
| 99_quest_tab_effectiveness.md | ✅ 구현됨 | 퀘스트탭 실효성 — 죽은 섹션 제거·HUB 턴 quest UI 부착(hasArcCommit)·AUTONOMOUS 시한 게이팅·단서 발견 배지 |
| 101_selfcheck_loop.md | ✅ 구현됨 | 자기개선 하네스 — 코드·문서·DB 3소스 정합 감사 디텍터 5족(`scripts/selfcheck/`) + 검증 사다리·런 예산 5회 (문서 헤더 "미구현"은 스테일) |
| 102_location_image_content_pool.md | ✅ 구현됨 | 이미지 정본 단일화 — location_images.json 콘텐츠 승격 + 초상화 npcs.json portraitUrl 외부화 + 마커 npcId 전환 + 장소 URL 서버 이관 (잔여: 클라 레거시 리졸버 삭제·실런 10턴) |
| 103_arc_endgame_stages.md | ✅ 구현됨 | 아크 종반부 3막 — 사문이던 arc 스테이지 이벤트(getArcEvents 소비 0곳) 배선 + 결말 선택지(arc_finale) + S5+5 안전망 HUB 확장 + 커밋 후 안내 (버그 3c501bf7, 잔여: 실LLM 서술 품질 1런) |
| 104_npc_dialogue_gate_rework.md | ✅ 구현됨 | NPC 대화 게이트 재설계 — 잡담 주입 화이트리스트 전환(small-talk-gate.core)·소진 폴백 제거 + 대화 잠금 3상태/streak 상한/BACKGROUND 제외(conversation-lock.core)·자기강화 루프 차단. 불변식 23·26·44·50 개정 (잔여: daily_topics 축약·되묻기 억제·P2 5종) |
| 105_run_review_defect_fixes.md | ✅ 구현됨 | 실런 1개 전문 정독에서 나온 결함 8건 — 실명 치환 substring 오염(정본 수렴)·소재 안내 자기모순·프롬프트 완성 문장 예시 복제·세계 밖 요청(META/ANACHRONISM) 무처리·미완결 등장·선택지 라벨·toneHint 탈주사위·시그널 자가오염. 불변식 51~54 신설 (잔여: npcLocations desync 근본 수정·장소 고정 실효 측정) |
| 106_input_content_safety_gate.md | ✅ 구현됨 | 입력 콘텐츠 세이프티 게이트 — 유해 입력(성적 노골·미성년/약자 폭력·자해) 방어. world-boundary 3부류에 4번째 부류 편입(`content-safety.core` L1 룰+nano contentSafety 축+L3 [유해 행동 제지 지시]). refused→forceRefulsal(델타 0)로 FREE≠자동성공 함정 회피. REDIRECT=제지 서술 / HARD_REFUSE=고정 문안(LLM 미호출)·무과금. MVP 4종 활성(HATE 비활성). 불변식 55 신설. 실측: 미성년 폭력 SUCCESS→HARD_REFUSE, 비속어 오탐 0, L1 오탐 baseline 1,201턴 전수=정상 입력 오탐 0% (잔여: HATE 활성화·L2 nano 오탐 샘플·어드민 flagged 집계) |
| archive/37_streaming_transition_issues.md | 📜 아카이브 | 35+36과 중복 |
| archive/38_stream_vs_nonstream_comparison.md | 📜 아카이브 | 35와 중복 |
| Context Coherence Reinforcement.md | ✅ 구현됨 | 컨텍스트 일관성 강화 |
| Narrative_Engine_v1_Integrated_Spec.md | ✅ 정본 | Narrative Engine v1 통합 |
| phase_history.md | 📜 이력 | 구현 단계 표 원문 전량 (163 항목) |
| fixplan_history.md | 📜 아카이브 | 완료된 플레이테스트 패치 내역 (fixplan 3/4/5 통합) |

### guides/ — 코드 구현 지침 (14 md)

| 파일 | 내용 |
|------|------|
| 01_server_module_map.md | 서버 전체 서비스 맵 (117 services, 45 타입 파일) |
| 02_client_component_map.md | 클라이언트 컴포넌트 맵 (71 components, stores, CSS) |
| 03_hub_engine_guide.md | HUB 엔진 구현 (판정, EventDirector, Narrative, NPC, 평판) |
| 04_llm_memory_guide.md | LLM 파이프라인, 메모리 L0~L4, Token Budget, Scene Continuity |
| 05_runstate_constants.md | RunState JSONB 구조, 핵심 상수, Content Data |
| 06_location_image_prompts.md | 장소별 이미지 프롬프트 가이드 |
| 07_living_world_guide.md | Living World 7 서비스 (LocationState/WorldFact/NpcSchedule/NpcAgenda/Consequence/Situation/PlayerGoal) 메서드·스키마 |
| 08_party_guide.md | 파티 시스템 서비스·엔드포인트·DB 테이블·SSE 이벤트 |
| 09_karnholt_asset_prompts.md | 카른홀트 팩 에셋 생성 프롬프트 (arch/80 팩 에셋 풀용) — 초상화/장소 파일명 짝지은 27종 + 공통 스타일 프리픽스 |
| 10_star_sand_item_prompts.md | 별빛모래 아이템 이미지 프롬프트(10종) + 아이콘 공통 스타일 + **부록: 새 아이템 추가 3층 프로세스**(서버 `items.json`·클라 `ITEM_CATALOG`·이미지 `client/public/items/itemId소문자.webp` — 팩 에셋 풀과 별개 경로, usableInHub는 effect 기준) |
| 11_scene_cut_guide.md | 장면 컷 제작·투입 가이드 (arch/96) — 파일명=태그 규약·고빈도 장면 유형·생성 프롬프트 템플릿·운영 튜닝 (인물·장소 자동 편입 포함) |
| 12_graymar_scene_cut_prompts.md | 그레이마르 장면 컷 프롬프트 — 1차 26종 + 2차 18종(#27~44) + 3차 18종(#92~109, 45일 991턴 재실측: 수레·필체 조작·광장·지붕 + fact·Incident 선행 태깅 + 미커버 인물 밴스·쉐도우·이졸데·토브렌·로넨 3컷째) |
| 13_star_sand_scene_cut_prompts.md | 별빛모래 장면 컷 3차 15종(#45~59) + 4차 16종(#60~75) + 5차 16종(#76~91) — 3·4차는 311턴 실측 기반(초상화 풀 부재 → 기존 감정 컷이 얼굴 정본 규약), 5차는 콘텐츠 주입 어휘 선행 태깅(Incident 7종·퀘스트 S2~S5 무대 4·SUB 첫 컷 4 — fact 문구가 questReveal로 서술에 확정 등장하는 원리) + **6차 33종(#110~142) — CORE·SUB 18명 전원 감정 컷 3종 체제**(355턴 실측, 리바·페나 첫 컷). 태그 규칙: 첫 토큰=실명(진입권) · **같은 인물 컷끼리 감정 토큰 겹침 금지**(겹치면 hits 동률 → 감정 무관 무작위 선택) · 감정어는 코퍼스 실측 상위에서만 |
| 14_dice_face_prompts.md | 주사위 면 텍스처 이미지 프롬프트 (Dice3D Tier 2) — 판정 연출 6면을 소유자 제작 이미지로 교체하기 위한 배리에이션 3종(ivory/obsidian/bronze) 프롬프트 + `client/public/dice/<배리에이션>/` 파일 규약. 이미지 투입 후 CSS 배선(`globals.css .dice3d-face`)은 별도 진행 |

## Working Language

설계 문서와 게임 콘텐츠는 한국어. 기술 식별자(enum, field name, schema key)는 영어.

## GBrain Configuration (configured by /setup-gbrain)
- Mode: CLI-only (local pglite)
- Engine: pglite
- Config file: ~/.gbrain/config.json (mode 0600)
- Setup date: 2026-07-30
- MCP registered: **no — 의도적 미등록 (Claude Code 기준).** PGLite는 단일 연결 DB라
  `serve`(MCP stdio)가 잠금을 쥐면 CLI 전 명령이 `Timed out waiting for PGLite lock`으로
  마비된다 (2026-07-30 실측). gstack 통합은 전부 CLI 경로라 CLI-only가 정본.
- **serve 스포너의 정체 = hermes gateway** (`hermes_cli gateway` 데몬이 gbrain serve를
  MCP 자식으로 상시 스폰 — 의도된 통합, brain에 hermes 페이지 존재). **시분할 운영이 정본**:
  검색이 잠금으로 막히면 `pkill -f 'gbrain.*serve'` 후 재시도 (hermes는 다음 사용 시
  lazy 재스폰하므로 무해). 선제 kill은 hermes 쓰기 중일 수 있으니 막혔을 때만.
- Artifacts sync: off
- Current repo policy: read-write (207 pages, embed 100%)

## GBrain Search Guidance (configured by /sync-gbrain)
<!-- gstack-gbrain-search-guidance:start -->

GBrain is set up on this machine (docs corpus). The agent should prefer gbrain
over Grep when the question is semantic or when you don't know the exact
identifier yet. Indexed corpus: **이 레포의 md 문서 전량** (architecture/specs/
guides/playtest-reports/content 등 208+ pages, embed 100%) via `gbrain import`.

Prefer gbrain when:
- "어느 문서에서 X를 다뤘지?" / semantic intent, no exact string yet:
    `gbrain search "<terms>"` (문서 검색이 핵심 용도)
- "What did we decide?" / past plans, learnings: `gbrain search "<terms>"`

**미가용**: `gbrain code-def`/`code-refs`/`code-callers` 등 코드 심볼 도구는
이 환경(pglite + v0.42.42)에서 `gbrain sources` 연결 실패로 동작하지 않는다
(2026-07-30 실측 — `connect timed out`). 코드 탐색은 Grep/Glob을 그대로 사용.

Grep is still right for known exact strings, regex, multiline patterns, and
file globs. **새 문서 추가 후 재색인은 정본 스크립트 `bash scripts/sync_gbrain_docs.sh`**
(증분 import → quartz stale 사본 제거 → 변경분 임베딩. 직접 `gbrain import`를 돌리면
quartz/ 옛 사본이 재유입되므로 스크립트 경유가 정본).

**⚠️ 한국어 질의 결함 (gbrain 0.42.42 실측)**: 순수 한국어 질의는 query 임베딩이
퇴화해 모든 질의가 동일 결과를 반환한다. **질의에 영문 키워드를 반드시 1개 이상
섞을 것** (예: `gbrain search "NPC self introduction 자기소개"`). 문서 쪽 임베딩은
한국어를 정상 처리하므로 영문 혼용 질의로 한국어 문서가 잘 검색된다.

<!-- gstack-gbrain-search-guidance:end -->
