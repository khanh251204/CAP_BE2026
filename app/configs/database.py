from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
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
    pool_pre_ping=True
)


# SQLAlchemy Base cho Models
Base = declarative_base()


# Session để Repository sử dụng
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
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
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
