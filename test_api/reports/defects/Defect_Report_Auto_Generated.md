# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

*Tổng hợp các lỗi phát hiện tự động từ đợt chạy kiểm thử API Thêm Product*

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Web Platform |
| **Tính năng (Feature)** | Thêm sản phẩm (Add Product API) |
| **Người báo cáo (Tester)** | Khánh Hoàng / Playwright Automation |
| **Môi trường (Environment)** | Localhost / Backend FastAPI |
| **Ngày tạo (Date)** | 1/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_PRODUCT_001** |
| **Tiêu đề (Summary)** | [TC25] Security: SQL injection trong product_name - Kỳ vọng Status 200 nhưng nhận được 400 |
| **Mức độ nghiêm trọng (Severity)** | **MEDIUM** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API không trả về đúng status code kỳ vọng khi gửi payload test. Cần điều chỉnh logic xử lý response hoặc validation backend. |

## 3. DESCRIPTION
Khi gửi request POST tới endpoint `/api/v1/products` với case **Security: SQL injection trong product_name**, hệ thống trả về HTTP Status **400** thay vì mã mong đợi **200**.

## 4. STEPS TO REPRODUCE
1. Xác thực đăng nhập qua `/api/v1/login`.
2. Gửi request POST tới `/api/v1/products`.
3. Header: `Content-Type: application/json`, Authorization: Bearer <token>.
4. Payload gửi lên:
```json
{
  "product_name": "Banh Snack' OR '1'='1",
  "product_type": "RESALE",
  "default_unit": "goi",
  "unit_price": 6000,
  "min_quantity": 5
}
```

## 5. EXPECTED RESULT
API trả về HTTP Status Code: **200**.

## 6. ACTUAL RESULT
- HTTP Status Code: **400**
- Response Body:
```json
{
  "detail": "Sản phẩm 'Banh Snack' OR '1'='1' đã tồn tại"
}
```

## 7. POTENTIAL ROOT CAUSE
Backend xử lý trả về mã lỗi/mã phản hồi chưa đồng nhất với quy chuẩn API hoặc chưa bắt ngoại lệ đúng cách.

## 8. API RESPONSE
```json
{
  "detail": "Sản phẩm 'Banh Snack' OR '1'='1' đã tồn tại"
}
```
- **HTTP Status**: 400
- **Endpoint**: `/api/v1/products`

## 9. IMPACT
Gây sai lệch contract giữa Backend và Frontend/Automation Test, có thể gây hiểu nhầm trạng thái giao dịch cho người dùng.

## 10. SUGGESTED FIX
Developer kiểm tra lại validator hoặc endpoint decorator tại `app/routes/product_route.py` và `app/services/product_service.py`.

## 11. ATTACHMENT & NOTES
- Test ID liên quan: `TC25`
- Chi tiết Payload: `{"product_name":"Banh Snack' OR '1'='1","product_type":"RESALE","default_unit":"goi","unit_price":6000,"min_quantity":5}`

## 12. ACCEPTANCE CRITERIA / VERIFICATION
☐  Gửi lại đúng payload trên ➔ API trả về đúng mã **200**.
☐  Chạy lại testcase `TC25` trong Playwright đạt PASSED.

## 13. DEFECT LIFECYCLE
Current Status: Open | Assignee: Dev Backend | Retest Required: Yes

---

