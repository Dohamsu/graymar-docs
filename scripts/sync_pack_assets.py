#!/usr/bin/env python3
"""팩 에셋 풀 동기화 (arch/80) — 정본 스크립트.

사용법: python3 scripts/sync_pack_assets.py <packId>          # 예: karnholt_v1

동작:
  1. content/<pack>/assets/{portraits,locations}/ 의 이미지(webp/png/jpg) 스캔
  2. client/public/pack-assets/<pack>/{portraits,locations}/ 로 복사 (URL 서빙용)
  3. 매니페스트 생성:
     - content/<pack>/assets.json           (정본 — 서버 ContentLoader가 로드)
     - client/src/data/pack-assets/<pack>.json (클라 사본 — 장소 이미지 리졸버가 번들 import)

파일명 규약 (관대):
  - 토큰 구분: '_' 또는 '-' (확장자 제외). 예: f_광부_02.webp → [f, 광부, 02]
  - 성별 힌트: m/male/남/남자 → male, f/female/여/여자 → female (초상화만 의미)
  - 숫자·1글자 토큰은 매칭 키워드에서 제외 (일련번호)
  - 나머지 토큰은 매칭 키워드 — NPC role/이름·장소 id/이름과 부분 일치 스코어링
  - 키워드 없이 넣어도 됨 (무힌트 = 아무 대상에나 배정 가능한 범용 이미지)

이미지를 넣거나 뺀 뒤 이 스크립트만 다시 실행하면 매니페스트가 갱신된다.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTS = {".webp", ".png", ".jpg", ".jpeg"}
MALE = {"m", "male", "남", "남자"}
FEMALE = {"f", "female", "여", "여자"}


def parse_tokens(stem: str):
    raw = [t for part in stem.split("_") for t in part.split("-") if t]
    gender = None
    keywords = []
    for t in raw:
        low = t.lower()
        if low in MALE:
            gender = "male"
        elif low in FEMALE:
            gender = "female"
        elif len(t) >= 2 and not t.isdigit():
            keywords.append(t)
    return gender, keywords


def collect(src_dir: Path, dst_dir: Path, url_base: str, kind: str):
    """복사 시 파일명을 ASCII 슬러그(portrait_01.webp 등)로 정규화한다.

    이유: URL에 한글 이름 토큰이 남으면 서버의 미소개 실명→별칭 치환 안전망이
    URL 문자열 안까지 치환해 404를 만든다 (2026-07-19 카른홀트 실측 —
    'f_오슬라_술집.webp' → 'f_행주 쥔 안주인_술집.webp'). 원본 파일명 토큰은
    매니페스트 keywords로만 보존되고 매칭에 그대로 쓰인다.
    """
    entries = []
    if not src_dir.is_dir():
        return entries
    dst_dir.mkdir(parents=True, exist_ok=True)
    # 삭제 반영: 대상 디렉토리를 소스 기준으로 재구성
    for old in dst_dir.iterdir():
        if old.suffix.lower() in EXTS:
            old.unlink()
    files = sorted(
        f for f in src_dir.iterdir() if f.suffix.lower() in EXTS
    )
    for i, f in enumerate(files, 1):
        slug = f"{kind}_{i:02d}{f.suffix.lower()}"
        shutil.copy2(f, dst_dir / slug)
        gender, keywords = parse_tokens(f.stem)
        entry = {"url": f"{url_base}/{slug}", "kind": kind, "keywords": keywords}
        if gender and kind == "portrait":
            entry["gender"] = gender
        entries.append(entry)
    return entries


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    pack = sys.argv[1]
    src = ROOT / "content" / pack / "assets"
    pub = ROOT / "client" / "public" / "pack-assets" / pack

    portraits = collect(
        src / "portraits", pub / "portraits", f"/pack-assets/{pack}/portraits", "portrait"
    )
    locations = collect(
        src / "locations", pub / "locations", f"/pack-assets/{pack}/locations", "location"
    )
    manifest = {"packId": pack, "portraits": portraits, "locations": locations}

    canon = ROOT / "content" / pack / "assets.json"
    canon.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    client_copy = ROOT / "client" / "src" / "data" / "pack-assets" / f"{pack}.json"
    client_copy.parent.mkdir(parents=True, exist_ok=True)
    client_copy.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[sync_pack_assets] {pack}: portraits {len(portraits)} · locations {len(locations)}")
    print(f"  정본: {canon.relative_to(ROOT)}")
    print(f"  클라: {client_copy.relative_to(ROOT)} + public/pack-assets/{pack}/")


if __name__ == "__main__":
    main()
