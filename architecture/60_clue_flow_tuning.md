# 60. Clue Flow Tuning — 흐름 점검 발견 4건 (워커 lost update + 자연스러움 3건)

> **목표**: 58·59 적용 후 단서 대사 흐름 점검(2026-07-04, 시나리오 7종 실측)에서 발견된 4건 수정.
> **선행**: architecture/58 (기록·서술 단일화) · architecture/59 (후속 안정화)
> **작성**: 2026-07-04
> **Status**: ✅ 구현됨 (라이브 재검증 통과)

---

## P0 — LLM 워커 runState 전체 되쓰기 lost update (정합성, 최우선)

### 실측 (점검 런 cede95d3)

빠른 연속 턴에서 t6·t7의 발견 기록이 소실되고 t8·t10에서 같은 fact가 재발견됨.
DB 최종 배열 순서 `[WAGE, LEDGER, ROUTE, SMUGGLE]`가 t8 이후 발견분만 반영 — t7↔t8 사이 wipe 입증.

### 원인

`llm-worker.service.ts`의 NpcAppearance(소개 롤백/제스처 축적)·ThemeRecord(narrativeThemes) 블록이
**턴 처리 시작 시점의 stale runState 스냅샷 전체**를 `.set({ runState })`로 되씀.
워커가 도는 사이(스트리밍 중) 플레이어가 다음 턴을 제출하면 그 턴의 모든 runState 변경
(discoveredQuestFacts, heat, trust, npcStates…)이 소실 — **Server is Source of Truth 위반**.
발생 조건: 스트리밍 스킵·선택지 연타·파티 4인 등 워커 완료 전 후속 턴 제출.

### 수정

`applyRunStatePatch(runId, label, patch)` 헬퍼 — 쓰기 직전 fresh runState를 재조회하고
워커 소유 필드만 그 위에 패치 후 저장. 두 블록 모두 전환.
(남는 위험은 ms 단위 순수 동시성 창뿐 — 초 단위 계통적 stale 쓰기는 제거.
완전 차단이 필요해지면 jsonb 부분 업데이트/버전 체크로 후속.)

### 재검증

동일 시나리오 재구동 — NPC 경로 발견 로그 중복 0건, DB 배열 = 발견 순서, 패치 에러 0.

---

## P1 — 주제 불일치 fallback 금지 (합리성)

### 실측 (S4)

하를런이 모르는 주제(마이렐 증거)를 물었는데 순서 fallback이 딴 단서(장부 소문)를 공개
→ 문답 불일치 + arch/46 인계 가이드("그건 ○○에게 물어보시오")가 questReveal에 가로채여 미발화.

### 수정

`selectRevealableFact`: 키워드 후보가 있으나 현재 NPC가 미보유면 **null 반환** (fallback 금지)
→ context-builder의 인계 가이드(mode B)가 자연 발화. 재검증: S4에서 questReveal 없음 + 인계 블록 발화 확인.

---

## P2a — 공개 턴 [단서 방향] 이월 (자연스러움)

### 실측 (S2)

연쇄 발견 구간에서 매 턴 `[이번 턴 NPC 공개] + [단서 방향 우연 연출]` 동시 발화 — 작위적 리듬.

### 수정

같은 턴에 questReveal이 있으면 directionHint를 부착하지 않고 `pendingQuestHint`를 유지해
다음 턴으로 이월. 최대 `DIRECTION_HINT_CARRY_MAX_TURNS`(3)턴, 초과 시 만료.
소비(정리)는 실제 부착 시점에 확정. 재검증: t9(공개 턴) 힌트 억제 → t10에서 이월 발화 확인.

---

## P2b — 비주제 fallback 확률 게이트 (자연스러움)

### 실측 (S5)

안부 인사(SUCCESS)만으로도 fallback 단서가 매턴 방출 — "묻지도 않았는데 술술".

### 수정

`matchedByTopic === false`인 공개는 `NON_TOPIC_FALLBACK_REVEAL_CHANCE`(35%) 확률 게이트.
**BRIBE/THREATEN은 면제** — 대가(금전/공포)를 치른 정보 요구. 상수는 quest-balance.config (불변식 30).
재검증: 잡담 턴 보류/통과가 확률적으로 발생 확인.

---

## 변경 파일 (server)

| 파일 | 변경 |
|------|------|
| `llm/llm-worker.service.ts` | applyRunStatePatch 헬퍼 + 2개 블록 전환 (P0) |
| `engine/hub/quest-progression.service.ts` | 주제 불일치 시 null (P1) |
| `turns/turns.service.ts` | directionHint 이월 + fallback 확률 게이트 (P2) |
| `engine/hub/quest-balance.config.ts` | 상수 2종 신설 (P2) |

## 부록 A — 사후 코드 리뷰(8앵글) 반영 (2026-07-04)

구현 후 전체 diff 코드 리뷰에서 확정된 결함/정리 사항과 조치:

| # | 발견 | 조치 |
|---|------|------|
| 1 | HUB 턴이 이월 힌트를 조기 삭제 (2앵글 교차 확인) — 발견↔복귀 사이 HUB 경유 시 [단서 방향] 소실 | HUB 만료 조건을 이월 창(`DIRECTION_HINT_CARRY_MAX_TURNS`) 기준으로 완화 |
| 2 | attach 시 무조건 정리가 같은 턴에 새로 쓰인 힌트(이벤트 경로 발견)를 소실 | `setAtTurn < turnNo`인 기존 힌트만 정리 — 신규 힌트 보호. 이월 의미 정정: 새 nextHint가 쓰이면 최신 우선(교체), 없으면 유지 |
| 3 | applyRunStatePatch의 잔여 ms 경합 창 — 빠른 연속 턴에서 힌트 이중 발화로 **실측** | CAS 격상: jsonb 동등 비교 WHERE + 3회 재시도, 충돌 시 soft 데이터 포기 |
| 4 | 공유 별칭("보스")이 부재 NPC를 STRONG 매칭 → whereabouts 안내가 이벤트 화자를 지움 | 별칭은 고유하거나 현장에 있을 때만 STRONG (matchParticleAll 동일), 회귀 스펙 추가 |
| 5 | [NPC 정보 보류] 블록의 인용 어구·제스처 예시 — LLM 원칙(anchor·어구 예시 금지) 위반 | 추상 가이드로 교체 |
| 6 | 한글 키워드 토크나이저 3중복 (드리프트 시 기록≠서술 데스싱크 재발 경로) | `common/text-utils.extractKoreanKeywords`로 단일화 |
| 7 | quest-balance 인라인 require 3개 (타입 미검증 — 키 변경 시 무음 undefined) | 톱레벨 import로 통일 |
| 8 | selectRevealableFact가 knownBy 결손 fact에서 throw → 퀘스트 패스 전체 스킵 | `(knownBy ?? [])` 방어 |

리뷰에서 반박(비결함 확인)된 것: 판정 npcId 체인 불일치 주장(양쪽 모두 payload 동기화로 동일 결과),
HINT_MODES 수정의 off-by-one 방향(정상 수정 확인), 파티 파이프라인 ui 필드 유실(경유 없음 확인).

## 남은 참고 사항 (미수정)

- 인계 가이드 topic 추출이 입력 첫 토큰(대개 NPC 호명)을 집는 문제 — 표시 품질 이슈, 별도 후속
- 키워드 모호성('장부' 4중첩)의 선택 우선순위/stage 인지 — 콘텐츠·사양 논의 후
- `extractTargetNpcFromInput` ↔ NpcResolver 이중 매처 통합 — arch/49 완성편
