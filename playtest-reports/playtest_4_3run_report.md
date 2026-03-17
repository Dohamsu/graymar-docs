# 플레이테스트 리포트 #4 — 3런 자동 테스트

> 일시: 2026-02-21
> 서버: NestJS localhost:3000
> LLM: openai / gpt-4o-mini
> 목적: NEW-1~5 수정 검증 + 신규 이슈 탐색

---

## 테스트 구성

| Run | 프리셋 | 성별 | 경로 | 턴 수 | 테스트 초점 |
|-----|--------|------|------|-------|------------|
| 1 | DOCKWORKER | male | LOC_MARKET | 10 | 거래/설득/관찰 파싱 |
| 2 | SMUGGLER | female | LOC_HARBOR → LOC_SLUMS | 14 | 다중 장소 + 은밀 행동 |
| 3 | HERBALIST | male | LOC_GUARD | 11 | 에스컬레이션 + 뇌물 재검증 |

---

## Run 1: DOCKWORKER (male) → LOC_MARKET

### 프롤로그
```
"부두에서 당신이 일하는 것을 봤소. 길드 안 사람은 아무도 믿을 수가 없어서… 외부 사람이 필요했소."
```
✅ DOCKWORKER 전용 prologueHook 정상 반영

### 턴별 분석

| Turn | Input | Parsed | Expected | Resolve | 평가 |
|------|-------|--------|----------|---------|------|
| T4 | 가판대의 물건을 살펴보며 상인에게 흥정을 시도한다 | **INVESTIGATE** | TRADE | PARTIAL | ❌ "살펴"→INVESTIGATE 우선 |
| T5 | 주변을 둘러보며 수상한 움직임이 없는지 살핀다 | OBSERVE | OBSERVE | PARTIAL | ✅ |
| T6 | 상인에게 진심을 담아 협력을 요청하며 정보를 구한다 | PERSUADE | PERSUADE | PARTIAL | ✅ |
| T7 | 장부를 꺼내서 살펴보며 기록을 확인한다 | INVESTIGATE | INVESTIGATE | PARTIAL | ✅ "꺼내서 살펴" 수정 작동 |
| T8 | 금화를 꺼내 상인 앞에서 흔들며 특별한 정보를 요구한다 | BRIBE | BRIBE | PARTIAL | ✅ NEW-2 수정 검증 |

**파싱 정확도**: 4/5 = 80%

**WorldState 변화**: heat 0 유지(시장은 저위험), DAY→NIGHT 진행 정상

**LLM 품질**: 400~520 토큰, 장면 요소 반영 양호 (상인 다툼, 뒷골목 상자 등)

**Resolve 분석**: 전부 PARTIAL — DOCKWORKER의 해당 스탯이 낮음 (ACC=3 INVESTIGATE, SPEED=4 PERSUADE/BRIBE). 스탯 그라데이션 정상 작동.

---

## Run 2: SMUGGLER (female) → LOC_HARBOR → LOC_SLUMS

### 프롤로그
```
"당신이 세관을 교묘히 빠져나간다는 걸 알고 있소. 사람을 찾아야 하는데… 그런 재주가 필요하오."
```
✅ SMUGGLER 전용 prologueHook 정상 반영

### 턴별 분석 — LOC_HARBOR

| Turn | Input | Parsed | Expected | Resolve | 평가 |
|------|-------|--------|----------|---------|------|
| T4 | 눈에 띄지 않게 조용히 창고 뒤편으로 잠입한다 | SNEAK | SNEAK | SUCCESS | ✅ EVA7→+2 보너스 |
| T5 | 부두에서 쉬고 있는 선원에게 말을 건다 | **REST** | TALK | (없음) | ❌ "쉬고"→REST 오매칭 |
| T6 | 감시가 소홀한 틈을 타 선적 명부를 슬쩍 챙긴다 | **SNEAK** | STEAL | PARTIAL | ❌ "슬쩍 챙" 미등록 |

### 턴별 분석 — LOC_SLUMS

| Turn | Input | Parsed | Expected | Resolve | 평가 |
|------|-------|--------|----------|---------|------|
| T11 | 뒷골목 정보원에게 은화를 내밀며 소문을 물어본다 | BRIBE | BRIBE | SUCCESS | ✅ SPEED7→+2 보너스 |
| T12 | 수상한 건물의 뒷문을 열어보며 안을 조사한다 | INVESTIGATE | INVESTIGATE | SUCCESS | ✅ |

**파싱 정확도**: 3/5 = 60%

**다중 장소 전환**: HARBOR → HUB → SLUMS 정상. HUB 복귀 시 heat 감쇠 정상 (heat 1→0).

**성별 반영**: T11 내러티브에서 "아가씨"로 호칭 ✅ (female SMUGGLER)

**LLM 품질**: T5 REST로 파싱되었으나 LLM은 대화 장면을 자연스럽게 서술. T11 BRIBE 장면의 빈민가 분위기 묘사 우수.

**Resolve 분석**: SNEAK SUCCESS (EVA7→+2), BRIBE SUCCESS (SPEED7→+2) — SMUGGLER의 강점 스탯이 판정에 정확히 반영됨.

---

## Run 3: HERBALIST (male) → LOC_GUARD

### 프롤로그
```
"당신의 약초 솜씨가 이 도시에서 꽤 알려졌다더군요. 세 세력 모두와 거래하는 사람이라면… 어디든 자연스럽게 드나들 수 있을 것이오."
```
✅ HERBALIST 전용 prologueHook 정상 반영 + "약초" 키워드 포함

### 턴별 분석

| Turn | Input | Parsed | Expected | Resolve | 평가 |
|------|-------|--------|----------|---------|------|
| T4 | 검을 꺼내들며 경비병에게 장부 행방을 대라고 으름장을 놓는다 | THREATEN | THREATEN | PARTIAL | ✅ **NEW-1 수정 검증** |
| T5 | 경비병의 멱살을 잡으며 가만두지 않겠다고 위협한다 | THREATEN | THREATEN | PARTIAL | ✅ insistence=1 |
| T6 | 칼을 겨누며 마지막 경고를 날린다 가만두지 않겠다 | **FIGHT** (esc) | FIGHT | SUCCESS | ✅ **에스컬레이션 작동** |
| T7 | 호주머니에서 금화를 꺼내 경비병 앞에 흔들며 정보를 요구한다 | BRIBE | BRIBE | PARTIAL | ✅ **NEW-2 수정 검증** |
| T8 | 부상당한 경비병을 발견하고 약초로 치료해주겠다고 제안한다 | HELP | HELP | SUCCESS | ✅ DEF9→+3 보너스 |
| T9 | 경비대장에게 진심을 담아 약재 납품 거래를 제안하며 신뢰를 구한다 | PERSUADE | PERSUADE | PARTIAL | ✅ |

**파싱 정확도**: 6/6 = 100%

### 고집 에스컬레이션 상세

```
T4: THREATEN (insistence=0) → heat 0→2
T5: THREATEN (insistence=1) → heat 2→4
T6: FIGHT   (insistence=2, escalated=True) → heat 4→7 ← 에스컬레이션!
```
✅ 3회 연속 THREATEN → FIGHT 에스컬레이션 완벽 작동 (NEW-3 수정 검증)

### Heat 추적

```
T4: heat=2  (THREATEN → +2)
T5: heat=4  (THREATEN → +2)
T6: heat=7  (FIGHT escalation → +3)
T7: heat=7  (BRIBE → +0)
T8: heat=8  (HELP → +1 누적)
T9: heat=8  (유지)
```
✅ 공격적 행동에 비례한 Heat 상승 정상

### LLM 내러티브 하이라이트

**T6 에스컬레이션 (FIGHT)**:
> "당신은 칼을 번뜩이며 경비병에게 마지막 경고를 날렸다. '가만두지 않겠다!'라는 강력한 목소리가 훈련장에 울려 퍼졌다."

**T8 HELP (약초상 정체성 반영)**:
> "'이걸로 치료해줄 수 있어. 조금만 참아봐.' 당신이 약초를 펼치며 말했다... 약초의 향기가 퍼지면서, 경비병은 조금씩 진정하는 듯 보였다."

✅ LLM이 프리셋의 정체성(약초상)과 에스컬레이션 상황을 자연스럽게 서술

---

## 신규 이슈

### NEW-6 (P1): "살펴보며 흥정" → INVESTIGATE (TRADE 기대)

**입력**: "가판대의 물건을 **살펴보며** 상인에게 **흥정**을 시도한다"
**원인**: "살펴" (INVESTIGATE 1 hit) vs "흥정" (TRADE 1 hit) → 동점 시 KEYWORD_MAP 순서에서 INVESTIGATE 우선
**영향**: 거래/교환 맥락에서 "살펴보다"가 자연스러운 수식어임에도 INVESTIGATE로 분류
**제안**: TRADE에 복합 키워드 추가 ("물건을 살", "흥정을 시", "값을 물") 또는 "살펴" 단독 매칭 약화

### NEW-7 (P1): "쉬고 있는 선원" → REST (TALK 기대)

**입력**: "부두에서 **쉬고 있는** 선원에게 **말을 건다**"
**원인**: "쉬고" → REST ("쉬" 키워드 매칭), "말을 건" → TALK. 동점에서 REST 우선
**영향**: "쉬고 있는"은 NPC 상태 묘사이지 플레이어 행동이 아님. REST는 본래 자기 휴식 의도
**제안**: REST 키워드에서 "쉬" 단독을 제거하고 "쉬어", "쉬겠", "쉬자", "쉬려" 등 의지 표현만 남기기

### NEW-8 (P2): "슬쩍 챙긴다" → SNEAK (STEAL 기대)

**입력**: "감시가 소홀한 **틈을 타** 선적 명부를 **슬쩍 챙긴다**"
**원인**: "틈을 타" → SNEAK (1 hit), "슬쩍 챙" → STEAL 키워드에 미등록 (0 hit)
**영향**: 절도 의도가 SNEAK으로 분류되어 판정 스탯이 달라짐
**제안**: STEAL에 "슬쩍 챙" 추가

---

## 이전 수정 검증 요약 (NEW-1~5)

| 수정 | 검증 결과 | 상세 |
|------|----------|------|
| **NEW-1**: INVESTIGATE "꺼내" 제거 | ✅ 통과 | "검을 꺼내들며 으름장" → THREATEN (Run3 T4) |
| **NEW-2**: BRIBE 키워드 추가 | ✅ 통과 | "금화를 꺼내 흔들며" → BRIBE (Run1 T8, Run3 T7) |
| **NEW-3**: 고집 에스컬레이션 | ✅ 통과 | THREATEN×3 → FIGHT (Run3 T6, escalated=True) |
| **NEW-4**: 프리셋별 프롤로그 | ✅ 통과 | 3개 프리셋 모두 전용 hook 반영 |
| **NEW-5**: "자유롭게 행동한다" 제거 | ✅ 통과 | 이전 검증 스크립트에서 확인 (0건) |

---

## 시스템 건전성

| 항목 | 상태 | 비고 |
|------|------|------|
| LLM 생성 | ✅ 전 턴 DONE | 400~530 토큰, gpt-4o-mini |
| 판정 시스템 | ✅ 정상 | 스탯 보너스 정확 반영 |
| Heat 시스템 | ✅ 정상 | 공격적 행동에 비례 상승, HUB 복귀 시 감쇠 |
| 시간 진행 | ✅ 정상 | DAY→NIGHT 자연 전환 |
| 다중 장소 | ✅ 정상 | Harbor→HUB→Slums 원활 전환 |
| 성별 반영 | ✅ 정상 | "아가씨" (female SMUGGLER) |
| 프리셋 정체성 | ✅ 우수 | 약초상 → 약초 치료 서술, 밀수업자 → 잠입 특화 |
| 이벤트 다양성 | ⚠️ 보통 | 동일 장소 연속 턴에서 같은 SceneDisplay 반복 가능 |
| 선택지 | ✅ 정상 | "자유롭게 행동" 제거됨 |

---

## 점수

| 항목 | 이전(#3) | 현재(#4) | 변화 |
|------|---------|---------|------|
| 파싱 정확도 | 50% (3/6) | **81%** (13/16) | +31% |
| 에스컬레이션 | ❌ 미작동 | ✅ 완벽 작동 | — |
| 프롤로그 개인화 | ❌ 동일 텍스트 | ✅ 프리셋별 차별화 | — |
| LLM 품질 | 7/10 | **8/10** | +1 |
| 시스템 안정성 | 8/10 | **9/10** | +1 |
| **종합** | **6.4/10** | **8.0/10** | **+1.6** |

---

## 다음 우선순위

1. **NEW-7 (P1)**: REST "쉬" 키워드 축소 — 가장 빈번한 오매칭 원인
2. **NEW-6 (P1)**: TRADE 키워드 보강 — "살펴보며 흥정" 케이스
3. **NEW-8 (P2)**: STEAL "슬쩍 챙" 추가 — 단순 누락
