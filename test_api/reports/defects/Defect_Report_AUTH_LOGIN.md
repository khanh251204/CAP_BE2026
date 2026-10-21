# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

*Tổng hợp các lỗi phát hiện tự động từ đợt kiểm thử Playwright API*

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Web Platform |
| **Tính năng (Feature)** | Auth - Login |
| **Người báo cáo (Tester)** | Khánh Hoàng |
| **Môi trường (Environment)** | Localhost / Backend FastAPI (Playwright API Automation) |
| **Ngày tạo (Date)** | 21/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_AUTH_-_LOGIN_001** |
| **Tiêu đề (Summary)** | [TC08] Password 300 ky tu |
| **Mức độ nghiêm trọng (Severity)** | **MEDIUM** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API Đăng nhập phản hồi HTTP 400 khác với mong đợi 422. |

## 3. DESCRIPTION
Khi gọi API `/api/v1/login` với testcase **TC08 - Password 300 ky tu**, kết quả trả về HTTP Status **400**, không đúng với mã kỳ vọng **422**.

## 4. STEPS TO REPRODUCE
1. Chuẩn bị môi trường kiểm thử Backend.
2. Gửi request POST tới endpoint `/api/v1/login`.
4. Request Payload:
```json
{
  "email": "buithinhu1408@gmail.com",
  "password": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
}
```

## 5. EXPECTED RESULT
API phản hồi HTTP Status Code: **422**.

## 6. ACTUAL RESULT
- **HTTP Status Code thực tế**: **400**
- **Response Body**:
```json
{
  "status": "error",
  "success": false,
  "message": "Dữ liệu không hợp lệ",
  "detail": [
    {
      "type": "string_too_long",
      "loc": [
        "body",
        "password"
      ],
      "msg": "String should have at most 128 characters",
      "input": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
      "ctx": {
        "max_length": 128
      }
    }
  ]
}
```

## 7. POTENTIAL ROOT CAUSE
⚠ **Suspected Root Cause**:
Backend validation logic hoặc exception handling chưa bắt và trả về mã HTTP chuẩn theo API Specification.

## 8. API RESPONSE
```json
{
  "status": "error",
  "success": false,
  "message": "Dữ liệu không hợp lệ",
  "detail": [
    {
      "type": "string_too_long",
      "loc": [
        "body",
        "password"
      ],
      "msg": "String should have at most 128 characters",
      "input": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
      "ctx": {
        "max_length": 128
      }
    }
  ]
}
```
- **HTTP Status**: 400
- **Endpoint**: `/api/v1/login`

## 9. IMPACT (Business/User Impact)
- Ảnh hưởng đến khả năng bắt lỗi đồng nhất trên Frontend / Mobile.
- Khiến người dùng hoặc client không nhận được thông báo phản hồi chính xác.

## 10. SUGGESTED FIX
Developer kiểm tra controller/service xử lý API tương ứng để trả về đúng HTTP Status Code và message thân thiện.

## 11. ATTACHMENT & NOTES
- Testcase ID: `TC08`
- Chi tiết Payload kiểm thử: `{"email":"buithinhu1408@gmail.com","password":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}`

## 12. ACCEPTANCE CRITERIA / VERIFICATION
☐  Gửi lại request với cùng payload ➔ API trả về đúng HTTP Status **422**.
☐  Chạy lại kịch bản test Playwright `TC08` đạt PASSED.

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

