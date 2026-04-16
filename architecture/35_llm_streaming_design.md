# 35. LLM 스트리밍 설계

> **목표**: OpenRouter stream: true 활성화 → 체감 응답 속도 개선 + 실시간 타이핑
> **작성일**: 2026-04-16
> **상태**: 설계 중

---

## 1. 현재 구조 (폴링 방식)

```
[턴 제출]
  Client → POST /runs/:runId/turns → Server
  Server → Resolve 즉시 응답 (50ms)
  Client ← { turnNo, resolveOutcome, choices }
  
[LLM 서술 대기]
  Client: 2초 폴링 → GET /runs/:runId/turns/:turnNo
  Server: LLM Worker가 비동기 처리 중
    → OpenRouter API 호출 (stream: false, 3~15초)
    → 전체 서술 수신
    → 후처리 6단계 (Step A~F)
    → DB UPDATE (llmStatus='DONE', llmOutput=서술)
  Client: 폴링에서 DONE 감지 → 전체 서술 수신
  Client: 세그먼트 분할 → 타이핑 애니메이션
```

**문제점**:
- TTFB(첫 토큰) 대기: 3~15초 (모델/프로바이더에 따라)
- 폴링 지연: 최대 +2초 (폴링 주기)
- 유저 체감: 선택 후 5~17초 대기 → 타이핑 시작

---

## 2. 목표 구조 (스트리밍 방식)

```
[턴 제출]
  동일 — Resolve 즉시 응답

[LLM 서술 스트리밍]
  Server: LLM Worker → OpenRouter API (stream: true)
    → 토큰이 도착하는 대로 SSE로 전송
  Client: SSE 연결로 실시간 토큰 수신
    → 토큰 도착 즉시 타이핑 (파싱 없이 원문)
    → 전체 완성 후 후처리 + 최종 렌더링
```

**개선 효과**:
- TTFB: 0.5~2초 (첫 토큰 즉시 표시)
- 타이핑이 실시간으로 진행되어 "대기" 느낌 제거
- 전체 완료 시간은 동일하지만 체감 속도 대폭 개선

---

## 3. 핵심 설계 결정

### 3.1 스트리밍 vs 후처리 충돌 해결

**문제**: 현재 후처리(Step A~F)는 전체 서술이 완성된 후 실행됨. 스트리밍 중에는 불완전한 텍스트만 있어서 후처리 불가.

**해결 방안: 2-Phase 렌더링**

```
Phase 1 (스트리밍 중): 원문 실시간 표시
  → 토큰 도착 → 즉시 화면에 표시
  → @마커는 불완전할 수 있음 → 임시 숨김 처리
  → NPC 이름/초상화 없이 텍스트만 타이핑

Phase 2 (스트리밍 완료 후): 후처리 + 최종 렌더링
  → 전체 서술에 Step A~F 적용
  → @마커 파싱 → NPC 말풍선 변환
  → Phase 1의 원문 → Phase 2의 최종본으로 부드럽게 교체
```

### 3.2 클라이언트 전달 방식

**선택지**: SSE (Server-Sent Events)

이유:
- 이미 파티 시스템에서 SSE 패턴 사용 가능 (party-stream)
- 단방향 통신으로 충분 (서버→클라이언트)
- HTTP/2 환경에서 효율적
- WebSocket보다 구현/유지 비용 낮음

### 3.3 엔드포인트 설계

```
GET /v1/runs/:runId/turns/:turnNo/stream?token=JWT

Response: text/event-stream

event: token
data: {"text": "짙은 안개가"}

event: token  
data: {"text": " 항만을 감싸고"}

event: done
data: {"narrative": "전체 후처리 완료 서술", "choices": [...]}

event: error
data: {"message": "LLM 호출 실패"}
```

---

## 4. 서버 변경

### 4.1 OpenAI Provider — stream: true

**파일**: `server/src/llm/providers/openai.provider.ts`

```typescript
// 기존: 전체 완성 대기
const completion = await client.chat.completions.create({
  model, messages, max_tokens, temperature,
  ...openRouterParams,
});

// 변경: 스트리밍
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

### 4.2 LLM Worker — 스트리밍 지원

**파일**: `server/src/llm/llm-worker.service.ts`

```typescript
// 기존: 전체 완성 후 후처리
const result = await this.llmCaller.call({ messages, maxTokens, ... });
let narrative = result.response.text;
// ... Step A~F 후처리
// DB UPDATE

// 변경: 스트리밍 + 토큰 브로드캐스트 + 완료 후 후처리
const chunks: string[] = [];
for await (const token of this.llmCaller.callStream({ messages, maxTokens, ... })) {
  chunks.push(token);
  this.streamBroker.emit(runId, turnNo, 'token', token);
}
let narrative = chunks.join('');
// Step A~F 후처리 (동일)
// DB UPDATE
this.streamBroker.emit(runId, turnNo, 'done', { narrative, choices });
```

### 4.3 Stream Broker (신규)

턴별 SSE 연결을 관리하는 인메모리 브로커:

```typescript
@Injectable()
class LlmStreamBroker {
  private channels = new Map<string, Subject<StreamEvent>>();
  
  getChannel(runId: string, turnNo: number): Observable<StreamEvent> {
    const key = `${runId}:${turnNo}`;
    if (!this.channels.has(key)) {
      this.channels.set(key, new Subject());
    }
    return this.channels.get(key)!.asObservable();
  }
  
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

### 4.4 Turns Controller — SSE 엔드포인트

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

---

## 5. 클라이언트 변경

### 5.1 game-store.ts — SSE 연결 + 폴링 fallback

```typescript
// SSE 연결
const es = new EventSource(`/v1/runs/${runId}/turns/${turnNo}/stream?token=${jwt}`);

es.addEventListener('token', (e) => {
  const { text } = JSON.parse(e.data);
  feedStreamToken(text);  // StreamParser에 토큰 전달
});

es.addEventListener('done', (e) => {
  const { narrative, choices } = JSON.parse(e.data);
  finalizeNarrative(narrative, choices);  // 후처리 완료본으로 최종 교체
  es.close();
});

es.onerror = () => {
  es.close();
  fallbackToPolling(runId, turnNo);  // 기존 2초 폴링
};
```

### 5.2 StreamParser — 실시간 점진 파싱 엔진 (신규)

스트리밍 중 토큰을 실시간 분석하여, 서술은 즉시 표시하고 NPC 대사는 말풍선으로 변환하는 상태 머신.

```
                    ┌──────────────────────┐
                    │   NARRATION 모드     │
                    │  (텍스트 즉시 표시)    │
                    └─────────┬────────────┘
                              │ "@[" 감지
                              ▼
                    ┌──────────────────────┐
                    │   MARKER 버퍼링      │
                    │  (화면에 숨김)        │
                    └─────────┬────────────┘
                              │ "]" + 큰따옴표 감지
                              ▼
                    ┌──────────────────────┐
                    │  DIALOGUE 버퍼링     │
                    │  (대사 누적 중)       │
                    └─────────┬────────────┘
                              │ 닫는 큰따옴표 감지
                              ▼
                    ┌──────────────────────┐
                    │  말풍선 렌더링!       │
                    │  (NPC이름+초상화+대사) │
                    └─────────┬────────────┘
                              │ 다음 토큰
                              ▼
                        NARRATION 모드 복귀
```

#### StreamParser 상태 머신

```typescript
enum StreamState {
  NARRATION,      // 일반 서술 → 즉시 표시
  MARKER_OPEN,    // @[ 감지 → 버퍼링 중 (마커 이름+URL 수집)
  DIALOGUE_OPEN,  // 마커 완성 + 큰따옴표 열림 → 대사 버퍼링
}

class StreamParser {
  private state = StreamState.NARRATION;
  private markerBuffer = '';      // @[이름|URL] 누적
  private dialogueBuffer = '';    // 대사 텍스트 누적
  private markerName = '';        // 파싱된 NPC 이름
  private markerImage = '';       // 파싱된 초상화 URL
  
  feed(token: string): StreamOutput[] {
    const outputs: StreamOutput[] = [];
    
    for (const char of token) {
      switch (this.state) {
        case StreamState.NARRATION:
          if (this.checkMarkerStart(char)) {
            this.state = StreamState.MARKER_OPEN;
            this.markerBuffer = '@[';
          } else {
            outputs.push({ type: 'narration', text: char });
          }
          break;
          
        case StreamState.MARKER_OPEN:
          this.markerBuffer += char;
          if (char === ']') {
            // 마커 완성 — 이름/URL 파싱
            this.parseMarker(this.markerBuffer);
            // 다음 큰따옴표 대기
          }
          if (this.isQuoteOpen(char) && this.markerBuffer.includes(']')) {
            this.state = StreamState.DIALOGUE_OPEN;
            this.dialogueBuffer = '';
          }
          break;
          
        case StreamState.DIALOGUE_OPEN:
          if (this.isQuoteClose(char)) {
            // 대사 완성 → 말풍선 렌더링!
            outputs.push({
              type: 'dialogue',
              npcName: this.markerName,
              npcImage: this.markerImage,
              text: this.dialogueBuffer,
            });
            this.reset();
          } else {
            this.dialogueBuffer += char;
          }
          break;
      }
    }
    return outputs;
  }
}
```

#### 실시간 처리 예시

```
토큰 수신                        화면 표시
─────────────────────────────────────────────
"짙은 안개가 "               →  짙은 안개가 ▌ (즉시 타이핑)
"항만을 감싸고"              →  항만을 감싸고▌
"\n@["                       →  (버퍼링 시작, 숨김)
"날카로운 눈매의 회계사"      →  (버퍼 누적 중...)
"|/npc-portraits/edric.png]" →  (마커 완성, 큰따옴표 대기)
" \""                        →  (대사 시작)
"이 서류를 확인"             →  (대사 버퍼 누적...)
"하시오.\""                  →  💬 [회계사 초상화] "이 서류를 확인하시오." (말풍선!)
"\n그는 고개를 "             →  그는 고개를 ▌ (서술 재개)
"돌렸다."                    →  돌렸다.▌
```

### 5.3 StoryBlock.tsx — StreamParser 통합

```typescript
// 스트리밍 중: StreamParser 출력을 렌더링
function StreamingNarrative({ outputs }: { outputs: StreamOutput[] }) {
  return (
    <>
      {outputs.map((out, i) => {
        if (out.type === 'narration') {
          return <span key={i} className="narration-text">{out.text}</span>;
        }
        if (out.type === 'dialogue') {
          return (
            <DialogueBubble
              key={i}
              npcName={out.npcName}
              npcImageUrl={out.npcImage}
              text={out.text}
            />
          );
        }
      })}
    </>
  );
}

// done 이벤트 후: 기존 세그먼트 렌더링으로 교체
// Phase 2에서는 후처리 완료된 서술을 사용
// StreamParser 결과 → 최종본으로 부드럽게 교체 (이미 같은 내용이므로 시각적 변화 최소)
```

### 5.4 타이핑 속도 제어

```typescript
// 스트리밍 중: LLM 토큰 속도가 자연스러운 "타이핑"
// 토큰이 한 번에 여러 글자 오면 20ms 간격으로 분산 표시
const TOKEN_DISPLAY_INTERVAL_MS = 20;

function smoothTokenDisplay(text: string, callback: (char: string) => void) {
  let i = 0;
  const timer = setInterval(() => {
    if (i >= text.length) { clearInterval(timer); return; }
    callback(text[i]);
    i++;
  }, TOKEN_DISPLAY_INTERVAL_MS);
}
```

### 5.5 엣지 케이스 처리

| 상황 | 처리 |
|------|------|
| @마커 없이 큰따옴표 대사 | NARRATION으로 표시 (따옴표 포함) |
| @마커 후 대사 없이 서술 계속 | 마커 버퍼 폐기, NARRATION 복귀 |
| 불완전한 @마커 (스트림 끊김) | done 이벤트의 후처리본으로 교체 |
| 한 토큰에 마커+대사 전체 포함 | StreamParser가 순차 처리 (문자 단위) |
| 유니코드 따옴표 (" ") | isQuoteOpen/Close에서 모두 처리 |
| 대사 안에 이스케이프된 따옴표 | 연속 따옴표("") 감지하여 무시 |

---

## 6. 후처리 타이밍 변경

| 단계 | 현재 | 스트리밍 후 |
|------|------|-----------|
| Step A (마커 삽입) | 전체 완성 후 | 전체 완성 후 (동일) |
| Step B (마커 변환) | 전체 완성 후 | 전체 완성 후 (동일) |
| Step C (실명 가드) | 전체 완성 후 | 전체 완성 후 (동일) |
| Step D (발화 트리밍) | 전체 완성 후 | 전체 완성 후 (동일) |
| Step E (프리픽스 제거) | 전체 완성 후 | 전체 완성 후 (동일) |
| Step F (NPC 교정) | 전체 완성 후 | 전체 완성 후 (동일) |

**후처리는 변경 없음** — 전체 서술 완성 후 한 번에 적용. 스트리밍 중에는 원문 표시.

---

## 7. Fallback 전략

SSE 연결 실패 시 기존 폴링 방식으로 자동 전환:

```typescript
try {
  const es = new EventSource(streamUrl);
  // ... SSE 처리
  es.onerror = () => {
    es.close();
    fallbackToPolling(runId, turnNo);
  };
} catch {
  fallbackToPolling(runId, turnNo);
}
```

---

## 8. 구현 단계

### Phase 1: 서버 스트리밍 인프라
1. OpenAI Provider `callStream()` 메서드 추가
2. LlmStreamBroker 서비스 생성
3. LLM Worker에서 스트리밍 호출 + 토큰 브로드캐스트
4. Turns Controller SSE 엔드포인트 추가

### Phase 2: 클라이언트 SSE 연동
5. game-store.ts SSE 연결 + 폴링 fallback
6. StoryBlock.tsx 2-Phase 렌더링
7. 스트리밍 중 @마커 임시 숨김
8. done 이벤트 → 최종본 교체

### Phase 3: 최적화
9. 토큰 버퍼링 (너무 빠른 토큰 도착 시 부드럽게 분산)
10. SSE 재연결 로직
11. 이미 완료된 턴 조회 시 즉시 전체본 반환

---

## 9. 예상 효과

| 지표 | 현재 (폴링) | 스트리밍 후 |
|------|-----------|-----------|
| 첫 글자 표시 | 5~17초 | 1~3초 |
| 체감 대기 시간 | 5~17초 | 1~3초 |
| 전체 서술 완료 | 5~17초 | 5~17초 (동일) |
| NPC 말풍선 표시 | 서술 완료 후 | Phase 2에서 (서술 완료 후) |
| 네트워크 요청 수 | 2~8회 폴링 | 1회 SSE |

---

## 10. 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| SSE 연결 끊김 | 서술 미수신 | 폴링 fallback 자동 전환 |
| Phase 1→2 전환 시 깜빡임 | UX 저하 | 페이드 트랜지션 적용 |
| 스트리밍 중 NPC 이름 노출 | 몰입 깨짐 | @마커 패턴 실시간 감지 + 숨김 |
| PM2 클러스터 환경 | SSE가 다른 인스턴스로 | sticky session 또는 Redis pub/sub |
| OpenRouter 스트리밍 미지원 모델 | stream 실패 | fallback to non-stream |
