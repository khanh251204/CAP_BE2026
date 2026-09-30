from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.configs.database import auth_db, Base, engine
from app.configs.migrations.migrate_voice_record import (
    migrate_voice_record_schema,
)
from app.configs.migrations.migrate_transaction_detail import (
    migrate_transaction_detail_schema,
)
from app.configs.migrations.migrate_system_logs import (
    migrate_system_logs,
)
from app.configs.migrations.migrate_user_correction import (
    migrate_user_correction_schema,
)
from app.middlewares.system_log_middleware import SystemLogMiddleware
from app.services.closing_scheduler import ClosingScheduler
from app.services.data_lake_service import DataLakeService

# Core routers
from app.api.stt import router as stt_router
from app.routes import inventory_route
from app.routes.auth_route import router as auth_router
from app.routes.closing_route import router as closing_router
from app.routes.customer_route import customer_router
from app.routes.debt_route import debt_router
from app.routes.groq_route import router as groq_router
from app.routes.notification_route import router as notification_router
from app.routes.product_route import router as product_router
from app.routes.report_route import router as report_router
from app.routes.supplier_route import supplier_router
from app.routes.transaction_route import transaction_router

# Admin routers
from app.routes.admin_dashboard_route import router as admin_dashboard_router
from app.routes.admin_dataset_route import router as admin_dataset_router
from app.routes.admin_product_route import router as admin_product_router
from app.routes.admin_transaction_route import router as admin_transaction_router
from app.routes.admin_user_route import router as admin_user_router
from app.routes.admin_voice_route import router as admin_voice_router
from app.routes.admin_system_log_route import router as admin_system_log_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    auth_db()

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[DB] Table creation check: {e}")

    try:
        migrate_voice_record_schema()
    except Exception as e:
        print(f"[DB] Voice_Record migration error: {e}")

    try:
        migrate_transaction_detail_schema()
    except Exception as e:
        print(f"[DB] Transaction_Detail migration error: {e}")

    try:
        migrate_system_logs()
    except Exception as e:
        print(f"[DB] System_Logs migration error: {e}")

    try:
        migrate_user_correction_schema()
    except Exception as e:
        print(f"[DB] User_Correction migration error: {e}")

    try:
        ClosingScheduler.start()
    except Exception as e:
        print(f"[Scheduler] Start error: {e}")

    try:
        DataLakeService.init_storage()
    except Exception as e:
        print(f"[DataLake] Init error: {e}")

    yield

    try:
        ClosingScheduler.stop()
    except Exception:
        pass


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0",
    lifespan=lifespan,
)


# =====================================================
# CORS
# =====================================================

ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SystemLogMiddleware)


# =====================================================
# CORE ROUTERS
# =====================================================

CORE_ROUTERS = [
    transaction_router,
    inventory_route.router,
    notification_router,
    auth_router,
    product_router,
    groq_router,
    debt_router,
    customer_router,
    supplier_router,
    report_router,
    closing_router,
    stt_router,
]


# =====================================================
# ADMIN ROUTERS
# =====================================================

ADMIN_ROUTERS = [
    admin_dashboard_router,
    admin_dataset_router,
    admin_product_router,
    admin_transaction_router,
    admin_user_router,
    admin_voice_router,
    admin_system_log_router,
]


for router in CORE_ROUTERS:
    app.include_router(router, prefix="/api/v1")


for router in ADMIN_ROUTERS:
    app.include_router(router, prefix="/api/v1")


# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():
    return {
        "message": "Expense Tracker Backend is Running!"
    }