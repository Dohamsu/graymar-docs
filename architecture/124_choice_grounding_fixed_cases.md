# 124. 선택지 정본 대조 고정 사례 v1 (2026-09-28)

> §123 A1/B1의 **사람이 판정한 기준선**이다. 40건 = 문제 20 / 정상 20, `graymar_v1` 20건 / `star_sand_v1` 20건. 각 행은 표기한 실런 또는 회귀 픽스처의 경계를 요약했다. 회귀 픽스처는 실모델 발생 증거가 아니다. `미관찰`은 클릭 성공도 실패도 아니며 점수 분모에서 따로 센다.
>
> 참조 ID는 현재 팩의 fact/NPC/location ID가 있을 때만 썼다. 일반 소품은 아직 안정 ID가 없어 `SCENE_OBJECT:미해결`로 적는다. 이는 물건 부재 판정이 아니다. 사실 공개 전·후와 실제 소지 여부는 **각 행의 조건**이며, 모델이 제출한 ID로 이 조건을 변경할 수 없다. `허용`은 서술과 클릭까지 검증됐다는 뜻이 아니라 그 조건에서 선택지를 막지 말라는 기대다.

| ID | 팩 | 조건·최종 선택지/주장 | 정본 참조·공개 시점 | 기대 | 클릭 근거 | 출처 |
|---|---|---|---|---|---|---|
| G01 | graymar | 실무자의 주머니를 회계사의 손에 있는 가방으로 조사 | `SCENE_OBJECT:미해결`; 서술 소지자=실무자 | 거부 | 실런 잘못된 클릭→다음 턴 승격 | §123 §43 T7→8 |
| G02 | graymar | 회계사가 책상에 내려놓은 장부를 손에 든 것으로 조사 | `SCENE_OBJECT:미해결`; 위치=책상 | 거부 | 미관찰 | `ungrounded-owned-object-choices.core.spec.ts` 책상 회귀 |
| G03 | graymar | 직전 문장의 회계사를 다음 문장의 실무자 가방 소유자로 간주 | `SCENE_OBJECT:미해결`; 소지자=실무자 | 거부 | 미관찰 | 같은 파일 직전 문장 회귀 |
| G04 | graymar | 실무자의 가방을 `회계사의 작은 가방`으로 조사 | `SCENE_OBJECT:미해결`; 소지자=실무자 | 거부 | 미관찰 | 같은 파일 손 표현 없는 회귀 |
| G05 | graymar | 회계사가 실무자의 가방을 바라볼 뿐인데 회계사 소유로 조사 | `SCENE_OBJECT:미해결`; 소지자=실무자 | 거부 | 미관찰 | 같은 파일 두 인물 회귀 |
| G06 | graymar | 실무자가 든 가방을 회계사 소유로 조사(물건 뒤 관계절) | `SCENE_OBJECT:미해결`; 소지자=실무자 | 거부 | 미관찰 | 같은 파일 관계절 회귀 |
| G07 | graymar | `들고 있는 실무자`를 회계사 소유물로 조사 | `SCENE_OBJECT:미해결`; 소지자=실무자 | 거부 | 미관찰 | 같은 파일 `들고 있는` 회귀 |
| G08 | graymar | 미공개 `FACT_INSIDE_JOB`을 실패 턴에 결론으로 노출 | `FACT:FACT_INSIDE_JOB`; 그 턴 비공개 | 거부 | 미관찰 | §123 §17·§35 실패 턴 |
| G09 | graymar | 잘못된 NPC/단계 payload로 저작 후속을 위장 | `FACT:FACT_TAMPERED_LOGS`; 클릭 단계 불일치 | 거부 | 결정론 통합에서 거부 | §123 §36 저장 선택지 회귀 |
| G10 | graymar | 같은 choice ID지만 화면과 다른 서버 payload를 실행 | 최종 `choiceId→payload` 불일치 | 거부 | 과거 결함·수정 후 저장 조회 회귀 | §123 §36 저장 선택지 회귀 |
| G11 | graymar | 실무자의 손에 있는 천 주머니를 살핀다 | `SCENE_OBJECT:미해결`; 소지자=실무자 | 허용 | 미관찰 | `ungrounded-owned-object-choices.core.spec.ts` 정상 회귀 |
| G12 | graymar | 회계사가 실제로 든 작은 가방을 살핀다 | `SCENE_OBJECT:미해결`; 소지자=회계사 | 허용 | 미관찰 | 같은 파일 회계사 소지 회귀 |
| G13 | graymar | 회계사에게 가방을 가지고 있는지 묻는다 | `NPC:NPC_EDRIC_VEIL`; 소유는 미확인, 열린 질문 | 허용 | 미관찰 | 같은 파일 열린 질문 회귀 |
| G14 | graymar | 저작 선택지의 소지 여부 질문을 유지 | 저작 출처; 소유 불확정 | 허용 | 미관찰 | 같은 파일 저작/질문 회귀 |
| G15 | graymar | 다른 fact 발견 후 목표 `FACT_TAMPERED_LOGS` 미공개: 목표 후속 유지 | `FACT:FACT_TAMPERED_LOGS`; 그 턴 비공개 | 허용 | 결정론 DB/API 클릭→`LOC_GUARD` | §123 §37 통합 |
| G16 | graymar | 두 번째 조사 `FAIL` 뒤 경비대 기록 대조 선택 | `FACT:FACT_TAMPERED_LOGS`; 비공개, 저작 단계 검증 | 허용 | 결정론 DB/API 클릭→`LOC_GUARD` | §123 §37 통합 |
| G17 | graymar | 새 fact가 가리키는 실제 다음 장소 ID로 이동 | `LOCATION:저작 nextHintLocationIds`; 목적지 ID 일치 | 허용 | 후속 실클릭 별도 | `quest-forward-choice.core.spec.ts` ID 일치 회귀 |
| G18 | graymar | 공개한 `FACT_TAMPERED_LOGS`의 실제 기록 내용을 에드릭에게 재확인 | `FACT:FACT_TAMPERED_LOGS`; 공개 후, 같은 NPC | 허용 | §123 §27 T5→6 실런 | §123 §15·§27 |
| G19 | graymar | 목표 fact 비공개 `PARTIAL` 뒤 장부를 빛에 기울여 다시 조사 | `FACT:FACT_TAMPERED_LOGS`; 미공개, 저작 조사 | 허용 | §123 §28 T6→7 실런 | §123 §28·§35 |
| G20 | graymar | DONE 최종 Nano와 서버 기본 choice ID 충돌 시 화면 Nano payload 실행 | 최종 `choiceId→payload` 일치 | 허용 | 저장 조회 회귀; 실클릭 미관찰 | §123 §36 조회 회귀 |
| S01 | star_sand | 공개 전 이렌의 같은 문장 원문을 확정 인용 | `FACT:FACT_SS_SAME_WORDS`; 그 턴 비공개 | 거부 | 미관찰 | §123 §45 T5 |
| S02 | star_sand | 존재하지 않는 `그 문장을 적은 쪽지`를 살핀다 | `SCENE_OBJECT:미해결`; 문서 출처 없음 | 거부 | 미관찰 | §123 §45 T5 |
| S03 | star_sand | 이렌의 구술을 장부에 기록된 말로 단정 | `FACT:FACT_SS_SAME_WORDS`; 공개 후 이렌 매체=`SPOKEN` | 거부 | 미관찰 | §123 §45 T6 |
| S04 | star_sand | 소지·장면에 없는 거울로 장부를 살핀다 | `ITEM:미소지`; 장면 소품도 미해결 | 거부 | 수정 전 최종 노출·클릭 미관찰 | §123 §45 수정판 T6 |
| S05 | star_sand | 거울이 없다는 부정 문장을 거울 사용 근거로 삼는다 | `ITEM:미소지`; 장면은 부정 | 거부 | 미관찰 | `ungrounded-tool-choices.core.spec.ts` 부정 회귀 |
| S06 | star_sand | 여관에 없는 무대 뒤로 잠입 | `SCENE_OBJECT:미해결`; 저작 장면에 무대 없음 | 거부 | 미관찰 | `ungrounded-stage-choices.core.spec.ts` 무대 회귀 |
| S07 | star_sand | 무대 뒤 이동인데 payload는 TALK | 장면 근거 없음; 라벨↔행동 불일치 | 거부 | 미관찰 | 같은 파일 TALK payload 회귀 |
| S08 | star_sand | 지난 밤 자체를 직접 확인한다 | 과거 사건; 현재 조사 대상 아님 | 거부 | 미관찰 | `past-event-choices.core.spec.ts` 과거 직접 조사 회귀 |
| S09 | star_sand | 확인되지 않은 창고를 창문 틈으로 직접 살핀다 | `LOCATION:미해결`; 현장·저작 출처 없음 | 거부 | 미관찰 | `unconfirmed-place-choices.core.spec.ts` 창고 회귀 |
| S10 | star_sand | 이렌 구술 문장을 이미 가진 쪽지로 보여준다 | `FACT:FACT_SS_SAME_WORDS`; 공개 후 `SPOKEN`, 쪽지 미소지 | 거부 | 미관찰 | `evidence-medium-choices.core.spec.ts` 구술→종이 회귀 |
| S11 | star_sand | 이렌에게 마지막 말이 무엇인지 묻는다 | `NPC:NPC_SS_IREN`; 열린 질문 | 허용 | 수정판 T5→6 실클릭 확인 | §123 §45 수정판 |
| S12 | star_sand | 그 문장을 적은 쪽지가 있는지 묻는다 | 쪽지 미확인; `NPC:NPC_SS_IREN` 질문 | 허용 | 미관찰 | §123 §46 정상 회귀 |
| S13 | star_sand | 이렌의 구술 원문을 직접 다시 확인한다 | `FACT:FACT_SS_SAME_WORDS`; 공개 후 `SPOKEN` | 허용 | 미관찰 | §123 §44 정상 회귀 |
| S14 | star_sand | 헬룬의 정당한 문서 증언을 듣는다 | `FACT:FACT_SS_SAME_WORDS`; 공개 후 헬룬 매체=`DOCUMENT` | 허용 | 미관찰 | §123 §44 정상 회귀·팩 fact |
| S15 | star_sand | 실제 소지한 손거울로 살핀다 | `ITEM:소지 확인`; 해당 턴 수량>0 | 허용 | 미관찰 | `ungrounded-tool-choices.core.spec.ts` 소지 회귀 |
| S16 | star_sand | 저작 장면 탁자 위에 있는 거울을 사용한다 | `SCENE_OBJECT:미해결`; 장면 원문에 긍정 | 허용 | 미관찰 | 같은 파일 현장 거울 회귀 |
| S17 | star_sand | 거울이 있는지 이렌에게 묻는다 | 거울 존재 미확인; 열린 질문 | 허용 | 미관찰 | 같은 파일 열린 질문 회귀 |
| S18 | star_sand | 저작 장면에 무대가 있는 경우 그 뒤로 숨어든다 | `SCENE_OBJECT:미해결`; 사건 장면에 긍정 | 허용 | 미관찰 | `ungrounded-stage-choices.core.spec.ts` 무대 긍정 회귀 |
| S19 | star_sand | 무대가 없더라도 이렌에게 무대 소문을 묻는다 | 무대 존재 미확인; 열린 질문 | 허용 | 미관찰 | 같은 파일 소문 질문 회귀 |
| S20 | star_sand | 이렌에게 그날 밤 본 것을 묻는다 | `NPC:NPC_SS_IREN`; 과거 사실에 대한 현재 질문 | 허용 | 미관찰 | `past-event-choices.core.spec.ts` 현재 질문 회귀 |

## 판정·측정 경계

- 이 40건의 `거부/허용`은 고정 기대값이다. B1은 `STRUCTURE_MATCH`를 **라벨 의미 승인**으로 해석하지 않는다. 라벨↔대상·소유·시점 판단은 일반 소품 ID/사건 공개 메타가 없는 행에서 `UNRESOLVED`로 남을 수 있다.
- 근거 수준: 40건 중 대부분은 결정론적 회귀 또는 과거 실런이다. `실클릭 미관찰` 행을 클릭 정합률의 성공 분모로 넣지 않는다. G15/G16은 격리 DB/API 통합, S11은 실런 클릭이며 증거 수준을 혼합하지 않는다.
- 다음 측정은 이 고정 행에 대한 B1 `문제 미검출 / 정상 오차단 / 미해결 / 제안 누락` 네 분모와, 실제 최종 Nano 노출 선택지의 같은 분모를 나란히 기록한다. `SCENE_OBJECT:미해결`을 임의 ID로 채우거나 문구별 가드 통과를 구조 검증 성공으로 치지 않는다.
- G08·S01·S03처럼 **본문 주장**인 행은 B1 선택지 검출률 분모에서 제외하고 C 본문 출처 계약에서 재사용한다. 출처·공개 시점의 세부 판정은 각 원본 기록을 다시 읽어야 하며, 이 표만으로 `choiceId→payload→다음 턴` 전체가 잠긴 것은 아니다.

## 최종 Nano 표면·클릭 증거 보강 (2026-09-28)

`node scripts/choice-grounding-evidence.mjs <playtest-report.json>`은 `llmStatus=DONE`의 최종 `llmChoices`만 읽고 바로 다음 서버 턴의 `AGENT/CHOICE:<id>`를 연결한다. 테스터 입력에 붙는 `(preferred)`·`(sequence n/m)`·`(arc)` 주석은 ID 뒤에서만 허용한다. 보고서의 `choiceIds`는 서버 기본 목록일 수 있어 최종 Nano 표면의 대용으로 쓰지 않는다. `playtestTurn`은 보고서의 T번호이고 `turnNo`는 서버 턴 번호라 1 차이가 날 수 있다. `NOT_CLICKED`는 실패가 아니라 **그 선택지가 그 다음 턴에 선택되지 않았음**이다. 보고서 끝 또는 턴 번호 공백은 `UNOBSERVED`로 남긴다.

| 사례 | 실제 런·T / 서버 턴 | 최종 선택지 ID·payload | 다음 턴 증거 | 판정 범위 |
|---|---|---|---|---|
| G01 | `f6fe5833-0def-4366-9bc5-c275d0d96ed8` T6 / 7 | `nano_7_0`, `OBSERVE`, `NPC_EDRIC_VEIL`; `날카로운 회계사의 손에 있는 작은 가방을 살핀다` | T7 / 8 `AGENT:nano_7_0`, 회계사 가방을 받아들인 본문 | 잘못된 최종 선택지의 클릭·다음 턴 승격 확인. 이 런은 후속 좁은 가드 이전이다. |
| S02 | `1bf5f057-b40e-433e-86aa-d8137fd1b2a5` T5 / 6 | `nano_6_1`, `INVESTIGATE`, NPC 없음; `그 문장을 적은 쪽지를 살펴본다` | 다음 턴은 다른 선택지 | 최종 노출 확인, 이 ID 클릭은 미확인. |
| S04 | `7044dda3-0006-4cc0-a0d9-df355b7824cd` T6 / 7 | `nano_7_1`, `INVESTIGATE`, NPC 없음; `거울을 이용해 장부를 자세히 살핀다` | 다음 턴은 `ACTION:move_location` | 최종 노출 확인, 이 ID 클릭은 미확인. |
| S11 | 같은 수정판 런 T5 / 6 | `nano_6_1`, `TALK`, `NPC_SS_IREN`; `그녀에게 마지막 말이 어떤 것인지 묻는다` | T6 / 7 `AGENT:nano_6_1` | 정상 질문의 클릭·다음 턴 접수 확인. 정답 진전은 별도 P3-1. |

이는 기존 실런의 **증거 복원**이며 B1 구조 제안 실험이 켜져 있던 런이 아니다. 따라서 이 4건에 `STRUCTURE_MATCH/CONTRADICTED`를 역으로 만들어 붙이지 않는다. B1 비교에서는 본문 주장과 저작·서버 선택지, 그리고 최종 Nano 여부가 확인되지 않은 행을 각각 별도 분모로 둔다. 실험 후에도 `STRUCTURE_MATCH`는 라벨 의미의 안전 승인으로 세지 않는다.

## 고정 사례의 재실행 가능한 최종 표면 감사 (2026-09-28)

위 4건의 원본 완료 턴 `llmChoices`와 바로 다음 입력을 [[architecture/127_choice_grounding_fixed_evidence_20260928.json|증거 발췌]]에 보존했다. `node scripts/choice-grounding-fixed-case-audit.mjs architecture/124_choice_grounding_fixed_cases.md architecture/127_choice_grounding_fixed_evidence_20260928.json architecture/126_b1_shadow_audit_20260928.json --verify-source`로 현재 남아 있는 원본 보고서 3개를 다시 읽어 **4건 모두** 발췌본과 대조했다. 원본 경로가 사라지면 `--verify-source`는 실패하며, 플래그 없는 보관 발췌본 집계만 가능하다. 이 감사는 40건의 기대 판정(거부 20/허용 20), 정확한 최종 Nano 표면 4건(거부 3/허용 1), 실제 클릭 2건, 노출 후 비클릭 2건, 다른 36건의 최종 Nano 미연결을 재계산한다. **B1 shadow와 동일한 런·턴·choice ID·라벨·payload의 중첩은 0건**이다. 이 0은 오경보·미검출 0건이 아니라 B1 성능을 산출할 같은 표면 분모가 없다는 뜻이다. 36건 중 저작/본문/회귀 사례를 실제 Nano 부재나 클릭 실패로 읽지 않는다.
