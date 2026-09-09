# TODOS

## 최우선 — 거대 파일 4개 조각내기 (2026-09-08 결정, 순서대로)

재작성 대신 유지보수를 택한 근거와 설계는 `architecture/114_llm_worker_stage_pipeline.md`. 각 단계는 동작 보존(컷-페이스트 + 기계 대조 + 골든 스냅샷 + 전체 jest + 스모크), 서비스 무중단.

- [x] **T1. llm-worker 를 단계 파이프라인으로** (2026-09-08 Phase 1·2 완료, arch/114 §2-3, server `3656c03` 커밋·배포) — `processTurnInner` 1,955줄을 락→컨텍스트→nano 사전결정→프롬프트→호출→후처리→커밋→사후 단계 메서드로, 이어 후처리 헬퍼 군(마커 삽입 1,105 등)을 별도 서비스로. 진행: arch/114 §5
- [x] **T2. prompt-builder 를 블록 레지스트리로** (2026-09-08 Phase A 완료, arch/114 §7, server `3656c03`) — `[헤더]` 블록마다 "언제 켜지는가·무엇을 넣는가" 를 등록해 블록 간 모순(참고 선택지↔이동 지시, 정보 전달↔잡담)을 표에서 검출
- [x] **T3. RunState 타입 슬라이스** (2026-09-08 완료, arch/114 §8, server `3656c03`) — 워커 CAS 역류가 소프트 상태만 건드린다는 불변식 2 를 타입으로 강제

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
