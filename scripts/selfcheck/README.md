# 자기점검 하네스 (arch/101)

코드·문서·DB 3소스 정합 감사. **LLM 호출 0 · 포인트 0 · 서버 재시작 불필요.**

```bash
python3 scripts/selfcheck/invariants.py          # A족 — 불변식 감시
python3 scripts/selfcheck/content_consistency.py # E족 — 콘텐츠 정합
python3 scripts/audit_payload_keys.py --lifetime # B족 — 배선 감사 (arch/100 §16)
python3 scripts/selfcheck/pipeline_loss.py       # C족 — 파이프라인 손실 (--days N)
python3 scripts/selfcheck/reachability.py        # D족 — 임계 도달성
python3 scripts/selfcheck/wiring.py              # W족 — 배선 정합 (arch/112 P3-C, DB 불필요)
```

## 판정 규약

| 표기 | 뜻 |
|---|---|
| ✅ OK | 분모 N > 0 이고 위반 0 |
| ❌ VIOLATION | 위반 발견 — **원문 대조 후에만 결함으로 보고** |
| ❔ UNDECIDABLE | **분모 0** — 그 상태가 DB 에 없다. "정상"이 아니다 |
| ⚠️ ERROR | 질의 실패 |

**철칙 — 분모 없는 판정 금지.** `0/0` 은 통과가 아니라 판정 불가다.

## 오탐 이력 (디텍터가 배운 것)

| 회차 | 항목 | 오탐 | 원인 → 대책 |
|---|---|---|---|
| 1 | #45 엔진 리터럴 | 14/14 | enum·접두규약 예외 미구현 → 실제 팩 ID 대조 |
| 2 | #45 | 5/5 | enum 값이 콘텐츠 JSON 에도 존재 → db/types enum 멤버 제외 |
| 1 | #42 speechStyle | 1/4 | 정규식이 따옴표 쌍을 가로질러 매칭 → 쌍 내부만 + 호칭 제외 |
| 1 | #6 actionSlots | 분모 0 | jsonb 경로 오류 → `ui->actionSlots` |
| 5 | #9 Heat | — | 시간 창 없음 → 과거 행이 안 빠져 수정이 안 보임. `--days` 창 도입 |
| 5 | #17 프롬프트 | 전량 | 백스톱을 하드 상한으로 오판 → V12 발동률 ≤20% 로 기준 정정 |
| 7 | C4 questReveal | 30/30 | `ui.questReveal` 을 문자열로 봄 → 실제는 객체, `factId` 해석 필요 |
| 7 | C4 questReveal | 10/30 | 모든 revealMode 를 같은 기준으로 판정 → `direct` 만 게이트, indirect/observe 는 계측 |
| 9 | W1b 캐스트 계측 | 0/60 (전량 누락) | 정규식 끝 `\b` 가 `>)` 사이에서 불성립 → 후행 경계 제거 (C6 극단값 0% 는 검사기 의심) |
| 9 | W2 상태형 필드 | `avoid` 오탐 | `Id$` 를 대소문자 무시로 두어 "avo**id**" 매칭 → `[a-z]Id$` 대소문자 구분 |
| 9 | W2 검증 참조 | 4/5 오탐 | 변수명을 `result|parsed` 로 한정 + 검증 창 ±3줄 → 임의 변수(`guarded`)·6줄 뒤 clamp 를 놓침. 창 −3~+8 |
| 9 | W3 커밋 판정 | 1/3 오탐 | 삼항 연속행이 앞줄의 `isArcCommitted` 를 못 봄 → 앞 2줄 창 |

디텍터 수정 시 이 표에 추가한다. **오탐을 못 줄이면 루프는 노이즈 생성기가 된다**
(arch/101 §5).

## W족 판정 규약 (arch/112 P3-C)

| 항목 | 위반 뜻 | 정본 |
|---|---|---|
| W1 | `result.ui.X =` 부착 필드가 `UIBundle` 에 없음 — 소비자가 캐스트로만 읽는 "조용히 꺼진 배선" 후보 | `db/types/server-result.ts UIBundle` |
| W1b | 계측 — 타입 있는 필드를 `ui as Record/any` 로 우회하는 읽기·쓰기 수 (0 이 목표, 증가는 회귀) | — |
| W2 | 프롬프트가 소비하는 nano JSON 필드 중 상태를 이름하는 것(fact·npc·Id·signal·shift·level·type…)에 director 검증/정규화 참조가 없음 — 결함 B(`factRevealed` 무대조 승격) 부류 | director 검증 블록·`normalize*Core` |
| W3 | 조건식이 `arcState.currentRoute` 를 커밋 신호로 씀 — ARC_HINT 이벤트가 커밋 전에도 채우는 필드 (결함 A 부류) | `arc-stage.core isArcCommitted` |

DB 를 쓰지 않으므로 `--days` 창이 없다. 수용 예외는 `baseline.json` 의 `W…` id.

## D족 판정 규약

| 판정 | 뜻 |
|---|---|
| `UNREACHABLE` | 임계 > 관측 최대 — 기능이 완전히 꺼져 있다 |
| `NEAR_DEAD` | 임계 > p99 — 상위 1% 만 도달, 사실상 꺼짐 |
| `ALWAYS_ON` | 임계 < p50 — 상시 발동, 게이트가 무의미 |

`NEAR_DEAD` 는 **위반이 아니라 밸런스 신호**다. 임계를 낮출지, 축적 속도를
올릴지, 의도된 희소성인지는 소유자 판단 영역이라 자동 수정하지 않는다
(arch/101 §11-③).

## 검사기 감사 체크리스트 (M0 — 정본)

검사기가 틀리는 방식은 유한하다. 아래 8유형은 **전부 이 레포에서 실제로
발생한 것**이며(2026-08-12 하루), 새 검사기를 만들거나 기존 것을 감사할 때
이 목록을 순서대로 대조한다.

| # | 유형 | 실제 사례 | 확인 방법 |
|---|---|---|---|
| **C1** | **자료형 가정 오류** | `ui.questReveal` 을 문자열로 봄 → 실제는 `{npcId,factId,revealMode}` 객체 (30/30 오탐) | 실물 1건을 `jsonb_typeof` + 원문 출력으로 눈으로 확인 |
| **C2** | **분모 없음/0** | `#6 actionSlots` 경로 오류로 `0/0` → "정상"으로 보임 | 분모가 0 이면 `UNDECIDABLE`. 통과로 세지 않는다 |
| **C3** | **시간 창 없음** | `#9 Heat` 전 기간 집계라 수정해도 11 그대로 | DB 기반 검사는 `--days` 창 필수. 수정 효과가 보여야 한다 |
| **C4** | **기준이 설계 계약과 불일치** | 백스톱(best-effort)을 하드 상한으로 판정 → 494건 위반 | 문서의 *약속*을 읽고 기준을 맞춘다. 코드가 보장 안 하는 걸 요구하지 않는다 |
| **C5** | **표시명 vs ID 비교** | V8 게이트: `책임자` ≠ `마이렐 단 경` (동일 NPC) | 비교는 반드시 **ID 로 정규화 후** |
| **C6** | **정규식 과탐** | `speechStyle` 정규식이 따옴표 쌍을 가로지름 · 변수명 `rs` 가 DB row 와 충돌 | 매칭 결과 상위 5건을 원문과 눈으로 대조 |
| **C7** | **문서화된 예외 미구현** | 불변식 45 의 "enum·접두규약 예외" 를 안 넣어 14/14 오탐 | 불변식 문면의 괄호·예외 조항을 코드로 옮겼는가 |
| **C8** | **모드/맥락 무시** | `revealMode` 3종에 같은 잣대 → `indirect` 는 설계상 암시인데 위반 처리 | 대상에 모드·티어·경로 구분이 있으면 분해해서 판정 |

### 적용 규칙

1. **극단값은 검사기를 의심한다.** 100%·0%가 나오면 대개 C1~C2 다.
2. **위반 상위 3건은 반드시 원문 대조** 후 보고한다 (C6).
3. **판정 기준은 문서 인용과 함께** 적는다 (C4·C7).
4. 오탐을 고칠 때마다 위 "오탐 이력" 표에 추가한다.
