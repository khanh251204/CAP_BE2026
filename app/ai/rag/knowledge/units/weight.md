# Domain Knowledge: Đơn vị khối lượng (Weight Units)

## Bảng chuẩn hóa đơn vị khối lượng
- "ký", "kí", "cân", "kí lô", "kg" -> chuẩn hóa thành: "kg".
- "lạng": 1 lạng = 100g (ví dụ: 15 lạng -> quantity = 15, unit = "100g").
- "gram", "gam", "g" -> chuẩn hóa thành: "g".
- "yến": 1 yến = 10 kg.
- "tạ": 1 tạ = 100 kg.
- "tấn": 1 tấn = 1.000 kg.

---

## INTENT: nhap_hang (Ví dụ mua nguyên liệu có đơn vị khối lượng và đơn giá)

Example:
"Nhập thêm 80 kg nước cốt dừa giá 1tr một ký"

Expected extraction:
intent = "nhap_hang"
product = "nước cốt dừa"
quantity = 80
unit = "kg"
price = 1000000

---

## INTENT: nhap_hang (Ví dụ đơn vị lạng)

Example:
"Mua 15 lạng cúc áo của bác Hai"

Expected extraction:
intent = "nhap_hang"
product = "cúc áo"
quantity = 15
unit = "100g"
supplier = "bác Hai"