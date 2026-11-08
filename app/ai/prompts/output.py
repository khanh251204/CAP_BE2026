# prompts/output.py

OUTPUT_FORMAT_AND_EXAMPLES = """
Return JSON only:
{
  "status": "success|error",
  "text": "string",
  "intent": "string",
  "type": "income|expense|none",
  "entities": {
    "product": "string|null",
    "new_product_name": "string|null",
    "price": "number|null",
    "total_price": "number|null",
    "quantity": "number|null",
    "unit": "string|null",
    "customer": "string|null",
    "supplier": "string|null",
    "date": "string|null",
    "payment": "string|null",
    "category": "string|null",
    "items": "null | [{\"product\":string,\"quantity\":number|null,\"unit\":string|null,\"price\":number|null,\"total_price\":number|null}] (chỉ khi câu có từ 2 mặt hàng trở lên)"
  },
  "missing_fields": [],
  "message": "string|null"
}

Lưu ý cho sua_san_pham: product=tên cũ, new_product_name=tên mới ("A thành B" => product=A, new_product_name=B).
"""