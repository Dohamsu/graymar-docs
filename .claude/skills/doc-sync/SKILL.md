# 설계 문서·수치 동기화

서버·클라 코드가 바뀌었을 때 `CLAUDE.md` 와 `guides/01_server_module_map.md` / `guides/02_client_component_map.md` 의 수치·목록을 실제 상태에 맞게 재조정한다.

## 언제 사용

- 서비스/컴포넌트를 추가·제거·이동했을 때
- DB 테이블/컬럼이 늘거나 줄었을 때
- 사용자가 "설계문서 동기화해줘" 라고 요청했을 때

## 절차

### 1. 실제 상태 측정

```bash
# 서버 서비스 수
find server/src -name '*.service.ts' -not -path '*node_modules*' | wc -l

# HUB 서비스
ls server/src/engine/hub/*.service.ts 2>&1 | wc -l

# LLM 서비스
ls server/src/llm/*.service.ts server/src/llm/prompts/*.service.ts 2>&1 | wc -l

# 파티 서비스
ls server/src/party/*.service.ts 2>&1 | wc -l

# DB 스키마 파일·테이블
ls server/src/db/schema/*.ts | wc -l
grep -r "pgTable" server/src/db/schema/ | wc -l

# 클라 컴포넌트
find client/src/components -name '*.tsx' | wc -l

# 스토어
ls client/src/store/*-store.ts | wc -l
```

### 2. 차이 대조

- `CLAUDE.md` → Project Structure / Server module 표 / HUB 서브시스템 표 / Client 영역 표
- `guides/01_server_module_map.md` → 서비스 수치, 파일 목록
- `guides/02_client_component_map.md` → 컴포넌트 카운트, 영역
- `agents/backend.md` / `agents/frontend.md` → HUB 37, components 40+ 등

차이 나는 숫자·항목은 현재 측정값으로 교체. 신규 서비스/컴포넌트는 도메인별 표에 한 줄 추가.

### 3. INDEX 반영 여부 확인

신규 설계 문서를 추가했다면 `architecture/INDEX.md` 의 도메인별 섹션에도 한 줄 요약 추가. 상호 참조 맵에 필요 시 화살표 추가.

### 4. agents 동기화

`agents/*.md` 에 서비스 수치가 박혀있는 경우 (특히 backend.md의 HUB 표) 같이 수정하고 `.claude/agents/` 에도 동일 사본 복사:

```bash
cp agents/backend.md agents/database.md agents/frontend.md agents/llm.md .claude/agents/
```

### 5. 빌드·타입 검증

문서 수정만이라도 CI가 깨지지 않는지 확인:

```bash
cd server && pnpm build
cd client && npx tsc --noEmit
```

### 6. 커밋 메시지 규칙

- 문서만 변경: `docs: <섹션> 수치 동기화`
- 설계 문서 + agents: `docs: 설계문서 동기화 + agents 갱신`
- 단위: 루트 레포(docs)만 커밋 대상. `.claude/agents/`·`agents/`·`CLAUDE.md`·`guides/`·`architecture/` 모두 루트 레포에 속함.

## 주의

- 수치가 명확하게 셀 수 있는 것(서비스 수 등)은 실측으로 맞추고, "서비스 40+ / 컴포넌트 40+" 같은 대략 표기는 크게 벗어나지 않으면 그대로 둠
- `server/` `client/` 는 서브 레포 — 해당 프로젝트 내부 문서(`server/README.md` 등)는 이 스킬 범위 밖
- 대규모 압축·병합은 이 스킬이 아니라 `sc:doc-merge` / `sc:doc-audit` 같은 별도 도구 고려

## 참조

- CLAUDE.md — 최상위 요약표와 Document Status
- architecture/INDEX.md — 도메인별 색인
- guides/01 ~ 08 — 실무 구현 가이드
