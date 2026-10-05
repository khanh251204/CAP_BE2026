# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

*Tổng hợp các lỗi phát hiện tự động từ đợt kiểm thử Playwright API*

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Web Platform |
| **Tính năng (Feature)** | Products - Delete Product |
| **Người báo cáo (Tester)** | Khánh Hoàng |
| **Môi trường (Environment)** | Localhost / Backend FastAPI (Playwright API Automation) |
| **Ngày tạo (Date)** | 1/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_PRODUCTS_-_DELETE_PRODUCT_001** |
| **Tiêu đề (Summary)** | [TC04] Positive: Xoa mem san pham thanh cong (is_active = False) |
| **Mức độ nghiêm trọng (Severity)** | **MEDIUM** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API Xóa sản phẩm phản hồi HTTP 404 khác với kỳ vọng 200. |

## 3. DESCRIPTION
Khi gọi API `/api/v1/products/99999999` với testcase **TC04 - Positive: Xoa mem san pham thanh cong (is_active = False)**, kết quả trả về HTTP Status **404**, không đúng với mã kỳ vọng **200**.

## 4. STEPS TO REPRODUCE
1. Chuẩn bị môi trường kiểm thử Backend.
2. Gửi request POST tới endpoint `/api/v1/products/99999999`.
3. Headers:
```json
{
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNTAwMDIiLCJlbWFpbCI6ImJ1aXRoaW5odTE0MDhAZ21haWwuY29tIiwicm9sZSI6InVzZXIiLCJidXNpbmVzc190eXBlIjoiUkVTRUxMRVIiLCJleHAiOjE3OTA3OTMwMjEsInR5cGUiOiJhY2Nlc3MifQ.NUIChDLZdAJiQHNwmCrc60hKvAHcLNC14qmthlHNyXE"
}
```
4. Request Payload:
```json
{}
```

## 5. EXPECTED RESULT
API phản hồi HTTP Status Code: **200**.

## 6. ACTUAL RESULT
- **HTTP Status Code thực tế**: **404**
- **Response Body**:
```json
{
  "detail": "Không tìm thấy Product hoặc bạn không có quyền xóa"
}
```

## 7. POTENTIAL ROOT CAUSE
⚠ **Suspected Root Cause**:
Backend validation logic hoặc exception handling chưa bắt và trả về mã HTTP chuẩn theo API Specification.

## 8. API RESPONSE
```json
{
  "detail": "Không tìm thấy Product hoặc bạn không có quyền xóa"
}
```
- **HTTP Status**: 404
- **Endpoint**: `/api/v1/products/99999999`

## 9. IMPACT (Business/User Impact)
- Ảnh hưởng đến khả năng bắt lỗi đồng nhất trên Frontend / Mobile.
- Khiến người dùng hoặc client không nhận được thông báo phản hồi chính xác.

## 10. SUGGESTED FIX
Developer kiểm tra controller/service xử lý API tương ứng để trả về đúng HTTP Status Code và message thân thiện.

## 11. ATTACHMENT & NOTES
- Testcase ID: `TC04`
- Chi tiết Payload kiểm thử: `{}`

## 12. ACCEPTANCE CRITERIA / VERIFICATION
☐  Gửi lại request với cùng payload ➔ API trả về đúng HTTP Status **200**.
☐  Chạy lại kịch bản test Playwright `TC04` đạt PASSED.

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

