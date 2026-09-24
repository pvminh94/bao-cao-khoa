#!/usr/bin/env bash
# ============================================================================
# Khôi phục toàn hệ thống từ bản sao lưu của scripts/backup.sh
#   sudo bash scripts/restore.sh /var/backups/bao-cao-khoa/db_2026-09-24_0200.sql.gz
#   sudo bash scripts/restore.sh /var/backups/bao-cao-khoa/db_...sql.gz /var/backups/bao-cao-khoa/app_...tar.gz
# (file thứ 2 là tuỳ chọn — mã nguồn + .env; bỏ qua nếu chỉ phục hồi dữ liệu)
# ============================================================================
set -euo pipefail

APP_NAME="bao-cao-khoa"
APP_USER="baocao"
APP_DIR="/opt/${APP_NAME}"
DB_NAME="baocao"
DB_USER="baocao"
DB_PORT="${DB_PORT:-}"   # auto-detect nếu bỏ trống

if [[ $EUID -ne 0 ]]; then echo "Hãy chạy với sudo."; exit 1; fi
DB_FILE="${1:-}"
APP_FILE="${2:-}"
if [[ -z "$DB_FILE" || ! -f "$DB_FILE" ]]; then
  echo "Dùng: sudo bash scripts/restore.sh <file db_*.sql.gz> [file app_*.tar.gz]"
  exit 1
fi

# dò port/cluster PostgreSQL cục bộ (máy có thể có nhiều PostgreSQL)
PG_TARGET=(sudo -u postgres psql)
if command -v pg_lsclusters >/dev/null 2>&1; then
  CLUSTER="$(pg_lsclusters -h | awk '$4=="online"{print $1"/"$2; exit}')"
  if [[ -n "$CLUSTER" ]]; then
    PG_TARGET=(sudo -u postgres psql --cluster "$CLUSTER")
    DB_PORT="$(pg_lsclusters -h | awk '$4=="online"{print $3; exit}')"
  fi
fi
DB_PORT="${DB_PORT:-5432}"
echo "Cluster: ${CLUSTER:-mặc định} · port: ${DB_PORT}"

echo "Sẽ GHI ĐÈ database '${DB_NAME}' bằng: ${DB_FILE}"
[[ -n "$APP_FILE" ]] && echo "Và GIẢI NÉN mã nguồn: ${APP_FILE} → ${APP_DIR}"
read -r -p "Gõ 'restore' để tiếp tục: " CONFIRM
[[ "$CONFIRM" == "restore" ]] || { echo "Huỷ."; exit 1; }

echo "[1/5] Dừng ứng dụng..."
systemctl stop bao-cao-khoa 2>/dev/null || true

echo "[2/5] Sao lưu an toàn dữ liệu HIỆN TẠI..."
STAMP=$(date +%F_%H%M%S)
mkdir -p /var/backups/bao-cao-khoa
"${PG_TARGET[@]}" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1 \
  && sudo -u postgres pg_dump "$DB_NAME" | gzip > "/var/backups/bao-cao-khoa/truoc-khi-phuc-hoi_${STAMP}.sql.gz" \
  && echo "    → truoc-khi-phuc-hoi_${STAMP}.sql.gz" || echo "    (bỏ qua — DB chưa tồn tại)"

echo "[3/5] Tạo lại database..."
"${PG_TARGET[@]}" -qc "DROP DATABASE IF EXISTS ${DB_NAME};"
"${PG_TARGET[@]}" -qc "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

echo "[4/5] Nạp dữ liệu từ $DB_FILE ..."
gunzip -c "$DB_FILE" | "${PG_TARGET[@]}" -d "$DB_NAME" -q
"${PG_TARGET[@]}" -d "$DB_NAME" -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
"${PG_TARGET[@]}" -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" >/dev/null || true

if [[ -n "$APP_FILE" ]]; then
  if [[ ! -f "$APP_FILE" ]]; then echo "Không thấy $APP_FILE"; exit 1; fi
  echo "[4b/5] Giải nén mã nguồn + .env ..."
  tar -xzf "$APP_FILE" -C "$(dirname "$APP_DIR")"
  chown -R "$APP_USER:$APP_USER" "$APP_DIR"
fi

echo "[5/5] Khởi động lại ứng dụng..."
systemctl start bao-cao-khoa 2>/dev/null || true
sleep 2
if systemctl is-active --quiet bao-cao-khoa; then
  echo "✅ PHỤC HỒI XONG — service đang chạy: http://$(hostname -I | awk '{print $1}')/"
  echo "   Đăng nhập bằng tài khoản CÓ TRONG bản sao lưu (không phải tài khoản vừa giờ)."
else
  echo "⚠ service chưa chạy — xem: journalctl -u bao-cao-khoa -n 30"
  exit 1
fi
