# DEFECT REPORT / BUG REPORT
**QA/QC Documentation • Web Application & System Integration**

---

## 1. PROJECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Tên dự án (Project)** | VoiceCashBook / Expense Tracker Web Platform |
| **Tính năng (Feature)** | Quản lý sản phẩm - Thêm sản phẩm mới (Add Product API) |
| **Người báo cáo (Tester)** | Khánh Hoàng / QA Automation Team |
| **Môi trường (Environment)** | Localhost / FastAPI Backend (Playwright API Automation) |
| **Ngày tạo (Date)** | 01/10/2026 |

---

## 2. DEFECT INFORMATION
| Trường thông tin | Chi tiết |
| :--- | :--- |
| **Defect ID** | **BUG_PRODUCT_001** |
| **Tiêu đề (Summary)** | API Thêm sản phẩm trả về HTTP 200 OK thay vì chuẩn HTTP 201 Created khi tạo mới thành công |
| **Mức độ nghiêm trọng (Severity)** | **LOW** |
| **Độ ưu tiên (Priority)** | **MEDIUM** |
| **Trạng thái (Status)** | **OPEN** |
| **Người xử lý (Assignee)** | Dev Backend |

### Giải thích (Explanation)
- **Severity: Low**: Nghiệp vụ tạo sản phẩm vẫn thành công và lưu vào database bình thường, không gây gián đoạn luồng dữ liệu hay mất mát thông tin.
- **Priority: Medium**: Cần chuẩn hóa mã HTTP response theo đúng chuẩn RESTful API (`POST` tạo mới tài nguyên phải trả về `201 Created`), giúp Frontend và các dịch vụ tích hợp bên ngoài (Mobile/Third-party) xử lý status code đồng nhất theo API contract.

---

## 3. DESCRIPTION
Khi gửi request `POST /api/v1/products` với dữ liệu sản phẩm hợp lệ, hệ thống tạo mới sản phẩm thành công vào cơ sở dữ liệu nhưng trả về mã HTTP `200 OK` thay vì mã chuẩn `201 Created`. Điều này không tuân thủ tài liệu API Specification và chuẩn RESTful conventions.

---

## 4. STEPS TO REPRODUCE
1. Đăng nhập hệ thống qua API `POST /api/v1/login` để lấy `Authorization Bearer Token`.
2. Gửi request `POST` đến endpoint `/api/v1/products` với header `Authorization: Bearer <valid_token>`.
3. Body JSON gửi lên:
   ```json
   {
     "product_name": "Coca Cola 330ml Test",
     "product_type": "RESALE",
     "default_unit": "lon",
     "unit_price": 10000,
     "min_quantity": 5
   }
   ```
4. Quan sát HTTP Status Code và Response Body trả về.

---

## 5. EXPECTED RESULT
1. Sản phẩm được tạo thành công trong Database.
2. HTTP Status Code trả về phải là **`201 Created`**.
3. Response body trả về thông tin sản phẩm vừa tạo kèm mã xác nhận thành công.

---

## 6. ACTUAL RESULT
1. Sản phẩm được tạo thành công trong Database.
2. HTTP Status Code thực tế trả về là **`200 OK`**.
3. Response body:
   ```json
   {
     "success": true,
     "message": "Tạo Product thành công",
     "data": {
       "product_id": 12,
       "product_name": "Coca Cola 330ml Test",
       "product_type": "RESALE",
       "default_unit": "lon",
       "unit_price": 10000.0,
       "min_quantity": 5.0
     }
   }
   ```

---

## 7. POTENTIAL ROOT CAUSE
⚠ **Suspected Root Cause – Cần Developer xác nhận:**
Trong file route `app/routes/product_route.py` tại dòng 76:
```python
@router.post("/products")
@router.post("/productsNew")
def create_product(...):
```
Endpoint chưa khai báo tham số `status_code=status.HTTP_201_CREATED`, do đó FastAPI mặc định gán mã HTTP Status là `200 OK`.

---

## 8. API RESPONSE
```json
{
  "success": true,
  "message": "Tạo Product thành công",
  "data": {
    "product_id": 12,
    "user_id": 150002,
    "product_name": "Coca Cola 330ml Test",
    "product_type": "RESALE",
    "default_unit": "lon",
    "unit_price": 10000.0,
    "min_quantity": 5.0,
    "is_active": true
  }
}
```
- **HTTP Status**: 200 OK (Kỳ vọng: 201 Created)
- **API Message**: Tạo Product thành công
- **Endpoint**: `POST /api/v1/products`

---

## 9. IMPACT (Business/User Impact)
- Sai lệch so với tài liệu API Contract giữa Backend và Frontend / Mobile.
- Các bộ kiểm thử tự động (Automation Test Suite) dựa trên REST standard assertion sẽ đánh trượt (FAIL) test case do không đúng HTTP Status mong đợi.
- Không gây ảnh hưởng dữ liệu người dùng cuối trên UI.

---

## 10. SUGGESTED FIX
Tại `app/routes/product_route.py`, bổ sung `status_code=status.HTTP_201_CREATED` cho decorator của router:
```python
@router.post(
    "/products",
    status_code=status.HTTP_201_CREATED
)
@router.post(
    "/productsNew",
    status_code=status.HTTP_201_CREATED
)
def create_product(
    data: dict,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return ProductController.create_product(data, user_id, db)
```

---

## 11. ATTACHMENT & NOTES
- Test Script Playwright: [add-product.api.spec.ts](file:///d:/Huy_Rearch/BE/test_api/add-product.api.spec.ts)
- Test Case ID: `TC01`, `TC02`, `TC03`, `TC04`
- Báo cáo lỗi tự động từ Playwright:
  ```text
  Expected Status: 201
  Actual Status:   200
  ```

---

## 12. ACCEPTANCE CRITERIA / VERIFICATION
- [ ] Gửi payload thêm sản phẩm hợp lệ ➔ API trả về đúng HTTP `201 Created`.
- [ ] Response body giữ nguyên cấu trúc chuẩn `{ success: true, message: "...", data: {...} }`.
- [ ] Các trường hợp lỗi dữ liệu đầu vào (tên rỗng, giá âm...) vẫn trả về mã lỗi client `400 Bad Request`.
- [ ] Chạy lại toàn bộ test suite Playwright `add-product.api.spec.ts` đạt kết quả PASS.

---

## 13. DEFECT LIFECYCLE
| Mục | Trạng thái |
| :--- | :--- |
| **Current Status** | Open |
| **Next Action** | Backend Dev thêm `status_code=status.HTTP_201_CREATED` vào route `/products`. |
| **Retest Required** | Yes |
| **Regression Test Required** | Yes |
| **Reported by** | Khánh Hoàng |
| **Date** | 01/10/2026 |
| **Status** | Open |
