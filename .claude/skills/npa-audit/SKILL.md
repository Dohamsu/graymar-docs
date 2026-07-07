# NPA 대화 품질 감사

`scripts/e2e/audit/audit.ts` 로 NPC 대화 시나리오를 자동 플레이하고, 5축 품질 점수(연결성·자유도·사람다움·차별화·톤일치)와 자동 검출(ERROR/WARNING)을 리포트로 받아 기준선과 대조한다. 설계: architecture/47, 메트릭 v2: architecture/55.

## 언제 사용

- NPC 대화엔진·프롬프트·LLM 파이프라인을 변경한 뒤 체감 품질 검증이 필요할 때
- 사용자가 "대화 품질 확인해줘", "NPA 돌려줘" 라고 요청할 때
- architecture/5x 계열 작업(대화 품질 개선)의 전/후 A-B 비교가 필요할 때

## 절차

### 1. 서버 확인

dev 서버(localhost:3000)가 살아있어야 한다. 없으면 `/restart-dev` 스킬로 기동.

```bash
curl -s http://localhost:3000/v1/version | head -c 120
```

### 2. 시나리오 실행

tsx 는 레포 전체에서 `quartz/node_modules/.bin/tsx` 에만 설치되어 있다 (2026-07-07 확인 — e2e README 의 `pnpm exec tsx` 는 server/client 에서 동작 안 함).

```bash
cd /Users/dohamsu/Workspace/graymar
./quartz/node_modules/.bin/tsx scripts/e2e/audit/audit.ts --scenario chat-edric
```

| 시나리오 | 목적 |
|---|---|
| `chat-edric` / `chat-harlun` / `chat-mairel` / `chat-ronen` / `chat-rat-king` | CORE NPC 개별 10턴 잡담 — personality·어체·인간미 |
| `dialog-handoff` | 같은 NPC 8턴 연속 — 잡담→fact→인계 모드 전환 자연스러움 (기본값) |
| `fact-progression` | 단서 발견 → 퀘스트 전환 흐름 |
| `npc-continuity` | NPC 연속성 (점프/화자 오귀속) |

옵션: `--output playtest-reports/foo` `--max-turns N` `--poll-timeout ms`.
소요 ~3~5분/10턴 (LLM 폴링 대기 포함). 회원가입부터 새 런을 만들므로 별도 준비 불필요.

### 3. 리포트 해석

`playtest-reports/audit_<scenario>_<timestamp>.md` 생성됨. 확인 순서:

1. **자동 검출 ERROR** — 0건 유지 필수. 1건이라도 있으면 회귀.
2. **5축 점수** — 아래 기준선과 축별 비교. ±0.3 이상 하락한 축은 회귀 의심.
3. **대화 흐름 표** — 어색한 턴을 직접 원문 대조 (regex 감지 = 위반 아님, audit-quality 원칙 준용).
4. **Pipeline Trace** — 점수 하락 턴의 프롬프트 블록 구성으로 원인 추적 (어떤 블록이 주입/누락됐는지).

### 4. 기준선 대조

같은 시나리오의 직전 리포트와 비교:

```bash
ls -t playtest-reports/ | grep "audit_chat-edric" | head -3
```

2026-07-07 기준선 (chat-edric, 대화엔진 개선 1~3 적용 전): 종합 3.68 — 연결성 3.90 / 자유도 3.85 / 사람다움 4.14 / 차별화 4.00 / **톤일치 2.50** / 사용자 응답률 56%. 톤일치·응답률이 당시 최약축이었다.

⚠️ **어미 일치율 비교 주의**: 2026-07-07에 메트릭 버그(HAOCHE "-소" 종결 누락 + 말끝 흐림 파편 집계 — arch/55 부록 A)를 수정했다. 그 이전 리포트의 어미 일치율(45~73%)은 수정 후 값(88~100%)과 직접 비교 불가. 수정 후 기준선: 로넨 100 / 쥐왕 95 / 하를런 94 / 마이렐 91 / 에드릭 88%.

## 주의

- **1세션만** 실행 (동시접속 테스트 불필요 — 사용자 피드백).
- 실제 LLM 호출 비용이 발생한다. 같은 검증에 시나리오 1~2개면 충분.
- 리포트의 LATENCY avg 가 10초를 넘으면 품질과 별개로 반드시 보고 (레이턴시 10초 미만 필수 전제).
- 감지 결과를 원문 대조 없이 그대로 보고하지 않는다 (CLAUDE.md 품질 검사 워크플로우).
- 완료 시 Slack `✅` 알림 (점수 요약 포함).
