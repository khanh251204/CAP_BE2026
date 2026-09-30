import os
import shutil
import json
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath("data_lake")

def migrate_datalake():
    print(f"Bắt đầu chuyển đổi phân vùng Data Lake theo ngày (%Y-%m-%d): {BASE_DIR}")
    
    # 1. Quét các vùng: raw/voice, processed/ai_result, dataset, feedback/correction
    zones = [
        os.path.join(BASE_DIR, "raw", "voice"),
        os.path.join(BASE_DIR, "processed", "ai_result"),
        os.path.join(BASE_DIR, "dataset"),
        os.path.join(BASE_DIR, "feedback", "correction"),
    ]

    # Bản đồ intent & entities chuẩn hóa cho các mẫu thiếu
    fixes = {
        "1.json": {
            "intent": "ban_hang",
            "entities": {"product": None, "quantity": None, "unit": None, "price": None}
        },
        "30003.json": {
            "intent": "ban_hang",
            "entities": {"product": "nước ngọt", "quantity": 2, "unit": "lon", "price": None, "customer": None, "supplier": None, "payment": None, "date": None, "new_product_name": None}
        },
        "30004.json": {
            "intent": "ban_hang",
            "entities": {"product": "thuốc lá", "quantity": 1, "unit": "bao", "price": None, "customer": None, "supplier": None, "payment": None, "date": None, "new_product_name": None}
        },
        "30005.json": {
            "intent": "ban_hang",
            "entities": {"product": "sữa chua", "quantity": 2, "unit": "lốc", "price": None, "customer": None, "supplier": None, "payment": None, "date": None, "new_product_name": None}
        },
        "30007.json": {
            "intent": "ban_hang",
            "entities": {"product": "sữa chua", "quantity": 10, "unit": "lốc", "price": None, "customer": None, "supplier": None, "payment": None, "date": None, "new_product_name": None}
        }
    }

    # Timestamp mặc định cho 30003 - 30008 nếu cần
    timestamps = {
        "1.json": "2026-09-30T01:16:27.028432",
        "30003.json": "2026-09-26T19:52:02.000000",
        "30004.json": "2026-09-26T19:52:04.000000",
        "30005.json": "2026-09-26T19:57:55.000000",
        "30006.json": "2026-09-26T19:58:14.000000",
        "30007.json": "2026-09-26T20:10:58.000000",
        "30008.json": "2026-09-26T20:11:21.000000",
        "60001.json": "2026-09-28T21:29:33.000000",
        "60002.json": "2026-09-28T21:30:09.000000",
        "60003.json": "2026-09-28T21:33:15.000000",
        "60004.json": "2026-09-28T21:33:35.000000",
        "60005.json": "2026-09-28T21:33:56.000000",
        "90001.json": "2026-09-30T01:02:29.000000",
        "90002.json": "2026-09-30T01:12:42.000000",
        "90003.json": "2026-09-30T01:14:09.000000",
        "90004.json": "2026-09-30T01:14:30.000000",
        "90005.json": "2026-09-30T01:21:23.000000",
        "tx_1001.json": "2026-09-30T01:16:27.576924",
        "tx_1620002.json": "2026-09-28T21:30:25.833606"
    }

    migrated_count = 0

    for zone in zones:
        if not os.path.exists(zone):
            continue
        
        # Duyệt qua các thư mục con trong zone (như 2026-09)
        for sub in os.listdir(zone):
            sub_path = os.path.join(zone, sub)
            if not os.path.isdir(sub_path):
                continue
            
            # Chỉ xử lý nếu tên thư mục dạng YYYY-MM (độ dài 7)
            if len(sub) == 7 and sub.count("-") == 1:
                files = os.listdir(sub_path)
                for fname in files:
                    if not fname.endswith(".json"):
                        continue
                    old_file = os.path.join(sub_path, fname)
                    with open(old_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    # Xác định ngày tạo
                    c_date_str = data.get("created_at") or data.get("ingested_at") or timestamps.get(fname)
                    if c_date_str:
                        dt = datetime.fromisoformat(c_date_str.replace("Z", ""))
                        day_str = dt.strftime("%Y-%m-%d")
                    else:
                        day_str = f"{sub}-01"
                        dt = datetime.fromisoformat(f"{day_str}T00:00:00")

                    # Chuẩn hóa trường created_at trong dataset
                    if "created_at" not in data:
                        data["created_at"] = timestamps.get(fname, dt.isoformat())

                    # Cập nhật intent / entities nếu có sửa
                    if fname in fixes:
                        if not data.get("intent") or data.get("intent") is None:
                            data["intent"] = fixes[fname]["intent"]
                        if not data.get("entities") or data.get("entities") == {}:
                            data["entities"] = fixes[fname]["entities"]

                    # Tạo thư mục ngày mới
                    new_day_dir = os.path.join(zone, day_str)
                    os.makedirs(new_day_dir, exist_ok=True)
                    new_file = os.path.join(new_day_dir, fname)

                    # Ghi file mới
                    with open(new_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    # Xóa file cũ
                    os.remove(old_file)
                    migrated_count += 1
                    print(f"Đã chuyển: {os.path.relpath(old_file, BASE_DIR)} -> {os.path.relpath(new_file, BASE_DIR)}")

                # Xóa thư mục tháng cũ nếu trống
                try:
                    if not os.listdir(sub_path):
                        os.rmdir(sub_path)
                        print(f"Đã xóa thư mục tháng cũ: {sub_path}")
                except Exception as e:
                    print(f"Không thể xóa thư mục cũ {sub_path}: {e}")

    print(f"Hoàn thành chuyển đổi {migrated_count} tệp dữ liệu sang phân vùng theo ngày!")

if __name__ == "__main__":
    migrate_datalake()
