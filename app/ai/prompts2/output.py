OUTPUT_FORMAT_AND_EXAMPLES = """
# OUTPUT FORMAT

LLM PHẢI trả về đúng 1 JSON object.
Không giải thích thêm.
Không dùng Markdown.
Không thêm field ngoài schema.

## SCHEMA

{
  "status": "success hoặc error",
  "text": "Văn bản đã sửa lỗi chính tả",
  "intent": "Tên intent",
  "type": "income hoặc expense",
  "entities": {
    "product": "Tên sản phẩm hoặc null",
    "price": 150000,
    "quantity": 2,
    "unit": "Đơn vị hoặc null",
    "customer": "Tên/Xưng hô khách hàng hoặc null",
    "supplier": "Tên nhà cung cấp/chủ hàng hoặc null",
    "date": "Thời gian được nhắc đến hoặc null",
    "payment": "Hình thức/Trạng thái thanh toán hoặc null"
  },
  "missing_fields": [],
  "message": null
}

## QUY TẮC

### 1. status

- "success": Khi đủ thông tin bắt buộc.
- "error": Khi thiếu thông tin bắt buộc.

### 2. entities

Giữ nguyên cấu trúc:

- product: Tên sản phẩm hoặc null.
- price: Số tiền dạng số hoặc null.
- quantity: Số lượng dạng số hoặc null.
- unit: Đơn vị hoặc null.
- customer: Tên/xưng hô khách hàng hoặc null.
- supplier: Tên nhà cung cấp/chủ hàng hoặc null.
- date: Thời gian được nhắc đến hoặc null.
- payment: Hình thức/trạng thái thanh toán hoặc null.

Không tự đoán thông tin mà người dùng chưa nói.

### 3. Khi status = "success"

- missing_fields phải là [].
- message phải là null.

### 4. Khi status = "error"

- missing_fields chứa các trường bắt buộc còn thiếu.
- message là câu thông báo để người dùng biết cần bổ sung thông tin gì.
- Các thông tin đã xác định được vẫn phải giữ lại trong entities.
- Không tự điền giá trị còn thiếu.

# EXAMPLES

## Example 1: SUCCESS

Input:
Bán cho anh Hùng 5 ký cá rô 200 nghìn thiếu lại mai trả

Output:
{
  "status": "success",
  "text": "Bán cho anh Hùng 5 kg cá rô 200 nghìn thiếu lại mai trả.",
  "intent": "khách_ghi_nợ",
  "type": "income",
  "entities": {
    "product": "Cá rô",
    "price": 200000,
    "quantity": 5,
    "unit": "kg",
    "customer": "Anh Hùng",
    "supplier": null,
    "date": "Mai",
    "payment": "Nợ (Thiếu lại)"
  },
  "missing_fields": [],
  "message": null
}

---

## Example 2: SUCCESS

Input:
Sáng nay trả tiền chị Lan 2 triệu tiền nhập rau đợt trước

Output:
{
  "status": "success",
  "text": "Sáng nay trả tiền chị Lan 2 triệu tiền nhập rau đợt trước.",
  "intent": "trả_nợ_nhà_cung_cấp",
  "type": "expense",
  "entities": {
    "product": "Rau",
    "price": 2000000,
    "quantity": null,
    "unit": null,
    "customer": null,
    "supplier": "Chị Lan",
    "date": "Sáng nay",
    "payment": "Đã trả"
  },
  "missing_fields": [],
  "message": null
}

---

## Example 3: ERROR - Thiếu giá

Input:
Bán cho anh Hùng 5 ký cá rô

Output:
{
  "status": "error",
  "text": "Bán cho anh Hùng 5 kg cá rô.",
  "intent": "bán_hàng",
  "type": "income",
  "entities": {
    "product": "Cá rô",
    "price": null,
    "quantity": 5,
    "unit": "kg",
    "customer": "Anh Hùng",
    "supplier": null,
    "date": null,
    "payment": null
  },
  "missing_fields": [
    "entities.price"
  ],
  "message": "Bạn chưa nói giá tiền của cá rô. Vui lòng cung cấp thêm giá tiền."
}

---

## Example 4: ERROR - Thiếu số lượng và giá

Input:
Bán cho anh Hùng cá rô

Output:
{
  "status": "error",
  "text": "Bán cho anh Hùng cá rô.",
  "intent": "bán_hàng",
  "type": "income",
  "entities": {
    "product": "Cá rô",
    "price": null,
    "quantity": null,
    "unit": null,
    "customer": "Anh Hùng",
    "supplier": null,
    "date": null,
    "payment": null
  },
  "missing_fields": [
    "entities.price",
    "entities.quantity"
  ],
  "message": "Bạn chưa nói giá tiền và số lượng cá rô. Vui lòng cung cấp thêm."
}
"""