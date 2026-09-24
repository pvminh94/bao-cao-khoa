#!/usr/bin/env bash
# ============================================================================
# Cài đặt hệ thống Báo cáo Công tác Khoa trên VPS Ubuntu 22.04 / 24.04
# Chạy:  sudo bash scripts/install-ubuntu.sh
# ============================================================================
set -euo pipefail

APP_NAME="bao-cao-khoa"
APP_USER="baocao"
APP_DIR="/opt/${APP_NAME}"
APP_PORT="${APP_PORT:-8000}"
DB_NAME="baocao"
DB_USER="baocao"
# Đổi 2 dòng dưới trước khi chạy production!
DB_PASS="${DB_PASS:-baocao_change_me}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-Admin@123}"

# Mã hoá mật khẩu để nhúng an toàn vào DATABASE_URL (chống lỗi ký tự @ : / ! # ...)
db_pass_enc() {
  python3 -c 'import sys,urllib.parse as u; print(u.quote_plus(sys.argv[1]))' "$1"
}
# Escape nháy đơn cho SQL literal (chuẩn SQL: ' → '') — an toàn với mọi ký tự mật khẩu
sql_quote() { printf "'%s'" "${1//\'/\'\'}"; }
# Tạo/đổi mật khẩu role Postgres (psql -c KHÔNG thay biến :'pwd' → tự escape bên shell)
pg_set_pass() {
  sudo -u postgres psql -c "SET password_encryption='scram-sha-256'; ALTER USER ${DB_USER} WITH PASSWORD $(sql_quote "$1");"
}

if [[ $EUID -ne 0 ]]; then
  echo "Hãy chạy với sudo:  sudo bash scripts/install-ubuntu.sh"
  exit 1
fi

echo "==> [1/7] Cập nhật & cài gói hệ thống..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib \
  nginx ufw curl git acl rsync fonts-dejavu-core

echo "==> [2/7] Tạo user chạy ứng dụng..."
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
fi
mkdir -p "$APP_DIR"

# Sao chép mã nguồn (chạy từ repo clone — script nằm trong scripts/)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "    Nguồn: $SRC_DIR → $APP_DIR"
# Nếu đang cài lại trên chính /opt thì bỏ qua rsync self-copy
if [[ "$SRC_DIR" != "$APP_DIR" ]]; then
  rsync -a --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '*.db' \
    --exclude '.git' --exclude 'node_modules' --exclude '.env' \
    "$SRC_DIR/" "$APP_DIR/"
  # giữ lại .env cũ nếu có (không bị --delete xóa nhờ exclude trên)
  if [[ -f "$SRC_DIR/.env" && ! -f "$APP_DIR/.env" ]]; then
    cp "$SRC_DIR/.env" "$APP_DIR/.env"
  fi
fi

echo "==> [3/7] PostgreSQL: tạo DB + user..."
service postgresql start >/dev/null 2>&1 || systemctl start postgresql
# LUÔN đồng bộ mật khẩu role với DB_PASS (idempotent) — tránh lệch .env ↔ Postgres
if sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1; then
  pg_set_pass "$DB_PASS"
  echo "    Đã cập nhật mật khẩu role ${DB_USER} theo DB_PASS."
else
  sudo -u postgres psql -c "SET password_encryption='scram-sha-256'; CREATE USER ${DB_USER} WITH PASSWORD $(sql_quote "$DB_PASS");"
  echo "    Đã tạo role ${DB_USER}."
fi
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
  || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" >/dev/null
# PostgreSQL 15+ cần cả schema grant
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" >/dev/null || true

echo "==> [4/7] Python venv + dependencies..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip -q
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> [5/7] Viết file .env..."
DB_PASS_ENC="$(db_pass_enc "$DB_PASS")"
# LUÔN ensure DATABASE_URL khớp DB_PASS hiện tại (giữ SECRET_KEY cũ nếu đã có)
if [[ ! -f "$APP_DIR/.env" ]]; then
  SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
  cat > "$APP_DIR/.env" <<EOF
APP_NAME=Bao cao cong tac khoa
SECRET_KEY=${SECRET}
DATABASE_URL=postgresql+psycopg2://${DB_USER}:${DB_PASS_ENC}@127.0.0.1:5432/${DB_NAME}
SESSION_HOURS=12
HOST=127.0.0.1
PORT=${APP_PORT}
SEED_ADMIN_USER=${ADMIN_USER}
SEED_ADMIN_PASS=${ADMIN_PASS}
EOF
else
  # cập nhật lại dòng DATABASE_URL cho khớp DB_PASS mới (đã percent-encode → sed-safe)
  NEW_URL="postgresql+psycopg2://${DB_USER}:${DB_PASS_ENC}@127.0.0.1:5432/${DB_NAME}"
  if grep -q '^DATABASE_URL=' "$APP_DIR/.env"; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${NEW_URL}|" "$APP_DIR/.env"
  else
    echo "DATABASE_URL=${NEW_URL}" >> "$APP_DIR/.env"
  fi
  grep -q '^PORT=' "$APP_DIR/.env" || echo "PORT=${APP_PORT}" >> "$APP_DIR/.env"
  echo "    Đã đồng bộ DATABASE_URL trong .env với DB_PASS."
fi
chmod 600 "$APP_DIR/.env"

echo "==> [6/7] systemd service..."
cp "$APP_DIR/scripts/bao-cao-khoa.service" /etc/systemd/system/bao-cao-khoa.service
# fix đường dẫn nếu cần
sed -i "s|/opt/bao-cao-khoa|${APP_DIR}|g" /etc/systemd/system/bao-cao-khoa.service
systemctl daemon-reload
systemctl enable bao-cao-khoa >/dev/null

# quyền user app
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
setfacl -R -m u:$APP_USER:rwx -m u:www-data:r-x "$APP_DIR" 2>/dev/null || true

# ----------------------------------------------------------------------------
# [7/7] Kiểm tra kết nối DB bằng ĐÚNG DATABASE_URL trong .env, tự chữa nếu lỗi,
#       rồi mới init-db + create-admin (in rõ nguyên nhân thật khi thất bại)
# ----------------------------------------------------------------------------
echo "==> [7/7] Khởi tạo CSDL & tài khoản admin..."
if [[ ! -d "$APP_DIR/app" ]]; then
  echo "    ❌ Không thấy $APP_DIR/app — mã nguồn chưa được copy đúng."
  echo "       Kiểm tra lại rsync ở bước [2/7]."
  exit 1
fi
cd "$APP_DIR"

check_db() {
  "$APP_DIR/.venv/bin/python" - <<'PY'
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

url = None
env = Path(".env")
if env.exists():
    for line in env.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip()
            break
if not url:
    print("    ✗ .env không có DATABASE_URL")
    sys.exit(2)
try:
    eng = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    with eng.connect() as c:
        v = c.execute(text("select version()")).scalar()
        print("    ✓ Kết nối DB OK —", (v or "").split(",")[0])
except Exception as e:
    cand = [s.strip() for s in (str(getattr(e, "orig", "") or "") + "\n" + str(e)).splitlines() if s.strip()]
    msg = "(không rõ)"
    for s in cand:  # ưu tiên dòng nêu lý do thật
        if any(k in s for k in ("FATAL", "refused", "could not", "does not exist", "timeout", "no pg_hba")):
            msg = s
            break
    print("    ✗ KẾT NỐI DB THẤT BẠI →", msg)
    sys.exit(1)
PY
}

heal_db() {
  echo "    --- Chẩn đoán PostgreSQL ---"
  pg_isready -h 127.0.0.1 -p 5432 || true
  pg_lsclusters 2>/dev/null || true

  # (a) Postgres chạy chưa / có lắng nghe 5432 không?
  service postgresql start >/dev/null 2>&1 || systemctl start postgresql || true
  sleep 1
  if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    echo "    ✗ Postgres KHÔNG lắng nghe 127.0.0.1:5432"
    echo "      → Xem 'pg_lsclusters' ở trên: nếu cổng khác 5432 thì sửa DATABASE_URL trong .env"
    return 1
  fi

  # (b) Xác thực bằng chính DB_PASS qua TCP (cùng đường đi với ứng dụng)
  if PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d "$DB_NAME" \
       -c "SELECT 1;" >/dev/null 2>&1; then
    echo "    ✓ psql xác thực OK với DB_PASS"
    return 0
  fi
  echo "    ✗ Xác thực psql thất bại — tiến hành tự sửa..."

  # (c) Đặt lại mật khẩu (cùng session đặt password_encryption=scram-sha-256)
  pg_set_pass "$DB_PASS" >/dev/null

  # (d) DB + quyền
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
    || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" >/dev/null
  sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};" >/dev/null || true

  # (e) pg_hba: nếu dòng host dùng md5 nhưng mật khẩu lưu dạng scram → sửa + reload
  local HBA
  HBA="$(sudo -u postgres psql -tAc 'SHOW hba_file;' 2>/dev/null || true)"
  if [[ -n "$HBA" && -f "$HBA" ]] && grep -Eq '^[^#]*\bmd5\b' "$HBA"; then
    echo "    • pg_hba.conf dùng md5 — đổi các dòng host sang scram-sha-256 + reload"
    cp "$HBA" "${HBA}.bak-baocao"
    sed -i '/^\s*#/!s/\bmd5\b/scram-sha-256/g' "$HBA"
    systemctl reload postgresql 2>/dev/null || service postgresql reload 2>/dev/null || true
  fi

  # (f) Thử lại
  if PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d "$DB_NAME" \
       -c "SELECT 1;" >/dev/null 2>&1; then
    echo "    ✓ Đã tự sửa — xác thực OK"
    return 0
  fi
  echo "    ✗ Vẫn thất bại. Lỗi psql thật:"
  PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" || true
  return 1
}

DB_OK=0
for i in 1 2 3; do
  if check_db; then DB_OK=1; break; fi
  echo "    (lần $i/3) Tự chẩn đoán & sửa..."
  heal_db || true
done
if [[ $DB_OK -ne 1 ]]; then
  echo "❌ Không kết nối được PostgreSQL sau khi tự sửa."
  echo "   Gửi lại toàn bộ output trên cho lập trình viên (đã in đủ nguyên nhân thật)."
  exit 1
fi

sudo -u "$APP_USER" env HOME="$APP_DIR" PYTHONPATH="$APP_DIR" \
  "$APP_DIR/.venv/bin/python" -m app.cli init-db
sudo -u "$APP_USER" env HOME="$APP_DIR" PYTHONPATH="$APP_DIR" \
  "$APP_DIR/.venv/bin/python" -m app.cli create-admin "$ADMIN_USER" "$ADMIN_PASS"

systemctl restart bao-cao-khoa
sleep 2
if systemctl is-active --quiet bao-cao-khoa; then
  echo "    ✅ service bao-cao-khoa đang chạy"
else
  echo "    ❌ service lỗi — xem: journalctl -u bao-cao-khoa -n 50"
  systemctl status bao-cao-khoa --no-pager || true
  exit 1
fi

# --- nginx reverse proxy ---
echo "==> Cấu hình nginx (proxy 80 → ${APP_PORT})..."
cat > /etc/nginx/sites-available/${APP_NAME} <<EOF
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 10m;
    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/${APP_NAME} /etc/nginx/sites-enabled/${APP_NAME}
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# firewall (chỉ mở SSH + HTTP; HTTPS thêm khi có domain)
if command -v ufw >/dev/null; then
  ufw allow OpenSSH >/dev/null 2>&1 || true
  ufw allow 'Nginx Full' >/dev/null 2>&1 || ufw allow 80/tcp >/dev/null 2>&1 || true
  echo "    (Không bật ufw tự động — chạy: ufw enable nếu muốn)"
fi

echo ""
echo "============================================================================"
echo " CÀI ĐẶT XONG"
echo "   URL:        http://$(hostname -I | awk '{print $1}')/   (qua nginx)"
echo "   Hoặc thẳng: http://$(hostname -I | awk '{print $1}'):${APP_PORT}/"
echo "   Admin:      ${ADMIN_USER} / ${ADMIN_PASS}   ← ĐỔI NGAY sau lần đăng nhập đầu"
echo "   Service:    systemctl {start|stop|restart|status} bao-cao-khoa"
echo "   Log:        journalctl -u bao-cao-khoa -f"
echo "   App dir:    ${APP_DIR}"
echo "============================================================================"
