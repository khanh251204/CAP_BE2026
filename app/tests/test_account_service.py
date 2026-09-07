"""
Unit tests cho AccountService & AccountRepository — Tìm kiếm account_id theo tên.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.models.account_model import Account
from app.services.account_service import AccountService
from app.repositories.account_repository import AccountRepository


def _make_fake_account(
    account_id: int = 1,
    user_id: int = 99,
    account_name: str = "Tiền mặt",
    account_type: str = "CASH",
    balance: float = 5_000_000.0,
    currency: str = "VND",
    is_active: bool = True,
):
    acc = MagicMock(spec=Account)
    acc.account_id = account_id
    acc.user_id = user_id
    acc.account_name = account_name
    acc.account_type = account_type
    acc.balance = Decimal(str(balance))
    acc.currency = currency
    acc.is_active = is_active
    return acc


class TestAccountServiceFindIdByName:
    """Kiểm tra tìm account_id theo tên."""

    def test_get_account_id_by_exact_name(self):
        fake_acc = _make_fake_account(account_id=10, account_name="Tiền mặt", account_type="CASH")
        db = MagicMock()

        with patch("app.repositories.account_repository.AccountRepository.get_by_exact_name", return_value=fake_acc) as mock_exact:
            acc_id = AccountService.get_account_id_by_name(
                db=db,
                user_id=99,
                account_name="tiền mặt",
            )

            assert acc_id == 10
            mock_exact.assert_called_once_with(db=db, user_id=99, name="tiền mặt")

    def test_get_account_id_by_partial_name(self):
        fake_acc = _make_fake_account(account_id=20, account_name="Tài khoản MB Bank", account_type="BANK")
        db = MagicMock()

        with patch("app.repositories.account_repository.AccountRepository.get_by_exact_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_partial_name", return_value=fake_acc) as mock_partial:

            acc_id = AccountService.get_account_id_by_name(
                db=db,
                user_id=99,
                account_name="MB",
            )

            assert acc_id == 20
            mock_partial.assert_called_once_with(db=db, user_id=99, name="mb")

    def test_get_account_id_by_alias_keyword_bank(self):
        fake_acc = _make_fake_account(account_id=30, account_name="Ngân hàng Vietcombank", account_type="BANK")
        db = MagicMock()

        # Không tìm thấy exact hay partial với từ "chuyển khoản", nhưng alias map sang BANK
        with patch("app.repositories.account_repository.AccountRepository.get_by_exact_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_partial_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_type", return_value=fake_acc) as mock_type:

            acc_id = AccountService.get_account_id_by_name(
                db=db,
                user_id=99,
                account_name="chuyển khoản",
            )

            assert acc_id == 30
            mock_type.assert_called_once_with(db=db, user_id=99, account_type="BANK")

    def test_get_account_id_by_alias_keyword_momo(self):
        fake_acc = _make_fake_account(account_id=40, account_name="Ví MoMo", account_type="E-WALLET")
        db = MagicMock()

        with patch("app.repositories.account_repository.AccountRepository.get_by_exact_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_partial_name", return_value=fake_acc):

            acc_id = AccountService.get_account_id_by_name(
                db=db,
                user_id=99,
                account_name="momo",
            )

            assert acc_id == 40

    def test_get_account_id_not_found_returns_none(self):
        db = MagicMock()

        with patch("app.repositories.account_repository.AccountRepository.get_by_exact_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_partial_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_type", return_value=None):

            acc_id = AccountService.get_account_id_by_name(
                db=db,
                user_id=99,
                account_name="Tài khoản lạ không tồn tại",
                fallback_to_default=False,
            )

            assert acc_id is None

    def test_get_account_id_fallback_to_default(self):
        fake_default = _make_fake_account(account_id=1, account_name="Tiền mặt", account_type="CASH")
        db = MagicMock()

        with patch("app.repositories.account_repository.AccountRepository.get_by_exact_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_partial_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.get_by_type", return_value=fake_default):

            acc_id = AccountService.get_account_id_by_name(
                db=db,
                user_id=99,
                account_name="không tìm thấy",
                fallback_to_default=True,
            )

            assert acc_id == 1

    def test_get_account_id_empty_input_without_fallback(self):
        db = MagicMock()
        assert AccountService.get_account_id_by_name(db=db, user_id=99, account_name="", fallback_to_default=False) is None
        assert AccountService.get_account_id_by_name(db=db, user_id=99, account_name=None, fallback_to_default=False) is None


class TestAccountServiceOtherMethods:
    """Kiểm tra các method hỗ trợ khác trong AccountService."""

    def test_search_accounts(self):
        db = MagicMock()
        acc1 = _make_fake_account(account_id=1, account_name="Tiền mặt", balance=100000)
        acc2 = _make_fake_account(account_id=2, account_name="Ví MoMo", balance=500000)

        with patch("app.repositories.account_repository.AccountRepository.search_by_name", return_value=[acc1, acc2]):
            results = AccountService.search_accounts(db=db, user_id=99, name="tiền")
            assert len(results) == 2
            assert results[0]["account_id"] == 1
            assert results[0]["balance"] == 100000.0
            assert results[1]["account_id"] == 2

    def test_get_or_create_account_existing(self):
        fake_acc = _make_fake_account(account_id=5, account_name="Tiền mặt")
        db = MagicMock()

        with patch.object(AccountService, "get_account_by_name", return_value=fake_acc):
            acc = AccountService.get_or_create_account_by_name(
                db=db,
                user_id=99,
                account_name="Tiền mặt",
            )
            assert acc.account_id == 5

    def test_get_or_create_account_creates_new(self):
        db = MagicMock()
        new_acc = _make_fake_account(account_id=88, account_name="Tài khoản Techcombank", account_type="BANK")

        with patch.object(AccountService, "get_account_by_name", return_value=None), \
             patch("app.repositories.account_repository.AccountRepository.create", return_value=new_acc) as mock_create:

            acc = AccountService.get_or_create_account_by_name(
                db=db,
                user_id=99,
                account_name="Tài khoản Techcombank",
                account_type="BANK",
            )
            assert acc.account_id == 88
            mock_create.assert_called_once_with(
                db=db,
                user_id=99,
                account_name="Tài khoản Techcombank",
                account_type="BANK",
                balance=0.0,
                currency="VND",
            )
