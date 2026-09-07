
INTENT_RULES = """
## INTENTS

| Intent | Required |
|---|---|
| tim_san_pham | product |
| xem_san_pham | product |
| them_san_pham | product |
| sua_san_pham | product |
| xoa_san_pham | product |
| nhap_hang | product, quantity, unit |
| ban_hang | product, quantity, unit |
| ghi_no_khach_hang | customer |
| thu_no_khach_hang | customer, price |
| khach_ghi_no | customer |
| thu_no_khach | customer, price |
| ghi_no_nha_cung_cap | supplier, price |
| tra_no_nha_cung_cap | supplier, price |
| chi_phi | price |
| hang_hong | product, quantity, unit |
| kiem_kho | none |
| bao_cao | none |
| khac | none |

## RULES

- Chọn đúng 1 intent.
- Thiếu required -> status="error", thêm vào missing_fields.
- Đủ required -> status="success".
- Entity không được nói -> null.
- Không tự tạo giá trị.
- `ban_hang`: price không bắt buộc, không có -> null.
- `ghi_no_khach_hang`: Bắt buộc `customer`. `price` KHÔNG bắt buộc nếu người dùng có nói `product` (hệ thống sẽ tự động dùng search_products để tìm giá và tính: số tiền nợ = đơn giá * số lượng).
  Ví dụ: "Ghi nợ cho anh Tuấn 3 thùng bia", "Chị Lan mua 2 triệu, ghi nợ giúp anh", "Anh Tuấn còn thiếu 500 nghìn tiền hàng hôm qua", "Ghi sổ nợ cho khách tên Hoa 1 triệu 2".
- `thu_no_khach_hang`: dùng khi khách hàng trả bớt hoặc trả hết nợ.
  Ví dụ: "Chị Lan vừa trả 15 triệu", "Anh Tuấn trả hết nợ rồi", "Thanh toán 5 triệu cho đơn hàng ngày 3/9 của chị Hoa".
- Nếu người dùng tự sửa lời -> lấy giá trị sau cùng.
- Nếu câu mới bổ sung thông tin -> giữ intent và entity cũ.
- RAG chỉ dùng để hỗ trợ hiểu từ lóng, sản phẩm và đơn vị.
- Không tự đoán quy cách sản phẩm nếu RAG không có thông tin.


"""

