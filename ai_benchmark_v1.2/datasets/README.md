# VoiceCash NLP Benchmark Datasets

Thư mục này chứa tập dữ liệu đánh giá ngoại tuyến độc lập cho mô hình NLP VoiceCash.

## 1. File dữ liệu
- `voicecash_producer_1000.csv`: Tập dữ liệu 1000 câu giao dịch tiếng Việt mô hình `PRODUCER` (Sản xuất / Chế biến / F&B).

## 2. Cấu trúc Schema
| Cột | Ý nghĩa | Ví dụ |
| :--- | :--- | :--- |
| `id` | Mã định danh duy nhất của mẫu | `1`, `2`, `3` |
| `text` | Câu nói giao dịch tiếng Việt | `Khách lấy 50 hộp bánh trả 700k` |
| `business_type` | Loại hình kinh doanh | `PRODUCER` |
| `intent` | Ý định kế toán cốt lõi | `bán_hàng`, `nhập_hàng`, `chi_phi` |
| `product` | Tên sản phẩm / nguyên liệu | `hộp bánh` |
| `new_product_name` | Tên sản phẩm mới khi sửa đổi | `null` |
| `price` | Đơn giá chuẩn hóa hoặc tổng chi phí (VND) | `700000` |
| `quantity` | Số lượng sản phẩm | `50` |
| `unit` | Đơn vị tính | `hộp`, `kg`, `chai` |
| `customer` | Tên hoặc cách xưng hô khách hàng | `chị Linh`, `cô Ba` |
| `supplier` | Tên nhà cung cấp | `anh Bình`, `bác Hai` |
| `date` | Thời gian được nhắc đến | `Chiều nay`, `Cuối ngày hôm nay` |
| `payment` | Trạng thái hoặc hình thức thanh toán | `PAID`, `PENDING` |

## 3. Nguyên tắc bất biến (Ground Truth Immutability)
1. **Không sửa đổi Ground Truth**: Tuyệt đối không thay đổi các giá trị nhãn gốc trong file CSV.
2. **Offline Evaluation**: Toàn bộ quy trình so khớp và tính toán chỉ số (Accuracy, F1, Exact Match) được thực hiện offline thông qua module `ai_benchmark/evaluation/`.
3. **Sampling**: Hỗ trợ `--limit`, `--sample`, hoặc `--stratified` để chọn mẫu đại diện cân bằng giữa các ý định.
