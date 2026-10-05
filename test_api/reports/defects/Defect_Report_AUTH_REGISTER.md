# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

*Tổng hợp các lỗi phát hiện tự động từ đợt kiểm thử Playwright API*

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Web Platform |
| **Tính năng (Feature)** | Auth - Register |
| **Người báo cáo (Tester)** | Khánh Hoàng |
| **Môi trường (Environment)** | Localhost / Backend FastAPI (Playwright API Automation) |
| **Ngày tạo (Date)** | 1/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_AUTH_-_REGISTER_001** |
| **Tiêu đề (Summary)** | [TC08] Positive: Dang ky tai khoan personal hop le |
| **Mức độ nghiêm trọng (Severity)** | **MEDIUM** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API Đăng ký phản hồi HTTP 409 khác với kỳ vọng 201. |

## 3. DESCRIPTION
Khi gọi API `/api/v1/register` với testcase **TC08 - Positive: Dang ky tai khoan personal hop le**, kết quả trả về HTTP Status **409**, không đúng với mã kỳ vọng **201**.

## 4. STEPS TO REPRODUCE
1. Chuẩn bị môi trường kiểm thử Backend.
2. Gửi request POST tới endpoint `/api/v1/register`.
4. Request Payload:
```json
{
  "fullName": "Nguyen Van A",
  "email": "new_user_personal_1790792491878@example.com",
  "password": "Password@123",
  "accountType": "personal",
  "province": "Ha Noi"
}
```

## 5. EXPECTED RESULT
API phản hồi HTTP Status Code: **201**.

## 6. ACTUAL RESULT
- **HTTP Status Code thực tế**: **409**
- **Response Body**:
```json
{
  "detail": "Email đã được đăng ký"
}
```

## 7. POTENTIAL ROOT CAUSE
⚠ **Suspected Root Cause**:
Backend validation logic hoặc exception handling chưa bắt và trả về mã HTTP chuẩn theo API Specification.

## 8. API RESPONSE
```json
{
  "detail": "Email đã được đăng ký"
}
```
- **HTTP Status**: 409
- **Endpoint**: `/api/v1/register`

## 9. IMPACT (Business/User Impact)
- Ảnh hưởng đến khả năng bắt lỗi đồng nhất trên Frontend / Mobile.
- Khiến người dùng hoặc client không nhận được thông báo phản hồi chính xác.

## 10. SUGGESTED FIX
Developer kiểm tra controller/service xử lý API tương ứng để trả về đúng HTTP Status Code và message thân thiện.

## 11. ATTACHMENT & NOTES
- Testcase ID: `TC08`
- Chi tiết Payload kiểm thử: `{"fullName":"Nguyen Van A","email":"new_user_personal_1790792491878@example.com","password":"Password@123","accountType":"personal","province":"Ha Noi"}`

## 12. ACCEPTANCE CRITERIA / VERIFICATION
☐  Gửi lại request với cùng payload ➔ API trả về đúng HTTP Status **201**.
☐  Chạy lại kịch bản test Playwright `TC08` đạt PASSED.

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

