import math
from datetime import datetime
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user_model import User
from app.repositories.admin_user_repository import AdminUserRepository
from app.repositories.refresh_token_repository import revoke_all_user_refresh_tokens
from app.schemas.admin_user_schema import (
    AdminUserPagination,
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserDetailResponse,
    AdminUserStatusUpdateRequest,
    AdminUserStatusUpdateResponse,
)


class AdminUserService:

    @staticmethod
    def compute_user_status(user: User, now: Optional[datetime] = None) -> str:
        """
        Xác định trạng thái hoạt động của người dùng từ các trường sẵn có trong ERD:
        - LOCKED: nếu lock_until tồn tại và lớn hơn thời điểm hiện tại.
        - ACTIVE: nếu đã xác thực (is_verified = True) và không bị khóa.
        - UNVERIFIED: nếu chưa xác thực email (is_verified = False) và không bị khóa.
        """
        current_time = now or datetime.utcnow()
        if user.lock_until and user.lock_until > current_time:
            return "LOCKED"
        if user.is_verified:
            return "ACTIVE"
        return "UNVERIFIED"

    @classmethod
    def user_to_list_item(cls, user: User, now: Optional[datetime] = None) -> AdminUserListItem:
        user_status = cls.compute_user_status(user, now)
        return AdminUserListItem(
            id=user.user_id,
            user_id=user.user_id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            role=user.role,
            status=user_status,
            business_type=user.business_type,
            account_type=user.account_type or "personal",
            store_name=user.store_name,
            region=user.region,
            is_verified=bool(user.is_verified),
            lock_until=user.lock_until,
            created_at=user.created_at
        )

    @classmethod
    def user_to_detail_response(cls, user: User, now: Optional[datetime] = None) -> AdminUserDetailResponse:
        user_status = cls.compute_user_status(user, now)
        return AdminUserDetailResponse(
            id=user.user_id,
            user_id=user.user_id,
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            role=user.role,
            status=user_status,
            business_type=user.business_type,
            account_type=user.account_type or "personal",
            store_name=user.store_name,
            region=user.region,
            province_code=user.province_code,
            ward_code=user.ward_code,
            ward_name=user.ward_name,
            address_detail=user.address_detail,
            is_verified=bool(user.is_verified),
            failed_attempts=user.failed_attempts or 0,
            lock_until=user.lock_until,
            created_at=user.created_at
        )

    @classmethod
    def list_users(
        cls,
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
        status_filter: Optional[str] = None,
        business_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> AdminUserListResponse:
        # Validate phân trang
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tham số 'page' phải lớn hơn hoặc bằng 1"
            )
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tham số 'limit' phải nằm trong khoảng từ 1 đến 100"
            )

        # Validate khoảng thời gian
        if from_date and to_date and from_date > to_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Thời gian bắt đầu 'from' không được lớn hơn thời gian kết thúc 'to'"
            )

        # Validate status filter
        if status_filter and status_filter.strip():
            valid_statuses = {"ACTIVE", "LOCKED", "UNVERIFIED", "INACTIVE", "PENDING"}
            if status_filter.strip().upper() not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Trạng thái lọc '{status_filter}' không hợp lệ. Hỗ trợ: ACTIVE, LOCKED, UNVERIFIED"
                )

        users, total_count = AdminUserRepository.get_users(
            db=db,
            page=page,
            limit=limit,
            search=search,
            role=role,
            status=status_filter,
            business_type=business_type,
            from_date=from_date,
            to_date=to_date
        )

        now = datetime.utcnow()
        items = [cls.user_to_list_item(u, now) for u in users]
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 0

        return AdminUserListResponse(
            items=items,
            pagination=AdminUserPagination(
                page=page,
                limit=limit,
                total=total_count,
                total_pages=total_pages
            )
        )

    @classmethod
    def get_user_detail(
        cls,
        db: Session,
        user_id: int
    ) -> AdminUserDetailResponse:
        user = AdminUserRepository.get_user_by_id(db, user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )
        return cls.user_to_detail_response(user)

    @classmethod
    def update_user_status(
        cls,
        db: Session,
        user_id: int,
        current_admin_id: int,
        request: AdminUserStatusUpdateRequest
    ) -> AdminUserStatusUpdateResponse:
        user = AdminUserRepository.get_user_by_id(db, user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy người dùng"
            )

        raw_status = request.status.strip().upper()

        # Chỉ ADMIN mới được khóa / mở khóa tài khoản ADMIN khác
        from app.services.permission_service import PermissionService
        actor = PermissionService.get_user_access(current_admin_id, db)
        if (user.role or "").upper() == "ADMIN" and not actor.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ ADMIN mới được thay đổi trạng thái tài khoản ADMIN"
            )

        if raw_status in ("LOCKED", "LOCK"):
            if user.user_id == current_admin_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Không thể tự khóa tài khoản của chính mình"
                )

            # Khóa tài khoản: gán lock_until xa trong tương lai (năm 2099)
            lock_until = datetime(2099, 12, 31, 23, 59, 59)
            AdminUserRepository.lock_user(db, user, lock_until=lock_until)

            # Vô hiệu hóa toàn bộ refresh token hiện có của user này để ngắt phiên đăng nhập
            revoke_all_user_refresh_tokens(db, user_id=user.user_id, revoked_at=datetime.utcnow())
            db.commit()
            db.refresh(user)
            # Trạng thái khóa được kiểm tra ở mỗi request -> xóa cache để có hiệu lực ngay
            PermissionService.clear_cache(user.user_id)

            return AdminUserStatusUpdateResponse(
                success=True,
                message=f"Đã khóa tài khoản người dùng {user.full_name} thành công",
                user_id=user.user_id,
                status="LOCKED",
                lock_until=user.lock_until
            )

        elif raw_status in ("ACTIVE", "UNLOCKED", "UNLOCK"):
            AdminUserRepository.unlock_user(db, user)
            db.commit()
            db.refresh(user)
            # Trạng thái khóa được kiểm tra ở mỗi request -> xóa cache để có hiệu lực ngay
            PermissionService.clear_cache(user.user_id)

            return AdminUserStatusUpdateResponse(
                success=True,
                message=f"Đã mở khóa tài khoản người dùng {user.full_name} thành công",
                user_id=user.user_id,
                status=cls.compute_user_status(user),
                lock_until=None
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Giá trị 'status' không hợp lệ. Vui lòng sử dụng 'LOCKED' hoặc 'ACTIVE'"
            )
