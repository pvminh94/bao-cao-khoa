# Hệ thống Báo cáo Công tác Khoa — **Production**

Phiên bản triển khai thật: **đăng nhập + phân quyền theo khoa + khai báo đối tượng linh hoạt + PostgreSQL + script cài VPS Ubuntu**.

```
Form nhập theo khoa → PostgreSQL → Báo cáo động (ngày/tuần/tháng/khoảng) → Excel / In PDF
```

## ⚡ Cài production: clone + 1 lệnh

**Yêu cầu:** VPS/VM **Ubuntu 22.04 hoặc 24.04**, có quyền `sudo`, port 80 (HTTP) mở.

```bash
# 1) Clone
git clone https://github.com/pvminh94/bao-cao-khoa.git
cd bao-cao-khoa

# 2) Cài hoàn tất (1 lệnh) — KHUYẾN NGHỊ đổi mật khẩu trước khi chạy
sudo DB_PASS='mat_khau_postgres_manh' ADMIN_PASS='mat_khau_admin_manh' bash install.sh
```

Hoặc gộp thành **một dòng**:

```bash
git clone https://github.com/pvminh94/bao-cao-khoa.git \
  && cd bao-cao-khoa \
  && sudo DB_PASS='DoiMatKhauPg!' ADMIN_PASS='DoiMatKhauAdmin!' bash install.sh
```

**Script tự làm hết:**

| # | Bước |
|---|---|
| 1 | `apt` Python, PostgreSQL, Nginx, font DejaVu… |
| 2 | Tạo user hệ thống `baocao` + copy mã nguồn → `/opt/bao-cao-khoa` |
| 3 | Tạo DB `baocao` + role PostgreSQL |
| 4 | venv + `pip install -r requirements.txt` |
| 5 | Sinh `.env` (SECRET_KEY ngẫu nhiên, DATABASE_URL trỏ Postgres) |
| 6 | systemd `bao-cao-khoa` (enable + start) |
| 7 | Init DB, seed khoa/mẫu mẫu, tạo admin |
| 8 | Nginx reverse proxy **port 80** → app |

**Sau khi cài xong:**

```text
Mở trình duyệt:  http://<IP-VPS>/
Đăng nhập:       admin / <ADMIN_PASS bạn đã đặt>
```

Chạy lại (nâng cấp mã nguồn): clone/pull rồi chạy lại `sudo bash install.sh` — **không mất** `.env` và dữ liệu PostgreSQL.

---

## 1. Tính năng

| Nhóm | Chi tiết |
|---|---|
| **Đăng nhập** | PBKDF2-SHA256 (260k iter), phiên cookie 12h, đăng xuất |
| **Phân quyền** | `admin` = toàn khoa + cấu hình; `user` = **chỉ khoa được gán**, vào khoa khác → 403 |
| **Cấu hình mẫu** | **Chỉ admin**: thêm/sửa/xóa khoa, mục, dòng, cách tính kỳ (sum/đầu/cuối) |
| **Khai báo đối tượng** | **Chỉ admin**: cột nhập tay + cột tự tính (công thức) — *không set cứng* HS/TQ/TE… |
| **Quản lý người dùng** | tạo tài khoản, gán khoa, đổi mật khẩu, vô hiệu hóa |
| **Báo cáo** | ngày / hôm qua / tuần (T2–CN) / tháng / từ ngày→đến ngày; **xuất Excel + PDF server-side** + in |
| **Tổng hợp toàn viện** | **Chỉ admin**: bảng so sánh các khoa (khám/vào/ra/tử vong/hiện còn/tổng) cho ban giám đốc + PDF |
| **Lịch sử sửa số liệu** | **Chỉ admin**: audit log — ai sửa ô nào, từ gì → gì, lọc theo khoa/khoảng ngày |
| **CSDL** | PostgreSQL (production) · SQLite (fallback test) |

## 2. Chạy thử cục bộ (SQLite — không cần Postgres)

```bash
cd bao-cao-khoa-prod
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # DATABASE_URL mặc định trỏ Postgres — đổi sang:
# DATABASE_URL=sqlite:///./bao_cao.db
python -m app.cli init-db     # tạo bảng + seed admin/khoa mẫu
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Tài khoản seed:**

| Username | Password | Quyền |
|---|---|---|
| `admin` | `Admin@123` | Admin toàn hệ thống |
| `kpk` | `Khoa@123` | User — Khu Phẫu khoái |
| `ngoai` | `Khoa@123` | User — Khoa Ngoại |
| `noi` | `Khoa@123` | User — Khoa Nội tổng hợp |

> Đổi ngay sau khi triển khai thật.

## 3. Cài trên VPS Ubuntu 22.04 / 24.04

### 3.1. Chuẩn bị

```bash
# Máy ảo/VDPS: Ubuntu 22.04+, user có sudo, mở port 80 (và 22)
# Sao chép thư mục bao-cao-khoa-prod/ lên server, ví dụ:
scp -r bao-cao-khoa-prod/ user@your-vps:/tmp/
ssh user@your-vps
```

### 3.2. Chạy script cài đặt (một lệnh)

```bash
cd /tmp/bao-cao-khoa-prod

# KHUYẾN NGHỊ: đổi mật khẩu DB + admin trước khi chạy
sudo DB_PASS='mat_khau_postgres_man' ADMIN_PASS='mat_khau_admin_man' \
  bash scripts/install-ubuntu.sh
```

Script tự động:

1. Cài Python, PostgreSQL, Nginx, UFW  
2. Tạo user hệ thống `baocao` + thư mục `/opt/bao-cao-khoa`  
3. Tạo DB `baocao` + role PostgreSQL  
4. venv + `pip install`  
5. Sinh `.env` (SECRET_KEY ngẫu nhiên)  
6. `systemd` service **bao-cao-khoa** (start + enable)  
7. Init DB, seed, tạo admin  
8. Nginx reverse proxy port 80 → app  

### 3.3. Vận hành hằng ngày

```bash
sudo systemctl status bao-cao-khoa
sudo systemctl restart bao-cao-khoa
journalctl -u bao-cao-khoa -f          # xem log

# tạo/đổi admin
sudo bash scripts/create-admin.sh admin 'MatKhauMoiMan123'

# backup PostgreSQL
sudo -u postgres pg_dump baocao | gzip > /backup/baocao_$(date +%F).sql.gz
```

### 3.4. HTTPS (khuyến nghị khi có domain)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d baocao.benhvien.local
# sau đó trong app/main.py bật: SessionMiddleware(..., https_only=True)
```

## 4. Phân quyền — cách hoạt động

```
Đăng nhập
   ├─ role = admin  → thấy mọi khoa
   │                   + Cấu hình / Người dùng / Lịch sử / Tổng hợp toàn viện
   └─ role = user   → dept_id = khoa được gán
                        ├─ /nhap, /bao-cao ép về dept_id của mình
                        ├─ ?khoa=<khoa khác> → HTTP 403
                        └─ /cau-hinh*, /tong-hop → HTTP 403
```

Middleware kiểm tra ở `app/deps.py`: `get_current_user` · `require_admin` · `resolve_dept_id`.

## 5. Cấu trúc thư mục

```
bao-cao-khoa-prod/
├── app/
│   ├── main.py            # FastAPI + SessionMiddleware + router
│   ├── config.py          # .env
│   ├── database.py        # engine SQLAlchemy (PG/SQLite)
│   ├── models.py          # users, departments, templates, columns_def, entries...
│   ├── security.py        # PBKDF2 hash, phiên
│   ├── deps.py            # phân quyền
│   ├── report.py          # tổng hợp theo kỳ
│   ├── excel_export.py    # xuất xlsx
│   ├── seed.py            # seed admin + khoa + đối tượng mẫu
│   ├── cli.py             # init-db / create-admin
│   ├── routers/           # auth, pages, entry, reports, admin
│   ├── templates/         # giao diện
│   └── static/
├── scripts/
│   ├── install-ubuntu.sh  # ← cài VPS một lệnh
│   ├── create-admin.sh
│   └── bao-cao-khoa.service
├── .env.example
└── requirements.txt
```

## 6. Nâng cấp / mở rộng gợi ý

- Bật `https_only=True` cho session sau khi có TLS  
- Đổi host systemd `127.0.0.1` + chỉ nginx expose ra ngoài  
- Tích hợp SSO nội bộ (LDAP/AD) nếu bệnh viện có  
- Job tổng hợp báo cáo toàn viện 23:00 hàng ngày (cron + gửi mail/Zalo)  

**Đã có sẵn trong phiên bản này:**

- ✅ Lịch sử sửa số liệu (audit log) → `/cau-hinh/lich-su`  
- ✅ Tổng hợp toàn viện cho ban giám đốc → `/tong-hop` (+ PDF)  
- ✅ Xuất PDF server-side (reportlab + font DejaVu tiếng Việt) → nút **PDF** ở trang báo cáo  

## 7. So với bản demo

| | Demo (`bao-cao-khoa/`) | Production (`bao-cao-khoa-prod/`) |
|---|---|---|
| Đăng nhập | ❌ | ✅ PBKDF2 + session |
| Phân quyền khoa | ❌ | ✅ user chỉ thấy khoa mình |
| Cấu hình form | ai cũng vào được | ✅ **chỉ admin** |
| Đối tượng/cột | hardcode 7 cột | ✅ **khai báo thêm/bớt/công thức** |
| CSDL | SQLite file | ✅ **PostgreSQL** (SQLite fallback) |
| Cài VPS | manual | ✅ **script Ubuntu + systemd + nginx** |
