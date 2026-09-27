from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    Enum,
    Date,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.configs.database import Base


class ClosingPeriod(Base):
    __tablename__ = "closing_period"

    closing_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("User.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    period_type = Column(
        Enum("DAY", "MONTH", "QUARTER", "YEAR", name="closing_period_type_enum"),
        nullable=False
    )

    period_start = Column(
        Date,
        nullable=False
    )

    period_end = Column(
        Date,
        nullable=False
    )

    total_sales = Column(
        Numeric(15, 2),
        nullable=False,
        default=0.00
    )

    total_purchase = Column(
        Numeric(15, 2),
        nullable=False,
        default=0.00
    )

    total_income = Column(
        Numeric(15, 2),
        nullable=False,
        default=0.00
    )

    total_expense = Column(
        Numeric(15, 2),
        nullable=False,
        default=0.00
    )

    total_receivable = Column(
        Numeric(15, 2),
        nullable=False,
        default=0.00
    )

    total_payable = Column(
        Numeric(15, 2),
        nullable=False,
        default=0.00
    )

    total_inventory_value = Column(
        Numeric(15, 2),
        nullable=True,
        default=0.00
    )

    status = Column(
        Enum("CLOSED", "REOPENED", "OPEN", name="closing_status_enum"),
        nullable=False,
        default="CLOSED"
    )

    note = Column(
        Text,
        nullable=True
    )

    closed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now
    )

    # Unique Constraint: Duplicate protection - Không cho phép chốt trùng một kỳ của cùng một user
    __table_args__ = (
        UniqueConstraint("user_id", "period_type", "period_start", "period_end", name="uk_user_closing_period"),
    )

    # Relationships
    user = relationship("User", backref="closing_periods")
    closing_transactions = relationship("ClosingTransaction", back_populates="closing_period", cascade="all, delete-orphan")
    closing_reports = relationship("ClosingReport", back_populates="closing_period", cascade="all, delete-orphan")
