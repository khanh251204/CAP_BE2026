from typing import Any

from app.ai.intents.nhap_hang.handler import NhapHangHandler
from app.ai.intents.mua_hang.handler import MuaHangHandler
from app.ai.intents.ban_hang.handler import BanHangHandler
from app.ai.intents.khach_ghi_no.handler import KhachGhiNoHandler
from app.ai.intents.thu_no_khach.handler import ThuNoKhachHandler
from app.ai.intents.ghi_no_nha_cung_cap.handler import GhiNoNhaCungCapHandler
from app.ai.intents.tra_no_nha_cung_cap.handler import TraNoNhaCungCapHandler
from app.ai.intents.them_san_pham.handler import ThemSanPhamHandler
from app.ai.intents.sua_san_pham.handler import SuaSanPhamHandler
from app.ai.intents.xoa_san_pham.handler import XoaSanPhamHandler
from app.ai.intents.kiem_kho.handler import KiemKhoHandler
from app.ai.intents.tim_san_pham.handler import TimSanPhamHandler
from app.ai.intents.chi_phi.handler import ChiPhiHandler
from app.ai.intents.hang_hong.handler import HangHongHandler
from app.ai.intents.bao_cao.handler import BaoCaoHandler
from app.ai.intents.nhap_kho.handler import NhapKhoHandler
from app.ai.intents.xuat_kho.handler import XuatKhoHandler

_nhap_hang = NhapHangHandler()
_mua_hang = MuaHangHandler()
_ban_hang = BanHangHandler()
_nhap_kho = NhapKhoHandler()
_xuat_kho = XuatKhoHandler()
_khach_ghi_no = KhachGhiNoHandler()
_thu_no_khach = ThuNoKhachHandler()
_ghi_no_ncc = GhiNoNhaCungCapHandler()
_tra_no_ncc = TraNoNhaCungCapHandler()
_them_sp = ThemSanPhamHandler()
_sua_sp = SuaSanPhamHandler()
_xoa_sp = XoaSanPhamHandler()
_kiem_kho = KiemKhoHandler()
_tim_sp = TimSanPhamHandler()
_chi_phi = ChiPhiHandler()
_hang_hong = HangHongHandler()
_bao_cao = BaoCaoHandler()

HANDLERS = {
    "mua_hang": _mua_hang,
    "nhap_hang": _nhap_hang,
    "nhap_kho": _nhap_kho,
    "xuat_kho": _xuat_kho,
    "ban_hang": _ban_hang,
    "khach_ghi_no": _khach_ghi_no,
    "ghi_no_khach_hang": _khach_ghi_no,
    "thu_no_khach": _thu_no_khach,
    "thu_no_khach_hang": _thu_no_khach,
    "ghi_no_nha_cung_cap": _ghi_no_ncc,
    "ncc_ghi_no": _ghi_no_ncc,
    "tra_no_nha_cung_cap": _tra_no_ncc,
    "thu_no_nha_cung_cap": _tra_no_ncc,
    "tra_no_ncc": _tra_no_ncc,
    "them_san_pham": _them_sp,
    "sua_san_pham": _sua_sp,
    "xoa_san_pham": _xoa_sp,
    "kiem_kho": _kiem_kho,
    "tim_san_pham": _tim_sp,
    "xem_san_pham": _tim_sp,
    "chi_phi": _chi_phi,
    "hang_hong": _hang_hong,
    "bao_cao": _bao_cao,
}


class IntentRouter:
    """
    Router chỉ chịu trách nhiệm định tuyến intent -> handler.
    Không chứa validation, payload building, MCP, hay database logic.
    """

    @staticmethod
    def get_handler(intent: str):
        return HANDLERS.get(intent)

    @staticmethod
    async def route(
        intent: str,
        user_id: int,
        entities: dict[str, Any],
        text: str
    ) -> dict:
        handler = IntentRouter.get_handler(intent)
        if not handler:
            return {
                "success": False,
                "status": "error",
                "intent": intent,
                "message": f"Intent chưa được hỗ trợ: {intent}"
            }
        return await handler.handle(
            user_id=user_id,
            entities=entities,
            text=text,
            intent=intent
        )


# ============================================================
# AGENT ROUTER (TƯƠNG THÍCH NGƯỢC VỚI CÁC TEST CASES)
# ============================================================

from app.ai.core.handlers import (
    handle_ghi_no_khach_hang,
    handle_thu_no_khach_hang,
    handle_ghi_no_nha_cung_cap,
    handle_thu_no_nha_cung_cap,
    handle_sell,
    handle_import,
)


class AgentRouter:

    @staticmethod
    def get_tool(intent: str) -> str | None:
        return IntentRouter.get_handler(intent)

    @staticmethod
    async def execute(
        intent: str,
        user_id: int,
        entities: dict[str, Any],
        text: str
    ) -> dict:
        if intent == "ban_hang":
            return await handle_sell(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent == "nhap_hang":
            return await handle_import(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent in ("ghi_no_khach_hang", "khach_ghi_no"):
            return await handle_ghi_no_khach_hang(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent in ("thu_no_khach_hang", "thu_no_khach"):
            return await handle_thu_no_khach_hang(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent in ("ghi_no_nha_cung_cap", "ncc_ghi_no"):
            return await handle_ghi_no_nha_cung_cap(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        if intent in ("thu_no_nha_cung_cap", "tra_no_nha_cung_cap", "tra_no_ncc"):
            return await handle_thu_no_nha_cung_cap(
                intent=intent,
                user_id=user_id,
                entities=entities,
                text=text
            )

        return await IntentRouter.route(
            intent=intent,
            user_id=user_id,
            entities=entities,
            text=text
        )
