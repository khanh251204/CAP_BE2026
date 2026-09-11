import logging
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
from typing import Optional, List

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id
from app.services.closing_service import ClosingService
from app.services.websocket_manager import ws_manager, authenticate_websocket
from app.schemas.closing_schema import (
    ClosingPeriodRequest,
    ClosingPreviewResponse,
    ClosingPeriodResponse,
    ClosingPeriodListResponse,
    ClosingTransactionsResponse,
    ClosingReopenRequest,
    ClosingSettingResponse,
    ClosingSettingUpdateRequest,
    ClosingReportResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Closing Periods"])


# =========================================================
# 1. PREVIEW CLOSING PERIOD
# =========================================================
@router.post("/closing-periods/preview", response_model=ClosingPreviewResponse)
def preview_closing_period(
    data: ClosingPeriodRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    POST /closing-periods/preview:
    Xem trước số liệu tài chính trước khi xác nhận chốt sổ (không ghi vào DB).
    """
    params = {
        "period_type": data.period_type,
        "date_val": data.date,
        "year": data.year,
        "month": data.month,
        "quarter": data.quarter
    }
    return ClosingService.preview_closing(db, user_id, params)


# =========================================================
# 2. CREATE CLOSING PERIOD (CHỐT SỔ)
# =========================================================
@router.post("/closing-periods", response_model=ClosingPeriodResponse, status_code=status.HTTP_201_CREATED)
def create_closing_period(
    data: ClosingPeriodRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    POST /closing-periods:
    Thực hiện chốt sổ chính thức, ghi snapshot vào closing_period và liên kết closing_transaction.
    """
    params = {
        "period_type": data.period_type,
        "date_val": data.date,
        "year": data.year,
        "month": data.month,
        "quarter": data.quarter
    }
    try:
        closing = ClosingService.create_closing(db, user_id, params, note=data.note)
        return ClosingService.get_closing_period_detail(db, user_id, closing.closing_id)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Lỗi khi thực hiện chốt sổ cho user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi thực hiện chốt sổ: {str(e)}"
        )


# =========================================================
# 3. LIST CLOSING PERIODS (SNAPSHOT HISTORY)
# =========================================================
@router.get("/closing-periods", response_model=ClosingPeriodListResponse)
def get_closing_periods(
    status_val: Optional[str] = Query(None, alias="status", description="OPEN hoặc CLOSED"),
    period_type: Optional[str] = Query(None, description="DAY, MONTH, QUARTER, YEAR"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    GET /closing-periods:
    Lấy danh sách các kỳ đã chốt trong lịch sử.
    """
    return ClosingService.get_closing_periods(
        db=db,
        user_id=user_id,
        period_type=period_type,
        status_val=status_val,
        page=page,
        page_size=page_size
    )


# =========================================================
# 4. CLOSING PERIOD DETAIL
# =========================================================
@router.get("/closing-periods/{closing_id}", response_model=ClosingPeriodResponse)
def get_closing_period_detail(
    closing_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    GET /closing-periods/{id}:
    Xem chi tiết số liệu snapshot của một kỳ đã chốt.
    """
    return ClosingService.get_closing_period_detail(db, user_id, closing_id)


# =========================================================
# 5. CLOSING TRANSACTIONS (DRILL-DOWN)
# =========================================================
@router.get("/closing-periods/{closing_id}/transactions", response_model=ClosingTransactionsResponse)
def get_closing_transactions(
    closing_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    GET /closing-periods/{id}/transactions:
    Drill-down: Danh sách chi tiết các giao dịch thuộc về kỳ chốt này.
    """
    return ClosingService.get_closing_transactions(
        db=db,
        user_id=user_id,
        closing_id=closing_id,
        page=page,
        page_size=page_size
    )


# =========================================================
# 6. REOPEN CLOSING PERIOD
# =========================================================
@router.patch("/closing-periods/{closing_id}/reopen", response_model=ClosingPeriodResponse)
def reopen_closing_period(
    closing_id: int,
    data: Optional[ClosingReopenRequest] = None,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    PATCH /closing-periods/{id}/reopen:
    Mở lại kỳ chốt sổ để điều chỉnh giao dịch khi được phép.
    """
    reason = data.reason if data else None
    ClosingService.reopen_closing(db, user_id, closing_id, reason=reason)
    return ClosingService.get_closing_period_detail(db, user_id, closing_id)


# =========================================================
# 7. GET CLOSING SETTINGS
# =========================================================
@router.get("/closing-settings", response_model=ClosingSettingResponse)
def get_closing_settings(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    GET /closing-settings:
    Lấy cấu hình tự động chốt sổ và gửi email của người dùng.
    """
    return ClosingService.get_closing_settings(db, user_id)


# =========================================================
# 8. UPDATE CLOSING SETTINGS
# =========================================================
@router.put("/closing-settings", response_model=ClosingSettingResponse)
def update_closing_settings(
    data: ClosingSettingUpdateRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    PUT /closing-settings:
    Cập nhật thời gian, bật/tắt tự động chốt sổ và gửi email báo cáo.
    """
    update_dict = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data.dict(exclude_unset=True)
    return ClosingService.update_closing_settings(
        db=db,
        user_id=user_id,
        update_data=update_dict
    )


# =========================================================
# 9. GET CLOSING REPORTS HISTORY
# =========================================================
@router.get("/closing-reports", response_model=List[ClosingReportResponse])
def get_closing_reports(
    closing_id: Optional[int] = Query(None),
    status_val: Optional[str] = Query(None, alias="status"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    GET /closing-reports:
    Xem lịch sử gửi email báo cáo sau khi chốt sổ.
    """
    return ClosingService.get_closing_reports(
        db=db,
        user_id=user_id,
        closing_id=closing_id,
        status_val=status_val
    )


# =========================================================
# 10. RESEND CLOSING REPORT EMAIL
# =========================================================
@router.post("/closing-reports/{report_id}/resend")
def resend_closing_report(
    report_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    POST /closing-reports/{id}/resend:
    Thử gửi lại email báo cáo chốt sổ khi bị lỗi hoặc người dùng yêu cầu gửi lại.
    """
    return ClosingService.resend_closing_report(db, user_id, report_id)


# =========================================================
# 11. WEBSOCKET CLOSING EVENTS
# =========================================================
@router.websocket("/ws/closing")
async def ws_closing_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    WebSocket realtime cho chốt sổ:
    - CLOSING_CONFIRMATION_REQUIRED
    - CLOSING_COMPLETED
    - CLOSING_REPORT_SENT
    - CLOSING_REPORT_FAILED
    """
    try:
        user_id = authenticate_websocket(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect_closing(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_closing(websocket, user_id)
    except Exception:
        ws_manager.disconnect_closing(websocket, user_id)
