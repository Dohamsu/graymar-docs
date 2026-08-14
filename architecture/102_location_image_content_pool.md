# 102. 이미지 정본 단일화 — 장소 이미지 콘텐츠 승격 + 초상화 E-1~E-3 (2026-08-14)

## 문제

장소 이미지 결정 로직이 **100% 클라이언트 하드코딩**(`client/src/data/location-images.ts`)이었고, 팩마다 서로 다른 3가지 해석 전략이 한 함수에 공존했다.

| 팩 | 해석 방식 | 문제 |
|----|-----------|------|
| graymar_v1 | 정적 imageMap 26키 + 시간/안전도 폴백 체인 | 서버가 이미지 존재를 모름 |
| star_sand_v1 | 장소당 1장 (`_day_safe` 단일 키) | 〃 |
| karnholt_v1 | 에셋 풀 매니페스트 + 키워드 스코어 (arch/80) | 유일하게 서버 인지 |
| silverdeen_v1 | 빈 맵 가드 | — |

파생 결함 2건:

1. **장면 컷(arch/96) 장소 후보가 graymar·star_sand에서 영구 0** — SceneCutMatcher는 `assets.json` 매니페스트만 보는데, 이 두 팩의 장소 이미지는 클라에만 존재해 매니페스트 `locations`가 빈 배열이었다.
2. **미등록 접두사 신규 팩의 조용한 graymar 폴백** — `packFor()`의 기본값이 GRAYMAR라, 미래 팩의 장소 id가 `locPrefix` 미스 → `hubImage`(graymar 전경)로 떨어져 세계관이 오염된다. "이미지 없는 팩은 null" 원칙(arch/63 ⑥)과 정면 충돌하는 유일한 구멍.

## 결정

**장소 이미지 매핑을 팩 콘텐츠(`content/<pack>/location_images.json`)로 승격**한다 (불변식 45 — 엔진 코드 콘텐츠 리터럴 금지 정합). 파일 자체는 클라 public 서빙을 유지하고 (URL 불변), **메타데이터만** 콘텐츠로 이동 — 서버는 파일이 아니라 "어느 장소에 어떤 변형 이미지가 있는가"만 알면 된다.

```json
{
  "locations": {
    "LOC_MARKET": {
      "keywords": ["시장", "장터", "좌판"],
      "variants": { "day_safe": "/locations/market_day_safe.webp", "...": "..." }
    }
  }
}
```

- 변형 키: `<day|night>_<safe|alert|danger>`. 폴백 체인은 클라와 동일 — 정확 키 → 시간대 `_safe` → `day_safe` → null.
- `keywords`: 장면 컷 렉시컬 프리스크린용 (서술 본문 등장 토큰).
- karnholt는 기존 arch/80 매니페스트 경로 유지 (파일 소유자 투입형 팩 — sync가 정본). location_images.json은 **클라 정적 서빙형 팩**(graymar·star_sand) 전용.

## 구현 (1차 — 이번 반영)

1. **콘텐츠**: `content/{graymar_v1,star_sand_v1}/location_images.json` 신설 (클라 정적 맵에서 추출, URL 동일).
2. **서버 로더**: `ContentPackState.locationImages` + 선택 파일 로드 (assets.json과 동일 try/catch 패턴). API: `getLocationImageDef(locationId)` · `resolveLocationImageUrl(locationId, time, safety)` (폴백 체인은 `asset-pool.ts`의 `resolveLocationImageVariant` 순수 함수).
3. **장면 컷 장소 후보 부활**: SceneCutMatcher ③ 장소 컷에 콘텐츠 경로 추가 — 현재 장소의 현재 시간/안전도 변형 1장만 후보로. id는 URL 해시(`LOCIMG_<hash>`)라 변형별로 구분되어 usedIds가 정확히 그 이미지만 막는다. `currentHubSafety` 파라미터 신설 (worker가 `ui.worldState.hubSafety` 전달).
4. **클라 폴백 구멍 봉쇄**: `GRAYMAR_KNOWN_LOCATIONS` 화이트리스트 — graymar로 판별됐지만 실재 graymar 장소가 아니면 null (이미지 생략). 이미지 없는 graymar 자체 장소(LOC_NOBLE 등)의 hubImage 폴백은 유지.

검증: 매처 스펙 17케이스 (신규 2 — 콘텐츠 경로 후보·안전도 변형/폴백), 서버 전체 1,961 PASS.

## 2차 — 초상화 정본 단일화 E-1~E-3 (2026-08-14 같은 날 구현)

### E-1. NPC_PORTRAITS 정적 맵 콘텐츠 외부화

- graymar 35 + star_sand 18의 초상화 경로를 `npcs.json`의 `portraitUrl` 필드로 이전 (불변식 45 정합). 서버 `db/types/npc-portraits.ts`(정적 맵)와 미러 스펙, **클라 미러 맵 `data/npc-portraits.ts`까지 삭제** — 수동 이중 유지보수 소멸.
- 통합 리졸버 `getNpcPortraitUrl/Map` 1순위가 콘텐츠(`npcDef.portraitUrl`)로 교체. 맵이 팩 스코프로 한정되는 부수 정화 포함 (구 정적 맵은 전 팩 혼재).
- 도감(NpcDossierTab)은 서버가 `npcEmotional[].imageUrl`(통합 리졸버 결과)을 실어줘 소비 전용화 — **karnholt 풀·동적 NPC도 도감에 얼굴이 생긴다** (구 정적 맵엔 부재).

### E-2. 마커 와이어 포맷 npcId 전환

`@[표시명|URL]` → `@[표시명|npcId]`. URL이 서술 텍스트에 실려 다니던 구조가 별칭 치환 안전망의 URL 오염(2026-07-19 실측 404)·슬러그 변경 시 과거 턴 박제 문제의 근원이었다.

- **사전 전수 조사 결론**: URL은 100% 서버(워커 Step B 등)가 붙인다 — LLM은 URL 작성이 금지돼 있어 프롬프트 변경 0. 서버 regex 30여 개 중 2번째 필드 내용을 실제로 읽는 곳은 1.5곳뿐.
- 삽입 8곳 전환: Step B-1/B-1.5(URL→npcId 역해석, 실패 시 URL 유지)/콜론 승격/B-2×2/B-2.5 + Step F 교정 + 자기소개 삽입 + DialogueAppend.
- 소비 1곳(reconcile speakingNpc): 신 포맷 직해석 + 구 포맷 URL 역매핑 병행.
- **혼재 허용 설계**: 클라 `DialogueBubble.resolvePortraitRef` 단일 지점이 `/`·`http` 시작이면 URL(구 턴·스트림 npcImage), 아니면 npcId로 `npcPortraitMap` 조회. DB 과거 턴의 URL 마커는 영구 렌더 가능.
- **portraitMap 전달 3채널**: ① 턴 `ui.portraitMap`(npcStates 한정 — 유계) ② 런 복원 페이로드 `portraitMap` ③ 워커 reconcile 보충(커밋 시점 npcStates에 없던 첫 등장 BG NPC). 클라는 병합 축적 + speakingNpc·소개 카드 쌍도 흡수.
- 부수 이득: 미닫힘 마커 31자 제거 규칙(`@\[[^\]]{31,}`)과 URL 마커의 잠재 충돌이 npcId 단축으로 자연 해소. nano 선택지 npcId 오염 방어(normalizeChoiceNpcIdCore)는 오염이 정답이 되어 무해화.

### E-3. 장소 이미지 URL 서버 이관

- 서버 `resolveLocationImageForDisplay`(콘텐츠 체인 → karnholt 풀 스코어링 — `poolLocationImage`를 클라와 동일 djb2 결정론으로 포팅)가 정본. `ui.worldState.locationImageUrl`로 전달 — 장소 진입(node-transition 2곳)·FREE 턴·이력 복원 `locationEnter.imageUrl`(구 턴 소급).
- 클라 진입 컷·배경(LocationBackdrop)·복원이 서버 URL 우선, 부재 시(구 서버·구 턴) 레거시 리졸버 fallback.

## 남긴 것

- **클라 레거시 리졸버(`location-images.ts`) 최종 삭제**: 구 턴/구 서버 fallback 기간이 지나면 (배포 후 신규 런 위주가 되면) `getLocationImagePath`·팩별 정적 맵 제거 가능. 시나리오 배너(`getScenarioBannerImage`)는 별도 존치.
- **HUB(장소 미지정) 배경의 팩 인지**: `packFor(null)`이 GRAYMAR를 반환해 비-graymar 팩 HUB에서 graymar 전경이 뜰 수 있는 의심 경로 — worldState의 currentLocationId 유지 정책 확인 후 처리.
- **E-2 실런 검증**: 마커 시스템은 회귀 잦은 부분 — 배포 후 10턴 플레이테스트로 ① 신 포맷 마커 초상 렌더 ② 구 런 이어하기 URL 마커 렌더 ③ 소개 카드 정합(V8 센서)을 확인할 것.

## 관련

- arch/63 ⑥ (팩 인지 이미지 원칙) · arch/80 (에셋 풀) · arch/96 (장면 컷) · 불변식 45
- 이미지 표출 시스템 전수 분석 (2026-08-14 세션): 초상화 통합 리졸버 수정 · 장면 컷 병렬화 · SceneCutMetric 계측 · 해시 슬러그 확대 · 이력 복원 재현과 같은 트랙
