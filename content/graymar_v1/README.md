# Graymar v1 Content Dataset

중세 판타지 항만 도시 **그레이마르** — 정치 음모 RPG 콘텐츠 데이터셋.

## World

Medieval Fantasy — Graymar Harbor City (그레이마르 항만 도시)

## Engine Compatibility

- **Version**: engine_v1
- **정본**: `specs/combat_system.md`, `specs/combat_engine_resolve_v1.md`

## Core Systems

- **10 Combat Stats**: ATK, DEF, ACC, EVA, CRIT, CRIT_DMG, RESIST, SPEED, MaxHP, MaxStamina
- **Player Start**: HP 100 / Stamina 5 / ATK 15 / DEF 10
- **Combat Formulas**: d20+ACC hit, ATK*(100/(100+DEF)) damage, DOWNED on HP 0
- **4 Time Phases**: DAWN / DAY / DUSK / NIGHT (12 tick/day)
- **7 Locations**: 시장, 경비대, 항만, 빈민가, 상류 거리, 선술집, 창고구

## Main Quest

사라진 공물 장부 (왕국 정치 연계 사건)

- 6 Quest States: S0_ARRIVE → S1 → S2 → S3 → S4 → S5_RESOLVE
- 11 FACT Keys linked to quest progression
- 3 Arc Routes: EXPOSE_CORRUPTION / PROFIT_FROM_CHAOS / ALLY_GUARD

## Files (24 JSON)

| File | Content |
|------|---------|
| `combat_rules.json` | 엔진 공식 참조 + 시나리오 오버라이드 |
| `player_defaults.json` | 플레이어 초기 10스탯 + 시나리오 설정 |
| `presets.json` | 6 캐릭터 프리셋 (DOCKWORKER, DESERTER, SMUGGLER, HERBALIST, FALLEN_NOBLE, GLADIATOR) |
| `traits.json` | 6 캐릭터 특성 (BATTLE_MEMORY, STREET_SENSE, SILVER_TONGUE, GAMBLER_LUCK, BLOOD_OATH, NIGHT_CHILD) |
| `enemies.json` | 적 5종 (스탯, personality, 포지셔닝) |
| `encounters.json` | 전투 조우 3건 (적 구성, 환경, 보상) |
| `items.json` | 아이템 26종 (소비/장비/단서/열쇠) |
| `sets.json` | 장비 세트 정의 |
| `region_affixes.json` | 지역 Affix (접두사/접미사) |
| `npcs.json` | 42 NPC (CORE 5, SUB 12, BACKGROUND 25) |
| `factions.json` | 세력 4개 + 초기 평판 |
| `quest.json` | 메인 퀘스트 6단계 + stateTransitions + FACT 연계 |
| `locations.json` | 7개 LOCATION 정의 |
| `events_v2.json` | 123개 이벤트 (고정 + quest-fact 연계) |
| `scene_shells.json` | 장면 분위기 텍스트 |
| `scene_shells_v2.json` | 4상 시간별 분위기 텍스트 |
| `suggested_choices.json` | 이벤트 타입별 선택지 |
| `arc_events.json` | 아크 루트별 이벤트 |
| `shops.json` | 상점 재고 풀 |
| `incidents.json` | 8개 Incident 정의 (SMUGGLING, CORRUPTION, THEFT 등) |
| `endings.json` | 엔딩 템플릿 (NPC epilogues, city status) |
| `narrative_marks.json` | 12개 서사 표식 조건 |

## NPC 3계층 (42명)

| 계층 | 수 | 역할 | 초상화 |
|------|---|------|--------|
| CORE | 5 | 메인 스토리 핵심 NPC | 전용 초상화 |
| SUB | 12 | 퀘스트/이벤트 연계 NPC | 전용 초상화 |
| BACKGROUND | 25 | 배경/분위기 NPC | 없음 |

### CORE NPC (5명)

| ID | 이름 | 역할 |
|----|------|------|
| NPC_HARLUN | 하룬 | 항만 두목 |
| NPC_EDRIC_VEIL | 에드릭 베일 | 밀수 조직 리더 |
| NPC_MAIREL | 마이렐 단 | 경비대 부패 간부 |
| NPC_LORD_VANCE | 밴스 경 | 귀족 정치가 |
| NPC_RAT_KING | 쥐왕 | 빈민가 정보왕 |

### SUB NPC (12명)

| ID | 이름 | 역할 |
|----|------|------|
| NPC_TOBREN | 토브렌 | 창고 관리인 |
| NPC_MOON_SEA | 라이라 케스텔 | 문서 실무자 |
| NPC_MIRELA | 미렐라 | 약초 상인 |
| NPC_RENNICK | 레닉 | 정보 수집가 |
| NPC_CAPTAIN_BREN | 브렌 대위 | 경비대 장교 |
| NPC_ROSA | 로자 | 고아원 운영자 |
| NPC_INFO_BROKER | 쉐도우 | 정보 중개인 |
| NPC_GUARD_CAPTAIN | 벨론 대위 | 경비대 대장 |
| NPC_OWEN_KEEPER | 오웬 | 선술집 주인 |
| NPC_SERA_DOCKS | 세라 | 물류 관리자 |
| NPC_DAME_ISOLDE | 이졸데 여사 | 귀족 사교계 |
| NPC_GUARD_FELIX | 펠릭스 | 신참 경비병 |

## 캐릭터 프리셋 (6종)

| ID | 이름 | 컨셉 | 핵심 스탯 | 강점 |
|----|------|------|----------|------|
| DOCKWORKER | 부두 노동자 | 근접 탱커 | ATK16 DEF14 | FIGHT / HELP |
| DESERTER | 탈영병 | 균형 전투 | ATK17 ACC7 | FIGHT / INVESTIGATE |
| SMUGGLER | 밀수업자 | 은밀 특화 | EVA7 SPEED7 | SNEAK / PERSUADE |
| HERBALIST | 약초상 | 방어 유틸 | RESIST9 Stamina7 | INVESTIGATE / HELP |
| FALLEN_NOBLE | 몰락 귀족 | 정치 특화 | SPEED8 ACC6 | PERSUADE / BRIBE |
| GLADIATOR | 검투사 | 공격 특화 | ATK18 CRIT8 | FIGHT / THREATEN |

## 캐릭터 특성 (6종)

| ID | 효과 |
|----|------|
| BATTLE_MEMORY | 전투 경험 보너스 |
| STREET_SENSE | 위험 감지 보너스 |
| SILVER_TONGUE | 설득/협상 보너스 |
| GAMBLER_LUCK | FAIL→50% PARTIAL, 크리티컬 비활성 |
| BLOOD_OATH | 저HP 보너스 +2/+3, 치료 50% 감소 |
| NIGHT_CHILD | NIGHT +2 보너스, DAY -1 페널티 |

## 7개 탐험 장소

| ID | 이름 | 특징 |
|----|------|------|
| market | 시장 거리 | 상업, 정보 수집 |
| guard | 경비대 지구 | 권력, 법 집행 |
| harbor | 항만 부두 | 밀수, 항만 노동 |
| slums | 빈민가 | 빈곤, 지하 경제 |
| noble | 상류 거리 | 귀족, 정치 |
| tavern | 잠긴 닻 선술집 | 사교, 정보 교환 |
| warehouse | 항만 창고구 | 물류, 은밀 활동 |

## Enemy Summary

| Enemy | HP | Personality | Tier |
|-------|----|-------------|------|
| 부두 깡패 | 60 | AGGRESSIVE | Fodder |
| 항만 경비병 | 80 | TACTICAL | Standard |
| 밀수업자 | 50 | SNIPER | Glass Cannon |
| 매수된 수비대원 | 90 | TACTICAL | Elite |
| 창고 야경꾼 | 45 | COWARDLY | Fodder |

## Encounter Flow (Quest-linked)

```
S1_GET_ANGLE  → ENC_DOCK_AMBUSH (부두 깡패 x2)
S3_TRACE_ROUTE → ENC_WAREHOUSE_INFILTRATION (야경꾼 + 밀수업자)
S4_CONFRONT   → ENC_GUARD_CONFRONTATION (수비대원 + 경비병) [BOSS]
```

This dataset is ready for server seed usage.
