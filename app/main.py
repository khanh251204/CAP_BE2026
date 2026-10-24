import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from fastapi.exceptions import RequestValidationError
logger = logging.getLogger(__name__)

from app.configs.database import auth_db, check_db_health
from app.configs.settings import settings
from app.middlewares.system_log_middleware import SystemLogMiddleware
from app.services.closing_scheduler import ClosingScheduler
from app.services.data_lake_service import DataLakeService
from app.services.notification_cleanup_service import NotificationCleanupScheduler
from app.services.token_cleanup_service import TokenCleanupScheduler
from app.services.inactivity_reminder_service import InactivityReminderScheduler

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
from app.routes.admin_notification_route import router as admin_notification_router
from app.routes.admin_rbac_route import router as admin_rbac_router, ui_router as admin_rbac_ui_router
from app.routes.admin_closing_route import router as admin_closing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Xác thực kết nối DB (SELECT 1 ping), không chạy DDL lock trong lifespan đa tiến trình
    auth_db()

    # 1b. Quy tắc chốt sổ: chặn ghi giao dịch mới vào kỳ đã chốt (mọi luồng: API, MCP, admin)
    from app.services.closing.closing_guard import install_transaction_guard
    install_transaction_guard()

    # 1c. Đồng bộ danh mục quyền (app/configs/permissions.py) vào DB: thêm quyền/role còn thiếu,
    #     không ghi đè các chỉnh sửa ma trận quyền của Admin. Nhiều worker chạy song song vẫn an toàn
    #     (worker thua bị lỗi unique sẽ bỏ qua vì worker kia đã đồng bộ).
    try:
        from app.configs.database import SessionLocal
        from app.services.permission_service import PermissionService
        with SessionLocal() as rbac_db:
            rbac_summary = PermissionService.sync_catalog(rbac_db)
        if any(rbac_summary.values()):
            logger.info(f"[RBAC] Đồng bộ danh mục quyền: {rbac_summary}")
    except Exception as e:
        logger.warning(f"[RBAC] Bỏ qua đồng bộ danh mục quyền: {e}")

    # 2. Khởi động Closing Scheduler
    try:
        ClosingScheduler.start()
    except Exception as e:
        logger.error(f"[Scheduler] Start error: {e}")

    # 3. Khởi tạo Data Lake storage
    try:
        DataLakeService.init_storage()
    except Exception as e:
        logger.error(f"[DataLake] Init error: {e}")

    # 4. Khởi động Notification Cleanup Scheduler (tự động dọn dẹp thông báo cũ)
    try:
        NotificationCleanupScheduler.start()
    except Exception as e:
        logger.error(f"[NotificationCleanupScheduler] Start error: {e}")

    # 5. Khởi động Token Cleanup Scheduler (tự động dọn dẹp refresh token hết hạn)
    try:
        TokenCleanupScheduler.start()
    except Exception as e:
        logger.error(f"[TokenCleanupScheduler] Start error: {e}")

    # 6. Khởi động Inactivity Reminder Scheduler (tự động nhắc nhở người dùng không vào app 7 ngày qua FCM)
    try:
        InactivityReminderScheduler.start()
    except Exception as e:
        logger.error(f"[InactivityReminderScheduler] Start error: {e}")

    yield

    try:
        ClosingScheduler.stop()
    except Exception:
        pass

    try:
        NotificationCleanupScheduler.stop()
    except Exception:
        pass

    try:
        TokenCleanupScheduler.stop()
    except Exception:
        pass

    try:
        InactivityReminderScheduler.stop()
    except Exception:
        pass


app = FastAPI(
    title="Expense Tracker API",
    version="1.0.0",
    lifespan=lifespan,
)


from app.services.error_handler_service import ErrorHandlerService

ErrorHandlerService.register_exception_handlers(app)


# =====================================================
# CORS (Cấu hình động từ biến môi trường CORS_ORIGINS)
# =====================================================

ORIGINS = settings.cors_origins_list

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
    admin_notification_router,
    admin_rbac_router,
    admin_rbac_ui_router,
    admin_closing_router,
]


for router in CORE_ROUTERS:
    app.include_router(router, prefix="/api/v1")


for router in ADMIN_ROUTERS:
    app.include_router(router, prefix="/api/v1")


# =====================================================
# SYSTEM & HEALTH PROBES
# =====================================================

@app.get("/health", tags=["Health"])
def health_check():
    """
    Liveness & Readiness probe cho Docker / Kubernetes.
    Ping SELECT 1 kiểm tra tình trạng kết nối Database.
    """
    if not check_db_health():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected"
            }
        )
    return {
        "status": "healthy",
        "database": "connected"
    }


# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():
    return {
        "message": "Expense Tracker Backend is Running!"
    }