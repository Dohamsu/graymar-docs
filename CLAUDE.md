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

## 서버 프로세스 관리 (필수)

**⚠️ 서버는 launchd 상주 서비스 `com.graymar.server`(KeepAlive)가 관리한다** —
`node dist/src/main.js`를 graymar/server cwd로 실행하며, kill해도 수 초 내 자동 리스폰된다.
`pnpm start:dev`를 병행하면 launchd 앱과 **포트 경쟁 + LLM 워커 이중 폴링**(신·구 코드가 턴을 번갈아 처리)이
발생한다 (2026-07-09 선택지 검증에서 실측). 관련: `com.graymar.cloudflared`(api.dimtale.com 터널).

### 서버 재시작 (정본 절차)
```bash
cd server && pnpm build && launchctl kickstart -k "gui/$(id -u)/com.graymar.server"
sleep 5 && curl -s http://localhost:3000/v1/version   # 해시·startedAt 확인
```

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

## Repository Overview

LLM-powered turn-based text RPG — **정치 음모 RPG**에서 이름 없는 용병이 왕국의 권력 투쟁을 거쳐 성장한다. 서버가 모든 게임 로직을 결정론적으로 처리하고, LLM은 내러티브 텍스트만 생성한다.

## Project Structure

```
├── server/              ← NestJS + Drizzle ORM + PostgreSQL 백엔드
├── client/              ← Next.js 16 + Zustand + Tailwind v4 프론트엔드
├── specs/               ← 원본 상세 설계 스펙 (17 md, 정본 참조)
├── architecture/        ← 통합 아키텍처 문서 (67 md + INDEX.md 색인, 실무 참조, archive 4 md)
├── guides/              ← 코드 구현 지침 (9 md, 서비스맵/컴포넌트맵/구현가이드/팩 에셋 프롬프트)
├── schema/              ← DB 스키마, JSON Schema, OpenAPI (3 files)
├── samples/             ← 샘플 페이로드 (JSON, 10 files)
├── content/             ← 게임 콘텐츠 시드 데이터 (graymar_v1 + silverdeen_v1 미니 팩 + star_sand_v1 별빛모래 + karnholt_v1 자율 서사 AUTONOMOUS 팩)
├── agents/              ← 에이전트 역할 정의서 (5 md)
├── scripts/             ← 플레이테스트 등 자동화 스크립트 (playtest.py, audit_quality.py 외)
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

### Server — 14 modules, 107 services, 12 controllers

| 모듈 | 서비스 수 | 역할 |
|------|----------|------|
| common/ | - | Guards, Filters, Pipes, Decorators |
| auth/ | 1 | JWT 인증 (register/login) |
| db/ | - | Drizzle ORM (23 tables / 21 schema files, 45 타입 파일) |
| content/ | 2 | 게임 콘텐츠 로더 — 멀티 팩(4팩) 캐시 + AsyncLocalStorage 스코프 + scenarios.controller (GET /v1/scenarios, creation-bundle) |
| engine/rng,stats,status | 3 | RNG, 스탯 계산, 상태효과 |
| engine/combat | 5 | Hit, Damage, EnemyAI, PropMatcher, CombatService |
| engine/input | 3 | RuleParser → Policy → ActionPlan |
| engine/nodes | 7 | 노드별 리졸버 + 전이 |
| engine/rewards | 5 | 보상, 인벤토리, 장비, 접미사, Legendary |
| engine/hub | 41 | HUB 엔진 6 서브시스템 (아래 참조) |
| engine/planner | 1 | RUN 구조 생성 (RunPlannerService) |
| runs/ | 2 | RUN 생성/조회 + BugReportService |
| turns/ | 1 | 턴 제출/조회 |
| llm/ | 23 | Worker, ContextBuilder, TokenBudget, Prompt, NpcDialogueMarker, NanoDirector, NanoEventDirector, NpcReactionDirector, ChallengeClassifier, ThemeClassifier, DialogueGenerator, LlmStreamBroker, StreamClassifier, FactExtractor, Lorebook, MemoryRenderer, PlotDirector, PlotSeedGenerator, LlmCallLog 외 |
| scene-image/ | 1 | AI 장면 이미지 (Gemini, rate limit) |
| portrait/ | 1 | 초상화 업로드/생성 (독립 모듈) |
| campaigns/ | 1 | 캠페인 구조 (독립 모듈) |
| endings/ | - | 여정 아카이브 조회 (GET /v1/endings, SummaryBuilder는 engine/hub 소속) |
| party/ | 8 | 파티 시스템 (Party, Chat, Stream, Lobby, PartyTurn, Vote, Reward, RunParticipants) |

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

### Client — 77 components, 5 stores

| 영역 | 수 | 핵심 |
|------|---|------|
| narrative/ | 7 | NarrativePanel, StoryBlock, StreamingBlock, DialogueBubble, NpcPortraitCard, SceneImageButton, narrative-text |
| input/ | 2 | InputSection, QuickActionButton |
| hub/ | 15 | HubScreen, SignalFeed, Incident, NPC, Notifications, CollapsibleSection, DiceFace, PackMeterGauge |
| location/ | 5 | TurnResultBanner, LocationToastLayer, LocationImage 외 |
| screens/ | 11 | StartScreen(+start-screen/ 하위 5), EndingScreen, RunEndScreen, NodeTransitionScreen 외 |
| side-panel/ | 7 | SidePanel, CharacterTab, InventoryTab, EquipmentTab, SetBonusDisplay, NpcDossierTab, QuestTab |
| ui/ | 12 | ErrorBanner, LlmFailureModal, BugReportButton, BugReportModal, NetworkStatus, PageTransition, SplashScreen, InstallPrompt, NewsModal, PortraitCropModal |
| layout/ | 2 | Header (자동 숨김), MobileBottomNav (햄버거 메뉴) |
| battle/ | 4 | BattlePanel 외 (창의 전투 버튼 폼 + 적 카드 + 펼침 + 아이템 모달) |
| party/ | 11 | PartyHUD, PartyLobby, PartyChatWindow, PartyChatInput, PartyTurnStatus, VoteModal, LootDistribution 외 |
| brand/ | 1 | 브랜드 로고/타이포 |

Stores: game-store, game-selectors, settings-store, auth-store, party-store.

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
| LLM | Gemma 4 26B MoE (메인, stream:true) / GPT-4.1 Mini (fallback) / GPT-4.1-nano (경량) | Multi-provider via OpenRouter |

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
2. **LLM is narrative-only** — LLM 출력은 게임 결과에 영향 없음. 실패해도 게임 진행.
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
17. **Token Budget 2단** — 메모리 블록 2500(블록별 배분·저우선 트리밍) + 프롬프트 총량 백스톱 `GRAND_TOTAL_CHAR_BUDGET` 16,000자(≈9.7k tok — 11k부터 soft 지시 절벽 실측, arch/79). 백스톱은 스냅샷성 블록만 제거, 기억·L0 절대 보호.
18. **Procedural Plot Protection** — 동적 이벤트에서 arcRouteTag/commitmentDelta 절대 금지.
19. **NATURAL 엔딩 최소 15턴** — ALL_RESOLVED 엔딩은 totalTurns ≥ 15 이상이어야 발동.
20. **RUN_ENDED 시 메모리 통합** — go_hub/MOVE_LOCATION 없이 런 종료 시에도 finalizeVisit() 호출.
21. **MOVE_LOCATION fallback** — 목표 장소 불명확 시 HUB 복귀 처리 (이동 의도 무시 방지). KW MOVE_LOCATION은 장소명+이동접미사 복합감지 시에만 LLM보다 우선. 단순 키워드 1-hit은 LLM 신뢰.
22. **Living World 초기화** — createRun 시 locationDynamicStates(팩의 locations 전체), worldFacts(빈 배열), npcLocations, playerGoals 초기화 필수.
23. **NPC 3계층** — CORE 우선 상황 생성, BACKGROUND 배경만, SUB 일반 (수치는 팩별 — graymar 6/25/12, silverdeen 2/6/4).
24. **선별 주입(Selective Injection)** — LLM 컨텍스트에 메모리를 주입할 때, 전체가 아닌 현재 턴에 관련된 것만 선별: NpcPersonalMemory는 등장 NPC만, LocationMemory는 현재 장소만, IncidentMemory는 관련 사건만, ItemMemory는 장착/획득(RARE 이상) 아이템만.
25. **프리셋 배경 참조** — 프리셋별 npcPostureOverrides(NPC 초기 태도 오버라이드), actionBonuses(행동 보너스), LLM 배경 텍스트가 게임 메카닉과 서술 모두에 반영.
26. **대화 잠금(Conversation Lock)** — 대화 계열 행동(TALK/PERSUADE/BRIBE/THREATEN/HELP) 시 같은 이벤트/NPC 최대 4턴 연속 유지. 비대화 행동(SNEAK/STEAL/FIGHT) 시 NPC 연속성 해제. 작별 인사(dialogueAct=FAREWELL) 턴 이후에도 잠금 해제 — 닫힌 대화는 잇지 않는다.
27. **NPC knownFacts 점진 공개 + 기록·서술 단일화** — SUCCESS/PARTIAL 판정 + 정보행동 시 NPC 보유 fact 중 **입력 주제 매칭 우선**(없으면 순서) 공개. 발견 fact는 `ui.questReveal`로 LLM 서술에 동일 주입되어 기록 fact = 서술 fact 보장 (architecture/58). 이벤트 discoverableFact는 SUCCESS=100%, PARTIAL=50%. FAIL은 미공개.
28. **퀘스트 자동 전환** — discoveredQuestFacts 누적 → quest.json stateTransitions 조건 충족 시 questState 자동 전환 (S0→S1→...→S5).
29. **questFactTrigger SitGen 바이패스** — 미발견 fact 이벤트가 있는 장소에서 매 턴 이벤트 매칭 허용. 이때 SituationGenerator를 건너뛰고 EventDirector로 직행하여 fact 이벤트 매칭을 보장.
30. **밸런스 상수 외부화** — SitGen 확률, PARTIAL 발견률, weight 부스트 등 핵심 밸런스 상수는 `quest-balance.config.ts`에서 관리. 코드 내 하드코딩 금지.
31. **보너스 스탯 합계 = 6** — 캐릭터 생성 시 bonusStats 각 값 0~6, 합계 정확히 6. 서버에서 검증.
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
44. **사교 발화 fact 게이트** — 순수 사교 발화(dialogueAct: GREETING/WELLBEING/THANKS/FAREWELL, `common/dialogue-act.ts`) 턴은 NPC fact 공개 경로·인계/보류 힌트를 타지 않는다 (잡담 모드로 전환). 질문 턴은 비주제 fallback fact 공개 금지 — 물은 것과 무관한 단서로 답하지 않는다. BRIBE/THREATEN은 면제. **대화 계열(TALK/PERSUADE/TRADE/HELP)은 주제 매칭 시에만 fact 공개** — 잡담·인사에 NPC가 먼저 단서를 흘리지 않는다(선제 단서 억제, arch/68 부록 M). 조사·탐색(INVESTIGATE/SEARCH/OBSERVE)은 확률 fallback 유지.
45. **엔진 코드 콘텐츠 ID 리터럴 금지** — 시나리오 팩(콘텐츠)의 NPC/장소/이벤트 ID·표시명·스크립트는 엔진 서비스 코드에 리터럴로 둘 수 없다. 콘텐츠 JSON 필드 + ContentLoader 파생 API로만 접근 (fallback은 content-loader 단일 지점, 접두사 규약 `NPC_`/`LOC_`/`EVT_`·enum 리터럴은 예외). 팩 계약: questState는 S0_ARRIVE~S5_RESOLVE 명명, incidents `resolutionConditions`·events `payload.tags` 필수 — architecture/63.
46. **경제 루프 — 퀘스트 사례금 + 정보 구매** — fact 발견/questState 전환 시 quest.json `rewards`(factGold/transitionGold) 사례금 지급(`[사례금]` GOLD 이벤트, 총량은 콘텐츠로 유한 → 파밍 불가). NPC가 미공개 fact를 보류/거부한 턴은 `nanoEventCtx.bribeOpportunity`로 nano 선택지에 BRIBE 1개 노출. BRIBE 기본 비용은 `quest-balance.config.ts`(-6/-3) — fact 사례금(5G)보다 싸지 않게 유지 — architecture/65.
47. **디렉터 비트 = 의도 정합 시에만 채택 (불변식 D)** — 자율 서사(AUTONOMOUS) 디렉터의 선계산 비트는 **플레이어 의도와 정합할 때만** 채택한다. 인력(gravity)은 유인이지 강제가 아니다 — 서사 강제 진행 금지. 구체: 강제창(`BEAT_FORCE_AFTER_TURNS`, turns.service `determineTurnModeCore` 규칙 1.5-C)은 **대화 잠금 활성 턴·사교 발화(GREETING/WELLBEING/THANKS/FAREWELL)·REST 의도 턴에는 발동하지 않는다**. **상호작용 단위 확장(버그 d20c1de8, 2026-07-17)**: 직전 턴과 동일 NPC 연속 상호작용(contextNpcId — 사교든 폭력이든) 중이면 그 NPC를 포함하지 않는 비트는 승격(1.5·3.6)·채택(requiredNpcId 하드 게이트) 모두 금지 — 채택 비트가 화자를 가로채 구타 대상이 스왑되던 실측 차단. "대화·휴식하려는데 사건 끼워넣기" 패턴이 조사 최다 이탈 요인("의도 무시 강제 진행")이므로 원천 차단. 정합률은 P8 계측(의도 정합 채택률)으로 감시 — architecture/76 D1.
48. **콘텐츠 캐시 객체 변조 금지 — 이벤트는 사용 전 딥카피** — EventMatcher/`getEventById`는 ContentLoader 팩 캐시 객체를 참조로 반환하므로, 턴 파이프라인의 제자리 변조(primaryNpcId 동기화 등)가 캐시 원본에 영구 반영되어 **이후 모든 런의 이벤트 정의를 오염**시킨다 (2026-07-17 실측: coercer 런의 NPC 지목이 EVT_GUARD_INT_1 정의를 변조 → chatty 런에서 EventChoiceGate·Step 0b 동시 무력화, 브렌↔펠릭스 분열 4연속). 모든 이벤트 경로 수렴점(turns.service `const event = structuredClone(matchedEvent!)`)에서 딥카피하고, EventChoiceGate 기준은 클론 직후 캡처한 콘텐츠 원본 NPC(`eventContentPrimaryNpc`)를 쓴다. 새 콘텐츠 참조 소비처를 추가할 때 변조 가능성이 있으면 같은 원칙 적용. 어체 사후 교정도 화자 단위로만(R5v2 — 구 R5의 primary 일괄 치환은 타 화자 대사 파괴 실측).
49. **timePhase = phaseV2 파생 미러 (단일 시간 정본)** — 시간의 단일 정본은 phaseV2(globalClock 12tick=1일)이며, v1 `timePhase`(DAY/NIGHT)는 `deriveTimePhaseFromV2(phaseV2)`로만 파생한다. 과거 `advanceTime`가 timeCounter 5턴마다 timePhase를 독립 토글해 phaseV2와 충돌(전투 경로 timePhase=NIGHT vs phaseV2=DAY 실측)했던 이중 시간계를 폐지. timePhase를 독립적으로 변경하는 코드 추가 금지. 시간 진행은 WorldTick.preStepTick(globalClock/phaseV2)만 소유 — architecture/81.
50. **저모델 반복 억제 = 구체 어휘 주입 금지** — 메인 서술 LLM(저모델)은 프롬프트에 넣은 구체 어구·제스처 풀을 positive/negative 무관하게 복제/변형 반복한다(불변식 41/42 연장). 반복 억제는 정적 풀 노출이 아니라 ① 앵커 제거 ② 모델 레버(frequency_penalty 0.4/presence_penalty 0.3 — 메인 서술만, nano/추출 제외) ③ 추적 차원 축소(무한 문구→유한 상위 차원)로 한다. 하드 whitelist는 whack-a-mole — architecture/82, memory feedback_concrete_vocab_anchor.

## 과금 원칙 (설계 — 미과금 프로토타입, 미래 결정 봉인)

시장 조사 결론("정상 작동에는 과금하지 않는다")에 따라, 향후 과금 도입 시 아래 3원칙을 불변으로 유지한다 (지금은 코드 변경 없음, 결정만 선봉인) — architecture/76 D5.

1. **정상 작동은 무료** — 기억·일관성·판정·진행은 과금 등급과 무관하게 동일. 서버 정본(불변식 1)이 만드는 핵심 가치를 프리미엄화하지 않는다.
2. **과금은 부가가치만** — 이미지·문체 프리셋·추가 캠페인/팩 등 선택적 확장에만.
3. **실패 턴 무과금** — LLM 오류·빈 응답·재생성에 비용 차감 금지 (`retry-llm` 무료 유지). 생성 실패에도 과금하는 것은 조사 최악 평가 축.

## Canonical Enums (정본)

모든 서버 enum의 정본 위치: `server/src/db/types/enums.ts`

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
| IntentActionType | `enums.ts` | INVESTIGATE, PERSUADE, SNEAK, BRIBE, THREATEN, HELP, STEAL, FIGHT, OBSERVE, TRADE, TALK, SEARCH, MOVE_LOCATION, REST, SHOP |
| HubSafety | `enums.ts` | SAFE, ALERT, DANGER |
| TimePhase | `enums.ts` | DAY, NIGHT |
| TimePhaseV2 | `world-state.ts` | DAWN, DAY, DUSK, NIGHT |
| MatchPolicy | `enums.ts` | SUPPORT, BLOCK, NEUTRAL |
| Affordance | `enums.ts` | INVESTIGATE, PERSUADE, SNEAK, BRIBE, THREATEN, HELP, STEAL, FIGHT, OBSERVE, TRADE, ANY |
| EventTypeV2 | `enums.ts` | RUMOR, FACTION, ARC_HINT, SHOP, CHECKPOINT, AMBUSH, ENCOUNTER, OPPORTUNITY, FALLBACK |
| ArcRoute | `enums.ts` | EXPOSE_CORRUPTION, PROFIT_FROM_CHAOS, ALLY_GUARD |
| NpcPosture | `enums.ts` | FRIENDLY, CAUTIOUS, HOSTILE, FEARFUL, CALCULATING |
| IncidentKind | `incident.ts` | CRIMINAL, POLITICAL, SOCIAL, ECONOMIC, MILITARY |
| IncidentOutcome | `incident.ts` | CONTAINED, ESCALATED, EXPIRED |
| SignalChannel | `signal-feed.ts` | RUMOR, SECURITY, NPC_BEHAVIOR, ECONOMY, VISUAL |
| NarrativeMarkType | `narrative-mark.ts` | BETRAYER, SAVIOR, KINGMAKER, SHADOW_HAND, MARTYR, PROFITEER, PEACEMAKER, WITNESS, ACCOMPLICE, AVENGER, COWARD, MERCIFUL |
| StepStatus | `operation-session.ts` | PENDING, IN_PROGRESS, COMPLETED, SKIPPED |
| Status ID | [[specs/status_effect_system_v1|status effect system v1]] §10 | BLEED, POISON, STUN, WEAKEN, FORTIFY |
| ResolveOutcome | `resolve-result.ts` | SUCCESS, PARTIAL, FAIL |
| Client Phase | `game-store.ts` | TITLE, LOADING, HUB, LOCATION, COMBAT, NODE_TRANSITION, RUN_ENDED, ERROR |
| StoryMessageType | `game.ts` | SYSTEM, NARRATOR, PLAYER, CHOICE, RESOLVE |
| CharacterPreset | `presets.json` | DOCKWORKER, DESERTER, SMUGGLER, HERBALIST, FALLEN_NOBLE, GLADIATOR |
| CharacterTrait | `traits.json` | BATTLE_MEMORY, STREET_SENSE, SILVER_TONGUE, GAMBLER_LUCK, BLOOD_OATH, NIGHT_CHILD |
| NpcTier | `content.types.ts` | CORE, SUB, BACKGROUND |
| FactCategory | `world-fact.ts` | PLAYER_ACTION, NPC_ACTION, WORLD_CHANGE, DISCOVERY, RELATIONSHIP |
| SituationTrigger | `situation-generator.service.ts` | LANDMARK, INCIDENT_DRIVEN, NPC_ACTIVITY, NPC_CONFLICT, ENVIRONMENTAL, CONSEQUENCE, DISCOVERY, OPPORTUNITY, ROUTINE |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/auth/register` | 회원가입 (email, password, nickname) |
| POST | `/v1/auth/login` | 로그인 (email, password) → JWT |
| POST | `/v1/runs` | 새 RUN 생성 (presetId, gender) |
| GET | `/v1/runs` | 활성 RUN 조회 (userId 기반) |
| GET | `/v1/runs/:runId` | RUN 상태 조회 (turnsLimit 옵션) |
| POST | `/v1/runs/:runId/turns` | 턴 제출 (ACTION/CHOICE, idempotencyKey 필수) |
| GET | `/v1/runs/:runId/turns/:turnNo` | 턴 상세 (LLM 폴링용, includeDebug 옵션) |
| POST | `/v1/runs/:runId/turns/:turnNo/retry-llm` | LLM 재시도 (FAILED → PENDING 리셋) |
| GET | `/v1/settings/llm` | LLM 설정 조회 (API 키 마스킹) |
| PATCH | `/v1/settings/llm` | LLM 설정 변경 (런타임) |
| POST | `/v1/bug-reports` | 버그 리포트 생성 (runId, turnNo, category, description) |
| GET | `/v1/bug-reports` | 버그 리포트 목록 조회 (페이징) |
| GET | `/v1/bug-reports/:id` | 버그 리포트 상세 조회 |
| PATCH | `/v1/bug-reports/:id` | 버그 리포트 상태 변경 (resolved 등) |
| POST | `/v1/portrait/generate` | AI 초상화 생성 (presetId, gender, appearanceDescription) |
| GET | `/v1/version` | 서버 버전 조회 (git hash, startedAt, uptime) |
| POST | `/v1/parties` | 파티 생성 (name) |
| GET | `/v1/parties/my` | 내 파티 조회 |
| GET | `/v1/parties/search` | 파티 검색 (?q=) |
| POST | `/v1/parties/join` | 초대코드로 가입 (inviteCode) |
| POST | `/v1/parties/:partyId/leave` | 파티 탈퇴 |
| POST | `/v1/parties/:partyId/kick` | 멤버 추방 (userId) |
| DELETE | `/v1/parties/:partyId` | 파티 해산 |
| POST | `/v1/parties/:partyId/messages` | 채팅 전송 (content) |
| GET | `/v1/parties/:partyId/messages` | 채팅 히스토리 (cursor, limit) |
| GET | `/v1/parties/:partyId/stream` | SSE 실시간 스트림 (?token=JWT) |
| GET | `/v1/parties/:partyId/lobby` | 로비 상태 조회 |
| POST | `/v1/parties/:partyId/lobby/ready` | 준비 완료 토글 (ready) |
| POST | `/v1/parties/:partyId/lobby/start` | 던전 시작 (리더 전용) |
| POST | `/v1/parties/:partyId/runs/:runId/turns` | 파티 행동 제출 (inputType, rawInput, idempotencyKey) |
| POST | `/v1/parties/:partyId/votes` | 이동 투표 제안 (targetLocationId) |
| POST | `/v1/parties/:partyId/votes/:voteId/cast` | 투표 참여 (choice: yes/no) |
| POST | `/v1/parties/:partyId/lobby/invite-run` | 내 세계에 초대 — 리더 솔로 런에 합류 (Phase 3) |
| GET | `/v1/parties/:partyId/runs/:runId/turns/:turnNo` | 파티 턴 상세 조회 (partyActions + serverResult + llm) |
| POST | `/v1/parties/:partyId/runs/:runId/leave` | 던전 이탈 (보상 정산 + AI 전환) |

## Environment Variables (`server/.env`)

```
DATABASE_URL=postgresql://user:password@localhost:5432/textRpg
LLM_PROVIDER=openai          # openai | claude | gemini | mock
OPENAI_API_KEY=sk-...
OPENAI_MODEL=google/gemma-4-26b-a4b-it   # OpenRouter 메인 모델 (Gemma 4 26B MoE)
LLM_ALTERNATE_MODEL=google/gemma-4-26b-a4b-it  # 교차 모델 (동일 모델 사용)
OPENAI_BASE_URL=https://openrouter.ai/api/v1  # optional, OpenAI-compatible endpoint
CLAUDE_API_KEY=               # optional
GEMINI_API_KEY=               # optional
LLM_MAX_RETRIES=2
LLM_TIMEOUT_MS=8000
LLM_MAX_TOKENS=1024
LLM_TEMPERATURE=0.8
LLM_LIGHT_MODEL=gpt-4.1-nano          # nano/경량 계열 (arch/67 — 명시 고정)
LLM_LIGHT_TIMEOUT_MS=5000             # nano 요청 단위 타임아웃 (전역 60s 대체)
LLM_DIALOGUE_MODEL=google/gemma-4-26b-a4b-it  # 대사 생성(Stage B+자기소개) — 하오체 준수용 Flash급+
LLM_FIRST_TOKEN_TIMEOUT_MS=5000       # 스트리밍 첫 토큰 타임아웃 — 초과 시 non-stream fallback (arch/62, 0=off)
LLM_PROVIDER_SORT=throughput          # OpenRouter 라우팅 정렬 — 생성 tok/s 우선 (arch/62)
LLM_PROVIDER_IGNORE=cloudflare,dekallm  # OpenRouter 배제 provider (저 uptime — arch/62 부록)
LLM_FALLBACK_PROVIDER=openai          # fallback: 같은 OpenRouter 경유
LLM_FALLBACK_MODEL=openai/gpt-4.1-mini  # fallback 모델 (이전: Claude Haiku 4.5)
GEMINI_REASONING_MAX_TOKENS=0         # Gemini Flash thinking 비활성화 (0=off)
LLM_JSON_MODE=false               # JSON 구조화 출력 (스트리밍과 비호환, false 권장)
```

## Implementation Phase Status (구현 단계)

| Phase | 범위 | 상태 |
|-------|------|------|
| **Phase 1** | HUB 순환 탐험 + LOCATION 판정 + 전투 + LLM 내러티브 + 프리셋/인증 | ✅ 완료 |
| **Phase 2** | NPC 소개 + 5축 감정 | ✅ 완료 |
| **Phase 2** | DAG 노드 라우팅 | ✅ 완료 — 24노드 DAG 그래프 + 3루트 분기 |
| **Phase 3** | Turn Orchestration (NPC 주입, pressure) | ✅ 완료 |
| **Narrative v1** | Incident + 4상시간 + Signal + NpcEmotional + Mark + Ending + Operation | ✅ 완료 |
| **Memory v2** | StructuredMemory + [MEMORY]/[THREAD] 태그 + Scene Continuity | ✅ 완료 |
| **Narrative v2** | Token Budget + Mid Summary + Intent Memory + Active Clues | ✅ 완료 |
| **Event v2** | Event Director + Event Library(123개) + Procedural Event | ✅ 완료 |
| **Bridge** | IntentV3 + IncidentRouter + WorldDelta + PlayerThread + Notification | ✅ 완료 |
| **Client** | Notification UI + 엔딩 행동 성향 | ✅ 완료 |
| **Fixplan3** | P1 메모리통합 + P2 NPC소개 + P4 이동 + P5 씬연속 + P7 엔딩가드 + P10 조사 | ✅ 완료 |
| **Living World v2** | LocationState + WorldFact + NpcSchedule + SituationGenerator + ConsequenceProcessor + PlayerGoal | ✅ 완료 |
| **Phase 4** | 장비 v2 (세트/리전) + 리전 경제 | ✅ 완료 — 장비 드랍/착용, 동적 경제, 세트효과, Legendary |
| **Memory v3** | NpcPersonalMemory + LocationMemory + IncidentMemory + ItemMemory (선별 LLM 주입) | ✅ 완료 |
| **Preset v2** | 프리셋 배경 시스템 (npcPostureOverrides, actionBonuses, LLM 배경 참조) | ✅ 완료 |
| **Bug Report** | 인게임 버그 리포트 시스템 (bug_reports 테이블, API 4개) | ✅ 완료 |
| **Assets** | 캐릭터 초상화 8장 + 장소 이미지 24장 (Gemini 생성) | ✅ 완료 |
| **Mobile UX** | 헤더 자동 숨김 + 하단 네비 햄버거 + 대화창 최대화 + OG 메타데이터 | ✅ 완료 |
| **LLM Multi-Provider** | Claude provider 구현 (@anthropic-ai/sdk) + cacheCreationTokens 추적 | ✅ 완료 |
| **프롬프트 최적화** | 시스템 프롬프트 압축 21% + HUB 턴 경량화 37% + posture baseline 재설계 | ✅ 완료 |
| **NPC 대화 개선** | 대화 잠금 4턴 + 턴카운터 + 행동반응매핑 + 직전대사추출 + speechStyle 예시 제거 | ✅ 완료 |
| **NPC 콘텐츠 강화** | 43명 gender + role 다채화 + 18명 knownFacts/linkedIncidents | ✅ 완료 |
| **퀘스트 시스템** | QuestProgressionService + 6단계 전환 + 3 Arc 루트 + FACT 점진 공개 | ✅ 완료 |
| **프론트엔드 디자인 점검** | error boundary + PWA + 색상 토큰 통일 + HUB 접기/펼치기 + 핀치줌 차단 | ✅ 완료 |
| **NPC 초상화** | CORE 6명 초상화 생성 + 첫 등장 시 표시 시스템 | ✅ 완료 |
| **프롬프트 최적화 v2** | NPC 감정 블록 선별 주입 + 장소 블록 보완 + dry-run 프롬프트 추출 | ✅ 완료 |
| **라우트 재구성** | / → 랜딩(SEO), /play → 게임(SPA), api.dimtale.com 고정 터널 | ✅ 완료 |
| **퀘스트 밸런싱** | Fact 이벤트 11개 추가 + NPC ID 정규화 + P0~P5 매칭 개선 (SitGen 바이패스, weight 부스트, PARTIAL 50%, 밸런스 config 외부화, FREE 힌트) | ✅ 완료 |
| **캐릭터 생성** | 프리셋 6종(+몰락귀족/검투사) + 특성 6종 + 이름 입력 + AI 초상화 생성 + 보너스 스탯 +6 배분 + 6단계 UI + 특성 런타임 효과 | ✅ 완료 |
| **Intent Parser 강화** | MOVE_LOCATION KW_OVERRIDE 오탐 방지 + LLM 판정 신뢰 강화 (장소명 복합감지) | ✅ 완료 |
| **타이틀 UX 개선** | 로딩 애니메이션 (dotPulse) + 버튼 stagger fade-in + ads.txt | ✅ 완료 |
| **아이템 이미지 수정** | items/ 26개 중 10개 초상화 오류 → Gemini 2.5 Flash로 아이콘 재생성 | ✅ 완료 |
| **LLM Gemma 4 전환** | gpt-4.1-mini → Gemma 4 26B MoE (OpenRouter), openai provider baseURL 지원, 이미지 생성 비활성화 (과금 방지) | ✅ 완료 |
| **서술 품질 개선** | unknownAlias 매칭 강화 + encounterCount 4단계 NPC 관계 깊이 + PRESET_MANNERISMS 6종 + NPC 팩트 반복 버그 수정 | ✅ 완료 |
| **speakingNpc 버그 수정** | PROC_/SIT_ 이벤트 injectedNpc 분리 + 무명 인물 실루엣 아이콘 | ✅ 완료 |
| **린트 0/0** | 서버 unused-vars 62건 + unsafe 404건 수정, 클라이언트 린트 0/0, TS2871 빌드 에러 수정 | ✅ 완료 |
| **NPC 초상화 확장** | CORE + SUB NPC 초상화 12개 클라이언트 배치 | ✅ 완료 |
| **파티 Phase 1** | 파티 CRUD + 초대코드 + 실시간 채팅(SSE) + 로비 UI + PartyHUD | ✅ 완료 |
| **파티 Phase 2** | 파티 던전: 로비 준비→시작→4인 동시 턴→통합 판정→LLM 3인칭 서술→이동 투표→보상 분배→던전 종료 | ✅ 완료 |
| **파티 Phase 2 보강** | 이탈자 자동행동 + 재접속 AI해제 + HUB 투표이동 + 솔로동기화 + 개별HP + 턴상세API + 주사위 애니메이션 + 카운트다운 UI + party:error SSE + 멀티탭 방어 | ✅ 완료 |
| **파티 Phase 3** | 런 통합(내 세계에 초대) + run_participants 테이블 + 던전 중간 합류/이탈 + 보상 정산 | ✅ 완료 |
| **NPC 대사 마커 v2** | 하이브리드 @마커 시스템 (서버 regex 6단계 + nano 개별 판단), 정확도 30%→100%, 프롬프트 따옴표 규칙, 홑따옴표 강조 UI | ✅ 완료 |
| **서술 파이프라인 v2** | 3-Stage Pipeline (NanoDirector→Gemma4→NanoProcessor), 서술 다양성 개선, @마커 규칙 Gemma4에서 분리 | ✅ 완료 |
| **NPC 주도 행동** | trust 기반 dialogueSeed 5단계 + 비대화 행동 NPC 끼어들기 + 대화 잠금 LLM 전달 | ✅ 완료 |
| **OpenRouter 최적화** | provider sort:latency 적용 (평균 33초→7초) | ✅ 완료 |
| **클라이언트 UX 개선** | 세그먼트 기반 타이핑 + 페이지 전환 7종 + 장소 이미지 켄 번스 + NPC 카드 연출 + 시간대 알림 + 판정 순차 공식 + 네트워크 상태 | ✅ 완료 |
| **LLM Gemini Flash Lite 전환** | Gemma4 → Gemini 2.5 Flash Lite (속도 2.7배, 비용 17% 절감), Claude Haiku fallback | ✅ 완료 |
| **대사 오인 방지** | rawInput 유사도 필터 + 인용 조사 필터 + 불완전 마커 자동 정리 + role 매칭 강화 | ✅ 완료 |
| **LLM 모델 평가 v2** | 9개 모델 비교 평가 (Qwen3 235B 1위), Fallback GPT-4.1 Mini 전환, cost_usd DB 추적 | ✅ 완료 |
| **서술 파이프라인 v3** | 반복 패턴 해결(2중주입 제거), 판정 리마인더, 메타 서술 금지, 태그 누출 방어 | ✅ 완료 |
| **NPC 마커 nano 전환** | 발화자 판단 주 파이프라인: regex→nano LLM, regex는 fallback 격하. 호칭 강화 프롬프트 | ✅ 완료 |
| **서술 파이프라인 v4** | sessionTurns THREAD 하이브리드 + 톤 가이드 동적화 + 감각 순환 폐기 + 모델 교차(Next80B/FlashLite) | ✅ 완료 |
| **마커 안정화** | distance 60→100 + 대사 최소 8자 + 위치 검증 + 클라이언트 재배치 방어 + NPC 목록 확장 + 호칭 정확 매칭 | ✅ 완료 |
| **E2E 테스트** | Playwright 기반 자동 테스트: 회원가입→캐릭터생성→게임진입→20턴 플레이→렌더링 검증 | ✅ 완료 |
| **과금 모델 추가** | Qwen3/Llama4/Flash Lite 가격표 + PWA 캐시 초기화 버튼 + 플레이어 대사 방어 | ✅ 완료 |
| **NanoEventDirector** | nano LLM 기반 동적 이벤트 엔진: 매 턴 이벤트 컨셉/NPC/fact/선택지 생성, NPC 선택 행동별 전환 규칙, sourceNpcId 연속성, 기존 EventDirector fallback | ✅ 완료 |
| **연쇄 반응 시스템** | Layer 2: 치안/불안 임계값 → LOCKDOWN/RIOT 조건 자동 발동, 판정 보정(blockedActions -2), 시그널 피드 알림 | ✅ 완료 |
| **IntentParser 강화 v2** | 고위험 키워드(FIGHT/STEAL/THREATEN/BRIBE) LLM보다 KW 우선, targetNpcId KW 우선 (플레이어 NPC 지목) | ✅ 완료 |
| **NPC 능동 반응** | Layer 3: WITNESSED NPC trust 기반 경고/회피/밀고(Heat+5)/적대(Heat+8), LLM [NPC 반응] 블록 주입 | ✅ 완료 |
| **동시접속 최적화** | LLM Worker 5턴 병렬(Promise.allSettled) + DB 풀 max30 + 폴링 1초 + DB 쿼리 병렬 + 레이트 리미터 + Throttle 완화 + PM2 클러스터 설정 → 10명 동시접속 10/10 성공 | ✅ 완료 |
| **Quest→Ending** | S5+5턴 auto-ending (Incident resolved=CONTAINED), factToIncident 매핑, questEndingApproach LLM 톤 주입 | ✅ 완료 |
| **NPC 마커 오귀속 방지** | 매칭 실패 시 마커 미삽입, nano 결과 후보 별칭 검증, 하오체 보조 감지 | ✅ 완료 |
| **초상화 크롭** | react-easy-crop 카카오톡 스타일 드래그+줌, 4:5 비율 고정 | ✅ 완료 |
| **NPC 태도 변화 알림** | posture 전환 시 골드색 이벤트 표시, POSTURE_CHANGE 태그 | ✅ 완료 |
| **그레이마르 호외** | 양피지 모달 + nano 기사 변환 (장소/시간/사건 컨텍스트), 세계 변화 시그널 확장 (퀘스트/장소/NPC 아젠다) | ✅ 완료 |
| **NPC 아젠다 목격** | 같은 장소에서 NPC 행동을 [목격 장면] LLM 프롬프트로 자연 삽입 | ✅ 완료 |
| **메타 서술 방어** | 턴 번호/플레이어 3인칭/행동 복붙/활성 단서 후처리 제거, 프롬프트 행동 지시 개선 | ✅ 완료 |
| **NPC 소개 카드 정합성** | LLM 서술 기반 npcPortrait 갱신, 서술에 없는 NPC 카드 제거, 소개 턴 초상화 표시 | ✅ 완료 |
| **품질 검증 V7~V9** | V7 프롬프트 누출 9패턴, V8 NPC 정합성(카드↔마커↔화자), V9 서술 품질(반복/하오체) | ✅ 완료 |
| **UI 개선** | 타이핑 전 서식 정제, 행동 입력 시 선택지 즉시 제거, 페이지 전환 페이드 통일, 고립 @마커 제거 | ✅ 완료 |
| **@마커 오류율 개선** | 3전략: 프롬프트 강화(호칭 패턴/교차 대화/금지 규칙) + 서브 LLM 2차 검증(미할당 대사 GPT-4.1-mini 재판단) + JSON 구조화 출력 모드(LLM_JSON_MODE) | ✅ 완료 |
| **Memory v4** | nano 구조화 추출(entity_facts UPSERT) + 직전 턴 원문→nano 요약 전환 + nano 요약 주입 (반복률 71% 감소) | ✅ 완료 |
| **별칭 반복 해소** | shortAlias 18명 추가 + 서버 후처리(deduplicateAliases) + NPC lookup에 shortAlias/name includes 매칭 | ✅ 완료 |
| **행동별 프리셋 묘사** | PRESET_MANNERISMS 6종 × 4~5행동 = 26개 세부 묘사, actionType 기반 동적 주입 | ✅ 완료 |
| **LLM Flash 전환** | Gemini Flash Lite → Flash (영어 누출/메타 서술 해소, 비용 +81%, 속도 +17%) | ✅ 완료 |
| **대사 분리 파이프라인** | 2-Stage LLM (서술+대사 분리), DialogueGeneratorService, dialogue_slot JSON, 서버 마커 자동 삽입, 하오체 검증+재시도 | ✅ 완료 |
| **로어북 시스템** | 키워드 트리거 기반 세계 지식 동적 주입 (NPC knownFacts 34개 + 장소 비밀 13개 + 사건 단서 19개 + entity_facts 키워드 검색) | ✅ 완료 |
| **다중 어체 시스템** | NPC별 speechRegister 5종 (HAOCHE/HAEYO/BANMAL/HAPSYO/HAECHE), 어체별 검증+fallback, 43명 배정 | ✅ 완료 |
| **NPC_ID 정확도 강화** | NPC 목록 [ID:NPC_XXX] 병기, resolveNpcId 퍼지매칭(레벤슈타인 거리 2), 서술 본문 한글 fallback, name 2글자 가드 | ✅ 완료 |
| **테스트 검증 강화** | V9-a sanitize 오탐, V9-b CHOICE 대화 맥락, V9-c fallback 감지, --choice-rate/--model 옵션 | ✅ 완료 |
| **Player-First 이벤트 엔진** | TurnMode 3분류(PLAYER_DIRECTED/CONVERSATION_CONT/WORLD_EVENT) + NPC 우선순위 변경 + 맥락 NPC 연결 + EventMatcher targetNpcId 가중치 | ✅ 완료 |
| **NanoEventDirector 비동기 분리** | turns.service → llm-worker로 이동, nanoCtx만 빌드 후 LLM Worker에서 generate() 호출, 턴 응답 300~1000ms 절감 | ✅ 완료 |
| **NPC 불일치 후처리** | Step E(대사 내 NPC이름: 프리픽스 제거) + Step F(primaryNpcId와 LLM NPC 불일치 강제 교정) | ✅ 완료 |
| **LLM 스트리밍** | OpenRouter stream:true + LlmStreamBroker(SSE) + StreamParser(문장 단위 버퍼링) + 2-Phase 렌더링 | ✅ 완료 |
| **이미지 WebP 최적화** | 81개 이미지 PNG→WebP 변환 (114MB→1.9MB, 98% 절감) + npc-portraits rewrites 제거 + imageSizes 커스텀 | ✅ 완료 |
| **프롤로그 합쇼체 전환** | 로넨 대사 HAPSYO 전환 + 6종 프리셋 prologueHook 합쇼체 | ✅ 완료 |
| **단위 테스트 강화** | Player-First 엔진 101개 테스트 (determineTurnMode 35개 + extractTargetNpc 16개 + NanoEventDirector 25개 + 후처리 20개 + EventMatcher 5개) | ✅ 완료 |
| **스트리밍 렌더 안정화** | StreamTyper once-guard + onComplete 멱등성(텍스트 사라짐 방지) + 타이핑 중/후 DOM/폰트 래퍼 통일(스타일 점프 제거) + analyzeText 문단 재조합(문장별 \n 제거) + 대사 내부 raw 마커 후처리 | ✅ 완료 |
| **버그 리포트 수집 확장** | bug_reports에 client_snapshot/network_log/client_version 컬럼 추가 + 메시지 상세 직렬화 + DOM 요약 + 자동 네트워크 타임라인 로거(request 래퍼) | ✅ 완료 |
| **엔딩 연출 개선** | Part B MIN_TURNS 가드 + commitTurnRecord 순서 수정 + arcRoute 분기 에필로그(12분기) + personalClosing + ui.endingResult 누락 수정 + SignalFeed soft deadline + DeadlineBanner 상단(D-3/2/1/0/초과) + LLM deadlineContext 조건부 주입 | ✅ 완료 |
| **여정 아카이브 Phase 1** | run_sessions.ending_summary jsonb + SummaryBuilderService(synopsis/keyEvents/keyNpcs/finale 템플릿) + EndingsController(GET /v1/endings, /:runId) + lazy fallback + EndingsListScreen + JourneySummaryScreen 양피지 스타일 + StartScreen "여정 기록" 버튼 | ✅ 완료 |
| **아이템 정합성 (A+B)** | 시스템 프롬프트 3/4번(구체 아이템·골드 증여 금지 규칙) + prompt-builder [이번 턴 획득 아이템] 블록 + EventItemReward 타입 + turns.service payload.itemRewards 지급 경로 + KEY_ITEM 3종 이벤트 매핑(길드 인장/허가증/밀수 지도) + 희귀 장비 2종 상점 추가 | ✅ 완료 |
| **소지품 UX 개선** | InventoryTab 교체 확인 모달(EquipReplaceModal + 비교 카드) + USABLE_ITEMS 동적화(ItemMeta.usableInHub) + 전투 중 사용 버튼 자동 disabled + EquipmentDropToast(rarity별 5초 자동 페이드) + 에러 문구 한국어 매핑 10종 | ✅ 완료 |
| **NPA v2 메트릭** | NpcDistinctness(distinct pool 매칭률) + ToneMatch(baseline-aware mismatch) 신설, 5축 점수(연결성·자유도·사람다움·차별화·톤일치) | ✅ 완료 |
| **NPC Distinctness v1** | R1 회피 어휘 강제 룰(2회+ 등장 시 약한 표현 치환) + CORE 6명 mannerism 확장(speechStyle/signature) + rat-king dark 톤 화제 한정 — 차별화 4.83/5, ERR 0 | ✅ 완료 |
| **A51 R2~R6 + A52 시스템 프롬프트 압축** | R2 사용자 키워드 인용 가이드 + R4 NPC 권장 호칭 자동 추출 + R5 HAOCHE 어미 후처리 + R6 단일 NPC 응답 강제 + C1 P0/P1/P2 우선순위 박스 + 프롬프트 11,400→9,000자(-21%) | ✅ 완료 |
| **NPA 메트릭 v2 (다중 NPC 정확화)** | toneConsistency / pronounConsistency를 utterance 단위로 자기 NPC register/호칭 평가 + system 프롬프트 자기모순 정정(실제 NPC unknownAlias 금지 예시 제거) | ✅ 완료 |
| **A56 NPC Reaction Director + 어휘 폭주 해소** | NpcReactionDirector(추상 톤 3축 nano 사전결정) + ChallengeClassifier(자유 행동 주사위 스킵) + speechStyle 어구 예시 추상화(9 NPC) + 마커 substring 합쳐짐 자동 복구. 시그니처 어구 39.7% → 6.2% (-84%), 마이렐 패턴 0% (완전 제거), TTR +0.057, 5회 A/B + 일반 시나리오 3회 검증 | ✅ 완료 |
| **Fact 일급 객체 도입** | facts.json 신규 + ContentLoader API — Fact 를 NPC·Incident 와 동일 레벨의 콘텐츠 원자로 승격, 매칭/조회 일관화 | ✅ 완료 |
| **잠금 NPC + Fact awareness 통합** | 대화 잠금 중 NPC 의 fact 인식 상태를 LLM 컨텍스트에 통합 전달 — architecture/46 | ✅ 완료 |
| **NPC 점프 완전 차단** | event.payload.primaryNpcId 동기화 누락 수정 + NPC 후보 names에서 일반 단어 제거(스트림 점프 차단) + 대화 잠금 중 MOVE_LOCATION 차단(회귀 방지) | ✅ 완료 |
| **NPC 결정 권한 단일 통합** | NpcResolverService 신설 — 텍스트매칭/IntentV3/대화잠금/Nano/이벤트배정 5단계 우선순위를 단일 권한자로 통합. Discoverability + Content 검증 — architecture/48/49 | ✅ 완료 |
| **직전 NPC 대사 슬롯 + 회피 패턴 정상화** | 사용자 응답 복사 / 위치 회피 해소 — 직전 NPC 대사가 슬롯 누락 시 LLM 이 사용자 입력을 복사하는 버그 + 동일 NPC 의 위치 회피 부자연스러움 동시 해소 | ✅ 완료 |
| **메인 LLM Gemma 4 26B 복귀** | Gemini Flash → Gemma 4 26B MoE (OpenRouter) 메인 복귀, fallback GPT-4.1 Mini 유지. 한국어 서술 일관성·톤·OpenRouter 게이트웨이 안정성 종합 판단 — architecture/25 부록 A-1 | ✅ 완료 |
| **nano 선택지 DB/stream desync 봉합** | llm-worker.service.ts 의 첫 UPDATE 에서 llmChoices 분리 → Track 2 완료 후 finalChoices 단일 변수로 DB UPDATE + stream emit 동시 사용. Single Source of Truth 복원. 9턴 연속 DB↔API 라벨 SET byte-equal 검증 통과 | ✅ 완료 |
| **Fact 공개 단일화** | 단서 기록·서술 데스싱크 해소 — selectRevealableFact(주제 우선 선택) + ui.questReveal 전달 + 보류 가이드(factWithheldHint). 기록 fact = 서술 fact 보장 — architecture/58 | ✅ 완료 |
| **단서 대화 후속 안정화** | 판정 NPC=서술 NPC 정합(NpcResolver 부분 이름 매칭) + [단서 방향] nextHint ui 전달 복구 + HINT_MODES off-by-one — architecture/59 | ✅ 완료 |
| **단서 흐름 튜닝 + 워커 정합성** | LLM 워커 runState lost update 해소(fresh 부분 패치) + 주제 불일치 fallback 금지(인계 양보) + [단서 방향] 공개 턴 이월 + 비주제 공개 확률 게이트 — architecture/60 | ✅ 완료 |
| **NPC 대화 자연화 3종** | ① 대화 행위 감지(인사/안부/감사/작별 — 사교 턴 fact 공개 게이트 + FAREWELL 잠금 해제 + 톤 가이드) ② primary NPC 직전 발화 이어받기(마커 기반 추출 → 메인 LLM positive 블록 + nano recentNpcDialogues 정밀화) ③ 질문 우선 응답(디렉티브 + 감각초점/목격장면 억제 + fact 키워드 2-hit 스코어링 + 질문 턴 비주제 fallback 차단). NPA 검증: 인사 단서 덤핑 제거, 응답률 에드릭 56→70% | ✅ 완료 |
| **NPA 어미 메트릭 수정** | HAOCHE 최빈 종결 '-소' 누락 + 말끝 흐림 파편 집계 버그 — 하오체 준수 NPC가 45~59%로 오측정되던 것 88~100% 정상화 (로넨 45→100%, 위반 0건). 수정 전후 어미 일치율 직접 비교 불가 — architecture/55 부록 A | ✅ 완료 |
| **NPC 이름 공개 무결성** | A~E + B(pendingIntroduction) + 연출 3층 방어(경로 분기/introAttempts/IntroFallback) + **R7 스트림 문장 새니타이즈**(emit 전 미공개 실명·별칭 중복 차단, done 최종본 교체 프로토콜 확인, 죽은 배선 정리). 회귀 26건 — architecture/64 | ✅ 완료 |
| **멀티 시나리오 ① 멀티 팩 로더** | ContentPackState 팩 캐시 + AsyncLocalStorage 스코프 — 단일 활성 시나리오 정책 폐지, 서로 다른 팩 런 동시 플레이 격리. ensureScenario(팩 확보)+enterScenario(동기 컨텍스트) 규약, 진입점 4곳. 인터리브 실런·격리 스펙 4건 검증 — architecture/63 부록 D | ✅ 완료 |
| **멀티 시나리오 ⑥ 클라 선택 UI** | GET /v1/scenarios + StartScreen 여정 선택 화면(2팩 이상일 때) + store.scenarioId + HUB 라벨/프리셋 표기 시나리오 인지 + location-images 팩 인지(null=이미지 생략). E2E 완주 검증 — architecture/63 부록 C | ✅ 완료 |
| **경제 루프 v1** | 단서·진전 사례금(quest.json rewards, 팩별) + 정보 보류 턴 BRIBE 선택지 노출(nanoCtx.bribeOpportunity) + BRIBE 기본 비용 -6/-3 config 외부화. 실측 근거: 30일 441턴 골드 이벤트 4건, 대화·조사 86% — architecture/65 | ✅ 완료 |
| **엔딩 완주 평가 P1~P4** | P1 순수 이동 상용구 KW_OVERRIDE(26턴 갇힘 해소) + P2 NPC 작별 발화 잠금 해제(npcFarewell 마킹) + P3 접두 융합 별칭·무명 라벨 후처리 + P4 퀘스트 전환 장비 보상(transitionEquipment)·드랍 중복 감쇠 — architecture/65 부록 B | ✅ 완료 |
| **마커·대사 정합 마감** | 콜론 라벨 3-Tier 유일성 매칭(무명 오귀속 6→1, 잔여는 의도) + 카드 서술 언급 검사 + 진입 턴 직전 인물 이월 차단 + audit V8/V9-c 노이즈 정밀화 — 9/9 PASS 최초, 구조 결함 소진 판정 — architecture/65 부록 C | ✅ 완료 |
| **엔딩 턴 피날레 + 자기소개 사전 확정** | 엔딩 확정 턴 [마지막 장면] 디렉티브(endingType별 종결 톤)+nano 스킵+소개 비활성 (arch/65 부록 D) · NPC 자기소개 3단 사다리(nano 사전 생성→positive 주입→서버 삽입, 전 성향 통일, sanitize 소개 턴 역할 재정렬) — 자기소개 성사 0%→보장 — architecture/66 | ✅ 완료 |
| **Nano 엔진 감사** | 요청 단위 timeoutMs(light 5s/dialogue 10s — 죽은 설정 부활) + 워커 이중 처리 락(.returning 선점 확인, 7/650 실측) + NpcReaction JSON 재시도(실패 10.4%→구제) + nano 모델 env 명시 고정 — architecture/67 | ✅ 완료 |
| **카드 정합 근본 수정 + 테스트 시스템 감사** | V8 복합 원인(audit 턴 매핑 밀림 + 완전형 마커 미수집 + 부분 문자열 오매칭) 해소, 카드 교체 로직 부활 · 구 정책 테스트 갱신(스위트 실패 0)·V9-a 융합 센서 재정의·복제 drift를 export 정본 참조로 전환 — architecture/67 부록 A·B | ✅ 완료 |
| **자유 대화 정합 4종** | 언급 질문 가드 확장(조사·역할 경로, 얼마나/~가 말한) + 화자 표시·기록 소스 단일화(레거시 재계산 제거) + 작별 턴 소개 이월 + 재탕 감지 센서 — 자유 입력 '대화 상대 핑퐁' 해소 실측 — architecture/67 부록 D | ✅ 완료 |
| **멀티 시나리오 디커플링 ②~⑤** | 엔진 하드코딩 콘텐츠 ID 외부화(표시명 11곳·활동장소·entityAliases·프롤로그 스크립트·L0 테마·moveKeywords·HUB 선택지) + DAG graph.json화 + 시스템 프롬프트 세계관 주입(문면 동일 검증) + silverdeen_v1 미니 팩(장소5/NPC12/퀘스트 6단계) + scenarioId 런 경로 + 시나리오 일치 가드. 단일 활성 시나리오 정책 — ①멀티 팩 로더/⑥클라는 보류. architecture/63 | ✅ 완료 |
| **UI/UX 실사 리뷰 v1** | 헤드리스 신규 유저 경로 순회 + 6건 수정: 인물 도감 조우 필터(enc/app ≥1)+이어하기 복원(GET run npcEmotional 조립) · 모바일 상태줄(HP/STA/골드/시간) · 모바일 인물 탭 · 호외 모달 서술 완료 후 표시 · "(으)로" 조사 처리(korParticleRo ㄹ예외+7곳) · 개발자 정보 dev 게이트 — architecture/68 | ✅ 완료 |
| **UI/UX 폴리싱 C-2~C-7** | 선택지 rest 어포던스(.choice-btn 골드 카드) · 시나리오 카드 배너(getScenarioBannerImage, fallback 그라데이션) · 스탯 뮤트 앤틱 팔레트(--stat-* 토큰, 중복 3곳 정본 수렴) · 라벨 정리(카리스마 줄바꿈·레이더 한글·범례 제3명칭 통일) · 모바일 메뉴 lucide · 골드 체크박스(.checkbox-gold) — architecture/68 부록 A | ✅ 완료 |
| **C-1 거점 사랑방 개방 (A안)** | HUB 자유 입력은 서버 계약(CHOICE 전용) 유지 — 대신 팩별 거점 사랑방 장소를 HUB에 개방: graymar LOC_TAVERN·silverdeen LOC_SD_INN `hubAccessible: true` (서버 0줄, go_* 기계 파생) + 클라 HubInputNotice 안내. 자유 대화는 기존 LOCATION 파이프라인 100% 재사용, 실측 검증 — architecture/68 부록 B | ✅ 완료 |
| **자유 입력 발견성** | 첫 LOCATION 1회 코치마크(인라인 골드 배너, localStorage 플래그+포커스/닫기 소멸, useSyncExternalStore) + placeholder 행동 예시 4종 로테이션 + 시작 튜토리얼 자유 입력 안내 1줄 — architecture/68 부록 C | ✅ 완료 |
| **NanoChoiceNpcFix** | nano 선택지 sourceNpcId 오염 서버 검증 게이트(버그 5f31d803) — 대화 연속 턴에서 대화 계열 선택지의 NPC가 대화 상대와 다르면 교정(지목형 라벨·작별 턴 예외), finalChoices 확정 직전 단일 지점, export 코어+유닛 7케이스 — architecture/68 부록 D | ✅ 완료 |
| **상점 노출 동선** | 구매 dead path 부활(SHOP 인텐트 도달 불능 — TRADE+구매 표현 진입 확장, 상점 없는 장소 은유 침묵) + 클라 ui.shops 소비 신설: store shops 상태 · LocationHeader 상점 칩 · InventoryTab 진열+구매 버튼(submitAction 재사용). E2E 실구매 검증(전 DB 최초 [상점] 이벤트) — architecture/68 부록 E | ✅ 완료 |
| **NPC 선제 단서 억제 (부록 M)** | 이방인 잡담 시 NPC가 먼저 단서 흘리는 부자연스러움 제거 — 대화 계열(TALK/PERSUADE/TRADE/HELP)은 주제 매칭 시에만 fact 공개, 조사·탐색은 fallback 유지, 차단 fact는 뇌물 기회 이월. 실측: 잡담 단서 0·명시 질문 공개. B축(NPC 살아있음)은 후속 — architecture/68 부록 M | ✅ 완료 |
| **이벤트-서술 NPC 분열 (부록 L)** | 버그 185a8ddd — 첫 진입 WORLD_EVENT로 음유시인 조우 이벤트 매칭, 서술은 정보상·선택지는 음유시인 분열. EVT_TAVERN_ENC_BARD primaryNpcId 명시(콘텐츠) + 유저 명시 지목≠이벤트 NPC 시 이벤트 선택지 폐기 게이트(코드). 조우 이벤트 NPC 명시 규약은 후속 — architecture/68 부록 L. 검증 인프라: EventChoiceGate export 정본화+유닛 5케이스, playtest V10(이벤트 NPC≠서술 화자 분열 감지) | ✅ 완료 |
| **판정·서술 불일치 + 초상화 오귀속 (부록 K)** | 버그 f4bf2e66 — bribeOpportunity가 nano 이벤트 컨셉 오염(OBSERVE인데 뇌물 서술) → NanoConceptGuard(비강압 행동+뇌물 신호 시 서술필드 억제, 선택지 유지)+빈 concept 스킵+프롬프트 positive. 배경 대사 초상화 오귀속 → 마커 등장 후 무마커 대사 무명화. 유닛 3케이스 — architecture/68 부록 K | ✅ 완료 |
| **후처리 순서 의존성 정비 (부록 J)** | 소개·별칭 후처리 순서 사각지대(5.11 재삽입이 5.10 정리 이후) 해소 — 순수 텍스트 정리 5종을 멱등 배리어 sanitizeAliasArtifacts로 묶어 5.10(1차)+5.14(최종) 동일 호출. 5.14 2→5종 확장, 재삽입 완전 커버. 동작 보존(1047 passed) — architecture/68 부록 J | ✅ 완료 |
| **긴 별칭 일괄 정비 (부록 I)** | CORE/SUB 15/18명 긴 unknownAlias 편중 해소 — graymar 14명 압축(12~14자→5~10자, 첫인상 형용사 유지) + BACKGROUND shortAlias 25명 신설 + silverdeen 대칭. 코드 0줄(콘텐츠), 충돌·오류 0, 실전 검증(긴 별칭 완전 소멸) — architecture/68 부록 I | ✅ 완료 |
| **오웬 별칭 반복 수정 (부록 H)** | 사랑방 개방 후 오웬(9자 긴 별칭) 미소개 반복 결함 — 저장 직전 최종 별칭 정리(5.14, IntroFallback 재삽입 커버) + shouldIntroduce appearanceCount 강제소개 posture 차등(FRIENDLY/FEARFUL 3회, 우호 상주 조기 소개). 실전 검증: 오웬 T4 자기소개→실명 전환, 긴 별칭 소멸 — architecture/68 부록 H | ✅ 완료 |
| **선술집 BG 초상화 6종** | 사용자 제작 초상화(비올라·헬가·그래디·갤러스·제롬·마일로) 클라/서버 매핑 + 비올라 여성 개명(구 단테)·헬가 gender 정정 — 사랑방 개방 후속, 실전 검증(여성 지칭 전층 반영) — architecture/68 부록 G | ✅ 완료 |
| **아크 커밋 동선 + 3사이클 프로세스** | S5 완주 3연속 실증 + 결정 4건: 아크 루트 HUB 명시 분기(arc_commit_*, 콘텐츠 routeCommitChoices, 팩 조건부 — "정의의 대가" 12분기 최초 진입) · 봇 확장(아크/상점/사랑방) · 어휘 반복 계측 · 도착 디렉티브 MOVE 이벤트 완화(무명 인사 구멍) · 구매 target 파서 누락 보충 — architecture/68 부록 F | ✅ 완료 |
| **캠페인 자유 시나리오 선택** | 첫 시나리오 자유 선택(원점 정책 폐기, AVAILABLE/IN_PROGRESS/COMPLETED) + GET /v1/scenarios/:id/creation-bundle(팩 프리셋·특성 서빙, 클라 하드코딩 대체) + 캠페인 6단계 캐릭터 생성 통일(identity 이월 정상화) + 장비 carrySnapshot 이월 + 소모품 골드 환산 + statBonusPerScenario 배선 + campaignSummary 서사 이월 + 이월 스탯 리셋 버그 수정 — architecture/71 | ✅ 완료 |
| **NPC 반응 권한 통합** | 목격자 반응(Layer 3)↔NpcReactionDirector 이중 권한 해소: 대화 상대 목격자 루프 제외(② 단일 권한) + 당턴 1회 발화(2턴 중복 주입 제거) + posture 우선 trust 밴드(witness-reaction.core, FRIENDLY→warn) + ui.primaryNpcWitnessedTags→nano [직전 목격] 블록 + 주입 라벨 방관자 스코프 명시(메인+NanoEventDirector). 버그 599a00a1 — architecture/72 | ✅ 완료 |
| **자율 서사 팩 배포 (karnholt_v1, 2026-07-16)** | arch/74 논의 → arch/75 상세설계 → **P0~P6+P8 구현·배포** — "진상 선확정 디렉터 모드" AUTONOMOUS 팩. PlotSeedGeneratorService(진상 선확정 Plot Seed+검증/폴백) + PlotDirectorService(3막 비트 선계산·워커 비동기 CAS)+동기 채택(beat-gravity, 불변식 47 의도 정합만) + 동적 NPC 등록(dynamic-npc) + 규명율 기반 엔딩(autonomous-ending) + 킬스위치. content/karnholt_v1 팩(장소/NPC 저작·코어 외 생성) + 클라 AUTONOMOUS 라벨. P8 계측: 디렉터 존재감 낮음(채택 0~2/12턴, 의도 정합률 33%) — stale 창 확대 vs 수용 후속 결정 대기 — architecture/75 | ✅ 구현·배포 (P7/P8 후속) |
| **시장 조사 대응 (자유도·판정 투명성)** | D1 강제창 의도 존중(불변식 47: 대화 잠금·사교·REST 제외) + 과금 3원칙 등재 + D2 판정 투명성(보정 출처 분해 modifiers·FAIL 부족분·FREE 스킵 안내) + D3 actionType 탈버킷(통합 nano 감정: statHint 행동-특정 스탯·difficultyMod·plausibility 서술 치환·physicalImpact) + propsState nano 흔적 추출(링버퍼·CAS) + 되짚기(고임팩트 과거 행동 언급). 기상천외 입력 실측으로 마법-as-FIGHT 재생·흔적 과잉 해소. + **D4·D1-c 계측 트랙**: playtest 서사 방향 계측 4종(n-gram 반복률·이벤트 다양성·스레드 억제·무진행 감시) + 의도 정합 채택률(plotProgress.beatAdoptions·isBeatIntentAligned, 카른홀트 실측 33%) — architecture/76 | ✅ 완료 |
| **감정·행동화 탈버킷 (D3-b′/c′/combat)** | 원안 D3-b/c 폐기·재설계 — ① 감정 탈버킷: nano socialImpact 5축(±5) + `applyActionImpact` 블렌드(base×0.4+nano×2, 부재 시 테이블 100%) + NpcReactionDirector emotionalShiftHint 죽은 출력 CAS 배선 ② 감정→세계 행동화: npc-agitation.core(fear→도주/회피, susp→신고 Heat+5, trust→접근, 쿨다운 6턴, witness 당턴 제외) + ws.npcFleeOverrides(스케줄 재구축 우선 적용) + [NPC 능동 행동] 디렉티브 ③ 전투 기만: appraiseCombatTactic nano(Tier 3/4만) + combat-tactic.core 성향 차등(COWARDLY 1.5/TACTICAL 0.5/BERSERK 0) + 전투 내 1회 감쇠. 실런: 오웬 FLEE_LOCATION 발동·운석 기만 DISTRACTION 분류·BERSERK 무효 실측. 부수 수정: enc_generic 500 크래시(getAmbushEncounterId fallback). **후속 2건**: ① R2 어휘 인용 가이드 → 의미 단서 교체(키워드 리스트 삭제, appraisalNote 채널 — 가짜 운석 실체화 해소) ② 전투 턴 장소 NPC 앵커링 해소(triggerCombat 조기 커밋의 actionHistory 누락 수정 + isCombat 프롬프트 게이트 4블록 + [전투 장면] 디렉티브) — architecture/76 | ✅ 완료 |
| **어체 정합 근원 수정 (2026-07-17)** | 3층 결함 동시 해소 — ① 시스템 프롬프트 P0-A 자기모순(하오체 무조건 열거 → speechRegister 준수) ② 구 R5 오폭 폐기(primary 일괄 하오체 치환이 합쇼체 보조 화자 대사 파괴 — llm_speech_audit 자가 계측 실증) → **R5v2 화자 인지 정규화**(마커 화자별 register 해석 후 그 어체 어미만 교정, 낮춤체·일반 ~소는 계측만) ③ validateSpeechRegister 혼용 감지에 해요체 추가 + speech-register 합쇼체 예시 모순 교정 + silverdeen BG 6명 register 배정. 3배치 실측: 합쇼체→하오체 끌림 11→1건. 부수: 인계 가이드 지칭을 unknownAlias 인용 → shortAlias 직책 호칭으로 (따옴표 제거) | ✅ 완료 |
| **감정→행동화 실증 완결 + 밸런스 (2026-07-17~18)** | agitation 4종 전부 실발동 실증 — FLEE(마이렐 fear 89.5)·AVOID·REPORT(에드릭 susp 63.5, heat+5 + **시그널 피드 SECURITY 가시화** 신설)·APPROACH(하를런 trust 57/attach 26.8, devotee 30턴 롱런). 임계 실측 조정 2회: attach 30→10, trust 50→42 (로그 감속 곡선 — 15턴 38→30턴 45). 전투 기만 COWARDLY는 실콘텐츠 사슬 스펙 4케이스로 검증(라이브 도달은 창고 잠입·보스전 한정). 검증 페르소나 3종 신설(brawler/sneaky_liar/devotee) | ✅ 완료 |
| **서술 품질·계측 정비 (2026-07-17)** | ① 개시어 편중 동적 억제 — overusedOpeners(세션 3회+ 개시어 추출→[최근 사용 표현] 블록 확장, 26런 2,162문장 계측 15.3%→11.8% 실측, 롱런 잔여는 백로그: 임계 3→2·대명사 계열 합산) ② PlayerThread COMPLETED 데드 상태 해소(사건 해소 정산 배선) + **스레드 억제 정책 기각**(행동 카운터라 억제=기록 누락) + D4-3 재조준(사건 공존 계측) ③ V10 센서 정밀화(이벤트 선택지 실노출 조건 — 게이트 폐기 턴 FP 제거) | ✅ 완료 |
| **arch/77 Phase 2 (2026-07-17~18)** | context-builder `build()` God method **1,528→553줄 (-64%)** — P2.1~P2.10 동작 보존 컷-페이스트(FactPool/장면연속성/NPC기록/World/NarrativeEngine/Aux억제/메모리로드/프리셋배경/직전장소/소개상태). 캡처 하네스 대신 기존 유닛+playtest 게이트(Phase 3 실용 기준 적용), 게이트 2회 전부 10/10. 암묵 클로저 의존 4건 명시화 | ✅ 완료 |
| **서술 개시어·대명사 억제 사이클 (2026-07-18)** | D5 계측 센서(playtest.py — 대명사 개시어율·지칭 명사구 CONTENT/NON_ALIAS 분류) + 개시어 임계 3→2 + 대명사 화이트리스트 12종 1키 합산(동률 우선). 12턴×5런 실측: 20.3%→16.2%(상대 -20.2%, 기준 -30% 미달 — soft 지시 천장, chatty 짝은 -30.4%). 즉흥 별칭 가설 실측 기각(전부 콘텐츠 별칭·축약형 — "책임자"=마이렐 별칭 축약). 2차 처방(디렉티브 승격/후처리/수용)은 결정 대기 — architecture/78 | ⚠️ 부분 달성 |
| **팩 에셋 풀 (2026-07-19)** | 이미지 자동 매칭 시스템 — content/<pack>/assets/ 투입 + sync_pack_assets.py(ASCII 슬러그 — URL 실명 치환 404 방어) → 저작 NPC 팩 로드 시 결정론 배정 + 동적 NPC 등록 시 배정(registerDynamicNpc 3rd arg) + getNpcPortraitUrl/Map 통합 리졸버(소비처 5곳) + 클라 LOC_KH_* 매니페스트 장소 리졸버·배너. 유닛 6케이스, 카른홀트 실런 검증(마커 pack-assets URL 실부착) — architecture/80 | ✅ 완료 |
| **프롬프트 토큰 최적화 (2026-07-19)** | arch/79 P3~P4 — ShortResponse 재시도 스킵(16.5%→0%) + 시스템 프롬프트 재압축(12,154→4,668자, P0/P1/P2 박스 정본 승격) + NPC 발화 가이드 클러스터 지시 압축(데이터 무손실) + 총량 백스톱(GRAND_TOTAL_CHAR_BUDGET 16,000자, 기억 블록 보호). 최종 avg 7,495tok(-31%)·12k+ 절벽 턴 0%·게이트 7런 10/10·회귀 0·devotee 관계 누적 정상. 대화 턴 대명사 기저(~29%)는 크기 무관 별개 문제 확정 — architecture/79 | ✅ 완료 |
| **arch/77 전 Phase 마감 (2026-07-18)** | God method 리팩토링 완결 — **P3** turns.service Inner **4,440→1,937줄(-56%)** P3.1~P3.15(HUB복귀 2벌 단일화·Quest 528줄·Step1~3 턴모드+비트채택 473줄 포함) · **P4** llm-worker Inner **3,503→1,746줄(-50%)** 금지선 4곳 마킹 + narrative-filter.core 정본화(유닛 16, P5 경어체 규칙 = 한글 `\b` 불성립 죽은 규칙 발견) + 마커 대단위 920줄 · **전투/DAG** Combat 544→319줄(-41%) + **DAG 골드 무바닥 결함 수정**(유일한 의도적 동작 변경) · **P5 클라** StartScreen -26%/game-store -42%(공개 훅 유지)/StoryBlock -45%(StreamTyper 멱등성 잔존). 서버 25커밋+클라 3커밋, 매 스텝 유닛 1,390 green + playtest/E2E/browse 게이트, 회귀 0(V9 4건 전부 flaky 인과 배제). 신규 관찰: LLM 즉흥 별칭 반복은 콘텐츠 별칭 억제 커버리지 밖 | ✅ 완료 |
| **밤낮 시스템 재설계 (2026-07-20)** | 이중 시간계 근본 해소 — ① 행동 가중 timeCost(사교 0·이동/휴식 2·기타 1, 기계식 전환 제거) ② 전환 서술 주입(recentPhaseTransition → 전환 턴만 [시간대 전환] 디렉티브, 급전환 방지) ③ 4상 UI 승격(WorldStateUI phaseV2·day, 클라 새벽/낮/황혼/밤, 황혼 오표기 해소) ④ **이중 시간계 통합**(deriveTimePhaseFromV2 — v1 advanceTime 토글 폐지, timePhase = phaseV2 파생 미러, 전투 경로 불일치 해소). 실측 chatty 15턴 전환 5회→1회·brawler 정합. 신규 불변: timePhase = phaseV2 미러 — architecture/81 | ✅ 완료 |
| **어체 자기모순 교정 (2026-07-20)** | 고정 팩 speechRegister↔speechStyle 모순 3건(펠릭스·라이라·올드릭, 전부 HAPSYO↔하오체 산문) 교정 — 프롬프트 상충 주입이 어체 혼용 유발. 3팩 전수 스캔(금지목록 제거+명칭 우선, 정본 regex 1차 24건 중 21건 FP). field를 산문(정본)에 맞춰 HAOCHE. 실측 펠릭스 순수 하오체·로넨 무피해. content-validator 하드닝은 백로그 — architecture/82 A | ✅ 완료 |
| **NPC 자연스러움 3종 (2026-07-20)** | 대화 분석(자연스러움·연속성) 도출 — #5 배경 감시자 advance-or-dismiss(정적 "훑어본다" 반복→진전/퇴장 강제) · #6 제스처 앵커 제거 L0+L1(recommendPool 삭제 — 정적 풀=anchor 불변식 41/42 + frequency/presence_penalty 0.4/0.3 미사용 모델 레버 투입, "목덜미" 상투구 0회) · #7 첫 조우 개방 깊이 티어(trust+encounterCount 긍정 프레이밍, 낯선 이 과다 개방 억제). memory feedback_concrete_vocab_anchor 신설 — architecture/82 B | ✅ 완료 |

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

### architecture/ — 통합 아키텍처 (67 md + INDEX)

| 파일 | 상태 | 비고 |
|------|------|------|
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
| 21_living_world_redesign.md | ✅ 구현됨 | Living World v2 설계 배경 (구현 API는 guides/07) |
| 22_dice_roll_animation.md | ✅ 구현됨 | 주사위 판정 애니메이션 |
| 23_dialogue_ui_redesign.md | ✅ 설계 | 대화 UI 고도화 (메신저 형태) |
| 24_multiplayer_party_system.md | ✅ 구현됨 | 파티 설계·Phase 1~3 (구현 API는 guides/08) |
| 25_llm_model_evaluation.md | 📎 참고 | LLM 모델 평가 (v1+v2 통합) + 운영 모델 변천 부록. **현 운영: Gemma 4 26B MoE 메인 + GPT-4.1 Mini fallback** |
| 26_narrative_pipeline_v2.md | ✅ 구현됨 | 3-Stage Pipeline + Narrative v2/Event(18/19/20 부록) + AI 가이드라인(부록 A) |
| archive/27_image_asset_plan.md | 📜 아카이브 | 에셋 계획 — 부분 구현, content/ 하위 실측 참조 (2026-04-22) |
| archive/28_nano_event_director.md | 📜 아카이브 | 34_player_first_event_engine 의 배경 설계 (2026-04-22) |
| 30_marker_accuracy_improvement.md | ✅ 구현됨 | @마커 오류율 개선 3전략 |
| 31_memory_system_v4.md | ✅ 구현됨 | Memory v4: entity_facts UPSERT + nano 요약 주입 |
| 32_dialogue_split_pipeline.md | ✅ 구현됨 | 2-Stage 대사 분리 파이프라인 |
| 33_lorebook_system.md | ✅ 구현됨 | 키워드 트리거 로어북 |
| 34_player_first_event_engine.md | ✅ 구현됨 | Player-First 이벤트 엔진 |
| 35_llm_streaming.md | ✅ 구현됨 | LLM 스트리밍 설계 + Dual-Track 구현 + 후속 수정(2026-04-17) |
| 36_llm_pipeline_changelog_20260417.md | 📜 이력 | 2026-04-17 LLM 파이프라인·렌더링·품질 수정 Before/After 정리 |
| 39_ending_journey_archive.md | ✅ 구현됨 | 엔딩 연출 6항목 + 여정 아카이브 Phase 1 (2026-04-20) |
| 40_inventory_item_integrity.md | ✅ 구현됨 | 소지품 UX 개선 + LLM-실획득 정합성 A+B + 콘텐츠 매핑 (2026-04-20) |
| 41_creative_combat_actions.md | ✅ 구현됨 | 창의 전투 5-Tier 분류 MVP — PropMatcher + CombatService effects + LLM 조건부 재해석 블록 (2026-04-22) |
| 42_combat_ui_buttonform.md | ✅ 구현됨 | 전투 UI 버튼 폼 — 적 카드 클릭 타겟 + 5 주요 버튼 + 특수 펼침 + 아이템 모달 (2026-04-22) |
| 43_sudden_action_context_preservation.md | ✅ 구현됨 | 돌발행동 맥락 보존 — SuddenActionDetectorService (engine/hub) |
| 44_npc_dialogue_quality_v2.md | ✅ 구현됨 | NPC 대사 품질 v2 — 이슈① 환각 융합 별칭 차단(marker) + 이슈② 크로스 NPC 테마 반복 해소(ThemeClassifier) |
| 45_npc_free_dialogue.md | ✅ 구현됨 | NPC 자유 대화 — daily_topic 잡담 풀 + FACT/DAILY 공개 항목 (Phase 2~3) |
| 46_fact_pool_continuity.md | ✅ 구현됨 | Fact 일급 객체(facts.json) + NPC 연속성 — NPC 점프 근본 차단 |
| 47_dialogue_quality_audit.md | ✅ 구현됨 | NPA Audit 시스템 설계 (scripts/e2e/audit/로 구현) |
| 48_npc_discoverability_v1.md | ✅ 구현됨 | NPC Discoverability — 49로 통합 |
| 49_npc_resolver_authority.md | ✅ 구현됨 | NpcResolverService 단일 권한자 (server 56446b0) |
| 50_natural_dialogue_v1.md | 📜 폐기 | A50 자연 대화 v1 — 모든 phase 메트릭 후퇴로 전체 롤백, 51로 대체 |
| 51_npc_distinctness_v1.md | ✅ 구현됨 | NPC Distinctness v1 — A50 회고 + NPA v2 메트릭 + R1 회피 어휘 룰 + CORE mannerism 확장 (2026-04-28) |
| 55_npa_metric_v2.md | ✅ 구현됨 | NPA 메트릭 v2 — 다중 NPC 정확 측정 (utterance 단위 자기 register/호칭 평가) (2026-04-29) + 부록 A 어미 패턴 '-소' 수정 (2026-07-07) |
| 56_npc_reaction_director.md | ✅ 구현됨 | NpcReactionDirector + ChallengeClassifier + speechStyle 추상화 + 마커 합쳐짐 방어. 어휘 폭주 -84% 해소 (2026-05-04) |
| 58_fact_reveal_unification.md | ✅ 구현됨 | 단서 기록·서술 단일화 — 주제 우선 선택 + ui.questReveal + 보류 가이드 (2026-07-03) |
| 59_fact_dialogue_followup_plan.md | ✅ 구현됨 | 판정 NPC 정합 + [단서 방향] 복구 + off-by-one — 58 검증 발견 3건 (2026-07-04) |
| 60_clue_flow_tuning.md | ✅ 구현됨 | 워커 lost update(P0) + 인계 양보 + 힌트 이월 + fallback 확률 게이트 (2026-07-04) |
| 61_choice_recommendation_tuning.md | ✅ 구현됨 | 선택지 추천 튜닝 P1~P6 — nano 미리보기 꼬리 결합 + dialogueAct 전달 + 직전 라벨 반복 금지 + go_hub 라벨 정합 (2026-07-09) |
| 62_latency_optimization.md | ✅ 구현됨 | 레이턴시 최적화 4건 — nano 병렬화 2건 + 워커 즉시 킥 + 첫 토큰 타임아웃 non-stream fallback + provider sort/ignore (2026-07-09) |
| 63_multi_scenario_content_decoupling.md | ✅ 구현됨 | 멀티 시나리오 선행작업 ②~⑤ — 하드코딩 외부화 + graph.json + 프롬프트 세계관 주입 + silverdeen_v1 미니 팩 (2026-07-10) |
| 64_npc_name_reveal_integrity.md | ✅ 구현됨 | NPC 이름 공개 정합 — 2턴 분리 + pendingIntroduction + 3층 방어(경로 분기/attempts/IntroFallback) + R7 스트리밍 새니타이즈 (2026-07-10) |
| 65_economy_loop_v1.md | ✅ 구현됨 | 경제 루프 v1 — 단서·진전 사례금 + BRIBE 정보 구매 노출 + 비용 외부화 (2026-07-11) |
| 66_npc_self_introduction.md | ✅ 구현됨 | NPC 자기소개 사전 확정 — 3단 사다리 + 소개 턴 실명 역할 재정렬 + 부록 A 3차 완주 실측(성사 5/5)·다듬기 4건 (2026-07-11) |
| 67_nano_engine_audit.md | ✅ 구현됨 | Nano 엔진 전수 감사 + 부록 A~E: 카드 정합 · 테스트 감사 · 완주 평가 · 자유 대화(가드·화자 단일화·LockSeed 잠금 공백 차단) (2026-07-11~12) |
| 68_uiux_audit_v1.md | ✅ 구현됨 | UI/UX 실사 리뷰 v1 — 헤드리스 순회 + 6건 수정(도감 필터·복원, 모바일 상태줄/인물 탭, 호외 타이밍, 조사, dev 게이트) + 잔여 관찰 백로그 (2026-07-12) |
| 69_npc_living_presence.md | ✅ 구현됨 | NPC Living Presence B축 — B0~B4 구현·통합 검증(정보 편향 88→40%, 근황 발화, 목격 버그 수정) + 어미 다양화 26명 + 어체 검증 완결(C1~C2.6 — 시스템 프롬프트 하오체 전역 강제가 진짜 원인, 침식 80→9.1%, C3 미발동 확정). 잔여 과제 §7 통합 (2026-07-13) |
| 70_campaign_progression.md | ⚠️ 게이팅 대체됨 | 캠페인 순차 진행 — 캐리오버 엔진·완주/실패 시맨틱·폴백 7곳 제거는 유효, 순차 게이팅(원점/LOCKED)은 71로 교체 (2026-07-14) |
| 71_campaign_free_scenario_selection.md | ✅ 구현됨 | 캠페인 자유 시나리오 선택 — 첫 시나리오 자유 + 클리어 개방 + creation-bundle API + 장비 스냅샷 이월 + 소모품 골드 환산 + 서사 이월(campaignSummary) + 기존 버그 3건 수정 (2026-07-14) |
| 72_npc_reaction_authority_unification.md | ✅ 구현됨 | NPC 반응 권한 통합 — (가) 목격자 반응 대화 상대 제외(② 단일 권한) + 1회 발화 보장 + posture 우선 trust 밴드 + 목격 신호 ② 전달. 버그 599a00a1 (2026-07-14) |
| 73_scenario_differentiation.md | 📎 설계(제안) | 시나리오 차별화 — 동형 수렴 층위 진단(첫인상=프리셋 명명 / 중반=이벤트 밀도 123 vs 36 / 종반=ArcRoute 삼각) + Tier A(콘텐츠 탈템플릿)/B(추가형 packMeters — 연쇄 조건 재사용·아크 팩화)/C 개선안 + 검증 지표 6종. 검토 v2 실측 반영, 미구현 (2026-07-15) |
| 74_autonomous_narrative_direction.md | 📎 논의(제안) | 자율 서사·NPC 생성 심층 논의 — "핵심 NPC+세계관만 저작, LLM이 스토리·NPC 생성" 바람이 불변식 1·2(서버=진실/LLM=서술전용)와 충돌하는 지점 실측(NPC=콘텐츠 풀 select, 생성 부재) + 3층 하이브리드 디렉터 모드(동적 NPC 레지스트리·창발 디렉터·일관성 하네스) + 자율 L0~L3 + 기본값편향 역설(73 연결) + L1 스파이크 착수. **상세설계는 75로 확정** (2026-07-15) |
| 75_autonomous_pack_design.md | ✅ 구현·배포 (P7/P8 후속 대기) | 자율 서사 팩 "진상 선확정 디렉터 모드" — 문답 14결정 고정(L3·코어 외 NPC 전부 생성·장소 저작·진상 선확정 Plot Seed·3막+게이지 종결·매 런 캐스팅·모티프 풀 조합·비동기 선계산·자율 팩 재진입 예외·주민화·규명율 엔딩) + 해석 심(P0 스파이크 관문) + P0~P8 단계. **P0~P6+P8 구현·배포 (2026-07-16, karnholt_v1 AUTONOMOUS 팩)** — PlotSeedGenerator(진상 선확정+검증/폴백) + PlotDirector(비트 선계산·워커 CAS)+동기 채택(beat-gravity 불변식 47) + 동적 NPC + 규명율 엔딩 + 킬스위치. P8 계측: 디렉터 존재감 낮음(채택 0~2/12턴) — 후속 튜닝 대기 (2026-07-15 설계 → 2026-07-16 배포) |
| 76_market_alignment_direction.md | ✅ 구현됨 (D6 저작 도구만 잔여) | 시장 조사 대응 방향 — AI 텍스트 RPG 이용자 긍/부정 요인 ↔ 현 구조 대조(서버 정본·장기 기억 = 구조적 강점 / 강제 진행·판정 투명성·과금 원칙 = 갭) + D1~D6 우선순위(의도 존중 가드·판정 근거 UI·자유도 체감 3종·반복 계측·과금 3원칙·저작 도구) + §5 진행 체크리스트 (2026-07-16) |
| 77_god_method_refactoring.md | ✅ 구현됨 | God method 리팩토링 — **전 Phase 완료(2026-07-18)**: P1 prompt-builder -62% / P2 context-builder -64% / P3 turns.service -56% / P4 llm-worker -50%(금지선 4곳 항구 마킹) / 전투·DAG -41%(골드 무바닥 수정) / P5 클라 3파일 -26~-45%. §9 진행 로그가 스텝·게이트·flaky 판정의 정본. 잔여: §5 재비대화 래칫(ESLint max-lines warn) 미착수 |
| 78_narrative_opener_pronoun_cycle.md | ✅ 2차까지 완료 | 개시어·대명사 억제 — 1차(임계 2+12종 합산, -20.2%) + 2차 [서술 지칭 규칙] 디렉티브(대화 턴 상시·주어 생략 기본·별칭 문단 1회). 대화 턴 29~35%→18.8%, chatty 10.0%. devotee 단일 NPC 잠금 잔존 — 후처리 옵션만 (2026-07-19) |
| 80_pack_asset_pool.md | ✅ 구현됨 | 팩 에셋 풀 — 이미지 폴더 투입→sync(슬러그 정규화)→저작·동적 NPC·장소 자동 매칭 (성별·키워드 스코어, 결정론, 중복 배제, 빈 풀 무동작). 카른홀트 최초 적용 (2026-07-19) |
| 81_day_night_system.md | ✅ 구현됨 | 밤낮 시스템 재설계 — 행동 가중 timeCost + 전환 서술 주입(recentPhaseTransition) + 4상 UI 승격 + **이중 시간계 통합**(deriveTimePhaseFromV2, v1 advanceTime 토글 폐지). 신규 불변: timePhase = phaseV2 파생 미러. 잔여: 시간대별 특이 이벤트(콘텐츠) (2026-07-20) |
| 82_npc_dialogue_naturalness.md | ✅ 구현됨 | NPC 대화 자연스러움 — A 어체 자기모순 3건 교정(speechRegister↔speechStyle) + B 자연스러움 3종(#5 감시자 advance-or-dismiss · #6 제스처 앵커 제거 L0+L1 · #7 첫 조우 개방 깊이 티어). 저모델 반복 억제 원칙 재확인(정적 풀=anchor) (2026-07-20) |
| 79_prompt_token_optimization.md | ✅ 구현됨 | 측정 기반 프롬프트 예산 — P1 회고 1,556턴(soft 문체 11k 절벽) → 예산 10k → 4파트(재시도 스킵·시스템 -62%·NPC 클러스터 압축·총량 백스톱). avg -31%·절벽 턴 0%·게이트 7런 10/10·회귀 0. 대화 턴 대명사 기저는 크기 무관 확정 → arch/78 백로그 (2026-07-19) |
| archive/37_streaming_transition_issues.md | 📜 아카이브 | 35+36과 중복 (2026-04-22) |
| archive/38_stream_vs_nonstream_comparison.md | 📜 아카이브 | 35와 중복 (2026-04-22) |
| Context Coherence Reinforcement.md | ✅ 구현됨 | 컨텍스트 일관성 강화 |
| Narrative_Engine_v1_Integrated_Spec.md | ✅ 정본 | Narrative Engine v1 통합 |
| fixplan_history.md | 📜 아카이브 | 완료된 플레이테스트 패치 내역 (fixplan 3/4/5 통합) |

### guides/ — 코드 구현 지침 (9 md)

| 파일 | 내용 |
|------|------|
| 01_server_module_map.md | 서버 전체 서비스 맵 (107 services, 45 타입 파일) |
| 02_client_component_map.md | 클라이언트 컴포넌트 맵 (77 components, stores, CSS) |
| 03_hub_engine_guide.md | HUB 엔진 구현 (판정, EventDirector, Narrative, NPC, 평판) |
| 04_llm_memory_guide.md | LLM 파이프라인, 메모리 L0~L4, Token Budget, Scene Continuity |
| 05_runstate_constants.md | RunState JSONB 구조, 핵심 상수, Content Data |
| 06_location_image_prompts.md | 장소별 이미지 프롬프트 가이드 |
| 07_living_world_guide.md | Living World 7 서비스 (LocationState/WorldFact/NpcSchedule/NpcAgenda/Consequence/Situation/PlayerGoal) 메서드·스키마 |
| 08_party_guide.md | 파티 시스템 서비스·엔드포인트·DB 테이블·SSE 이벤트 |
| 09_karnholt_asset_prompts.md | 카른홀트 팩 에셋 생성 프롬프트 (arch/80 팩 에셋 풀용) — 초상화/장소 파일명 짝지은 27종 + 공통 스타일 프리픽스 |

## Working Language

설계 문서와 게임 콘텐츠는 한국어. 기술 식별자(enum, field name, schema key)는 영어.
