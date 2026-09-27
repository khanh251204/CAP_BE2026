from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal


class PeriodInfo(BaseModel):
    type: str
    start: str
    end: str
    is_closed: bool = False
    closing_id: Optional[int] = None


class LiveSummary(BaseModel):
    total_sales: Decimal = Decimal("0.00")
    total_purchase: Decimal = Decimal("0.00")
    total_income: Decimal = Decimal("0.00")
    total_expense: Decimal = Decimal("0.00")
    operating_expense: Decimal = Decimal("0.00")
    purchase_cash_paid: Decimal = Decimal("0.00")
    supplier_debt_paid: Decimal = Decimal("0.00")
    total_cash_outflow: Decimal = Decimal("0.00")
    cogs: Decimal = Decimal("0.00")
    total_receivable: Decimal = Decimal("0.00")
    total_payable: Decimal = Decimal("0.00")
    gross_profit: Optional[Decimal] = Decimal("0.00")
    profit: Optional[Decimal] = Decimal("0.00")
    cash_profit: Optional[Decimal] = Decimal("0.00")


class LiveInventory(BaseModel):
    total_in: Decimal = Decimal("0.00")
    total_out: Decimal = Decimal("0.00")
    total_damage: Decimal = Decimal("0.00")
    total_adjustment: Decimal = Decimal("0.00")


class LiveReportResponse(BaseModel):
    period: PeriodInfo
    business_type: Optional[str] = "RESELLER"
    summary: LiveSummary
    transaction_count: int = 0
    inventory: LiveInventory


class RevenueSummary(BaseModel):
    total: Decimal = Decimal("0.00")


class PurchaseSummary(BaseModel):
    total: Decimal = Decimal("0.00")
    cash_paid: Decimal = Decimal("0.00")


class ExpenseSummary(BaseModel):
    total: Decimal = Decimal("0.00")
    operating: Decimal = Decimal("0.00")
    supplier_debt_paid: Decimal = Decimal("0.00")


class ProfitSummary(BaseModel):
    total: Optional[Decimal] = Decimal("0.00")
    gross_profit: Optional[Decimal] = Decimal("0.00")
    cogs: Optional[Decimal] = Decimal("0.00")
    operating_expense: Optional[Decimal] = Decimal("0.00")
    cash_profit: Optional[Decimal] = Decimal("0.00")


class DebtSummary(BaseModel):
    receivable: Decimal = Decimal("0.00")
    payable: Decimal = Decimal("0.00")


class SummaryReportResponse(BaseModel):
    period: PeriodInfo
    business_type: Optional[str] = "RESELLER"
    revenue: RevenueSummary
    purchase: PurchaseSummary
    expense: ExpenseSummary
    profit: ProfitSummary
    debt: DebtSummary


class ProductSalesDetail(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity_sold: Decimal = Decimal("0.00")
    unit: Optional[str] = None
    revenue: Decimal = Decimal("0.00")
    cost_price: Decimal = Decimal("0.00")
    cogs: Decimal = Decimal("0.00")
    gross_profit: Decimal = Decimal("0.00")


class SalesReportResponse(BaseModel):
    period: PeriodInfo
    total_sales: Decimal = Decimal("0.00")
    cogs: Decimal = Decimal("0.00")
    gross_profit: Decimal = Decimal("0.00")
    transaction_count: int = 0
    average_order_value: Decimal = Decimal("0.00")
    payment_status: Dict[str, Decimal] = Field(default_factory=dict)
    products: List[ProductSalesDetail] = Field(default_factory=list)


class SupplierBreakdown(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    total_amount: Decimal = Decimal("0.00")
    transaction_count: int = 0


class PurchaseReportResponse(BaseModel):
    period: PeriodInfo
    total_purchase: Decimal = Decimal("0.00")
    transaction_count: int = 0
    suppliers: List[SupplierBreakdown] = Field(default_factory=list)


class CategoryBreakdown(BaseModel):
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    amount: Decimal = Decimal("0.00")


class ExpenseReportResponse(BaseModel):
    period: PeriodInfo
    total_expense: Decimal = Decimal("0.00")
    categories: List[CategoryBreakdown] = Field(default_factory=list)


class DebtAmountDetail(BaseModel):
    original_amount: Decimal = Decimal("0.00")
    remaining: Decimal = Decimal("0.00")


class DebtReportResponse(BaseModel):
    period: PeriodInfo
    receivable: DebtAmountDetail
    payable: DebtAmountDetail


class InventoryReportResponse(BaseModel):
    period: PeriodInfo
    total_in: Decimal = Decimal("0.00")
    total_out: Decimal = Decimal("0.00")
    total_damage: Decimal = Decimal("0.00")
    total_adjustment: Decimal = Decimal("0.00")


class TransactionReportItem(BaseModel):
    transaction_id: int
    transaction_date: str
    intent: Optional[str] = None
    total_amount: Decimal = Decimal("0.00")
    payment_status: str
    input_method: Optional[str] = None
    category_name: Optional[str] = None
    customer_name: Optional[str] = None
    supplier_name: Optional[str] = None
    note: Optional[str] = None


class TransactionReportResponse(BaseModel):
    items: List[TransactionReportItem] = Field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0


class TransactionDetailItem(BaseModel):
    detail_id: int
    product_id: int
    product_name: str
    unit: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal


class TransactionDetailReportResponse(BaseModel):
    transaction_id: int
    transaction_date: str
    intent: Optional[str] = None
    total_amount: Decimal
    payment_status: str
    input_method: Optional[str] = None
    note: Optional[str] = None
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    details: List[TransactionDetailItem] = Field(default_factory=list)
