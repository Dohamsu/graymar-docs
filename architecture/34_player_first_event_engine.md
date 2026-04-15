# 34. Player-First 이벤트 엔진 재설계

> **목표**: "이벤트가 유저를 끌고가는" 현재 구조를 "유저가 게임을 끌고가는" 구조로 전환
> **작성일**: 2026-04-15
> **상태**: 설계 중

---

## 1. 문제 진단

### 1.1 핵심 문제: 이벤트가 플레이어 의도를 덮어씀

```
현재 흐름:
플레이어: "구두닦이 소년에게 소문 묻기" (대상: NPC_BG_SHOE_SHINE)
     ↓
IntentParser: targetNpcId = NPC_BG_SHOE_SHINE ← 정확함
     ↓
EventMatcher: EVT_MARKET_DSC_4 매칭 (primaryNpcId: NPC_EDRIC_VEIL)
     ↓
❌ 이벤트 NPC가 플레이어 대상을 덮어씀!
     ↓
최종 NPC: NPC_EDRIC_VEIL (회계사) — 소년이 아닌 회계사가 응답
```

### 1.2 구조적 원인 3가지

| # | 원인 | 코드 위치 | 영향 |
|---|------|----------|------|
| **C1** | 이벤트 매칭이 플레이어 의도보다 먼저 실행됨 | turns.service.ts:1091-1234 | shouldMatchEvent 조건 충족 시 무조건 이벤트 선택 |
| **C2** | 이벤트의 primaryNpcId가 최종 NPC를 결정 | turns.service.ts:2129-2138 | textMatch/intentV3/conversationLock 실패 시 이벤트 NPC가 fallback |
| **C3** | BG NPC용 이벤트 부재 | events_v2.json | 123개 중 66개가 CORE/SUB NPC 하드코딩, BG NPC 이벤트 0개 |

### 1.3 실패하는 3가지 시나리오

| 시나리오 | 현재 결과 | 기대 결과 |
|---------|----------|----------|
| **S1**: 특정 NPC와 대화 이어가기 | 이벤트가 다른 NPC로 전환 | 같은 NPC와 자연스럽게 대화 지속 |
| **S2**: 이전 대화 참조 질문 | 무관한 이벤트 장면 생성 | 이전 맥락 기반 자연스러운 응답 |
| **S3**: BG NPC와 상호작용 | CORE NPC로 강제 전환 | BG NPC가 직접 응답 |

### 1.4 현재 이벤트 매칭 트리거 분석

```typescript
// turns.service.ts:1091-1097
const shouldMatchEvent =
  !isConversationContinuation && (
    isFirstTurnAtLocation ||      // 장소 첫 진입
    incidentPressureHigh ||       // 사건 압력 ≥ 50
    routingHasStrongIncident ||   // 강한 사건 라우팅
    questFactTrigger              // 미발견 퀘스트 팩트
  );
```

**문제**: `isConversationContinuation`이 유일한 방어선이지만, 이 조건은 **직전 턴이 같은 NPC와의 대화 행동**일 때만 작동. 플레이어가 새 NPC를 명시적으로 지목해도 shouldMatchEvent=true면 이벤트가 강제됨.

---

## 2. 설계 원칙

### 2.1 Player-First 원칙

```
변경 후 우선순위:

1순위: 플레이어가 명시한 대상/행동 (targetNpcId, actionType)
2순위: 대화 연속성 (conversationLock)
3순위: 세계 이벤트 (사건 압력, 퀘스트 트리거)
4순위: 배경 분위기 (NanoEventDirector 컨셉)
```

### 2.2 이벤트 역할 재정의

| | 현재 (Event-Driven) | 변경 후 (Player-First) |
|---|---|---|
| 이벤트 역할 | 매 턴 장면을 결정 | 특수 조건에서만 개입 |
| NPC 결정 | 이벤트가 NPC 배정 | 플레이어 의도가 NPC 결정, 이벤트는 참고 |
| LLM 지시 | 이벤트 sceneFrame 필수 | 플레이어 행동 맥락이 주요 지시 |
| 대화 흐름 | 이벤트 전환으로 끊김 | 플레이어가 끊을 때까지 지속 |

### 2.3 불변 유지 사항

- **퀘스트 팩트 발견 보장** — questFactTrigger 이벤트는 여전히 매칭
- **Arc/Incident 이벤트 보장** — 스토리 진행용 LANDMARK/ARC_HINT 유지
- **판정 공식 불변** — 1d6 + floor(stat/4) + baseMod
- **Heat/Safety 시스템 불변** — ±8 clamp, 0~100 범위
- **NPC 감정 시스템 불변** — trust/fear/respect/suspicion/attachment

---

## 3. 아키텍처 변경

### 3.1 턴 모드 분류 (신규)

현재 모든 LOCATION 턴이 동일한 파이프라인을 탄다. 이를 **3가지 턴 모드**로 분류한다:

```typescript
enum TurnMode {
  /** 플레이어가 NPC/행동을 명시 → 이벤트 매칭 스킵, NPC 직접 상호작용 */
  PLAYER_DIRECTED = 'PLAYER_DIRECTED',
  
  /** 대화 연속 중 → 이벤트 매칭 스킵, 같은 NPC 유지 */
  CONVERSATION_CONT = 'CONVERSATION_CONT',
  
  /** 세계 이벤트 트리거 → 기존 이벤트 매칭 파이프라인 */
  WORLD_EVENT = 'WORLD_EVENT',
}
```

### 3.2 턴 모드 결정 로직

```
┌─────────────────────────────────────────────────┐
│            TurnMode 결정 (Phase 2.5)            │
└─────────────────────────────────────────────────┘

Intent 파싱 완료 후, 이벤트 매칭 전에 실행:

1. targetNpcId가 명시적으로 존재하는가?
   ├─ YES → PLAYER_DIRECTED
   └─ NO ↓

2. 대화 연속 조건 충족? (SOCIAL_ACTION + lastPrimaryNpcId)
   ├─ YES → CONVERSATION_CONT
   └─ NO ↓

3. 강제 이벤트 트리거 존재?
   (questFactTrigger || isFirstTurnAtLocation || 
    incidentPressureHigh >= 70)
   ├─ YES → WORLD_EVENT
   └─ NO ↓

4. 기본값 → PLAYER_DIRECTED
   (플레이어 행동 중심, 이벤트 강제 없음)
```

**핵심 변경**: 기본값이 WORLD_EVENT → PLAYER_DIRECTED로 역전

### 3.3 모드별 파이프라인 차이

#### PLAYER_DIRECTED 모드

```
플레이어 입력 → IntentParser → targetNpcId 확정
    ↓
이벤트 매칭 스킵 → FREE_PLAYER_{turnNo} 이벤트 셸 생성
    ↓
NanoEventDirector 호출 (컨셉 생성만, NPC 변경 금지)
    ↓
ResolveService 판정 (matchPolicy=NEUTRAL, friction=0)
    ↓
LLM 서술 (플레이어 행동 + NPC 반응 중심)
```

**NanoEventDirector 제약**:
- `nanoEventResult.npcId`는 무시 (플레이어가 지정한 NPC 유지)
- `concept`, `tone`, `opening`은 분위기 참고용으로만 사용
- `fact` 추천은 유지 (퀘스트 진행)

#### CONVERSATION_CONT 모드

```
플레이어 입력 → IntentParser → conversationLockedNpcId 유지
    ↓
이벤트 매칭 스킵 → FREE_CONV_{turnNo} 이벤트 셸 (기존과 동일)
    ↓
NanoEventDirector 호출 (NPC 고정, 대화 깊이 반영)
    ↓
ResolveService 판정
    ↓
LLM 서술 ([대화 연속 상태] 블록 주입)
```

기존 isConversationContinuation 로직과 유사하지만, 트리거 조건을 완화:
- 현재: `!isFirstTurnAtLocation && lastPrimaryNpcId && SOCIAL_ACTIONS.has(actionType)`
- 변경: `lastPrimaryNpcId && SOCIAL_ACTIONS.has(actionType)` (첫 턴 제약 제거)
- 추가: 비대화 행동(SEARCH, OBSERVE)도 같은 NPC 맥락이면 CONVERSATION_CONT로 분류

#### WORLD_EVENT 모드

```
강제 트리거 감지 → 기존 이벤트 매칭 파이프라인
    ↓
SituationGenerator → EventDirector → ProceduralEvent (기존 그대로)
    ↓
★ 변경점: targetNpcId가 있으면 이벤트 NPC보다 우선
    ↓
ResolveService 판정
    ↓
LLM 서술
```

**WORLD_EVENT 진입 조건 강화** (이벤트 강제 트리거 축소):
```typescript
// 변경 전: 4가지 조건 중 하나만 충족
const shouldMatchEvent =
  isFirstTurnAtLocation ||
  incidentPressureHigh ||          // pressure >= 50
  routingHasStrongIncident ||
  questFactTrigger;

// 변경 후: 강제 트리거 임계값 상향
const shouldForceWorldEvent =
  isFirstTurnAtLocation ||
  incidentPressureHigh >= 70 ||    // 50 → 70으로 상향
  questFactTrigger;                 // 퀘스트 팩트는 유지
  // routingHasStrongIncident 제거 (강제가 아닌 가중치로 전환)
```

### 3.4 NPC 결정 우선순위 변경

```
변경 전 (turns.service.ts:2129-2138):
  eventPrimaryNpc =
    resolvedTargetNpcId           // 텍스트 매칭
    ?? conversationLockedNpcId    // 대화 잠금
    ?? event.payload.primaryNpcId // 이벤트 배정 ← 여기가 문제

변경 후:
  eventPrimaryNpc =
    resolvedTargetNpcId           // 1순위: 플레이어 명시 (텍스트 매칭)
    ?? intentV3.targetNpcId       // 2순위: IntentParser 결과 (기존에 누락)
    ?? conversationLockedNpcId    // 3순위: 대화 잠금
    ?? nanoEventResult?.npcId     // 4순위: NanoEventDirector 추천 (WORLD_EVENT만)
    ?? event.payload.primaryNpcId // 5순위: 이벤트 배정 (최후 fallback)
```

### 3.5 BG NPC 동적 이벤트 생성

BG NPC(BACKGROUND 티어)는 정적 이벤트 풀에 없으므로, NanoEventDirector가 동적으로 처리:

```typescript
// PLAYER_DIRECTED 모드 + BG NPC 대상
if (turnMode === 'PLAYER_DIRECTED' && targetNpc.tier === 'BACKGROUND') {
  // NanoEventDirector에 BG NPC 전용 컨텍스트 전달
  nanoCtx.forcedNpcId = targetNpcId;
  nanoCtx.npcTier = 'BACKGROUND';
  nanoCtx.npcRole = targetNpc.role;       // "구두닦이", "빵집 주인" 등
  nanoCtx.npcKnowledge = 'limited';       // BG NPC는 제한된 정보만
  
  // NanoEventDirector가 BG NPC 맥락에 맞는 컨셉 생성
  // fact 추천은 BG NPC의 locationId와 연관된 것만
}
```

**BG NPC 프롬프트 가이드라인**:
- BG NPC는 세계의 분위기를 전달하는 역할
- 직접적인 퀘스트 정보는 제공하지 않지만, 간접 힌트/소문은 가능
- 대화 깊이 제한: 최대 2턴 (이후 "더 이상 알지 못한다" 자연 종료)
- NPC 성격은 role 기반으로 LLM이 즉석 생성

---

## 4. 상세 변경 사항

### 4.1 turns.service.ts 변경

#### Phase 2.5: 턴 모드 결정 (신규 삽입 — Intent 파싱 후, 이벤트 매칭 전)

```typescript
// ── Phase 2.5: 턴 모드 결정 ──
const turnMode = this.determineTurnMode({
  targetNpcId: resolvedTargetNpcId,     // 텍스트 매칭 or IntentV3
  intentV3,
  intent,
  lastPrimaryNpcId,
  isFirstTurnAtLocation,
  incidentPressure: routingResult?.matchScore ?? 0,
  questFactTrigger,
  actionHistory,
});
```

```typescript
private determineTurnMode(ctx: {
  targetNpcId: string | null;
  intentV3: ParsedIntentV3 | null;
  intent: ParsedIntentV2;
  lastPrimaryNpcId: string | null;
  isFirstTurnAtLocation: boolean;
  incidentPressure: number;
  questFactTrigger: boolean;
  actionHistory: unknown[];
}): TurnMode {
  // 1) 플레이어가 NPC를 명시적으로 지목
  if (ctx.targetNpcId || ctx.intentV3?.targetNpcId) {
    return TurnMode.PLAYER_DIRECTED;
  }

  // 2) 대화 연속 (SOCIAL_ACTION + 이전 대화 NPC 존재)
  const SOCIAL = new Set([
    'TALK','PERSUADE','BRIBE','THREATEN','HELP',
    'INVESTIGATE','OBSERVE','TRADE',
  ]);
  if (ctx.lastPrimaryNpcId && SOCIAL.has(ctx.intent.actionType)) {
    return TurnMode.CONVERSATION_CONT;
  }

  // 3) 강제 세계 이벤트 (축소된 조건)
  if (
    ctx.isFirstTurnAtLocation ||
    ctx.incidentPressure >= 70 ||
    ctx.questFactTrigger
  ) {
    return TurnMode.WORLD_EVENT;
  }

  // 4) 기본값: 플레이어 주도
  return TurnMode.PLAYER_DIRECTED;
}
```

#### Phase 3: 이벤트 매칭 분기 (기존 로직 래핑)

```typescript
// ── Phase 3: 모드별 이벤트 처리 ──
let matchedEvent: EventDefV2 | null = null;

switch (turnMode) {
  case TurnMode.PLAYER_DIRECTED:
    matchedEvent = this.buildPlayerDirectedShell(turnNo, locationId, intent);
    break;

  case TurnMode.CONVERSATION_CONT:
    matchedEvent = this.buildConversationContShell(
      turnNo, locationId, lastPrimaryNpcId!, intent,
    );
    break;

  case TurnMode.WORLD_EVENT:
    // 기존 이벤트 매칭 파이프라인 (SituationGen → EventDirector → Procedural)
    matchedEvent = await this.matchWorldEvent(/* 기존 파라미터 */);
    break;
}

// FREE 이벤트 셸 보장 (WORLD_EVENT에서 매칭 실패 시)
if (!matchedEvent) {
  matchedEvent = this.buildFreeShell(turnNo, locationId, intent);
}
```

#### Phase 4c: NanoEventDirector 호출 변경

```typescript
// NanoEventDirector는 모든 모드에서 호출하되, 역할이 다름
if (this.nanoEventDirector) {
  const nanoCtx = this.buildNanoContext(/* ... */);
  
  // PLAYER_DIRECTED: NPC 변경 금지, 컨셉만 생성
  nanoCtx.npcLocked = (turnMode === TurnMode.PLAYER_DIRECTED 
                    || turnMode === TurnMode.CONVERSATION_CONT);
  
  nanoEventResult = await this.nanoEventDirector.generate(nanoCtx);
  
  // NPC 오버라이드는 WORLD_EVENT에서만 허용
  if (turnMode === TurnMode.WORLD_EVENT && nanoEventResult?.npcId) {
    event.payload.primaryNpcId = nanoEventResult.npcId;
  }
  // PLAYER_DIRECTED/CONVERSATION_CONT에서는 NPC 유지
}
```

### 4.2 NanoEventDirector 변경

#### npcLocked 모드 추가

```typescript
interface NanoEventContext {
  // ... 기존 필드
  npcLocked: boolean;          // true면 NPC 변경 금지
  forcedNpcId?: string;        // BG NPC 강제 지정
  npcTier?: 'CORE' | 'SUB' | 'BACKGROUND';
}
```

#### 프롬프트 분기

```typescript
// npcLocked=true일 때 시스템 프롬프트
if (ctx.npcLocked) {
  systemPrompt += `
NPC는 이미 결정되어 있습니다: ${ctx.forcedNpcId ?? ctx.lastNpcId}
이 NPC를 변경하지 마세요. 대신:
- 이 NPC에 맞는 상황 컨셉을 생성하세요
- 이 NPC가 자연스럽게 반응할 수 있는 장면을 만드세요
- NPC 필드에는 동일한 NPC를 반환하세요
`;
}

// BG NPC일 때 추가 지시
if (ctx.npcTier === 'BACKGROUND') {
  systemPrompt += `
이 NPC는 배경 인물(${ctx.npcRole})입니다.
- 제한된 정보만 가지고 있습니다 (소문, 일상 관찰)
- 퀘스트 핵심 정보를 직접 전달하지 않습니다
- 세계의 분위기와 일상을 전달하는 역할입니다
- 대화가 2턴 이상 이어지면 "더 이상 아는 게 없다"며 자연 종료
`;
}
```

### 4.3 event-matcher.service.ts 변경

#### targetNpcId 호환 필터 추가

WORLD_EVENT 모드에서도 플레이어 targetNpcId가 있으면 호환 이벤트 우선:

```typescript
// matchWithIncidentContext()에 targetNpcId 파라미터 추가
matchWithIncidentContext(
  candidates: EventDefV2[],
  // ... 기존 파라미터
  targetNpcId?: string | null,    // 신규
): EventDefV2 | null {
  
  // targetNpcId가 있으면 호환 이벤트 가중치 대폭 상향
  if (targetNpcId) {
    for (const evt of candidates) {
      const evtNpc = evt.payload.primaryNpcId;
      if (evtNpc === targetNpcId) {
        evt._weight = (evt._weight ?? evt.weight) + 50;  // +50 보너스
      } else if (evtNpc && evtNpc !== targetNpcId) {
        evt._weight = Math.max(1, (evt._weight ?? evt.weight) - 50);  // -50 패널티
      }
      // primaryNpcId가 없는 이벤트는 중립 (어떤 NPC와도 호환)
    }
  }
}
```

### 4.4 LLM 프롬프트 변경

#### PLAYER_DIRECTED 모드 전용 프롬프트 블록

```typescript
// prompt-builder.service.ts
if (turnMode === 'PLAYER_DIRECTED') {
  blocks.push(`
[플레이어 주도 장면]
플레이어가 직접 ${targetNpcDisplayName}에게 접근했습니다.
- 이 NPC가 플레이어의 행동에 자연스럽게 반응하도록 서술하세요
- 다른 NPC가 끼어들거나 장면을 가로채지 마세요
- 판정 결과(${outcome})에 맞는 NPC 반응을 보여주세요
`);
}
```

#### BG NPC 서술 가이드

```typescript
if (targetNpcTier === 'BACKGROUND') {
  blocks.push(`
[배경 인물 상호작용]
${targetNpcDisplayName}은(는) ${npcRole}입니다.
- 이 인물만의 개성과 말투를 즉석에서 만들어주세요
- 직업과 일상에 맞는 소소한 정보를 전달할 수 있습니다
- 핵심 비밀이나 퀘스트 정보는 "잘 모르겠는데..." 정도로 간접 암시만
- 세계의 분위기와 활기를 전달하는 데 집중하세요
`);
}
```

---

## 5. 이벤트 트리거 재설계

### 5.1 트리거 조건 비교

| 조건 | 현재 | 변경 후 | 이유 |
|------|------|---------|------|
| isFirstTurnAtLocation | WORLD_EVENT | WORLD_EVENT | 장소 진입 시 분위기 설정 필요 |
| incidentPressureHigh (≥50) | WORLD_EVENT | ≥70으로 상향 | 50은 너무 잦음, 플레이어 행동 방해 |
| routingHasStrongIncident | WORLD_EVENT | **제거** (가중치로 전환) | 강제가 아닌 NanoEventDirector 컨셉에 반영 |
| questFactTrigger | WORLD_EVENT | WORLD_EVENT | 퀘스트 진행 보장 필수 |
| 플레이어 targetNpcId 있음 | (고려 안함) | PLAYER_DIRECTED | **신규**: 플레이어 의도 우선 |
| 대화 연속 | CONV_CONT (부분적) | CONVERSATION_CONT (강화) | 비대화 행동도 맥락 유지 |

### 5.2 이벤트 발생 빈도 예상

| 턴 유형 | 현재 비율 (추정) | 변경 후 비율 (목표) |
|---------|-----------------|-------------------|
| 이벤트 강제 턴 | ~60% | ~25% |
| 대화 연속 턴 | ~15% | ~30% |
| 플레이어 주도 턴 | ~25% (FREE) | ~45% |

### 5.3 WORLD_EVENT 중 플레이어 의도 보존

WORLD_EVENT 모드에서도 targetNpcId가 있으면:

```
1. 이벤트 매칭 시 targetNpcId 호환 이벤트 가중치 +50
2. 매칭된 이벤트의 primaryNpcId와 targetNpcId가 다르면:
   a. 이벤트 sceneFrame은 유지 (세계 이벤트 분위기)
   b. primaryNpcId는 targetNpcId로 교체 (플레이어 대상 유지)
   c. LLM 프롬프트: "세계 이벤트가 일어나는 중에 {NPC}와 상호작용"
```

---

## 6. 구현 계획

### Phase 1: 턴 모드 분류 + NPC 우선순위 변경 (핵심)

**변경 파일**:
| 파일 | 변경 내용 |
|------|----------|
| `turns.service.ts` | TurnMode enum + determineTurnMode() + Phase 3 분기 |
| `turns.service.ts` | NPC 결정 우선순위 변경 (라인 2129-2138) |
| `turns.service.ts` | NanoEventDirector npcLocked 전달 |

**검증**:
- 플레이테스트 10턴: "소년에게 말 걸기" → 소년이 응답하는지
- 대화 연속 3턴: 같은 NPC 유지되는지
- 퀘스트 팩트 트리거: 여전히 작동하는지

### Phase 2: NanoEventDirector npcLocked 모드 + BG NPC

**변경 파일**:
| 파일 | 변경 내용 |
|------|----------|
| `nano-event-director.service.ts` | npcLocked 모드, BG NPC 프롬프트 |
| `prompt-builder.service.ts` | PLAYER_DIRECTED 프롬프트 블록 |
| `prompt-builder.service.ts` | BG NPC 서술 가이드 블록 |

**검증**:
- BG NPC 대화 자연스러운지
- npcLocked에서 NPC 변경 안 되는지
- LLM 서술 품질 유지되는지

### Phase 3: 이벤트 트리거 축소 + EventMatcher targetNpcId

**변경 파일**:
| 파일 | 변경 내용 |
|------|----------|
| `turns.service.ts` | shouldMatchEvent 조건 강화 (pressure ≥70, routing 제거) |
| `event-matcher.service.ts` | targetNpcId 호환 가중치 |

**검증**:
- 이벤트 발생 빈도 감소 확인
- 퀘스트 진행 속도 유지되는지
- Arc 이벤트 정상 발동하는지

---

## 7. 리스크 및 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| 이벤트 감소로 퀘스트 진행 지연 | 높음 | questFactTrigger는 WORLD_EVENT 유지, NanoEventDirector fact 추천 강화 |
| BG NPC 대화 품질 낮음 | 중간 | NanoEventDirector BG 전용 프롬프트 + 2턴 제한 |
| 장소 분위기 없는 턴 증가 | 중간 | NanoEventDirector가 PLAYER_DIRECTED에서도 컨셉/톤 제공 |
| WORLD_EVENT 중 NPC 충돌 | 낮음 | targetNpcId 있으면 이벤트 NPC 교체 |
| 기존 테스트 깨짐 | 높음 | determineTurnMode()를 독립 메서드로 분리하여 단위 테스트 |

---

## 8. 변경 전/후 플로우 비교

### 변경 전

```
매 LOCATION 턴:
  IntentParse → shouldMatchEvent? → [YES] → SitGen/EventDir/Procedural → 이벤트 NPC 강제
                                  → [NO]  → isConvCont? → [YES] → FREE_CONV
                                                        → [NO]  → FREE (드문 경우)
```

### 변경 후

```
매 LOCATION 턴:
  IntentParse → determineTurnMode()
    → PLAYER_DIRECTED (기본값) → FREE_PLAYER 셸 + NanoEvent(npcLocked) → 플레이어 NPC 유지
    → CONVERSATION_CONT        → FREE_CONV 셸 + NanoEvent(npcLocked) → 대화 NPC 유지
    → WORLD_EVENT (축소 조건)   → SitGen/EventDir + targetNpcId 보존 → 이벤트 + 플레이어 의도 공존
```

---

## 9. 성공 지표

| 지표 | 현재 | 목표 |
|------|------|------|
| NPC 전환 없이 대화 이어가기 성공률 | ~40% | ≥90% |
| BG NPC 상호작용 가능 여부 | 불가 | 가능 (2턴 제한) |
| 플레이어 지목 NPC 정확 응답률 | ~60% | ≥95% |
| 이벤트 강제 턴 비율 | ~60% | ~25% |
| 퀘스트 팩트 발견 속도 | 기준선 | 기준선 ±10% (유지) |
