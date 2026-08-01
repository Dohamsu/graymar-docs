# 96. 런 중 저장 이미지 인라인 삽입 — A+C 단계 결합 설계

> 상태: ✅ 구현됨 (2026-08-01 — §7 구현 기록). 소유자 결정: 3안 중 **A+C 단계 결합** 채택.
> 소유자 비전 확정: "상황 이미지를 미리 생성·태그화해 폴더에 넣으면 서술 태그 매칭으로 자동 삽입" —
> Phase C의 1급 소스 = **소유자 사전 제작 장면 컷 풀** (`content/<pack>/assets/scenes/`).
> B(유저 수동 삽입 + 런 갤러리)는 폐기가 아니라 직교 후속 — 과금 부가가치(이미지) 트랙에서 별도 설계.

## 1. 목표와 비목표

**목표**: 이미 저장되어 있는 이미지 자산(팩 에셋·scene_images)을 서술 흐름 **안에** 삽입해,
정해진 위치(장소 헤더·초상화 카드·배경 레이어)에만 뜨던 시각 요소를 서사의 리듬 포인트로 확장한다.

**비목표**:
- 이미지 **생성**은 다루지 않는다 — scene-image 생성 기능은 봉인 유지 (비용 통제).
- 유저 수동 삽입(B안)·엔딩 앨범은 후속 트랙.
- 배경 레이어(arch/93)·초상화 카드(기존)는 그대로 — 본 설계는 **서술 로그 내 인라인 컷** 전용.

## 2. 자산 인벤토리 (삽입 소스)

| 소스 | 위치 | 선별 기준 |
|------|------|----------|
| 장소 이미지 | `client/public` 팩 에셋 (arch/80 sync, 시간대 힌트 보유) | 현재 장소 + timePhase 매칭 |
| NPC 초상화 | 팩 에셋 + runState 배정분 (`portrait_XX.webp`, 런 내 고정) | **배정된 것만** — 풀 비면 무동작 (arch/80 원칙 준수) |
| 아이템 아이콘 | `client/public/items/<itemId>.webp` (guides/10 3층 프로세스) | RARE 이상 획득 시 |
| AI 장면 이미지 | `scene_images` 테이블 (run×turn, imageUrl) | 해당 런에서 과거 생성분만 (Phase C 재사용 후보) |

## 3. Phase A — 이벤트 트리거 자동 삽입 (결정론)

### 3.1 트리거 표 (초기 4종 — 과다 삽입은 소음, 보수적으로 시작)

| 트리거 | 시점 | 이미지 | 빈도 제어 |
|--------|------|--------|----------|
| 장소 첫 진입 | MOVE_LOCATION 커밋 (턴 응답) | 장소 이미지 (시간대 매칭) | 런 내 장소당 1회 (재진입 생략) |
| NPC 자기소개 성사 | 워커 introduced 확정 (llm 완료 페이로드) | 배정 초상화 | NPC당 1회 (소개는 원래 1회) |
| RARE+ 아이템 획득 | LOOT 이벤트 커밋 (턴 응답) | 아이템 아이콘 | 아이템당 1회 |
| 엔딩 진입 | RUN_ENDED 턴 | 거점/피날레 장소 이미지 | 런당 1회 |

### 3.2 서버 — 부착 지점 2개

**① 턴 커밋 시점** (이동·아이템·엔딩 — 결정론 데이터, LLM 무관):
`ServerResultV1.ui.inlineImages: Array<{ kind: 'LOCATION'|'ITEM'|'ENDING'; url: string; caption: string; refId: string }>`
— 기존 `ui.questReveal`·`ui.shops`와 동렬. turns 테이블에 저장되므로 스토리 로그 복원 시 재현.

**② 워커 완료 시점** (NPC 소개 — introduced는 LLM 후 확정):
llm 완료 페이로드에 `llm.ui.inlineImages`로 동일 스키마 부착. 폴링·SSE 완료 이벤트 양쪽에 포함.
runState 반영이 필요한 중복 방지 카운터(`insertedImageRefs`)는 **CAS 경유** (불변식 2 — 소프트 상태 목록에 등재 필요).

**공통 규칙**:
- URL은 ContentLoader 파생 API·runState 배정에서만 온다 — 엔진 코드에 콘텐츠 경로 리터럴 금지 (불변식 45).
- 미소개 NPC 초상화는 절대 삽입하지 않는다 (이름 비공개 원칙 — 불변식 15와 정합).
- 턴당 최대 1장 (복수 트리거 동시 발화 시 우선순위: 소개 > 엔딩 > 장소 > 아이템).

### 3.3 클라이언트

- `StoryMessageType`에 `IMAGE` 추가하지 **않고**, NARRATOR/RESOLVE 메시지에 `inlineImages` 필드를 얹어
  StoryBlock 하단에 캡션 컷으로 렌더 (메시지 타입 신설보다 회귀 면적이 작다).
- 렌더: 서술 블록 말미, 최대 폭 제한 + 캡션 (`장소명`, `NPC 표시명` 등), lazy 로딩, 
  arch/93 배경 레이어와 시각 충돌 없게 카드형 (반투명 배경 위 불투명 컷).
- 이미지 로드 실패 시 조용히 생략 (onError hide — 404가 UI를 깨지 않게).

### 3.4 계측·게이트 (Phase C 진입 관문)

- 삽입 빈도: 평균 N턴당 1장 이하 유지 (목표 ≤ 1/4턴 — 소음 방지).
- 플레이테스트 10~15턴 × 2팩에서: 삽입 시점 위화감 0건, 초상화 오귀속 0건, 로그 복원 재현 100%.
- 통과 시 Phase C 착수.

## 4. Phase C — nano 문맥 매칭 자동 삽입 (관문 통과 후)

### 4.1 구조

1. **태그 인덱스** (팩 로드 시 1회 구축): 이미지별 `{url, kind, tags[]}` — 팩 에셋 파일명 힌트
   (`day/night`·키워드, arch/80)와 장소·NPC 연결, scene_images는 `promptUsed`에서 키워드 추출.
2. **매칭 시점**: 워커에서 서술 확정 후 nano 1콜 — 입력: 서술 요약 + 후보 태그 목록(현재 장소·등장 NPC로 사전 필터한 상위 ~10개), 출력: `{refId | none, confidence}`.
3. **채택 게이트**: confidence 임계 미달·후보 0개면 무삽입 (억지 삽입 금지 — 불변식 47의 정합 원칙과 동형).
4. **빈도 제어**: 쿨다운 3턴 + 런 내 같은 이미지 재사용 금지 + Phase A 트리거와 같은 턴이면 A 우선.

### 4.2 안전장치

- 킬스위치: `INLINE_IMAGE_MATCH_DISABLED=1` (기존 킬스위치 패턴).
- nano 실패·타임아웃 = 무삽입 (턴 진행 무영향 — LLM narrative-only 원칙).
- 오매칭 계측: 플레이테스트 센서 신설 (삽입 이미지 kind vs 서술 내 장소/화자 대조) — 오매칭률 >5%면 임계 상향 또는 봉인.

### 4.3 비용

nano 1콜/삽입 후보 턴 ≈ $0.0002 (~0.3원). 쿨다운 적용 시 런당 3~5콜 수준 — 무시 가능.

## 5. 구현 순서 (예상 2~2.5일)

1. **A-1** 서버: ui.inlineImages 스키마 + 이동/아이템/엔딩 트리거 (턴 커밋 경로) — 0.5일
2. **A-2** 서버: 소개 트리거 (워커 경로 + CAS insertedImageRefs) — 0.25일
3. **A-3** 클라: StoryBlock 인라인 컷 렌더 + 복원 재현 — 0.5일
4. **A-4** 검증: 플레이테스트 2팩 + 관문 판정 — 0.25일
5. **C-1~3** 태그 인덱스 → nano 매칭 → 센서·튜닝 — 1일 (관문 통과 후)

## 6. 미결·후속

- B안(유저 수동 갤러리): 과금 부가가치 트랙에서 별도 설계 — 본 설계의 ui.inlineImages 스키마를 그대로 재사용 가능 (source: 'USER' 확장).
- scene-image 생성 봉인 해제 여부: Phase C에서 저장분 재사용 효과를 본 뒤 판단.
- 파티 모드: Phase A는 리더 런 기준 동일 동작 (파티 분기 없음), C는 파티 검증 별도.

## 7. 구현 기록 (2026-08-01)

**Phase A 재정의**: 착수 시 실사에서 장소 진입 컷(`StoryMessage.locationImage` — LOCATION_ENTER 태그)과
NPC 소개 초상화 카드(`ui.npcPortrait` 워커 reconcile)가 **이미 구현·배포 상태**임을 확인.
잔여였던 RARE+ 아이템·엔딩 컷은 소음 우려로 보류(후속 판단) — Phase A는 기구현 인정으로 종결.

**Phase C 구현 (본체)**:
- 투입: `content/<pack>/assets/scenes/` + `sync_pack_assets.py` scenes 카테고리 확장
  (파일명 토큰 = 태그, day/night → `time` 필드 분리, `SCN_NN` 안정 id, ASCII 슬러그 정규화).
  graymar_v1에 시드 컷 3장 (장소 이미지 재활용 — 소유자 제작 컷으로 교체 예정).
- 서버: `SceneCutMatcherService` (llm/) — 3단 게이트:
  ① 프리필터 (킬스위치·MOVE 턴(LOCATION_ENTER 태그, 클라 locationImage 기준과 동일 신호)·
  쿨다운 3턴·런 내 usedIds·시간대) ② **렉시컬 프리스크린** (태그가 서술/장소명에 부분 등장하는
  후보만, 겹침 0이면 nano 미호출 무삽입 — 억지 매칭 차단+비용 절약) ③ nano 판정
  (`scene-cut-match` 스테이지, confidence ≥ `SCENE_CUT_MIN_CONFIDENCE` 기본 0.65).
- 워커 배선: DONE 커밋 직전 매칭 → `ui.sceneCut` serverResult UPDATE(npcPortrait reconcile 패턴)
  → `runState.sceneCutState{lastTurn, usedIds}` CAS (불변식 2 소프트 상태 등재).
- 전달 3경로: 스트림 done 이벤트 payload / 폴링 turn detail serverResult / 이력 복원
  (runs.service 턴 프로젝션 `sceneCut` 필드).
- 클라: `StoryMessage.sceneCut` → StoryBlock NARRATOR 하단 비네팅 컷 렌더 (로드 실패 무해).
- 검증: 단위 11케이스 (게이트 전수) + 실런 E2E — 시장 소란 서술에서 SCN_02 발화·쿨다운 차단·
  복원 렌더 스크린샷 확인. 전체 스위트 1,637 통과.

**env**: `INLINE_IMAGE_MATCH_DISABLED=1` (킬스위치) · `SCENE_CUT_MIN_CONFIDENCE` (기본 0.65).

**확장 (2026-08-01 2차) — 인물·장소 후보 편입**: 매칭 풀을 scenes 단일에서
scenes ∪ 인물(서술 등장 + introduced NPC의 배정 초상만 — 불변식 15 호출측 필터,
소개 카드 턴 제외, `POR_<npcId>` 런당 1회) ∪ 장소(팩 매니페스트 locations 중
**현재 장소** 매칭 엔트리만, `LOCIMG_n`)로 확장. 프리스크린에서 인물·장소는 서술
본문 등장만 인정(장소명 보너스는 scene 전용 — 상주 장소 컷의 매 턴 후보화 방지).
nano 프롬프트에 종류 라벨(장면/인물/장소)과 종류별 채택 기준 주입. 단위 15케이스.
제작 가이드: [[../guides/11_scene_cut_guide|guides/11]].

**후속**: ① 오매칭 계측 센서 (플레이테스트) ② B안 갤러리 ③ 아이템·엔딩 컷 재검토.
