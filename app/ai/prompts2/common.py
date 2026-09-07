# prompts/common.py

COMMON_RULES = """
====================================
QUY TẮC SỬA LỖI CHÍNH TẢ & PHÁT ÂM (STT)
====================================
1. Sửa lỗi chính tả theo ngữ cảnh mua bán/giao dịch tiểu thương Việt Nam.
2. Tự động chuyển đổi các từ phát âm vùng miền/viết sai về từ chuẩn:
   - "kí", "kí lô", "cân" -> "kg"
   - "thâu nợ" -> "thu nợ"
   - "nạp tiền" -> "thanh toán" / "trả tiền"

====================================
QUY TẮC TỰ SỬA LỜI (SELF-CORRECTION)
====================================
- Nếu người dùng nói ngập ngừng hoặc tự sửa lời (VD: "bán 3... à không 5 kg", "200k nhầm 300k"):
  -> LUÔN ƯU TIÊN lấy giá trị/thông tin được nhắc đến SAU CÙNG.

====================================
QUY TẮC CHUYỂN ĐỔI TIỀN TỆ & ĐƠN VỊ
====================================
1. QUY TẮC TIỀN TỆ (SLANG / KHẨU NGỮ):
   - nghìn / ngàn / k / ca               -> x 1.000 (VD: 50k = 50.000)
   - chục (khi nói về TIỀN)              -> x 10.000 (VD: 3 chục = 30.000)
   - xị / trăm (khi nói về TIỀN lẻ)       -> x 100.000 (VD: 2 xị = 200.000)
   - lít                                 -> 1 lít = 100.000 (VD: 5 lít = 500.000)
   - củ / triệu / trẹo / tr              -> x 1.000.000 (VD: 2 củ = 2.000.000)
   - tỏi / tỷ                            -> x 1.000.000.000
   * Nói số tròn ở vị trí giá tiền ("áo hai trăm", "cà phê ba mươi") -> Mặc định là NGHÌN ĐỒNG (200.000, 30.000).

2. PHÂN BIỆT ĐA NGHĨA ("chục", "lít"):
   - "chục": Đi kèm hàng hóa -> Số lượng = 10. Ở vị trí giá -> Giá = 10.000đ.
   - "lít": Đi kèm chất lỏng -> Đơn vị = "lít". Ở vị trí giá -> Tiền = 100.000đ.

3. CHUẨN HÓA ĐƠN VỊ TÍNH (UNIT):
   - Khối lượng : "kg", "lạng"
   - Dung tích   : "lít"
   - Đóng gói    : "thùng", "bao", "hộp", "gói", "vỉ", "chai", "lon", "ly", "cốc", "bó", "mớ", "con", "cái", "chiếc"
"""