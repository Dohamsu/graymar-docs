#!/bin/bash
# graymar DB 백업 정본 (보안 감사 2026-09-07 H6 — 백업 0건 해소)
#
# - docker 컨테이너 textRpg-db 안에서 pg_dump -Fc(custom, 압축) → ~/Backups/graymar/
# - iCloud Drive 가 있으면 오프사이트 사본도 남긴다 (Mac 디스크 장애 대비)
# - 보존 14일. 복원: pg_restore -U user -d textRpg --clean --if-exists <file>
# - launchd com.graymar.db-backup 이 매일 04:30 실행. 수동: bash scripts/backup-db.sh
set -euo pipefail

CONTAINER="${GRAYMAR_DB_CONTAINER:-textRpg-db}"
DB_USER="${GRAYMAR_DB_USER:-user}"
DB_NAME="${GRAYMAR_DB_NAME:-textRpg}"
DEST="${GRAYMAR_BACKUP_DIR:-$HOME/Backups/graymar}"
ICLOUD="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Backups/graymar"
KEEP_DAYS="${GRAYMAR_BACKUP_KEEP_DAYS:-14}"
TS=$(date +%Y%m%d-%H%M%S)
OUT="$DEST/${DB_NAME}-${TS}.dump"

mkdir -p "$DEST"
chmod 700 "$DEST"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "[backup-db] container $CONTAINER not running" >&2
  exit 1
fi

# 임시 파일에 받은 뒤 검증 후 제자리 이동 — 반쪽 파일이 정본 이름을 차지하지 않게
TMP="$OUT.partial"
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc >"$TMP"
# 아카이브 무결성 — pg_restore --list 가 읽히면 유효
docker exec -i "$CONTAINER" pg_restore --list >/dev/null <"$TMP"
mv "$TMP" "$OUT"
chmod 600 "$OUT"
SIZE=$(du -h "$OUT" | cut -f1)
echo "[backup-db] wrote $OUT ($SIZE)"

# 보존 정리
find "$DEST" -name "${DB_NAME}-*.dump" -mtime +"$KEEP_DAYS" -delete

# 오프사이트 사본 (iCloud Drive 존재 시)
if [ -d "$(dirname "$ICLOUD")" ] || [ -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs" ]; then
  mkdir -p "$ICLOUD"
  cp "$OUT" "$ICLOUD/"
  find "$ICLOUD" -name "${DB_NAME}-*.dump" -mtime +"$KEEP_DAYS" -delete
  echo "[backup-db] offsite copy → iCloud Drive/Backups/graymar"
fi
