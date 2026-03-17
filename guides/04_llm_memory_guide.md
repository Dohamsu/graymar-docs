# LLM & 메모리 시스템 구현 지침

> 정본 위치: `server/src/llm/`
> 설계 문서: `architecture/05_llm_narrative.md`, `18_narrative_runtime_patch.md`
> 최종 갱신: 2026-03-17

## LLM Narrative Pipeline

```
1. Server marks turn llmStatus: PENDING
2. LLM Worker polls (2s), builds L0-L4 context, calls provider
3. Worker parses [THREAD], [MEMORY], [CHOICES] tags from output
4. Client polls GET /turns/:turnNo (2s, max 15 attempts)
5. Narrator message shows loading animation → replaced with LLM text
6. Pending messages/choices flush after narrator completes
7. 실패 시: LlmFailureModal → 재시도(retry-llm API) / 서술 건너뛰기 / 닫기
```

### Message Display Order
1. SYSTEM messages (즉시 표시)
2. RESOLVE (주사위 애니메이션 1.2s → 판정 결과 공개, 즉시 표시)
3. NARRATOR (LLM 로딩 → 완료 시 교체)
4. 나머지 messages + CHOICE (narrator 완료 후 flush)

HUB↔LOCATION 전환 시: 전환 화면 없이 즉시 전환, enter narrator만 표시

---

## 메모리 계층 (L0~L4+)

`server/src/llm/context-builder.service.ts`

| 계층 | 데이터 | DB 테이블 | 설명 |
|------|--------|----------|------|
| L0 | theme | run_memories | 세계관 기억 (**절대 삭제 금지**) |
| L0+ | worldSnapshot | (runState) | WorldState 요약 (시간/경계도/긴장도) |
| L1 | storySummary | run_memories | 이야기 요약 (LOCATION 방문 요약 누적) |
| L1+ | locationContext | (runState) | 현재 장소 ID |
| L1+ | midSummary | (생성) | 4턴 초과 시 초기 턴 200자 요약 |
| L2 | nodeFacts | node_memories | 현재 노드 사실 |
| L3 | locationSessionTurns | turns | 현재 방문 대화 (최대 4턴, MidSummary 적용) |
| L3 | recentTurns | turns (최근 5개) | 글로벌 최근 행동+결과 (fallback) |
| L3+ | intentMemory | (생성) | 행동 패턴 감지 결과 (6종) |
| L3+ | activeClues | (생성) | 활성 단서 (PLOT_HINT importance≥0.6, 최대 5개) |
| L4 | currentEvents | (serverResult) | 이번 턴 events |
| L4+ | agendaArc | (runState) | Agenda/Arc 진행도 |
| L4+ | npcEmotional | (runState) | NPC 감정/관계 요약 (displayName 사용) |
| L4+ | introducedNpcIds | (runState) | NPC 소개 상태 |

### Structured Memory v2 프롬프트 블록 순서
`[World State]` → `[Narrative Milestones]` → `[Story Summary]` → `[직전 장소 정보]` → `[NPC Relationships]` → `[Incident Chronicle]` → `[Extracted Facts]`

### LOCATION 떠날 때 기억 저장
go_hub/MOVE_LOCATION/RUN_ENDED → `MemoryIntegration.finalizeVisit()` → `run_memories.structuredMemory` + 호환 `storySummary` 동시 저장
- Fixplanv1 PR3: `lastExitSummary` (VisitExitSummary) 동시 생성 → 다음 장소에서 `[직전 장소 정보]` 블록으로 활용
- Fixplanv2 PR-B: `updateNpcJournal()`에서 NPC별 관련 행동만 필터 (`relatedNpcId` 매칭). 관련 행동 없는 NPC는 interaction 미기록 → npcJournal 오염 방지
- **Fixplan3 P1**: RUN_ENDED 경로에서도 `finalizeVisit()` 호출 추가 — go_hub/MOVE_LOCATION 없이 런이 끝나도 structuredMemory 보존

### VisitAction 구조 (Fixplanv2 PR-B)
`server/src/db/types/structured-memory.ts`
```
{ rawInput, actionType, outcome, eventId?, brief, summaryShort?, relatedNpcId? }
```
- `summaryShort`: 행동+결과 요약 (최대 60자). turns.service.ts에서 `summaryText` 전달. sceneFrame이 아닌 실제 행동 기반.
- `relatedNpcId`: 이 행동에 관련된 NPC ID. updateNpcJournal에서 NPC별 필터링에 사용.
- snippet 생성 우선순위: summaryShort > rawInput > brief (sceneFrame은 최후 fallback)

### NPC Knowledge 자동 수집 (Fixplanv2 PR-E)
`server/src/engine/hub/memory-collector.service.ts`
- 기존: 대화형 actionType(TALK, PERSUADE 등) + SUCCESS/PARTIAL → source=`PLAYER_TOLD`
- 추가: 이벤트 태그(EVIDENCE, SECRET, RUMOR 등) 감지 → source=`AUTO_COLLECT`
- source 타입: `PLAYER_TOLD | WITNESSED | INFERRED | AUTO_COLLECT`
- 중복 방지: 같은 턴+NPC+source 조합이면 스킵
- 렌더링 시 중복 제거: `MemoryRendererService.deduplicateNpcKnowledge()` — AUTO_COLLECT와 nonAuto가 같은 턴이면 AUTO_COLLECT 제거

---

## Token Budget (2500 토큰)

`server/src/llm/token-budget.service.ts` — 설계문서 18

### 블록별 예산
| 블록 | 토큰 | 내용 |
|------|------|------|
| SCENE_CONTEXT | 150 | [현재 장면 상태] |
| INTENT_MEMORY | 200 | [플레이어 행동 패턴] |
| ACTIVE_CLUES | 150 | [활성 단서] |
| RECENT_STORY | 700 | [이번 방문 대화] |
| PREVIOUS_VISIT | 150 | [직전 장소 정보] (PR3 추가, priority=57, minTokens=0) |
| STRUCTURED_MEMORY | 450 | [이야기 요약]+[NPC 관계]+[사건 일지]+[서사 이정표]+[기억된 사실] |
| BUFFER | 250 | 기타 블록 (장비, 성향, NPC 목록 등) |
| **TOTAL** | **2500** | |

### 토큰 추정
```typescript
estimateTokens(text: string): number → Math.ceil(text.length / 3)  // 한국어 ~3자/token
```

### 트리밍
문장 경계(. 。 !) 기준으로 자르기. 예산 초과 시 저우선 블록부터 트리밍.

---

## Mid Summary (4턴 제한 + 중간 요약)

`server/src/llm/mid-summary.service.ts` — 설계문서 18

```
locationSessionTurns > 4턴
  → 초기 턴들을 200자 요약으로 압축 (midSummary)
  → 최근 4턴만 locationSessionTurns에 유지
  → [중간 요약] 블록을 [이번 방문 대화] 앞에 삽입
```

LLM 호출 없이 서버 계산 (SoT 원칙):
- resolved incidents, NPC 상태 변화, 획득 아이템, 주요 판정 결과 포함

---

## Active Clues (활성 단서)

`server/src/llm/memory-renderer.service.ts` → `renderActiveClues()`

```
1. llmExtracted에서 category='PLOT_HINT' && importance≥0.6 추출
2. 미해결 incident 관련 단서 추출
3. 중요도 내림차순 정렬, 최대 5개
4. [기억된 사실] 블록에서 PLOT_HINT 중복 제거
```

---

## Scene Continuity System (장면 연속성)

> 정본: `context-builder.service.ts`, `prompt-builder.service.ts`

### 문제
EventMatcher가 매 턴 다른 이벤트를 선택 → sceneFrame 변경 → LLM 장면 점프

### 3가지 메커니즘

1. **`[현재 장면 상태]` 블록**: 대화 상대/세부 위치/직전 행동을 명시적 전달
2. **sceneFrame 3단계 억제**: 첫턴=전달, 1턴=참고, 2턴+=완전억제
3. **씬 이벤트 유지**: ACTION 입력 시 직전 이벤트 1턴만 자동 유지 (Fixplan3 P5: 2턴→1턴 축소)
4. **`[이번 방문 대화]` 7개 연속성 규칙**:
   - 규칙 1-5: 기본 연속성 (이전 대화 이어가기, 인물 유지 등)
   - 규칙 6: ⚠️ NPC가 알려준 정보/획득 물건/단서를 반드시 기억
   - 규칙 7: ⚠️ 이미 대화한 NPC 재등장 시 이전 대화 내용 인지

### Narrative Thread
- LLM `[THREAD]` 태그 → `node_memories.narrativeThread` 누적
- 엔트리당 max 200자, 총 예산 1200자
- 장면 흐름 블록으로 LLM에 재전달

### locationSessionTurns 서술 포함량 (거리 기반)
| 거리 | 서술 포함 | 라벨 |
|------|----------|------|
| 0 (직전) | 300자 (끝부분) | "여기서 이어쓰세요" |
| 1~2 | 250~150자 | "맥락 참고 — 복사 금지" |
| 3+ | 100자 | "요약 참고" |

---

## LLM Worker Tag Parsing

`server/src/llm/llm-worker.service.ts`

| 태그 | 저장 위치 | 용도 |
|------|----------|------|
| `[THREAD]...[/THREAD]` | `node_memories.narrativeThread` | 장면 흐름 추적 (max 200자/항목, 총 1200자) |
| `[MEMORY]...[/MEMORY]` | `run_memories.structuredMemory.llmExtracted` | LLM 추출 사실 (max 15개) |
| `[MEMORY:NPC_KNOWLEDGE:NPC_ID]` | `run_memories.structuredMemory.npcKnowledge` | NPC가 알게 된 정보 (source=WITNESSED, NPC당 max 5개) |
| `[CHOICES]...[/CHOICES]` | `turns.suggestedChoices` | LLM 제안 선택지 (JSON 파싱) |

NPC 소개 5-way 분기 (`prompt-builder.service.ts`):
- 첫만남+소개 / 재만남+소개 / 첫만남+미소개 / 이미 소개 / 미등장
