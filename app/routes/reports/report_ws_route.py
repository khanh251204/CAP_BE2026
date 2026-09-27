import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.configs import database as db_config
from app.services.report_service import ReportService
from app.services.websocket_manager import ws_manager, authenticate_websocket, serialize_ws_data

ws_router = APIRouter(tags=["Reporting WebSocket"])


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

    try:
        await websocket.send_text(json.dumps({
            "event": "CONNECTED",
            "data": {
                "user_id": user_id,
                "period": current_period,
                "params": active_params,
                "message": "Kết nối thành công tới WebSocket Dashboard & Báo cáo"
            }
        }, ensure_ascii=False))

        with db_config.get_db_session() as db:
            live_rep = ReportService.get_live_report(db, user_id, active_params)
            dash_sum = ReportService.get_summary_report(db, user_id, active_params)

        ser_live = serialize_ws_data(live_rep)
        ser_dash = serialize_ws_data(dash_sum)

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


@ws_router.websocket("/ws/reports")
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
    await handle_dashboard_report_ws(
        websocket, token=token, access_token=access_token, period=period,
        year=year, month=month, quarter=quarter, date=date
    )


@ws_router.websocket("/ws/dashboard")
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
    await handle_dashboard_report_ws(
        websocket, token=token, access_token=access_token, period=period,
        year=year, month=month, quarter=quarter, date=date
    )
