import logging
from sqlalchemy import create_engine, text
from sqlalchemy import event
from sqlalchemy.orm import declarative_base, sessionmaker, Session, with_loader_criteria

from app.configs.settings import settings

logger = logging.getLogger(__name__)

DATABASE_URL = settings.MYSQL_TRACKER_URL


engine = create_engine(
    DATABASE_URL,
    connect_args={
        "ssl": {
            "check_hostname": False,
            "cert_reqs": 0
        }
    },
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30.0
)


# SQLAlchemy Base cho Models
Base = declarative_base()


class SafeSession(Session):
    """
    Session an toàn: đảm bảo luôn đóng session và giải phóng connection về QueuePool
    ngay khi khối context manager (with ...) kết thúc, kể cả khi có exception.
    """
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


@event.listens_for(Session, "do_orm_execute")
def _hide_soft_deleted_debts(state):
    """
    Mọi SELECT ORM tự loại khoản nợ đã xoá mềm (Debt.is_active = False), kể cả lazy load quan hệ.
    Cần xem cả nợ đã xoá thì truyền .execution_options(include_deleted=True).
    """
    if (
        state.is_select
        and not state.is_column_load
        and not state.execution_options.get("include_deleted", False)
    ):
        from app.models.debt_model import Debt
        state.statement = state.statement.options(
            with_loader_criteria(Debt, Debt.is_active.is_(True), include_aliases=True)
        )


# Session để Repository sử dụng
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=SafeSession
)


def auth_db():
    """
    Kiểm tra kết nối Database
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Kết nối Database thành công!")

    except Exception as err:
        logger.error(f"Lỗi Database: {err}")


def check_db_health() -> bool:
    """
    Ping kiểm tra kết nối Database bằng lệnh SELECT 1.
    Phục vụ cho Docker/Kubernetes Liveness & Readiness probe.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except Exception as err:
        logger.error(f"[Health] Lỗi Database ping: {err}")
        return False


def get_db():
    """
    Dependency cung cấp database session cho từng request.
    Đảm bảo rollback khi có lỗi và luôn đóng session trong finally.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session():
    """
    Lấy Session ngoài request FastAPI (dùng cho MCP server, background tasks, tests).
    Sử dụng SafeSession nên khi dùng trong 'with get_db_session() as db:' sẽ tự động close().
    """
    return SessionLocal()