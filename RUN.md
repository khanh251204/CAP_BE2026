# Hướng dẫn chạy VoiceCashBook BE

Lệnh dưới đây viết cho Windows (Git Bash / PowerShell). Chạy từ thư mục gốc `BE`.

## 1. Yêu cầu

- Python 3.10+ (Docker dùng 3.11; nên dùng 3.11 trở lên vì Google đã bỏ hỗ trợ 3.10)
- MySQL 8 hoặc TiDB
- FFmpeg có trong `PATH` (xử lý audio)
- Redis (tùy chọn; không có thì session lưu ở bảng `User_Pending_Confirmation`)

## 2. Cài thư viện

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Để chạy test, cài thêm:

```bash
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

## 3. Tạo file `.env`

Đặt ở thư mục gốc, không commit lên Git.

| Biến | Bắt buộc | Ghi chú |
| :--- | :---: | :--- |
| `MYSQL_TRACKER_URL` | ✅ | `mysql+pymysql://user:pass@host:port/db` |
| `JWT_SECRET_KEY` | ✅ | Chuỗi bí mật bất kỳ |
| `GROQ_API_KEY` (`_2`, `_3`...) | ✅ | Cần cho STT và LLM, có thể khai nhiều key để xoay vòng |
| `GEMINI_API_KEY` | | LLM dự phòng, OCR dự phòng |
| `APP_ENV` | | `development` khi chạy local |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | | Thời hạn token |
| `REDIS_URL` | | Bỏ trống thì dùng DB làm session store |
| `GOOGLE_*_CLIENT_ID` | | Đăng nhập Google |
| `SMTP_*` | | Gửi OTP qua email |
| `CLOUDINARY_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | | Lưu file / audio |

Push notification cần thêm file `firebase-service-account.json` ở thư mục gốc.

## 4. Migration và dữ liệu phân quyền

```bash
./.venv/Scripts/python.exe scripts/run_migrations.py
./.venv/Scripts/python.exe scripts/seed_rbac.py   # chỉ khi cần seed lại role / permission
```

Chạy lại migration sau mỗi lần pull code mới có file trong `alembic/versions/`. Dùng DB thật thì cần hỏi trước khi chạy.

## 5. Chạy server

```bash
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

| Địa chỉ | Mô tả |
| :--- | :--- |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/redoc | ReDoc |
| http://127.0.0.1:8000/health | Health check |

Để điện thoại hoặc máy khác trong LAN gọi được, thêm `--host 0.0.0.0`.

## 6. Chạy test

```bash
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -m pytest tests -q
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -m pytest tests/test_multi_item.py -q   # một file
```

Test mặc định dùng SQLite trong bộ nhớ. 4 test tranh chấp tồn kho chỉ chạy khi có MySQL test riêng (tên database phải kết thúc bằng `_test`):

```bash
set TEST_MYSQL_URL=mysql+pymysql://user:pass@127.0.0.1:3306/voicecash_test
```

## 7. Chạy bằng Docker

```bash
docker compose up -d --build
docker compose logs -f api
```

Container tự chạy migration (`docker-entrypoint.sh`) rồi mở cổng 8000. Cần có `.env` cùng thư mục với `docker-compose.yml`.

## 8. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| :--- | :--- |
| `No module named 'redis'` trong log | Chỉ là thông báo; app dùng DB làm session store. Muốn dùng Redis thì cài `redis` và đặt `REDIS_URL`. |
| STT báo lỗi ffmpeg | Cài FFmpeg và thêm vào `PATH`. |
| Lỗi kết nối DB | Kiểm tra `MYSQL_TRACKER_URL`; TiDB cần SSL. |
