# 43. Sudden Action Context Preservation — 돌발행동 맥락 보존

> **문제**: 플레이어가 "수비대 대장을 칼로 찌른다" 같은 **돌발행동**(세계관·NPC 관계에 큰 변화를 주는 행위)을 했을 때, 서버·LLM·UI 어느 계층에서도 그 영향이 다음 턴으로 제대로 전파되지 않는다.
>
> **목표**: 돌발행동 1회 발생 → **N턴에 걸쳐 NPC·세계·서술 모두에 일관된 결과** 반영.
>
> **배경 버그**: report `0907761f` (2026-04-22) — 벨론 대위를 칼로 찌른 직후 태연히 대화.

---

## 1. 문제 정의

### 1.1 현상
1. 플레이어 T14 "수비대 대장을 칼로 찌른다" → FIGHT 의도, SUCCESS 판정
2. 서버: gold+5 획득, NPC 회피/밀고 이벤트만 기록
3. 다음 턴 T15:
   - NPC posture: 여전히 CAUTIOUS (변경 없음)
   - IncidentMemory: 미등록
   - NPC knownFacts: 공격 사실 없음
   - Mid Summary: `@[NPC|URL]` 마커 포함된 60자 fallback (요약 품질 낮음)
4. LLM 서술: 찔린 NPC가 태연히 일반 대화 수행

### 1.2 근본 원인

| 계층 | 누락 | 영향 |
|------|------|------|
| 서버 ResolveService | FIGHT 의도 + targetNpcId → posture 자동 전환 없음 | NPC 감정 상태가 공격 이전과 동일 |
| 서버 IncidentMemory | 폭력 사건 자동 등록 없음 | "관련 사건" 블록 비어있음 |
| 서버 NPC knownFacts | 공격 사실 자동 기록 없음 | NPC가 공격을 "모른다" |
| LLM 프롬프트 | `[NPC 감정 상태]` 블록이 posture 기반 → 갱신 안 된 상태로 LLM에 전달 | LLM이 태연한 서술 생성 |
| Mid Summary | 60자 fallback + `@[NPC|URL]` 마커 포함 | 요약 품질 저하, 핵심 사건 전달 약화 |

### 1.3 성공 기준
- [ ] 돌발행동(폭력/절도/배신) 발생 턴 T → T+1 턴 LLM 서술에 그 사실이 **반드시** 반영
- [ ] 공격받은 NPC는 다음 턴부터 HOSTILE/FEARFUL posture로 반응
- [ ] 후속 턴 3개 이상에 걸쳐 decay 모델로 자연스럽게 약화
- [ ] IncidentMemory에 자동 등록되어 `[관련 사건]` 블록에 표시
- [ ] 기존 Turn 판정 로직(SUCCESS/PARTIAL/FAIL)과 공존

---

## 2. 돌발행동 분류

### 2.1 분류 체계

| Severity | 명칭 | 예시 | Intent |
|----------|------|------|--------|
| 🔴 **CRITICAL** | 살해 의도 | 칼로 찌른다, 목을 벤다, 죽인다 | FIGHT + 치명 키워드 |
| 🔴 **CRITICAL** | 중상 폭행 | 철퇴로 내려친다, 얼굴을 짓이긴다 | FIGHT + 고강도 키워드 |
| 🟠 **SEVERE** | 일반 폭력 | 때린다, 밀친다, 발로 찬다 | FIGHT |
| 🟠 **SEVERE** | 무력 위협 | 칼을 겨눈다, 목덜미를 잡는다 | THREATEN + 무기 키워드 |
| 🟡 **MODERATE** | 절도 | 물건을 빼앗는다, 훔친다 | STEAL |
| 🟡 **MODERATE** | 언어 위협 | 협박한다, 거칠게 몰아붙인다 | THREATEN |
| 🟢 **MINOR** | 배신 신호 | 거래를 깬다, 약속을 어긴다 | (맥락 기반) |

### 2.2 탐지 로직

```typescript
// server/src/engine/hub/sudden-action-detector.ts (신규)
export const CRITICAL_KEYWORDS = [
  '찌른다', '찔러', '베다', '벤다', '벤', '죽인다', '죽여', '살해',
  '목을', '심장을', '급소를', '처형', '절명',
];
export const SEVERE_KEYWORDS = [
  '때린다', '밀친다', '발로 찬다', '주먹으로', '내려친다', '짓이긴다',
];
export const WEAPON_THREAT_KEYWORDS = [
  '칼을 겨눈다', '칼을 들이댄다', '목덜미', '인질',
];

export function detectSuddenAction(
  intent: ParsedIntent,
  rawInput: string,
): SuddenAction | null {
  const isFight = intent.intents.includes('FIGHT');
  const isThreaten = intent.intents.includes('THREATEN');
  const isSteal = intent.intents.includes('STEAL');

  if (isFight && CRITICAL_KEYWORDS.some(k => rawInput.includes(k))) {
    return { severity: 'CRITICAL', type: 'KILL_ATTEMPT', targetNpcId: intent.targets[0] };
  }
  if (isFight && SEVERE_KEYWORDS.some(k => rawInput.includes(k))) {
    return { severity: 'SEVERE', type: 'ASSAULT', targetNpcId: intent.targets[0] };
  }
  if (isThreaten && WEAPON_THREAT_KEYWORDS.some(k => rawInput.includes(k))) {
    return { severity: 'SEVERE', type: 'WEAPON_THREAT', targetNpcId: intent.targets[0] };
  }
  if (isFight) {
    return { severity: 'SEVERE', type: 'ASSAULT', targetNpcId: intent.targets[0] };
  }
  if (isSteal) {
    return { severity: 'MODERATE', type: 'THEFT', targetNpcId: intent.targets[0] };
  }
  if (isThreaten) {
    return { severity: 'MODERATE', type: 'VERBAL_THREAT', targetNpcId: intent.targets[0] };
  }
  return null;
}
```

---

## 3. 데이터 모델

### 3.1 NPCState 확장

```typescript
// server/src/db/types/npc-state.ts
interface NPCState {
  // 기존 필드
  posture: NpcPosture;
  emotional: { trust, fear, respect, affection, hostility };
  knownFacts: string[];
  // ...

  // 신규: 돌발행동 이력
  suddenActions?: Array<{
    turnNo: number;
    type: 'KILL_ATTEMPT' | 'ASSAULT' | 'WEAPON_THREAT' | 'THEFT' | 'VERBAL_THREAT';
    severity: 'CRITICAL' | 'SEVERE' | 'MODERATE' | 'MINOR';
    summary: string; // "플레이어가 칼로 찔렀다"
    decayFactor?: number; // 1.0 → 턴 경과에 따라 감소
  }>;
}
```

### 3.2 새 IncidentMemory 카테고리

```typescript
interface IncidentMemoryEntry {
  incidentId: string;
  // ...
  category?: 'QUEST' | 'PLAYER_VIOLENCE' | 'PLAYER_BETRAYAL';
  suddenAction?: SuddenAction; // 신규
}
```

### 3.3 RunState 확장 (선택)

```typescript
interface RunState {
  // ...
  playerViolenceCount?: number; // CRITICAL 이상 누적
  playerReputation?: {
    notoriety: number; // 0~100, 폭력 명성
    lastSuddenTurnNo: number;
  };
}
```

---

## 4. 서버 파이프라인

### 4.1 전체 흐름

```
rawInput "수비대 대장을 칼로 찌른다"
   │
   ▼
┌────────────────────────────────────────────┐
│ IntentParserV2                              │
│ → intent: FIGHT, targetNpcId: NPC_GUARD_CAP │
└────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────┐
│ SuddenActionDetector (신규)                 │
│ → severity: CRITICAL, type: KILL_ATTEMPT    │
└────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────┐
│ ResolveService (확장)                       │
│ · 기본 판정 (1d6 + stat)                    │
│ · suddenAction 감지 시:                     │
│   · NPC posture → HOSTILE/FEARFUL 강제       │
│   · NPC emotional.fear/hostility 급상승      │
│   · NPC knownFacts: "플레이어가 찔렀다" 추가 │
│   · IncidentMemory 등록 (PLAYER_VIOLENCE)   │
│   · heat +8 clamp 상한까지                  │
│   · suddenAction 기록을 runState에 저장     │
└────────────────────────────────────────────┘
   │
   ▼
ServerResult
   │
   ▼
┌────────────────────────────────────────────┐
│ Context Builder — [돌발 사건 이력] 블록     │
│ ↓                                           │
│ Prompt Builder — LLM 프롬프트 주입          │
└────────────────────────────────────────────┘
   │
   ▼
LLM 서술 (반영된 맥락으로 생성)
```

### 4.2 ResolveService 확장 의사코드

```typescript
// server/src/engine/hub/resolve.service.ts
async resolve(input: ResolveInput): Promise<ResolveResult> {
  // 기존 판정
  const outcome = this.rollOutcome(intent, stat, ...);

  // 돌발행동 감지
  const suddenAction = detectSuddenAction(intent, input.rawInput);

  if (suddenAction && suddenAction.targetNpcId) {
    const npc = runState.npcStates?.[suddenAction.targetNpcId];
    if (npc) {
      this.applySuddenActionToNpc(npc, suddenAction, turnNo);
    }
    this.registerAsIncident(runState, suddenAction, turnNo);
    heatDelta = Math.max(heatDelta, this.suddenActionHeatDelta(suddenAction));
  }

  return { outcome, suddenAction, ... };
}

private applySuddenActionToNpc(
  npc: NPCState,
  action: SuddenAction,
  turnNo: number,
) {
  // posture 강제 전환
  if (action.severity === 'CRITICAL' || action.severity === 'SEVERE') {
    npc.posture = 'HOSTILE';
    npc.emotional.fear = Math.min(100, npc.emotional.fear + 40);
    npc.emotional.hostility = Math.min(100, npc.emotional.hostility + 50);
    npc.emotional.trust = Math.max(0, npc.emotional.trust - 30);
  } else if (action.severity === 'MODERATE') {
    if (npc.posture === 'FRIENDLY') npc.posture = 'CAUTIOUS';
    else if (npc.posture === 'CAUTIOUS') npc.posture = 'HOSTILE';
    npc.emotional.fear = Math.min(100, npc.emotional.fear + 20);
    npc.emotional.trust = Math.max(0, npc.emotional.trust - 15);
  }

  // knownFacts 기록
  npc.knownFacts = npc.knownFacts || [];
  npc.knownFacts.push(this.summarizeSuddenAction(action));

  // suddenActions 이력 추가
  npc.suddenActions = npc.suddenActions || [];
  npc.suddenActions.push({
    turnNo,
    type: action.type,
    severity: action.severity,
    summary: action.summary,
    decayFactor: 1.0,
  });
}
```

### 4.3 Decay 모델

```typescript
// 턴 경과에 따른 decay
function decayFactor(turnsSince: number, severity: Severity): number {
  if (severity === 'CRITICAL') {
    // 살해 의도 — 10턴 이상 유지
    if (turnsSince < 3) return 1.0;
    if (turnsSince < 6) return 0.8;
    if (turnsSince < 10) return 0.5;
    return 0.2; // 여전히 기억되지만 약화
  }
  if (severity === 'SEVERE') {
    if (turnsSince < 2) return 1.0;
    if (turnsSince < 5) return 0.6;
    return 0.3;
  }
  if (severity === 'MODERATE') {
    if (turnsSince < 2) return 0.8;
    return 0.4;
  }
  return 0.5;
}
```

### 4.4 Reconciliation (화해)

- 플레이어가 PERSUADE/HELP 의도로 SUCCESS 시 decayFactor 추가 감소
- CRITICAL 레벨은 reconciliation 불가 (퀘스트/엔딩 분기 영향)

---

## 5. LLM 프롬프트 통합

### 5.1 신규 블록: [돌발 사건 이력]

서버가 `runState.npcStates[X].suddenActions`를 조회해 currentTurn - suddenTurn 차이로 decay 계산 후 프롬프트에 주입.

```
[돌발 사건 이력]
⚠️ 이 NPC는 플레이어에게 공격/배신당한 기억이 있습니다.
현재 이 사건이 NPC의 말투·반응·거리감을 지배합니다.

- T14 "플레이어가 칼로 찔렀다" (CRITICAL, 1턴 전, 영향도 100%)
  → 벨론 대위: 극도의 공포·분노. 대화 거부 or 도주 or 보복 시도.
  → 서술 가이드: 이 사건을 무시하고 태연히 대화하지 말 것.
    공포에 떨거나, 분노로 무장을 꺼내거나, 도움을 외치거나.

NPC 반응 톤 우선순위 (HIGH → LOW):
1. 돌발 사건 이력 (CRITICAL/SEVERE)  ← **최우선**
2. 현재 posture
3. 대화 주제 반복 금지 규칙
```

### 5.2 system-prompt 규칙 추가

```
## 돌발 사건 반영 규칙

[돌발 사건 이력] 블록이 있으면 **다른 모든 규칙보다 우선** 적용하세요.

- CRITICAL (살해 시도): 공포·비명·출혈·도주 or 보복. 태연한 대화 절대 금지.
- SEVERE (폭행/위협): 긴장·움츠림·공격적 방어 태세. 친밀한 태도 금지.
- MODERATE (절도/협박): 거리감·불신·경계. 원만한 분위기 금지.

⚠️ "해당 사건이 없었던 것처럼" 서술하지 마세요.
⚠️ decayFactor가 낮더라도 한 문장은 반영해야 합니다 (간접적이어도).
```

### 5.3 기존 블록 조정
- `[NPC 감정 상태]`: posture가 돌발행동으로 전환된 상태로 이미 반영됨
- `[이번 방문 대화]`: T14 "찔렀다" 요약 품질 개선 (§7)

---

## 6. Mid Summary 품질 개선 (부수 작업)

### 6.1 현재 문제
T14 요약이 `@[NPC|URL]` 마커를 포함한 60자 fallback:
```
"...론 대위|/npc-portraits/captain_bellon.webp]
  '이 일을 어찌 수습할 작정이오!'"
```

### 6.2 개선안
- `@[NPC|URL]` 마커 제거 후 요약
- 사건 키워드(공격/훔침/배신) 우선 추출
- nano LLM THREAD 요약 실패 이유 디버깅 (왜 fallback으로 떨어졌나)

### 6.3 Fallback 품질 개선 (최소 변경)

```typescript
function fallbackSummary(llmOutput: string, suddenAction?: SuddenAction): string {
  let text = llmOutput.replace(/@\[[^\]]+\]/g, ''); // 마커 제거

  // 돌발행동 있으면 우선 prefix
  if (suddenAction) {
    return `⚠️ ${suddenAction.summary} | ...` + text.slice(-40);
  }

  return text.length > 60 ? '...' + text.slice(-60) : text;
}
```

---

## 7. 구현 단계

### Phase 1 — 서버 기본 (1일)
1. `sudden-action-detector.ts` 신규 작성 (키워드 + Intent 매칭)
2. `NPCState.suddenActions` 필드 추가 + 스키마
3. `ResolveService.applySuddenActionToNpc()` 구현
4. `IncidentMemory` 자동 등록 (PLAYER_VIOLENCE)
5. 유닛 테스트 15건
   · 키워드 감지 (8)
   · NPC posture 전환 (3)
   · IncidentMemory 등록 (2)
   · decayFactor 계산 (2)

### Phase 2 — LLM 프롬프트 통합 (반나절)
1. `context-builder`: `[돌발 사건 이력]` 블록 빌드
2. `prompt-builder`: 조건부 주입
3. `system-prompts`: 돌발 사건 반영 규칙 추가
4. 통합 테스트 5건

### Phase 3 — Mid Summary 개선 (반나절)
1. `@[NPC|URL]` 마커 제거 helper
2. suddenAction 시 요약 prefix
3. fallback 품질 테스트

### Phase 4 — Decay 운영 튜닝 (1~2일)
1. 플레이테스트 10건: 돌발행동 후 10턴 추적
2. decayFactor 계수 조정
3. Reconciliation (화해) 메커니즘 도입

---

## 8. 검증 기준

### 자동 테스트
- [ ] "칼로 찌른다" → severity=CRITICAL, type=KILL_ATTEMPT 감지
- [ ] CRITICAL 발생 시 NPC posture → HOSTILE 강제 전환
- [ ] NPC knownFacts에 요약 추가
- [ ] IncidentMemory에 PLAYER_VIOLENCE 카테고리 등록
- [ ] decayFactor 10턴 후 CRITICAL = 0.2
- [ ] T+1 LLM 프롬프트에 [돌발 사건 이력] 블록 포함

### 플레이테스트 정성 기준
- [ ] T+1: 찔린 NPC가 태연한 대화 **금지**
- [ ] T+1~3: 서술에 사건 영향 반영 (공포/분노/경보)
- [ ] T+5~10: 점차 일상 복귀 (decay)
- [ ] CRITICAL 이력은 퀘스트 분기·엔딩에 영향

---

## 9. 리스크 및 완화

| 리스크 | 완화책 |
|--------|--------|
| LLM이 여전히 규칙 무시 | 프롬프트 블록 우선순위 명시 + 사후 regex 감지 ("태연히"/"정상적으로" 매칭 시 플래그) |
| 키워드 오탐 ("목을 굽혀 인사한다" → 살해 오탐) | 동사 결합 2글자 이상 매칭 + 동작 컨텍스트 확인 |
| decayFactor 과도/부족 — 밸런스 | Phase 4 플레이테스트 기반 튜닝 |
| 퀘스트와 충돌 (퀘스트 NPC 찌르면 엔딩 막힘) | CRITICAL은 퀘스트 상태 fork (bad ending route) |
| 과도한 폭력 유도 플레이 | CRITICAL 누적 시 playerViolenceCount 증가 → 경비대 추적·배회 NPC 적대·상점 거부 |
| 파티 모드 호환 | Phase 4 이후 별도 — 파티원이 대신 공격하면? (다른 설계 필요) |

---

## 10. 기존 문서 연관

- `09_npc_politics.md` — 5축 감정 모델 · posture 전환 규칙 (기반)
- `14_user_driven_code_bridge.md` — IntentV3 → Incident 라우터 (확장 지점)
- `21_living_world_redesign.md` — NpcAgenda · ConsequenceProcessor (연동)
- `31_memory_system_v4.md` — Mid Summary 생성 로직 (§6 개선 대상)
- `34_player_first_event_engine.md` — TurnMode · NPC 결정 우선순위 (상위 프레임워크)
- `CLAUDE.md` Invariant 15 — NPC 이름 비공개→공개 단계 (관련)

---

## 11. 향후 확장

### 11.1 "세계가 기억하는 돌발행동"
- 같은 장소의 다른 NPC도 해당 사건을 "소문"으로 알게 됨
- 24시간 뒤 수비대 전체가 "수배자" 태도로 변환

### 11.2 "보복 이벤트" 동적 생성
- 살아남은 NPC가 복수 이벤트 스포닝 (EVT_REVENGE_X)
- 특정 장소 이동 시 과거 공격한 NPC가 무장 동료와 함께 등장

### 11.3 "양심" 시스템 (엔딩 분기)
- CRITICAL 누적 → 특정 엔딩 잠금 or 개방
- "이름 없는 용병" → "학살자" 성향 브랜딩

---

**작성일**: 2026-04-22
**배경 버그**: bug_reports.0907761f — "지금 사람을 찌른 후 상황인데 npc반응이 이상해요"
**상태**: 📎 설계 — 구현 대기
