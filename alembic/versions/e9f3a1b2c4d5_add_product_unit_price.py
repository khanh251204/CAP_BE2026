"""add unit_price to Product_Unit

Giá bán riêng theo từng đơn vị quy đổi (vd 1 thùng rẻ hơn mua lẻ từng lon).

Revision ID: e9f3a1b2c4d5
Revises: b6e2d4a8c1f0
Create Date: 2026-11-21 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9f3a1b2c4d5'
down_revision: Union[str, None] = 'b6e2d4a8c1f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "Product_Unit"
COLUMN = "unit_price"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(TABLE)}
    if COLUMN not in cols:
        op.add_column(TABLE, sa.Column(COLUMN, sa.Numeric(15, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns(TABLE)}
    if COLUMN in cols:
        op.drop_column(TABLE, COLUMN)
