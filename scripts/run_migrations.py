"""
Database migration & schema initialization runner.
Executes once in pre-start entrypoint before multi-worker Uvicorn starts,
preventing DDL metadata lock (MDL) contentions in MySQL.
"""
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger("migration_runner")

from app.configs.database import Base, engine, check_db_health
from app.configs.migrations.migrate_voice_record import migrate_voice_record_schema
from app.configs.migrations.migrate_transaction_detail import migrate_transaction_detail_schema
from app.configs.migrations.migrate_system_logs import migrate_system_logs
from app.configs.migrations.migrate_user_correction import migrate_user_correction_schema
import app.models  # Ensure all SQLAlchemy models are registered


def wait_for_database(max_retries: int = 15, delay_seconds: int = 2):
    """Wait for database availability before running migrations."""
    logger.info("Checking database connection...")
    for attempt in range(1, max_retries + 1):
        if check_db_health():
            logger.info("Database connection verified successfully!")
            return True
        logger.warning(f"Database not ready yet (attempt {attempt}/{max_retries}). Retrying in {delay_seconds}s...")
        time.sleep(delay_seconds)
    logger.error("Could not establish database connection after multiple attempts.")
    return False


def run_all_migrations():
    logger.info("=== Starting Pre-flight Database Migrations ===")
    
    if not wait_for_database():
        logger.error("Aborting migration: Database unreachable.")
        sys.exit(1)

    # 1. SQLAlchemy create_all for missing tables
    try:
        logger.info("Ensuring all registered tables exist via Base.metadata.create_all...")
        Base.metadata.create_all(bind=engine)
        logger.info("Table verification/creation completed.")
    except Exception as e:
        logger.warning(f"Table verification check warning: {e}")

    # 2. Voice_Record schema migration
    try:
        logger.info("Running migrate_voice_record_schema()...")
        migrate_voice_record_schema()
        logger.info("migrate_voice_record_schema completed.")
    except Exception as e:
        logger.warning(f"migrate_voice_record_schema warning: {e}")

    # 3. Transaction_Detail schema migration
    try:
        logger.info("Running migrate_transaction_detail_schema()...")
        migrate_transaction_detail_schema()
        logger.info("migrate_transaction_detail_schema completed.")
    except Exception as e:
        logger.warning(f"migrate_transaction_detail_schema warning: {e}")

    # 4. System_Logs migration
    try:
        logger.info("Running migrate_system_logs()...")
        migrate_system_logs()
        logger.info("migrate_system_logs completed.")
    except Exception as e:
        logger.warning(f"migrate_system_logs warning: {e}")

    # 5. User_Correction migration
    try:
        logger.info("Running migrate_user_correction_schema()...")
        migrate_user_correction_schema()
        logger.info("migrate_user_correction_schema completed.")
    except Exception as e:
        logger.warning(f"migrate_user_correction_schema warning: {e}")

    logger.info("=== All Database Migrations Executed Successfully! ===")


if __name__ == "__main__":
    run_all_migrations()
