from pydantic import BaseModel
from typing import Optional


class TransactionCreateRequest(BaseModel):

    # Thông tin chung
    text: Optional[str] = ""
    intent: Optional[str] = ""
    type: Optional[str] = ""

    # Thông tin chi tiết
    product: str
    price: float
    quantity: float

    # Thông tin chi tiết (không bắt buộc)
    unit: Optional[str] = None
    customer: Optional[str] = None
    supplier: Optional[str] = None
    date: Optional[str] = None
    payment: Optional[str] = None