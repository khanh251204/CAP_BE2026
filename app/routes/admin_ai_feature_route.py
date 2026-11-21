"""
Admin API quản lý gói AI & phân quyền intent theo từng tài khoản.

- Cho phép Admin tạo/sửa/xóa các gói AI (VD: gói 50k chỉ 2 intent `ban_hang`, `mua_hang`).
- Cho phép Admin gán gói hoặc chọn trực tiếp từng intent + multi-item + OCR cho từng tài khoản.
- Hiển thị ước lượng % giảm prompt / token cho từng gói và từng tài khoản.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.configs.database import get_db
from app.configs.jwt import get_current_user_id, require_admin_area, require_permission
from app.schemas.admin_ai_feature_schema import (
    AdminAIPlanUpsertRequest,
    AdminBulkAssignAIFeatureRequest,
    AdminUserAIFeatureUpdateRequest,
)
from app.services import ai_feature_service
from app.services.system_log_service import log_event

router = APIRouter(
    prefix="/admin/ai-features",
    tags=["Admin - AI Feature & Plan Management"],
    dependencies=[Depends(require_admin_area)],
)

_read_perm = Depends(require_permission("admin_user:read"))
_manage_perm = Depends(require_permission("admin_user:manage"))


@router.get(
    "/catalog",
    summary="Danh mục 17 AI Intents & các gói hiện có",
    description="Trả về danh mục đầy đủ 17 intent (tên, nhóm, alias, mô tả) và các gói dịch vụ kèm thống kê tiết kiệm prompt/token.",
    dependencies=[_read_perm],
)
def get_ai_catalog(db: Session = Depends(get_db)):
    plans = ai_feature_service.get_plans(db)
    return {
        "success": True,
        "data": {
            "intents": ai_feature_service.INTENT_CATALOG,
            "plans": [ai_feature_service.annotate_plan_with_stats(p) for p in plans.values()],
        },
    }


@router.get(
    "/plans",
    summary="Danh sách gói AI",
    dependencies=[_read_perm],
)
def list_ai_plans(db: Session = Depends(get_db)):
    plans = ai_feature_service.get_plans(db)
    return {
        "success": True,
        "data": [ai_feature_service.annotate_plan_with_stats(p) for p in plans.values()],
    }


@router.put(
    "/plans/{plan_code}",
    summary="Tạo mới hoặc cập nhật gói AI",
    description="VD: Tạo gói `basic_50k` chỉ mở `['ban_hang', 'mua_hang']`, tắt multi-item & OCR.",
    dependencies=[_manage_perm],
)
def upsert_ai_plan(
    plan_code: str,
    body: AdminAIPlanUpsertRequest,
    current_admin_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        data = ai_feature_service.upsert_plan(
            db=db,
            plan_code=plan_code,
            name=body.name,
            price_vnd=body.price_vnd,
            description=body.description,
            allowed_intents=body.allowed_intents,
            allow_multi_item=body.allow_multi_item,
            allow_ocr=body.allow_ocr,
            admin_id=current_admin_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    log_event(
        "INFO",
        "ADMIN",
        f"Admin cập nhật gói AI '{plan_code}'",
        detail={"plan_code": plan_code, "allowed_intents": body.allowed_intents},
        user_id=current_admin_id,
    )
    return {"success": True, "data": data}


@router.delete(
    "/plans/{plan_code}",
    summary="Xóa gói AI tự tạo",
    dependencies=[_manage_perm],
)
def delete_ai_plan(
    plan_code: str,
    current_admin_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        deleted = ai_feature_service.delete_plan(db=db, plan_code=plan_code, admin_id=current_admin_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy gói '{plan_code}'")

    log_event("INFO", "ADMIN", f"Admin xóa gói AI '{plan_code}'", user_id=current_admin_id)
    return {"success": True, "message": f"Đã xóa gói '{plan_code}'"}


@router.get(
    "/users",
    summary="Danh sách cấu hình AI theo tài khoản",
    description="Lọc theo từ khóa (tên/email/SĐT) hoặc `plan_code` (vd: `basic_50k`, `standard`, `pro`, `custom`, `default`).",
    dependencies=[_read_perm],
)
def list_user_ai_features(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    plan_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    data = ai_feature_service.list_user_ai_features(
        db=db, page=page, limit=limit, search=search, plan_code=plan_code
    )
    return {"success": True, "data": data["items"], "pagination": data["pagination"]}


@router.get(
    "/users/{user_id}",
    summary="Xem cấu hình AI của 1 tài khoản",
    dependencies=[_read_perm],
)
def get_user_ai_feature(user_id: int, db: Session = Depends(get_db)):
    data = ai_feature_service.get_user_ai_feature_detail(db=db, user_id=user_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")
    return {"success": True, "data": data}


@router.put(
    "/users/{user_id}",
    summary="Gán gói hoặc tùy chỉnh intent AI cho tài khoản",
    description=(
        "Gửi `{\"plan_code\": \"basic_50k\"}` để áp nhanh gói 50k (2 intent), hoặc gửi "
        "`{\"allowed_intents\": [\"ban_hang\", \"mua_hang\", \"chi_phi\"], \"allow_multi_item\": false, \"allow_ocr\": false}` "
        "để bật/tắt tùy chỉnh từng chức năng. Có hiệu lực ngay lập tức (xóa cache)."
    ),
    dependencies=[_manage_perm],
)
def update_user_ai_feature(
    user_id: int,
    body: AdminUserAIFeatureUpdateRequest,
    current_admin_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Phân biệt giữa "không gửi field allowed_intents" vs "gửi allowed_intents: null" (reset về full)
    intents_arg = body.allowed_intents if "allowed_intents" in body.model_fields_set else ...
    try:
        data = ai_feature_service.set_user_ai_feature(
            db=db,
            user_id=user_id,
            plan_code=body.plan_code,
            allowed_intents=intents_arg,
            allow_multi_item=body.allow_multi_item,
            allow_ocr=body.allow_ocr,
            note=body.note,
            admin_id=current_admin_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")

    log_event(
        "INFO",
        "ADMIN",
        f"Admin cập nhật quyền AI cho user_id={user_id}",
        detail={
            "target_user_id": user_id,
            "plan_code": data["plan_code"],
            "allowed_intents": data["allowed_intents"],
            "allow_multi_item": data["allow_multi_item"],
            "allow_ocr": data["allow_ocr"],
        },
        user_id=current_admin_id,
    )
    return {"success": True, "data": data}


@router.post(
    "/users/bulk-assign",
    summary="Gán gói / quyền AI hàng loạt cho nhiều tài khoản",
    dependencies=[_manage_perm],
)
def bulk_assign_ai_features(
    body: AdminBulkAssignAIFeatureRequest,
    current_admin_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    intents_arg = body.allowed_intents if "allowed_intents" in body.model_fields_set else ...
    try:
        result = ai_feature_service.bulk_assign_user_ai_features(
            db=db,
            user_ids=body.user_ids,
            plan_code=body.plan_code,
            allowed_intents=intents_arg,
            allow_multi_item=body.allow_multi_item,
            allow_ocr=body.allow_ocr,
            note=body.note,
            admin_id=current_admin_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    log_event(
        "INFO",
        "ADMIN",
        f"Admin gán quyền AI hàng loạt ({result['updated_count']} tài khoản)",
        detail={"plan_code": body.plan_code, "updated_count": result["updated_count"]},
        user_id=current_admin_id,
    )
    return {"success": True, "data": result}


@router.delete(
    "/users/{user_id}",
    summary="Khôi phục quyền AI mặc định (không giới hạn) cho tài khoản",
    dependencies=[_manage_perm],
)
def reset_user_ai_feature(
    user_id: int,
    current_admin_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    data = ai_feature_service.reset_user_ai_feature(db=db, user_id=user_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")
    log_event("INFO", "ADMIN", f"Admin khôi phục quyền AI mặc định cho user_id={user_id}", user_id=current_admin_id)
    return {"success": True, "data": data}
