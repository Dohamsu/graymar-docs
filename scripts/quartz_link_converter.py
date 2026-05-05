#!/usr/bin/env python3
"""
Quartz wiki link 변환기

graymar 문서들의 백틱 파일경로(`architecture/26_narrative_pipeline_v2.md` 등)를
wiki link `[[architecture/26_narrative_pipeline_v2|26 Narrative Pipeline]]`으로 변환.

변환 대상:
- `architecture/...md`
- `specs/...md`
- `guides/...md`
- 단순 파일명: `26_narrative_pipeline_v2.md` (architecture 폴더 가정)

제외:
- 코드 블록 (```...```) 안
- inline 코드 식별자 (변수명/함수명)
- server/, client/, content/ 같은 코드 경로 (Quartz가 빌드 안 하므로)
- 이미 wiki link/마크다운 링크 형태

사용법:
  python3 scripts/quartz_link_converter.py --dry-run     # 변경 전 미리보기
  python3 scripts/quartz_link_converter.py               # 실제 적용
  python3 scripts/quartz_link_converter.py --files CLAUDE.md architecture/INDEX.md  # 특정 파일만
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path("/Users/dohamsu/Workspace/graymar")

# 변환 대상 폴더 (Quartz가 빌드하는)
LINKABLE_FOLDERS = ["architecture", "specs", "guides"]

# wiki link 변환 패턴
# 1. 백틱 안의 파일경로: `architecture/26_narrative_pipeline_v2.md`
PATTERN_BACKTICK_PATH = re.compile(
    r"`((?:" + "|".join(LINKABLE_FOLDERS) + r")/[A-Za-z0-9_/-]+\.md)`"
)

# 2. 백틱 안의 단순 파일명: `26_narrative_pipeline_v2.md` → architecture/.. 추정
PATTERN_BACKTICK_FILE = re.compile(
    r"`(\d+_[a-z_]+\.md)`"
)

# 3. 백틱 안의 CLAUDE.md / README.md
PATTERN_BACKTICK_ROOT = re.compile(
    r"`(CLAUDE\.md|README\.md)`"
)

# 4. 코드 블록 (변환 제외)
PATTERN_CODE_BLOCK = re.compile(r"```[\s\S]*?```")


def find_file_in_folders(filename: str) -> str | None:
    """단순 파일명을 보고 어느 폴더에 있는지 찾음."""
    name = filename.removesuffix(".md")
    for folder in LINKABLE_FOLDERS:
        if (ROOT / folder / filename).exists():
            return f"{folder}/{name}"
    return None


def make_display_name(path_no_md: str) -> str:
    """wiki link의 표시 이름 — 파일명에서 추출."""
    name = path_no_md.split("/")[-1]
    # 숫자 prefix 제거 (예: "26_narrative_pipeline_v2" → "narrative pipeline v2")
    name = re.sub(r"^\d+_", "", name)
    name = name.replace("_", " ")
    return name


def convert_text(text: str, filepath: Path) -> tuple[str, int]:
    """텍스트를 변환하고 (변환된 텍스트, 변환 건수) 반환."""
    # 1. 코드 블록을 placeholder로 치환 (변환 제외)
    code_blocks = []
    def stash_code(m):
        code_blocks.append(m.group(0))
        return f"\x00CODEBLOCK{len(code_blocks)-1}\x00"

    text = PATTERN_CODE_BLOCK.sub(stash_code, text)

    count = 0

    # 2. 백틱 안 파일경로 → wiki link
    def convert_path(m):
        nonlocal count
        path = m.group(1).removesuffix(".md")
        display = make_display_name(path)
        count += 1
        return f"[[{path}|{display}]]"

    text = PATTERN_BACKTICK_PATH.sub(convert_path, text)

    # 3. 단순 파일명 (백틱) → wiki link
    def convert_file(m):
        nonlocal count
        filename = m.group(1)
        path = find_file_in_folders(filename)
        if path:
            display = make_display_name(path)
            count += 1
            return f"[[{path}|{display}]]"
        return m.group(0)  # 못 찾으면 원본 유지

    text = PATTERN_BACKTICK_FILE.sub(convert_file, text)

    # 4. CLAUDE.md / README.md (백틱) → wiki link
    def convert_root(m):
        nonlocal count
        filename = m.group(1).removesuffix(".md")
        count += 1
        return f"[[{filename}]]"

    text = PATTERN_BACKTICK_ROOT.sub(convert_root, text)

    # 5. 코드 블록 복원
    for i, block in enumerate(code_blocks):
        text = text.replace(f"\x00CODEBLOCK{i}\x00", block)

    return text, count


def process_file(filepath: Path, dry_run: bool = False) -> int:
    """파일을 처리하고 변환 건수 반환."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️ 읽기 실패: {filepath} — {e}", flush=True)
        return 0

    new_text, count = convert_text(text, filepath)
    if count == 0:
        return 0

    rel = filepath.relative_to(ROOT)
    if dry_run:
        print(f"  [DRY] {rel}: {count}건 변환 예정", flush=True)
    else:
        filepath.write_text(new_text, encoding="utf-8")
        print(f"  ✓ {rel}: {count}건 변환", flush=True)
    return count


def main():
    parser = argparse.ArgumentParser(description="Quartz wiki link 변환기")
    parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 미리보기")
    parser.add_argument("--files", nargs="+", help="특정 파일만 처리 (root 기준 상대경로)")
    args = parser.parse_args()

    if args.files:
        targets = [ROOT / f for f in args.files]
    else:
        # 기본: CLAUDE.md + architecture/ + specs/ + guides/ 모든 .md
        targets = [ROOT / "CLAUDE.md"]
        for folder in LINKABLE_FOLDERS:
            targets.extend((ROOT / folder).rglob("*.md"))

    print(f"=== Quartz wiki link 변환 ({'DRY RUN' if args.dry_run else '실제 적용'}) ===", flush=True)
    print(f"대상: {len(targets)}개 파일", flush=True)
    print()

    total = 0
    files_changed = 0
    for f in targets:
        if not f.exists():
            continue
        c = process_file(f, args.dry_run)
        if c > 0:
            files_changed += 1
            total += c

    print(flush=True)
    print(f"=== 결과 ===", flush=True)
    print(f"변경된 파일: {files_changed}/{len(targets)}", flush=True)
    print(f"총 변환 건수: {total}", flush=True)


if __name__ == "__main__":
    main()
