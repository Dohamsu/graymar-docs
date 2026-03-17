# Character Growth System v1
> 통합 문서: Progression System + Permanent Growth System
> 방향: 스토리 중심 RPG + RUN 단위 탐험 구조
> 목표: 장비는 RUN 단위 리셋, 캐릭터 능력은 영구 성장
> 범위: 전술 + 정치 + 마법 확장 기반

---

## 1. 핵심 철학

이 게임은 "반복되는 탐험"이 아닌
"에피소드형 임무 수행" 구조이다.

각 RUN은:

- 특정 지역 탐험
- 특정 사건 해결
- 특정 목표 달성

을 의미한다.

RUN 종료는 실패가 아니라
**임무 완료 또는 철수** 개념이다.

플레이어는 RUN마다 경험을 축적하며,
성장 방향은 플레이어가 자유롭게 선택한다.
빌드 강제는 없지만 플레이 성향은 자연스럽게 형성된다.

---

## 2. 장비 리셋의 스토리적 정당화

### 2.1 기본 설정

플레이어는 용병/탐험가/조사관 소속이다.

각 RUN 시작 시:

- 소속 기관(용병 집합소, 기사단, 길드, 마을 의회 등)에서
- 기본 장비를 배급받음
- 임무 종료 후 장비는 회수됨

### 2.2 장비 리셋 근거

스토리적 설명:

- 장비는 길드 소유 자산
- 고위 장비는 특정 임무 전용
- 위험 지역 장비는 정화/격리 필요
- 군수 체계상 개인 소유 불가
- 임무 보고 후 장비 반납 의무

> 따라서 RUN 종료 시 장비 리셋은 자연스럽다.

---

## 3. RUN 내부 성장

RUN 내에서만 유지되는 임시 요소:

- 임시 장비
- 임시 버프
- 일시적 스킬 해금
- 노드 기반 강화

RUN 종료 시 전부 초기화된다.

---

## 4. Growth Point(GP) 시스템

### 4.1 GP 정의

RUN 종료 시 다음 항목을 합산하여 Growth Point(GP)를 지급한다:

- StoryClearBonus
- NodeClearBonus
- 특별 이벤트 보상

### 4.2 GP 획득 경로

- RUN 완료
- 메인 아크 진행
- 정치적 선택 성공
- 고위험 RUN 성공
- 특정 세력 신뢰도 달성

### 4.3 GP 투자 규칙

- GP는 허브에서만 투자 가능
- 영구 기본 스탯 또는 특성 트리에 투자
- 각 스탯은 단계별 비용 증가

---

## 5. 기본 스탯 (Permanent Stats)

GP로 투자 가능한 영구 능력치:

| 스탯 | 설명 | 전투/판정 효과 |
|------|------|----------------|
| Max HP | 최대 체력 | HP 상한 증가 |
| Max Stamina | 최대 스태미나 | Stamina 상한 증가 |
| Base Attack | 기본 공격력 | ATK 기본값 증가 |
| Base Defense | 기본 방어력 | DEF 기본값 증가 |
| Crit Base | 치명타 기본값 | CRIT% 기본값 증가 |
| Tactical Awareness | 위치 판정 보너스 | 환경 활용 판정 +bonus, SIDE/BACK 전환 성공률 +bonus |
| Political Influence | 설득 판정 보너스 | TALK 판정 +bonus, 세력 평판 획득량 ×(1 + level×0.1) |

> Tactical Awareness: 위치 변경 시 d20 + TacticalAwareness ≥ 12이면 SIDE→BACK 전환 가능
> Political Influence: TALK 판정 시 d20 + PoliticalInfluence ≥ 10 + NPC_resistance로 성공/실패 판정

추가로 **특성 슬롯 해금**도 GP 투자 대상이다.

### 5.1 GP 투자 비용 테이블

cost = baseCost × (1 + currentLevel × 0.15)

| 스탯 | baseCost | 최대 레벨 | 비고 |
|------|----------|-----------|------|
| Max HP | 3 GP | 20 | |
| Max Stamina | 4 GP | 10 | |
| Base Attack | 5 GP | 15 | ATK 기본값 |
| Base Defense | 5 GP | 15 | DEF 기본값 |
| Base ACC | 4 GP | 12 | 명중 보정 |
| Base EVA | 4 GP | 12 | 회피 보정 |
| Crit Base | 6 GP | 12 | CRIT% 기본값 |
| Crit DMG | 6 GP | 8 | CRIT_DMG 배율 (기본 1.5, 최대 2.5) |
| Base RESIST | 4 GP | 12 | 상태이상/DOWNED 저항 |
| Base SPEED | 3 GP | 10 | 다수 적 전투 resolve 순서 |
| Tactical Awareness | 4 GP | 10 | 위치 판정 보너스 |
| Political Influence | 4 GP | 10 | 설득 판정 보너스 |
| 특성 슬롯 해금 | 8 GP (고정) | 6 | |

> ACT당 평균 GP 수입: ACT1 ~15GP, ACT2 ~25GP, ACT3 ~35GP, ACT4 ~45GP, ACT5 ~55GP, ACT6 ~65GP
> 모든 스탯을 최대까지 올리는 것은 불가능하도록 설계 (선택의 의미 유지)

---

## 6. 특성 트리: 전술 (Tactical Path)

특성은 능동 효과보다는 **조건 완화 / 보너스 강화** 위주이다.

전술 트리 효과:

- 보너스 슬롯 조건 완화
- 완벽 회피 시 확률 증가
- 측면 판정 보너스
- ENGAGED 상태 유지 보너스
- 다수 적 상대 페널티 감소

---

## 7. 특성 트리: 정치 (Diplomatic Path)

정치 트리 효과:

- 설득 성공률 증가
- 세력 평판 획득량 증가
- 협상 비용 감소
- 허브 이벤트 추가 선택지 해금
- 정치 긴장 완화 능력

---

## 8. 특성 트리: 전략/정보 (Strategic Path)

전략/정보 트리 효과:

- 적 AI 의도 예측 힌트
- 환경 태그 판정 보너스
- 함정 탐지 강화
- RUN 내 자원 효율 증가
- 마법 사용 비용 감소

---

## 9. 마법 연계

특정 특성 해금 시 마법 시스템과 연동된다:

- 마법 Action 비용 감소
- 마법 사용 후 정치 반작용 감소
- 특정 세력 의심도 완화

---

## 10. 성장 한계

- 모든 트리를 완전 마스터할 수 없다
- GP는 제한적으로 공급된다
- 선택의 의미를 유지하기 위한 설계이다

---

## 11. 영웅 서사 단계

성장 시스템은 서사 진행과 연동된다:

| 단계 | 플레이어 상태 |
|------|---------------|
| 초기 | 생존 중심 |
| 중반 | 전술/정치 선택 분화 |
| 후반 | 플레이어 고유 스타일 확립 |

---

## 12. UI 설계 및 저장 구조

### 12.1 허브 UI

허브에서 다음 패널을 표시한다:

- 스탯 패널
- 특성 트리 패널
- 세력 영향 표시
- 마법 해금 상태 표시

### 12.2 저장 구조

> player_profile 저장 구조 정본: `schema/07_database_schema.md` player_profiles
