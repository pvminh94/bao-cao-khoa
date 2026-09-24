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
sudo -u "$USER_RUN" "$APP_DIR/.venv/bin/python" -m app.cli create-admin "$1" "$2"
