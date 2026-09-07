import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.configs.database import Base
from app.models.user_model import User
from app.models.supplier_model import Supplier
from app.models.product_model import Product
from app.models.debt_model import Debt
from app.models.transaction_model import Transaction
from app.models.account_model import Account
from app.models.customer_model import Customer
from app.models.inventory_model import InventoryTransaction
from app.services.inventory_service import InventoryService
from app.ai.agent.handlers.transaction import handle_import, handle_sell


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Seed User
    user = User(
        user_id=1,
        full_name="Test User",
        email="test@example.com",
        password_hash="fakehash",
        role="ADMIN",
    )
    session.add(user)

    from datetime import datetime
    now = datetime.now()

    # Seed Product: Sữa tươi Vinamilk
    product = Product(
        product_id=10,
        user_id=1,
        product_name="Sữa tươi Vinamilk",
        default_unit="lốc",
        unit_price="20000",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(product)

    # Seed Supplier: Vinamilk
    supplier = Supplier(
        supplier_id=5,
        user_id=1,
        supplier_name="Vinamilk",
        created_at=now,
        updated_at=now,
    )
    session.add(supplier)

    # Seed Customer: Anh Nam
    customer = Customer(
        customer_id=20,
        user_id=1,
        customer_name="Anh Nam",
        created_at=now,
        updated_at=now,
    )
    session.add(customer)

    # Seed initial Transaction for stock
    init_tx = Transaction(
        transaction_id=1,
        user_id=1,
        total_amount=Decimal("0"),
        payment_status="PAID",
        transaction_date=now,
        created_at=now,
        updated_at=now,
    )
    session.add(init_tx)
    session.flush()

    # Seed initial inventory: 100 lốc
    inv = InventoryTransaction(
        inventory_transaction_id=1,
        user_id=1,
        product_id=10,
        transaction_id=1,
        inventory_type="IN",
        quantity=Decimal("100"),
        unit="lốc",
        quantity_before=Decimal("0"),
        quantity_after=Decimal("100"),
        created_at=now,
    )
    session.add(inv)

    session.commit()
    yield session
    session.close()


def test_import_goods_unpaid_creates_supplier_debt(db_session, monkeypatch):
    """
    Test scenario: 'Nhập hàng 300 lốc sữa tươi Vinamilk giá 6 triệu chưa trả tiền'
    - quantity: 300
    - price: 20000 (total: 6,000,000)
    - payment_status: 'chưa trả tiền'
    - supplier_name: 'Vinamilk'
    Expect:
    - Debt record created with direction='PAYABLE', original_amount=6000000, remaining_debt=6000000, status='UNPAID'
    - Supplier created or resolved
    """
    service = InventoryService(db_session)

    payload = {
        "product_name": "Sữa tươi Vinamilk",
        "quantity": 300,
        "unit": "lốc",
        "unit_price": 20000,
        "supplier_name": "Vinamilk",
        "payment_status": "chưa trả tiền",
        "input_text": "Nhập hàng 300 lốc sữa tươi Vinamilk giá 6 triệu chưa trả tiền",
    }

    result = service.import_goods(user_id=1, payload=payload)

    assert result["success"] is True
    assert result["total_amount"] == 6000000.0
    assert result["amount_paid"] == 0.0
    assert result["remaining_debt"] == 6000000.0
    assert result["supplier_debt"] == 6000000.0
    assert result["supplier_id"] is not None
    assert result["debt_id"] is not None

    # Check database
    debt = db_session.query(Debt).filter(Debt.debt_id == result["debt_id"]).first()
    assert debt is not None
    assert debt.direction == "PAYABLE"
    assert debt.original_amount == Decimal("6000000.00")
    assert debt.remaining_debt == Decimal("6000000.00")
    assert debt.status == "UNPAID"
    assert debt.supplier_id == result["supplier_id"]

    supplier = db_session.query(Supplier).filter(Supplier.supplier_id == result["supplier_id"]).first()
    assert supplier is not None
    assert supplier.supplier_name == "Vinamilk"

    # Transaction payment status should be PENDING
    tx = db_session.query(Transaction).filter(Transaction.transaction_id == result["transaction_id"]).first()
    assert tx.payment_status == "PENDING"


def test_import_goods_partial_paid_creates_partial_debt(db_session):
    """
    Test scenario: Nhập 6 triệu, trả trước 2 triệu cho Vinamilk
    Expect:
    - amount_paid: 2,000,000
    - remaining_debt: 4,000,000
    - debt status: 'PARTIAL'
    - Transaction payment_status: 'PARTIAL'
    """
    service = InventoryService(db_session)

    payload = {
        "product_name": "Sữa tươi Vinamilk",
        "quantity": 300,
        "unit": "lốc",
        "unit_price": 20000,
        "supplier_name": "Vinamilk",
        "amount_paid": 2000000,
        "payment_status": "PARTIAL",
    }

    result = service.import_goods(user_id=1, payload=payload)

    assert result["success"] is True
    assert result["amount_paid"] == 2000000.0
    assert result["remaining_debt"] == 4000000.0
    assert result["supplier_debt"] == 4000000.0

    debt = db_session.query(Debt).filter(Debt.debt_id == result["debt_id"]).first()
    assert debt is not None
    assert debt.direction == "PAYABLE"
    assert debt.remaining_debt == Decimal("4000000.00")
    assert debt.status == "PARTIAL"


def test_import_goods_with_nonexistent_supplier_returns_error_and_does_not_create_supplier(db_session):
    """
    Test scenario: Nhập hàng với supplier chưa có trong DB
    Expect:
    - KHÔNG được tự động tạo supplier mới
    - Báo lỗi không tìm thấy nhà cung cấp
    - Không lưu Debt rác
    """
    service = InventoryService(db_session)

    supplier_count_before = db_session.query(Supplier).count()

    payload = {
        "product_name": "Sữa tươi Vinamilk",
        "quantity": 100,
        "unit": "lốc",
        "unit_price": 20000,
        "supplier_name": "Nhà cung cấp lạ chưa từng có",
        "payment_status": "chưa thanh toán",
    }

    result = service.import_goods(user_id=1, payload=payload)

    assert result["success"] is False
    assert "Không tìm thấy nhà cung cấp" in result["message"]

    # Đảm bảo không tạo thêm Supplier mới
    supplier_count_after = db_session.query(Supplier).count()
    assert supplier_count_after == supplier_count_before


@pytest.mark.anyio
async def test_handle_import_handler_detects_unpaid_and_supplier(db_session, monkeypatch):
    """
    Test handle_import handler when user says:
    'Nhập hàng 300 lốc sữa tươi Vinamilk giá 6 triệu chưa trả tiền'
    """
    from app.ai.agent.handlers import transaction as tx_handler

    # Mock get_db_session in handler
    monkeypatch.setattr(tx_handler, "get_db_session", lambda: db_session)

    # Mock search_product
    async def mock_search_product(product_name, user_id):
        return {
            "success": True,
            "products": [
                {
                    "product_id": 10,
                    "product_name": "Sữa tươi Vinamilk",
                    "default_unit": "lốc",
                    "unit_price": "20000",
                }
            ]
        }

    monkeypatch.setattr(tx_handler, "search_product", mock_search_product)

    entities = {
        "product": "Sữa tươi Vinamilk",
        "quantity": 300,
        "unit": "lốc",
        "price": 20000,
        "supplier": "Vinamilk",
        "payment": "chưa trả tiền",
    }
    text = "Nhập hàng 300 lốc sữa tươi Vinamilk giá 6 triệu chưa trả tiền"

    res = await handle_import(
        intent="nhap_hang",
        user_id=1,
        entities=entities,
        text=text,
    )

    assert res["success"] is True
    assert res["status"] == "waiting_confirmation"
    assert res["payload"]["product_id"] == 10
    assert res["payload"]["amount_paid"] == 0.0
    assert res["payload"]["supplier_name"] == "Vinamilk"
    assert "Chưa trả tiền - ghi nợ" in res["message"]


@pytest.mark.anyio
async def test_handle_import_handler_supplier_not_found(db_session, monkeypatch):
    """
    Test handle_import when user mentions a supplier NOT in DB:
    Expect status='supplier_not_found', no new supplier created.
    """
    from app.ai.agent.handlers import transaction as tx_handler

    monkeypatch.setattr(tx_handler, "get_db_session", lambda: db_session)

    async def mock_search_product(product_name, user_id):
        return {
            "success": True,
            "products": [
                {
                    "product_id": 10,
                    "product_name": "Sữa tươi Vinamilk",
                    "default_unit": "lốc",
                    "unit_price": "20000",
                }
            ]
        }

    monkeypatch.setattr(tx_handler, "search_product", mock_search_product)

    entities = {
        "product": "Sữa tươi Vinamilk",
        "quantity": 300,
        "unit": "lốc",
        "price": 20000,
        "supplier": "Nhà cung cấp chưa có trong DB",
        "payment": "chưa trả tiền",
    }
    text = "Nhập hàng 300 lốc sữa tươi Vinamilk giá 6 triệu chưa trả tiền từ Nhà cung cấp chưa có trong DB"

    res = await handle_import(
        intent="nhap_hang",
        user_id=1,
        entities=entities,
        text=text,
    )

    assert res["success"] is False
    assert res["status"] == "supplier_not_found"
    assert "Không tìm thấy nhà cung cấp" in res["message"]


# ============================================================
# TESTS CHO BÁN HÀNG (ban_hang) & CÔNG NỢ KHÁCH HÀNG (RECEIVABLE DEBT)
# ============================================================

def test_sell_goods_unpaid_creates_customer_debt(db_session):
    """
    Test scenario: Bán hàng 10 lốc sữa tươi Vinamilk cho Anh Nam chưa trả tiền
    - product: Sữa tươi Vinamilk (id=10, tồn kho 100, giá 20000)
    - quantity: 10
    - customer_name: 'Anh Nam' (id=20)
    - payment_status: 'chưa trả tiền'
    Expect:
    - Debt record created with direction='RECEIVABLE', original_amount=200000, remaining_debt=200000, status='UNPAID'
    - Customer resolved to id=20
    - Transaction created with payment_status='PENDING', customer_id=20
    - Tồn kho giảm từ 100 xuống 90
    """
    service = InventoryService(db_session)

    payload = {
        "product_name": "Sữa tươi Vinamilk",
        "quantity": 10,
        "unit": "lốc",
        "unit_price": 20000,
        "customer_name": "Anh Nam",
        "payment_status": "chưa trả tiền",
        "input_text": "Bán 10 lốc sữa tươi Vinamilk cho Anh Nam chưa trả tiền",
    }

    result = service.sell_goods(user_id=1, payload=payload)

    assert result["success"] is True
    assert result["total_amount"] == 200000.0
    assert result["amount_paid"] == 0.0
    assert result["remaining_debt"] == 200000.0
    assert result["customer_debt"] == 200000.0
    assert result["customer_id"] == 20
    assert result["debt_id"] is not None

    # Kiểm tra database Debt
    debt = db_session.query(Debt).filter(Debt.debt_id == result["debt_id"]).first()
    assert debt is not None
    assert debt.direction == "RECEIVABLE"
    assert debt.original_amount == Decimal("200000.00")
    assert debt.remaining_debt == Decimal("200000.00")
    assert debt.status == "UNPAID"
    assert debt.customer_id == 20

    # Kiểm tra Transaction
    tx = db_session.query(Transaction).filter(Transaction.transaction_id == result["transaction_id"]).first()
    assert tx is not None
    assert tx.customer_id == 20
    assert tx.payment_status == "PENDING"

    # Kiểm tra tồn kho sau khi bán: 100 - 10 = 90
    latest_inv = (
        db_session.query(InventoryTransaction)
        .filter(InventoryTransaction.product_id == 10)
        .order_by(InventoryTransaction.inventory_transaction_id.desc())
        .first()
    )
    assert latest_inv.quantity_after == Decimal("90")


def test_sell_goods_partial_paid_creates_partial_debt(db_session):
    """
    Test scenario: Bán 10 lốc giá 200k, Anh Nam trả trước 50k
    Expect:
    - amount_paid: 50,000
    - remaining_debt: 150,000
    - debt status: 'PARTIAL'
    - transaction payment_status: 'PARTIAL'
    """
    service = InventoryService(db_session)

    payload = {
        "product_name": "Sữa tươi Vinamilk",
        "quantity": 10,
        "unit": "lốc",
        "unit_price": 20000,
        "customer_name": "Anh Nam",
        "amount_paid": 50000,
        "payment_status": "PARTIAL",
    }

    result = service.sell_goods(user_id=1, payload=payload)

    assert result["success"] is True
    assert result["amount_paid"] == 50000.0
    assert result["remaining_debt"] == 150000.0
    assert result["customer_debt"] == 150000.0

    debt = db_session.query(Debt).filter(Debt.debt_id == result["debt_id"]).first()
    assert debt is not None
    assert debt.direction == "RECEIVABLE"
    assert debt.remaining_debt == Decimal("150000.00")
    assert debt.status == "PARTIAL"


def test_sell_goods_with_nonexistent_customer_returns_error_and_does_not_create_customer(db_session):
    """
    Test scenario: Bán hàng cho khách hàng chưa có trong DB
    Expect:
    - KHÔNG được tự động tạo Customer mới
    - Báo lỗi không tìm thấy khách hàng
    - Không phát sinh Debt hay Transaction
    """
    service = InventoryService(db_session)

    customer_count_before = db_session.query(Customer).count()

    payload = {
        "product_name": "Sữa tươi Vinamilk",
        "quantity": 5,
        "unit": "lốc",
        "unit_price": 20000,
        "customer_name": "Khách lạ chưa từng có",
        "payment_status": "nợ",
    }

    result = service.sell_goods(user_id=1, payload=payload)

    assert result["success"] is False
    assert "Không tìm thấy khách hàng" in result["message"]

    # Đảm bảo không tạo Customer mới
    customer_count_after = db_session.query(Customer).count()
    assert customer_count_after == customer_count_before


def test_sell_goods_unpaid_without_customer_returns_error(db_session):
    """
    Test scenario: Bán hàng ghi nợ nhưng không có thông tin khách hàng
    Expect:
    - Báo lỗi cần có thông tin khách hàng để ghi nợ
    """
    service = InventoryService(db_session)

    payload = {
        "product_name": "Sữa tươi Vinamilk",
        "quantity": 5,
        "unit": "lốc",
        "unit_price": 20000,
        "payment_status": "ghi nợ",
    }

    result = service.sell_goods(user_id=1, payload=payload)

    assert result["success"] is False
    assert "cần có thông tin Khách hàng để ghi nợ" in result["message"]


@pytest.mark.anyio
async def test_handle_sell_handler_detects_unpaid_and_resolves_customer(db_session, monkeypatch):
    """
    Test handle_sell handler when user says:
    'Bán 5 lốc sữa tươi Vinamilk cho Anh Nam chưa trả tiền'
    Expect:
    - Resolves customer_id=20 from Customer table
    - Sets amount_paid=0.0
    - Waiting confirmation with debt note
    """
    from app.ai.agent.handlers import transaction as tx_handler

    monkeypatch.setattr(tx_handler, "get_db_session", lambda: db_session)

    async def mock_get_stock(product_name, user_id):
        return {
            "success": True,
            "product_id": 10,
            "product_name": "Sữa tươi Vinamilk",
            "quantity": 100.0,
            "unit_price": 20000.0,
            "default_unit": "lốc",
        }

    monkeypatch.setattr(tx_handler, "get_stock", mock_get_stock)

    entities = {
        "product": "Sữa tươi Vinamilk",
        "quantity": 5,
        "unit": "lốc",
        "price": 20000,
        "customer": "Anh Nam",
        "payment": "chưa trả tiền",
    }
    text = "Bán 5 lốc sữa tươi Vinamilk cho Anh Nam chưa trả tiền"

    res = await handle_sell(
        intent="ban_hang",
        user_id=1,
        entities=entities,
        text=text,
    )

    assert res["success"] is True
    assert res["status"] == "waiting_confirmation"
    assert res["payload"]["customer_id"] == 20
    assert res["payload"]["customer_name"] == "Anh Nam"
    assert res["payload"]["amount_paid"] == 0.0
    assert "Chưa thanh toán - ghi nợ cho khách 'Anh Nam'" in res["message"]


@pytest.mark.anyio
async def test_handle_sell_handler_customer_not_found(db_session, monkeypatch):
    """
    Test handle_sell handler when user mentions a customer NOT in DB:
    Expect status='customer_not_found', NO new customer created in DB.
    """
    from app.ai.agent.handlers import transaction as tx_handler

    monkeypatch.setattr(tx_handler, "get_db_session", lambda: db_session)

    async def mock_get_stock(product_name, user_id):
        return {
            "success": True,
            "product_id": 10,
            "product_name": "Sữa tươi Vinamilk",
            "quantity": 100.0,
            "unit_price": 20000.0,
            "default_unit": "lốc",
        }

    monkeypatch.setattr(tx_handler, "get_stock", mock_get_stock)

    customer_count_before = db_session.query(Customer).count()

    entities = {
        "product": "Sữa tươi Vinamilk",
        "quantity": 5,
        "unit": "lốc",
        "price": 20000,
        "customer": "Khách Vãng Lai Chưa Có",
        "payment": "chưa trả tiền",
    }
    text = "Bán 5 lốc sữa tươi Vinamilk cho Khách Vãng Lai Chưa Có chưa trả tiền"

    res = await handle_sell(
        intent="ban_hang",
        user_id=1,
        entities=entities,
        text=text,
    )

    assert res["success"] is False
    assert res["status"] == "customer_not_found"
    assert "Không tìm thấy khách hàng" in res["message"]

    # Đảm bảo không tạo mới Customer trong DB
    customer_count_after = db_session.query(Customer).count()
    assert customer_count_after == customer_count_before


@pytest.mark.anyio
async def test_handle_sell_handler_unpaid_missing_customer_requires_customer(db_session, monkeypatch):
    """
    Test handle_sell handler when user says:
    'Bán 5 lốc sữa tươi Vinamilk ghi nợ' (không có tên khách hàng)
    Expect status='need_information', missing_fields=['customer'].
    """
    from app.ai.agent.handlers import transaction as tx_handler

    monkeypatch.setattr(tx_handler, "get_db_session", lambda: db_session)

    async def mock_get_stock(product_name, user_id):
        return {
            "success": True,
            "product_id": 10,
            "product_name": "Sữa tươi Vinamilk",
            "quantity": 100.0,
            "unit_price": 20000.0,
            "default_unit": "lốc",
        }

    monkeypatch.setattr(tx_handler, "get_stock", mock_get_stock)

    entities = {
        "product": "Sữa tươi Vinamilk",
        "quantity": 5,
        "unit": "lốc",
        "price": 20000,
        "payment": "ghi nợ",
    }
    text = "Bán 5 lốc sữa tươi Vinamilk ghi nợ"

    res = await handle_sell(
        intent="ban_hang",
        user_id=1,
        entities=entities,
        text=text,
    )

    assert res["success"] is False
    assert res["status"] == "need_information"
    assert "customer" in res["missing_fields"]

