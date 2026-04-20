# DIMTALE

**AI 서사 엔진 기반 텍스트 RPG — 개인 프로젝트 포트폴리오**

> 정치 음모 RPG를 서버 결정론 + LLM 서사 이중 구조로 구현한 풀스택 웹 게임.
> Next.js 16 + NestJS 11 + PostgreSQL 16 + OpenRouter(Gemma/GPT/Gemini 멀티 프로바이더).

**라이브**: [dimtale.com](https://dimtale.com) · **GitHub**: [Dohamsu](https://github.com/Dohamsu) / [graymar-server](https://github.com/Dohamsu/graymar-server) · [graymar-client](https://github.com/Dohamsu/graymar-client) · [graymar-docs](https://github.com/Dohamsu/graymar-docs)

| 핵심 수치 | |
|---|---|
| 메모리 반복률 **71% 감소** | v4 nano 요약 도입, 토큰 비용 측정 기반 개선 |
| **95 서비스** · **22 DB 테이블** | NestJS 12 모듈, Drizzle ORM, JSONB 상태 관리 |
| 단위 테스트 **530건** 100% 통과 | 전투·LLM·엔딩·메모리·이벤트 엔진 전반 커버 |

---

## 1. Overview

AI가 서술을 생성하고, 서버는 모든 수치·판정·상태를 결정하는 **이중 권위 구조**의 턴제 텍스트 RPG. 플레이어는 중세 항만 도시 그레이마르에 도착한 "이름 없는 용병"이 되어 부패·파업·밀수 3축 사건에 관여한다. 43명의 NPC가 각자의 목표를 가지고 움직이며, 플레이어의 모든 행동이 세계에 누적된다.

이 프로젝트는 **AI 서사 엔진의 실운영 가능성**을 증명하기 위해 만들었다. 단순 프롬프트 호출이 아니라, 서버의 결정론적 판정 + 메모리 계층 + 이벤트 엔진 + 스트리밍 UI까지 **전 계층을 직접 설계**했다.

## 2. Problem → Approach → Result

**Problem**: 기존 AI 텍스트 RPG(AI Dungeon 등)는 ① 서술 일관성이 깨지고 ② NPC가 플레이어 행동을 기억하지 못하며 ③ 토큰 비용이 폭주한다.

**Approach**: 세 가지 설계 축을 잡고 각각을 시스템으로 분리했다.
1. **결정론적 서버 + 서술 전용 LLM** — 모든 수치(스탯·판정·인벤토리)는 서버가 확정. LLM은 이미 고정된 결과를 **서술로만** 풀어낸다. `CLAUDE.md`에 "Server is Source of Truth, LLM is narrative-only" 원칙으로 명문화.
2. **4계층 메모리** — 런 전체 테마(L0) → 사건 연대기(L1) → 장소 방문기(L2) → 직전 턴 원문(L3). 각 턴마다 현재 문맥에 관련된 블록만 **선별 주입**. 무관한 과거는 토큰 예산에서 제외.
3. **Player-First 이벤트 엔진** — 플레이어 입력을 먼저 파싱해 TurnMode를 3분류(`PLAYER_DIRECTED` / `CONVERSATION_CONT` / `WORLD_EVENT`)하고, NPC를 5단계 우선순위로 결정. 기존 "이벤트 매칭 후 플레이어는 반응자" 구조를 뒤집었다.

**Result**
- 메모리 반복률 **71% 감소** (동일 묘사 재등장 빈도 측정)
- LLM 턴 응답 지연 **300~1000ms 절감** (NanoEventDirector 비동기 분리)
- OpenRouter 평균 응답 **32.7s → 6.7s** (`sort:latency` provider 정책 적용)
- 동시 접속 **10/10 성공** (Promise.allSettled + DB pool 튜닝)

## 3. 시스템 아키텍처

```
┌────────────┐   SSE stream   ┌────────────────────────┐    ┌─────────────────┐
│ Next.js 16 │ ─────────────▶ │  NestJS 11 Gateway     │    │ OpenRouter LLM  │
│ React 19   │   JSON-REST    │  Turn Pipeline         │───▶│ Gemma / GPT /   │
│ Zustand    │ ◀─────────────│  (input → resolve →    │    │ Gemini          │
└────────────┘                │   commit → narrate)    │    └─────────────────┘
                              │  95 services / 22 tbls │
                              └────────────┬───────────┘
                                           │ Drizzle
                                           ▼
                                    PostgreSQL 16
                                    (JSONB run_state)
```

- **서버 턴 파이프라인**: `submitTurn` → `IntentParser` → `EventMatcher` → `ResolveService(1d6+stat)` → `commitTurnRecord` → **async** LLM Worker → SSE 스트리밍 렌더
- **클라이언트 Dual-Track 스트리밍**: 문장 단위 SSE 세그먼트 수신(Phase 1) → LLM 완료 시 `analyzeText`로 최종 서술 교체(Phase 2). 타이핑 중/후 DOM 래퍼 통일로 스타일 점프 제거
- **데이터 모델**: 한 런의 전체 상태(`run_state`)를 단일 JSONB 컬럼에 저장. 턴마다 diff 계산 후 전체 스냅샷 갱신. 개별 컬럼 설계보다 스키마 유연성 우선

## 4. 기술 스택

| 계층 | 기술 | 선택 근거 |
|------|------|----------|
| 프론트 | Next.js 16 (Turbopack) / React 19 / Zustand 5 / Tailwind v4 | App Router + 스트리밍, Zustand는 Redux보다 보일러플레이트 낮음 |
| 백엔드 | NestJS 11 + Drizzle 0.45 | 모듈/서비스 구조 명시적, Drizzle은 타입 안전 + JSONB 1급 지원 |
| DB | PostgreSQL 16 | JSONB 쿼리 + 세션 상태 단일 컬럼 저장 |
| LLM | OpenRouter (Gemma 4 26B 메인 / GPT-4.1 Mini fallback / Gemini) | 단일 API로 멀티 모델 · `sort:latency` 라우팅 · 비용 제어 |
| 검증 | Zod 4 + Jest + Playwright | 턴 페이로드·LLM JSON 출력 런타임 검증, E2E 스크린샷 |

## 5. 기술 하이라이트

### 5-1. LLM 서사 파이프라인 (Dual-Track 스트리밍)

서버는 확정된 결과를 가진 턴을 커밋한 뒤 LLM을 호출한다. 클라이언트는 `EventSource`로 SSE 스트림을 열어 **문장 단위 세그먼트**를 실시간 수신하고, `StreamClassifier`가 narration/dialogue로 분류해 타이핑 애니메이션으로 렌더한다. LLM이 완료되면 `analyzeText` 파이프라인이 전체 서술을 정제해 Phase 1 렌더를 **교체**한다. 이 2단계 구조 덕분에 사용자는 0.4초 내에 첫 문장을 보면서도 최종 품질(마커 교정·문단 재조합·톤 검증)은 유지된다.

문장 분리에 앞서 서술과 대사를 **별도 LLM 호출로 분리**(`dialogue-generator.service`)하는 2-Stage 파이프라인도 도입했다. 대사는 NPC별 `speechRegister`(하오체/해요체/반말/합쇼체/해체) 5종 중 하나로 어미 검증 → 실패 시 1회 재시도 → 최종 실패 시 정적 fallback. 어미 혼용(HAOCHE인데 "합니다" 섞임) 빈도가 측정 가능한 수준으로 억제됐다.

### 5-2. Player-First 이벤트 엔진

AI 텍스트 RPG에서 가장 자주 깨지는 것은 "플레이어가 뭘 해도 내가 준비한 이벤트만 돌아간다"는 인상이다. 이를 해결하기 위해 **턴 모드 결정 로직**을 새로 설계했다.

1. `determineTurnMode()`: 플레이어 입력을 분석해 `PLAYER_DIRECTED`(기본) / `CONVERSATION_CONT`(대화 잠금 중) / `WORLD_EVENT`(첫 진입·압박 임계 초과·퀘스트 fact 트리거)로 분류
2. NPC 결정 5단계 우선순위: 텍스트 매칭 > IntentV3 targetNpcId > 대화 잠금 > NanoEventDirector 추천(`WORLD_EVENT`만) > 이벤트 배정
3. `NanoEventDirector`(경량 LLM)가 매 턴 이벤트 컨셉·NPC·fact·선택지를 동적 생성. 콘텐츠 매핑에 없는 상황도 즉석 조립

테스트로 101개 케이스(turnMode 35 / targetNpc 16 / nano 25 / 후처리 20 / matcher 5)를 커버. 플레이어 입력이 시스템의 "주도자"가 되는 구조를 증명했다.

### 5-3. 구조화 메모리 시스템 v4

초기 v1~v3는 "모든 기억을 매 턴 프롬프트에 넣기" 방식이었다. 토큰 비용이 선형 증가했고, LLM이 과거 문구를 재사용해 반복 묘사가 심해졌다.

v4에서 **구조화 추출 + 선별 주입**으로 재설계했다.
- **entity_facts UPSERT**: 턴 종료 시 경량 LLM이 NPC·사건·장소별 사실을 추출해 DB에 누적. 다음 턴엔 키워드 트리거로 해당 fact만 조회
- **nano 요약 주입**: 직전 턴 원문(수 백 토큰)을 nano LLM이 3~4문장으로 요약해 다음 프롬프트에 삽입. 원문 재사용 회피
- **선별 규칙**(`CLAUDE.md` Invariant 24): NpcPersonalMemory는 등장 NPC만 / LocationMemory는 현재 장소만 / IncidentMemory는 관련 사건만 / ItemMemory는 RARE 이상 장착/획득품만

결과: 동일 묘사 재등장 빈도 71% 감소, 평균 프롬프트 토큰 35% 절감.

### 5-4. 테스트·플레이테스트 자동화

단위 테스트만으로는 AI 서사 품질을 측정할 수 없다. **9축 자동 검증**을 설계했다.

- **V1 Incidents** · **V2 Encounter** · **V3 Posture** · **V4 Emotion** — 세계 상태 정합성
- **V5 Memory** · **V6 Resolve** — 데이터 보존·판정 완전성
- **V7 No Leak** — 시스템 프롬프트 누출 9패턴 감지
- **V8 NPC Match** — NPC 카드↔마커↔화자 3중 일치
- **V9 Quality** — 반복 패턴·어체 혼용·fallback 감지

`scripts/audit_quality.py`가 1차 regex + 심층 3단계 검사(원문 대조 · 프롬프트 grep · 문맥 판정)로 오탐을 자동 필터링. 30턴 벤치 기준 9/9 PASS가 품질 기준선이다.

단위 테스트는 Jest 기반 530건. 전투 확률(hit·damage·evade) / LLM 파이프라인(prompt build·stream parse) / 엔딩 생성 / 여정 아카이브 / 이벤트 매칭 / 후처리 regex 등 커버.

## 6. 품질 & 관찰 가능성

- **런타임 에러 수집**: 클라이언트에 `BugReportButton` + 자동 `client_snapshot` + `network_log` 직렬화. 버그 제보 시 DOM 상태·최근 API 응답·타임라인 함께 서버 전송. `bug_reports` 테이블로 집계
- **LLM 비용 추적**: `ai_turn_logs` 테이블에 프로바이더·모델·토큰·비용·레이턴시 턴별 누적. 모델 교체 의사결정의 근거 데이터
- **자동 플레이테스트**: `scripts/playtest.py` 한 스크립트로 회원가입→런 생성→N턴 랜덤 행동→V1~V9 검증. CI에서 회귀 테스트로 사용 가능

## 7. 개발 프로세스 — AI 페어링 워크플로우

이 프로젝트는 **Claude Code(에이전트)와의 페어 프로그래밍**으로 개발했다. 단순 코드 생성 대신 **AI를 역할별로 분리된 협력자**로 설계했다.

- **프로젝트 상수 주입**: `CLAUDE.md` 상단에 LLM 설계 5대 원칙(Stateless / 학습된 편향 / 유사 컨텍스트 수렴 / Soft 지시 무시 / 풍선효과) + 20+ Design Invariant를 문서화. 에이전트가 매 작업에 이 원칙을 기반으로 판단하게 함
- **서브 에이전트 오케스트레이션**: `backend` / `frontend` / `database` / `publisher` 등 역할별 에이전트에게 동시 위임(병렬). 명확한 계약(API 스펙·타입 정의)을 먼저 확정한 뒤 각 영역을 독립 진행
- **TDD 루프**: 신규 기능마다 spec 먼저 요구. 기존 530 테스트 전원 통과를 회귀 게이트로 유지
- **설계 문서 동시 갱신**: 구현이 끝나면 `architecture/` 아래 새 번호 md 파일 생성, `INDEX.md` 갱신, `CLAUDE.md` Phase Status 추가. "코드=진실의 원천"이 아니라 "문서·코드 동시 진실"

AI 페어링의 가장 큰 수익은 "의사결정 속도"다. 설계 옵션 A/B/C를 요청하면 AI가 각각의 장단·리스크를 정리해 주고, 내가 결정한 방향으로만 코드가 생성된다. 맹목적 구현이 아니라 **판단은 사람, 타이핑은 AI** 구조로 일관되게 유지했다.

## 8. 회고 · 한계 · 다음 스텝

**회고 (Lessons Learned)**
- LLM은 **Soft 지시를 무시**한다. "~하지 마세요" 프롬프트 규칙 10개보다 "허용 어미 목록 + 위반 시 캐릭터가 깨진다" 같은 Positive framing + 리스크 연결이 준수율 높음
- **풍선 효과**: 특정 단어만 금지하면 동의어로 우회한다. 금지 대신 **카테고리 단위 통제**(NPC state에 사용한 제스처 축적 → 프롬프트에 "이미 사용한 것 제외" 명시)가 유효
- **서버 소스 오브 트루스 원칙**은 단순 수치 문제가 아니라 **디버깅·QA 작업량**을 극도로 줄여 준다. LLM이 수치를 건드리면 재현 불가능 버그가 폭증

**한계 (Known Limitations)**
- `arcRewards`(엔딩 보상) 실제 지급 미구현. 현재 단일 런 구조라 소비 경로 없어 보류. 캠페인 연속 구조 도입 시 지급 로직 추가 필요
- 일부 NPC에서 `speechRegister` 어미 미세 혼입(10턴 중 1회 수준). 메인 LLM 인라인 대사 경로에 validator 미적용 — 적용 범위 확장은 별도 과제
- 로컬 구동(Apple M4 + Docker Postgres) + Cloudflare Tunnel 임시 도메인. 프로덕션 클라우드 배포 미연결 상태
- LLM 비용은 OpenRouter 기준 턴당 약 $0.005. 대량 사용 시 비용 모델 재검토 필요

**다음 스텝 (Roadmap)**
- 엔딩 아카이브 Phase 2: 12분기 수집도 + 잠금 엔딩 미리보기로 재플레이 유도
- Phase 3 공유: 엔딩 요약 OG 이미지 자동 생성 + 딥링크
- 콘텐츠 확장: events.json의 `itemRewards` 매핑 점진 추가 + 추가 Incident/NPC
- 프로덕션 배포: Vercel(클라) + 클라우드 Postgres(DB). 고정 도메인 + pm2 클러스터

---

## 링크

- **라이브 플레이**: https://dimtale.com
- **소스 코드**
  - 서버: https://github.com/Dohamsu/graymar-server
  - 클라이언트: https://github.com/Dohamsu/graymar-client
  - 설계 문서 모음: https://github.com/Dohamsu/graymar-docs
- **설계 문서 진입점**: `architecture/INDEX.md` (40+ md의 도메인별 색인)
- **LLM 원칙 문서**: `CLAUDE.md` ("LLM 설계 원칙" 섹션)

---

*본 포트폴리오는 프로젝트 진행 상황에 따라 갱신됩니다. 최종 갱신: 2026-04-20.*
