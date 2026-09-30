from sqlalchemy import text, inspect
from app.configs.database import engine, Base
from app.models.user_correction_model import UserCorrection


def migrate_user_correction_schema():
    """
    Tự động đồng bộ và khởi tạo bảng User_Correction nếu chưa tồn tại trong DB:
    - id INT AUTO_INCREMENT PRIMARY KEY
    - user_id INT NULL
    - voice_record_id INT NULL
    - transaction_id INT NULL
    - correction_type VARCHAR(50) NULL
    - original_ai_result JSON NULL
    - corrected_result JSON NULL
    - diff JSON NULL
    - extra_metadata JSON NULL
    - created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        target_table = None
        for t in ["User_Correction", "user_correction"]:
            if t in tables:
                target_table = t
                break

        if not target_table:
            # Tạo bảng nếu chưa tồn tại
            UserCorrection.__table__.create(bind=engine, checkfirst=True)
            return

        columns = [c["name"].lower() for c in inspector.get_columns(target_table)]

        with engine.begin() as conn:
            if "correction_type" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `correction_type` VARCHAR(50) NULL;"))
                except Exception:
                    pass

            if "diff" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `diff` JSON NULL;"))
                except Exception:
                    pass

            if "extra_metadata" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `extra_metadata` JSON NULL;"))
                except Exception:
                    pass

    except Exception as e:
        print(f"Warning: migrate_user_correction_schema encountered an issue: {e}")
