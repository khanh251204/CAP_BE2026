import json
from datetime import datetime
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session  
from typing import Optional

from app.configs.database import get_db
from app.configs import database as db_config
from app.configs.jwt import get_current_user_id
from app.services.report_service import ReportService
from app.services.websocket_manager import ws_manager, authenticate_websocket, serialize_ws_data
from app.schemas.report_schema import (
    LiveReportResponse,
    SummaryReportResponse,
    SalesReportResponse,
    PurchaseReportResponse,
    ExpenseReportResponse,
    DebtReportResponse,
    InventoryReportResponse,
    TransactionReportResponse,
    TransactionDetailReportResponse
)

router = APIRouter(tags=["Reporting"])


def extract_period_params(
    period_type: Optional[str] = Query(None, description="DAY, MONTH, QUARTER, YEAR"),
    date: Optional[str] = Query(None, description="YYYY-MM-DD (cho DAY)"),
    year: Optional[int] = Query(None, description="Năm (cho MONTH, QUARTER, YEAR)"),
    month: Optional[int] = Query(None, description="Tháng 1-12 (cho MONTH)"),
    quarter: Optional[int] = Query(None, description="Quý 1-4 (cho QUARTER)"),
    from_date: Optional[str] = Query(None, alias="from", description="Khoảng từ ngày YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="Khoảng đến ngày YYYY-MM-DD")
):
    return {
        "period_type": period_type,
        "date_val": date,
        "year": year,
        "month": month,
        "quarter": quarter,
        "from_date": from_date,
        "to_date": to_date
    }


# =========================================================
# 1. LIVE REPORT (REALTIME)
# =========================================================
@router.get("/reports/live", response_model=LiveReportResponse)
def get_live_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Lấy số liệu realtime tổng hợp của kỳ (DAY, MONTH, QUARTER, YEAR hoặc khoảng ngày).
    Hoàn toàn READ-ONLY, không ghi vào Database.
    """
    return ReportService.get_live_report(db, user_id, params)


# =========================================================
# 2. SUMMARY DASHBOARD REPORT
# =========================================================
@router.get("/reports/summary", response_model=SummaryReportResponse)
def get_summary_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Báo cáo tổng quan Dashboard: Doanh thu, Mua hàng, Chi phí, Lợi nhuận (Thu - Chi), Công nợ.
    """
    return ReportService.get_summary_report(db, user_id, params)


# =========================================================
# 3. SALES REPORT
# =========================================================
@router.get("/reports/sales", response_model=SalesReportResponse)
def get_sales_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Báo cáo bán hàng (intent = 'ban_hang'): tổng bán, số đơn, giá trị trung bình đơn, phân loại thanh toán.
    """
    return ReportService.get_sales_report(db, user_id, params)


# =========================================================
# 4. PURCHASE REPORT
# =========================================================
@router.get("/reports/purchases", response_model=PurchaseReportResponse)
def get_purchase_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Báo cáo nhập mua hàng (intent = 'mua_hang'): tổng mua, số giao dịch, phân rã theo nhà cung cấp.
    """
    return ReportService.get_purchase_report(db, user_id, params)


# =========================================================
# 5. EXPENSE REPORT
# =========================================================
@router.get("/reports/expenses", response_model=ExpenseReportResponse)
def get_expense_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Báo cáo chi phí (intent = 'chi_tien' hoặc category = 'EXPENSE'): phân rã theo từng Category.
    """
    return ReportService.get_expense_report(db, user_id, params)


# =========================================================
# 6. DEBT REPORT
# =========================================================
@router.get("/reports/debts", response_model=DebtReportResponse)
def get_debt_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Báo cáo công nợ thực tế: Phải thu (khách hàng còn nợ) và Phải trả (user còn nợ NCC).
    """
    return ReportService.get_debt_report(db, user_id, params)


# =========================================================
# 7. INVENTORY REPORT
# =========================================================
@router.get("/reports/inventory", response_model=InventoryReportResponse)
def get_inventory_report(
    params: dict = Depends(extract_period_params),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Báo cáo biến động kho: Nhập (IN), Xuất (OUT), Hàng hỏng (DAMAGE), Cân đối kiểm kê (ADJUSTMENT).
    """
    return ReportService.get_inventory_report(db, user_id, params)


# =========================================================
# 8. TRANSACTIONS REPORT (PAGINATED)
# =========================================================
@router.get("/reports/transactions", response_model=TransactionReportResponse)
def get_transactions_report(
    params: dict = Depends(extract_period_params),
    intent: Optional[str] = Query(None, description="Tên intent (vd: ban_hang, mua_hang, chi_tien)"),
    category_id: Optional[int] = Query(None, description="ID danh mục"),
    payment_status: Optional[str] = Query(None, description="PAID, PARTIAL, PENDING"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Lấy danh sách giao dịch có phân trang ở Database (SQL LIMIT/OFFSET).
    """
    return ReportService.get_transactions_report(
        db=db,
        user_id=user_id,
        period_params=params,
        intent_name=intent,
        category_id=category_id,
        payment_status=payment_status,
        page=page,
        page_size=page_size
    )


# =========================================================
# 9. TRANSACTION DETAIL
# =========================================================
@router.get("/reports/transactions/{transaction_id}", response_model=TransactionDetailReportResponse)
def get_transaction_detail(
    transaction_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Xem chi tiết từng dòng hàng hóa và đối tác trong giao dịch.
    """
    return ReportService.get_transaction_detail(db, user_id, transaction_id)


# =========================================================
# 10. WEBSOCKET REALTIME (DASHBOARD & REPORTS)
# =========================================================
async def handle_dashboard_report_ws(
    websocket: WebSocket,
    token: Optional[str] = None,
    access_token: Optional[str] = None,
    period: Optional[str] = "DAY",
    year: Optional[int] = None,
    month: Optional[int] = None,
    quarter: Optional[int] = None,
    date: Optional[str] = None
):
    """
    Xử lý kết nối WebSocket cho cả Dashboard và Báo cáo:
    1. Xác thực linh hoạt: query param (?token=... / ?access_token=...) hoặc header Authorization
    2. Hỗ trợ đầy đủ tham số kỳ: period (DAY/MONTH/QUARTER/YEAR), year, month, quarter, date
    3. Chấp nhận kết nối và gửi ngay snapshot dữ liệu ban đầu
    4. Hỗ trợ nhận message tương tác từ client: ping, get_report, get_dashboard, subscribe, refresh
    5. Tự động nhận push khi có giao dịch mới (REPORT_UPDATED / DASHBOARD_UPDATED)
    """
    auth_token = token or access_token
    if not auth_token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]

    if not auth_token:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "event": "ERROR",
            "message": "Thiếu token xác thực. Hãy truyền ?token=<jwt_token> hoặc header Authorization."
        }, ensure_ascii=False))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        user_id = authenticate_websocket(auth_token)
    except Exception as e:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "event": "ERROR",
            "message": f"Xác thực thất bại: {str(e)}"
        }, ensure_ascii=False))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    current_period = (period or "DAY").upper()
    active_params = {
        "period_type": current_period,
        "year": year,
        "month": month,
        "quarter": quarter,
        "date_val": date
    }
    await ws_manager.connect_report(websocket, user_id, period=current_period)

    # Gửi dữ liệu ban đầu ngay khi kết nối
    try:
        # 1. Thông báo kết nối
        await websocket.send_text(json.dumps({
            "event": "CONNECTED",
            "data": {
                "user_id": user_id,
                "period": current_period,
                "params": active_params,
                "message": "Kết nối thành công tới WebSocket Dashboard & Báo cáo"
            }
        }, ensure_ascii=False))

        # 2. Snapshot dữ liệu realtime theo kỳ yêu cầu
        with db_config.get_db_session() as db:
            live_rep = ReportService.get_live_report(db, user_id, active_params)
            dash_sum = ReportService.get_summary_report(db, user_id, active_params)

        ser_live = serialize_ws_data(live_rep)
        ser_dash = serialize_ws_data(dash_sum)

        # 3. Gửi INITIAL_DATA, REPORT_DATA và DASHBOARD_DATA
        await websocket.send_text(json.dumps({
            "event": "INITIAL_DATA",
            "data": {
                "period": current_period,
                "params": active_params,
                "live_report": ser_live,
                "dashboard": ser_dash
            }
        }, ensure_ascii=False))

        await websocket.send_text(json.dumps({
            "event": "REPORT_DATA",
            "data": ser_live
        }, ensure_ascii=False))

        await websocket.send_text(json.dumps({
            "event": "DASHBOARD_DATA",
            "data": ser_dash
        }, ensure_ascii=False))

    except Exception:
        pass

    # 4. Vòng lặp nhận dữ liệu từ Client
    try:
        while True:
            text = await websocket.receive_text()
            if not text:
                continue

            try:
                msg = json.loads(text)
            except Exception:
                msg = {"action": text.strip().lower()}

            action = str(msg.get("action", "")).lower()

            if action in ("ping", "heartbeat"):
                await websocket.send_text(json.dumps({
                    "event": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))

            elif action in ("get_report", "get_live_report"):
                p_params = {
                    "period_type": str(msg.get("period_type") or msg.get("period") or active_params.get("period_type") or "DAY").upper(),
                    "year": msg.get("year", active_params.get("year")),
                    "month": msg.get("month", active_params.get("month")),
                    "quarter": msg.get("quarter", active_params.get("quarter")),
                    "date_val": msg.get("date") or msg.get("date_val") or active_params.get("date_val")
                }
                with db_config.get_db_session() as db:
                    lr = ReportService.get_live_report(db, user_id, p_params)
                await websocket.send_text(json.dumps({
                    "event": "REPORT_DATA",
                    "data": serialize_ws_data(lr)
                }, ensure_ascii=False))

            elif action in ("get_dashboard", "get_summary"):
                p_params = {
                    "period_type": str(msg.get("period_type") or msg.get("period") or active_params.get("period_type") or "DAY").upper(),
                    "year": msg.get("year", active_params.get("year")),
                    "month": msg.get("month", active_params.get("month")),
                    "quarter": msg.get("quarter", active_params.get("quarter")),
                    "date_val": msg.get("date") or msg.get("date_val") or active_params.get("date_val")
                }
                with db_config.get_db_session() as db:
                    ds = ReportService.get_summary_report(db, user_id, p_params)
                await websocket.send_text(json.dumps({
                    "event": "DASHBOARD_DATA",
                    "data": serialize_ws_data(ds)
                }, ensure_ascii=False))

            elif action == "subscribe":
                if msg.get("period_type") or msg.get("period"):
                    active_params["period_type"] = str(msg.get("period_type") or msg.get("period")).upper()
                if "year" in msg:
                    active_params["year"] = msg["year"]
                if "month" in msg:
                    active_params["month"] = msg["month"]
                if "quarter" in msg:
                    active_params["quarter"] = msg["quarter"]
                if "date" in msg:
                    active_params["date_val"] = msg["date"]

                await websocket.send_text(json.dumps({
                    "event": "SUBSCRIBED",
                    "data": {
                        "period": active_params["period_type"],
                        "params": active_params
                    }
                }, ensure_ascii=False))

            elif action == "refresh":
                with db_config.get_db_session() as db:
                    lr = ReportService.get_live_report(db, user_id, active_params)
                    ds = ReportService.get_summary_report(db, user_id, active_params)
                await websocket.send_text(json.dumps({
                    "event": "INITIAL_DATA",
                    "data": {
                        "params": active_params,
                        "live_report": serialize_ws_data(lr),
                        "dashboard": serialize_ws_data(ds)
                    }
                }, ensure_ascii=False))

    except WebSocketDisconnect:
        ws_manager.disconnect_report(websocket, user_id)
    except Exception:
        ws_manager.disconnect_report(websocket, user_id)


@router.websocket("/ws/reports")
async def ws_reports_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    period: Optional[str] = Query("DAY"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    quarter: Optional[int] = Query(None),
    date: Optional[str] = Query(None)
):
    """WebSocket realtime cho Báo cáo (hỗ trợ period, year, month, quarter, date)."""
    await handle_dashboard_report_ws(
        websocket, token=token, access_token=access_token, period=period,
        year=year, month=month, quarter=quarter, date=date
    )


@router.websocket("/ws/dashboard")
async def ws_dashboard_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    access_token: Optional[str] = Query(None),
    period: Optional[str] = Query("DAY"),
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    quarter: Optional[int] = Query(None),
    date: Optional[str] = Query(None)
):
    """WebSocket realtime cho Dashboard (hỗ trợ period, year, month, quarter, date)."""
    await handle_dashboard_report_ws(
        websocket, token=token, access_token=access_token, period=period,
        year=year, month=month, quarter=quarter, date=date
    )
