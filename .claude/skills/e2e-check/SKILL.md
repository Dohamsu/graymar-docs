# E2E 스모크 + 레이턴시 게이트

`scripts/e2e/` 정본 스크립트로 회원가입→게임 플레이 전체 플로우(smoke)와 LLM 레이턴시 분포(perf)를 검사한다. 배포 전·파이프라인 변경 후의 "게임이 실제로 돌아가고, 10초 안에 응답하는가" 게이트.

## 언제 사용

- 턴 파이프라인·LLM 워커·스트리밍 등 런타임 동작을 바꾼 뒤 (정적 검증만으로 부족할 때)
- 배포 전 최종 확인, 또는 프로덕션(api.dimtale.com) 상태 점검
- 사용자가 "E2E 돌려줘", "제대로 도는지 확인해줘" 라고 요청할 때 (테스트는 E2E Playwright 이 기본)

## 절차

### 1. 서버·클라 기동 확인

localhost:3000(서버) + 3001(클라)이 필요하다. 없거나 오래된 빌드면 `/restart-dev` 스킬로 재기동.

### 2. smoke (~2분) — 기본 플로우

tsx 는 `quartz/node_modules/.bin/tsx` 에만 설치되어 있다 (2026-07-07 확인).

```bash
cd /Users/dohamsu/Workspace/graymar
./quartz/node_modules/.bin/tsx scripts/e2e/smoke.ts
```

- 회원가입 → 3턴 → API 기본 플로우 + 브라우저 렌더 검증
- 브라우저 없이 API만: `SMOKE_NO_BROWSER=1` 접두

### 3. perf (~3분) — 레이턴시 게이트

```bash
./quartz/node_modules/.bin/tsx scripts/e2e/perf.ts
```

- 10턴 LLM latency p50/p75/p95 출력
- **판정 기준: p95 < 10,000ms.** 스크립트가 10초 초과 턴을 자체 경고한다 — 위배 시 품질과 별개로 반드시 보고 (레이턴시 10초 미만은 UX 기본 전제). 원인 후보: OpenRouter provider 라우팅(sort:latency 적용 여부), nano 직렬 호출 증가, fallback 모델 전환.

### 4. 필요 시 심화

```bash
TURNS=20 ./quartz/node_modules/.bin/tsx scripts/e2e/full-run.ts   # 풀 런 + V1~V9 assert (~10분)
./quartz/node_modules/.bin/tsx scripts/e2e/regression.ts          # UI 회귀: 오프닝/프롬프트 누출/뎁스 전환 (~1분)
```

full-run 리포트는 `playtest-reports/e2e_full_*.json` 저장. 옵션: `PRESET=SMUGGLER GENDER=female CHOICE_RATE=0.5`.

### 5. 프로덕션 대상 실행

```bash
SERVER_BASE=https://api.dimtale.com/v1 CLIENT_BASE=https://dimtale.com \
  ./quartz/node_modules/.bin/tsx scripts/e2e/smoke.ts
```

프로덕션에는 smoke 만 — full-run/perf 는 실 사용자 트래픽·비용에 영향.

## 판정 요약

| 검사 | 통과 기준 |
|---|---|
| smoke | 전 단계 통과 (가입/턴/렌더), 콘솔 에러 0 |
| perf | p95 < 10초, 10초 초과 턴 0건 |
| regression | 오프닝 1회 / 프롬프트 누출 0 / 뎁스 전환 정상 |

## 주의

- **1세션만** 실행 — 동시접속 테스트는 하지 않는다 (사용자 피드백).
- 실제 LLM 비용이 발생한다. smoke+perf 조합이 기본, full-run 은 필요할 때만.
- 대화 "품질" 평가는 이 스킬이 아니라 `/npa-audit` 담당 — 여기는 동작·성능 게이트.
- 완료 시 Slack `✅` 알림 (p95 수치 포함).
