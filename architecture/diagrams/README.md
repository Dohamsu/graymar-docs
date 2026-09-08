# architecture/diagrams — 엔진·LLM 파이프라인 구성도

`archify` 스킬(`tt-a1i/archify`, MIT)로 만든 자립형 HTML 다이어그램. 브라우저에서 바로 열면 되고, 다크/라이트·줌·검색·경로 추적·Present·PNG/SVG Export 가 내장돼 있다.

| 파일 | 종류 | 내용 |
|---|---|---|
| `engine-architecture.html` | architecture | 클라 → Cloudflare Tunnel → Auth/Throttler → TurnsService → HUB 엔진 → PostgreSQL → LlmWorker → nano/OpenRouter → SSE 브로커. 컴포넌트마다 `SRC` 배지로 서버 코드 file:line 근거 첨부 |
| `llm-pipeline-sync.html` | sequence | LOCATION 턴 ① 동기 — 제출 → 멱등·과금 → 의도 파싱(nano) → 게이트 → 판정 → commit(PENDING) → 200 |
| `llm-pipeline-async.html` | sequence | LOCATION 턴 ② 비동기 — 워커 락 → nano 사전 결정 → 프롬프트·스트리밍 → SSE → 후처리·DONE → T2 선택지·CAS → 사후 추출·환불 |

정본 스펙은 `src/*.json`. 근거는 2026-09-07 기준 서버 코드(`server` HEAD `814e786`)와 CLAUDE.md 의 파이프라인 표.

## 재생성

```bash
A=.agents/skills/archify/bin/archify.mjs            # npx skills add tt-a1i/archify@archify
export ARCHIFY_UPDATE_CHECK_DISABLED=1
node $A validate architecture architecture/diagrams/src/engine-architecture.json --quality showcase --repo-root server --json
node $A deliver  architecture architecture/diagrams/src/engine-architecture.json architecture/diagrams/engine-architecture.html --quality showcase --repo-root server --json
node $A deliver  sequence architecture/diagrams/src/llm-pipeline-sync.json  architecture/diagrams/llm-pipeline-sync.html  --quality showcase --json
node $A deliver  sequence architecture/diagrams/src/llm-pipeline-async.json architecture/diagrams/llm-pipeline-async.html --quality showcase --json
node $A visual-check architecture/diagrams/engine-architecture.html --json   # 브라우저 증거 (부산물 *.visual-check.* 는 gitignore)
```

## 저작 시 배운 제약

- **폭**: showcase 는 1440px 데스크톱에서 노드 글자 6px 이상을 요구한다. architecture 는 sublabel 원본 9px 라 viewBox 폭 ≤ ~1390, sequence 는 7px 라 ≤ ~1000.
- **높이**: 세로 스크롤 없이 한 화면에 들어가야 한다. 카드 3장이 약 150px 를 먹으므로 sequence 는 메시지 12개 안팎이 상한 — 그래서 파이프라인을 동기/비동기 두 장으로 나눴다.
- **라벨 폭**: 관계 라벨은 노드 사이 clear gap 안에 들어가야 한다(≈6.5px×ASCII 단위 + 13, 한글은 2단위). 라벨을 지우지 말고 간격을 벌리거나 어휘를 줄인다.
- **`sources`** 를 쓰면 `meta.repository`(GitHub URL + 40자 SHA) 가 필수이고 `--repo-root` 로 file:line 존재를 검증한다. 서버 레포가 private 이어도 로컬 git 으로 검증된다.
