ENTITY_RULES = """

# TRÍCH XUẤT THỰC THỂ (ENTITIES)

Cần trích xuất các thông tin sau:

1. items (Danh sách sản phẩm): Array các object, mỗi object gồm:

   * product: Tên sản phẩm/hàng hóa (String hoặc null)
   * price: Đơn giá của MỘT đơn vị sản phẩm, dạng số nguyên VND (Number hoặc null)
   * quantity: Số lượng dạng số (Number hoặc null)
   * unit: Đơn vị tính đã chuẩn hóa (String hoặc null)

   QUY TẮC PRICE:

   * `price` LUÔN là đơn giá của một đơn vị sản phẩm, KHÔNG phải tổng tiền.

   * Nếu người dùng nói rõ đơn giá bằng các cụm như:
     "mỗi", "mỗi cái", "mỗi hộp", "mỗi lốc", "mỗi sản phẩm",
     "đơn giá" thì số tiền đó là `price`.

   * Nếu người dùng chỉ cung cấp tổng tiền và đã biết `quantity`,
     phải tính đơn giá:

     price = total_price / quantity

   Ví dụ:
   "Nhập 500 lốc sữa chua, mỗi lốc 28k"
   → quantity = 500
   → unit = "lốc"
   → price = 28000

   "Nhập 500 lốc sữa chua giá 10 triệu"
   → quantity = 500
   → unit = "lốc"
   → total_price = 10000000
   → price = 20000

   "Nhập 500 lốc sữa chua, tổng 10 triệu"
   → quantity = 500
   → unit = "lốc"
   → total_price = 10000000
   → price = 20000

   LƯU Ý:

   * Từ "giá" đứng một mình KHÔNG mặc định có nghĩa là `price`.
   * Phải xét ngữ cảnh để xác định số tiền là đơn giá hay tổng tiền.
   * Nếu số tiền là giá trị của toàn bộ số lượng sản phẩm thì đó là
     `total_price`, sau đó tính `price = total_price / quantity`.
   * Không được gán toàn bộ `total_price` vào `price`.

2. Thông tin chung:

   * customer: Tên hoặc xưng hô khách hàng (String hoặc null)
   * supplier: Tên nhà cung cấp / chủ mối (String hoặc null)
   * date: Thời gian được nhắc tới (String hoặc null)
   * payment: Hình thức/trạng thái thanh toán ("tiền mặt", "chuyển khoản", "nợ"...)
   * total_price: Tổng số tiền giao dịch (Number hoặc null)

3. Quy tắc cho công nợ khách hàng (ghi_no_khach_hang, thu_no_khach_hang, ghi_nơ_nha_cung_cap, tra_no_nha_cung_cap):
   * customer: Tên khách hàng (bắt buộc).
   * product: Tên sản phẩm được ghi nợ (nếu có nhắc tới sản phẩm).
   * quantity: Số lượng sản phẩm (nếu có).
   * unit: Đơn vị tính (nếu có).
   * price: Số tiền ghi nợ hoặc số tiền khách trả (nếu người dùng có nói giá). Nếu người dùng KHÔNG nói giá khi ghi nợ sản phẩm -> để null (hệ thống sẽ tự động dùng search_products để tìm giá niêm yết của sản phẩm và tính: số tiền nợ = đơn giá * số lượng).
   * KHÔNG tự bịa `debt_id` (chỉ trích xuất khi người dùng nói đích danh mã nợ cụ thể).
   * KHÔNG tự bịa `transaction_id`.
   * KHÔNG thêm trường `note` vào công nợ Debt.
   * payment: Trạng thái thanh toán của công nợ khách hàng hoặc nhà cung cấp. Chỉ được phép: `"PAID"`, `"PARTIAL"`, `"PENDING"`, hoặc `null`. Không được tự đoán hoặc tự tạo giá trị khác. Người dùng không nói rõ trạng thái thanh toán -> `null`. "đã trả đủ", "thanh toán rồi", "trả hết" -> `"PAID"`. "trả một phần", "trả bớt", "còn lại nợ" -> `"PARTIAL"`. "chưa trả", "ghi nợ", "còn nợ" -> `"PENDING"`.

4. Quy tắc cho chi phí hoạt động (chi_phi):
   * price: Số tiền chi phí, dạng số nguyên VND (Bắt buộc). VD: "Chi 500k tiền điện" -> price = 500000.
   * category: Loại chi phí hoặc mục đích chi (VD: "tiền điện", "tiền nước", "mặt bằng", "tiền nhà", "vận chuyển", "xăng xe", "văn phòng phẩm"...).
   * note: Ghi chú chi phí (nếu có nói thêm chi tiết).
   * payment: Hình thức/trạng thái thanh toán ("tiền mặt", "chuyển khoản", "PAID").
"""
