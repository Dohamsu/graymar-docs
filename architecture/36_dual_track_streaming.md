# 36. Dual-Track 스트리밍 재설계

> **목표**: 서술+대사 LLM(스트리밍)과 계산 LLM(백그라운드)을 병렬 분리하여 깨끗한 실시간 타이핑 구현
> **작성일**: 2026-04-16
> **상태**: 설계 중

---

## 1. 현재 문제

현재 LLM이 서술+대사+시스템태그([CHOICES], [THREAD], [MEMORY])를 모두 한 번에 생성하고, 후처리에서 분리하는 구조. 스트리밍 시 후처리 전 원문이 노출되어:

- @마커, [CHOICES], [THREAD] 등 시스템 태그가 화면에 보임
- 대사가 말풍선이 아닌 일반 텍스트로 노출
- 후처리 완료 후 전체 교체 → 타이핑 중단 + 깜빡임

---

## 2. 설계: Dual-Track 아키텍처

```
턴 제출 (Resolve 즉시 응답)
    ↓
    Track 1: 서술 LLM (스트리밍)
    → 순수 서술 + 대사(따옴표)만 생성
    → 시스템 태그 없음
    → SSE로 토큰 실시간 전송
    → 클라이언트: 타이핑 + 따옴표 대사 → 말풍선 변환
    ↓
    Track 1 완료 → 서술 후처리 (경량)
    ↓
    Track 2: 계산 LLM (서술 결과 기반, 순차)
    → 선택지 생성 (NanoEventDirector, 서술 맥락 포함)
    → 메모리/요약 추출 (FactExtractor)
    → 클라이언트: 짧은 로딩 표시
    ↓
    Track 2 완료 → done 이벤트 (최종 서술 + 선택지)
    → 선택지 표시
```

> **핵심 변경**: Track 2는 서술 결과를 입력으로 사용하므로 Track 1 완료 후 순차 실행.
> 유저가 타이핑을 읽는 시간 + 짧은 로딩으로 대기감을 최소화.

---

## 3. Track 1: 서술 LLM (스트리밍)

### 3.1 프롬프트 변경

기존 프롬프트에서 제거:
- `[CHOICES]` 선택지 생성 지시
- `[THREAD]` 메모리 태그 생성 지시
- `[MEMORY]` 기억 태그 생성 지시
- `@NPC_ID` 마커 삽입 지시

LLM에게 요구하는 것:
- 환경 묘사 + NPC 행동/반응 + 대사(따옴표)
- NPC 대사는 반드시 큰따옴표(`"대사"`)로 감싸기
- 대사 직전에 NPC 호칭 언급 (화자 식별용)
- 시스템 태그, 마커 일체 생성 금지

프롬프트 예시:
```
서술 규칙:
- 환경, NPC 행동, 대사를 자연스럽게 묘사하세요.
- NPC 대사는 반드시 큰따옴표로 감싸세요. 예: "이 서류를 확인하시오."
- 대사 직전에 NPC 호칭을 한 번 언급하세요. 예: 회계사가 입을 열었다. "대사"
- @마커, [태그], 선택지, 메모리 등 시스템 요소를 포함하지 마세요.
- 순수 서술 텍스트만 생성하세요.
```

### 3.2 스트리밍 흐름

```
LLM 토큰 생성 → SSE 전송 → 클라이언트 수신
    ↓
StreamClassifier:
    일반 텍스트 → narration 이벤트 (문장 단위)
    큰따옴표 감지 → 버퍼링 → 닫는 따옴표 → NPC 식별 → dialogue 이벤트
    ↓
클라이언트 StreamingBlock:
    narration → 글자 단위 타이핑
    dialogue → NPC 이름 + 초상화 + 글자 단위 타이핑 (말풍선)
```

### 3.3 NPC 식별 (StreamClassifier)

따옴표 대사의 화자를 실시간 식별:
1. 따옴표 직전 60자에서 NPC 이름/호칭 매칭
2. 발화동사 패턴 ("~가 말했다", "~이 답했다") 감지
3. 대명사 ("그가", "그녀가") → 직전 매칭 NPC
4. fallback → primaryNpcId (턴의 주 NPC)

NPC 후보 목록에 이름, 별칭, 역할, 초상화 URL이 포함되어 있으므로 말풍선 렌더링에 필요한 정보를 즉시 제공.

### 3.4 스트리밍 완료 후 서술 후처리

서술 LLM 완료 후 경량 후처리만 수행:
- Step C: 실명 세이프가드 (introduced=false 체크)
- Step F: NPC 불일치 교정 (primaryNpcId vs 실제 등장 NPC)
- Step D: 발화 도입 문장 트리밍 (선택적)

제거되는 후처리:
- Step A: 마커 삽입 (불필요 — 마커 없는 깨끗한 텍스트)
- Step B: 마커 변환 (불필요)
- Step E: NPC이름 프리픽스 제거 (불필요 — 프롬프트에서 방지)

---

## 4. Track 2: 계산 LLM (백그라운드)

### 4.1 병렬 실행 항목

| 항목 | 담당 | 현재 위치 |
|------|------|----------|
| 선택지 생성 | NanoEventDirector (nano LLM) | llm-worker |
| 메모리 추출 | FactExtractor (nano LLM) | llm-worker |
| 요약 생성 | MidSummary | llm-worker |
| NPC 감정 업데이트 | 서버 로직 (LLM 불필요) | turns.service |

### 4.2 실행 시점

Track 2는 **Track 1(서술) 완료 후** 시작:
- 선택지(NanoEventDirector): 서술 맥락을 입력으로 사용 → 서술에서 발생한 상황에 맞는 선택지 생성
- FactExtractor: 서술 내용에서 사실 추출
- MidSummary: 서술 내용 요약

모두 서술 결과가 필요하므로 순차 실행. 하지만 유저는 이때 타이핑을 읽는 중이므로 체감 대기 최소.
Track 2 처리 중 클라이언트에 짧은 로딩 인디케이터 표시.

### 4.3 결과 전달

Track 2 결과는 done 이벤트에 포함:
```typescript
// done 이벤트
{
  type: 'done',
  narrative: '후처리 완료된 최종 서술',
  choices: [
    { id: 'nano_1', label: '선택지 텍스트', affordance: 'TALK' },
    ...
  ],
}
```

---

## 5. 클라이언트 변경

### 5.1 StreamingBlock (Track 1 수신)

```
SSE 이벤트 수신:
  narration → 글자 단위 타이핑 (25ms/글자, 구두점 딜레이)
  dialogue → NPC 말풍선 + 글자 단위 타이핑
  done → 후처리 완료본으로 교체 (typed=true, 재타이핑 없음) + 선택지 표시
```

StreamingBlock은 StoryBlock(내레이터 박스) 안에서 렌더링.

### 5.2 정제 불필요

Track 1의 LLM 출력에 시스템 태그가 없으므로:
- `cleanStreamText()` 함수 불필요 (또는 최소한의 안전망만)
- @마커 파싱 불필요 (따옴표 기반 대사 감지)
- StreamClassifier가 깨끗한 텍스트에서 따옴표만 감지

### 5.3 선택지 표시 타이밍

```
서술 타이핑 중 → (유저가 읽는 시간)
서술 타이핑 완료 →
  Track 2 이미 완료됨 → 즉시 선택지 표시
  Track 2 아직 진행 중 → 짧은 로딩 인디케이터 (점 애니메이션) → 완료 시 선택지 표시
```

로딩 인디케이터는 선택지 영역에 "..." 또는 스피너로 표시.
Track 2는 nano LLM(300~500ms) × 2~3회이므로 보통 1~2초 이내 완료.

---

## 6. 서버 변경

### 6.1 프롬프트 빌더

- 시스템 태그 생성 지시 제거 ([CHOICES], [THREAD], [MEMORY])
- 대사 형식 지시 추가 (따옴표 + NPC 호칭)
- @마커 지시 제거

### 6.2 LLM Worker

```
기존:
  LLM 호출 (서술+태그+대사) → 후처리 6단계 → DB 저장

변경:
  Track 1: LLM 스트리밍 (서술+대사만) → SSE 전송 → 경량 후처리 → DB 저장
  Track 2: 병렬 — NanoEventDirector(선택지) + FactExtractor(메모리)
  둘 다 완료 → done 이벤트
```

### 6.3 StreamClassifier

현재 역할 유지 + 강화:
- 문장 단위 버퍼링
- 따옴표 대사 감지 → dialogue 이벤트 (NPC 이름 + 초상화)
- 시스템 태그 필터링 (안전망 — 프롬프트 위반 시)

---

## 7. 구현 계획

### Phase 1: 프롬프트 분리 (서버)

**목표**: LLM이 순수 서술+따옴표 대사만 생성하도록 프롬프트 변경

**변경 파일**:
| 파일 | 변경 |
|------|------|
| `server/src/llm/prompts/system-prompts.ts` | [CHOICES], [THREAD], [MEMORY] 생성 지시 제거. @마커 지시 제거. "따옴표 대사 + NPC 호칭" 지시 추가 |
| `server/src/llm/prompts/prompt-builder.service.ts` | 시스템 태그 관련 프롬프트 블록 제거. 대사 형식 지시 추가 |

**검증**:
- dry-run으로 프롬프트 추출 → 시스템 태그 지시 없는지 확인
- 5턴 플레이테스트 → LLM 출력에 [CHOICES], [THREAD], @NPC_ 없는지 확인

### Phase 2: LLM Worker Track 분리 (서버)

**목표**: 스트리밍 완료 후 Track 2(선택지+메모리)를 서술 결과 기반으로 호출

**변경 파일**:
| 파일 | 변경 |
|------|------|
| `server/src/llm/llm-worker.service.ts` | Track 1(스트리밍) 완료 후 Track 2 시작. NanoEventDirector에 서술 텍스트 전달. FactExtractor에 서술 텍스트 전달. Track 2 완료 후 done 이벤트에 선택지 포함 |
| `server/src/llm/nano-event-director.service.ts` | NanoEventContext에 narrativeText 필드 추가. 선택지 생성 시 서술 맥락 참조 |
| `server/src/llm/llm-stream-broker.service.ts` | `choices_loading` 이벤트 타입 추가 (Track 2 시작 알림) |

**상세 흐름**:
```typescript
// LLM Worker 내부
// Track 1: 스트리밍
for await (const chunk of this.llmCaller.callStream(request)) {
  streamBroker.emit(runId, turnNo, segEvt.type, segEvt); // narration/dialogue
}
// Track 1 완료 → 경량 후처리 (Step C, F만)
narrative = applyLightPostProcess(rawNarrative);

// Track 2 시작 알림
streamBroker.emit(runId, turnNo, 'choices_loading', {});

// Track 2: 선택지 생성 (서술 맥락 포함)
const nanoResult = await nanoEventDirector.generate({
  ...nanoCtx,
  narrativeText: narrative,  // 서술 결과 전달
});

// Track 2: 메모리 추출
const facts = await factExtractor.extract(narrative, ...);

// Track 2: 요약
const summary = await midSummary.generate(narrative, ...);

// 모두 완료 → done
streamBroker.emit(runId, turnNo, 'done', {
  narrative,
  choices: nanoResult?.choices ?? serverDefaultChoices,
});
```

### Phase 3: 후처리 경량화 (서버)

**목표**: 스트리밍 모드에서 불필요한 후처리 단계 제거

**변경 파일**:
| 파일 | 변경 |
|------|------|
| `server/src/llm/llm-worker.service.ts` | 스트리밍 모드용 경량 후처리 함수 분리 |

**경량 후처리 (스트리밍 모드)**:
| 단계 | 유지/제거 | 이유 |
|------|----------|------|
| Step A (마커 삽입) | 제거 | @마커 없는 깨끗한 텍스트, StreamClassifier가 실시간 처리 |
| Step B (마커 변환) | 제거 | @마커 없음 |
| Step C (실명 가드) | 유지 | introduced=false NPC 실명 노출 방지 |
| Step D (발화 트리밍) | 제거 | @마커 기반이므로 불필요 |
| Step E (NPC이름: 제거) | 제거 | 프롬프트에서 방지 |
| Step F (NPC 교정) | 유지 | primaryNpcId 불일치 안전망 |
| dialogue-generator | 제거 | LLM이 직접 대사 생성 |
| dialogue_slot 파싱 | 제거 | JSON 모드 없음 |

**경량 후처리 함수**:
```typescript
function applyLightPostProcess(narrative: string, npcStates, primaryNpcId): string {
  // Step C: 실명 세이프가드
  narrative = sanitizeNpcNamesForTurn(narrative, npcStates, ...);
  // Step F: NPC 불일치 교정
  narrative = correctNpcMismatch(narrative, primaryNpcId, ...);
  return narrative;
}
```

### Phase 4: StreamClassifier 강화 (서버)

**목표**: 따옴표 대사를 정확히 감지하여 dialogue 이벤트 생성

**변경 파일**:
| 파일 | 변경 |
|------|------|
| `server/src/llm/stream-classifier.service.ts` | 안전망 필터 추가 (잔여 태그 제거). NPC 식별 정확도 개선 |

**안전망 필터 (프롬프트 위반 시)**:
```typescript
// classifySentence 내부 — 혹시 모를 시스템 태그 필터
if (/^\[(?:CHOICES|THREAD|MEMORY|\/CHOICES|\/THREAD|\/MEMORY)\]/.test(sentence)) {
  return []; // 시스템 태그 → 무시
}
```

### Phase 5: 클라이언트 정리

**목표**: StreamingBlock 내레이터 박스 내 렌더링 안정화 + 선택지 로딩 표시

**변경 파일**:
| 파일 | 변경 |
|------|------|
| `client/src/components/narrative/StreamingBlock.tsx` | cleanStreamText 간소화 (안전망만). dialogue 세그먼트 말풍선 타이핑 |
| `client/src/store/game-store.ts` | `choices_loading` 이벤트 처리. done 후 교체 로직 정리 |
| `client/src/components/narrative/StoryBlock.tsx` | 선택지 로딩 인디케이터 추가 |
| `client/src/lib/llm-stream.ts` | `choices_loading` 이벤트 핸들러 추가 |

**선택지 로딩 UI**:
```
서술 타이핑 완료 →
  done 미수신 → "..." 점 애니메이션 (선택지 영역)
  done 수신 → 선택지 표시
```

**done 후 교체 흐름 (정리)**:
```
done 수신 → streamDoneNarrative 저장
StreamingBlock 타이핑 완료 → finalizeStreaming()
  → 최종 서술 교체 (typed=true, 재타이핑 없음)
  → 선택지 표시 (flushPending)
```

### Phase 6: 테스트 + 검증

**단위 테스트**:
- StreamClassifier: 따옴표 대사 감지 + NPC 식별 테스트 추가
- 경량 후처리: Step C, F만 적용되는지 확인

**통합 테스트**:
- 5턴 플레이테스트: 시스템 태그 노출 0건 확인
- E2E: 스트리밍 타이핑 + 말풍선 + 선택지 순서 확인
- TTFB 측정: 이전(2.2초)과 비교

---

## 7.1 구현 우선순위

| 순서 | Phase | 예상 작업량 | 의존성 |
|------|-------|----------|--------|
| 1 | Phase 1: 프롬프트 분리 | 중 | 없음 |
| 2 | Phase 3: 후처리 경량화 | 소 | Phase 1 |
| 3 | Phase 4: StreamClassifier 강화 | 소 | Phase 1 |
| 4 | Phase 2: Worker Track 분리 | 대 | Phase 1, 3 |
| 5 | Phase 5: 클라이언트 정리 | 중 | Phase 2 |
| 6 | Phase 6: 테스트 | 중 | Phase 5 |

---

## 8. 예상 효과

| 지표 | 현재 | Dual-Track 후 |
|------|------|-------------|
| 스트리밍 중 태그 노출 | 있음 | 없음 |
| 스트리밍 중 마커 노출 | 있음 | 없음 |
| 대사 말풍선 실시간 | 불가 | 가능 (따옴표 감지) |
| 선택지 표시 대기 | 후처리 완료까지 | Track 2 병렬 (더 빠름) |
| 후처리 복잡도 | 6단계 (A~F) | 2~3단계 (C, F만) |
| TTFB | 2.2초 | 2.2초 (동일) |

---

## 9. 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| LLM이 여전히 태그를 생성 | 태그 노출 | StreamClassifier에서 태그 필터링 안전망 |
| LLM이 따옴표 없이 대사 | 말풍선 미변환 | 후처리에서 Step A(마커 삽입) fallback |
| NPC 식별 실패 | 잘못된 말풍선 | primaryNpcId fallback |
| Track 2 지연 | 선택지 늦게 표시 | 타이핑 끝나면 로딩 표시 후 대기 |
