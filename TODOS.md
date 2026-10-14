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
- [x] ~~(선택) `/tmp/graymar-server.log` 회전~~ — 2026-10-14 완료: `scripts/rotate-server-log.sh` + launchd `com.graymar.server-logrotate`(매시, 200MB 초과 시 gzip 사본·보존 4, 사본 `scripts/launchd/`). 위치 이전(`~/Library/Logs`)은 안 함 — newsyslog 는 sudo 가 필요하고 launchd append 모드라 copytruncate 로 충분 (arch/144 §16).

## 전투 토픽 스택 (2026-10-14 소유자 지시 — 수정 보류, 나중에 몰아서 진행)

전투 관련 이벤트·트리거·전투 돌입 전환은 발견해도 고치지 않고 여기에만 쌓는다. 다른 작업이 전투 경로에 걸리면 전투 경로는 종전 동작으로 남기고 적는다.

- [ ] **전투 돌입 턴의 서술이 라이브에서 안 보임** (2026-10-14, arch/144 §9) — 장소에서 행동이 전투를 일으키면(`location-turn` → `nextNodeType: 'COMBAT'` 전환) 그 행동 턴의 서술은 생성·과금되지만, 클라가 전환 즉시 전투 진입 턴 서술만 요청해 화면에 안 나온다(이어하기 복원 때만 보임). 거점·장소 이동은 "서술 먼저 보여 주고 전환"(클라 `pendingTransition`)으로 고쳤으나 COMBAT 은 `deferTransition` 에서 제외해 종전 동작 유지. 몰아서 진행 때: 보여 줄지(A) / 서술 생략할지(B) 결정 → 클라 조건 한 줄 또는 서버 skipLlm.
- [ ] **`compoundFight` 스트림 보류 사유** (arch/144 §2·§7) — "밀치고 주먹" 복합 공격 턴은 여전히 완료 때 일괄 표시. 관측 0건.
