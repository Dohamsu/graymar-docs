# 38. LLM Streaming ON / OFF 비교 분석 — 요청·응답 구조와 LLM 게임에서의 장단점

> OpenAI-compatible API (OpenRouter 경유 Gemma 4) 기준으로, `stream` 옵션이
> 켜졌을 때와 꺼졌을 때 **서버 요청 / 수신 스트림 / 클라이언트 렌더 / DB 저장**
> 각 레이어가 어떻게 달라지는지와 LLM 게임 맥락의 장단점을 한 문서로 정리.

---

## 0. 한 줄 요약

- **Stream OFF (폴링)**: "전체 완성본을 받아서 천천히 타이핑해 보여준다." 단순·안정·후처리 자유롭지만, **첫 글자까지 5~17초 대기**.
- **Stream ON (SSE)**: "토큰이 오는 대로 실시간으로 흘려보낸다." 체감 속도 **TTFB 0.5~2초**, 대기감 소멸. 단, **조각 상태를 다뤄야 하고 후처리 경로가 복잡해진다**.

---

## 1. API 레이어 — 요청/응답 차이

### 1.1 Stream OFF (폴링 방식)

#### 서버 → LLM API (OpenRouter)
```json
POST https://openrouter.ai/api/v1/chat/completions
{
  "model": "google/gemma-4-26b-a4b-it",
  "messages": [...],
  "temperature": 0.8,
  "max_tokens": 1024,
  "stream": false
}
```

#### LLM API → 서버
```json
{
  "id": "chatcmpl-...",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "차가운 새벽 공기가 골목을 가른다.\n\n@[로넨|URL] \"실례합니다. 항만 노동 길드 서기관 로넨입니다.\"\n..."
    },
    "finish_reason": "stop"
  }],
  "usage": { "prompt_tokens": 9837, "completion_tokens": 452, "total_tokens": 10289 }
}
```
→ **서술 전체가 한 덩어리 JSON**. 완성된 후에 한 번에 도착.

#### 서버 내부
1. `await openai.chat.completions.create({ stream: false })` — Promise 하나
2. 응답 수신 후 전체 text를 변수 `narrative` 에 담음
3. 후처리 6단계(Step A~F) 순차 적용 (마커 삽입, 실명 정리, 어체 교정 등)
4. DB `turns` 테이블 업데이트: `llm_output=완성본`, `llm_status='DONE'`, `llm_token_stats=usage`

#### 클라 ← 서버 (폴링)
- 턴 제출 직후 `POST /runs/:runId/turns` 응답에는 `llm.status='PENDING'` + ui/diff만 도착
- 클라는 **2초 간격으로** `GET /runs/:runId/turns/:turnNo` 호출
- `llm.status==='DONE'` 이면 `llm.output` 전체 수신
- 클라 측 타이핑 렌더 시작

```
t=0ms   턴 제출 → 서버 resolve 즉시 응답 (50ms)
t=3~17s LLM 완성본 DB 저장 (비동기)
t=3~19s 클라 폴링이 DONE 감지
t≈19s   타이핑 애니메이션 시작
```

### 1.2 Stream ON (SSE 방식)

#### 서버 → LLM API
```json
POST https://openrouter.ai/api/v1/chat/completions
{
  "model": "google/gemma-4-26b-a4b-it",
  "messages": [...],
  "stream": true                   ← 차이 한 줄
}
```

#### LLM API → 서버 (SSE 스트림)
```
data: {"choices":[{"delta":{"content":"차"}}]}
data: {"choices":[{"delta":{"content":"가"}}]}
data: {"choices":[{"delta":{"content":"운"}}]}
data: {"choices":[{"delta":{"content":" 새"}}]}
...
data: {"choices":[{"delta":{"content":"니다."}, "finish_reason":"stop"}]}
data: [DONE]
```
→ **delta 조각들이 실시간 푸시**. 마지막에 `[DONE]` 센티넬.

#### 서버 내부
1. `for await (const chunk of openai.chat.completions.create({ stream: true }))` — AsyncIterable
2. 각 chunk의 `delta.content` 를 `rawBuffer` 에 누적
3. 매 chunk마다 `LlmStreamBrokerService.emit(runId, turnNo, 'token', {text: delta})` — 인메모리 SSE 브로커로 브로드캐스트
4. `stream-classifier` 가 문장 경계 감지 → narration/dialogue 타입으로 분류된 이벤트 추가 emit
5. 완료 후 `rawBuffer` 전체에 기존 후처리 6단계 동일 적용 → DB 저장 + `done` 이벤트 emit

#### 클라 ← 서버
- 턴 제출 후 서버가 즉시 resolve/ui 응답 (폴링과 동일)
- 클라가 **즉시 SSE 연결**: `EventSource("/runs/:runId/turns/:turnNo/stream")`
- 이벤트 종류:
  - `token`: 토큰 단위 실시간
  - `narration` / `dialogue`: 문장 단위 분류
  - `choices_loading`: 선택지 생성 시작
  - `done`: 최종 서술 + 선택지 (후처리 완료본)
  - `error`: 실패
- 클라 측: 각 token을 `streamTextBuffer` 누적 → `StreamTyper` 가 자체 속도로 한 글자씩 타이핑 렌더

```
t=0ms      턴 제출 → 서버 resolve 응답
t=0.5~2s   첫 token 이벤트 (TTFT)
t=0.5~2s   타이핑 애니메이션 즉시 시작
t=5~15s    마지막 token 이벤트 (TTLT)
t=5~15s    done 이벤트 — 후처리된 최종본으로 교체
```

---

## 2. 데이터 흐름 비교 다이어그램

### 2.1 Stream OFF
```
[Client]                 [Server]                  [LLM API]
턴 제출    ─────────▶ POST /chat/completions (stream:false)
              ◀── resolve/ui 즉시
                          ├ await 전체 응답
폴링 2s ◀─────────▶ GET turns/:n (status=PENDING)
                          ├ 완성본 수신 (3~17s)
                          ├ 후처리 6단계
                          └ DB UPDATE (llm_output)
폴링 2s ◀─────────▶ GET turns/:n (status=DONE + output)
[타이핑 시작]
```

### 2.2 Stream ON
```
[Client]                 [Server]                  [LLM API]
턴 제출    ─────────▶ POST /chat/completions (stream:true)
              ◀── resolve/ui 즉시
SSE 구독   ─────────▶ GET turns/:n/stream
                          ├ for await chunk:
                          │    emit('token', delta)  ◀─ chunk ─┐
                          │                                     │
              ◀── token(delta) × N  ─────────────────────────────┤
[StreamTyper 점진 렌더]                                          │
                          │    (stream-classifier)              │
              ◀── narration/dialogue × M ──                       │
                          │                                     │
                          ├ 완성 후 rawBuffer 후처리            │
                          ├ DB UPDATE (llm_output)              │
              ◀── done { narrative, choices }                   ─┘
[StreamTyper 버퍼 → 최종본 교체 + 선택지 표시]
```

---

## 3. 코드 차이 (요지)

### 3.1 서버 호출부

```ts
// OFF
const res = await openai.chat.completions.create({
  model, messages, stream: false,
});
const narrative = res.choices[0].message.content;
// ... 후처리 + DB 저장

// ON
const stream = await openai.chat.completions.create({
  model, messages, stream: true,
});
let raw = '';
for await (const chunk of stream) {
  const delta = chunk.choices[0]?.delta?.content ?? '';
  if (!delta) continue;
  raw += delta;
  this.streamBroker.emit(runId, turnNo, 'token', { text: delta });
}
// ... raw 후처리 + DB 저장 + done emit
```

### 3.2 클라 수신부

```ts
// OFF (폴링)
async function pollTurn(runId, turnNo) {
  while (true) {
    const data = await GET(`/runs/${runId}/turns/${turnNo}`);
    if (data.llm.status === 'DONE') return data.llm.output;
    await sleep(2000);
  }
}

// ON (SSE)
const es = new EventSource(`/runs/${runId}/turns/${turnNo}/stream`);
es.addEventListener('token', (e) => {
  const { text } = JSON.parse(e.data);
  streamTextBuffer += text;  // StreamTyper가 이 buffer 소비
});
es.addEventListener('done', (e) => {
  const { narrative, choices } = JSON.parse(e.data);
  replaceMessage(narrative);
  renderChoices(choices);
  es.close();
});
```

---

## 4. 비교 정리

| 항목 | Stream OFF | Stream ON |
|------|-----------|-----------|
| 서버 → LLM | 단일 Promise | AsyncIterable 스트림 |
| 서버 → 클라 | 폴링 2초 | SSE 실시간 푸시 |
| 타이핑 시작 시점 | 전체 수신 후 | 첫 토큰 도착 즉시 |
| TTFB(첫 글자 체감) | 5~17초 | 0.5~2초 |
| 총 완료 시간 | 동일 | 동일 |
| 후처리 타이밍 | 완성본 한 번에 | 완성 후 한 번에 (중간에 조각 렌더) |
| DB 저장 | 1회 (완성본) | 1회 (완성본) |
| 네트워크 | HTTP GET 반복 | TCP 지속 (HTTP keep-alive + chunked) |
| 서버 자원 | chunk 처리 CPU +α, 소켓 유지 비용 | — |
| 오류 처리 | Promise.reject | 스트림 에러 이벤트 + 재연결 복잡 |
| 구현 난이도 | 낮음 | 중 (브로커/이벤트 큐/조각 상태) |
| 연결 실패 복구 | 재요청 간단 | EventSource 자동 재연결 + 상태 동기화 필요 |
| JSON 모드 호환 | ✅ 원활 | ⚠️ 충돌 (조각 JSON 파싱 불가 → 표시 차단 필요) |

---

## 5. 사용 시 주의점 / 알아두면 좋은 점

### 5.1 공통
- OpenAI-compatible API는 `stream` 플래그 하나만 다르다. 나머지 필드(`model`, `messages`, `temperature`)는 동일.
- **usage (토큰 수)** 는 stream 모드에서 마지막 chunk 또는 별도 이벤트로 제공되거나 생략될 수 있다. 서버에서 직접 카운트하거나 provider 별 문서 확인 필요.
- 프롬프트 캐시(OpenAI/Anthropic 등)는 stream과 무관하게 동작.

### 5.2 Stream OFF 주의점
- **LLM 호출 시간 + 폴링 주기 = 총 대기 시간**. 폴링 주기가 짧으면 서버 부하, 길면 체감 UX 악화.
- 타임아웃은 전체 응답 기준으로 잡아야 한다 (예: 30s).
- 긴 서술(1500자+)일수록 사용자 체감 지연이 선형으로 증가.

### 5.3 Stream ON 주의점
- **불완전 조각 처리**: token 이벤트로 `@[로넨` 까지만 도착해도 화면에 쓸 수 없다. 클라에 "잘린 마커 제거" 필터 필수 (현재 graymar는 `cleanResidualMarkers` 가 이 역할).
- **후처리 타이밍**: 서술 전체 후처리(마커 변환·실명 정리·어체 교정)는 완성 후에만 가능. 스트리밍 중에는 **원문 그대로** 보이므로 "최종본과 미세 차이" 가 생김.
  - 해법: **2-Phase 렌더링**. Phase 1=스트리밍 중 원문 표시, Phase 2=done 직후 최종본으로 교체.
- **멱등성 가드**: 완료 콜백이 두 번 호출되면 상태를 덮어쓰는 경우가 있다 (graymar에서 `StreamTyper.completedRef` + onComplete early return 가드 필요했음).
- **폰트 / 스타일 일관성**: 스트리밍 렌더와 완성 렌더의 DOM 구조가 다르면 전환 시 "스타일 점프" 가 눈에 띈다. 부모 래퍼 동일화 필요.
- **네트워크 복구**: EventSource 는 기본 재연결을 시도하지만, 서버가 토큰을 재전송하지는 않음. `done` 이벤트 누락 시 폴링 fallback 필요.
- **JSON 모드 비호환**: `response_format: json_object` 는 스트리밍 조각 파싱이 불가. 둘 중 하나만 쓰거나 Partial JSON 파서 도입.
- **SSE 프록시**: Nginx/Cloudflare/일부 CDN은 기본 설정으로 SSE 버퍼링. `X-Accel-Buffering: no` 또는 `Cache-Control: no-cache` 헤더 필요.
- **서버 인메모리 브로커의 한계**: 멀티 인스턴스 환경에서는 Redis pub/sub 같은 공유 브로커로 교체해야 "턴 제출한 인스턴스 ≠ SSE 구독한 인스턴스" 케이스를 해결.
- **토큰 측정 분리**: TTFT(첫 토큰)/TTLT(마지막 토큰)를 별도로 측정해야 병목(모델 vs 네트워크 vs 파이프라인)을 구분할 수 있다.

---

## 6. LLM 게임(Text RPG) 맥락의 장단점

### 6.1 Stream OFF의 장점
- **서술 품질 관점**: 서버가 완성본을 완전히 다듬은 후 보내므로, 마커·실명·어체 이탈 위험이 적다.
- **선택지 동시 도착**: 서술과 선택지를 같은 API 응답으로 받아 "서술 완료 → 선택지 등장" 플로우가 깔끔.
- **재시도 단순**: LLM 실패 시 같은 요청을 다시 보내면 끝. 파셜 상태 없음.
- **후처리 자유도**: 서술 전체를 본 후에만 가능한 교정(일관성 체크, 중복 문장 삭제 등)이 쉬움.
- **모바일 배터리**: 폴링 간격이 길수록(2~3s) 라디오 사용이 줄어 유리.

### 6.2 Stream OFF의 단점
- **첫 반응까지 5~17초 대기 → "멈춘 것 같은" UX**. 게임 몰입 최대 적.
- 서술이 길수록 체감이 더 나빠짐 (300자→500자 전환 시 완성 시간 +5초).
- LLM provider가 일시적으로 느려지면 사용자는 이유를 모른 채 기다림.

### 6.3 Stream ON의 장점
- **체감 응답 즉시**: 첫 글자 0.5~2초에 보임. "살아있는 서술자" 느낌.
- **서술 길이에 덜 민감**: 시작은 빠르고 뒤로 갈수록 더 읽을거리 등장. 사용자는 이미 읽기 시작.
- **부분 실패 복원**: 중간까지 보인 조각이 유효한 "상황 묘사"로 남을 수 있어 fallback이 쉬움.
- **연출 여지**: 타이핑 속도·구두점 pause·대사 강조 등을 **클라가 자체 제어** — 게임 연출과 결합.

### 6.4 Stream ON의 단점 / 리스크
- **불완전 조각 노출 위험**: 마커·시스템 문자·특수 태그가 잠깐 보일 수 있어 추가 필터 레이어 필요.
- **최종본과 중간본 사이의 불일치**: 스트리밍 중엔 원문, done 후엔 후처리본 → 사용자가 "글자가 바뀌었다" 인지 가능. 2-Phase 렌더링 설계 필요.
- **상태 관리 복잡**: `isStreaming` / `streamBuffer` / `streamDone` / `narratorMessage.typed` / `onComplete` 멱등성 등 여러 플래그 + 가드.
- **테스트 비용 증가**: TTFT·TTLT 분리 측정 + 중간 조각 검증 + 완료 검증 각각 필요.
- **운영 관측 난이도**: 폴링은 HTTP 로그만 보면 되지만 SSE는 "언제 끊겼는지/몇 토큰 받았는지" 별도 계측.
- **JSON 구조 출력과 상극**: `response_format: json` 게임 로직(이벤트 판정을 LLM에 맡기는 등)을 쓰면 스트리밍은 기능 상실.

### 6.5 이 프로젝트(graymar)에서의 선택 기준
- **스트리밍 ON 채택** — 이유:
  - 텍스트 RPG는 한 턴당 300~600자 서술. 한 번에 받으면 대기가 너무 길다.
  - 서버가 **상태/판정**은 이미 결정론적으로 소유하므로 스트리밍 서술은 "연출"로만 쓰면 됨 → 상태 불일치 리스크 낮음.
  - @마커·어체·실명 등 민감한 처리는 **done 이벤트의 후처리본**에 집중하고, 스트리밍 중은 원문(이미 대체로 깨끗함)을 그대로 보여줌.
  - 2-Phase 렌더링 + 멱등성 가드로 전환 순간 아티팩트를 제거함.
- 다만 **LLM_JSON_MODE는 여전히 false 유지** — 스트리밍과 공존 가능한 Partial JSON 파서 도입 전까지는 이 조합이 최적.

---

## 7. 게임 개발 관점 운영 체크리스트

- [ ] TTFT / TTLT / 서버 latency 를 상시 계측 (graymar: `scripts/bench-models.py`)
- [ ] 불완전 조각 필터 (`@[...` / `[NPC_` / `[UNMATCHED]` 등) — 클라 렌더 전단계
- [ ] 2-Phase 렌더링 (스트리밍 원문 → done 후처리본 교체) 시 사용자 눈에 띄지 않도록 폰트·크기·줄바꿈 일치
- [ ] `onComplete` / `onDone` 멱등성 가드 (트리거 + 핸들러 양쪽)
- [ ] 서버 인메모리 브로커는 단일 인스턴스 전제 — 확장 시 Redis / Vercel Queues 등 고려
- [ ] LLM provider 타임아웃(> 30s) 대비 폴링 fallback 유지
- [ ] SSE 프록시 버퍼링 비활성 헤더 (`X-Accel-Buffering: no`)
- [ ] JSON 모드와의 상호배타적 사용 (설정 UI/환경변수에서 명시적으로)
- [ ] 에러 이벤트 전용 UI (`error` → 재시도 / 스킵 버튼)
- [ ] 토큰/비용 집계는 **완성 후 일괄**. 스트리밍 중간 수치는 신뢰하지 말 것.

---

## 8. 참조

- [[architecture/35_llm_streaming|llm streaming]] — 스트리밍 설계 + Dual-Track 구현
- [[architecture/37_streaming_transition_issues|streaming transition issues]] — 전환 이슈 9건 간략 리스트
- `scripts/bench-models.py` — TTFT/TTLT 벤치마크
- `scripts/inspect-streaming-leaks.py` — 스트림 토큰 누수 감지
- OpenAI API 공식: https://platform.openai.com/docs/api-reference/streaming
- OpenRouter 스트리밍: https://openrouter.ai/docs/streaming
