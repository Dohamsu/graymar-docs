# 35. LLM 스트리밍

> **목표**: OpenRouter `stream: true` + Dual-Track 파이프라인으로 체감 응답 속도 개선과 깨끗한 실시간 타이핑
> **작성일**: 2026-04-16 (최초 설계) / 2026-04-17 (후속 수정)
> **상태**: ✅ 서버+클라이언트 구현됨 / Dual-Track 재설계는 Phase 별 구현 중

---

## 1. 스트리밍 설계

### 1.1 폴링 → 스트리밍 전환 개요

**기존 (폴링)**: Resolve 즉시 응답 후 클라이언트가 2초 간격으로 LLM 상태 폴링. TTFB 3~15초, 폴링 지연 +최대 2초.

**변경 (스트리밍)**: LLM Worker가 OpenRouter `stream: true`로 토큰을 받아 SSE로 브로드캐스트. 클라이언트는 토큰 도착 즉시 타이핑.

개선 효과:
- TTFB: 0.5~2초 (첫 토큰 즉시 표시)
- 전체 완료 시간은 동일하지만 체감 대기 대폭 감소
- 네트워크 요청 수 2~8회 폴링 → 1회 SSE

### 1.2 핵심 설계 결정

**2-Phase 렌더링** — 후처리와의 충돌을 피하기 위해:
- Phase 1 (스트리밍 중): 원문 실시간 표시. @마커는 불완전할 수 있어 임시 숨김.
- Phase 2 (스트리밍 완료 후): Step A~F 후처리 → 최종본으로 교체.

**전달 방식**: SSE. 단방향 통신으로 충분, 파티 시스템과 패턴 통일, WebSocket 대비 구현/유지 비용 낮음.

### 1.3 엔드포인트

```
GET /v1/runs/:runId/turns/:turnNo/stream?token=JWT

Response: text/event-stream

event: token
data: {"text": "짙은 안개가"}

event: done
data: {"narrative": "전체 후처리 완료 서술", "choices": [...]}

event: error
data: {"message": "LLM 호출 실패"}
```

### 1.4 서버 구성요소

**OpenAI Provider — `callStream()`**
```typescript
async *callStream(request, model): AsyncGenerator<string> {
  const stream = await client.chat.completions.create({
    model, messages, max_tokens, temperature,
    stream: true,
    ...openRouterParams,
  });
  for await (const chunk of stream) {
    const delta = chunk.choices[0]?.delta?.content;
    if (delta) yield delta;
  }
}
```

**LLM Worker — 스트리밍 + 후처리**
```typescript
const chunks: string[] = [];
for await (const token of this.llmCaller.callStream({ messages, maxTokens, ... })) {
  chunks.push(token);
  this.streamBroker.emit(runId, turnNo, 'token', token);
}
let narrative = chunks.join('');
// Step A~F 후처리
// DB UPDATE
this.streamBroker.emit(runId, turnNo, 'done', { narrative, choices });
```

**Stream Broker (인메모리)**
```typescript
@Injectable()
class LlmStreamBroker {
  private channels = new Map<string, Subject<StreamEvent>>();
  getChannel(runId: string, turnNo: number): Observable<StreamEvent> { /* ... */ }
  emit(runId: string, turnNo: number, type: string, data: unknown) {
    const key = `${runId}:${turnNo}`;
    this.channels.get(key)?.next({ type, data });
    if (type === 'done' || type === 'error') {
      this.channels.get(key)?.complete();
      this.channels.delete(key);
    }
  }
}
```

**Turns Controller — SSE 엔드포인트**
```typescript
@Get(':runId/turns/:turnNo/stream')
@Sse()
streamTurn(@Param('runId') runId, @Param('turnNo') turnNo, @Query('token') token) {
  // JWT 검증
  // 이미 DONE이면 즉시 완성본 전송
  // PENDING/RUNNING이면 StreamBroker 구독
  return this.streamBroker.getChannel(runId, turnNo).pipe(
    map(event => ({ data: JSON.stringify(event) })),
  );
}
```

### 1.5 클라이언트 구성요소

**game-store.ts — SSE + 폴링 fallback**
```typescript
const es = new EventSource(`/v1/runs/${runId}/turns/${turnNo}/stream?token=${jwt}`);
es.addEventListener('token', (e) => {
  const { text } = JSON.parse(e.data);
  feedStreamToken(text);
});
es.addEventListener('done', (e) => {
  const { narrative, choices } = JSON.parse(e.data);
  finalizeNarrative(narrative, choices);
  es.close();
});
es.onerror = () => { es.close(); fallbackToPolling(runId, turnNo); };
```

**StreamParser — 실시간 점진 파싱 엔진**

스트리밍 중 토큰을 실시간 분석하여 서술은 즉시 표시하고 NPC 대사는 말풍선으로 변환하는 상태 머신.

```
NARRATION → (@[ 감지) → MARKER_OPEN → (] + 큰따옴표) → DIALOGUE_OPEN
  → (닫는 큰따옴표) → 말풍선 렌더링 → NARRATION
```

```typescript
enum StreamState { NARRATION, MARKER_OPEN, DIALOGUE_OPEN }

class StreamParser {
  private state = StreamState.NARRATION;
  private markerBuffer = '';
  private dialogueBuffer = '';
  private markerName = '';
  private markerImage = '';

  feed(token: string): StreamOutput[] {
    const outputs: StreamOutput[] = [];
    for (const char of token) {
      switch (this.state) {
        case StreamState.NARRATION:
          if (this.checkMarkerStart(char)) {
            this.state = StreamState.MARKER_OPEN;
            this.markerBuffer = '@[';
          } else outputs.push({ type: 'narration', text: char });
          break;
        case StreamState.MARKER_OPEN:
          this.markerBuffer += char;
          if (char === ']') this.parseMarker(this.markerBuffer);
          if (this.isQuoteOpen(char) && this.markerBuffer.includes(']')) {
            this.state = StreamState.DIALOGUE_OPEN;
            this.dialogueBuffer = '';
          }
          break;
        case StreamState.DIALOGUE_OPEN:
          if (this.isQuoteClose(char)) {
            outputs.push({
              type: 'dialogue',
              npcName: this.markerName,
              npcImage: this.markerImage,
              text: this.dialogueBuffer,
            });
            this.reset();
          } else this.dialogueBuffer += char;
          break;
      }
    }
    return outputs;
  }
}
```

**StoryBlock 통합**: 스트리밍 중에는 StreamParser 출력(narration span / DialogueBubble)을 렌더, done 이벤트 후 후처리 완료본으로 교체.

**토큰 분산 표시**: 한 번에 여러 글자가 도착하면 20ms 간격(`TOKEN_DISPLAY_INTERVAL_MS`)으로 분산.

**엣지 케이스**
| 상황 | 처리 |
|------|------|
| @마커 없이 큰따옴표 대사 | NARRATION으로 표시 (따옴표 포함) |
| @마커 후 대사 없이 서술 계속 | 마커 버퍼 폐기, NARRATION 복귀 |
| 불완전한 @마커 (스트림 끊김) | done 이벤트의 후처리본으로 교체 |
| 한 토큰에 마커+대사 전체 포함 | StreamParser가 문자 단위 순차 처리 |
| 유니코드 따옴표 | isQuoteOpen/Close에서 모두 처리 |
| 대사 내 이스케이프 따옴표 | 연속 따옴표("") 감지 후 무시 |

### 1.6 후처리 타이밍

Step A~F 모두 **전체 완성 후 한 번에 적용** — 스트리밍 중에는 원문 표시.

### 1.7 Fallback

SSE 연결 실패 시 기존 폴링 방식으로 자동 전환 (`fallbackToPolling`).

### 1.8 리스크 & 완화

| 리스크 | 완화 |
|--------|------|
| SSE 연결 끊김 | 폴링 fallback |
| Phase 1→2 전환 깜빡임 | 페이드 트랜지션 |
| 스트리밍 중 NPC 이름 노출 | @마커 실시간 감지 + 숨김 |
| PM2 클러스터 환경 | sticky session 또는 Redis pub/sub |
| OpenRouter 스트리밍 미지원 모델 | non-stream fallback |

### 1.9 구현 현황 & 제약

| 단계 | 상태 |
|------|------|
| OpenAI Provider generateStream() | ✅ |
| LlmStreamBrokerService (인메모리 SSE) | ✅ |
| LLM Worker 스트리밍 모드 + done 이벤트 | ✅ |
| Turns Controller SSE 엔드포인트 | ✅ |
| StreamParser 문장 단위 버퍼링 | ✅ |
| game-store SSE 연결 + 폴링 fallback | ✅ |
| StreamingBlock 실시간 렌더링 | ✅ |
| SKIPPED/DONE 턴 즉시 폴링 처리 | ✅ |

제약: `LLM_JSON_MODE=true`일 때 스트리밍 중 표시 차단 (JSON 원문 노출 방지). 권장: `LLM_JSON_MODE=false` + 스트리밍 활성화.

TTFB 측정: Gemma 4 26B MoE + stream:true → **2.2초**.

---

## 2. Dual-Track 구현 계획

> **목표**: 서술+대사 LLM(스트리밍)과 계산 LLM(백그라운드)을 분리하여 깨끗한 실시간 타이핑 + 시스템 태그 미노출

### 2.1 현재 문제

LLM이 서술+대사+시스템태그([CHOICES], [THREAD], [MEMORY])+@마커를 한 번에 생성 → 스트리밍 시 후처리 전 원문이 노출:
- 시스템 태그가 화면에 보임
- 대사가 말풍선이 아닌 일반 텍스트
- 후처리 완료 후 전체 교체 → 타이핑 중단/깜빡임

### 2.2 Dual-Track 아키텍처

```
턴 제출 (Resolve 즉시 응답)
    ↓
Track 1: 서술 LLM (스트리밍)
  → 순수 서술 + 대사(따옴표)만 생성 / 시스템 태그 없음
  → SSE로 토큰 실시간 전송
  → 클라이언트: 타이핑 + 따옴표 대사 → 말풍선 변환
    ↓
Track 1 완료 → 서술 후처리 (경량)
    ↓
Track 2: 계산 LLM (서술 결과 기반, 순차)
  → 선택지 생성 (NanoEventDirector, narrativeText 포함)
  → 메모리/요약 추출 (FactExtractor, MidSummary)
  → 클라이언트: 짧은 로딩 인디케이터
    ↓
Track 2 완료 → done (최종 서술 + 선택지)
```

**핵심**: Track 2는 서술을 입력으로 사용 → Track 1 완료 후 순차 실행. 유저가 타이핑을 읽는 시간으로 체감 대기 최소.

### 2.3 Track 1 — 서술 LLM

**프롬프트 변경**: `[CHOICES]`, `[THREAD]`, `[MEMORY]`, `@NPC_ID` 생성 지시 제거. 요구사항:
- 환경 묘사 + NPC 행동/반응 + 대사(따옴표)
- NPC 대사는 반드시 큰따옴표로 감싸기
- 대사 직전 NPC 호칭 언급 (화자 식별)
- 시스템 태그·마커 일체 생성 금지

**StreamClassifier 흐름**:
- 일반 텍스트 → `narration` 이벤트 (문장 단위)
- 큰따옴표 감지 → 버퍼링 → 닫는 따옴표 → NPC 식별 → `dialogue` 이벤트

**NPC 식별 우선순위**:
1. 따옴표 직전 60자에서 이름/호칭 매칭
2. 발화동사 패턴 ("~가 말했다", "~이 답했다")
3. 대명사 ("그가/그녀가") → 직전 매칭 NPC
4. fallback → `primaryNpcId`

**경량 후처리** (Track 1 완료 후):
- 유지: Step C (실명 가드), Step F (NPC 불일치 교정), Step D (선택적)
- 제거: Step A/B (마커 삽입·변환 불필요), Step E (NPC이름 프리픽스 — 프롬프트에서 방지)

### 2.4 Track 2 — 계산 LLM

| 항목 | 담당 |
|------|------|
| 선택지 생성 | NanoEventDirector (nano LLM, narrativeText 입력) |
| 메모리 추출 | FactExtractor (nano LLM) |
| 요약 생성 | MidSummary |
| NPC 감정 업데이트 | 서버 로직 (LLM 불필요) |

실행 시점: Track 1 완료 후 순차. nano LLM × 2~3회로 보통 1~2초 이내 완료. 클라이언트에는 `choices_loading` 이벤트로 진행 알림.

`done` 이벤트:
```typescript
{
  type: 'done',
  narrative: '후처리 완료된 최종 서술',
  choices: [{ id: 'nano_1', label: '...', affordance: 'TALK' }, ...],
}
```

### 2.5 Phase별 구현 로드맵

#### Phase 1 — 프롬프트 분리 (서버)

| 파일 | 변경 |
|------|------|
| `server/src/llm/prompts/system-prompts.ts` | [CHOICES]/[THREAD]/[MEMORY]/@마커 지시 제거. "따옴표 대사 + NPC 호칭" 지시 추가 |
| `server/src/llm/prompts/prompt-builder.service.ts` | 시스템 태그 관련 블록 제거. 대사 형식 지시 추가 |

검증: dry-run 프롬프트 추출 + 5턴 플레이테스트로 LLM 출력에 시스템 태그/마커 없음 확인.

#### Phase 2 — LLM Worker Track 분리 (서버)

| 파일 | 변경 |
|------|------|
| `server/src/llm/llm-worker.service.ts` | Track 1 완료 후 Track 2 시작. narrativeText 전달. done에 choices 포함 |
| `server/src/llm/nano-event-director.service.ts` | NanoEventContext에 `narrativeText` 필드 추가 |
| `server/src/llm/llm-stream-broker.service.ts` | `choices_loading` 이벤트 타입 추가 |

```typescript
// Track 1: 스트리밍
for await (const chunk of this.llmCaller.callStream(request)) {
  streamBroker.emit(runId, turnNo, segEvt.type, segEvt);
}
// Track 1 완료 → 경량 후처리
narrative = applyLightPostProcess(rawNarrative);

// Track 2 시작 알림
streamBroker.emit(runId, turnNo, 'choices_loading', {});

// Track 2: 선택지 + 메모리 + 요약
const nanoResult = await nanoEventDirector.generate({ ...nanoCtx, narrativeText: narrative });
const facts = await factExtractor.extract(narrative, ...);
const summary = await midSummary.generate(narrative, ...);

streamBroker.emit(runId, turnNo, 'done', {
  narrative,
  choices: nanoResult?.choices ?? serverDefaultChoices,
});
```

#### Phase 3 — 후처리 경량화 (서버)

| 단계 | 유지/제거 | 이유 |
|------|----------|------|
| Step A (마커 삽입) | 제거 | 마커 없는 깨끗한 텍스트 |
| Step B (마커 변환) | 제거 | @마커 없음 |
| Step C (실명 가드) | 유지 | introduced=false 노출 방지 |
| Step D (발화 트리밍) | 제거 | @마커 기반이라 불필요 |
| Step E (NPC이름: 제거) | 제거 | 프롬프트에서 방지 |
| Step F (NPC 교정) | 유지 | primaryNpcId 안전망 |
| dialogue-generator | 제거 | LLM 직접 대사 생성 |
| dialogue_slot 파싱 | 제거 | JSON 모드 없음 |

```typescript
function applyLightPostProcess(narrative: string, npcStates, primaryNpcId): string {
  narrative = sanitizeNpcNamesForTurn(narrative, npcStates, ...); // Step C
  narrative = correctNpcMismatch(narrative, primaryNpcId, ...);   // Step F
  return narrative;
}
```

#### Phase 4 — StreamClassifier 강화 (서버)

| 파일 | 변경 |
|------|------|
| `server/src/llm/stream-classifier.service.ts` | 안전망 필터 추가, NPC 식별 정확도 개선 |

```typescript
// 시스템 태그 안전망 (프롬프트 위반 시)
if (/^\[(?:CHOICES|THREAD|MEMORY|\/CHOICES|\/THREAD|\/MEMORY)\]/.test(sentence)) {
  return [];
}
```

#### Phase 5 — 클라이언트 정리

| 파일 | 변경 |
|------|------|
| `client/src/components/narrative/StreamingBlock.tsx` | cleanStreamText 간소화. dialogue 세그먼트 말풍선 타이핑 |
| `client/src/store/game-store.ts` | `choices_loading` 이벤트 처리. done 후 교체 로직 정리 |
| `client/src/components/narrative/StoryBlock.tsx` | 선택지 로딩 인디케이터 추가 |
| `client/src/lib/llm-stream.ts` | `choices_loading` 핸들러 추가 |

타이밍 흐름:
```
서술 타이핑 중 → (유저가 읽는 시간)
서술 타이핑 완료 →
  done 수신됨 → 즉시 선택지 표시
  done 미수신 → "..." 점 애니메이션 → 완료 시 선택지 표시
done 수신 → streamDoneNarrative 저장
StreamingBlock 타이핑 완료 → finalizeStreaming() → 최종 서술 교체(typed=true) + flushPending
```

#### Phase 6 — 테스트 + 검증

- 단위: StreamClassifier 따옴표 대사 + NPC 식별. 경량 후처리 Step C/F 적용 확인.
- 통합: 5턴 플레이테스트에서 시스템 태그 노출 0건.
- E2E: 스트리밍 타이핑 + 말풍선 + 선택지 순서.
- TTFB: 이전(2.2초)과 비교.

### 2.6 구현 우선순위

| 순서 | Phase | 작업량 | 의존성 |
|------|-------|--------|--------|
| 1 | Phase 1 프롬프트 분리 | 중 | 없음 |
| 2 | Phase 3 후처리 경량화 | 소 | 1 |
| 3 | Phase 4 StreamClassifier | 소 | 1 |
| 4 | Phase 2 Worker Track 분리 | 대 | 1, 3 |
| 5 | Phase 5 클라이언트 정리 | 중 | 2 |
| 6 | Phase 6 테스트 | 중 | 5 |

### 2.7 예상 효과 & 리스크

| 지표 | 현재 | Dual-Track 후 |
|------|------|-------------|
| 스트리밍 중 태그 노출 | 있음 | 없음 |
| 스트리밍 중 마커 노출 | 있음 | 없음 |
| 대사 말풍선 실시간 | 불가 | 가능 (따옴표 감지) |
| 선택지 표시 대기 | 후처리 완료까지 | Track 2 병렬 (더 빠름) |
| 후처리 복잡도 | 6단계 | 2~3단계 |
| TTFB | 2.2초 | 2.2초 |

| 리스크 | 완화 |
|--------|------|
| LLM이 여전히 태그 생성 | StreamClassifier 안전망 |
| LLM이 따옴표 없이 대사 | Step A(마커 삽입) fallback |
| NPC 식별 실패 | primaryNpcId fallback |
| Track 2 지연 | 타이핑 후 로딩 표시 |

---

## 3. 후속 수정 (2026-04-17)

초기 구현 이후 플레이테스트·버그 리포트로 확인된 세 가지 렌더 이슈를 잡고 수집 데이터를 확장함.

### A. StreamTyper onComplete 2회 호출로 내레이터 텍스트 사라짐 (버그 d8b9de24 / 8d469994)

**증상**: 타이핑이 끝나는 순간 내레이터 박스의 본문이 통째로 빈 문자열로 교체됨.

**원인**: `client/src/components/narrative/StoryBlock.tsx`의 `StreamTyper` useEffect 가 `typedLength >= buffer.length && isDone` 조건을 재평가될 때마다 `onComplete()` 를 호출할 수 있었음. 1회차가 `streamTextBuffer=''` 로 초기화한 뒤 같은 tick에 2회차가 실행되면, 2회차는 store에서 빈 버퍼를 읽어 `messages[msg].text = ''` 로 덮어씀.

**수정**: 양방향 멱등성 가드.
- 트리거: `completedRef` once-guard 로 `onComplete` 1회만 호출.
- 핸들러: 진입 시 `!store.isStreaming || finalText.length === 0` 이면 early return.

### B. 타이핑 중 / 완료 후 스타일 점프 (버그 c3f880f3)

**증상**: 타이핑 중에는 기본 폰트/line-height/크기로 보이다 완료 순간 `font-narrative` 로 급전환.

**원인**: 완료 경로는 `<div className="font-narrative leading-[1.75]" style={fontSize}>` 래퍼를 씌우는 반면, `loading && isStreaming` 경로의 `StreamTyper` 는 래퍼 없이 직계 자식이었음. 또한 `StreamTyper`/`TypewriterText` 내부의 narration 렌더는 인라인 `<span>` + `leading-relaxed` 인 반면 `NarratorContent` 는 `\n` split + `block` 래핑 + 빈 줄 `h-3` 간격을 사용.

**수정**:
- `renderNarrationLines()` 헬퍼로 `NarratorContent` 와 동일한 block 기반 줄 렌더 통일.
- `StreamTyper` 호출부를 완료 경로와 같은 `<div font-narrative leading-[1.75]` + `fontSize>` 로 감쌈.

### C. 문장별 줄바꿈 (버그 c3f880f3)

**증상**: 스트리밍 경로의 서술이 모든 문장마다 한 줄씩 끊겨서 렌더됨.

**원인**: `client/src/store/game-store.ts` 의 스트림 버퍼 축적이 매 flush마다 `analyzedBuffer + '\n' + analyzed` 로 이어붙임. 서버 `stream-classifier` 가 문장 단위로 이벤트를 emit 하므로 최종 버퍼가 문장별 개행 덩어리가 됨.

**수정**:
- `analyzeText()` 재작성: 입력을 빈 줄 기준 문단으로 분할, 각 문단 내 narration 라인은 공백으로 병합해 하나의 덩어리로 합치고 대사(`@[...] "..."`) 라인만 독립 줄 유지.
- `appendAnalyzed()` 헬퍼: 이전 버퍼 끝이 개행이면 그대로, 아니면 공백으로 연결 — extract 경계에서 끊긴 narration이 다음 조각과 자연스럽게 이어짐.

### D. 대사 내부 raw 마커 잔해 (버그 fc14ed2b)

**증상**: DialogueBubble 안에 `[로넨|/npc-portraits/ronen.webp] 정말 감사합니다...` 가 그대로 노출.

**원인**: LLM 이 `@[로넨|URL] "@[로넨|URL] 대사"` 형태 이중 마커를 생성 → 외부 마커는 서버 B-2.5 regex 가 치환하지만 큰따옴표 내부 잔해는 뒤에 `"` 가 없어 어느 regex에도 매칭되지 않고, 이후 어느 단계에서 `@` 프리픽스만 떨어져 raw 대괄호 마커가 대사 텍스트의 일부로 살아남음.

**수정**:
- 서버 `llm-worker.service.ts` 에 5.10.5 단계 추가: `deduplicateAliases` 직후 큰따옴표 쌍 내부에서 `@?[이름|URL]` / `@[이름]` 잔해 제거.
- 클라 `cleanResidualMarkers` 에 `(^|[^@])\[[^\]|]+\|\/npc-portraits\/[^\]]+\]` 방어 정규식 추가 (정상 `@` 마커 보호, `npc-portraits` 경로 포함 잔해만 제거).

### E. 버그 리포트 수집 데이터 확장

분석 시 추측해야 했던 맥락을 데이터로 남기기 위해 `bug_reports` 컬럼 3개 추가.

- `client_snapshot` (jsonb): phase, currentNodeType/Index, currentTurnNo, locationId, HUD, worldState 요약, 스트리밍 상태, pending 카운트, lastMessages 요약, characterInfo, llmStats, llmFailure, DOM 요약(choice-btn / dialogue-bubble 카운트, viewport, scrollY)
- `network_log` (jsonb): 최근 100개 API 호출 타임라인 — method/path/status/latencyMs/ok/errorCode. `api-client.ts request()` 래퍼가 자동 기록.
- `client_version` (text): `NEXT_PUBLIC_CLIENT_VERSION` 을 같이 저장해 서버/클라 배포 불일치 여부를 즉시 판별.

클라 `BugReportModal.tsx` 는 `serializeMessage`(메시지 전체 필드 직렬화), `collectClientSnapshot`, `collectDomSummary`, `getNetworkLog`, `clientVersion` 을 한 번에 전송한다. `DialogueBubble` 에는 `data-dialogue-bubble` 속성을 추가해 DOM 스캔이 가능하도록 했다.
