"""
Admin Email Management API:
- Xem thống kê & trạng thái SMTP
- Xem lịch sử gửi email (Email_Log), xem chi tiết nội dung & gửi lại email lỗi
- Gửi email test SMTP & gửi email thủ công (cá nhân / nhóm sắp hết hạn / toàn bộ user)
- Cấu hình tự động gửi email & mẫu tiêu đề / ghi chú
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_admin_area, require_permission
from app.models.email_log_model import EmailLog
from app.schemas.admin_email_schema import (
    AdminEmailSettingsUpdateRequest,
    AdminSendCustomEmailRequest,
    AdminSendTestEmailRequest,
)
from app.services.email_management_service import (
    build_custom_html,
    get_email_settings,
    get_email_stats,
    list_email_logs,
    resolve_recipients,
    serialize_email_log,
    update_email_settings,
)
from app.services.email_service import send_email

router = APIRouter(
    prefix="/admin/emails",
    tags=["Admin Email Management"],
    dependencies=[Depends(require_admin_area)],
)

_read_perm = Depends(require_permission("admin_notification:read"))
_manage_perm = Depends(require_permission("admin_notification:manage"))


@router.get("/stats", dependencies=[_read_perm])
def admin_get_email_stats(db: Session = Depends(get_db)):
    return {"success": True, "data": get_email_stats(db)}


@router.get("/logs", dependencies=[_read_perm])
def admin_list_email_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    email_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    data = list_email_logs(
        db,
        page=page,
        limit=limit,
        search=search,
        email_type=email_type,
        status=status_filter,
    )
    return {"success": True, "data": data["items"], "pagination": data["pagination"]}


@router.get("/logs/{log_id}", dependencies=[_read_perm])
def admin_get_email_log_detail(log_id: int, db: Session = Depends(get_db)):
    row = db.query(EmailLog).filter(EmailLog.email_log_id == log_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bản ghi email")
    return {"success": True, "data": serialize_email_log(row, include_body=True)}


@router.post("/logs/{log_id}/resend", dependencies=[_manage_perm])
def admin_resend_email_log(
    log_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(get_current_user_id),
):
    row = db.query(EmailLog).filter(EmailLog.email_log_id == log_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bản ghi email")

    send_email(
        to_email=row.to_email,
        subject=row.subject,
        text_content=row.text_body or row.subject,
        html_content=row.html_body,
        email_type=row.email_type or "OTHER",
        user_id=row.user_id,
        sent_by=admin_id,
    )
    return {"success": True, "message": f"Đã gửi lại email tới {row.to_email}"}


@router.post("/test", dependencies=[_manage_perm])
def admin_send_test_email(
    payload: AdminSendTestEmailRequest,
    admin_id: int = Depends(get_current_user_id),
):
    to_email = payload.to_email.strip()
    if "@" not in to_email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Địa chỉ email không hợp lệ")

    subject = "[VoiceCashBook] Email kiểm tra kết nối SMTP"
    text_body = (
        "Xin chào,\n\n"
        "Đây là email kiểm tra từ hệ thống quản trị VoiceCashBook.\n"
        "Nếu bạn nhận được email này, cấu hình SMTP đang hoạt động bình thường.\n\n"
        "Trân trọng,\nVoiceCashBook Admin"
    )
    html_body = build_custom_html("Kiểm tra kết nối SMTP thành công", text_body)

    send_email(
        to_email=to_email,
        subject=subject,
        text_content=text_body,
        html_content=html_body,
        email_type="TEST",
        sent_by=admin_id,
    )
    return {"success": True, "message": f"Đã gửi email kiểm tra tới {to_email}"}


@router.post("/send", dependencies=[_manage_perm])
def admin_send_custom_email(
    payload: AdminSendCustomEmailRequest,
    db: Session = Depends(get_db),
    admin_id: int = Depends(get_current_user_id),
):
    recipients = resolve_recipients(db, payload.mode, payload.to_emails)
    if not recipients:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Không tìm thấy địa chỉ email người nhận phù hợp",
        )

    html_body = build_custom_html(payload.subject, payload.body_text)
    sent_count = 0
    failed_count = 0
    errors = []

    for rec in recipients:
        try:
            send_email(
                to_email=rec["email"],
                subject=payload.subject,
                text_content=payload.body_text,
                html_content=html_body,
                email_type="CUSTOM",
                user_id=rec["user_id"],
                sent_by=admin_id,
            )
            sent_count += 1
        except Exception as exc:
            failed_count += 1
            detail = getattr(exc, "detail", None) or str(exc)
            errors.append({"email": rec["email"], "error": detail})

    return {
        "success": True,
        "message": f"Đã gửi {sent_count}/{len(recipients)} email",
        "data": {
            "total": len(recipients),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "errors": errors[:10],
        },
    }


@router.get("/settings", dependencies=[_read_perm])
def admin_get_email_settings(db: Session = Depends(get_db)):
    return {"success": True, "data": get_email_settings(db)}


@router.put("/settings", dependencies=[_manage_perm])
def admin_update_email_settings(
    payload: AdminEmailSettingsUpdateRequest,
    db: Session = Depends(get_db),
    admin_id: int = Depends(get_current_user_id),
):
    updated = update_email_settings(db, payload.model_dump(exclude_unset=True), admin_id=admin_id)
    return {"success": True, "data": updated, "message": "Đã cập nhật cấu hình email"}


@router.post("/run-auto-reminders", dependencies=[_manage_perm])
def admin_run_auto_reminders(db: Session = Depends(get_db)):
    """Chạy ngay toàn bộ quy tắc gửi mail tự động (sắp hết hạn + mời gia hạn lại)."""
    from app.services.ai_subscription_email_service import run_all_scheduled_reminders

    res = run_all_scheduled_reminders(db=db)
    return {
        "success": True,
        "message": (
            f"Đã gửi {res['total_sent']}/{res['total_checked']} email tự động "
            f"(sắp hết hạn: {res['expiry']['sent_count']}, mời gia hạn: {res['renewal']['sent_count']})"
        ),
        "data": res,
    }
