import json
import logging
import asyncio
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Set, Any, Optional
# pyrefly: ignore [missing-import]
from fastapi import WebSocket
# pyrefly: ignore [missing-import]
from starlette.websockets import WebSocketState
from app.configs.jwt import decode_access_token

logger = logging.getLogger(__name__)


def serialize_ws_data(obj: Any) -> Any:
    """
    Chuyển đổi đệ quy các kiểu dữ liệu đặc thù (Decimal, datetime, date)
    sang kiểu chuẩn JSON mà frontend có thể parse trực tiếp.
    """
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_ws_data(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_ws_data(item) for item in obj]
    return obj


class WebSocketManager:
    """
    Quản lý kết nối WebSocket cho các kênh:
    - /ws/reports & /ws/dashboard: Cập nhật realtime số liệu Doanh thu, Mua hàng, Chi phí, Công nợ, Lợi nhuận, Tồn kho.
    - /ws/closing: Tiến trình chốt sổ (CLOSING_*).
    
    Phân lập tuyệt đối theo user_id, không broadcast chéo giữa các tài khoản.
    """

    def __init__(self):
        # user_id -> Set[WebSocket]
        self._report_connections: Dict[int, Set[WebSocket]] = {}
        self._closing_connections: Dict[int, Set[WebSocket]] = {}

    async def connect_report(self, websocket: WebSocket, user_id: int, period: str = "DAY"):
        """Chấp nhận kết nối và thêm vào nhóm theo dõi Dashboard & Report của user_id."""
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()

        if user_id not in self._report_connections:
            self._report_connections[user_id] = set()
        self._report_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected to Dashboard/Report WebSocket. Active sockets: {len(self._report_connections[user_id])}")

    def disconnect_report(self, websocket: WebSocket, user_id: int):
        """Hủy theo dõi socket khỏi nhóm Report & Dashboard."""
        if user_id in self._report_connections:
            self._report_connections[user_id].discard(websocket)
            if not self._report_connections[user_id]:
                del self._report_connections[user_id]
        logger.info(f"User {user_id} disconnected from Dashboard/Report WebSocket")

    async def connect_closing(self, websocket: WebSocket, user_id: int):
        """Chấp nhận kết nối kênh chốt sổ."""
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.accept()

        if user_id not in self._closing_connections:
            self._closing_connections[user_id] = set()
        self._closing_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected to /ws/closing. Active sockets: {len(self._closing_connections[user_id])}")

    def disconnect_closing(self, websocket: WebSocket, user_id: int):
        """Hủy theo dõi socket kênh chốt sổ."""
        if user_id in self._closing_connections:
            self._closing_connections[user_id].discard(websocket)
            if not self._closing_connections[user_id]:
                del self._closing_connections[user_id]
        logger.info(f"User {user_id} disconnected from /ws/closing")

    async def notify_report_updated(
        self,
        user_id: int,
        transaction_id: Optional[int] = None,
        affected: Optional[list] = None,
        affected_periods: Optional[list] = None,
        live_data: Optional[dict] = None,
        db_session: Optional[Any] = None
    ):
        """
        Broadcast sự kiện thay đổi dữ liệu đến tất cả socket đang mở của user_id.
        Tự động đính kèm toàn bộ snapshot mới nhất (live_report & dashboard),
        giúp ứng dụng Frontend có thể hiển thị tức thì mà không cần round-trip gọi lại REST API.
        """
        if user_id not in self._report_connections or not self._report_connections[user_id]:
            return

        live_report = live_data
        dashboard_summary = None

        # Tự động tính toán số liệu realtime nếu chưa được truyền vào
        if not live_report:
            sess_obj = None
            is_own_session = False
            try:
                from app.configs import database as db_config
                from app.services.report_service import ReportService
                if db_session is not None:
                    sess_obj = db_session
                else:
                    sess_obj = db_config.get_db_session()
                    is_own_session = True

                live_report = ReportService.get_live_report(sess_obj, user_id, {"period_type": "DAY"})
                dashboard_summary = ReportService.get_summary_report(sess_obj, user_id, {"period_type": "DAY"})
            except Exception as err:
                logger.warning(f"Could not compute live report for user {user_id}: {err}")
                if is_own_session and sess_obj:
                    try:
                        sess_obj.rollback()
                    except Exception:
                        pass
                live_report = None
                dashboard_summary = None
            finally:
                if is_own_session and sess_obj:
                    try:
                        sess_obj.close()
                    except Exception:
                        pass

        serialized_live = serialize_ws_data(live_report)
        serialized_dashboard = serialize_ws_data(dashboard_summary)

        # 1. Sự kiện REPORT_UPDATED (kèm full snapshot)
        report_payload = {
            "event": "REPORT_UPDATED",
            "data": {
                "transaction_id": transaction_id,
                "report_type": "LIVE",
                "affected_periods": affected_periods or ["DAY", "MONTH", "QUARTER", "YEAR"],
                "affected": affected or ["sales", "purchase", "expense", "profit", "debt", "inventory"],
                "live_report": serialized_live,
                "dashboard": serialized_dashboard
            }
        }
        await self._send_to_user(self._report_connections, user_id, report_payload)

        # 2. Sự kiện DASHBOARD_UPDATED (dành riêng cho component Dashboard trên Mobile/Web)
        dashboard_payload = {
            "event": "DASHBOARD_UPDATED",
            "data": serialized_dashboard or (serialized_live.get("summary") if serialized_live else {})
        }
        await self._send_to_user(self._report_connections, user_id, dashboard_payload)

    async def send_report_update(
        self,
        user_id: int,
        transaction_id: Optional[int] = None,
        affected: Optional[list] = None,
        affected_periods: Optional[list] = None,
        live_data: Optional[dict] = None,
        db_session: Optional[Any] = None
    ):
        """Tên hàm tương thích ngược."""
        await self.notify_report_updated(
            user_id=user_id,
            transaction_id=transaction_id,
            affected=affected,
            affected_periods=affected_periods,
            live_data=live_data,
            db_session=db_session
        )

    async def notify_closing_event(
        self,
        user_id: int,
        event_name: str,
        data: Dict[str, Any]
    ):
        """
        Gửi sự kiện chốt sổ tới người dùng:
        - CLOSING_CONFIRMATION_REQUIRED
        - CLOSING_COMPLETED
        - CLOSING_REPORT_SENT
        - CLOSING_REPORT_FAILED
        """
        payload = {
            "event": event_name,
            "data": serialize_ws_data(data)
        }
        await self._send_to_user(self._closing_connections, user_id, payload)

    async def _send_to_user(
        self,
        connection_map: Dict[int, Set[WebSocket]],
        user_id: int,
        payload: Dict[str, Any]
    ):
        """Gửi chuỗi JSON an toàn đến toàn bộ active websockets của user."""
        if user_id not in connection_map or not connection_map[user_id]:
            return

        dead_connections = set()
        message_str = json.dumps(serialize_ws_data(payload), ensure_ascii=False)

        for ws in list(connection_map[user_id]):
            try:
                await ws.send_text(message_str)
            except Exception as e:
                logger.warning(f"Error sending message to user {user_id}: {e}")
                dead_connections.add(ws)

        for dead_ws in dead_connections:
            connection_map[user_id].discard(dead_ws)
        if user_id in connection_map and not connection_map[user_id]:
            del connection_map[user_id]


# Global singleton instance
ws_manager = WebSocketManager()


def trigger_report_update(
    user_id: int,
    transaction_id: Optional[int] = None,
    affected: Optional[list] = None,
    affected_periods: Optional[list] = None
):
    """
    Helper đồng bộ/bất đồng bộ an toàn: Gọi từ bất kỳ đâu (controller, service, route, sync/async)
    để kích hoạt cập nhật Socket cho Dashboard và Report.
    """
    try:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                ws_manager.notify_report_updated(
                    user_id=user_id,
                    transaction_id=transaction_id,
                    affected=affected,
                    affected_periods=affected_periods
                )
            )
        except RuntimeError:
            asyncio.run(
                ws_manager.notify_report_updated(
                    user_id=user_id,
                    transaction_id=transaction_id,
                    affected=affected,
                    affected_periods=affected_periods
                )
            )
    except Exception as e:
        logger.warning(f"Failed to trigger report socket update for user {user_id}: {e}")


def authenticate_websocket(token: Optional[str]) -> int:
    """
    Xác thực JWT token từ WebSocket query param hoặc Authorization header.
    Trả về user_id (int) nếu hợp lệ.
    """
    if not token:
        raise ValueError("Thiếu authentication token cho WebSocket")
    if token.startswith("Bearer "):
        token = token[7:]
    payload = decode_access_token(token)
    user_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
    if not user_id:
        raise ValueError("Token không chứa user id hợp lệ")
    return int(user_id)
