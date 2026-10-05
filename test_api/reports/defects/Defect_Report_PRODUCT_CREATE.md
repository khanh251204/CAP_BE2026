# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

*Tổng hợp các lỗi phát hiện tự động từ đợt kiểm thử Playwright API*

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Web Platform |
| **Tính năng (Feature)** | Products - Create Product |
| **Người báo cáo (Tester)** | Khánh Hoàng |
| **Môi trường (Environment)** | Localhost / Backend FastAPI (Playwright API Automation) |
| **Ngày tạo (Date)** | 1/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_PRODUCTS_-_CREATE_PRODUCT_001** |
| **Tiêu đề (Summary)** | [TC25] Security: SQL injection trong product_name |
| **Mức độ nghiêm trọng (Severity)** | **MEDIUM** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API Thêm sản phẩm phản hồi HTTP 400 khác với kỳ vọng 200. |

## 3. DESCRIPTION
Khi gọi API `/api/v1/products` với testcase **TC25 - Security: SQL injection trong product_name**, kết quả trả về HTTP Status **400**, không đúng với mã kỳ vọng **200**.

## 4. STEPS TO REPRODUCE
1. Chuẩn bị môi trường kiểm thử Backend.
2. Gửi request POST tới endpoint `/api/v1/products`.
3. Headers:
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNTAwMDIiLCJlbWFpbCI6ImJ1aXRoaW5odTE0MDhAZ21haWwuY29tIiwicm9sZSI6InVzZXIiLCJidXNpbmVzc190eXBlIjoiUkVTRUxMRVIiLCJleHAiOjE3OTA3OTMwMzcsInR5cGUiOiJhY2Nlc3MifQ.QVKHaRXHPj99uRs38Vrn9zDx-ilkwhrA3Tn5g1hz7RA"
}
```
4. Request Payload:
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
API phản hồi HTTP Status Code: **200**.

## 6. ACTUAL RESULT
- **HTTP Status Code thực tế**: **400**
- **Response Body**:
```json
{
  "detail": "Sản phẩm 'Banh Snack' OR '1'='1' đã tồn tại"
}
```

## 7. POTENTIAL ROOT CAUSE
⚠ **Suspected Root Cause**:
Backend validation logic hoặc exception handling chưa bắt và trả về mã HTTP chuẩn theo API Specification.

## 8. API RESPONSE
```json
{
  "detail": "Sản phẩm 'Banh Snack' OR '1'='1' đã tồn tại"
}
```
- **HTTP Status**: 400
- **Endpoint**: `/api/v1/products`

## 9. IMPACT (Business/User Impact)
- Ảnh hưởng đến khả năng bắt lỗi đồng nhất trên Frontend / Mobile.
- Khiến người dùng hoặc client không nhận được thông báo phản hồi chính xác.

## 10. SUGGESTED FIX
Developer kiểm tra controller/service xử lý API tương ứng để trả về đúng HTTP Status Code và message thân thiện.

## 11. ATTACHMENT & NOTES
- Testcase ID: `TC25`
- Chi tiết Payload kiểm thử: `{"product_name":"Banh Snack' OR '1'='1","product_type":"RESALE","default_unit":"goi","unit_price":6000,"min_quantity":5}`

## 12. ACCEPTANCE CRITERIA / VERIFICATION
☐  Gửi lại request với cùng payload ➔ API trả về đúng HTTP Status **200**.
☐  Chạy lại kịch bản test Playwright `TC25` đạt PASSED.

## 13. DEFECT LIFECYCLE
| Thuộc tính | Trạng thái |
| :--- | :--- |
| **Current Status** | Open |
| **Next Action** | Developer investigate and fix API response handling |
| **Retest Required** | Yes |
| **Regression Test Required** | Yes |
| **Reported by** | Khánh Hoàng |
| **Date** | 1/10/2026 |
| **Status** | Open |

---

