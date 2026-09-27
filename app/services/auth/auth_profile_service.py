from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.user_repository import (
    get_user_by_id,
    update_user_profile
)
from app.schemas.auth_schema import UpdateProfileRequest
from app.services.auth.auth_registration_service import user_to_dict


def update_user_profile_service(db: Session, user_id: int, data: UpdateProfileRequest):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")

    target_account_type = data.accountType or user.account_type
    target_store_name = data.storeName if data.storeName is not None else user.store_name
    target_business_type = (data.businessField or data.businessType) if (data.businessField or data.businessType) is not None else user.business_type

    if target_account_type == "business":
        if not target_store_name or not str(target_store_name).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên cửa hàng/doanh nghiệp là bắt buộc đối với tài khoản doanh nghiệp"
            )
        if not target_business_type or not str(target_business_type).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lĩnh vực kinh doanh là bắt buộc đối với tài khoản doanh nghiệp"
            )

    try:
        update_user_profile(
            db=db,
            user=user,
            full_name=data.fullName,
            phone_number=data.phone,
            region=data.province,
            account_type=data.accountType,
            store_name=data.storeName,
            business_type=data.businessField or data.businessType,
            province_code=data.provinceCode,
            ward_code=data.wardCode,
            ward_name=data.wardName,
            address_detail=data.addressDetail
        )
        db.commit()
        db.refresh(user)

        return {
            "success": True,
            "message": "Cập nhật thông tin thành công",
            "user": user_to_dict(user)
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Không thể cập nhật thông tin người dùng")
