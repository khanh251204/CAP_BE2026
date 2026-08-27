from pydantic import BaseModel
from typing import Optional

class TransactionCreateRequest(BaseModel):

    # ThÃ´ng tin chung
    text: Optional[str] = ""
    intent: Optional[str] = ""
    type: Optional[str] = ""

    # ThÃ´ng tin chi tiáº¿t (Báº¯t buá»™c pháº£i cÃ³)
    product: str
    price: float
    quantity: float

    # ThÃ´ng tin chi tiáº¿t (KhÃ´ng báº¯t buá»™c)
    unit: Optional[str] = None
    customer: Optional[str] = None
    supplier: Optional[str] = None
    date: Optional[str] = None
    payment: Optional[str] = None
