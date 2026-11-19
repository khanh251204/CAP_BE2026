# prompts/intent.py

INTENT_RULES = """
## INTENTS & REQUIRED FIELDS
| Intent | Required Fields | Nghiệp vụ |
|---|---|---|
| ban_hang | product, quantity | Bán hàng cho khách (giá không bắt buộc) |
| mua_hang / nhap_hang | product, quantity | Mua/nhập hàng từ nhà cung cấp (cùng một nghiệp vụ; trích xuất giá nhập & đơn vị nếu có) |
| ghi_no_khach_hang / khach_ghi_no | customer | Ghi nợ cho khách (bắt buộc customer; price không bắt buộc nếu có product) |
| thu_no_khach_hang / thu_no_khach | customer, price | Khách trả nợ (bắt buộc customer, price) |
| ghi_no_nha_cung_cap | supplier, price | Nợ tiền nhà cung cấp |
| tra_no_nha_cung_cap | supplier, price | Trả nợ nhà cung cấp |
| chi_phi | price | Chi phí kinh doanh (tiền điện, mặt bằng, vận chuyển...) |
| khac | (none) | Không thuộc các nghiệp vụ trên |

## INTENT RULES
0. `intent` CHỈ được lấy từ cột Intent trong bảng trên. Tuyệt đối không tự đặt tên intent mới
   (vd. "thu_tien", "nhan_tien", "tra_tien_hang"). Không khớp nghiệp vụ nào -> "khac".
1. Chọn đúng 1 intent. Đủ required -> status="success". Thiếu required -> status="error", ghi tên field vào missing_fields.
2. Entity không có trong câu -> null. Tuyệt đối không tự suy diễn hay bịa tên người, sản phẩm.
3. Phân biệt nghiệp vụ:
   - `ban_hang` vs `khach_ghi_no` (BÁN NỢ):
     * Có hàng hóa cụ thể (product + quantity) kèm "nợ", "chịu", "ghi sổ", "trả sau", "thiếu lại"
       -> `ban_hang` với payment="PENDING". VD: "Bán nợ 5 lon coca cho chị Lan", "Chị Lan lấy chịu 2 thùng bia",
       "Ghi nợ anh Sơn 4 chai dầu ăn" -> đều là `ban_hang`.
     * Chỉ ghi nợ một số tiền, không kèm số lượng hàng -> `khach_ghi_no`. VD: "Ghi nợ anh Phúc 350k", "Chị Lan nợ 500 nghìn".
   - `chi_phi` vs `tra_no_nha_cung_cap`: "thanh toán", "đóng", "trả", "chi" + một khoản chi
     (tiền điện, nước, internet, mặt bằng, lương, vận chuyển, rác...) -> `chi_phi`.
     VD: "Thanh toán tiền điện 1 triệu", "Đóng tiền nước 200k", "Trả lương bảo vệ 4 triệu" -> `chi_phi`.
     Chỉ khi trả cho NHÀ CUNG CẤP / trả nợ tiền hàng -> `tra_no_nha_cung_cap`.
     "Trả"/"đóng"/"chi" + khoản chi vận hành (vận chuyển, giao hàng, nhân công, thuê mặt bằng/xưởng, quảng cáo,
     phí ngân hàng, sửa máy, xăng xe...) mà KHÔNG có "nợ" và KHÔNG nêu nhà cung cấp -> luôn là `chi_phi`.
     VD: "Trả 90 nghìn tiền bốc xếp", "Trả tiền thuê xe tải chở hàng hết 400k" -> `chi_phi`.
   - `chi_phi` vs `mua_hang`: "Chi"/"Bỏ ra" + mua/lấy NGUYÊN LIỆU, hàng hóa để bán/sản xuất -> `mua_hang`.
     VD: "Chi 120k mua dừa về nấu chè" -> `mua_hang`.
   - Hướng công nợ (xét ai trả cho ai):
     * "X trả nợ", "X trả bớt", "X gửi lại tiền nợ", "thu nợ X" (X là người) -> `thu_no_khach` (X trả cho mình).
       Nhìn vị trí tên: tên người ĐỨNG TRƯỚC "trả" (X là người trả) -> `thu_no_khach`, dù có hay không có chữ "nợ";
       tên ĐỨNG SAU "trả (nợ/bớt) (cho)" (mình là người trả) -> `tra_no_nha_cung_cap`.
     * "Trả nợ cho X", "thanh toán nợ cho đại lý/công ty/nhà cung cấp X", "trả bớt nợ X" (mình trả) -> `tra_no_nha_cung_cap`.
     * "X nợ tôi", "X còn nợ", "X còn thiếu tôi", "ghi nợ X", "ghi sổ X" (X là người mua, CHƯA trả) -> `khach_ghi_no`.
       Phân biệt: "nợ / còn nợ / thiếu" là GHI NỢ (`khach_ghi_no`); "trả / gửi lại / thu" mới là THU NỢ (`thu_no_khach`).
     * "Còn nợ/ghi nợ đại lý, công ty, nhà cung cấp X" (mình nợ X) -> `ghi_no_nha_cung_cap`.
     * Chỉ có tên người, không có dấu hiệu nhà cung cấp -> coi là khách hàng; backend sẽ tra danh bạ để xác nhận.
     VD: "Em Linh mang 300k nợ cũ tới trả", "Bác Phước tất toán 1 triệu tiền nợ" -> `thu_no_khach`;
     "Chị Nhung còn nợ 450k", "Ông Sáu thiếu tôi 2 triệu" -> `khach_ghi_no`;
     "Mình trả đợt đầu 2 triệu cho lò bánh Kim Long", "Thanh toán nợ đại lý Bảo An 1 triệu" -> `tra_no_nha_cung_cap`.
   - Dịch vụ làm cho khách (cắt tóc, sửa xe, thay nhớt, giặt ủi, rửa xe...) có thu tiền -> `ban_hang` (product = tên dịch vụ,
     quantity = null), KHÔNG phải `chi_phi` (chi_phi là tiền mình trả ra).
     VD: "Làm móng cho chị Hương 250k" -> `ban_hang`; "Lắp điều hòa cho anh Khoa 1 triệu" -> `ban_hang`.
"""
