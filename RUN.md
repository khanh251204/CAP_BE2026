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

### Chuẩn bị

- Cài Docker Desktop (Windows) và bật nó lên. Kiểm tra: `docker --version`, `docker compose version`.
- Có file `.env` cùng thư mục với `docker-compose.yml` (xem mục 3). Compose nạp nó qua `env_file`.
- `MYSQL_TRACKER_URL` phải trỏ tới DB mà **container** truy cập được. Nếu DB chạy trên máy bạn, `127.0.0.1` trong container là chính container đó, hãy dùng `host.docker.internal` thay cho `127.0.0.1`.
- Muốn push notification thì để `firebase-service-account.json` ở thư mục gốc (file này được copy vào image).

### Chạy

```bash
docker compose up -d --build     # build image và chạy nền
docker compose ps                # xem trạng thái, cột STATUS phải là "healthy"
docker compose logs -f api       # xem log (Ctrl+C để thoát, container vẫn chạy)
```

Khi khởi động, container tự chạy `python scripts/run_migrations.py` (qua `docker-entrypoint.sh`) rồi mở Uvicorn 4 worker ở cổng 8000. Nếu migration lỗi thì container dừng, xem nguyên nhân bằng `docker compose logs api`.

Kiểm tra: http://localhost:8000/health và http://localhost:8000/docs.

### Lệnh hay dùng

| Việc | Lệnh |
| :--- | :--- |
| Dừng, giữ container | `docker compose stop` |
| Dừng và xoá container | `docker compose down` |
| Khởi động lại | `docker compose restart api` |
| Build lại sau khi sửa code hoặc `requirements.txt` | `docker compose up -d --build` |
| Build lại từ đầu, không dùng cache | `docker compose build --no-cache` |
| Vào shell trong container | `docker compose exec api sh` |
| Chạy migration thủ công | `docker compose exec api python scripts/run_migrations.py` |
| Seed lại role / permission | `docker compose exec api python scripts/seed_rbac.py` |
| Chạy test trong container | cài `pytest` trước (`docker compose exec api pip install pytest`), rồi `docker compose exec api python -m pytest tests -q` |

`docker compose down` không xoá dữ liệu: log (`app_logs`) và Data Lake (`app_data_lake`) nằm trong volume. Muốn xoá cả volume thì thêm `-v` (mất dữ liệu, cân nhắc trước).

### Đổi cấu hình

- Đổi `.env` thì chạy `docker compose up -d` để container nạp lại (không cần build).
- Đổi số worker: sửa `--workers` ở dòng `CMD` trong `Dockerfile` rồi build lại.
- Đổi cổng ngoài: sửa `"8000:8000"` trong `docker-compose.yml`, ví dụ `"9000:8000"` thì truy cập qua cổng 9000.
- Redis: đặt `REDIS_URL` trong `.env`. Image chỉ chứa API, Redis cần chạy riêng.

### Lưu ý

- Repo chưa có `.dockerignore`, nên `COPY . .` đưa cả `.env`, `.venv`, `firebase-service-account.json` và các thư mục benchmark vào image. Không đẩy image này lên registry công khai, và nên thêm `.dockerignore` để image gọn hơn.
- Image không cài gói OCR (`requirements-ocr.txt`), nên route OCR không chạy trong Docker nếu chưa cài thêm.

### Dùng chung với ngrok

Docker và ngrok chạy cùng được. Cách đơn giản nhất là chạy ngrok trên máy host, trỏ vào cổng mà container đã mở:

```bash
docker compose up -d --build
ngrok http 8000
```

ngrok in ra một link `https://xxxx.ngrok-free.app`, dùng link đó làm địa chỉ API cho app mobile (FE). Kiểm tra bằng `https://xxxx.ngrok-free.app/health`.

- Link miễn phí đổi sau mỗi lần chạy lại ngrok, nhớ cập nhật lại trong FE.
- Gọi từ trình duyệt (Admin web) thì thêm link ngrok vào `CORS_ORIGINS` trong `.env`, rồi `docker compose up -d`. App mobile gốc không bị CORS chặn.
- Cổng 8000 là cổng ngoài ở `docker-compose.yml`; nếu bạn đổi thành `9000:8000` thì chạy `ngrok http 9000`.

## 8. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| :--- | :--- |
| `No module named 'redis'` trong log | Chỉ là thông báo; app dùng DB làm session store. Muốn dùng Redis thì cài `redis` và đặt `REDIS_URL`. |
| STT báo lỗi ffmpeg | Cài FFmpeg và thêm vào `PATH`. |
| Lỗi kết nối DB | Kiểm tra `MYSQL_TRACKER_URL`; TiDB cần SSL. |
