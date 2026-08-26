# 109. NPC 관계 엔진 고도화 — 관계 유형·마일스톤·지속성

> 상태: ✅ R1~R3 구현됨 (2026-08-26)
> 선행: relationship-tier.core (관계 티어 4단, ca70874) · arch/82 #7 개방 깊이 · arch/76 D3 감정 행동화 · arch/91 통성명

## 0. R1 구현 기록 (2026-08-26)

- **전이 정본**: `engine/hub/relationship-kind.core.ts` — `applyRelationSignalCore` 순수 함수.
  수락 = romanceable + BONDED + fear<40 + suspicion<50. 거절 쿨다운 5턴(`CONFESSION_COOLDOWN_TURNS`),
  milestones 상한 8(FIFO). DEEP_TRUST: 무유형+CLOSE→FRIEND, FRIEND+BONDED→CONFIDANT,
  GRUDGE/RIVAL+CLOSE→화해(FRIEND+RECONCILED). HOSTILE_BREAK: 신뢰 유형→GRUDGE+BETRAYED,
  무유형+trust≤-10→RIVAL. 스펙 22케이스 (`relationship-kind.core.spec.ts`).
- **상태**: `NPCState.relationship { kind, sinceTurn, milestones }` (`db/types/npc-state.ts`) —
  runState jsonb 에 영속, 세션 재개 시 그대로 복원된다.
- **신호 감지(nano)**: NpcReactionDirector 출력에 `relationSignal` 축 추가
  (CONFESSION/DEEP_TRUST/HOSTILE_BREAK/NONE, 미검증 값은 NONE). 불변식 2 목록 등재 완료.
- **쓰기 단일 지점**: llm-worker `relationSignal` CAS — 콜백 내부에서 fresh 감정으로 티어를
  재계산해 판정하므로 emotionalShift 패치와의 순서 경합은 ±5 soft 오차뿐.
- **프롬프트 순증 0**: `computeRelationshipTierCore` 에 `kind` 입력 추가 — 기존 개방 깊이
  힌트 줄을 kind-aware 문구로 값 교체(연인/벗/심우/원한/맞수). GRUDGE·RIVAL 은 티어 무관
  오버라이드, FRIEND/CONFIDANT 는 관계가 식으면(CLOSE 미만) 티어 힌트로 복귀.
  NpcReactionDirector 의 `관계 단계:` 줄도 동일 원칙.
- **콘텐츠 저작**: 3팩 `relationProfile.romanceable` — true 17명(graymar 7·star_sand 7·karnholt 3),
  명시 false 4명(토브렌·메린=기혼, 루오르=성직, 세피=미성년). 미저작 기본 false.
  `audit_content.py` 에 `RELATION_PROFILE_SHAPE` 모양 검사 추가 (사문 배선 방지).
- 검증: 서버 2,321 passed·스냅샷 17 불변·audit_content ERROR 0.

### 0.1 실런 게이트 결과 (2026-08-26, run bf90c097 — star_sand 이렌)

**PASS.** 호감 8턴(trust 30→100·attach 0→54, BONDED 도달) → 고백 →
`[RelationSignal] confession-accepted (kind=ROMANCE)` + `CONFESSION_ACCEPTED`
마일스톤 DB 기록 → 세션 재개 재회 턴에서 상태 그대로 복원 + 연인 톤
("카일, 그렇게 다정하게 웃어주시니 제 마음까지 다 훈훈해지네요").

1차 시도에서 잡은 결함 2건 (둘 다 게이트 없었으면 사문화됐을 부류):

- **고백 THREATEN 오분류 + nano NONE 이중 소실** (d7746ad) — "나와 연인이
  되어 주겠소?" 의 요구형 어미를 intent 파서가 협박으로 읽어 fear 테이블
  급증(1→34)·DISMISS 반응, nano relationSignal 도 그 맥락에 눌려 NONE.
  BONDED 충족 상태에서 고백이 통째로 증발했다. 해소는 L1+L2 층위
  (world-boundary 관례): `detectConfessionIntentL1` 명시 문형 결정론 감지
  → intent THREATEN→TALK 강등 가드 + 워커 신호 L1 폴백. 재시도에서 nano 는
  여전히 NONE 이었고 **L1 폴백이 실제 성사 경로**였다 — nano 단독 의존이면
  이 기능은 죽어 있었다.
- **연인 재회에 "손님" 호칭** (640e336) — R4 권장 호칭(speechStyle 최빈
  "손님")이 관계를 몰라 kind=ROMANCE 재회에도 "어서 오세요, 손님".
  ROMANCE+통성명이면 R4 줄을 이름 호명 지시로 값 교체.

미수행: 거절·romanceable=false 경로의 실런 (판정은 코어 스펙 22케이스로
검증 — 실런은 호감 축적 비용 대비 실익 낮아 보류). CAS 충돌 재시도 시
`[RelationSignal]` 로그가 2회 찍힐 수 있으나 최종 상태는 단일 기록 — 무해.

### 0.2 R2·R3 구현 기록 (2026-08-26, server 4b1204b · client 80f1a9d)

**R2 (지속성·일상 반영 — 전부 기존 줄 값 교체·기존 게이트 준수):**

- **관계 깊이 가이드 kind-aware** — encCount 사다리보다 유형이 지배.
  연인인데 "재회 — 얼굴을 기억함" 거리감이 주입되던 모순 차단.
- **잡담 턴 관계 사건 소재** — `latestRelationTopic`(마일스톤→소재어, 최근
  12턴 window — 매 턴 같은 줄 = anchor 라 기억은 자연히 옅어지게). 입력
  화제 유지 턴 제외 (B4 화자 주도 화제 경쟁과 동일 사유). 소재어 정본
  `RELATION_MILESTONE_TOPICS` (불변식 50 — 완성 문장 금지).
- **제3자 인지 `[주변의 눈]`** — 잡담 화자의 npcRelations 에 플레이어의
  연인 NPC 가 있으면 "눈치채고 있다" 1줄 (놀림·축하·걱정, 강요 금지).
  질투·삼각은 비범위 유지. 헤더 드리프트 가드 등재.

**R3 (UI):** `ui.npcEmotional` 에 relationTierLabel(낯섦/안면/가까움/각별)·
relationKindLabel(연인/벗/막역한 벗/맞수/원한)·relationMilestones 추가 —
라벨 정본은 서버(`RELATION_KIND_LABELS` 등), 클라 NpcDossierTab 은 dumb
렌더(배지 2종 + 관계 기록 패널). 수치 임계 비노출.

실런 확인(run bf90c097 T16): UI 번들 `연인/각별/[서로 마음을 확인한 일 T13]`
정확 + 서술 이름 호명·연인 톤 유지. 소재·제3자 라인은 발화 조건이 확률적이라
코드 경로/단위 스펙으로 검증 (잡담 게이트 켜진 턴 + window 내 한정).

잔여(후속 후보): SummaryBuilder 여정 아카이브 관계 요약 1줄 · GRUDGE/RIVAL
실런 · daily_topics 와 관계 소재의 경합 관측.

## 1. 배경 — 무엇이 되고 무엇이 안 되나 (2026-08-26 실측)

이날 구축·실증된 기반:

| 축 | 상태 | 실증 |
|---|---|---|
| 감정 5축 (trust/fear/respect/suspicion/**attachment**) | ✅ 영속·감쇠 | 대시 5턴에 trust 45→73, attach 12→43.9 |
| 관계 티어 4단 (낯섦→말트임→친밀→각별) | ✅ 프롬프트+nano 배선 | BONDED 힌트로 애정 표현 수용 실증 |
| APPROACH 행동화 (NPC가 먼저 다가옴) | ✅ trust42/attach5 | arch/76 실증 완료 |
| 완급 반응 | ✅ 창발 | 칭찬·고백·데이트 환영, 포옹 DEFLECT, 스킨십에 fear/susp 동반 상승 |
| 개인 기억·통성명·재회 호명 | ✅ | arch/91 |

**격차 (이 문서의 대상):**

1. **관계 유형이 없다** — 깊이(티어)만 있고 성격이 없다. 같은 BONDED라도 전우·연인·은인이 구분되지 않아, 고백을 받아줘도 "친밀한 지인"의 연출로 수렴한다.
2. **마일스톤이 없다** — 고백 수락이 상태로 남지 않는다. 다음 세션에 LLM은 그 사건을 개인 기억 한 줄로만 안다.
3. **관계의 일상 반영이 없다** — 재회 인사·잡담·다른 NPC의 반응(질투·소문)이 관계를 모른다.
4. **UI 노출이 없다** — 인물 탭에서 감정·관계를 볼 수 없어 플레이어가 진행감을 확인할 길이 없다.

## 2. 설계 원칙

- **서버 결정론 우선 (불변식 1·2)**: 관계 유형·마일스톤 전이는 서버 순수 함수가 판정한다. LLM(nano)은 신호 감지만 하고, 역류는 CAS 3조건(하드 금지·CAS 경유·불변식 2 목록 등재)을 지킨다.
- **프롬프트 순증 0 (불변식 17)**: 신규 블록 금지 — 기존 티어 힌트 줄의 **값 교체**로 관계 유형을 표현한다. V12 게이트 통과를 커밋 조건으로 건다.
- **콘텐츠 리터럴 금지 (불변식 45)**: NPC별 관계 성향(연애 가능 여부·우정 전용 등)은 npcs.json 필드로 저작한다.
- **세이프티 불변 (arch/106)**: SEXUAL_EXPLICIT 차단 유지. 관계 유형은 순애 연출까지만 연다.

## 3. Phase R1 — 관계 유형 + 마일스톤 (서버 상태)

### 3.1 상태 스키마 (NPCState 확장)

```ts
relationship?: {
  kind: 'FRIEND' | 'CONFIDANT' | 'ROMANCE' | 'RIVAL' | 'GRUDGE';
  sinceTurn: number;
  milestones: Array<{ type: RelationshipMilestone; turnNo: number }>;
  // CONFESSION_ACCEPTED | CONFESSION_DECLINED | FIRST_GIFT | RECONCILED | BETRAYED …
}
```

- 티어(파생값, 매턴 재계산)와 달리 **kind는 사건으로 전이되는 실상태**다.
- 전이 정본은 `relationship-kind.core.ts` 순수 함수 — 신호(아래) + 감정 임계 + NPC 저작 성향으로 판정.

### 3.2 신호 감지 (nano) — 새 역류 경로

- ChallengeClassifier 또는 NpcReactionDirector에 `relationSignal` 축 추가: `CONFESSION | DEEP_TRUST | HOSTILE_BREAK | NONE`.
- **판정은 서버**: 예) CONFESSION 신호 + 티어 BONDED + NPC `romanceable=true` + fear<40 → `CONFESSION_ACCEPTED` 마일스톤 + kind=ROMANCE. 조건 미달이면 `CONFESSION_DECLINED` + 쿨다운(재고백 N턴 제한 — 스팸 방어).
- 불변식 2의 소프트 상태 목록에 `relationSignal` 등재 (CAS 경유).

### 3.3 콘텐츠 저작 (팩별)

```jsonc
// npcs.json
"relationProfile": { "romanceable": true, "friendCapacity": "open" }
```

- 미저작 시 기본: romanceable=false (기혼·성직 등 세계관 보호), friend=open.
- audit_content L2에 모양 검사 추가 (사문 배선 방지 — arch/21 Part 11 교훈).

### 3.4 프롬프트 (순증 0)

- 티어 힌트 줄을 kind-aware로 교체: BONDED+ROMANCE → "연인 사이 — 애정 표현이 자연스럽고, 서로의 안위를 먼저 챙긴다". BONDED+FRIEND → "믿는 벗 — 속내를 터놓고 농을 주고받는다".
- nano 관계 단계 줄도 동일 값 교체.

## 4. Phase R2 — 지속성·일상 반영

- **재회 인사 kind-aware**: arch/91 재회 경로에 관계 유형 반영 (연인 재회 ≠ 친구 재회).
- **관계 파생 잡담**: daily_topics가 아니라 **상태 파생 화제** 1종 추가 (콘텐츠 아님 — "지난 약속" 마일스톤 참조). 잡담 게이트(불변식 44) 화이트리스트 유지.
- **제3자 인지 (선택)**: npcRelations 보유 NPC가 관계를 화제로 언급 (소문 1줄). 질투·삼각은 비범위 (창발에 맡김).
- **감정 균형 유지**: 과한 대시 → fear/susp 상승 → CONFESSION 거절·GRUDGE 전이 경로가 자연 밸런스 (이미 창발 실증, 임계만 스펙화).

## 5. Phase R3 — UI 노출

- NpcDossierTab: 관계 단계(티어)·유형·주요 마일스톤 표시. 감정 수치는 비노출(게임성 — 수치 노출은 메타게임 유발) — 서술형 라벨만.
- 여정 아카이브(ending_summary)에 관계 요약 1줄 (SummaryBuilder).

## 6. 비범위 (명시)

- NPC 동행(follower) — 별도 트랙 (프롬프트·이동·전투 파급이 커서 분리).
- 성적 묘사 개방 — arch/106 불변.
- 결혼·동거 등 생활 시뮬 — 런 수명(15~40턴)과 부정합.

## 7. 검증 게이트

- 코어 스펙: relationship-kind 전이 전수 (수락/거절/쿨다운/성향 게이트).
- 실런: ① 고백→수락→**다음 세션 재회에서 연인 톤 유지** (지속성이 핵심 검증) ② 거절 경로 ③ romanceable=false NPC의 정중한 거절.
- V12 게이트 (프롬프트 재비대) + 어체·마커 기존 게이트.

## 8. 구현 순서 제안

R1(코어+신호+저작 필드, 서버) → 실런 게이트 → R2(재회·잡담) → R3(UI). 각 단계 독립 배포 가능.
