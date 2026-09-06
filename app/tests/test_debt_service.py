"""
Unit tests cho DebtService — công nợ khách hàng.

Các case được test:
  1. collect_customer_debt — thanh toán một phần (partial)
  2. collect_customer_debt — thanh toán đủ (paid)
  3. collect_customer_debt — thanh toán vượt (400 error)

Sử dụng unittest.mock để mock toàn bộ DB session,
không cần kết nối database thực.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from fastapi import HTTPException


# ─── helpers để build fake objects ───────────────────────────────────────────

def _make_debt(
    debt_id: int = 1,
    total_debt: float = 1_500_000,
    status: str = "open",
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
    debt.total_debt = Decimal(str(total_debt))
    debt.status = status
    debt.payments = payments or []
    debt.transaction_id = transaction_id
    return debt


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


def _make_intent(intent_id: int = 20, intent_name: str = "collect_customer_debt"):
    intent = MagicMock()
    intent.intent_id = intent_id
    intent.intent_name = intent_name
    return intent


def _make_db(debt=None, account=None, intent=None, new_tx_id: int = 100):
    """
    Trả về một mock Session đơn giản với `.query(...).filter(...).first()` chain.
    Thứ tự gọi query: Debt → Account → Intent
    """
    db = MagicMock()

    # Chain: db.query(X).filter(...).first()
    def _query_side_effect(model):
        inner = MagicMock()
        name = getattr(model, "__name__", str(model))

        if "Debt" in name:
            inner.filter.return_value.first.return_value = debt
        elif "Account" in name:
            inner.filter.return_value.first.return_value = account
        elif "Intent" in name:
            inner.filter.return_value.first.return_value = intent
        else:
            inner.filter.return_value.first.return_value = None
        return inner

    db.query.side_effect = _query_side_effect

    # flush() / commit() / refresh() → no-op
    db.flush.return_value = None
    db.commit.return_value = None

    def _refresh(obj):
        # Gán payment_id cho DebtPayment sau khi flush/commit
        if hasattr(obj, "payment_id"):
            obj.payment_id = 200
    db.refresh.side_effect = _refresh

    return db


# ─── TEST: thanh toán một phần (partial) ────────────────────────────────────

class TestCollectCustomerDebtPartial:
    """Thu 500,000 / 1,500,000 → còn nợ 1,000,000, status = partial"""

    def setup_method(self):
        self.debt = _make_debt(total_debt=1_500_000, status="open", payments=[])
        self.account = _make_account(balance=2_000_000)
        self.intent = _make_intent()
        self.db = _make_db(
            debt=self.debt,
            account=self.account,
            intent=self.intent,
        )

    def test_returns_partial_status(self):
        from app.services.debt_service import DebtService

        # Patch Transaction + DebtPayment constructor để không cần real SQLAlchemy
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

        assert result["debt_status"] == "partial"
        assert result["remaining_debt"] == pytest.approx(1_000_000, rel=1e-4)
        assert result["debt_id"] == 1

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

        # balance phải tăng đúng amount
        assert self.account.balance == initial_balance + Decimal("500000")


# ─── TEST: thanh toán đủ (paid) ─────────────────────────────────────────────

class TestCollectCustomerDebtFullPayment:
    """Thu đúng 1,500,000 / 1,500,000 → còn nợ 0, status = paid"""

    def setup_method(self):
        self.debt = _make_debt(total_debt=1_500_000, status="open", payments=[])
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

        assert result["debt_status"] == "paid"
        assert result["remaining_debt"] == pytest.approx(0, abs=1)


class TestCollectCustomerDebtPartialThenFull:
    """
    Thu lần 1: 1,000,000 (partial)
    Thu lần 2: 500,000  (paid)
    """

    def _run(self, previous_paid: float, amount: float) -> dict:
        from app.services.debt_service import DebtService

        prev = MagicMock()
        prev.amount = Decimal(str(previous_paid))

        debt = _make_debt(
            total_debt=1_500_000,
            status="partial",
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

            return DebtService.collect_customer_debt(
                db=db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=amount,
                payment_date=None,
                note=None,
            )

    def test_second_payment_closes_debt(self):
        result = self._run(previous_paid=1_000_000, amount=500_000)
        assert result["debt_status"] == "paid"
        assert result["remaining_debt"] == pytest.approx(0, abs=1)


# ─── TEST: thanh toán vượt (400) ─────────────────────────────────────────────

class TestCollectCustomerDebtOverpayment:
    """Thu 2,000,000 khi chỉ nợ 1,500,000 → HTTPException 400"""

    def setup_method(self):
        self.debt = _make_debt(total_debt=1_500_000, status="open", payments=[])
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
                amount=2_000_000,   # vượt số nợ
                payment_date=None,
                note=None,
            )

        assert exc_info.value.status_code == 400
        assert "vượt" in exc_info.value.detail.lower()

    def test_raises_400_when_exceed_remaining_partial(self):
        """Đã thu 1,200,000 rồi, còn 300,000 — thu thêm 400,000 phải lỗi."""
        from app.services.debt_service import DebtService

        prev = MagicMock()
        prev.amount = Decimal("1200000")
        debt = _make_debt(
            total_debt=1_500_000,
            status="partial",
            payments=[prev],
        )
        db = _make_db(debt=debt, account=self.account, intent=self.intent)

        with pytest.raises(HTTPException) as exc_info:
            DebtService.collect_customer_debt(
                db=db,
                user_id=99,
                debt_id=1,
                account_id=5,
                amount=400_000,
                payment_date=None,
                note=None,
            )

        assert exc_info.value.status_code == 400

    def test_raises_400_when_debt_already_paid(self):
        """Công nợ đã đóng (paid) → từ chối luôn, không cần tính toán."""
        from app.services.debt_service import DebtService

        debt = _make_debt(total_debt=1_500_000, status="paid", payments=[])
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
