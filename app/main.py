# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from app.routes.hello_route import router as hello_router
# from app.routes.category_route import router as category_router

from app.configs.database import auth_db

from app.routes.transaction_route import transaction_router
# from app.routes.groq_route import router as groq_router


from app.routes.category_route import router as category_router
from app.routes.auth_route import router as auth_router
from app.routes.notification_route import router as notification_router
from app.routes.product_route import router as product_router

from app.routes.groq_route import router as groq_router
from app.api.stt import router as stt_router

from app.routes.auth_route import router as auth_router
from app.routes import inventory_route
from app.routes.debt_route import debt_router
from app.routes.customer_route import customer_router
from app.routes.supplier_route import supplier_router
from app.routes.report_route import router as report_router
from app.routes.closing_route import router as closing_router
from app.services.closing_scheduler import ClosingScheduler
from app.configs.database import Base, engine


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0"
)

# =====================================================
# CẤU HÌNH CORS (BẮT BUỘC ĐỂ NHẬN COOKIE TỪ FRONTEND)
# =====================================================
# Khai báo các địa chỉ Frontend được phép gọi API
origins = [
    "http://localhost:3000",       # Dành cho React (Create React App)
    "http://localhost:5173",       # Dành cho React (Vite)
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    # Quan trọng: Nếu bạn đang test trên điện thoại hoặc máy khác trong mạng LAN, 
    # hãy thêm IP của máy chạy Frontend vào đây. Ví dụ:
    # "http://192.168.10.XX:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,         # KHÔNG được dùng ["*"] ở đây
    allow_credentials=True,        # Cho phép nhận Cookie/Token
    allow_methods=["*"],           # Cho phép mọi method (GET, POST, PUT, DELETE, OPTIONS)
    allow_headers=["*"],           # Cho phép mọi headers
)
# =====================================================

# STARTUP
@app.on_event("startup")
def startup():
    auth_db()
    # Tự động tạo các bảng mới (closing_period, closing_transaction, closing_setting, closing_report)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Table creation check: {e}")
    # Khởi động background closing scheduler
    try:
        ClosingScheduler.start()
    except Exception as e:
        print(f"ClosingScheduler start error: {e}")


# SHUTDOWN
@app.on_event("shutdown")
def shutdown():
    try:
        ClosingScheduler.stop()
    except Exception:
        pass

# ROUTERS
app.include_router(
    hello_router,
    prefix="/api/v1"
)

# app.include_router(
#     category_router,
#     prefix="/api/v1"
# )

app.include_router(
    transaction_router,
    prefix="/api/v1"
)

app.include_router(
    inventory_route.router,
    prefix="/api/v1"
)

app.include_router(
    notification_router,
    prefix="/api/v1"
)

app.include_router(
    auth_router,
    prefix="/api/v1"
)

app.include_router(
    product_router,
    prefix="/api/v1"
)

app.include_router(
    groq_router,
    prefix="/api/v1"
)

app.include_router(
    debt_router,
    prefix="/api/v1"
)

app.include_router(
    customer_router,
    prefix="/api/v1"
)

app.include_router(
    supplier_router,
    prefix="/api/v1"
)

# Reporting Router (hỗ trợ cả /api/v1/reports và alias trực tiếp /reports, /ws/reports)
app.include_router(
    report_router,
    prefix="/api/v1"
)
app.include_router(
    report_router
)

# Closing Router (hỗ trợ cả /api/v1/closing-* và alias trực tiếp /closing-*, /ws/closing)
app.include_router(
    closing_router,
    prefix="/api/v1"
)
app.include_router(
    closing_router
)

# Speech-to-Text Router (hỗ trợ cả /api/v1/stt/groq và alias trực tiếp /stt/groq)
app.include_router(
    stt_router,
    prefix="/api/v1"
)
app.include_router(
    stt_router
)

# ROOT
@app.get("/")
def root():
    return {
        "message": "Expense Tracker Backend is Running!"
    }