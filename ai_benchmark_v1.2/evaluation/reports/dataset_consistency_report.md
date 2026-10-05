# Báo cáo Kiểm tra Tính Nhất quán của Dữ liệu (Dataset Consistency Report)

## 1. Thông tin Dataset
- **Tệp nguồn**: `ai_benchmark/datasets/voicecash_producer_1000.csv`
- **Các trường trong dataset**: `id`, `text`, `business_type`, `intent`, `type`, `product`, `new_product_name`, `price`, `quantity`, `unit`, `customer`, `supplier`, `payment`, `missing_fields`, `message`.

---

## 2. Các Quy ước Hiện tại trong Ground Truth

### A. Semantics của trường `price`
- **Thực tế kiểm tra dữ liệu**:
  - `Bán 10 bao bột ngọt hết 50 nghìn` ──► `quantity = 10`, `price = 50000` (Tổng tiền được nói trong câu).
  - `Bán cho chị Mai 120 hộp bánh kẹo hết 1 triệu` ──► `quantity = 120`, `price = 1000000`.
  - `Bán 2 hộp bật lửa hết 100 nghìn` ──► `quantity = 2`, `price = 100000`.
  - `Xuất 120 hộp trà túi lọc cho bác Tư hết 250 nghìn` ──► `quantity = 120`, `price = 250000`.
  - `Mua 5 ký bột ngọt giá 20 ngàn một ký` ──► `quantity = 5`, `price = 20000` (Đơn vị giá khi chỉ nói đơn giá).
- **Kết luận**:
  - `price` trong ground truth là **giá trị số tiền cụ thể được phát ngôn trong câu** (quy đổi về số nguyên VND).
  - Ground truth **KHÔNG** thực hiện phép chia `total_amount / quantity` để tính đơn giá.

### B. Trường `payment`
- Trong toàn bộ 20 mẫu đầu của dataset, tất cả các câu chi phí (`chi_phi`) như *"Trả 20 nghìn tiền thuê mặt bằng"*, *"Trả 250 ngàn tiền thuê cửa hàng"*, *"Thanh toán 700 ngàn tiền phí ship"* đều có nhãn `payment = null`.
- Model chỉ trích xuất `payment = "credit"` khi câu có từ khóa nợ rõ ràng (`nợ`, `chưa trả`). Mọi trường hợp còn lại mặc định `null`.

### C. Trường `date`
- Dataset `voicecash_producer_1000.csv` không có cột nhãn `date`. Mọi dự đoán sinh ra `date` (như `"hôm nay"`) đều là hallucination và phải trả về `null`.

### D. Vai trò `customer` vs `supplier`
- Cấu trúc `cho [Tên]` trong câu bán hàng / xuất hàng (`ban_hang`, `xuat_kho`):
  - *"Bán cho chị Mai 120 hộp bánh kẹo"* ──► `customer = "chị Mai"`.
  - *"Xuất 15 gói bột ngọt cho em Trang"* ──► `customer = "em Trang"`.
  - *"Xuất 120 hộp trà túi lọc cho bác Tư"* ──► `customer = "bác Tư"`.
  - *"Xuất 3 hộp kem đánh răng cho chị Hương"* ──► `customer = "chị Hương"`.
- Cấu trúc `của [Tên]` trong câu nhập hàng (`nhap_hang`):
  - *"Vừa lấy 20 hộp sữa bột của cô Tám"* ──► `supplier = "cô Tám"`.
  - *"Lấy 3 thùng sữa hộp của công ty Thiên Phú"* ──► `supplier = "công ty Thiên Phú"`.

---

## 3. Chuẩn hóa Intent: `ban_hang` vs `xuat_kho` vs `nhap_hang` vs `chi_phi`

### Điểm bất nhất quán trước đây:
- Ban đầu trong file `voicecash_producer_1000.csv`, các câu bắt đầu bằng động từ *"Xuất"* (như *"Xuất 15 gói bột ngọt cho em Trang giá 500 nghìn"*, *"Xuất 3 hộp kem đánh răng cho chị Hương giá 500k"*, *"Xuất 120 hộp trà túi lọc cho bác Tư hết 250 nghìn"*) bị gắn nhãn nhầm thành `bán_hàng` (`sale`) do có thông tin người nhận và giá tiền.
- Đồng thời, code chuẩn hóa hậu nghiệm từng có heuristic gán ép `có người nhận + giá tiền = ban_hang`, gây xung đột giữa tầng NLP và nghiệp vụ kho bãi.

### Quy tắc chuẩn hóa mới:
1. **Ưu tiên hành động chính và hướng di chuyển hàng hóa**:
   - **`xuat_kho`**: Hành động là *"xuất"*, *"xuất kho"*, *"chuyển hàng ra khỏi kho"*. Kể cả khi câu có giá tiền hoặc người nhận ("cho em Trang"), intent cốt lõi vẫn là `xuat_kho`.
   - **`ban_hang`**: Hành động bán hàng trực tiếp: *"bán"*, *"bán cho"*, *"chốt đơn"*, *"khách lấy"*, *"giao"*.
   - **`nhap_hang`**: Mua hoặc nhập hàng hóa/nguyên liệu vào kho: *"nhập"*, *"vừa nhập"*, *"mua"*, *"mua thêm"*, *"lấy về"*, *"chi ... mua ... về bán"*. Hành động nhập hàng hóa có ưu tiên cao hơn thông tin tiền tệ ("hết 500 nghìn" không biến câu thành `chi_phi`).
   - **`chi_phi`**: Chi phí vận hành cửa hàng (tiền điện, nước, thuê mặt bằng, phí ship, lương nhân viên), KHÔNG bao gồm mua hàng hóa/tồn kho.
2. **Loại bỏ hoàn toàn logic ép intent trong Normalization-RAG**:
   - Toàn bộ việc nhận diện intent do LLM (Qwen2.5-1.5B) xử lý dựa trên semantic và prompt rõ ràng, không dùng regex/keyword ghi đè intent trong Python.
3. **Cập nhật nhãn Ground Truth tương ứng**:
   - Mẫu id 16, 18, 19 trong `voicecash_producer_1000.csv` đã được chuẩn hóa về `intent = xuat_kho` và `type = export` để bảo đảm tính nhất quán với nghiệp vụ VoiceCash.
