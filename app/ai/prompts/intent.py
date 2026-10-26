# prompts/intent.py

INTENT_RULES = """
## INTENTS & REQUIRED FIELDS
| Intent | Required Fields | Nghiệp vụ |
|---|---|---|
| ban_hang | product, quantity | Bán hàng cho khách (giá không bắt buộc) |
| mua_hang / nhap_hang | product, quantity | Mua/nhập hàng từ nhà cung cấp (cùng một nghiệp vụ; trích xuất giá nhập & đơn vị nếu có) |
| nhap_kho | product, quantity | Nhập hàng vào kho đơn thuần |
| xuat_kho | product, quantity | Xuất kho đơn thuần |
| kiem_kho | product | Kiểm tra/hỏi số lượng tồn kho |
| ghi_no_khach_hang / khach_ghi_no | customer | Ghi nợ cho khách (bắt buộc customer; price không bắt buộc nếu có product) |
| thu_no_khach_hang / thu_no_khach | customer, price | Khách trả nợ (bắt buộc customer, price) |
| ghi_no_nha_cung_cap | supplier, price | Nợ tiền nhà cung cấp |
| tra_no_nha_cung_cap | supplier, price | Trả nợ nhà cung cấp |
| chi_phi | price | Chi phí kinh doanh (tiền điện, mặt bằng, vận chuyển...) |
| hang_hong | product, quantity, unit | Báo hàng hư hỏng/hết hạn |
| them_san_pham | product | Thêm sản phẩm mới |
| sua_san_pham | product | Sửa sản phẩm |
| xoa_san_pham | product | Xóa sản phẩm |
| tim_san_pham / xem_san_pham | product | Tìm kiếm/tra cứu sản phẩm |
| bao_cao | (none) | Báo cáo doanh thu, sổ sách |
| khac | (none) | Không thuộc các nghiệp vụ trên |

## INTENT RULES
0. `intent` CHỈ được lấy từ cột Intent trong bảng trên. Tuyệt đối không tự đặt tên intent mới
   (vd. "thu_tien", "nhan_tien", "tra_tien_hang"). Không khớp nghiệp vụ nào -> "khac".
1. Chọn đúng 1 intent. Đủ required -> status="success". Thiếu required -> status="error", ghi tên field vào missing_fields.
2. Entity không có trong câu -> null. Tuyệt đối không tự suy diễn hay bịa tên người, sản phẩm.
3. Phân biệt nghiệp vụ:
   - `mua_hang` vs `nhap_kho`: có từ "nhập kho" -> `nhap_kho`.
   - `ban_hang` vs `xuat_kho`: có từ "xuất kho" -> `xuat_kho`.
   - `ban_hang` vs `khach_ghi_no` (BÁN NỢ):
     * Có hàng hóa cụ thể (product + quantity) kèm "nợ", "chịu", "ghi sổ", "trả sau", "thiếu lại"
       -> `ban_hang` với payment="PENDING". VD: "Bán nợ 5 lon coca cho chị Lan", "Chị Lan lấy chịu 2 thùng bia",
       "Ghi nợ chị Lan 3 gói mì" -> đều là `ban_hang`.
     * Chỉ ghi nợ một số tiền, không kèm số lượng hàng -> `khach_ghi_no`. VD: "Ghi nợ chị Lan 200k", "Chị Lan nợ 500 nghìn".
   - `chi_phi` vs `tra_no_nha_cung_cap`: "thanh toán", "đóng", "trả", "chi" + một khoản chi
     (tiền điện, nước, internet, mặt bằng, lương, vận chuyển, rác...) -> `chi_phi`.
     VD: "Thanh toán tiền điện 1 triệu", "Đóng tiền nước 200k", "Trả lương nhân viên 5 triệu" -> `chi_phi`.
     Chỉ khi trả cho NHÀ CUNG CẤP / trả nợ tiền hàng -> `tra_no_nha_cung_cap`.
   - `kiem_kho`: hỏi còn hàng, check kho ("kiểm kho tôm", "bánh mì còn không") -> `kiem_kho`, bắt buộc trích xuất `product`.
"""
