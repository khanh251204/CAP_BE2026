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
| **Ngày tạo (Date)** | 21/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_AUTH_-_REGISTER_001** |
| **Tiêu đề (Summary)** | [TC09] Positive: Dang ky tai khoan business RESELLER hop le |
| **Mức độ nghiêm trọng (Severity)** | **HIGH** |
| **Độ ưu tiên (Priority)** | **HIGH** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API Đăng ký phản hồi HTTP 500 khác với kỳ vọng 201. |

## 3. DESCRIPTION
Khi gọi API `/api/v1/register` với testcase **TC09 - Positive: Dang ky tai khoan business RESELLER hop le**, kết quả trả về HTTP Status **500**, không đúng với mã kỳ vọng **201**.

## 4. STEPS TO REPRODUCE
1. Chuẩn bị môi trường kiểm thử Backend.
2. Gửi request POST tới endpoint `/api/v1/register`.
4. Request Payload:
```json
{
  "fullName": "Tran Thi B",
  "email": "new_user_business_1792597375440@example.com",
  "password": "Password@123",
  "accountType": "business",
  "province": "Ho Chi Minh",
  "storeName": "Cua Hang Hoa Binh",
  "businessField": "RESELLER"
}
```

## 5. EXPECTED RESULT
API phản hồi HTTP Status Code: **201**.

## 6. ACTUAL RESULT
- **HTTP Status Code thực tế**: **500**
- **Response Body**:
```json
{
  "detail": "Không thể đăng ký tài khoản"
}
```

## 7. POTENTIAL ROOT CAUSE
⚠ **Suspected Root Cause**:
Backend validation logic hoặc exception handling chưa bắt và trả về mã HTTP chuẩn theo API Specification.

## 8. API RESPONSE
```json
{
  "detail": "Không thể đăng ký tài khoản"
}
```
- **HTTP Status**: 500
- **Endpoint**: `/api/v1/register`

## 9. IMPACT (Business/User Impact)
- Ảnh hưởng đến khả năng bắt lỗi đồng nhất trên Frontend / Mobile.
- Khiến người dùng hoặc client không nhận được thông báo phản hồi chính xác.

## 10. SUGGESTED FIX
Developer kiểm tra controller/service xử lý API tương ứng để trả về đúng HTTP Status Code và message thân thiện.

## 11. ATTACHMENT & NOTES
- Testcase ID: `TC09`
- Chi tiết Payload kiểm thử: `{"fullName":"Tran Thi B","email":"new_user_business_1792597375440@example.com","password":"Password@123","accountType":"business","province":"Ho Chi Minh","storeName":"Cua Hang Hoa Binh","businessField":"RESELLER"}`

## 12. ACCEPTANCE CRITERIA / VERIFICATION
☐  Gửi lại request với cùng payload ➔ API trả về đúng HTTP Status **201**.
☐  Chạy lại kịch bản test Playwright `TC09` đạt PASSED.

## 13. DEFECT LIFECYCLE
| Thuộc tính | Trạng thái |
| :--- | :--- |
| **Current Status** | Open |
| **Next Action** | Developer investigate and fix API response handling |
| **Retest Required** | Yes |
| **Regression Test Required** | Yes |
| **Reported by** | Khánh Hoàng |
| **Date** | 21/10/2026 |
| **Status** | Open |

---

