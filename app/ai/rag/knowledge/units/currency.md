# Domain Knowledge: Tiền tệ và Quy đổi Giá trị (Currency & Price)

## Bảng quy đổi tiền tệ tiếng Việt thông dụng
- "k", "K", "nghìn", "ngàn": 1k = 1.000 VNĐ (ví dụ: 25k = 25000, 50 nghìn = 50000, 100 ngàn = 100000).
- "tr", "triệu", "chai": 1tr = 1.000.000 VNĐ (ví dụ: 1tr = 1000000, 2 triệu = 2000000, 1 triệu 500 = 1500000).
- "lít", "loét": 1 lít = 100.000 VNĐ (ví dụ: 3 lít = 300000).
- "củ": 1 củ = 1.000.000 VNĐ.

---

## INTENT: chi_phi (Ví dụ chi phí vận hành có số tiền)

Example:
"Chi tiền phí dịch vụ hết 300k"

Expected extraction:
intent = "chi_phi"
price = 300000
product = null
quantity = null
unit = null

---

## INTENT: ban_hang (Ví dụ tính đơn giá từ tổng tiền)

Example:
"Bán 50 hộp bánh hết 700k"

Expected extraction:
intent = "ban_hang"
product = "bánh"
quantity = 50
unit = "hộp"
price = 14000