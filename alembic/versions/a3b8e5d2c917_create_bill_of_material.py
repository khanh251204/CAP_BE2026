"""create Bill_Of_Material table

Định mức nguyên vật liệu (BOM) cho PRODUCER: thành phẩm -> danh sách nguyên liệu.

Revision ID: a3b8e5d2c917
Revises: 9f4b2c7d1e3a
Create Date: 2026-11-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b8e5d2c917'
down_revision: Union[str, None] = '9f4b2c7d1e3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "Bill_Of_Material"


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column("bom_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("User.user_id"), nullable=False),
        sa.Column("finished_product_id", sa.Integer(), sa.ForeignKey("Product.product_id"), nullable=False),
        sa.Column("material_product_id", sa.Integer(), sa.ForeignKey("Product.product_id"), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(15, 4), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "user_id", "finished_product_id", "material_product_id",
            name="uq_bom_user_finished_material",
        ),
    )
    op.create_index("ix_Bill_Of_Material_user_id", TABLE, ["user_id"])
    op.create_index("ix_Bill_Of_Material_finished_product_id", TABLE, ["finished_product_id"])


def downgrade() -> None:
    op.drop_table(TABLE)
