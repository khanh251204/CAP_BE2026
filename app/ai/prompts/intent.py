# prompts/intent.py

INTENT_RULES = """
## INTENTS & REQUIRED FIELDS
| Intent | Required Fields | Nghiệp vụ |
|---|---|---|
| ban_hang | product, quantity | Bán hàng cho khách (giá không bắt buộc) |
| mua_hang / nhap_hang | product, quantity | Mua hàng từ nhà cung cấp (giá không bắt buộc) |
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
1. Chọn đúng 1 intent. Đủ required -> status="success". Thiếu required -> status="error", ghi tên field vào missing_fields.
2. Entity không có trong câu -> null. Tuyệt đối không tự suy diễn hay bịa tên người, sản phẩm.
3. Phân biệt nghiệp vụ:
   - `mua_hang` vs `nhap_kho`: có từ "nhập kho" -> `nhap_kho`.
   - `ban_hang` vs `xuat_kho`: có từ "xuất kho" -> `xuat_kho`.
   - `kiem_kho`: hỏi còn hàng, check kho ("kiểm kho tôm", "bánh mì còn không") -> `kiem_kho`, bắt buộc trích xuất `product`.
"""
