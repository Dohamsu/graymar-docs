# 32 — 대사 분리 파이프라인: 서술/대사 2-Stage LLM 아키텍처

> 메인 LLM의 서술과 NPC 대사 생성을 분리하여,
> 각 역할에 특화된 프롬프트로 품질 향상 + 토큰 절감 + 마커 문제 해소.
>
> 작성: 2026-04-14

---

## 1. 현재 시스템 문제점

| 문제 | 원인 | 영향 |
|------|------|------|
| 하오체 불일치 | 메인 LLM이 서술(해라체)+대사(경어체) 동시 생성 | NPC 대사에 해라체 혼입 |
| @마커 오류 | LLM이 마커 형식을 직접 출력 → 오마킹/누락 | 타이핑 중 raw 마커 노출 |
| NPC 캐릭터성 약화 | 하나의 프롬프트에 서술+대사+판정+연속성 규칙 혼재 | 대사가 generic해짐 |
| 프롬프트 비대 | 대사 규칙만 ~3,180토큰 (전체의 30%) | 토큰 낭비, 지시 준수율 저하 |
| 초상화 누락 | LLM이 마커에 URL을 안 붙이거나 잘못 붙임 | 카드 미표시 |

---

## 2. 아키텍처 개요

```
[기존: 1-Stage]
NanoDirector → 메인 LLM (서술+대사 통합) → 후처리(마커/별칭)
                     ↓
              단일 프롬프트 ~10K 토큰

[제안: 2-Stage]
NanoDirector → Stage A: 서술 LLM (환경+행동+골격)
                     ↓ dialogue_slot 포함 JSON
              Stage B: 대사 LLM (NPC별 대사 생성)
                     ↓ 대사 텍스트
              서버 조립 (마커 자동 삽입)
```

---

## 3. Stage A: 서술 생성 (메인 LLM)

### 3.1 역할

- 환경/감각 묘사
- 플레이어 행동 결과 서술
- NPC 등장/행동 묘사 (대사 제외)
- 대사가 들어갈 위치와 의도를 `dialogue_slot`으로 지정

### 3.2 프롬프트 변경

**제거 (~3,180토큰 절감):**
- NPC 대사 작성 규칙 (하오체, 경어체, 따옴표 규칙)
- 대사 호칭 패턴 (speaker_alias 지시)
- 직전 대사 추출/반복 금지
- NPC 대화 자세/단계 블록

**유지:**
- 서술 문체 (해라체)
- 세계관, 장면 범위, 연속성 규칙
- NPC 등장 방식 (시각적 묘사)

**추가:**
- `dialogue_slot` 출력 형식 지시
- intent enum 가이드

### 3.3 JSON 출력 형식

```typescript
interface NarrativeJsonOutput_v2 {
  segments: Array<
    | { type: 'narration'; text: string }
    | {
        type: 'dialogue_slot';
        speaker_id: string;        // NPC_HARLUN
        intent: DialogueIntent;    // WARN, INFO, QUESTION, REFUSE, GREET, REACT
        context: string;           // "플레이어가 쇠사슬을 주움, 밀수 의심"
        tone?: string;             // "경계하며", "낮은 목소리로"
      }
  >;
  choices?: Array<{ label: string; affordance: string; hint?: string }>;
  memories?: Array<{ category: string; text: string }>;
  thread?: string;
}

type DialogueIntent =
  | 'WARN'      // 경고
  | 'INFO'      // 정보 전달
  | 'QUESTION'  // 질문
  | 'REFUSE'    // 거부/거절
  | 'GREET'     // 인사/자기소개
  | 'REACT'     // 감정 반응
  | 'HINT'      // 단서/암시
  | 'THREATEN'  // 위협
  | 'TRADE';    // 거래 제안
```

### 3.4 출력 예시

```json
{
  "segments": [
    { "type": "narration", "text": "새벽빛이 부두를 은빛으로 물들인다. 당신은 창고 입구에서 떨어진 쇠사슬 조각을 주워 들었다." },
    { "type": "narration", "text": "투박한 노동자가 불안한 눈빛으로 당신을 바라본다. 그의 손이 작업복 주머니 안에서 움직인다." },
    { "type": "dialogue_slot", "speaker_id": "NPC_HARLUN", "intent": "WARN", "context": "쇠사슬 발견, 임금 조작 의심, 주변 경계", "tone": "나지막이" },
    { "type": "narration", "text": "그의 눈빛이 창고 뒤쪽으로 흘렀다. 문틈으로 낯선 기름 냄새가 스며나온다." },
    { "type": "dialogue_slot", "speaker_id": "NPC_SERA_DOCKS", "intent": "WARN", "context": "창고 접근 금지, 하역 후 출입 제한", "tone": "무표정하게" }
  ],
  "thread": "부두 창고에서 쇠사슬 발견, 노동자 경고, 창고 여인 접근 금지"
}
```

### 3.5 비용/속도

- 프롬프트: ~7K 토큰 (현재 ~10K에서 30% 절감)
- 출력: ~400 토큰 (대사 없이 서술만)
- 비용: Flash ~3.5원, Qwen3 ~1.5원
- 속도: 2~4초

---

## 4. Stage B: NPC 대사 생성

### 4.1 역할

- dialogue_slot별 NPC 대사 텍스트 생성
- 하오체/경어체 일관성 100% 보장
- NPC 성격/감정/posture 반영
- knownFacts 기반 정보 공개

### 4.2 프롬프트

```
시스템: 당신은 중세 판타지 RPG의 NPC 대사 작성자입니다.

## 규칙
- 모든 대사는 경어체(~소/~오/~하오/~이오)로만 작성합니다.
- 금지 어미: ~다(해라체), ~지(반말), ~합니다(현대), ~일세(고어)
- 플레이어 지칭: "그대" 또는 "당신"
- 대사 길이: 1~2문장 (30~80자)
- 캐릭터 성격과 감정 상태를 반영합니다.

## NPC 정보
{npcProfile}

## 상황
{dialogueSlot.context}

## 지시
의도: {dialogueSlot.intent}
톤: {dialogueSlot.tone}

## 출력
NPC 대사만 작성하세요. 따옴표 없이 대사 텍스트만.
```

### 4.3 입력 구조

```typescript
interface DialogueGenerationInput {
  slot: {
    speaker_id: string;
    intent: DialogueIntent;
    context: string;
    tone?: string;
  };
  npcProfile: {
    name: string;
    unknownAlias: string;
    shortAlias: string;
    role: string;
    personality: {
      speechStyle: string;     // "투박하고 직설적, 의리 있는 어투"
      innerConflict: string;
      signature: string[];     // 시그니처 표현
    };
    posture: string;           // FRIENDLY | CAUTIOUS | HOSTILE
    emotional: { trust: number; fear: number };
    encounterCount: number;
  };
  // 선택적: knownFacts에서 이번에 공개할 정보
  factToReveal?: string;
  // 이전 대사 (반복 방지)
  previousDialogues?: string[];
  // Stage A 서술 골격 (문맥 파악용)
  narrativeContext: string;
}
```

### 4.4 출력 구조

```typescript
interface DialogueGenerationOutput {
  text: string;           // NPC 대사 (따옴표 없이)
  speaker_alias: string;  // 표시 이름 (unknownAlias or name)
}
```

### 4.5 비용/속도

- 프롬프트: ~1.5K 토큰 (NPC 정보 + 상황 + 규칙)
- 출력: ~50 토큰 (대사 1~2문장)
- 모델: nano (gpt-4.1-nano) — 대사만이므로 경량 모델로 충분
- 비용: ~0.15원/슬롯
- 속도: ~0.5초/슬롯
- 다중 슬롯: 병렬 호출 → 슬롯 수에 무관하게 ~0.5초

---

## 5. 서버 조립

### 5.1 조립 로직

```typescript
async assembleWithDialogue(
  stageA: NarrativeJsonOutput_v2,
  dialogueResults: Map<number, DialogueGenerationOutput>,
  npcStates: Record<string, NPCState>,
): string {
  const parts: string[] = [];
  let slotIdx = 0;

  for (const seg of stageA.segments) {
    if (seg.type === 'narration') {
      parts.push(seg.text);
    } else if (seg.type === 'dialogue_slot') {
      const result = dialogueResults.get(slotIdx);
      if (result) {
        // 서버가 직접 마커 삽입 → 오마킹 0%
        const npcDef = this.content.getNpc(seg.speaker_id);
        const npcState = npcStates[seg.speaker_id];
        const displayName = getNpcDisplayName(npcState, npcDef, turnNo);
        const portrait = NPC_PORTRAITS[seg.speaker_id] ?? '';
        const marker = portrait
          ? `@[${displayName}|${portrait}]`
          : `@[${displayName}]`;
        parts.push(`${marker} "${result.text}"`);
      }
      slotIdx++;
    }
  }

  return parts.join('\n');
}
```

### 5.2 마커 자동 삽입의 이점

| 항목 | Before (LLM 생성) | After (서버 삽입) |
|------|-------------------|------------------|
| 마커 형식 | LLM이 `@[이름\|URL]` 직접 출력 | 서버가 DB에서 정확한 이름+URL 삽입 |
| 오마킹 | 30% 턴에서 발생 | 0% |
| 초상화 URL | LLM이 URL을 기억해야 함 | 서버가 NPC_PORTRAITS에서 직접 참조 |
| unknownAlias 관리 | LLM이 introduced 상태 판단 | 서버가 getNpcDisplayName() 호출 |
| 타이핑 중 노출 | 불완전 마커 보임 | 완성된 마커만 존재 |

---

## 6. 파이프라인 전체 흐름

```
1. 턴 제출 → ServerResult 생성
2. ContextBuilder.build() → LLM 컨텍스트
3. NanoDirector/NanoEventDirector → 연출 지시서
4. PromptBuilder.build() → Stage A 프롬프트 (대사 규칙 제외)
5. Stage A: 메인 LLM 호출 → JSON (narration + dialogue_slot)
   ├─ 파싱 + dialogue_slot 추출
   ├─ 각 slot의 NPC 정보 수집
   └─ Stage B 호출 (병렬)
6. Stage B: 대사 LLM 호출 (slot당 1회, 병렬) → 대사 텍스트
7. 서버 조립: narration + dialogue + @마커 → 최종 서술
8. 후처리: deduplicateAliases, FactExtractor, THREAD 생성
9. DB 저장 → 클라이언트 폴링
```

---

## 7. 비용/성능 비교

| 항목 | 현재 (1-Stage) | 제안 (2-Stage) | 차이 |
|------|---------------|---------------|------|
| Stage A 프롬프트 | 10K | 7K | -30% |
| Stage A 출력 | 700 | 400 | -43% |
| Stage A 비용 | 5.6원 (Flash) | 3.5원 | -38% |
| Stage B 프롬프트 | - | 1.5K × 2슬롯 | +3K |
| Stage B 출력 | - | 50 × 2슬롯 | +100 |
| Stage B 비용 | - | 0.3원 (nano) | +0.3원 |
| **총 비용** | **5.6원** | **3.8원** | **-32%** |
| **총 레이턴시** | **3~6초** | **3~5초** | **유사** |
| 대사 품질 | 하오체 90% | 하오체 99%+ | ↑ |
| 마커 정확도 | 70~90% | 100% | ↑↑ |

---

## 8. Fallback 전략

### 8.1 Stage A 실패

JSON 파싱 실패 → 기존 1-Stage 파이프라인으로 fallback (현재 코드 유지)

### 8.2 Stage B 실패

대사 LLM 실패 → 서버가 간단 fallback 대사 생성:

```typescript
function fallbackDialogue(intent: DialogueIntent, npcAlias: string): string {
  const fallbacks: Record<DialogueIntent, string[]> = {
    WARN: ['조심하시오.', '위험하오.'],
    INFO: ['알아두시오.', '들어보시오.'],
    QUESTION: ['무슨 일이시오?', '무엇을 찾으시오?'],
    REFUSE: ['그건 곤란하오.', '더 이상 할 말이 없소.'],
    GREET: ['어서 오시오.', '무슨 용무이시오?'],
    REACT: ['흠...', '그렇소.'],
    HINT: ['혹시...', '한 가지 알려드리리다.'],
    THREATEN: ['그대의 안전을 보장할 수 없소.'],
    TRADE: ['거래를 원하시오?'],
  };
  return fallbacks[intent]?.[0] ?? '...';
}
```

### 8.3 dialogue_slot 미생성

메인 LLM이 dialogue_slot 없이 narration만 출력 → NPC 등장 없는 턴으로 처리 (정상)

---

## 9. 마이그레이션 전략

### Phase A: Stage B 구현 (대사 전용 LLM)

1. `DialogueGeneratorService` 생성
2. 대사 전용 프롬프트 설계
3. llm-worker에서 dialogue_slot 감지 → Stage B 호출
4. 조립 로직 구현
5. 기존 1-Stage와 A/B 테스트

### Phase B: Stage A 프롬프트 축소

1. 시스템 프롬프트에서 대사 규칙 제거
2. JSON 스키마에 dialogue_slot 추가
3. NPC 대화 자세/단계 블록 Stage B로 이동
4. 10턴 플레이테스트 검증

### Phase C: 마커 파이프라인 간소화

1. npc-dialogue-marker.service.ts 호출 제거 (2-Stage 경로)
2. cleanResidualMarkers 간소화
3. 클라이언트 마커 방어 코드 유지 (안전장치)

### Phase D: 1-Stage 코드 정리

1. 기존 대사 생성 프롬프트 deprecated
2. 마커 서비스 fallback 전용으로 격하
3. A/B 테스트 플래그 제거

---

## 10. 참고 문헌

- Skeleton-of-Thought (Ning et al. 2023) — 골격+채우기 패턴. arxiv.org/abs/2307.15337
- Self-Refine (Madaan et al. 2023) — 멀티 스테이지 품질 향상. arxiv.org/abs/2303.17651
- CALYPSO (Zhu et al. 2023) — TTRPG LLM 역할 분리. arxiv.org/abs/2308.07540
- Voyager (Wang et al. 2023) — 멀티 에이전트 작업 분해. arxiv.org/abs/2305.16291
- AI Dungeon — 단일→멀티 스테이지 진화 사례
- Character.AI — 대사 전문화 프로덕션 검증
- Inworld AI — 캐릭터 대사/씬 묘사 분리 상용화
