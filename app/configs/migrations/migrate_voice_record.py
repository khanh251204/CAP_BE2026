from sqlalchemy import text, inspect
from app.configs.database import engine


def migrate_voice_record_schema():
    """
    Tự động đồng bộ các cột mới cho bảng Voice_Record:
    - user_id INT NULL
    - audio_path VARCHAR(500) NULL
    - intent VARCHAR(100) NULL
    - status VARCHAR(50) NULL DEFAULT 'SUCCESS'
    - confidence NUMERIC(5,4) NULL
    - processing_time FLOAT NULL
    - error_message TEXT NULL
    - llm_output JSON NULL
    - updated_at DATETIME NULL
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Check both cases in case of table name case sensitivity
        target_table = None
        for t in ["Voice_Record", "voice_record"]:
            if t in tables:
                target_table = t
                break

        if not target_table:
            return

        columns = [c["name"].lower() for c in inspector.get_columns(target_table)]

        with engine.begin() as conn:
            # 1. user_id
            if "user_id" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `user_id` INT NULL;"))
                except Exception:
                    pass

            # 2. audio_path expansion to 500
            try:
                conn.execute(text(f"ALTER TABLE `{target_table}` MODIFY COLUMN `audio_path` VARCHAR(500) NULL;"))
            except Exception:
                pass

            # 3. transaction_id to nullable
            try:
                conn.execute(text(f"ALTER TABLE `{target_table}` MODIFY COLUMN `transaction_id` INT NULL;"))
            except Exception:
                pass

            # 4. intent
            if "intent" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `intent` VARCHAR(100) NULL;"))
                except Exception:
                    pass

            # 5. status
            if "status" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `status` VARCHAR(50) NULL DEFAULT 'SUCCESS';"))
                except Exception:
                    pass

            # 6. confidence
            if "confidence" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `confidence` NUMERIC(5,4) NULL;"))
                except Exception:
                    pass

            # 7. processing_time
            if "processing_time" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `processing_time` FLOAT NULL;"))
                except Exception:
                    pass

            # 8. error_message
            if "error_message" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `error_message` TEXT NULL;"))
                except Exception:
                    pass

            # 9. llm_output
            if "llm_output" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `llm_output` JSON NULL;"))
                except Exception:
                    pass

            # 10. updated_at
            if "updated_at" not in columns:
                try:
                    conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;"))
                except Exception:
                    pass

    except Exception as e:
        print(f"Warning: migrate_voice_record_schema encountered an issue: {e}")
