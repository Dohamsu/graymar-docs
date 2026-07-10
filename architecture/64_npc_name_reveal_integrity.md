# NPC 이름 공개 무결성 — 정밀 분석 + 수정 A/C/D/E

> 작성 2026-07-10. 상태: 구현 완료 (A·C·D·E), B는 후속.
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

## 5. 잔여 (후속)

- **B (권장 후속)**: AppearanceIntro를 "다음 턴 소개 후보(pendingIntroduction)"로 —
  연출 지시 없는 조용한 공개 경로 자체 제거. graymar에서 상시 발생
  (RAT_KING·HARLUN·MAIREL·MOON_SEA 로그).
- R6: 미조우 NPC 실명의 콘텐츠 경유 유입(npcRelations·facts versions·lorebook)은
  안전망(npcStates 순회) 사각 — 실측 0건, 사례 발견 시 정밀 대응.
- R7: 스트리밍 원문은 후처리 전 노출 (화면↔DB 불일치 가능) — 스트림 리셋 프로토콜
  별도 설계 필요 (arch/62 계열).
- E 잔여: T5 중복의 정확한 생성 단계 미확정 (dedupe 이후 후단) — 2중 적용으로 최종본은
  보장되나 원인 규명은 재발 시 스트림 원문 로깅으로.
- LLM 소개 연출 준수율: FEARFUL/경계 NPC의 감정 지시와 자기소개 지시 충돌 —
  (a)/(b) 경로(제3자 호명·단서 발견) 우선 유도 등 프롬프트 튜닝 후보.
