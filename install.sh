#!/usr/bin/env bash
# ============================================================================
#  CÀI ĐẶT PRODUCTION — 1 LỆNH sau khi clone
#
#  git clone https://github.com/pvminh94/bao-cao-khoa.git
#  cd bao-cao-khoa
#  sudo bash install.sh
#
#  Tuỳ chọn (đổi mật khẩu trước khi chạy production):
#    sudo DB_PASS='mat_khau_pg_man' ADMIN_PASS='mat_khau_admin' bash install.sh
# ============================================================================
set -euo pipefail

REPO_URL="https://github.com/pvminh94/bao-cao-khoa.git"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Hãy chạy quyền root:"
  echo "  sudo bash install.sh"
  echo "hoặc (nếu chưa clone):"
  echo "  git clone ${REPO_URL} && cd bao-cao-khoa && sudo bash install.sh"
  exit 1
fi

# Kiểm tra môi trường tối thiểu
if ! command -v python3 >/dev/null; then
  echo "❌ Thiếu python3 — cài: apt-get install -y python3"
  exit 1
fi
if [[ ! -f "$ROOT/requirements.txt" || ! -f "$ROOT/scripts/install-ubuntu.sh" ]]; then
  echo "❌ Không tìm thấy mã nguồn đầy đủ trong $ROOT"
  echo "   Cần chạy từ repo clone (có requirements.txt và scripts/)"
  exit 1
fi

echo "============================================================================"
echo " CÀI ĐẶT: Hệ thống Báo cáo Công tác Khoa"
echo "   Source : $ROOT"
echo "   Target : /opt/bao-cao-khoa"
echo "============================================================================"
echo

# Gọi script chính (giữ biến môi trường DB_PASS / ADMIN_PASS / APP_PORT nếu có)
exec bash "$ROOT/scripts/install-ubuntu.sh"
