# VoiceCash AI Benchmark Module (Llama 3.1 8B & Groq)

Module độc lập phục vụ đánh giá và benchmark mô hình NLP phân loại ý định (Intent Classification) và trích xuất thực thể (Slot Filling / Entity Extraction) cho hệ thống kế toán giọng nói **VoiceCash**.

---

## 🌟 Đặc Điểm Nổi Bật

1. **Hoàn toàn độc lập (Decoupled & Isolated)**:
   - **KHÔNG** kết nối database (MySQL / TiDB).
   - **KHÔNG** gọi MCP production tools.
   - **KHÔNG** phụ thuộc FastAPI backend hay React Native mobile app.
   - Có thể chạy độc lập trên máy tính cá nhân hoặc môi trường GPU đám mây (Google Colab).
2. **Hỗ trợ Đa Mô Hình (Model Abstraction)**:
   - **Llama 3.1 8B Instruct** (`meta-llama/Llama-3.1-8B-Instruct`): Chạy local với 4-bit NF4 Quantization (BitsAndBytes) trên GPU.
   - **Groq API** (`openai/gpt-oss-120b`, `llama-3.3-70b-versatile`): Dùng làm baseline so sánh độ chính xác và tốc độ.
3. **Streaming Persistence & Resume**:
   - Ghi từng kết quả dự đoán ngay lập tức vào file `.jsonl` kèm lệnh `flush()`.
   - Khi chạy lại, tự động quét các sample ID đã hoàn thành và **bỏ qua**, không bị mất kết quả hay chạy lặp lại khi Colab ngắt kết nối.
4. **Đánh Giá Toàn Diện (Offline Evaluation)**:
   - Tính toán bằng Python & `scikit-learn` hoàn toàn ngoại tuyến sau khi inference xong.
   - Đo đạc cả **Strict Match** và **Normalized Match** cho End-to-End Accuracy.
   - Xuất đầy đủ Confusion Matrix, Per-class Intent report, Per-entity report, Benchmark summary.

---

## 📁 Cấu Trúc Thư Mục

```text
ai_benchmark/
├── README.md                      # Hướng dẫn chi tiết
├── requirements.txt               # Dependencies độc lập cho benchmark
├── config.py                      # Cấu hình môi trường, paths, hyper-parameters
├── schemas.py                     # Schema Pydantic cho entities, predictions, summary
├── run.py                         # CLI entrypoint thống nhất
├── prompts/
│   └── intent_entity_prompt.txt   # Prompt chuẩn hóa, deterministic cho benchmark
├── models/
│   ├── base.py                    # Interface ModelProvider trừu tượng
│   ├── groq_model.py              # Provider cho Groq API
│   └── llama_local.py             # Provider cho Hugging Face Llama 3.1 8B 4-bit
├── inference/
│   └── predictor.py               # Engine chạy inference, streaming JSONL & resume
├── evaluation/
│   ├── normalization.py           # Chuẩn hóa tiếng Việt, tiền tệ, đơn vị, intent
│   ├── metrics.py                 # Tính Accuracy, F1, Precision, Recall, E2E
│   ├── confusion_matrix.py        # Tính và xuất Confusion Matrix
│   └── evaluator.py               # Offline evaluator đọc file JSONL và xuất reports
├── datasets/
│   ├── README.md                  # Tài liệu cấu trúc dataset
│   └── voicecash_producer_1000.csv# Tập dữ liệu 1000 mẫu PRODUCER
├── predictions/
│   └── .gitkeep                   # Nơi lưu trữ các file predictions.jsonl
└── notebooks/
    └── llama31_8b_colab.ipynb     # Jupyter Notebook sẵn sàng chạy trên Google Colab GPU
```

---

## ⚙️ Cài Đặt (Installation)

### 1. Trên máy Local
Cài đặt các thư viện cần thiết:
```bash
pip install -r ai_benchmark/requirements.txt
```

Nếu muốn chạy mô hình Groq, hãy cấu hình API Key trong file `.env` hoặc biến môi trường:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 2. Trên Google Colab
Mở notebook `ai_benchmark/notebooks/llama31_8b_colab.ipynb`, chọn runtime **T4 GPU** hoặc **A100 GPU**. Notebook đã tích hợp cell cài đặt tự động.

---

## 🔑 Cấu Hình Hugging Face Token (Cho Llama 3.1 8B)

Llama 3.1 8B là gated model. Bạn cần:
1. Đăng nhập [Hugging Face](https://huggingface.co/) và chấp thuận điều khoản tại [meta-llama/Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct).
2. Tạo User Access Token (loại Read).
3. Đặt token vào biến môi trường:
   ```bash
   export HF_TOKEN="hf_your_token"   # Linux/macOS
   $env:HF_TOKEN="hf_your_token"      # Windows PowerShell
   ```
   *Trên Google Colab: Thêm Secret có tên `HF_TOKEN` trong mục biểu tượng chìa khóa bên trái giao diện.*

---

## 🚀 Hướng Dẫn Sử Dụng (CLI Commands)

### 1. Chạy Benchmark với Groq API (Local / Cloud)
```bash
# Chạy 50 mẫu đầu tiên
python -m ai_benchmark.run --model-provider groq --limit 50

# Chạy 100 mẫu ngẫu nhiên có phân tầng theo intent
python -m ai_benchmark.run --model-provider groq --sample 100 --stratified --delay 0.3
```

### 2. Chạy Benchmark với Llama 3.1 8B Instruct (GPU)
```bash
# Chạy 200 mẫu trên GPU với 4-bit quantization
python -m ai_benchmark.run --model-provider llama_local --model-name meta-llama/Llama-3.1-8B-Instruct --limit 200 --load-in-4bit true
```

### 3. Bật RAG Kiến Thức (ChromaDB + VectorStore)
Để kiểm tra tác động của RAG đối với độ chính xác trích xuất từ lóng/phương ngữ:
```bash
# Bật RAG với Groq
python -m ai_benchmark.run --model-provider groq --use-rag --limit 50

# Tùy chỉnh top-k và ngưỡng similarity
python -m ai_benchmark.run --model-provider groq --use-rag --rag-top-k 2 --rag-threshold 0.40 --limit 50
```
Kết quả dự đoán sẽ tự động được lưu riêng vào file `{model}_rag_predictions.jsonl` và ghi nhận context `knowledge` trong từng mẫu.

### 4. Chỉ Chạy Offline Evaluation (Không gọi lại LLM)
Nếu bạn đã có file kết quả `predictions.jsonl` từ Colab hoặc phiên chạy trước, bạn có thể phân tích số liệu offline ngay lập tức:
```bash
python -m ai_benchmark.run --eval-only --predictions-file ai_benchmark/predictions/meta_llama_Llama_3.1_8B_Instruct_predictions.jsonl
```

---

## 📊 Phương Pháp Đánh Giá (Evaluation Methodology)

### 1. Intent Classification
- **Accuracy**: Tỷ lệ phân loại intent đúng trên toàn bộ tập dữ liệu.
- **Macro F1-Score**: Điểm F1 trung bình không trọng số giữa các lớp ý định (đánh giá tốt trên dữ liệu mất cân bằng).
- **Weighted F1-Score**: Điểm F1 có trọng số theo số lượng mẫu thực tế của từng lớp.
- **Confusion Matrix**: Ma trận nhầm lẫn chi tiết giữa nhãn thực tế (Ground Truth) và nhãn dự đoán.

### 2. Entity Extraction (Slot Filling)
Đánh giá độc lập cho từng thực thể trong 9 thực thể:
- `product`: Tên sản phẩm / nguyên liệu
- `new_product_name`: Tên mới khi đổi tên
- `price`: Đơn giá (đơn giá x số lượng hoặc tổng chi phí)
- `quantity`: Số lượng
- `unit`: Đơn vị tính chuẩn hóa (kg, lit, hop, chai, cai...)
- `customer`: Tên khách hàng
- `supplier`: Tên nhà cung cấp
- `date`: Thời gian
- `payment`: Trạng thái/phương thức thanh toán

### 3. End-to-End (E2E) Match
Một mẫu được coi là **E2E Đúng** khi:
- Intent dự đoán đúng; **VÀ**
- Tất cả các trường thực thể xuất hiện trong ground-truth đều được dự đoán chính xác.

Báo cáo phân tách rõ:
- **Strict Match Accuracy**: So khớp nguyên bản (exact string & value).
- **Normalized Match Accuracy**: So khớp sau khi chuẩn hóa tiếng Việt, đơn vị đồng nghĩa, và chuyển đổi tiền tệ (ví dụ: *100k* = *100000*, *ký* = *kg*).

---

## 📈 Kết Quả Xuất Ra (Output Artifacts)

Sau mỗi phiên benchmark, các tệp sau được lưu tại `ai_benchmark/evaluation/reports/` và `ai_benchmark/predictions/`:
- `evaluation_report.json`: Báo cáo chỉ số chi tiết dạng JSON.
- `evaluation_report.md`: Báo cáo tóm tắt định dạng Markdown trực quan.
- `classification_report.csv`: Bảng số liệu Precision, Recall, F1, Support cho từng Intent.
- `entity_metrics.csv`: Bảng số liệu Precision, Recall, F1 cho từng Entity.
- `confusion_matrix.csv`: Bảng ma trận nhầm lẫn Intent.
- `predictions.jsonl`: Bản ghi chi tiết từng mẫu gồm text, prediction, latency (ms), input/output tokens, error.
- `benchmark_summary.json`: Tóm tắt hiệu năng: throughput (mẫu/giây), độ trễ p50/p95/avg, mức tiêu thụ VRAM GPU.
