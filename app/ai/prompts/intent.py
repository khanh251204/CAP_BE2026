# prompts/intent.py

INTENT_RULES = """
## INTENTS & REQUIRED FIELDS
| Intent | Required Fields | Nghiệp vụ |
|---|---|---|
| ban_hang | product, quantity | Bán hàng cho khách (giá không bắt buộc) |
| mua_hang / nhap_hang | product, quantity | Mua/nhập hàng từ nhà cung cấp (cùng một nghiệp vụ; trích xuất giá nhập & đơn vị nếu có) |
| nhap_kho | product, quantity | Nhập kho KHÔNG mất tiền: tồn đầu kỳ, hàng được tặng, khách trả lại, sản xuất xong nhập kho |
| xuat_kho | product, quantity | Xuất kho đơn thuần |
| kiem_kho | product | Hỏi tồn kho, hoặc kiểm kê: báo số lượng đếm thực tế (quantity = số đếm) |
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
| chot_so | (none) | Chốt sổ cuối ngày / tháng / quý / năm |
| khac | (none) | Không thuộc các nghiệp vụ trên |

## INTENT RULES
0. `intent` CHỈ được lấy từ cột Intent trong bảng trên. Tuyệt đối không tự đặt tên intent mới
   (vd. "thu_tien", "nhan_tien", "tra_tien_hang"). Không khớp nghiệp vụ nào -> "khac".
1. Chọn đúng 1 intent. Đủ required -> status="success". Thiếu required -> status="error", ghi tên field vào missing_fields.
2. Entity không có trong câu -> null. Tuyệt đối không tự suy diễn hay bịa tên người, sản phẩm.
3. Phân biệt nghiệp vụ:
   - `mua_hang` vs `nhap_kho`: nhập hàng mặc định là MUA (mất tiền) -> `mua_hang`, kể cả khi có chữ "nhập kho",
     "thêm/nhập ... vào kho", có hay không có giá. VD: "Nhập kho 25 ký đường", "Thêm 10 thùng bia vào kho",
     "Nhập kho 5 bao gạo giá 300k" -> `mua_hang`.
     Chỉ dùng `nhap_kho` khi câu nói rõ là KHÔNG mất tiền: "tồn đầu", "tồn đầu kỳ", "hàng tặng", "được cho",
     "khách trả lại", "sản xuất xong / làm xong ... nhập kho". VD: "Nhập tồn đầu 50 lon coca",
     "Làm xong 30 ổ bánh nhập kho" -> `nhap_kho`.
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
     "Trả"/"đóng"/"chi" + khoản chi vận hành (vận chuyển, giao hàng, nhân công, thuê mặt bằng/xưởng, quảng cáo,
     phí ngân hàng, sửa máy, xăng xe...) mà KHÔNG có "nợ" và KHÔNG nêu nhà cung cấp -> luôn là `chi_phi`.
     VD: "Trả 90 nghìn tiền bốc xếp", "Trả tiền thuê xe tải chở hàng hết 400k" -> `chi_phi`.
   - `chi_phi` vs `mua_hang`: "Chi"/"Bỏ ra" + mua/lấy NGUYÊN LIỆU, hàng hóa để bán/sản xuất -> `mua_hang`.
     VD: "Chi 120k mua dừa về nấu chè" -> `mua_hang`.
   - `ban_hang` vs `chot_so`: "chốt đơn" + hàng hóa (số lượng, giá) là CHỐT MỘT ĐƠN BÁN -> `ban_hang`.
     `chot_so` chỉ dùng cho chốt sổ/khóa sổ theo kỳ (ngày, tuần, tháng, quý, năm).
   - `ban_hang` vs `xuat_kho`: "xuất"/"giao" hàng cho khách hoặc có giá bán, KHÔNG có chữ "kho" -> `ban_hang`.
     VD: "Xuất 3 thùng nước ngọt cho anh Sơn giá 200 nghìn" -> `ban_hang`. Chỉ khi có "xuất kho" hoặc xuất nội bộ -> `xuat_kho`.
   - `mua_hang` vs `them_san_pham`: "thêm/nhập N <hàng> vào kho" (có số lượng) là nhập hàng -> `mua_hang`
     (theo quy tắc `mua_hang` vs `nhap_kho` ở trên);
     `them_san_pham` chỉ khi tạo MẶT HÀNG MỚI trong danh mục (thường kèm giá, không có số lượng tồn).
     VD: "Thêm 25 kí đường vào kho" -> `mua_hang`; "Tạo mặt hàng nước đá giá 5 nghìn" -> `them_san_pham`.
   - Hướng công nợ (xét ai trả cho ai):
     * "X trả nợ", "X trả bớt", "X gửi lại tiền nợ", "thu nợ X" (X là người) -> `thu_no_khach` (X trả cho mình).
       Nhìn vị trí tên: tên người ĐỨNG TRƯỚC "trả" (X là người trả) -> `thu_no_khach`, dù có hay không có chữ "nợ";
       tên ĐỨNG SAU "trả (nợ/bớt) (cho)" (mình là người trả) -> `tra_no_nha_cung_cap`.
     * "Trả nợ cho X", "thanh toán nợ cho đại lý/công ty/nhà cung cấp X", "trả bớt nợ X" (mình trả) -> `tra_no_nha_cung_cap`.
     * "X nợ tôi", "X còn nợ", "X còn thiếu tôi", "ghi nợ X", "ghi sổ X" (X là người mua, CHƯA trả) -> `khach_ghi_no`.
       Phân biệt: "nợ / còn nợ / thiếu" là GHI NỢ (`khach_ghi_no`); "trả / gửi lại / thu" mới là THU NỢ (`thu_no_khach`).
     * "Còn nợ/ghi nợ đại lý, công ty, nhà cung cấp X" (mình nợ X) -> `ghi_no_nha_cung_cap`.
     * Chỉ có tên người, không có dấu hiệu nhà cung cấp -> coi là khách hàng; backend sẽ tra danh bạ để xác nhận.
     VD: "Em Linh mang 300k nợ cũ tới trả", "Bác Phước tất toán 1 triệu tiền nợ",
     "Thím Bảy trả trước một nửa là 600 nghìn" -> `thu_no_khach`;
     "Chị Nhung còn nợ 450k", "Ông Sáu thiếu tôi 2 triệu" -> `khach_ghi_no`;
     "Mình trả đợt đầu 2 triệu cho lò bánh Kim Long", "Thanh toán nợ đại lý Bảo An 1 triệu" -> `tra_no_nha_cung_cap`.
   - Dịch vụ làm cho khách (cắt tóc, sửa xe, thay nhớt, giặt ủi, rửa xe...) có thu tiền -> `ban_hang` (product = tên dịch vụ,
     quantity = null), KHÔNG phải `chi_phi` (chi_phi là tiền mình trả ra).
     VD: "Làm móng cho chị Hương 250k" -> `ban_hang`; "Lắp điều hòa cho anh Khoa 1 triệu" -> `ban_hang`.
   - `kiem_kho`: hỏi còn hàng, check kho ("kiểm kho tôm", "bánh mì còn không") -> `kiem_kho`, bắt buộc trích xuất `product`.
     Kiểm kê, người dùng báo số đếm thực tế ("kiểm kho coca còn 15 lon", "đếm lại mì tôm được 30 gói")
     -> `kiem_kho`, quantity = số đếm thực tế. Câu hỏi ("coca còn không", "còn bao nhiêu") -> quantity = null.
   - `tim_san_pham` vs `kiem_kho`: hỏi cửa hàng CÓ BÁN / CÓ mặt hàng đó trong danh mục không, hoặc hỏi giá
     ("có bán X không", "có X không", "X giá bao nhiêu") -> `tim_san_pham`. Hỏi CÒN bao nhiêu / còn hàng không -> `kiem_kho`.
     VD: "Tiệm mình có bán nước suối Lavie không" -> `tim_san_pham`; "Lavie còn mấy chai" -> `kiem_kho`.
   - `new_product_name` CHỈ dùng khi `sua_san_pham` ĐỔI TÊN ("đổi tên A thành B"). Các trường hợp khác để null:
     * `them_san_pham`: tên mặt hàng mới đặt ở `product`. VD: "Thêm sản phẩm kẹo dẻo giá 8k một gói"
       -> product="kẹo dẻo", new_product_name=null.
     * `sua_san_pham` đổi giá / đơn vị: product = tên hiện tại, new_product_name = null
       (không lặp lại tên cũ vào new_product_name).
   - `chot_so` vs `bao_cao`: có từ "chốt sổ", "khóa sổ", "chốt ca", "chốt sổ cuối ngày/tháng" -> `chot_so`.
     Chỉ xem số liệu ("doanh thu hôm nay bao nhiêu", "báo cáo tháng này") -> `bao_cao`.
"""
