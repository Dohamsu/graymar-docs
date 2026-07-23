# 87. 어드민 콘솔 — 운영 관제 시스템 설계

> 상태: ✅ 구현됨 (2026-07-23 — 설계 당일 전 Phase 구현·배포)
> 선행: arch/85 (포인트 시스템 — AdminTokenGuard·`/v1/admin/codes` 최초 도입)
> 목적: 소프트 베타 운영을 위한 단일 관제 화면 — 유저·포인트·런·LLM 비용·버그 리포트를
> 한 곳에서 조회하고, 소수의 운영 액션(포인트 조정·런 강제 종료·LLM 설정·코드 발급)을 수행한다.
>
> **구현 결과 요약**: Phase A~C 전부 완료. 서버 `admin/` 모듈(컨트롤러 5·서비스 3·DTO,
> API 12종) + 어드민 앱(`graymar-admin` 레포, Vercel `graymar-admin` 프로젝트,
> https://graymar-admin.vercel.app — admin.dimtale.com 은 DNS 레코드 대기).
> 보안 결함 2건 발견·봉쇄: ① `PATCH /v1/settings/llm` 일반 유저 개방 ② bug-reports
> 목록/상세/상태변경 일반 유저 개방. 헤드리스 QA 로 5탭 실데이터 렌더 검증
> (QA 발견 수정 3건: llmError jsonb 렌더 크래시·빈 status 422·PATCH 필드명).
> 구현 편차는 §4.1 표·§6 하단 주석 참조. 소유자 계정(rlawlsdnjswk@) admin 승격 완료.

---

## 1. 배경과 목표

### 1.1 현재 상태 (실측)

운영에 필요한 데이터·API 는 이미 대부분 존재하지만 **흩어져 있고 UI 가 없다**:

| 자산 | 위치 | 상태 |
|------|------|------|
| AdminTokenGuard (`x-admin-token` = env `ADMIN_TOKEN`) | `common/guards/admin-token.guard.ts` | ✅ 동작 (arch/85) |
| 코드 발급/목록 API | `POST/GET /v1/admin/codes` (points.controller) | ✅ 동작, UI 없음 (curl 운영) |
| 포인트 원장 | `point_transactions` + `users.points` 캐시 | ✅ 조회 API는 본인 것만 |
| LLM 턴당 비용 실측 | `llm_call_logs` (모델·스테이지별 breakdown jsonb) | ✅ 적재 중, 집계 API 없음 |
| 메인 서술 로그 | `ai_turn_logs` | ✅ 적재 중 |
| 버그 리포트 CRUD | `/v1/bug-reports` (status: open/reviewed/resolved) | ✅ API 완비, 관리 UI 없음 |
| LLM 런타임 설정 | `GET/PATCH /v1/settings/llm` | ⚠️ **AuthGuard 만 — 일반 유저도 PATCH 가능 (보안 결함)** |
| 서버 버전/업타임 | `GET /v1/version` | ✅ |
| 런 세션 | `run_sessions` (status·scenarioId·partyId) | ✅ 조회는 본인 것만 |

### 1.2 목표

1. **관제(읽기)**: 접속·비용·실패율·포인트 흐름을 대시보드 한 화면에서 파악.
2. **운영 액션(쓰기)**: 코드 발급, 포인트 수동 조정, 런 강제 종료, 버그 상태 전환, LLM 설정 변경.
3. **보안 마감**: `/v1/settings/llm` PATCH 를 어드민 게이트로 이동. 모든 어드민 쓰기 행위는 감사 로그.
4. **솔로 운영자 규모에 맞는 최소 구현** — RBAC·다중 어드민·승인 워크플로우 없음.

### 1.3 비목표 (이번 범위 제외)

- 결제 PG 연동 대시보드 (런칭 백로그 — 포인트 시스템 arch/85 참조)
- 실시간 웹소켓 관제 (폴링 30s 로 충분)
- 콘텐츠 팩 저작 도구 (arch/76 D6 별도 트랙)
- 유저 밴/제재 시스템 (어뷰징 대응은 런칭 백로그 — 스키마에 자리만 마련)

---

## 2. 인증 설계 — 하이브리드 AdminGuard

### 2.1 결정: `users.role` 컬럼 + 기존 토큰 병행

```
users.role: text enum ['user', 'admin']  NOT NULL DEFAULT 'user'
```

새 **AdminGuard** (기존 AdminTokenGuard 대체·확장):

```
통과 조건 (OR):
  ① x-admin-token 헤더 === env ADMIN_TOKEN     (curl/스크립트 운영 경로 — 기존 호환)
  ② JWT 유효 && user.role === 'admin'          (어드민 콘솔 UI 경로)
```

- 근거: ①만 있으면 클라 UI 가 토큰을 localStorage 에 들고 있어야 해서 유출면이 커지고,
  ②만 있으면 기존 curl 운영 절차(코드 발급)가 깨진다. 둘 다 허용이 이행 비용 최소.
- 어드민 승격은 UI 없이 SQL 1회: `UPDATE users SET role='admin' WHERE email='...'`.
  (솔로 운영 — 승격 API 를 만들면 그 API 가 또 다른 공격면이 된다.)
- JWT payload 에 role 포함하지 **않는다** — 가드에서 매 요청 DB 조회 (users PK lookup, 부하 무시 가능).
  role 을 토큰에 넣으면 강등 시 토큰 만료까지 권한이 살아있는 문제.

### 2.2 기존 게이트 이관

| 대상 | 현재 | 변경 |
|------|------|------|
| `/v1/admin/codes` | AdminTokenGuard | AdminGuard (동작 동일 + JWT 경로 추가) |
| `/v1/settings/llm` GET | AuthGuard | 유지 (키 마스킹된 읽기 — 게임 클라 dev 패널 호환) |
| `/v1/settings/llm` PATCH | AuthGuard ⚠️ | **경로 유지 + @AdminEndpoint() 게이트 교체** (P0 보안 수정 — 별도 /v1/admin 경로 신설 대신 제자리 게이트. 게임 클라 LlmSettingsModal 은 admin 계정만 동작하게 됨 — 의도) |

---

## 3. DB 변경 (2건)

### 3.1 `users.role` — §2.1

### 3.2 `admin_audit_logs` — 어드민 행위 감사 로그 (신규)

```ts
adminAuditLogs = pgTable('admin_audit_logs', {
  id: uuid PK defaultRandom,
  actor: text NOT NULL,            // 'token' | userId (JWT 경로)
  action: text NOT NULL,           // 'CODE_CREATE' | 'POINT_ADJUST' | 'RUN_ABORT'
                                   // | 'LLM_SETTINGS_PATCH' | 'BUG_STATUS_CHANGE' | ...
  targetType: text,                // 'user' | 'run' | 'code' | 'settings' | 'bug_report'
  targetId: text,
  payload: jsonb,                  // 요청 본문 스냅샷 (API 키 등 민감값 마스킹 후)
  createdAt: timestamp defaultNow,
});
```

- 쓰기 시점: AdminGuard 를 통과한 **모든 mutation** (GET 제외). 인터셉터 1개로 일괄 처리
  (`AdminAuditInterceptor` — 컨트롤러마다 수동 호출하지 않는다).
- 포인트 수동 조정은 이와 별개로 `point_transactions` 원장에도 남는다 (원장이 진실, 감사 로그는 행위 기록).

그 외 대시보드 지표는 **전부 기존 테이블 집계로 해결** — 신규 테이블 불필요:
users(가입), run_sessions(활성 런·시나리오 분포), turns(턴 수·llmStatus), llm_call_logs(비용·토큰·레이턴시), point_transactions(발행/소진), bug_reports(미처리 건수).

---

## 4. 서버 — `admin/` 모듈 신설

```
server/src/admin/
├── admin.module.ts
├── admin-stats.controller.ts     # GET  /v1/admin/stats/*        (대시보드 집계)
├── admin-users.controller.ts     # GET  /v1/admin/users, POST .../points-adjust
├── admin-runs.controller.ts      # GET  /v1/admin/runs, POST .../abort
├── admin-llm.controller.ts       # GET  /v1/admin/llm/*          (+ settings PATCH 이관)
├── admin-stats.service.ts        # SQL 집계 (Drizzle raw 허용 — 성능 우선)
└── admin-ops.service.ts          # 쓰기 액션 (조정·강제 종료)
```

- 기존 `AdminCodesController` 는 points 모듈에 그대로 두고 가드만 교체 (이동 비용 > 이득).
- 기존 `BugReportService` 의 목록/상세/PATCH 를 재사용 — 어드민용 신규 API 불필요,
  가드만 문제: 현 `/v1/bug-reports` GET(목록)이 AuthGuard 라면 어드민 게이트 검토 (구현 시 확인).

### 4.1 API 목록

#### 관제 (읽기)

| Method | Path | 내용 |
|--------|------|------|
| GET | `/v1/admin/stats/overview` | 핵심 KPI 1콜: 오늘/7일 가입·활성 유저(턴 제출 기준)·활성 런·오늘 턴 수·오늘 LLM 비용(USD)·LLM 실패율·미처리 버그 수·포인트 유통량(발행-소진) |
| GET | `/v1/admin/stats/llm-cost?days=30` | 일자별 비용·토큰·호출 수 시계열 + 모델별 비용/평균 레이턴시/실패 집계 (`llm_call_logs.calls` jsonb 언네스트) |
| GET | `/v1/admin/stats/points?days=30` | 일자별 발행(REDEEM/ADMIN/SIGNUP)·소진(CHAT)·환불 시계열 |
| GET | `/v1/admin/users?q=&page=` | 유저 검색 (email/nickname LIKE) — id·email·nickname·points·가입일·런 수 |
| GET | `/v1/admin/users/:id` | 상세: 잔액·최근 트랜잭션 20·런 목록·버그 리포트 수 |
| GET | `/v1/admin/runs?status=&scenarioId=&page=` | 런 목록 — 유저·시나리오·턴 수·마지막 턴 시각·llmStatus |
| GET | `/v1/admin/runs/stuck` | 스턱 런 감지: llmStatus PENDING/RUNNING 이 10분+ 정체, 또는 활성 런인데 24h+ 무턴 |
| GET/PATCH | `/v1/settings/llm` | 기존 경로 그대로 사용 (PATCH 는 @AdminEndpoint 게이트) — /v1/admin 별도 경로 없음 |
| GET | `/v1/admin/llm/failures?limit=50` | 최근 FAILED 턴 목록 (runId·turnNo·에러 요약) — retry-llm 유도용 |
| GET | `/v1/admin/health` | `/v1/version` + DB ping + LLM 워커 최근 처리 시각 (워커 정지 감지) |

#### 운영 액션 (쓰기 — 전부 감사 로그)

| Method | Path | 내용 |
|--------|------|------|
| POST | `/v1/admin/users/:id/points-adjust` | `{ amount: ±n, reason }` → point_transactions type `ADMIN_ADJUST` + 잔액 캐시 갱신 (기존 PointsService 원자 경로 재사용, 음수 잔액 방지) |
| POST | `/v1/admin/runs/:id/abort` | `{ reason }` → status RUN_ABORTED (finalizeVisit 메모리 통합 경로 — 불변식 20 준수) |
| POST | `/v1/admin/runs/:id/turns/:turnNo/retry-llm` | 기존 retry-llm 을 어드민이 유저 대신 실행 (스턱 런 구제) |
| POST | `/v1/admin/codes` | 기존 유지 (가드만 AdminGuard) |
| PATCH | `/v1/bug-reports/:id` | 기존 유지 — 어드민 콘솔에서 호출 |

### 4.2 집계 쿼리 원칙

- 대시보드 집계는 **요청 시 SQL 집계** (사전 집계 테이블·크론 없음). 소프트 베타 데이터 규모
  (수십 유저·수천 턴)에서 인덱스만으로 충분. 느려지는 시점에 materialized view 검토 — 지금은 YAGNI.
- 필요 인덱스 확인: `llm_call_logs(created_at)`, `point_transactions(created_at)`,
  `turns(created_at)` — 없으면 이번에 추가.
- `llm_call_logs.calls` jsonb 모델별 집계는 `jsonb_array_elements` 언네스트 — 30일 범위 제한 필수.

---

## 5. 클라이언트 — **별도 어드민 앱 분리** (`admin/` 신규, 별도 배포)

### 5.1 위치 결정 — 분리 (2026-07-23 확정)

초안은 기존 client 내 `/admin` 라우트였으나 **별도 앱 분리로 확정**. 판단 근거를 정확히 기록:

- **퍼포먼스는 분리 이유가 아니다** — App Router 라우트 단위 코드 스플리팅으로 `/admin` 번들은
  게임 플레이어에게 로드되지 않는다. 런타임 손해 ≈ 0, 빌드 시간만 소폭 증가.
- **분리의 실제 근거는 보안·격리 3가지**:
  1. **오리진 격리** — 동일 오리진이면 게임 클라 XSS 1건으로 어드민 JWT/세션까지 탈취 가능.
     서브도메인 분리 시 브라우저가 localStorage/cookie 를 오리진 단위로 격리해 원천 차단.
  2. **노출면 축소** — `dimtale.com/admin` 은 존재 자체가 추측 가능. 별도 서브도메인은 비공개
     + 앞단 차단 가능. **이미 cloudflared 터널 운영 중이므로 `admin.dimtale.com` 에
     Cloudflare Zero Trust Access(이메일 SSO 게이트)를 무료로 전치** — 앱이 로드되기 전에 차단.
  3. **배포 격리** — 게임 클라 배포 사고·롤백이 어드민에 무영향 (역도 동일).

구성:

```
graymar/
├── client/        # 게임 (기존, dimtale.com)
├── admin/         # 어드민 콘솔 (신규) — 독립 package.json, 별도 Vercel 프로젝트
└── server/        # NestJS (공용 — admin API 는 같은 서버, 분리는 프론트만)
```

- 레포: 기존 패턴대로 `admin/` 은 **독립 git 레포 `graymar-admin`** (server/docs/client 에 이은
  4번째 레포). 브랜치 정책 동일 — main 직접 커밋, Vercel main push 자동 배포.
- 스택: **Next.js 유지** (스택 통일 — 운영자가 한 사람이므로 학습 비용 최소화). 단 게임 클라
  의존성·store 를 일절 import 하지 않는 독립 앱. 공유가 필요한 코드는 request 래퍼(JWT 헤더
  ~50줄) 정도뿐이라 복사가 관리 비용보다 싸다 — 모노레포 공유 패키지화는 YAGNI.
- 배포: 별도 Vercel 프로젝트 → `admin.dimtale.com`. 게임 클라와 동일하게 main push 자동 배포.
- 서버 CORS: allowlist 에 `admin.dimtale.com` 오리진 추가 필요 (구현 시 main.ts CORS 설정 확인).
- 인증: 어드민 앱 자체 로그인 화면 (기존 `/v1/auth/login` 재사용) → role=admin 계정만 통과 (§2).
  Cloudflare Access 를 앞단에 두면 로그인은 2차 방어가 된다 (다층 방어).
- 데스크톱 우선 (운영자 1인 — 모바일 대응은 테이블 가로 스크롤 정도만).

### 5.2 화면 구성 (5탭)

```
admin/app/
├── layout.tsx          # 권한 프로브 (GET /v1/admin/health — 403 시 로그인/안내)
├── login/page.tsx      # 어드민 로그인 (기존 auth API 재사용)
├── page.tsx            # ① 대시보드
├── users/page.tsx      # ② 유저·포인트
├── runs/page.tsx       # ③ 런 관제
├── llm/page.tsx        # ④ LLM 관제
└── bugs/page.tsx       # ⑤ 버그 리포트
```

| 탭 | 내용 |
|----|------|
| ① 대시보드 | KPI 카드 8개 (overview 1콜) + 비용 30일 라인차트 + 포인트 유통 차트. 30s 폴링 |
| ② 유저·포인트 | 검색 테이블 → 행 클릭 상세 패널(트랜잭션·런) → 포인트 조정 모달(사유 필수) · 코드 발급/목록 섹션 |
| ③ 런 관제 | 활성 런 테이블 + **스턱 런 경고 배너** (stuck API) → 행 액션: retry-llm / 강제 종료(confirm 2단) |
| ④ LLM 관제 | 현 설정 폼(모델·provider·fallback — PATCH) + 모델별 비용/레이턴시/실패 테이블 + 최근 실패 로그 |
| ⑤ 버그 리포트 | 기존 API 그대로 — 목록(status 필터) → 상세(recentTurns·clientSnapshot 뷰어) → 상태 전환 버튼 |

- 차트는 경량 유지 — 신규 차트 라이브러리 도입 전에 CSS/SVG 자작 or 기존 의존성 확인
  (게임 클라에 차트 라이브러리 없음 — 30일 라인차트 2개면 단순 SVG 로 충분).

---

## 6. 구현 단계

| 단계 | 범위 | 산출 |
|------|------|------|
| **A. 보안 마감 + 기반** (P0) | `users.role` + AdminGuard(하이브리드) + `admin_audit_logs` + AuditInterceptor + **settings/llm PATCH 이관** + 기존 codes 가드 교체 | 보안 결함 해소가 최우선 — 이 단계만으로도 배포 가치 |
| **B. 관제 읽기** | admin 모듈 stats/users/runs/llm 읽기 API 전부 + **admin 앱 스캐폴드**(별도 Next.js + Vercel 프로젝트 + admin.dimtale.com + CORS + Cloudflare Access) + 5탭 읽기 화면 | 대시보드 가동 |
| **C. 운영 액션** | points-adjust · run abort · admin retry-llm + 클라 액션 UI (confirm·사유 입력) | curl 운영 졸업 |
| **D. 자동 감시 (선택)** | stuck 런·일 비용 임계(예: $5/일) 초과 시 알림 — 알림 채널은 현재 Slack 비활성 정책이므로 **대시보드 배너까지만**, 외부 푸시는 정책 재활성화 시 | 후순위 |

각 단계 완료 기준: 서버 `pnpm build` + lint 0 + 유닛(가드·조정 원자성·감사 인터셉터) + 클라 `pnpm build`,
배포는 정본 절차 (build + launchctl kickstart + `/v1/version` 확인).

---

## 7. 보안 체크리스트

- [ ] `/v1/settings/llm` PATCH 어드민 게이트 이관 (P0)
- [ ] AdminGuard: 토큰 비교 timing-safe (`crypto.timingSafeEqual`)
- [ ] 어드민 mutation 전부 감사 로그 (인터셉터 — 컨트롤러 누락 불가 구조)
- [ ] 감사 로그 payload 에서 API 키·비밀번호 필드 마스킹
- [ ] `/v1/admin/*` rate limit (Throttle) — 토큰 무차별 대입 방어
- [ ] 어드민 프론트 오리진 분리 (admin.dimtale.com) + 서버 CORS allowlist 명시 추가
- [ ] (권장) Cloudflare Zero Trust Access 전치 — 앱 로드 전 이메일 SSO 게이트
- [ ] admin 앱 noindex 메타 (Access 뒤라도 이중 방어)
- [ ] 어드민 응답에서 `passwordHash` 등 민감 컬럼 select 제외 (Drizzle columns 명시)
- [ ] 포인트 조정: 음수 잔액 방지 + 원장·캐시 원자성 (기존 PointsService 트랜잭션 재사용)
- [ ] run abort: RUN_ENDED 메모리 통합 경로 준수 (불변식 20)

---

## 8. 관제 강화 (2026-07-23, server 99a32cc)

소프트 베타 운영 중 요청된 7건. arch/87 §5.2 "차트 라이브러리 금지"는 이 사이클에서 **사용자 지시로 명시적 오버라이드**(recharts 도입).

### 8.1 테스터 계정 개념 도입
- **정본 판정**: `server/src/common/tester.util.ts` — 이메일 도메인 기준(`test.com`·`t.com`·`example.com`·`test.local`·`example.test`·`graymar.local`). 별도 컬럼 없이(마이그레이션 회피) `isTesterEmail()` + `TESTER_DOMAINS_SQL_ARRAY` 단일 정본. 실유저 도메인(gmail·naver·회사)은 절대 미포함.
- **집계 제외**: `admin-stats.service.overview` 의 가입·활성 유저·활성 런·오늘 턴 4지표가 `notTesterSql(emailCol)` predicate 로 테스터를 제외(턴 집계는 실패율까지 실유저 기준). 대시보드에 "테스터 제외" 캡션.
- **정리 실적**: 테스트 도메인 계정 1,706개 + 관련 데이터(런 1,650·턴 18,974·llm 로그 5,059·파티 47·캠페인 40 등)를 단일 트랜잭션 cascade 삭제. 실유저 15명만 잔존. 이후 정본 테스터 `playtest@test.com` fresh 재생성(비번 `Test1234!!`).
- **스크립트 재사용**: `scripts/playtest.py` 기본값을 `playtest@test.com` register-or-login 재사용으로 전환(`--new-account` 시에만 신규). `party-playtest.py` 도 결정론적 `party_<name>@test.com` + login fallback.

### 8.2 유저 관제 — 삭제·비밀번호
- **하드 삭제**: `DELETE /v1/admin/users/:id`(reason 필수) → `AdminOpsService.cascadeDeleteUsers(userFilter)`. FK `onDelete` 미설정이라 역위상 순서 수동 삭제(트랜잭션): run children(run_id) → 타인 런 잔여 유저행 → 파티 children(party_id) → 타인 파티 잔여 유저행 → run_sessions → redeem_codes 체인 → 유저 직접소유(campaigns/hub_states/player_profiles/point_transactions) → parties → users. `run_sessions.party_id`·`campaign_id` FK 때문에 run_sessions 를 parties·campaigns 보다 먼저 삭제. **admin role 계정은 차단**(ForbiddenError). 클라: 이메일 재입력 2단 확인.
- **비밀번호 강제 변경**: `POST /v1/admin/users/:id/password`(password ≥8 + reason) → auth 와 동일 bcrypt rounds 12. 클라: UserDetailPanel 모달. 왕복 검증(변경 후 새 비번 login 200).
- 단일 유저 삭제와 대량 정리가 **동일 cascade 순서**를 공유(서비스 `cascadeDeleteUsers` = 정리 SQL 과 동형).

### 8.3 런 관제 — 스턱 강제 종료
스턱 런 배너 각 행에 **강제 종료** 버튼 추가(기존 `POST /v1/admin/runs/:id/abort` 재사용, RUN_ABORTED, reason 2단 확인). 스턱은 정의상 RUN_ACTIVE 라 abort 경로가 그대로 성립.

### 8.4 LLM 비용 차트 + 원화
- **차트**: `admin/components/LlmCostChart.tsx` — recharts ComposedChart(일 비용 막대 + 호출 라인 이중축) + **Brush 드래그 확대/축소** + 기간 선택(7/30/90일 refetch). LLM 관제 탭에 배치.
- **원화 통일**: `admin/lib/format.ts` `USD_TO_KRW=1500`·`usdToKrw`·`fmtKrw`. 어드민의 모든 금액(대시보드 KPI·비용 차트·모델별 비용 테이블)을 ₩ 표기. 환율 1500원/$ 고정(프로젝트 정책).

### 8.5 버그 리포트 보고자
`BugReportService.findAll/findOne` 이 users leftJoin 으로 `reporterNickname`·`reporterEmail` 제공(`getTableColumns` 스프레드). 어드민 버그 테이블에 보고자 열 + 상세 메타에 이메일. 계정 삭제 시 null → "(삭제된 계정)".

### 8.6 검증
서버 build·lint 0·유닛(tester.util 7 + admin dto/ops 기존 8) + 라이브 왕복(overview 테스터 제외·bug-report 보고자·password 변경 후 login·cascade 삭제 후 404). 어드민 build·lint 0. 차트 브라우저 시각 확인은 admin JWT 필요 — 별도 QA 잔여.

---

## 9. 실제 과금 대조 — OpenRouter Activity 연동 (2026-07-23)

**배경**: 어드민 비용 차트(`llm_call_logs` 기반)가 실제 OpenRouter 청구와 큰 괴리(주간 실측 $5.15 vs 측정 $0.10, 53배). 원인 분석:
- **단가는 정확** — `costUsd`는 OpenRouter 응답의 `usage.cost`를 그대로 저장(자체 가격표 아님, openai.provider). 제로/누락 비용 행 0건.
- **원인 ① 테스터 로그 삭제(지배적, ~89%)** — §8.1 테스터 정리 때 `llm_call_logs` 5,059행 삭제. 실제 과금 대부분이 테스터 플레이테스트 게임 턴 비용이라 차트가 붕괴.
- **원인 ② 서버 미경유 호출(구조적, ~11%)** — `llm_call_logs`에 아예 안 남는 실지출: 플레이테스트 **에이전트 플레이어**(`--agent`, gpt-4.1-mini를 OpenRouter 직접 호출, 서버 우회) + **모델 평가**(arch/25, deepseek-v4-pro·solar-pro-3 등 턴 파이프라인 밖).

**연동**: OpenRouter Activity API(`GET /api/v1/activity`)로 실제 청구를 대조.
- 응답 `ActivityItem`: `{ date(UTC), model, model_permaslug, provider_name, usage(USD 실청구), requests, prompt/completion/reasoning_tokens }`. 최근 30 완료 UTC일. `usage`가 실제 청구액(사용자 CSV `total_usage`와 동일 필드).
- **인증 = Management(Provisioning) 키** — 일반 추론 키(sk-or-v1-)는 403. `openrouter.ai/settings/management-keys`에서 발급 → server `.env` `OPENROUTER_MANAGEMENT_KEY`.
- 서버 `AdminOpenRouterService.costReconciliation(days)` — Activity(10분 캐시) + `llm_call_logs` 측정을 일자·모델별 병합. 미설정 시 `configured:false` + 측정치만 반환(UI 안내). `GET /v1/admin/stats/cost-reconciliation?days=`.
- 클라 `CostReconciliation.tsx` — 실제 vs 측정 그룹 막대(recharts, Brush 확대/축소) + 갭 KPI(실제−측정, %) + 실제 청구 모델별 표. 전부 원화. 미설정 시 management 키 발급 안내 배너.
- **주의**: Activity `date`는 UTC, `llm_call_logs.created_at`은 서버 로컬 → 일 경계 스큐 가능. 실지출 진실원은 Activity(실제 청구), `llm_call_logs`는 서버 경유분만.
