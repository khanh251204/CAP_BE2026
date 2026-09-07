"""
Unit & Integration tests cho MCP Debt Server & Tools (ghi_no_khach_hang, thu_no_khach_hang).

Kiểm tra:
  1. GhiNoKhachHangInput & ThuNoKhachHangInput validation (Pydantic).
  2. ghi_no_khach_hang tool invocation & output schema mapping.
  3. thu_no_khach_hang tool invocation:
     - FIFO mode (customer_id): phân bổ qua các khoản nợ, trả đúng ThuNoKhachHangOutput.
     - Đích danh mode (debt_id): trả đúng ThuNoKhachHangOutput.
     - Lỗi vượt quá tổng nợ (HTTPException 400).
  4. Đăng ký trong FastMCP server & MCP client (list_mcp_tools, find_mcp_server, call_mcp_tool).
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from pydantic import ValidationError

from app.ai.mcp.debt.tools import (
    GhiNoKhachHangInput,
    GhiNoKhachHangOutput,
    ThuNoKhachHangInput,
    ThuNoKhachHangOutput,
    DebtAllocationItem,
)
from app.ai.mcp.debt.server import (
    server as debt_server,
    ghi_no_khach_hang,
    thu_no_khach_hang,
)
from app.ai.mcp.client import (
    list_mcp_tools,
    find_mcp_server,
    call_mcp_tool,
    normalize_mcp_result,
    MCP_SERVERS,
)


class TestDebtPydanticModels:
    """Test validation của các Pydantic model cho MCP Debt tools."""

    def test_ghi_no_khach_hang_input_valid(self):
        data = GhiNoKhachHangInput(
            customer_id=10,
            original_amount=1_500_000.0,
            transaction_id=5,
        )
        assert data.customer_id == 10
        assert data.original_amount == 1_500_000.0
        assert data.transaction_id == 5

    def test_ghi_no_khach_hang_input_without_transaction_id(self):
        data = GhiNoKhachHangInput(
            customer_id=10,
            original_amount=500_000.0,
        )
        assert data.customer_id == 10
        assert data.original_amount == 500_000.0
        assert data.transaction_id is None

    def test_ghi_no_khach_hang_input_invalid_amount(self):
        with pytest.raises(ValidationError):
            GhiNoKhachHangInput(customer_id=10, original_amount=0)

        with pytest.raises(ValidationError):
            GhiNoKhachHangInput(customer_id=10, original_amount=-100)

    def test_thu_no_khach_hang_input_valid_fifo(self):
        inp = ThuNoKhachHangInput(
            account_id=1,
            amount=500_000.0,
            customer_id=10,
        )
        assert inp.account_id == 1
        assert inp.amount == 500_000.0
        assert inp.customer_id == 10
        assert inp.debt_id is None

    def test_thu_no_khach_hang_input_valid_specific_debt(self):
        inp = ThuNoKhachHangInput(
            account_id=1,
            amount=500_000.0,
            debt_id=99,
        )
        assert inp.account_id == 1
        assert inp.amount == 500_000.0
        assert inp.debt_id == 99
        assert inp.customer_id is None

    def test_thu_no_khach_hang_input_neither_debt_nor_customer(self):
        with pytest.raises(ValidationError) as exc_info:
            ThuNoKhachHangInput(
                account_id=1,
                amount=500_000.0,
            )
        assert "Phải có debt_id hoặc customer_id" in str(exc_info.value)

    def test_thu_no_khach_hang_input_both_debt_and_customer(self):
        with pytest.raises(ValidationError) as exc_info:
            ThuNoKhachHangInput(
                account_id=1,
                amount=500_000.0,
                debt_id=1,
                customer_id=2,
            )
        assert "Chỉ được truyền MỘT trong hai" in str(exc_info.value)

    def test_thu_no_khach_hang_input_invalid_amount(self):
        with pytest.raises(ValidationError):
            ThuNoKhachHangInput(
                account_id=1,
                amount=0,
                customer_id=10,
            )


class TestDebtToolsDirect:
    """Test trực tiếp hàm tool ghi_no_khach_hang và thu_no_khach_hang."""

    @patch("app.ai.mcp.debt.server.get_db_session")
    @patch("app.ai.mcp.debt.server.DebtController.create_customer_debt")
    def test_ghi_no_khach_hang_success(self, mock_create, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_create.return_value = {
            "debt_id": 101,
            "status": "UNPAID",
            "total_debt": 2_000_000.0,
            "original_amount": 2_000_000.0,
            "remaining_debt": 2_000_000.0,
        }

        inp = GhiNoKhachHangInput(
            customer_id=10,
            original_amount=2_000_000.0,
        )

        out = ghi_no_khach_hang(input=inp, user_id=99)

        assert isinstance(out, GhiNoKhachHangOutput)
        assert out.debt_id == 101
        assert out.status == "UNPAID"
        assert out.remaining_debt == 2_000_000.0

        mock_create.assert_called_once_with(
            db=mock_db,
            user_id=99,
            customer_id=10,
            total_debt=2_000_000.0,
            transaction_id=None,
        )
        mock_db.close.assert_called_once()

    @patch("app.ai.mcp.debt.server.get_db_session")
    @patch("app.ai.mcp.debt.server.DebtController.collect_customer_debt")
    def test_thu_no_khach_hang_fifo_success(self, mock_collect, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_collect.return_value = {
            "customer_id": 10,
            "payment_id": 201,
            "amount_collected": 15_000_000.0,
            "total_remaining_before": 20_000_000.0,
            "total_remaining_after": 5_000_000.0,
            "remaining_debt": 5_000_000.0,
            "debt_status": "PARTIAL",
            "debts": [
                {
                    "debt_id": 1,
                    "payment_id": 201,
                    "amount_applied": 10_000_000.0,
                    "remaining_debt": 0.0,
                    "debt_status": "PAID",
                },
                {
                    "debt_id": 2,
                    "payment_id": 202,
                    "amount_applied": 5_000_000.0,
                    "remaining_debt": 5_000_000.0,
                    "debt_status": "PARTIAL",
                },
            ],
        }

        inp = ThuNoKhachHangInput(
            account_id=2,
            amount=15_000_000.0,
            customer_id=10,
        )

        out = thu_no_khach_hang(input=inp, user_id=99)

        assert isinstance(out, ThuNoKhachHangOutput)
        assert out.amount_collected == 15_000_000.0
        assert out.customer_id == 10
        assert out.total_remaining_before == 20_000_000.0
        assert out.total_remaining_after == 5_000_000.0
        assert out.debt_id is None
        assert len(out.debts) == 2
        assert out.debts[0].debt_id == 1
        assert out.debts[0].amount_applied == 10_000_000.0
        assert out.debts[0].debt_status == "PAID"
        assert out.debts[1].debt_id == 2
        assert out.debts[1].remaining_debt == 5_000_000.0
        assert out.debts[1].debt_status == "PARTIAL"

        mock_collect.assert_called_once_with(
            db=mock_db,
            user_id=99,
            account_id=2,
            amount=15_000_000.0,
            debt_id=None,
            customer_id=10,
        )
        mock_db.close.assert_called_once()

    @patch("app.ai.mcp.debt.server.get_db_session")
    @patch("app.ai.mcp.debt.server.DebtController.collect_customer_debt")
    def test_thu_no_khach_hang_specific_debt_success(self, mock_collect, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_collect.return_value = {
            "payment_id": 301,
            "debt_id": 45,
            "remaining_debt": 0.0,
            "debt_status": "PAID",
            "amount_collected": 5_000_000.0,
        }

        inp = ThuNoKhachHangInput(
            account_id=2,
            amount=5_000_000.0,
            debt_id=45,
        )

        out = thu_no_khach_hang(input=inp, user_id=99)

        assert isinstance(out, ThuNoKhachHangOutput)
        assert out.amount_collected == 5_000_000.0
        assert out.debt_id == 45
        assert out.remaining_debt == 0.0
        assert out.debt_status == "PAID"
        assert out.customer_id is None

        mock_collect.assert_called_once_with(
            db=mock_db,
            user_id=99,
            account_id=2,
            amount=5_000_000.0,
            debt_id=45,
            customer_id=None,
        )
        mock_db.close.assert_called_once()

    @patch("app.ai.mcp.debt.server.get_db_session")
    @patch("app.ai.mcp.debt.server.DebtController.collect_customer_debt")
    def test_thu_no_khach_hang_exceed_debt_raises(self, mock_collect, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collect.side_effect = HTTPException(
            status_code=400,
            detail="Số tiền thu (3000000) vượt quá tổng số nợ hiện có (1000000).",
        )

        inp = ThuNoKhachHangInput(
            account_id=1,
            amount=3_000_000.0,
            customer_id=10,
        )

        with pytest.raises(HTTPException) as exc_info:
            thu_no_khach_hang(input=inp, user_id=99)

        assert exc_info.value.status_code == 400
        assert "vượt quá tổng số nợ" in exc_info.value.detail
        mock_db.close.assert_called_once()


class TestDebtMcpServerAndClient:
    """Test tích hợp server FastMCP và MCP client."""

    @pytest.mark.anyio
    async def test_server_lists_debt_tools(self):
        tools = await debt_server.list_tools()
        tool_names = [t.name for t in tools]
        assert "ghi_no_khach_hang" in tool_names
        assert "thu_no_khach_hang" in tool_names

    @pytest.mark.anyio
    async def test_client_mcp_servers_registered(self):
        assert "debt" in MCP_SERVERS
        tools = await list_mcp_tools()
        debt_tools = [t for t in tools if t["server"] == "debt"]
        assert len(debt_tools) == 2
        names = [t["name"] for t in debt_tools]
        assert "ghi_no_khach_hang" in names
        assert "thu_no_khach_hang" in names

    @pytest.mark.anyio
    async def test_find_mcp_server(self):
        server_ghi_no = await find_mcp_server("ghi_no_khach_hang")
        assert server_ghi_no is debt_server

        server_thu_no = await find_mcp_server("thu_no_khach_hang")
        assert server_thu_no is debt_server

    @pytest.mark.anyio
    @patch("app.ai.mcp.debt.server.get_db_session")
    @patch("app.ai.mcp.debt.server.DebtController.create_customer_debt")
    async def test_call_mcp_tool_ghi_no(self, mock_create, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_create.return_value = {
            "debt_id": 77,
            "status": "UNPAID",
            "original_amount": 1_200_000.0,
            "remaining_debt": 1_200_000.0,
        }

        result = await call_mcp_tool(
            "ghi_no_khach_hang",
            {
                "input": {
                    "customer_id": 5,
                    "original_amount": 1_200_000.0,
                },
                "user_id": 99,
            },
        )

        normalized = normalize_mcp_result(result)
        assert isinstance(normalized, dict)
        assert normalized["debt_id"] == 77
        assert normalized["status"] == "UNPAID"
        assert normalized["remaining_debt"] == 1_200_000.0

    @pytest.mark.anyio
    @patch("app.ai.mcp.debt.server.get_db_session")
    @patch("app.ai.mcp.debt.server.DebtController.collect_customer_debt")
    async def test_call_mcp_tool_thu_no_fifo(self, mock_collect, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_collect.return_value = {
            "customer_id": 10,
            "payment_id": 501,
            "amount_collected": 5_000_000.0,
            "total_remaining_before": 10_000_000.0,
            "total_remaining_after": 5_000_000.0,
            "remaining_debt": 5_000_000.0,
            "debt_status": "PARTIAL",
            "debts": [
                {
                    "debt_id": 1,
                    "payment_id": 501,
                    "amount_applied": 5_000_000.0,
                    "remaining_debt": 0.0,
                    "debt_status": "PAID",
                }
            ],
        }

        result = await call_mcp_tool(
            "thu_no_khach_hang",
            {
                "input": {
                    "account_id": 1,
                    "amount": 5_000_000.0,
                    "customer_id": 10,
                },
                "user_id": 99,
            },
        )

        normalized = normalize_mcp_result(result)
        assert isinstance(normalized, dict)
        assert normalized["amount_collected"] == 5_000_000.0
        assert normalized["customer_id"] == 10
        assert normalized["total_remaining_after"] == 5_000_000.0
        assert len(normalized["debts"]) == 1
        assert normalized["debts"][0]["debt_id"] == 1


class TestHandleGhiNoKhachHang:
    """Test handler handle_ghi_no_khach_hang với tính năng tự tìm giá qua search_products."""

    @pytest.mark.anyio
    @patch("app.ai.agent.handlers.transaction.get_db_session")
    @patch("app.ai.agent.handlers.transaction.search_product")
    async def test_without_price_calculates_price_times_quantity(self, mock_search, mock_get_db):
        from app.ai.agent.handlers.transaction import handle_ghi_no_khach_hang

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_cust = MagicMock()
        mock_cust.customer_id = 15
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cust

        mock_search.return_value = {
            "success": True,
            "products": [
                {
                    "product_id": 3,
                    "product_name": "Bia Heineken",
                    "default_unit": "thùng",
                    "unit_price": "350000",
                }
            ],
        }

        entities = {
            "customer": "Anh Tuấn",
            "product": "Bia Heineken",
            "quantity": 3,
            "unit": "thùng",
            # Không có price!
        }

        result = await handle_ghi_no_khach_hang(
            intent="ghi_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Ghi nợ cho anh Tuấn 3 thùng bia Heineken",
        )

        assert result["success"] is True
        assert result["status"] == "waiting_confirmation"
        assert result["action"] == "ghi_no_khach_hang"
        payload = result["payload"]
        assert payload["customer_id"] == 15
        assert payload["customer_name"] == "Anh Tuấn"
        assert payload["product_name"] == "Bia Heineken"
        assert payload["unit_price"] == 350000.0
        assert payload["quantity"] == 3.0
        # Số tiền ghi nợ = đơn giá * số lượng = 350.000 * 3 = 1.050.000
        assert payload["original_amount"] == 1_050_000.0
        assert payload["amount"] == 1_050_000.0
        assert "1,050,000đ" in result["message"]
        mock_search.assert_called_once_with(product_name="Bia Heineken", user_id=99)

    @pytest.mark.anyio
    @patch("app.ai.agent.handlers.transaction.search_product")
    async def test_without_price_product_not_found(self, mock_search):
        from app.ai.agent.handlers.transaction import handle_ghi_no_khach_hang

        mock_search.return_value = {
            "success": True,
            "products": [],
        }

        entities = {
            "customer": "Anh Tuấn",
            "product": "Rượu ngoại XYZ",
            "quantity": 2,
        }

        result = await handle_ghi_no_khach_hang(
            intent="ghi_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Anh Tuấn nợ 2 chai rượu ngoại XYZ",
        )

        assert result["success"] is False
        assert result["status"] == "product_not_found"
        assert "Không tìm thấy" in result["message"]

    @pytest.mark.anyio
    @patch("app.ai.agent.handlers.transaction.search_product")
    async def test_without_price_product_has_no_price(self, mock_search):
        from app.ai.agent.handlers.transaction import handle_ghi_no_khach_hang

        mock_search.return_value = {
            "success": True,
            "products": [
                {
                    "product_id": 8,
                    "product_name": "Gạo ST25",
                    "default_unit": "bao",
                    "unit_price": None,
                }
            ],
        }

        entities = {
            "customer": "Chị Hoa",
            "product": "Gạo ST25",
            "quantity": 1,
        }

        result = await handle_ghi_no_khach_hang(
            intent="ghi_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Chị Hoa nợ 1 bao gạo ST25",
        )

        assert result["success"] is False
        assert result["status"] == "price_not_found"
        assert "chưa có giá" in result["message"]

    @pytest.mark.anyio
    @patch("app.ai.agent.handlers.transaction.get_db_session")
    @patch("app.ai.agent.handlers.transaction.search_product")
    async def test_with_price_does_not_need_search(self, mock_search, mock_get_db):
        from app.ai.agent.handlers.transaction import handle_ghi_no_khach_hang

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_cust = MagicMock()
        mock_cust.customer_id = 20
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cust

        entities = {
            "customer": "Chị Lan",
            "price": 2_000_000,
        }

        result = await handle_ghi_no_khach_hang(
            intent="ghi_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Chị Lan mua 2 triệu, ghi nợ giúp anh",
        )

        assert result["success"] is True
        assert result["status"] == "waiting_confirmation"
        assert result["payload"]["original_amount"] == 2_000_000.0
        mock_search.assert_not_called()

    @pytest.mark.anyio
    async def test_missing_customer_returns_need_information(self):
        from app.ai.agent.handlers.transaction import handle_ghi_no_khach_hang

        entities = {
            "product": "bia",
            "quantity": 2,
        }

        result = await handle_ghi_no_khach_hang(
            intent="ghi_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Ghi nợ 2 thùng bia",
        )

        assert result["success"] is False
        assert result["status"] == "need_information"
        assert "customer" in result["missing_fields"]

    @pytest.mark.anyio
    @patch("app.ai.agent.agent_router.handle_ghi_no_khach_hang")
    async def test_agent_router_dispatches_to_handler(self, mock_handler):
        from app.ai.agent.agent_router import AgentRouter

        mock_handler.return_value = {"success": True, "status": "waiting_confirmation"}

        res = await AgentRouter.execute(
            intent="ghi_no_khach_hang",
            user_id=99,
            entities={"customer": "Anh Tuấn", "product": "Bia", "quantity": 2},
            text="Ghi nợ anh Tuấn 2 thùng bia",
        )

        assert res["success"] is True
        mock_handler.assert_called_once_with(
            intent="ghi_no_khach_hang",
            user_id=99,
            entities={"customer": "Anh Tuấn", "product": "Bia", "quantity": 2},
            text="Ghi nợ anh Tuấn 2 thùng bia",
        )


class TestHandleThuNoKhachHang:
    """Test handler handle_thu_no_khach_hang với AccountService tìm account_id theo tên/phương thức thanh toán."""

    @pytest.mark.anyio
    @patch("app.ai.agent.handlers.transaction.get_db_session")
    @patch("app.ai.agent.handlers.transaction.AccountService.get_account_by_name")
    @patch("app.ai.agent.handlers.transaction.DebtRepository.get_open_debts_by_customer_and_user")
    async def test_finds_account_by_name_or_keyword(self, mock_debts, mock_get_acc, mock_get_db):
        from app.ai.agent.handlers.transaction import handle_thu_no_khach_hang

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Mock customer
        mock_cust = MagicMock()
        mock_cust.customer_id = 10
        mock_cust.customer_name = "Chị Lan"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cust

        # Mock account resolved by AccountService (e.g. MB Bank)
        mock_acc = MagicMock()
        mock_acc.account_id = 45
        mock_acc.account_name = "Tài khoản MB Bank"
        mock_get_acc.return_value = mock_acc

        # Mock open debt of 10m
        mock_debt = MagicMock()
        mock_debt.debt_id = 1
        mock_debt.remaining_debt = Decimal("10000000")
        mock_debts.return_value = [mock_debt]

        entities = {
            "customer": "Chị Lan",
            "price": 5_000_000,
            "payment": "chuyển khoản",
        }

        result = await handle_thu_no_khach_hang(
            intent="thu_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Chị Lan vừa chuyển khoản 5 triệu",
        )

        assert result["success"] is True
        assert result["status"] == "waiting_confirmation"
        assert result["action"] == "thu_no_khach_hang"
        payload = result["payload"]
        assert payload["customer_id"] == 10
        assert payload["account_id"] == 45
        assert payload["account_name"] == "Tài khoản MB Bank"
        assert payload["amount"] == 5_000_000.0
        assert "Tài khoản MB Bank" in result["message"]
        mock_get_acc.assert_called_once_with(
            db=mock_db,
            user_id=99,
            account_name="chuyển khoản",
            fallback_to_default=True,
        )

    @pytest.mark.anyio
    @patch("app.ai.agent.handlers.transaction.get_db_session")
    @patch("app.ai.agent.handlers.transaction.AccountService.get_account_by_name")
    @patch("app.ai.agent.handlers.transaction.DebtRepository.get_open_debts_by_customer_and_user")
    async def test_fallback_to_default_account_when_payment_not_specified(self, mock_debts, mock_get_acc, mock_get_db):
        from app.ai.agent.handlers.transaction import handle_thu_no_khach_hang

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_cust = MagicMock()
        mock_cust.customer_id = 20
        mock_cust.customer_name = "Anh Tuấn"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cust

        mock_acc = MagicMock()
        mock_acc.account_id = 1
        mock_acc.account_name = "Tiền mặt"
        mock_get_acc.return_value = mock_acc

        mock_debt = MagicMock()
        mock_debt.debt_id = 2
        mock_debt.remaining_debt = Decimal("5000000")
        mock_debts.return_value = [mock_debt]

        entities = {
            "customer": "Anh Tuấn",
            "price": 2_000_000,
        }

        result = await handle_thu_no_khach_hang(
            intent="thu_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Anh Tuấn trả 2 triệu nợ",
        )

        assert result["success"] is True
        assert result["status"] == "waiting_confirmation"
        assert result["payload"]["account_id"] == 1
        assert result["payload"]["account_name"] == "Tiền mặt"

    @pytest.mark.anyio
    @patch("app.ai.agent.handlers.transaction.get_db_session")
    async def test_customer_not_found_returns_error(self, mock_get_db):
        from app.ai.agent.handlers.transaction import handle_thu_no_khach_hang

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        entities = {
            "customer": "Khách Vãng Lai",
            "price": 1_000_000,
        }

        result = await handle_thu_no_khach_hang(
            intent="thu_no_khach_hang",
            user_id=99,
            entities=entities,
            text="Khách Vãng Lai trả 1 triệu",
        )

        assert result["success"] is False
        assert result["status"] == "customer_not_found"

    @pytest.mark.anyio
    @patch("app.ai.agent.agent_router.handle_thu_no_khach_hang")
    async def test_agent_router_dispatches_to_thu_no_handler(self, mock_handler):
        from app.ai.agent.agent_router import AgentRouter

        mock_handler.return_value = {"success": True, "status": "waiting_confirmation"}

        res = await AgentRouter.execute(
            intent="thu_no_khach_hang",
            user_id=99,
            entities={"customer": "Chị Lan", "price": 5000000},
            text="Chị Lan trả 5 triệu",
        )

        assert res["success"] is True
        mock_handler.assert_called_once_with(
            intent="thu_no_khach_hang",
            user_id=99,
            entities={"customer": "Chị Lan", "price": 5000000},
            text="Chị Lan trả 5 triệu",
        )



