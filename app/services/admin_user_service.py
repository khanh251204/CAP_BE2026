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
    AdminUserLockHistoryItem,
    AdminUserLockHistoryResponse,
)
from app.models.user_lock_history_model import UserLockHistory
from app.services.auth.account_lock_service import (
    record_lock_event,
    LOCK,
    UNLOCK,
    REASON_ADMIN_LOCK,
    REASON_ADMIN_UNLOCK,
    REASON_TOO_MANY_FAILED_LOGINS,
    REASON_EMAIL_OTP_UNLOCK,
)

# Nhãn lý do hiển thị cho admin
LOCK_REASON_LABELS = {
    REASON_TOO_MANY_FAILED_LOGINS: "Hệ thống tự khóa do nhập sai mật khẩu nhiều lần",
    REASON_ADMIN_LOCK: "Admin khóa tài khoản",
    REASON_EMAIL_OTP_UNLOCK: "Người dùng tự mở khóa bằng mã xác minh email",
    REASON_ADMIN_UNLOCK: "Admin mở khóa tài khoản",
}


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
        detail = cls.user_to_detail_response(user)
        if detail.status == "LOCKED":
            # Lý do của lần khóa gần nhất
            last_lock = (
                db.query(UserLockHistory)
                .filter(UserLockHistory.user_id == user.user_id, UserLockHistory.action == LOCK)
                .order_by(UserLockHistory.created_at.desc(), UserLockHistory.id.desc())
                .first()
            )
            if last_lock:
                actor = db.get(User, last_lock.actor_id) if last_lock.actor_id else None
                detail.lock_reason_code = last_lock.reason_code
                detail.lock_reason = last_lock.reason or LOCK_REASON_LABELS.get(last_lock.reason_code)
                detail.locked_at = last_lock.created_at
                detail.locked_by_name = actor.full_name if actor else None
        return detail

    @classmethod
    def get_lock_history(cls, db: Session, user_id: int, limit: int = 50) -> AdminUserLockHistoryResponse:
        """Lịch sử khóa / mở khóa của một người dùng, mới nhất trước."""
        if not AdminUserRepository.get_user_by_id(db, user_id=user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng")

        rows = (
            db.query(UserLockHistory)
            .filter(UserLockHistory.user_id == user_id)
            .order_by(UserLockHistory.created_at.desc(), UserLockHistory.id.desc())
            .limit(limit)
            .all()
        )
        actor_ids = {r.actor_id for r in rows if r.actor_id}
        actors = {
            u.user_id: u.full_name
            for u in db.query(User).filter(User.user_id.in_(actor_ids)).all()
        } if actor_ids else {}

        return AdminUserLockHistoryResponse(
            user_id=user_id,
            items=[
                AdminUserLockHistoryItem(
                    id=r.id,
                    action=r.action,
                    reason_code=r.reason_code,
                    reason_label=LOCK_REASON_LABELS.get(r.reason_code, r.reason_code),
                    reason=r.reason,
                    actor_id=r.actor_id,
                    actor_name=actors.get(r.actor_id) if r.actor_id else None,
                    ip_address=r.ip_address,
                    user_agent=r.user_agent,
                    created_at=r.created_at,
                )
                for r in rows
            ],
        )

    @classmethod
    def update_user_status(
        cls,
        db: Session,
        user_id: int,
        current_admin_id: int,
        request: AdminUserStatusUpdateRequest,
        client: Optional[dict] = None
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
            record_lock_event(
                db, user, LOCK, REASON_ADMIN_LOCK,
                reason=(request.reason or "").strip() or None,
                actor_id=current_admin_id,
                client=client,
            )

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
            was_locked = cls.compute_user_status(user) == "LOCKED"
            AdminUserRepository.unlock_user(db, user)
            if was_locked:
                record_lock_event(
                    db, user, UNLOCK, REASON_ADMIN_UNLOCK,
                    reason=(request.reason or "").strip() or None,
                    actor_id=current_admin_id,
                    client=client,
                )
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
