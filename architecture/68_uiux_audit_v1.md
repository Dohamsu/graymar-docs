# 68. UI/UX 실사 리뷰 v1 — 헤드리스 순회 + 6건 수정

- 날짜: 2026-07-12
- 방법: gstack browse 헤드리스 Chromium으로 신규 유저 경로 전체 순회
  (가입 → 캐릭터 생성 6단계 → 프롤로그 → HUB → LOCATION 자유 입력 턴 →
  사이드패널 5탭 → 모바일 375px / 태블릿 768px), 스크린샷 31장, 콘솔 에러 0.
- 배경: 로직 안정화(완주 2연속 9/9, arch/67) 이후 UI/UX 트랙 전환의 첫 작업.
  엔진 성숙도 대비 클라이언트는 기능이 누적된 구조라 정보 설계·일관성 실사가
  한 번도 없었다.

## A. 발견 → 수정 6건

### A-1. 인물 도감 43명 전원 노출 (심각도 1위)

- 증상: 2턴 시점 실제 조우 2명(로넨·노부인)인데 인물 탭이 "만난 인물 (43)"으로
  팩 전체 NPC를 그리드 표시. 별칭 방어는 작동하나 미조우 인물 노출 자체가
  스포일러 + encounterCount 기반 점진 발견 시스템 무력화.
- 원인: `turns.service.ts` npcEmotional UI 조립이 `npcStates` 전체를 매핑
  (npcStates는 createRun 시 팩 전원 초기화 — Living World 불변식 22).
  클라 `NpcDossierTab`은 "npcEmotional에 있으면 만난 것"으로 가정.
- 수정: 조립에 조우 필터 적용 —
  `(encounterCount ?? 0) >= 1 || (appearanceCount ?? 0) >= 1`
  (직접 대면 또는 서술 @마커 등장).
- **연쇄 발견 — 이어하기 복원 갭**: 필터 검증 중, 마지막 턴이 이동/HUB 턴이면
  `ui.npcEmotional`이 실리지 않아(판정 결과 빌더에서만 조립) 새 세션 도감이
  "만난 인물이 없다"로 비는 기존 갭 확인 (43명 문제에 가려져 있던 것).
  → `GET /v1/runs/:runId` 응답에 `npcEmotional`을 runState.npcStates 기반으로
  동일 기준 조립해 포함 (`runs.service.ts`, getNpcDisplayName 재사용으로
  실명/별칭 공개 상태 반영), 클라 `resumeRun`이 복원.
- 검증: 실런 도감 "만난 인물 (3)" — 로넨·미렐라 실명, 미소개 에드릭
  "날카로운 눈매의 회계사" 별칭. 재접속 복원도 동일.

### A-2. 모바일 핵심 상태 확인 불가

- 증상: 모바일 헤더는 위치 텍스트만, 캐릭터 화면에도 HP 없음 —
  모바일에서 HP/STA/골드/시간을 볼 경로가 전무.
- 수정: `MobileHeader`에 2행 상태줄(`MobileStatusRow`) 추가 —
  HP 바+수치 / STA 바+수치 / 골드 / TimePhaseIndicator.
  헤더 자동 숨김과 함께 translateY로 움직임. 비-이야기 탭 스페이서
  h-12 → h-20, 드롭다운 top 보정.

### A-3. 모바일 메뉴 인물 탭 부재

- 증상: 데스크톱 5탭(캐릭터/장비/소지품/인물/퀘스트) 대비 모바일 메뉴는
  4항목 — NPC 도감 접근 경로 없음.
- 수정: 햄버거 메뉴에 🎭 인물 추가 + `mobileTab === "npcs"` 분기에서
  `NpcDossierTab` 렌더.

### A-4. 호외 모달이 판정 연출을 가림

- 증상: 판정 성공 배너·주사위·서술 스트리밍 시작 순간 "그레이마르 호외"
  모달이 자동 팝업해 전부 덮음 — 플레이어 행동 결과보다 신문이 먼저.
- 수정: NewsModal 렌더 게이트에 `!isNarrating && !isSubmitting &&
  !choicesLoading` 추가. pendingNewsSignals는 유지되므로 서술 완료 시 등장.

### A-5. "(으)로" 조사 병기 노출

- 증상: 이동 시스템 메시지 "시장 거리(으)로 향한다/이동했다" 등 노출 7곳.
- 수정: `common/korean.ts` `korParticleRo`에 ㄹ받침 예외 추가('마을'→'마을로'),
  서버 5곳(turns 이동 커밋 2·격화 경고·node-transition·party vote) +
  클라 2곳(VoteModal·StartScreen) 치환. 클라용 `client/src/lib/korean.ts` 신설
  (서버와 동일 로직).
- 검증: 실런 "시장 거리로 향한다." / "시장 거리로 이동했다."

### A-6. 개발자 정보 일반 노출

- 증상: 헤더 `P:8734 C:7360 1620ms` 디버그 배지 상시 표시, 설정 모달에
  Provider/Model/Fallback + LLM 과금 현황(턴별 원화) 노출.
- 수정: 두 영역 모두 `process.env.NODE_ENV !== "production"` 게이트 —
  프로덕션 빌드에서 트리쉐이킹 제거, 로컬 dev에선 유지.
  Client/Server 버전 해시 푸터는 지원 문의용으로 존치.

## B. 리뷰에서 확인된 강점 (유지)

- 프롤로그 진입 즉시 타이핑 시작 (로딩 체감 0), 대기 신호
  ("서술 표시 중… 완료되면 선택지와 입력이 활성화됩니다") 명확.
- 판정 성공 배너 + 스탯 태그 선택지 + 대사 버블/초상화 + 퀘스트 탭
  (D-day·세력 관계·시한) 완성도 높음.
- 지난 평가의 "온보딩 부재" 우려는 프롤로그가 상당 부분 해소 —
  남은 갭은 자유 입력 발견성(placeholder 한 줄) 정도.

## C. 잔여 관찰 백로그

| # | 항목 | 상태 |
|---|------|------|
| C-1 | HUB에서 자유 입력창 미렌더 (선택지 전용) | ✅ 부록 B — A안(거점 사랑방 개방)으로 해소 (2026-07-12) |
| C-2 | 선택지 어포던스 | ✅ 부록 A-1 (2026-07-12) |
| C-3 | 시나리오 선택 화면 빈약 | ✅ 부록 A-2 |
| C-4 | 스탯 무지개 색상 | ✅ 부록 A-3 |
| C-5 | 스탯 라벨 깨짐·혼용 | ✅ 부록 A-4 |
| C-6 | 모바일 메뉴 이모지 아이콘 | ✅ 부록 A-5 |
| C-7 | 체크박스 기본 스타일 | ✅ 부록 A-6 |

## 부록 A — C-2~C-7 수정 (2026-07-12, 클라 단독)

### A-1. 선택지 어포던스 (C-2) — 접근성 절반은 오진

재조사 결과 선택지는 이미 `<button>` + aria-label/busy/disabled +
포커스 관리(choiceRegionRef) 완비 — 리뷰 시 browse `snapshot -i`가
@c(cursor-interactive)로 분류한 것은 수집 특성의 착시였다. 실제 문제는
**rest 상태가 서술 텍스트와 구분 안 되는 것**뿐 → `.choice-btn`에
골드 테두리 `rgba(201,169,98,0.18)` + 배경 `0.04` 추가 (globals.css).

교훈: 접근성 트리 스냅샷 도구의 분류를 그대로 믿지 말고 DOM
(`tagName`/`focus()`) 실측으로 재확인할 것.

### A-2. 시나리오 카드 배너 (C-3)

`getScenarioBannerImage(scenarioId)` 신설 (location-images.ts) —
graymar_v1 → `graymar_overview.webp`, silverdeen_v1 → null.
카드 상단 h-36(sm:h-44) 배너: 이미지면 cover+호버 줌, null이면
그라데이션 fallback(카드 높이 대칭 유지). 팩 추가 시 매핑 한 줄.

### A-3. 스탯 뮤트 앤틱 팔레트 (C-4)

globals.css `--stat-str~cha` 토큰 신설: `#C0625A`(테라코타)
`#C9A962`(골드) `#8FAC7E`(세이지) `#7291AC`(스틸블루)
`#A08CC0`(라벤더) `#C08A9B`(로즈). 색 구분성(선택지 스탯 태그 매칭)
유지, 원색 채도만 제거. **중복 3곳 수렴**: STAT_COLORS
(stat-descriptions.ts, 정본) ← StartScreen STAT_COLORS_MAP(파생) ·
PresetCard 인라인(제거) · game-store fallback(토큰 참조).

### A-4. 스탯 라벨 정리 (C-5)

- 출신 카드 "카리스 마" 줄바꿈: 라벨 폭 w-8 → w-12 + whitespace-nowrap.
- 레이더 차트 STR/DEX/... → 힘/민첩/재치/체질/통찰/카리스마 (카드와 통일).
- 연쇄 발견: 1단계 하단 범례가 "지력/지각/매력"이라는 **제3의 명칭** 사용
  → 정본(STAT_KOREAN_NAMES) 명칭으로 통일.

### A-5. 모바일 메뉴 lucide 전환 (C-6)

📖👤🎒🎭📜 → BookOpen/User/Backpack/Users/ScrollText (size 15,
활성 탭 골드).

### A-6. 골드 체크박스 (C-7)

`accent-color`는 checked 색만 바꾸고 미체크 흰 네모가 남음 →
`.checkbox-gold` (appearance:none, 다크 배경+테두리, checked 시 골드
채움+다크 체크 SVG data URI, hover/focus-visible 링) 신설.

### 검증

클라 빌드 통과·린트 에러 0. 헤드리스 실측: 체크박스 checked 상태,
출신 카드 팔레트+한 줄 라벨+범례, 확인 화면 한글 레이더, 시나리오
카드 배너(그레이마르 이미지/실버딘 그라데이션), 모바일 메뉴 아이콘,
선택지 카드 어포던스(데스크톱·모바일) 스크린샷 확인.

## D. 검증 요약

- 서버·클라 빌드 통과, 서버 유닛 1034 passed / 실패 0, 클라 린트 에러 0
  (경고 4건은 기존 `<img>`·PRESETS 건).
- launchd 재시작 후 실플레이 검증: A-1(도감 3명+별칭+복원), A-2(상태줄),
  A-3(인물 탭), A-5(조사) 직접 확인. A-4·A-6은 코드 게이트 검증.

## 부록 B — C-1 해소: 거점 사랑방 개방 (A안, 2026-07-12)

### 배경 판단

HUB 자유 입력은 클라 누락이 아니라 **서버 계약**이었다 —
`handleHubTurn`이 CHOICE 외 입력을 하드 거부(`HUB requires CHOICE input`),
초기 설계(순환 허브 = 이동·정비 전용)의 의도적 제약. 자유 대화
파이프라인(IntentParserV2→NpcResolver→EventDirector→Resolve)의 요구
컨텍스트(NPC 배치·이벤트 매칭·locationSessionTurns·동적 상태)가 전부
장소 단위라, HUB에 ACTION을 여는 것은 별도 경량 파이프라인 신설을 의미.

검토안: A) 거점 사랑방 장소 개방(콘텐츠 1줄) / B) HUB ACTION 경량 허용
(판정·fact 없는 겉대화 위험) / C) HUB 자체를 장소화(순환 설계 파괴).
**A 채택** — 기존 LOCATION 자산 100% 재사용, HUB 리듬 유지, 롤백 1줄.

### 구현 (서버 코드 0줄)

- `graymar_v1/locations.json` LOC_TAVERN: `hubAccessible: true` +
  hubHint "휴식과 대화, 정보가 모이는 곳". 이미 정식 장소로 완비
  (SOCIAL/REST/INFORMATION 태그, secrets 1, 이벤트 11, NPC 배치 32참조,
  이미지 tavern_day/night_safe) — 개방만 잠겨 있던 상태.
- `silverdeen_v1/locations.json` LOC_SD_INN(잿빛 램프 여관, HUB/SAFE):
  동일 적용 — 팩 계약 대칭 (거점 사랑방 1곳 규약).
- 클라 `InputSection`/`MobileInputSection`: HUB에서 `return null` →
  `HubInputNotice` 배너("거점에서는 행선지를 선택하세요 — 대화와 행동은
  장소에 들어가 자유롭게 입력할 수 있습니다").
- `go_tavern` choiceId는 hubChoiceIdFor() 기계 파생 — 서버 무수정.

### 검증 (실측)

HUB 5번째 선택지 등장 + 안내 배너 → 선술집 진입(서빙꾼 선인사) →
자유 입력 "항구 소문을 물어본다" → 판정(카리스마2+🎲2+보정1=5 SUCCESS)
+ 주제 정합 응답 스트리밍. LOCATION 파이프라인 전체 정상.

### 수용한 트레이드오프

선술집 방문도 LOCATION 턴 — 시간대·D-day 시계 소모. 휴식·정보 수집에
시간을 쓰는 자연스러운 교환으로 판단 (데드라인 경제 유지).

## 부록 C — 자유 입력 발견성 (2026-07-12, 클라 단독)

리뷰 §B에서 남긴 마지막 갭("자유 입력 발견 장치가 placeholder 한 줄뿐")
해소. 신규 플레이어의 '선택지 클릭 게임' 오해 방지 — 3층 구성:

1. **첫 LOCATION 1회 코치마크** — 입력창 위 인라인 골드 배너
   "선택지가 전부가 아닙니다. 하고 싶은 행동을 문장으로 직접 입력해
   보세요 — 대화·조사·잠입·거래 모두 이야기에 반영됩니다."
   닫기 버튼/입력창 포커스로 소멸, `graymar:free-input-hint-v1`
   localStorage 플래그로 재노출 차단. 모달이 아니라 흐름 무간섭.
2. **placeholder 예시 로테이션** — "행동을 입력하세요..." →
   "원하는 행동을 입력하세요 — 예: 수상한 자를 미행한다" 등 4종 중
   마운트당 랜덤 1개 (상시 저강도 암시). COMBAT 문구는 유지.
3. **시작 튜토리얼 보강** — 능력치 안내 메시지 말미에
   "선택지는 제안일 뿐 — 하고 싶은 행동을 입력창에 문장으로 직접
   쓸 수 있습니다." 1줄 추가 (game-store).

구현 노트: dismiss 상태는 `useSyncExternalStore`(localStorage 원본 +
탭 내 구독자 셋) — 레포 린트가 effect 내 동기 setState를 에러로 막아
정석 패턴 채택. 서버 스냅샷 true(숨김)로 SSR 안전, 데스크톱/모바일
입력창이 스토어 공유(한쪽 닫으면 양쪽 소멸).

검증: 노출→예시 placeholder→닫기 소멸→플래그 기록→포커스 dismiss
실측, 빌드·린트 에러 0.

## 부록 D — NanoChoiceNpcFix: nano 선택지 NPC 오염 교정 (2026-07-12)

버그 리포트 `5f31d803`(2026-07-12, narrative) 분석·수정.

### 증상 → 근본 원인

정보상과 대화 연속 중(T5~T6 primaryNpcId=NPC_INFO_BROKER) 선택지
"그의 말을 더 듣고 싶다"(nano_6_1) 클릭 → T7 화자·마커·초상이 전부
에드릭으로 점프. DB 대조로 오염원 확정: **NanoEventDirector가 해당
선택지에만 `sourceNpcId: NPC_EDRIC_VEIL`을 배정** (같은 턴 나머지 2개는
정보상으로 정합 — 장부 주제의 컨텍스트 오염 추정). 이후 NpcResolver
Step 0(CHOICE_EXPLICIT)이 payload를 신뢰해 엔진은 정합하게 에드릭 처리.
Step 0의 전제("선택지 payload = 플레이어 의도")가 nano 출력 오염으로
깨진 사례 — CLAUDE.md LLM 원칙 "nano 출력은 서버 검증" 미적용 지점.

### 수정 (A안 — 서버 검증 게이트)

`llm-worker.service.ts` finalChoices 확정 직전 단일 게이트(Track 1/2
공통 커버). `sanitizeNanoChoiceNpcsCore` (export 순수 함수 — spec 직접
import, 복제 drift 방지):

- 조건: 이번 턴 parsedType ∈ 대화 계열(TALK/PERSUADE/BRIBE/THREATEN/HELP,
  잠금 유지 계열과 동일 집합) && actionContext.primaryNpcId 존재
- 교정: 대화 계열 선택지의 sourceNpcId ≠ 대화 상대 → 대화 상대로 교체
  + `[NanoChoiceNpcFix]` 경고 로그 (상시 센서)
- 예외: ① 라벨이 대상 NPC 이름/별칭/shortAlias 명시(지목형 — nano 배정
  존중) ② 작별 턴(5.12 npcFarewell 감지를 로컬 플래그로 공유 — 잠금 닫힘)

### 검증

- 유닛 7케이스 신규(`llm-worker.nano-choice-npc.spec.ts`) — 버그 원본
  페이로드 재현 교정 + 예외 5종. 전체 스위트 1041 passed / 실패 0.
- 실측: 서빙꾼 대화 연속 턴 nano 3종 정합 생성(게이트 무개입), 회귀 없음.
- 부수: 부록 B 선술집 개방으로 구 정책이 된 스펙("HUB 선택지 4곳") 1건을
  현행 5곳(go_tavern 포함)으로 갱신.

## 부록 E — 상점 노출 동선 (2026-07-12)

리뷰 관찰 항목 "상점 노출 0회(5개 런)"의 근본 원인 2건 수정.

### 원인 실측

1. **구매 경로 사망**: 상점 구매 처리는 `intent.actionType === 'SHOP'`만
   진입하는데 KW 파서는 구매 입력을 TRADE로 분류, LLM 파서는 SHOP을
   TRADE로 정규화(normalizeActionType — 이벤트 매칭용 리다이렉트).
   전 DB 실측: SHOP 인텐트 0건, `[상점]` 구매 이벤트 0건 — dead path.
2. **클라 미소비**: 서버가 매 LOCATION 턴 `ui.shops`(상점별 재고·가격
   지수)를 조립해 내려주는데 클라 소비처 0건 — 통째로 폐기되던 상태.

### 수정

- **서버** (turns.service): 구매 진입을 `isBuyIntent`로 확장 — SHOP 또는
  TRADE+구매 표현(`구매|구입|매입|사겠|사고 싶|사줘|산다|[을를] 사`).
  실패 안내(`[상점] 해당 물건을 구매할 수 없다`)는 현 장소에 상점이
  있을 때만 — 은유("정보를 산다") 오탐에는 침묵, 일반 TRADE 서사가 담당.
- **클라 3층 동선**:
  - store `shops` 상태 — uiBundle마다 갱신(필드 없으면 [] 클리어,
    장소 이탈 시 이전 장소 진열 잔류 방지) + resumeRun 복원.
  - 발견: LocationHeader 골드 칩("상점 N곳"/상점명, hover에 소지품 안내).
  - 접근: InventoryTab ShopSection — 상점별 품목(아이콘·rarity 색·
    가격·수량) + 구매 버튼이 `submitAction("〈이름〉을 구매한다")` 제출
    (자유 입력과 동일 ACTION 경로 재사용, 별도 구매 API 없음).
    골드 부족 disabled.

### 검증 (E2E)

시장 거리: 칩 "상점 2곳" → 소지품 탭 잡화점(4)·길드 상단(3) 진열
(100G 봉인 disabled) → 구매 클릭 → 판정 SUCCESS + 상인 서술("여기
15골드를 받겠소") → DB: `[상점] 하급 치료제를 15G에 구매했다.`
(**전 DB 최초의 상점 구매 이벤트**), 골드 95→80, 인벤 +1, 재고 차감.
유닛 1041 passed·빌드·린트 통과.

### 남긴 것

판매(sell) 경로는 미구현 그대로 (TRADE 서사 담당). 상점 UI에서의
판매 버튼은 수요 확인 후 별도 트랙.

## 부록 F — 3사이클 완주 프로세스 + 결정 4건 구현 (2026-07-12)

### 3사이클 결과 (완주 런 × 3)

| | 게이트 | 퀘스트 | 자체 수정 |
|---|---|---|---|
| 1 | 8/9→정밀화 후 무관 | S5_RESOLVE | audit V8 화자 오탐(대사 내 명사 '떠도는 말') — 대사 내부 제외+발화 동사형 한정 |
| 2 | 9/9 | S5_RESOLVE | 0 (NanoChoiceNpcFix 실전 2건 교정 — 부록 D 유효성 실증) |
| 3 | 9/9 | S5_RESOLVE | 0 |

S5 완주 3연속(이전: S3 조기 엔딩 2연속). 무명 실결함 0.

### 결정 4건 구현 (사용자 선택: 1-A·2-B·3-B·4-A)

- **4-A 봇 확장** (playtest.py): arc_* 최우선 클릭(1회) + ui.shops 확률
  구매(아이템당 1회) + LOCATIONS에 tavern. 신규 기능이 완주 회귀에 편입.
- **2-B 어휘 계측**: 종합 출력에 "어휘 반복 톱5" 상시 리포트(게이트 아님).
- **3-B 진입 인사 무명** — **B안 전제 정정**: 오웬은 4상 전부 선술집
  배치 완비. 실원인은 ACTION 이동(MOVE_LOCATION) 도착 턴이 도착
  디렉티브(NPC 대사 금지)의 inputType==='SYSTEM' 한정에 안 걸리는 구멍.
  → prompt-builder isMoveOnly를 MOVE 이벤트 기반으로 완화 (최소 수정).
- **1-A 아크 커밋 동선**: questState S3+ && currentRoute null이면 HUB
  선택지 선두에 노선 3종(`arc_commit_*`) 노출 — 라벨은 콘텐츠
  (arc_events.json routeCommitChoices, ContentLoader 파생 API). 클릭 시
  switchRoute + 결의 +2. 아크 자산 없는 팩(실버딘)은 자동 미노출
  (팩 계약 — 유닛 2케이스). handleHubTurn arc_commit_ 분기 +
  buildHubChoices/transitionToHub questState 배선.
- 파생 수정: 구매 입력의 파서 target 누락(TRADE, target='') 실측 →
  현 장소 재고 이름을 rawInput과 직접 대조해 보충.

### 통합 검증 (완주 런 9/9)

아크 커밋 T27(고발 노선) → **엔딩 "정의의 대가"** — 4런 연속
NONE("스쳐간 이방인")이던 arcRoute 12분기 에필로그 최초 진입.
상점 실구매 2건(치료제 15G + 장비 순찰대 경갑 55G), go_tavern 방문,
S5 완주. 유닛 1043 passed / 실패 0.

### 남은 관찰

- 어휘 클러스터(2-B 계측으로 추이 수집 — '그는/멀리서/것이오' 상위)
- 아크 커밋 라벨·결의 +2 밸런스는 실플레이어 데이터로 재조정 여지

## 부록 G — 선술집 상주 BG 초상화 6종 (2026-07-12, 사용자 제작)

이미지 커버리지 실측(초상화 29/43)에서 1순위로 추천한 **선술집 상주 BG
6명** — 사랑방 개방(부록 B)으로 대화 노출이 급증한 인물들. 사용자가
제작·투입, 매핑·검증은 세션에서 처리.

| 파일 | NPC | 비고 |
|------|-----|------|
| tavern_bard.webp | NPC_BG_BARD 비올라 | **여성 전환 + 개명**(구 단테) — 콘텐츠 참조 0건 확인 후 |
| tavern_cook.webp | NPC_BG_COOK 헬가 | **gender male→female 정정** (이름과 불일치하던 정본) |
| harbor_captain_pipe.webp | NPC_BG_CAPTAIN_OLD 그래디 | |
| veteran_swordsmith.webp | NPC_BG_ARMORER 갤러스 | |
| old_artificer.webp | NPC_BG_ANTIQUE_DEALER 제롬 영감 | |
| milo.webp | NPC_BG_WAREHOUSE_GUARD 마일로 | |

- 규격 1024×1280(4:5) 다크 유화 — 표시 위젯(도감 카드 110×140 등)이
  4:5라 원본 유지, 재인코딩 생략.
- 매핑 2곳: 클라 `data/npc-portraits.ts` + 서버 `db/types/npc-portraits.ts`
  (마커 URL 삽입용 — 양쪽 미러 규약).
- 실전 검증: 밤 선술집 "류트를 든 음유시인에게 노래를 청한다" →
  비올라 초상 버블·카드 표시 + 서술·nano 선택지 여성 지칭("그녀는…")
  정합 — 콘텐츠 gender 변경이 파이프라인 전층 반영 확인.
- 잔여 미보유: BG 8명(상류 거리 사용인 계열 — 저노출) + silverdeen 12명
  (2순위 세트).

## 부록 H — 오웬 별칭 반복 + 우호 상주 조기 소개 (2026-07-12)

부록 F 이후 런 테스트(사랑방/아크/상점/초상화 통합 검증)에서 V9 실패
1건 발견·수정. 종합은 성공: S5 완주 + arcRoute EXPOSE_CORRUPTION
"정의의 대가"(12분기 2연속) + 상점 2건·장비 4개 + 아크 커밋 + 사랑방.

### 결함: 오웬 긴 별칭 반복 (V9)

증상(T21 실측): `넉넉한 체구의 넉넉한 체구의 선술집 주인`(접두 중복) +
`넉넉한 체구의 선주인: "…"`(축약+콜론 라벨).

근본 원인 (다중):
1. 오웬 unknownAlias가 "넉넉한 체구의 선술집 주인" 9자로 유독 김.
2. 사랑방 개방(부록 B)으로 노출 급증(서술 5턴)했으나 봇이 오웬을
   대화 상대(primaryNpcId)로 지목 안 함 → **encounterCount=0**,
   appearanceCount=2. FRIENDLY(1회 소개)인데 encounterCount 0이라 미소개,
   appearanceCount 강제소개(≥5)도 미달 → 끝까지 긴 별칭 반복.
3. IntroFallback(이 런 9회)이 5.11에서 `@[별칭]` 마커를 본문에 삽입 —
   5.10.11 stripAliasPrefixDup '이후'라 재삽입된 접두 중복이 최종본에 새어남.

### 수정

- **5.14 저장 직전 최종 별칭 정리** (llm-worker): DB update 직전에
  stripAliasPrefixDup + stripFusedAliasPrefix 한 번 더 — 5.11~5.13
  재삽입 이후를 커버하는 마지막 방어.
- **A안 우호 상주 조기 소개** (npc-state shouldIntroduce): appearanceCount
  강제 소개 임계를 posture 차등 — FRIENDLY/FEARFUL(첫만남 소개 성향)은
  서술 3회, 그 외는 기존 5회. 거점 사랑방 상주(오웬·비올라·헬가 등
  우호 NPC)가 배경 반복 등장만으로도 조기에 자기소개 → 긴 별칭 반복
  근원 차단. 유닛 3케이스 추가.

### 남은 관찰

- 콜론 라벨 축약("선주인:")은 A안(오웬 조기 소개)이 해소하면 자연 소멸
  예상 — 소개 후엔 실명 마커를 쓰므로. 잔존 시 별도 처리.
- 봇이 거점 상주 NPC를 대화 상대로 지목하지 않는 커버리지 공백(4-A 후속).

## 부록 I — 긴 별칭 일괄 정비 (2026-07-12)

부록 H 분석에서 드러난 **구조적 편중**(CORE/SUB 18명 중 15명이 8자+
unknownAlias) 해소. 오웬은 개별 버그가 아니라 이 편중의 표면화였다.

### 조사

코드에서 unknownAlias 텍스트는 주석·동적 파싱(공백 분리 후 재계산)만
참조 — 별칭 텍스트 변경은 콘텐츠 순수 변경(코드 무영향). shortAlias
축약도 별칭을 런타임 분해하므로 안전.

### 정비 (content, 코드 0줄)

- **graymar CORE/SUB unknownAlias 14명 압축** — 12~14자 → 5~10자
  (예: "넉넉한 체구의 선술집 주인" 14 → "선술집 주인" 6, "권위적인 야간
  경비 책임자" 14 → "야간 경비 책임자" 9, "날카로운 눈매의 회계사" 12 →
  "날카로운 회계사" 7). 첫인상 형용사는 유지, 과잉 수식만 제거.
  shortAlias는 이미 서로 구별돼 있어 유지.
- **BACKGROUND shortAlias 25명 신설** — 기존 전무 → deduplicateAliases
  대명사 치환만 가능했음. 축약형 추가로 반복 시 shortAlias 치환 활성화.
  (BG unknownAlias는 첫인상 유지 위해 존치, 축약형만 보강.)
- **silverdeen CORE/SUB 6명 압축 + BG short 2명** — 팩 계약 대칭.
- 검증: 양 팩 unknownAlias≠shortAlias, shortAlias 충돌 0, CORE/SUB
  최대 별칭 graymar 10 / silverdeen 9자.

### 실전 검증

오웬 새 런: 옛 "넉넉한 체구의" 0회(완전 소멸), 새 "선술집 주인"(6자)
마커·서술 사용, 자기소개 정상. 소개 전 반복 부담·마커 표시명 길이 동시 해소.

## 부록 J — 후처리 순서 의존성 정비: 멱등 배리어 (2026-07-12)

부록 H 분석의 구조적 약점 3(높은 순서 의존성) 해소.

### 문제

소개·별칭 후처리가 10+ 함수로 흩어져 코드 위치 순서(5.10→5.11→5.13→
5.14)에 암묵 의존. 특히 5.11(IntroFallback/IntroDialogueInsert)이 별칭을
본문에 **재삽입**하는데 이게 5.10 정리 '이후'라, 재삽입분의 접두 중복·
융합·조사 오류가 안 잡혔다(오웬 실측). 부록 H의 5.14는 이를 2종
(stripAliasPrefixDup+stripFusedAliasPrefix)만 재실행해 부분 대응.

### 정비

순수 텍스트 정리 5종을 **멱등 배리어** `sanitizeAliasArtifacts`로 묶고,
5.10(1차)과 저장 직전(5.14 최종) **동일 호출**:
- stripAliasPrefixDup · stripFusedAliasPrefix · stripAliasFragmentBeforeName
  · fixNpcNameParticles · stripAnonymousSpeakerLabels

효과:
1. 5.14가 2종 → **5종 전체**로 확장 — 재삽입분 완전 커버.
2. 배리어 멱등(제거 연산 = 재적용 no-op)이라 "재삽입이 1차 정리보다
   뒤에 온다"는 순서 의존성이 무해해짐.
3. 새 텍스트 정리 후처리는 배리어 함수에만 추가하면 두 지점 자동 적용
   — 순서 사각지대 재발 방지.

※ IntroMarkerNorm(소개 상태 의존, 비멱등)은 배리어 제외 — 5.10.13 유지.
※ 상태 변경 후처리(IntroRollback/Fallback, 5.13 마커 재결정)는 그대로.

### 검증

전체 유닛 1047 passed(동작 보존 — 5.10.11+12 동일 순서 통합) + 실런
아티팩트 0(접두 중복·콜론 라벨·융합 전무), 오웬 소개 정상.

## 부록 K — 판정·서술 불일치 + 배경 대사 초상화 오귀속 (2026-07-13)

버그 리포트 `f4bf2e66`(2026-07-12, npc) 두 증상 수정.

### 증상 1: 관찰 선택인데 뇌물 서술 (서버, 심각)

정본: turn 5 `그의 행동을 자세히 관찰한다`(OBSERVE)→PARTIAL 판정 정상.
그러나 서술은 뇌물 장면("은화가 그의 손에 스며든다")+골드는 사례금 +5G
수입 → 판정·골드·서술 삼중 모순.

근본 원인: `bribeOpportunity`(정보 보류 → 뇌물 '선택지' 1개 유도, arch/65)를
NanoEventDirector가 이벤트 **컨셉**(서술 방향)으로 확대. 컨셉 "은화 밀어넣기"가
`[이벤트 컨셉 — 이 방향으로 서술하세요]`로 조건 없이 주입 → LLM이 뇌물 서술.
TurnMode=CONVERSATION_CONT인데 컨셉이 플레이어 행동을 덮음 (Player-First 위반).

수정 (3겹):
- **NanoConceptGuard** (nano-event-director.validate): actionType이 금전/강압
  계열(BRIBE/THREATEN/STEAL)이 아닌데 concept/opening/npcGesture가 뇌물 신호
  (은화·밀어넣·뇌물·매수·수고비…)를 담으면 그 3필드만 비운다 — **선택지
  (BRIBE 노출)는 유지**해 bribeOpportunity 의도 보존.
- **prompt-builder**: concept 빈 문자열이면 "[이벤트 컨셉]" 블록 전체 스킵
  (빈 헤더가 LLM을 혼란시키지 않게).
- **nano 프롬프트 positive**: bribeOpportunity 지시에 "금전 접근은 선택지로만,
  서술 방향은 플레이어 행동을 따를 것" 명시.

플레이어가 직접 뇌물 입력 시(actionType=BRIBE)는 행동=컨셉이라 게이트 미작동
— 정상 뇌물 플로우 무영향(유닛으로 고정).

### 증상 2: 배경 인물 대사에 대표 화자 초상화 (클라, 중간)

turn 5 서술 끝 무마커 배경 대사("행상인 두 명이 수군거린다…")에 직전
관리인 초상화 상속. 원인(StoryBlock.tsx): 무마커 대사가 무조건
`speakingNpc?.imageUrl` fallback → 마커 화자+배경 화자 혼재 턴에서 오귀속.

수정: `markerSeenInTurn` 플래그 — 마커가 한 번이라도 등장한 턴의 후속 무마커
대사는 speakingNpc 초상화/이름 상속 금지(무명 처리). 마커 전무 턴은 기존 fallback.

### 검증

nano 유닛 30 passed(가드 3케이스: OBSERVE+뇌물→억제, BRIBE+뇌물→유지,
OBSERVE+정상→유지) + 서버 전체 1055 passed + 서버/클라 빌드 통과.

### 후속: 무명 여러 화자 분리 표출

증상 2 수정으로 배경 대사가 '무명 인물'로 통일되자, 무명 여러 명의 연속
대사가 DialogueBubble의 compact(헤더 생략 묶음)로 한 사람처럼 보이는
부작용. 무명 인물(npcName='무명 인물'/빈 화자)은 compact를 적용하지 않고
각 대사를 독립 실루엣 버블로 분리 — 세 렌더 경로 통일(renderStyledText
완료본 + StreamingBlock 스트리밍 + StreamTyper는 기존 compact=false).
서버가 배경 화자를 구분해 주지 않아 '서로 다른 두 사람'까진 아니지만
'여러 발화'임은 드러난다.

## 부록 L — 이벤트-서술 NPC 분열: 선택지 정합 게이트 (2026-07-13)

버그 리포트 `185a8ddd`(choices) — 정보상과 대화 중인데 선택지가 음유시인.

### 근본 원인

`determineTurnModeCore`는 **isFirstTurnAtLocation이면 유저 지목·대화 연속과
무관하게 WORLD_EVENT를 강제**한다(1·2·3번 조건 전부). turn 5는 선술집 첫
진입 + "그에게"(대명사라 NPC 추출 실패) → WORLD_EVENT → 장소 이벤트
`EVT_TAVERN_ENC_BARD`(음유시인) 매칭. 그런데 이벤트 `payload.primaryNpcId`가
**없어** primaryNpcIdForSpeaking=null → LLM이 present NPC(정보상)를 유저
맥락으로 골라 서술. 선택지는 이벤트 payload.choices(음유시인) →
**서술(정보상) ↔ 선택지(음유시인) 분열**. 사랑방 개방(부록 B)으로 선술집
이벤트 노출이 늘며 표면화.

### 수정 (콘텐츠 + 코드 게이트, A안)

1. **콘텐츠**: `EVT_TAVERN_ENC_BARD.payload.primaryNpcId = NPC_BG_BARD` 명시.
   → primaryNpcIdForSpeaking=음유시인으로 확정, 서술·선택지 모두 음유시인
   정합(분열 제거). 조우 이벤트는 대상 NPC를 명시해야 한다는 원칙.
2. **코드 게이트** (turns.service): 유저가 텍스트로 특정 NPC를 명시 지목
   (resolvedTargetNpcId)했는데 그게 이벤트 정의 NPC(eventDefinedNpc)와
   다르면, 이벤트 고유 선택지(resolvedChoices)를 폐기하고 서술 NPC 기준
   기본 선택지로 대체. → 유저가 "정보상에게 묻는다" 명시 시 음유시인 이벤트
   선택지 억제(Player-First). eventDefinedNpc는 payload.primaryNpcId가
   덮이기 전 원본 캡처.

### 범위·한계

- 선술집 조우 이벤트 중 명확한 단수 NPC(음유시인)만 명시. STRANGER/TRADE
  등 '미지의 인물' 연출 이벤트는 의도적 무명이라 별도 판단(관찰).
- 근본적 Player-First(첫 진입에도 present NPC 자유 대화)는 TurnMode/
  EventMatcher 대수술이라 보류 — 현 수정은 분열 제거 + 명시 지목 존중.
- 전체 조우 이벤트 31개가 NPC 미명시 — 유사 분열 잠재. 조우 이벤트
  NPC 명시 규약을 콘텐츠 계약으로 확립할지는 후속 트랙.

### 검증

서버 빌드 + 전체 1058 passed + 재시작. 게이트 로직 단순(지목≠이벤트NPC
→ 선택지 폐기).

### 검증 인프라 보강 (2겹)

이 계열(부록 K 뇌물 컨셉·L 이벤트 분열)이 그동안 테스트런에 안 잡힌 이유:
① 선술집이 최근에야 개방(부록 B)·봇 방문(부록 F)되어 경로 부재 ② 발생
확률적 ③ **V1~V9가 '선택지-서술 NPC 정합'을 검사하지 않는 사각지대**(V8은
서술 내부 마커-화자만). ③이 결정적 — 밟았어도 자동 통과했을 것.

- **유닛 (export 정본화)**: 인라인 게이트를 `shouldDiscardEventChoicesCore`
  export로 추출 + `event-choice-gate.spec` 5케이스. `findDowngradeLockNpcCore`도
  export 정본화(복제 drift 방지 원칙). 게이트 로직 회귀 방지.
- **통합 V10 (playtest)**: 실런 각 LOCATION 턴에서 이벤트 정의
  NPC(payload.primaryNpcId) ≠ 서술 화자(actionContext.primaryNpcId)면 분열
  경고. 게이트가 놓친 새 분열 패턴을 실런에서 감지. 한계: 이벤트 NPC가
  명시된 것만 감지(미명시 31개는 여전히 사각 — 조우 이벤트 NPC 명시 규약
  확립 시 커버리지↑).
