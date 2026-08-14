from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("MYSQL_TRACKER_URL")

print("🔎 DATABASE HOST:", DATABASE_URL.split("@")[1].split(":")[0])
print("🔎 DATABASE PORT:", DATABASE_URL.split(":")[3].split("/")[0])

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

Base = declarative_base()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def auth_db():
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