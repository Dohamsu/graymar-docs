#!/bin/bash
# gbrain 문서 색인 정본 스크립트 (2026-07-30, CLAUDE.md "GBrain Search Guidance" 참조)
#
# 하는 일: repo md 전량 증분 import → quartz/ stale 사본 페이지 제거 → 변경분 임베딩.
# quartz/content/ 는 정본의 옛 복사본이라 색인에 남으면 검색 결과를 오염시킨다.
# gbrain 0.42.42는 .gbrainignore 미구현(git-tracked 파일 제외 불가)이라 사후 삭제가 유일한 방법.
#
# 주의: gbrain serve(MCP)가 떠 있으면 PGLite 잠금 경쟁으로 쓰기가 전부 블록된다.
# 시작 전에 serve를 내린다 (CLI-only 운영이 정본 — CLAUDE.md GBrain Configuration).
set -uo pipefail

REPO="/Users/dohamsu/Workspace/graymar"
cd "$REPO"

# 0. serve 정리 (잠금 경쟁 방지)
pkill -f 'gbrain.*serve' 2>/dev/null && sleep 1
rm -f ~/.gbrain/brain.pglite/.gbrain-lock/lock 2>/dev/null

# 1. 증분 import (content hash 기준 변경분만)
echo "=== import ==="
gbrain import "$REPO" --no-embed || exit 1

# 2. quartz stale 사본 제거 (import가 다시 넣은 것만 — 대부분 no-op)
echo "=== quartz 사본 제거 ==="
d=0
for f in $(git ls-files 'quartz/*.md'); do
  timeout 30 gbrain delete "${f%.md}" >/dev/null 2>&1 && d=$((d+1))
done
echo "removed: $d"

# 3. 변경분 임베딩 (ollama nomic-embed-text — ollama 상주 서비스 필요)
echo "=== embed ==="
gbrain embed --stale
echo "=== 완료 ==="
