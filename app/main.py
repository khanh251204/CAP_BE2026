from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.hello_route import router as hello_router
# from app.routes.category_route import router as category_router

from app.configs.database import auth_db

from app.routes.transaction_route import transaction_router
from app.routes.groq_route import router as groq_router


from app.routes.category_route import router as category_router
from app.routes.auth_route import router as auth_router
from app.routes.notification_route import router as notification_router
from app.routes.product_route import router as product_router
from app.routes.intent_route import router as intent_router
from app.routes.account_route import router as account_router
from app.routes.customer_router import router as customer_router
from app.routes.supplier_route import router as supplier_router

from app.routes.auth_route import router as auth_router

# from app.routes.agent_route import router as agent_router

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
    groq_router,
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
    intent_router,
    prefix="/api/v1"
)
app.include_router(
    account_router,
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


# app.include_router(
#     agent_router,
#     prefix="/api/v1"
# )

# ROOT
@app.get("/")
def root():
    return {
        "message": "Expense Tracker Backend is Running!"
    }