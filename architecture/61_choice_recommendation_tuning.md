# 61. 선택지 추천 시스템 점검 + 몰입성 튜닝 (2026-07-09)

> **선행**: architecture/28(NanoEventDirector 배경), 34(Player-First), 60(nano 선택지 DB/stream desync 봉합)
> **상태**: ✅ 구현됨

## 1. 점검 배경

선택지 추천이 "흐름상 적절한 선택지를 제시하는가, 스토리 몰입을 깨지 않는가"를
코드 흐름 + 실런 데이터(쥐왕 10턴 연속 등)로 전수 점검. 구조(3층 파이프라인,
desync 봉합, 양풀 클릭 역매핑)는 견고했으나 몰입성 이슈 6건 발견.

### 선택지 파이프라인 (점검 시점)

1. **턴 응답(동기)** — scene-shell: 이벤트 고유 choices > suggested 템플릿 > 장소 기본
   (+ 판정 후 buildFollowUpChoices). modifier·hint 부착, go_hub 포함.
2. **LLM Worker Track 2(비동기)** — 서술 완료 후 NanoEventDirector가 선택지 3개
   재생성 → finalChoices로 DB·stream 동시 교체.
3. **클라이언트** — choices_loading → done에서 최종 표시. 클릭은 서버/llm 양풀 매칭.

## 2. 발견 및 수정

| # | 발견 (실측 근거) | 수정 |
|---|---|---|
| P1 | nano가 서술 **앞 300자**만 봐서 서술 끝 NPC 질문/제안이 선택지에 미반영 — 쥐왕이 "장부와 관련된 무언가를 찾고 있소?"로 턴을 닫았는데 응답 선택지 0개 | 미리보기를 머리 150 + 꼬리 350 결합으로 변경 + "마지막 NPC 발언에 이어지는 선택지 포함" 지시 |
| P2 | 작별 턴에 "대화 이어가기" 선택지 — dialogueAct(개선 1)가 nanoCtx에 미전달. 서술은 작별을 연출하는데 선택지가 다시 여는 자기모순 | nanoCtx에 dialogueAct 전달. FAREWELL → 대화 계속 선택지 금지 + 떠남/이동 중심 지시. GREETING/WELLBEING → 가벼운 전개 중심 |
| P3 | "더 묻는다/살핀다/물러난다" 공식이 10턴 연속 반복 — 직전 라벨이 main LLM에만 전달, nano에 미전달 | previousChoiceLabels를 nanoCtx에 전달 + [직전 턴 선택지 — 유사 반복 금지] 블록 + "서술의 구체 요소 인용" positive 규칙 |
| P4 | Track 1/2 go_hub 라벨 "다른 장소로 이동한다"(MOVE_LOCATION) — 클릭 시 실제로는 선술집 복귀 (라벨-결과 불일치) | 서버 기본과 통일: "'잠긴 닻' 선술집으로 돌아간다" + returnToHub payload + hint |
| P5 | nano 교체 시 hint·예상 보정치(modifier) 소실 | 프리셋 특기 보너스(actionBonuses)를 nano 선택지 modifier로 부착 (이벤트 의존 보정은 다음 턴 이벤트 미확정이라 제외). go_hub에 hint 복원 |
| P6 | 라벨 문체 혼재 ("~한다" vs "~하기") | nano 규칙에 "~한다 통일" 명시 |

**P7 (미수정, 기록)** — main LLM [CHOICES] 태그 파서(parseAndValidateChoices)는
시스템 프롬프트가 태그 출력을 금지해 사실상 사문화된 fallback. Track 2 실패 시
서버 기본 선택지가 유지되므로 동작상 안전 — 제거하지 않고 유지.

## 3. 변경 파일

- `server/src/llm/nano-event-director.service.ts` — NanoEventContext(dialogueAct,
  previousChoiceLabels) + buildUserMessage(P1/P2/P3) + SYSTEM_PROMPT 규칙 4 강화(P3/P6)
- `server/src/llm/llm-worker.service.ts` — previousChoiceLabels 주입(P3),
  Track 1/2 go_hub 통일(P4), 프리셋 modifier 부착(P5)
- `server/src/turns/turns.service.ts` — dialogueAct 계산을 nanoCtx 빌드 앞으로 이동 + 전달(P2)

## 4. 검증

- 빌드 성공, 전체 테스트 871 passed (기존 실패 2건 외 신규 0)
- 린트: 변경 3파일 기준 27 → 25건 (typed 필드 전환으로 감소, 신규 위반 0)
- 실런: chat-rat-king 시나리오 — 작별 턴 선택지 / 질문 응답 선택지 / 라벨 다양성 확인 (§5)

## 5. 실런 검증 결과 (chat-rat-king 2회, 2026-07-09)

### 확인된 개선

- **P1** — 마지막 발언 이어받기 작동: 쥐왕 "조용히 흐르는 물처럼 움직이는 것이 상책"
  → 선택지 "그의 조언에 따라 조용히 움직이기로 결심한다". 응답형 선택지가 매 턴 1개 이상.
- **P3** — 서술 구체 요소 인용: "그림자와 찢어진 천 조각을 자세히 살핀다",
  "그가 말한 추악한 거래의 정체를 더 묻는다" 등 generic 3종 세트 탈피.
  단, 인접 2~3턴에서 유사 세트 재사용 잔존 (nano 경량 모델 준수율 한계 — 후속 후보:
  서버측 직전 라벨 유사도 필터).
- **P4/P5** — 전 턴 go_hub "'잠긴 닻' 선술집으로 돌아간다" 균일 + 프리셋 보정치
  [+1] 표시 확인.
- **P2** — FAREWELL 감지→nano 지시 경로는 유닛테스트로 검증. 실런 T14("또 뵙겠소")는
  보강 패턴 배포 2초 전 제출되어 미감지 — 다음 정기 NPA 감사에서 자연 확인 예정.
  (검증 중 FAREWELL_RE에 "또 뵙/다음에 뵙" 계열 보강, "처음 뵙겠소" 인사 오분류 방지 확인.)

### 부수 발견 — launchd 이중 워커 (운영 중대)

1차 실런에서 신·구 go_hub 라벨이 한 런에 혼재 → 조사 결과 서버가 **launchd 상주
서비스 `com.graymar.server`(KeepAlive)** 로 관리되고 있었고, `pnpm start:dev`를 겹쳐
띄우면 두 프로세스가 LLM 워커 큐를 번갈아 폴링 (구코드 턴 처리 혼입). launchd 앱은
명령줄이 상대경로(`dist/src/main.js`)라 기존 경로 기반 pkill에 걸리지 않았다.
→ **재시작 정본 = `pnpm build` + `launchctl kickstart -k gui/$UID/com.graymar.server`**.
CLAUDE.md 서버 프로세스 관리 섹션·restart-dev 스킬 갱신 완료.
