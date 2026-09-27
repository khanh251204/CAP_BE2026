# prompts/entity.py

ENTITY_RULES = """
# TRÍCH XUẤT THỰC THỂ (ENTITIES)

1. Thực thể sản phẩm & số lượng:
   - `product`: Tên sản phẩm/hàng hóa (String hoặc null).
   - `quantity`: Số lượng dạng số (Number hoặc null).
   - `unit`: Đơn vị tính đã chuẩn hóa (kg, lốc, thùng, cái, hộp, gói, lon, chai, ly, vỉ... hoặc null).
   - `price`: Đơn giá của MỘT đơn vị sản phẩm (số nguyên VND, hoặc null).
     * `price` LUÔN là đơn giá 1 đơn vị, KHÔNG phải tổng tiền.
     * Người dùng nói đơn giá ("mỗi cái 28k", "đơn giá 28k") -> price = 28000.
     * Người dùng chỉ cho tổng tiền và số lượng -> tính: price = total_price / quantity.
       (VD: "Nhập 500 lốc sữa chua giá/tổng 10 triệu" -> quantity=500, price=20000). Không gán cả 10 triệu vào price!

2. Thông tin đối tác & thanh toán:
   - `customer`: Tên hoặc cách xưng hô khách hàng (String hoặc null).
   - `supplier`: Tên nhà cung cấp (String hoặc null).
   - `date`: Thời gian được nhắc tới (String hoặc null).
   - `payment`: Hình thức/trạng thái thanh toán ("tiền mặt", "chuyển khoản" hoặc trạng thái công nợ: "PAID", "PARTIAL", "PENDING", null).
     * "đã trả đủ", "thanh toán rồi" -> "PAID".
     * "trả một phần", "trả bớt" -> "PARTIAL".
     * "chưa trả", "còn nợ", "ghi nợ" -> "PENDING".

3. Chi phí (chi_phi):
   - `price`: Số tiền chi, dạng số nguyên VND (Bắt buộc). VD: "Chi 500k tiền điện" -> price = 500000.
"""
