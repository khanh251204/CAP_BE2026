# 🎙️ VoiceCashBook - Backend

Backend của ứng dụng **VoiceCashBook**, được xây dựng bằng **FastAPI** nhằm cung cấp RESTful API cho ứng dụng React Native. Hệ thống hỗ trợ ghi nhận giao dịch bằng giọng nói thông qua **Whisper (Speech-to-Text)** và **Gemini LLM (Information Extraction)**.

---

# 🚀 Công nghệ sử dụng

* Python 3.10+
* FastAPI
* MySQL
* Pydantic
* SQLAlchemy *(nếu sử dụng ORM)*
* Faster Whisper
* Gemini API
* Uvicorn

---

# 📂 Cấu trúc thư mục

```text
## 📂 Project Structure

```text
BE/
│
├── app/
│   │
│   ├── configs/             # Cấu hình hệ thống (Database, JWT, Logger, Settings)
│   │
│   ├── routes/              # Khai báo các API Endpoint
│   │
│   ├── controllers/         # Tiếp nhận Request, gọi Service và trả Response
│   │
│   ├── services/            # Xử lý Business Logic và AI (Whisper, Gemini,...)
│   │
│   ├── repositories/        # Thao tác trực tiếp với MySQL (CRUD)
│   │
│   ├── models/              # Định nghĩa Model (SQLAlchemy ORM - nếu sử dụng)
│   │
│   ├── schemas/             # Request/Response Model (Pydantic Validation)
│   │
│   ├── ai/                  # Chứa các module AI
│   │   ├── stt/             # Speech-to-Text (Whisper)
│   │   ├── llm/             # Gemini LLM
│   │   └── prompts/         # Prompt dùng cho LLM
│   │
│   ├── uploads/             # Lưu file người dùng tải lên (audio,...)
│   │   └── audio/           # File ghi âm trước khi xử lý
│   │
│   ├── utils/               # Các hàm tiện ích dùng chung
│   │           
│   ├── tests/               # test
│   │
│   └── main.py              # Điểm khởi động của FastAPI
│
├── requirements.txt         # Danh sách thư viện Python
├── .env                     # Biến môi trường
└── README.md                # Tài liệu dự án
```




# ⚙️ Cài đặt

## 1. Clone dự án

```bash
git clone <repository-url>
cd backend
```

---

## 2. Tạo Virtual Environment

Windows

```bash
python -m venv .venv
```

Kích hoạt

```bash
.venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

---

## 4. Tạo file .env

Ví dụ:

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=voicecashbook
DB_USER=root
DB_PASSWORD=123456

GEMINI_API_KEY=YOUR_API_KEY
```

---

## 5. Chạy ứng dụng

```bash
uvicorn app.main:app --reload
```

Nếu `main.py` nằm trực tiếp trong thư mục `backend/`:

```bash
uvicorn main:app --reload
```

---

# 🌐 Truy cập

API

```text
http://127.0.0.1:8000
```

Swagger UI

```text
http://127.0.0.1:8000/docs
```

ReDoc

```text
http://127.0.0.1:8000/redoc
```

---

# 🔄 Luồng xử lý

```text
React Native
      │
      ▼
Routes
      │
      ▼
Controllers
      │
      ▼
Services
      │
      ├── Whisper
      ├── Gemini
      └── Business Logic
      │
      ▼
Repositories
      │
      ▼
MySQL
```

---

# 📝 Ghi chú

* Controller chỉ tiếp nhận và trả kết quả, không xử lý nghiệp vụ.
* Business Logic được đặt trong `services/`.
* Mọi thao tác với cơ sở dữ liệu thực hiện trong `repositories/`.
* File ghi âm lưu trong `uploads/audio/`, cơ sở dữ liệu chỉ lưu đường dẫn.
* Nếu sử dụng ORM (SQLAlchemy), định nghĩa bảng trong `models/`; nếu dùng SQL thuần có thể bỏ thư mục này.
