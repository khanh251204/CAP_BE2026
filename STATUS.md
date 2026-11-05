# PROJECT STATUS: VoiceCashBook AI Subsystem
**Cập nhật lần cuối:** 2026-11-04  
**Dự án:** VoiceCashBook Backend (FastAPI + MySQL/TiDB + Groq LPUs)  
**Tài liệu tham chiếu:** [docs/ai_architecture_analysis.md](file:///d:/Huy_Rearch/BE/docs/ai_architecture_analysis.md), [docs/ai_pipeline_specification.md](file:///d:/Huy_Rearch/BE/docs/ai_pipeline_specification.md), [AGENTS.md](file:///d:/Huy_Rearch/BE/AGENTS.md)

---

## 1. TỔNG QUAN KIẾN TRÚC & TIẾN ĐỘ THỰC HIỆN

| Hạng mục kiến trúc | Trạng thái | Chi tiết triển khai | Độ sẵn sàng |
| :--- | :--- | :--- | :--- |
| **1. Audio Pipeline & STT** | ✅ Hoàn thành | FFmpeg giải mã 16kHz PCM, WebRTC VAD lọc khoảng lặng, Groq Whisper API (`whisper-large-v3-turbo`) | 100% |
| **2. Normalization-RAG Layer** | ✅ Hoàn thành | `NormalizationService` (in-memory regex greedy match, < 10ms), chuẩn hóa đơn vị tính, số từ, tiền tệ và từ lóng 3 miền | 95% |
| **3. LLM Inference Engine** | ✅ Hoàn thành | `openai/gpt-oss-120b` chạy trên Groq LPU qua `GroqService`, trích xuất 9 thực thể JSON có cấu trúc | 95% |
| **4. AI Agent Orchestrator** | ✅ Hoàn thành | `Agent` (`app/ai/core/agent.py`), luồng 2 pha (Analyze $\rightarrow$ Waiting Confirmation $\rightarrow$ Confirm), điều phối qua `SessionStoreService` | 100% |
| **5. Intent Router** | ✅ Hoàn thành | `IntentRouter` (`app/ai/core/router.py`), 17 handlers và aliases nghiệp vụ | 100% |
| **6. MCP Layer (FastMCP)** | ✅ Hoàn thành | 4 MCP Servers: `product`, `inventory`, `debt`, `expense` kết nối qua `app/ai/mcp/client.py` | 95% |
| **7. Business Rules Validation** | ✅ Hoàn thành | Chuẩn hóa `business_type` (`RESELLER`, `PRODUCER`, `SERVICE`) & `product_type` (`RESALE`, `RAW_MATERIAL`, `FINISHED_GOOD`) | 95% |
| **8. Data Lake & MLOps Loop** | ✅ Hoàn thành | `DataLakeService`: Ghi nhận bất đồng bộ Voice record, kết quả AI, và diff sửa lỗi từ người dùng | 90% |

---

## 2. MA TRẬN TIẾN ĐỘ CÁC INTENTS

### 2.1. PHẠM VI CAPSTONE 1 (7 INTENT CỐT LÕI - GIAO DỊCH TÀI CHÍNH & KHO MCP)

| STT | Intent | Nghiệp vụ | Phân loại | MCP Tool Trọng Tâm | Quy Tắc Nghiệp Vụ / Tác Động Dữ Liệu | Trạng Thái |
| :---: | :--- | :--- | :---: | :--- | :--- | :---: |
| 1 | `ban_hang` | Bán hàng cho khách | `INCOME` | `check_stock`, `export_inventory` | Tạo Tx, trừ kho (`Inventory_Tx OUT` nếu là RESELLER, cho phép stock=0 nếu là PRODUCER FINISHED_GOOD, bỏ qua nếu SERVICE), tạo Debt nếu còn nợ. | ✅ Hoàn thành |
| 2 | `mua_hang` (`nhap_hang`) | Mua hàng từ nhà cung cấp | `EXPENSE` | `import_inventory` | Tạo Tx, tăng kho (`Inventory_Tx IN`), tạo Debt nếu mua nợ NCC. | ✅ Hoàn thành |
| 3 | `chi_tien` (`chi_phi`) | Chi phí kinh doanh (điện, nước, mặt bằng...) | `EXPENSE` | `create_expense` | Tạo Tx chi phí, trừ số dư tài khoản (`Account.balance`). | ✅ Hoàn thành |
| 4 | `ghi_no_khach_hang` (`khach_ghi_no`) | Ghi nợ khách hàng | `DEBT (RECEIVABLE)` | `ghi_no_khach_hang` | Tạo bản ghi nợ phải thu trong Debt (`direction = RECEIVABLE`). | ✅ Hoàn thành |
| 5 | `thu_no_khach_hang` (`thu_no_khach`) | Thu nợ khách hàng | `DEBT / INCOME` | `thu_no_khach_hang` | Thu nợ, tạo phiếu thu, cấn trừ công nợ theo FIFO hoặc chỉ định. | ✅ Hoàn thành |
| 6 | `ghi_no_nha_cung_cap` (`ghi_no_ncc`) | Ghi nợ nhà cung cấp | `DEBT (PAYABLE)` | `ghi_no_nha_cung_cap` | Tạo bản ghi nợ phải trả trong Debt (`direction = PAYABLE`). | ✅ Hoàn thành |
| 7 | `tra_no_nha_cung_cap` (`tra_no_ncc`) | Trả nợ nhà cung cấp | `DEBT (PAYABLE) / EXPENSE` | `thu_no_nha_cung_cap` | Thanh toán nợ, giảm công nợ NCC (`direction = PAYABLE`). | ✅ Hoàn thành |

### 2.2. PHẠM VI CAPSTONE 2 (CÁC INTENTS MỞ RỘNG & TÍNH NĂNG NÂNG CAO)

| STT | Intent | Nhóm nghiệp vụ | Handler / Tool | Ghi chú & Kế hoạch triển khai Capstone 2 |
| :---: | :--- | :--- | :--- | :--- |
| 1 | `them_san_pham` | Danh mục sản phẩm | `create_product` | Thêm sản phẩm mới bằng giọng nói kèm đơn giá, loại sản phẩm. |
| 2 | `sua_san_pham` | Danh mục sản phẩm | `update_product` | Chỉnh sửa tên, đơn vị tính, đơn giá, ngưỡng tồn an toàn. |
| 3 | `xoa_san_pham` | Danh mục sản phẩm | `delete_product` | Soft-delete (`is_active = 0`) bảo toàn toàn vẹn lịch sử giao dịch. |
| 4 | `tim_san_pham` | Danh mục sản phẩm | `search_products` | Tra cứu giá và thông tin tồn kho sản phẩm. |
| 5 | `nhap_kho` | Quản trị kho nội bộ | `nhap_kho` | Chỉ nhập kho KHÔNG mất tiền (tồn đầu kỳ, hàng tặng, khách trả lại, sản xuất xong). "Nhập kho / thêm vào kho" thông thường được hiểu là `mua_hang` (có giao dịch chi). |
| 6 | `xuat_kho` | Quản trị kho nội bộ | `xuat_kho` | Xuất kho điều chuyển / hao hụt nội bộ. |
| 7 | `hang_hong` | Quản trị kho nội bộ | `report_damage` | Ghi nhận hàng tồn kho hư hỏng/hết hạn (`type = DAMAGE`). |
| 8 | `kiem_kho` | Quản trị kho nội bộ | `check_stock`, `adjust_stock` | Hỏi tồn trả kết quả ngay; báo số đếm thực tế → bản nháp, xác nhận ghi `ADJUSTMENT`. |
| 9 | `bao_cao` | Báo cáo & Phân tích | `Report MCP` | Tổng hợp doanh thu, chi phí, lợi nhuận, công nợ định kỳ. |
| 10 | `chot_so` | Báo cáo & Phân tích | `preview_closing`, `close_period` | Chốt sổ ngày / tháng / quý / năm: xem trước → xác nhận → `ClosingService.create_closing`. |
| 11 | **BOM Module** | Nghiệp vụ nâng cao | Production Service | Định mức nguyên vật liệu cho `PRODUCER`. |
| 12 | **Multi-item Batch** | AI Core nâng cao | LLM 120B Inference | Trích xuất và xử lý nhiều sản phẩm trong 1 câu nói. |

---

## 3. TRẠNG THÁI CÁC MCP SERVERS

| Server | Đường dẫn | Công cụ cung cấp | Trạng thái |
| :--- | :--- | :--- | :---: |
| **Product MCP** | `app/ai/mcp/product/` | `get_all_products`, `get_product_by_id`, `search_products`, `create_product`, `update_product`, `delete_product` | ✅ Hoạt động ổn định |
| **Inventory MCP** | `app/ai/mcp/inventory/` | `check_stock`, `import_inventory`, `export_inventory`, `nhap_kho`, `xuat_kho`, `report_damage`, `adjust_stock` | ✅ Hoạt động ổn định |
| **Debt MCP** | `app/ai/mcp/debt/` | `ghi_no_khach_hang`, `thu_no_khach_hang`, `ghi_no_nha_cung_cap`, `thu_no_nha_cung_cap` | ✅ Hoạt động ổn định |
| **Expense MCP** | `app/ai/mcp/expense/` | `create_expense` | ✅ Hoạt động ổn định |
| **Report MCP** | `app/ai/mcp/report/` | `get_summary_report`, `preview_closing`, `close_period` | ✅ Hoạt động ổn định |

---

## 4. QUY TẮC NGHIỆP VỤ & TỒN KHO THEO BUSINESS_TYPE

| Tiêu chí | RESELLER | PRODUCER | SERVICE |
| :--- | :--- | :--- | :--- |
| **Bản chất** | Mua hàng về và bán lại trực tiếp. | Mua nguyên liệu $\rightarrow$ chế biến/sản xuất $\rightarrow$ bán thành phẩm. | Cung cấp dịch vụ (sửa chữa, cắt tóc, vận chuyển...). |
| **Product Type chính** | `RESALE` | `RAW_MATERIAL` & `FINISHED_GOOD` | Không yêu cầu hoặc dịch vụ vô hình. |
| **Kiểm tra tồn kho khi bán** | **BẮT BUỘC**: `qty_sell <= current_stock`. Nếu thiếu $\rightarrow$ Báo lỗi `out_of_stock`. | **KHÔNG BẮT BUỘC** với `FINISHED_GOOD` (sản xuất theo order, cho phép bán khi tồn = 0). Chặn bán trực tiếp `RAW_MATERIAL`. | **KHÔNG KIỂM TRA TỒN KHO**. |
| **Biến động kho (Inventory_Tx)** | Ghi giảm `OUT` tương ứng khi xác nhận bán. | Giữ nguyên trừ khi có lệnh xuất kho/sản xuất (BOM phase sau). | Không tạo bản ghi `Inventory_Transaction.OUT`. |

---

## 5. CÔNG VIỆC ĐANG THỰC HIỆN & BACKLOG TIẾP THEO

- [x] Thiết lập chuẩn hóa `business_type` và `product_type` trong DB và code.
- [x] Áp dụng quy tắc tồn kho theo mô hình kinh doanh cho intent `ban_hang`.
- [x] Thử nghiệm FastMCP client cho 4 nhóm nghiệp vụ cốt lõi.
- [x] Tạo Skill Antigravity `voicecash-agent` tại `.agents/skills/voicecash-agent/SKILL.md`.
- [x] Nhiều sản phẩm trong một câu ("Bán 2 lon coca và 3 gói mì") cho `ban_hang` / `mua_hang`: `app/ai/core/multi_item.py`, prompt 1.3.0 (`entities.items`). Mỗi dòng đi qua handler một sản phẩm, một dòng lỗi thì huỷ cả bản nháp (`line_index`), gộp dòng trùng sản phẩm, kiểm tra nguyên liệu BOM theo tổng; xác nhận là một giao dịch nhiều dòng. Test: `tests/test_multi_item.py`. Chưa làm: sản phẩm mới trong câu nhiều dòng (báo thêm sản phẩm trước); màn Xác nhận trên mobile hiển thị / sửa từng dòng; benchmark AI cho câu nhiều sản phẩm.
- [x] BOM cho `PRODUCER`: bảng `Bill_Of_Material`, `/boms`, trừ nguyên liệu khi bán, cảnh báo thiếu. Chi tiết giao dịch trả thêm `materials_used` (nguyên liệu đã trừ lúc bán, lấy từ dòng xuất kho gắn giao dịch nên sửa định mức sau này không đổi lịch sử). Không làm intent khai báo BOM bằng giọng nói (nhập trên mobile).
- [~] Test tranh chấp tồn kho song song: `tests/test_concurrent_stock_mysql.py` (4 kịch bản), chỉ chạy khi đặt `TEST_MYSQL_URL` trỏ tới database riêng tên `*_test`; **chưa chạy trên MySQL thật**. Đã đổi đọc tồn trong các hàm ghi kho sang `SELECT ... FOR UPDATE` (`get_latest_stock(for_update=True)`) vì MySQL/TiDB mặc định REPEATABLE READ có thể đọc tồn cũ sau khi chờ khoá; sửa lỗi hai dòng cùng sản phẩm trong một đơn cùng thấy tồn cũ (bán vượt tồn).
- [x] Audit Log giao dịch, công nợ, kho (2026-11-04): bảng `Audit_Log` (migration `e7a4c1b9d205`), ghi tự động bằng sự kiện ORM khi `Transaction` / `Transaction_Detail` được tạo / sửa / xoá (`app/services/audit_service.py`). Cùng database transaction với thao tác gốc (rollback thì không có vết), kèm người thực hiện (USER / ADMIN / SYSTEM, lấy từ token qua `SystemLogMiddleware`), nguồn nhập, trước / sau / trường đổi. Lỗi ghi vết không làm hỏng giao dịch. API admin: `GET /admin/audit-logs`, `/admin/audit-logs/summary`, `/admin/audit-logs/transactions/{id}` (quyền `system:log_read`). Test: `tests/test_audit_log.py`, `tests/test_admin_audit_monitoring.py`. Cũng ghi vết công nợ (`Debt`, `Debt_Payment`) và biến động kho (`Inventory_Transaction`, kể cả kiểm kê / hàng hỏng không gắn giao dịch). Chưa ghi vết: sản phẩm, khách hàng, nhà cung cấp, tài khoản.
- [x] Cài đặt ghi vết cho admin (2026-11-04), vì Audit Log và system_logs ngốn DB: bảng `App_Setting` (migration `f2c8d6a1b730`, khoá `observability`), `app/services/app_setting_service.py` (mặc định, kiểm tra giá trị, cache 30 giây, lỗi đọc DB thì dùng mặc định). Admin chọn: chức năng nào được ghi vết (giao dịch, dòng hàng, nợ, thu/trả nợ, kho; kho mặc định TẮT), lưu đầy đủ trước/sau hay chỉ trường đổi, số ngày giữ Audit Log (0 = giữ mãi), có ghi request thành công vào system_logs không, có lưu body/query không, số ngày giữ log thường / log lỗi. API `GET/PUT /admin/settings/observability`, `POST .../reset`, `POST .../cleanup`, quyền mới `system:setting_manage`. `DataRetentionScheduler` dọn mỗi ngày theo lô nhỏ (trước đây `system_logs` có hàm dọn nhưng không lịch nào gọi nên phình mãi). Test: `tests/test_observability_settings.py`. Cần đăng nhập lại / đồng bộ quyền để role có `system:setting_manage` (ADMIN tự có).
- [x] AI Monitoring: `GET /admin/ai-monitoring/corrections` trả tỉ lệ người dùng sửa bản nháp AI theo lệnh (Voice_Record SUCCESS làm mẫu số, User_Correction làm tử số), kèm trường bị sửa nhiều nhất và số bị từ chối; gộp tên lệnh cũ (nhap_hang -> mua_hang...). Hiệu chỉnh không gắn bản ghi giọng nói được đếm riêng. Cần chạy `scripts/run_migrations.py` (hoặc alembic) để tạo bảng `Audit_Log` trên DB thật.
- [x] Sửa 15 test BE đang lỗi (2026-11-04): test dùng tên module cũ `nhap_hang`; `them_san_pham` chặn giá ≤ 0; bán dịch vụ không nói số lượng mặc định 1 lần, đơn vị "lần", nhãn "Dịch vụ mới"; test Groq không phụ thuộc key 4..9 trong .env máy; test dọn thông báo theo quy tắc mới (xoá mọi thông báo quá hạn). Kết quả: 449 đạt, 4 bỏ qua (test MySQL).
- [x] Chuẩn hoá số lượng nói đời thường (`NormalizationService._normalize_quantities`): "hai chục" -> 20, "ba ký rưỡi" -> 3.5 kg, "năm lăm" -> 55, "một xị" (sau từ báo giá) -> 100000, "nửa ký" -> 0.5 kg; tiền và tên người ("chị Ba") giữ nguyên. Test: `tests/test_normalization_spoken.py`. Từ điển JSON thêm 12 mục; tiếp tục bổ sung từ `datalake_improve.py dict` khi có dữ liệu sửa.
