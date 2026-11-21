# prompts/entity.py

ENTITY_RULES = """
# TRÍCH XUẤT THỰC THỂ (ENTITIES)

1. Thực thể sản phẩm & số lượng:
   - `product`: Tên sản phẩm/hàng hóa (String hoặc null).
   - `quantity`: Số lượng dạng số (Number hoặc null).
     * Chỉ điền khi người dùng NÓI RÕ số lượng. KHÔNG tự đoán là 1 khi câu chỉ có đơn vị.
     * VD: "Bán thùng nước ngọt 180k, chuyển khoản" -> quantity=null, unit="thùng", total_price=180000.
     * Số đứng NGAY TRƯỚC đơn vị tính (lốc, thùng, kg, lon, gói...) LUÔN là `quantity`, kể cả số rất lớn;
       KHÔNG đưa số đó vào price / total_price.
   - `unit`: Đơn vị tính đã chuẩn hóa (kg, lốc, thùng, cái, hộp, gói, lon, chai, ly, vỉ... hoặc null).
   - `price`: Đơn giá của MỘT đơn vị sản phẩm (số nguyên VND, hoặc null).
     * Chỉ điền khi số tiền GẮN VỚI MỘT ĐƠN VỊ: "mỗi cái 28k", "giá 30k mỗi kí", "đơn giá 28k", "20k một lon",
       "30k/kg", "28k một cái".
     * Câu KHÔNG nói số lượng (thêm / sửa sản phẩm, "áo 2 trăm", "Bán thùng nước ngọt 180k") thì "giá X" là đơn giá
       hoặc tiền của món đó như các quy tắc khác.
   - `total_price`: TỔNG số tiền của cả đơn hàng hóa (số nguyên VND, hoặc null).
     * Người dùng nói "hết", "tổng", "tổng cộng", "tất cả", "cả thảy", "thành tiền", "tính tiền" + số tiền -> total_price.
     * Câu CÓ số lượng mà chỉ nói "giá X" / "X" KHÔNG kèm "mỗi / một <đơn vị>", "/<đơn vị>", "đơn giá"
       -> X là TỔNG tiền -> total_price.
     * KHÔNG tự chia ra đơn giá (backend sẽ tính). Có total_price thì để price = null nếu không nói đơn giá.
     * VD: "Bán 5 lon coca hết 100k" -> quantity=5, total_price=100000, price=null.
       "Nhập 500 lốc sữa chua tổng 10 triệu" -> quantity=500, total_price=10000000, price=null.
       "Nhập 5 kí thịt heo giá 300k" -> quantity=5, unit="kg", total_price=300000, price=null.
       "Nhập 5 kí thịt heo giá 30k mỗi kí" -> quantity=5, unit="kg", price=30000, total_price=null.
     * Nghiệp vụ chỉ có tiền, không có hàng (chi_phi, thu nợ, trả nợ, ghi nợ tiền): số tiền BẮT BUỘC điền vào `price`.
       Câu có nói số tiền thì KHÔNG được để price = null (kể cả số rất lớn; số âm giữ nguyên dấu âm để backend báo lỗi).
       Áp dụng cho MỌI cách nói thu nợ / trả nợ (có hay không có chữ "nợ", số tiền đứng trước hay sau tên người).
       VD: "Chi tiền gas hết 400k" -> price=400000.

2. Thông tin đối tác & thanh toán:
   - `customer`: Tên hoặc cách xưng hô khách hàng (String hoặc null).
   - `supplier`: Tên nhà cung cấp (String hoặc null).
     * `mua_hang` / `nhap_hang`: người bán hàng cho mình ("nhập ... từ X", "mua của X", "lấy hàng của X") LUÔN là
       `supplier`, KHÔNG phải `customer`, dù đã trả hay chưa trả tiền.
   - `date`: Thời gian được nhắc tới (String hoặc null).
   - `payment`: Hình thức/trạng thái thanh toán ("tiền mặt", "chuyển khoản" hoặc trạng thái công nợ: "PAID", "PARTIAL", "PENDING", null).
     * "đã trả đủ", "thanh toán rồi" -> "PAID".
     * "trả một phần", "trả bớt" -> "PARTIAL".
     * "chưa trả", "còn nợ", "ghi nợ", "bán nợ", "bán chịu", "mua chịu", "lấy chịu", "ghi sổ", "thiếu lại", "trả sau" -> "PENDING".
     * Câu KHÔNG có các chữ trên thì KHÔNG được ghi "PENDING" (nhập / bán hàng bình thường -> payment = null
       hoặc hình thức thanh toán người dùng nói).

3. Nhiều sản phẩm trong MỘT câu (chỉ ban_hang, mua_hang):
   - Câu nêu từ 2 mặt hàng KHÁC NHAU trở lên ("bán 2 lon coca và 3 gói mì") -> điền `items`, mỗi phần tử là
     {"product","quantity","unit","price","total_price"} của đúng mặt hàng đó. Đặt `product`, `quantity`, `unit`,
     `price`, `total_price` ở cấp ngoài = null.
   - `customer`, `supplier`, `payment`, `date` dùng chung cả đơn: để ở cấp ngoài, không lặp trong từng phần tử.
   - Mỗi mặt hàng giữ đúng số lượng / đơn vị / giá của riêng nó, không gộp, không đoán giá còn thiếu (null).
   - Chỉ 1 mặt hàng -> `items` = null và dùng các trường cấp ngoài như bình thường.
   - Đơn giá / tổng tiền của từng mặt hàng theo đúng quy tắc `price` / `total_price` ở mục 1.
   - VD: "Bán 2 lon coca 10k một lon và 3 gói mì giá 15k cho chị Lan" -> intent=ban_hang, customer="chị Lan",
     items=[{"product":"coca","quantity":2,"unit":"lon","price":10000},{"product":"mì","quantity":3,"unit":"gói","total_price":15000}].

4. Chi phí (chi_phi):
   - `price`: Số tiền chi, dạng số nguyên VND (Bắt buộc). VD: "Chi 800k tiền vệ sinh" -> price = 800000.
   - `category`: Tên khoản chi ngắn gọn như người dùng nói (String hoặc null), bỏ các từ "thanh toán", "đóng", "chi".
     VD: "Thanh toán tiền điện 1 triệu" -> category="tiền điện"; "Đóng tiền internet 300k" -> category="tiền internet";
     "Trả lương bảo vệ 4 triệu" -> category="lương bảo vệ". Nghiệp vụ khác -> null.
"""
