from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.configs.database import Base


class DebtPayment(Base):
    __tablename__ = "Debt_Payment"

    payment_id = Column(Integer, primary_key=True, autoincrement=True)

    debt_id = Column(
        Integer,
        ForeignKey("Debt.debt_id"),
        nullable=False
    )

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id"),
        nullable=False
    )

    account_id = Column(
        Integer,
        ForeignKey("Account.account_id"),
        nullable=False
    )

    amount = Column(Numeric(15, 2), nullable=False)

    # = amount / Debt.total_debt  (lưu tỉ lệ %)
    payment_percentage = Column(Numeric(5, 2), nullable=True)

    payment_date = Column(DateTime, nullable=False, default=datetime.now)

    note = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=True, default=datetime.now)

    # ------------ relationships ------------
    debt = relationship("Debt", back_populates="payments")
    transaction = relationship("Transaction", back_populates="debt_payments")
    account = relationship("Account", back_populates="debt_payments")
