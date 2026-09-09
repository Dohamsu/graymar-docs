# 115. 보안 감사 후속 — 접근제어·프록시·세션·시크릿 (2026-09-07)

> 상태: ✅ **구현·배포됨** (server `814e786` · client `8b836ac`·`7ab6247` · docs `c664f72`, 2026-09-08 푸시). 소유자 수동 잔여 3건은 `TODOS.md` 가 정본.
> 원 리포트: `.gstack/security-reports/2026-09-07-cso-report.md` (gitignored — 취약점 재현 세부는 레포에 두지 않는다). 관련: arch/87(어드민 게이트), arch/107(비공개 테스트 게이트), arch/35(SSE)

## 0. 요약

`/cso` daily 감사(server·client·admin·docs 4레포)가 HIGH 6·MED 10 을 냈고, 소유자 지시로 전항목을 같은 날 수정했다. 전부 **"동작은 정상인데 경계가 없던"** 부류다 — 기능 테스트·게이트 15종·자기점검 하네스(arch/101) 어느 것도 잡지 못했다. 소유권 검증이 빠진 id 조회, 전 라우트에 열린 쿼리 토큰, 프록시 뒤에서 무의미해진 per-IP 제한, 타입만 있고 런타임 검증이 없던 PATCH body.

## 1. 서버 수정 (server `814e786`)

| ID | 결함 | 수정 | 파일 |
|----|------|------|------|
| H1 | `POST /v1/runs` 가 타인 `campaignId` 로 carry-over 를 가져오고 런 종료 시 타인 캠페인 진행을 덮어쓰는 IDOR | `campaignsService.getCampaign(id, userId)` 소유권 선행 검증 — 미소유 403 | `runs/runs.service.ts` |
| H2 | 파티 턴 상세가 `run.partyId` 를 검사하지 않아 cross-run 조회 가능 | 런 ∈ 파티 가드 | `party/party.controller.ts` |
| H3 | `castVote` 가 vote ∈ 파티를 검증하지 않음 + stale row read-then-write 로 동시 요청 1인 2표 | 파티 불일치 404 + **원자적 조건부 UPDATE**(`PENDING` + 미투표를 DB 가 재확인, 카운터 제자리 증가, 0 rows = 경쟁 패배) | `party/vote.service.ts` |
| H4 | 취약 의존성 | drizzle-orm 0.45.2 · @nestjs/core|platform-express 11.2.3 · sharp 0.35.4, stale `package-lock.json` 삭제(pnpm 단일화) | `package.json` |
| M1 | `includeDebug` 가 시스템 프롬프트 전문(`llmPrompt`)을 일반 유저에게 노출 | `x-admin-token` 동반 요청에만 (`safeTokenEqual`) — 플레이테스트 V12 게이트가 이 경로로 표본을 모으므로 `playtest.py` 가 토큰을 첨부(docs `be4ce9f`) | `turns/turns.controller.ts`·`turns.service.ts` |
| M2 | cloudflared 뒤에서 `req.ip` 가 전부 127.0.0.1 → ThrottlerGuard·초상화 업로드 per-IP 제한이 **전 인터넷 합산 버킷 하나**(로그인 10/min 이 전역 상한) | `app.set('trust proxy', 'loopback')` — 루프백에서 온 연결의 X-Forwarded-For 만 신뢰(LAN 스푸핑 불가) + 기본 바인딩 `127.0.0.1`(`HOST` env 로 해제) | `main.ts` |
| M3 | AuthGuard 가 **모든** 라우트에서 `?token=` 쿼리 인증을 받아 JWT 가 프록시·터널 로그·브라우저 이력에 남음 | `@AllowQueryToken()` 데코레이터를 단 SSE 핸들러 2곳(턴 스트림·파티 스트림)만 허용 — EventSource 는 커스텀 헤더를 못 붙이므로 그곳만 필요 | `common/decorators/allow-query-token.decorator.ts`·`common/guards/auth.guard.ts` |
| M4 | 클라가 JWT 를 localStorage 에 두던 것을 httpOnly 쿠키 세션으로 바꾸면서 쿠키를 지우는 서버 경로가 없음 | `POST /v1/auth/logout` 신설(무인증·멱등) | `auth/auth.controller.ts` |
| M8 | `PATCH /v1/settings/llm` body 가 TS 타입만 있고 런타임 검증이 없어 `{...config, ...body}` 로 `openaiApiKey`·`openaiBaseUrl` 까지 덮어쓰기 가능 — 어드민 토큰 유출 시 전 프롬프트를 임의 호스트로 흘리는 경로 | Zod `.strict()` allowlist(provider·model 슬러그 `^[\w./:-]+$`·maxRetries 0~5·timeoutMs·maxTokens·temperature·fallback) — 미등재 키 400 | `llm/llm-settings.controller.ts` |
| M9 | 파티원 nickname 이 system 메시지에 그대로 들어감(프롬프트 인젝션 벡터) | `sanitizeNickname` 후 주입 | `llm/prompts/prompt-builder.service.ts` |
| M10 | docker-compose 에 DB 비밀번호 평문 | `POSTGRES_PASSWORD` 를 `server/.env` 참조(`${POSTGRES_PASSWORD:?...}` — 미설정 시 기동 실패) | `docker-compose.yml` |

## 2. 클라이언트 (client `8b836ac`·`7ab6247`)

- **H5** next 16.3.4 상향.
- **M4** JWT localStorage 제거 → httpOnly 쿠키 세션. `/v1/auth/me` 로 세션 복원, SSE 는 `withCredentials`. 어드민 앱은 vercel.app(cross-site)라 토큰 localStorage 유지.
- CSP/HSTS/X-Frame-Options 헤더(`next.config.ts`), Cloudflare Web Analytics 비콘 호스트 CSP 허용(후속 `7ab6247`).

## 3. 시크릿·백업 (docs `c664f72`)

- 공개 레포에 평문으로 있던 테스터 계정 비밀번호 리터럴 **29곳** 제거 → `server/.env PLAYTEST_PASSWORD`. 읽기 정본은 `scripts/playtest_env.py`(`playtest_password()`)·`scripts/e2e/_helpers.ts`(`loadServerEnv`). 문서·스킬에도 리터럴을 두지 않는다(`.claude/skills/quality-cycle` 2026-09-09 정정).
- `ADMIN_TOKEN` 64자 hex 회전, env 파일 0600, `.env.bak` 삭제, 루트 레포 `refs/original` 제거+gc.
- **백업 0 → 일일 백업**: `scripts/backup-db.sh`(`pg_dump -Fc`), launchd `com.graymar.db-backup` 04:30, `~/Backups/graymar` + iCloud 사본, 14일 보존.

## 4. 소유자 잔여 (TODOS.md 정본)

| 항목 | 이유 |
|------|------|
| DB 자격증명 회전 (`ALTER USER`) | 에이전트 실행이 자동 모드 분류기에 차단 — compose·env 는 준비됨 |
| Slack Incoming Webhook 재발급 | 루트 `.env` 평문 이력 |
| 미사용 OpenRouter 키 revoke | `server/.env` 에 없는 구 키 |

## 5. 검증

서버 2,592 passed(당시)·`/v1/version` 해시 일치·스모크 PASS. 게이트 거절은 curl 로 직접 확인(타 캠페인 id 403·비 SSE 라우트 `?token=` 401·PATCH 미등재 키 400). 재감사 시 리포트 JSON fingerprint 로 추세 비교.

## 6. 교훈

- **경계 결함은 기능 테스트가 못 잡는다** — 정상 입력만 통과시키는 테스트는 "남의 id" 를 넣지 않는다. IDOR 부류는 서비스 진입점에서 `(id, userId)` 를 함께 받는 시그니처로 강제하는 편이 리뷰보다 낫다(H1 이 그 형태).
- **프록시 뒤 rate limit 은 trust proxy 없이는 사문**이다(불변식 부류 "조용히 꺼진 배선", arch/101). 배포 토폴로지가 바뀌면 `req.ip` 가 무엇인지 먼저 확인한다.
- **런타임 검증 없는 PATCH 는 allowlist 로**. TS 타입은 와이어를 지키지 않는다.
