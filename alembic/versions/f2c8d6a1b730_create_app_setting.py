"""create App_Setting table

Cài đặt toàn hệ thống do admin chỉnh (khoá -> JSON): bật / tắt Audit Log theo chức năng, thời gian giữ log.

Revision ID: f2c8d6a1b730
Revises: e7a4c1b9d205
Create Date: 2026-11-04 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2c8d6a1b730'
down_revision: Union[str, None] = 'e7a4c1b9d205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "App_Setting"


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column("setting_key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table(TABLE)
