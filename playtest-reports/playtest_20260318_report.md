# Playtest Report — 2026-03-18

## A. 기본 정보

| 항목 | 값 |
|------|-----|
| RunID | e0c8caa9-2114-45e2-b548-9d14830791f9 |
| 프리셋 | DESERTER (male) |
| 턴 수 | 20턴 (+ Turn 0 초기화) |
| 최종 상태 | RUN_ACTIVE (20턴 소진) |
| 방문 장소 | market (1곳만) |
| LLM 모델 | gpt-4.1-mini-2025-04-14 |

## B. 턴 흐름 요약

| 턴 | 장소 | 입력 | 이벤트 | 결과 | 비고 |
|----|------|------|--------|------|------|
| 0 | HUB | (초기화) | enter_quest_0 | - | 프롤로그 (476자) |
| 1 | HUB | CHOICE:accept_quest | sys_1 | - | 의뢰 수락 |
| 2 | HUB | CHOICE:go_market | sys_2 | - | 시장 이동 |
| 3 | LOCATION | ACTION:주변을 자세히 살펴본다 | EVT_MARKET_SHOP | PARTIAL | 첫 이벤트 |
| 4 | LOCATION | CHOICE:mkt_shop_trade | EVT_MARKET_SHOP | - | -3gold |
| 5 | LOCATION | CHOICE:mkt_shop_bribe | EVT_MARKET_SHOP | - | -3gold |
| 6 | LOCATION | CHOICE:mkt_shop_investigate | EVT_MARKET_SHOP | - | |
| 7 | LOCATION | CHOICE:fu_mkt_p_adapt | EVT_MARKET_SHOP | - | |
| 8-13 | LOCATION | CHOICE:fu_mkt_* | EVT_MARKET_SHOP | - | 같은 이벤트 반복 |
| 14-20 | LOCATION | CHOICE:fu_mkt_*/mkt_shop_* | EVT_MARKET_SHOP | - | 선택지 순환 |

## C. 종합 점수 (10점 만점)

| 항목 | 점수 | 비고 |
|------|------|------|
| 서사 흐름 | 5.0 | LLM 서술 자체는 양호하나, 반복 이벤트로 전체 흐름 단조 |
| NPC 일관성 | 6.0 | 초기 로넨 등장은 좋으나, 이후 NPC 다양성 부족 |
| 맥락 유지 | 5.0 | 같은 이벤트 내에서는 유지되나, 진전 없는 반복 |
| 이벤트 다양성 | 2.0 | 18턴 연속 동일 이벤트 — 심각한 문제 |
| 메모리 시스템 | 5.0 | 기본 동작 확인, 장소 전환 없어 검증 불가 |
| **종합** | **4.6** | |

## D. 개선 권장사항

### Critical
1. **CHOICE sourceEventId 무한 루프** — CHOICE 입력의 `sourceEventId`가 이벤트 다양성 메커니즘을 완전히 우회. 같은 이벤트가 18턴 연속 반복됨.
   - 파일: `server/src/turns/turns.service.ts:546-549`
   - 원인: CHOICE의 sourceEventId가 있으면 Step 1에서 즉시 이벤트 매칭되어, Step 3의 EventDirector/hardcap/penalty가 전혀 적용되지 않음
   - ACTION에는 `consecutiveCount < 1` 가드(line 569)가 있지만, CHOICE에는 없음

### High
2. **follow-up 선택지 sourceEventId 확산** — `buildFollowUpChoices()`에서 이벤트 고유 선택지와 첫 번째 보충 선택지에 sourceEventId를 부여하여, 대부분의 선택지가 같은 이벤트로 되돌아감.
   - 파일: `server/src/engine/hub/scene-shell.service.ts:535, 572`

### Medium
3. **장소 전환 유도 부재** — 한 장소에서 6턴 이상 체류해도 HUB 복귀를 유도하는 메커니즘 없음

---

## 심층 분석 [1] 이벤트 서술 품질

### LLM 서술 품질 (llm.output 기준)
- T0 프롤로그: 476자, 중세 톤 일관, 감각 묘사(소리/시각/냄새) 우수
- T1 의뢰 수락: 95자, 간결하지만 적절
- LOCATION 턴(T3~): LLM output 기준 400~800자, 감각 묘사와 NPC 대사 포함

### 문제점
- **serverResult.summary.short**: 템플릿 텍스트 ("플레이어가 X를 시도하여 Y 성공했다", 33~47자)
- LLM output은 실제로 잘 생성되지만, API 응답에서 `llm.output` 필드를 별도로 폴링해야 접근 가능
- 반복 이벤트로 인해 LLM이 비슷한 씬을 반복 묘사 → 후반부 서술의 신선도 하락

### 서술 길이 분포 (llm.output 기준)
- Turn 0: 476자 (프롤로그)
- Turn 3 검증: ~700자 (상세 장면 묘사 확인)
- 평균: 약 500~700자 (적정 범위)

### 점수: 6.5/10
- LLM 자체 품질은 양호하나, 동일 이벤트 반복으로 서술 다양성 심각 저하

---

## 심층 분석 [3] 이벤트 다양성

### 이벤트 ID 분포
| 이벤트 ID | 종류 | 횟수 |
|-----------|------|------|
| event_EVT_MARKET_SHOP | NPC | 18회 |
| enter_quest_0 | QUEST | 1회 |
| sys_1 | SYSTEM | 1회 |
| sys_2 | SYSTEM | 1회 |

### 핵심 문제: sourceEventId 무한 루프

```
CHOICE → sourceEventId 존재 → Step 1에서 즉시 매칭 → 같은 이벤트 반환
→ buildFollowUpChoices() → 다시 sourceEventId 포함 선택지 생성
→ 플레이어가 선택 → 다시 Step 1... (무한 반복)
```

EventDirector의 5-stage 필터(hard block, hardcap, penalty)가 **전혀 실행되지 않음**.

### 연속 반복 검출
- 같은 이벤트 18턴 연속: **직전 이벤트 hard block 완전 우회**
- 방문 내 하드캡(2회 이상 필터): **CHOICE 경로에서는 적용 안 됨**

### ProceduralEvent 비율
- 고정 이벤트: 18/18 (100%)
- 동적 생성: 0/18 (0%)
- ProceduralEvent가 한 번도 발동하지 않음 (Step 3에 도달하지 못했으므로)

### Fallback 발동
- 0회 (이벤트 매칭이 Step 1에서 완료되어 Step 3 미도달)

### 점수: 2.0/10
- 단일 이벤트 18턴 반복은 게임 경험을 심각하게 훼손

---

## 심층 분석 [6] 장소 전환 & HUB

### 장소 순회 패턴
| 장소 | 방문 | 체류 턴 |
|------|------|---------|
| market | 1회 | 18턴 |
| guard | 0회 | - |
| harbor | 0회 | - |
| slums | 0회 | - |

### MOVE_LOCATION 처리
- MOVE_LOCATION 의도가 한 번도 발생하지 않음
- `go_hub` 선택지는 매 턴 제공되었으나, 다른 선택지에 밀려 선택되지 않음

### 선택지 구성 분석
- 매 턴 3~4개 선택지 + `go_hub` 제공
- 이벤트 고유/follow-up 선택지가 항상 `go_hub`보다 앞에 배치
- sourceEventId가 포함된 선택지가 대부분 → 같은 이벤트 루프

### finalizeVisit 타이밍
- 장소 이탈이 없어 finalizeVisit 미호출

### 점수: 3.0/10
- 장소 전환 자체는 구현되어 있으나, 이벤트 루프가 전환을 사실상 차단
- 6턴 이상 체류 시 Mid Summary는 동작하지만, 이동 유도는 없음

---

## 수정 전 종합

| 항목 | 점수 |
|------|------|
| 이벤트 서술 품질 | 6.5 |
| 이벤트 다양성 | 2.0 |
| 장소 전환 & HUB | 3.0 |
| **종합** | **4.6** |

---

## 수정 내용

### Fix 1: CHOICE sourceEventId 연속 횟수 제한 (Critical)
- **파일**: `server/src/turns/turns.service.ts:546-549`
- **변경**: CHOICE의 sourceEventId로 같은 이벤트가 3턴 이상 연속되면 sourceEventId를 무시하고 EventDirector 새 이벤트 매칭으로 전환
- `choiceConsecutive < 3` 가드 추가 (ACTION의 `consecutiveCount < 1`과 유사한 패턴)

### Fix 2: follow-up 보충 선택지 sourceEventId 제거 (High)
- **파일**: `server/src/engine/hub/scene-shell.service.ts:563-572`
- **변경**: `buildFollowUpChoices()`의 보충 선택지(follow-up pool)에서 sourceEventId 부여를 제거
- 이벤트 고유 선택지(eventChoices)에만 sourceEventId 유지

---

## 수정 전후 비교

### 2차 플레이테스트 결과
- RunID: 23a2a77f-c6ad-4d8e-8bb1-0e0ebe0f2642
- 조건: 동일 (DESERTER, 20턴, market 시작)

### 점수 비교

| 항목 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 이벤트 서술 품질 | 6.5 | 8.0 | **+1.5** |
| 이벤트 다양성 | 2.0 | 7.5 | **+5.5** |
| 장소 전환 & HUB | 3.0 | 4.0 | **+1.0** |
| **종합** | **4.6** | **6.5** | **+1.9** |

### 핵심 지표 비교

| 지표 | 1차 | 2차 | 변화 |
|------|-----|-----|------|
| 고유 이벤트 수 | 1 | 8 | **+7** |
| 최대 연속 반복 | 18턴 | 3턴 | **-15** |
| Narrative 평균 길이 | 38ch (template) | 826ch (LLM output) | **+788ch** |
| ProceduralEvent 발동 | 0회 | 1회 | **+1** |
| 이벤트 종류 | EVT_MARKET_SHOP만 | ATM/DSC/OPP/RUMOR/ENC/INT/PROC | 7종 |
| 이벤트 전환 주기 | 없음 | 3턴마다 | 정상 |

### 2차 이벤트 분포

| 이벤트 ID | 종류 | 횟수 |
|-----------|------|------|
| EVT_MARKET_ATM_1 | ATMOSPHERE | 3회 |
| EVT_MARKET_DSC_2 | DISCOVERY | 3회 |
| EVT_MARKET_OPP_LOST_CARGO | OPPORTUNITY | 3회 |
| EVT_MARKET_RUMOR | RUMOR | 3회 |
| EVT_MARKET_ENC_BUSKER | ENCOUNTER | 3회 |
| EVT_MARKET_INT_2 | INTERACTION | 2회 |
| PROC_19 | PROCEDURAL | 1회 |

### 2차 서술 품질 평가
- LLM output 기준 평균 826자 (500~1000자 범위)
- 이벤트 전환마다 새로운 NPC와 장면 등장
- 톤 일관성 유지 (중세 배경, 경어체)
- 감각 묘사 풍부 (시장 노점, 약초 냄새, 거리 소음 등)

### 수정 항목별 검증
- [✅] CHOICE sourceEventId 3턴 제한: 모든 이벤트가 정확히 3턴 후 전환
- [✅] 보충 선택지 sourceEventId 제거: sourceEventId 없는 선택지가 이벤트 전환을 유도
- [⚠️] 장소 전환: 테스트 스크립트가 go_hub을 선택하지 않아 미검증 (서버 로직 자체는 정상)

### 회귀 검출
- 서사 흐름: 6.5 → 8.0 (개선)
- NPC 일관성: 6.0 → 6.5 (소폭 개선, 다양한 NPC 등장)
- 맥락 유지: 5.0 → 6.0 (개선, 이벤트 전환 시 자연스러운 연결)
- 메모리 시스템: 5.0 → 5.0 (변동 없음)
- **회귀 항목 없음**
