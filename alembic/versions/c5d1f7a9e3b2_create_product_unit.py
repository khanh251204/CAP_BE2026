"""create Product_Unit table

Đơn vị quy đổi của sản phẩm: 1 gói = 1000 g, 1 thùng = 24 lon...

Revision ID: c5d1f7a9e3b2
Revises: a3b8e5d2c917
Create Date: 2026-11-04 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d1f7a9e3b2'
down_revision: Union[str, None] = 'a3b8e5d2c917'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "Product_Unit"


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column("product_unit_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("User.user_id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("Product.product_id"), nullable=False),
        sa.Column("unit_name", sa.String(length=50), nullable=False),
        sa.Column("factor", sa.Numeric(15, 4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("product_id", "unit_name", name="uq_product_unit_name"),
    )
    op.create_index("ix_Product_Unit_user_id", TABLE, ["user_id"])
    op.create_index("ix_Product_Unit_product_id", TABLE, ["product_id"])


def downgrade() -> None:
    op.drop_table(TABLE)
