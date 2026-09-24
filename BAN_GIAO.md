# TÀI LIỆU BÀN GIAO & NGHIỆM THU
## Hệ thống Báo cáo Công tác Khoa — Bệnh viện (on-premise)

| | |
|---|---|
| **Tên hệ thống** | Báo cáo Công tác Khoa (bao-cao-khoa) |
| **Phiên bản** | Production 1.0 |
| **Ngày bàn giao** | 24/09/2026 |
| **Nền tảng** | Ubuntu 22.04/24.04 · PostgreSQL · FastAPI · Nginx · systemd |
| **Thư mục mã nguồn** | `bao-cao-khoa-prod/` |

---

## 1. Danh mục bàn giao

| # | Hạng mục | Vị trí | Ghi chú |
|---|---|---|---|
| 1 | Mã nguồn ứng dụng | `bao-cao-khoa-prod/app/` | Python / FastAPI |
| 2 | Script cài VPS | `scripts/install-ubuntu.sh` | Chạy 1 lệnh bằng sudo |
| 3 | Systemd service | `scripts/bao-cao-khoa.service` | Tự khởi động cùng máy |
| 4 | Tạo/khôi phục admin | `scripts/create-admin.sh` | |
| 5 | Cấu hình môi trường | `.env.example` → `.env` | SECRET_KEY, DATABASE_URL |
| 6 | Phụ thuộc | `requirements.txt` | `pip install -r` |
| 7 | Hướng dẫn triển khai | `README.md` | |
| 8 | Tài liệu này | `BAN_GIAO.md` | Nghiệm thu + đào tạo + backup |

---

## 2. Checklist nghiệm thu (acceptance)

### 2.1. Cài đặt & vận hành

- [ ] Script cài đặt chạy thành công trên VPS Ubuntu sạch
- [ ] `systemctl status bao-cao-khoa` → **active (running)**
- [ ] Truy cập `http://<ip>/` thấy trang **Đăng nhập**
- [ ] PostgreSQL có database `baocao`, user `baocao`
- [ ] `.env` quyền `600`, không commit lên git

### 2.2. Đăng nhập & phân quyền

- [ ] Chưa đăng nhập → tự chuyển về `/login`
- [ ] Đăng nhập sai mật khẩu → thông báo lỗi, **không** vào được
- [ ] `admin` thấy menu: Tổng quan, Nhập liệu, Báo cáo, **Tổng hợp**, **Cấu hình**, **Người dùng**
- [ ] Tài khoản khoa (vd `kpk`) **không thấy** menu Tổng hợp / Cấu hình
- [ ] Tài khoản khoa gõ URL `/cau-hinh` hoặc `/tong-hop` → trang **403** tiếng Việt
- [ ] Tài khoản khoa chọn khoa khác (`?khoa=2`) → **400/403**, không thấy số liệu khoa khác
- [ ] Đăng xuất → quay lại trang chủ → bắt đăng nhập lại

### 2.3. Nhập liệu

- [ ] Mỗi khoa thấy **mẫu riêng** (mục, dòng khác nhau)
- [ ] Cột **Tổng BHYT / Tổng** tự tính, không nhập tay
- [ ] Lưu thành công; reload trang số liệu còn nguyên
- [ ] **Nhân bản ngày hôm qua** hoạt động
- [ ] Enter nhảy ô tiếp theo; tổng cuối bảng cập nhật real-time

### 2.4. Báo cáo theo kỳ

- [ ] **Ngày / Hôm qua / Tuần (T2–CN) / Tháng / Từ ngày→đến ngày** đều ra số
- [ ] Dòng “Cũ” / “Hiện còn” lấy **đầu/cuối kỳ** (không cộng dồn)
- [ ] Dòng khám/bệnh nhân **cộng dồn** theo khoảng ngày
- [ ] Xuất **Excel** (.xlsx) mở được bằng Excel/LibreOffice, tiếng Việt đủ dấu
- [ ] Xuất **PDF** server-side, tiếng Việt đủ dấu, A4 ngang
- [ ] In từ trình duyệt (Ctrl+P) ẩn menu, chỉ còn bảng báo cáo

### 2.5. Cấu hình mẫu (chỉ admin)

- [ ] Thêm/sửa/xóa **mục** (section) → biểu hiện ngay ở form nhập & báo cáo
- [ ] Thêm/sửa/xóa **dòng**; chọn cách tính: Cộng dồn / Đầu kỳ / Cuối kỳ
- [ ] Tab **Đối tượng**: thêm cột nhập (vd “Đối tượng 6T”), thêm cột tự tính (công thức `hs+tq+te+khac`)
- [ ] Cột mới xuất hiện ở **Nhập liệu**, **Báo cáo**, **Excel**, **PDF**
- [ ] Thêm khoa mới → tự có mẫu trống + đối tượng BHYT mặc định

### 2.6. Quản lý người dùng (chỉ admin)

- [ ] Tạo user + gán **đúng 1 khoa**
- [ ] User mới đăng nhập chỉ thấy khoa được gán
- [ ] Đổi mật khẩu; vô hiệu hóa → không đăng nhập được
- [ ] Không xóa/vô hiệu được chính admin đang đăng nhập

### 2.7. Tổng hợp toàn viện (chỉ admin)

- [ ] `/tong-hop` liệt kê **toàn bộ khoa** active
- [ ] Có dòng TỔNG CỘNG; số khớp với tổng các khoa
- [ ] Xuất PDF tổng hợp mở được
- [ ] Link “Mở” → báo cáo chi tiết từng khoa

### 2.8. Lịch sử sửa số liệu (chỉ admin)

- [ ] Sửa 1 ô số → log ghi **giá trị cũ → mới**, thời gian, người sửa, dòng/cột
- [ ] Lọc theo khoa và khoảng ngày
- [ ] Nhân bản ngày ghi log loại “nhân bản”

---

## 3. Hướng dẫn đào tạo (tóm tắt cho các khoa)

### 3.1. Mỗi sáng nhập báo cáo (~2–3 phút/đối tượng)

1. Mở trình duyệt → `http://<địa-chỉ-hệ-thống>/`
2. Đăng nhập bằng tài khoản **khoa mình** (nhận từ admin)
3. Bấm **Nhập liệu** → kiểm tra **Khoa** và **Ngày**
4. Nhập các ô vàng (chỉ cột đầu vào; cột Tổng tự tính)
5. Bấm **Lưu ngày …** → thấy “✓ Đã lưu …”
6. Nếu hôm trước đã nhập类似 → bấm **Nhân bản từ ngày …** rồi sửa chênh lệch

### 3.2. Cuối ngày / cuối tuần / cuối tháng nộp báo cáo

1. **Báo cáo** → chọn khoa
2. Chọn kỳ: **Hôm nay** / **Tuần này** / **Tháng này** / **Từ ngày → đến ngày**
3. Kiểm tra số → bấm **⬇ Excel** hoặc **⬇ PDF** → nộp file

### 3.3. Quy tắc số liệu quan trọng

| Dòng | Cách tính kỳ |
|---|---|
| Cũ, Hiện còn | Lấy ngày **đầu** / **cuối** kỳ |
| Khám bệnh, Vào, Ra viện, Tử vong… | **Cộng dồn** cả kỳ |
| Cột Tổng BHYT | = HS + TQ + TE + Khác (tự động) |
| Cột Tổng | = Tổng BHYT + Dịch vụ (tự động) |

- Tuần báo cáo: **Thứ 2 → Chủ nhật**
- Số liệu đã lưu có **lịch sử sửa** — admin xem được ai sửa gì

### 3.4. Người quản trị (admin)

| Việc | Đường dẫn |
|---|---|
| Thêm khoa | Cấu hình → **+ Thêm khoa** |
| Sửa mẫu (mục/dòng) | Cấu hình → tab **Mẫu báo cáo** |
| Thêm đối tượng/cột | Cấu hình → tab **Đối tượng** |
| Tạo tài khoản khoa | **Người dùng** |
| Xem ai sửa số liệu | Cấu hình → **Lịch sử sửa** |
| Báo cáo cho ban giám đốc | **Tổng hợp** → Xuất PDF |

---

## 4. Vận hành hệ thống (IT)

### 4.1. Lệnh thường dùng

```bash
# Trạng thái / khởi động lại
sudo systemctl status bao-cao-khoa
sudo systemctl restart bao-cao-khoa

# Log realtime
journalctl -u bao-cao-khoa -f

# Tạo lại / đổi mật khẩu admin
sudo bash /opt/bao-cao-khoa/scripts/create-admin.sh admin 'MatKhauMoiMan123'

# Restart Nginx (sau khi sửa cấu hình)
sudo nginx -t && sudo systemctl reload nginx
```

### 4.2. Backup (bắt buộc — lập lịch hàng ngày)

```bash
#!/bin/bash
# /opt/bao-cao-khoa/scripts/backup.sh  — thêm cron như mục 4.3
set -e
BACKUP_DIR=/var/backups/bao-cao-khoa
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%F_%H%M)

# 1) PostgreSQL
sudo -u postgres pg_dump baocao | gzip > "$BACKUP_DIR/db_$STAMP.sql.gz"

# 2) Mã nguồn + .env (không gồm .venv)
tar --exclude='.venv' --exclude='__pycache__' --exclude='*.db' \
    -czf "$BACKUP_DIR/app_$STAMP.tar.gz" -C /opt bao-cao-khoa

# 3) Giữ 30 bản
find "$BACKUP_DIR" -name '*.gz' -mtime +30 -delete
echo "Backup OK: $STAMP"
```

```bash
chmod +x /opt/bao-cao-khoa/scripts/backup.sh
# cron 02:00 hàng ngày
echo '0 2 * * * root /opt/bao-cao-khoa/scripts/backup.sh >> /var/log/bao-cao-backup.log 2>&1' \
  > /etc/cron.d/bao-cao-backup
```

```bash
# Khôi phục toàn hệ thống (dừng app → backup an toàn hiện tại → nạp lại DB → chạy lại):
sudo bash /opt/bao-cao-khoa/scripts/restore.sh /var/backups/bao-cao-khoa/db_2026-09-24_0200.sql.gz
# kèm phục hồi cả mã nguồn + .env (tuỳ chọn):
sudo bash /opt/bao-cao-khoa/scripts/restore.sh db_....sql.gz app_....tar.gz
```

**Cách 1 — ngay trên giao diện web (khuyến nghị cho quản trị):**

Đăng nhập admin → **Cấu hình → Sao lưu**:

- **Tạo bản sao lưu** — chứa toàn bộ dữ liệu (khoa, mẫu, số liệu, lịch sử, tài khoản) thành 1 file `.json.gz`
- **Tải về** để lưu ở máy khác (bản tốt nhất là bản nằm ngoài server)
- **Phục hồi** từ bản trên máy chủ hoặc **Tải lên** file từ máy khác — hệ thống **tự tạo bản sao lưu an toàn** trước khi ghi đè; mọi thao tác sao lưu/phục hồi đều ghi vào Lịch sử sửa

**Cách 2 — script hệ thống (cho IT, chạy cron mỗi đêm):**


```bash
gunzip -c /var/backups/bao-cao-khoa/db_YYYY-MM-DD_HHMM.sql.gz | \
  sudo -u postgres psql -d baocao --force
```

### 4.3. Nâng cấp phiên bản mới

```bash
# trên VPS
cd /opt/bao-cao-khoa
sudo systemctl stop bao-cao-khoa
# sao lưu trước!
sudo -u postgres pg_dump baocao | gzip > /var/backups/bao-cao-khoa/pre-upgrade.sql.gz
# copy mã nguồn mới đè (trừ .env và bao_cao.db nếu dùng sqlite)
rsync -a /path/moi/ /opt/bao-cao-khoa/ --exclude .env --exclude .venv
sudo -u baocao /opt/bao-cao-khoa/.venv/bin/pip install -r requirements.txt
sudo -u baocao /opt/bao-cao-khoa/.venv/bin/python -m app.cli init-db   # thêm bảng mới nếu có
sudo systemctl start bao-cao-khoa
```

### 4.4. HTTPS (khuyến nghị)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d baocao.benhvien.vn
# sau đó sửa app/main.py: SessionMiddleware(..., https_only=True) và restart
```

### 4.5. Bảo mật tối thiểu

- [ ] Đổi `SEED_ADMIN_PASS` / admin thật ngay sau cài
- [ ] Đổi `DB_PASS` trong PostgreSQL khớp `.env`
- [ ] `.env` chỉ root/baocao đọc được (`chmod 600`)
- [ ] UFW: chỉ mở 22 (SSH) + 80/443
- [ ] Không port 8000 ra Internet trực tiếp (chỉ Nginx)
- [ ] Backup **ngoài** VPS (NAS/máy khác) ít nhất 1 bản/tuần
- [ ] Đổi mật khẩu user khoa định kỳ; vô hiệu tài khoản khi nghỉ việc

---

## 5. Thông tin tài khoản bàn giao

| Vai trò | Username | Mật khẩu mặc định | Hành động |
|---|---|---|---|
| Admin | `admin` | `Admin@123` | **Đổi ngay** lần đầu đăng nhập |
| User khoa | `kpk`, `ngoai`, `noi` | `Khoa@123` | Đổi khi phát cho khoa thật |

> Ghi mật khẩu ra sổ nội bộ — **không** dán vào email/Zalo công khai.

---

## 5b. Quy tắc thay đổi cấu trúc mẫu (bảo toàn số liệu lịch sử)

Từ phiên bản này, **"xóa" = "ngừng sử dụng"** (ẩn đi, KHÔNG xóa số liệu):

- **Ngừng** dòng / nhóm dòng (vd "1.1. Trong giờ") / mục / đối tượng (cột) → ẩn khỏi
  form nhập và báo cáo mới, nhưng **số liệu đã nhập giữ nguyên trong CSDL**.
- Báo cáo theo khoảng thời gian có dữ liệu của phần đã ngừng → hiển thị thêm bảng
  **"Số liệu thuộc dòng/mục đã ngừng"** (HTML/Excel/PDF) → tổng hợp toàn viện vẫn chính xác.
- Có thể **Khôi phục** bất kỳ lúc nào trong Cấu hình (phần mờ "đã ngừng").
- **Đổi tên** dòng/mục/nhóm chỉ nên dùng để đổi cách GỌI (số liệu gắn theo dòng, giữ nguyên).
  Nếu đổi cả Ý NGHĨA: thêm dòng mới + ngừng dòng cũ, đừng đổi tên dòng cũ.
- Nhóm dòng (vd "1.1. Trong giờ / 1.2. Ngoài giờ") giờ quản lý được đầy đủ trong
  Cấu hình: thêm / đổi tên / lên-xuống / ngừng / khôi phục.
- CSDL tạo từ phiên bản cũ được **tự nâng cấp** (thêm cột) khi khởi động ứng dụng —
  không cần thao tác gì.

## 6. Giới hạn đã biết & hướng xử lý

| Vấn đề | Xử lý |
|---|---|
| Chưa có SSO/LDAP | Tạo tài khoản nội bộ theo mẫu người dùng |
| Chưa có duyệt báo cáo (ký số) | Giai đoạn 2: thêm trạng thái “Đã duyệt” + log người duyệt |
| Chưa tự động mail/Zalo | Giai đoạn 2: cron + SMTP nội bộ |
| Số liệu “Tổng chỉ tiêu” tổng hợp | Dòng sum các mẫu — khoa mẫu khác chỉ tiêu sẽ khác; cần thống nhất chỉ tiêu cấp viện nếu muốn so sánh chặt |

---

## 7. Ký bàn giao

| Bên bàn giao | Bên tiếp nhận |
|---|---|
| Họ tên: …………………… | Họ tên: …………………… |
| Chức vụ: …………………… | Chức vụ: …………………… |
| Ngày: ………/……../2026 | Ngày: ………/……../2026 |
| Ký/ghép tên: …………… | Ký/ghép tên: …………… |

---

*Kết thúc tài liệu.*
