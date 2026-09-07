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
    "quantity": "number|null",
    "unit": "string|null",
    "customer": "string|null",
    "supplier": "string|null",
    "date": "string|null",
    "payment": "string|null"
  },
  "missing_fields": [],
  "message": "string|null"
}

For sua_san_pham:
- product = old/current product name
- new_product_name = new name
- "A thành B" => product=A, new_product_name=B
"""