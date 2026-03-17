## 구현 상태 (2026-03-17)

| 이슈 | 심각도 | 상태 | 수정 내용 |
|------|--------|------|----------|
| P1 | Critical | ✅ 완료 | RUN_ENDED 전 `finalizeVisit()` 호출 추가 |
| P2 | Critical | ✅ 완료 | TAG_TO_NPC 기반 encounterCount 보충, context-builder NPC 이름 노출 확인 완료 |
| P3 | High | ✅ P1 해결로 자동 개선 | structuredMemory 정상화로 정보 반복 방지 |
| P4 | High | ✅ 완료 | MOVE_LOCATION 목표 불명확 시 HUB 복귀 처리 |
| P5 | Medium | ✅ 완료 | 씬 연속성 2턴→1턴 축소 (`consecutiveCount < 1`) |
| P6 | Medium | ⚠️ 미구현 | NPC 태도 급변 — 프롬프트 강화 필요 |
| P7 | Medium | ✅ 완료 | `checkEndingConditions`에 최소 15턴 가드 추가 |
| P8 | Medium | ✅ P1 해결로 자동 개선 | structuredMemory 정상화로 아이템 추적 복구 |
| P9 | Low | ⚠️ 미구현 | 선택지 affordance 편향 |
| P10 | Low | ✅ 완료 | NPC 에필로그 `korParticle()` 조사 적용 |
| P11 | Low | ⚠️ 미구현 | turnNo 갭 (의도된 동작) |

---

P1. structuredMemory 완전 미작동 — Critical
설계 vs 현실 갭 분석:
설계 문서에 따르면 메모리 저장은 두 시점에서 발생해야 합니다. 매 LOCATION 턴마다 MemoryCollectorService.collect()가 visitContext를 실시간 수집하고, go_hub 또는 MOVE_LOCATION 선택 시 MemoryIntegrationService.finalizeVisit()이 구조화 메모리를 통합 저장해야 합니다.
의심 원인: turns.service.ts의 LOCATION 턴 파이프라인을 보면, 현재 실제 흐름은 IntentParser → EventMatcher → Resolve → WorldTick → IncidentManagement → NpcEmotional → Orchestration → Commit 순서입니다. 여기서 MemoryCollector.collect() 호출이 빠져있을 가능성이 높습니다.
해결 방안:
turns.service.ts의 handleLocationTurn 내에서, Resolve 완료 직후(WorldState 업데이트 이전 또는 직후) MemoryCollector.collect()를 호출해야 합니다. 이때 전달해야 하는 visitContext는 현재 턴의 actionType, outcome, eventId, relatedNpcId, summaryShort 등입니다. VisitAction 구조({ rawInput, actionType, outcome, eventId?, brief, summaryShort?, relatedNpcId? })에 맞춰 조립해서 넘기면 됩니다.
go_hub CHOICE 처리 분기에서 MemoryIntegration.finalizeVisit() 호출도 확인해야 합니다. 설계 문서에 "go_hub/MOVE_LOCATION → MemoryIntegration.finalizeVisit() → run_memories.structuredMemory + 호환 storySummary 동시 저장"이라고 명시되어 있으므로, 이 호출이 실제 코드에 있는지 turns.service.ts의 go_hub 분기를 확인하세요.
추가로 Fixplanv2 PR-B에서 도입된 relatedNpcId 필드가 실제 VisitAction에 전달되고 있는지도 체크해야 합니다. 이것이 없으면 updateNpcJournal()의 NPC별 필터링이 작동하지 않아 npcJournal이 비게 됩니다.

P2. NPC 이름 공개 시스템 미작동 — Critical
설계 분석:
shouldIntroduce(npcState, posture) 함수가 encounterCount와 effectivePosture를 비교해서 소개 여부를 결정합니다. FRIENDLY/FEARFUL은 1회, CAUTIOUS는 2회, CALCULATING/HOSTILE은 3회 만남 후 소개하는 것이 규칙입니다.
Fixplanv2 PR-A에서 "encounterCount 방문 단위 제한"이 도입되었습니다. actionHistory에서 이미 만난 NPC면 스킵하고, 같은 방문 내 5턴 연속 만나도 encounterCount는 1만 증가하도록 설계되어 있습니다.
의심 원인: 핵심은 effectiveNpcId 통합입니다. matchedEvent.payload.primaryNpcId 우선, 없으면 orchestrationResult.npcInjection.npcId fallback 방식인데, 두 소스 모두 없으면 null이 됩니다. 이 경우 encounterCount 증가 로직 자체가 실행되지 않습니다.
해결 방안:
첫째, turns.service.ts에서 턴 처리 후 effectiveNpcId가 null이 아닐 때 npcState.encounterCount++ 및 shouldIntroduce() 체크 → introduced = true 설정이 실제로 실행되는지 확인합니다.
둘째, 이벤트 라이브러리(events.json)의 LOC_MARKET 이벤트들에 primaryNpcId가 제대로 설정되어 있는지 검증합니다. 만약 이벤트에 primaryNpcId가 없고, TurnOrchestration의 NPC 주입도 해당 NPC를 주입하지 않았다면, 7턴 연속 만나도 encounterCount는 0입니다.
셋째, LLM 프롬프트에서 NPC 실명이 컨텍스트에 노출되는 것을 막아야 합니다. T9에서 "에드릭 베일의 모습은 보이지 않았으나"가 나온 것은, context-builder.service.ts가 NPC 목록을 빌드할 때 introduced === false인 NPC의 실명을 다른 블록(incidentContext, signalContext 등)에서 노출시켰을 가능성이 있습니다. 모든 LLM 전달 블록에서 getNpcDisplayName()을 일관 적용해야 합니다.

P3. 정보 반복 루프 — High
근본 원인: P1(structuredMemory 미작동)의 직접적 파생입니다.
설계에 따르면, [이번 방문 대화] 규칙 6번 "NPC가 알려준 정보/획득 물건을 기억하고 반복 금지"와 규칙 7번 "이미 대화한 NPC는 이전 대화 내용을 알고 있어야 함"이 이를 방지해야 합니다. 하지만 structuredMemory가 비어있으면, LLM 컨텍스트에 [이야기 요약], [NPC 관계], [사건 일지] 블록이 모두 빈 상태로 전달됩니다.
해결 방안:
P1 해결이 선행 조건입니다. 추가로 LLM 프롬프트에 명시적인 "이미 공유된 정보 목록" 가드를 넣어야 합니다.
MemoryRendererService에서 렌더링하는 [NPC 관계] 블록에, npcJournal의 과거 상호작용에서 공유된 핵심 정보를 "이 NPC가 이미 알려준 것: ..." 형태로 포함시키는 것이 효과적입니다. 현재 npcKnowledge에 PLAYER_TOLD, AUTO_COLLECT 소스가 있으므로, 이 데이터가 실제로 수집되고 렌더링되면 LLM이 반복을 피할 수 있습니다.
또한 activeClues(활성 단서) 시스템이 정상 작동하면, [기억된 사실] 블록에 이미 발견된 PLOT_HINT가 포함되어 LLM이 새로운 방향으로 서사를 진행할 수 있습니다.

P4. MOVE_LOCATION 인텐트 파싱 실패 — High
설계 분석:
IntentParserV2의 IntentActionType에는 MOVE_LOCATION이 15종 중 하나로 정의되어 있습니다. 하지만 키워드 매핑 목록을 보면 MOVE_LOCATION에 대한 한국어 키워드가 설계 문서에 명시되어 있지 않습니다. Rule Parser의 키워드 테이블에 MOVE(전투용: 오른쪽/왼쪽/이동/물러)는 있지만, LOCATION용 MOVE_LOCATION 키워드는 별도입니다.
또한 구조적으로, LOCATION 내에서 ACTION 입력으로 MOVE_LOCATION을 발동시키는 것이 설계상 허용되는지가 중요합니다. HUB 노드에서 go_market/go_guard 등의 CHOICE로만 장소를 이동하는 것이 현재 설계 흐름입니다. LOCATION 내에서의 이동은 go_hub CHOICE → HUB 복귀 → 다른 장소 선택이 정석 경로입니다.
해결 방안:
두 가지 접근이 있습니다.
접근 A (키워드 추가): intent-parser-v2.service.ts에 MOVE_LOCATION 키워드를 추가합니다. "이동", "다른 장소", "옮기", "떠나", "장소를 바꾸", "나가" 등. 파싱 성공 시, go_hub와 동일하게 처리하거나 직접 장소 이동을 허용합니다.
접근 B (CHOICE 안내): ACTION 입력에서 장소 이동 의도가 감지되면, TRANSFORM 정책으로 "go_hub CHOICE를 안내하는 응답"을 반환합니다. 이것이 현재 아키텍처에 더 부합합니다. LOCATION에서의 이동은 원래 go_hub CHOICE로 허브에 복귀한 후 다른 장소를 선택하는 것이 설계된 흐름이기 때문입니다.
권장: 접근 A와 B를 혼합합니다. MOVE_LOCATION 키워드를 추가하되, 파싱 성공 시 go_hub와 동일한 처리(장기기억 저장 + HUB 복귀)를 트리거하고, LLM에게 "장소를 떠나는 장면"을 서술하게 합니다.

P5. 이벤트 2턴 반복 패턴 — Medium
설계 분석:
EventDirector의 5단계 정책에서 Cooldown Filter가 evaluateGates() + cooldownTurns를 사용합니다. EventMatcherService에는 이미 3중 방지 체계가 있습니다. 직전 이벤트 hard block(Fixplanv2 PR-D), 누진 반복 페널티(-60/-70/-100), 방문 내 하드캡(동일 이벤트 2회 이상 제거)입니다.
의심 원인: LOC_MARKET에 매칭 가능한 이벤트가 5개뿐일 가능성이 높습니다. 이벤트 라이브러리 88개 중 LOC_MARKET의 locationId 조건을 만족하고, 현재 stage/conditions/gates를 통과하는 이벤트가 극소수라면, 쿨다운이 적용되더라도 소수 이벤트가 순환될 수밖에 없습니다.
해결 방안:
첫째, LOC_MARKET에 매칭 가능한 이벤트 풀을 확인하고 부족하면 추가합니다. 콘텐츠(events.json) 레벨의 문제입니다.
둘째, ProceduralEventService(동적 이벤트 생성)가 EventDirector의 fallback 체인에서 실제로 호출되고 있는지 확인합니다. 설계에 따르면 "고정 이벤트 → 절차적 이벤트 → atmosphere fallback" 체인인데, 절차적 이벤트가 실제 생성되지 않으면 5개 고정 이벤트만 순환합니다.
셋째, 직전 이벤트 hard block은 현재 recentEventIds[last] 하나만 차단합니다. 이를 최근 2개로 확장하면 기계적 2턴 반복을 즉시 방지할 수 있습니다. EventMatcherService의 match() 함수에서 recentEventIds.slice(-2) 범위로 hard block을 적용하면 됩니다.

P6. NPC 태도 급변 — Medium
설계 분석:
NpcEmotionalService의 computeEffectivePosture(npcState)는 5축 감정 상태(trust, fear, respect, suspicion, attachment)를 기반으로 동적 posture를 계산합니다. 이 posture는 LLM 컨텍스트의 npcPostures에 전달되고, [현재 장면 상태] 블록에 "(CAUTIOUS)" 같은 형태로 포함됩니다.
의심 원인: 두 가지 가능성이 있습니다.
하나는 npcEmotionalContext가 LLM에 전달되더라도, LLM이 서사 편의상 이를 무시하는 경우입니다. 특히 "열쇠를 보여준다" 같은 정보 제공 행동은 LLM이 플롯 진행을 위해 posture를 무시하고 협조적으로 만드는 경향이 있습니다.
다른 하나는 NpcEmotionalService의 감정 업데이트가 매 턴 실행되지만, LLM 서술과의 동기화가 안 되는 경우입니다. 서버에서 NPC의 effectivePosture가 CAUTIOUS로 계산되었는데 LLM이 이미 협조적 서술을 생성하면 불일치가 발생합니다.
해결 방안:
prompt-builder.service.ts에서 NPC posture를 더 강하게 강제하는 지시를 추가합니다. 현재는 "[현재 장면 상태]"에 posture만 표기하는 수준인데, "이 NPC는 현재 {posture} 태도입니다. 이 태도에 맞지 않는 행동(예: 자발적 정보 제공, 열쇠 보여주기)은 절대 서술하지 마세요"처럼 명시적 금지 규칙을 넣어야 합니다.
또한 ResolveResult의 outcome이 posture와 연동되어야 합니다. CAUTIOUS NPC에게 PERSUADE를 시도해서 PARTIAL을 받았다면, LLM에 "부분적으로만 응해야 함"을 명확히 전달해야 합니다.

P7. 조기 RUN_ENDED (Turn 13, NATURAL) — Medium
설계 분석:
EndingGeneratorService.checkEndingConditions()에서 엔딩 트리거 조건은 ALL_RESOLVED, DEADLINE, PLAYER_CHOICE 세 가지입니다. NATURAL 엔딩은 ALL_RESOLVED에 해당하며, INC_MARKET_THEFT가 control ≥ 80으로 CONTAINED 상태가 되면서 발동한 것으로 보입니다.
해결 방안:
ending-generator.service.ts의 checkEndingConditions()에 최소 턴 수 가드를 추가합니다.
typescriptif (endingType === 'NATURAL' && runState.totalTurns < MIN_TURNS_FOR_NATURAL) {
  return null; // 엔딩 지연
}
MIN_TURNS_FOR_NATURAL은 설정 가능한 값으로 두되, 초기값은 15턴이 적절합니다. 이렇게 하면 사건이 조기 해결되더라도 플레이어가 최소한의 탐색을 할 수 있습니다.
추가로, 사건 1개만 해결되었을 때 바로 NATURAL 엔딩이 뜨는 것 자체가 콘텐츠 부족의 신호이기도 합니다. 동시 활성 Incident가 1개뿐이면 해결 직후 끝나는 것이 당연하므로, IncidentManagementService의 spawn 확률(현재 20%/tick, 최대 3개 동시)이 실제로 충분한 사건을 생성하는지도 확인해야 합니다.

P8. 종이 조각 추적 실패 — Medium
P1의 직접적 파생입니다. MemoryCollector.collect()가 동작하지 않으면 아이템 획득 사실이 structuredMemory에 기록되지 않고, 이후 턴의 LLM 컨텍스트에 "종이 조각을 가지고 있다"는 정보가 전달되지 않습니다.
P1이 해결되면, LLM의 [MEMORY:NPC_DETAIL] 태그가 "종이 조각 획득"을 기록하고 llmExtracted에 누적됩니다. 이것이 다음 턴의 [기억된 사실] 블록에 포함되어 자연스럽게 해결됩니다.

P9. 선택지 affordance 편향 — Low
설계 분석:
LLM이 [CHOICES] 태그로 생성하는 선택지는 "AFFORDANCE 2종 이상"이라는 규칙이 시스템 프롬프트에 있습니다. 하지만 LOC_MARKET 이벤트의 affordances[] 자체가 INVESTIGATE, PERSUADE, OBSERVE에 편중되어 있다면 LLM도 이 범위 내에서만 선택지를 생성합니다.
해결 방안:
system-prompts.ts의 [CHOICES] 생성 규칙에 다양성 강제를 추가합니다. "직전 2턴에서 제안된 affordance와 다른 유형을 최소 1개 포함하세요"와 같은 지시입니다.
또한 SceneShellService의 서버 측 선택지 생성에서도 다양성을 확보할 수 있습니다. 선택지 3단 우선순위 로직에서 최근 N턴 affordance 이력을 참조하여 미사용 affordance에 가중치를 부여하면 됩니다.

P10. NPC 에필로그 조사 문법 오류 — Low
해결 방안:
한국어 조사 유틸 함수를 도입합니다.
typescriptfunction attachPostposition(name: string, type: '은는' | '이가' | '을를'): string {
  const lastChar = name.charCodeAt(name.length - 1);
  const hasBatchim = (lastChar - 0xAC00) % 28 !== 0;
  const map = { '은는': hasBatchim ? '은' : '는', '이가': hasBatchim ? '이' : '가', '을를': hasBatchim ? '을' : '를' };
  return name + map[type];
}
ending-generator.service.ts의 NPC epilogue 생성 부분에서 현재 ${name}은(는) 하드코딩을 attachPostposition(name, '은는') 호출로 교체합니다.

P11. turnNo 갭 (T3 누락) — Low
설계에 따르면 HUB 노드 NODE_ENDED → 새 LOCATION 노드 생성 → enter 턴 자동 생성(SYSTEM, PENDING) 과정에서 내부 턴이 소비됩니다. 이것이 의도된 동작이라면, 클라이언트에서 turnNo를 표시할 때 내부 SYSTEM 턴을 제외한 "플레이어 가시 턴 번호"를 별도로 계산하는 것이 깔끔합니다.
turns 테이블에서 inputType !== 'SYSTEM'인 턴만 카운트하는 visibleTurnNo 필드를 클라이언트 측에서 계산하거나, 서버의 serverResult에 displayTurnNo를 추가로 내려주면 됩니다.

권장 작업 순서
P1 → P2 → P4 → P5 순서로 진행하는 것을 추천합니다. P1이 해결되면 P3, P8은 자동 개선되고, P2 해결 시 NPC 서사 연속성이 크게 향상됩니다. P10은 독립적이라 언제든 적용 가능하고, P7은 checkEndingConditions()에 한 줄 가드만 추가하면 되므로 빠르게 처리할 수 있습니다.