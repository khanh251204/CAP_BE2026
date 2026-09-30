from sqlalchemy import text, inspect
from app.configs.database import engine


def migrate_transaction_detail_schema():
    """
    Tự động đồng bộ cột product_name cho bảng Transaction_Detail và backfill dữ liệu cũ:
    - product_name VARCHAR(255) NULL AFTER product_id
    - Backfill tên sản phẩm từ bảng Product cho các bản ghi Transaction_Detail cũ
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        target_table = None
        for t in ["Transaction_Detail", "transaction_detail"]:
            if t in tables:
                target_table = t
                break

        if not target_table:
            return

        columns = [c["name"].lower() for c in inspector.get_columns(target_table)]

        with engine.begin() as conn:
            # 1. Thêm cột product_name nếu chưa có
            if "product_name" not in columns:
                try:
                    if engine.dialect.name == "sqlite":
                        conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `product_name` VARCHAR(255) NULL;"))
                    else:
                        conn.execute(text(f"ALTER TABLE `{target_table}` ADD COLUMN `product_name` VARCHAR(255) NULL AFTER `product_id`;"))
                except Exception as err:
                    print(f"[Migration] Add column product_name note: {err}")

            # 2. Backfill dữ liệu cũ từ bảng Product nếu product_name IS NULL
            try:
                prod_table = None
                for pt in ["Product", "product"]:
                    if pt in tables:
                        prod_table = pt
                        break

                if prod_table:
                    if engine.dialect.name == "sqlite":
                        conn.execute(text(f"""
                            UPDATE `{target_table}` 
                            SET `product_name` = (
                                SELECT `product_name` FROM `{prod_table}` 
                                WHERE `{prod_table}`.`product_id` = `{target_table}`.`product_id`
                            )
                            WHERE `product_name` IS NULL;
                        """))
                    else:
                        conn.execute(text(f"""
                            UPDATE `{target_table}` td 
                            JOIN `{prod_table}` p ON td.product_id = p.product_id 
                            SET td.product_name = p.product_name 
                            WHERE td.product_name IS NULL;
                        """))
            except Exception as err:
                print(f"[Migration] Backfill product_name note: {err}")

    except Exception as e:
        print(f"Warning: migrate_transaction_detail_schema encountered an issue: {e}")
