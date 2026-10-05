# Domain Knowledge: Quy cách đóng gói và Đơn vị bao bì (Packaging Units)

## Các đơn vị bao bì đóng gói thường dùng
- **thùng**: Đơn vị thùng lớn (thùng mì, thùng bia, thùng nước ngọt, thùng dầu ăn).
- **két**: Đóng gói đồ uống chai (két bia, két nước ngọt, thường 20-24 chai).
- **lốc**: Cụm sản phẩm nhỏ gắn liền (lốc sữa, lốc nước ngọt, thường 4-6 hộp/lon).
- **vỉ**: Dạng khay/vỉ (vỉ trứng, vỉ sữa chua, vỉ xúc xích).
- **bao**: Bao tải nguyên liệu hoặc hàng hóa (bao gạo, bao xi măng, bao đường, bao bột mì).
- **hộp / gói / bịch / túi**: Đóng gói lẻ (hộp bánh, gói mì, bịch bánh tráng, túi đường).
- **chai / lon / ly / cốc**: Đồ uống và chất lỏng (chai tương ớt, lon nước ngọt, ly cà phê).
- **cây**: Hàng que, thanh dài hoặc đóng gói theo lốc dài (cây kem, cây xúc xích, cây viết).

---

## INTENT: ban_hang (Ví dụ bán hàng có quy cách đóng gói và số lượng)

Example:
"Giao 50 chai tương ớt cho khách"

Expected extraction:
intent = "ban_hang"
product = "tương ớt"
quantity = 50
unit = "chai"

---

## INTENT: xuat_kho (Ví dụ xuất kho có số lượng và đơn vị)

Example:
"Xuất 300 cây xúc xích"

Expected extraction:
intent = "xuat_kho"
product = "xúc xích"
quantity = 300
unit = "cây"
