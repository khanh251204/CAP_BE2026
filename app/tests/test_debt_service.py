"""
Unit tests cho DebtService — công nợ khách hàng (ghi nợ và thu nợ).

Các case được test:
  1. create_customer_debt — ghi nợ khách hàng mới (tự sinh transaction với payment_status = PENDING)
  2. create_customer_debt — ghi nợ với transaction_id có sẵn
  3. create_customer_debt — validate customer không tồn tại (404) hoặc amount <= 0 (400)
  4. collect_customer_debt — thanh toán một phần (status = PARTIAL)
  5. collect_customer_debt — thanh toán đủ (status = PAID)
  6. collect_customer_debt — thanh toán 2 lần: lần 1 partial, lần 2 paid
  7. collect_customer_debt — thanh toán vượt (HTTPException 400)
  8. collect_customer_debt — thanh toán khi đã paid (HTTPException 400)
  9. get_customer_debts — lấy danh sách nợ khách hàng (direction = RECEIVABLE)
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from datetime import datetime

from fastapi import HTTPException


# ─── helpers để build fake objects ───────────────────────────────────────────

def _make_debt(
    debt_id: int = 1,
    total_debt: float = 1_500_000,
    remaining_debt: float | None = None,
    status: str = "UNPAID",
    payments: list | None = None,
    customer_id: int = 10,
    direction: str = "RECEIVABLE",
    user_id: int = 99,
    transaction_id: int = 7,
):
    debt = MagicMock()
    debt.debt_id = debt_id
    debt.user_id = user_id
    debt.customer_id = customer_id
    debt.supplier_id = None
    debt.direction = direction
    debt.original_amount = Decimal(str(total_debt))
    rem = remaining_debt if remaining_debt is not None else total_debt
    debt.remaining_debt = Decimal(str(rem))
    debt.total_debt = debt.original_amount
    debt.status = status
    debt.payments = payments or []
    debt.transaction_id = transaction_id
    debt.transaction = None
    debt.created_at = datetime(2026, 9, 1)
    debt.updated_at = datetime(2026, 9, 1)
    return debt


def _make_customer(
    customer_id: int = 10,
    user_id: int = 99,
    customer_name: str = "Nguyễn Văn A"
):
    cust = MagicMock()
    cust.customer_id = customer_id
    cust.user_id = user_id
    cust.customer_name = customer_name
    return cust


def _make_account(
    account_id: int = 5,
    balance: float = 2_000_000,
    user_id: int = 99,
    is_active: bool = True,
):
    acc = MagicMock()
    acc.account_id = account_id
    acc.user_id = user_id
    acc.balance = Decimal(str(balance))
    acc.is_active = is_active
    return acc


def _make_intent(intent_id: int = 20, intent_name: str = "thu_no_khach_hang"):
    intent = MagicMock()
    intent.intent_id = intent_id
    intent.intent_name = intent_name
    return intent


def _make_db(debt=None, customer=None, account=None, intent=None):
    """
    Trả về một mock Session đơn giản với chainable `.query(...).options(...).filter(...).first()`.
    """
    db = MagicMock()

    def _query_side_effect(model):
        inner = MagicMock()
        name = getattr(model, "__name__", str(model))

        target = None
        if "Debt" in name:
            target = debt
        elif "Customer" in name:
            target = customer
        elif "Account" in name:
            target = account
        elif "Intent" in name:
            target = intent

        inner.options.return_value = inner
        inner.filter.return_value = inner
        inner.order_by.return_value = inner
        inner.join.return_value = inner
        inner.outerjoin.return_value = inner
        inner.first.return_value = target
        inner.all.return_value = [target] if target else []
        return inner

    db.query.side_effect = _query_side_effect
    db.flush.return_value = None
    db.commit.return_value = None

    def _refresh(obj):
        if hasattr(obj, "payment_id") and getattr(obj, "payment_id") is None:
            obj.payment_id = 200
        if hasattr(obj, "debt_id") and getattr(obj, "debt_id") is None:
            obj.debt_id = 1
    db.refresh.side_effect = _refresh

    return db


# ─── TEST: Tạo công nợ khách hàng (ghi_no_khach_hang) ────────────────────────

class TestCreateCustomerDebt:

    def setup_method(self):
        self.customer = _make_customer(customer_id=10, user_id=99)
        self.intent = _make_intent(intent_id=13, intent_name="ghi_no_khach_hang")
        self.db = _make_db(customer=self.customer, intent=self.intent)

    def test_create_customer_debt_auto_creates_transaction(self):
        from app.services.debt_service import DebtService

        with (
            patch("app.services.debt_service.Transaction") as MockTx,
            patch("app.services.debt_service.Debt") as MockDebt,
        ):
            fake_tx = MagicMock()
            fake_tx.transaction_id = 101
            MockTx.return_value = fake_tx

            fake_debt = MagicMock()
            fake_debt.debt_id = 1
            fake_debt.status = "UNPAID"
            fake_debt.original_amount = Decimal("3000000")
            fake_debt.remaining_debt = Decimal("3000000")
            fake_debt.total_debt = Decimal("3000000")
            MockDebt.return_value = fake_debt

            result = DebtService.create_customer_debt(
                db=self.db,
                user_id=99,
                customer_id=10,
                total_debt=3_000_000,
                transaction_id=None,
                note="Bán nợ 30kg tôm"
            )

        assert result["debt_id"] == 1
        assert result["status"] == "UNPAID"
        assert result["original_amount"] == 3_000_000
        assert result["remaining_debt"] == 3_000_000
        # Kiểm tra Transaction được khởi tạo với payment_status = PENDING theo ERD
        MockTx.assert_called_once()
        _, kwargs = MockTx.call_args
        assert kwargs["payment_status"] == "PENDING"
        assert kwargs["user_id"] == 99
        assert kwargs["customer_id"] == 10

    def test_create_customer_debt_with_existing_transaction(self):
        from app.services.debt_service import DebtService

        with (
            patch("app.services.debt_service.Transaction") as MockTx,
            patch("app.services.debt_service.Debt") as MockDebt,
        ):
            fake_debt = MagicMock()
            fake_debt.debt_id = 2
            fake_debt.status = "UNPAID"
            fake_debt.original_amount = Decimal("1000000")
            fake_debt.remaining_debt = Decimal("1000000")
            fake_debt.total_debt = Decimal("1000000")
            MockDebt.return_value = fake_debt

            result = DebtService.create_customer_debt(
                db=self.db,
                user_id=99,
                customer_id=10,
                total_debt=1_000_000,
                transaction_id=55,
                note="Ghi nợ từ hóa đơn 55"
            )

        assert result["debt_id"] == 2
        # Không được tạo thêm Transaction mới khi đã có transaction_id
        MockTx.assert_not_called()

    def test_create_customer_debt_not_found(self):
        from app.services.debt_service import DebtService
        db_no_cust = _make_db(customer=None)

        with pytest.raises(HTTPException) as exc_info:
            DebtService.create_customer_debt(
                db=db_no_cust,
                user_id=99,
                customer_id=999,
                total_debt=1_000_000
            )
        assert exc_info.value.status_code == 404

    def test_create_customer_debt_invalid_amount(self):
        from app.services.debt_service import DebtService

        with pytest.raises(HTTPException) as exc_info:
            DebtService.create_customer_debt(
                db=self.db,
                user_id=99,
                customer_id=10,
                total_debt=0
            )
        assert exc_info.value.status_code == 400


# ─── TEST: Thu nợ khách hàng một phần (partial) ──────────────────────────────

class TestCollectCustomerDebtPartial:
    """Thu 500,000 / 1,500,000 → còn nợ 1,000,000, status = PARTIAL"""

    def setup_method(self):
        self.debt = _make_debt(total_debt=1_500_000, remaining_debt=1_500_000, status="UNPAID", payments=[])
        self.account = _make_account(balance=2_000_000)
        self.intent = _make_intent(intent_name="thu_no_khach_hang")
        self.db = _make_db(
            debt=self.debt,
            account=self.account,
            intent=self.intent,
        )

    def test_returns_partial_status(self):
        from app.services.debt_service import DebtService

        with (
            patch("app.services.debt_service.Transaction") as MockTx,
            patch("app.services.debt_service.DebtPayment") as MockDP,
        ):
            fake_tx = MagicMock()
            fake_tx.transaction_id = 100
            MockTx.return_value = fake_tx

            fake_dp = MagicMock()
            fake_dp.payment_id = 200
            MockDP.return_value = fake_dp

            result = DebtService.collect_customer_debt(
                db=self.db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=500_000,
                payment_date=datetime(2026, 9, 5),
                note="Thu một phần",
            )

        assert result["debt_status"].upper() == "PARTIAL"
        assert result["remaining_debt"] == pytest.approx(1_000_000, rel=1e-4)
        assert result["debt_id"] == 1
        assert self.debt.status == "PARTIAL"

    def test_account_balance_increased(self):
        from app.services.debt_service import DebtService

        initial_balance = Decimal("2000000")
        self.account.balance = initial_balance

        with (
            patch("app.services.debt_service.Transaction") as MockTx,
            patch("app.services.debt_service.DebtPayment") as MockDP,
        ):
            fake_tx = MagicMock()
            fake_tx.transaction_id = 100
            MockTx.return_value = fake_tx
            MockDP.return_value = MagicMock(payment_id=200)

            DebtService.collect_customer_debt(
                db=self.db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=500_000,
                payment_date=None,
                note=None,
            )

        assert self.account.balance == initial_balance + Decimal("500000")


# ─── TEST: Thu nợ đủ (paid) ──────────────────────────────────────────────────

class TestCollectCustomerDebtFullPayment:
    """Thu đúng 1,500,000 / 1,500,000 → còn nợ 0, status = PAID"""

    def setup_method(self):
        self.debt = _make_debt(total_debt=1_500_000, remaining_debt=1_500_000, status="UNPAID", payments=[])
        self.account = _make_account(balance=5_000_000)
        self.intent = _make_intent()
        self.db = _make_db(
            debt=self.debt,
            account=self.account,
            intent=self.intent,
        )

    def test_returns_paid_status(self):
        from app.services.debt_service import DebtService

        with (
            patch("app.services.debt_service.Transaction") as MockTx,
            patch("app.services.debt_service.DebtPayment") as MockDP,
        ):
            fake_tx = MagicMock()
            fake_tx.transaction_id = 101
            MockTx.return_value = fake_tx
            MockDP.return_value = MagicMock(payment_id=201)

            result = DebtService.collect_customer_debt(
                db=self.db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=1_500_000,
                payment_date=None,
                note="Thanh toán đủ",
            )

        assert result["debt_status"].upper() == "PAID"
        assert result["remaining_debt"] == pytest.approx(0, abs=1)
        assert self.debt.status == "PAID"


# ─── TEST: Thu nợ 2 lần (partial rồi paid) ────────────────────────────────────

class TestCollectCustomerDebtPartialThenFull:
    """
    Nợ 1,500,000:
    Lần 1 đã thu 1,000,000, còn lại 500,000.
    Thu tiếp 500,000 → status = PAID.
    """

    def test_second_payment_closes_debt(self):
        from app.services.debt_service import DebtService

        prev = MagicMock()
        prev.amount = Decimal("1000000")

        debt = _make_debt(
            total_debt=1_500_000,
            remaining_debt=500_000,
            status="PARTIAL",
            payments=[prev],
        )
        account = _make_account()
        intent = _make_intent()
        db = _make_db(debt=debt, account=account, intent=intent)

        with (
            patch("app.services.debt_service.Transaction") as MockTx,
            patch("app.services.debt_service.DebtPayment") as MockDP,
        ):
            MockTx.return_value = MagicMock(transaction_id=102)
            MockDP.return_value = MagicMock(payment_id=202)

            result = DebtService.collect_customer_debt(
                db=db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=500_000,
                payment_date=None,
                note=None,
            )

        assert result["debt_status"].upper() == "PAID"
        assert result["remaining_debt"] == pytest.approx(0, abs=1)
        assert debt.status == "PAID"


# ─── TEST: Thanh toán vượt / lỗi ─────────────────────────────────────────────

class TestCollectCustomerDebtOverpayment:

    def setup_method(self):
        self.debt = _make_debt(total_debt=1_500_000, remaining_debt=1_500_000, status="UNPAID", payments=[])
        self.account = _make_account()
        self.intent = _make_intent()
        self.db = _make_db(
            debt=self.debt,
            account=self.account,
            intent=self.intent,
        )

    def test_raises_400_when_overpay(self):
        from app.services.debt_service import DebtService

        with pytest.raises(HTTPException) as exc_info:
            DebtService.collect_customer_debt(
                db=self.db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=2_000_000,   # vượt số nợ 1,500,000
                payment_date=None,
                note=None,
            )

        assert exc_info.value.status_code == 400
        assert "vượt" in exc_info.value.detail.lower()

    def test_raises_400_when_exceed_remaining_partial(self):
        from app.services.debt_service import DebtService

        debt = _make_debt(
            total_debt=1_500_000,
            remaining_debt=300_000,
            status="PARTIAL",
        )
        db = _make_db(debt=debt, account=self.account, intent=self.intent)

        with pytest.raises(HTTPException) as exc_info:
            DebtService.collect_customer_debt(
                db=db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=400_000,  # vượt 300,000
                payment_date=None,
                note=None,
            )

        assert exc_info.value.status_code == 400

    def test_raises_400_when_debt_already_paid(self):
        from app.services.debt_service import DebtService

        debt = _make_debt(total_debt=1_500_000, remaining_debt=0, status="PAID", payments=[])
        db = _make_db(debt=debt, account=self.account, intent=self.intent)

        with pytest.raises(HTTPException) as exc_info:
            DebtService.collect_customer_debt(
                db=db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=1,
                payment_date=None,
                note=None,
            )

        assert exc_info.value.status_code == 400


# ─── TEST: Thu nợ tự động phân bổ FIFO theo customer_id ──────────────────────

class TestCollectCustomerDebtFIFO:
    """
    Test thu nợ tổng theo khách hàng:
    Tự động phân bổ FIFO (cũ nhất trước) qua các khoản nợ đang mở.
    """

    def test_fifo_allocates_across_two_debts(self):
        from app.services.debt_service import DebtService

        debt1 = _make_debt(debt_id=10, total_debt=500_000, remaining_debt=500_000, status="UNPAID")
        debt2 = _make_debt(debt_id=11, total_debt=1_000_000, remaining_debt=1_000_000, status="UNPAID")
        customer = _make_customer(customer_id=99, user_id=99)
        account = _make_account(account_id=1, balance=5_000_000)

        db = MagicMock()

        with (
            patch("app.repositories.debt_repository.DebtRepository.get_customer_by_id_and_user", return_value=customer),
            patch("app.repositories.debt_repository.DebtRepository.get_open_debts_by_customer_and_user", return_value=[debt1, debt2]),
            patch("app.repositories.debt_repository.DebtRepository.get_account_by_id_and_user", return_value=account),
            patch("app.services.debt_service.Transaction") as MockTx,
            patch("app.services.debt_service.DebtPayment") as MockDP,
        ):
            MockTx.return_value = MagicMock(transaction_id=999)
            MockDP.side_effect = [MagicMock(payment_id=101), MagicMock(payment_id=102)]

            result = DebtService.collect_customer_debt(
                db=db,
                user_id=99,
                account_id=1,
                amount=800_000,
                customer_id=99,
                note="Khách trả gộp 800k",
            )

        # Debt 1 được trả hết 500k -> PAID
        assert debt1.status == "PAID"
        assert debt1.remaining_debt == 0

        # Debt 2 được trả 300k -> PARTIAL, còn lại 700k
        assert debt2.status == "PARTIAL"
        assert debt2.remaining_debt == 700_000

        # Kết quả tổng
        assert result["customer_id"] == 99
        assert result["amount_collected"] == 800_000
        assert result["total_remaining_before"] == 1_500_000
        assert result["total_remaining_after"] == 700_000
        assert len(result["debts"]) == 2
        assert result["debts"][0]["amount_applied"] == 500_000
        assert result["debts"][0]["debt_status"] == "PAID"
        assert result["debts"][1]["amount_applied"] == 300_000
        assert result["debts"][1]["debt_status"] == "PARTIAL"

        # Account balance tăng 800k
        assert account.balance == Decimal("5800000")

    def test_fifo_overpayment_raises_400(self):
        from app.services.debt_service import DebtService

        debt1 = _make_debt(debt_id=10, total_debt=500_000, remaining_debt=500_000, status="UNPAID")
        customer = _make_customer(customer_id=99, user_id=99)
        account = _make_account()
        db = MagicMock()

        with (
            patch("app.repositories.debt_repository.DebtRepository.get_customer_by_id_and_user", return_value=customer),
            patch("app.repositories.debt_repository.DebtRepository.get_open_debts_by_customer_and_user", return_value=[debt1]),
            patch("app.repositories.debt_repository.DebtRepository.get_account_by_id_and_user", return_value=account),
        ):
            with pytest.raises(HTTPException) as exc_info:
                DebtService.collect_customer_debt(
                    db=db,
                    user_id=99,
                    account_id=1,
                    amount=1_000_000,  # nợ chỉ có 500k
                    customer_id=99,
                )

        assert exc_info.value.status_code == 400
        assert "vượt" in exc_info.value.detail.lower()

    def test_fifo_customer_not_found_raises_404(self):
        from app.services.debt_service import DebtService
        db = MagicMock()

        with patch("app.repositories.debt_repository.DebtRepository.get_customer_by_id_and_user", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                DebtService.collect_customer_debt(
                    db=db,
                    user_id=99,
                    account_id=1,
                    amount=500_000,
                    customer_id=999,
                )

        assert exc_info.value.status_code == 404

    def test_fifo_no_open_debts_raises_404(self):
        from app.services.debt_service import DebtService

        customer = _make_customer(customer_id=99, user_id=99)
        db = MagicMock()

        with (
            patch("app.repositories.debt_repository.DebtRepository.get_customer_by_id_and_user", return_value=customer),
            patch("app.repositories.debt_repository.DebtRepository.get_open_debts_by_customer_and_user", return_value=[]),
        ):
            with pytest.raises(HTTPException) as exc_info:
                DebtService.collect_customer_debt(
                    db=db,
                    user_id=99,
                    account_id=1,
                    amount=500_000,
                    customer_id=99,
                )

        assert exc_info.value.status_code == 404
        assert "không có khoản nợ" in exc_info.value.detail.lower()

    def test_missing_both_debt_and_customer_id_raises_400(self):
        from app.services.debt_service import DebtService
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            DebtService.collect_customer_debt(
                db=db,
                user_id=99,
                account_id=1,
                amount=500_000,
                debt_id=None,
                customer_id=None,
            )

        assert exc_info.value.status_code == 400


# ─── TEST: Lấy tất cả công nợ (get_all_debts) ────────────────────────────────

class TestGetAllDebts:

    def test_get_all_debts_without_filter(self):
        from app.services.debt_service import DebtService

        debt1 = _make_debt(debt_id=1, total_debt=500_000, direction="RECEIVABLE")
        debt2 = _make_debt(debt_id=2, total_debt=300_000, direction="PAYABLE")
        db = MagicMock()

        with patch("app.repositories.debt_repository.DebtRepository.get_all_by_user", return_value=[(debt1, "Khách A", None), (debt2, None, "NCC B")]):
            result = DebtService.get_all_debts(user_id=99, db=db)

        assert len(result) == 2
        assert result[0]["debt_id"] == 1
        assert result[0]["customer_name"] == "Khách A"
        assert result[0]["direction"] == "RECEIVABLE"
        assert result[1]["debt_id"] == 2
        assert result[1]["supplier_name"] == "NCC B"
        assert result[1]["direction"] == "PAYABLE"

    def test_get_all_debts_with_direction_and_status_filter(self):
        from app.services.debt_service import DebtService

        debt1 = _make_debt(debt_id=1, total_debt=500_000, status="UNPAID", direction="RECEIVABLE")
        db = MagicMock()

        with patch("app.repositories.debt_repository.DebtRepository.get_all_by_user", return_value=[(debt1, "Khách A", None)]) as mock_repo:
            result = DebtService.get_all_debts(
                user_id=99,
                db=db,
                name="customer",
                direction="RECEIVABLE",
                status="UNPAID",
            )

        mock_repo.assert_called_once_with(
            user_id=99,
            db=db,
            name="customer",
            direction="RECEIVABLE",
            status="UNPAID",
        )
        assert len(result) == 1
        assert result[0]["status"] == "UNPAID"


