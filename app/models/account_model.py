from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    Enum,
    Boolean,
    DateTime
)
from sqlalchemy.orm import relationship

from app.configs.database import Base

class Account(Base):
    __tablename__ = "Account"
    account_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("User.user_id"), nullable=True)
    name = Column(String(255), nullable=False)
    type = Column(
        Enum (
            "CASH",
            "BANK",
            "E-WALLET"
        ),
        nullable=False
    )
    balance = Column(
        Numeric(15, 2),
        nullable=False
    )
    currency= Column(
        String(255),
        nullable=False
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True
    )
    created_at = Column(DateTime,nullable=False)
    updated_at = Column(DateTime, nullable=False)

    transactions = relationship(
                "Transaction",
                back_populates="account"
            )
    user = relationship(
                "User",
                back_populates="account"
            )