# VoiceCash AI Benchmark v1.0 (Baseline Version)

Đây là phiên bản lưu trữ nguyên trạng của module **AI** và công cụ đánh giá **Benchmark v1.0** của hệ thống VoiceCash trước thời điểm tối ưu hóa đồng bộ với benchmark v1.2.

---

## 📁 Cấu trúc thư mục

```text
ai_benchmark_v1.0/
├── README.md                      # Tài liệu mô tả phiên bản v1.0
├── ai/                            # Toàn bộ mã nguồn app/ai nguyên bản trước khi sửa
│   ├── core/                      # Agent, Router, Handlers, State
│   │   ├── agent.py               # Agent cũ (chưa qua tiền/hậu xử lý và chưa truyền knowledge/business_type)
│   │   ├── handlers.py
│   │   ├── router.py
│   │   └── state.py
│   ├── intents/                   # Các Intent handlers
│   ├── llm/                       # Dịch vụ GroqService & GeminiService gốc
│   │   ├── groq_service.py        # GroqService ban đầu (chưa tích hợp normalization pipeline)
│   │   └── gemini_service.py
│   ├── mcp/                       # MCP client và tools
│   ├── prompts/                   # Hệ thống prompt cũ
│   │   ├── common.py              # Quy tắc chung 18 dòng
│   │   ├── entity.py              # Quy tắc trích xuất thực thể 28 dòng
│   │   ├── intent.py              # Bảng phân loại intent 33 dòng
│   │   ├── main.py                # Ghép nối prompt hệ thống
│   │   └── output.py              # Schema output 26 dòng
│   ├── rag/                       # RAG & Normalization cũ
│   │   ├── knowledge/
│   │   │   └── normalization_data.json # Từ điển cũ (còn chứa từ "cân")
│   │   ├── normalization_service.py    # Service cũ (chưa có _normalize_money)
│   │   ├── rag_service.py
│   │   └── vector_store.py
│   └── version.py                 # Phiên bản 1.0.0
└── evaluation/                    # Bộ công cụ đánh giá v1.0
    ├── evaluation_report.md       # Báo cáo đánh giá hiệu năng v1.0 (Exact match: 72.00%)
    ├── evaluator.py               # NLPEvaluator chạy qua GroqService cũ
    ├── groq_predictions_cache.json# Cache kết quả dự đoán
    ├── metrics.py                 # Hàm tính toán chỉ số
    ├── predictions.csv            # File so sánh ground truth vs predicted
    ├── run_evaluation.py          # Entrypoint chạy đánh giá
    └── voicecash_producer_1000.csv# Tập dữ liệu 1000 mẫu
```

---

## 📊 Hiệu năng phiên bản v1.0

- **Mô hình**: `openai/gpt-oss-120b` (Groq API)
- **Sentence Exact Match Accuracy**: **`72.00%`** (18/25)
- **Intent Accuracy**: **`92.00%`**
- **Entity Micro F1**: **`88.51%`**
- **Price F1**: `88.24%`
- **Unit F1**: `74.07%` (Precision 58.82%, nhiều false positive do dính token tiền tệ)
- **Date F1**: `44.44%` (Hallucination ngày hiện tại)
