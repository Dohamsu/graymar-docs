# 06 --- Graymar 콘텐츠 설계

> **정본 데이터**: `content/graymar_v1/` (21 JSON + 1 README)
> **의존 문서**: `HUB_RPG_Engine_Spec_v2.md` (HUB 엔진), `03_combat_rules.md` (전투 수치)
> **이전 문서**: `08_graymar_scenario.md` (DAG 라우팅 포함, 본 문서로 대체)

---

## 1. 시나리오 개요 --- 그레이마르 항구 도시

### 1.1 배경

그레이마르는 왕국 남부의 항만 도시다. 항만 세금 횡령과 밀수가 얽힌 권력 부패가 도시를 잠식하고 있다. 플레이어는 이름 없는 용병으로서 실종 사건 조사를 통해 도시의 어두운 진실에 접근한다.

### 1.2 메인 퀘스트 --- 사라진 공물 장부

| 항목 | 값 |
|------|-----|
| questId | `MAIN_Q1_LEDGER` |
| 규모 | 왕국 정치 연계 |
| 퀘스트 상태 | S0_ARRIVE → S1_GET_ANGLE → S2_PROVE_TAMPER → S3_TRACE_ROUTE → S4_CONFRONT → S5_RESOLVE |

**Fact 키** (11개): `FACT_LEDGER_EXISTS`, `FACT_WAGE_FRAUD_PATTERN`, `FACT_TAMPERED_LOGS`, `FACT_ROUTE_TO_EAST_DOCK`, `FACT_INSIDE_JOB`, `FACT_SMUGGLE_ROUTE_GUILD`, `FACT_MAIREL_GUILD_EVIDENCE`, `FACT_OFFICIAL_INQUIRY`, `FACT_MAIREL_GUARD_EVIDENCE`, `FACT_SHADOW_INTEL`, `FACT_BOTH_SIDES_EVIDENCE`

### 1.3 분위기 곡선

- **초반**: 조사/의심 -- 도시 탐색, 단서 수집
- **중반**: 갈등 고조 -- 세력 충돌, 선택 압박
- **후반**: 대면/폭로 -- 클라이맥스 전투, 아크 해결

### 1.4 현재 게임 구조

현재 구현된 시스템은 **HUB 중심 순환 탐험**이다:

```
HUB (4개 LOCATION 선택)
  └─ LOCATION (Action-First 파이프라인)
       ├─ EventMatcher → ResolveService → 결과
       ├─ COMBAT 발생 가능
       └─ HUB 복귀
```

플레이어는 HUB에서 LOCATION을 선택하고, LOCATION에서 자유 행동(ACTION)을 수행한다. EventMatcher가 행동에 맞는 이벤트를 매칭하고, ResolveService가 판정한다. 전투가 발생하면 COMBAT 페이즈로 전환된다.

---

## 2. 콘텐츠 파일 목록

`content/graymar_v1/` 디렉토리에 21개 JSON 파일이 존재한다.

| # | 파일명 | 용도 | 주요 키 |
|---|--------|------|---------|
| 1 | `player_defaults.json` | 기본 플레이어 스탯/장비 (미사용, presets로 대체) | -- |
| 2 | `presets.json` | 4종 캐릭터 프리셋 | presetId |
| 3 | `enemies.json` | 적 9종 정의 | enemyId |
| 4 | `encounters.json` | 전투 조합 9종 + 보상 | encounterId |
| 5 | `items.json` | 아이템 카탈로그 (단서 3 + 소모품 + 키 아이템) | itemId |
| 6 | `npcs.json` | NPC 7명 + unknownAlias (소개 전 별칭) | npcId |
| 7 | `factions.json` | 세력 4개 + 초기 평판 | factionId |
| 8 | `quest.json` | 메인 퀘스트 상태/Fact 정의 | questId |
| 9 | `locations.json` | 4개 LOCATION 정의 | locationId |
| 10 | `events_v2.json` | HUB 이벤트 88개 (LOCATION당 22개, eventCategory 포함) | eventId |
| 11 | `scene_shells.json` | LOCATION x TimePhase x Safety 분위기 텍스트 (v1) | locationId.timePhase.safety |
| 12 | `scene_shells_v2.json` | 확장 분위기 텍스트 (v2) | locationId.timePhase.safety |
| 13 | `suggested_choices.json` | eventType별 선택지 템플릿 | eventType |
| 14 | `arc_events.json` | 아크 루트별 이벤트 (3루트 x 3단계) | arcRouteTag |
| 15 | `combat_rules.json` | 전투 수치 공식 (엔진 참조용) | hit/damage/crit/stamina |
| 16 | `shops.json` | 상점 정의 (아이템/가격) | shopId |
| 17 | `sets.json` | 장비 세트 정의 | setId |
| 18 | `region_affixes.json` | 리전 접미사 정의 | affixId |
| 19 | `incidents.json` | Incident 정의 (Narrative Engine v1) | incidentId |
| 20 | `endings.json` | 엔딩 조건/결과 정의 | endingId |
| 21 | `narrative_marks.json` | 12개 불가역 표식 정의 | markId |

---

## 3. 4개 LOCATION 설계

### 3.1 LOCATION 목록

| locationId | 이름 | 태그 | 위험도 | 야간 가능 |
|------------|------|------|--------|----------|
| `LOC_MARKET` | 시장 거리 | TRADE, SOCIAL, CROWDED | 1 | O |
| `LOC_GUARD` | 경비대 지구 | AUTHORITY, MILITARY, STRICT | 2 | O |
| `LOC_HARBOR` | 항만 부두 | MARITIME, DANGEROUS, NIGHT | 3 | O |
| `LOC_SLUMS` | 빈민가 | UNDERGROUND, DANGER, HIDDEN | 4 | O |

### 3.2 LOCATION 특성

**시장 거리** (LOC_MARKET) -- 정보 수집과 거래의 중심지. 상인들의 소문을 통해 사건의 실마리를 잡는다. 위험도가 가장 낮아 초반 탐색에 적합하다.

**경비대 지구** (LOC_GUARD) -- 질서 유지 구역이나 내부 부패가 만연하다. 경비대 평판이 낮으면 검문에 걸린다. 벨론 대위와 ALLY_GUARD 아크의 핵심 무대.

**항만 부두** (LOC_HARBOR) -- 밀수와 노동 착취의 현장. 밤에는 밀수선이 드나들고 부두 깡패가 활개친다. 위험하지만 핵심 단서가 집중된 곳.

**빈민가** (LOC_SLUMS) -- 법의 손길이 닿지 않는 암흑가. 정보 브로커 쉐도우가 거점으로 삼는다. 위험도 최고, PROFIT_FROM_CHAOS 아크의 후반 무대.

### 3.3 Scene Shell 구조

`scene_shells.json`은 LOCATION x TimePhase(DAY/NIGHT) x Safety(SAFE/ALERT/DANGER) 조합으로 분위기 텍스트를 제공한다. SceneShellService가 현재 WorldState에 따라 적절한 텍스트를 선택하여 LLM 프롬프트에 전달한다.

```
scene_shells[locationId][timePhase][safety] → 분위기 텍스트 (1~2문단)
```

총 조합: 4 LOCATION x 2 TimePhase x 3 Safety = **24개 분위기 텍스트**

---

## 4. 이벤트 시스템 (88개)

### 4.1 이벤트 분포

`events_v2.json`에 88개 이벤트가 정의되어 있다 (LOCATION당 22개).

| LOCATION | 이벤트 수 | eventType 구성 |
|----------|----------|----------------|
| LOC_MARKET | 22 | RUMOR, FACTION, SHOP, CHECKPOINT, ARC_HINT, ENCOUNTER, OPPORTUNITY, FALLBACK 등 |
| LOC_GUARD | 22 | FACTION, CHECKPOINT, ARC_HINT, AMBUSH, ENCOUNTER, OPPORTUNITY, FALLBACK 등 |
| LOC_HARBOR | 22 | RUMOR, AMBUSH, ARC_HINT, ENCOUNTER, OPPORTUNITY, SHOP, FALLBACK 등 |
| LOC_SLUMS | 22 | RUMOR, FACTION, AMBUSH, ARC_HINT, ENCOUNTER, OPPORTUNITY, FALLBACK 등 |
| **FALLBACK** | (각 LOCATION에 포함) | 다른 이벤트가 매칭되지 않을 때 사용 |

### 4.2 eventType 설명

| eventType | 역할 | friction |
|-----------|------|----------|
| RUMOR | 소문/단서 제공. 낮은 위험 | 0 |
| FACTION | 세력 관련 이벤트. 평판 조건 존재 | 1 |
| SHOP | 상점 접근 이벤트 | 0 |
| CHECKPOINT | 경비대 검문. 통과/회피 판정 | 1~2 |
| AMBUSH | 적대적 조우. 전투 전환 가능 | 2 |
| ARC_HINT | 아크 진행 힌트. Fact/Arc 조건 필요 | 2 |
| FALLBACK | 기본 탐색. 조건 없음, weight 최고 | 0 |

### 4.3 이벤트 매칭 흐름

EventMatcherService의 6단계 필터링:

```
1. location 필터 → 해당 LOCATION 이벤트만
2. conditions 필터 → 평판/상태 조건 충족
3. gates 필터 → 쿨다운, 필수 플래그, 아크 조건
4. affordance 필터 → 플레이어 actionType과 이벤트 affordance 매칭
5. heat 간섭 → 높은 Heat에서 위험 이벤트 가중치 증가
6. 가중치 선택 → weight 기반 랜덤 선택
```

### 4.4 이벤트 구조 예시 (축약)

```json
{
  "eventId": "EVT_MARKET_RUMOR",
  "locationId": "LOC_MARKET",
  "eventType": "RUMOR",
  "priority": 5,
  "weight": 60,
  "conditions": null,
  "gates": [{ "type": "COOLDOWN_TURNS", "turns": 3 }],
  "affordances": ["INVESTIGATE", "BRIBE", "OBSERVE"],
  "friction": 0,
  "matchPolicy": "SUPPORT",
  "payload": {
    "sceneFrame": "시장 한구석에서 상인들이 속삭이고 있다...",
    "primaryNpcId": null,
    "choices": [
      { "id": "mkt_rumor_investigate", "label": "...", "affordance": "INVESTIGATE" },
      { "id": "mkt_rumor_bribe", "label": "...", "affordance": "BRIBE" },
      { "id": "mkt_rumor_observe", "label": "...", "affordance": "OBSERVE" }
    ],
    "tags": ["GOSSIP", "TAX", "GUARD_CORRUPTION"]
  }
}
```

### 4.5 Suggested Choices

`suggested_choices.json`은 eventType별 기본 선택지 템플릿을 제공한다. SceneShellService가 이벤트별 커스텀 choices가 없을 때 fallback으로 사용한다.

지원 타입: `RUMOR`, `FACTION`, `CHECKPOINT`, `AMBUSH`, `ARC_HINT`, `FALLBACK`, `SHOP`

---

## 5. 캐릭터 프리셋 (4종)

`presets.json`에 4종 프리셋이 정의된다. 런 생성 시 플레이어가 하나를 선택한다.

### 5.1 프리셋 비교

| presetId | 이름 | 별칭 | 플레이스타일 | HP | STA | ATK | DEF | ACC | EVA | CRIT | SPD | Gold |
|----------|------|------|-------------|-----|-----|-----|-----|-----|-----|------|-----|------|
| DOCKWORKER | 부두 노동자 | 항만의 주먹 | 근접 탱커 | 120 | 5 | 16 | 14 | 3 | 2 | 4 | 4 | 30 |
| DESERTER | 탈영병 | 추적받는 검 | 균형 근접 | 100 | 5 | 17 | 11 | 7 | 3 | 5 | 5 | 45 |
| SMUGGLER | 밀수업자 | 어둠의 운반책 | 회피/치명타 | 80 | 6 | 14 | 7 | 5 | 7 | 8 | 7 | 60 |
| HERBALIST | 약초상 | 뒷골목 약사 | 아이템 활용 | 90 | 7 | 11 | 9 | 6 | 4 | 4 | 4 | 40 |

### 5.2 프리셋 상세

**부두 노동자 (DOCKWORKER)**
- 배경: 그레이마르 항만에서 10년간 화물을 나른 노동자. 간부의 횡령을 목격한 뒤 '사고'로 위장된 습격을 당해 쫓겨났다.
- 초기 아이템: 하급 치료제 x2
- 강점: 최고 HP(120) + 최고 DEF(14). 맞으면서 버티는 전투.
- 약점: 낮은 ACC/EVA. 명중률과 회피가 부족하다.

**탈영병 (DESERTER)**
- 배경: 왕국 남부 수비대 출신. 상관의 민간인 약탈 명령에 항명하여 탈영. 수배 중.
- 초기 아이템: 하급 치료제 x1, 체력 강장제 x1
- 강점: 최고 ATK(17) + 높은 ACC(7). 정석적 근접 전투.
- 약점: 수배 중이라 경비대 구역에서 불리. 중간 체력.

**밀수업자 (SMUGGLER)**
- 배경: 밀수 조직 '검은 조류'의 하급 운반책. 조직 와해 후 제거 대상이 되어 도주 중.
- 초기 아이템: 연막탄 x1, 독침 x1
- 강점: 최고 EVA(7) + 최고 CRIT(8) + 최고 SPEED(7). 빠르고 치명적.
- 약점: 최저 HP(80) + 최저 DEF(7). 한 번 맞으면 치명적.

**약초상 (HERBALIST)**
- 배경: 항만 뒷골목에서 합법 약재와 밀수 독초를 함께 취급하는 약사. 세 세력 모두와 거래해왔다.
- 초기 아이템: 하급 치료제 x2, 독침 x2, 체력 강장제 x1
- 강점: 최고 STA(7) + 최고 RESIST(9) + 풍부한 초기 아이템. 아이템 전술 전투.
- 약점: 최저 ATK(11). 직접 공격력이 낮다.

---

## 6. NPC & 세력

### 6.1 세력 (4개)

| factionId | 이름 | 초기 평판 | 역할 |
|-----------|------|----------|------|
| LABOR_GUILD | 항만 노동 길드 | +5 | 부두 노동자 조직. 하를런이 핵심 연락책 |
| MERCHANT_CONSORTIUM | 상인 길드 연합 | -10 | 에드릭 베일의 이중 장부. 밀수 세탁 |
| CITY_GUARD | 도시 수비대 | 0 | 마이렐의 부패 vs 벨론의 정의 |
| ARCANE_SOCIETY | 비전 학회 | 0 | (현재 시나리오에서 주요 역할 없음) |

### 6.2 NPC (7명)

| npcId | 이름 | unknownAlias (소개 전) | 역할 | 세력 | basePosture |
|-------|------|----------------------|------|------|------------|
| NPC_YOON_HAMIN | 하를런 보스 | 투박한 노동자 | 부두 노동 형제단 연락책 | LABOR_GUILD | FRIENDLY |
| NPC_SEO_DOYUN | 에드릭 베일 | 날카로운 눈매의 회계사 | 은장부 상단 회계 담당 | MERCHANT_CONSORTIUM | CAUTIOUS |
| NPC_KANG_CHAERIN | 마이렐 단 경 | 권위적인 야간 경비 책임자 | 수비대 야간 책임자 (핵심 악역) | CITY_GUARD | CALCULATING |
| NPC_BAEK_SEUNGHO | 토브렌 하위크 | 수상한 창고 관리인 | 동부 부두 창고 관리자 | 무소속 | CAUTIOUS |
| NPC_MOON_SEA | 라이라 케스텔 | 조용한 문서 실무자 | 상단 문서실 암호 메모 실무자 | MERCHANT_CONSORTIUM | FEARFUL |
| NPC_INFO_BROKER | 쉐도우 | 후드를 깊이 쓴 정보상 | 뒷골목 정보 브로커 | 무소속 | CALCULATING |
| NPC_GUARD_CAPTAIN | 벨론 대위 | 위풍당당한 수비대 장교 | 수비대 대위, 내부 부패 진압 의지 | CITY_GUARD | CAUTIOUS |

> NPC 소개 시스템: 첫 만남에서 `unknownAlias`로 표시. posture에 따라 1~3회 만남 후 실명 공개. 상세: `09_npc_politics.md` §1.4

### 6.3 핵심 NPC 관계도

```
마이렐 단 경 (악역)
  ├─ 토브렌 하위크 (하수인, 창고 관리)
  ├─ 매수된 수비대원 (전투 적)
  └─ [대립] 벨론 대위 (상관, 정의)

하를런 보스 ─── 노동 길드 ─── [피해자] 부두 노동자
에드릭 베일 ─── 상인 길드 ─── [기록] 이중 장부
라이라 케스텔 ─── 상인 길드 ─── [문서] 암호 메모
쉐도우 ─── [독립] 정보 중개 (양쪽에 정보 판매)
```

---

## 7. 아크 루트 (3경로)

`arc_events.json`에 3개 아크 루트가 정의된다. 각 루트는 3단계로 구성되며, 플레이어의 행동 성향(Agenda)과 선택에 따라 commitmentDelta가 누적되어 루트가 확정된다.

### 7.1 아크 루트 요약

| arcRouteTag | 이름 | 핵심 NPC | 주요 LOCATION | 톤 |
|-------------|------|----------|--------------|-----|
| EXPOSE_CORRUPTION | 부패 폭로 | 벨론 대위, 에드릭 | LOC_GUARD, LOC_MARKET | 정의, 공식 |
| PROFIT_FROM_CHAOS | 혼란 이용 | 쉐도우 | LOC_HARBOR, LOC_SLUMS | 탐욕, 위험 |
| ALLY_GUARD | 경비대 동맹 | 벨론 대위 | LOC_GUARD | 질서, 협력 |

### 7.2 EXPOSE_CORRUPTION (부패 폭로)

| 단계 | eventId | 장소 | 내용 | 보상 |
|------|---------|------|------|------|
| 1 | arc_expose_1 | LOC_MARKET | 상인이 이중 장부 귀띔. 장부 사본 확보 | FACT_WAGE_FRAUD_PATTERN, 단서 |
| 2 | arc_expose_2 | LOC_GUARD | 벨론 대위에게 증거 전달. 내부 조사 시작 | FACT_OFFICIAL_INQUIRY, 경비대 허가증, 30G |
| 3 | arc_expose_3 | LOC_GUARD | 마이렐의 무력 저항. 최종 대치 | FACT_INSIDE_JOB, 100G, 평판 대변동 |

### 7.3 PROFIT_FROM_CHAOS (혼란 이용)

| 단계 | eventId | 장소 | 내용 | 보상 |
|------|---------|------|------|------|
| 1 | arc_profit_1 | LOC_HARBOR | 밀수 경로 정보 구매 (쉐도우) | FACT_ROUTE_TO_EAST_DOCK, 밀수 지도, -35G |
| 2 | arc_profit_2 | LOC_SLUMS | 양쪽 세력에 증거 협박. 중개자 자처 | FACT_BOTH_SIDES_EVIDENCE, 80G |
| 3 | arc_profit_3 | LOC_SLUMS | 양쪽 연합 공격. 토브렌+마이렐 대치 | FACT_INSIDE_JOB, 150G, 전세력 평판 하락 |

### 7.4 ALLY_GUARD (경비대 동맹)

| 단계 | eventId | 장소 | 내용 | 보상 |
|------|---------|------|------|------|
| 1 | arc_guard_1 | LOC_GUARD | 벨론 대위의 비공식 조사 의뢰 | FACT_TAMPERED_LOGS, 경비대 허가증, 20G |
| 2 | arc_guard_2 | LOC_GUARD | 야간 순찰 기록 조사. 병영 수색 | FACT_OFFICIAL_INQUIRY, 단서, 40G |
| 3 | arc_guard_3 | LOC_GUARD | 체포 영장 집행. 마이렐 제압 | FACT_INSIDE_JOB, 80G, 경비대 평판 +25 |

### 7.5 아크 커밋먼트

- ArcService가 commitment 값을 관리한다.
- 이벤트의 `commitmentDeltaOnSuccess` 필드로 해당 아크 commitment가 누적된다.
- commitment가 임계치(lock threshold = 3)에 도달하면 루트가 확정(lock)된다.
- 확정 후에는 다른 아크 이벤트가 매칭되지 않는다.

---

## 8. 전투 콘텐츠

### 8.1 적 (9종)

| enemyId | 이름 | 세력 | HP | ATK | DEF | 성격 | 비고 |
|---------|------|------|-----|-----|-----|------|------|
| ENEMY_DOCK_THUG | 부두 깡패 | LABOR_GUILD | 15 | 12 | 6 | AGGRESSIVE | 기본 잡몹 |
| ENEMY_HARBOR_WATCHMAN | 항만 경비병 | MERCHANT | 25 | 14 | 12 | TACTICAL | 방패+곤봉 |
| ENEMY_SMUGGLER | 밀수업자 | 무소속 | 18 | 16 | 5 | SNIPER | 석궁+단검 |
| ENEMY_CORRUPT_GUARD | 매수된 수비대원 | CITY_GUARD | 30 | 16 | 14 | TACTICAL | 보스전 재활용 |
| ENEMY_WAREHOUSE_GUARD | 창고 야경꾼 | 무소속 | 12 | 10 | 8 | COWARDLY | 위협 시 도주 |
| ENEMY_HIRED_MUSCLE | 고용 무력배 | LABOR_GUILD | 22 | 13 | 8 | AGGRESSIVE | 길드 루트 |
| ENEMY_CORRUPT_GUARD_LOYAL | 마이렐 충성 부하 | CITY_GUARD | 25 | 12 | 12 | TACTICAL | 경비대 루트 보스전 |
| ENEMY_GUILD_THUG_ELITE | 길드 정예 깡패 | LABOR_GUILD | 28 | 16 | 7 | AGGRESSIVE | 독자 루트 |
| ENEMY_TOBREN_COMBAT | 토브렌 (전투형) | 무소속 | 20 | 11 | 6 | COWARDLY | 독자 보스전 |

### 8.2 전투 조합 (9종)

| encounterId | 이름 | 적 구성 | 보스 | 비고 |
|-------------|------|---------|------|------|
| ENC_DOCK_AMBUSH | 부두 습격 | 부두 깡패 x2 | X | 공통 |
| ENC_WAREHOUSE_INFILTRATION | 창고 잠입 | 야경꾼 x1 + 밀수업자 x1 | X | 공통 |
| ENC_GUARD_CONFRONTATION | 수비대 대치 | 매수 수비대원 x1 + 항만 경비 x1 | O | 공통 보스 |
| ENC_WHARF_RAID | 부두 창고 급습 | 밀수업자 x2 + 무력배 x1 | X | 길드 루트 |
| ENC_GUILD_BOSS | 마이렐 대치(길드) | 마이렐(강화) + 수비대원 | O | 길드 보스 |
| ENC_BARRACKS | 병영 내부 전투 | 수비대원 x1 + 경비병 x1 | X | 경비대 루트 |
| ENC_GUARD_BOSS | 마이렐 체포 저항 | 마이렐(강화) + 충성 부하 | O | 경비대 보스 |
| ENC_ALLEY | 뒷골목 기습 | 정예 깡패 x1 + 수비대원 x1 | X | 독자 루트 |
| ENC_SOLO_BOSS | 토브렌-마이렐 연합 | 토브렌 + 마이렐(강화) | O | 독자 보스(최고 난이도) |

**보스 오버라이드** (마이렐 단 경): HP 65, ATK 18, DEF 16, ACC 7, personality TACTICAL

---

## 9. DAG 루트 구조 (미구현 --- TO-BE)

> **주의**: 아래 DAG 라우팅 시스템은 **설계만 존재하며 현재 구현되지 않았다**. 현재 게임은 Section 1.4의 HUB 중심 순환 구조로 동작한다. 향후 선형 스토리 모드 추가 시 참조용으로 유지한다.

### 9.1 개념

S2(핵심 분기점)에서의 선택에 따라 3개 루트(길드/경비대/독자)로 완전 분기되는 **유향 비순환 그래프(DAG)** 라우팅 시스템.

```
        공통 구간 (4노드)
        common_s0 → common_s1 → common_combat_dock → common_s2
                                                         |
                    +------------------------------------+-----------------------------+
                    v                                    v                             v
            길드 루트 (6노드)                    경비대 루트 (6노드)             독자 루트 (6노드)
            guild_rest → guild_shop →            guard_event_s3 → ...          solo_event_s3 → ...
            guild_event_s3 → guild_combat →
            guild_event_s4 → guild_boss
                    +------------------------------------+-----------------------------+
                                                         v
                                                합류 구간 (2노드)
                                                merge_s5 → merge_exit
```

- **총 노드**: 24개 (4 공통 + 6x3 루트 + 2 합류)
- **런당 방문**: 항상 12노드 (4 + 6 + 2)
- **분기 조건**: `common_s2`에서 choiceId에 따라 `guild_ally` / `guard_ally` / `solo_path`
- **노드 전환**: EdgeCondition(DEFAULT / CHOICE / COMBAT_OUTCOME) 기반 우선순위 평가

### 9.2 루트별 체험 비교 (TO-BE)

| 항목 | 길드 루트 | 경비대 루트 | 독자 루트 |
|------|----------|-----------|----------|
| 톤 | 거칠고 의리있는 | 공식적, 절차적 | 고독, 위험, 잠행 |
| 핵심 NPC | 하를런 | 라이라 + 벨론 대위 | 쉐도우 |
| 난이도 | 중간 | 낮음~중간 | 높음 |
| 보상 | 보통 | 저렴한 보급소 | 높은 골드, 고가 상점 |
| 노드 순서 | REST→SHOP→EVENT→COMBAT→EVENT→BOSS | EVENT→SHOP→COMBAT→EVENT→REST→BOSS | EVENT→COMBAT→REST→SHOP→EVENT→BOSS |

> DAG 구현 상세 (데이터 타입, DB 스키마, 서비스 변경)는 기존 `08_graymar_scenario.md` Part 3~7을 참조한다.

---

## 10. 콘텐츠 확장 가이드

### 10.1 새 LOCATION 추가

1. `locations.json`에 locationId, name, tags, dangerLevel 추가
2. `scene_shells.json`에 DAY/NIGHT x SAFE/ALERT/DANGER 6개 텍스트 추가
3. `events_v2.json`에 최소 4개 이벤트 추가 (FALLBACK 필수)
4. HUB 화면의 LOCATION 선택 카드에 반영

### 10.2 새 이벤트 추가

필수 필드:
- `eventId`: 유일한 식별자 (`EVT_{LOCATION}_{TYPE}` 패턴)
- `locationId`: 소속 LOCATION
- `eventType`: RUMOR / FACTION / SHOP / CHECKPOINT / AMBUSH / ARC_HINT / FALLBACK
- `affordances`: 매칭 가능한 IntentActionType 배열
- `payload.sceneFrame`: LLM에 전달될 장면 프레임 텍스트
- `payload.choices`: 선택지 배열 (id, label, hint, affordance)

### 10.3 새 아크 루트 추가

1. `arc_events.json`에 새 arcRouteTag 키로 3단계 이벤트 배열 추가
2. 각 단계에 requirements (minQuestState, requiredFacts, minReputation) 설정
3. 관련 이벤트의 `arcRouteTag` 필드에 새 루트 태그 설정
4. `commitmentDeltaOnSuccess` 값 조정 (lock threshold = 3 기준)

### 10.4 새 적/전투 추가

- `enemies.json`: enemyId, stats, personality, defaultDistance/Angle 필수
- `encounters.json`: encounterId, enemies 배열(ref + count + overrides), initialPositioning, rewards
- personality 옵션: AGGRESSIVE, TACTICAL, COWARDLY, BERSERK, SNIPER

### 10.5 새 프리셋 추가

`presets.json`에 추가. 필수 필드:
- `presetId`, `name`, `subtitle`, `description`, `playstyleHint`
- `protagonistTheme`: LLM 프롬프트의 L0 theme memory에 고정 삽입되는 주인공 배경 텍스트
- `stats`: MaxHP, MaxStamina, ATK, DEF, ACC, EVA, CRIT, CRIT_DMG, RESIST, SPEED
- `startingGold`, `startingItems`

---

*이 문서는 `content/graymar_v1/`의 실제 데이터를 기준으로 작성되었다. 코드 레벨 구현 상세는 `server/src/` 소스를 참조한다.*
