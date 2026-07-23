# 85. 포인트 시스템 (코드 발급 → 충전 → 채팅 차감)

> 상태: 📎 설계 → 구현 착수 (2026-07-23)
> 배경: 소프트 베타(지인/소수) 출시 준비. LLM 비용 상한을 유저별 포인트로 통제.
> 관련: [[76_market_alignment_direction]] D5 과금 3원칙 · CLAUDE.md "과금 원칙" · 메모리 project_llm_cost_baseline

## 1. 목적 · 배경

소프트 베타 출시의 **하드 블로커 = 비용 통제**. 현재 안전장치는 버스트 차단(글로벌 Throttler 5/초·60/분, LLM RateLimiter 동시10·3/초)뿐이라, 유저 1명이 지속적으로 턴을 제출하면 이론상 하루 수만 턴 = 수십만 원까지 비용이 샌다(유저별 총량 상한 부재).

**포인트제**로 이 구멍을 막는다: 소유자가 **코드를 발급**하면 유저가 입력해 **포인트를 충전**하고, **채팅 1회마다 포인트를 차감**한다. 발급한 포인트 총량 = 비용 상한이며, 누구에게 얼마나 줄지 소유자가 코드로 직접 통제한다.

기준값: **1턴(1채팅) = 3원** 확정 (llm_call_logs 실측, 31b⇄deepseek-flash 교차 구성 — project_llm_cost_baseline).

## 2. 확정 파라미터 (2026-07-23 소유자 결정)

| # | 항목 | 값 | 비고 |
|---|------|-----|------|
| 1 | 채팅당 소모 | **5p 고정** (`POINTS_PER_CHAT=5`) | 1p = 0.6원 (3원 ÷ 5) |
| 2 | 차감 대상 | **전 턴 일괄** | HUB 이동 포함, 모든 `submitTurn` 유저 액션 |
| 3 | 코드 유형 | **다회용** | N인 공용(`maxRedemptions`) + 유저당 1회(`unique(codeId,userId)`) |
| 4 | 가입 보너스 | **50p** (`SIGNUP_BONUS_POINTS=50`) | =10채팅 ≈ 30원, 온보딩 체험 |

**경제 예시:** 코드 500p = 100채팅 ≈ 300원 / 코드 250p = 50채팅 ≈ 150원. 가입 즉시 50p로 10채팅 무료 체험.

## 3. 데이터 모델

### 3.1 `users.points` (컬럼 추가)
- `points integer not null default 0` — 현재 잔액 캐시. 빠른 조회 + 원자적 차감의 앵커.
- 진실의 원장은 `point_transactions`. 불일치 시 원장 재집계(`sum(delta)`)로 복구.

### 3.2 `point_transactions` (원장 — 신규)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | uuid PK | |
| userId | uuid FK→users | |
| delta | integer | +충전/보너스/환불, −차감 |
| reason | text enum | `REDEEM` \| `SPEND` \| `REFUND` \| `BONUS` |
| refType | text nullable | `turn` \| `code` \| `signup` |
| refId | text nullable | 참조 id (turnId, codeId 등) |
| balanceAfter | integer | 차감 후 잔액 스냅샷 |
| createdAt | timestamp | |
- **멱등 유니크**: `unique(userId, refType, refId, reason)` — 유저 단위로 (참조·사유) 유일. turn SPEND/REFUND 이중 차감·환불 차단, 다회용 코드 REDEEM 유저당 1회, BONUS refId=NULL은 NULLS DISTINCT로 유저별 1행.

### 3.3 `redeem_codes` (발급 코드 — 신규)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | uuid PK | |
| code | text unique | 사용자 입력 코드 (대문자·하이픈 정규화) |
| points | integer | 지급 포인트 |
| maxRedemptions | integer | 최대 사용 인원 (다회용) |
| usedCount | integer default 0 | 현재 사용 수 |
| expiresAt | timestamp nullable | 만료 (null=무기한) |
| active | boolean default true | 비활성 스위치 |
| createdBy | uuid nullable | 발급 admin |
| createdAt | timestamp | |

### 3.4 `code_redemptions` (사용 이력 — 신규)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | uuid PK | |
| codeId | uuid FK→redeem_codes | |
| userId | uuid FK→users | |
| redeemedAt | timestamp | |
- **유저당 1회**: `unique(codeId, userId)`.

## 4. 차감 로직 (불변식 준수)

### 4.1 차감 단위 = `submitTurn` 1회 (유저 액션 1회)
- **전 턴 일괄**: 모든 유저 제출(ACTION/CHOICE)당 5p. HUB 이동·LOCATION·COMBAT 구분 없음.
- 한 `submitTurn`이 내부적으로 여러 turn 레코드를 만들어도(예: 이동→장소 진입) **유저 액션 1회 = 1회 차감**. `commitTurnRecord` 단위가 아니라 `submitTurn` 진입 단위.

### 4.2 가드 & 원자적 차감
- **차감 지점**: `submitTurn`의 **노드 검증 통과 후 · 디스패치(handleXxxTurn) 직전**. 소유권·활성·턴번호에 더해 노드 조회까지 끝난 뒤 차감한다.
- **원자적 차감**: `UPDATE users SET points = points - :cost WHERE id = :userId AND points >= :cost RETURNING points` → 0행이면 부족(레이스 없음). 성공 시 `point_transactions`에 SPEND 기록.
- **부족 시** `402 INSUFFICIENT_POINTS`(details: required/balance). 차감은 try 밖이라 402는 환불 경로를 타지 않음.
- **거부 액션 환불(중요)**: 차감 후 핸들러가 액션을 거부(throw — 예: HUB 자유텍스트 `422 HUB requires CHOICE`)하면 디스패치 try/catch가 `refundTurn`으로 환불한다. **차감을 노드 검증보다 앞에 두면 거부된 액션도 과금되는 버그**(2026-07-23 실측: SPEND만 남고 턴 레코드 없음) — 디스패치 직전 차감 + throw 환불로 해소.

### 4.3 멱등성
- 기존 idempotencyKey 방어: 같은 키 재제출 = 기존 턴 반환(turns.service:666) → **차감 경로 진입 전 early-return** 이므로 이중 차감 불가.
- 추가 방어: 원장 `unique(refType='turn', refId=turnId)`.

### 4.4 D5 실패 턴 무과금
- **정책(불변식·봉인)**: LLM 오류·빈 응답·재생성에 비용 차감 금지.
- **구현**: 디스패치 직전 차감 → LLM 워커가 **최종 `llmStatus=FAILED`로 종결되면 자동 REFUND**. `retry-llm`은 새 턴이 아니므로 이미 무료.
- **워커 FAILED 경로 2곳 모두 환불(중요)**: ① LLM 호출이 **에러 결과 반환**(주 경로, `refundOnFailure` before `return`) ② 파이프라인 **예외 throw**(catch). 초기엔 ②만 배선해 HUB 서술 실패(①)가 환불 누락됐던 것(2026-07-23 실측)을 `refundOnFailure(pending)` 헬퍼로 단일화해 양쪽 배선.
- `refundTurn`은 대응 SPEND 존재 + 미환불일 때만 1회(멱등). 동기 거부 환불과 비동기 FAILED 환불이 같은 idempotencyKey를 써 **최대 1회만** 환불.

## 5. API

| Method | Path | 인증 | 용도 |
|--------|------|------|------|
| POST | `/v1/points/redeem` | user | `{ code }` → 충전, 새 잔액 반환 |
| GET | `/v1/points/balance` | user | `{ points }` |
| GET | `/v1/points/transactions` | user | 사용 내역 (cursor, 선택) |
| POST | `/v1/admin/codes` | **admin** | `{ points, maxRedemptions, expiresAt? }` → 코드 발급 |
| GET | `/v1/admin/codes` | **admin** | 발급 목록 + usedCount |

- **admin 게이트**: `ADMIN_TOKEN` env 헤더 검사 (소수 운영). 병행: `scripts/issue_code.py`로 CLI 발급.
- **redeem 검증**: active·미만료·usedCount<maxRedemptions·유저 미사용 → 통과. 실패 사유별 에러 코드(`CODE_NOT_FOUND`/`CODE_EXPIRED`/`CODE_EXHAUSTED`/`ALREADY_REDEEMED`).
- **redeem 원자성**: `redeem_codes.usedCount` 증가 + `code_redemptions` insert + `users.points` 증가 + 원장 REDEEM을 **단일 트랜잭션**. unique 충돌 시 롤백.

## 6. 클라이언트 UX

- **잔액 표시**: 헤더/HUD에 `💎 N` (game-store에 points 상태 + GET balance).
- **코드 충전 모달**: 코드 입력 → redeem → 성공 토스트 + 잔액 갱신. 에러 사유 한국어 매핑.
- **잔액 부족 차단**: 402 수신 시 입력 차단 + "포인트가 부족합니다 · 코드를 입력해 충전하세요" 유도 모달.
- **소모 표기**: 포인트 안내 UI(충전 모달 PointsModal)에서 잔액과 나란히 "채팅 1회 = Np" 표시(입력창 아님 — 소유자 지시 2026-07-23). chatCost는 서버 balance 응답에서.

## 7. 환경 변수 (server/.env)

```
POINTS_PER_CHAT=5              # 채팅당 소모 포인트
SIGNUP_BONUS_POINTS=50         # 가입 시 지급
ADMIN_TOKEN=<secret>           # 코드 발급 admin 게이트
POINTS_ENABLED=true            # 킬스위치 (false=차감 전면 비활성, 롤백용)
```

## 8. 구현 Task (체크리스트 — 완료 시 커밋 해시 기록)

> 서버 → 클라 순. 매 스텝 `pnpm build` + 유닛 게이트. 커밋/푸시는 소유자 명시 요청 시.

### 서버 (구현·라이브 검증 완료 2026-07-23, 미커밋)
| # | Task | 규모 | 상태 | 비고 |
|---|------|------|------|------|
| S1 | DB 스키마 4종(users.points + point_transactions + redeem_codes + code_redemptions) | 스키마 | ✅ | drizzle-kit ESM 로드 실패 → 동등 DDL 직접 적용 |
| S2 | `PointsService` — getBalance/chargeTurn/refundTurn/redeem/grantSignupBonus/createCode/listCodes + 원장 | 서버 중 | ✅ | 순수 헬퍼 3종 export |
| S3 | 차감 배선 — 디스패치 직전 chargeTurn + 거부 throw 환불 + 402 | 서버 중 | ✅ | **버그 수정**: 조기 차감→거부 액션 과금 |
| S4 | D5 환불 — 워커 FAILED **2경로**(에러결과+예외) refundOnFailure | 서버 소 | ✅ | **버그 수정**: ①경로 누락 |
| S5 | `PointsController` — redeem/balance/transactions | 서버 소 | ✅ | |
| S6 | Admin 코드 발급 `/v1/admin/codes` (AdminTokenGuard) | 서버 소 | ✅ | scripts/issue_code.py 잔여 |
| S7 | 가입 보너스 50p (auth register) | 서버 소 | ✅ | |
| S8 | env 4종 + POINTS_ENABLED 킬스위치 + 유닛(6 pass) | 테스트 | ✅ | 라이브 E2E 8경로 검증 |

**라이브 검증(2026-07-23):** 가입 50p · 잔액 · 코드발급 · 충전(50→300) · 재사용차단(ALREADY_REDEEMED) · admin 403 · 턴 5p 차감+SPEND · 멱등 재제출 · 402 무차감 · **HUB 거부 액션 SPEND→REFUND net 0** · **HUB 서술 LLM FAILED→환불**. 서버 빌드 성공.

### 클라이언트 (구현 완료 2026-07-23, 미커밋)
| # | Task | 규모 | 상태 | 비고 |
|---|------|------|------|------|
| C1 | points-store + GET balance(로그인 시 로드·턴 후 갱신) + Header 💎 잔액(클릭=충전) | 클라 소 | ✅ | |
| C2 | PointsModal 코드 충전 + redeemPointCode API (서버 한국어 메시지 직접 표시) | 클라 중 | ✅ | |
| C3 | 402 잔액 부족 → 충전 모달 자동 오픈(submitAction/submitChoice catch) | 클라 소 | ✅ | |

**클라 빌드·lint 통과.** 서버 lint 0 · 유닛 6/6.

### 마감
| # | Task | 상태 |
|---|------|------|
| F1 | CLAUDE.md Phase Status + Document Status(85) 갱신 | ✅ |
| F2 | INDEX.md 색인 추가 | ✅ |
| F3 | 서버 빌드 + launchd 재시작 + `/v1/version` 확인 (커밋 시) | ✅ |

## 9. 하지 말 것 (D5 · 불변식 정합)

- **정상 작동을 프리미엄화하지 않는다** — 포인트는 소프트 베타 비용 게이트일 뿐, 기억·일관성·판정·진행 품질은 포인트와 무관하게 동일(D5-1).
- **실패 턴 과금 금지** — LLM 오류·빈 응답·재생성 무과금(D5-3). §4.4 환불로 보장.
- **서버 판정에 포인트를 얽지 않는다** — 불변식 1(서버=진실). 포인트는 접근 게이트, 게임 수치 아님.
- **차감을 `commitTurnRecord` 단위로 두지 않는다** — 한 유저 액션이 복수 turn 레코드를 만들 수 있어 이중 차감 위험. `submitTurn` 단위 고정.

## 10. 코드 리뷰 후속 수정 (2026-07-23, /code-review)

두 축(Standards/Spec) 리뷰가 지적한 3건 + 검증 중 파생 1건 수정. 전부 라이브 검증.

### 10.1 (HARD) 전이 턴 D5 환불 누락 → `chargeKey` 컬럼
- **문제**: 차감 SPEND는 `body.idempotencyKey`로 키잉되나, 전이 턴(enter/hub/combat/dag/return/loc)은 **파생 idempotencyKey**(`${run.id}_loc_N` 등)로 커밋된다. 그 전이 턴의 LLM이 실패하면 워커 `refundOnFailure`가 파생 키로 SPEND를 못 찾아 **환불 누락**(D5 위반). 초기 라이브 검증은 우연히 키가 일치하는 경로(LOCATION 액션·accept_quest)만 쳐서 놓침.
- **수정**: `turns.chargeKey`(nullable) 컬럼 신설 — 모든 턴 insert(commitTurnRecord + 전이 7종)에 `body.idempotencyKey` 스탬프. 워커는 `refundTurn(userId, pending.chargeKey ?? pending.idempotencyKey)`.
- **검증**: 모델 무효화 후 `go_market` 이동 → turn3 `LOCATION FAILED`(idempotency_key=`146b52fe…` ≠ charge_key=`f1b_move`) → SPEND/REFUND net 0.

### 10.2 (Spec) redeem `maxRedemptions` 초과 레이스 → 원자적 슬롯 클레임
- **문제**: `redeem()`이 check-then-increment(`if usedCount>=max throw` … 후 `usedCount+1`), 행 잠금 없음. 다른 두 유저 동시 충전이 둘 다 체크 통과 → 공용 상한 초과.
- **수정**: 조건부 `UPDATE … SET used_count=used_count+1 WHERE id=? AND active AND used_count < max_redemptions RETURNING`. UPDATE 행 잠금이 직렬화, 0행이면 소진. code_redemptions(유저당 1회) insert를 먼저.
- **검증**: maxRedemptions=1 코드에 2유저 병렬 → 1건 성공·1건 CODE_EXHAUSTED, used_count=1.

### 10.3 (Standards) chargeTurn 동시 중복 제출 23505 미가드 + 오환불
- **문제 A**: 같은 idempotencyKey 동시 제출 시 `existing` 체크를 함께 통과한 둘이 SPEND insert → 두 번째 23505 uncaught.
- **문제 B(검증 중 발견)**: 디스패치 catch가 **차감 안 한 형제(loser)의 handler throw에도** `refundTurn`을 호출 → 형제의 정당한 차감을 환불(무료 턴).
- **수정 A**: `chargeTurn`을 try/catch로 감싸 `isUniqueViolation`이면 txn 롤백(이중 차감 없음) + `charged:false` 반환. **수정 B**: `submitTurn`에 `didCharge` 플래그 — 실제 차감한 제출(`charged:true`)만 catch에서 환불.
- **검증**: 같은 키 병렬 5회 → SPEND 1·REFUND 0, 턴 1회 커밋, 정확히 5p 차감.

### 10.5 (Spec) redeem 사유별 top-level 에러 코드
- **문제**: 4가지 실패 모두 `code:'BAD_REQUEST'` + `details.reason`으로만 구분(§5 스펙은 사유별 코드 요구).
- **수정**: `RedeemError(code, message)` 클래스 신설(GameError 상속, code=CODE_NOT_FOUND/CODE_EXPIRED/CODE_EXHAUSTED/ALREADY_REDEEMED). GameExceptionFilter가 `exception.code`를 응답 top-level `code`로 매핑.
- **검증**: 라이브 — 존재하지 않는/소진/재사용 코드가 각각 top-level `CODE_NOT_FOUND`/`CODE_EXHAUSTED`/`ALREADY_REDEEMED` 반환.

### 10.4 문서/주석 정정
- `point-transactions.ts` refType/refId 주석: `turnId` → `idempotencyKey(=turn.chargeKey)`.

**회귀**: 서버 전체 1471 passed·lint 0. `setBalance` store 액션 dead code(리뷰 Note)는 잔여 — 향후 낙관적 갱신에 사용 예정이라 보존.
