# 48. NPC Discoverability v1 — 사용자 자유 NPC 호명 + 위치 안내

> **목표**: 플레이어가 어떤 표현으로든("X 두목/형제단의 누구/지하 조직의 두목") 특정 NPC에 다가갈 수 있게 하고, 그 NPC가 현재 장소에 없으면 주변인이 자연스럽게 위치를 안내한다.
> **선행**: architecture/45 (자유 대화) + 46 (Fact 분리·Continuity) + 47 (NPA 감사).
> **검출 도구**: NPA가 검출한 회귀 5건 (chat-harlun 4 ERR + chat-rat-king 1 ERR).
> **작성**: 2026-04-27

---

## 1. 동기 — NPA가 드러낸 회귀

### 1.1 실제 검출된 사례

```
chat-harlun (항만 진입 후 "부두 형제단의 두목에게 다가간다"):
  T04: 수상한 창고 관리인 응답 (하를런 X)
  T05~T08: 수상한 창고 관리인 4턴
  T09: 토브렌 하위크 점프
  T10: 풋풋한 젊은 경비병 점프
  T11: 드디어 하를런 (FIGHT 이벤트 트리거됐을 때만)
  T13~T14: 펠릭스 → 밧줄장인 연쇄 점프
```

```
chat-rat-king (빈민가 진입 후 "지하 조직의 두목에게 다가간다"):
  T04: 하를런 보스 (빈민가인데?!)
  T05~T07: 입이 가벼운 술꾼
  T08~T13: 레닉 7턴 연속
  쥐왕(NPC_RAT_KING)은 한 번도 등장 X
```

### 1.2 사용자 의도

> "특정 NPC에게 자유롭게 다가갈 수 있어야 하고, 다른 곳에 있다면 주변인이 알려줘야"

즉:
- 플레이어 발화 자유도: "두목/형제단/지하 조직" 같은 role 표현으로도 매칭
- NPC 위치 검색: schedule 기반 현재 location lookup
- 위치 안내: 다른 장소면 주변인이 "그는 X에 있더이다" 자연 발화

### 1.3 현 시스템 한계 (코드 진단)

| 항목 | 현재 | 문제 |
|---|---|---|
| textMatchedNpcId | name + unknownAlias + alias keyword 3-pass 매칭 | role/title 키워드 미인식 |
| NPC 위치 검색 | 없음 | 다른 장소 NPC 호명 시 무력 |
| EventMatcher | default 이벤트 자동 매칭 | textMatch 활성 시도 우회 |
| 주변인 발화 | 없음 | 위치 안내 콘텐츠 부재 |

---

## 2. 4-Layer 아키텍처

```
┌─ Layer 1: 명시적 NPC 호명 인식 (textMatchedNpcId 강화)
│   • Pass 1: name 전체 매칭 (현행)
│   • Pass 2: "~에게" 패턴 (현행)
│   • Pass 3: alias keyword (현행)
│   • Pass 4: ⭐ role/title 키워드 매칭 (신규)
│   • Pass 5: ⭐ NPC.roleKeywords 명시 필드 (신규)
│
├─ Layer 2: NPC 위치 lookup (NpcWhereaboutsService)
│   • lookupNpc(npcId, currentTimePhase) → NpcLocationStatus
│     - { sameLocation: true } → 같은 장소
│     - { sameLocation: false, locationId: 'LOC_X', activity: '...' } → 다른 장소
│   • schedule.{TimePhase}.locationId + activity 활용
│   • dynamicOverride (Living World 이동 결과) 우선
│
├─ Layer 3: EventMatcher 우선순위 보정
│   • textMatchedNpcId 활성 + 같은 장소 → EventMatcher의 default 이벤트
│     primaryNpcId override 차단 (혹은 textMatched NPC 이벤트 강제 매칭)
│   • LOCATION 첫 진입 default 이벤트 가중치 ↓ when textMatch active
│
└─ Layer 4: 주변인 안내 LLM 프롬프트
    • NPC가 다른 장소 → 주변 NPC(SitGen 또는 default)에게
      "[NPC 위치 안내] 그대가 찾는 X는 Y(activity)" 블록 주입
    • 자연 발화 가이드: "당신이 찾는 그자는 X에 있다 들었소"
```

---

## 3. Layer 1 — role/title 키워드 매칭

### 3.1 자동 추출 (가벼운 시작)

NPC.role 필드에서 한글 명사 2-4글자 추출 → 키워드 자동 생성:
```ts
function extractRoleKeywords(role: string): string[] {
  const matches = role.match(/[가-힣]{2,4}/g) ?? [];
  const STOP = new Set(['역할', '담당', '관리', '책임자', '경험', '인물']);
  return [...new Set(matches)].filter(k => !STOP.has(k));
}
```

예시:
- 하를런 role="부두 노동 형제단 연락책. 은퇴한 복서로 뒷골목 싸움의 중재자"
- 추출: ["부두", "노동", "형제단", "연락책", "은퇴", "복서", "뒷골목", "싸움", "중재자"]

### 3.2 명시 필드 (정밀화)

content/graymar_v1/npcs.json에 `roleKeywords?: string[]` 추가:
```json
{
  "npcId": "NPC_HARLUN",
  "name": "하를런 보스",
  "role": "...",
  "roleKeywords": ["두목", "형제단", "복서", "보스", "연락책"]
}
```

CORE 6명만 명시 필드로 정밀화 (작업량 작음). 나머지는 자동 추출 fallback.

### 3.3 매칭 로직 (turns.service.ts)

```ts
// Pass 4: role/title 키워드 매칭 (architecture/48)
if (!textMatchedNpcId) {
  for (const npc of allNpcs) {
    const roleKws = npc.roleKeywords ?? extractRoleKeywords(npc.role ?? '');
    const matched = roleKws.some(
      (k: string) => k.length >= 2 && inputLower.includes(k.toLowerCase())
    );
    if (matched) {
      textMatchedNpcId = npc.npcId;
      break;
    }
  }
}
```

### 3.4 충돌 해결

여러 NPC가 같은 키워드 ("두목" — 하를런/쥐왕/RAT_KING 모두) → **현재 location 우선**:
```ts
// 현재 장소에 있는 NPC 우선
const localFirst = matchedNpcs.find(
  npc => isNpcAtLocation(npc, currentLocationId, currentTimePhase)
);
if (localFirst) textMatchedNpcId = localFirst.npcId;
else textMatchedNpcId = matchedNpcs[0].npcId; // fallback (Layer 2 위치 안내 트리거)
```

---

## 4. Layer 2 — NpcWhereaboutsService

### 4.1 책임

- 입력: `npcId`, `currentLocationId`, `currentTimePhase`, `runState`
- 출력: `NpcLocationStatus`

```ts
export type NpcLocationStatus =
  | { kind: 'SAME_LOCATION'; activity?: string }
  | { kind: 'DIFFERENT_LOCATION'; locationId: string; activity?: string }
  | { kind: 'UNKNOWN' };
```

### 4.2 구현 골자

```ts
@Injectable()
export class NpcWhereaboutsService {
  constructor(private content: ContentLoaderService) {}

  lookupNpc(
    npcId: string,
    currentLocationId: string,
    timePhase: TimePhase,
    runState?: RunState,
  ): NpcLocationStatus {
    // 1. Living World dynamicOverride (npcLocations) 우선
    const dynamicLoc = runState?.worldState?.npcLocations?.[npcId];
    if (dynamicLoc) {
      return dynamicLoc.locationId === currentLocationId
        ? { kind: 'SAME_LOCATION', activity: dynamicLoc.activity }
        : { kind: 'DIFFERENT_LOCATION', ...dynamicLoc };
    }

    // 2. NPC schedule 기반 lookup
    const npc = this.content.getNpc(npcId);
    const slot = npc?.schedule?.default?.[timePhase];
    if (!slot?.interactable) return { kind: 'UNKNOWN' };

    return slot.locationId === currentLocationId
      ? { kind: 'SAME_LOCATION', activity: slot.activity }
      : {
          kind: 'DIFFERENT_LOCATION',
          locationId: slot.locationId,
          activity: slot.activity,
        };
  }
}
```

### 4.3 location 한글 라벨 매핑

```ts
const LOC_LABELS: Record<string, string> = {
  LOC_MARKET: '시장 거리',
  LOC_HARBOR: '항만 부두',
  LOC_GUARD: '경비대 지구',
  LOC_SLUMS: '빈민가',
  LOC_NOBLE: '귀족가',
  // ...
};
```

---

## 5. Layer 3 — EventMatcher 우선순위 보정

### 5.1 현 동작

LOCATION 첫 진입 시 EventMatcher가 `EVT_HARBOR_ARC_HINT` 같은 default 이벤트를 자동 매칭. 그 이벤트의 primaryNpcId가 다른 NPC.

### 5.2 변경 전략

`textMatchedNpcId` 활성이고 같은 장소 NPC면:
1. EventMatcher가 textMatched NPC를 primaryNpcId로 가진 이벤트 우선 매칭
2. 매칭 이벤트 없으면 FREE_PLAYER 이벤트 (default conversation) 강제 사용
3. textMatched NPC를 primaryNpcId로 채워 actionContext에 넣음

코드 위치: `turns.service.ts` resolvedTargetNpcId 분기 직후, EventMatcher 호출 전 또는 후. 현행 로직과 호환되도록 후처리로 추가.

### 5.3 예외

- 사용자 입력에 명시적 이동 의도 ("X로 이동한다") 또는 명시적 fact 호명 시 → EventMatcher 우선

---

## 6. Layer 4 — 주변인 안내 LLM 프롬프트

### 6.1 트리거 조건

- `textMatchedNpcId` 매칭됨
- `NpcWhereaboutsService` 결과 = `DIFFERENT_LOCATION`
- 현재 location에 fallback NPC (default 이벤트 NPC 또는 SitGen NPC) 있음

### 6.2 프롬프트 블록 (prompt-builder.service.ts)

```ts
if (ctx.npcWhereaboutsHint) {
  const { searchedNpcDisplay, locationLabel, activity } = ctx.npcWhereaboutsHint;
  factsParts.push(
    [
      `[NPC 위치 안내]`,
      `플레이어가 ${searchedNpcDisplay}을(를) 찾고 있습니다.`,
      `${searchedNpcDisplay}은(는) 현재 ${locationLabel}에서 ${activity ?? '활동 중'}이라는 사실을 주변 인물이 자연스럽게 안내해 주세요.`,
      `예: "그자라면 ${locationLabel} 쪽에 있다 들었소.", "${locationLabel}에 가면 만날 수 있을 게요."`,
      `톤은 주변 NPC 말투에 맞춰 1~2 문장으로. 강요 X, 자연 흘림. 플레이어 동기 부여.`,
    ].join('\n'),
  );
}
```

### 6.3 LlmContext 추가

```ts
// context-builder.service.ts
npcWhereaboutsHint: {
  searchedNpcId: string;
  searchedNpcDisplay: string;
  locationLabel: string;
  activity?: string;
} | null;
```

---

## 7. 데이터 모델 변경

### 7.1 npcs.json (선택적)

CORE 6명에 `roleKeywords` 추가 (정밀화). 나머지는 자동 추출 fallback.

```json
"roleKeywords": ["두목", "형제단", "복서", "보스"]
```

### 7.2 LlmContext 신규 필드

```ts
npcWhereaboutsHint: {
  searchedNpcId: string;
  searchedNpcDisplay: string;
  locationLabel: string;
  activity?: string;
} | null;
```

### 7.3 actionContext (turns.service.ts)

```ts
actionContext: {
  // ...
  textMatchedNpcId?: string | null;  // Layer 3 우선순위 판단용
  whereaboutsHint?: { ... };          // 디버그용 (NPA 검증)
}
```

---

## 8. 구현 단계

### Phase 1 — Layer 1 (role 키워드 매칭, ~2h)
- [ ] `extractRoleKeywords` helper (turns.service.ts)
- [ ] textMatchedNpcId Pass 4 추가
- [ ] CORE 6명 npcs.json `roleKeywords` 명시
- [ ] 단위 테스트: "두목/형제단/조직/회계사" 입력 매칭 검증

### Phase 2 — Layer 2 (NpcWhereaboutsService, ~1.5h)
- [ ] 신규 파일 `engine/hub/npc-whereabouts.service.ts`
- [ ] HubModule 등록
- [ ] LOC_LABELS 매핑 (locations.json 또는 상수)
- [ ] 단위 테스트: 같은/다른 장소/UNKNOWN 케이스

### Phase 3 — Layer 3 (EventMatcher 우선순위, ~2h)
- [ ] turns.service.ts resolvedTargetNpcId 분기에 같은 장소 텍스트매치 우선 처리
- [ ] EventMatcher 호출 후 textMatched NPC 강제 override (현재 장소 시)
- [ ] 단위 테스트: NPA chat-harlun T04 패턴 회귀

### Phase 4 — Layer 4 (주변인 안내 프롬프트, ~1.5h)
- [ ] context-builder.service.ts npcWhereaboutsHint 빌드
- [ ] prompt-builder.service.ts 블록 주입
- [ ] LlmContext 타입 확장

### Phase 5 — 회귀 검증 (~1h)
- [ ] NPA chat-harlun, chat-rat-king 재실행
- [ ] ERROR 0 목표
- [ ] 평균 종합 점수 +0.3 목표

### Phase 6 — 커밋·푸시
- [ ] graymar-server 커밋 (turns.service.ts + npc-whereabouts.service.ts + context-builder.ts + prompt-builder.ts)
- [ ] graymar-docs 커밋 (architecture/48 + npcs.json)

총 소요: ~10h

---

## 9. 위험 및 완화

| 위험 | 완화 |
|---|---|
| role 키워드 충돌 (여러 NPC 매칭) | 현재 장소 우선, 그래도 모호하면 첫 매칭 (Layer 2가 안내 트리거) |
| 자동 추출 노이즈 | STOP 리스트 + 명시 필드로 CORE NPC는 정밀화 |
| LOCATION 변경 의도와 혼동 | architecture/46 §4.2 (MOVE_LOCATION 차단) 이미 적용됨 |
| EventMatcher 강제 override가 quest 흐름 깨뜨림 | textMatched 활성 + 같은 장소만 적용. 다른 장소면 안내만 |
| 주변인 안내 발화 어색 | LLM 프롬프트에 "1~2문장 자연 흘림" 명시 |

---

## 10. 측정 메트릭 (NPA로)

| 지표 | 베이스라인 (chat-harlun/rat-king) | 목표 |
|---|---|---|
| ERROR (NPC_JUMP) | 5건 | 0건 |
| 평균 종합 점수 | 3.03 (★★★) | 4.0+ (★★★★) |
| 의도 NPC 첫 등장 턴 | T11 (하를런), 미등장 (쥐왕) | T04~T05 |
| TONE_DRIFT | 56~59% | < 70% (LLM 변동성 한계) |

---

## 11. 향후 확장 (v2)

- **NPC 이동 비용**: 다른 장소 안내 → 자동 이동 옵션 ("그곳으로 가시겠소?")
- **NPC 부재 시간대**: schedule.NIGHT/DAWN 등 시간대별 위치 변동 반영
- **NPC 동선 예측**: dynamicSchedule (LivingWorld v2 NpcAgenda 통합)
- **소문 시스템**: 주변 NPC가 "X는 요즘 Y와 자주 만난다" 같은 동적 정보 제공

---

## 12. 관련 문서

- `architecture/45_npc_free_dialogue.md` — daily_topics 기반 잡담
- `architecture/46_fact_pool_continuity.md` — Fact 분리 + Continuity (lock + fact awareness)
- `architecture/47_dialogue_quality_audit.md` — NPA (이 회귀 검출 도구)
- `guides/07_living_world_guide.md` — NpcSchedule (Layer 2 데이터 소스)
- `server/src/turns/turns.service.ts:2299` — textMatchedNpcId 현행 로직
- `server/src/engine/hub/event-matcher.service.ts` — Layer 3 변경 대상
