# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

*Tổng hợp các lỗi phát hiện tự động từ đợt kiểm thử Playwright API*

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Web Platform |
| **Tính năng (Feature)** | Transactions - Create Purchase (Mua hàng) |
| **Người báo cáo (Tester)** | Khánh Hoàng |
| **Môi trường (Environment)** | Localhost / Backend FastAPI (Playwright API Automation) |
| **Ngày tạo (Date)** | 1/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_TRANSACTIONS_-_CREATE_PURCHASE_(MUA_HÀNG)_001** |
| **Tiêu đề (Summary)** | [TC04] Mua hang gia tien am |
| **Mức độ nghiêm trọng (Severity)** | **MEDIUM** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API Tạo giao dịch mua hàng phản hồi HTTP 201 khác với kỳ vọng 400. |

## 3. DESCRIPTION
Khi gọi API `/api/v1/transactions` với testcase **TC04 - Mua hang gia tien am**, kết quả trả về HTTP Status **201**, không đúng với mã kỳ vọng **400**.

## 4. STEPS TO REPRODUCE
1. Chuẩn bị môi trường kiểm thử Backend.
2. Gửi request POST tới endpoint `/api/v1/transactions`.
3. Headers:
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNTAwMDIiLCJlbWFpbCI6ImJ1aXRoaW5odTE0MDhAZ21haWwuY29tIiwicm9sZSI6InVzZXIiLCJidXNpbmVzc190eXBlIjoiUkVTRUxMRVIiLCJleHAiOjE3OTA3OTM0OTAsInR5cGUiOiJhY2Nlc3MifQ.zUM6hu3ytiaKSq3BzWUBF8QQH2GYexgqlM0iqMZ1X1U"
}
```
4. Request Payload:
```json
{
  "intent": "mua_hang",
  "text": "Mua 100 loc Sua tuoi Vinamilk giá -500000",
  "product": "Sua tuoi Vinamilk",
  "price": -500000,
  "quantity": 100,
  "unit": "loc"
}
```

## 5. EXPECTED RESULT
API phản hồi HTTP Status Code: **400**.

## 6. ACTUAL RESULT
- **HTTP Status Code thực tế**: **201**
- **Response Body**:
```json
{
  "success": true,
  "message": "Đã lưu giao dịch thành công!",
  "data": {
    "transaction_id": 1680060,
    "user_id": 150002,
    "intent_id": 30001,
    "intent": "mua_hang",
    "intent_name": "mua_hang",
    "intent_type": "EXPENSE",
    "type": "EXPENSE",
    "account_id": 1,
    "customer_id": null,
    "supplier_id": null,
    "product_id": 990021,
    "inventory_transaction_id": 1260019,
    "debt_id": null,
    "quantity": 100,
    "unit": "loc",
    "unit_price": -5000,
    "total_amount": -500000,
    "payment_status": "PAID",
    "input_method": "MANUAL",
    "input_text": "Mua 100 loc Sua tuoi Vinamilk giá -500000",
    "transaction_date": "2026-10-01T01:23:19.605276",
    "created_at": "2026-10-01T01:23:20",
    "updated_at": "2026-10-01T01:23:20"
  }
}
```

## 7. POTENTIAL ROOT CAUSE
⚠ **Suspected Root Cause**:
Backend validation logic hoặc exception handling chưa bắt và trả về mã HTTP chuẩn theo API Specification.

## 8. API RESPONSE
```json
{
  "success": true,
  "message": "Đã lưu giao dịch thành công!",
  "data": {
    "transaction_id": 1680060,
    "user_id": 150002,
    "intent_id": 30001,
    "intent": "mua_hang",
    "intent_name": "mua_hang",
    "intent_type": "EXPENSE",
    "type": "EXPENSE",
    "account_id": 1,
    "customer_id": null,
    "supplier_id": null,
    "product_id": 990021,
    "inventory_transaction_id": 1260019,
    "debt_id": null,
    "quantity": 100,
    "unit": "loc",
    "unit_price": -5000,
    "total_amount": -500000,
    "payment_status": "PAID",
    "input_method": "MANUAL",
    "input_text": "Mua 100 loc Sua tuoi Vinamilk giá -500000",
    "transaction_date": "2026-10-01T01:23:19.605276",
    "created_at": "2026-10-01T01:23:20",
    "updated_at": "2026-10-01T01:23:20"
  }
}
```
- **HTTP Status**: 201
- **Endpoint**: `/api/v1/transactions`

## 9. IMPACT (Business/User Impact)
- Ảnh hưởng đến khả năng bắt lỗi đồng nhất trên Frontend / Mobile.
- Khiến người dùng hoặc client không nhận được thông báo phản hồi chính xác.

## 10. SUGGESTED FIX
Developer kiểm tra controller/service xử lý API tương ứng để trả về đúng HTTP Status Code và message thân thiện.

## 11. ATTACHMENT & NOTES
- Testcase ID: `TC04`
- Chi tiết Payload kiểm thử: `{"intent":"mua_hang","text":"Mua 100 loc Sua tuoi Vinamilk giá -500000","product":"Sua tuoi Vinamilk","price":-500000,"quantity":100,"unit":"loc"}`

## 12. ACCEPTANCE CRITERIA / VERIFICATION
☐  Gửi lại request với cùng payload ➔ API trả về đúng HTTP Status **400**.
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

