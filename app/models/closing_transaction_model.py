from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.configs.database import Base


class ClosingTransaction(Base):
    __tablename__ = "closing_transaction"

    closing_id = Column(
        BigInteger,
        ForeignKey("closing_period.closing_id", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )

    transaction_id = Column(
        Integer,
        ForeignKey("Transaction.transaction_id", ondelete="RESTRICT"),
        primary_key=True,
        index=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now
    )

    # Relationships
    closing_period = relationship("ClosingPeriod", back_populates="closing_transactions")
    transaction = relationship("Transaction", backref="closing_links")
