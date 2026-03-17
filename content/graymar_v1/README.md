# Graymar v1 Content Dataset

## World
Medieval Fantasy – Graymar Harbor City

## Engine Compatibility
- **Version**: engine_v1
- **정본**: `design/combat_system.md`, `design/combat_engine_resolve_v1.md`

## Core Systems
- **10 Combat Stats**: ATK, DEF, ACC, EVA, CRIT, CRIT_DMG, RESIST, SPEED, MaxHP, MaxStamina
- **Player Start**: HP 100 / Stamina 5 / ATK 15 / DEF 10
- **Combat Formulas**: d20+ACC hit, ATK*(100/(100+DEF)) damage, DOWNED on HP 0
- **3 Time Phases**: Morning / Afternoon / Night
- **2–3 Combat Encounters per Run**

## Main Quest
사라진 공물 장부 (왕국 정치 연계 사건)
- 6 Quest States: S0_ARRIVE → S5_RESOLVE
- 5 FACT Keys linked to CLUE items

## Files

| File | Content |
|------|---------|
| `combat_rules.json` | 엔진 공식 참조 + 시나리오 오버라이드 |
| `player_defaults.json` | 플레이어 초기 10스탯 + 시나리오 설정 |
| `enemies.json` | 적 5종 (스탯, personality, 포지셔닝) |
| `encounters.json` | 전투 조우 3건 (적 구성, 환경, 보상) |
| `items.json` | 단서 3 + 전투 소모품 4 |
| `npcs.json` | NPC 5명 (faction, 적대 조건, combatProfile) |
| `factions.json` | 세력 4개 + 초기 평판 |
| `quest.json` | 메인 퀘스트 상태 머신 + FACT |

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
