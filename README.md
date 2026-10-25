# 🎙️ VoiceCashBook – Backend

Backend của **VoiceCashBook** – sổ thu chi bằng giọng nói cho hộ kinh doanh nhỏ. Xây dựng bằng **FastAPI + SQLAlchemy + MySQL/TiDB**, cung cấp REST API và WebSocket cho ứng dụng React Native và trang Admin.

Người dùng chỉ cần nói *"bán 5 lon coca cho chị Lan, nợ 50k"* → hệ thống nhận dạng giọng nói, hiểu nghiệp vụ, kiểm tra tồn kho/công nợ, tạo **bản nháp** cho người dùng xác nhận, rồi mới ghi vào sổ.

> Tài liệu liên quan: [AGENTS.md](AGENTS.md) (nguyên tắc phát triển AI Agent), [STATUS.md](STATUS.md) (tiến độ), [docs/](docs/) (nghiệp vụ, ERD, API contract).

---

## 📑 Mục lục

1. [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
2. [Kiến trúc tổng quan](#-kiến-trúc-tổng-quan)
3. [Kiến trúc phân lớp (Layered Architecture)](#-kiến-trúc-phân-lớp)
4. [Hệ thống AI Agent](#-hệ-thống-ai-agent)
5. [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
6. [Cơ sở dữ liệu](#-cơ-sở-dữ-liệu)
7. [Bảo mật & phân quyền](#-bảo-mật--phân-quyền)
8. [Tác vụ nền & Realtime](#-tác-vụ-nền--realtime)
9. [Nhóm API chính](#-nhóm-api-chính)
10. [Cài đặt & chạy](#-cài-đặt--chạy)
11. [Kiểm thử](#-kiểm-thử)
12. [Quy ước phát triển](#-quy-ước-phát-triển)

---

## 🚀 Công nghệ sử dụng

| Nhóm | Công nghệ |
| :--- | :--- |
| Web framework | FastAPI, Uvicorn (multi-worker), Starlette WebSocket |
| ORM & Migration | SQLAlchemy 2.x, Alembic |
| Database | MySQL / TiDB (kết nối SSL) |
| Cache / Session | Redis (tùy chọn) – fallback bảng `User_Pending_Confirmation` |
| Speech-to-Text | Groq Whisper `whisper-large-v3-turbo`, FFmpeg + WebRTC VAD |
| LLM | `openai/gpt-oss-120b` trên Groq LPU (chính), Gemini (dự phòng) |
| Tool calling | MCP (FastMCP) – Product / Inventory / Debt / Expense / Report |
| Xác thực | JWT (python-jose), bcrypt/passlib, Google OAuth, OTP qua email |
| Lưu trữ & Thông báo | Cloudinary (file/audio), Firebase Cloud Messaging (push), SMTP |
| Validation & Config | Pydantic v2, pydantic-settings |
| Triển khai | Docker (Python 3.11-slim, non-root), docker-compose |

---

## 🏗️ Kiến trúc tổng quan

```text
┌───────────────────────┐      ┌───────────────────────┐
│  Mobile (React Native)│      │   Admin Web Dashboard │
└───────────┬───────────┘      └───────────┬───────────┘
            │   REST /api/v1  ·  WebSocket /ws/*       │
            └──────────────────┬───────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│  Middleware: CORS · SystemLogMiddleware · Exception handlers │
│  Guard: JWT + RBAC (require_permission) · Closing guard      │
├──────────────────────────────────────────────────────────────┤
│  Routes ─► Controllers ─► Services ─► Repositories ─► Models │
│                              │                               │
│                              ▼                               │
│                 AI Agent (app/ai) ─► MCP Tools               │
├──────────────────────────────────────────────────────────────┤
│  Background schedulers: Closing · Token/Notification cleanup │
│                         · Inactivity reminder (FCM)          │
└───────┬──────────────┬──────────────┬───────────────┬────────┘
        ▼              ▼              ▼               ▼
   MySQL / TiDB      Redis       Groq / Gemini   Cloudinary · FCM · SMTP
                   (tùy chọn)       APIs          · Data Lake (file)
```

Điểm khởi động là [app/main.py](app/main.py): khi `lifespan` chạy, ứng dụng sẽ
1. kiểm tra kết nối DB (`SELECT 1`),
2. cài **closing guard** – chặn ghi giao dịch vào kỳ đã chốt sổ,
3. đồng bộ danh mục quyền RBAC từ [app/configs/permissions.py](app/configs/permissions.py) vào DB,
4. khởi tạo Data Lake và các scheduler nền.

Mọi router được gắn dưới tiền tố `/api/v1`. Endpoint `/health` dùng cho Docker healthcheck.

---

## 🧱 Kiến trúc phân lớp

```text
HTTP Request
    │
    ▼
routes/        Khai báo endpoint, Depends (auth, permission), parse schema
    │
    ▼
controllers/   Điều phối request → service, định dạng response (không chứa nghiệp vụ)
    │
    ▼
services/      Business logic: bán hàng, công nợ FIFO, tồn kho, chốt sổ, báo cáo...
    │
    ▼
repositories/  Truy vấn DB (CRUD, query phân trang), luôn lọc theo user_id
    │
    ▼
models/        SQLAlchemy ORM (map 1-1 với bảng theo ERD)
```

| Lớp | Vai trò | Ví dụ |
| :--- | :--- | :--- |
| `schemas/` | Pydantic request/response, validate đầu vào | `transaction_schema.py`, `agent_schema.py` |
| `routes/` | Endpoint + dependency (chuẩn RESTful) | `transaction_route.py`, `groq_route.py`, `admin_*_route.py` |
| `controllers/` | Cầu nối route ↔ service | `transaction_controller.py`, `debt/` |
| `services/` | Nghiệp vụ, chia module con theo domain | `debt/`, `inventory/`, `closing/`, `reports/`, `audio/`, `auth/` |
| `repositories/` | Truy cập dữ liệu | `debt/debt_query_repo.py`, `inventory/inventory_stock_repo.py` |
| `models/` | ORM entity | `transaction_model.py`, `debt_model.py` |
| `configs/` | Settings, DB, JWT, cookie, RBAC, Firebase, Cloudinary | `settings.py`, `database.py`, `jwt.py` |
| `middlewares/` | Ghi log hệ thống cho mọi request | `system_log_middleware.py` |

Module nghiệp vụ lớn được tách theo kiểu **CQRS nhẹ**, ví dụ công nợ: `debt_command_repo` (ghi) / `debt_query_repo` (đọc) / `debt_paginated_repo` (phân trang); tồn kho: `inventory_lookup_repo` / `inventory_mutation_repo` / `inventory_stock_repo`.

---

## 🤖 Hệ thống AI Agent

AI Agent hoạt động theo mô hình **2 pha**: *Phân tích → Chờ xác nhận → Commit DB*. LLM **chỉ** phân loại intent và trích xuất thực thể; mọi quy tắc nghiệp vụ (tồn kho, giá, công nợ, cho phép/từ chối) do backend quyết định.

### Luồng xử lý

```text
[Giọng nói / Text]
      │  POST /api/v1/speech/transcriptions  →  POST /api/v1/agent/messages
      ▼
Audio Pipeline (services/audio)          FFmpeg decode 16kHz → VAD → khử nhiễu
      │                                   → lọc hallucination
      ▼
Groq Whisper large-v3-turbo              Speech-to-Text
      ▼
NormalizationService (ai/rag)            Regex + từ điển: số chữ, đơn vị, tiền tệ,
      │                                   phương ngữ (< 10ms, in-memory)
      ▼
LLM gpt-oss-120b (ai/llm, ai/prompts)    JSON: { intent, entities }
      ▼
Agent Orchestrator (ai/core/agent.py)
      ▼
IntentRouter (ai/core/router.py)         intent + alias → handler
      ▼
Intent Handler (ai/intents/<intent>/)
  ├─ validator.py   kiểm tra thực thể bắt buộc
  ├─ MCP tools      tra cứu sản phẩm, tồn kho, khách hàng, công nợ
  ├─ Business rules RESELLER / PRODUCER / SERVICE
  └─ payload.py     tính tiền bằng Decimal → draft payload
      ▼
status = waiting_confirmation            lưu SessionStoreService (TTL 10 phút)
      │
      │  POST /api/v1/agent/pending-action/confirmation   (hủy: DELETE /api/v1/agent/pending-action)
      ▼
AgentConfirmService                      validate lại payload người dùng sửa
      ▼
MCP / Service thực thi trong 1 DB transaction (atomic, rollback nếu lỗi)
  Transaction · Transaction_Detail · Inventory_Transaction · Debt / Debt_Payment
      ▼
DataLakeService (async)                  lưu audio, kết quả AI, diff người dùng sửa
```

### Thành phần

| Thư mục | Vai trò |
| :--- | :--- |
| [app/ai/core/](app/ai/core/) | `Agent` (orchestrator) và `IntentRouter` |
| [app/ai/intents/](app/ai/intents/) | Mỗi intent một thư mục: `handler.py`, `validator.py`, `payload.py` |
| [app/ai/mcp/](app/ai/mcp/) | 5 FastMCP server (`product`, `inventory`, `debt`, `expense`, `report`) + `client.py` (`call_mcp_tool`) gọi tool **in-process** qua chỉ mục tool → server |
| [app/ai/llm/](app/ai/llm/) | `groq_service.py` (chính), `gemini_service.py` (dự phòng) |
| [app/ai/models/](app/ai/models/) | Adapter model: Groq, Ollama, Llama local |
| [app/ai/prompts/](app/ai/prompts/) | System prompt cho intent, entity, output JSON |
| [app/ai/rag/](app/ai/rag/) | `normalization_service.py` + `knowledge/` (đơn vị, tiền tệ, phương ngữ) |
| [app/ai/evaluation/](app/ai/evaluation/) | Bộ đánh giá độ chính xác intent/entity trên dataset CSV |

### Intent được hỗ trợ

| Nhóm | Intent (kèm alias) |
| :--- | :--- |
| **Capstone 1 – Giao dịch tài chính** | `ban_hang` · `mua_hang` (`nhap_hang`) · `chi_phi` (`chi_tien`) · `khach_ghi_no` (`ghi_no_khach_hang`) · `thu_no_khach` (`thu_no_khach_hang`) · `ghi_no_nha_cung_cap` (`ncc_ghi_no`) · `tra_no_nha_cung_cap` (`tra_no_ncc`, `thu_no_nha_cung_cap`) |
| **Capstone 2 – Sản phẩm** | `them_san_pham` · `sua_san_pham` · `xoa_san_pham` (soft-delete) · `tim_san_pham` (`xem_san_pham`) |
| **Capstone 2 – Kho nội bộ** | `nhap_kho` · `xuat_kho` · `hang_hong` · `kiem_kho` |
| **Capstone 2 – Báo cáo** | `bao_cao` |

### Quy tắc nghiệp vụ theo loại hình kinh doanh

| `business_type` | `product_type` | Khi bán (`ban_hang`) |
| :--- | :--- | :--- |
| `RESELLER` | `RESALE` | Bắt buộc đủ tồn kho, nếu thiếu → `INSUFFICIENT_STOCK`; tạo `Inventory_Transaction OUT` (có khóa dòng chống race condition) |
| `PRODUCER` | `FINISHED_GOOD` | Được bán khi tồn = 0 (làm theo đơn) |
| `PRODUCER` | `RAW_MATERIAL` | Không được bán → `cannot_sell_raw_material` |
| `SERVICE` | – | Bỏ qua kiểm tra kho, không tạo phiếu xuất |

Chi tiết xem [AGENTS.md](AGENTS.md) và [docs/BUSINESS_RULES_RESELLER_PRODUCER.md](docs/BUSINESS_RULES_RESELLER_PRODUCER.md).

---

## 📂 Cấu trúc thư mục

```text
BE/
├── app/
│   ├── main.py                 # Khởi tạo FastAPI, lifespan, middleware, đăng ký router
│   ├── api/                    # Endpoint STT (stt.py)
│   ├── ai/                     # AI Agent: core, intents, mcp, llm, prompts, rag, evaluation
│   ├── configs/                # settings, database, jwt, cookie, roles, permissions, firebase...
│   ├── controllers/            # Điều phối request → service
│   ├── middlewares/            # SystemLogMiddleware
│   ├── models/                 # SQLAlchemy ORM models
│   ├── repositories/           # Data access (debt/, inventory/ tách đọc/ghi)
│   ├── routes/                 # Endpoint người dùng + admin_* + WebSocket (reports/)
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # Business logic
│   │   ├── audio/              #   Pipeline xử lý âm thanh (decoder, VAD, noise, hallucination)
│   │   ├── auth/               #   Đăng ký, đăng nhập, mật khẩu, hồ sơ
│   │   ├── closing/            #   Chốt sổ: action, query, guard, email báo cáo
│   │   ├── debt/               #   Công nợ khách hàng / NCC, cấn trừ FIFO
│   │   ├── inventory/          #   Biến động & kiểm tra tồn kho
│   │   ├── reports/            #   Báo cáo doanh thu, mua hàng, chi phí, công nợ, live
│   │   ├── agent_confirm_service.py, session_store_service.py, data_lake_service.py
│   │   └── *_scheduler / *_cleanup_service.py   # Tác vụ nền
│   └── static/                 # Trang quản trị RBAC (admin_rbac.html)
├── alembic/                    # Migration schema DB
├── data_lake/                  # raw/voice · processed/ai_result · feedback/correction · dataset
├── docs/                       # Tài liệu nghiệp vụ, ERD, API contract
├── evaluation/                 # Kết quả đánh giá AI
├── scripts/                    # run_migrations, seed_rbac, tiện ích bảo trì
├── tests/                      # Pytest: business rules, RBAC, chốt sổ, chống trùng...
├── test_api/                   # Bộ test API end-to-end (Playwright)
├── Dockerfile · docker-compose.yml · docker-entrypoint.sh
├── requirements.txt
├── AGENTS.md · STATUS.md
└── README.md
```

---

## 🗄️ Cơ sở dữ liệu

Các bảng chính (theo [docs/erd_new.md](docs/erd_new.md)):

| Nhóm | Bảng |
| :--- | :--- |
| Người dùng & phân quyền | `User`, `Store`, `Role`, `Permission`, `Refresh_Token`, `OTP_Code` |
| Danh mục | `Product`, `Category`, `Customer`, `Supplier`, `Account` |
| Giao dịch | `Transaction`, `Transaction_Detail`, `Inventory_Transaction` |
| Công nợ | `Debt` (`RECEIVABLE` / `PAYABLE`), `Debt_Payment` |
| Chốt sổ | `closing_period`, `closing_transaction`, `closing_report`, `closing_setting` |
| AI & giọng nói | `Intent`, `Voice_Record`, `User_Correction`, `User_Pending_Confirmation` |
| Hệ thống | `system_logs` |

Enum cố định theo ERD:
- `payment_status`: `PAID`, `PARTIAL`, `PENDING`
- `Inventory_Transaction.inventory_type`: `IN`, `OUT`, `DAMAGE`, `ADJUSTMENT`
- `User.business_type`: `RESELLER`, `PRODUCER`, `SERVICE`
- `Product.product_type`: `RESALE`, `RAW_MATERIAL`, `FINISHED_GOOD`

Nguyên tắc dữ liệu:
- **Multi-tenant**: mọi truy vấn đều lọc theo `user_id` của người đăng nhập.
- **Atomic**: giao dịch + chi tiết + phiếu kho + công nợ được commit trong cùng một session, lỗi thì rollback toàn bộ.
- **Soft-delete** sản phẩm đã có lịch sử (`is_active = False`).
- **Chốt sổ**: không ghi giao dịch mới lùi ngày vào kỳ đã chốt (mã lỗi `PERIOD_CLOSED`).

Migration được quản lý bằng **Alembic** (`alembic/versions/`) và chạy tự động qua `scripts/run_migrations.py` khi container khởi động.

---

## 🔐 Bảo mật & phân quyền

- **Xác thực**: JWT access token (15 phút) + refresh token (15 ngày, lưu DB). Token được đọc theo thứ tự: cookie HttpOnly → header `Authorization: Bearer` → query `?token=` (dùng cho WebSocket).
- **Đăng nhập**: email/mật khẩu (bcrypt), Google OAuth (Web/iOS/Android), OTP qua email cho đăng ký và quên mật khẩu.
- **RBAC**: 2 vai trò `user` / `admin`; quyền dạng `module:action` (`product:read`, `debt:manage`, `voice:use`...) khai báo trong [app/configs/permissions.py](app/configs/permissions.py), tự đồng bộ vào DB khi khởi động. Endpoint dùng `Depends(require_permission("..."))`; mỗi intent AI cũng được ánh xạ tới quyền tương ứng (`INTENT_PERMISSIONS`).
- **Quyền luôn đọc từ DB**, không tin claim `role` trong token.
- **Audit**: `SystemLogMiddleware` ghi log mọi request vào `system_logs`.

---

## ⏱️ Tác vụ nền & Realtime

| Thành phần | Chức năng |
| :--- | :--- |
| `ClosingScheduler` | Tự động chốt sổ theo cấu hình (ngày/tháng/quý/năm), gửi email báo cáo |
| `TokenCleanupScheduler` | Dọn refresh token hết hạn |
| `NotificationCleanupScheduler` | Dọn thông báo cũ |
| `InactivityReminderScheduler` | Nhắc người dùng không mở app 7 ngày (FCM push) |
| `StockAlertService` | Cảnh báo sản phẩm sắp hết hàng |
| WebSocket `/ws/reports`, `/ws/dashboard`, `/ws/closing` | Đẩy số liệu doanh thu, chi phí, công nợ, tồn kho và trạng thái chốt sổ theo thời gian thực |

---

## 🌐 Nhóm API chính

API theo chuẩn **RESTful**, tất cả dưới tiền tố `/api/v1`:
- tên tài nguyên là danh từ số nhiều, kebab-case; hành động thể hiện qua HTTP method (không có động từ trong URL);
- tài nguyên con lồng theo cha (`/customers/{id}/debts`), lọc/tìm kiếm bằng query (`/products?name=`);
- đổi trạng thái bằng `PATCH` lên chính tài nguyên (`PATCH /closing-periods/{id}` `{ "status": "OPEN" }`);
- tạo mới trả `201 Created`; tài nguyên của người đang đăng nhập nằm dưới `/users/me`.

Bảng chuyển đổi URL cũ → mới: [docs/API_REST_MIGRATION.md](docs/API_REST_MIGRATION.md). Danh sách đầy đủ xem Swagger tại `/docs`.

| Nhóm | Endpoint |
| :--- | :--- |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/google`, `/auth/refresh`, `/auth/logout`, `/auth/otp`, `/auth/otp/verification`, `/auth/password-reset` |
| Người dùng hiện tại | `GET/PATCH /users/me`, `GET /users/me/permissions`, `PUT /users/me/password`, `POST /users/me/devices` |
| Giọng nói & AI | `POST /speech/transcriptions?provider=groq\|gemini`, `POST /agent/messages`, `POST /agent/pending-action/confirmation`, `DELETE /agent/pending-action` |
| Sản phẩm | `GET/POST /products` (`?name=`), `GET/PUT/DELETE /products/{id}`, `GET/POST /products/{id}/inventory-transactions`, `POST /products/{id}/stock-counts` |
| Kho | `GET /inventory/items`, `GET /inventory/alerts`, `GET /inventory/stock` |
| Bán / mua | `POST /sales`, `POST /purchases` |
| Giao dịch | `GET/POST /transactions`, `GET/PUT/DELETE /transactions/{id}` |
| Khách hàng / NCC | `/customers`, `/suppliers` (CRUD), `GET/POST /customers/{id}/debts`, `POST /customers/{id}/debt-payments` (tương tự cho `/suppliers`) |
| Công nợ | `GET /debts` (`?direction=RECEIVABLE\|PAYABLE`), `GET /debts/summary`, `GET /debts/{id}`, `GET/POST /debts/{id}/payments` |
| Báo cáo | `GET /reports/summary`, `/reports/sales`, `/reports/purchases`, `/reports/expenses`, `/reports/debts`, `/reports/inventory`, `/reports/live`, `/reports/transactions[/{id}]` |
| Chốt sổ | `GET/POST /closing-periods`, `POST /closing-periods/preview`, `GET/PATCH /closing-periods/{id}`, `GET /closing-periods/{id}/transactions`, `GET/PUT /closing-settings`, `GET /closing-reports`, `POST /closing-reports/{id}/deliveries` |
| Thông báo | `GET/POST/DELETE /notifications`, `PATCH/DELETE /notifications/{id}` |
| Admin | `/admin/dashboard`, `/admin/users`, `/admin/products`, `/admin/transactions`, `/admin/voice-records`, `/admin/voice-corrections`, `/admin/datasets`, `/admin/rbac`, `/admin/closing`, `/admin/system-logs`, `/admin/notifications` |
| WebSocket | `/ws/reports`, `/ws/dashboard`, `/ws/closing` |

Hợp đồng API cho Frontend: [docs/api_fe_contract.md](docs/api_fe_contract.md), [docs/ai-api-contract.md](docs/ai-api-contract.md) (một số tài liệu cũ trong `docs/` có thể còn ghi URL trước chuẩn hóa — đối chiếu bảng chuyển đổi ở trên).

---

## ⚙️ Cài đặt & chạy

### Yêu cầu
- Python 3.10+ (Docker dùng 3.11)
- MySQL 8 / TiDB
- FFmpeg (cho audio pipeline)
- Redis (tùy chọn)

### 1. Môi trường ảo & thư viện

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Tạo file `.env`

```env
APP_ENV=development
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Database (bắt buộc)
MYSQL_TRACKER_URL=mysql+pymysql://user:password@host:4000/voicecashbook

# JWT (bắt buộc)
JWT_SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=15

# AI
GROQ_API_KEY=
GEMINI_API_KEY=

# Tùy chọn
REDIS_URL=
GOOGLE_CLIENT_ID=
GOOGLE_WEB_CLIENT_ID=
GOOGLE_IOS_CLIENT_ID=
GOOGLE_ANDROID_CLIENT_ID=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
CLOUDINARY_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

Push notification cần file `firebase-service-account.json` ở thư mục gốc. **Không commit `.env` và file này lên Git.**

### 3. Migration & dữ liệu RBAC

```bash
python scripts/run_migrations.py
python scripts/seed_rbac.py      # nếu cần seed lại role/permission
```

### 4. Chạy server

```bash
uvicorn app.main:app --reload
```

| Địa chỉ | Mô tả |
| :--- | :--- |
| http://127.0.0.1:8000/docs | Swagger UI |
| http://127.0.0.1:8000/redoc | ReDoc |
| http://127.0.0.1:8000/health | Health check |

### 5. Chạy bằng Docker

```bash
docker compose up -d --build
```

Container chạy user non-root, tự chạy migration trước khi khởi động Uvicorn 4 worker. Log và Data Lake được mount ra volume `app_logs`, `app_data_lake`.

---

## 🧪 Kiểm thử

```bash
pytest tests/                                    # unit/integration
python -m app.ai.evaluation.run_evaluation       # đánh giá độ chính xác AI
```

Ma trận test bắt buộc cho AI Agent (RESELLER/PRODUCER/SERVICE, multi-tenant, race condition) được mô tả ở mục 6 của [AGENTS.md](AGENTS.md). Bộ test API end-to-end nằm trong [test_api/](test_api/).

---

## 📝 Quy ước phát triển

- **Controller** không chứa nghiệp vụ; **service** chứa nghiệp vụ; **repository** là nơi duy nhất truy vấn DB.
- Mọi truy vấn phải có điều kiện `user_id` (multi-tenant).
- Tiền tệ tính bằng `Decimal`, không tin số liệu tính sẵn từ client.
- Không đưa logic kiểm tra tồn kho/số dư vào prompt LLM.
- Thêm intent mới: `validator.py` → `payload.py` → `handler.py` → đăng ký trong `router.py` → xử lý confirm trong `agent_confirm_service.py` / `groq_route.py` (xem mục 5 [AGENTS.md](AGENTS.md)).
- Thay đổi schema DB phải đi kèm migration Alembic.
