# Phương ngữ Huế trong giao dịch

## Mục đích

Tài liệu này hỗ trợ chuẩn hóa các cách nói phổ biến của người Huế
khi nhập hàng, bán hàng, kiểm kho và ghi nhận thu chi.

Không được dịch máy móc từ địa phương sang tiếng phổ thông.
Phải xét toàn bộ câu và ngữ cảnh giao dịch.

---

## Đại từ và từ hỏi

### chi

"chi" thường tương đương "gì".

Ví dụ:

"bán cái chi"
→ "bán cái gì"

"mua chi"
→ "mua gì"

Trong giao dịch, không xem "chi" là tên sản phẩm nếu nó
chỉ đóng vai trò từ hỏi.

---

### mô

"mô" thường tương đương "đâu".

Ví dụ:

"khách ở mô"
→ "khách ở đâu"

"cửa hàng mô"
→ "cửa hàng nào/ở đâu" tùy ngữ cảnh.

Không tự động biến "mô" thành tên sản phẩm.

---

### răng

"răng" thường tương đương "sao"/"thế nào".

Ví dụ:

"răng mà chưa trả tiền"
→ "sao mà chưa trả tiền"

"làm răng"
→ "làm sao"

---

### rứa

"rứa" thường tương đương "vậy"/"thế".

Ví dụ:

"chi rứa"
→ "gì vậy"

"răng rứa"
→ "sao vậy"

---

### ni

"ni" thường tương đương "này".

Ví dụ:

"chai ni"
→ "chai này"

"thùng ni"
→ "thùng này"

---

### nớ

"nớ" thường tương đương "đó"/"kia" tùy ngữ cảnh.

Ví dụ:

"chai nớ"
→ "chai đó"

"lấy thùng nớ"
→ "lấy thùng kia/đó"

---

### tê

"tê" thường tương đương "kia".

Ví dụ:

"lấy cái tê"
→ "lấy cái kia"

---

### mần

"mần" thường tương đương "làm".

Ví dụ:

"mần chi"
→ "làm gì"

---

### chộ

"chộ" có thể mang nghĩa "thấy".

Ví dụ:

"không chộ hàng"
→ "không thấy hàng"

---

## Quy tắc quan trọng

Các từ:

- mô
- tê
- răng
- rứa
- chi
- ni
- nớ
- ri
- mần

không nhất thiết xuất hiện trong JSON cuối cùng.

LLM cần chuẩn hóa chúng thành nghĩa tiếng Việt chuẩn
trước khi xác định intent và entity.

---

## Ví dụ giao dịch

Người dùng:

"bán 3 ký gạo ni"

Hiểu:

"bán 3 kg gạo này"

JSON:

product = "gạo"
quantity = 3
unit = "kg"

---

Người dùng:

"nhập 2 thùng sữa nớ"

Hiểu:

"nhập 2 thùng sữa đó"

JSON:

product = "sữa"
quantity = 2
unit = "thùng"

---

Người dùng:

"mần phiếu nhập 5 bao gạo"

Hiểu:

"làm phiếu nhập 5 bao gạo"

Intent:

nhap_hang

---

Người dùng:

"cái ni bán răng"

Hiểu:

"cái này bán sao"

Không được hiểu "răng" là sản phẩm.

---

## Không được tự đoán

Nếu từ địa phương có nhiều nghĩa hoặc câu không đủ
ngữ cảnh, không được tự tạo entity.

Ví dụ:

"lấy cái nớ"

Không được tự đoán:

product = ???

Nếu chưa biết "cái nớ" là sản phẩm nào,
cần hỏi thêm hoặc dùng dữ liệu sản phẩm từ MCP.