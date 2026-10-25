# prompts/entity.py

ENTITY_RULES = """
# TRÍCH XUẤT THỰC THỂ (ENTITIES)

1. Thực thể sản phẩm & số lượng:
   - `product`: Tên sản phẩm/hàng hóa (String hoặc null).
   - `quantity`: Số lượng dạng số (Number hoặc null).
   - `unit`: Đơn vị tính đã chuẩn hóa (kg, lốc, thùng, cái, hộp, gói, lon, chai, ly, vỉ... hoặc null).
   - `price`: Đơn giá của MỘT đơn vị sản phẩm (số nguyên VND, hoặc null).
     * Chỉ điền khi người dùng nói rõ đơn giá: "giá 20k", "mỗi cái 28k", "đơn giá 28k", "20k một lon", "30k/kg".
   - `total_price`: TỔNG số tiền của cả đơn hàng hóa (số nguyên VND, hoặc null).
     * Người dùng nói "hết", "tổng", "tổng cộng", "tất cả", "cả thảy", "thành tiền", "tính tiền" + số tiền -> total_price.
     * KHÔNG tự chia ra đơn giá (backend sẽ tính). Có total_price thì để price = null nếu không nói đơn giá.
     * VD: "Bán 5 lon coca hết 100k" -> quantity=5, total_price=100000, price=null.
       "Nhập 500 lốc sữa chua tổng 10 triệu" -> quantity=500, total_price=10000000, price=null.
     * Nghiệp vụ chỉ có tiền, không có hàng (chi_phi, thu nợ, trả nợ, ghi nợ tiền): số tiền điền vào `price`
       như cũ. VD: "Chi tiền điện hết 500k" -> price=500000.

2. Thông tin đối tác & thanh toán:
   - `customer`: Tên hoặc cách xưng hô khách hàng (String hoặc null).
   - `supplier`: Tên nhà cung cấp (String hoặc null).
   - `date`: Thời gian được nhắc tới (String hoặc null).
   - `payment`: Hình thức/trạng thái thanh toán ("tiền mặt", "chuyển khoản" hoặc trạng thái công nợ: "PAID", "PARTIAL", "PENDING", null).
     * "đã trả đủ", "thanh toán rồi" -> "PAID".
     * "trả một phần", "trả bớt" -> "PARTIAL".
     * "chưa trả", "còn nợ", "ghi nợ", "bán nợ", "bán chịu", "mua chịu", "lấy chịu", "ghi sổ", "thiếu lại", "trả sau" -> "PENDING".

3. Chi phí (chi_phi):
   - `price`: Số tiền chi, dạng số nguyên VND (Bắt buộc). VD: "Chi 500k tiền điện" -> price = 500000.
"""
