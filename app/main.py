from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.hello_route import router as hello_router
# from app.routes.category_route import router as category_router

from app.configs.database import auth_db

from app.routes.transaction_route import transaction_router

from app.routes.category_route import router as category_router
from app.routes.auth_route import router as auth_router
from app.routes.customer_route import router as customer_router
from app.routes.supplier_route import router as supplier_router
from app.routes.notification_route import router as notification_router


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0"
)

# CẤU HÌNH CORS
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    transaction_router
)

app.include_router(
    auth_router
)

app.include_router(
    customer_router
)

app.include_router(
    supplier_router
)

app.include_router(
    notification_router,
    prefix="/api/v1"
)


# ROOT
@app.get("/")
def root():
    return {
        "message": "Expense Tracker Backend is Running!"
    }