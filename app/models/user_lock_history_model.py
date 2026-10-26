from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, text

from app.configs.database import Base


class UserLockHistory(Base):
    """
    Lịch sử khóa / mở khóa tài khoản: admin xem được ai, khi nào, vì sao.

    action:      LOCK | UNLOCK
    reason_code: TOO_MANY_FAILED_LOGINS (hệ thống khóa do sai mật khẩu)
                 ADMIN_LOCK              (admin khóa tay)
                 EMAIL_OTP_UNLOCK        (người dùng tự mở bằng mã email)
                 ADMIN_UNLOCK            (admin mở khóa)
    """
    __tablename__ = "User_Lock_History"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    action = Column(String(20), nullable=False)
    reason_code = Column(String(50), nullable=False)
    # Lý do hiển thị cho admin (admin nhập, hoặc hệ thống tự ghi)
    reason = Column(Text, nullable=True)

    # Admin thực hiện; NULL = hệ thống / chính người dùng
    actor_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="SET NULL"),
        nullable=True
    )

    # Nơi phát sinh (lần đăng nhập sai cuối cùng, hoặc nơi admin thao tác)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True
    )
