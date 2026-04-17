# 최신 버그 리포트 분석

DB의 `bug_reports` 테이블에서 최신 N건을 조회하고, `client_snapshot`·`ui_debug_log`·`network_log`를 연결해 근본 원인을 추적하는 분석 템플릿.

## 언제 사용

- 사용자가 "최신 버그 리포트를 분석해줘"라고 요청
- 재현 맥락(스트리밍 상태·뷰포트·API 레이턴시)을 확인해야 할 때
- 유사 증상이 반복될 때 server_version / client_version 짝을 보고 배포 불일치 판별

## 절차

### 1. 최신 목록 조회 (기본 1건, 필요 시 N건)

```bash
docker exec textRpg-db psql -U user -d textRpg -c "
  SELECT id, turn_no, category, description,
         created_at, server_version, client_version,
         (client_snapshot IS NOT NULL) AS has_snapshot,
         (network_log IS NOT NULL) AS has_network
  FROM bug_reports
  ORDER BY created_at DESC
  LIMIT 1;"
```

버전 짝 확인: `server_version != client_version` 또는 예상한 최신 해시와 다르면 브라우저 PWA 캐시/배포 미반영 가능성 즉시 의심.

### 2. 맥락 데이터 덤프

대상 ID가 정해지면 아래를 순서대로 꺼내서 분석 근거로 사용:

```bash
# 메시지 상세
docker exec textRpg-db psql -U user -d textRpg -At \
  -c "SELECT recent_turns::text FROM bug_reports WHERE id = '<ID>';"

# 게임 런타임 스냅샷
docker exec textRpg-db psql -U user -d textRpg -t \
  -c "SELECT jsonb_pretty(client_snapshot) FROM bug_reports WHERE id = '<ID>';"

# UI 이벤트 타임라인
docker exec textRpg-db psql -U user -d textRpg -t \
  -c "SELECT jsonb_pretty(ui_debug_log) FROM bug_reports WHERE id = '<ID>';"

# 네트워크 호출 타임라인 (있을 때만)
docker exec textRpg-db psql -U user -d textRpg -t \
  -c "SELECT jsonb_pretty(network_log) FROM bug_reports WHERE id = '<ID>';"
```

### 3. 분석 체크리스트

사용자 기술 → 코드 경로를 끊지 말고 단계별로 확인:

1. **재현 조건**: phase / currentNodeType / currentTurnNo / locationId
2. **타이밍**: ui_debug_log 의 `t` 값 흐름 — flushNarrator → StreamTyper → onComplete → flushPending 중 어디서 예상과 다름?
3. **상태 점프**: loading/typed/isStreaming 플래그가 기대와 다르게 전환되는 구간
4. **네트워크**: 문제 직전 실패·지연 API (status != 200, latencyMs 급증)
5. **LLM 원문**: `recent_turns[].messages[].text` 에 마커/따옴표/줄바꿈 이상
6. **버전 불일치**: server_version / client_version 짝이 최신 main 과 다른지
7. **DOM**: client_snapshot.dom.renderedChoiceButtonCount / renderedDialogueBubbleCount / viewport 가 기대와 맞는지

### 4. 보고 형식

- 증상 요약 → 결정적 근거(로그 인용) → 근본 원인 → 수정 방향 후보 A/B
- 이미 수정된 영역이면 "가드 동작 확인 ✅" 로 표기
- 수정 진행 여부는 사용자 결정 대기 (자동 작성 금지)

## 참조

- 버그 리포트 수집 확장 설계: `architecture/35_llm_streaming.md` §후속 수정 E
- DTO / 서비스: `server/src/runs/dto/create-bug-report.dto.ts`, `server/src/runs/bug-report.service.ts`
- 클라 수집: `client/src/components/ui/BugReportModal.tsx`, `client/src/lib/network-logger.ts`, `client/src/lib/ui-logger.ts`
