# VoiceCash BE — hướng dẫn cho Claude

@AGENTS.md
@STATUS.md

## Bổ sung ngắn

- App mobile (FE) ở `D:\Huy_Rearch\VoiceCashBook`. Đổi API (route, schema, tên field, mã trạng thái) thì kiểm tra FE đang gọi thế nào (`src/services/`) và báo lại nếu FE cần sửa theo. Thêm field mới thì không phá client cũ; đổi tên / bỏ field phải hỏi trước.
- Nhánh: `v1` → `main` = Capstone 1, `v2` = Capstone 2 (cùng tên nhánh với FE). Không trộn code giữa `main` và `v2`.
- Chạy server: `./.venv/Scripts/python.exe -m uvicorn app.main:app --reload`
- Test: `PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -m pytest tests/<file> -q`. Test fail sẵn từ trước thì xác nhận không do mình rồi báo lại, không sửa lan sang.
- Trả lời người dùng bằng tiếng Việt. Chỉ commit / push khi được yêu cầu.
