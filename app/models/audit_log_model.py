from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, JSON, String, text

from app.configs.database import Base


class AuditLog(Base):
    """
    Vết kiểm toán (Audit Log): ai làm gì với giao dịch nào, trước / sau ra sao.

    Ghi tự động bằng sự kiện ORM (app/services/audit_service.py) mỗi khi Transaction hoặc
    Transaction_Detail được tạo / sửa / xoá, nên mọi đường vào (giọng nói, nhập tay, nợ, admin...)
    đều có vết. Ghi cùng database transaction với thao tác gốc: thao tác rollback thì vết cũng rollback.

    Không có khoá ngoại để vết vẫn còn sau khi giao dịch / người dùng bị xoá. Không bị dọn tự động
    như system_logs.
    """
    __tablename__ = "Audit_Log"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True,
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    # TRANSACTION | TRANSACTION_DETAIL | DEBT | DEBT_PAYMENT | INVENTORY
    entity_type = Column(String(30), nullable=False, index=True)
    entity_id = Column(Integer, nullable=True)
    # Giao dịch cha (với dòng chi tiết) hoặc chính giao dịch: để xem toàn bộ lịch sử một giao dịch
    transaction_id = Column(Integer, nullable=True, index=True)
    # CREATE | UPDATE | DELETE
    action = Column(String(10), nullable=False, index=True)

    # Chủ dữ liệu (user sở hữu giao dịch) và người thực hiện (có thể là admin)
    owner_user_id = Column(Integer, nullable=True, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    # USER | ADMIN | SYSTEM (tác vụ nền: chốt sổ tự động, nhắc nợ...)
    actor_role = Column(String(10), nullable=False, default="SYSTEM")
    # VOICE | MANUAL | ... (cách nhập của giao dịch, nếu có)
    source = Column(String(20), nullable=True)

    request_id = Column(String(64), nullable=True, index=True)
    api_path = Column(String(255), nullable=True)
    http_method = Column(String(10), nullable=True)

    before_data = Column(JSON, nullable=True)
    after_data = Column(JSON, nullable=True)
    # {"tên_trường": {"before": ..., "after": ...}} chỉ với UPDATE
    changes = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_audit_log_tx_created", "transaction_id", "created_at"),
    )
