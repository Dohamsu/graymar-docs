# 88 — S5 엔딩 동선(arc 커밋) 복구 + encounterCount 추적 수정 (2026-07-23)

활성 star_sand 런 분석에서 드러난 두 구조 결함을 함께 수정한다. 하나(B)는 종착
퀘스트 단계에서 "최종 선택" 동선이 사라지는 문제, 다른 하나(C)는 NPC 조우
카운트가 전 팩에서 0으로 고착되는 버그다. 둘 다 "설계된 시스템이 실질 무동작"인
상태였고, 실측 런(run c4c934d8, star_sand_v1 42턴)에서 동시에 관측됐다.

관련: [[architecture/68_uiux_audit_v1|arc 커밋 동선 부록 F]] · [[architecture/66_npc_self_introduction|NPC 자기소개]] · [[architecture/56_npc_reaction_director|NpcReactionDirector]] · [[architecture/39_ending_journey_archive|엔딩 연출]]

---

## B — S5 종착 단계 최종 선택(arc 커밋) 동선 부재

### 증상
questState가 종착 `S5_RESOLVE`(별빛모래: "별고래의 눈 앞에서 최종 선택")에 도달해도
플레이어가 조사 루프에 갇히고, 제시 선택지 어디에도 마무리 동선이 없다. 매 턴
"묻는다/조사한다/관찰한다 + 거점 복귀"만 반복하다 S5+5턴 타이머로 강제 종료.

### 근본 원인 (2중)
1. **콘텐츠 누락** — S5의 "최종 선택"은 실제로 **arc 루트 커밋**(해방/봉인/전이 중
   택1)이다. arc 커밋 선택지(`arc_commit_*`)는 `content/<pack>/arc_events.json`
   최상위 `routeCommitChoices`에서 생성되는데(scene-shell.service.ts, questStage≥3 &&
   currentRoute==null이면 HUB 선택지 선두 노출 — arch/68 부록 F), **star_sand_v1엔
   arc_events.json 파일 자체가 없었다.** → `getArcRouteCommitChoices()`가 [] →
   커밋 선택지가 어디에도 안 뜸 → 모든 런이 `currentRoute=null`인 채 종료.
   - 역설: star_sand `endings.json`엔 3루트 엔딩(EXPOSE_CORRUPTION/ALLY_GUARD/
     PROFIT_FROM_CHAOS × STABLE/UNSTABLE/COLLAPSED)이 **완비**돼 있었다. 작가가 엔딩은
     다 만들고 커밋 경로만 빠뜨려 3분기 엔딩 콘텐츠가 전부 사장.
2. **종착 상태 유도 힌트 침묵** — `getStaleHint`는 `stateTransitions` 중
   `from===currentState`인 전환을 찾아 다음 목표를 힌트로 준다. 종착 상태는 시작
   전환이 없어 **항상 null** → 체류 힌트(turns.service 단계 미변경 분기)가 하필
   해결 단계에서 아무것도 안 냄. 플레이어를 목표로 이끄는 시스템이 종착에서 꺼짐.

### 수정
1. **콘텐츠** — `content/star_sand_v1/arc_events.json` 신규. 세계관에 맞춘 3개
   커밋 선택지(해방=닻을 끊는다 / 봉인=꿈을 잠근다 / 전이=새 닻을 세운다). 커밋
   처리(turns.service `arc_commit_*` 분기)·엔딩 분기(arcRouteEndings)는 기존 제네릭
   경로 재사용 → **서버 코드 0줄로 3분기 엔딩 활성화**.
2. **신호(서버)** — `QuestProgressionService.isTerminalState(state)` 추가(전방
   stateTransition 없음 판정). turns.service 단계 미변경 분기에서 **종착 상태 &&
   arc 루트 미커밋 && 커밋 선택지 보유 팩**이면 매 턴 "단서가 모두 모였다. 거점으로
   돌아가 최종 선택을 내릴 때다" `pendingQuestHint` 주입. `getArcRouteCommitChoices()
   .length>0` 게이트라 아크 자산 없는 팩(실버딘·카른홀트)은 무영향.

### 결과 / 플레이 영향
- star_sand: 밋밋한 무커밋(NONE) 엔딩 → 플레이어 선택에 따라 갈리는 3분기 엔딩으로
  정상화. 재플레이 가치 상승.
- graymar(이미 arc_events.json 보유): 커밋 플로우 정상 + S5 미커밋 시 유도 힌트가
  붙는 부수 개선(회귀 아님).
- 종착 유도 힌트는 이제 S5 도달하는 모든 아크형 팩 공통 작동 → 신규 팩도 같은 구멍
  회피.

### 팩 계약 (신규)
아크 루트 엔딩(`endings.json` arcRouteEndings)을 정의한 팩은 **반드시**
`arc_events.json`의 `routeCommitChoices`도 함께 정의해야 한다. 커밋 경로 없이
엔딩만 정의하면 해당 루트 엔딩이 전부 도달 불능(NONE 고착).

---

## C — NPC encounterCount 증가 불능 (관계 깊이 티어링 무동작)

### 증상
NPC_SS_IREN이 introduced=true·trust=97·11턴 연속 상호작용에도 **encounterCount=0**.
star_sand 팩 전체에서 enc>0인 NPC가 2명뿐 → 사실상 전 팩 무동작.

### 근본 원인 — 워커 LockSeed 백필이 증가 게이트를 오염
`encounterCount` 증가 게이트는 `actionHistory.some(h => h.primaryNpcId === npcId)`
(turns.service.ts, "이번 방문에 이미 만났으면 증가 안 함")였다. 그런데 LLM 워커가
턴 커밋 **이후 비동기로** `actionHistory[턴].primaryNpcId`를 서술 화자로 **백필**
한다(llm-worker.service.ts, "LockSeed"). star_sand는 진입·분위기 이벤트가
`primaryNpcId=null`(예: EVT_SS_INN_LAMP_TREMOR)이라 NPC가 **환경 이벤트 턴에서
서술 화자로 먼저 등장** → 그 턴엔 증가 블록 미실행 + 워커가 사후 백필 → 이후 그
NPC가 대화잠금으로 정식 primary가 되는 첫 턴엔 게이트가 **이미 true** → 증가 영구
스킵. (소개·감정은 eventPrimaryNpc 블록에서 정상 반영되나 encounterCount만 누락 →
introduced=true·trust=97·enc=0 모순.)

대조: LUOR(enc=1)는 첫 등장이 실제 콘텐츠 이벤트(primaryNpcId=LUOR)라 LockSeed보다
먼저 동기 증가.

### 수정 — per-visit 키를 nodeInstanceId 명시 플래그로 교체
LOCATION 한 방문 = LOCATION 노드 instance 1개(실측: INN 방문 전 구간 동일
nodeInstanceId). 이 값은 워커 LockSeed가 안 건드려 오염 불가능한 완벽한 방문 키.
- `NPCState.lastEncounterNodeId?: string` 신설(npc-state.ts).
- 증가 게이트 2곳(eventPrimaryNpc / injectedNpc)을
  `if (lastEncounterNodeId !== currentNodeId) { encounterCount++; lastEncounterNodeId = currentNodeId; }`
  로 교체. `currentNodeId`(=currentNode.id)를 두 헬퍼
  (updatePrimaryNpcEmotionAndRecords·applyInjectedNpcRecords) 시그니처에 전달.
- tagNpc 경로는 유지(간접 참조, 의도적 미카운트).
- 방문당 1회 증가 시맨틱 보존 + 재방문(새 노드) 시 정상 증가.

### 결과 / 플레이 영향
그동안 enc가 전 NPC에서 0 고착이라 관계 깊이 소비처 3곳이 항상 "낯선 이"로 동작했다.
수정으로 설계 의도대로 복원(순증):
- **재회 프레이밍**(prompt-builder isFirstEncounter/isReEncounter) — 여러 번 만난
  NPC를 "다시 마주친 아는 얼굴"로 서술.
- **소개 타이밍**(npc-state.ts shouldIntroduce) — FRIENDLY/FEARFUL enc≥1 소개가
  appearanceCount fallback(≥3/≥5)으로 지연되던 것 → 첫 대화에 정상 소개.
- **반응 gradation**(NpcReactionDirector) — 항상 stranger 취급 → 관계 깊이 반영.
- CAS(applyRunStatePatch)는 enc 미변경, revert 아님 확인.

파괴적 회귀 없음(값이 0→정상으로 커지는 순방향). 기존 런의 굳은 0은 소급 복구 안 되나
이후 조우·재방문부터 정상 카운트.

---

## 검증
- **C**: star_sand 12턴 chatty 플레이테스트 — IREN/ED encounterCount=1(한 방문 내
  다회 대화에도 정확히 1 = dedup 정상, 수정 전 0 고착), lastEncounterNodeId 기록,
  전 게이트(V10/V11) 통과, 위화감 노트 0.
- **B**: 로더 동일 로직으로 routeCommitChoices 3개 파싱 확인, 빌드/린트 0.
- 서버 build + kickstart + `/v1/version` 해시 일치(24b781e).

## 배포
- server(graymar-server) `24b781e` — turns.service.ts / quest-progression.service.ts /
  npc-state.ts.
- content(graymar-docs) `1b1cc90` — content/star_sand_v1/arc_events.json.
- client 스핀오프(별건, 같은 세션): 선택지 hint 서브텍스트 라이브 턴 경로 통일
  (graymar-client 01f28d6).
