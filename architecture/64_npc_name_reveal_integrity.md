# NPC 이름 공개 무결성 — 정밀 분석 + 수정 A/C/D/E

> 작성 2026-07-10. 상태: 구현 완료 (A·B·C·D·E).
> 증상: "공개하지 않았는데 이름으로 묘사됨" + "다른(이상한) 이름으로 표시됨".

## 1. 시스템 구조 (분석 결과)

- 상태: `npcStates[id].introduced` + `introducedAtTurn` — **2턴 분리**: 소개 턴엔 별칭
  유지(LLM이 이름 밝힘 장면 연출), 다음 턴부터 실명 (`getNpcDisplayName(state, def, turnNo)`).
- 판정 `shouldIntroduce`: FRIENDLY·FEARFUL 1회 / CAUTIOUS 2회 / CALCULATING·HOSTILE 3회,
  BACKGROUND 영구 미소개, appearanceCount≥5 강제.
- 소개 경로 3개: turns.service primary / turns.service injected / llm-worker AppearanceIntro.
- 방어 2중: 프롬프트 최종 안전망(user 메시지의 미소개 실명→별칭 치환), IntroRollback
  (LLM이 이름 미언급 시 소개 취소).
- 실측(graymar 최근 12런): 끝까지 미소개 실명 노출 0, 소개 이전 노출 0, 오귀속 마커 0,
  UI 카드 위반 0 — **정상 경로는 견고**.

## 2. 실증된 고장 사슬 (silverdeen 핍 케이스)

T4: FEARFUL 1회 임계 소개 판정 → LLM 연출 실패("제 이름은 전령 소년이에요" — 별칭 자기소개)
→ IntroRollback 발동 → **같은 후처리 패치의 AppearanceIntro가 같은 초에 재소개**
(로그 실증) → T5부터 소개 장면 없이 "전령 소년 핍" 실명 등장.

## 3. 근본 원인과 수정

| # | 원인 | 수정 |
|---|------|------|
| R1 | 롤백-재소개 상쇄: 임계 1회 NPC는 IntroRollback이 같은 패치 AppearanceIntro에 항상 패배 | **A**: `rolledBackThisTurn` 집합 — 이번 턴 롤백된 NPC는 같은 패치 재소개 금지 ("한 턴 소개 시도 1회") |
| R3 | 소개 힌트 실명 오염: 경로별 npcName 규칙 불일치로 `(실명: …)`에 별칭이 들어감 | **C**: nameRevealHint 실명은 콘텐츠 `npcDef.name` 직접 |
| R5 | context-builder 표시명 17곳 turnNo 미전달 — 소개 턴 실명 선노출 | **C**: `turnNoForNames` 일괄 전달 (사설 메서드 3곳 파라미터 배선 포함), turn-orchestration npcInjection도 turnNo 반영 |
| R4 | injected 소개 경로 `introducedAtTurn` 미설정 — 2턴 분리 무력화 | **D**: turnNo 세팅 |
| 표시 | 별칭 접두 중복 결합 "팔뚝 굵은 광부 팔뚝 굵은 광부 조합장" | **E**: `stripAliasPrefixDup()` — dedupe 초입 + **최종 저장 직전 2중 적용** (T5 실측에서 dedupe 이후 단계 생성분 확인 — 발생 지점 미확정이어도 최종본 보장) |

회귀 스펙: `npc-name-reveal.spec.ts` 11건 (2턴 분리 계약, 핍 시나리오 재현 — 가드
유/무 대조, 접두 중복 4케이스).

## 4. 실런 검증 (수정 후, silverdeen 새 런)

- T4: 핍 소개 시도 → LLM 연출 재실패 → 롤백 **유지** (로그: 재소개 없음, DB introduced=false).
- T5: 실명 '핍' 미등장, 별칭 유지 — **사용자 증상 해소**. 소개는 다음 성공 연출까지 자연 이월.
- T4 프롬프트 실측: 소개 지시(자기소개 대사 예문 + 실명)가 완전하게 포함 —
  실패는 LLM 준수율(FEARFUL 감정 지시와 충돌). 롤백 안전망이 이를 흡수하는 구조 확인.

## 4-1. B 구현 (2026-07-10 — 같은 날 후속)

- `NPCState.pendingIntroduction` 신설. **워커는 공개를 결정만, 집행은 턴 파이프라인이**:
  - AppearanceIntro: 임계 충족 시 introduced 대신 pending 마킹 (조용한 공개 제거).
  - IntroRollback: 연출 실패 시 introduced 취소 + pending 마킹 (다음 관련 턴 재시도 이월).
    A의 rolledBackThisTurn 가드는 워커가 introduced를 더 이상 찍지 않아 구조적으로 불필요해짐.
  - turns.service primary/injected 소개 판정: `pendingIntroduction === true`면 임계 재판정
    없이 승격 — introduced=true + introducedAtTurn + newlyIntroducedNpcIds 편입
    (= 소개 연출 지시 + IntroRollback 검증까지 정식 파이프라인 통과).
- 승격 조건 = "해당 NPC가 primary/injected로 실제 장면에 등장하는 턴" — 미등장 턴 승격으로
  인한 연출실패 공회전 방지.
- 자기소개 지시문 보강: "⚠️ 별칭은 겉모습 묘사이지 이름이 아님 — 이름 자리에 별칭 금지"
  (별칭이 이름 슬롯에 anchor되는 준수 실패 완화).
- 실런 검증 (핍 런 연속): T7 연출 실패 → `롤백 → pending` / T8 pending **승격**
  (newlyIntroducedNpcIds 재편입) → 재실패 → 다시 pending. 3연속 실패에도 실명 노출 0 —
  **실패 모드가 "별칭 유지"로 안전**함을 확인. 성공 시 정상 공개.
- 회귀 스펙 4건 추가 (npc-name-reveal.spec.ts — 총 15건).

## 4-2. 소개 연출 성공률 튜닝 (2026-07-10 — 같은 날 후속)

3층 방어로 "무결성 + 종결성"을 모두 보장한다:

1. **경로 분기** (`prompts/intro-directive.ts`): `shouldAvoidSelfIntro` — 경계 성향
   (FEARFUL/HOSTILE/CALCULATING) 또는 실패 이력(introAttempts≥1)이면 자기소개(본인 발화)
   경로 금지, (a) 제3자 호명 / (b) 단서 발견만 지시. 자기소개 경로는 감정 지시("정보를
   쉽게 주지 않음")와 충돌해 실패가 빈발했음 (핍 실측). NPC 목록/[NPC 등장] 두 블록 적용.
2. **실패 추적**: `NPCState.introAttempts` — IntroRollback 시 누적. 우호 NPC도 1회
   실패하면 다음 시도는 외부 경로로 전환.
3. **결정론적 마감** (`IntroFallback`): 2회 실패 누적 후 또 실패하면 서버가 제3자 호명
   문장("...가 ${alias}을/를 향해 \"${name}!\" 하고 부르고는...")을 서술 말미에 삽입하고
   소개 확정 (LLM 원칙 6: 서버 로직 우선. Gemma가 avoid 경로 지시에도 미준수 실측 —
   프롬프트만으로 종결 불가).

실런 검증 (핍 T9~T11): T9 — posture가 FRIENDLY로 전환돼 3경로 지시(설계대로) → 실패 →
attempts=1. T10 — avoid 경로 지시 발화 확인(프롬프트 실측) → 실패 → attempts=2.
T11 — `[IntroFallback]` 발동, 호명 문장 삽입 + introduced 확정(2턴 분리 유지). 전 과정
실명 유출 0. 회귀 스펙 8건 추가 (경로 분기 5 + 마감 3, 총 23건).

## 4-3. R7 — 스트리밍 원문 노출 (2026-07-10)

조사 결과, 우려했던 "화면↔DB 영구 불일치"는 존재하지 않았다 — 클라에 최종본 교체
프로토콜(bug 4693)이 이미 있음: 서버 `done` 이벤트가 후처리 완료 서술을 전달 →
`onDone`이 스트림 버퍼를 강제 교체 → 타이핑 완료 시 그 최종본으로 메시지 확정.
폴링/타임아웃 fallback도 DB 최종본 사용. 실제 갭 2건을 수정:

1. **타이핑 중 원문 일시 노출** → `sanitizeStreamSegment()` (llm-worker): 스트림
   emit 직전 문장 단위로 ① 미공개 실명→별칭(`sanitizeNpcNamesForTurn`, 2턴 분리
   인지) ② 별칭 접두 중복 정리(`stripAliasPrefixDup`) 적용 (본류+tail flush).
   전체 문맥이 필요한 후처리(마커 교정 Step E/F 등)는 기존대로 done 최종본 교체 담당.
   레거시 token 경로(비classifier)는 토큰 조각이라 치환 불가 — 미적용 (classifier가 기본).
2. **죽은 배선 정리** — 클라 `streamDoneNarrative`(세팅처 없음)/`finalizeStreaming`
   (호출처 없음) 미완성 코드 삭제.

검증: 유닛 3건(총 26건) + SSE 실측 — silverdeen 새 런 턴 제출과 동시에 SSE 직접
구독, 스트림 세그먼트에 미공개 실명 0건·별칭 정상·done.narrative 정상.
확정 후 화면==DB는 코드 경로(onDone 교체→onComplete 확정)로 입증 — UI 완주 E2E는
캐릭터 생성 자동화 이슈로 중단 (핵심 검증에 불요, 사용자 지시로 종결).

## 5. 잔여 (후속)
- R6: 미조우 NPC 실명의 콘텐츠 경유 유입(npcRelations·facts versions·lorebook)은
  안전망(npcStates 순회) 사각 — 실측 0건, 사례 발견 시 정밀 대응.
- R7 잔여: 레거시 token 스트림 경로(비classifier)는 문장 새니타이즈 미적용 —
  classifier가 기본이라 실사용 없음, 경로 제거 후보.
- E 잔여: T5 중복의 정확한 생성 단계 미확정 (dedupe 이후 후단) — 2중 적용으로 최종본은
  보장되나 원인 규명은 재발 시 스트림 원문 로깅으로.
- IntroFallback 호명 문장은 범용 템플릿 1종 — 장소/상황 어색 케이스 발견 시
  scenario.json 콘텐츠 템플릿화 후보. dialogue-generator 슬롯 이름 주입은 미착수.
