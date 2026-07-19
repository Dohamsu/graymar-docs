# 80. 팩 에셋 풀 — 이미지 자동 매칭 시스템 (2026-07-19)

> **상태**: ✅ 구현됨 — 카른홀트 실런 검증 (저작 배정·마커 URL 부착·URL 실명 치환 결함 수정)
> **동기**: 소유자가 NPC·장소 이미지를 만들어 폴더에 넣기만 하면, 고정 매핑 없이 **동적 NPC 생성·저작 NPC·장소에 자동 매칭**되어 등장하는 시스템 (카른홀트 AUTONOMOUS 팩 최초 적용 — 기존엔 이미지 전무·실루엣 fallback).
> **관련**: arch/75(동적 NPC 레지스트리 P1), arch/63(멀티 팩), 불변식 45(콘텐츠 외부화 — 엔진에 이미지 매핑 리터럴 없음).

## 1. 사용법 (소유자 워크플로우)

```
1. 이미지를 넣는다:
   content/karnholt_v1/assets/portraits/f_오슬라_술집.webp     ← NPC 초상화
   content/karnholt_v1/assets/locations/mine_night.webp        ← 장소 이미지
2. 동기화: python3 scripts/sync_pack_assets.py karnholt_v1
3. 서버 재시작 (팩 로드 시 배정) + 클라 배포
```

**파일명 규약 (관대 — 힌트는 선택)**:
- 토큰 구분 `_`/`-`. 성별 힌트: `m/male/남` · `f/female/여` (초상화만).
- 나머지 토큰 = 매칭 키워드 — NPC 이름·role, 장소 locationId와 부분 일치 스코어링. `day`/`night`는 장소 시간대 필터.
- **키워드 없이 넣어도 됨** — 범용 이미지로 아무 동적 NPC에나 배정 가능.
- 숫자·1글자 토큰은 일련번호로 무시.

## 2. 구조

| 구성 | 위치 | 역할 |
|---|---|---|
| 정본 폴더 | `content/<pack>/assets/{portraits,locations}/` | 소유자가 이미지 투입 |
| 동기화 | `scripts/sync_pack_assets.py` | 스캔 → `client/public/pack-assets/<pack>/` 복사(**ASCII 슬러그 정규화**) → 매니페스트 2벌(`content/<pack>/assets.json` 정본 + `client/src/data/pack-assets/<pack>.json` 번들 사본) |
| 매칭 순수 모듈 | `server/src/content/asset-pool.ts` | 성별 게이트(불일치 배제) + 키워드 부분일치 +2 + 동률 시드(djb2) 결정론 pick + used 중복 배제 |
| 로드·저작 배정 | ContentLoader `loadScenario` | assets.json 선택 로드 → `assignAuthoredPortraits` (키워드 실매칭만 그리디, 이미지당 1명, 범용 이미지는 동적 몫으로 유보) |
| 동적 NPC 배정 | `registerDynamicNpc` 3rd arg | 등록 시 성별·role·성격 텍스트 매칭 pick → `stub.portraitUrl` (runState 영속 — 런 내 같은 얼굴 고정), used = 저작 배정 + 기존 동적 배정 (소진 시 미배정 = 실루엣) |
| 통합 리졸버 | ContentLoader `getNpcPortraitUrl` / `getNpcPortraitMap` | **정적 맵(NPC_PORTRAITS, graymar 레거시) → 팩 풀 저작 배정 → 동적 stub** 순. 소비처 5곳(worker 마커·Step B·역해석, stream-classifier, dialogue-generator)이 직조회 대신 리졸버 사용 |
| 클라 장소 이미지 | `location-images.ts` | `LOC_KH_*` → 매니페스트 키워드 매칭(locationId 토큰 + day/night 필터), locationId 해시 결정론. 시나리오 배너 = 풀 첫 장소 이미지 |

## 3. 안전 성질

- **풀이 비면 완전 무동작** — 기존 fallback(실루엣/이미지 생략) 그대로. 빈 매니페스트가 커밋되어 있어 이미지 0장 상태로도 빌드·플레이 무해.
- **같은 얼굴 두 인물 금지** — used 배제, 소진 시 재사용 대신 미배정.
- **결정론** — 같은 NPC/장소는 재시작·재렌더에도 같은 이미지 (시드 = npcId/locationId 해시). 동적 배정은 runState 영속.
- **세계관 오염 금지** — 타 팩 이미지 fallback 없음 (silverdeen 정책 계승).

## 4. 검증 (2026-07-19)

- 유닛 6케이스 (성별 게이트·키워드 우선·중복 배제·결정론·저작 그리디·범용 유보) + 전체 1,414 green + 클라 빌드/린트 통과.
- **카른홀트 실런**: placeholder 4장(오슬라 키워드 초상 등) → `[AssetPool] karnholt_v1: portraits 2 · locations 2 · 저작 배정 1` + 마커에 `/pack-assets/` URL 실부착 (T6/7/10).
- **결함 발견·수정**: 파일명에 한글 실명 토큰이 남으면 미소개 실명→별칭 치환 안전망이 **URL 문자열 안까지 치환**해 404 유발 ('f_오슬라_술집.webp' → 'f_행주 쥔 안주인_술집.webp' 실측) → sync가 ASCII 슬러그(portrait_01.webp)로 정규화, 키워드는 매니페스트에만 보존.

## 5. 잔여·주의

- 소유자 이미지 투입 후 절차: sync → **서버 재시작**(저작 배정은 팩 로드 시) → 클라 push(Vercel 자동 배포 — public/ 파일 포함).
- 동적 NPC 배정은 비트 채택으로 NPC가 생성될 때 발생 — AUTONOMOUS 팩 전용 경로 (유닛으로 고정, 실발동은 채택 빈도에 의존).
- graymar/silverdeen/star_sand에도 동일 구조 사용 가능 (assets/ + sync — 현재는 karnholt만 클라 장소 리졸버 배선, 타 팩은 기존 정적 맵 우선이라 필요 시 확장).
