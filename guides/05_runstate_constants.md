# RunState 구조 & 핵심 상수

> 최종 갱신: 2026-03-17

## RunState Structure (서버 JSONB)

`run_sessions.runState` — 런 전체 상태

```typescript
RunState {
  // 기본 스탯
  gold, hp, maxHp, stamina, maxStamina, inventory[]

  // HUB 시스템
  worldState: WorldState       // Heat, Safety, TimePhaseV2, Reputation, globalClock, day
  agenda: PlayerAgenda         // 성향 추적
  arcState: ArcState           // 아크 루트/커밋먼트
  npcRelations: Record<string, number>
  eventCooldowns: Record<string, number>
  actionHistory: ActionHistoryEntry[]  // 고집 에스컬레이션용

  // NPC 시스템
  npcStates: Record<string, NPCState>  // introduced, encounterCount, NpcEmotionalState 포함
  relationships: Record<string, Relationship>
  pbp: PlayerBehaviorProfile

  // Turn Orchestration
  pressure: number             // 긴장도 (0~100)
  lastPeakTurn: number

  // Equipment
  equipped: EquippedGear
  equipmentBag: ItemInstance[]

  // Narrative Engine v1
  activeIncidents: IncidentRuntime[]    // 활성 사건 목록
  signalFeed: SignalFeedItem[]          // 시그널 피드
  narrativeMarks: NarrativeMark[]       // 불가역 서사 표식
  mainArcClock: MainArcClock            // 메인 아크 시계 (deadline)
  operationSession: OperationSession | null  // 멀티스텝 세션

  // Narrative v2 (설계문서 18~20)
  proceduralHistory?: ProceduralHistoryEntry[]  // 절차적 이벤트 이력 (max 15)
}
```

---

## 핵심 상수

### 시간 & 환경
| 상수 | 값 | 위치 | 설명 |
|------|-----|------|------|
| TICKS_PER_DAY | 12 | WorldTickService | DAWN2+DAY4+DUSK2+NIGHT4 |
| TIME_CYCLE_TURNS | 5턴 | WorldStateService | DAY↔NIGHT 전환 주기 (legacy) |
| HEAT_DECAY_ON_HUB_RETURN | 5 | WorldStateService | HUB 복귀 시 Heat 감소 |
| HEAT_DELTA_CLAMP | ±8 | ResolveService | 턴당 Heat 변동 제한 |

### 전투 & 판정
| 상수 | 값 | 위치 | 설명 |
|------|-----|------|------|
| MAX_COMBAT_PER_WINDOW | 3 | ResolveService | 윈도우당 최대 전투 |
| DANGER_BLOCK_CHANCE | 25% | EventMatcherService | DANGER 시 BLOCK 확률 |
| CRACKDOWN_BLOCK_CHANCE | 40% | EventMatcherService | ALERT 시 BLOCK 확률 |

### 긴장도 & 사건
| 상수 | 값 | 위치 | 설명 |
|------|-----|------|------|
| PEAK_THRESHOLD | 60 | TurnOrchestrationService | 압력 정점 임계값 |
| PRESSURE_MAX | 100 | TurnOrchestrationService | 긴장도 최대 |
| INCIDENT_SPAWN_CHANCE | 20% | IncidentManagementService | tick당 사건 발생 확률 |
| MAX_ACTIVE_INCIDENTS | 3 | IncidentManagementService | 동시 활성 사건 |
| MAX_SIGNALS | 20 | SignalFeedService | 시그널 피드 최대 |

### LLM
| 상수 | 값 | 위치 | 설명 |
|------|-----|------|------|
| LLM_POLL_INTERVAL | 2000ms | LlmWorkerService | 서버 폴링 주기 |
| LLM_LOCK_TIMEOUT | 60s | LlmWorkerService | 락 타임아웃 |
| CLIENT_LLM_POLL_INTERVAL | 2000ms | game-store.ts | 클라이언트 폴링 주기 |
| CLIENT_LLM_POLL_MAX | 15회 | game-store.ts | 최대 30초 |

### 메모리 & 서술
| 상수 | 값 | 위치 | 설명 |
|------|-----|------|------|
| TOKEN_BUDGET_TOTAL | 2500 | TokenBudgetService | 프롬프트 총 토큰 예산 |
| LOCATION_SESSION_MAX | 4턴 | ContextBuilderService | MidSummary 적용 후 (Fixplanv1 PR3: 6→4) |
| PREVIOUS_VISIT_BUDGET | 150 | TokenBudgetService | [직전 장소 정보] 블록 (priority=57) |
| STRUCTURED_MEMORY_BUDGET | 450 | TokenBudgetService | 구조화 메모리 블록 (PR3: 500→450) |
| BUFFER_BUDGET | 250 | TokenBudgetService | 기타 블록 (PR3: 300→250) |
| STORY_SUMMARY_LIMIT | 2000자 | ContextBuilderService | 이야기 요약 최대 |
| THREAD_ENTRY_MAX | 200자 | LlmWorkerService | THREAD 엔트리당 |
| THREAD_TOTAL_BUDGET | 1200자 | LlmWorkerService | THREAD 총 예산 |
| LLM_EXTRACTED_MAX | 15개 | LlmWorkerService | MEMORY 태그 최대 |

### UI
| 상수 | 값 | 위치 | 설명 |
|------|-----|------|------|
| ROLL_DURATION_MS | 1200ms | ResolveOutcomeBanner | 주사위 애니메이션 |

---

## Content Data 구조

`content/graymar_v1/` — 22 files

| 파일 | 용도 |
|------|------|
| player_defaults.json | 초기 스탯/장비/시나리오 설정 |
| presets.json | 4 캐릭터 프리셋 |
| enemies.json | 적 정의 |
| encounters.json | 전투 조합 + 보상 |
| items.json | 아이템 카탈로그 |
| npcs.json | 11 NPC (name, unknownAlias, role, faction, basePosture) — PR1에서 4명 추가 |
| factions.json | 세력 정의 |
| quest.json | 퀘스트 정의 |
| locations.json | 4 LOCATION (시장/경비대/항만/빈민가) |
| events_v2.json | 88개 이벤트 (22개/LOCATION) |
| scene_shells.json | LOCATION×TimePhase×Safety 분위기 |
| scene_shells_v2.json | 4상 시간 분위기 |
| suggested_choices.json | 이벤트 타입별 선택지 |
| arc_events.json | 아크 루트별 이벤트 |
| combat_rules.json | 전투 규칙 오버라이드 |
| shops.json | 상점 정의 |
| sets.json | 장비 세트 |
| region_affixes.json | 리전 접미사 |
| incidents.json | 8개 Incident (dual-axis) |
| endings.json | 엔딩 템플릿 |
| narrative_marks.json | 12개 서사 표식 조건 |
