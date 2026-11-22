"""Transaction_Detail.quantity lưu 2 chữ số lẻ (bán theo cân); gộp 2 nhánh migration

Trước đây cột là DECIMAL(15,0) nên bán 0,3 kg lưu thành 0, 2,5 kg thành 2 hoặc 3,
trong khi kho (Inventory_Transaction) đã lưu đúng 2 chữ số lẻ.

Đồng thời gộp 2 head đang tách nhánh từ a3b8e5d2c917 (c5d1f7a9e3b2 Product_Unit và
f2c8d6a1b730 App_Setting) để `alembic upgrade head` chạy được.

Revision ID: b6e2d4a8c1f0
Revises: c5d1f7a9e3b2, f2c8d6a1b730
Create Date: 2026-11-17 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b6e2d4a8c1f0'
down_revision: Union[str, Sequence[str], None] = ('c5d1f7a9e3b2', 'f2c8d6a1b730')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "Transaction_Detail"
COLUMN = "quantity"


def _quantity_column():
    cols = {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns(TABLE)}
    return cols.get(COLUMN)


def upgrade() -> None:
    col = _quantity_column()
    if col is None:
        return
    scale = getattr(col["type"], "scale", None)
    if scale is not None and scale >= 2:
        return
    op.alter_column(
        TABLE, COLUMN,
        existing_type=col["type"],
        type_=sa.Numeric(15, 2),
        existing_nullable=False,
    )


def downgrade() -> None:
    col = _quantity_column()
    if col is None:
        return
    op.alter_column(
        TABLE, COLUMN,
        existing_type=col["type"],
        type_=sa.Numeric(15, 0),
        existing_nullable=False,
    )
