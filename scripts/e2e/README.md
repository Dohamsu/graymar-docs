# scripts/e2e — 정본 E2E 테스트

이전 26개 `scripts/e2e-*.ts`를 4개 정본으로 통합. 레거시는 `scripts/_e2e-legacy/`.

## 파일

| 파일 | 소요 | 목적 |
|---|---|---|
| `_helpers.ts` | — | ApiClient · Playwright 유틸 · V1~V9 검증 라이브러리 |
| `smoke.ts` | ~2분 | 회원가입 → 3턴 → API 기본 플로우 검증 (+ 선택적 브라우저 렌더) |
| `full-run.ts` | ~10분 | 35턴 풀 엔딩 런 + V1~V9 assert + 성능 메트릭 + JSON 저장 |
| `perf.ts` | ~3분 | 10턴 LLM latency 분포 (p50/p75/p95) + 10초 기준 검사 |
| `regression.ts` | ~1분 | UI 회귀 (타이틀 오프닝 세션 1회 / 프롬프트 누출 / 뎁스 전환) |

## 실행

```bash
# 로컬 개발 (기본)
pnpm exec tsx scripts/e2e/smoke.ts
pnpm exec tsx scripts/e2e/full-run.ts
pnpm exec tsx scripts/e2e/perf.ts
pnpm exec tsx scripts/e2e/regression.ts

# 프로덕션 대상
SERVER_BASE=https://api.dimtale.com/v1 CLIENT_BASE=https://dimtale.com \
  pnpm exec tsx scripts/e2e/smoke.ts

# 옵션
TURNS=20 pnpm exec tsx scripts/e2e/full-run.ts
PRESET=SMUGGLER GENDER=female pnpm exec tsx scripts/e2e/full-run.ts
HEADLESS=false pnpm exec tsx scripts/e2e/regression.ts
SMOKE_NO_BROWSER=1 pnpm exec tsx scripts/e2e/smoke.ts
```

## 환경 변수

| 변수 | 기본 | 설명 |
|---|---|---|
| `SERVER_BASE` | `http://localhost:3000/v1` | 서버 API 베이스 |
| `CLIENT_BASE` | `http://localhost:3001` | 클라이언트 베이스 |
| `HEADLESS` | `true` | 브라우저 숨김 (false = 보이게) |
| `TURNS` | 35 / 10 | 턴 수 (full-run / perf) |
| `PRESET` | `DESERTER` | 프리셋 ID |
| `GENDER` | `male` | 성별 |
| `LOC_TURNS` | 4 | 장소당 체류 턴 (full-run) |
| `CHOICE_RATE` | 0.3 | CHOICE 선택 확률 (full-run) |
| `SMOKE_NO_BROWSER` | — | `1` 이면 브라우저 스킵 (smoke) |
| `OUT` | `playtest-reports/e2e_full_*.json` | full-run 리포트 경로 |

## 검증 체계 (_helpers.ts · verifyRun)

| | 대상 |
|---|---|
| V1 | Incidents 활성 여부 |
| V2 | NPC encounterCount |
| V3 | NPC posture 누락 |
| V4 | 감정축 (trust/fear) 활성 |
| V5 | structuredMemory (visitLog) |
| V6 | resolveOutcome 포함 턴 |
| V7 | 프롬프트 누출 (9 regex) |
| V8 | NPC 정합성 (소개 카드 ↔ 서술 @마커) |
| V9 | 서술 품질 (단어 반복 3턴 윈도우) |

V9는 풍선효과로 자주 실패 — critical fail로 처리 안 함 (exit code 영향 X).

## 권장 워크플로우

- **PR 제출 전** → `smoke`
- **서버 변경 후** → `smoke` + `full-run`
- **LLM/프롬프트 튜닝** → `full-run` + JSON diff
- **클라이언트 배포 후** → `regression`
- **성능 벤치마크** → `perf`

## 레거시 26개 → 이 4개 매핑

| 레거시 | 대체 |
|---|---|
| e2e-portfolio.ts (스크린샷 4종) | 필요 시 별도 script로 재작성 (정본 아님) |
| e2e-combat-* (8종) | 전투 시나리오는 현재 정본 미포함 — 필요 시 추가 |
| e2e-ending-* | `full-run`의 엔딩 섹션 |
| e2e-journey-archive | `regression`에 추가 가능 |
| e2e-inventory / equip / drop-toast | `regression` 확장 대상 |
| e2e-sudden-action / sudden-screenshot | `regression` 확장 대상 |
| e2e-news-test / news-ui | 필요 시 별도 |
| e2e-char-tab / continue / narrative / paragraph-check | `full-run` 또는 `regression` |
| e2e-landing-capture | 필요 시 별도 |

## 레거시 복원

```bash
cp scripts/_e2e-legacy/e2e-portfolio.ts scripts/e2e-portfolio.ts
```
