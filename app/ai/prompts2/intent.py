# prompts/intent.py

INTENT_RULES = """
====================================
DANH SÁCH INTENT & TYPE
====================================
- Intent: nhập_hàng, bán_hàng, ghi_nợ_nhà_cung_cấp, trả_nợ_nhà_cung_cấp, khách_ghi_nợ, thu_nợ_khách, ghi_no_khach_hang, thu_no_khach_hang, chi_phí, hàng_hỏng, kiểm_kho, báo_cáo, khác.

- Type: 
  + income  : bán_hàng, thu_nợ_khách, thu_no_khach_hang
  + expense : nhập_hàng, ghi_nợ_nhà_cung_cấp, trả_nợ_nhà_cung_cấp, chi_phí, hàng_hỏng, ghi_no_khach_hang
  + none    : kiểm_kho, báo_cáo, khác

====================================
QUY TẮC BẮT BUỘC (VALIDATION RULES)
====================================
Dựa theo Intent, nếu thiếu các trường sau thì tính là VI PHẠM (Phải trả về status: "error"):

1. Intent `bán_hàng`, `nhập_hàng`:
   - BẮT BUỘC có ít nhất 1 mặt hàng trong `items`, và mỗi mặt hàng BẮT BUỘC phải có `product` VÀ `price`.
2. Intent `thu_nợ_khách`, `thu_no_khach_hang`:
   - BẮT BUỘC: `customer` VÀ `price`.
3. Intent `khách_ghi_nợ`, `ghi_no_khach_hang`:
   - BẮT BUỘC: `customer`. `price` không bắt buộc nếu có `product` (hệ thống tự tra cứu giá qua search_products).
4. Intent `ghi_nợ_nhà_cung_cấp`, `trả_nợ_nhà_cung_cấp`:
   - BẮT BUỘC: `supplier` VÀ `price`.
5. Intent `chi_phí`, `hàng_hỏng`:
   - BẮT BUỘC: `price`.
"""