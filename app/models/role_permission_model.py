from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, text
from sqlalchemy.orm import relationship

from app.configs.database import Base

# Bảng trung gian Role_Permission (Many-to-Many giữa Role và Permission)
role_permissions = Table(
    "Role_Permission",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("Role.role_id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("Permission.permission_id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "Role"

    role_id = Column(Integer, primary_key=True, autoincrement=True)
    role_name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Quan hệ N-N với Permission
    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin"
    )

    # Quan hệ 1-N với User
    users = relationship("User", back_populates="role_rel")


class Permission(Base):
    __tablename__ = "Permission"

    permission_id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), nullable=False, unique=True, index=True)
    module = Column(String(50), nullable=False, index=True)  # USER, PRODUCT, TRANSACTION, REPORT, SYSTEM...
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    # Quan hệ N-N với Role
    roles = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions",
        lazy="selectin"
    )
