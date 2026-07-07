# 서버 변경 회귀 검증

서버 코드 변경 후 빌드 + 전체 테스트 + 변경 파일 린트를 한 번에 돌리고, **기존 실패와 신규 실패를 stash 대조로 분리**해서 내 변경이 깨뜨린 것만 보고한다. CLAUDE.md "빌드 검증" 규칙의 정본 절차.

## 언제 사용

- `server/src` 를 수정한 모든 작업의 마무리 단계 (기능 구현, 버그 수정, 리팩터)
- 테스트 실패가 내 변경 탓인지 기존 이슈인지 판별해야 할 때
- 사용자가 "검증해줘", "빌드 확인해줘" 라고 요청할 때

## 절차

### 1. 빌드

```bash
cd /Users/dohamsu/Workspace/graymar/server && pnpm build
```

### 2. 전체 테스트 (~2초, 전체 실행이 기본)

```bash
pnpm test
```

특정 스위트만: `pnpm jest --testPathPatterns='패턴1|패턴2'`
⚠️ jest 30 — `--testPathPatterns` (복수형). 구형 `--testPathPattern` 과 `pnpm jest -- --...` 전달 방식은 동작하지 않는다.

### 3. 실패 시 기존/신규 분리 (핵심)

실패가 나오면 변경 전 코드에서 같은 스펙을 돌려 대조:

```bash
git stash -q && pnpm jest --testPathPatterns=<실패한스펙> 2>&1 | tail -5; git stash pop -q
```

- 변경 전에도 실패 → 기존 이슈. 고치지 말고 보고만 한다 (근본 원인 조사 없이 표면 수정 금지).
- 변경 전엔 통과 → 내 변경이 원인. 수정 후 재검증.

### 4. 린트 — 변경 파일만

```bash
git status --short   # 변경 파일 확인
npx eslint <변경 파일들만 나열>
```

⚠️ `pnpm lint` 는 레포 전체 `--fix` 라 무관한 파일까지 포맷팅해 diff 를 오염시킨다. 실수로 돌렸으면 무관 파일은 `git checkout -- <파일>` 로 원복. 여기서도 에러가 나오면 3번과 같은 stash 대조로 기존/신규를 분리한다.

### 5. 클라이언트 변경이 있으면

```bash
cd /Users/dohamsu/Workspace/graymar/client && pnpm build
```

서버만 변경했으면 클라 빌드는 생략 가능 (변경 없음을 근거로 명시).

## 알려진 기준선 (2026-07-07)

신규 실패만 잡기 위한 기존 이슈 목록 — 아래는 **변경 전에도 실패**:

- `llm/stream-classifier.service.spec.ts` 2건 — buildCandidates 짧은 호칭("재무관"/"회계사") 후보 기대값 불일치
- 레포 전역 lint 기존 에러 다수 — turns.service unused vars 4건(isNameRevealed 등), llm-worker unsafe-any 계열, common no-control-regex 등

이 목록과 다른 실패/에러가 나오면 그것이 신규다. 기준선이 바뀌면(기존 이슈 수정 등) 이 섹션을 갱신한다.

## 주의

- 검증 통과 ≠ 커밋. 커밋/푸시는 사용자가 명시 요청할 때만.
- 테스트 실패를 숨기지 않는다 — 기존 이슈라도 보고에 한 줄 남긴다.
- 유의미한 작업 완료면 Slack `✅` 알림 (검증 결과 요약 포함).
