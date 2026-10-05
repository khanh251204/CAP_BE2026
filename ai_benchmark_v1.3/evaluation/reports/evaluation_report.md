# VoiceCash Benchmark Evaluation Report

- **Total Evaluated Samples**: 20
- **Strict Match E2E Accuracy**: **0.00%** (0/20)
- **Normalized Match E2E Accuracy**: **60.00%** (12/20)

---

## 1. Intent Classification Metrics

| Metric | Giá trị |
| :--- | :--- |
| **Accuracy** | **95.00%** |
| **Macro Precision** | 97.44% |
| **Macro Recall** | 93.33% |
| **Macro F1-Score** | **94.96%** |
| **Weighted F1-Score** | 94.82% |

### Chi tiết từng Intent:
| Intent | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| `ban_hang` | 0.9231 | 1.0000 | **0.9600** | 12 |
| `chi_phi` | 1.0000 | 1.0000 | **1.0000** | 3 |
| `nhap_hang` | 1.0000 | 0.8000 | **0.8889** | 5 |

---

## 2. Confusion Matrix

| True \ Pred | pred_ban_hang | pred_chi_phi | pred_nhap_hang |
| :--- | :---: | :---: | :---: |
| true_ban_hang | 12 | 0 | 0 |
| true_chi_phi | 0 | 3 | 0 |
| true_nhap_hang | 1 | 0 | 4 |

---

## 3. Entity Extraction Metrics (Slot Filling)

- **Micro F1-Score**: **88.89%**
- **Macro F1-Score**: **79.83%**

### Chi tiết từng Entity:
| Entity | Precision | Recall | F1-Score | TP | FP | FN | Support |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `product` | 1.0000 | 1.0000 | **1.0000** | 17 | 0 | 0 | 17 |
| `new_product_name` | 0.0000 | 0.0000 | **0.0000** | 0 | 0 | 0 | 0 |
| `price` | 0.9231 | 0.7059 | **0.8000** | 12 | 1 | 5 | 17 |
| `quantity` | 1.0000 | 0.9412 | **0.9697** | 16 | 0 | 1 | 17 |
| `unit` | 0.9375 | 0.8824 | **0.9091** | 15 | 1 | 2 | 17 |
| `customer` | 1.0000 | 0.8333 | **0.9091** | 5 | 0 | 1 | 6 |
| `supplier` | 1.0000 | 1.0000 | **1.0000** | 3 | 0 | 0 | 3 |
| `date` | 0.0000 | 0.0000 | **0.0000** | 0 | 0 | 0 | 0 |
| `payment` | 0.0000 | 0.0000 | **0.0000** | 0 | 0 | 6 | 6 |

---

## 4. Error Analysis (8 Failed Samples)

| ID | Text | Failed Fields | Error Category | Expected | Predicted |
| :---: | :--- | :--- | :--- | :--- | :--- |
| 1 | Bán ra 50 suất cháo lòng đặc biệt hết 20 nghìn khách chuyển khoản | unit, payment | unit_error, payment_error | `intent`: ban_hang, `unit`: suất, `payment`: chuyển khoản | `intent`: ban_hang, `unit`: tuan, `payment`: None |
| 2 | Chốt đơn 30 phần cháo lòng giá 80 ngàn một phần trả tiền mặt | payment | payment_error | `intent`: ban_hang, `payment`: tiền mặt | `intent`: ban_hang, `payment`: None |
| 8 | Anh kiên lấy 5 tô cháo huyết bán nợ | price, customer, payment | price_error, customer_error, payment_error | `intent`: ban_hang, `price`: 50000.0, `customer`: anh Kiên, `payment`: nợ | `intent`: ban_hang, `price`: None, `customer`: None, `payment`: None |
| 9 | Bán cho chị Yến 1 tô cháo huyết ghi nợ | price, quantity, unit, payment | price_error, quantity_error, unit_error, payment_error | `intent`: ban_hang, `price`: 1000000.0, `quantity`: 1.0, `unit`: tô, `payment`: nợ | `intent`: ban_hang, `price`: None, `quantity`: None, `unit`: None, `payment`: None |
| 12 | Mua 5 hũ mắm tôm giá 100 nghìn một hũ | intent | intent_error | `intent`: nhap_hang | `intent`: ban_hang |
| 13 | Bán cho anh Long 50 hộp cháo lòng mang về chưa trả tiền | price, payment | price_error, payment_error | `intent`: ban_hang, `price`: 500000.0, `payment`: nợ | `intent`: ban_hang, `price`: None, `payment`: None |
| 17 | Lấy 25 kg gan heo ở tiệm rau cô Sáu hết 2 triệu đồng | price | price_error | `intent`: nhap_hang, `price`: 2000000.0 | `intent`: nhap_hang, `price`: 200000 |
| 18 | Anh phong lấy 20 tô cháo lòng thường ghi sổ nợ | price, payment | price_error, payment_error | `intent`: ban_hang, `price`: 10000.0, `payment`: nợ | `intent`: ban_hang, `price`: None, `payment`: None |

---

## 5. Normalization RAG Statistics

- **Tỷ lệ câu được chuẩn hóa**: **50.00%** (10/20 mẫu)
