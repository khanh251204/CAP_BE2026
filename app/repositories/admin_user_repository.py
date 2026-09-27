from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.models.user_model import User


class AdminUserRepository:

    @staticmethod
    def get_users(
        db: Session,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        business_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Tuple[List[User], int]:
        """
        Truy vấn danh sách người dùng phía database với Search, Filter và Pagination tối ưu.
        Trả về: (users, total_count)
        """
        query = db.query(User)
        filters = []
        now = datetime.utcnow()

        # 1. Search (full_name, email, phone_number, store_name)
        if search and search.strip():
            kw = f"%{search.strip()}%"
            filters.append(
                or_(
                    User.full_name.ilike(kw),
                    User.email.ilike(kw),
                    User.phone_number.ilike(kw),
                    User.store_name.ilike(kw)
                )
            )

        # 2. Filter theo Role
        if role and role.strip():
            filters.append(User.role.ilike(role.strip()))

        # 3. Filter theo Business Type
        if business_type and business_type.strip():
            filters.append(User.business_type.ilike(business_type.strip()))

        # 4. Filter theo Status (sử dụng lock_until và is_verified có sẵn trong ERD)
        if status and status.strip():
            clean_status = status.strip().upper()
            if clean_status == "LOCKED":
                filters.append(
                    and_(
                        User.lock_until.isnot(None),
                        User.lock_until > now
                    )
                )
            elif clean_status == "ACTIVE":
                filters.append(
                    and_(
                        User.is_verified.is_(True),
                        or_(
                            User.lock_until.is_(None),
                            User.lock_until <= now
                        )
                    )
                )
            elif clean_status in ("UNVERIFIED", "INACTIVE", "PENDING"):
                filters.append(
                    and_(
                        User.is_verified.is_(False),
                        or_(
                            User.lock_until.is_(None),
                            User.lock_until <= now
                        )
                    )
                )

        # 5. Filter theo khoảng thời gian tạo
        if from_date is not None:
            filters.append(User.created_at >= from_date)
        if to_date is not None:
            filters.append(User.created_at <= to_date)

        if filters:
            query = query.filter(and_(*filters))

        # Đếm tổng số bản ghi thỏa điều kiện lọc trực tiếp tại database
        total_count = query.with_entities(func.count(User.user_id)).scalar() or 0

        # Phân trang và sắp xếp giảm dần theo thời gian tạo
        offset = (page - 1) * limit
        users = (
            query
            .order_by(User.created_at.desc(), User.user_id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return users, total_count

    @staticmethod
    def get_user_by_id(
        db: Session,
        user_id: int
    ) -> Optional[User]:
        """
        Lấy thông tin người dùng theo ID.
        """
        return db.query(User).filter(User.user_id == user_id).first()

    @staticmethod
    def lock_user(
        db: Session,
        user: User,
        lock_until: datetime
    ) -> User:
        """
        Khóa tài khoản người dùng bằng cách gán lock_until trong tương lai.
        """
        user.lock_until = lock_until
        db.flush()
        return user

    @staticmethod
    def unlock_user(
        db: Session,
        user: User
    ) -> User:
        """
        Mở khóa tài khoản người dùng bằng cách xóa lock_until và reset failed_attempts.
        """
        user.lock_until = None
        user.failed_attempts = 0
        db.flush()
        return user
