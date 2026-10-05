# Báo Cáo Đánh Giá Hiệu Năng Dự Án NLP Groq

- **Mô hình Groq**: `openai/gpt-oss-120b`
- **Tập dữ liệu**: `evaluation/voicecash_producer_1000.csv`
- **Số lượng mẫu đánh giá**: `25`
- **Sentence Exact Match Accuracy**: **`72.00%`** (18/25)

---

## 1. Intent Classification (Phân loại ý định)

| Metric | Giá trị |
| :--- | :--- |
| **Overall Accuracy** | **92.00%** |
| **Macro Precision** | **75.00%** |
| **Macro Recall** | **70.23%** |
| **Macro F1-Score** | **72.49%** |
| **Weighted F1-Score** | **95.80%** |

### Chi tiết theo từng Intent:

| Intent | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| `ban_hang` | 1.0000 | 0.9091 | **0.9524** | 11 |
| `chi_phi` | 1.0000 | 1.0000 | **1.0000** | 4 |
| `nhap_hang` | 1.0000 | 0.9000 | **0.9474** | 10 |
| `xuat_kho` | 0.0000 | 0.0000 | **0.0000** | 0 |

---

## 2. Entity Extraction (Trích xuất thực thể / Slot Filling)

| Entity | Precision | Recall | F1-Score | TP | FP | FN | Support |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `product` | 0.9524 | 0.9524 | **0.9524** | 20 | 1 | 1 | 21 |
| `price` | 0.8824 | 0.8824 | **0.8824** | 15 | 2 | 2 | 17 |
| `quantity` | 1.0000 | 1.0000 | **1.0000** | 21 | 0 | 0 | 21 |
| `unit` | 0.5882 | 1.0000 | **0.7407** | 10 | 7 | 0 | 10 |
| `customer` | 1.0000 | 0.7143 | **0.8333** | 5 | 0 | 2 | 7 |
| `supplier` | 1.0000 | 1.0000 | **1.0000** | 4 | 0 | 0 | 4 |
| `date` | 0.6667 | 0.3333 | **0.4444** | 2 | 1 | 4 | 6 |

### Tổng hợp Entity Extraction:
- **Micro Precision**: `87.50%`
- **Micro Recall**: `89.53%`
- **Micro F1-Score**: **`88.51%`**
- **Macro F1-Score**: **`83.62%`**

---

## 3. Nhận xét và Phân tích lỗi
- Đánh giá dựa trên tập dữ liệu sản xuất của VoiceCashBook (`PRODUCER`).
- Tỷ lệ nhận diện các intent giao dịch cốt lõi (`ban_hang`, `nhap_hang`, `chi_phi`).
- Độ chính xác trích xuất thực thể số lượng (`quantity`), giá bán (`price`), và sản phẩm (`product`).