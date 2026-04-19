# 36. LLM 파이프라인 변경 이력 — 2026-04-17

> 2026-04-17 세션에서 진행한 LLM 파이프라인·렌더링·품질 수정을 이전 설계와
> 비교해 한 문서로 정리. 각 수정의 Before / After / 효과 / 근거를 포함한다.

---

## 0. TL;DR

| 영역 | Before | After | 핵심 효과 |
|------|--------|-------|----------|
| StreamTyper 완료 처리 | onComplete 중복 호출 가능 | `completedRef` once-guard + 핸들러 멱등성 | 타이핑 완료 순간 본문 사라짐 제거 |
| 타이핑 중 / 완료 렌더 구조 | 인라인 `<span leading-relaxed>` vs block 래핑 불일치 | `renderNarrationLines` + 공통 `font-narrative` 부모 | 전환 순간 스타일 점프 제거 |
| 스트림 버퍼 조합 | 매 flush마다 `\n` 연결 (문장별 개행) | `analyzeText` 문단 재조합 + `appendAnalyzed` 공백 조인 | 문장별 줄바꿈 현상 해소 |
| 대사 내부 raw 마커 | LLM 이중 마커 → `[이름\|URL]` 말풍선 노출 | 서버 5.10.5 strip + 클라 `cleanResidualMarkers` #6 | 라이브 세션 노출 0 |
| BG NPC 어체 규칙 주입 | BACKGROUND tier 발화자 시 프롬프트 누락 (0%) | `sr.ui.speakingNpc` 기반 강제 포함 + 보조 posture | 주입률 100%, 규정 어체 준수 |
| 버그 리포트 수집 | recentTurns + uiDebugLog 만 | + clientSnapshot + networkLog + clientVersion | 재현 분석 시간 단축 |

> 누적 커밋: server `ec1018b` → `68d29a2` → `b49dee0`, client `64849be` → `03e938b` → `cb26b2c` → `8685c36` → `6a8a4dd`, docs `0f84232` → `6625a2e`.

---

## 1. 타이핑·렌더링 파이프라인

### 1.1 문제 정의

배포 이후 3건의 UI 버그 리포트(`d8b9de24`, `8d469994`, `fc14ed2b`, `c3f880f3`)에서 동일 계열 이슈가 반복 발생:

1. 타이핑이 끝나는 순간 내레이터 박스의 본문이 통째로 사라짐
2. 타이핑 중 폰트·line-height·크기가 완료 후와 달라 "스타일 점프"
3. 스트리밍 경로의 문장들이 모두 한 줄씩 독립 줄로 렌더링

### 1.2 Before (기존 파이프라인)

```
LLM 토큰 스트림
   └→ game-store.streamNarrative
        ├→ rawBuffer 누적
        ├→ extractCompleteSentences() (300ms)
        ├→ analyzeText() — 각 줄 NPC 대사 변환
        └→ analyzedBuffer = prev + '\n' + analyzed   ← 문제 ①

StoryBlock 렌더
   ├ loading=true + isStreaming → <StreamTyper />
   │    └ onComplete = () => { ... setState(messages, text=buffer) }
   └ loading=false + typed → <NarratorContent />
        ├ text.split('\n') → <span className="block">
        └ 빈 줄 → <span className="block h-3" />

   ※ StreamTyper: 부모 래퍼 없음 (font-narrative 미적용)     ← 문제 ②
   ※ StreamTyper.useEffect: onComplete 호출 가드 없음         ← 문제 ③
```

문제:
- ①: LLM이 문장마다 `.\n`을 출력하면 flush 단위별로 `\n` 중첩 → 한 문장 한 줄
- ②: StreamTyper 하위 인라인 span은 `leading-relaxed` (1.625) + 기본 폰트, 완료 후는 `font-narrative` + `leading-[1.75]` → 전환 시 시각적 점프
- ③: `typedLength >= buffer.length && isDone` 상태가 여러 번 evaluate 되면 `onComplete`가 같은 tick에 2회 호출 → 1회차가 `streamTextBuffer=''`로 초기화한 뒤 2회차는 messages.text를 빈 문자열로 덮어씀

### 1.3 After (현재 파이프라인)

```
game-store.streamNarrative
   ├ extractCompleteSentences()
   ├ analyzeText()                   ← 문단 기준 재조합
   │     • transformed = 각 줄 NPC 대사 마커 변환
   │     • paragraphs = 빈 줄 기준 분할
   │       · 각 문단 내부:
   │         narration 라인들 → 공백 병합 (한 문장으로)
   │         대사 라인(@[...] "...") → 독립 줄 유지
   │     • paragraphs.join('\n\n')
   └ appendAnalyzed(current, next)    ← 경계 처리
        • current.endsWith('\n') → current + next
        • 그 외 → current + ' ' + next

StoryBlock 렌더
   ├ loading=true + isStreaming
   │    └ <div class="font-narrative leading-[1.75]" fontSize={X}>
   │         <StreamTyper onComplete={…}/>
   │    └ StreamTyper
   │         • completedRef.current = false 초기값
   │         • effect: if (typedLength >= buffer.length && isDone && !completedRef.current)
   │                       completedRef.current = true; onComplete()
   │         • renderNarrationLines(seg.text, key) — block 래핑 통일
   │    └ onComplete 핸들러
   │         • if (!store.isStreaming || finalText.length === 0) return
   │         • setState(isStreaming=false, buffer='') → messages 갱신
   └ loading=false + typed
        └ <div class="font-narrative leading-[1.75]">
             <NarratorContent text={msg.text}/> — 기존 block 렌더 유지
```

핵심 변경:

- **멱등성 가드 양방향** (트리거 + 핸들러): StreamTyper 와 onComplete 양쪽 모두 1회만 유효 동작하도록 가드
- **렌더 구조 통일**: `renderNarrationLines` 헬퍼로 타이핑 중/후 모두 `\n` → `<span className="block">` + 빈 줄 `h-3` 일관 처리
- **부모 래퍼 이식**: 타이핑 중 경로에도 `font-narrative leading-[1.75] fontSize` 래퍼 씌워 폰트·line-height 상속 일관화
- **문단 기반 조합**: narration은 공백 병합, 대사만 독립 줄. 문단 경계(`\n\n`)는 LLM 원문 구조 그대로 보존

### 1.4 측정 결과

- 타이핑 → 완료 전환 시 사라짐 재현: 불가 (onComplete 1회 호출 확인, UI debug log 기준)
- 스타일 점프: 육안 구분 불가 (같은 폰트/크기/line-height)
- 문장별 줄바꿈: 분석된 20턴 서술에서 `\n` 기준 짧은 독립 줄 28.9% (LLM 원문 특성 영향 남음, 클라 렌더는 공백 병합으로 자연스럽게 표시)

---

## 2. 대사 내부 Raw 마커 제거

### 2.1 문제 정의

버그 `fc14ed2b`에서 DialogueBubble 말풍선 안에 `[로넨|/npc-portraits/ronen.webp] 정말 감사합니다. 부디 도와주십시오.` 같이 **@ 프리픽스가 없는 raw 마커 잔해**가 그대로 노출됨.

### 2.2 Before (기존 후처리 체인)

```
llm-worker.service.ts — 후처리 B 단계:
  B-1: @[NPC_ID]         → @[표시이름|URL]
  B-2: @[A-Z_0-9]        → @[표시이름|URL]
  B-2.5: @[한글호칭]     → @[표시이름|URL]        ← lookahead: 공백 + "
  B-3: @한글이름 → 제거

문제:
  LLM이 이중 마커 생성 시
      @[로넨|URL] "@[로넨|URL] 대사..."
  외부 마커는 B-2.5가 치환하지만, 큰따옴표 내부 @[로넨|URL] 은
  뒤에 " 가 없어 어느 regex 에도 매칭되지 않음.
  이후 @ 프리픽스가 다른 경로에서 탈락하고 [이름|URL] 만 대사 텍스트의
  일부로 남아 말풍선에 노출.
```

클라 `cleanResidualMarkers` 는 `@[...]` 패턴만 처리, `@` 없이 시작하는 `[...|URL]` 잔해는 손대지 않았음.

### 2.3 After

서버 (llm-worker.service.ts 5.10.5 신규 단계):

```ts
// deduplicateAliases 직후 실행
narrative = narrative.replace(
  /(["\u201C])([^"\u201D]*?)(["\u201D])/g,
  (_m, q1, inner, q2) => {
    const cleaned = inner
      .replace(/@?\[[^\]|]*\|[^\]]+\]\s*/g, '')   // @[이름|URL] / [이름|URL]
      .replace(/@\[[^\]]+\]\s*/g, '');            // @[이름]
    return `${q1}${cleaned}${q2}`;
  },
);
```

클라 (`StoryBlock.cleanResidualMarkers` #6):

```ts
// 정상 @[이름|URL] 은 앞 문자가 @ → 보호
// @ 없이 npc-portraits URL 을 포함하는 raw 마커만 제거
text = text.replace(/(^|[^@])\[[^\]|]+\|\/npc-portraits\/[^\]]+\]\s*/g, '$1');
```

양방향 방어로:
- 서버가 DB 저장 전 이중 마커 잔해 제거 → 저장 데이터 청소
- 클라가 엣지 케이스(서버 리트라이 실패 등)도 방어

### 2.4 검증

- 3개 벤치 런 (29턴) + 20턴 종합 벤치 (21턴)에서 `rawMarkerLeak_total = 0`
- 말풍선에 `[이름|URL]` 잔해 재노출 사례 재현 불가

---

## 3. BG NPC 어체 규칙 주입

### 3.1 문제 정의

플레이테스트 중 거리의 아이(`NPC_BG_STREET_KID`, 규정 BANMAL)가 `"~것이오"`, `"~어요"` 같은 하오체/해요체 대사를 반복적으로 출력. 거리 아이 말투로서 부적절.

### 3.2 근거 확보 — 전수 감사

3개 런 × 11턴씩 전수 감사 (프롬프트 덤프 + 실제 대사 대조):

| 런 | BG 발화 턴 | 어체 규칙 주입된 턴 | 규정 이탈 대사 |
|----|----------|------------------|-------------|
| 26B_bench1 | 4 | **0 / 4 (0%)** | 0 (휴리스틱 UNK 분류) |
| 31B_bench1 | 4 | **0 / 4 (0%)** | 1 |
| 26B_solo   | 4 | **0 / 4 (0%)** | 3 (HAEYO/HAOCHE 혼용) |
| **합계** | 12 | **0 / 12 (0%)** | 4+ |

즉 BG NPC 발화 12턴 **전부에서** 어체 규칙이 프롬프트에 주입되지 않음. 100% 재현.

### 3.3 근본 원인

```
prompt-builder.service.ts:1368~
   const relevantNpcIds =
     targetNpcIds.size > 0
       ? targetNpcIds                         // Player-First 주요 타겟 1~2명
       : new Set(Object.keys(ctx.npcPostures));  // fallback
```

조합된 두 문제:

1. `targetNpcIds` 는 IntentParser/이벤트 primaryNpc 기반 1~2명만 포함 → BACKGROUND NPC가 실제 발화자여도 여기에 안 들어감.
2. `ctx.npcPostures` 자체가 `NPC_LOCATION_AFFINITY` 등재 NPC (CORE/SUB 11명) 만 계산 → BG 25명은 애초에 posture가 없음.
3. 결과: BG NPC 가 발화해도 `[NPC 대화 자세]` 블록에 규칙·성격이 주입되지 않고, LLM은 주변 다른 NPC 의 어체를 오염 적용.

### 3.4 After (prompt-builder.service.ts 수정)

```ts
const relevantNpcIds =
  targetNpcIds.size > 0
    ? new Set(targetNpcIds)
    : new Set(Object.keys(ctx.npcPostures));

// 실제 발화자(primaryNpcId / speakingNpc) 를 반드시 포함
const actualSpeaker =
  sr.ui?.speakingNpc?.npcId ??
  sr.ui?.actionContext?.primaryNpcId;

const speakerExtraPosture: Record<string, string> = {};
if (actualSpeaker) {
  relevantNpcIds.add(actualSpeaker);
  if (!ctx.npcPostures?.[actualSpeaker]) {
    // BG NPC 는 NPC_LOCATION_AFFINITY 미등록이므로 보조 posture 주입
    speakerExtraPosture[actualSpeaker] = 'CAUTIOUS';
  }
}

const effectivePostures = {
  ...(ctx.npcPostures ?? {}),
  ...speakerExtraPosture,
};

const postureLines = Object.entries(effectivePostures)
  .filter(([npcId]) => relevantNpcIds.has(npcId))
  .map(...);  // speechRegister 규칙 + speechStyle + traits
```

### 3.5 검증 결과

fix 이후 10턴 재검증 (run `36a5c185`):

| 지표 | Before (3런) | After (fix v3) |
|------|-------------|---------------|
| BG 발화 턴 | 12 | 4 |
| 어체 규칙 주입률 | 0 / 12 (0%) | **4 / 4 (100%)** |
| 대사 어체 일치 | 4 / 12 | **4 / 4 (100%)** |

20턴 종합 벤치 (run `6176d1c8`)에서도 재현:

| 지표 | 값 |
|------|-----|
| BG 발화 턴 | 10 |
| 어체 규칙 주입률 | **10 / 10 (100%)** |
| BG 대사 어체 일치 | 5 (BANMAL) + 5 (UNK, 짧은 감탄사) — 규정 이탈 0 |

실제 대사 샘플:

- "야, 너 방금 되게 쥐새끼 같았어."
- "너, 눈썰미가 장난 아니네. 근데 너무 쳐다보지는 마, 다른 녀석들이 엮이기 싫어하거든."
- "거기서 뭐 하는 거야? 눈에 띄면 끝장이라고."

이전의 `"~것이오"`, `"~어요"` 오염 완전 해소.

### 3.6 부작용 분석

- 프롬프트 길이: BG NPC 1명 추가 주입 시 ~6줄 (어체 규칙 + 성격 + 말투). 200k 입력 토큰 중 ~100 토큰 수준. 토큰 예산 영향 미미.
- TTFT/TTLT: 수정 전후 유의미한 차이 없음 (20턴 종합 벤치 mean 9.1s 유지).
- CORE/SUB NPC: 기존 주입 경로 그대로, 부작용 없음.

---

## 4. 버그 리포트 수집 데이터 확장

### 4.1 문제 정의

버그 분석 시 현재 스트리밍 상태·뷰포트·API 레이턴시·메시지 플래그 등을 알 수 없어 원인 추적에 추정이 필요했음.

### 4.2 Before

`bug_reports` 테이블:
- `recent_turns` (jsonb): type + text 만
- `ui_debug_log` (jsonb): 스트림/타이퍼 이벤트 타임라인
- `server_version` (text)

### 4.3 After

DB 컬럼 3개 추가:

- `client_snapshot` (jsonb): phase, nodeType, turnNo, locationId, HUD, worldState 요약, 스트리밍 상태, pending 카운트, lastMessages 요약, llmStats, llmFailure, DOM 요약 (choice-btn / dialogue-bubble 카운트, viewport, scrollY)
- `network_log` (jsonb): 최근 100개 API 호출 타임라인 — method/path/status/latencyMs/ok/errorCode (api-client `request()` 래퍼가 자동 기록)
- `client_version` (text): `NEXT_PUBLIC_CLIENT_VERSION` (git sha) — 서버/클라 배포 불일치 즉시 판별

클라 `BugReportModal`:
- `serializeMessage` — 메시지 전체 필드 직렬화 (id/tags/loading/typed/selectedChoiceId/resolveOutcome/speakingNpc/npcPortrait/choices/locationImage)
- `collectClientSnapshot` — 게임 상태 스냅샷
- `collectDomSummary` — 실제 렌더 DOM 통계
- `getNetworkLog` — API 타임라인 스냅샷
- `clientVersion` 필드 전송

### 4.4 효과

bug `fc14ed2b` 와 `c3f880f3` 분석 시:
- `server_version=68d29a2`, `client_version=8685c36` 짝으로 배포 불일치 즉시 판별
- client_snapshot 의 `lastMessages[].typed` / `isStreaming` / `streamBufferLength` 로 렌더 단계 직접 확인
- 추측 기반 분석에서 실증 기반 분석으로 전환

---

## 5. 진단·측정 인프라

### 5.1 신규 스크립트

#### `scripts/bench-models.py` — 모델 벤치마크

- 임의 N개 모델에 대해 M턴 플레이테스트 (프롤로그 + N-1턴 ACTION)
- SSE 스트림 직접 연결하여 TTFT/TTLT 측정
- DB `llm_token_stats` 에서 server latency/토큰 수 회수
- OpenRouter 가격표 (출처 `https://openrouter.ai/google`) 적용해 비용 산출
- 결과 `playtest-reports/bench_*.json` 저장 + 간단 비교 프린트

실행 예:
```bash
python3 scripts/bench-models.py \
  --models google/gemma-4-26b-a4b-it google/gemma-4-31b-it \
  --turns 10
```

#### `scripts/verify-bench-quality.py` — 품질 감사

- DB `turns.llm_output` 전체를 읽어 대사 추출 + 어체 휴리스틱 분류
- 메타 서술 ("당신은" 시작 등), 문장별 줄바꿈, @마커, raw 마커 누수 카운트
- 결과 `playtest-reports/bench_quality_verify.json` 저장

#### `/tmp/audit_bg_registers_v2.py` — BG NPC 어체 주입 감사

- 각 턴의 `llm_prompt` 를 덤프해 `[NPC 대화 자세]` 블록 추출
- 발화자 NPC (`server_result.ui.speakingNpc.npcId`) 의 규정 어체 vs 실제 대사 어체 대조
- tier별 (CORE/SUB vs BACKGROUND) 통계

### 5.2 `.claude/skills/` 신규

- `bug-analyze` — 최신 bug_reports 조회 + 분석 템플릿
- `restart-dev` — 서버·클라 정리/재기동
- `doc-sync` — 서비스·컴포넌트 실측 수치 동기화

---

## 6. 관련 파일 및 커밋

### 6.1 수정된 서버 파일
- `server/src/llm/llm-worker.service.ts` — 5.10.5 raw 마커 strip
- `server/src/llm/prompts/prompt-builder.service.ts` — BG NPC 어체 주입 (발화자 강제 포함)
- `server/src/db/schema/bug-reports.ts` — client_snapshot / network_log / client_version 컬럼
- `server/src/runs/dto/create-bug-report.dto.ts` — DTO 확장
- `server/src/runs/bug-report.service.ts` — 필드 저장 로직

### 6.2 수정된 클라이언트 파일
- `client/src/components/narrative/StoryBlock.tsx` — 멱등성 가드 + 폰트 래퍼 + renderNarrationLines + cleanResidualMarkers #6
- `client/src/components/narrative/DialogueBubble.tsx` — `data-dialogue-bubble` DOM 스캔 속성
- `client/src/store/game-store.ts` — analyzeText 문단 재조합 + appendAnalyzed
- `client/src/lib/network-logger.ts` (신규) — API 호출 타임라인 버퍼
- `client/src/lib/api-client.ts` — request 래퍼 로깅 통합 + submitBugReport 시그니처 확장
- `client/src/components/ui/BugReportModal.tsx` — 수집 로직 확장 (serializeMessage / collectClientSnapshot / collectDomSummary / clientVersion)

### 6.3 커밋 이력 (2026-04-17)

| 레포 | 커밋 | 요약 |
|------|------|------|
| server | `ec1018b` | 대사 내부 raw 마커 잔해 제거 (5.10.5) |
| server | `68d29a2` | bug_reports client_version 컬럼 추가 |
| server | `b49dee0` | BG NPC 어체 규칙 프롬프트 주입 |
| client | `64849be` | StreamTyper/TypewriterText block 래핑 통일 |
| client | `03e938b` | StreamTyper 멱등성 가드 |
| client | `cb26b2c` | 대사 raw 마커 클라 방어 regex |
| client | `8685c36` | 스타일 점프 + clientVersion 전송 |
| client | `6a8a4dd` | 스트림 문장별 줄바꿈 제거 |
| docs | `0f84232` | 설계 문서 35 후속 수정 섹션 + CLAUDE.md |
| docs | `6625a2e` | guides/01·02 + CLAUDE.md 수치 동기화 |

---

## 7. 검증 상태 매트릭스

| 항목 | Before | After | 검증 방법 |
|------|--------|-------|----------|
| 타이핑 중 텍스트 사라짐 | 재현됨 (버그 8d469994) | 재현 불가 | ui_debug_log + onComplete 로그 |
| 스타일 점프 | 재현됨 (버그 c3f880f3) | 육안 구분 불가 | 부모 래퍼 코드 비교 |
| 문장별 줄바꿈 | 모든 스트리밍 턴 | 클라 렌더 공백 병합 | game-store analyzeText 테스트 |
| Raw 마커 노출 | 재현됨 (버그 fc14ed2b) | 29턴 + 21턴 벤치에서 0건 | `rawMarkerLeak_total` |
| 따옴표 짝 홀수 | — | 0 / 21턴 | dq_odd_turns |
| "당신은" 시작 | 0~10.2% (런별) | 2.1% | 서술 정규식 |
| BG NPC 어체 규칙 주입 | 0 / 12 (0%) | 10 / 10 (100%) | 프롬프트 덤프 + 포스처 블록 매칭 |
| BG 대사 어체 일치 | 8 / 12 (나머지 HAOCHE 오염) | 10 / 10 (BANMAL 또는 UNK 단문) | 어체 휴리스틱 |
| 서버/클라 버전 짝 | 수동 추적 | bug_reports 자동 저장 | client_version 컬럼 |

---

## 8. 향후 과제

- BG NPC 어체 다양성: CORE/SUB 와 달리 BG는 동일 NPC가 반복 등장 시 프롬프트 순환(`speechParts rotate`) 효과가 약함. 추가 관찰 필요.
- 문장별 줄바꿈 원문 특성: LLM 원문의 `.\n` 습관 억제를 프롬프트에서 더 강하게 유도할지 결정.
- 어체 자동 분류 한계: UNK 비율 40%+ (짧은 감탄사, 종결어미 변형). 분류기 개선 또는 LLM 기반 평가 고려.
- 벤치 샘플 크기: 현재 10~20턴 기준. NPC 다양성 확보(HUB 이동 강제, 프리셋 순회)로 통계적 파워 향상.

---

## 9. 참조

- `architecture/05_llm_narrative.md` — 전체 LLM 파이프라인 개요 (정본)
- `architecture/26_narrative_pipeline_v2.md` — 3-Stage Pipeline + AI 가이드라인 부록
- `architecture/30_marker_accuracy_improvement.md` — @마커 시스템 3전략
- `architecture/31_memory_system_v4.md` — Memory v4 + entity_facts
- `architecture/32_dialogue_split_pipeline.md` — 2-Stage 대사 분리
- `architecture/34_player_first_event_engine.md` — Player-First 이벤트 엔진 (targetNpcId/sceneNpcIds)
- `architecture/35_llm_streaming.md` — LLM 스트리밍 설계 + Dual-Track 구현 + 후속 수정 섹션 (A~E)
- `architecture/INDEX.md` — 도메인별 색인
- `guides/04_llm_memory_guide.md` — LLM 파이프라인·메모리 실무 가이드
