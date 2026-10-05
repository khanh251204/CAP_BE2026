# prompts/entity.py

ENTITY_RULES = """
==================================================
2. ENTITY SCHEMA & TRÍCH XUẤT THỰC THỂ
==================================================

Fields:
- product: string or null (Tên sản phẩm/hàng hóa tiếng Việt, KHÔNG kèm đơn vị tính hay quy cách đóng gói. Đối với "chi_phi" như tiền điện, tiền kho, tiền xăng: product = null).
- new_product_name: string or null (Dành cho sua_san_pham: "A thành B" -> product=A, new_product_name=B).
- price: integer VND or null (Đơn vị tính bằng số nguyên VND).
- quantity: float/integer or null (Số lượng hàng hóa).
- unit: string or null (Đơn vị tính chuẩn hóa: kg, con, cai, bao, cay, bo, cuon, thung, hop, bich, chai, lon, ly, to, bat, dia, qua...).
- customer: string or null (Tên người mua/khách hàng).
- supplier: string or null (Tên người bán/nhà cung cấp).
- date: string or null.
- payment: string or null ("tiền mặt", "chuyển khoản", hoặc "PAID", "PARTIAL", "PENDING", null).

==================================================
3. MONEY AND UNIT PRICE RULES (INTEGER VND)
==================================================

1. Quy đổi tiền tệ tiếng Việt sang số nguyên VND ("k", "nghìn", "ngàn" -> 000; "tr", "triệu" -> 000000).
2. "price" đại diện cho ĐƠN GIÁ (UNIT PRICE) bằng số nguyên VND:
   - Nếu câu nói có tổng tiền và số lượng mà chưa có đơn giá: price = Tổng tiền / Số lượng.
     Ví dụ: Mua 80kg tỏi băm hết 2 triệu -> quantity=80, price=25000 (25k/kg).
     Cân bán 20 ký sườn non hết 1tr -> quantity=20, price=50000.
   - Nếu câu nói nêu rõ đơn giá ("mỗi kg 100k", "giá 80k một kg", "50k/kg"): trích xuất chính xác đơn giá đó, KHÔNG nhân với số lượng.
3. Người mua vs Nhà cung cấp:
   - Trong "nhap_hang" / "mua_hang": bên đối tác là "supplier" (nhà cung cấp, lò mổ, trại chăn nuôi, thương lái).
   - Trong "ban_hang": bên đối tác là "customer" (khách hàng, người mua, quán ăn, bếp ăn).
"""
