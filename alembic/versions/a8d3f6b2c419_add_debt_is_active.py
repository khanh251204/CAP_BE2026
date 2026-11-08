"""add Debt.is_active (xoá mềm khoản nợ)

Revision ID: a8d3f6b2c419
Revises: 9f4b2c7d1e3a
Create Date: 2026-11-08 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8d3f6b2c419'
down_revision: Union[str, None] = '9f4b2c7d1e3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "Debt"
COLUMN = "is_active"


def upgrade() -> None:
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)]
    if COLUMN in cols:
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    cols = [c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)]
    if COLUMN in cols:
        op.drop_column(TABLE, COLUMN)
