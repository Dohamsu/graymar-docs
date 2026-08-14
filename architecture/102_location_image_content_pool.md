# 102. 장소 이미지 콘텐츠 승격 — location_images.json (2026-08-14)

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

## 남긴 것 (2차 — E와 함께)

- **URL 결정의 완전 서버 이관**: 서버가 매 턴 `ui`에 resolved URL을 내려주고 클라 리졸버(`location-images.ts`)를 소비 전용으로 축소. 지금 안 한 이유 — 구 턴 복원(저장된 serverResult에 URL 없음)과의 호환 때문에 클라 리졸버를 legacy fallback으로 유지해야 해서, 마커 URL 임베드 정리(E)와 함께 설계하는 게 이중화 기간을 최소화한다.
- **HUB(장소 미지정) 배경의 팩 인지**: `packFor(null)`이 GRAYMAR를 반환해 비-graymar 팩 HUB에서 graymar 전경이 뜰 수 있는 의심 경로 — worldState의 currentLocationId 유지 정책 확인 후 처리.
- location_images.json의 클라 소비 (정적 맵 대체) — 2차 이관 시 번들 import로 전환.

## 관련

- arch/63 ⑥ (팩 인지 이미지 원칙) · arch/80 (에셋 풀) · arch/96 (장면 컷) · 불변식 45
- 이미지 표출 시스템 전수 분석 (2026-08-14 세션): 초상화 통합 리졸버 수정 · 장면 컷 병렬화 · SceneCutMetric 계측 · 해시 슬러그 확대 · 이력 복원 재현과 같은 트랙
