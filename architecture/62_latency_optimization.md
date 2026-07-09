# 62. LLM 턴 레이턴시 최적화 (2026-07-09)

> **전제**: 레이턴시 10초 미만 필수 (UX 기본 전제). NPA 감사 실측 avg 13~19초, p95 41~51초.
> **상태**: ✅ 구현됨 (#1~#4)

## 1. 조사 — 병목은 메인 LLM이 아니라 nano 직렬 체인

DB 95턴 통계 + 서버 로그 7사이클 타임라인 분해 (2026-07-09):

| 단계 | 소요 | 비고 |
|---|---|---|
| Intent 파서 (nano, 동기) | ~1.0s | 턴 응답 전 |
| ChallengeClassifier (nano, 동기) | ~0.5s | 회색지대만 LLM |
| 워커 픽업(1초 폴링) + 컨텍스트 빌드 | ~1.0s | |
| Track 1 NanoEventDirector | ~2.0s | |
| NpcReactionDirector | ~1.6s | Track 1 뒤 직렬 |
| **메인 LLM (Gemma 4)** | **4.2s** (p50 3.6 / p95 7.3) | 준수 |
| 후처리 | ~0.5s | regex+DB |
| Track 2 선택지 nano | ~2.5s | 서술 완료 후 |
| **합계 (선택지까지)** | **~13.3s** | 감사 실측과 일치 |

- 입력→첫 토큰 ≈ **6.3초** — 전부 메인 LLM 시작 전 오버헤드.
- p95 스파이크(41~51s)는 메인 호출 무응답 → 타임아웃(8s)×재시도×fallback 누적.

## 2. 수정 4건

| # | 수정 | 예상 효과 |
|---|---|---|
| 1 | **Track 1 ∥ NpcReaction 병렬화** (llm-worker) — pre-known NPC(플레이어 지목/대화 잠금/이벤트 배정, `actionContext.primaryNpcId`)가 있으면 두 nano를 동시 실행. Step F가 서술 NPC를 primaryNpcId로 강제 교정하므로 nano 추천 NPC보다 primaryNpcId 기준 반응이 최종 서술과 더 정합 | −1.6s |
| 2 | **Challenge 분류 ∥ 이벤트 매칭** (turns.service) — classify를 조기 return(EQUIP/MOVE)·intent 다운그레이드 직후 promise로 발화, resolve 게이트에서 회수. eventTitle·판정 NPC posture는 보조 힌트라 생략 (rawInput+actionType이 지배 요소) | −0.5s |
| 3 | **워커 즉시 킥** — commitTurnRecord에서 PENDING 커밋 직후 `LlmWorkerService.wake()` 호출 (1초 setInterval 대기 제거). poll()은 DB 락 기반이라 중복 호출 안전 | −0.5s |
| 4 | **첫 토큰 타임아웃** (openai.provider) — `LLM_FIRST_TOKEN_TIMEOUT_MS`(기본 5000ms) 내 첫 콘텐츠 델타가 없으면 abort → caller의 non-stream fallback(재시도+fallback 모델). 첫 토큰 전에만 작동해 토큰 중복 없음 | p95 꼬리 절단 |

미적용(제외): nano OpenRouter→OpenAI 직결 실험 (#5, 사용자 결정으로 제외).

## 3. 실측 결과 (chat-mairel 14턴, 2026-07-09)

### 오버헤드 절감 — 목표 달성 확인

total(제출→DONE) − main(메인 호출) = 파이프라인 오버헤드:

- **개선 전**: ~5.1s (픽업 1s + Track1 2s + NpcReaction 1.6s + 기타)
- **개선 후**: **~1.5~2.5s** (T1은 0.08s — 픽업 즉시 + 병렬 nano)
- 정상 provider 턴(8/14)의 전체 레이턴시: **4.3~6.8s** — 10초 목표 구간 진입.

### 단, 이번 런 평균은 24.2s — provider 스루풋 스파이크 (변경과 무관)

6/14턴에서 메인 호출 자체가 15~30s. 토큰/초로 확증: 느린 턴 **10~14 tok/s** vs
정상 턴 37~68 tok/s (동일 분량 출력). OpenRouter Gemma provider의 시점성 저하로,
첫 토큰은 5초 내 도착해 #4(첫 토큰 타임아웃)가 발화하지 않는 "느린 생성" 케이스.

### 남은 문제 정의 (후속 결정 사안)

느린 생성(low tok/s)은 현 4건으로 커버 불가 — 스트림 중간 abort는 이미 노출된
토큰과 fallback 재생성의 중복 문제(클라 2-phase 렌더)가 있어 별도 설계 필요:
(a) 토큰 간 갭/총 스트림 상한 + 클라 스트림 리셋 프로토콜,
(b) OpenRouter provider 고정/제외 리스트(`provider.order`/`ignore`),
(c) 메인 모델 재평가 (arch/25 연장).
