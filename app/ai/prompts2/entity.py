# prompts/entity.py

ENTITY_RULES = """
====================================
TRÍCH XUẤT THỰC THỂ (ENTITIES)
====================================
Cần trích xuất các thông tin sau:

1. items (Danh sách sản phẩm): Array các object, mỗi object gồm:
   - product: Tên sản phẩm/hàng hóa (String hoặc null)
   - price: Số tiền dạng số nguyên VND (Number hoặc null)
   - quantity: Số lượng dạng số (Number hoặc null)
   - unit: Đơn vị tính đã chuẩn hóa (String hoặc null)

2. Thông tin chung:
   - customer: Tên hoặc xưng hô khách hàng (String hoặc null)
   - supplier: Tên nhà cung cấp / chủ mối (String hoặc null)
   - date: Thời gian được nhắc tới (String hoặc null)
   - payment: Hình thức/trạng thái thanh toán ("tiền mặt", "chuyển khoản", "nợ"...)
   - total_price: Tổng số tiền giao dịch (Number hoặc null)

3. Quy tắc cho công nợ khách hàng (ghi_no_khach_hang, thu_no_khach_hang):
   - customer: Bắt buộc
   - product, quantity, unit: Trích xuất nếu người dùng có nói
   - price: Số tiền nợ hoặc số tiền thu. Khi ghi nợ sản phẩm nếu người dùng không nói giá thì để null (hệ thống tự tra cứu giá sản phẩm qua search_products và tính: giá * số lượng)
   - Không tự đoán debt_id hoặc transaction_id
   - Không thêm note vào công nợ
"""