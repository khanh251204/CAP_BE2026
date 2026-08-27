from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

class TransactionCreateRequest(BaseModel):
    
    # Thông tin chung
    text: Optional[str] = ""
    intent: Optional[str] = ""
    type: Optional[str] = ""
    
    # Thông tin chi tiết (Bắt buộc phải có)
    product: str
    price: float
    quantity: float
    
    # Thông tin chi tiết (Không bắt buộc)
    unit: Optional[str] = None
    customer: Optional[str] = None
    supplier: Optional[str] = None
    date: Optional[str] = None
    payment: Optional[str] = None


class TransactionDetailUpdate(BaseModel):
    product: str
    quantity: Decimal
    unit: str
    unit_price: Decimal


class TransactionUpdateRequest(BaseModel):
    intent_id: Optional[int] = None
    intent: Optional[str] = None

    payment_status: Optional[str] = None
    account_id: Optional[int] = None

    customer: Optional[str] = None
    supplier: Optional[str] = None

    product: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None

    input_text: Optional[str] = None
    transaction_date: Optional[datetime] = None