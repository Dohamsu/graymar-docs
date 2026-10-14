#!/bin/bash
# graymar 서버 로그 회전 정본 (arch/144 §16 — 2026-10-14 회전 설정 0, 1.27GB 누적 실측)
#
# - launchd com.graymar.server 의 표준출력 /tmp/graymar-server.log 가 상한을 넘으면
#   gzip 사본(.1.gz)을 남기고 원본을 0 바이트로 비운다(copytruncate). launchd 가 파일을
#   append 모드로 열어 두므로 비운 뒤에도 서버는 파일 끝에 이어 쓴다 — 재시작 불필요.
# - 보존: .1.gz ~ .${KEEP}.gz. scripts/stream_metrics_monitor.py 는 .1.gz 까지 함께 읽는다.
# - launchd com.graymar.server-logrotate 가 매시 정각 실행 (scripts/launchd/ 사본을
#   ~/Library/LaunchAgents/ 에 두고 bootstrap). 수동: bash scripts/rotate-server-log.sh
# - 9월 디스크 풀 사고(memory reference_disk_full_incident_20260910) 재발 방지 목적.
set -euo pipefail

LOG="${GRAYMAR_SERVER_LOG:-/tmp/graymar-server.log}"
MAX_MB="${GRAYMAR_LOG_MAX_MB:-200}"
KEEP="${GRAYMAR_LOG_KEEP:-4}"

[ -f "$LOG" ] || exit 0
size_mb=$(( $(stat -f %z "$LOG") / 1024 / 1024 ))
if [ "$size_mb" -lt "$MAX_MB" ]; then
  exit 0
fi

# 오래된 사본부터 한 칸씩 밀기
rm -f "$LOG.$KEEP.gz"
for ((i = KEEP - 1; i >= 1; i--)); do
  [ -f "$LOG.$i.gz" ] && mv "$LOG.$i.gz" "$LOG.$((i + 1)).gz"
done

# 압축 사본을 임시 이름으로 만든 뒤 검증하고 제자리로 — 반쪽 파일이 .1.gz 를 차지하지 않게
gzip -c "$LOG" >"$LOG.1.gz.partial"
gzip -t "$LOG.1.gz.partial"
mv "$LOG.1.gz.partial" "$LOG.1.gz"
: >"$LOG"

echo "[rotate-server-log] $(date '+%F %T') ${size_mb}MB → $LOG.1.gz (보존 $KEEP)"
