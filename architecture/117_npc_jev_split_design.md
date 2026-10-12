# 117. NPC 반응 JEV 분리 설계 검토

2026-09-22. 범위: 소스 기반 읽기 전용 조사와 전환 설계. 운영 코드·설정·서버 실행에는 변경 없음. 이 문서는 API 실측 결과가 아니며 실제 모델 정확도·지연시간은 별도 평가 결과를 따른다.

## 결론

`reactionType`와 `refusalLevel`은 닫힌 선택형 판단이라 분리 후보지만, **기존 nano 결과의 두 필드만 JEV 값으로 덮어쓰는 것은 권장하지 않는다.** 현재 nano는 목표·대사 방향·톤·감정 변화·관계 사건 신호까지 함께 결정하며, 이들은 서술과 상태 변경에 소비된다. 빠른 JEV 호출을 추가해도 nano가 남는 동안 전체 응답이 빨라진다는 보장은 없다.

당장 권장하는 범위는 오프라인 동일 맥락 비교와 보류(abstain) 기준 검증이다. 정식 전환은 **판단 정확도, 필드 간 정합성, 첫 서술까지의 전체 지연시간**이 함께 통과했을 때 별도 진행한다.

## 1. 현재 호출 구조와 의존성

| 영역 | 현재 책임 | 분리 시 보존 사항 |
|---|---|---|
| NPC 확정·맥락 | 서버가 NPC ID, 상태, 최근 대화·행동, 자기 목적, 목격 위험 태그 조립 | 동일 스냅샷을 두 모델에 전달; 다른 NPC 기록 혼입 방지 |
| nano 반응 디렉터 | 7종 반응, 4종 거절, 목표·자세·대사 방향·톤 3축, 감정 5축, 관계 신호 | enum 이외 기존 출력 계약 유지 |
| 서버 후처리 | 반응 4연속 방지(R2), 실패 기본 반응, 감정 범위 제한 | 원출력과 교정 결과를 구분해 계측 |
| 메인 서술 | 반응·거절·목표·대사 방향을 P0 지시로 받음 | 서로 충돌하는 지시를 만들지 않음 |
| 상태 | 감정 변화 CAS 반영, 관계 신호에 대한 서버 전이 판정 | JEV 평가 결과가 운영 상태를 변경하지 않음 |

근거: [반응 계약](/Users/dohamsu/Workspace/graymar/server/src/llm/npc-reaction-director.service.ts:59), [맥락 조립](/Users/dohamsu/Workspace/graymar/server/src/llm/llm-worker.service.ts:741), [서술 지시 조립](/Users/dohamsu/Workspace/graymar/server/src/llm/prompts/prompt-builder.service.ts:3869), [감정 CAS](/Users/dohamsu/Workspace/graymar/server/src/llm/llm-worker.service.ts:3330), [관계 전이](/Users/dohamsu/Workspace/graymar/server/src/llm/llm-worker.service.ts:3388).

### 이미 병렬인 부분

NPC가 `primaryNpcId`로 미리 정해지면 NPC 반응은 Track 1 이벤트 디렉터와 **이미 병렬 실행**된다. NPC가 미정인 경우에는 이벤트 디렉터가 추천한 NPC를 받은 뒤 반응을 직렬 호출한다. 그 후 프롬프트 조립과 메인 서술 호출이 이어진다. 따라서 반응 호출만 빨라져도 이벤트 디렉터가 더 느리면 사용자 체감 이득이 없을 수 있다.

근거: [병렬 시작](/Users/dohamsu/Workspace/graymar/server/src/llm/llm-worker.service.ts:853), [병렬 회수·직렬 분기](/Users/dohamsu/Workspace/graymar/server/src/llm/llm-worker.service.ts:993), [전체 단계 순서](/Users/dohamsu/Workspace/graymar/server/src/llm/llm-worker.service.ts:503).

지연 구조의 근사식(실측 아님): 이벤트 단계 시간을 E, 기존 반응 시간을 N, JEV를 J, 결정에 조건화한 축소 nano를 N'라 할 때:

- 기존, NPC 사전 확정: `max(E, N)`
- JEV 다음 nano 순차: `max(E, J + N')`
- 기존 nano와 JEV 독립 병렬: `max(E, N, J)` — 무조건 기다린다면 기존보다 짧아지지 않음
- NPC 미정: 위 `max` 대신 이벤트 단계 E 뒤에 반응 경로 시간이 더해짐

DB·조립·메인 모델의 첫 토큰 시간은 별도이며 실제 TTFT에는 모두 포함해야 한다. 코드 주석의 과거 약 1.6초는 이번 환경의 실측으로 인용하지 않는다.

## 2. 중요한 정확도 함정

1. **nano와의 일치율은 정답률이 아니다.** 서로 자연스러운 대체 반응이 가능하다. 상황별 허용 반응 집합과 반드시 지켜야 할 금지 조건으로 평가한다.
2. `WELCOME/OPEN_UP + POLITE 이상`은 프롬프트에서 금지하지만, R2 가드는 OPEN_UP으로 변경하며 거절을 한 단계만 완화하므로 조합 모순이 남을 수 있다. 기존 가드를 보존하되 원결정/후처리 각각 평가해야 한다. [금지 원칙](/Users/dohamsu/Workspace/graymar/server/src/llm/npc-reaction-director.service.ts:166), [R2 거절 보정](/Users/dohamsu/Workspace/graymar/server/src/llm/npc-reaction-director.service.ts:711)
3. R1 행동 급변, R3 거절 단조성, 위험 목격 시 호의 금지는 대부분 **프롬프트 지시**이지 각각의 강제 서버 가드가 아니다. 존재하지 않는 가드가 이미 안전을 보장한다고 가정하면 안 된다. 특히 컨텍스트에는 최근 reactionType만 있고 이전 refusalLevel은 명시 필드가 없다. R3를 검증·강제하려면 NPC별 거절 이력을 정식 입력에 추가하는 설계가 필요하다. [컨텍스트 계약](/Users/dohamsu/Workspace/graymar/server/src/llm/npc-reaction-director.service.ts:92), [행동 규칙](/Users/dohamsu/Workspace/graymar/server/src/llm/npc-reaction-director.service.ts:223)
4. 독립 선택형 질문 두 개는 서로의 결과를 모르는 판단으로 취급해야 한다. 두 답의 confidence가 높더라도 조합은 모순일 수 있다. 로컬 조합 검증을 필수로 두고, 필요하면 허용된 `(reactionType, refusalLevel)` 쌍을 하나의 Choice로 평가하는 방식도 비교한다.
5. 현재 파서는 거절 enum이 잘못되면 NONE으로 보정하며, 실패 재시도는 최대 2회 호출이다. raw 형식 성공률과 보정 후 성공률을 구분하지 않으면 비교가 왜곡된다. [호출·재시도](/Users/dohamsu/Workspace/graymar/server/src/llm/npc-reaction-director.service.ts:260), [거절 파서](/Users/dohamsu/Workspace/graymar/server/src/llm/npc-reaction-director.service.ts:616)

## 3. 정식 전환 설계 후보

### A. 평가 단계 — 이번 권장 범위

- 운영 디렉터와 분리된 평가 어댑터로 동일 맥락을 JEV와 nano에 전달한다.
- JEV 출력은 enum 두 개, confidence와 확률분포, 모델/프롬프트 버전, 지연시간만 보관한다.
- 기존 `JevDecisionService`의 typed 질문·timeout·호출 계측을 재사용할 수 있다. 단 소비자가 허용 enum과 요청 질문의 존재를 추가 검증해야 한다. [기존 포트](/Users/dohamsu/Workspace/graymar/server/src/llm/jev-decision.service.ts:42)
- 학습/프롬프트 조정용 사례와 최종 holdout을 나누고, holdout 결과를 보고 같은 holdout에 맞춰 재튜닝하지 않는다.
- nano가 정한 자유문장·감정·관계 필드는 운영과 동일하게 유지한다. 평가 코드가 상태 쓰기 경로를 호출하지 않도록 한다.

### B. 정합성 우선 전환 후보 — JEV 결정 후 조건화한 nano

JEV의 검증·가드가 끝난 반응을 nano에 **고정 입력**으로 주고, nano에는 나머지 자유문장·감정·관계 필드만 요청한다. nano의 enum 재추론은 제거한다. JEV 오류·저신뢰·모순일 때 기존 전체 nano 경로로 복귀한다. 이는 정합성과 모듈 경계를 가장 명확하게 보존하지만 순차 호출 비용이 생기므로, 속도 통과 전에는 운영 채택하지 않는다.

확장 가능한 계약은 `ReactionDecision`과 `ReactionExpression/StateHints`를 분리하고, 최종 `NpcReactionResult`는 서버에서 조립한다. confidence·채택 근거·fallback 이유는 서술 입력과 별도 메타데이터로 둔다. 단일 `source: llm|fallback`만으로 혼합 결과 출처를 표현하지 않는다.

### C. 속도 우선 장기 후보 — 표현을 메인 서술로 이동

JEV enum + 서버/NPC 정체성 맥락으로 메인 모델이 직접 대사·톤을 표현하면 선행 자유문장 생성 호출을 없앨 가능성이 있다. 그러나 현재 nano의 감정·관계 신호는 실제 상태에 영향을 주므로 통째로 삭제할 수 없다. 해당 상태 판단의 대체 설계와 표현 품질 회귀 평가가 필요하며 **이번 두 enum 평가 범위를 넘는다.** 별도 승인 작업으로 취급한다.

독립 병렬 nano+JEV를 돌리고 enum만 덮어쓰는 방식은 실험용 비교에는 유효하지만, 중복 판단이 유지되고 자유문장 모순을 해결하지 않으므로 최종 구조로 추천하지 않는다.

## 4. 제안하는 채택 기준 — 측정 결과가 아닌 사전 기준

- **정확도:** 독립 라벨의 허용 반응/거절 조합 정확도가 기존 이상. 위협 직후 무근거 환영, 신뢰 관계의 불필요 거절, 명시 거절과 대사 동의 등 중대 모순 0건. 전체 수치 외 NPC 성격·관계·행동 전환별 지표도 확인한다.
- **보류 정책:** 잘못 채택한 비율과 커버리지를 함께 제시한다. 초기 목표는 채택 부분 정밀도 95% 이상이며, 소표본은 신뢰구간과 표본 수를 공개하고 확정 근거로 쓰지 않는다. confidence 임계값은 모델 출력의 자기 확신을 그대로 신뢰하지 말고 검증 집합에서 정한다.
- **속도:** 동일 사례·모델·호출 조건에서 paired 반복 측정. 반응 경로 p50/p95, 첫 서술 p50/p95, 재시도·fallback 포함 지연을 분리한다. 제안 gate는 첫 서술 p50 개선과 p95 5% 이내 비열화이며 최소 3회 반복의 분산도 확인한다. 서버를 실행하지 않는 오프라인 평가로는 실제 첫 서술 gate를 통과했다고 주장하지 않는다.
- **확장성:** 판단 enum/정책/가드가 하나의 타입 계약을 공유하고, 테스트는 모델 어댑터와 분리한다. 새 반응 추가 시 후보표·정합성 정책·fixtures를 함께 수정하게 한다.
- **운영 안전:** feature flag 기본 꺼짐, 실패/timeout/미지 enum/저신뢰/조합 모순 fallback, NPC ID와 컨텍스트 버전 일치, 최종 가드 1회, 기존 감정·관계 CAS 단일 쓰기 경로 보존.

이번 조사에서는 호출 속도나 첫 서술 시간, JEV 정확도를 실측하지 않았다. 별도 비교 평가 결과와 본 설계의 의존성 검토를 함께 보고 도입 여부를 결정한다.
