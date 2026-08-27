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


# Session Ä‘á»ƒ Repository sá»­ dá»¥ng
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def auth_db():
    """
    Kiá»ƒm tra káº¿t ná»‘i Database
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("âœ… Káº¿t ná»‘i Database thÃ nh cÃ´ng!")

    except Exception as err:
        print(f"âŒ Lá»—i Database: {err}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
