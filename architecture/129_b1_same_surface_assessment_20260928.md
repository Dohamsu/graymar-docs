# 129. B1 동일 표면 격리 관찰 — 공개 참조와 최종 클릭 (2026-09-28)

## 실험 범위와 재현

- 서버 `ad8b53e`, 격리 DB `graymar_p3_e2e_20260927`, 포트 3015, `CHOICE_GROUNDING_PROPOSAL_EXPERIMENT=true`. 운영 서버·DB는 건드리지 않았고 격리 서버는 종료했다. 극야해안 `92f803d6-6e87-4b95-825c-6dcb83c14568`, 그레이마르 `16c790ad-48ae-4ce4-bc6b-4b76d7ddf857`을 각각 10턴 실행했다. 자동 품질 게이트는 두 런 모두 15/15였으나 아래 의미 검사를 대신하지 않는다.
- [[architecture/128_b1_shadow_same_surface_20260928.json|원자료]]는 12개 shadow 턴의 `publicRefIds`, 생성 후보 affordance, 구조 제안, 최종 Nano ID·라벨·전체 payload와 해당 플레이테스트의 서술·바로 다음 턴 입력 발췌를 담는다. 독립 출처인 [[architecture/128_b1_shadow_stdout_20260928.txt|원시 shadow 로그]], [[architecture/128_b1_star_source_report_20260928.json|극야해안 원본 보고서]], [[architecture/128_b1_graymar_source_report_20260928.json|그레이마르 원본 보고서]]도 보관했다. `node scripts/choice-grounding-shadow-surface.mjs architecture/128_b1_shadow_same_surface_20260928.json --verify-source`로 원시 로그↔감사 기록, 원본 보고서↔발췌, 동일 런·턴·최종 라벨·payload·실제 클릭을 재대조한다.
- 최종 Nano **35개**(극야해안 17·그레이마르 18), 실클릭 **6**, 다음 턴에서 다른 선택지를 누른 노출 **23**, 마지막 턴이라 클릭 미관찰 **6**. 구조 상태는 `CONTRADICTED 22`, `STRUCTURE_MATCH 12`, `UNRESOLVED 1`, `MISSING/MALFORMED 0`. 이유 코드는 중복 허용으로 `UNKNOWN_REF 18`, `INTENT_PAYLOAD_MISMATCH 9`, `LABEL_CHANGED_AFTER_PROPOSAL 4`다. 구조 `intent`↔원 후보 affordance 변경 **4**, 원 후보 affordance↔최종 payload 변경 **5**를 분리했다. 22/35는 유해 선택지 비율이 아니다.
- 격리 테스트 계정에는 각 런 50p씩 총 100p를 발급했고 종료 잔액은 0p다. 격리 DB `turns.llm_token_stats`의 기록 합은 극야해안 $0.006296850·그레이마르 $0.006605982, 평균 `latencyMs`는 각각 2,855·5,172ms(각 13개 DONE 서버 턴)다. 이 값은 모든 에이전트 호출의 실제 청구액이나 Nano 선택지 생성 단계 단독 지연이 아니며, 플래그 OFF 대조 없이 속도 영향으로 해석하지 않는다.

## 같은 표면에서 확인된 오판 경계

| 원자료 위치 | 화면 라벨과 제안 | 관찰 가능한 결론 |
|---|---|---|
| 극야해안 T5 `nano_5_1` | `장부의 기록을 더 자세히 살핀다`의 `targetRef=ITEM:ITEM_SS_STAR_CHART`; 구조 `STRUCTURE_MATCH` | 장면의 숙박 명부와 팩의 **낡은 별자리 도표**는 다른 물건이다. 유효 ID만 맞아도 라벨 대상 바인딩이 틀릴 수 있다. |
| 극야해안 T12 `nano_12_0` | `별기름 램프의 이상한 빛에 대해 질문한다`의 `targetRef=FACT:FACT_SS_FIRST_DREAM`; `STRUCTURE_MATCH` | 램프 질문을 첫 공통몽 시점 fact로 연결했다. 참조 유효성 통과가 질문 출처의 의미 일치를 증명하지 않는다. |
| 그레이마르 T12 `nano_12_0`·`nano_12_1` | 팔뚝 흠집·바닥의 종이 조각을 살피거나 묻는 두 라벨이 모두 `ITEM:ITEM_MINOR_HEALING`을 지목; 둘 다 `STRUCTURE_MATCH` | 이 ID는 **하급 치료제**다. 서술에 종이 조각은 있지만 안정 소품 ID가 없어, 모델이 가용한 인벤토리 ID를 대신 꽂은 사례다. 두 선택지의 허용/거부 판정과 **제안 참조의 오류**는 별개다. |
| 극야해안 T4 `nano_4_1`, 그레이마르 T5 `nano_5_1` | 이렌/회계사에게 말 거는 라벨의 `targetRef`가 각각 내부 `NPC_SS_IREN`/`NPC_EDRIC_VEIL`; `UNKNOWN_REF` | 두 NPC는 해당 서술에 등장한다. 내부 ID를 공개 별칭으로 제안하지 않은 계약 위반은 맞지만, 그것만으로 화면 라벨이 유해하다고 결론낼 수 없다. |
| 그레이마르 T4 `nano_4_0` | 아직 공개되지 않은 `FACT_WAGE_FRAUD_PATTERN`을 지목하면서 `장부와 소문에 대해 더 묻는다`; `UNKNOWN_REF` | 비공개 사실을 **이미 안다고 주장하는 선택지**와 단순히 묻는 **열린 질문**을 같은 신호로 막으면 정상 질문 오차단 가능성이 있다. 이 행은 자동 허용 판정도 아니다. |

위 사례는 `STRUCTURE_MATCH`에 최소 네 건의 **라벨↔참조 의미 불일치**가 있고 `UNKNOWN_REF`에도 **화면상 대화 가능한 NPC/열린 질문**이 섞인다는 결함 증거다. 전체 35개의 사람 `REJECT/ALLOW` 라벨을 완성한 표본은 아니므로 B1 미검출률·오경보율을 산출하지 않는다. §124의 A1 40건과 이번 런의 동일 표면 겹침도 **0**이다.

## 다음 구현 경계

1. B1 제안의 `targetRef`가 유효한지만 검사하지 말고, 라벨에서 주장하는 대상·소유·매체와 **동일 실체**인지 평가할 검증 계약을 먼저 만든다. 인벤토리 아이템을 일반 장면 소품의 대리 ID로 쓰지 못하게 하되, 미해결 소품을 부재로 확정하지 않는다.
2. 공개 NPC 별칭과 내부 NPC ID의 연결 정책, 비공개 fact를 묻는 열린 질문의 조건, 제안 후 STEER 교체 시 구조 폐기/재제안 정책을 정한다. 이 결정 전에는 `UNKNOWN_REF`를 바로 UI 차단으로 승격하지 않는다.
3. 고정 A1 사례와 동일한 최종 Nano 표면·사람 판정·클릭을 확보해 미검출/오경보를 측정한다. 플래그 OFF 동경로 대조 및 선택지 생성 지연도 아직 없다. B2 한 LOCATION 활성화는 그 이후의 별도 관문이며, P3-2/P2-E는 계속 열린다.

이번 블록은 실모델 관찰과 감사 도구·증거 보관이다. B1 제안은 운영 기본값 OFF, 선택지 동작 수정·차단 없음. 기존 반복 증상 R1~R3의 수정·재검증 시도는 각각 **0/2회**다.
