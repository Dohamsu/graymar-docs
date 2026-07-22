# 84. 파티 던전 클라이언트 배선 완성

> 설계 배경: [[24_multiplayer_party_system|multiplayer party system]] · 구현 가이드: [[../guides/08_party_guide|party guide]]
> 작성: 2026-07-22 · 상태: 🚧 구현 중

## 1. 문제 — "서버는 완성, UI 협동은 미배선"

별빛모래 2인 파티 던전을 실측(`scripts/party-playtest.py`, star_sand_v1)한 결과, **서버 API 레벨의 2인 협동은 완벽 작동**(통합 판정·2인 서사·투표 이동·초상화·사례금)했다. 그러나 두 차례 독립 검증(backend 계획 검증 + frontend 배선 매핑)으로 **실제 게임 UI에서는 파티 협동이 작동하지 않음**이 확정됐다.

### 확정된 배선 공백

| 항목 | 상태 | 근거 |
|------|------|------|
| game-store 파티 런 판별 | 부재 | `partyRunId/isParty` 필드 없음 (party-store에만 존재) |
| 액션/선택지 → 파티 엔드포인트 | 부재 | `submitAction`/`submitChoice`가 무조건 솔로 `submitTurn` 호출 |
| `party-store.submitPartyAction` | 죽은 코드 | 어느 컴포넌트도 호출 안 함 |
| `PartyTurnService.startTurn` (턴 타이머) | 죽은 코드 | 서버 어디서도 호출 안 함 |
| 멤버 화면 로드 | 구조적 부재 | `getActiveRun`이 userId 소유 한정 → 멤버는 리더 런 못 읽음 |
| `dungeon:turn_resolved` → 서사/선택지 | 부재 | SSE 핸들러가 turnStatus만 정리, 화면 미갱신 |

**결론**: 파티 던전은 로비·채팅·투표·HUD·서버 엔진은 완성됐으나 "협동 플레이 입력→결과 표시" 배선이 게임 화면에 연결된 적이 없다(회귀 아님, 처음부터 미완성). 라이브에서 리더는 파티 런을 솔로처럼 혼자 진행하고, 멤버는 행동 제출 자체가 불가능하다.

## 2. 부수 발견 — 프롤로그 소프트락 (하네스 한정)

파티 API에 직접 CHOICE를 보내는 하네스(`party-playtest.py`)에서, HUB 프롤로그 `accept_quest`가 파티 가드에 400 거부됨을 발견:

- `resolveTurn`(party-turn.service.ts)이 항상 `type:'ACTION'`으로 평탄화 → HUB 노드는 CHOICE 필수(turns.service.ts) → 실패
- 어제 커밋 `8977352`가 이 실패를 제출 시점 400으로 앞당기며 **`go_`만 화이트리스트** → 정당한 HUB CHOICE(accept_quest/contact_ally/pay_cost)까지 차단
- `accept_quest`는 전 팩 공통(runs.service.ts)이라, 파티 엔드포인트를 실제로 쓰게 되면 **모든 팩의 신규 파티 던전이 첫 화면에서 막힘**

클라 배선을 완성하면 이 경로가 실제로 쓰이므로, 프롤로그 소프트락 해소가 배선의 전제 조건이 된다.

## 3. 설계 결정

1. **멤버 화면 로드 = 서버 참가자 조회 개방** — 신규 `GET /v1/parties/:partyId/runs/:runId/state`가 `run_participants` 멤버십을 검증하고 리더 런의 runState/서사/선택지를 반환. 멤버 진입·재접속·새로고침에 강건(SSE 주입만 방식은 새로고침 시 빈 화면이라 기각).
2. **HUB 비-go_ CHOICE = 리더 대표 통과** — `accept_quest`/`contact_ally`/`pay_cost`는 통합 판정·투표 없이 리더 대표로 solo 파이프라인 통과(1회성 서사 전환·공동 골드 소모). 리더 대표 턴은 `party_turn_actions`가 비어 단수 리더 서사가 나오나, 프롤로그·Heat엔 적절.
3. **arc_commit은 이번 스코프 제외** — 파티 서사 방향을 1인이 확정하는 리스크(불변식 47 정신과 긴장). `vote_type=ARC_COMMIT` 투표화는 백로그. 이번엔 400 유지.
4. **리더도 파티 엔드포인트 경유** — 리더가 솔로 경로를 쓰면 `party_turn_actions`에 리더 행동이 안 들어가 `checkAllSubmitted`가 영구 미충족. 리더/멤버 모두 파티 엔드포인트로 제출.

## 4. 구현 항목

### 서버
- **S1** `PartyTurnService.submitLeaderHubChoice(runId, partyId, userId, choiceId)` — 리더 검증(멤버는 위임 응답), 리더 계정으로 `turnsService.submitTurn({input:{type:'CHOICE', choiceId}})`, `dungeon:turn_resolved` SSE, `{accepted, leaderChoice:true, serverResult, llmStatus}` 반환.
- **S2** controller `submitPartyAction` 가드 수정 — run 조회에 userId 추가. HUB && CHOICE && 화이트리스트(accept_quest/contact_ally/pay_cost) → submitLeaderHubChoice. arc_commit·ACTION·미지 CHOICE는 400 유지. 분기 순서로 어제 소프트락 방어 보존.
- **S5** 턴 타이머·연쇄 — `startTurn` 트리거(던전 시작 + resolveTurn 후 다음 턴 연쇄), deadline 상수 소거 버그(제출 경로 waiting이 즉시 0초) 수정, 타임아웃·경고·waiting 복구.
- **S6** 멤버 데이터 경로 — 신규 `GET .../runs/:runId/state`(참가자 검증 후 리더 런 상태 반환) + `getPartyTurnDetail` 응답에 choices(워커 llmChoices) 추가.

### 클라
- **C7** game-store 파티 입력 배선 — 파티 런 판별(partyContext) + `submitAction`/`submitChoice` 파티 분기(go_ voteCreated / 비-go_ HUB CHOICE / 일반 CHOICE) + api-client 응답 타입 보강 + `getPartyTurnDetail`·`getPartyRunState` 신설.
- **C8** 턴 결과 화면 갱신 + 멤버 진입 — game-store 신규 액션 `applyPartyTurnResult`(순환참조 방지 캡슐화) + 서사 폴링 + 멤버 진입 시 `getPartyRunState`로 초기 복원.
- **C9** 대기·투표 UI 마감 — PartyTurnStatus 카운트다운 정상화 + 투표 후 `dungeon:location_changed` 화면 갱신.

## 5. 검증
- API E2E: `scripts/party-playtest.py --scenario star_sand_v1` — 프롤로그 우회 없이 진입.
- 클라 2인 브라우저 E2E: 파티 입력→파티 엔드포인트, 턴 대기 UI, 멤버 서사/선택지 갱신, 투표 이동.
- 회귀: go_ 투표·LOCATION 2인 통합 서사·karnholt 스모크·솔로 런 무영향.

## 6. 백로그
- arc_commit 파티 투표화(`vote_type=ARC_COMMIT`).
- `dungeon:narrative_ready` SSE로 멤버 서사 폴링 제거(최적화).
- 던전 이탈 버튼 클라 배선(`POST .../runs/:runId/leave`).
