# 추가 이미지 8장 — 2026-09-09

생성: 소유자 요청에 따라 built-in image_gen 사용. 1672×941 PNG 원본에서 WebP quality 86으로 변환. 그레이마르와 극야해안은 독립 지역으로 제작했다.

| 이미지 | 소비 경로 |
|---|---|
| 상류 거리 낮/밤 | `LOC_NOBLE`, `/locations/noble-{day,night}-v1.webp` |
| 항만 창고구 낮/밤 | `LOC_DOCKS_WAREHOUSE`, `/locations/warehouse-{day,night}-v1.webp` |
| 극야해안 전경 | `star_sand_v1` HUB 및 클라이언트 시나리오 배너, `/locations/star_sand_v1/coast-overview-v1.webp` |
| 꿈잠 여관 경계 | `LOC_SS_INN` day/night × alert/danger, `/locations/star_sand_v1/dream-inn-alert-v1.webp` |
| 잉크 흔적 | `SCN_350ef5cc`, 시장·낮, 현장 묘사 확인 |
| 열린 창고 지하 통로 | `SCN_b2428604`, 항만/창고구, 현장 묘사 확인 |

장소 배경 원본 WebP는 `content/<pack>/location-art/`에 보관한다. `location_images.json`이 서버의 등록 정본이며 파일은 클라이언트 public의 표에 적힌 URL로 복사한다. 상류/창고구는 기존 fallback 규칙으로 같은 시간대 safe 이미지를 사용한다. 여관 위험 상태는 별도 위험 그림을 만들 때까지 경계 그림을 공유한다. 극야의 day/night 키는 태양이 뜨는 낮을 의미하지 않는다.

## 조사 컷 등록과 노출 조건

`assets/scenes/<stem>.scene.json`은 같은 이름의 WebP에 대한 조건이다. sync 스크립트는 이를 읽어 `assets.json.guardedScenes`에 보존한다. 일반 `scenes`와 분리한 이유는 구버전 서버가 신규 발견 그림을 무조건 후보에 넣지 않게 하기 위해서다. 새 서버의 `getSceneCuts()`만 두 목록을 합친다.

- `locationIds`: 현재 장소의 허용 목록. 다른 장소 또는 장소 미상은 제외한다.
- `requiredKeywordGroups`: 각 그룹에서 최소 한 단어가 실제 서술에 있어야 한다. 장소명 가산점으로 대체하지 않는다.
- `description`: 실제 그림에 보이는 내용을 편집 모델에 전달한다.
- `requiresObservedScene`: 계획·추측·소문·회상·발견 실패가 아닌 현장 관찰 장면만 선택하도록 편집 모델에 요구한다.

현재 LOCATION_SECRET에는 확정 발견 ID 트래커가 없어 이를 새로 만들거나 기존 퀘스트 상태를 변조하지 않았다. 현장 확인의 최종 판단은 기존 경량 편집 모델의 의미 판정이며, 결정론적 발견 보장은 아니다. 조건이 불확실하면 삽입하지 않는다. 기존 3턴 간격, 이동 턴 제외, 1런 1회 규칙은 유지한다.

원본 파일을 추가/수정한 뒤 기존처럼 `python3 scripts/sync_pack_assets.py graymar_v1`을 실행한다. sidecar 없이 discovery WebP만 옮기지 않는다. 장소 그림은 `assets/locations/`의 자동 풀에 중복 등록하지 않는다.

## 배포

1. 클라이언트 public 에셋과 배너 매핑을 배포한다.
2. 운영 호스트의 graymar-docs 작업 폴더에서 최신 main을 받아 content 파일을 갱신한다.
3. 운영 호스트의 server 작업 폴더에서 최신 graymar-server main을 받고 `pnpm build` 후 기존 `com.graymar.server` launchd 서비스를 재시작한다.
4. `/v1/version` 해시 및 기존 기동 스모크를 확인한다. 클라이언트 push만으로 별도 서버의 콘텐츠 캐시는 갱신되지 않는다.

## 검증

로컬 격리 하네스에서 기존 매처 24개 + 신규 조건 7개 테스트 통과. Nest/LLM 외부 경계만 스텁하고 실제 매처/asset-pool 코드를 실행했다. sync sidecar 왕복, 54개 기존 컷 유지, 새 2개 ID 유일성, 새 8개 URL 파일 존재, 시간대/안전도 fallback을 확인했다. 실제 모델의 오매칭률 검증은 운영 플레이 표본이 필요하다.
