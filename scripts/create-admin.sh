#!/usr/bin/env bash
# Tạo/khôi phục tài khoản admin (chạy trên VPS):
#   sudo bash scripts/create-admin.sh <username> <password>
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/bao-cao-khoa}"
USER_RUN="${USER_RUN:-baocao}"
if [[ $# -lt 2 ]]; then
  echo "Usage: sudo bash scripts/create-admin.sh <username> <password>"
  exit 1
fi
cd "$APP_DIR"
sudo -u "$USER_RUN" env HOME="$APP_DIR" PYTHONPATH="$APP_DIR" \
  "$APP_DIR/.venv/bin/python" -m app.cli create-admin "$1" "$2"
