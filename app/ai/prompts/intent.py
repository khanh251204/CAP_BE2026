
INTENT_RULES = """
## INTENTS

| Intent | Required |
|---|---|
| tim_san_pham | product |
| xem_san_pham | product |
| them_san_pham | product |
| sua_san_pham | product |
| xoa_san_pham | product |
| mua_hang | product, quantity |
| nhap_hang | product, quantity |
| ban_hang | product, quantity |
| nhap_kho | product, quantity |
| xuat_kho | product, quantity |
| ghi_no_khach_hang | customer |
| thu_no_khach_hang | customer, price |
| khach_ghi_no | customer |
| thu_no_khach | customer, price |
| ghi_no_nha_cung_cap | supplier, price |
| tra_no_nha_cung_cap | supplier, price |
| chi_phi | price |
| hang_hong | product, quantity, unit |
| kiem_kho | product |
| bao_cao | none |
| khac | none |

## RULES

- Chọn đúng 1 intent duy nhất.
- Thiếu required field -> status="error", thêm field bị thiếu vào missing_fields (VD: thiếu product -> missing_fields=["product"]; thiếu quantity -> missing_fields=["quantity"]).
- Đủ required -> status="success".
- Entity không được nói rõ trong câu -> null. Tuyệt đối không tự suy luận hoặc tự bịa entity (không tự đoán Product, Customer, Supplier, Debt).

### PHÂN BIỆT NGHIỆP VỤ BẮT BUỘC:
1. `mua_hang` != `nhap_kho`:
   - `mua_hang`: Nghiệp vụ mua hàng từ nhà cung cấp (VD: "Mua 30kg tôm giá 100k từ bà Hoa", "Mua 10 thùng bia", "Nhập 50 thùng mì từ nhà cung cấp").
   - `nhap_kho`: Nghiệp vụ nhập tồn kho đơn thuần (VD: "Nhập kho 30kg tôm", "Nhập 30kg tôm vào kho", "Nhập thêm 20 thùng nước ngọt vào kho").
   - Câu "Nhập kho 30kg tôm từ bà Hoa": Người dùng nói rõ "nhập kho" nên BẮT BUỘC là `nhap_kho`, KHÔNG được tự ý biến thành `mua_hang`.
2. `ban_hang` != `xuat_kho`:
   - `ban_hang`: Nghiệp vụ bán hàng cho khách hàng (VD: "Bán 5kg tôm giá 120k", "Bán cho chị Lan 5kg tôm").
   - `xuat_kho`: Nghiệp vụ xuất tồn kho đơn thuần (VD: "Xuất kho 10kg tôm", "Xuất 10kg tôm khỏi kho"). KHÔNG tự động biến thành `ban_hang` và KHÔNG tự tạo Customer.
3. `kiem_kho` != `xuat_kho`:
   - `kiem_kho`: Tra cứu/kiểm tra số lượng tồn kho (VD: "Kiểm kho tôm", "Tôm còn bao nhiêu trong kho", "Check kho bánh mì"). KHÔNG được nhầm thành `xuat_kho` hay `hang_hong`.
4. Quy tắc công nợ & giá:
   - `ban_hang`: price không bắt buộc (nếu không nói -> null).
   - `mua_hang`: price không bắt buộc (nếu không nói -> null).
   - `ghi_no_khach_hang`: Bắt buộc `customer`. `price` KHÔNG bắt buộc nếu có `product`.
   - `thu_no_khach_hang`: dùng khi khách trả nợ (Bắt buộc `customer`, `price`).
5. Xử lý câu nói:
   - Nếu người dùng tự sửa lời (VD: "bán 3... à không 5kg") -> LUÔN lấy giá trị sau cùng.
   - Nếu câu mới bổ sung thông tin -> giữ nguyên intent và entity cũ.
   - RAG chỉ hỗ trợ từ lóng, đơn vị, sản phẩm. Không tự bịa thông tin không có.
"""

