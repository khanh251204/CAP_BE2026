"""
Admin Dashboard — Router

Endpoints:
  GET /admin/dashboard                    — Tổng quan hệ thống (System KPIs, Voice AI, Activity, Dataset, Recent Activity, Health)
  GET /admin/dashboard/trends             — Xu hướng hoạt động hệ thống theo ngày (New users, Transactions, Voice)
  GET /admin/dashboard/top-products        — Deprecated: Trả danh sách rỗng (Admin không quản lý chỉ số kinh doanh)
  GET /admin/dashboard/expense-categories — Deprecated: Trả danh sách rỗng (Admin không quản lý cơ cấu chi phí)

Authorization: JWT + quyền admin_* (require_admin_area + require_permission)
"""
from typing import Optional, List
import json
from datetime import datetime
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import require_permission, require_admin_area
from app.services.websocket_manager import ws_manager, authenticate_websocket
from app.schemas.admin_dashboard_schema import (
    AdminDashboardResponse,
    AdminActivityTrendItem,
    AdminDashboardTopProductItem,
    AdminDashboardExpenseCategoryItem,
)
from app.services.admin_dashboard_service import AdminDashboardService


router = APIRouter(
    prefix="/admin/dashboard",
    tags=["Admin - Dashboard"],
    dependencies=[Depends(require_admin_area)]
)


@router.get(
    "",
    response_model=AdminDashboardResponse,
    summary="Xem tổng quan hệ thống Admin Dashboard",
    description=(
        "Cung cấp toàn diện tình trạng vận hành hệ thống VoiceCash: "
        "System KPIs (User, Transaction, Voice), Voice AI Processing & Trend, "
        "User & Transaction Activity, Data Lake/Dataset summary, Recent activity và System health."
    ),
    dependencies=[Depends(require_permission("admin_dashboard:read"))],
)
def get_admin_dashboard(
    period_type: Optional[str] = Query(None, description="Loại kỳ: DAY, WEEK, MONTH, QUARTER, YEAR, CUSTOM"),
    date_from: Optional[str] = Query(None, alias="from", description="Từ ngày (YYYY-MM-DD hoặc ISO 8601)"),
    date_to: Optional[str] = Query(None, alias="to", description="Đến ngày (YYYY-MM-DD hoặc ISO 8601)"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng cụ thể"),
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_dashboard(
        db=db,
        period_type=period_type,
        from_date=date_from,
        to_date=date_to,
        user_id=user_id,
    )


@router.get(
    "/trends",
    response_model=List[AdminActivityTrendItem],
    summary="Xem xu hướng hoạt động hệ thống theo ngày (Admin)",
    description="Thống kê lượng người dùng mới, giao dịch và lượt xử lý giọng nói theo từng ngày trong kỳ.",
    dependencies=[Depends(require_permission("admin_dashboard:read"))],
)
def get_dashboard_trends(
    period_type: Optional[str] = Query(None, description="Loại kỳ: DAY, WEEK, MONTH, QUARTER, YEAR, CUSTOM"),
    date_from: Optional[str] = Query(None, alias="from", description="Từ ngày (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, alias="to", description="Đến ngày (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="Lọc theo ID người dùng cụ thể"),
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_trends(
        db=db,
        period_type=period_type,
        from_date=date_from,
        to_date=date_to,
        user_id=user_id,
    )


@router.get(
    "/top-products",
    response_model=List[AdminDashboardTopProductItem],
    summary="Top sản phẩm (Đã ngừng hỗ trợ trên Admin Dashboard)",
    description="Admin Dashboard tập trung vào chỉ số hệ thống và Voice AI; chỉ số sản phẩm kinh doanh thuộc User Report.",
    dependencies=[Depends(require_permission("admin_dashboard:read"))],
)
def get_top_products(
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_top_products(db=db)


@router.get(
    "/expense-categories",
    response_model=List[AdminDashboardExpenseCategoryItem],
    summary="Cơ cấu chi phí (Đã ngừng hỗ trợ trên Admin Dashboard)",
    description="Admin Dashboard tập trung vào chỉ số hệ thống và Voice AI; cơ cấu chi phí kinh doanh thuộc User Report.",
    dependencies=[Depends(require_permission("admin_dashboard:read"))],
)
def get_expense_categories(
    db: Session = Depends(get_db),
):
    return AdminDashboardService.get_expense_categories(db=db)


ws_admin_router = APIRouter(tags=["Admin - Realtime WebSocket"])


@ws_admin_router.websocket("/ws/admin")
async def admin_realtime_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
):
    """Kênh WebSocket realtime cho giao diện Admin (tự động đẩy sự kiện khi dữ liệu thay đổi)."""
    auth_token = token or access_token
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]

    if not auth_token:
        await websocket.accept()
        await websocket.send_text(json.dumps({"event": "ERROR", "message": "Thiếu token xác thực"}, ensure_ascii=False))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        user_id = authenticate_websocket(auth_token)
    except Exception as exc:
        await websocket.accept()
        await websocket.send_text(json.dumps({"event": "ERROR", "message": f"Xác thực thất bại: {exc}"}, ensure_ascii=False))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect_admin(websocket)
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "event": "CONNECTED",
                    "data": {"user_id": user_id, "timestamp": datetime.utcnow().isoformat()},
                },
                ensure_ascii=False,
            )
        )
        while True:
            raw = await websocket.receive_text()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
                action = str(msg.get("action", "")).lower()
            except Exception:
                action = raw.strip().lower()
            if action in ("ping", "heartbeat"):
                await websocket.send_text(json.dumps({"event": "pong", "timestamp": datetime.utcnow().isoformat()}))
    except WebSocketDisconnect:
        ws_manager.disconnect_admin(websocket)
    except Exception:
        ws_manager.disconnect_admin(websocket)
