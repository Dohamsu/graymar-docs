# 멀티 레포 커밋

변경된 파일을 레포별로 분리하여 빌드 검증 → 커밋 → 푸시 → Slack 알림.

## 절차

### 1단계: 빌드 검증
```bash
cd server && pnpm build
cd client && pnpm build
```
빌드 실패 시 사용자에게 보고하고 중단.

### 2단계: 변경사항 확인
각 레포에서 `git status`와 `git diff`로 변경 내용 파악:
- `server/` — 서버 코드
- `client/` — 클라이언트 코드
- 루트 (`mdfile`) — 설계 문서, 리포트, CLAUDE.md 등

### 3단계: 설계 문서 동기화
코드 수정에 따라 업데이트가 필요한 설계 문서가 있는지 확인:
- `guides/03_hub_engine_guide.md` — HUB 엔진 변경 시
- `guides/04_llm_memory_guide.md` — LLM/메모리 변경 시
- `guides/05_runstate_constants.md` — RunState 구조 변경 시
- `architecture/*.md` — 아키텍처 수준 변경 시
- `CLAUDE.md` — 불변식/enum/phase 변경 시

### 4단계: 스테이징 & 커밋
변경사항이 있는 각 레포에서 커밋:

```bash
# 서버
cd server
git add {수정된 파일들}
git commit -m "커밋 메시지

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"

# 클라이언트 (변경 시)
cd client
git add {수정된 파일들}
git commit -m "커밋 메시지

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"

# 문서 (변경 시)
git add {수정된 파일들}
git commit -m "docs: 커밋 메시지

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

커밋 메시지 형식:
- 서버: `fix:` / `feat:` / `refactor:` + 핵심 변경 1줄 요약
- 클라이언트: `fix:` / `feat:` + 핵심 변경 요약
- 문서: `docs:` + 변경 요약

### 5단계: 푸시
```bash
cd server && git push origin main
cd client && git push origin main  # 변경 시
git push origin main               # 문서 변경 시
```

### 6단계: Slack 알림
```bash
curl -s -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"✅ 커밋 완료 — [변경 요약]\"}" \
  "$(grep SLACK_WEBHOOK_URL /Users/dohamsu/Workspace/mdfile/.env | cut -d= -f2)"
```

## 주의사항
- `.env`, credentials 등 민감 파일은 커밋하지 않는다
- 빌드 실패 시 커밋하지 않는다
- pre-commit hook 실패 시 새 커밋을 만든다 (amend 금지)
