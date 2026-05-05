# 37. LLM 폴링 → 스트리밍 전환 이슈 요약

> 기존: LLM Worker가 서술을 **한 번에 완성**하고 클라가 2초 폴링으로 수신.
> 현재: OpenRouter `stream: true` + SSE 브로커로 **토큰 단위 실시간 전송**.
> 전환 과정에서 노출된 문제와 각 해결 + 최종 상태를 간략 정리.

---

## 0. 기존 (폴링) vs 현재 (스트리밍) 한눈에

| | 폴링 (Before) | 스트리밍 (After) |
|---|---|---|
| 서버 LLM 호출 | `stream: false`, 서술 완료 후 DB 저장 | `stream: true`, 토큰 도착마다 SSE 브로커로 emit |
| 클라 수신 | 2초 폴링 → `turns/:n` 조회 | SSE `turns/:n/stream` 실시간 구독 |
| 렌더 | 서술 전체를 받아 후처리 → 타이핑 재생 | 실시간 토큰 → StreamTyper 점진 렌더 + 완료 후 최종본 교체 |
| TTFB 체감 | 5~17초 | 0.5~2초 |
| 타이핑 시작 | 전체 수신 후 | 첫 토큰 도착 즉시 |

---

## 1. 전환 과정에서 발생한 문제 리스트

### 1-1. StreamTyper `onComplete` 중복 호출 → 내레이터 텍스트 사라짐
**증상**: 타이핑이 끝나는 순간 내레이터 박스의 본문이 통째로 빈 문자열이 됨. (버그 `d8b9de24`, `8d469994`)
**원인**: useEffect가 `typedLength >= buffer.length && isDone` 조건에서 `onComplete`를 매번 호출할 수 있었음. 1회차가 `streamTextBuffer=''`로 초기화한 직후 같은 tick의 2회차가 실행되어 messages.text를 빈 문자열로 덮어씀.
**해결**: 양방향 멱등성 가드
- 트리거: `completedRef` once-guard → `onComplete` 1회만 호출
- 핸들러: 진입 시 `!store.isStreaming || finalText.length === 0` 이면 early return
**결과**: 완료 전환 순간 본문 사라짐 재현 불가.

### 1-2. 타이핑 중 vs 완료 후 스타일 점프
**증상**: 타이핑 중엔 기본 폰트·크기로 보이다가 완료 순간 `font-narrative` / `leading-[1.75]`로 급전환.
**원인**:
- 완료 경로는 `<div className="font-narrative leading-[1.75]" fontSize>` 래퍼 사용
- 스트리밍 경로의 StreamTyper는 래퍼 없이 직계 자식 + 내부 인라인 `<span leading-relaxed>`
**해결**:
- `renderNarrationLines` 헬퍼로 타이핑 중/후 모두 `\n` → `<span className="block">` + 빈 줄 `h-3` 공통 처리
- StreamTyper 호출부도 완료 경로와 같은 부모 래퍼로 감쌈
**결과**: 전환 순간 폰트·크기·line-height 동일 → 육안 점프 구분 불가.

### 1-3. 문장별 줄바꿈
**증상**: 스트리밍 경로 서술의 모든 문장이 한 줄씩 독립 표시.
**원인**: 서버 `stream-classifier`가 `.!?` 뒤 공백/개행 기준으로 문장 단위 emit → 클라 `game-store`가 매 flush마다 `analyzedBuffer + '\n' + analyzed` 로 연결 → 문장별 `\n` 누적.
**해결**:
- `analyzeText` 재작성: 입력을 빈 줄 기준 문단으로 분할, narration 라인은 공백 병합(한 덩어리), 대사 라인은 독립 줄 유지
- `appendAnalyzed(current, next)` 헬퍼: 이전 버퍼 끝이 `\n`이면 그대로, 아니면 공백으로 연결
**결과**: 스트리밍 렌더 시 문장들이 문단으로 자연스럽게 이어짐. LLM 원문 `\n\n` 문단 경계만 보존.

### 1-4. 대사 내부 Raw 마커 잔해
**증상**: DialogueBubble 말풍선 안에 `[로넨|/npc-portraits/ronen.webp] 정말 감사합니다...` 같이 `@` 프리픽스 없는 마커 잔해 노출. (버그 `fc14ed2b`)
**원인**: LLM이 이중 마커 생성 시 `@[로넨|URL] "@[로넨|URL] 대사..."`. 외부는 `B-2.5 regex`가 치환하지만 큰따옴표 내부 잔해는 뒤에 `"`가 없어 어느 regex에도 매칭 안 됨. 이후 `@`만 떨어지고 `[이름|URL]`이 대사 텍스트로 남음.
**해결**:
- 서버 `llm-worker.service.ts` 5.10.5 단계 추가: `deduplicateAliases` 직후 큰따옴표 쌍 내부에서 `@?[이름|URL]` / `@[이름]` 제거
- 클라 `cleanResidualMarkers` #6 방어 regex: `(^|[^@])\[[^\]|]+\|/npc-portraits/[^\]]+\]` → `$1` (정상 `@` 마커 보호)
**결과**: 50턴+ 벤치에서 `rawMarkerLeak_total = 0`.

### 1-5. BG NPC 어체 규칙이 프롬프트에 주입 안 됨
**증상**: 거리 아이(BANMAL 규정)가 반복적으로 `"~것이오"`, `"~어요"` 출력. (버그 관찰 + 감사 확인)
**원인** (스트리밍 고유 문제는 아니지만 동시기 발견):
- `relevantNpcIds` 가 `targetNpcIds`(Player-First 타겟 1~2명)만 포함
- BG NPC 는 `NPC_LOCATION_AFFINITY` 에 미등록 → `npcPostures` 자체에 없음
- 발화자여도 `[NPC 대화 자세]` 블록에 어체 규칙이 안 들어감
**해결** (`prompt-builder.service.ts`):
- `sr.ui.speakingNpc.npcId` / `actionContext.primaryNpcId` 에서 실제 발화자 추출
- `relevantNpcIds`에 강제 포함 + `npcPostures`에 없으면 기본 `CAUTIOUS` 보조 주입
- `effectivePostures` 로 `postureLines` 순회
**결과**: 3런 29턴 0% 주입 → 20턴 벤치 10/10 (100%) 주입. 실제 BG 대사 어체 일치율 큰 폭 개선.

### 1-6. 스트리밍과 JSON 모드 동시 사용 불가
**증상**: `LLM_JSON_MODE=true` 상태에서 스트리밍하면 JSON 원문 조각이 노출됨.
**원인**: JSON 모드는 완성된 JSON 덩어리 후 파싱 필요, 스트리밍은 조각 단위 표시 전제.
**해결**: `LLM_JSON_MODE=true` 일 때 클라의 "스트리밍 중 표시"를 차단 (폴링 fallback 유지). 설계 문서에 "동시 활성 금지" 불변식 명시.
**결과**: 충돌 회피. 단, 향후 Partial JSON 파서 도입 시 재검토 필요.

### 1-7. 스트리밍 중 불완전 `@` 마커 노출
**증상**: 토큰이 `@[로넨` 까지만 도착했을 때 화면에 그대로 표시.
**원인**: 스트리밍 중 조각을 실시간 렌더하는 한계.
**해결**: `cleanResidualMarkers` 초기 단계에서 불완전 패턴 필터
```ts
text = text.replace(/@\[[^\]]*\]/g, '');   // 완성된 @[...]
text = text.replace(/@\[[^\]]*$/g, '');    // 잘린 @[... 패턴
text = text.replace(/@마커/g, '');         // LLM이 출력한 리터럴
```
**결과**: 타이핑 도중 `@` 로 시작하는 파편이 본문에 보이지 않음. 완료 후 정상 마커만 DialogueBubble로 변환됨.

### 1-8. TTFT 측정 도구 부재
**증상**: 폴링 환경에서는 응답 시작 시각을 알기 어려움. 스트리밍 전환 후 성능 비교 수치가 없음.
**해결**: `scripts/bench-models.py` 신규 — SSE 엔드포인트에 직접 연결해 첫 토큰(TTFT) / 마지막 토큰(TTLT) / 서버 측 `llm_token_stats.latencyMs` 를 턴 단위로 수집, `p50/p90/mean/max` 산출.
**결과**: 26B vs 31B 비교, 수정 전후 회귀 측정에 실사용. 최신 26B 20턴 벤치: TTFT p50 4.4s / TTLT p50 8.8s / mean 9.1s (< 10s 목표 통과).

### 1-9. 재현 분석을 위한 맥락 데이터 부족
**증상**: 버그 리포트만으로 스트리밍 상태·뷰포트·API 레이턴시 등 재현 맥락 추적 불가.
**해결**: `bug_reports` 테이블에 `client_snapshot` / `network_log` / `client_version` 컬럼 추가. 클라 `BugReportModal` 에서 스냅샷·DOM 요약·네트워크 타임라인·빌드 해시 자동 수집.
**결과**: 이후 버그 리포트에서 서버/클라 버전 짝 즉시 판별 + 재현 1건에 필요한 증거가 JSON 하나에 모임.

---

## 2. 이슈 → 해결 요약표

| # | 이슈 | 해결 위치 | 최종 상태 |
|---|------|---------|-----------|
| 1-1 | 완료 순간 텍스트 사라짐 | client StoryBlock (once-guard + 핸들러 early return) | ✅ 재현 불가 |
| 1-2 | 스타일 점프 | client StoryBlock (부모 래퍼 통일 + renderNarrationLines) | ✅ 육안 구분 불가 |
| 1-3 | 문장별 줄바꿈 | client game-store (analyzeText + appendAnalyzed) | ✅ 문단 자연 병합 |
| 1-4 | 대사 내부 raw 마커 | server llm-worker 5.10.5 + client cleanResidualMarkers #6 | ✅ 21턴 벤치 0건 |
| 1-5 | BG NPC 어체 규칙 누락 | server prompt-builder (발화자 강제 포함) | ✅ 100% 주입 |
| 1-6 | JSON 모드 × 스트리밍 충돌 | client 표시 차단 + 문서 불변식 | ✅ 충돌 회피 |
| 1-7 | 불완전 `@` 마커 노출 | client cleanResidualMarkers 초기 단계 | ✅ 표시 억제 |
| 1-8 | TTFT 측정 도구 부재 | scripts/bench-models.py | ✅ 회귀 측정 도구 확보 |
| 1-9 | 재현 분석 맥락 부족 | DB bug_reports 확장 + 클라 수집 로직 | ✅ 자동 수집 |

---

## 3. 최종 성능 / 품질 수치 (2026-04-17 기준, 26B 20턴 벤치)

| 항목 | 값 |
|------|-----|
| TTFT | p50 4,381ms · p90 7,506ms · mean 4,701ms |
| TTLT | p50 8,805ms · p90 13,656ms · mean 9,141ms |
| 서버 레이턴시 (token_stats) | p50 4,773ms · mean 5,273ms |
| 턴당 비용 | $0.00076 |
| 따옴표 짝 홀수 턴 | 0 / 21 |
| Raw 마커 누수 | 0 |
| NPC_ID 원문 누출 | 0 |
| "당신은" 서술 시작 | 2.1% (목표 < 10%) |
| BG NPC 어체 규칙 주입률 | 100% (10 / 10) |
| BG NPC 대사 규정 이탈 | 0건 |

---

## 4. 참조

- [[architecture/35_llm_streaming|llm streaming]] — 스트리밍 설계 + Dual-Track 구현 + 후속 수정 섹션(A~E)
- [[architecture/36_llm_pipeline_changelog_20260417|llm pipeline changelog 20260417]] — 동일 이슈의 상세 기술 문서
- `scripts/bench-models.py` — TTFT/TTLT 벤치마크
- `scripts/verify-bench-quality.py` — 품질 감사
- 커밋: server `ec1018b` / `68d29a2` / `b49dee0` · client `64849be` / `03e938b` / `cb26b2c` / `8685c36` / `6a8a4dd`
