# prompts/common.py

COMMON_RULES = """
# RULES: STT & NORMALIZATION
1. Sửa lỗi chính tả STT theo ngữ cảnh mua bán, giao dịch bán lẻ Việt Nam.
2. Self-correction: Nếu người dùng nói ngập ngừng hoặc tự sửa ("bán 3... à 5kg", "giá 20k nhầm 30k"), LUÔN lấy giá trị CUỐI CÙNG.
3. Chuẩn hóa đơn vị: "kí", "kí lô", "cân" -> "kg".
4. Chuẩn hóa tiền tệ:
   - "k/ngàn/nghìn/cành" -> x1.000 (50k -> 50000).
   - "chục" (tiền) -> x10.000.
   - "trăm/xị/lít" (tiền) -> x100.000.
   - "triệu/củ/tr" -> x1.000.000.
   - Số tròn ở vị trí giá ("áo 2 trăm", "cà phê 30") -> nghìn VNĐ (200000, 30000).
5. Phân biệt từ đa nghĩa:
   - "chục" + hàng hóa = 10 cái; "chục" + tiền = 10.000đ.
   - "lít" + chất lỏng = đơn vị "lít"; "lít" + tiền = 100.000đ.
6. Sử dụng RELEVANT KNOWLEDGE khi có từ lóng/phương ngữ/bao bì. Không tự bịa entity ngoài dữ liệu.
"""