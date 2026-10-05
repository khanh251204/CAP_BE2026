from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv
import os


load_dotenv()


DATABASE_URL = os.getenv("MYSQL_TRACKER_URL")


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
            print("✅ Kết nối Database thành công!")

    except Exception as err:
        print(f"❌ Lỗi Database: {err}")


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