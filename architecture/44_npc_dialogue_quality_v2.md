# NPC 대사 품질 v2 — 환각 융합 별칭 차단 + 크로스 NPC 주제 반복 해소

**Status**: 📎 설계 (2026-04-22)
**Context**: QA 60턴 종합 검증(run a63c12dd) NPC 대사 25개 분석 결과 두 개의 고정 이슈 도출
**Related**: [[architecture/30_marker_accuracy_improvement|marker accuracy improvement]], [[architecture/32_dialogue_split_pipeline|dialogue split pipeline]], `26_narrative_pipeline_v2.md`

---

## 배경

a63c12dd 런에서 9명 NPC의 25개 대사를 수집해 검토한 결과, 서술 품질을 반복적으로 해치는 두 고정 결함이 확인됨.

### 이슈 ① 환각 융합 별칭
**예시**: `"토단정한 제복의 장교 하위크: \"...\""`

- `토브렌 하위크`(실명) + `단정한 제복의 장교`(unknownAlias) 두 표현이 LLM 출력에서 **한 발화자 지칭**으로 융합
- 현재 서버 마커 매칭이 이 융합 별칭을 "부분 일치" 점수로 정상 매칭 처리 → 오염된 alias가 서술 본문에 그대로 남음

### 이슈 ② 크로스 NPC 주제 반복
**예시**: 6턴 구간에 하위크 `"자중하시오"`, 마이렐 `"너무 깊게 파고들지 마시오"`, 드루인 `"발을 들이지 마시오"` — 서로 다른 단어, **동일 테마(경계/자중)**

- `recentTopics`가 NPC별 독립 저장이라 크로스 NPC 반복을 추적 못함
- 키워드 추출이 표층 명사 기준이라 의미적 동의어 우회 허용
- posture CAUTIOUS + 프리셋 배경이 "경계 톤" 수렴 → LLM 설계 원칙 #5(풍선효과)

---

## 이슈 ① 구현 설계 — 환각 융합 별칭 차단

### 대전제
- "서술에 NPC 2명 등장"은 정상. 차단 대상이 아님
- "한 alias 문자열 1개 안에 두 NPC 이름 파편이 섞인 경우"만 차단
- 정당한 복수 표기(`"토브렌과 하위크"`)는 연결어 존재 여부로 구분하여 허용

### 수정 포인트
**파일**: `server/src/llm/npc-dialogue-marker.service.ts`

#### 1. 연결어 감지 상수 신규
```typescript
// 복수 NPC 표기 연결어 (정당한 복수 발화 신호)
private static readonly MULTI_NPC_CONNECTORS = /\s*(?:과|와|그리고|및|랑|하고|·|,|또는)\s*/;
```

#### 2. `resolveNpcIdFromAlias()` 개선 (`lines 327-364`)
기존 양방향 substring 매칭 **앞에** 융합 감지 가드 추가.

```typescript
private resolveNpcIdFromAlias(
  alias: string,
  candidates: NpcCandidate[],
): string | null {
  // [1] 정확 매칭 (기존 유지)
  for (const c of candidates) {
    for (const name of c.names) {
      if (name === alias) return c.npcId;
    }
  }

  // [2] 환각 융합 감지 — NEW
  const hitNpcIds = new Set<string>();
  const hitFragments: Array<{ npcId: string; name: string; pos: number }> = [];
  for (const c of candidates) {
    for (const name of c.names) {
      if (name.length < 2) continue;
      const pos = alias.indexOf(name);
      if (pos >= 0) {
        hitNpcIds.add(c.npcId);
        hitFragments.push({ npcId: c.npcId, name, pos });
      }
    }
  }

  if (hitNpcIds.size >= 2) {
    // 파편 사이에 연결어가 있는지 검사
    const sorted = [...hitFragments].sort((a, b) => a.pos - b.pos);
    let hasConnector = false;
    for (let i = 0; i < sorted.length - 1; i++) {
      const betweenStart = sorted[i].pos + sorted[i].name.length;
      const betweenEnd = sorted[i + 1].pos;
      if (betweenEnd <= betweenStart) continue;
      const between = alias.slice(betweenStart, betweenEnd);
      if (NpcDialogueMarkerService.MULTI_NPC_CONNECTORS.test(between)) {
        hasConnector = true;
        break;
      }
    }

    if (hasConnector) {
      // 정당한 복수 표기: 마커 삽입 포기 (한 라인에 두 발화자 불가)
      this.logger.debug(
        `[MultiSpeaker] 복수 발화 감지 → 마커 스킵: "${alias}"`,
      );
      return null;
    }

    // 환각 융합: 거부
    this.logger.warn(
      `[MarkerReject] 환각 융합 의심: "${alias}" hits=${[...hitNpcIds].join(',')}`,
    );
    return null;
  }

  // [3] 부분 포함 매칭 (기존 유지, 단일 NPC hit만 도달)
  let bestMatch: { npcId: string; score: number } | null = null;
  for (const c of candidates) {
    for (const name of c.names) {
      if (name.length < 2) continue;
      if (alias.includes(name) || name.includes(alias)) {
        const score = Math.min(alias.length, name.length);
        if (!bestMatch || score > bestMatch.score) {
          bestMatch = { npcId: c.npcId, score };
        }
      }
    }
  }
  if (bestMatch && bestMatch.score >= 2) return bestMatch.npcId;

  // [4] role 매칭 (기존 유지)
  ...
}
```

#### 3. 서술 본문 잔류 제거 — Step F 확장
**파일**: `server/src/llm/llm-worker.service.ts` (Step F 후처리 근처)

환각 융합 alias는 마커 삽입이 거부돼도 **서술 본문에 그대로 남아있다**. 예:
```
토단정한 제복의 장교 하위크가 서류를 밀며 말했다.
```

Step F 정규화 로직에 "환각 융합 문자열 정본화" 단계 추가:

```typescript
// primaryNpcId 있고 hitNpcIds.size>=2 && !hasConnector → 정본 이름으로 치환
function normalizeHallucinatedFusion(
  text: string,
  primaryNpcDef: NpcDef,
  fusionPattern: RegExp,
): string {
  const canonical = primaryNpcDef.unknownAlias ?? primaryNpcDef.name;
  return text.replace(fusionPattern, canonical);
}
```

`fusionPattern`은 2단계에서 감지된 융합 문자열을 실시간 등록. 재등장 시 전체 문서 일괄 치환.

### 복수 발화 포맷 유도 (B' 보완)
**파일**: `server/src/llm/dialogue-generator.service.ts` (`DIALOGUE_SYSTEM` 프롬프트)

동일 턴에 두 NPC가 공동 발화해야 할 때, `"토브렌과 하위크: "대사""` 대신 라인 분리를 강제:

```
⚠️ 복수 NPC가 동시에 말할 때는 반드시 각자 개별 라인으로 분리하세요.
금지: "토브렌과 하위크: "갑시다""
허용:
  토브렌 하위크: "가죠"
  단정한 제복의 장교: "동의합니다"
```

### 테스트 케이스 (`npc-dialogue-marker.service.spec.ts`)
신규 describe 블록:
```
describe('환각 융합 별칭 차단', () => {
  it('"토단정한 제복의 장교 하위크" → null (연결어 없음, 융합)', ...);
  it('"토브렌과 하위크" → null (정당한 복수 표기, 마커 스킵)', ...);
  it('"토브렌의 심복 하위크" → NPC_TOBREN (단일 NPC 파생 표현, 허용)', ...);
  it('"하위크" → NPC_TOBREN (단순 부분 매칭, 기존 동작 유지)', ...);
});
```

---

## 이슈 ② 구현 설계 — 크로스 NPC 주제 반복 차단

### 대전제
- 개별 NPC 단위가 아닌 **런 전역**에서 주제 반복을 추적
- 단어 일치가 아닌 **의미 카테고리 단위**로 통제 (동의어 우회 차단)
- 프롬프트는 Negative("X 금지") 보다 Positive("Y/Z 중 선택") 우선 (CLAUDE.md LLM 설계 원칙)

### 신규 스키마 — `runState.narrativeThemes`
**파일**: `server/src/db/types/permanent-stats.ts` 또는 `narrative-theme.ts`(신규)

```typescript
export type NarrativeThemeTag =
  | 'WARNING'      // 경고/자중 (가장 수렴되는 테마)
  | 'SUSPICION'    // 의심/속셈 질문
  | 'REASSURE'     // 안심/환대
  | 'THREAT'       // 위협/협박
  | 'INFO_REQUEST' // 정보 요구
  | 'GOSSIP'       // 소문/잡담
  | 'ROMANCE'      // 호의/관심
  | 'FAREWELL'     // 작별/퇴장
  | 'OTHER';

export interface NarrativeThemeEntry {
  turnNo: number;
  npcId: string;
  theme: NarrativeThemeTag;
  snippet: string; // 원대사 앞 20자 (로깅·디버깅)
}

export interface RunState {
  ...
  narrativeThemes?: NarrativeThemeEntry[]; // 최근 10턴만 유지 (FIFO)
}
```

### 테마 분류 함수 신규
**파일**: `server/src/llm/theme-classifier.service.ts`(신규)

```typescript
const THEME_PATTERNS: Record<NarrativeThemeTag, RegExp[]> = {
  WARNING: [
    /자중|파고들|조심|물러|위험|발(?:을)? 들이|끌려들|손(?:을)? 떼|개입 말|간섭 말/,
    /위험하(?:오|다|오이다|소)|그만두시(?:오|게)/,
  ],
  SUSPICION: [
    /무슨 속셈|노리(?:오|시|는)|왜 그러|목적이 뭐|정체가|수상/,
  ],
  REASSURE: [
    /걱정 마|괜찮|안전|믿으시|염려 마/,
  ],
  THREAT: [
    /가만 안|죽(?:이|여)|혼내|박살/,
  ],
  INFO_REQUEST: [
    /말해 주시|알려 주시|물어 보|여쭤|뭘 아시/,
  ],
  GOSSIP: [
    /소문|들었(?:소|네)|떠돌(?:오|더)/,
  ],
  ROMANCE: [
    /마음에 드|끌리|호감|반했/,
  ],
  FAREWELL: [
    /그럼 이만|가 보(?:오|겠)|다음(?:에|이)/,
  ],
};

@Injectable()
export class ThemeClassifierService {
  classify(dialogue: string): NarrativeThemeTag {
    for (const [theme, patterns] of Object.entries(THEME_PATTERNS)) {
      if (patterns.some(p => p.test(dialogue))) {
        return theme as NarrativeThemeTag;
      }
    }
    return 'OTHER';
  }
}
```

### 기록 시점
**파일**: `server/src/turns/turns.service.ts` (LLM 후처리 committing 구간)

LLM 서술이 DB에 저장되기 직전, 추출된 대사 각각을 `ThemeClassifierService`로 분류하여 `runState.narrativeThemes`에 추가.

```typescript
// dialogues: [{ npcId, text }] — 마커 파싱 후
for (const d of dialogues) {
  const theme = this.themeClassifier.classify(d.text);
  if (theme !== 'OTHER') {
    runState.narrativeThemes = pushTheme(runState.narrativeThemes ?? [], {
      turnNo,
      npcId: d.npcId,
      theme,
      snippet: d.text.slice(0, 20),
    });
  }
}
// pushTheme: 최근 10턴만 유지
```

### 프롬프트 주입
**파일**: `server/src/llm/prompts/prompt-builder.service.ts`

메인 서술 프롬프트 + DialogueGenerator 양쪽에 공통 블록 추가:

```typescript
function buildThemeGuard(recent: NarrativeThemeEntry[]): string {
  if (!recent?.length) return '';

  // 최근 3턴 테마 집계
  const last3 = recent.filter(e => e.turnNo >= currentTurn - 2);
  const counts = new Map<NarrativeThemeTag, number>();
  for (const e of last3) counts.set(e.theme, (counts.get(e.theme) ?? 0) + 1);

  // 2회 이상 등장한 테마 → 회피
  const saturated = [...counts.entries()]
    .filter(([, n]) => n >= 2)
    .map(([t]) => t);

  if (!saturated.length) return '';

  // Positive framing
  const allThemes: NarrativeThemeTag[] = ['WARNING','SUSPICION','REASSURE','THREAT','INFO_REQUEST','GOSSIP','ROMANCE','FAREWELL'];
  const alternatives = allThemes.filter(t => !saturated.includes(t));

  return [
    `[대화 테마 분포 — 최근 3턴]`,
    last3.map(e => `  T${e.turnNo} ${e.npcId}: ${e.theme} "${e.snippet}..."`).join('\n'),
    ``,
    `⚠️ 위 중 ${saturated.join(', ')} 테마가 포화 상태입니다. 이번 턴 NPC 대사는 다음 테마 중 하나를 선택:`,
    `  ${alternatives.join(' / ')}`,
    `같은 의미를 다른 단어로 표현하는 것도 반복입니다. 테마 자체를 바꾸세요.`,
  ].join('\n');
}
```

### DialogueGenerator 크로스 NPC 회피 (C')
**파일**: `server/src/llm/llm-worker.service.ts:671`

현재 `previousDialogues: [] as string[]`로 비어있음. 같은 턴/런 다른 NPC의 최근 대사 주입:

```typescript
const previousDialogues = collectRecentDialogues(runState, {
  currentNpcId: npcId,
  turnWindow: 3,
  maxCount: 3,
});
// [다른 NPC 최근 대사 — 유사 반복 금지]
```

DialogueGenerator 프롬프트에 추가:
```
[다른 NPC 최근 대사 — 유사 표현/테마 반복 금지]
T${n-2} 마이렐: "너무 깊게 파고들지 마시오"
T${n-1} 드루인: "발을 들이지 마시오"

⚠️ 위와 같은 "경계/자중" 테마는 이번 NPC 대사에서 다른 주제로 전환하세요.
```

### 테스트 케이스
- 3턴 연속 WARNING 발생 시 4턴째 프롬프트에 `saturated=['WARNING']` 포함 확인
- `classify("자중하시오")` → `WARNING`
- `classify("너무 깊게 파고들지 마시오")` → `WARNING` (동의어도 분류)
- `classify("날씨가 좋소")` → `OTHER`

---

## 구현 순서 (단계별 검증 가능)

### Phase A — 이슈 ① (30분~1시간)
1. `MULTI_NPC_CONNECTORS` 상수 + `resolveNpcIdFromAlias` 가드 추가
2. 단위 테스트 4건 추가·통과
3. Step F 서술 본문 융합 치환 추가
4. DialogueGenerator 프롬프트 라인 분리 규칙 추가

### Phase B — 이슈 ② (1~2시간)
1. `NarrativeThemeEntry` 타입 + `runState.narrativeThemes` 스키마
2. `ThemeClassifierService` 신규 + 단위 테스트
3. turns.service commit 구간에 테마 기록
4. `buildThemeGuard` 프롬프트 블록 + prompt-builder 주입
5. DialogueGenerator `previousDialogues` 실제 데이터 주입

### Phase C — 검증
- 단위 테스트 전체 통과
- 30턴 플레이테스트 1회 → NPC 대사 수집 → 환각 별칭 0건, 동일 테마 3턴 연속 0건 확인
- Slack 완료 알림

---

## 예상 영향

| 지표 | Before (a63c12dd) | After (목표) |
|------|-------------------|--------------|
| 환각 융합 별칭 | 1건/25대사 (4%) | 0건 |
| 3턴 내 동일 테마 반복 | 3회 WARNING/6턴 | ≤ 1회/3턴 |
| 마커 정상 삽입율 | 측정 필요 | ≥ 95% 유지 |

---

## 보류/후속

- **Phase D (콘텐츠)**: NPC 43명 `speechStyle`/`personality.signature` 다양화 — WARNING 외 패턴 강제 주입 가능한 콘텐츠 보강. 2025-05월 예정
- **테마 자동 확장**: 런타임에 등장한 OTHER 대사를 nano LLM으로 재분류하여 `THEME_PATTERNS`에 제안 추가 (반자동)
