# VoiceCashBook Data Lake Architecture

Thư mục lưu trữ dữ liệu nghiên cứu và huấn luyện AI cho hệ thống VoiceCashBook.

## Cấu trúc các phân vùng (Zones):

1. **`raw/voice/`**: Lưu trữ tham chiếu metadata âm thanh và giọng nói thô khi người dùng ghi âm.
2. **`processed/ai_result/`**: Lưu trữ snapshot kết quả phân tích AI (Transcript, Intent, Entities) theo từng bản ghi giao dịch.
   Kèm số token LLM của giao dịch: `input_tokens`, `output_tokens` và `token_usage`
   (`total_tokens`, `llm_calls`, `calls[]` — chi tiết từng lần gọi: model, token, độ trễ).
   Một giao dịch có thể gọi LLM nhiều lần (phân tích ở bước STT, agent phân tích lại) → số liệu được cộng dồn.
3. **`feedback/correction/`**: Dữ liệu hiệu chỉnh từ người dùng khi điều chỉnh kết quả nhận diện (Human-in-the-loop).
4. **`dataset/`**: Bộ dữ liệu tổng hợp phục vụ AI Evaluation & Research. Cũng có `input_tokens`, `output_tokens`, `token_usage` như vùng processed.

> **Lưu ý**: Các tệp JSON chi tiết sinh ra trong quá trình chạy ứng dụng (`YYYY-MM-DD/*.json`) được quản lý cục bộ và bỏ qua bởi Git (thông qua `.gitignore`) để tránh làm phình repository và bảo mật thông tin giao dịch người dùng.
