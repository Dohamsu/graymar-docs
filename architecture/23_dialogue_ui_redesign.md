# 23. Dialogue UI Redesign (대화 UI 고도화)

> NPC 대사를 메신저 형태로 표시 — 초상화 + 말풍선 스타일

## 1. 개요

### 목적

현재 LLM 서술에서 큰따옴표(`""`) 안의 NPC 대사는 골드색 텍스트로만 구분된다. 이를 메신저 대화처럼 **NPC 초상화 + 말풍선**으로 표시하여:

- NPC 대사와 서술 텍스트를 시각적으로 명확히 분리
- 대화 상대 NPC의 정체성을 초상화로 직관 전달
- 텍스트 RPG에서 "대화하는 느낌"을 강화

### 범위

| 적용 대상 | 설명 |
|-----------|------|
| NARRATOR 타입 StoryMessage | LLM 서술 내 큰따옴표 대사를 말풍선으로 변환 |
| LOCATION 모드 | 대화형 NPC 상호작용 (TALK, PERSUADE, BRIBE, THREATEN, HELP) |
| HUB 모드 | NPC 등장 시 대사 |
| COMBAT | 미적용 (전투 대사는 짧으므로 기존 유지) |

---

## 2. 현재 구현 상태

### 2.1 대사 파싱 (StoryBlock.tsx:105-137)

```
renderStyledText(text) {
  정규식: /("[^"]*"?|…)/g
  큰따옴표 → className="block my-6 font-dialogue" style={color: var(--gold)}
  작은따옴표 → className="font-dialogue" (인라인, 강조)
}
```

**한계**:
- 모든 대사가 동일한 골드 색상
- 대사 주체(누가 말하는지) 식별 불가
- 블록 레이아웃이지만 서술 흐름 안에 섞임

### 2.2 NPC 초상화 (StoryBlock.tsx:301-351)

- `NpcPortraitCard`: 80x80px 이미지 + NPC 이름 + "첫 만남" 배지
- **CORE 5명만** 초상화 보유 (NPC_PORTRAITS 매핑)
- 서술 **상단에만** 표시 (대사 위치가 아님)
- 새로 만난 NPC의 첫 등장 시에만 렌더링

### 2.3 서버 데이터

- `server_result.ui.npcPortrait`: { npcId, npcName, imageUrl, isNewlyIntroduced }
- `primaryNpcId`: 해당 턴의 주 상호작용 NPC
- LLM 서술 텍스트 안에서 대사 주체 식별은 불가 (서버가 직접 마킹하지 않음)

---

## 3. 핵심 과제: 대사 주체 식별

### 3.1 문제

LLM 서술에서 큰따옴표 대사가 누구의 것인지 **프로그래밍적으로 식별이 어렵다**.

예시:
```
부두의 그늘진 곳에서 투박한 노동자가 팔짱을 끼고 서 있었다.
"여기서 뭘 찾는 거요? 이 부두는 일하는 자들의 자리란 말이오."
당신이 장부에 대해 묻자, 그의 눈이 좁아진다.
"장부? 그런 건 내 알 바 아니오. 구석에서 긁적거리는 놈들한테 물어보시오."
```

→ 두 대사 모두 같은 NPC지만, 텍스트만으로는 확실히 알 수 없음.

### 3.2 해결 전략 (3가지 옵션)

#### A. primaryNpcId 기반 단순 매핑 (권장 — Phase 1)

- 해당 턴의 `primaryNpcId`가 있으면, 모든 대사를 그 NPC의 것으로 간주
- 대부분의 턴에서 NPC는 1명만 등장 (대화 잠금 4턴 규칙)
- 초상화 없는 NPC는 기본 실루엣 아이콘 사용

**장점**: 서버 수정 없음, 즉시 구현 가능
**단점**: 복수 NPC 대사 구분 불가 (향후 Phase 2)

#### B. LLM 출력에 화자 태그 삽입 (Phase 2)

- LLM 프롬프트에 `[NPC_ID:]` 태그를 대사 앞에 붙이도록 지시
- 후처리에서 태그 파싱 → 화자별 말풍선 분리
- 예: `[NPC_HARLUN:] "여기서 뭘 찾는 거요?"`

**장점**: 정확한 화자 식별
**단점**: LLM 프롬프트 수정 필요, 토큰 증가, 태그 누락 가능성

#### C. 서버에서 대사 구조체 분리 전달 (Phase 3)

- `server_result.dialogues: [{ npcId, text }]`로 대사를 구조화하여 전달
- LLM 출력 후처리에서 대사 추출 + primaryNpcId 매핑

**장점**: 가장 깔끔한 구조
**단점**: 서버 + LLM 파이프라인 대규모 수정 필요

---

## 4. Phase 1 설계 (primaryNpcId 기반)

### 4.1 렌더링 규칙

```
서술 텍스트를 파싱하여:
1. 큰따옴표 밖 → 기존 서술 스타일 (font-narrative)
2. 큰따옴표 안 → 말풍선 컴포넌트로 변환

말풍선 구성:
┌──────────────────────────────┐
│ [초상화]  NPC 이름            │
│           "대사 내용이        │
│            여기에 표시됨"     │
└──────────────────────────────┘
```

### 4.2 데이터 흐름

```
StoryMessage (type: NARRATOR)
  ├── text: "서술... \"대사\" ...서술... \"대사\" ..."
  ├── npcPortrait?: { npcId, npcName, imageUrl }
  └── (추가) speakingNpcId?: primaryNpcId (result-mapper에서 매핑)

StoryBlock
  └── renderStyledText(text, speakingNpc)
        ├── 서술 부분 → <NarrationSegment>
        └── 대사 부분 → <DialogueBubble npc={speakingNpc}>
```

### 4.3 DialogueBubble 컴포넌트 설계

```
Props:
  - text: string (대사 내용, 따옴표 포함)
  - npcName: string | null
  - npcImageUrl: string | null (없으면 기본 실루엣)
  - isPlayerSpeech: boolean (향후 플레이어 대사 구분용)

레이아웃 (NPC 대사):
┌─────────────────────────────────────┐
│  ┌────┐                             │
│  │ 📷 │  NPC 이름                   │
│  │40px│  ┌─────────────────────┐    │
│  └────┘  │ "대사 내용이 여기에  │    │
│          │  표시됩니다."        │    │
│          └─────────────────────┘    │
└─────────────────────────────────────┘

  초상화: 40x40px rounded-full
  이름: text-xs font-semibold, NPC별 색상
  말풍선: bg-[var(--bg-card)] border rounded-xl p-3
  대사: font-dialogue, var(--gold)
```

### 4.4 초상화 없는 NPC 처리

| NPC 유형 | 초상화 | 표시 방법 |
|----------|--------|-----------|
| CORE 5명 (초상화 있음) | 실제 이미지 | 40px 원형 이미지 |
| SUB/BACKGROUND (초상화 없음) | 없음 | 기본 실루엣 아이콘 (User 아이콘) + 이름만 표시 |
| NPC 미식별 (primaryNpcId 없음) | 없음 | 기존 골드 텍스트 유지 (말풍선 미적용) |

### 4.5 StoryMessage 타입 확장

```typescript
// game.ts
export interface StoryMessage {
  // ... 기존 필드
  /** 대사 주체 NPC 정보 (primaryNpcId 기반) */
  speakingNpc?: {
    npcId: string;
    displayName: string;  // 소개 전이면 alias, 소개 후면 실명
    imageUrl?: string;    // CORE NPC만
  };
}
```

### 4.6 result-mapper 수정

```
// result-mapper.ts
NARRATOR 메시지 생성 시:
  if (serverResult.ui.npcPortrait || serverResult.primaryNpcId) {
    message.speakingNpc = {
      npcId: primaryNpcId,
      displayName: npcPortrait?.npcName ?? unknownAlias,
      imageUrl: npcPortrait?.imageUrl,
    };
  }
```

---

## 5. 시각 디자인

### 5.1 말풍선 스타일

```css
.dialogue-bubble {
  background: var(--bg-card);
  border: 1px solid var(--border-primary);
  border-radius: 12px;
  padding: 10px 14px;
  margin-left: 48px;  /* 초상화 + gap */
  position: relative;
}

/* 말풍선 꼬리 (선택) */
.dialogue-bubble::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 12px;
  width: 12px;
  height: 12px;
  background: var(--bg-card);
  border-left: 1px solid var(--border-primary);
  border-bottom: 1px solid var(--border-primary);
  transform: rotate(45deg);
}
```

### 5.2 NPC별 색상 (선택)

| NPC 계층 | 이름 색상 | 말풍선 보더 |
|----------|-----------|------------|
| CORE | var(--gold) | var(--gold)/30 |
| SUB | var(--text-secondary) | var(--border-primary) |
| BACKGROUND | var(--text-muted) | var(--border-primary) |

### 5.3 전환 효과

- 서술 → 말풍선 전환 시 자연스러운 간격 (my-4)
- 말풍선 등장: fadeSlideIn 0.3s (기존 keyframe 재사용)
- 연속 대사: 같은 NPC면 초상화 생략, 말풍선만 연속 표시

---

## 6. 수정 파일 목록

| 파일 | 수정 내용 |
|------|-----------|
| `client/src/types/game.ts` | StoryMessage에 speakingNpc 필드 추가 |
| `client/src/lib/result-mapper.ts` | NARRATOR 메시지에 speakingNpc 매핑 |
| `client/src/components/narrative/StoryBlock.tsx` | renderStyledText 분기 + DialogueBubble |
| `client/src/components/narrative/DialogueBubble.tsx` | 신규 — 말풍선 컴포넌트 |
| `client/src/app/globals.css` | dialogue-bubble 스타일 (선택) |

---

## 7. 성능 고려

- 대사 파싱은 기존 정규식 기반 (추가 비용 미미)
- DialogueBubble은 React.memo로 감싸 리렌더링 방지
- 초상화 이미지: Next.js Image 컴포넌트 + sizes="40px"로 최적화
- 기본 실루엣은 인라인 SVG (네트워크 요청 없음)

---

## 8. 모바일 대응

| 항목 | 데스크탑 | 모바일 (<768px) |
|------|---------|----------------|
| 초상화 크기 | 40x40px | 32x32px |
| 말풍선 margin-left | 48px | 40px |
| NPC 이름 | text-xs | text-[10px] |
| 대사 폰트 | text-sm | text-sm (동일) |

---

## 9. 접근성

- 초상화에 `alt={npcName}` 제공
- 말풍선에 `role="dialog"` + `aria-label="{npcName}의 대사"` (선택)
- 색상 외에 레이아웃(들여쓰기, 말풍선)으로 대사 구분

---

## 10. 테스트 시나리오

| 시나리오 | 검증 항목 |
|---------|----------|
| CORE NPC와 TALK | 초상화 + 이름 + 말풍선 정상 표시 |
| BACKGROUND NPC와 대화 | 실루엣 아이콘 + unknownAlias 표시 |
| 대사 없는 서술 (OBSERVE) | 기존 서술 스타일 유지 |
| 대사 2개 이상 | 각 대사가 별도 말풍선으로 분리 |
| primaryNpcId 없는 턴 | 기존 골드 텍스트 유지 |
| 모바일 화면 | 32px 초상화, 레이아웃 정상 |
| 과거 턴 스크롤 | 동일하게 말풍선 표시 |

---

## 11. 향후 확장 (Phase 2+)

### 11.1 화자 태그 기반 분리 (Phase 2)
- LLM 프롬프트에 `[NPC_ID:]` 태그 삽입 지시
- 복수 NPC 대화 장면에서 화자별 말풍선 분리

### 11.2 플레이어 대사 말풍선 (Phase 2)
- 플레이어 행동이 대화형(TALK, PERSUADE)일 때
- 오른쪽 정렬 말풍선 (메신저 "나" 스타일)
- 플레이어 초상화 표시

### 11.3 감정 이모티콘 (Phase 3)
- NPC emotional 상태에 따라 초상화 옆에 감정 아이콘
- 😠 (hostile), 🤔 (cautious), 😊 (friendly), 😨 (fearful)

### 11.4 SUB NPC 초상화 자동 생성 (Phase 3)
- Gemini로 SUB 12명 + 주요 BACKGROUND NPC 초상화 생성
- 첫 소개 시 자동 생성 후 캐싱

---

## 12. 구현 체크리스트

- [ ] `game.ts`에 `speakingNpc` 타입 추가
- [ ] `result-mapper.ts`에서 primaryNpcId → speakingNpc 매핑
- [ ] `DialogueBubble.tsx` 신규 생성
- [ ] `StoryBlock.tsx` renderStyledText 분기 로직
- [ ] 기본 실루엣 SVG 아이콘 (초상화 없는 NPC용)
- [ ] 말풍선 CSS 스타일링
- [ ] 모바일 반응형 테스트
- [ ] `pnpm build` 빌드 검증
