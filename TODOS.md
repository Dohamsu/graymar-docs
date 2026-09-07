# TODOS

소유자 수동 작업 대기 목록. 완료 시 항목을 지운다. (자세한 배경은 로컬 `.gstack/security-reports/2026-09-07-cso-report.md` — gitignored)

## 보안 (2026-09-07 감사 후속, 서비스 동작과 무관 — 시간 날 때)

- [ ] **DB 자격증명 회전** — 에이전트 실행이 차단돼 소유자가 직접. `docker-compose.yml` 은 이미 `server/.env` 의 `POSTGRES_PASSWORD` 를 참조한다.
  ```bash
  cd /Users/dohamsu/Workspace/graymar
  NEW=$(openssl rand -hex 24); echo "$NEW"
  docker exec textRpg-db psql -U user -d textRpg -c "ALTER USER \"user\" WITH PASSWORD '$NEW'"
  # server/.env 의 DATABASE_URL 비밀번호 부분 + POSTGRES_PASSWORD 두 줄을 $NEW 로 교체
  launchctl kickstart -k "gui/$(id -u)/com.graymar.server" && sleep 5 && curl -s http://localhost:3000/v1/version
  ```
- [ ] **Slack Incoming Webhook 재발급** — Slack 앱 설정에서 기존 웹훅 삭제 → 새로 발급 → 루트 `.env` `SLACK_WEBHOOK_URL` 교체 (`scripts/health-monitor.py`·`bug-monitor.py` 가 읽음).
- [ ] **미사용 OpenRouter API 키 revoke** — openrouter.ai Keys 에서 현재 `server/.env` 에 없는 키 정리.
- [ ] (선택) `/tmp/graymar-server.log` 를 `~/Library/Logs` + newsyslog 회전으로 이전 — 감사 부록 LOW.
- [ ] (선택) `gstack` 업그레이드 (`/gstack-upgrade`, 1.60.1 → 1.81.0).
