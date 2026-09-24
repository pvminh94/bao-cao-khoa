# Backup — Báo cáo Công tác Khoa
# Chạy: sudo bash scripts/backup.sh   (đã có cron mẫu trong BAN_GIAO.md)
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bao-cao-khoa}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/bao-cao-khoa}"
DB_NAME="${DB_NAME:-baocao}"
STAMP=$(date +%F_%H%M)

mkdir -p "$BACKUP_DIR"

echo "[1/2] Dump PostgreSQL..."
sudo -u postgres pg_dump "$DB_NAME" | gzip > "$BACKUP_DIR/db_${STAMP}.sql.gz"

echo "[2/2] Gói mã nguồn + .env..."
tar --exclude='.venv' --exclude='__pycache__' --exclude='*.db' \
  -czf "$BACKUP_DIR/app_${STAMP}.tar.gz" -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")"

# giữ 30 ngày
find "$BACKUP_DIR" -name '*.gz' -mtime +30 -delete 2>/dev/null || true

echo "OK → $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -5
