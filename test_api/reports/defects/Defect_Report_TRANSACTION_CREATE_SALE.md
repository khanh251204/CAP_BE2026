# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

*Tổng hợp các lỗi phát hiện tự động từ đợt kiểm thử Playwright API*

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Web Platform |
| **Tính năng (Feature)** | Transactions - Create Sale (Bán hàng) |
| **Người báo cáo (Tester)** | Khánh Hoàng |
| **Môi trường (Environment)** | Localhost / Backend FastAPI (Playwright API Automation) |
| **Ngày tạo (Date)** | 1/10/2026 |

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_TRANSACTIONS_-_CREATE_SALE_(BÁN_HÀNG)_001** |
| **Tiêu đề (Summary)** | [TC04] Ban hang gia tien am |
| **Mức độ nghiêm trọng (Severity)** | **MEDIUM** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |
| **Giải thích** | API Tạo giao dịch bán hàng phản hồi HTTP 201 khác với kỳ vọng 400. |

## 3. DESCRIPTION
Khi gọi API `/api/v1/transactions` với testcase **TC04 - Ban hang gia tien am**, kết quả trả về HTTP Status **201**, không đúng với mã kỳ vọng **400**.

## 4. STEPS TO REPRODUCE
1. Chuẩn bị môi trường kiểm thử Backend.
2. Gửi request POST tới endpoint `/api/v1/transactions`.
3. Headers:
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNTAwMDIiLCJlbWFpbCI6ImJ1aXRoaW5odTE0MDhAZ21haWwuY29tIiwicm9sZSI6InVzZXIiLCJidXNpbmVzc190eXBlIjoiUkVTRUxMRVIiLCJleHAiOjE3OTA3OTM0OTIsInR5cGUiOiJhY2Nlc3MifQ.0f7CbR4X3yhpCPluQyp9jneaqC5LO3Syn_BVdjqPQIo"
}
```
4. Request Payload:
```json
{
  "intent": "ban_hang",
  "text": "Bán 2 lon Coca Cola 330ml giá -5000",
  "product": "Coca Cola 330ml",
  "price": -5000,
  "quantity": 2,
  "unit": "lon"
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
    "transaction_id": 1680058,
    "user_id": 150002,
    "intent_id": 30002,
    "intent": "ban_hang",
    "intent_name": "ban_hang",
    "intent_type": "INCOME",
    "type": "INCOME",
    "account_id": 1,
    "customer_id": null,
    "supplier_id": null,
    "product_id": 990001,
    "inventory_transaction_id": 1260018,
    "debt_id": null,
    "quantity": 2,
    "unit": "lon",
    "unit_price": -2500,
    "total_amount": -5000,
    "payment_status": "PAID",
    "input_method": "MANUAL",
    "input_text": "Bán 2 lon Coca Cola 330ml giá -5000",
    "transaction_date": "2026-10-01T01:23:19.278867",
    "created_at": "2026-10-01T01:23:19",
    "updated_at": "2026-10-01T01:23:19"
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
    "transaction_id": 1680058,
    "user_id": 150002,
    "intent_id": 30002,
    "intent": "ban_hang",
    "intent_name": "ban_hang",
    "intent_type": "INCOME",
    "type": "INCOME",
    "account_id": 1,
    "customer_id": null,
    "supplier_id": null,
    "product_id": 990001,
    "inventory_transaction_id": 1260018,
    "debt_id": null,
    "quantity": 2,
    "unit": "lon",
    "unit_price": -2500,
    "total_amount": -5000,
    "payment_status": "PAID",
    "input_method": "MANUAL",
    "input_text": "Bán 2 lon Coca Cola 330ml giá -5000",
    "transaction_date": "2026-10-01T01:23:19.278867",
    "created_at": "2026-10-01T01:23:19",
    "updated_at": "2026-10-01T01:23:19"
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
- Chi tiết Payload kiểm thử: `{"intent":"ban_hang","text":"Bán 2 lon Coca Cola 330ml giá -5000","product":"Coca Cola 330ml","price":-5000,"quantity":2,"unit":"lon"}`

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

