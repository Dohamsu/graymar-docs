# architecture/55 — NPA 메트릭 v2: 다중 NPC 정확 측정

> **상태**: 설계 완료 (구현 대기)
> **의존**: architecture/47 (NPA 기반), architecture/51 §A (NPA v2 메트릭)
> **배경**: A54 작업 중 발견 — NPA가 한 응답에 여러 NPC가 등장할 때 모두 primary NPC register로 측정해 정확도 떨어지는 버그 식별. 또한 system 프롬프트가 실제 NPC unknownAlias를 "금지 예시"로 명시하는 자기모순 발견.

---

## 1. 발견된 문제

### 1.1 NPA toneConsistency 측정 버그

**현재 코드** (`scripts/e2e/audit/dialogue-quality.ts` L234~253):

```ts
for (const p of evalPairs) {
  const txt = utterancesText(p);  // 모든 utterance text를 공백으로 join
  const npc = p.speakerNpcId ? npcs.get(p.speakerNpcId) : null;  // primary NPC만
  const patterns = REGISTER_PATTERNS[npc?.speechRegister ?? "HAOCHE"]
                   ?? REGISTER_PATTERNS.HAOCHE;
  const sentences = txt.split(/[.!?…]\s*/)...;
  for (const s of sentences) {
    toneDen++;
    if (patterns.some((re) => re.test(s))) toneHit++;
  }
}
```

**문제**:
- `p.speakerNpcId`는 첫 번째 NPC(primary)만 식별
- 한 pair에 여러 NPC utterance가 있어도 모두 primary NPC의 register로 평가
- 다른 register NPC가 자기 register로 정확히 답해도 mismatch 카운트

**실증 사례**:
- `chat-edric` 시나리오 T5: 에드릭(HAOCHE) + 라이라(HAPSYO, "조용한 문서 실무자") 등장
- 라이라가 "회계사님, 여기서 무엇을 하고 계십니까?" — 정확한 HAPSYO
- NPA는 에드릭 HAOCHE 기준으로 평가 → mismatch (잘못된 측정)

### 1.2 System 프롬프트 자기모순

**현재** (`server/src/llm/prompts/system-prompts.ts` L135 이전):

```
- ⚠️ NPC를 묘사할 때 새로운 호칭을 만들지 말 것. "조용한 문서 실무자",
  "무표정한 창고 여인" 등 서버 목록에 없는 이름/호칭 창작 절대 금지.
```

**문제**:
- "조용한 문서 실무자" = NPC_MOON_SEA (라이라 케스텔)의 unknownAlias
- "무표정한 창고 여인" = NPC_SERA_DOCKS (세라)의 unknownAlias
- 즉 실제 등록된 NPC를 "금지 예시"로 명시 → LLM에게 정당한 NPC를 쓰지 말라고 한 셈

**상태**: A54 작업에서 두 예시 이미 제거 (미커밋, 작업 디렉토리)

---

## 2. 설계

### 2.1 NPA toneConsistency 수정

**원칙**: utterance 단위로 자기 NPC register 패턴 매칭.

**필요 변경**:

1. **NpcContentSnapshot 확장** — name 외 매칭 정보 추가:

```ts
interface NpcContentSnapshot {
  npcId: string;
  name: string;
  unknownAlias: string | null;      // ← 추가
  aliases: string[];                 // ← 추가
  signatureKeywords: Set<string>;
  distinctPool: Set<string>;
  speechRegister: "HAOCHE" | "HAEYO" | "BANMAL" | "HAPSYO" | "HAECHE";
  baselineTone: "dark" | "warm" | "cold" | "neutral";
}
```

2. **NPC 매칭 헬퍼** — utterance.npcName으로 NPC 찾기:

```ts
function findNpcByDisplayName(
  displayName: string,
  npcs: Map<string, NpcContentSnapshot>,
): NpcContentSnapshot | null {
  if (!displayName) return null;
  const trimmed = displayName.trim();
  // 1. name 정확 매칭
  for (const npc of npcs.values()) {
    if (npc.name === trimmed) return npc;
  }
  // 2. unknownAlias 정확 매칭
  for (const npc of npcs.values()) {
    if (npc.unknownAlias === trimmed) return npc;
  }
  // 3. aliases 매칭
  for (const npc of npcs.values()) {
    if (npc.aliases.includes(trimmed)) return npc;
  }
  return null;
}
```

3. **toneConsistency 측정 변경** — utterance 단위 평가:

```ts
let toneHit = 0;
let toneDen = 0;
for (const p of evalPairs) {
  for (const u of p.npcUtterances) {
    if (!u.text) continue;
    const npc = findNpcByDisplayName(u.npcName, npcs);
    const patterns = REGISTER_PATTERNS[npc?.speechRegister ?? "HAOCHE"]
                     ?? REGISTER_PATTERNS.HAOCHE;
    const sentences = u.text
      .split(/[.!?…]\s*/)
      .map((s) => s.trim())
      .filter(Boolean);
    for (const s of sentences) {
      toneDen++;
      if (patterns.some((re) => re.test(s))) toneHit++;
    }
  }
}
const toneConsistency = toneDen > 0 ? toneHit / toneDen : 1;
```

### 2.2 영향받는 다른 메트릭

NPA dialogue-quality.ts에서 `utterancesText(p)`를 사용해 모든 utterance를 합치는 다른 메트릭:

| 메트릭 | 라인 | 현재 처리 | 수정 필요 |
|---|---|---|---|
| keywordCarryOverRate | L198~217 | 모든 utterance 합쳐서 carry-over 검사 | ❌ 불필요 (NPC 무관) |
| pronounConsistency | L222~232 | 모든 utterance 호칭 카운트 | ⚠️ 검토 필요 |
| toneConsistency | L234~253 | primary register로 모두 평가 | ✅ 수정 (위) |
| userResponseRate | L255~271 | 모든 utterance에서 사용자 명사 검색 | ❌ 불필요 |
| toneMatchScore | L450+ | 사용자 톤 vs NPC 톤 비교 | ⚠️ 검토 필요 |

**pronounConsistency 검토**:
- 한 NPC 내 호칭 일관성을 보는 메트릭
- 다른 NPC 등장 시 "그대" vs "형제" 등 다른 호칭 카운트 → 불일치 처리됨
- → utterance 단위로 변경하면 각 NPC 호칭 일관성 측정 (더 정확)
- → 수정 권장 (다음 단계)

**toneMatchScore 검토**:
- 사용자 casual/serious 톤 vs NPC 응답 톤 비교
- primary NPC만 측정해도 됨 (사용자가 primary와 대화 중)
- → 수정 불필요 가능. 검토 후 결정

### 2.3 System 프롬프트 정정

**현재 상태**: A54 작업에서 라인 135 두 예시 이미 제거 (미커밋).

**점검 결과**:
- 모든 NPC 43명의 unknownAlias 검사 → system 프롬프트에 등장하는 것 2개:
  - "날카로운 눈매의 회계사" (NPC_EDRIC_VEIL): **올바른 예시**로 다수 사용 — OK
  - "약초 노점의 노부인" (NPC_MIRELA): **올바른 예시**로 사용 — OK
- 금지 예시로 사용된 unknownAlias는 라인 135의 2개 ("조용한 문서 실무자", "무표정한 창고 여인") — 이미 제거됨
- 추가 정정 불필요

**작업**:
- A 변경 (라인 135 1줄 수정) commit·push만 진행

---

## 3. 구현 계획

### Phase 1: NPA 메트릭 수정 (Critical)

1. `scripts/e2e/audit/dialogue-quality.ts`:
   - NpcContentSnapshot에 unknownAlias + aliases 추가
   - loadNpcs()에서 추출
   - findNpcByDisplayName 헬퍼 추가
   - toneConsistency 측정 utterance 단위로 변경
2. types.ts (해당 시): NpcContentSnapshot 타입 동기화
3. 검증: 8 시나리오 NPA 재실행 → toneConsistency 변화 측정

### Phase 2: System 프롬프트 commit (이미 변경, 미커밋)

1. system-prompts.ts L135 1줄 변경 commit
2. server 리포 push

### Phase 3: 추가 정확도 (선택)

- pronounConsistency도 utterance 단위 변경 검토
- toneMatchScore 검토

---

## 4. 측정 방법

### Before vs After

**Before (현재)**:
- chat-edric 톤일치 2.50 (라이라 HAPSYO가 mismatch 카운트)
- chat-mairel 톤일치 2.50 (다른 NPC HAPSYO 끼어들기)

**After (수정 후 예상)**:
- chat-edric 톤일치 향상 — 라이라가 자기 HAPSYO로 평가
- chat-mairel 톤일치 향상 — 끼어들기 NPC가 자기 register로 평가
- 진짜 LLM 품질이 정확히 반영됨

### 검증 시나리오

8 시나리오 모두 재실행. 5턴 빠른 검증 또는 10턴 정밀.

### 비교 기준

- A52 묶음 8 시나리오 평균: 3.78
- 수정 후 평균: TBD (예상 +0.1~+0.3)
- ERR 0 유지 필수

---

## 5. 위험 분석

### 위험 1: 메트릭 변경으로 이전 측정과 비교 어려움
- 완화: architecture/51 §A의 v2 메트릭을 v3으로 표기하거나 동일 메트릭 변형으로 명시
- 이전 측정값은 baseline으로만 참조

### 위험 2: NPC 매칭 실패 (unknownAlias가 정확히 일치 안 할 때)
- 마커 시스템(NpcDialogueMarkerService)이 npcName을 그대로 넣어주면 매칭 잘 됨
- 부분 매칭 fallback 추가 가능

### 위험 3: TONE_DRIFT WARN 분포 변화
- 일부 NPC는 점수 향상, 일부는 그대로
- → 진짜 LLM 품질 문제 식별 가능 (잔존 WARN은 진짜 문제)

---

## 6. 우선순위

🔴 **Phase 1 (Critical)** — NPA 메트릭 수정. 모든 향후 측정의 정확도 의존
🟡 **Phase 2 (High)** — System 프롬프트 1줄 commit
🟢 **Phase 3 (Medium)** — pronoun/toneMatch 추가 검토

---

## 7. 커밋 전략

- Phase 1+2 묶음 커밋: "fix(audit): NPA toneConsistency utterance 단위 측정 — 다중 NPC 정확화"
- 메시지에 architecture/55 참조 + 측정 변화 수치 포함
