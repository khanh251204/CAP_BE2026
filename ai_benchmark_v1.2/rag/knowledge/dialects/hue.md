# Domain Knowledge: Từ vựng và Phương ngữ địa phương (Regional Dialects)

## Phương ngữ miền Trung / Huế thông dụng
- "mần" = làm (ví dụ: "mần phiếu nhập" -> tạo phiếu nhập).
- "ni" = này (ví dụ: "cái ni" -> cái này).
- "nớ" = đó (ví dụ: "thùng sữa nớ" -> thùng sữa đó).
- "bắp chuối" = hoa chuối.
- "đậu phụng" = lạc (đậu phộng).
- "chè hẻm" = chè.
- "răng" = sao / thế nào (ví dụ: "bán răng" -> bán thế nào, không phải sản phẩm).

---

## INTENT: nhap_hang (Ví dụ câu nói có phương ngữ)

Example:
"Mần phiếu nhập 30 kí bột nở của anh Bình"

Expected extraction:
intent = "nhap_hang"
product = "bột nở"
quantity = 30
unit = "kg"
supplier = "anh Bình"