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
    "price": "number|null",
    "total_price": "number|null",
    "quantity": "number|null",
    "unit": "string|null",
    "customer": "string|null",
    "supplier": "string|null",
    "date": "string|null",
    "payment": "string|null",
    "category": "string|null"
  },
  "missing_fields": [],
  "message": "string|null"
}
"""
